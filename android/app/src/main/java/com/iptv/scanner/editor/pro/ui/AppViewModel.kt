package com.iptv.scanner.editor.pro.ui

import android.app.Application
import android.content.ContentValues
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgList
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.data.IptvEpgSource
import com.iptv.scanner.editor.pro.data.IptvGroup
import com.iptv.scanner.editor.pro.data.IptvRepository
import com.iptv.scanner.editor.pro.data.IptvSource
import com.iptv.scanner.editor.pro.data.IptvStatus
import com.iptv.scanner.editor.pro.data.MappingEntry
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.ResumeItem
import com.iptv.scanner.editor.pro.data.BookmarkItem
import com.iptv.scanner.editor.pro.data.ScanResult
import com.iptv.scanner.editor.pro.data.ScanStatus
import com.iptv.scanner.editor.pro.data.SubtitleItem
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.mpv.MpvController
import com.iptv.scanner.editor.pro.player.CatchupHelper
import com.iptv.scanner.editor.pro.player.CatchupProgram
import com.iptv.scanner.editor.pro.player.ExoPlayerController
import com.iptv.scanner.editor.pro.player.IjkController
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.PlaybackState
import com.iptv.scanner.editor.pro.player.Player
import com.iptv.scanner.editor.pro.player.PlayerCapabilities
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.player.VlcController
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import org.json.JSONArray
import org.json.JSONObject

/**
 * 应用级 ViewModel：管理全局状态（初始化、频道列表、当前播放、catchup/timeshift、面板开关）。
 *
 * 设计要点：
 * 1. 持有 [IptvRepository]、[MpvController]、[UserPrefs] 引用，作为 UI 层与数据/播放/偏好层的桥梁
 * 2. 所有状态用 StateFlow 暴露，Compose 自动观察
 * 3. 初始化流程：initContext → 轮询 getStatus 直到加载完成或超时 → loadChannels
 * 4. 频道切换：playChannel 调用 mpv.playFile，同时重置 catchup/timeshift 状态并预取 EPG
 * 5. catchup/timeshift：与 PC 端 controllers/catchup_controller.py 对齐
 *    - startCatchup(program)：EPG 过去节目点击触发
 *    - startLiveTimeshift(sliderSec)：直播进度条超出缓冲触发
 *    - exitCatchup()：退出回看/时移，恢复原始频道直播
 *
 * 状态机（与 PC 端 core/play_state.py PlayMode 对齐）：
 * - IDLE → LIVE（playChannel）
 * - LIVE → CATCHUP（startCatchup）
 * - LIVE → TIMESHIFT（startLiveTimeshift）
 * - CATCHUP/TIMESHIFT → LIVE（exitCatchup）
 * - 任意 → IDLE（stopPlay）
 */
class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val repository = IptvRepository.getInstance()
    private val userPrefs = UserPrefs.getInstance().also { it.init(app) }

    // -----------------------------------------------------------------
    // 多播放器架构：MPV / ExoPlayer / VLC / IJK 可切换
    //
    // - mpvSingleton：MpvController 单例（始终保留，用于 setVoAndHwdec 等 mpv 专属 API）
    // - _player：当前活跃的 Player 实例（默认 mpvSingleton，切换时换实例）
    // - mpv：公共字段（类型为 Player 接口），保留字段名以避免大规模 UI 改动
    //   所有 Player 接口方法都可通过 mpv.xxx 调用
    // - playerType：当前播放器类型（持久化，下次启动自动恢复）
    // - playerCapabilities：当前播放器能力（UI 据此决定哪些功能面板可用）
    // -----------------------------------------------------------------
    private val mpvSingleton: MpvController = MpvController.getInstance()

    private val _player = MutableStateFlow<Player>(mpvSingleton)

    /** 当前播放器实例（Player 接口类型，UI 用 mpv.xxx 调用 Player 接口方法） */
    val mpv: Player get() = _player.value

    private val _playerType = MutableStateFlow(
        runCatching { PlayerType.valueOf(userPrefs.getPlayerType()) }.getOrDefault(PlayerType.MPV)
    )
    val playerType: StateFlow<PlayerType> = _playerType.asStateFlow()

    val playerCapabilities: StateFlow<PlayerCapabilities> =
        _player.map { it.capabilities }
            .stateIn(viewModelScope, SharingStarted.Eagerly, mpvSingleton.capabilities)

    /**
     * 切换播放器：保存当前播放状态 → detach 旧实例 → 创建新实例 → 通知 View 重建。
     *
     * View 重建由 MainPlayerScreen 监听 playerType 变化触发（key(playerType) 强制 AndroidView 重建）。
     * 重建后调用 [consumePendingRestore] 获取保存的状态，在 attachView 完成后调用
     * restorePlaybackState 恢复进度。
     *
     * @param newType 目标播放器类型
     */
    fun switchPlayer(newType: PlayerType) {
        if (_playerType.value == newType) return
        val oldPlayer = _player.value
        // 1. 保存当前播放状态（url + timePos）
        val savedState = oldPlayer.savePlaybackState()
        // 2. detach 旧实例（释放资源）
        oldPlayer.detach()
        // 3. 创建新实例（mpv 用单例，其他播放器新建实例）
        // 显式声明类型为 Player，避免 when 表达式类型推断为 Any
        val newPlayer: Player = when (newType) {
            PlayerType.MPV -> mpvSingleton
            PlayerType.EXO -> ExoPlayerController(getApplication())
            PlayerType.VLC -> VlcController(getApplication())
            PlayerType.IJK -> IjkController(getApplication())
        }
        // 4. 检测 IJK native 库是否可用（x86/x86_64 设备上不可用）
        if (newType == PlayerType.IJK && newPlayer is IjkController && !newPlayer.nativeAvailable) {
            // IJK native 不可用，oldPlayer 已 detach 无法复用，回退到 MPV 单例作为安全兜底
            _player.value = mpvSingleton
            _playerType.value = PlayerType.MPV
            userPrefs.setPlayerType(PlayerType.MPV.name)
            showOsd("播放器", "IJK 在此设备不可用（需 ARM 架构），已回退到 MPV")
            return
        }
        _player.value = newPlayer
        _playerType.value = newType
        userPrefs.setPlayerType(newType.name)
        // 5. 保存待恢复状态，等 View 重建后 attachView 完成再恢复
        pendingRestoreState = savedState
        showOsd("播放器", "已切换到 ${newType.displayName}，重新加载中...")
    }

    /** 待恢复的播放状态（切换播放器后由 MainPlayerScreen 消费） */
    private var pendingRestoreState: Pair<String, Double>? = null

    /**
     * 消费待恢复的播放状态（MainPlayerScreen 在新 View attachView 完成后调用）。
     * 返回 Pair<url, timePosSec>，null 表示无待恢复状态。
     */
    fun consumePendingRestore(): Pair<String, Double>? {
        val s = pendingRestoreState
        pendingRestoreState = null
        return s
    }


    // -----------------------------------------------------------------
    // UI 模式（手机触摸 / TV 遥控器）
    // -----------------------------------------------------------------
    private val _uiMode = MutableStateFlow(UiModeDetector.detect(app))
    val uiMode: StateFlow<UiMode> = _uiMode.asStateFlow()

    // -----------------------------------------------------------------
    // 初始化状态
    // -----------------------------------------------------------------
    sealed class InitState {
        object Idle : InitState()
        object Initializing : InitState()
        data class Ready(val status: IptvStatus) : InitState()
        data class Failed(val message: String) : InitState()
    }

    private val _initState = MutableStateFlow<InitState>(InitState.Idle)
    val initState: StateFlow<InitState> = _initState.asStateFlow()

    private val _iptvStatus = MutableStateFlow<IptvStatus?>(null)
    val iptvStatus: StateFlow<IptvStatus?> = _iptvStatus.asStateFlow()

    // 所有属性初始化完成后再启动初始化（Kotlin 按声明顺序初始化，init 块必须在所有 StateFlow 声明之后）
    init {
        startInitialization()
    }

    private var statusPollJob: Job? = null

    // -----------------------------------------------------------------
    // 频道列表
    // -----------------------------------------------------------------
    private val _channels = MutableStateFlow<List<IptvChannel>>(emptyList())
    val channels: StateFlow<List<IptvChannel>> = _channels.asStateFlow()

    private val _groups = MutableStateFlow<List<String>>(emptyList())
    val groups: StateFlow<List<String>> = _groups.asStateFlow()

    private val _currentIdx = MutableStateFlow(-1)
    val currentIdx: StateFlow<Int> = _currentIdx.asStateFlow()

    val currentChannel: StateFlow<IptvChannel?> = combine(_currentIdx, _channels) { idx, channels ->
        channels.getOrNull(idx)
    }.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    // -----------------------------------------------------------------
    // 频道列表面板状态
    // -----------------------------------------------------------------
    enum class ChannelTab { SUB, LOCAL, FAV, HIST, QUEUE }

    private val _channelsTab = MutableStateFlow(ChannelTab.SUB)
    val channelsTab: StateFlow<ChannelTab> = _channelsTab.asStateFlow()

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    private val _selectedGroup = MutableStateFlow("")
    val selectedGroup: StateFlow<String> = _selectedGroup.asStateFlow()

    // -----------------------------------------------------------------
    // 收藏 / 历史 / 队列
    // -----------------------------------------------------------------
    private val _favorites = MutableStateFlow<Set<Int>>(emptySet())
    val favorites: StateFlow<Set<Int>> = _favorites.asStateFlow()

    private val _history = MutableStateFlow<List<Int>>(emptyList())
    val history: StateFlow<List<Int>> = _history.asStateFlow()

    private val _queue = MutableStateFlow<List<Int>>(emptyList())
    val queue: StateFlow<List<Int>> = _queue.asStateFlow()

    // -----------------------------------------------------------------
    // Shuffle 模式（与 PC 端 FileQueueController.toggle_shuffle 对齐）
    // -----------------------------------------------------------------
    /** shuffle 开关：开启后 nextChannel 随机选择（避免短期重复） */
    private val _shuffleMode = MutableStateFlow(false)
    val shuffleMode: StateFlow<Boolean> = _shuffleMode.asStateFlow()

    /** shuffle 历史栈：记录已播放索引，避免短期重复（与 PC 端 _shuffle_history 对齐） */
    private val shuffleHistory = mutableListOf<Int>()
    private val shuffleHistoryMax = 50
    /** shuffle 撤销栈：prevChannel 时弹出，用于回到上一个随机播放的频道 */
    private val shuffleBackStack = mutableListOf<Int>()

    // -----------------------------------------------------------------
    // EPG
    // -----------------------------------------------------------------
    /** key=channel idx, value=EPG 节目列表 */
    private val epgCache = mutableMapOf<Int, List<IptvEpgProgram>>()

    private val _currentEpg = MutableStateFlow<List<IptvEpgProgram>>(emptyList())
    val currentEpg: StateFlow<List<IptvEpgProgram>> = _currentEpg.asStateFlow()

    private val _epgLoading = MutableStateFlow(false)
    val epgLoading: StateFlow<Boolean> = _epgLoading.asStateFlow()

    // -----------------------------------------------------------------
    // 播放状态（catchup/timeshift 状态机）
    // -----------------------------------------------------------------
    private val _playbackState = MutableStateFlow(PlaybackState())
    val playbackState: StateFlow<PlaybackState> = _playbackState.asStateFlow()

    /** 退出 catchup 按钮是否显示（catchup/timeshift 模式时显示） */
    val showExitCatchup: StateFlow<Boolean> = _playbackState.map { it.mode.isCatchupOrTimeshift }
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    // -----------------------------------------------------------------
    // OSD（顶部反馈信息）
    // -----------------------------------------------------------------
    data class OsdInfo(val title: String, val subtitle: String = "", val extra: String = "")

    private val _osd = MutableStateFlow<OsdInfo?>(null)
    val osd: StateFlow<OsdInfo?> = _osd.asStateFlow()

    private var osdHideJob: Job? = null

    // -----------------------------------------------------------------
    // 面板开关（手机模式：抽屉式；TV 模式：全屏覆盖式）
    // -----------------------------------------------------------------
    private val _channelsPanelOpen = MutableStateFlow(false)
    val channelsPanelOpen: StateFlow<Boolean> = _channelsPanelOpen.asStateFlow()

    private val _epgPanelOpen = MutableStateFlow(false)
    val epgPanelOpen: StateFlow<Boolean> = _epgPanelOpen.asStateFlow()

    private val _menuPanelOpen = MutableStateFlow(false)
    val menuPanelOpen: StateFlow<Boolean> = _menuPanelOpen.asStateFlow()

    /** TV 端统一面板（三列：模式切换 + 频道列表/主菜单 + EPG 节目单） */
    private val _tvUnifiedPanelOpen = MutableStateFlow(false)
    val tvUnifiedPanelOpen: StateFlow<Boolean> = _tvUnifiedPanelOpen.asStateFlow()

    private val _controlsVisible = MutableStateFlow(true)
    val controlsVisible: StateFlow<Boolean> = _controlsVisible.asStateFlow()

    // -----------------------------------------------------------------
    // 订阅源管理
    // -----------------------------------------------------------------
    private val _sources = MutableStateFlow<List<IptvSource>>(emptyList())
    val sources: StateFlow<List<IptvSource>> = _sources.asStateFlow()

    private val _sourceLoading = MutableStateFlow(false)
    val sourceLoading: StateFlow<Boolean> = _sourceLoading.asStateFlow()

    private val _sourceMessage = MutableStateFlow("")
    val sourceMessage: StateFlow<String> = _sourceMessage.asStateFlow()

    private val _sourceManagerOpen = MutableStateFlow(false)
    val sourceManagerOpen: StateFlow<Boolean> = _sourceManagerOpen.asStateFlow()

    // EPG 订阅源
    private val _epgSources = MutableStateFlow<List<IptvEpgSource>>(emptyList())
    val epgSources: StateFlow<List<IptvEpgSource>> = _epgSources.asStateFlow()

    // 订阅源管理 Tab
    enum class SourceTab { PLAYLIST, EPG }
    private val _sourceTab = MutableStateFlow(SourceTab.PLAYLIST)
    val sourceTab: StateFlow<SourceTab> = _sourceTab.asStateFlow()

    // 播放器设置面板（主菜单 → 设置 → 播放器设置）
    // 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
    // 用户可手动切换 vo（gpu / mediacodec_embed），立即生效并持久化
    private val _playerSettingsOpen = MutableStateFlow(false)
    val playerSettingsOpen: StateFlow<Boolean> = _playerSettingsOpen.asStateFlow()

    // 当前播放器 vo/hwdec（从 UserPrefs 读取，供 UI 显示当前选择）
    private val _currentVo = MutableStateFlow(userPrefs.getVo())
    val currentVo: StateFlow<String> = _currentVo.asStateFlow()

    private val _currentHwdec = MutableStateFlow(userPrefs.getHwdec())
    val currentHwdec: StateFlow<String> = _currentHwdec.asStateFlow()

    // 局域网管理服务器
    private val _adminServerUrl = MutableStateFlow("")
    val adminServerUrl: StateFlow<String> = _adminServerUrl.asStateFlow()

    private val _adminServerRunning = MutableStateFlow(false)
    val adminServerRunning: StateFlow<Boolean> = _adminServerRunning.asStateFlow()

    /** 自动停止倒计时（秒），0 表示无倒计时。启动后 5 分钟自动停止，避免长时间占用端口和电量 */
    private val _adminCountdown = MutableStateFlow(0)
    val adminCountdown: StateFlow<Int> = _adminCountdown.asStateFlow()
    private var adminCountdownJob: Job? = null

    // -----------------------------------------------------------------
    // 更多功能面板（主菜单 → 播放 → 视频/音频/字幕/播放/截图/视图/关于）
    // 与 PC 端 controllers 对齐，直接调 MpvController，不走 Python
    // -----------------------------------------------------------------
    private val _videoSettingsOpen = MutableStateFlow(false)
    val videoSettingsOpen: StateFlow<Boolean> = _videoSettingsOpen.asStateFlow()

    private val _audioSettingsOpen = MutableStateFlow(false)
    val audioSettingsOpen: StateFlow<Boolean> = _audioSettingsOpen.asStateFlow()

    private val _subtitleSettingsOpen = MutableStateFlow(false)
    val subtitleSettingsOpen: StateFlow<Boolean> = _subtitleSettingsOpen.asStateFlow()

    // 字幕在线搜索面板
    private val _subtitleSearchOpen = MutableStateFlow(false)
    val subtitleSearchOpen: StateFlow<Boolean> = _subtitleSearchOpen.asStateFlow()
    private val _subtitleSearching = MutableStateFlow(false)
    val subtitleSearching: StateFlow<Boolean> = _subtitleSearching.asStateFlow()
    private val _subtitleSearchResults = MutableStateFlow<List<SubtitleItem>>(emptyList())
    val subtitleSearchResults: StateFlow<List<SubtitleItem>> = _subtitleSearchResults.asStateFlow()
    private val _subtitleSearchError = MutableStateFlow("")
    val subtitleSearchError: StateFlow<String> = _subtitleSearchError.asStateFlow()
    private val _subtitleDownloading = MutableStateFlow(false)
    val subtitleDownloading: StateFlow<Boolean> = _subtitleDownloading.asStateFlow()

    private val _playbackPanelOpen = MutableStateFlow(false)
    val playbackPanelOpen: StateFlow<Boolean> = _playbackPanelOpen.asStateFlow()

    private val _screenshotPanelOpen = MutableStateFlow(false)
    val screenshotPanelOpen: StateFlow<Boolean> = _screenshotPanelOpen.asStateFlow()

    private val _viewSettingsOpen = MutableStateFlow(false)
    val viewSettingsOpen: StateFlow<Boolean> = _viewSettingsOpen.asStateFlow()

    private val _aboutPanelOpen = MutableStateFlow(false)
    val aboutPanelOpen: StateFlow<Boolean> = _aboutPanelOpen.asStateFlow()

    /** 打开网络流 URL 输入对话框 */
    private val _openUrlDialogOpen = MutableStateFlow(false)
    val openUrlDialogOpen: StateFlow<Boolean> = _openUrlDialogOpen.asStateFlow()

    // -----------------------------------------------------------------
    // 频道映射面板
    // -----------------------------------------------------------------
    private val _mappingPanelOpen = MutableStateFlow(false)
    val mappingPanelOpen: StateFlow<Boolean> = _mappingPanelOpen.asStateFlow()

    /** 映射列表（远程 + 用户） */
    private val _mappingList = MutableStateFlow<List<MappingEntry>>(emptyList())
    val mappingList: StateFlow<List<MappingEntry>> = _mappingList.asStateFlow()

    /** 映射加载中 */
    private val _mappingLoading = MutableStateFlow(false)
    val mappingLoading: StateFlow<Boolean> = _mappingLoading.asStateFlow()

    /** 映射刷新状态文本 */
    private val _mappingStatusText = MutableStateFlow("")
    val mappingStatusText: StateFlow<String> = _mappingStatusText.asStateFlow()

    // -----------------------------------------------------------------
    // A/V 同步监控面板
    // -----------------------------------------------------------------
    private val _avSyncPanelOpen = MutableStateFlow(false)
    val avSyncPanelOpen: StateFlow<Boolean> = _avSyncPanelOpen.asStateFlow()

    /** A/V 差值（秒，正值=音频领先，负值=视频领先） */
    private val _avDiff = MutableStateFlow(0.0)
    val avDiff: StateFlow<Double> = _avDiff.asStateFlow()

    /** 音频 PTS（秒） */
    private val _audioPts = MutableStateFlow(0.0)
    val audioPts: StateFlow<Double> = _audioPts.asStateFlow()

    /** 视频 PTS（秒） */
    private val _videoPts = MutableStateFlow(0.0)
    val videoPts: StateFlow<Double> = _videoPts.asStateFlow()

    /** 当前音频延迟（秒） */
    private val _currentAudioDelay = MutableStateFlow(0.0)
    val currentAudioDelay: StateFlow<Double> = _currentAudioDelay.asStateFlow()

    /** avdiff 历史采样（用于波形图，最多 200 点） */
    private val _avDiffHistory = MutableStateFlow<List<Float>>(emptyList())
    val avDiffHistory: StateFlow<List<Float>> = _avDiffHistory.asStateFlow()

    /** 字幕自动同步开关 */
    private val _subSyncEnabled = MutableStateFlow(false)
    val subSyncEnabled: StateFlow<Boolean> = _subSyncEnabled.asStateFlow()

    /** 字幕自动同步采样协程 */
    private var avSyncJob: Job? = null
    private var subSyncJob: Job? = null

    // -----------------------------------------------------------------
    // 网络增强面板
    // -----------------------------------------------------------------
    private val _networkPanelOpen = MutableStateFlow(false)
    val networkPanelOpen: StateFlow<Boolean> = _networkPanelOpen.asStateFlow()

    // -----------------------------------------------------------------
    // 工具面板
    // -----------------------------------------------------------------
    private val _toolsPanelOpen = MutableStateFlow(false)
    val toolsPanelOpen: StateFlow<Boolean> = _toolsPanelOpen.asStateFlow()

    // URL 范围扫描面板（与 PC 端 controllers/scan_controller.py 对齐，后端为 StandaloneScanner）
    private val _scanPanelOpen = MutableStateFlow(false)
    val scanPanelOpen: StateFlow<Boolean> = _scanPanelOpen.asStateFlow()
    private val _scanStatus = MutableStateFlow<ScanStatus?>(null)
    val scanStatus: StateFlow<ScanStatus?> = _scanStatus.asStateFlow()
    private val _scanResults = MutableStateFlow<List<ScanResult>>(emptyList())
    val scanResults: StateFlow<List<ScanResult>> = _scanResults.asStateFlow()
    private val _scanLoading = MutableStateFlow(false)
    val scanLoading: StateFlow<Boolean> = _scanLoading.asStateFlow()
    private val _scanError = MutableStateFlow("")
    val scanError: StateFlow<String> = _scanError.asStateFlow()
    private var scanPollJob: Job? = null

    // -----------------------------------------------------------------
    // 节目提醒（与 PC 端 services/epg_reminder_service.py 对齐）
    //
    // - 启动时从 UserPrefs 加载
    // - 10 秒间隔轮询检查，60 秒提前触发弹窗
    // - 触发后通过 _triggeredReminder 暴露给 UI 显示弹窗
    // - 用户点击"切换频道"切到目标频道；点击"稍后"关闭弹窗
    // - 节目结束超过 1 小时自动清理
    // -----------------------------------------------------------------
    private val _reminderPanelOpen = MutableStateFlow(false)
    val reminderPanelOpen: StateFlow<Boolean> = _reminderPanelOpen.asStateFlow()
    private val _reminders = MutableStateFlow<List<ReminderItem>>(emptyList())
    val reminders: StateFlow<List<ReminderItem>> = _reminders.asStateFlow()
    private val _triggeredReminder = MutableStateFlow<ReminderItem?>(null)
    val triggeredReminder: StateFlow<ReminderItem?> = _triggeredReminder.asStateFlow()
    private var reminderCheckJob: Job? = null
    /** 已通知过的提醒 ID 集合，避免同一节目重复弹窗 */
    private val notifiedReminderIds = mutableSetOf<String>()

    // -----------------------------------------------------------------
    // 续播位置（与 PC 端 controllers/resume_playback_controller.py 对齐）
    //
    // - 启动时从 UserPrefs 加载
    // - 自动保存：每 10 秒检查（仅 VOD/本地视频，跳过直播流）
    // - 自动恢复：fileLoaded 时延迟 400ms seek
    // - skipNextResume：队列/书签切换时跳过下次自动恢复
    // -----------------------------------------------------------------
    private val _resumePanelOpen = MutableStateFlow(false)
    val resumePanelOpen: StateFlow<Boolean> = _resumePanelOpen.asStateFlow()
    private val _resumeList = MutableStateFlow<List<ResumeItem>>(emptyList())
    val resumeList: StateFlow<List<ResumeItem>> = _resumeList.asStateFlow()
    private var resumeSaveJob: Job? = null
    /** 当前正在播放的 URL（用于自动保存） */
    private var currentPlaybackUrl: String = ""
    /** 当前播放名（频道名/文件名） */
    private var currentPlaybackName: String = ""
    /** 是否为本地视频（决定 chIdx 是否为 -1） */
    private var currentIsLocalFile: Boolean = false
    /** 跳过下次自动恢复（队列/书签切换时设置） */
    private var skipNextResumeFlag: Boolean = false

    // -----------------------------------------------------------------
    // 书签（与 PC 端 controllers/bookmark_controller.py 对齐）
    //
    // - 以 URL 分组，同 URL 0.5s 容差内覆盖
    // - 当前 URL 书签列表 + 全部书签列表（"当前文件/所有文件"视图切换）
    // - 跳转时若跨 URL，调用 skipNextResume 避免续播位置覆盖书签位置
    // -----------------------------------------------------------------
    private val _bookmarkPanelOpen = MutableStateFlow(false)
    val bookmarkPanelOpen: StateFlow<Boolean> = _bookmarkPanelOpen.asStateFlow()
    /** 视图模式：true=当前文件，false=所有文件 */
    private val _bookmarkShowCurrent = MutableStateFlow(true)
    val bookmarkShowCurrent: StateFlow<Boolean> = _bookmarkShowCurrent.asStateFlow()
    /** 当前 URL 的书签列表 */
    private val _currentBookmarks = MutableStateFlow<List<BookmarkItem>>(emptyList())
    val currentBookmarks: StateFlow<List<BookmarkItem>> = _currentBookmarks.asStateFlow()
    /** 所有书签列表（按 createdAt 降序） */
    private val _allBookmarks = MutableStateFlow<List<BookmarkItem>>(emptyList())
    val allBookmarks: StateFlow<List<BookmarkItem>> = _allBookmarks.asStateFlow()

    // -----------------------------------------------------------------
    // EPG 时间线视图（与 PC 端 EpgTimelineDialog + Web 端 renderEpgTimeline 对齐）
    //
    // 多频道 × 24h 横向网格，Canvas 自绘，支持：
    // - 频道范围筛选（全部/收藏/当前分组）
    // - 日期切换（±7 天）
    // - 当前时间竖线 + 自动滚动到当前时间
    // - 节目块点击：过去→回看，当前/未来→提醒
    // -----------------------------------------------------------------

    /** 时间线频道范围（与 Web 端 select 一致） */
    enum class EpgTimelineRange { ALL, FAVORITES, CURRENT_GROUP }

    /** 时间线单行数据（一个频道 + 当日节目列表） */
    data class EpgTimelineRow(
        val channelIdx: Int,
        val channelName: String,
        val programs: List<IptvEpgProgram>
    )

    private val _epgTimelineOpen = MutableStateFlow(false)
    val epgTimelineOpen: StateFlow<Boolean> = _epgTimelineOpen.asStateFlow()

    private val _epgTimelineLoading = MutableStateFlow(false)
    val epgTimelineLoading: StateFlow<Boolean> = _epgTimelineLoading.asStateFlow()

    private val _epgTimelineRows = MutableStateFlow<List<EpgTimelineRow>>(emptyList())
    val epgTimelineRows: StateFlow<List<EpgTimelineRow>> = _epgTimelineRows.asStateFlow()

    private val _epgTimelineRange = MutableStateFlow(EpgTimelineRange.ALL)
    val epgTimelineRange: StateFlow<EpgTimelineRange> = _epgTimelineRange.asStateFlow()

    /** 日期偏移（0=今天，-1=昨天，1=明天，范围 ±7） */
    private val _epgTimelineDateOffset = MutableStateFlow(0)
    val epgTimelineDateOffset: StateFlow<Int> = _epgTimelineDateOffset.asStateFlow()

    /** 时间线加载状态文本（用于 UI 显示） */
    private val _epgTimelineStatus = MutableStateFlow("")
    val epgTimelineStatus: StateFlow<String> = _epgTimelineStatus.asStateFlow()

    // -----------------------------------------------------------------
    // 全局搜索（与 PC 端 UnifiedSearchDialog + Web 端 search 面板对齐）
    //
    // 搜索范围：
    // - 频道：name / group / url（与 PC 端一致）
    // - 节目：title / desc（与 EpgPanel 局部搜索一致，比 PC 端多搜 desc）
    //
    // 节目搜索异步遍历 epgCache（已加载的频道），上限 200 条（与 PC 端一致）。
    // -----------------------------------------------------------------

    /** 搜索范围 */
    enum class SearchScope { ALL, CHANNELS, PROGRAMS }

    /** 搜索结果（密封类：频道 / 节目） */
    sealed class SearchResult {
        data class ChannelResult(val idx: Int, val channel: IptvChannel) : SearchResult()
        data class ProgramResult(
            val channelIdx: Int,
            val channelName: String,
            val program: IptvEpgProgram
        ) : SearchResult()
    }

    private val _searchPanelOpen = MutableStateFlow(false)
    val searchPanelOpen: StateFlow<Boolean> = _searchPanelOpen.asStateFlow()

    private val _searchResults = MutableStateFlow<List<SearchResult>>(emptyList())
    val searchResults: StateFlow<List<SearchResult>> = _searchResults.asStateFlow()

    private val _searchLoading = MutableStateFlow(false)
    val searchLoading: StateFlow<Boolean> = _searchLoading.asStateFlow()

    private val _searchScope = MutableStateFlow(SearchScope.ALL)
    val searchScope: StateFlow<SearchScope> = _searchScope.asStateFlow()

    private var searchJob: Job? = null

    // -----------------------------------------------------------------
    // 流质量检测（与 PC 端 get_live_media_info + Web 端 stream_quality 面板对齐）
    //
    // 详细展示 mpv 实时流信息：视频/音频/网络/缓存/丢帧/硬件解码。
    // 数据来源：mpv.getPropertyString/Int/Double（只读，无需持久化）。
    // -----------------------------------------------------------------

    private val _streamQualityPanelOpen = MutableStateFlow(false)
    val streamQualityPanelOpen: StateFlow<Boolean> = _streamQualityPanelOpen.asStateFlow()

    // -----------------------------------------------------------------
    // HDR 输出模式（与 PC 端 hdr_output_mode 对齐）
    //
    // 模式：auto / tonemap / passthrough / disable
    // Android 端不改变 vo（保持用户选择），只在文件加载时应用 HDR 配置。
    // -----------------------------------------------------------------

    /** HDR 输出模式 */
    enum class HdrMode { DISABLE, AUTO, TONEMAP, PASSTHROUGH }

    private val _hdrMode = MutableStateFlow(
        runCatching { HdrMode.valueOf(userPrefs.getHdrMode().uppercase()) }.getOrDefault(HdrMode.DISABLE)
    )
    val hdrMode: StateFlow<HdrMode> = _hdrMode.asStateFlow()

    // -----------------------------------------------------------------
    // 初始化流程
    // -----------------------------------------------------------------

    /**
     * 启动初始化流程：initContext → 轮询 getStatus 直到完成或超时 → loadChannels → loadPrefs。
     * 在 ViewModel init 块中自动调用，也供 SplashScreen 的重试按钮调用。
     */
    fun startInitialization() {
        if (_initState.value is InitState.Initializing ||
            _initState.value is InitState.Ready
        ) return

        _initState.value = InitState.Initializing
        viewModelScope.launch {
            try {
                // 首次启动时给 ART 一点时间完成初始类加载和 JIT 编译，
                // 避免 Python native 库加载与 JIT 线程冲突导致偶发 SIGSEGV
                delay(300)

                // 1. 初始化 Python + ServerContext 单例（在 IO 线程执行，减少主线程压力）
                val initResult = withContext(Dispatchers.IO) {
                    repository.initContext()
                }
                if (initResult.isFailure) {
                    val msg = initResult.exceptionOrNull()?.message ?: "初始化失败"
                    Log.e(TAG, "initContext failed: $msg")
                    _initState.value = InitState.Failed(msg)
                    return@launch
                }
                Log.i(TAG, "initContext OK, start polling status")

                // 2. 轮询 getStatus（最长 60 秒）
                val maxWaitMs = 60_000L
                val intervalMs = 1_000L
                val startTime = System.currentTimeMillis()

                while (isActive) {
                    val elapsed = System.currentTimeMillis() - startTime
                    if (elapsed > maxWaitMs) {
                        _initState.value = InitState.Failed("初始化超时（60 秒）")
                        return@launch
                    }

                    val statusResult = repository.getStatus()
                    statusResult.fold(
                        onSuccess = { status ->
                            _iptvStatus.value = status
                            Log.d(TAG, "status: inited=${status.inited} loading=${status.sourceLoading} total=${status.channelsTotal}")

                            // 判断是否完成：
                            // - inited=true 且 sourceLoading=false → 完成（无论 channels_total 是否为 0）
                            if (status.inited && !status.sourceLoading) {
                                _initState.value = InitState.Ready(status)
                                startBackgroundStatusRefresh()
                                // 加载频道列表和用户偏好
                                loadChannels()
                                loadUserPrefs()
                                return@launch
                            }
                        },
                        onFailure = { e ->
                            Log.w(TAG, "getStatus failed (will retry): ${e.message}")
                        }
                    )
                    delay(intervalMs)
                }
            } catch (e: CancellationException) {
                // 协程被取消（如 Activity 销毁），不修改状态
                throw e
            } catch (e: Throwable) {
                // 捕获所有异常（包括 Chaquopy 首次启动时的资源解压错误），避免崩溃
                Log.e(TAG, "startInitialization crashed", e)
                _initState.value = InitState.Failed(e.message ?: "未知错误")
            }
        }
    }

    /**
     * 启动后台状态刷新（订阅源加载完成后的周期性检查）。
     * 用于：用户添加订阅源后，UI 能感知到 channels_total 变化并自动重载频道列表。
     */
    private fun startBackgroundStatusRefresh() {
        statusPollJob?.cancel()
        statusPollJob = viewModelScope.launch {
            var lastTotal = _iptvStatus.value?.channelsTotal ?: 0
            while (isActive) {
                delay(3_000L)
                repository.getStatus().fold(
                    onSuccess = { status ->
                        _iptvStatus.value = status
                        // 订阅源加载完成导致频道数变化时，自动重载频道列表
                        if (status.channelsTotal != lastTotal) {
                            Log.i(TAG, "channels total changed: $lastTotal → ${status.channelsTotal}, reload")
                            lastTotal = status.channelsTotal
                            loadChannels()
                        }
                    },
                    onFailure = { /* 静默忽略 */ }
                )
            }
        }
    }

    // -----------------------------------------------------------------
    // 频道列表加载
    // -----------------------------------------------------------------

    /** 加载所有频道和分组 */
    fun loadChannels() {
        viewModelScope.launch {
            // 加载全部频道（不分页，方便本地过滤；分页由 UI 的 LazyColumn 处理）
            val result = repository.getChannels(page = 1, size = 10_000)
            result.fold(
                onSuccess = { page ->
                    _channels.value = page.channels
                    // 提取分组（保持 M3U 顺序，去重）
                    val groupList = page.channels
                        .map { it.group }
                        .filter { it.isNotEmpty() }
                        .distinct()
                    _groups.value = groupList
                    Log.i(TAG, "Loaded ${page.channels.size} channels, ${groupList.size} groups")
                },
                onFailure = { e ->
                    Log.e(TAG, "loadChannels failed: ${e.message}")
                }
            )
        }
    }

    /** 加载用户偏好（收藏/历史/队列/提醒/续播位置/书签） */
    private fun loadUserPrefs() {
        _favorites.value = userPrefs.getFavorites()
        _history.value = userPrefs.getHistory()
        _queue.value = userPrefs.getQueue()
        _reminders.value = userPrefs.getReminders()
        _resumeList.value = userPrefs.getResumeList()
        _allBookmarks.value = userPrefs.getAllBookmarks()
        // 启动提醒定时检查（与 PC 端 QTimer 10 秒间隔对齐）
        startReminderCheck()
        // 启动续播位置自动保存（10 秒间隔，与 Web 端 autoSaveResume 对齐）
        startResumeAutoSave()
    }

    // -----------------------------------------------------------------
    // 频道列表面板状态
    // -----------------------------------------------------------------

    fun setChannelsTab(tab: ChannelTab) {
        _channelsTab.value = tab
        _selectedGroup.value = ""  // 切换 tab 时重置分组筛选
    }

    fun setSearchQuery(query: String) {
        _searchQuery.value = query
    }

    fun setSelectedGroup(group: String) {
        _selectedGroup.value = group
    }

    /**
     * 获取过滤后的频道列表（按 tab/搜索/分组）。
     * UI 直接调用此方法获取当前应显示的频道列表。
     */
    fun getFilteredChannels(): List<Pair<IptvChannel, Int>> {
        val all = _channels.value
        val query = _searchQuery.value.lowercase()
        val group = _selectedGroup.value
        val tab = _channelsTab.value

        val filtered: List<Pair<IptvChannel, Int>> = when (tab) {
            ChannelTab.SUB -> all.mapIndexed { idx, c -> c to idx }
            ChannelTab.LOCAL -> all.mapIndexed { idx, c -> c to idx }
                .filter { (c, _) -> ProgressHelper.isLocalFile(c.url) }
            ChannelTab.FAV -> all.mapIndexed { idx, c -> c to idx }
                .filter { (c, idx) -> _favorites.value.contains(idx) }
            ChannelTab.HIST -> _history.value.mapNotNull { idx ->
                all.getOrNull(idx)?.let { it to idx }
            }
            ChannelTab.QUEUE -> _queue.value.mapNotNull { idx ->
                all.getOrNull(idx)?.let { it to idx }
            }
        }

        return filtered.filter { (c, _) ->
            // 分组筛选（仅 SUB/LOCAL tab 应用）
            val groupMatch = tab != ChannelTab.SUB && tab != ChannelTab.LOCAL ||
                    group.isEmpty() || c.group == group
            // 搜索筛选
            val searchMatch = query.isEmpty() ||
                    c.name.lowercase().contains(query) ||
                    c.group.lowercase().contains(query)
            groupMatch && searchMatch
        }
    }

    // -----------------------------------------------------------------
    // 频道播放
    // -----------------------------------------------------------------

    /**
     * 播放指定频道（按索引）。
     *
     * 与 PC 端 playChannel 和 mobile index.html playChannel 对齐：
     * 1. 重置 catchup/timeshift 状态（清空 originalChannel/catchupProgram/liveTimeshiftSeconds）
     * 2. 隐藏退出 catchup 按钮
     * 3. 设置 playMode='live'
     * 4. 调用 mpv.playFile
     * 5. 显示 OSD（频道名 + 分组）
     * 6. 关闭面板（频道列表）
     * 7. 加入历史（去重后插入队首）
     * 8. 预取 EPG
     */
    fun playChannel(idx: Int, silent: Boolean = false) {
        val channel = _channels.value.getOrNull(idx) ?: run {
            Log.w(TAG, "playChannel: invalid idx $idx")
            return
        }
        Log.i(TAG, "playChannel: ${channel.name} (${channel.url})")

        _currentIdx.value = idx

        // 重置 catchup/timeshift 状态（与 PC 端 _exit_catchup_mode 对齐）
        _playbackState.value = PlaybackState(mode = PlayMode.LIVE)

        // 续播位置：记录当前播放 URL（用于自动保存）
        currentPlaybackUrl = channel.url
        currentPlaybackName = channel.name
        currentIsLocalFile = false
        // 刷新当前 URL 的书签列表
        refreshCurrentBookmarks()

        // 播放
        mpv.playFile(channel.url)

        // 显示 OSD
        if (!silent) {
            showOsd(channel.name, channel.group)
        }

        // 关闭面板
        if (!silent) {
            closeAllPanels()
        }

        // 加入历史
        userPrefs.addToHistory(idx)
        _history.value = userPrefs.getHistory()

        // 预取 EPG（避免用户必须先打开 EPG 面板才能看到节目信息）
        fetchEpgForCurrent()
    }

    /**
     * 切换 shuffle 模式（与 PC 端 toggle_shuffle 对齐）。
     * 开启时清空历史栈和撤销栈；关闭时同样清空。
     */
    fun toggleShuffleMode(): Boolean {
        val newValue = !_shuffleMode.value
        _shuffleMode.value = newValue
        shuffleHistory.clear()
        shuffleBackStack.clear()
        showOsd(if (newValue) "随机播放：开" else "随机播放：关")
        return newValue
    }

    /** 上一频道 */
    fun prevChannel() {
        val cur = _currentIdx.value
        if (cur < 0) return
        // shuffle 模式：从撤销栈弹出上一个随机播放的频道
        if (_shuffleMode.value && shuffleBackStack.isNotEmpty()) {
            // 当前频道压回历史栈（让 nextChannel 能回到它）
            cur.let { shuffleHistory.add(it) }
            val prev = shuffleBackStack.removeAt(shuffleBackStack.lastIndex)
            playChannel(prev)
            return
        }
        val next = if (cur > 0) cur - 1 else _channels.value.lastIndex
        if (next >= 0 && next < _channels.value.size) playChannel(next)
    }

    /** 下一频道 */
    fun nextChannel() {
        val cur = _currentIdx.value
        if (cur < 0) return
        // shuffle 模式：随机选择（避免短期重复）
        if (_shuffleMode.value) {
            val next = pickRandomChannelIdx(cur)
            if (next >= 0 && next != cur) {
                // 当前频道压入撤销栈，便于 prevChannel 回退
                shuffleBackStack.add(cur)
                // 清理过长的撤销栈（与历史栈上限一致）
                if (shuffleBackStack.size > shuffleHistoryMax) {
                    shuffleBackStack.removeAt(0)
                }
            }
            if (next in _channels.value.indices) playChannel(next)
            return
        }
        val next = if (cur < _channels.value.lastIndex) cur + 1 else 0
        if (next in _channels.value.indices) playChannel(next)
    }

    /**
     * 随机选择一个频道索引（避免短期重复，与 PC 端 _pick_random_index 对齐）。
     * 候选范围基于当前过滤后的可见频道列表（按 tab/搜索/分组），
     * 这样 shuffle 只在当前可见频道范围内随机。
     */
    private fun pickRandomChannelIdx(currentIdx: Int): Int {
        // 优先从当前过滤后的可见频道中随机（与用户视角一致）
        val visibleIdxList = getFilteredChannels().map { it.second }.distinct()
        val total = visibleIdxList.size
        if (total <= 1) return currentIdx

        // 清理过长的历史（保留最近一半）
        if (shuffleHistory.size > shuffleHistoryMax) {
            repeat(shuffleHistory.size - shuffleHistoryMax / 2) { shuffleHistory.removeAt(0) }
        }

        // 候选 = 可见频道中排除当前和近期历史的
        var candidates = visibleIdxList.filter { it != currentIdx && it !in shuffleHistory }
        if (candidates.isEmpty()) {
            candidates = visibleIdxList.filter { it != currentIdx }
        }
        if (candidates.isEmpty()) return currentIdx

        val picked = candidates.random()
        shuffleHistory.add(picked)
        return picked
    }

    /** 停止播放 */
    fun stopPlay() {
        Log.i(TAG, "stopPlay")
        mpv.stop()
        _playbackState.value = PlaybackState(mode = PlayMode.IDLE)
        _currentIdx.value = -1
        _currentEpg.value = emptyList()
        showOsd("已停止")
    }

    // -----------------------------------------------------------------
    // Catchup / Timeshift
    // -----------------------------------------------------------------

    /**
     * 启动回看（EPG 过去节目点击触发）。
     * 与 PC 端 catchup_controller.start_catchup 对齐。
     *
     * @param program EPG 节目（含 start/end/title/desc）
     */
    fun startCatchup(program: IptvEpgProgram) {
        val idx = _currentIdx.value
        if (idx < 0) {
            showOsd("回看", "无当前频道")
            return
        }
        val channel = _channels.value.getOrNull(idx) ?: return

        // 检查频道是否支持回看
        if (!CatchupHelper.isCatchupEnabled(channel)) {
            showOsd("回看", "该频道不支持回看")
            return
        }

        // 提取节目时间戳
        val (startMs, endMs) = CatchupHelper.extractProgramTimestamps(program)
        if (startMs <= 0 || endMs <= startMs) {
            showOsd("回看", "节目时间无效")
            return
        }

        // 构建 catchup URL
        val catchupUrl = CatchupHelper.buildCatchupUrl(channel, startMs, endMs)
        if (catchupUrl.isNullOrEmpty()) {
            showOsd("回看", "无法构建回看 URL")
            return
        }

        // 进入 catchup 状态
        val catchupProgram = CatchupProgram(program, startMs, endMs)
        _playbackState.value = _playbackState.value.enterCatchup(channel, catchupProgram, PlayMode.CATCHUP)

        // 播放 catchup URL
        mpv.playFile(catchupUrl)

        // 显示 OSD + 关闭面板
        showOsd("回看", program.title.ifEmpty { channel.name })
        closeAllPanels()

        Log.i(TAG, "startCatchup: ${program.title} ($startMs-$endMs) → $catchupUrl")
    }

    /**
     * 启动时移（直播进度条超出缓冲触发）。
     * 与 PC 端 catchup_controller.start_live_timeshift_from_progress 对齐。
     *
     * @param sliderSec 进度条点击位置（秒）
     * @return true 表示启动成功
     */
    fun startLiveTimeshift(sliderSec: Double): Boolean {
        val idx = _currentIdx.value
        if (idx < 0) return false
        val channel = _channels.value.getOrNull(idx) ?: return false

        // 检查频道是否支持回看（时移需要 catchup_source）
        if (!CatchupHelper.isCatchupEnabled(channel)) {
            showOsd("时移", "该频道不支持时移")
            return false
        }

        // 计算目标墙钟时间
        val now = System.currentTimeMillis()
        val currentProgram = ProgressHelper.findCurrentProgram(_currentEpg.value, now)
        val hasEpg = currentProgram != null
        val programStartMs = if (currentProgram != null) {
            CatchupHelper.extractProgramTimestamps(currentProgram).first
        } else 0L
        val hourStartMs = CatchupHelper.currentHourStartMs()

        val targetWallclock = CatchupHelper.computeTimeshiftTarget(
            programStartMs, hourStartMs, sliderSec, hasEpg
        )
        if (targetWallclock <= 0) {
            showOsd("时移", "目标时间无效")
            return false
        }

        // 计算 endMs（节目结束 or now+30min）
        val endMs = if (currentProgram != null) {
            val (_, pEnd) = CatchupHelper.extractProgramTimestamps(currentProgram)
            if (pEnd > now) pEnd else now + 30 * 60 * 1000L
        } else {
            hourStartMs + 3600_000L
        }

        // 构建 catchup URL
        val catchupUrl = CatchupHelper.buildCatchupUrl(channel, targetWallclock, endMs)
        if (catchupUrl.isNullOrEmpty()) {
            showOsd("时移", "无法构建时移 URL")
            return false
        }

        // 进入 timeshift 状态
        val offsetSec = ((now - targetWallclock) / 1000).coerceAtLeast(0L)
        val catchupProgram = if (currentProgram != null) {
            CatchupProgram(currentProgram, programStartMs.ifElse(hourStartMs) { programStartMs > 0 }, endMs)
        } else {
            // 无 EPG 时构造一个占位 program
            val placeholder = IptvEpgProgram(title = channel.name, start = "", stop = "")
            CatchupProgram(placeholder, hourStartMs, endMs)
        }
        _playbackState.value = _playbackState.value.enterCatchup(channel, catchupProgram, PlayMode.TIMESHIFT)
            .copy(liveTimeshiftSeconds = offsetSec)

        // 播放 timeshift URL
        mpv.playFile(catchupUrl)

        // 显示 OSD
        showOsd("时移", "落后 ${offsetSec} 秒")

        Log.i(TAG, "startLiveTimeshift: offset=${offsetSec}s target=$targetWallclock → $catchupUrl")
        return true
    }

    /**
     * 退出回看/时移，恢复原始频道直播。
     * 与 PC 端 catchup_controller.exit_catchup 对齐。
     *
     * 关键：走完整的 playChannel 流程（而非直接 mpv.playFile），确保：
     * 1. mpv 从错误状态（如 catchup URL 400 错误）中恢复
     * 2. 重置 catchup/timeshift 状态
     * 3. EPG 重新预取
     */
    fun exitCatchup() {
        val state = _playbackState.value
        if (!state.mode.isCatchupOrTimeshift) {
            showOsd("回看", "未在回看模式")
            return
        }

        // 清除回看状态（退出后是直播，与 PC 端 exit_catchup 一致）
        _playbackState.value = state.clearCatchup(PlayMode.LIVE)

        // 恢复原始频道直播：走完整的 playChannel 流程
        val idx = _currentIdx.value
        if (idx >= 0) {
            playChannel(idx, silent = true)
            showOsd("回看", "已退出，恢复直播")
        } else {
            showOsd("回看", "已退出")
        }
    }

    /**
     * 进度条 seek 处理。
     * 与 PC 端 controllers/playback_controller.seek_live 和 mobile handleProgressSeek 对齐。
     *
     * @param percent 进度条百分比（0-100）
     */
    fun seekProgress(percent: Float) {
        val state = _playbackState.value
        val channel = currentChannel.value

        when (state.mode) {
            PlayMode.CATCHUP -> {
                // 回看模式：基于 mpv timePos 直接 seek
                val program = state.catchupProgram ?: return
                val targetSec = (percent / 100f * program.durationSec).toDouble()
                mpv.seekAbsolute(targetSec)
            }
            PlayMode.TIMESHIFT, PlayMode.LIVE -> {
                // 无频道（本地视频/网络流）：VOD seek，直接按 duration 比例 seek
                if (channel == null) {
                    val duration = mpv.duration.value
                    if (duration > 0) {
                        mpv.seekAbsolute((percent / 100f * duration).toDouble())
                    }
                    return
                }
                // 时移/直播模式：根据缓冲判断走 mpv seek 还是重建 URL
                handleLiveSeek(percent, state, channel)
            }
            PlayMode.IDLE -> { /* 无播放，忽略 */ }
        }
    }

    /**
     * 直播/时移 seek 处理（缓冲边界判断）。
     */
    private fun handleLiveSeek(percent: Float, state: PlaybackState, channel: IptvChannel) {
        val now = System.currentTimeMillis()
        val currentProgram = ProgressHelper.findCurrentProgram(_currentEpg.value, now)
        val hasEpg = currentProgram != null

        // 计算 targetWallclock
        val (startMs, endMs) = if (currentProgram != null) {
            CatchupHelper.extractProgramTimestamps(currentProgram)
        } else {
            val hourStart = CatchupHelper.currentHourStartMs()
            hourStart to hourStart + 3600_000L
        }
        if (startMs <= 0 || endMs <= startMs) return

        val totalSec = ((endMs - startMs) / 1000).coerceAtLeast(1L)
        val sliderSec = (percent / 100f * totalSec).toLong()
        val targetWallclock = (startMs + sliderSec * 1000).coerceAtMost(now - 2_000L)
        val offsetSec = ((now - targetWallclock) / 1000).coerceAtLeast(0L)

        // 缓冲边界判断
        val mpvTimePos = mpv.timePos.value
        val cacheDuration = mpv.getPropertyDouble("demuxer-cache-duration") ?: 0.0
        val cacheTime = mpv.getPropertyDouble("demuxer-cache-time") ?: 0.0
        val (targetPos, inBuffer) = ProgressHelper.computeSeekTarget(offsetSec, mpvTimePos, cacheDuration, cacheTime)

        if (inBuffer && offsetSec <= 2) {
            // 目标在缓冲区内且接近直播：直接 mpv seek，清空 timeshift
            mpv.seekAbsolute(targetPos)
            if (state.mode.isTimeshift) {
                _playbackState.value = state.copy(mode = PlayMode.LIVE, liveTimeshiftSeconds = 0L)
            }
        } else if (inBuffer) {
            // 目标在缓冲区内但有时移偏移：mpv seek + 设置 timeshift 状态
            mpv.seekAbsolute(targetPos)
            if (!state.mode.isTimeshift) {
                _playbackState.value = state.switchToTimeshift(offsetSec)
            } else {
                _playbackState.value = state.copy(liveTimeshiftSeconds = offsetSec)
            }
            showOsd("时移", "落后 ${offsetSec} 秒")
        } else {
            // 目标超出缓冲区：调用 startLiveTimeshift 重建 catchup URL
            if (!CatchupHelper.isCatchupEnabled(channel)) {
                showOsd("提示", "该频道不支持时移回看")
                return
            }
            startLiveTimeshift(sliderSec.toDouble())
        }
    }

    // -----------------------------------------------------------------
    // EPG
    // -----------------------------------------------------------------

    /**
     * 预取当前频道的 EPG（与 PC 端 fetchEpgForCurrent 对齐）。
     * 切换频道时自动调用，避免用户必须先打开 EPG 面板才能看到节目信息。
     */
    fun fetchEpgForCurrent() {
        val idx = _currentIdx.value
        if (idx < 0) {
            _currentEpg.value = emptyList()
            return
        }
        val channel = _channels.value.getOrNull(idx) ?: return

        // 优先用缓存
        epgCache[idx]?.let { cached ->
            _currentEpg.value = cached
            return
        }

        _epgLoading.value = true
        viewModelScope.launch {
            val result = repository.getEpg(
                channelName = channel.name,
                tvgId = channel.tvgId,
                tvgName = channel.tvgName,
                commaName = channel.name
            )
            result.fold(
                onSuccess = { epgList ->
                    val programs = epgList.programmes
                    epgCache[idx] = programs
                    _currentEpg.value = programs
                    Log.i(TAG, "fetchEpgForCurrent: ${programs.size} programs for ${channel.name}")
                },
                onFailure = { e ->
                    Log.w(TAG, "fetchEpgForCurrent failed: ${e.message}")
                    _currentEpg.value = emptyList()
                }
            )
            _epgLoading.value = false
        }
    }

    /** 获取当前正在播放的 EPG 节目（用于控制面板第二行显示） */
    fun getCurrentProgram(): IptvEpgProgram? {
        return ProgressHelper.findCurrentProgram(_currentEpg.value, System.currentTimeMillis())
    }

    /** 计算当前进度条信息（用于 UI 进度条渲染） */
    fun computeProgress(): ProgressHelper.ProgressInfo {
        return ProgressHelper.computeProgress(
            state = _playbackState.value,
            channel = currentChannel.value,
            currentProgram = getCurrentProgram(),
            mpvTimePos = mpv.timePos.value,
            mpvDuration = mpv.duration.value,
        )
    }

    // -----------------------------------------------------------------
    // 收藏 / 历史 / 队列
    // -----------------------------------------------------------------

    /** 切换当前频道收藏状态，返回是否已收藏 */
    fun toggleFavorite(): Boolean {
        val idx = _currentIdx.value
        if (idx < 0) return false
        val added = userPrefs.toggleFavorite(idx)
        _favorites.value = userPrefs.getFavorites()
        showOsd(if (added) "已收藏" else "已取消收藏")
        return added
    }

    /** 添加频道到队列 */
    fun addToQueue(idx: Int) {
        userPrefs.addToQueue(idx)
        _queue.value = userPrefs.getQueue()
        showOsd("已加入队列")
    }

    /** 从队列移除 */
    fun removeFromQueue(idx: Int) {
        userPrefs.removeFromQueue(idx)
        _queue.value = userPrefs.getQueue()
    }

    /** 清空历史 */
    fun clearHistory() {
        userPrefs.clearHistory()
        _history.value = emptyList()
        showOsd("历史已清空")
    }

    /** 清空队列 */
    fun clearQueue() {
        userPrefs.clearQueue()
        _queue.value = emptyList()
        showOsd("队列已清空")
    }

    // -----------------------------------------------------------------
    // OSD
    // -----------------------------------------------------------------

    /** 显示 OSD（3 秒后自动隐藏） */
    fun showOsd(title: String, subtitle: String = "", extra: String = "") {
        _osd.value = OsdInfo(title, subtitle, extra)
        osdHideJob?.cancel()
        osdHideJob = viewModelScope.launch {
            delay(3_000L)
            _osd.value = null
        }
    }

    /** 隐藏 OSD */
    fun hideOsd() {
        osdHideJob?.cancel()
        _osd.value = null
    }

    // -----------------------------------------------------------------
    // 面板控制
    // -----------------------------------------------------------------

    fun toggleChannelsPanel() {
        _channelsPanelOpen.value = !_channelsPanelOpen.value
        // 关闭面板时自动显示控制层（避免面板关闭后控制层不显示）
        if (!_channelsPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleEpgPanel() {
        _epgPanelOpen.value = !_epgPanelOpen.value
        if (!_epgPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleMenuPanel() {
        _menuPanelOpen.value = !_menuPanelOpen.value
        if (!_menuPanelOpen.value) _controlsVisible.value = true
    }
    /** TV 端统一面板切换（打开时关闭其他面板，关闭时恢复控制层） */
    fun toggleTvUnifiedPanel() {
        _tvUnifiedPanelOpen.value = !_tvUnifiedPanelOpen.value
        if (_tvUnifiedPanelOpen.value) {
            // 打开统一面板时关闭其他面板
            _channelsPanelOpen.value = false
            _epgPanelOpen.value = false
            _menuPanelOpen.value = false
        } else {
            _controlsVisible.value = true
        }
    }
    fun toggleControls() { _controlsVisible.value = !_controlsVisible.value }

    fun closeAllPanels() {
        _channelsPanelOpen.value = false
        _epgPanelOpen.value = false
        _menuPanelOpen.value = false
        _tvUnifiedPanelOpen.value = false
        _sourceManagerOpen.value = false
        _playerSettingsOpen.value = false
        _videoSettingsOpen.value = false
        _audioSettingsOpen.value = false
        _subtitleSettingsOpen.value = false
        _subtitleSearchOpen.value = false
        _playbackPanelOpen.value = false
        _screenshotPanelOpen.value = false
        _viewSettingsOpen.value = false
        _aboutPanelOpen.value = false
        _openUrlDialogOpen.value = false
        _mappingPanelOpen.value = false
        _avSyncPanelOpen.value = false
        _networkPanelOpen.value = false
        _toolsPanelOpen.value = false
        _scanPanelOpen.value = false
        _reminderPanelOpen.value = false
        _resumePanelOpen.value = false
        _bookmarkPanelOpen.value = false
        _epgTimelineOpen.value = false
        _searchPanelOpen.value = false
        _streamQualityPanelOpen.value = false
        stopScanPolling()
        // 关闭 A/V 同步采样
        stopAvSyncSampling()
        stopSubSync()
        // 关闭所有面板后自动显示控制层
        _controlsVisible.value = true
    }

    /**
     * 是否有任意面板打开（只读查询，不关闭面板）。
     * 用于 TV 端 DPAD 路由：面板打开时方向键交给 Compose 焦点系统在面板内导航。
     */
    val anyPanelOpen: Boolean
        get() = _channelsPanelOpen.value || _epgPanelOpen.value ||
                _menuPanelOpen.value || _tvUnifiedPanelOpen.value ||
                _sourceManagerOpen.value ||
                _playerSettingsOpen.value ||
                _videoSettingsOpen.value || _audioSettingsOpen.value ||
                _subtitleSettingsOpen.value || _subtitleSearchOpen.value || _playbackPanelOpen.value ||
                _screenshotPanelOpen.value || _viewSettingsOpen.value ||
                _aboutPanelOpen.value || _openUrlDialogOpen.value ||
                _mappingPanelOpen.value || _avSyncPanelOpen.value ||
                _networkPanelOpen.value || _toolsPanelOpen.value || _scanPanelOpen.value ||
                _reminderPanelOpen.value || _resumePanelOpen.value || _bookmarkPanelOpen.value ||
                _epgTimelineOpen.value || _searchPanelOpen.value ||
                _streamQualityPanelOpen.value

    /**
     * 关闭任意打开的面板。返回 true 表示关闭了面板（用于 BACK 键消费判断）。
     * 与 PC 端 closeFuncPanel 对齐：有关闭任何面板时返回 true，无面板时返回 false。
     */
    fun closeAnyPanel(): Boolean {
        val hadOpen = anyPanelOpen
        closeAllPanels()
        return hadOpen
    }

    fun showChannelsPanel() { _channelsPanelOpen.value = true }
    fun showEpgPanel() { _epgPanelOpen.value = true }
    fun showMenuPanel() { _menuPanelOpen.value = true }

    fun hideControls() { _controlsVisible.value = false }
    fun showControls() { _controlsVisible.value = true }

    // -----------------------------------------------------------------
    // 更多功能面板切换（主菜单 → 播放 → 各子面板）
    // -----------------------------------------------------------------

    fun toggleVideoSettings() {
        _videoSettingsOpen.value = !_videoSettingsOpen.value
        if (!_videoSettingsOpen.value) _controlsVisible.value = true
    }
    fun toggleAudioSettings() {
        _audioSettingsOpen.value = !_audioSettingsOpen.value
        if (!_audioSettingsOpen.value) _controlsVisible.value = true
    }
    fun toggleSubtitleSettings() {
        _subtitleSettingsOpen.value = !_subtitleSettingsOpen.value
        if (!_subtitleSettingsOpen.value) _controlsVisible.value = true
    }

    /** 打开/关闭字幕在线搜索面板 */
    fun toggleSubtitleSearchPanel() {
        _subtitleSearchOpen.value = !_subtitleSearchOpen.value
        if (!_subtitleSearchOpen.value) _controlsVisible.value = true
    }

    /**
     * 在线搜索字幕。三源并行（SubHD/SubtitleCat/OpenSubtitles），约 30-65s。
     * @param query 关键词/片名（支持中英文，中文会自动通过 IMDB 中转）
     * @param language 语言代码：chi/eng/jpn/all
     */
    fun searchSubtitles(query: String, language: String = "all") {
        if (query.isBlank()) {
            showOsd("字幕搜索", "请输入搜索关键词")
            return
        }
        viewModelScope.launch {
            _subtitleSearching.value = true
            _subtitleSearchError.value = ""
            _subtitleSearchResults.value = emptyList()
            val result = repository.searchSubtitles(query = query, language = language)
            _subtitleSearching.value = false
            result.onSuccess { response ->
                _subtitleSearchResults.value = response.subtitles
                _subtitleSearchError.value = response.lastError
                if (response.subtitles.isEmpty()) {
                    showOsd("字幕搜索", "未找到匹配字幕")
                } else {
                    showOsd("字幕搜索", "找到 ${response.subtitles.size} 条结果")
                }
            }.onFailure { e ->
                _subtitleSearchError.value = e.message ?: "搜索失败"
                showOsd("字幕搜索", "搜索失败: ${e.message}")
            }
        }
    }

    /**
     * 下载字幕并自动加载到播放器。
     * 仅适用于 auto_download=true 的字幕（OpenSubtitles/SubtitleCat）。
     * SubHD 的 auto_download=false，需用浏览器打开。
     */
    fun downloadAndLoadSubtitle(item: SubtitleItem) {
        viewModelScope.launch {
            _subtitleDownloading.value = true
            val destDir = File(getApplication<Application>().cacheDir, "subtitles").apply { mkdirs() }
            val result = repository.downloadSubtitle(
                downloadLink = item.downloadLink,
                destDir = destDir.absolutePath,
                fileName = item.fileName.ifBlank { "subtitle_${System.currentTimeMillis()}" },
                language = item.languageId.ifBlank { item.language }
            )
            _subtitleDownloading.value = false
            result.onSuccess { path ->
                mpv.addSubtitleFile(path)
                showOsd("字幕已加载", path.substringAfterLast('/'))
            }.onFailure { e ->
                showOsd("字幕下载失败", e.message ?: "未知错误")
            }
        }
    }
    fun togglePlaybackPanel() {
        _playbackPanelOpen.value = !_playbackPanelOpen.value
        if (!_playbackPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleScreenshotPanel() {
        _screenshotPanelOpen.value = !_screenshotPanelOpen.value
        if (!_screenshotPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleViewSettings() {
        _viewSettingsOpen.value = !_viewSettingsOpen.value
        if (!_viewSettingsOpen.value) _controlsVisible.value = true
    }
    fun toggleAboutPanel() {
        _aboutPanelOpen.value = !_aboutPanelOpen.value
        if (!_aboutPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleOpenUrlDialog() {
        _openUrlDialogOpen.value = !_openUrlDialogOpen.value
        if (!_openUrlDialogOpen.value) _controlsVisible.value = true
    }
    fun toggleMappingPanel() {
        _mappingPanelOpen.value = !_mappingPanelOpen.value
        if (_mappingPanelOpen.value) {
            loadMappings()
        } else {
            _controlsVisible.value = true
        }
    }
    fun toggleAvSyncPanel() {
        _avSyncPanelOpen.value = !_avSyncPanelOpen.value
        if (_avSyncPanelOpen.value) {
            startAvSyncSampling()
        } else {
            stopAvSyncSampling()
            stopSubSync()
            _controlsVisible.value = true
        }
    }
    fun toggleNetworkPanel() {
        _networkPanelOpen.value = !_networkPanelOpen.value
        if (!_networkPanelOpen.value) _controlsVisible.value = true
    }
    fun toggleToolsPanel() {
        _toolsPanelOpen.value = !_toolsPanelOpen.value
        if (!_toolsPanelOpen.value) _controlsVisible.value = true
    }

    // -----------------------------------------------------------------
    // URL 范围扫描（与 PC 端扫描功能对齐，后端 StandaloneScanner）
    // -----------------------------------------------------------------

    /** 打开/关闭 URL 范围扫描面板 */
    fun toggleScanPanel() {
        _scanPanelOpen.value = !_scanPanelOpen.value
        if (!_scanPanelOpen.value) {
            // 关闭面板时停止轮询（扫描本身仍在后台继续）
            stopScanPolling()
            _controlsVisible.value = true
        } else {
            // 打开面板时刷新一次状态（若仍在运行则启动轮询）
            refreshScanStatusOnce()
        }
    }

    /**
     * 启动 URL 范围扫描。baseUrl 支持 [1-255] 范围表达式
     * （如 http://192.168.1.[1-255]:8080）。启动成功后开始轮询状态。
     */
    fun startScan(baseUrl: String, timeout: Int = 10, threads: Int = 4) {
        if (baseUrl.isBlank()) {
            showOsd("扫描", "请输入基础 URL")
            return
        }
        viewModelScope.launch {
            _scanLoading.value = true
            _scanError.value = ""
            _scanResults.value = emptyList()
            val result = repository.startScan(baseUrl, timeout, threads)
            _scanLoading.value = false
            result.onSuccess { started ->
                if (started) {
                    showOsd("扫描", "已启动")
                    startScanPolling()
                } else {
                    _scanError.value = "扫描已在运行"
                    showOsd("扫描", "扫描已在运行")
                }
            }.onFailure { e ->
                _scanError.value = e.message ?: "启动失败"
                showOsd("扫描", "启动失败: ${e.message}")
            }
        }
    }

    /** 停止扫描 */
    fun stopScan() {
        viewModelScope.launch {
            val result = repository.stopScan()
            result.onSuccess {
                showOsd("扫描", "已停止")
            }.onFailure { e ->
                showOsd("扫描", "停止失败: ${e.message}")
            }
        }
    }

    /** 单次刷新状态（打开面板时用，若仍在运行则启动轮询） */
    private fun refreshScanStatusOnce() {
        viewModelScope.launch {
            val status = repository.getScanStatus().getOrNull()
            if (status == null) return@launch
            _scanStatus.value = status
            if (status.running) {
                startScanPolling()
            } else if (status.scanned > 0 && _scanResults.value.isEmpty()) {
                // 已完成的扫描但结果未加载，加载结果
                repository.getScanResults().onSuccess { _scanResults.value = it }
            }
        }
    }

    /** 启动扫描状态轮询（800ms 间隔，扫描结束后自动加载结果并停止轮询） */
    private fun startScanPolling() {
        scanPollJob?.cancel()
        scanPollJob = viewModelScope.launch {
            while (isActive) {
                delay(800)
                val statusResult = repository.getScanStatus()
                val status = statusResult.getOrNull()
                if (status == null) {
                    _scanError.value = statusResult.exceptionOrNull()?.message ?: "状态查询失败"
                    break
                }
                _scanStatus.value = status
                if (!status.running) {
                    // 扫描结束，加载结果
                    repository.getScanResults().onSuccess { _scanResults.value = it }
                    showOsd("扫描", "完成: 共 ${status.total}，有效 ${status.valid}，无效 ${status.invalid}")
                    break
                }
            }
        }
    }

    /** 停止扫描状态轮询（不停止扫描本身） */
    private fun stopScanPolling() {
        scanPollJob?.cancel()
        scanPollJob = null
    }

    // -----------------------------------------------------------------
    // 节目提醒管理（与 PC 端 controllers/epg_reminder_controller.py 对齐）
    //
    // 入口：
    // - toggleReminder(program, channel)：EPG 点击当前/未来节目时调用
    // - toggleReminderPanel()：工具菜单 → 提醒管理
    // - acceptTriggeredReminder() / dismissTriggeredReminder()：弹窗按钮
    //
    // 定时检查：
    // - startReminderCheck()：启动后每 10 秒检查一次
    // - checkReminders()：60 秒提前触发；节目结束超 1 小时清理
    // -----------------------------------------------------------------

    /**
     * 切换某节目的提醒状态（设置/取消）。
     * @param program EPG 节目（current/future 才允许）
     * @param channel 当前频道（用于保存频道信息，因 IptvEpgProgram 缺少频道关联字段）
     */
    fun toggleReminder(program: IptvEpgProgram, channel: IptvChannel?) {
        val startMs = program.startTs * 1000L
        val stopMs = program.stopTs * 1000L
        if (startMs <= 0) {
            showOsd("提醒", "节目时间无效")
            return
        }
        val chIdx = _currentIdx.value
        val id = "${chIdx}_${program.title}_${startMs}"

        if (userPrefs.hasReminder(id)) {
            // 已存在 → 取消
            userPrefs.removeReminder(id)
            notifiedReminderIds.remove(id)
            _reminders.value = userPrefs.getReminders()
            showOsd("提醒", "已取消: ${program.title}")
            return
        }

        // 新增
        val item = ReminderItem(
            id = id,
            channelIdx = chIdx,
            channelName = channel?.name ?: "",
            tvgId = channel?.tvgId ?: "",
            programTitle = program.title,
            startTs = startMs,
            stopTs = stopMs,
            createdAt = System.currentTimeMillis(),
        )
        if (userPrefs.addReminder(item)) {
            _reminders.value = userPrefs.getReminders()
            val now = System.currentTimeMillis()
            val remainingMin = (startMs - now) / 60_000
            val msg = if (remainingMin > 0) "将在 $remainingMin 分钟后开始" else "即将开始"
            showOsd("提醒已设置", "${program.title} $msg")
        }
    }

    /** 检查某节目提醒是否已存在（UI 显示状态用） */
    fun isReminderSet(program: IptvEpgProgram): Boolean {
        val chIdx = _currentIdx.value
        val startMs = program.startTs * 1000L
        val id = "${chIdx}_${program.title}_${startMs}"
        return userPrefs.hasReminder(id)
    }

    /** 打开/关闭提醒管理面板 */
    fun toggleReminderPanel() {
        _reminderPanelOpen.value = !_reminderPanelOpen.value
        if (!_reminderPanelOpen.value) {
            _controlsVisible.value = true
        } else {
            // 刷新最新数据
            _reminders.value = userPrefs.getReminders()
        }
    }

    /** 删除指定提醒 */
    fun removeReminder(id: String) {
        if (userPrefs.removeReminder(id)) {
            _reminders.value = userPrefs.getReminders()
            notifiedReminderIds.remove(id)
            showOsd("提醒", "已删除")
        }
    }

    /** 清空全部提醒 */
    fun clearReminders() {
        userPrefs.clearReminders()
        _reminders.value = emptyList()
        notifiedReminderIds.clear()
        showOsd("提醒", "已清空")
    }

    /** 用户点击"切换频道"：切到提醒对应频道并关闭弹窗 */
    fun acceptTriggeredReminder() {
        val item = _triggeredReminder.value ?: return
        _triggeredReminder.value = null
        val chIdx = item.channelIdx
        if (chIdx in _channels.value.indices) {
            playChannel(chIdx)
            showOsd("提醒", "已切换到 ${item.channelName}")
        } else {
            showOsd("提醒", "频道不可用（可能已下线）")
        }
    }

    /** 用户点击"稍后"：仅关闭弹窗，不切台 */
    fun dismissTriggeredReminder() {
        _triggeredReminder.value = null
    }

    /** 启动定时检查（10 秒间隔，对齐 PC 端 QTimer） */
    private fun startReminderCheck() {
        reminderCheckJob?.cancel()
        reminderCheckJob = viewModelScope.launch {
            while (isActive) {
                delay(10_000)
                try {
                    checkReminders()
                } catch (e: Exception) {
                    Log.w(TAG, "reminder check failed: ${e.message}")
                }
            }
        }
    }

    /** 停止定时检查 */
    private fun stopReminderCheck() {
        reminderCheckJob?.cancel()
        reminderCheckJob = null
    }

    // -----------------------------------------------------------------
    // 续播位置管理（与 PC 端 controllers/resume_playback_controller.py 对齐）
    //
    // 入口：
    // - toggleResumePanel()：工具菜单 → 续播位置
    // - playResume(item)：从断点列表恢复指定项
    // - removeResume(url) / clearResumeList()：列表管理
    //
    // 自动保存：startResumeAutoSave() 每 10 秒检查
    // 自动恢复：onFileLoaded 时调用 tryRestoreResume
    // 跳过下次恢复：skipNextResume()（队列/书签切换时设置）
    // -----------------------------------------------------------------

    /** 打开/关闭续播位置面板 */
    fun toggleResumePanel() {
        _resumePanelOpen.value = !_resumePanelOpen.value
        if (!_resumePanelOpen.value) {
            _controlsVisible.value = true
        } else {
            _resumeList.value = userPrefs.getResumeList()
        }
    }

    /** 删除指定 URL 的断点 */
    fun removeResume(url: String) {
        if (userPrefs.removeResume(url)) {
            _resumeList.value = userPrefs.getResumeList()
            showOsd("续播", "已删除")
        }
    }

    /** 清空全部断点 */
    fun clearResumeList() {
        userPrefs.clearResume()
        _resumeList.value = emptyList()
        showOsd("续播", "已清空")
    }

    /**
     * 从断点列表恢复指定项。
     * - 频道（chIdx>=0）：切台后延迟 seek
     * - 本地视频（chIdx<0）：直接 playFile 后 seek
     */
    fun playResume(item: ResumeItem) {
        _resumePanelOpen.value = false
        _controlsVisible.value = true
        // 跳过自动恢复，避免 seek 被覆盖
        skipNextResumeFlag = false  // 我们要主动 seek，不需要跳过
        if (item.channelIdx >= 0 && item.channelIdx in _channels.value.indices) {
            // 频道：切台后延迟 seek
            playChannel(item.channelIdx)
            viewModelScope.launch {
                delay(800)  // 等待 fileLoaded
                mpv.seekAbsolute(item.position.toDouble())
                showOsd("续播", "${item.name} · ${formatDuration(item.position)} / ${formatDuration(item.duration)}")
            }
        } else {
            // 本地视频：直接 playFile 后延迟 seek
            currentPlaybackUrl = item.url
            currentPlaybackName = item.name
            currentIsLocalFile = true
            _currentIdx.value = -1
            _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
            mpv.playFile(item.url)
            viewModelScope.launch {
                delay(800)
                mpv.seekAbsolute(item.position.toDouble())
                showOsd("续播", "${item.name} · ${formatDuration(item.position)} / ${formatDuration(item.duration)}")
            }
        }
    }

    /**
     * 标记跳过下次自动恢复。
     * 用于队列切换/书签跳转等场景，避免恢复到旧位置。
     */
    fun skipNextResume() {
        skipNextResumeFlag = true
    }

    /** 获取当前播放 URL（供 UI 层 LaunchedEffect 触发恢复用） */
    fun getCurrentPlaybackUrl(): String = currentPlaybackUrl

    /**
     * 文件加载完成时尝试恢复位置（由播放器回调触发）。
     * - 跳过标志为 true 时直接消费并返回
     * - 位置 <5s 或距结尾 <3s 不恢复
     * - 延迟 400ms 后 seek（与 PC 端 _on_file_loaded 对齐）
     */
    fun onFileLoadedForResume(url: String) {
        if (skipNextResumeFlag) {
            skipNextResumeFlag = false
            Log.i(TAG, "resume: skip flag consumed for $url")
            return
        }
        val resume = userPrefs.getResume(url) ?: return
        if (resume.position < 5) return
        if (resume.duration > 0 && resume.position + 3 >= resume.duration) return
        viewModelScope.launch {
            delay(400)
            mpv.seekAbsolute(resume.position.toDouble())
            Log.i(TAG, "resume: restored ${resume.name} to ${resume.position}s")
            showOsd("续播", "${resume.name} · 已恢复到 ${formatDuration(resume.position)}")
        }
    }

    /**
     * 启动自动保存定时（10 秒间隔，与 Web 端 autoSaveResume 对齐）。
     * 仅保存 VOD/本地视频（duration > 0 且 <86400），直播流不保存。
     */
    private fun startResumeAutoSave() {
        resumeSaveJob?.cancel()
        resumeSaveJob = viewModelScope.launch {
            while (isActive) {
                delay(10_000)
                try {
                    autoSaveResume()
                } catch (e: Exception) {
                    Log.w(TAG, "resume auto-save failed: ${e.message}")
                }
            }
        }
    }

    private fun stopResumeAutoSave() {
        resumeSaveJob?.cancel()
        resumeSaveJob = null
    }

    /**
     * 自动保存当前播放位置。
     * - 直播流（duration=0 或 >86400）不保存
     * - 未在播放（url 为空）不保存
     */
    private fun autoSaveResume() {
        if (currentPlaybackUrl.isEmpty()) return
        val pos = mpv.timePos.value
        val dur = mpv.duration.value
        // 直播流不保存（与 Web 端 dur>86400 判断对齐）
        if (dur <= 0 || dur > 86400) return
        if (pos < 1) return

        val item = ResumeItem(
            id = currentPlaybackUrl,
            url = currentPlaybackUrl,
            name = currentPlaybackName,
            channelIdx = if (currentIsLocalFile) -1 else _currentIdx.value,
            position = pos.toLong(),
            duration = dur.toLong(),
            updatedAt = System.currentTimeMillis(),
        )
        val newList = userPrefs.saveResume(item)
        _resumeList.value = newList
    }

    /** 格式化秒为 mm:ss 或 hh:mm:ss */
    private fun formatDuration(sec: Long): String {
        if (sec <= 0) return "00:00"
        val h = sec / 3600
        val m = (sec % 3600) / 60
        val s = sec % 60
        return if (h > 0) "%02d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
    }

    // -----------------------------------------------------------------
    // 书签管理（与 PC 端 controllers/bookmark_controller.py 对齐）
    //
    // 入口：
    // - toggleBookmarkPanel()：工具菜单 → 书签
    // - addBookmark(name)：在当前位置添加书签
    // - gotoBookmark(item)：跳转到书签位置（跨 URL 时切台 + skipNextResume）
    // - deleteBookmark(item) / clearCurrentBookmarks() / clearAllBookmarks()
    // - setBookmarkShowCurrent(show)：切换"当前文件/所有文件"视图
    // -----------------------------------------------------------------

    /** 打开/关闭书签面板 */
    fun toggleBookmarkPanel() {
        _bookmarkPanelOpen.value = !_bookmarkPanelOpen.value
        if (!_bookmarkPanelOpen.value) {
            _controlsVisible.value = true
        } else {
            // 刷新数据
            _currentBookmarks.value = userPrefs.getBookmarks(currentPlaybackUrl)
            _allBookmarks.value = userPrefs.getAllBookmarks()
        }
    }

    /** 切换视图：true=当前文件，false=所有文件 */
    fun setBookmarkShowCurrent(show: Boolean) {
        _bookmarkShowCurrent.value = show
    }

    /**
     * 在当前位置添加书签。
     * @param name 书签名（空则自动生成：文件名 @时间）
     */
    fun addBookmark(name: String = "") {
        if (currentPlaybackUrl.isEmpty()) {
            showOsd("书签", "未在播放")
            return
        }
        val pos = mpv.timePos.value
        if (pos < 1) {
            showOsd("书签", "位置无效")
            return
        }
        val finalName = if (name.isBlank()) {
            "${currentPlaybackName} @${formatDuration(pos.toLong())}"
        } else name
        val list = userPrefs.addBookmark(currentPlaybackUrl, pos.toLong(), finalName)
        _currentBookmarks.value = list
        _allBookmarks.value = userPrefs.getAllBookmarks()
        showOsd("书签已添加", "$finalName @${formatDuration(pos.toLong())}")
    }

    /**
     * 跳转到书签位置。
     * - 同 URL：直接 seek
     * - 跨 URL：在频道列表中查找，切台后延迟 seek，并调用 skipNextResume
     */
    fun gotoBookmark(item: BookmarkItem) {
        if (item.url == currentPlaybackUrl) {
            // 同 URL 直接 seek
            mpv.seekAbsolute(item.position.toDouble())
            showOsd("书签", "${item.name} @${formatDuration(item.position)}")
            _bookmarkPanelOpen.value = false
            _controlsVisible.value = true
            return
        }
        // 跨 URL：在频道列表中查找
        val chIdx = _channels.value.indexOfFirst { it.url == item.url }
        if (chIdx >= 0) {
            // 频道：切台后延迟 seek
            skipNextResume()  // 避免续播位置覆盖书签位置
            playChannel(chIdx, silent = true)
            viewModelScope.launch {
                delay(800)
                mpv.seekAbsolute(item.position.toDouble())
                showOsd("书签", "${item.name} @${formatDuration(item.position)}")
            }
            _bookmarkPanelOpen.value = false
            _controlsVisible.value = true
        } else {
            // 本地视频或网络流（不在频道列表中）
            skipNextResume()
            currentPlaybackUrl = item.url
            currentPlaybackName = item.name
            currentIsLocalFile = true
            _currentIdx.value = -1
            _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
            mpv.playFile(item.url)
            viewModelScope.launch {
                delay(800)
                mpv.seekAbsolute(item.position.toDouble())
                showOsd("书签", "${item.name} @${formatDuration(item.position)}")
            }
            _bookmarkPanelOpen.value = false
            _controlsVisible.value = true
        }
    }

    /** 删除指定书签 */
    fun deleteBookmark(item: BookmarkItem) {
        if (userPrefs.deleteBookmark(item.url, item.position)) {
            _currentBookmarks.value = userPrefs.getBookmarks(currentPlaybackUrl)
            _allBookmarks.value = userPrefs.getAllBookmarks()
            showOsd("书签", "已删除")
        }
    }

    /** 清除当前 URL 的所有书签 */
    fun clearCurrentBookmarks() {
        if (currentPlaybackUrl.isEmpty()) return
        userPrefs.clearBookmarks(currentPlaybackUrl)
        _currentBookmarks.value = emptyList()
        _allBookmarks.value = userPrefs.getAllBookmarks()
        showOsd("书签", "已清除当前文件书签")
    }

    /** 清除所有书签 */
    fun clearAllBookmarks() {
        userPrefs.clearAllBookmarks()
        _currentBookmarks.value = emptyList()
        _allBookmarks.value = emptyList()
        showOsd("书签", "已清空全部")
    }

    /** 刷新当前 URL 的书签（playChannel/playLocalVideo 后调用） */
    fun refreshCurrentBookmarks() {
        _currentBookmarks.value = userPrefs.getBookmarks(currentPlaybackUrl)
        _allBookmarks.value = userPrefs.getAllBookmarks()
    }

    /**
     * 检查提醒：
     * - 60 秒内即将开始且未通知过 → 弹窗
     * - 节目结束超过 1 小时 → 自动清理
     */
    private fun checkReminders() {
        val now = System.currentTimeMillis()
        val list = userPrefs.getReminders()
        if (list.isEmpty()) {
            if (_reminders.value.isNotEmpty()) _reminders.value = emptyList()
            return
        }

        val ONE_HOUR = 60 * 60 * 1000L
        val mutable = list.toMutableList()
        var changed = false

        // 1) 清理过期（节目结束超 1 小时）
        val expired = mutable.filter { it.stopTs in 1..(now - ONE_HOUR) }
        if (expired.isNotEmpty()) {
            expired.forEach { notifiedReminderIds.remove(it.id) }
            mutable.removeAll(expired)
            changed = true
        }

        // 2) 触发即将开始的提醒（60 秒提前）
        val triggered = mutable.firstOrNull { item ->
            val remaining = item.startTs - now
            remaining in 0..60_000 && item.id !in notifiedReminderIds &&
                    _triggeredReminder.value?.id != item.id
        }
        if (triggered != null) {
            notifiedReminderIds.add(triggered.id)
            _triggeredReminder.value = triggered
            Log.i(TAG, "reminder triggered: ${triggered.programTitle} (ch=${triggered.channelName})")
        }

        // 3) 持久化清理结果
        if (changed) {
            userPrefs.setReminders(mutable)
            _reminders.value = mutable
        }
    }

    // -----------------------------------------------------------------
    // EPG 时间线视图（与 PC 端 EpgTimelineDialog + Web 端 renderEpgTimeline 对齐）
    //
    // 多频道 × 24h 横向网格，复用 epgCache 避免重复加载，最多 30 频道。
    // -----------------------------------------------------------------

    /** 打开/关闭 EPG 时间线视图 */
    fun toggleEpgTimelinePanel() {
        _epgTimelineOpen.value = !_epgTimelineOpen.value
        if (!_epgTimelineOpen.value) {
            _controlsVisible.value = true
        } else {
            // 首次打开自动加载
            if (_epgTimelineRows.value.isEmpty()) {
                loadEpgTimeline()
            }
        }
    }

    /** 切换频道范围并重新加载 */
    fun setEpgTimelineRange(range: EpgTimelineRange) {
        if (_epgTimelineRange.value == range) return
        _epgTimelineRange.value = range
        loadEpgTimeline()
    }

    /** 切换日期（offset 范围 ±7 天） */
    fun setEpgTimelineDateOffset(offset: Int) {
        val clamped = offset.coerceIn(-7, 7)
        if (_epgTimelineDateOffset.value == clamped) return
        _epgTimelineDateOffset.value = clamped
        loadEpgTimeline()
    }

    /**
     * 加载时间线数据：按 [EpgTimelineRange] 筛选频道（最多 30 个），
     * 复用 [epgCache]，按选中日期过滤节目。
     */
    fun loadEpgTimeline() {
        val channels = _channels.value
        if (channels.isEmpty()) {
            _epgTimelineStatus.value = "无频道数据"
            _epgTimelineRows.value = emptyList()
            return
        }

        val selectedChannels = when (_epgTimelineRange.value) {
            EpgTimelineRange.ALL -> channels
            EpgTimelineRange.FAVORITES -> _favorites.value
                .mapNotNull { idx -> channels.getOrNull(idx) }
            EpgTimelineRange.CURRENT_GROUP -> {
                val group = _selectedGroup.value
                if (group.isEmpty()) channels
                else channels.filter { it.group == group }
            }
        }.take(30)

        if (selectedChannels.isEmpty()) {
            _epgTimelineStatus.value = "所选范围无频道"
            _epgTimelineRows.value = emptyList()
            return
        }

        // 选中日期的 [dayStartMs, dayEndMs) 时间范围
        val cal = java.util.Calendar.getInstance().apply {
            add(java.util.Calendar.DAY_OF_MONTH, _epgTimelineDateOffset.value)
            set(java.util.Calendar.HOUR_OF_DAY, 0)
            set(java.util.Calendar.MINUTE, 0)
            set(java.util.Calendar.SECOND, 0)
            set(java.util.Calendar.MILLISECOND, 0)
        }
        val dayStartMs = cal.timeInMillis
        val dayEndMs = dayStartMs + 24 * 60 * 60 * 1000L

        _epgTimelineLoading.value = true
        _epgTimelineStatus.value = "加载中...（${selectedChannels.size} 频道）"

        viewModelScope.launch {
            val rows = withContext(Dispatchers.IO) {
                selectedChannels.map { channel ->
                    val idx = channels.indexOf(channel)
                    // 复用缓存（fetchEpgForCurrent 已缓存的频道直接用）
                    val allPrograms = epgCache[idx] ?: run {
                        repository.getEpg(
                            channelName = channel.name,
                            tvgId = channel.tvgId,
                            tvgName = channel.tvgName,
                            commaName = channel.name
                        ).getOrDefault(IptvEpgList()).programmes.also {
                            if (it.isNotEmpty()) epgCache[idx] = it
                        }
                    }
                    // 按日期过滤（与当天有交集的节目）
                    val filtered = allPrograms.filter { p ->
                        val startMs = parseEpgTimeMs(p.start, p.startTs)
                        val endMs = parseEpgTimeMs(p.end.ifEmpty { p.stop }, p.stopTs)
                        if (startMs <= 0 || endMs <= 0) false
                        else startMs < dayEndMs && endMs > dayStartMs
                    }
                    EpgTimelineRow(idx, channel.name, filtered)
                }
            }
            _epgTimelineRows.value = rows
            _epgTimelineLoading.value = false
            val totalPrograms = rows.sumOf { it.programs.size }
            _epgTimelineStatus.value = "${rows.size} 频道 / $totalPrograms 节目"
        }
    }

    /** 时间解析辅助（与 EpgPanel.kt parseTimeToMs 对齐，避免私有函数跨文件可见性问题） */
    private fun parseEpgTimeMs(iso: String, ts: Long): Long {
        if (ts > 0) return ts * 1000L
        if (iso.isEmpty()) return 0
        val patterns = listOf(
            "yyyy-MM-dd'T'HH:mm:ssXXX",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd HH:mm"
        )
        for (pattern in patterns) {
            try {
                return SimpleDateFormat(pattern, Locale.US).parse(iso)?.time ?: continue
            } catch (_: Exception) {
            }
        }
        return iso.toLongOrNull()?.let { if (it > 1_000_000_000_000L) it else it * 1000 } ?: 0
    }

    // -----------------------------------------------------------------
    // 全局搜索（与 PC 端 UnifiedSearchDialog + Web 端 search 面板对齐）
    //
    // 频道搜索本地过滤，节目搜索异步遍历 epgCache，上限 200 条。
    // -----------------------------------------------------------------

    /** 打开/关闭全局搜索面板 */
    fun toggleSearchPanel() {
        _searchPanelOpen.value = !_searchPanelOpen.value
        if (!_searchPanelOpen.value) {
            _controlsVisible.value = true
            searchJob?.cancel()
        }
    }

    /** 切换搜索范围 */
    fun setSearchScope(scope: SearchScope) {
        if (_searchScope.value == scope) return
        _searchScope.value = scope
    }

    /**
     * 执行搜索（防抖 250ms，与 PC 端一致）。
     * - 频道：本地过滤 name/group/url 包含关键字（大小写不敏感）
     * - 节目：异步遍历 epgCache，匹配 title/desc 包含关键字，上限 200 条
     * @param query 搜索关键字（空则清空结果）
     */
    fun performSearch(query: String) {
        searchJob?.cancel()
        if (query.isBlank()) {
            _searchResults.value = emptyList()
            _searchLoading.value = false
            return
        }
        _searchLoading.value = true
        searchJob = viewModelScope.launch {
            delay(250)  // 防抖
            val q = query.trim()
            val scope = _searchScope.value
            val results = mutableListOf<SearchResult>()

            // 频道搜索（主线程快速过滤）
            if (scope == SearchScope.ALL || scope == SearchScope.CHANNELS) {
                val channels = _channels.value
                val seenUrls = HashSet<String>()
                channels.forEachIndexed { idx, ch ->
                    if (ch.name.contains(q, ignoreCase = true) ||
                        ch.group.contains(q, ignoreCase = true) ||
                        ch.url.contains(q, ignoreCase = true)
                    ) {
                        if (seenUrls.add(ch.url)) {  // 按 url 去重（与 PC 端一致）
                            results.add(SearchResult.ChannelResult(idx, ch))
                        }
                    }
                }
            }

            // 节目搜索（异步遍历 epgCache）
            if (scope == SearchScope.ALL || scope == SearchScope.PROGRAMS) {
                val channels = _channels.value
                val maxResults = 200  // 与 PC 端 MAX_RESULTS 一致
                for ((channelIdx, programs) in epgCache) {
                    if (results.size >= maxResults) break
                    val channel = channels.getOrNull(channelIdx) ?: continue
                    for (p in programs) {
                        if (results.size >= maxResults) break
                        if (p.title.contains(q, ignoreCase = true) ||
                            p.desc.contains(q, ignoreCase = true)
                        ) {
                            results.add(
                                SearchResult.ProgramResult(channelIdx, channel.name, p)
                            )
                        }
                    }
                }
            }

            _searchResults.value = results
            _searchLoading.value = false
        }
    }

    /**
     * 搜索结果点击处理（与 PC 端 _on_global_search_channel_selected + _on_epg_search_program_selected 对齐）：
     * - 频道：切台并播放
     * - 节目：切台，若为过去节目则触发 catchup
     */
    fun onSearchResultClick(result: SearchResult) {
        when (result) {
            is SearchResult.ChannelResult -> {
                playChannel(result.idx, silent = true)
                closeAllPanels()
            }
            is SearchResult.ProgramResult -> {
                playChannel(result.channelIdx, silent = true)
                // 判断是否为过去节目（与 PC 端 _on_epg_search_program_selected 对齐）
                val now = System.currentTimeMillis()
                val startMs = parseEpgTimeMs(result.program.start, result.program.startTs)
                val endMs = parseEpgTimeMs(
                    result.program.end.ifEmpty { result.program.stop }, result.program.stopTs
                )
                if (startMs in 1 until now && endMs in 1 until now && endMs < now) {
                    // 过去节目：延迟触发 catchup（等频道切换完成）
                    viewModelScope.launch {
                        delay(800)
                        startCatchup(result.program)
                    }
                }
                closeAllPanels()
            }
        }
    }

    // -----------------------------------------------------------------
    // 流质量检测（与 PC 端 get_live_media_info + Web 端 stream_quality 面板对齐）
    //
    // 详细展示 mpv 实时流信息，数据只读无需持久化。
    // -----------------------------------------------------------------

    /** 打开/关闭流质量检测面板 */
    fun toggleStreamQualityPanel() {
        _streamQualityPanelOpen.value = !_streamQualityPanelOpen.value
        if (!_streamQualityPanelOpen.value) {
            _controlsVisible.value = true
        }
    }

    // -----------------------------------------------------------------
    // HDR 模式切换（与 PC 端 _apply_hdr_on_file_loaded / _set_hdr_mode 对齐）
    //
    // Android 端简化为 4 种模式：DISABLE / AUTO / TONEMAP / PASSTHROUGH
    // - 不改变 vo（保持用户持久化选择），只在文件加载时应用 HDR 配置
    // - 不支持 d3d11-output-csp（D3D11 专属）和 target-colorspace-hint（vo 不支持）
    // - AUTO 模式：Android 端检测系统 HDR 较复杂，固定走 tonemap（与 PC 端 fallback 一致）
    // -----------------------------------------------------------------

    /**
     * 设置 HDR 输出模式：持久化 + 更新状态 + 立即应用到当前已加载视频。
     * 切换模式时若已有视频加载，会即时应用新配置，无需重新打开视频。
     */
    fun setHdrMode(mode: HdrMode) {
        if (_hdrMode.value == mode) return
        userPrefs.setHdrMode(mode.name.lowercase())
        _hdrMode.value = mode
        // 立即应用到当前已加载的视频
        if (mpv.fileLoaded.value) {
            applyHdrOnFileLoaded()
        }
        val modeName = when (mode) {
            HdrMode.DISABLE -> "禁用 HDR（强制 SDR）"
            HdrMode.AUTO -> "自动（系统未启用 HDR → tonemap）"
            HdrMode.TONEMAP -> "HDR→SDR 色调映射"
            HdrMode.PASSTHROUGH -> "HDR 直通（PQ 输出）"
        }
        showOsd("HDR 模式：$modeName")
        Log.i(TAG, "HDR 模式切换：$mode")
    }

    /**
     * 文件加载完成后应用 HDR 配置。
     * 在 MainPlayerScreen 的 LaunchedEffect(fileLoaded) 中调用。
     *
     * 流程（与 PC 端 _apply_hdr_on_file_loaded 一致）：
     * 1. disable → 重置为 SDR 默认值（target-prim=bt.709, target-trc=bt.1886）
     * 2. 非 disable 时检测视频是否 HDR（gamma 含 pq/hlg 或 sig-peak > 100）
     *    - 非 HDR 视频 → 重置 SDR 默认值
     *    - HDR 视频 + tonemap → 色调映射到 SDR
     *    - HDR 视频 + passthrough → PQ 直通
     *    - HDR 视频 + auto → Android 端固定 tonemap（系统 HDR 检测复杂）
     */
    fun applyHdrOnFileLoaded() {
        val mode = _hdrMode.value
        val mpv = this.mpv
        if (!mpv.fileLoaded.value) return

        try {
            // disable 模式：直接重置 SDR 参数
            if (mode == HdrMode.DISABLE) {
                resetHdrParams(mpv)
                Log.i(TAG, "HDR 配置：disable → 重置 SDR 默认值")
                return
            }

            // 检测视频是否 HDR
            val gamma = (mpv.getPropertyString("video-params/gamma") ?: "").lowercase()
            val prim = (mpv.getPropertyString("video-params/primaries") ?: "").lowercase()
            val peak = mpv.getPropertyDouble("video-params/sig-peak") ?: 0.0
            val isHdr = gamma.contains("pq") || gamma.contains("smpte2084") ||
                    gamma.contains("hlg") || gamma.contains("arib-std-b67") || peak > 100.0
            Log.i(TAG, "HDR 检测：gamma=$gamma, primaries=$prim, sig_peak=$peak, isHdr=$isHdr")

            if (!isHdr) {
                // 非 HDR 视频也重置 SDR 参数（避免残留上次 HDR 配置）
                resetHdrParams(mpv)
                Log.i(TAG, "HDR 配置：非 HDR 视频 → 重置 SDR 默认值")
                return
            }

            when (mode) {
                HdrMode.TONEMAP, HdrMode.AUTO -> applyTonemapConfig(mpv)
                HdrMode.PASSTHROUGH -> applyPassthroughConfig(mpv)
                else -> resetHdrParams(mpv)
            }
            Log.i(TAG, "HDR 配置：mode=$mode 应用完成")
        } catch (e: Exception) {
            Log.e(TAG, "应用 HDR 设置失败", e)
        }
    }

    /**
     * 重置 HDR 参数为 SDR 默认值（与 PC 端 _reset_hdr_params 对齐）。
     * 显式指定 SDR 目标，确保 bt.2020 色域（WCG）视频能正确映射到 bt.709。
     */
    private fun resetHdrParams(mpv: Player) {
        mpv.setPropertyString("tone-mapping", "")
        mpv.setPropertyString("tone-mapping-mode", "")
        mpv.setPropertyString("tone-mapping-desat", "")
        mpv.setPropertyString("hdr-compute-peak", "")
        mpv.setPropertyString("hdr10-opt", "no")
        mpv.setPropertyString("target-prim", "bt.709")
        mpv.setPropertyString("target-trc", "bt.1886")
    }

    /**
     * HDR→SDR 色调映射配置（与 PC 端 _apply_tonemap_config 对齐）。
     * 关键：hdr-compute-peak=no 信任 HDR10+ 动态元数据，不自行计算峰值。
     * tone-mapping=auto 让 mpv 自动选择算法（HDR10+→st2094-40, HDR10/HLG→bt.2390）。
     */
    private fun applyTonemapConfig(mpv: Player) {
        mpv.setPropertyString("tone-mapping", "auto")
        mpv.setPropertyString("tone-mapping-mode", "auto")
        mpv.setPropertyString("tone-mapping-desat", "0.5")
        mpv.setPropertyString("hdr-compute-peak", "no")
        mpv.setPropertyString("hdr10-opt", "yes")
        mpv.setPropertyString("target-prim", "bt.709")
        mpv.setPropertyString("target-trc", "bt.1886")
    }

    /**
     * HDR 直通配置（与 PC 端 _apply_passthrough_config 对齐）。
     * 显式指定 HDR 目标色域和传递特性（PQ OETF 依赖明确 target-trc 才能正确转换）。
     */
    private fun applyPassthroughConfig(mpv: Player) {
        mpv.setPropertyString("tone-mapping", "clip")
        mpv.setPropertyString("hdr-compute-peak", "no")
        mpv.setPropertyString("hdr10-opt", "yes")
        mpv.setPropertyString("target-prim", "bt.2020")
        mpv.setPropertyString("target-trc", "pq")
    }

    // -----------------------------------------------------------------
    // 文件操作（打开播放列表 / 打开网络流 / 打开本地视频）
    // 与 PC 端 文件 菜单组对齐
    // -----------------------------------------------------------------

    /**
     * 播放本地视频文件（直接调 mpv.playFile，不走频道列表）。
     * @param uri SAF 返回的 content:// URI 或 file:// 路径
     */
    fun playLocalVideo(uri: String) {
        Log.i(TAG, "playLocalVideo: $uri")
        _currentIdx.value = -1  // 清除当前频道选择（本地视频不在频道列表中）
        _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
        // 续播位置：记录本地视频信息
        currentPlaybackUrl = uri
        currentPlaybackName = uri.substringAfterLast('/').substringAfterLast('%')
        currentIsLocalFile = true
        // 刷新当前 URL 的书签列表
        refreshCurrentBookmarks()
        mpv.playFile(uri)
        showOsd("本地视频", currentPlaybackName)
        closeAllPanels()
    }

    /**
     * 播放网络流 URL（直接调 mpv.playFile，不走频道列表）。
     * @param url M3U/M3U8/HLS/RTSP/RTMP 等协议 URL
     */
    fun playUrl(url: String) {
        if (url.isBlank()) {
            showOsd("请输入 URL")
            return
        }
        Log.i(TAG, "playUrl: $url")
        _currentIdx.value = -1
        _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
        // 续播位置：记录网络流信息（VOD 才保存，直播流自动过滤）
        currentPlaybackUrl = url
        currentPlaybackName = url
        currentIsLocalFile = true  // 网络流走本地视频路径（chIdx=-1）
        // 刷新当前 URL 的书签列表
        refreshCurrentBookmarks()
        mpv.playFile(url)
        showOsd("网络流", url)
        closeAllPanels()
    }

    /**
     * 从 M3U 文件 URI 导入频道到列表。
     * 读取文件内容后调用 repository.importChannels。
     * @param uri SAF 返回的 content:// URI
     */
    fun importPlaylist(uri: Uri) {
        viewModelScope.launch {
            showOsd("正在导入播放列表...")
            val content = withContext(Dispatchers.IO) {
                try {
                    getApplication<Application>().contentResolver.openInputStream(uri)?.use {
                        it.bufferedReader().readText()
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "importPlaylist read failed", e)
                    null
                }
            } ?: run {
                showOsd("导入失败", "无法读取文件")
                return@launch
            }
            val result = repository.importChannels(content)
            result.fold(
                onSuccess = { count ->
                    showOsd("导入成功", "已导入 $count 个频道")
                    loadChannels()
                },
                onFailure = { e ->
                    showOsd("导入失败", e.message ?: "")
                }
            )
        }
    }

    /**
     * 从本地字幕文件 URI 加载外挂字幕。
     * @param uri SAF 返回的 content:// URI
     */
    fun loadSubtitleFile(uri: Uri) {
        viewModelScope.launch {
            // SAF 返回的 content:// URI 需要拷贝到缓存目录才能给 mpv 用
            val subFile = withContext(Dispatchers.IO) {
                try {
                    val resolver = getApplication<Application>().contentResolver
                    val cacheDir = getApplication<Application>().cacheDir
                    val tempFile = File(cacheDir, "subtitle_${System.currentTimeMillis()}.srt")
                    resolver.openInputStream(uri)?.use { input ->
                        tempFile.outputStream().use { input.copyTo(it) }
                    }
                    tempFile.absolutePath
                } catch (e: Exception) {
                    Log.e(TAG, "loadSubtitleFile copy failed", e)
                    null
                }
            } ?: run {
                showOsd("字幕加载失败", "无法读取文件")
                return@launch
            }
            mpv.addSubtitleFile(subFile)
            showOsd("字幕已加载", subFile.substringAfterLast('/'))
        }
    }

    /**
     * 截图到 Pictures/IPTV_Screenshots 目录。
     * @param mode "video"（仅画面）/ "subtitles"（含字幕）/ "window"（含 OSD）
     */
    fun takeScreenshot(mode: String = "video") {
        viewModelScope.launch {
            val now = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val filename = "screenshot_$now.png"

            val savedPath = withContext(Dispatchers.IO) {
                try {
                    val app = getApplication<Application>()
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        // Android 10+ 用 MediaStore 写到 Pictures 目录
                        val resolver = app.contentResolver
                        val values = ContentValues().apply {
                            put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
                            put(MediaStore.MediaColumns.MIME_TYPE, "image/png")
                            put(MediaStore.MediaColumns.RELATIVE_PATH, "Pictures/IPTV_Screenshots")
                        }
                        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                            ?: return@withContext null
                        // mpv screenshot-to-file 需要文件路径，不能直接写 content:// URI
                        // 先截到缓存目录，再复制到 MediaStore
                        val cacheFile = File(app.cacheDir, filename)
                        mpv.screenshotToFile(cacheFile.absolutePath, mode)
                        // 等待截图文件写入（mpv 异步执行）
                        var retry = 0
                        while (!cacheFile.exists() && retry < 10) {
                            Thread.sleep(200)
                            retry++
                        }
                        if (cacheFile.exists()) {
                            resolver.openOutputStream(uri)?.use { out ->
                                cacheFile.inputStream().use { it.copyTo(out) }
                            }
                            cacheFile.delete()
                            "Pictures/IPTV_Screenshots/$filename"
                        } else null
                    } else {
                        // Android 9 及以下，直接写到公共目录
                        @Suppress("DEPRECATION")
                        val dir = File(
                            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES),
                            "IPTV_Screenshots"
                        )
                        if (!dir.exists()) dir.mkdirs()
                        val file = File(dir, filename)
                        mpv.screenshotToFile(file.absolutePath, mode)
                        var retry = 0
                        while (!file.exists() && retry < 10) {
                            Thread.sleep(200)
                            retry++
                        }
                        if (file.exists()) file.absolutePath else null
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "takeScreenshot failed", e)
                    null
                }
            }
            if (savedPath != null) {
                showOsd("截图已保存", savedPath)
            } else {
                showOsd("截图失败")
            }
        }
    }

    // -----------------------------------------------------------------
    // 连拍截图（与 PC 端 BurstScreenshotDialog 对齐）
    // 按可配置间隔定时截图，复用 takeScreenshot()
    // -----------------------------------------------------------------

    private val _burstActive = MutableStateFlow(false)
    val burstActive: StateFlow<Boolean> = _burstActive.asStateFlow()

    private val _burstCount = MutableStateFlow(0)
    val burstCount: StateFlow<Int> = _burstCount.asStateFlow()

    private val _burstTotal = MutableStateFlow(0)
    val burstTotal: StateFlow<Int> = _burstTotal.asStateFlow()

    private var burstJob: kotlinx.coroutines.Job? = null

    /**
     * 开始连拍截图。
     * @param intervalSec 间隔秒数（0.5~60）
     * @param total 总张数（1~999）
     * @param mode 截图模式（video/subtitles/window）
     */
    fun startBurstScreenshot(intervalSec: Double, total: Int, mode: String = "video") {
        if (_burstActive.value) return
        _burstActive.value = true
        _burstCount.value = 0
        _burstTotal.value = total
        showOsd("连拍截图", "开始：间隔 ${intervalSec}s，共 $total 张")
        burstJob = viewModelScope.launch {
            for (i in 1..total) {
                if (!isActive) break
                _burstCount.value = i
                takeScreenshot(mode)
                if (i < total) {
                    kotlinx.coroutines.delay((intervalSec * 1000).toLong())
                }
            }
            _burstActive.value = false
            showOsd("连拍截图", "完成：$total 张已保存到 Pictures/IPTV_Screenshots")
        }
    }

    /** 停止连拍截图 */
    fun stopBurstScreenshot() {
        burstJob?.cancel()
        burstJob = null
        _burstActive.value = false
        showOsd("连拍截图", "已停止（已拍 ${_burstCount.value} 张）")
    }

    // -----------------------------------------------------------------
    // 订阅源管理（主菜单 → 文件 → 订阅源管理）
    // -----------------------------------------------------------------

    fun toggleSourceManager() {
        _sourceManagerOpen.value = !_sourceManagerOpen.value
        if (_sourceManagerOpen.value) {
            loadSources()
            loadEpgSources()
            // 刷新频道列表：用户可能通过局域网管理页面在电脑端添加了订阅源，
            // 服务器端已自动加载频道，这里同步到 Android 端
            loadChannels()
            refreshAdminServerStatus()
        } else {
            // 关闭面板时自动显示控制层
            _controlsVisible.value = true
        }
    }

    fun setSourceTab(tab: SourceTab) { _sourceTab.value = tab }

    // -----------------------------------------------------------------
    // 播放器设置（vo / hwdec）
    //
    // 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
    // 用户可手动切换 vo（gpu / mediacodec_embed），立即生效并持久化。
    // -----------------------------------------------------------------

    fun togglePlayerSettings() {
        _playerSettingsOpen.value = !_playerSettingsOpen.value
        if (!_playerSettingsOpen.value) _controlsVisible.value = true
    }

    /**
     * 切换 video output（gpu / mediacodec_embed）。
     * - 持久化到 UserPrefs（下次启动生效）
     * - 动态切换 mpv vo（立即生效，重新加载当前文件）
     * - 更新 voFallbackTriggered 状态
     */
    fun setPlayerVo(vo: String) {
        userPrefs.setVo(vo)
        _currentVo.value = vo
        val hwdec = if (vo == "mediacodec_embed") "mediacodec" else userPrefs.getHwdec()
        if (vo == "mediacodec_embed") {
            // 切换到 mediacodec_embed 时，hwdec 也应为 mediacodec
            userPrefs.setHwdec(hwdec)
            _currentHwdec.value = hwdec
            // 标记已 fallback（不需要再黑屏检测）
            userPrefs.setVoFallbackConfirmed(true)
        } else if (vo == "gpu") {
            // 切换回 gpu 时，清除 fallback 标记，重新启用黑屏检测
            userPrefs.setVoFallbackConfirmed(false)
        }
        // vo 切换只在 MPV 模式下有意义（其他播放器无 vo 概念）
        val hasFile = (_player.value as? MpvController)?.setVoAndHwdec(vo, hwdec)
        showOsd(
            "播放器设置",
            "vo=$vo" + if (hasFile != null) "，已重新加载" else "（重启后生效）"
        )
    }

    /**
     * 切换 hwdec（auto-copy / mediacodec / no）。
     * 注意：hwdec 必须与 vo 匹配：
     * - vo=gpu → hwdec=auto-copy 或 no
     * - vo=mediacodec_embed → hwdec=mediacodec
     */
    fun setPlayerHwdec(hwdec: String) {
        userPrefs.setHwdec(hwdec)
        _currentHwdec.value = hwdec
        (_player.value as? MpvController)?.setVoAndHwdec(_currentVo.value, hwdec)
        showOsd("播放器设置", "hwdec=$hwdec")
    }

    /**
     * 重置播放器设置为默认值（vo=gpu, hwdec=auto-copy）。
     * 用户换设备或想重新探测黑屏时调用。
     */
    fun resetPlayerSettings() {
        userPrefs.resetPlayerSettings()
        _currentVo.value = userPrefs.getVo()
        _currentHwdec.value = userPrefs.getHwdec()
        _hdrMode.value = HdrMode.DISABLE
        // 恢复默认应立即生效：若当前不是 MPV，切换回 MPV（MPV 是默认内核）
        // switchPlayer 内部会 detach 旧播放器 + 重建 View + 恢复播放进度
        if (_playerType.value != PlayerType.MPV) {
            switchPlayer(PlayerType.MPV)
        } else {
            (_player.value as? MpvController)?.setVoAndHwdec(_currentVo.value, _currentHwdec.value)
            // 已加载视频时立即应用重置后的 HDR 配置（disable → SDR 默认值）
            if (mpv.fileLoaded.value) {
                applyHdrOnFileLoaded()
            }
        }
        showOsd("播放器设置", "已重置为默认值")
    }

    // -----------------------------------------------------------------
    // 备份与恢复（订阅源 + EPG 源 + 收藏/历史/队列 + 播放器设置）
    //
    // 解决卸载重装数据丢失问题：
    // - 导出：完整配置打包写入 Downloads/IPTV_backup_YYYYMMDD_HHmmss.json
    // - 导入：从备份文件恢复所有配置，触发 reload 加载频道
    // -----------------------------------------------------------------

    /** 导出完整配置到下载目录 */
    fun exportConfig() {
        viewModelScope.launch {
            showOsd("备份", "正在导出配置...")
            val pyConfig = withContext(Dispatchers.IO) { repository.exportConfig() }
            pyConfig.fold(
                onSuccess = { pyJson ->
                    val fullBackup = buildFullBackup(pyJson)
                    val written = writeBackupToFile(fullBackup)
                    if (written) {
                        showOsd("备份", "已导出到下载目录")
                    } else {
                        showOsd("备份", "导出失败：无法写入文件")
                    }
                },
                onFailure = { showOsd("备份", "导出失败", it.message ?: "") }
            )
        }
    }

    /** 从指定 URI 恢复配置（由 SAF 文件选择器回调触发） */
    fun importConfig(uri: Uri) {
        viewModelScope.launch {
            showOsd("恢复", "正在导入配置...")
            val result = withContext(Dispatchers.IO) {
                val json = readBackupFromFile(uri)
                    ?: return@withContext Result.failure<Unit>(Exception("读取文件失败"))
                restoreFullBackup(json)
            }
            result.fold(
                onSuccess = {
                    showOsd("恢复", "配置已恢复，正在加载频道...")
                    loadSources()
                    loadEpgSources()
                    loadChannels()
                    loadUserPrefs()
                },
                onFailure = { showOsd("恢复", "恢复失败", it.message ?: "") }
            )
        }
    }

    /** 构建完整备份 JSON：Python 配置 + UserPrefs */
    private fun buildFullBackup(pyConfigJson: String): String {
        val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
        val pyConfig = JSONObject(pyConfigJson)
        val backup = JSONObject().apply {
            put("backup_version", 1)
            put("backup_time", now)
            // Python 配置（订阅源 + EPG 源）
            put("playlist_sources", pyConfig.optJSONArray("playlist_sources") ?: JSONArray())
            put("epg_sources", pyConfig.optJSONArray("epg_sources") ?: JSONArray())
            // UserPrefs 配置（收藏/历史/队列）
            put("favorites", JSONArray(userPrefs.getFavorites().toList()))
            put("history", JSONArray(userPrefs.getHistory()))
            put("queue", JSONArray(userPrefs.getQueue()))
            // 播放器设置
            put("player_vo", userPrefs.getVo())
            put("player_hwdec", userPrefs.getHwdec())
            put("player_vo_fallback", userPrefs.isVoFallbackConfirmed())
        }
        return backup.toString(2)
    }

    /** 恢复完整备份：Python 配置 + UserPrefs */
    private suspend fun restoreFullBackup(json: String): Result<Unit> {
        return try {
            val backup = JSONObject(json)
            // 构造 Python import_config 需要的 JSON（只含 playlist_sources + epg_sources）
            val pyConfig = JSONObject().apply {
                put("playlist_sources", backup.optJSONArray("playlist_sources") ?: JSONArray())
                put("epg_sources", backup.optJSONArray("epg_sources") ?: JSONArray())
            }
            val pyResult = repository.importConfig(pyConfig.toString())
            if (pyResult.isFailure) return pyResult

            // 恢复 UserPrefs
            backup.optJSONArray("favorites")?.let { arr ->
                val set = (0 until arr.length()).mapNotNull { arr.optInt(it, -1).takeIf { i -> i >= 0 } }.toSet()
                userPrefs.setFavorites(set)
            }
            backup.optJSONArray("history")?.let { arr ->
                val list = (0 until arr.length()).mapNotNull { arr.optInt(it, -1).takeIf { i -> i >= 0 } }
                userPrefs.setHistory(list)
            }
            backup.optJSONArray("queue")?.let { arr ->
                val list = (0 until arr.length()).mapNotNull { arr.optInt(it, -1).takeIf { i -> i >= 0 } }
                userPrefs.setQueue(list)
            }
            backup.optString("player_vo").takeIf { it.isNotEmpty() }?.let { userPrefs.setVo(it) }
            backup.optString("player_hwdec").takeIf { it.isNotEmpty() }?.let { userPrefs.setHwdec(it) }
            if (backup.has("player_vo_fallback")) {
                userPrefs.setVoFallbackConfirmed(backup.optBoolean("player_vo_fallback"))
            }

            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "restoreFullBackup failed", e)
            Result.failure(e)
        }
    }

    /** 写入备份文件到下载目录（Android 10+ 用 MediaStore，旧版本用公共目录） */
    private fun writeBackupToFile(json: String): Boolean {
        val now = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val filename = "IPTV_backup_$now.json"
        return try {
            val app = getApplication<Application>()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val resolver = app.contentResolver
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
                    put(MediaStore.MediaColumns.MIME_TYPE, "application/json")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return false
                resolver.openOutputStream(uri)?.use { it.write(json.toByteArray()) } ?: return false
            } else {
                @Suppress("DEPRECATION")
                val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                if (!dir.exists()) dir.mkdirs()
                File(dir, filename).writeText(json)
            }
            Log.i(TAG, "Backup written to Downloads/$filename")
            true
        } catch (e: Exception) {
            Log.e(TAG, "writeBackupToFile failed", e)
            false
        }
    }

    /** 从指定 URI 读取备份文件 */
    private fun readBackupFromFile(uri: Uri): String? {
        return try {
            val resolver = getApplication<Application>().contentResolver
            resolver.openInputStream(uri)?.use { it.bufferedReader().readText() }
        } catch (e: Exception) {
            Log.e(TAG, "readBackupFromFile failed", e)
            null
        }
    }

    fun loadSources() {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.getSources() }
            result.onSuccess { _sources.value = it }
                .onFailure { showOsd("加载订阅源失败", it.message ?: "") }
        }
    }

    fun loadEpgSources() {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.getEpgSources() }
            result.onSuccess { _epgSources.value = it }
                .onFailure { showOsd("加载 EPG 源失败", it.message ?: "") }
        }
    }

    fun addSource(url: String, name: String = "") {
        if (url.isBlank()) {
            showOsd("请输入订阅源 URL")
            return
        }
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.addSource(url, name) }
            result.onSuccess {
                showOsd("订阅源已添加", "正在加载频道...")
                loadSources()
                // 新添加的订阅源默认 enabled=true，自动触发重载以加载频道列表
                reloadSources()
            }.onFailure { showOsd("添加失败", it.message ?: "") }
        }
    }

    fun addEpgSource(url: String, name: String = "") {
        if (url.isBlank()) {
            showOsd("请输入 EPG 订阅源 URL")
            return
        }
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.addEpgSource(url, name) }
            result.onSuccess {
                showOsd("EPG 源已添加", "正在重载 EPG...")
                loadEpgSources()
                // 自动触发 EPG 重载
                reloadEpgSources()
            }.onFailure { showOsd("添加失败", it.message ?: "") }
        }
    }

    fun deleteSource(idx: Int) {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.deleteSource(idx) }
            result.onSuccess {
                showOsd("订阅源已删除")
                loadSources()
            }.onFailure { showOsd("删除失败", it.message ?: "") }
        }
    }

    fun deleteEpgSource(idx: Int) {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.deleteEpgSource(idx) }
            result.onSuccess {
                showOsd("EPG 源已删除")
                loadEpgSources()
            }.onFailure { showOsd("删除失败", it.message ?: "") }
        }
    }

    fun toggleSourceEnabled(idx: Int, enabled: Boolean) {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) {
                repository.updateSource(idx, mapOf("enabled" to enabled.toString()))
            }
            result.onSuccess { loadSources() }
                .onFailure { showOsd("更新失败", it.message ?: "") }
        }
    }

    fun reloadSources() {
        viewModelScope.launch {
            _sourceLoading.value = true
            showOsd("正在重载订阅源...")
            val result = withContext(Dispatchers.IO) { repository.reloadSources() }
            result.onSuccess { started ->
                if (started) {
                    showOsd("订阅源重载已启动", "请稍候...")
                    pollSourceStatus()
                } else {
                    _sourceLoading.value = false
                    showOsd("订阅源重载失败")
                }
            }.onFailure {
                _sourceLoading.value = false
                showOsd("重载失败", it.message ?: "")
            }
        }
    }

    fun reloadEpgSources() {
        viewModelScope.launch {
            showOsd("正在重载 EPG...")
            val result = withContext(Dispatchers.IO) { repository.reloadEpg() }
            result.onSuccess { showOsd("EPG 重载已启动") }
                .onFailure { showOsd("EPG 重载失败", it.message ?: "") }
        }
    }

    /** 轮询订阅源加载状态，完成后自动刷新频道列表 */
    private fun pollSourceStatus() {
        viewModelScope.launch {
            val startTime = System.currentTimeMillis()
            while (isActive) {
                if (System.currentTimeMillis() - startTime > 60_000L) {
                    _sourceLoading.value = false
                    showOsd("订阅源加载超时")
                    return@launch
                }
                val result = withContext(Dispatchers.IO) { repository.getSourceStatus() }
                result.onSuccess { status ->
                    _sourceLoading.value = status.loading
                    _sourceMessage.value = status.message
                    if (!status.loading) {
                        showOsd("订阅源加载完成", "频道数: ${status.channelsTotal}")
                        loadChannels()
                        return@launch
                    }
                }
                delay(1000L)
            }
        }
    }

    // -----------------------------------------------------------------
    // 局域网管理服务器（TV 端遥控器输入不便，手机浏览器扫码管理）
    // -----------------------------------------------------------------

    fun toggleAdminServer() {
        if (_adminServerRunning.value) {
            stopAdminServer()
        } else {
            startAdminServer()
        }
    }

    fun startAdminServer() {
        viewModelScope.launch {
            showOsd("正在启动局域网管理服务器...")
            val result = withContext(Dispatchers.IO) { repository.startAdminServer(8080) }
            result.onSuccess { info ->
                _adminServerUrl.value = info.url
                if (info.running) {
                    // server 已启动（可能是 already_running）
                    _adminServerRunning.value = true
                    showOsd("局域网管理已启动", info.url)
                    startAdminCountdown()
                } else {
                    // server 正在后台启动（Chaquopy import 中），启动轮询检测
                    _adminServerRunning.value = false
                    showOsd("正在后台启动...", info.url)
                    pollAdminServerStartup(info.url)
                }
            }.onFailure {
                // 记录完整错误到 logcat 方便排查（Python 端 _admin_server_error 包含 traceback）
                Log.e("AppViewModel", "Admin server start failed: ${it.message}", it)
                showOsd("启动失败", it.message ?: "")
            }
        }
    }

    /**
     * 轮询 admin server 启动状态。
     * Python 端 start_admin_server 立即返回（避免 callAttr 持有 GIL 阻塞子线程 import），
     * Kotlin 端每 2 秒调用 getAdminUrl() 检测 running，最多等待 90 秒（首次 Chaquopy import 可能 30+ 秒）。
     */
    private fun pollAdminServerStartup(url: String) {
        viewModelScope.launch {
            var pollCount = 0
            val maxPolls = 45  // 90 秒 = 45 * 2 秒
            while (pollCount < maxPolls && isActive) {
                delay(2000)
                pollCount++
                val result = withContext(Dispatchers.IO) { repository.getAdminUrl() }
                result.onSuccess { info ->
                    if (info.running) {
                        _adminServerUrl.value = info.url
                        _adminServerRunning.value = true
                        showOsd("局域网管理已启动", info.url)
                        startAdminCountdown()
                        return@launch
                    }
                    if (info.error.isNotEmpty()) {
                        _adminServerRunning.value = false
                        showOsd("启动失败", info.error)
                        return@launch
                    }
                }.onFailure {
                    Log.e("AppViewModel", "Admin server poll failed: ${it.message}", it)
                }
            }
            // 超时
            _adminServerRunning.value = false
            showOsd("启动较慢，请稍后刷新状态查看")
        }
    }

    /**
     * 启动自动停止倒计时（5 分钟 = 300 秒）。
     * 避免长时间占用端口和电量；用户可手动停止或重新启动重置倒计时。
     */
    private fun startAdminCountdown() {
        adminCountdownJob?.cancel()
        _adminCountdown.value = 300
        adminCountdownJob = viewModelScope.launch {
            while (_adminCountdown.value > 0 && isActive) {
                delay(1000)
                _adminCountdown.value -= 1
            }
            if (_adminCountdown.value <= 0 && _adminServerRunning.value) {
                showOsd("局域网管理已自动停止（超时）")
                stopAdminServer()
            }
        }
    }

    fun stopAdminServer() {
        adminCountdownJob?.cancel()
        _adminCountdown.value = 0
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.stopAdminServer() }
            result.onSuccess {
                _adminServerRunning.value = false
                showOsd("局域网管理已停止")
            }.onFailure {
                showOsd("停止失败", it.message ?: "")
            }
        }
    }

    fun refreshAdminServerStatus() {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.getAdminUrl() }
            result.onSuccess { info ->
                _adminServerUrl.value = info.url
                _adminServerRunning.value = info.running
            }
        }
    }

    // -----------------------------------------------------------------
    // 频道映射 CRUD（通过 IptvRepository 调用 Python bridge）
    // -----------------------------------------------------------------

    fun loadMappings() {
        viewModelScope.launch {
            _mappingLoading.value = true
            _mappingStatusText.value = "加载中..."
            val result = repository.getMappings()
            _mappingLoading.value = false
            result.onSuccess { list ->
                _mappingList.value = list
                _mappingStatusText.value = "共 ${list.size} 条映射"
            }.onFailure { e ->
                _mappingStatusText.value = "加载失败: ${e.message}"
                Log.e(TAG, "loadMappings failed", e)
            }
        }
    }

    fun addMapping(rawName: String, standardName: String, logoUrl: String = "", groupName: String = "") {
        if (rawName.isBlank() || standardName.isBlank()) {
            showOsd("频道映射", "原始名和标准名不能为空")
            return
        }
        viewModelScope.launch {
            _mappingLoading.value = true
            val result = repository.addMapping(rawName, standardName, logoUrl, groupName)
            _mappingLoading.value = false
            result.onSuccess {
                showOsd("频道映射", "已添加: $rawName → $standardName")
                loadMappings()
            }.onFailure { e ->
                showOsd("频道映射", "添加失败: ${e.message}")
                Log.e(TAG, "addMapping failed", e)
            }
        }
    }

    fun deleteMapping(standardName: String, rawName: String = "") {
        viewModelScope.launch {
            _mappingLoading.value = true
            val result = repository.deleteMapping(standardName, rawName)
            _mappingLoading.value = false
            result.onSuccess {
                showOsd("频道映射", "已删除")
                loadMappings()
            }.onFailure { e ->
                showOsd("频道映射", "删除失败: ${e.message}")
                Log.e(TAG, "deleteMapping failed", e)
            }
        }
    }

    fun refreshMappings() {
        viewModelScope.launch {
            _mappingLoading.value = true
            _mappingStatusText.value = "正在刷新远程映射..."
            val result = repository.refreshMappings()
            _mappingLoading.value = false
            result.onSuccess {
                _mappingStatusText.value = "远程映射已更新"
                showOsd("频道映射", "远程映射已刷新")
                loadMappings()
            }.onFailure { e ->
                _mappingStatusText.value = "刷新失败: ${e.message}"
                showOsd("频道映射", "刷新失败: ${e.message}")
                Log.e(TAG, "refreshMappings failed", e)
            }
        }
    }

    // -----------------------------------------------------------------
    // A/V 同步监控（仅 MPV 播放器支持，其他播放器属性返回 null）
    // -----------------------------------------------------------------

    /**
     * 启动 A/V 同步采样：每 100ms 读取 mpv 的 avdiff / audio-pts / video-pts / audio-delay。
     * 与 PC 端 av_sync_dialog.py 的 200ms 定时器对齐（Android 用协程替代 QTimer）。
     */
    private fun startAvSyncSampling() {
        avSyncJob?.cancel()
        avSyncJob = viewModelScope.launch {
            while (isActive) {
                // 仅 MPV 播放器支持属性读取
                val mpv = mpvSingleton
                val avdiff = mpv.getPropertyDouble("avdiff") ?: 0.0
                val aPts = mpv.getPropertyDouble("audio-pts") ?: 0.0
                val vPts = mpv.getPropertyDouble("video-pts") ?: 0.0
                val aDelay = mpv.getPropertyDouble("audio-delay") ?: 0.0
                _avDiff.value = avdiff
                _audioPts.value = aPts
                _videoPts.value = vPts
                _currentAudioDelay.value = aDelay
                // 追加历史采样（最多 200 点）
                val history = _avDiffHistory.value.toMutableList()
                history.add(avdiff.toFloat())
                while (history.size > 200) history.removeAt(0)
                _avDiffHistory.value = history
                delay(100)
            }
        }
    }

    private fun stopAvSyncSampling() {
        avSyncJob?.cancel()
        avSyncJob = null
    }

    /**
     * 设置音频延迟（秒）。
     * 仅 MPV 播放器支持（capabilities.supportsAudioDelay）。
     */
    fun adjustAudioDelay(delta: Double) {
        val newDelay = (_currentAudioDelay.value + delta)
        val player = _player.value
        if (player.capabilities.supportsAudioDelay) {
            if (player.setAudioDelay(newDelay)) {
                _currentAudioDelay.value = newDelay
                showOsd("音频延迟", "${"%.3f".format(newDelay)}s")
            }
        } else {
            showOsd("音频延迟", "当前播放器不支持")
        }
    }

    fun resetAudioDelay() {
        val player = _player.value
        if (player.capabilities.supportsAudioDelay) {
            if (player.setAudioDelay(0.0)) {
                _currentAudioDelay.value = 0.0
                showOsd("音频延迟", "已重置")
            }
        } else {
            showOsd("音频延迟", "当前播放器不支持")
        }
    }

    /**
     * 切换字幕自动同步开关。
     * 基于 avdiff 的比例控制算法（与 PC 端 _sub_sync_tick 对齐）：
     * - 每 500ms 采样 avdiff，存入 6 点滑动窗口
     * - 取最近 3+ 点平均，超过阈值（0.05s）时按 delta = avg * gain（0.30）调整 sub_delay
     * - 跳过极端值（>1s，可能是 seek/暂停）
     */
    fun toggleSubSync() {
        _subSyncEnabled.value = !_subSyncEnabled.value
        if (_subSyncEnabled.value) {
            startSubSync()
            showOsd("字幕同步", "已开启自动同步")
        } else {
            stopSubSync()
            showOsd("字幕同步", "已关闭自动同步")
        }
    }

    private var subSyncWindow = ArrayDeque<Float>()

    private fun startSubSync() {
        subSyncJob?.cancel()
        subSyncWindow.clear()
        subSyncJob = viewModelScope.launch {
            while (isActive) {
                val avdiff = _avDiff.value.toFloat()
                // 跳过极端值（>1s，可能是 seek/暂停）
                if (kotlin.math.abs(avdiff) < 1.0f) {
                    subSyncWindow.addLast(avdiff)
                    while (subSyncWindow.size > 6) subSyncWindow.removeFirst()
                    // 需要至少 3 个采样点
                    if (subSyncWindow.size >= 3) {
                        val avg = subSyncWindow.takeLast(3).average().toFloat()
                        val threshold = 0.05f
                        if (kotlin.math.abs(avg) > threshold) {
                            val gain = 0.30f
                            val delta = avg * gain
                            val mpv = mpvSingleton
                            val currentSubDelay = mpv.getPropertyDouble("sub-delay") ?: 0.0
                            mpv.setSubDelay(currentSubDelay + delta)
                        }
                    }
                }
                delay(500)
            }
        }
    }

    private fun stopSubSync() {
        subSyncJob?.cancel()
        subSyncJob = null
        subSyncWindow.clear()
    }

    // -----------------------------------------------------------------
    // 网络增强（HTTP Referer / Proxy / Headers，仅 MPV 播放器支持）
    // -----------------------------------------------------------------

    /** 加载持久化的网络设置（面板打开时调用） */
    fun loadNetworkSettings(): Triple<String, String, String> {
        return Triple(
            userPrefs.getHttpReferer(),
            userPrefs.getHttpProxy(),
            userPrefs.getHttpHeaders()
        )
    }

    /**
     * 应用网络设置到当前播放器（实时下发，仅对 MPV 有效）。
     * 注意：referer 和 http-proxy 对当前播放的流不会立即生效，下次 loadfile 时才生效。
     */
    fun applyNetworkSettings(referer: String, proxy: String, headers: String) {
        val mpv = mpvSingleton
        // Referer
        if (referer.isNotBlank()) {
            mpv.setPropertyString("referrer", referer)
        } else {
            mpv.setPropertyString("referrer", "")
        }
        // HTTP Proxy
        if (proxy.isNotBlank()) {
            mpv.setPropertyString("http-proxy", proxy)
        } else {
            mpv.setPropertyString("http-proxy", "")
        }
        // HTTP Headers（每行 "Key: Value"，需逐条设置）
        // mpv 的 http-header-fields 是列表属性，通过 command 设置
        if (headers.isNotBlank()) {
            headers.lines().filter { it.contains(":") }.forEach { line ->
                val parts = line.split(":", limit = 2)
                if (parts.size == 2) {
                    val key = parts[0].trim()
                    val value = parts[1].trim()
                    mpv.command(arrayOf("set", "http-header-fields", "$key: $value"))
                }
            }
        }
        showOsd("网络增强", "已应用（下次加载生效）")
    }

    /** 保存网络设置到持久化存储 + 应用 */
    fun saveNetworkSettings(referer: String, proxy: String, headers: String) {
        userPrefs.setHttpReferer(referer)
        userPrefs.setHttpProxy(proxy)
        userPrefs.setHttpHeaders(headers)
        applyNetworkSettings(referer, proxy, headers)
    }

    /** 清除所有网络设置 */
    fun clearNetworkSettings() {
        userPrefs.setHttpReferer("")
        userPrefs.setHttpProxy("")
        userPrefs.setHttpHeaders("")
        val mpv = mpvSingleton
        mpv.setPropertyString("referrer", "")
        mpv.setPropertyString("http-proxy", "")
        showOsd("网络增强", "已清除")
    }

    // -----------------------------------------------------------------
    // ViewModel 生命周期
    // -----------------------------------------------------------------

    override fun onCleared() {
        super.onCleared()
        statusPollJob?.cancel()
        osdHideJob?.cancel()
        avSyncJob?.cancel()
        subSyncJob?.cancel()
        reminderCheckJob?.cancel()
        resumeSaveJob?.cancel()
        // 退出前保存最后一次位置
        try { autoSaveResume() } catch (_: Exception) {}
    }

    // -----------------------------------------------------------------
    // 工具函数
    // -----------------------------------------------------------------

    /** 类似 Kotlin 的 takeIf 但用于 if-else 表达式 */
    private fun <T> T.ifElse(other: T, predicate: () -> Boolean): T =
        if (predicate()) this else other

    companion object {
        private const val TAG = "AppViewModel"

        fun factory(app: Application): ViewModelProvider.AndroidViewModelFactory =
            object : ViewModelProvider.AndroidViewModelFactory(app) {}
    }
}
