package com.iptv.scanner.editor.pro.ui

import android.app.Application
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import androidx.core.content.FileProvider
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
import com.iptv.scanner.editor.pro.data.RecentEntry
import com.iptv.scanner.editor.pro.data.ResumeItem
import com.iptv.scanner.editor.pro.data.BookmarkItem
import com.iptv.scanner.editor.pro.data.ChannelPlayerSettings
import com.iptv.scanner.editor.pro.data.ScanResult
import com.iptv.scanner.editor.pro.data.ScanStatus
import com.iptv.scanner.editor.pro.data.SubtitleItem
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.mpv.MpvController
import com.iptv.scanner.editor.pro.player.CatchupHelper
import com.iptv.scanner.editor.pro.player.CatchupProgram
import com.iptv.scanner.editor.pro.player.ExoPlayerWrapper
import com.iptv.scanner.editor.pro.player.FccHelper
import com.iptv.scanner.editor.pro.player.FccService
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.SubPlayer
import com.iptv.scanner.editor.pro.player.SubPlayerState
import com.iptv.scanner.editor.pro.player.PlaybackState
import com.iptv.scanner.editor.pro.player.Player
import com.iptv.scanner.editor.pro.data.SpeedConfig
import com.iptv.scanner.editor.pro.player.PlayerCapabilities
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.player.ProgressHelper
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
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
data class ChannelDisplayInfo(
    val name: String = "",
    val logo: String = "",
    val group: String = "",
    val idx: Int = -1,
    val isLocal: Boolean = false
)

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val repository = IptvRepository.getInstance()
    private val userPrefs = UserPrefs.getInstance().also { it.init(app) }
    private val fccService = FccService()

    // 辅助类：从 AppViewModel 拆分出的独立业务模块
    internal val scanHelper = ScanHelper(repository, viewModelScope, userPrefs)
    internal val mappingHelper = MappingHelper(repository, viewModelScope)
    internal val updateHelper = UpdateHelper(app, repository, viewModelScope)

    // -----------------------------------------------------------------
    // 播放器架构：MPV / ExoPlayer / 系统解码 三内核可切换
    //
    // - mpvSingleton：MpvController 单例（MPVLib.create 只能调一次，需复用）
    // - exoWrapper：ExoPlayerWrapper 实例（EXO 硬解 / SYSTEM 软解）
    // - mpv：公共字段（类型为 Player 接口），当前活跃的播放器实例
    // - playerType：当前播放器类型（MPV / EXO / SYSTEM）
    // - playerCapabilities：当前播放器能力（UI 据此决定哪些功能面板可用）
    //
    // 切换播放器类型时：
    // 1. 停止当前播放器并 detach View
    // 2. 切换 _player 到新播放器实例
    // 3. MainPlayerScreen 根据 playerType 创建对应的 View（MPVView / PlayerView）
    // 4. 新 View 的 factory 中调用 player.attachView(view) 绑定
    // -----------------------------------------------------------------
    private val mpvSingleton: MpvController = MpvController.getInstance()
    private var exoWrapper: ExoPlayerWrapper? = null

    /**
     * 持久化的播放器类型（从 UserPrefs 读取，支持运行时切换）。
     */
    private val _playerType = MutableStateFlow(
        PlayerType.fromName(userPrefs.getPlayerType())
    )
    val playerType: StateFlow<PlayerType> = _playerType.asStateFlow()

    /** 内核切换后待播放的 URL（延迟播放机制：等 Compose 重建视图后再 playFile） */
    private val _pendingSwitchPlayUrl = MutableStateFlow("")
    val pendingSwitchPlayUrl: StateFlow<String> = _pendingSwitchPlayUrl.asStateFlow()

    /**
     * 当前活跃的 Player 实例。
     *
     * 关键修复：根据持久化的 playerType 初始化正确的播放器实例。
     * 之前硬编码为 mpvSingleton，导致启动时若上次保存的是 EXO/SYSTEM 模式，
     * _player 仍指向 MpvController（无 View），所有 playFile 命令被跳过。
     */
    private val _player = MutableStateFlow<Player>(
        when (_playerType.value) {
            PlayerType.MPV -> mpvSingleton
            PlayerType.EXO, PlayerType.SYSTEM -> {
                ExoPlayerWrapper(getApplication(), _playerType.value).also {
                    exoWrapper = it
                }
            }
        }
    )

    /** 当前播放器实例（Player 接口类型，UI 用 mpv.xxx 调用 Player 接口方法） */
    val mpv: Player get() = _player.value

    val playerCapabilities: StateFlow<PlayerCapabilities> =
        _player.map { it.capabilities }
            .stateIn(viewModelScope, SharingStarted.Eagerly, mpvSingleton.capabilities)

    /**
     * 切换播放器类型（MPV / EXO / SYSTEM）。
     *
     * 切换流程：
     * 1. 保存当前播放 URL（用于切换后恢复播放）
     * 2. 停止并 detach 当前播放器
     * 3. 创建/复用目标播放器实例
     * 4. 更新 _playerType 和 _player
     * 5. 持久化设置
     * 6. 恢复播放（如果有当前频道）
     */
    fun switchPlayerType(newType: PlayerType) {
        if (_playerType.value == newType) return
        Log.i(TAG, "switchPlayerType: ${_playerType.value} -> $newType")

        // 保存当前播放状态
        val savedUrl = currentPlaybackUrl
        val savedIdx = _currentIdx.value

        // 取消所有定时器
        timeoutSwitchJob?.cancel()
        timeoutSwitchJob = null
        reconnectJob?.cancel()
        reconnectJob = null
        switchPlayJob?.cancel()
        switchPlayJob = null
        consecutiveTimeoutCount = 0

        // 1. 先停止当前播放器（同步停止，防止旧播放器继续播放声音）
        _player.value.stop()
        _player.value.detach()

        // 2. 先更新 _playerType，触发 Compose 重组
        //    key(playerType) 会销毁旧 View（触发 onRelease）并创建新 View（触发 factory + attachView）
        _playerType.value = newType

        // 3. 创建新播放器实例
        val newPlayer: Player = when (newType) {
            PlayerType.MPV -> {
                // MPV 单例已被 detach，attachView 时会重新绑定
                mpvSingleton
            }
            PlayerType.EXO, PlayerType.SYSTEM -> {
                // 每次都重建 ExoPlayer wrapper，确保渲染器配置正确
                exoWrapper?.detach()
                exoWrapper = ExoPlayerWrapper(getApplication(), newType).also {
                    it.setHardwareDecode(newType == PlayerType.EXO)
                }
                exoWrapper!!
            }
        }
        _player.value = newPlayer
        userPrefs.setPlayerType(newType.name)

        showOsd("播放器已切换到 ${newType.displayName}")

        // 设置待播放 URL，由 MainPlayerScreen 的 update 回调在 attachView 后播放
        if (savedIdx >= 0 && savedUrl.isNotEmpty()) {
            _pendingSwitchPlayUrl.value = savedUrl
        }
    }

    fun clearPendingSwitchPlayUrl() {
        _pendingSwitchPlayUrl.value = ""
    }

    /**
     * 兼容方法：消费待恢复的播放状态（当前仅 MPV 单实例，始终返回 null）。
     * 保留方法签名以兼容 MainPlayerScreen 调用。
     */
    fun consumePendingRestore(): Pair<String, Double>? = null

    /**
     * 释放旧播放器 View（切换播放器类型时由 MainPlayerScreen onRelease 调用）。
     * 对于 ExoPlayer 需要真正 detach；MPV 单例只 detach 不销毁。
     */
    fun detachOldPlayer() {
        // 由 MainPlayerScreen onRelease 回调中调用
        // ExoPlayer 的 View 销毁时需要 detach
        if (_playerType.value != PlayerType.MPV) {
            _player.value.detach()
        }
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

    private val _channelDisplayInfo = MutableStateFlow(ChannelDisplayInfo())
    val channelDisplayInfo: StateFlow<ChannelDisplayInfo> = _channelDisplayInfo.asStateFlow()

    private val _switchingFrame = MutableStateFlow<android.graphics.Bitmap?>(null)
    val switchingFrame: StateFlow<android.graphics.Bitmap?> = _switchingFrame.asStateFlow()

    // -----------------------------------------------------------------
    // 多画面状态（TV 端多画面功能）
    //
    // 主画面（index=0）用 MPV（单例）。
    // 副画面（index=1+）用 ExoPlayer（SubPlayer），支持多实例同时播放。
    // -----------------------------------------------------------------
    private val _multiViewState = MutableStateFlow(MultiViewState())
    val multiViewState: StateFlow<MultiViewState> = _multiViewState.asStateFlow()

    /** 副画面播放器实例池（key=视口索引，value=SubPlayer） */
    private val subPlayers = mutableMapOf<Int, SubPlayer>()

    /** 副画面播放器状态流（UI 观察用，key=视口索引） */
    private val _subPlayerStates = MutableStateFlow<Map<Int, SubPlayerState>>(emptyMap())
    val subPlayerStates: StateFlow<Map<Int, SubPlayerState>> = _subPlayerStates.asStateFlow()

    // -----------------------------------------------------------------
    // 频道列表面板状态
    // -----------------------------------------------------------------
    enum class ChannelTab { SUB, LOCAL, FAV, HIST }

/** 竖屏底部 Tab（首页/列表/工具/设置） */
enum class PortraitTab { HOME, LIST, TOOLS, SETTINGS }

/** 列表页视图模式 */
enum class ListViewMode { LIST, THUMBNAIL }

/** 列表页数据源 */
enum class ListSourceTab { SUBSCRIPTION, LOCAL }

private val _portraitTab = MutableStateFlow(PortraitTab.HOME)
val portraitTab: StateFlow<PortraitTab> = _portraitTab.asStateFlow()

/** 列表页视图模式：列表 / 缩略图 */
private val _listViewMode = MutableStateFlow(ListViewMode.LIST)
val listViewMode: StateFlow<ListViewMode> = _listViewMode.asStateFlow()

/** 列表页数据源：订阅 / 本地 */
private val _listSourceTab = MutableStateFlow(ListSourceTab.SUBSCRIPTION)
val listSourceTab: StateFlow<ListSourceTab> = _listSourceTab.asStateFlow()

/** 竖屏首页/播放器模式切换：true=首页（浏览），false=播放器界面
 * TV 模式无首页，始终为 false，避免 playChannel 走 pendingSwitchPlayUrl 分支导致黑屏 */
private val _showHome = MutableStateFlow(!UiModeDetector.detect(app).isTV)
val showHome: StateFlow<Boolean> = _showHome.asStateFlow()

/** 切换到播放器界面（选择频道/打开文件后调用） */
fun showPlayerScreen() {
    _showHome.value = false
    // 播放器 Surface 重新创建后，需要重新加载当前频道
    val idx = _currentIdx.value
    val url = currentPlaybackUrl
    if (idx >= 0 && url.isNotEmpty()) {
        viewModelScope.launch {
            delay(200)  // 等 Surface 创建完成
            if (mpv.fileLoaded.value) {
                // 已在播放，刷新 Surface
                mpv.refreshSurface()
            } else {
                // 重新加载频道
                mpv.playFile(url)
            }
            Log.i(TAG, "showPlayerScreen: restored playback for $url")
        }
    }
}

/** 切换回首页（播放器界面的返回按钮调用，视频继续播放） */
fun showHomeScreen() {
    _showHome.value = true
    // 播放器被移除渲染，需要暂停播放（避免后台播放占用资源）
    // 如果需要后台继续播放音频，注释掉这行
    // mpv.setPause(true)
}

/** 切换列表视图模式 */
fun setListViewMode(mode: ListViewMode) {
    _listViewMode.value = mode
}

/** 切换列表数据源 */
fun setListSourceTab(tab: ListSourceTab) {
    _listSourceTab.value = tab
}

fun setPortraitTab(tab: PortraitTab) {
        _portraitTab.value = tab
    }

    /** 获取指定频道的缓存 EPG 当前节目（用于频道列表显示） */
    fun getCachedCurrentProgram(idx: Int): IptvEpgProgram? {
        val programs = epgCache[idx] ?: return null
        return ProgressHelper.findCurrentProgram(programs, System.currentTimeMillis())
    }

/** 打开 EPG 面板（不重载视频） */
fun playChannelAndShowEpg(idx: Int) {
    // 不调用 playChannel，避免重载视频。只获取该频道 EPG 数据并显示面板。
    if (idx != _currentIdx.value) {
        _currentIdx.value = idx
    }
    fetchEpgForCurrent()
    showEpgPanel()
}

    /** 频道信息详情面板 */
    private val _channelInfoOpen = MutableStateFlow(false)
    val channelInfoOpen: StateFlow<Boolean> = _channelInfoOpen.asStateFlow()

    fun toggleChannelInfo() {
        _channelInfoOpen.value = !_channelInfoOpen.value
    }

    /** 判断指定频道是否已收藏 */
    fun isChannelFavorite(idx: Int): Boolean = _favorites.value.contains(idx)

    /** 切换指定频道收藏状态 */
    fun toggleFavoriteByIndex(idx: Int): Boolean {
        val added = userPrefs.toggleFavorite(idx)
        _favorites.value = userPrefs.getFavorites()
        showOsd(if (added) "已收藏" else "已取消收藏")
        return added
    }

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
    // 超时换源 / 断线重连 / 倍速控制（与酷9对齐）
    // -----------------------------------------------------------------

    /** 超时换源定时器：播放超时后自动切到下一个源 */
    private var timeoutSwitchJob: Job? = null
private var switchPlayJob: Job? = null

    /**
     * 连续超时换源计数器：防止所有频道都无法播放时无限循环换台。
     * 每次成功加载（fileLoaded=true）时重置为 0。
     * 超过阈值时停止自动换源，避免"换了内核也一直自动换台"的死循环。
     */
    private var consecutiveTimeoutCount = 0

    /** 超时换源档位（0-5），0=5s ... 5=30s */
    private val _timeoutSwitchSource = MutableStateFlow(userPrefs.getTimeoutSwitchSource())
    val timeoutSwitchSource: StateFlow<Int> = _timeoutSwitchSource.asStateFlow()

    /** 断线重连定时器 */
    private var reconnectJob: Job? = null

    /**
     * 文件加载错误自动换源 Job：onFileError 回调中启动的延迟换源任务。
     *
     * 关键：用户手动切台时必须取消此 Job，避免以下竞态条件：
     * 坏频道触发 onFileError → 1秒延迟中用户手动切回好频道 →
     * nextChannel() 执行，把好频道切走。
     */
    private var fileErrorSwitchJob: Job? = null

    /** 断线重连档位（0-5），0=关闭 ... 5=20s */
    private val _reconnectIndex = MutableStateFlow(userPrefs.getReconnectIndex())
    val reconnectIndex: StateFlow<Int> = _reconnectIndex.asStateFlow()

    /** 倍速双步进配置 */
    private val _speedConfig = MutableStateFlow(userPrefs.getSpeedConfig())
    val speedConfig: StateFlow<SpeedConfig> = _speedConfig.asStateFlow()

    // -----------------------------------------------------------------
    // 时移 URL 重建冷却（与 PC 端 catchup_controller.URL_REBUILD_COOLDOWN 对齐）
    // -----------------------------------------------------------------
    /** URL 重建冷却时间（秒），防止频繁重建导致服务器拒绝 */
    private val urlRebuildCooldown = 3.0

    /** 上次 URL 重建的时间戳（System.nanoTime 转秒） */
    private var lastUrlRebuildTime: Double = 0.0

    /** 是否有待执行的冷却后 seek */
    private var urlRebuildPending: Boolean = false

    /** 冷却后待执行的 seek 百分比（0-100） */
    private var pendingSeekAfterCooldown: Double? = null

    /** 冷却定时器 Job */
    private var cooldownJob: Job? = null

    /** 时移续播 Job */
    private var continueTimeshiftJob: Job? = null

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

    /** EPG 缓存版本号，每次更新缓存时递增，用于触发 UI 刷新 */
    private val _epgCacheVersion = MutableStateFlow(0)
    val epgCacheVersion: StateFlow<Int> = _epgCacheVersion.asStateFlow()

    private val _currentEpg = MutableStateFlow<List<IptvEpgProgram>>(emptyList())
    val currentEpg: StateFlow<List<IptvEpgProgram>> = _currentEpg.asStateFlow()

    private val _epgLoading = MutableStateFlow(false)
    val epgLoading: StateFlow<Boolean> = _epgLoading.asStateFlow()

    /** TV 统一面板中焦点频道的 EPG（独立于当前播放频道的 EPG） */
    private val _focusedEpg = MutableStateFlow<List<IptvEpgProgram>>(emptyList())
    val focusedEpg: StateFlow<List<IptvEpgProgram>> = _focusedEpg.asStateFlow()

    private val _focusedEpgLoading = MutableStateFlow(false)
    val focusedEpgLoading: StateFlow<Boolean> = _focusedEpgLoading.asStateFlow()

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

/** 歌词行（与 PC 端 LyricsWidget 对齐） */
data class LyricsLine(val time: Long, val text: String)

    private val _osd = MutableStateFlow<OsdInfo?>(null)
    val osd: StateFlow<OsdInfo?> = _osd.asStateFlow()

    /** OSD 持久模式（菜单触发时启用，不自动隐藏，再次选中 OSD 时关闭） */
    private val _osdPinned = MutableStateFlow(false)
    val osdPinned: StateFlow<Boolean> = _osdPinned.asStateFlow()

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

    /** 文件浏览器面板（SAF 不可用时的替代方案，浏览本地 M3U/媒体文件） */
    private val _fileBrowserOpen = MutableStateFlow(false)
    val fileBrowserOpen: StateFlow<Boolean> = _fileBrowserOpen.asStateFlow()

    /** 文件浏览器模式：PLAYLIST（选择 M3U 导入）/ MEDIA（选择音视频文件播放） */
    enum class FileBrowserMode { PLAYLIST, MEDIA }
    private val _fileBrowserMode = MutableStateFlow(FileBrowserMode.PLAYLIST)
    val fileBrowserMode: StateFlow<FileBrowserMode> = _fileBrowserMode.asStateFlow()

    /** TV 端统一面板（三列：模式切换 + 频道列表/主菜单 + EPG 节目单） */
    private val _tvUnifiedPanelOpen = MutableStateFlow(false)
    val tvUnifiedPanelOpen: StateFlow<Boolean> = _tvUnifiedPanelOpen.asStateFlow()

    private val _controlsVisible = MutableStateFlow(true)
    val controlsVisible: StateFlow<Boolean> = _controlsVisible.asStateFlow()

    /** 横屏沉浸侧边栏可见性 */
    private val _landscapeSidebarVisible = MutableStateFlow(false)
    val landscapeSidebarVisible: StateFlow<Boolean> = _landscapeSidebarVisible.asStateFlow()

    fun setLandscapeSidebarVisible(visible: Boolean) {
        _landscapeSidebarVisible.value = visible
        if (visible) {
            _controlsVisible.value = true
        }
    }


    /** 控制层持久模式（菜单 OSD 按钮触发，不自动隐藏，再次选中关闭） */
    private val _controlsPinned = MutableStateFlow(false)
    val controlsPinned: StateFlow<Boolean> = _controlsPinned.asStateFlow()

    /** TV 端控制面板自动隐藏定时器（几秒后自动隐藏） */
    private var tvControlsAutoHideJob: kotlinx.coroutines.Job? = null

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

    /** 频道缩略图路径缓存：url -> file_path */
    private val _thumbnailPaths = MutableStateFlow<Map<String, String>>(emptyMap())
    val thumbnailPaths: StateFlow<Map<String, String>> = _thumbnailPaths.asStateFlow()

    /** 缩略图生成进度：null=未在生成, Pair(current, total)=正在生成 */
    private val _thumbnailGenProgress = MutableStateFlow<Pair<Int, Int>?>(null)
    val thumbnailGenProgress: StateFlow<Pair<Int, Int>?> = _thumbnailGenProgress.asStateFlow()

    /** 当前选中的订阅源 URL（空=全部） */
    private val _selectedSource = MutableStateFlow("")
    val selectedSource: StateFlow<String> = _selectedSource.asStateFlow()

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

    // RTSP 传输协议（tcp/udp），供 UI 显示和切换
    private val _currentRtspTransport = MutableStateFlow(userPrefs.getRtspTransport())
    val currentRtspTransport: StateFlow<String> = _currentRtspTransport.asStateFlow()

// 反交错（no/auto），供 UI 显示和切换
private val _currentDeinterlace = MutableStateFlow(userPrefs.getDeinterlace())
val currentDeinterlace: StateFlow<String> = _currentDeinterlace.asStateFlow()

// 日志等级（debug/info/warn/error），与 PC 端 core/log_manager.py 对齐
private val _logLevel = MutableStateFlow(userPrefs.getLogLevel())
val logLevel: StateFlow<String> = _logLevel.asStateFlow()

    /** 当前是否使用硬件解码（所有播放器内核通用，UI 通过 collectAsState 自动响应） */
    private val _hardwareDecode = MutableStateFlow(userPrefs.getHwdec() != "no")

    init {
        // 注册 MPV 黑屏 fallback 回调：当 vo=gpu 渲染黑屏自动 fallback 到 mediacodec_embed 时，
        // 同步更新 UI 状态（_currentVo / _currentHwdec），使设置面板的选中项正确显示。
        // 不持久化（仅本次会话），避免误判永久化。
mpvSingleton.onVoFallback = { vo, hwdec ->
_currentVo.value = vo
_currentHwdec.value = hwdec
Log.i(TAG, "onVoFallback: UI updated vo=$vo, hwdec=$hwdec (session only)")
}

// 注册文件加载错误回调：当 mpv 报告文件加载失败时换源，
// 添加短暂延迟避免坏流导致 mpv 核心状态未清理就加载下一个流。
mpvSingleton.onFileError = {
if (mpv.fileLoaded.value) {
    Log.i(TAG, "onFileError: skipped, file already loaded (stale callback)")
} else if (playChannelDebounceJob?.isActive == true) {
    Log.i(TAG, "onFileError: skipped, channel switch in progress (debounce job active)")
} else {
    val mpvPath = try { mpvSingleton.getPath() } catch (_: Throwable) { "" }
    if (mpvPath.isNotEmpty() && mpvPath != currentPlaybackUrl) {
        Log.i(TAG, "onFileError: skipped, mpv path='$mpvPath' != currentUrl='$currentPlaybackUrl' (stale END_FILE from previous channel)")
    } else if (_playbackState.value.mode.isCatchup || _playbackState.value.mode.isTimeshift) {
Log.w(TAG, "onFileError: in catchup/timeshift mode, skipping auto-switch")
showOsd("回看失败", "该节目可能无法回看或已过期")
_playbackState.value = PlaybackState(mode = PlayMode.LIVE)
val curIdx = _currentIdx.value
if (curIdx >= 0) {
val ch = _channels.value.getOrNull(curIdx)
if (ch != null) mpv.playFile(ch.url)
}
} else {
Log.w(TAG, "onFileError: file failed to load, triggering switch after delay")
mpvSingleton.markNeedPreStop()
timeoutSwitchJob?.cancel()
fileErrorSwitchJob?.cancel()
consecutiveTimeoutCount++
val maxConsecutive = minOf(10, maxOf(3, _channels.value.size / 3))
if (consecutiveTimeoutCount > maxConsecutive) {
Log.w(TAG, "onFileError: stopped after $consecutiveTimeoutCount consecutive errors")
consecutiveTimeoutCount = 0
showOsd("自动换源已停止", "连续加载失败，请检查网络或切换播放器内核")
} else {
showOsd("加载失败", "当前频道无法播放，自动切换")
fileErrorSwitchJob = viewModelScope.launch {
delay(1000)
if (mpv.fileLoaded.value) {
Log.i(TAG, "onFileError: skipped auto-switch, file already loaded (user manually switched)")
return@launch
}
if (_playerType.value == PlayerType.MPV) {
Log.w(TAG, "onFileError: forcing mpv state reset before switch")
mpvSingleton.forceRecreate()
mpvSingleton.markNeedPreStop()
delay(500)
}
nextChannel()
}
}
}
}
}
    }

    init {
    // 时移 EOF 自动续播：监听 mpv eofReached，在时移模式下自动重建 URL 续播
    // （与 PC 端 catchup_controller.continue_timeshift 对齐）
    viewModelScope.launch {
        mpvSingleton.eofReached.collect { eof ->
            if (eof && _playbackState.value.mode.isTimeshift) {
                Log.i(TAG, "eofReached in timeshift mode, triggering continueTimeshift")
                continueTimeshiftJob?.cancel()
                continueTimeshiftJob = viewModelScope.launch {
                    delay(500) // 短暂延迟避免与 end-file 事件竞态
                    if (_playbackState.value.mode.isTimeshift) {
                        continueTimeshift()
                    }
                }
            }
        }
    }
    }

    val hardwareDecode: StateFlow<Boolean> = _hardwareDecode.asStateFlow()

    // 局域网管理服务器
    private val _adminServerUrl = MutableStateFlow("")
    val adminServerUrl: StateFlow<String> = _adminServerUrl.asStateFlow()

    private val _adminServerToken = MutableStateFlow("")
    val adminServerToken: StateFlow<String> = _adminServerToken.asStateFlow()

    private val _adminServerRunning = MutableStateFlow(false)
    val adminServerRunning: StateFlow<Boolean> = _adminServerRunning.asStateFlow()

    /** 自动停止倒计时（秒），0 表示无倒计时。启动后 5 分钟自动停止，避免长时间占用端口和电量 */
    private val _adminCountdown = MutableStateFlow(0)

/** 遥控器数字键输入缓冲（如输入 "1","2","3" → 切换到频道 123） */
private var _channelInputBuffer: String? = null
private var _channelInputJob: kotlinx.coroutines.Job? = null
    val adminCountdown: StateFlow<Int> = _adminCountdown.asStateFlow()
    private var adminCountdownJob: Job? = null

    /** 虚拟遥控器命令轮询协程 */
    private var remotePollJob: Job? = null
    private var playerStatusJob: Job? = null

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

    // -----------------------------------------------------------------
    // 版本检查（与 PC 端 UpdateController 对齐）
    // -----------------------------------------------------------------
    /** 版本检查状态 */
    sealed class UpdateState {
        object Idle : UpdateState()
        object Checking : UpdateState()
        data class UpdateAvailable(val latestVersion: String, val downloadUrl: String, val releaseUrl: String) : UpdateState()
        object UpToDate : UpdateState()
        data class Error(val message: String) : UpdateState()
    }

    private val _updateState = MutableStateFlow<UpdateState>(UpdateState.Idle)
    val updateState: StateFlow<UpdateState> = _updateState.asStateFlow()

    /** 更新提示对话框是否显示 */
    private val _updateDialogOpen = MutableStateFlow(false)
    val updateDialogOpen: StateFlow<Boolean> = _updateDialogOpen.asStateFlow()

    // -----------------------------------------------------------------
    // 应用内 APK 下载更新（替代浏览器跳转，TV 端友好）
    // -----------------------------------------------------------------
    /** 下载状态：空闲 / 下载中 / 下载完成 / 下载失败 */
    sealed class ApkDownloadState {
        object Idle : ApkDownloadState()
        data class Downloading(val progress: Int) : ApkDownloadState()  // 0-100
        object Completed : ApkDownloadState()
        data class Error(val message: String) : ApkDownloadState()
    }

    private val _apkDownloadState = MutableStateFlow<ApkDownloadState>(ApkDownloadState.Idle)
    val apkDownloadState: StateFlow<ApkDownloadState> = _apkDownloadState.asStateFlow()

    /** 当前下载任务的 DownloadManager ID（用于取消/查询） */
    @Volatile
    private var apkDownloadId: Long = -1L

    /** 下载完成 BroadcastReceiver 实例（用于注销） */
    @Volatile
    private var apkDownloadReceiver: BroadcastReceiver? = null

    /** 下载进度轮询协程 Job */
    @Volatile
    private var apkProgressJob: Job? = null

    /** 退出确认对话框是否显示（BACK 键退出时提示：立即退出 / 进入 PiP） */
    private val _exitConfirmOpen = MutableStateFlow(false)
    val exitConfirmOpen: StateFlow<Boolean> = _exitConfirmOpen.asStateFlow()

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
    private var currentPlaybackName: String = ""
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
    // 新增功能面板（与 PC 端功能对齐）
    // -----------------------------------------------------------------

    /** 主题模式：dark / light / system */
    private val _themeMode = MutableStateFlow(userPrefs.getThemeMode())
    val themeMode: StateFlow<String> = _themeMode.asStateFlow()

    /** 最近打开文件面板 */
    private val _recentPanelOpen = MutableStateFlow(false)
    val recentPanelOpen: StateFlow<Boolean> = _recentPanelOpen.asStateFlow()
    private val _recentFiles = MutableStateFlow<List<RecentEntry>>(emptyList())
    val recentFiles: StateFlow<List<RecentEntry>> = _recentFiles.asStateFlow()

    /** 切片导出面板 */
    private val _clipExportPanelOpen = MutableStateFlow(false)
    val clipExportPanelOpen: StateFlow<Boolean> = _clipExportPanelOpen.asStateFlow()
    private val _clipExportProgress = MutableStateFlow(0)
    val clipExportProgress: StateFlow<Int> = _clipExportProgress.asStateFlow()
    private val _clipExportStatus = MutableStateFlow("")
    val clipExportStatus: StateFlow<String> = _clipExportStatus.asStateFlow()

    /** 音频可视化面板 */
    private val _audioVisualizerOpen = MutableStateFlow(false)
    val audioVisualizerOpen: StateFlow<Boolean> = _audioVisualizerOpen.asStateFlow()
    /** 频谱数据（0-1 归一化，32 个频段） */
    private val _audioSpectrum = MutableStateFlow(FloatArray(32) { 0f })
    val audioSpectrum: StateFlow<FloatArray> = _audioSpectrum.asStateFlow()

    /** 歌词面板 */
    private val _lyricsOpen = MutableStateFlow(false)
    val lyricsOpen: StateFlow<Boolean> = _lyricsOpen.asStateFlow()
    /** 当前歌词行列表 */
    private val _lyricsLines = MutableStateFlow<List<LyricsLine>>(emptyList())
    val lyricsLines: StateFlow<List<LyricsLine>> = _lyricsLines.asStateFlow()
    /** 当前高亮的歌词行索引 */
    private val _currentLyricLine = MutableStateFlow(-1)
    val currentLyricLine: StateFlow<Int> = _currentLyricLine.asStateFlow()

    val anyPanelOpenFlow: StateFlow<Boolean> = combine(
        _channelsPanelOpen, _epgPanelOpen, _menuPanelOpen, _tvUnifiedPanelOpen,
        _fileBrowserOpen, _sourceManagerOpen, _playerSettingsOpen, _videoSettingsOpen,
        _audioSettingsOpen, _subtitleSettingsOpen, _subtitleSearchOpen, _playbackPanelOpen,
        _screenshotPanelOpen, _viewSettingsOpen, _aboutPanelOpen, _mappingPanelOpen,
        _avSyncPanelOpen, _networkPanelOpen, _toolsPanelOpen, _scanPanelOpen,
        _reminderPanelOpen, _resumePanelOpen, _bookmarkPanelOpen, _epgTimelineOpen,
        _searchPanelOpen, _streamQualityPanelOpen, _recentPanelOpen, _clipExportPanelOpen,
        _audioVisualizerOpen, _lyricsOpen, _exitConfirmOpen, _channelInfoOpen,
        _openUrlDialogOpen, _updateDialogOpen, _landscapeSidebarVisible
    ) { arr -> arr.any { it } }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    /** PiP 回调（Activity 注入，ViewModel 不能直接调用 Activity 方法）
     *  使用 WeakReference 防止 Configuration Change 后旧 Activity 泄漏 */
    private var _onEnterPip: java.lang.ref.WeakReference<() -> Unit>? = null
    var onEnterPip: (() -> Unit)?
        get() = _onEnterPip?.get()
        set(value) {
            _onEnterPip = if (value != null) java.lang.ref.WeakReference(value) else null
        }

    /** 刷新 UI 状态 */
    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()

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
                // 传递 Android 存储路径给 Python（jnius 不可用时的兜底方案）
                val app = getApplication<Application>()
                val extFilesDir = app.getExternalFilesDir(null)?.absolutePath ?: ""
                val filesDir = app.filesDir.absolutePath
                val nativeLibDir = app.applicationInfo.nativeLibraryDir
                val logLevel = userPrefs.getLogLevel()
                val initResult = withContext(Dispatchers.IO) {
                    repository.initContext(extFilesDir, filesDir, logLevel, nativeLibDir)
                }
                if (initResult.isFailure) {
                    val msg = initResult.exceptionOrNull()?.message ?: "初始化失败"
                    Log.e(TAG, "initContext failed: $msg")
                    _initState.value = InitState.Failed(msg)
                    return@launch
                }
                Log.i(TAG, "initContext OK, start polling status")

                // 1.5 设置应用版本信息（供 Web 界面使用）
                val version = getCurrentVersion()
                val buildDate = getBuildDate()
                withContext(Dispatchers.IO) {
                    repository.setAppInfo(version, buildDate)
                }

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
                                // 初始化完成后延迟 5 秒自动检查更新（避免影响启动性能）
                                viewModelScope.launch {
                                    delay(5000)
                                    checkForUpdates(auto = true)
                                }
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
                    // 保存当前播放的 URL，防止频道列表更新后 currentChannel 变 null
                    val savedUrl = currentPlaybackUrl
                    val savedIdx = _currentIdx.value
                    _channels.value = page.channels
                    // 如果当前正在播放，尝试在新列表中找到对应频道
                    if (savedIdx >= 0 && savedUrl.isNotEmpty()) {
                        val newIdx = page.channels.indexOfFirst { it.url == savedUrl }
                        if (newIdx >= 0 && newIdx != savedIdx) {
                            _currentIdx.value = newIdx
                            Log.i(TAG, "loadChannels: current idx updated $savedIdx -> $newIdx")
                        } else if (newIdx < 0) {
                            // URL 不在新列表中，保持原 idx 不变（避免显示未选择频道）
                            Log.w(TAG, "loadChannels: current channel URL not found in new list, keeping idx $savedIdx")
                        }
                    }
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

    /**
     * 启动时恢复上次播放的频道。
     *
     * 优先按 URL 在频道列表中查找上次播放的频道（URL 比 idx 更稳健，即使频道顺序
     * 变化也能找到）。找不到则播放第一个频道（与之前行为一致）。
     *
     * 由 MainActivityCompose 在 InitState.Ready + channels 加载完成后调用。
     */
    fun restoreLastChannel() {
        if (_currentIdx.value >= 0) {
            // 已经在播放（可能被其他逻辑触发），不重复恢复
            return
        }
        if (!userPrefs.isAutoResumeOnStart()) {
            Log.i(TAG, "restoreLastChannel: auto-resume disabled by user, skipping")
            return
        }
        // 外部标志文件：如果存在则跳过自动续播（用于测试/调试）
        try {
            val extDir = android.os.Environment.getExternalStorageDirectory()
            val flagFile = java.io.File(extDir, "Android/data/com.iptv.scanner.editor.pro/files/ISEP/skip_auto_resume")
            if (flagFile.exists()) {
                Log.i(TAG, "restoreLastChannel: skip_auto_resume flag file exists, skipping")
                return
            }
        } catch (e: Exception) {
            // 忽略文件检查错误
        }
        val channels = _channels.value
        if (channels.isEmpty()) return

        val lastUrl = userPrefs.getLastChannelUrl()
        if (lastUrl.isNotEmpty()) {
            val lastIdx = channels.indexOfFirst { it.url == lastUrl }
            if (lastIdx >= 0) {
                Log.i(TAG, "restoreLastChannel: restoring '$lastUrl' at idx=$lastIdx")
                playChannel(lastIdx, silent = true)
                return
            }
            Log.i(TAG, "restoreLastChannel: last URL '$lastUrl' not found in ${channels.size} channels, playing first")
        }
        // 回退：播放第一个频道
        playChannel(0, silent = true)
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
                .filter { (c, _) -> c.source.isEmpty() || ProgressHelper.isLocalFile(c.url) }
            ChannelTab.FAV -> all.mapIndexed { idx, c -> c to idx }
                .filter { (c, idx) -> _favorites.value.contains(idx) }
            ChannelTab.HIST -> _history.value.mapNotNull { idx ->
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
     * 与 PC 端 playChannel 对齐：
     * 1. 重置 catchup/timeshift 状态（清空 originalChannel/catchupProgram/liveTimeshiftSeconds）
     * 2. 隐藏退出 catchup 按钮
     * 3. 设置 playMode='live'
     * 4. 调用 mpv.playFile
     * 5. 显示 OSD（频道名 + 分组）
     * 6. 关闭面板（频道列表）
     * 7. 加入历史（去重后插入队首）
     * 8. 预取 EPG
     */
    private var playChannelDebounceJob: Job? = null

    private var uiUpdateJob: kotlinx.coroutines.Job? = null

    fun playChannel(idx: Int, silent: Boolean = false) {
        val channel = _channels.value.getOrNull(idx) ?: return
        if (currentPlaybackUrl == channel.url && mpv.fileLoaded.value && _currentIdx.value == idx) {
            Log.i(TAG, "playChannel: skipped, same URL already playing")
            return
        }
        Log.i(TAG, "playChannel: ${channel.name} (${channel.url})")

        _channelDisplayInfo.value = ChannelDisplayInfo(
            name = channel.name, logo = channel.logo, group = channel.group, idx = idx,
            isLocal = channel.source.isEmpty() || ProgressHelper.isLocalFile(channel.url)
        )
        _currentIdx.value = idx
        _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
        _showHome.value = false
        currentPlaybackUrl = channel.url
        currentPlaybackName = channel.name
        currentIsLocalFile = false


        fccService.onChannelChange(channel.url)

        fileErrorSwitchJob?.cancel()
        fileErrorSwitchJob = null

        uiUpdateJob?.cancel()
        uiUpdateJob = viewModelScope.launch(kotlinx.coroutines.Dispatchers.IO) {
            val frame = mpvSingleton.captureFrameSync()
            if (frame != null) {
                withContext(kotlinx.coroutines.Dispatchers.Main) {
                    _switchingFrame.value = frame
                }
            }

            mpv.playFile(channel.url)

            if (!silent && !_landscapeSidebarVisible.value) {
                withContext(kotlinx.coroutines.Dispatchers.Main) {
                    closeAllPanelsExceptSidebar()
                }
            }
            if (!silent) {
                withContext(kotlinx.coroutines.Dispatchers.Main) {
                    if (uiMode.value.isTV) showControlsAutoHide() else showOsd(channel.name, channel.group)
                }
            }

            if (userPrefs.isPerChannelPlayerSettings() && _currentIdx.value >= 0 && _currentIdx.value != idx) {
                autoSaveCurrentSettingsToChannel(_currentIdx.value)
            }
            refreshCurrentBookmarks()

            applyChannelSettingsIfNeeded(idx)
            loadPlaybackSettingsFromStore(channel.url)
            startTimeoutSwitchSource(idx)
            userPrefs.addToHistory(idx)
            _history.value = userPrefs.getHistory()
            userPrefs.setLastChannelUrl(channel.url)
            fetchEpgForCurrent()
            prefetchAdjacentChannels(idx)
            if (uiMode.value != UiMode.TV) captureChannelThumbnail()
        }
    }

    /**
     * 启动超时换源定时器（与酷9 LIVE_CONNECT_TIMEOUT 对齐）。
     *
     * 播放开始后启动定时器，如果在超时时间内 fileLoaded 仍为 false，
     * 则自动切换到下一个频道（源），避免用户长时间等待黑屏。
     *
     * @param idx 当前频道索引（用于日志）
     */
    private fun startTimeoutSwitchSource(idx: Int) {
        timeoutSwitchJob?.cancel()
        timeoutSwitchJob = viewModelScope.launch {
            val timeoutMs = userPrefs.getTimeoutMs()
            delay(timeoutMs)
            // 超时后检查是否已加载
            if (!mpv.fileLoaded.value) {
                consecutiveTimeoutCount++
                Log.w(TAG, "Timeout switch source: idx=$idx not loaded in ${timeoutMs}ms (consecutive=$consecutiveTimeoutCount)")

                // 关键修复：连续超时 >= 1 次时，stop 命令已无法清除卡死的 demuxer，
                // 必须强制重建 mpv 核心才能恢复播放。
                // 场景：坏流的 demuxer 线程卡在网络读取上（如 TLS 握手失败），
                // stop 命令虽然被接受，但无法真正中断阻塞的 I/O 调用。
                // 后续 loadfile 命令在旧 demuxer 未释放时被发送，
                // 新流也无法加载——导致所有后续频道都无法播放。
                // forceRecreate() 通过 stop + playlist-clear 重置 mpv 内部状态（不终止核心），
                // 下次 playFile() 时 ensureInstanceAlive() 检测到 forceRecreatePending 标志后
                // 直接返回（核心仍存活，idle=yes 保证不会自动 shutdown）。
                if (consecutiveTimeoutCount >= 1 && _playerType.value == PlayerType.MPV) {
                    Log.w(TAG, "Timeout switch: forcing mpv state reset (consecutive=$consecutiveTimeoutCount)")
                    mpvSingleton.forceRecreate()
                    mpvSingleton.markNeedPreStop()
                    delay(500)
                } else {
                    mpv.stop()
                }

                // 连续超时保护：如果连续多次超时换源（超过频道总数的 1/3，最多 10 次），
                // 说明可能是网络故障或播放器核心问题，停止自动换源避免死循环。
                // 用户可以手动切台或切换播放器内核来恢复。
                val maxConsecutive = minOf(10, maxOf(3, _channels.value.size / 3))
                if (consecutiveTimeoutCount > maxConsecutive) {
                    Log.w(TAG, "Timeout switch source: stopped after $consecutiveTimeoutCount consecutive timeouts")
                    showOsd("自动换源已停止", "连续 ${consecutiveTimeoutCount} 次超时，请检查网络或切换播放器内核")
                    consecutiveTimeoutCount = 0
                    return@launch
                }

                showOsd("超时换源", "当前源加载超时，自动切换")
                nextChannel()
            }
        }
    }

    /**
     * 启动断线重连（与酷9 RECONNECT_INDEX 对齐）。
     *
     * 播放出错或 EOF 时，根据重连档位延迟后重新加载当前 URL。
     * 仅在直播模式下触发（回看/时移/本地视频不重连）。
     */
    fun startReconnect() {
        val delayMs = userPrefs.getReconnectDelayMs()
        if (delayMs <= 0) return  // 关闭重连
        if (_playbackState.value.mode != PlayMode.LIVE) return  // 仅直播重连

        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch {
            Log.i(TAG, "Reconnect in ${delayMs}ms")
            delay(delayMs)
            val url = currentPlaybackUrl
            if (url.isNotEmpty() && _playbackState.value.mode == PlayMode.LIVE) {
                Log.i(TAG, "Reconnecting: $url")
                mpv.playFile(url)
                showOsd("正在重连...")
            }
        }
    }

    // -----------------------------------------------------------------
    // 超时换源 / 断线重连 / 倍速控制 setter
    // -----------------------------------------------------------------

    /** 设置超时换源档位（0-5） */
    fun setTimeoutSwitchSource(value: Int) {
        _timeoutSwitchSource.value = value
        userPrefs.setTimeoutSwitchSource(value)
    }

    /** 设置断线重连档位（0-5） */
    fun setReconnectIndex(value: Int) {
        _reconnectIndex.value = value
        userPrefs.setReconnectIndex(value)
    }

    /**
     * 倍速加速（双步进，与酷9 Speed_value 对齐）。
     * 根据当前速度自动选择步进值：< 1.0 用慢放步进，>= 阈值用二级快放步进。
     */
    fun speedUp() {
        val config = _speedConfig.value
        val newSpeed = config.speedUp(mpv.speed.value)
        mpv.setSpeed(newSpeed)
        showOsd("倍速 ${"%.2f".format(newSpeed)}x")
    }

    /**
     * 倍速减速（双步进）。
     */
    fun speedDown() {
        val config = _speedConfig.value
        val newSpeed = config.speedDown(mpv.speed.value)
        mpv.setSpeed(newSpeed)
        showOsd("倍速 ${"%.2f".format(newSpeed)}x")
    }

    /** 倍速恢复 1.0x */
    fun speedReset() {
        mpv.setSpeed(1.0)
        showOsd("倍速 1.00x")
    }

    /** 设置倍速参数字符串（格式：min,max,slowStep,fastStep,fastStep2,threshold） */
    fun setSpeedParams(params: String) {
        userPrefs.setSpeedParams(params)
        _speedConfig.value = userPrefs.getSpeedConfig()
    }

    // -----------------------------------------------------------------
    // EPG 时区偏移（与酷9 TIME_ZONE_SELECT 对齐）
    // -----------------------------------------------------------------

    /** EPG 时区偏移档位（0-25） */
    private val _epgTimezoneOffset = MutableStateFlow(userPrefs.getEpgTimezoneOffset())
    val epgTimezoneOffset: StateFlow<Int> = _epgTimezoneOffset.asStateFlow()

    /** 设置 EPG 时区偏移档位 */
    fun setEpgTimezoneOffset(value: Int) {
        _epgTimezoneOffset.value = value
        userPrefs.setEpgTimezoneOffset(value)
        // 清除 EPG 缓存，下次获取时使用新时区
        epgCache.clear()
        _currentEpg.value = emptyList()
        fetchEpgForCurrent()
    }

    /**
     * 将 EPG 时间戳按时区偏移调整（与酷9 XML 时间偏移对齐）。
     * @param ts 原始时间戳（毫秒）
     * @return 调整后的时间戳
     */
    fun adjustEpgTimestamp(ts: Long): Long {
        val offsetHours = userPrefs.getEpgTimezoneOffsetHours()
        if (offsetHours == 0) return ts
        return ts + offsetHours * 3600_000L
    }

    // -----------------------------------------------------------------
    // EPG 缓存定时策略（与酷9 EPGCACHE_SELECT 对齐）
    // -----------------------------------------------------------------

    /** EPG 缓存定时档位（0-11） */
    private val _epgCacheSchedule = MutableStateFlow(userPrefs.getEpgCacheSchedule())
    val epgCacheSchedule: StateFlow<Int> = _epgCacheSchedule.asStateFlow()

    /** 设置 EPG 缓存定时档位 */
    fun setEpgCacheSchedule(value: Int) {
        _epgCacheSchedule.value = value
        userPrefs.setEpgCacheSchedule(value)
    }

    // -----------------------------------------------------------------
    // 画面锁定 / 换源不黑屏（与酷9 EYE_PROTECTION 对齐）
    // -----------------------------------------------------------------

    /** 画面锁定开关（true=换源保持画面，false=换源黑屏） */
    private val _screenLock = MutableStateFlow(userPrefs.getScreenLock())
    val screenLock: StateFlow<Boolean> = _screenLock.asStateFlow()

    /** 设置画面锁定 */
    fun setScreenLock(enabled: Boolean) {
        _screenLock.value = enabled
        userPrefs.setScreenLock(enabled)
        // 对 MPV：通过 keep-open 属性控制
        if (_playerType.value == PlayerType.MPV) {
            mpvSingleton.setPropertyBoolean("keep-open", enabled)
        }
    }

    // -----------------------------------------------------------------
    // 分屏模式（手机端：视频+频道列表并排显示）
    // -----------------------------------------------------------------

    /** 分屏模式开关（仅 PHONE 模式生效） */
    private val _splitMode = MutableStateFlow(userPrefs.getSplitMode())
    val splitMode: StateFlow<Boolean> = _splitMode.asStateFlow()

    /** 切换分屏模式 */
    fun toggleSplitMode() {
        _splitMode.value = !_splitMode.value
        userPrefs.setSplitMode(_splitMode.value)
        if (_splitMode.value) {
            // 开启分屏时关闭频道抽屉（分屏模式下频道列表始终可见）
            _channelsPanelOpen.value = false
        }
        showControlsAutoHide()
    }

    // -----------------------------------------------------------------
    // 二级分组模式（与酷9 GROUP_PARS_SET_SELECT 对齐）
    // -----------------------------------------------------------------

    /** 分组模式（0-3） */
    private val _groupMode = MutableStateFlow(userPrefs.getGroupMode())
    val groupMode: StateFlow<Int> = _groupMode.asStateFlow()

    /** 设置分组模式 */
    fun setGroupMode(value: Int) {
        _groupMode.value = value
        userPrefs.setGroupMode(value)
    }

    // -----------------------------------------------------------------
    // 开机自启动（与酷9 BOOT_START 对齐）
    // -----------------------------------------------------------------

    /** 开机自启动开关 */
    private val _bootStart = MutableStateFlow(userPrefs.getBootStart())
    val bootStart: StateFlow<Boolean> = _bootStart.asStateFlow()

    /** 设置开机自启动 */
    fun setBootStart(enabled: Boolean) {
        _bootStart.value = enabled
        userPrefs.setBootStart(enabled)
    }

    /** 启动自动续播开关 */
    private val _autoResume = MutableStateFlow(userPrefs.isAutoResumeOnStart())
    val autoResume: StateFlow<Boolean> = _autoResume.asStateFlow()

    /** 设置启动自动续播 */
    fun setAutoResume(enabled: Boolean) {
        _autoResume.value = enabled
        userPrefs.setAutoResumeOnStart(enabled)
    }

    // -----------------------------------------------------------------
    // 数字选台（与酷9 CHANNEL_NUMBER 对齐）
    // -----------------------------------------------------------------

    /** 当前数字选台输入缓存 */
    private val _channelNumberInput = MutableStateFlow("")
    val channelNumberInput: StateFlow<String> = _channelNumberInput.asStateFlow()

    /** 数字选台超时定时器 */
    private var channelNumberJob: Job? = null

    /**
     * 输入数字选台（TV 遥控器数字键 0-9）。
     * 累积输入并显示在 OSD 上，2秒无新输入自动切台。
     */
    fun inputChannelNumber(digit: Int) {
        val current = _channelNumberInput.value
        // 最多 4 位数
        val newInput = if (current.length >= 4) digit.toString() else current + digit.toString()
        _channelNumberInput.value = newInput
        showOsd("选台: $newInput")

        // 重启 2 秒超时定时器
        channelNumberJob?.cancel()
        channelNumberJob = viewModelScope.launch {
            delay(2000)
            commitChannelNumber()
        }
    }

    /**
     * 确认数字选台（按确认键或超时后自动调用）。
     * @return true 如果执行了切台（有有效输入）
     */
    fun commitChannelNumber(): Boolean {
        val input = _channelNumberInput.value
        if (input.isEmpty()) return false

        channelNumberJob?.cancel()
        _channelNumberInput.value = ""

        val targetNum = input.toIntOrNull() ?: return false
        if (targetNum <= 0) return false

        // 频道列表按 1-based 索引（第 1 个频道 = 1）
        val targetIdx = targetNum - 1
        val channels = _channels.value
        if (targetIdx in channels.indices) {
            playChannel(targetIdx)
            return true
        } else {
            showOsd("频道 $targetNum 不存在")
            return false
        }
    }

    /**
     * 预取相邻频道的 DNS 解析（与 PC 端 _prefetch_adjacent_channels 对齐）。
     *
     * 在后台协程中预解析下一/上一频道的域名，Android 系统 DNS 缓存会保存结果，
     * 切台时 mpv 的网络连接直接命中缓存，省去 DNS 查询时间（通常 50-500ms）。
     *
     * 仅做 DNS 预解析，不建立 TCP 连接（避免占用文件描述符和电量）。
     * TCP 预热由 mpv 内部在 loadfile 时自动完成。
     */
    private fun prefetchAdjacentChannels(currentIdx: Int) {
        val channels = _channels.value
        if (channels.size <= 1) return

        val adjacentUrls = mutableListOf<String>()
        for (delta in intArrayOf(1, -1)) {
            val adjIdx = currentIdx + delta
            if (adjIdx in channels.indices) {
                val url = channels[adjIdx].url
                if (url.isNotEmpty()) adjacentUrls.add(url)
            }
        }
        if (adjacentUrls.isEmpty()) return

        viewModelScope.launch(Dispatchers.IO) {
            for (url in adjacentUrls) {
                try {
                    val host = extractHost(url) ?: continue
                    // DNS 预解析：InetAddress.getByName 会缓存结果到系统 DNS 缓存
                    java.net.InetAddress.getByName(host)
                    Log.d(TAG, "DNS prefetch: $host (from $url)")
                } catch (e: Exception) {
                    // DNS 预解析失败不影响正常播放
                    Log.d(TAG, "DNS prefetch failed for $url: ${e.message}")
                }
            }
        }
    }

    /** 从 URL 中提取主机名（用于 DNS 预解析） */
    private fun extractHost(url: String): String? {
        return try {
            val uri = android.net.Uri.parse(url)
            uri.host
        } catch (e: Exception) {
            null
        }
    }

    // -----------------------------------------------------------------
    // 频道级播放器设置（per-channel override）
    //
    // 开启"频道记忆"后，每个频道可独立记忆播放器内核 / vo / hwdec / HDR 模式。
    // 切换频道时自动应用该频道的设置，实现不同频道用不同最佳配置。
    // -----------------------------------------------------------------

    /**
     * 应用频道级播放器设置（如果开启"频道记忆"且该频道有保存设置）。
     *
     * 在 playChannel 中调用，播放前应用该频道的专属设置。
     *
     * @return true 表示应用了频道级设置（调用方需覆盖 pendingRestoreState）
     */
    private fun applyChannelSettingsIfNeeded(idx: Int) {
        if (!userPrefs.isPerChannelPlayerSettings()) return
        val settings = userPrefs.getChannelSettings(idx) ?: return

        // 1. 应用 vo/hwdec（会触发 mpv 重新加载，随后 playFile 加载新频道）
        settings.vo?.let { vo ->
            if (_currentVo.value != vo) setPlayerVo(vo)
        }
        settings.hwdec?.let { hwdec ->
            val actualHwdec = if (settings.vo == "mediacodec_embed") "mediacodec" else hwdec
            if (_currentHwdec.value != actualHwdec) setPlayerHwdec(actualHwdec)
        }

        // 2. 应用 HDR 模式（只更新状态，由 applyHdrOnFileLoaded 在文件加载后应用）
        settings.hdrMode?.let { modeName ->
            try {
                val mode = HdrMode.valueOf(modeName.uppercase())
                if (_hdrMode.value != mode) {
                    userPrefs.setHdrMode(modeName.lowercase())
                    _hdrMode.value = mode
                }
            } catch (e: Exception) {
                Log.w(TAG, "applyChannelSettings: invalid hdrMode=$modeName")
            }
        }

        if (settings.vo != null || settings.hwdec != null || settings.hdrMode != null) {
            Log.i(TAG, "applyChannelSettings: idx=$idx, settings=$settings")
        }
    }

    /** 自动保存当前播放器设置到指定频道（频道记忆开启时，切换频道前自动调用） */
    private fun autoSaveCurrentSettingsToChannel(idx: Int) {
        val settings = ChannelPlayerSettings(
            playerType = PlayerType.MPV.name,
            vo = _currentVo.value,
            hwdec = _currentHwdec.value,
            hdrMode = _hdrMode.value.name.lowercase()
        )
        userPrefs.setChannelSettings(idx, settings)
        Log.i(TAG, "autoSaveCurrentSettingsToChannel: idx=$idx, settings=$settings")

        // 同时保存到 PlaybackSettingsStore（按 URL 持久化，#24）
        savePlaybackSettingsToStore(idx)
    }

    /**
     * 保存当前播放设置到 PlaybackSettingsStore（按 URL 持久化）。
     * 与 PC 端 playback_settings_store.save_settings 对齐。
     */
    private fun savePlaybackSettingsToStore(idx: Int) {
        val channel = _channels.value.getOrNull(idx) ?: return
        val url = channel.url.ifEmpty { return }
        val settings = mutableMapOf<String, String>()
        // 音轨
        val aid = mpv.getPropertyString("aid") ?: ""
        if (aid.isNotEmpty()) settings["aid"] = aid
        // 字幕轨
        val sid = mpv.getPropertyString("sid") ?: ""
        if (sid.isNotEmpty()) settings["sid"] = sid
        // 音量
        settings["volume"] = mpv.volume.value.toInt().toString()
        // 画面比例
        val aspect = mpv.getPropertyString("video-aspect") ?: ""
        if (aspect.isNotEmpty()) settings["video-aspect"] = aspect
        // 翻转
        val flip = mpv.getPropertyString("vf") ?: ""
        if (flip.isNotEmpty()) settings["vf"] = flip
        // 旋转
        val rotate = mpv.getPropertyString("video-rotate") ?: ""
        if (rotate.isNotEmpty() && rotate != "0") settings["video-rotate"] = rotate
        // 倍速
        val speed = mpv.speed.value
        if (speed != 1.0) settings["speed"] = speed.toString()

        if (settings.isNotEmpty()) {
            viewModelScope.launch {
                val jsonStr = buildJsonObject {
                    settings.forEach { (k, v) -> put(k, JsonPrimitive(v)) }
                }.toString()
                repository.savePlaybackSettings(url, jsonStr, channel.name)
                Log.d(TAG, "savePlaybackSettingsToStore: url=$url, settings=$settings")
            }
        }
    }

    /**
     * 从 PlaybackSettingsStore 加载并应用播放设置（按 URL 持久化，#24）。
     * 与 PC 端 playback_settings_store.load_settings 对齐。
     */
    private fun loadPlaybackSettingsFromStore(url: String) {
        if (url.isEmpty()) return
        viewModelScope.launch {
            val result = repository.loadPlaybackSettings(url)
            result.onSuccess { resp ->
                val settings = resp.settings
                if (settings.isEmpty()) return@onSuccess
                Log.d(TAG, "loadPlaybackSettingsFromStore: url=$url, settings=$settings")
                // 等待文件加载后再应用轨道设置
                settings["aid"]?.let { aid ->
                    if (aid.isNotEmpty()) {
                        kotlinx.coroutines.delay(500)
                        mpv.setPropertyString("aid", aid)
                    }
                }
                settings["sid"]?.let { sid ->
                    if (sid.isNotEmpty()) {
                        kotlinx.coroutines.delay(500)
                        mpv.setPropertyString("sid", sid)
                    }
                }
                settings["volume"]?.toIntOrNull()?.let { vol ->
                    mpv.setVolume(vol)
                }
                settings["video-aspect"]?.let { aspect ->
                    if (aspect.isNotEmpty()) mpv.setPropertyString("video-aspect", aspect)
                }
                settings["video-rotate"]?.toIntOrNull()?.let { rotate ->
                    if (rotate != 0) mpv.setPropertyString("video-rotate", rotate.toString())
                }
                settings["speed"]?.toDoubleOrNull()?.let { speed ->
                    if (speed != 1.0) mpv.setSpeed(speed)
                }
            }.onFailure { e ->
                Log.w(TAG, "loadPlaybackSettingsFromStore failed: ${e.message}")
            }
        }
    }

    /** 清除指定频道的专属播放器设置 */
    fun clearChannelSettings(idx: Int) {
        userPrefs.removeChannelSettings(idx)
        showOsd("频道设置", "已清除该频道的专属设置")
        Log.i(TAG, "clearChannelSettings: idx=$idx")
    }

    /** 查询指定频道是否有专属设置 */
    fun hasChannelSettings(idx: Int): Boolean = userPrefs.getChannelSettings(idx) != null

    /** 频道记忆开关 */
    val perChannelSettingsEnabled: StateFlow<Boolean>
        get() = _perChannelSettingsEnabled
    private val _perChannelSettingsEnabled = MutableStateFlow(userPrefs.isPerChannelPlayerSettings())

    fun setPerChannelSettingsEnabled(enabled: Boolean) {
        userPrefs.setPerChannelPlayerSettings(enabled)
        _perChannelSettingsEnabled.value = enabled
        showOsd("频道记忆", if (enabled) "已开启 — 每个频道将记忆各自的播放器设置" else "已关闭 — 所有频道使用全局设置")
    }

    // -----------------------------------------------------------------
    // 多画面控制
    //
    // 主画面（index=0）用当前播放器（MPV）
    // 副画面（index=1+）用 ExoPlayer（SubPlayer），支持多实例同时播放
    // -----------------------------------------------------------------

    /**
     * 进入多画面模式。
     *
     * - 主画面（index=0）保留当前播放的频道
     * - 副画面（index=1+）初始化为空画面，等待用户添加频道
     *
     * @param layout 布局模式（DUAL/QUAD）
     */
    fun enterMultiView(layout: MultiViewLayout = MultiViewLayout.DUAL) {
        if (_multiViewState.value.active) {
            switchMultiViewLayout(layout)
            return
        }
        val primaryIdx = _currentIdx.value
        val primaryName = currentChannel.value?.name ?: ""
        if (primaryIdx < 0) {
            showOsd("多画面", "请先选择一个频道")
            return
        }
        _multiViewState.value = MultiViewState.create(layout, primaryIdx, primaryName)
        closeAllPanels()
        // 隐藏控制层，让多画面网格完整可见（用户按 CENTER 可重新显示控制层）
        hideControls()
        showOsd("多画面", "已进入${layout.displayName}模式")
    }

    /**
     * 退出多画面模式。主画面保持播放，释放所有副画面播放器。
     */
    fun exitMultiView() {
        if (!_multiViewState.value.active) return
        releaseAllSubPlayers()
        _multiViewState.value = MultiViewState()
        _subPlayerStates.value = emptyMap()
        // 退出多画面后显示控制层（自动隐藏），让用户看到操作选项
        showControlsAutoHide()
        showOsd("多画面", "已退出多画面模式")
    }

    /**
     * 切换多画面布局。扩展布局新增空视口，缩小布局移除多余视口。
     */
    fun switchMultiViewLayout(layout: MultiViewLayout) {
        val current = _multiViewState.value
        if (!current.active || current.layout == layout) return
        // 缩小布局时，释放超出范围的副画面播放器
        if (layout.count < current.layout.count) {
            for (i in layout.count until current.layout.count) {
                releaseSubPlayer(i)
            }
        }
        val newViewports = (0 until layout.count).map { i ->
            current.viewports.getOrNull(i) ?: MultiViewport(index = i)
        }
        _multiViewState.value = current.copy(layout = layout, viewports = newViewports)
        showOsd("多画面", "已切换到${layout.displayName}")
    }

    /**
     * 添加频道到多画面。
     *
     * 优先添加到焦点视口（如果为空且非主画面），否则添加到第一个空闲视口。
     * 主画面（index=0）的频道切换走 [playChannel]，不在此处理。
     *
     * @return 目标视口索引，-1 表示无可用视口
     */
    fun addChannelToMultiView(channelIdx: Int): Int {
        val state = _multiViewState.value
        if (!state.active) return -1
        val channel = _channels.value.getOrNull(channelIdx) ?: return -1

        val focused = state.focusedViewport
        val targetViewport = if (focused != null && focused.isEmpty && !focused.isPrimary) {
            focused
        } else {
            state.firstEmptyViewport ?: run {
                showOsd("多画面", "画面已满，请先关闭一个画面")
                return -1
            }
        }
        val targetIdx = targetViewport.index

        // 主画面的频道切换走 playChannel
        if (targetIdx == 0) {
            playChannel(channelIdx)
            return 0
        }

        // 副画面：创建/复用 SubPlayer 并播放
        try {
            val subPlayer = getOrCreateSubPlayer(targetIdx)
            subPlayer.play(channel.url)

            // 更新视口状态
            _multiViewState.value = state.copy(
                viewports = state.viewports.map {
                    if (it.index == targetIdx) it.copy(
                        channelIdx = channelIdx,
                        channelName = channel.name,
                        isMuted = true
                    ) else it
                }
            )
            showOsd("多画面", "${channel.name} → 画面 ${targetIdx + 1}")

            return targetIdx
        } catch (e: Throwable) {
            Log.e(TAG, "addChannelToMultiView: failed to play on viewport $targetIdx", e)
            showOsd("多画面", "副画面播放失败: ${e.message}")
            return -1
        }
    }

    /**
     * 切换多画面视口的静音状态。
     * - 主画面（index=0）：切换主播放器静音
     * - 副画面（index=1+）：切换对应副 Player 静音
     *
     * @param viewportIndex 视口索引
     */
    fun toggleMultiViewMute(viewportIndex: Int) {
        val state = _multiViewState.value
        if (!state.active) return
        val viewport = state.viewports.getOrNull(viewportIndex) ?: return
        if (viewport.isEmpty) return  // 空画面无需静音

        val newMuted = !viewport.isMuted

        // 更新 UI 状态
        _multiViewState.value = state.copy(
            viewports = state.viewports.map {
                if (it.index == viewportIndex) it.copy(isMuted = newMuted) else it
            }
        )

        // 应用到 Player
        try {
            if (viewportIndex == 0) {
                _player.value.setMute(newMuted)
            } else {
                subPlayers[viewportIndex]?.setMuted(newMuted)
            }
        } catch (e: Throwable) {
            Log.w(TAG, "toggleMultiViewMute: viewport=$viewportIndex, failed: ${e.message}")
        }

        Log.i(TAG, "toggleMultiViewMute: viewport=$viewportIndex, muted=$newMuted")
        showOsd("多画面", "画面 ${viewportIndex + 1} ${if (newMuted) "已静音" else "已取消静音"}")
    }

    /**
     * 从多画面移除视口（清空频道）。主画面不能移除（用 [exitMultiView] 退出）。
     */
    fun removeFromMultiView(viewportIndex: Int) {
        val state = _multiViewState.value
        if (!state.active || viewportIndex == 0) return
        // 释放对应副画面播放器
        releaseSubPlayer(viewportIndex)
        val newViewports = state.viewports.map { vp ->
            if (vp.index == viewportIndex) MultiViewport(index = viewportIndex) else vp
        }
        _multiViewState.value = state.copy(viewports = newViewports)
    }

    /**
     * 获取指定视口的副画面播放器（供 UI 层渲染 PlayerView）。
     * @param viewportIndex 视口索引（1-8）
     * @return SubPlayer 实例，如果不存在或已释放则返回 null
     */
    fun getSubPlayer(viewportIndex: Int): SubPlayer? {
        return subPlayers[viewportIndex]
    }

    /**
     * 创建或复用副画面播放器。
     * 如果该视口已有 SubPlayer 实例则复用，否则创建新实例并初始化。
     */
    private fun getOrCreateSubPlayer(viewportIndex: Int): SubPlayer {
        return subPlayers.getOrPut(viewportIndex) {
            val app = getApplication<Application>()
            SubPlayer(app).also { it.init() }
        }
    }

    /**
     * 释放指定视口的副画面播放器。
     */
    private fun releaseSubPlayer(viewportIndex: Int) {
        subPlayers.remove(viewportIndex)?.release()
        _subPlayerStates.value = _subPlayerStates.value.toMutableMap().apply { remove(viewportIndex) }
    }

    /**
     * 释放所有副画面播放器。
     */
    private fun releaseAllSubPlayers() {
        subPlayers.values.forEach { it.release() }
        subPlayers.clear()
    }

    /**
     * 设置焦点视口（TV 端 D-pad 切换焦点）。
     */
    fun setFocusedViewport(viewportIndex: Int) {
        val state = _multiViewState.value
        if (!state.active) return
        if (viewportIndex !in state.viewports.indices) return
        _multiViewState.value = state.copy(focusedIndex = viewportIndex)
    }

    /**
     * 多画面模式下焦点视口切换（TV 端 D-pad）。
     * @param direction 0=左 1=上 2=右 3=下
     * @return true 表示焦点已切换
     */
    fun moveMultiViewFocus(direction: Int): Boolean {
        val state = _multiViewState.value
        if (!state.active) return false
        val current = state.focusedIndex
        val newIdx = when (state.layout) {
            MultiViewLayout.DUAL -> when (direction) {
                0, 2 -> if (current == 0) 1 else 0  // 左右切换
                else -> return false  // 双画面不支持上下
            }
            MultiViewLayout.QUAD -> {
                // 2x2 网格：0 1
                //          2 3
                val row = current / 2
                val col = current % 2
                when (direction) {
                    0 -> if (col == 0) return false else current - 1  // 左
                    1 -> if (row == 0) return false else current - 2  // 上
                    2 -> if (col == 1) return false else current + 1  // 右
                    3 -> if (row == 1) return false else current + 2  // 下
                    else -> return false
                }
            }
            MultiViewLayout.NINE -> {
                // 3x3 网格：0 1 2
                //          3 4 5
                //          6 7 8
                val cols = 3
                val row = current / cols
                val col = current % cols
                when (direction) {
                    0 -> if (col == 0) return false else current - 1  // 左
                    1 -> if (row == 0) return false else current - cols  // 上
                    2 -> if (col == cols - 1) return false else current + 1  // 右
                    3 -> if (row == cols - 1) return false else current + cols  // 下
                    else -> return false
                }
            }
            MultiViewLayout.SINGLE -> return false
        }
        if (newIdx !in state.viewports.indices) return false
        setFocusedViewport(newIdx)
        return true
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
        if (_shuffleMode.value && shuffleBackStack.isNotEmpty()) {
            cur.let { shuffleHistory.add(it) }
            val prev = shuffleBackStack.removeAt(shuffleBackStack.lastIndex)
            playChannelDebounced(prev)
            return
        }
        val channels = _channels.value
        if (channels.isEmpty()) return
        if (channels.size <= 1) return
        val next = if (cur > 0) cur - 1 else channels.lastIndex
        if (next >= 0 && next < channels.size) playChannelDebounced(next)
    }

    fun nextChannel() {
        val cur = _currentIdx.value
        if (cur < 0) return
        if (_shuffleMode.value) {
            val next = pickRandomChannelIdx(cur)
            if (next >= 0 && next != cur) {
                shuffleBackStack.add(cur)
                if (shuffleBackStack.size > shuffleHistoryMax) {
                    shuffleBackStack.removeAt(0)
                }
            }
            if (next in _channels.value.indices) playChannelDebounced(next)
            return
        }
        val next = if (cur < _channels.value.lastIndex) cur + 1 else 0
        if (next in _channels.value.indices) playChannelDebounced(next)
    }

    private fun playChannelDebounced(idx: Int) {
        val channel = _channels.value.getOrNull(idx) ?: return
        _currentIdx.value = idx
        _channelDisplayInfo.value = ChannelDisplayInfo(
            name = channel.name, logo = channel.logo, group = channel.group, idx = idx,
            isLocal = channel.source.isEmpty() || ProgressHelper.isLocalFile(channel.url)
        )
        fccService.onChannelChange(channel.url)
        playChannelDebounceJob?.cancel()
        playChannelDebounceJob = viewModelScope.launch {
            delay(250)
            playChannel(idx, silent = true)
            if (uiMode.value.isTV) showControlsAutoHide() else showOsd(channel.name, channel.group)
        }
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
        fccService.onStop()
        // 停止超时换源定时器
        timeoutSwitchJob?.cancel()
        timeoutSwitchJob = null
        // 停止文件加载错误自动换源
        fileErrorSwitchJob?.cancel()
        fileErrorSwitchJob = null
        // 停止重连定时器
        reconnectJob?.cancel()
        reconnectJob = null
        // 重置连续超时计数器
        consecutiveTimeoutCount = 0
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

        // 关键：取消所有延迟换源/超时定时器，避免 catchup URL 加载期间被干扰
        // 1. fileErrorSwitchJob：onFileError 延迟换源（已在 onFileError 中通过 isCatchup 判断跳过，双保险）
        fileErrorSwitchJob?.cancel()
        fileErrorSwitchJob = null
        // 2. timeoutSwitchJob：直播频道的超时换源定时器仍在运行！
        //    场景：用户在直播频道上点击过去节目 → startCatchup 播放 catchup URL →
        //    catchup URL 加载需要时间 → 直播频道的 timeoutSwitchJob 到期 →
        //    检查 fileLoaded=false（catchup 还没加载完）→ 调用 nextChannel() 切到下一个直播频道。
        //    这就是"点击回看后视频断了一下又接着直播播放"的根因。
        timeoutSwitchJob?.cancel()
        timeoutSwitchJob = null

        // 播放 catchup URL
        mpv.playFile(catchupUrl)

        // 显示 OSD（不调用 closeAllPanels，避免干扰播放器模式下的动态内容区域）
        showOsd("回看", program.title.ifEmpty { channel.name })

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

        // 取消所有延迟换源/超时定时器（与 startCatchup 一致）
        fileErrorSwitchJob?.cancel()
        fileErrorSwitchJob = null
        timeoutSwitchJob?.cancel()
        timeoutSwitchJob = null

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
            // 先停止 mpv 当前播放（回看 URL 可能已出错/EOF，不 stop 直接 loadfile 可能无法恢复）
            // 与项目约束一致："切换频道前必须先停止 mpv，否则资源泄漏/黑屏"
            mpv.stop()
            playChannel(idx, silent = true)
            showOsd("回看", "已退出，恢复直播")
        } else {
            showOsd("回看", "已退出")
        }
    }

    /**
     * 进度条 seek 处理。
     * 与 PC 端 controllers/playback_controller.seek_live 对齐。
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
            // 目标超出缓冲区：需要重建 catchup URL
            if (!CatchupHelper.isCatchupEnabled(channel)) {
                showOsd("提示", "该频道不支持时移回看")
                return
            }

            // URL 重建冷却检查（与 PC 端 catchup_controller.seek_catchup 对齐）
            val nowSec = System.nanoTime() / 1_000_000_000.0
            if (urlRebuildPending) {
                val elapsed = nowSec - lastUrlRebuildTime
                if (elapsed < urlRebuildCooldown) {
                    // 冷却中：保存待执行的 seek 百分比，等冷却结束后执行
                    pendingSeekAfterCooldown = percent.toDouble()
                    Log.i(TAG, "时移seek延迟: URL重建后冷却中(${"%.1f".format(elapsed)}s/${urlRebuildCooldown}s)")
                    ensureCooldownTimer()
                    showOsd("时移", "冷却中，请稍候...")
                    return
                } else {
                    urlRebuildPending = false
                }
            }

            startLiveTimeshift(sliderSec.toDouble())

            // 记录重建时间，设置 pending 标记
            lastUrlRebuildTime = System.nanoTime() / 1_000_000_000.0
            urlRebuildPending = true
            pendingSeekAfterCooldown = null
            cooldownJob?.cancel()
            cooldownJob = null
        }
    }

    /**
     * 确保冷却定时器在运行（冷却结束后执行待定的 seek）。
     * 与 PC 端 catchup_controller._ensure_cooldown_timer 对齐。
     */
    private fun ensureCooldownTimer() {
        if (cooldownJob?.isActive == true) return
        val nowSec = System.nanoTime() / 1_000_000_000.0
        val remaining = ((urlRebuildCooldown - (nowSec - lastUrlRebuildTime)) * 1000).toLong().coerceAtLeast(200)
        cooldownJob = viewModelScope.launch {
            delay(remaining)
            cooldownJob = null
            val pos = pendingSeekAfterCooldown
            pendingSeekAfterCooldown = null
            if (pos != null) {
                val elapsed = System.nanoTime() / 1_000_000_000.0 - lastUrlRebuildTime
                if (elapsed < urlRebuildCooldown) {
                    ensureCooldownTimer()
                    return@launch
                }
                Log.i(TAG, "冷却期结束，执行延迟的时移seek: percent=${"%.1f".format(pos)}")
                seekProgress(pos.toFloat())
            }
        }
    }

    /**
     * 时移流播放到终点后自动续播（与 PC 端 catchup_controller.continue_timeshift 对齐）。
     * 从当前播放位置重建时移 URL，实现无缝续播。
     */
    fun continueTimeshift() {
        val state = _playbackState.value
        if (!state.mode.isTimeshift) {
            Log.d(TAG, "continueTimeshift: not in timeshift mode, skipping")
            return
        }
        val program = state.catchupProgram ?: run {
            Log.w(TAG, "时移续播失败: 缺少节目信息")
            return
        }
        val channel = state.originalChannel ?: currentChannel.value ?: run {
            Log.w(TAG, "时移续播失败: 缺少频道信息")
            return
        }

        val programStartMs = program.startMs
        val programEndMs = program.endMs
        val now = System.currentTimeMillis()

        // 计算新的起始时间：基于上次的 catchupStartProgressSec + 实际播放时长
        val elapsedSinceStart = state.catchupStartProgressSec
        val newStartMs = if (elapsedSinceStart > 0) {
            val elapsedReal = now - state.catchupStartMs
            programStartMs + (elapsedSinceStart * 1000).toLong() + elapsedReal
        } else {
            now - 5_000L
        }

        var adjustedStartMs = newStartMs.coerceAtLeast(programStartMs)
        if (adjustedStartMs >= now) {
            adjustedStartMs = now - 5_000L
        }

        val endMs = if (programEndMs > now) programEndMs else now + 30 * 60 * 1000L

        val catchupUrl = CatchupHelper.buildCatchupUrl(channel, adjustedStartMs, endMs)
        if (catchupUrl.isNullOrEmpty()) {
            Log.w(TAG, "时移续播: 无法构建 URL")
            showOsd("时移", "续播失败")
            return
        }

        Log.i(TAG, "时移续播 -> new_start=$adjustedStartMs, end=$endMs, url=$catchupUrl")

        // 更新冷却状态
        lastUrlRebuildTime = System.nanoTime() / 1_000_000_000.0
        urlRebuildPending = true

        // 更新 playback state
        _playbackState.value = state.copy(
            catchupStartMs = System.currentTimeMillis(),
            catchupStartProgressSec = 0.0
        )

        mpv.playFile(catchupUrl)
    }

    /**
     * 直播/时移模式下的相对 seek（用于遥控器左右键快进/快退）。
     *
     * 负值（快退）：
     *   - 在 demuxer 缓冲区内 seek
     *   - seek 后落后于直播前沿超过 2 秒时，自动切换到时移模式
     * 正值（快进）：
     *   - 时移模式下 seek，追赶到前沿时切回直播
     *   - 直播模式下（已在前沿）显示提示
     *
     * @param seconds 相对秒数（负=快退，正=快进）
     */
    fun seekLiveRelative(seconds: Double) {
        val state = _playbackState.value
        val mpvTimePos = mpv.timePos.value
        val cacheTime = mpv.getPropertyDouble("demuxer-cache-time") ?: 0.0

        // 缓冲区信息不可用（刚切换频道，缓冲未建立）
        if (mpvTimePos <= 0 || cacheTime <= 0) {
            if (seconds < 0) {
                showOsd("提示", "缓冲中，请稍候")
            }
            return
        }

        val currentOffset = (cacheTime - mpvTimePos).coerceAtLeast(0.0)

        if (seconds < 0) {
            // 快退：seek 后偏移增大
            mpv.seekRelative(seconds)
            val newOffset = (currentOffset + (-seconds)).toLong()
            if (newOffset > 2) {
                if (!state.mode.isTimeshift) {
                    _playbackState.value = state.switchToTimeshift(newOffset)
                } else {
                    _playbackState.value = state.copy(liveTimeshiftSeconds = newOffset)
                }
                showOsd("时移", "落后 ${newOffset} 秒")
            }
        } else {
            // 快进
            if (state.mode.isTimeshift) {
                val newOffset = (currentOffset - seconds).toLong().coerceAtLeast(0L)
                if (newOffset <= 2) {
                    // 追赶到直播前沿：seek 到前沿并切回 LIVE
                    mpv.seekAbsolute(cacheTime - 1)
                    _playbackState.value = state.copy(mode = PlayMode.LIVE, liveTimeshiftSeconds = 0L)
                    showOsd("直播", "已恢复实时播放")
                } else {
                    mpv.seekRelative(seconds)
                    _playbackState.value = state.copy(liveTimeshiftSeconds = newOffset)
                    showOsd("时移", "落后 ${newOffset} 秒")
                }
            } else {
                // 已在直播前沿，无法快进
                showOsd("提示", "已是最新直播")
            }
        }
    }

    // -----------------------------------------------------------------
    // EPG
    // -----------------------------------------------------------------

    private var thumbnailJob: Job? = null

    /**
     * 裁剪 EPG 数据：只保留当前时间附近的节目，避免 898 条数据触发大量 Compose 重组。
     * 保留范围：过去 2 小时 + 未来 12 小时。如果裁剪后为空则保留原始数据（兜底）。
     */
    private fun trimEpgNearNow(programs: List<IptvEpgProgram>): List<IptvEpgProgram> {
        if (programs.size <= 30) return programs
        val now = System.currentTimeMillis()
        val pastMs = 2 * 3600_000L
        val futureMs = 12 * 3600_000L
        val hasTimestamps = programs.any { it.startTs > 0 || it.stopTs > 0 }
        val firstWithTs = programs.firstOrNull { it.startTs > 0 }
        val tsScale = if (firstWithTs != null && firstWithTs.startTs > 1_000_000_000_000L) 1L else 1000L
        val trimmed = if (hasTimestamps) {
            programs.filter { p ->
                val start = if (p.startTs > 0) p.startTs * tsScale else 0L
                val stop = if (p.stopTs > 0) p.stopTs * tsScale else Long.MAX_VALUE
                stop > now - pastMs && start < now + futureMs
            }
        } else {
            val centerIdx = programs.indexOfFirst { p ->
                p.start.isNotEmpty() && p.stop.isNotEmpty()
            }.coerceAtLeast(0)
            val from = (centerIdx - 5).coerceAtLeast(0)
            val to = (centerIdx + 25).coerceAtMost(programs.size)
            programs.subList(from, to)
        }
        var result = if (trimmed.isNotEmpty()) trimmed else programs
        if (result.size > 50 && hasTimestamps) {
            val currentIdx = result.indexOfFirst { p ->
                val s = if (p.startTs > 0) p.startTs * tsScale else 0L
                val e = if (p.stopTs > 0) p.stopTs * tsScale else Long.MAX_VALUE
                s <= now && e > now
            }.coerceAtLeast(0)
            val from = (currentIdx - 5).coerceAtLeast(0)
            val to = (currentIdx + 45).coerceAtMost(result.size)
            result = result.subList(from, to)
        }
        Log.d(TAG, "trimEpgNearNow: ${programs.size} -> ${result.size}")
        return result
    }

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

        // 优先用缓存（裁剪后给UI，缓存保留完整数据供EPG面板展开用）
        epgCache[idx]?.let { cached ->
            _currentEpg.value = trimEpgNearNow(cached)
            return
        }

        _epgLoading.value = true
        val baseName = channel.name
            .removeSuffix("-4K").removeSuffix("-HDR").removeSuffix("-8K")
            .removeSuffix(" 4K").removeSuffix(" HDR").removeSuffix(" 8K")
        viewModelScope.launch {
            val result = repository.getEpg(
                channelName = baseName,
                tvgId = channel.tvgId,
                tvgName = channel.tvgName,
                commaName = channel.name
            )
            result.fold(
                onSuccess = { epgList ->
                    val programs = epgList.programmes
                    if (programs.isEmpty()) {
                        // EPG 数据可能还在后台加载，3秒后重试一次
                        Log.w(TAG, "fetchEpgForCurrent: empty programs, will retry in 3s")
                        delay(3000)
                        val retry = withContext(Dispatchers.IO) {
                            repository.getEpg(channel.name, channel.tvgId, channel.tvgName, channel.name)
                        }
                        val retryPrograms = retry.getOrNull()?.programmes ?: emptyList()
                        epgCache[idx] = retryPrograms
                        _epgCacheVersion.value++
                        _currentEpg.value = trimEpgNearNow(retryPrograms)
                        Log.i(TAG, "fetchEpgForCurrent (retry): ${retryPrograms.size} programs for ${channel.name}")
                    } else {
                        epgCache[idx] = programs
                        _epgCacheVersion.value++
                        _currentEpg.value = trimEpgNearNow(programs)
                        Log.i(TAG, "fetchEpgForCurrent: ${programs.size} programs for ${channel.name}")
                    }
                },
                onFailure = { e ->
                    Log.w(TAG, "fetchEpgForCurrent failed: ${e.message}")
                    // EPG 服务器可能还没准备好，3秒后重试
                    delay(3000)
                    try {
                        val retry = withContext(Dispatchers.IO) {
                            repository.getEpg(channel.name, channel.tvgId, channel.tvgName, channel.name)
                        }
                        val retryPrograms = retry.getOrNull()?.programmes ?: emptyList()
                        epgCache[idx] = retryPrograms
                        _epgCacheVersion.value++
                        _currentEpg.value = trimEpgNearNow(retryPrograms)
                        Log.i(TAG, "fetchEpgForCurrent (retry after fail): ${retryPrograms.size} programs for ${channel.name}")
                    } catch (e2: Exception) {
                        _currentEpg.value = emptyList()
                    }
                }
            )
            _epgLoading.value = false
        }
    }

    /** 获取当前正在播放的 EPG 节目（用于控制面板第二行显示） */
    fun getCurrentProgram(): IptvEpgProgram? {
        return ProgressHelper.findCurrentProgram(_currentEpg.value, System.currentTimeMillis())
    }

    /** EPG 面板展开时获取完整（未裁剪）的 EPG 数据 */
    fun getFullEpgForCurrent(): List<IptvEpgProgram> {
        val idx = _currentIdx.value
        if (idx < 0) return emptyList()
        return epgCache[idx] ?: _currentEpg.value
    }

    /**
     * 获取指定频道的 EPG（用于 TV 统一面板焦点频道节目单显示）。
     * 复用 epgCache 避免重复加载。与 fetchEpgForCurrent 逻辑一致但写入 _focusedEpg。
     */
    fun fetchEpgForChannel(idx: Int) {
        val channel = _channels.value.getOrNull(idx) ?: run {
            _focusedEpg.value = emptyList()
            return
        }
        // 优先用缓存（裁剪后给UI）
        epgCache[idx]?.let { cached ->
            _focusedEpg.value = trimEpgNearNow(cached)
            return
        }
        _focusedEpgLoading.value = true
        val baseName = channel.name
            .removeSuffix("-4K").removeSuffix("-HDR").removeSuffix("-8K")
            .removeSuffix(" 4K").removeSuffix(" HDR").removeSuffix(" 8K")
        viewModelScope.launch {
            val result = repository.getEpg(
                channelName = baseName,
                tvgId = channel.tvgId,
                tvgName = channel.tvgName,
                commaName = channel.name
            )
            result.fold(
                onSuccess = { epgList ->
                    val programs = epgList.programmes
                    epgCache[idx] = programs
                    _epgCacheVersion.value++
                    _focusedEpg.value = trimEpgNearNow(programs)
                    Log.i(TAG, "fetchEpgForChannel: ${programs.size} programs for ${channel.name}")
                },
                onFailure = { e ->
                    Log.w(TAG, "fetchEpgForChannel failed: ${e.message}")
                    _focusedEpg.value = emptyList()
                }
            )
            _focusedEpgLoading.value = false
        }
    }

    /**
     * 批量预加载所有频道的 EPG（用于频道列表自动显示当前节目）。
     * 只加载未缓存的频道，每次最多并发 5 个，避免请求风暴。
     */
    fun preloadEpgForAllChannels() {
        val channels = _channels.value
        if (channels.isEmpty()) return
        val uncachedIdxs = channels.indices.filter { it !in epgCache }
        if (uncachedIdxs.isEmpty()) return
        Log.i(TAG, "preloadEpgForAllChannels: ${uncachedIdxs.size} channels need EPG preload")
        viewModelScope.launch {
            // 分批并发，每批 5 个
            uncachedIdxs.chunked(5).forEach { batch ->
                batch.forEach { idx ->
                    launch {
                        val channel = channels.getOrNull(idx) ?: return@launch
                        try {
                            val result = repository.getEpg(
                                channelName = channel.name,
                                tvgId = channel.tvgId,
                                tvgName = channel.tvgName,
                                commaName = channel.name
                            )
                            result.fold(
                                onSuccess = { epgList ->
                                    val programs = epgList.programmes
                                    if (programs.isNotEmpty()) {
                                        epgCache[idx] = programs
                                        _epgCacheVersion.value++
                                        Log.d(TAG, "preloadEpg: ${programs.size} programs for ${channel.name}")
                                    }
                                },
                                onFailure = { /* 静默失败，不打扰用户 */ }
                            )
                        } catch (_: Throwable) {}
                    }
                }
                // 等待当前批次完成
                kotlinx.coroutines.delay(500)
            }
        }
    }

    /**
     * 显示当前频道的 OSD 信息（用于 TV 统一面板 OSD 按钮）。
     * 持久模式切换：如果 OSD 已开启（pinned），则关闭；否则开启持久模式（不自动隐藏）。
     */
    fun showCurrentOsd() {
        // 如果 OSD 已开启且为持久模式，则关闭
        if (_osdPinned.value) {
            hideOsd()
            return
        }
        val channel = currentChannel.value
        if (channel != null) {
            val prog = getCurrentProgram()
            val subtitle = if (prog != null && prog.title.isNotEmpty()) prog.title else channel.group
            // 菜单触发的 OSD 设为持久模式（不自动隐藏，直至再次选中 OSD 关闭）
            _osdPinned.value = true
            _osd.value = OsdInfo(channel.name, subtitle)
            osdHideJob?.cancel()
        }
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

    /** 显示 OSD（5 秒后自动隐藏，持久模式下不自动隐藏） */
    fun showOsd(title: String, subtitle: String = "", extra: String = "") {
        _osd.value = OsdInfo(title, subtitle, extra)
        // 普通触发的 OSD 清除持久模式
        _osdPinned.value = false
        osdHideJob?.cancel()
        osdHideJob = viewModelScope.launch {
            delay(5_000L)
            _osd.value = null
        }
    }

    /** 隐藏 OSD（同时清除持久模式） */
    fun hideOsd() {
        osdHideJob?.cancel()
        _osdPinned.value = false
        _osd.value = null
    }

    // -----------------------------------------------------------------
    // 面板控制
    // -----------------------------------------------------------------

    fun toggleChannelsPanel() {
        _channelsPanelOpen.value = !_channelsPanelOpen.value
        // 关闭面板时自动显示控制层（避免面板关闭后控制层不显示）
        if (!_channelsPanelOpen.value) showControlsAutoHide()
    }
    fun toggleEpgPanel() {
        _epgPanelOpen.value = !_epgPanelOpen.value
        if (!_epgPanelOpen.value) showControlsAutoHide()
    }
    fun toggleMenuPanel() {
        _menuPanelOpen.value = !_menuPanelOpen.value
        if (!_menuPanelOpen.value) showControlsAutoHide()
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
            showControlsAutoHide()
        }
    }
    fun toggleControls() {
        if (_controlsVisible.value) hideControls() else showControls()
    }

    fun closeAllPanelsExceptSidebar() {
        androidx.compose.runtime.snapshots.Snapshot.withMutableSnapshot {
            _channelsPanelOpen.value = false
            _epgPanelOpen.value = false
            _menuPanelOpen.value = false
            _tvUnifiedPanelOpen.value = false
            _fileBrowserOpen.value = false
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
            _updateDialogOpen.value = false
            _exitConfirmOpen.value = false
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
            _recentPanelOpen.value = false
            _clipExportPanelOpen.value = false
            _audioVisualizerOpen.value = false
            _lyricsOpen.value = false
        }
        stopScanPolling()
        stopAvSyncSampling()
        stopSubSync()
        if (!_landscapeSidebarVisible.value) {
            showControlsAutoHide()
        }
    }

    fun closeAllPanels() {
        androidx.compose.runtime.snapshots.Snapshot.withMutableSnapshot {
            _channelsPanelOpen.value = false
            _epgPanelOpen.value = false
            _menuPanelOpen.value = false
            _tvUnifiedPanelOpen.value = false
            _fileBrowserOpen.value = false
            _sourceManagerOpen.value = false
            _playerSettingsOpen.value = false
            _videoSettingsOpen.value = false
            _audioSettingsOpen.value = false
            _subtitleSettingsOpen.value = false
            _landscapeSidebarVisible.value = false
            _subtitleSearchOpen.value = false
            _playbackPanelOpen.value = false
            _screenshotPanelOpen.value = false
            _viewSettingsOpen.value = false
            _aboutPanelOpen.value = false
            _updateDialogOpen.value = false
            _exitConfirmOpen.value = false
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
            _recentPanelOpen.value = false
            _clipExportPanelOpen.value = false
            _audioVisualizerOpen.value = false
            _lyricsOpen.value = false
        }
        stopScanPolling()
        // 关闭 A/V 同步采样
        stopAvSyncSampling()
        stopSubSync()
        // 关闭所有面板后自动显示控制层
        showControlsAutoHide()
    }

    /**
     * 是否有任意面板打开（只读查询，不关闭面板）。
     * 用于 TV 端 DPAD 路由：面板打开时方向键交给 Compose 焦点系统在面板内导航。
     */
    val anyPanelOpen: Boolean
        get() = _landscapeSidebarVisible.value ||
                _channelsPanelOpen.value || _epgPanelOpen.value ||
                _menuPanelOpen.value || _tvUnifiedPanelOpen.value || _fileBrowserOpen.value ||
                _sourceManagerOpen.value ||
                _playerSettingsOpen.value ||
                _videoSettingsOpen.value || _audioSettingsOpen.value ||
                _subtitleSettingsOpen.value || _subtitleSearchOpen.value || _playbackPanelOpen.value ||
                _screenshotPanelOpen.value || _viewSettingsOpen.value ||
                _aboutPanelOpen.value || _updateDialogOpen.value || _exitConfirmOpen.value || _openUrlDialogOpen.value ||
                _mappingPanelOpen.value || _avSyncPanelOpen.value ||
                _networkPanelOpen.value || _toolsPanelOpen.value || _scanPanelOpen.value ||
                _reminderPanelOpen.value || _resumePanelOpen.value || _bookmarkPanelOpen.value ||
                _epgTimelineOpen.value || _searchPanelOpen.value ||
                _streamQualityPanelOpen.value ||
                _recentPanelOpen.value || _clipExportPanelOpen.value ||
                _audioVisualizerOpen.value || _lyricsOpen.value

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

    /** 打开文件浏览器面板（SAF 不可用时的替代方案） */
    fun showFileBrowser() {
        closeAllPanels()
        _fileBrowserMode.value = FileBrowserMode.PLAYLIST
        _fileBrowserOpen.value = true
    }
    /** 打开应用内文件浏览器选择音视频文件播放（SAF 不可用时的兜底） */
    fun showMediaFileBrowser() {
        closeAllPanels()
        _fileBrowserMode.value = FileBrowserMode.MEDIA
        _fileBrowserOpen.value = true
    }
    fun toggleFileBrowser() {
        _fileBrowserOpen.value = !_fileBrowserOpen.value
        if (!_fileBrowserOpen.value) showControlsAutoHide()
    }

    /**
     * 从本地文件路径导入 M3U 播放列表（不依赖 SAF，直接读取文件系统）。
     * 用于 TV 端文件浏览器选择文件后的导入。
     */
    fun importPlaylistFromFile(path: String) {
        viewModelScope.launch {
            showOsd("正在导入播放列表...")
            val content = withContext(Dispatchers.IO) {
                try {
                    File(path).readText(charset = Charsets.UTF_8)
                } catch (e: Exception) {
                    Log.e(TAG, "importPlaylistFromFile read failed: $path", e)
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
                    _fileBrowserOpen.value = false
                },
                onFailure = { e ->
                    showOsd("导入失败", e.message ?: "")
                }
            )
        }
    }

    fun hideControls() {
        _controlsVisible.value = false
        _controlsPinned.value = false
        tvControlsAutoHideJob?.cancel()
    }
    fun showControls() { showControlsAutoHide() }

    /**
     * 显示控制面板，所有模式下 4 秒后自动隐藏（与 PC 端 autoHideControls 对齐）。
     * 若控制层已 pin（持久模式），则不启动自动隐藏定时器。
     */
    fun showControlsAutoHide() {
        _controlsVisible.value = true
        if (!_controlsPinned.value) {
            tvControlsAutoHideJob?.cancel()
            tvControlsAutoHideJob = viewModelScope.launch {
                delay(4_000L)
                _controlsVisible.value = false
            }
        }
    }

    /**
     * 切换控制层持久模式（菜单 OSD 按钮触发）。
     * - 未 pin 时：显示控制层并 pin（不自动隐藏）
     * - 已 pin 时：取消 pin 并隐藏控制层
     */
    fun toggleControlsPinned() {
        if (_controlsPinned.value) {
            _controlsPinned.value = false
            _controlsVisible.value = false
            tvControlsAutoHideJob?.cancel()
        } else {
            _controlsPinned.value = true
            _controlsVisible.value = true
            tvControlsAutoHideJob?.cancel()
        }
    }

    // -----------------------------------------------------------------
    // 更多功能面板切换（主菜单 → 播放 → 各子面板）
    // -----------------------------------------------------------------

    fun toggleVideoSettings() {
        _videoSettingsOpen.value = !_videoSettingsOpen.value
        if (!_videoSettingsOpen.value) showControlsAutoHide()
    }
    fun toggleAudioSettings() {
        _audioSettingsOpen.value = !_audioSettingsOpen.value
        if (!_audioSettingsOpen.value) showControlsAutoHide()
    }
    fun toggleSubtitleSettings() {
        _subtitleSettingsOpen.value = !_subtitleSettingsOpen.value
        if (!_subtitleSettingsOpen.value) showControlsAutoHide()
    }

    /** 打开/关闭字幕在线搜索面板 */
    fun toggleSubtitleSearchPanel() {
        _subtitleSearchOpen.value = !_subtitleSearchOpen.value
        if (!_subtitleSearchOpen.value) showControlsAutoHide()
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
        if (!_playbackPanelOpen.value) showControlsAutoHide()
    }
    fun toggleScreenshotPanel() {
        _screenshotPanelOpen.value = !_screenshotPanelOpen.value
        if (!_screenshotPanelOpen.value) showControlsAutoHide()
    }
    fun toggleViewSettings() {
        _viewSettingsOpen.value = !_viewSettingsOpen.value
        if (!_viewSettingsOpen.value) showControlsAutoHide()
    }
    fun toggleAboutPanel() {
        _aboutPanelOpen.value = !_aboutPanelOpen.value
        if (!_aboutPanelOpen.value) showControlsAutoHide()
    }

    // -----------------------------------------------------------------
    // 版本检查（与 PC 端 UpdateController 对齐）
    // -----------------------------------------------------------------

    /** 获取当前应用版本号（从 PackageManager 读取，与 build.gradle versionName 一致） */
    fun getCurrentVersion(): String {
        return try {
            val app = getApplication<Application>()
            val packageInfo = app.packageManager.getPackageInfo(app.packageName, 0)
            packageInfo.versionName ?: "0.0.0.0"
        } catch (e: Exception) {
            Log.e(TAG, "getCurrentVersion failed", e)
            "0.0.0.0"
        }
    }

    /** 获取编译日期（从 APK 的 lastUpdateTime 提取） */
    fun getBuildDate(): String {
        return try {
            val app = getApplication<Application>()
            val packageInfo = app.packageManager.getPackageInfo(app.packageName, 0)
            val date = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
            date.format(java.util.Date(packageInfo.lastUpdateTime))
        } catch (e: Exception) {
            Log.w(TAG, "getBuildDate failed", e)
            "unknown"
        }
    }

    /**
     * 检查更新（调用 GitHub API 获取最新 release）。
     * @param auto true=启动时自动检查（仅发现新版本时弹窗）；false=用户手动触发（无论结果都显示）
     */
    fun checkForUpdates(auto: Boolean = false) {
        if (_updateState.value is UpdateState.Checking) return
        _updateState.value = UpdateState.Checking
        viewModelScope.launch {
            try {
                val currentVersion = getCurrentVersion()
                val (latestVersion, downloadUrl, releaseUrl) = withContext(Dispatchers.IO) {
                    fetchLatestRelease()
                }
                if (latestVersion.isNullOrEmpty()) {
                    if (!auto) {
                        _updateState.value = UpdateState.Error("获取版本信息失败")
                    } else {
                        _updateState.value = UpdateState.Idle
                    }
                } else if (isNewerVersion(currentVersion, latestVersion)) {
                    _updateState.value = UpdateState.UpdateAvailable(
                        latestVersion,
                        downloadUrl ?: "",
                        releaseUrl ?: ""
                    )
                    _updateDialogOpen.value = true
                    showOsd("发现新版本", "v$latestVersion（当前 v$currentVersion）")
                } else {
                    if (!auto) {
                        _updateState.value = UpdateState.UpToDate
                    } else {
                        _updateState.value = UpdateState.Idle
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "checkForUpdates failed", e)
                if (!auto) {
                    _updateState.value = UpdateState.Error(e.message ?: "检查更新失败")
                } else {
                    _updateState.value = UpdateState.Idle
                }
            }
        }
    }

    /** 关闭更新提示对话框 */
    fun dismissUpdateDialog() {
        _updateDialogOpen.value = false
    }

    /**
     * 应用内下载并安装 APK（替代浏览器跳转，TV 端友好）。
     *
     * 流程：
     * 1. 注册 ACTION_DOWNLOAD_COMPLETE BroadcastReceiver
     * 2. 通过 DownloadManager 系统服务发起下载（保存到 app 专属目录 update/）
     * 3. 启动协程轮询下载进度，更新 [_apkDownloadState]
     * 4. 收到下载完成广播后，通过 FileProvider 获取 content:// URI 调起安装 Intent
     *
     * @param url APK 下载 URL（来自 GitHub Release asset 的 browser_download_url）
     */
    fun downloadAndInstallApk(url: String) {
        if (url.isBlank()) {
            _apkDownloadState.value = ApkDownloadState.Error("下载地址为空")
            return
        }
        // 安全：校验 URL 协议和域名，防止恶意 APK 下载
        val parsedUrl = try {
            android.net.Uri.parse(url)
        } catch (e: Exception) {
            _apkDownloadState.value = ApkDownloadState.Error("无效的下载地址")
            return
        }
        val scheme = parsedUrl.scheme?.lowercase()
        val host = parsedUrl.host?.lowercase() ?: ""
        if (scheme != "https" || (host != "github.com" && !host.endsWith(".github.com") &&
                !host.endsWith(".githubusercontent.com"))) {
            _apkDownloadState.value = ApkDownloadState.Error("仅允许从 GitHub 下载更新")
            Log.w(TAG, "downloadAndInstallApk: blocked non-GitHub URL: $url")
            return
        }
        if (_apkDownloadState.value is ApkDownloadState.Downloading) {
            Log.w(TAG, "downloadAndInstallApk: already downloading, ignored")
            return
        }

        val app = getApplication<Application>()
        val downloadManager = app.getSystemService(Context.DOWNLOAD_SERVICE) as? DownloadManager
        if (downloadManager == null) {
            _apkDownloadState.value = ApkDownloadState.Error("下载服务不可用")
            return
        }

        // 清理旧的下载任务（如有）
        cancelApkDownload()

        // 注册下载完成广播接收器
        registerApkDownloadReceiver(app)

        // 准备下载目录：app 专属外部存储（无需存储权限，卸载自动清理）
        val updateDir = File(app.getExternalFilesDir(null), "update").apply {
            if (!exists()) mkdirs()
        }
        val apkFile = File(updateDir, "isep-update.apk")
        // 删除旧文件避免 DownloadManager 报错 FILE_ALREADY_EXISTS
        if (apkFile.exists()) apkFile.delete()

        Log.i(TAG, "downloadAndInstallApk: starting download, url=$url, target=${apkFile.absolutePath}")

        // 构建下载请求
        val request = try {
            DownloadManager.Request(Uri.parse(url)).apply {
                setTitle("ISEP 更新")
                setDescription("正在下载最新版 APK...")
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                setDestinationUri(Uri.fromFile(apkFile))
                // 允许在移动网络和漫游下下载（更新包通常不大，且用户主动触发）
                setAllowedNetworkTypes(DownloadManager.Request.NETWORK_WIFI or DownloadManager.Request.NETWORK_MOBILE)
                setAllowedOverRoaming(true)
            }
        } catch (e: Exception) {
            Log.e(TAG, "downloadAndInstallApk: create request failed", e)
            _apkDownloadState.value = ApkDownloadState.Error("创建下载请求失败：${e.message}")
            unregisterApkDownloadReceiver(app)
            return
        }

        try {
            apkDownloadId = downloadManager.enqueue(request)
        } catch (e: Exception) {
            Log.e(TAG, "downloadAndInstallApk: enqueue failed", e)
            _apkDownloadState.value = ApkDownloadState.Error("下载服务异常：${e.message}")
            unregisterApkDownloadReceiver(app)
            return
        }
        _apkDownloadState.value = ApkDownloadState.Downloading(0)
        showOsd("应用更新", "开始下载 APK...")

        // 启动进度轮询协程
        apkProgressJob = viewModelScope.launch {
            while (isActive) {
                delay(500)  // 每 500ms 查询一次进度
                try {
                    val query = DownloadManager.Query().setFilterById(apkDownloadId)
                    val cursor = downloadManager.query(query)
                    if (cursor != null && cursor.moveToFirst()) {
                        val status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                        when (status) {
                            DownloadManager.STATUS_RUNNING -> {
                                val downloaded = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                                val total = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                                if (total > 0) {
                                    val progress = ((downloaded * 100) / total).toInt().coerceIn(0, 100)
                                    _apkDownloadState.value = ApkDownloadState.Downloading(progress)
                                }
                            }
                            DownloadManager.STATUS_PAUSED -> {
                                // 暂停（等待网络等），UI 仍显示下载中
                            }
                            DownloadManager.STATUS_PENDING -> {
                                // 等待开始
                            }
                            DownloadManager.STATUS_FAILED -> {
                                val reason = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                                Log.e(TAG, "downloadAndInstallApk: download failed, reason=$reason")
                                _apkDownloadState.value = ApkDownloadState.Error("下载失败（错误码 $reason）")
                                unregisterApkDownloadReceiver(app)
                                apkDownloadId = -1L
                                cursor.close()
                                return@launch
                            }
                        }
                    }
                    cursor?.close()
                } catch (e: Throwable) {
                    Log.w(TAG, "downloadAndInstallApk: progress poll error: ${e.message}")
                }
            }
        }
    }

    /**
     * 安装已下载完成的 APK（对外暴露，用于 UI 备用入口）。
     * 通过 FileProvider 获取 content:// URI，调起系统安装器。
     */
    fun installDownloadedApk() {
        val app = getApplication<Application>()
        val apkFile = File(app.getExternalFilesDir(null), "update/isep-update.apk")
        if (!apkFile.exists()) {
            _apkDownloadState.value = ApkDownloadState.Error("下载文件不存在")
            return
        }

        try {
            val authority = "${app.packageName}.fileprovider"
            val uri = FileProvider.getUriForFile(app, authority, apkFile)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            // Android 8+ 需要检查未知来源安装权限
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O &&
                !app.packageManager.canRequestPackageInstalls()
            ) {
                Log.w(TAG, "installDownloadedApk: no install permission, opening settings")
                _apkDownloadState.value = ApkDownloadState.Error("请先允许「安装未知应用」权限")
                // 引导用户到设置页面授权
                val settingsIntent = Intent(
                    android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${app.packageName}")
                ).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                try {
                    app.startActivity(settingsIntent)
                } catch (e: Exception) {
                    Log.e(TAG, "installDownloadedApk: cannot open unknown sources settings", e)
                }
                return
            }
            app.startActivity(intent)
            Log.i(TAG, "installDownloadedApk: install intent launched, uri=$uri")
            // 安装界面已弹出，关闭更新对话框
            _updateDialogOpen.value = false
        } catch (e: Throwable) {
            Log.e(TAG, "installDownloadedApk failed", e)
            _apkDownloadState.value = ApkDownloadState.Error("启动安装失败：${e.message}")
        }
    }

    /**
     * 注册 APK 下载完成 BroadcastReceiver。
     * 在收到 ACTION_DOWNLOAD_COMPLETE 后停止进度轮询并触发安装。
     */
    private fun registerApkDownloadReceiver(context: Context) {
        unregisterApkDownloadReceiver(context)
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context?, intent: Intent?) {
                val id = intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) ?: -1L
                if (id != apkDownloadId) return  // 不是我们的下载任务
                Log.i(TAG, "APK download complete, id=$id")
                apkProgressJob?.cancel()
                apkProgressJob = null

                val downloadManager = context?.getSystemService(Context.DOWNLOAD_SERVICE) as? DownloadManager
                if (downloadManager == null) {
                    _apkDownloadState.value = ApkDownloadState.Error("下载服务不可用")
                    unregisterApkDownloadReceiver(context)
                    return
                }

                // 查询下载结果
                val query = DownloadManager.Query().setFilterById(id)
                val cursor = downloadManager.query(query)
                if (cursor != null && cursor.moveToFirst()) {
                    val status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    if (status == DownloadManager.STATUS_SUCCESSFUL) {
                        _apkDownloadState.value = ApkDownloadState.Completed
                        showOsd("应用更新", "下载完成，正在启动安装...")
                        // 稍延迟启动安装（让 UI 先更新）
                        viewModelScope.launch {
                            delay(300)
                            installDownloadedApk()
                        }
                    } else {
                        val reason = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                        Log.e(TAG, "APK download failed on complete, reason=$reason")
                        _apkDownloadState.value = ApkDownloadState.Error("下载失败（错误码 $reason）")
                    }
                    cursor.close()
                } else {
                    _apkDownloadState.value = ApkDownloadState.Error("下载结果查询失败")
                }
                unregisterApkDownloadReceiver(context)
                apkDownloadId = -1L
            }
        }
        context.registerReceiver(
            receiver,
            IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE)
        )
        apkDownloadReceiver = receiver
    }

    /** 注销 APK 下载 BroadcastReceiver（如已注册） */
    private fun unregisterApkDownloadReceiver(context: Context) {
        apkDownloadReceiver?.let {
            try {
                context.unregisterReceiver(it)
            } catch (e: Throwable) {
                Log.w(TAG, "unregisterApkDownloadReceiver: ${e.message}")
            }
            apkDownloadReceiver = null
        }
    }

    /**
     * 取消当前 APK 下载任务（如有）。
     * 用于用户主动取消或重新发起下载前清理。
     */
    fun cancelApkDownload() {
        val app = getApplication<Application>()
        apkProgressJob?.cancel()
        apkProgressJob = null
        if (apkDownloadId > 0) {
            try {
                val dm = app.getSystemService(Context.DOWNLOAD_SERVICE) as? DownloadManager
                dm?.remove(apkDownloadId)
            } catch (e: Throwable) {
                Log.w(TAG, "cancelApkDownload: remove failed: ${e.message}")
            }
            apkDownloadId = -1L
        }
        unregisterApkDownloadReceiver(app)
        _apkDownloadState.value = ApkDownloadState.Idle
    }

    /** 显示退出确认对话框 */
    fun showExitConfirm() {
        _exitConfirmOpen.value = true
    }

    /** 关闭退出确认对话框 */
    fun dismissExitConfirm() {
        _exitConfirmOpen.value = false
    }

    /**
     * 调用 GitHub API 获取最新 release 信息。
     * 返回 (最新版本号, Android APK 下载链接, Release 页面链接)。
     *
     * 当前构建规则（build.gradle + build.yml）：
     * - 按 ABI 分包构建，生成两个独立 APK：
     *   - arm64-v8a → ISEP-Android-arm64.apk
     *   - armeabi-v7a → ISEP-Android-arm32.apk
     * - 不传 targetAbi 时生成通用包：ISEP-Android-universal.apk
     *
     * 兼容性：同时匹配旧版命名规则（IPTV Scanner Editor Pro-Android-xxx.apk / -arm64-v8a.apk / -armeabi-v7a.apk），
     * 确保旧版本 Release 的用户也能正常更新。
     */
    private fun fetchLatestRelease(): Triple<String?, String?, String?> {
        val conn = java.net.URL(GITHUB_LATEST_API).openConnection() as java.net.HttpURLConnection
        try {
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "IPTV-Scanner-Editor-Pro")
            conn.setRequestProperty("Accept", "application/vnd.github+json")
            conn.connectTimeout = 10_000
            conn.readTimeout = 10_000
            if (conn.responseCode == 200) {
                val json = conn.inputStream.bufferedReader().use { it.readText() }
                val release = JSONObject(json)
                val tagName = release.optString("tag_name", "").removePrefix("v")
                val releaseUrl = release.optString("html_url", "")

                val assets = release.optJSONArray("assets")
                var downloadUrl = releaseUrl
                if (assets != null) {
                    // 收集所有 Android APK asset
                    val androidApks = mutableListOf<Pair<String, String>>() // (name, url)
                    for (i in 0 until assets.length()) {
                        val asset = assets.optJSONObject(i) ?: continue
                        val name = asset.optString("name", "")
                        if (name.contains("Android", ignoreCase = true) && name.endsWith(".apk")) {
                            androidApks.add(name to asset.optString("browser_download_url", releaseUrl))
                        }
                    }

                    // 优先匹配通用 APK（无 ABI 后缀或 -universal 后缀，含所有 ABI）
                    val universalApk = androidApks.firstOrNull { (name, _) ->
                        name.equals("ISEP-Android.apk", ignoreCase = true) ||
                        name.equals("ISEP-Android-universal.apk", ignoreCase = true) ||
                        name.equals("IPTV Scanner Editor Pro-Android.apk", ignoreCase = true) ||
                        name.equals("IPTV Scanner Editor Pro-Android-universal.apk", ignoreCase = true)
                    }
                    if (universalApk != null) {
                        downloadUrl = universalApk.second
                    } else {
                        // 按 ABI 拆分的 APK：按设备首选 ABI 匹配
                        // 当前命名：arm64-v8a → -arm64.apk，armeabi-v7a → -arm32.apk
                        // 旧版命名：arm64-v8a → -arm64-v8a.apk，armeabi-v7a → -armeabi-v7a.apk
                        val deviceAbis = android.os.Build.SUPPORTED_ABIS.toList()
                        Log.i(TAG, "fetchLatestRelease: universal APK not found, fallback to ABI-specific, device ABIs=$deviceAbis")
                        downloadUrl = deviceAbis.firstNotNullOfOrNull { abi ->
                            // 标准 ABI 名称 → APK 文件名中使用的所有可能后缀
                            val possibleSuffixes = when (abi) {
                                "arm64-v8a" -> listOf("-arm64-v8a.apk", "-arm64.apk")
                                "armeabi-v7a" -> listOf("-armeabi-v7a.apk", "-arm32.apk")
                                "x86_64" -> listOf("-x86_64.apk", "-x64.apk")
                                "x86" -> listOf("-x86.apk")
                                else -> listOf("-$abi.apk")
                            }
                            androidApks.firstOrNull { (name, _) ->
                                possibleSuffixes.any { suffix -> name.endsWith(suffix, ignoreCase = true) }
                            }?.second
                        } ?: androidApks.firstOrNull()?.second ?: releaseUrl
                    }
                }
                Log.i(TAG, "Latest release: $tagName, downloadUrl=$downloadUrl")
                return Triple(tagName, downloadUrl, releaseUrl)
            } else if (conn.responseCode == 403) {
                Log.w(TAG, "GitHub API rate limited")
                return Triple(null, null, null)
            }
        } finally {
            conn.disconnect()
        }
        return Triple(null, null, null)
    }

    /** 比较版本号（与 PC 端 _is_newer_version 对齐），判断 latest 是否比 current 新 */
    private fun isNewerVersion(current: String, latest: String): Boolean {
        return try {
            // 清理版本号中的非数字前缀（如 v1.0.0）
            val cleanCurrent = current.trim().trimStart('v', 'V')
            val cleanLatest = latest.trim().trimStart('v', 'V')
            val currentParts = cleanCurrent.split(".").map { it.toIntOrNull() ?: 0 }
            val latestParts = cleanLatest.split(".").map { it.toIntOrNull() ?: 0 }
            val maxLen = maxOf(currentParts.size, latestParts.size)
            val c = currentParts + List(maxLen - currentParts.size) { 0 }
            val l = latestParts + List(maxLen - latestParts.size) { 0 }
            for (i in 0 until maxLen) {
                if (l[i] > c[i]) return true
                if (l[i] < c[i]) return false
            }
            false
        } catch (e: Exception) {
            Log.w(TAG, "Version comparison failed: current=$current latest=$latest")
            false
        }
    }
    fun toggleOpenUrlDialog() {
        _openUrlDialogOpen.value = !_openUrlDialogOpen.value
        if (!_openUrlDialogOpen.value) showControlsAutoHide()
    }
    fun toggleMappingPanel() {
        _mappingPanelOpen.value = !_mappingPanelOpen.value
        if (_mappingPanelOpen.value) {
            loadMappings()
        } else {
            showControlsAutoHide()
        }
    }
    fun toggleAvSyncPanel() {
        _avSyncPanelOpen.value = !_avSyncPanelOpen.value
        if (_avSyncPanelOpen.value) {
            startAvSyncSampling()
        } else {
            stopAvSyncSampling()
            stopSubSync()
            showControlsAutoHide()
        }
    }
    fun toggleNetworkPanel() {
        _networkPanelOpen.value = !_networkPanelOpen.value
        if (!_networkPanelOpen.value) showControlsAutoHide()
    }
    fun toggleToolsPanel() {
        _toolsPanelOpen.value = !_toolsPanelOpen.value
        if (!_toolsPanelOpen.value) showControlsAutoHide()
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
            showControlsAutoHide()
        } else {
            // 打开面板时刷新一次状态（若仍在运行则启动轮询）
            refreshScanStatusOnce()
        }
    }

    /**
     * 启动 URL 范围扫描。baseUrl 支持 [1-255] 范围表达式
     * （如 http://192.168.1.[1-255]:8080）。启动成功后开始轮询状态。
     */
    fun startScan(
        baseUrl: String, timeout: Int = 10, threads: Int = 4,
        engine: String = "requests", retry: Boolean = false, append: Boolean = false
    ) {
        if (baseUrl.isBlank()) {
            showOsd("扫描", "请输入基础 URL")
            return
        }
        viewModelScope.launch {
            _scanLoading.value = true
            _scanError.value = ""
            if (!append) _scanResults.value = emptyList()
            val result = repository.startScan(baseUrl, timeout, threads, engine, retry, append)
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

    /** 启动扫描状态轮询（800ms 间隔，扫描中实时加载结果，扫描结束后自动停止轮询） */
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
                // 每次轮询都获取最新结果（实时显示，不需等扫描结束）
                repository.getScanResults().onSuccess { _scanResults.value = it }
                if (!status.running) {
                    // 扫描结束
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

    /**
     * 删除单条扫描结果（仅前端列表，不影响已添加到频道列表的有效频道）。
     * 用于扫描完成后整理结果。
     */
    fun deleteScanResult(url: String) {
        _scanResults.value = _scanResults.value.filterNot { it.url == url }
    }

    /** 清空所有扫描结果（仅前端列表） */
    fun clearScanResults() {
        _scanResults.value = emptyList()
    }

    // -----------------------------------------------------------------
    // 频道网络验证（#5）
    // -----------------------------------------------------------------

    /** 启动频道网络验证 */
    fun startValidate(timeout: Int = 10, threads: Int = 4) {
        viewModelScope.launch {
            _scanLoading.value = true
            _scanError.value = ""
            val result = repository.startValidate(timeout, threads)
            _scanLoading.value = false
            result.onSuccess { started ->
                if (started) {
                    showOsd("验证", "已启动频道验证")
                    startScanPolling()
                } else {
                    _scanError.value = "扫描/验证已在进行中"
                    showOsd("验证", "扫描/验证已在进行中")
                }
            }.onFailure { e ->
                _scanError.value = e.message ?: "启动失败"
                showOsd("验证", "启动失败: ${e.message}")
            }
        }
    }

    // -----------------------------------------------------------------
    // 批量编辑（#4）
    // -----------------------------------------------------------------

    /** 批量编辑频道，成功后刷新频道列表 */
    fun batchEditChannels(action: String, optionsJson: String = "{}") {
        viewModelScope.launch {
            val result = repository.batchEditChannels(action, optionsJson)
            result.onSuccess { resp ->
                showOsd("批量编辑", "已修改 ${resp.changed}/${resp.total} 条")
                loadChannels()
            }.onFailure { e ->
                showOsd("批量编辑", "失败: ${e.message}")
            }
        }
    }

    // -----------------------------------------------------------------
    // 单条频道编辑（#6）
    // -----------------------------------------------------------------

    /** 更新单条频道字段，成功后刷新频道列表 */
    fun updateChannel(idx: Int, fields: Map<String, String>) {
        viewModelScope.launch {
            val result = repository.updateChannel(idx, fields)
            result.onSuccess {
                showOsd("编辑", "已保存")
                loadChannels()
            }.onFailure { e ->
                showOsd("编辑", "保存失败: ${e.message}")
            }
        }
    }

    /**
     * 将扫描结果中的有效频道导出为 M3U 文件，保存到 Downloads 目录。
     * 调用后端 get_m3u_text(group="扫描结果", validOnly=true) 获取 M3U 文本。
     */
    fun exportScanResultsAsM3u() {
        val validResults = _scanResults.value.filter { it.valid }
        if (validResults.isEmpty()) {
            showOsd("导出", "无有效频道可导出")
            return
        }

        viewModelScope.launch {
            try {
                // 直接从前端 scanResults 构造 M3U 内容，不依赖后端 getM3uText
                val m3uText = buildString {
                    appendLine("#EXTM3U")
                    for (result in validResults) {
                        val name = result.name.ifBlank { result.url }
                        val group = result.group.ifBlank { "扫描结果" }
                        appendLine("#EXTINF:-1 tvg-name=\"$name\" group-title=\"$group\",$name")
                        appendLine(result.url)
                    }
                }
                val channelCount = validResults.size

                val ts = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.CHINA)
                    .format(java.util.Date())
                val filename = "scan_$ts.m3u"
                val app = getApplication<Application>()
                val written = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val resolver = app.contentResolver
                    val values = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
                        put(MediaStore.MediaColumns.MIME_TYPE, "audio/x-mpegurl")
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    }
                    val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    if (uri == null) false
                    else {
                        resolver.openOutputStream(uri)?.use { it.write(m3uText.toByteArray()) } ?: false
                        true
                    }
                } else {
                    @Suppress("DEPRECATION")
                    val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                    if (!dir.exists()) dir.mkdirs()
                    File(dir, filename).writeText(m3uText)
                    true
                }
                if (written) {
                    showOsd("导出", "已保存到 Downloads/$filename（$channelCount 个频道）")
                    Log.i(TAG, "Scan results exported to Downloads/$filename ($channelCount channels)")
                } else {
                    showOsd("导出", "保存失败")
                }
            } catch (e: Exception) {
                Log.e(TAG, "exportScanResultsAsM3u failed", e)
                showOsd("导出", "导出失败: ${e.message}")
            }
        }
    }

    /**
     * 将扫描结果中的有效频道直接导入到播放列表。
     * 使用 import_channels 接口，构造 M3U 格式内容后导入。
     */
    fun importScanResultsToChannels() {
        val validResults = _scanResults.value.filter { it.valid }
        if (validResults.isEmpty()) {
            showOsd("导入", "无有效频道可导入")
            return
        }

        viewModelScope.launch {
            _scanLoading.value = true
            try {
                // 构造 M3U 格式内容
                val m3uContent = buildString {
                    appendLine("#EXTM3U")
                    for (result in validResults) {
                        val name = result.name.ifBlank { result.url }
                        val group = result.group.ifBlank { "扫描结果" }
                        appendLine("#EXTINF:-1 tvg-name=\"$name\" group-title=\"$group\",$name")
                        appendLine(result.url)
                    }
                }

                val importResult = repository.importChannels(m3uContent, "扫描结果导入")
                importResult.onSuccess { count ->
                    // 刷新频道列表
                    loadChannels()
                    showOsd("导入", "已导入 $count 个频道到播放列表")
                    Log.i(TAG, "importScanResultsToChannels: imported $count channels")
                }.onFailure { e ->
                    showOsd("导入", "导入失败: ${e.message}")
                    Log.e(TAG, "importScanResultsToChannels failed", e)
                }
            } catch (e: Exception) {
                Log.e(TAG, "importScanResultsToChannels failed", e)
                showOsd("导入", "导入失败: ${e.message}")
            } finally {
                _scanLoading.value = false
            }
        }
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
            showControlsAutoHide()
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
            showControlsAutoHide()
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
        showControlsAutoHide()
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
        // 仅本地文件恢复续播位置（直播/网络流不恢复，避免 seek 到错误位置）
        if (!ProgressHelper.isLocalFile(url)) return
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
     * - 仅本地视频/音频文件保存时间戳（与 PC 端 _is_network_url 判断对齐）
     * - 直播流（网络协议）不保存，避免 HLS 滑动窗口 duration 被误判为 VOD
     * - 未在播放（url 为空）不保存
     */
    private fun autoSaveResume() {
        if (currentPlaybackUrl.isEmpty()) return
        // 仅本地文件保存续播位置（直播/网络流不保存）
        if (!ProgressHelper.isLocalFile(currentPlaybackUrl)) return
        val pos = mpv.timePos.value
        val dur = mpv.duration.value
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
            showControlsAutoHide()
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
            showControlsAutoHide()
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
            showControlsAutoHide()
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
            showControlsAutoHide()
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
            showControlsAutoHide()
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
     * 加载时间线数据：按 [EpgTimelineRange] 筛选频道（显示所有频道），
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
        }

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
            showControlsAutoHide()
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
            showControlsAutoHide()
        }
    }

    // -----------------------------------------------------------------
    // 画中画 (PiP) — 与 PC 端 PipController 对齐
    // -----------------------------------------------------------------

    /** 手动进入 PiP 模式（由 Activity 的 enterPipManual() 实现） */
    fun enterPip() {
        onEnterPip?.invoke() ?: showOsd("画中画", "当前环境不支持")
    }

    // -----------------------------------------------------------------
    // 主题模式切换 — 与 PC 端 ThemeManager color_mode 对齐
    // -----------------------------------------------------------------

    /** 设置主题模式：dark / light / system */
    fun setThemeMode(mode: String) {
        _themeMode.value = mode
        userPrefs.setThemeMode(mode)
        val name = when (mode) {
            "light" -> "浅色"
            "system" -> "跟随系统"
            else -> "深色"
        }
        showOsd("主题", name)
    }

    // -----------------------------------------------------------------
    // 最近打开 — 与 PC 端 recent_menu 对齐
    // -----------------------------------------------------------------

    fun toggleRecentPanel() {
        _recentPanelOpen.value = !_recentPanelOpen.value
        if (_recentPanelOpen.value) {
            _recentFiles.value = userPrefs.getRecentFiles()
        } else {
            showControlsAutoHide()
        }
    }

    fun addRecentFile(uri: String, name: String, type: String) {
        userPrefs.addRecentFile(RecentEntry(uri, name, type, System.currentTimeMillis()))
        _recentFiles.value = userPrefs.getRecentFiles()
    }

    fun removeRecentFile(uri: String) {
        userPrefs.removeRecentFile(uri)
        _recentFiles.value = userPrefs.getRecentFiles()
    }

    fun clearRecentFiles() {
        userPrefs.clearRecentFiles()
        _recentFiles.value = emptyList()
        showOsd("最近打开", "已清空")
    }

    /** 从最近打开列表中恢复播放 */
    fun playRecent(entry: RecentEntry) {
        closeAllPanels()
        when (entry.type) {
            "playlist" -> openPlaylistFromUri(entry.uri, entry.name)
            "url" -> {
                _currentIdx.value = -1
                _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
                currentPlaybackUrl = entry.uri
                currentPlaybackName = entry.name
                mpv.playFile(entry.uri)
                showOsd("播放", entry.name)
            }
            "video" -> playLocalVideo(entry.uri)
        }
    }

    // -----------------------------------------------------------------
    // 另存为 — 导出频道列表为 M3U（与 PC 端 save_as 对齐）
    // -----------------------------------------------------------------

    /** 导出当前频道列表为 M3U 文件，写入下载目录 */
    fun saveAsM3u() {
        viewModelScope.launch {
            try {
                val channels = _channels.value
                if (channels.isEmpty()) {
                    showOsd("另存为", "频道列表为空")
                    return@launch
                }
                showOsd("另存为", "正在导出...")
                val m3uContent = buildM3uContent(channels)
                val written = withContext(Dispatchers.IO) { writeM3uToFile(m3uContent) }
                if (written) {
                    showOsd("另存为", "已导出到下载目录")
                } else {
                    showOsd("另存为", "导出失败")
                }
            } catch (e: Exception) {
                Log.e(TAG, "saveAsM3u failed: ${e.message}", e)
                showOsd("另存为", "导出失败: ${e.message}")
            }
        }
    }

    private fun buildM3uContent(channels: List<IptvChannel>): String {
        val sb = StringBuilder()
        sb.append("#EXTM3U\n")
        channels.forEach { ch ->
            val attrs = StringBuilder()
            if (ch.tvgId.isNotEmpty()) attrs.append(" tvg-id=\"${ch.tvgId}\"")
            if (ch.tvgName.isNotEmpty()) attrs.append(" tvg-name=\"${ch.tvgName}\"")
            if (ch.logo.isNotEmpty()) attrs.append(" tvg-logo=\"${ch.logo}\"")
            if (ch.group.isNotEmpty()) attrs.append(" group-title=\"${ch.group}\"")
            sb.append("#EXTINF:-1$attrs,${ch.name}\n")
            sb.append("${ch.url}\n")
        }
        return sb.toString()
    }

    private fun writeM3uToFile(content: String): Boolean {
        val now = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.US).format(java.util.Date())
        val filename = "ISEP_export_$now.m3u"
        return try {
            val app = getApplication<Application>()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val resolver = app.contentResolver
                val values = android.content.ContentValues().apply {
                    put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, filename)
                    put(android.provider.MediaStore.MediaColumns.MIME_TYPE, "audio/x-mpegurl")
                    put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = resolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return false
                resolver.openOutputStream(uri)?.use { it.write(content.toByteArray()) } ?: return false
            } else {
                @Suppress("DEPRECATION")
                val dir = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
                if (!dir.exists()) dir.mkdirs()
                java.io.File(dir, filename).writeText(content)
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "writeM3uToFile failed", e)
            false
        }
    }

    // -----------------------------------------------------------------
    // 刷新 UI — 重新加载频道/EPG（与 PC 端 F5 refresh 对齐）
    // -----------------------------------------------------------------

    fun refreshUi() {
        if (_refreshing.value) return
        _refreshing.value = true
        viewModelScope.launch {
            showOsd("刷新", "正在重新加载...")
            try {
                loadChannels()
                fetchEpgForChannel(_currentIdx.value)
                showOsd("刷新", "已完成")
            } catch (e: Exception) {
                showOsd("刷新", "失败: ${e.message}")
            } finally {
                _refreshing.value = false
            }
        }
    }

    // -----------------------------------------------------------------
    // 画面比例切换 — 循环：默认 → 16:9 → 4:3 → 拉伸 → 默认
    // -----------------------------------------------------------------

    private val aspectRatioModes = listOf("默认" to null, "16:9" to "16:9", "4:3" to "4:3", "拉伸" to "stretch")
    private val _aspectRatioIdx = MutableStateFlow(0)
    val aspectRatioIdx: StateFlow<Int> = _aspectRatioIdx.asStateFlow()

    /** 循环切换画面比例 */
    fun cycleAspectRatio() {
        _aspectRatioIdx.value = (_aspectRatioIdx.value + 1) % aspectRatioModes.size
        val (label, value) = aspectRatioModes[_aspectRatioIdx.value]
        when (value) {
            null -> {
                // 默认：恢复 keepaspect + 取消 pan-scan
                mpv.setPropertyString("keepaspect", "yes")
                mpv.setPropertyString("video-unscaled", "no")
                mpv.setPropertyString("video-zoom", "0")
            }
            "stretch" -> {
                // 拉伸：关闭 keepaspect，填满画面
                mpv.setPropertyString("keepaspect", "no")
                mpv.setPropertyString("video-unscaled", "no")
                mpv.setPropertyString("video-zoom", "0")
            }
            else -> {
                // 指定比例：keepaspect + video-aspect-override
                mpv.setPropertyString("keepaspect", "yes")
                mpv.setPropertyString("video-aspect-override", value)
                mpv.setPropertyString("video-unscaled", "no")
                mpv.setPropertyString("video-zoom", "0")
            }
        }
        showOsd("画面比例", label)
    }

    // -----------------------------------------------------------------
    // 切片导出 — 利用 ffmpeg（与 PC 端 ClipExportDialog 对齐）
    // -----------------------------------------------------------------

    fun toggleClipExportPanel() {
        _clipExportPanelOpen.value = !_clipExportPanelOpen.value
        if (!_clipExportPanelOpen.value) showControlsAutoHide()
    }

    /**
     * 导出视频片段。使用 ffmpeg 命令行裁剪指定时间段。
     * @param startTime 开始时间（秒）
     * @param duration 持续时间（秒）
     * @param format 输出格式："mp4" / "gif" / "mp3"
     */
    fun exportClip(startTime: Double, duration: Double, format: String) {
        val url = currentPlaybackUrl.ifBlank { return }
        if (duration <= 0 || startTime < 0) {
            showOsd("切片导出", "参数无效")
            return
        }
        viewModelScope.launch {
            _clipExportStatus.value = "准备中..."
            _clipExportProgress.value = 0
            try {
                val app = getApplication<Application>()
                val now = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.US).format(java.util.Date())
                val ext = when (format) { "gif" -> "gif"; "mp3" -> "mp3"; else -> "mp4" }
                val filename = "ISEP_clip_$now.$ext"

                // 获取输出路径
                val outFile = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val resolver = app.contentResolver
                    val mimeType = when (format) {
                        "gif" -> "image/gif"
                        "mp3" -> "audio/mpeg"
                        else -> "video/mp4"
                    }
                    val values = android.content.ContentValues().apply {
                        put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, filename)
                        put(android.provider.MediaStore.MediaColumns.MIME_TYPE, mimeType)
                        put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, android.os.Environment.DIRECTORY_DOWNLOADS)
                    }
                    val uri = resolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    uri?.let { resolver.openOutputStream(it) }?.let { java.io.File.createTempFile("clip_tmp", ".$ext", app.cacheDir).also { tmp -> tmp.outputStream().use { _ -> } } }
                } else {
                    @Suppress("DEPRECATION")
                    val dir = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
                    if (!dir.exists()) dir.mkdirs()
                    java.io.File(dir, filename)
                }

                if (outFile == null) {
                    _clipExportStatus.value = "无法创建输出文件"
                    return@launch
                }

                _clipExportStatus.value = "正在导出..."

                // 构建 ffmpeg 命令
                val ffmpegDir = java.io.File(app.applicationInfo.nativeLibraryDir, "ffmpeg")
                val ffmpegBin = if (ffmpegDir.exists()) ffmpegDir.absolutePath else "ffmpeg"

                val cmd = mutableListOf(ffmpegBin, "-y")
                cmd.addAll(listOf("-ss", startTime.toString()))
                cmd.addAll(listOf("-i", url))
                cmd.addAll(listOf("-t", duration.toString()))

                when (format) {
                    "gif" -> {
                        cmd.addAll(listOf("-vf", "fps=10,scale=480:-1:flags=lanczos"))
                        cmd.addAll(listOf("-loop", "0"))
                    }
                    "mp3" -> {
                        cmd.addAll(listOf("-vn", "-acodec", "libmp3lame", "-q:a", "2"))
                    }
                    else -> {
                        cmd.addAll(listOf("-c", "copy", "-avoid_negative_ts", "make_zero"))
                    }
                }
                cmd.add(outFile.absolutePath)

                val process = ProcessBuilder(cmd).redirectErrorStream(true).start()
                val reader = java.io.BufferedReader(java.io.InputStreamReader(process.inputStream))
                var line: String?
                var progress = 0
                while (reader.readLine().also { line = it } != null) {
                    Log.d(TAG, "ffmpeg: $line")
                    progress = (progress + 5) % 100
                    _clipExportProgress.value = progress
                }
                val exitCode = process.waitFor()
                if (exitCode == 0) {
                    _clipExportProgress.value = 100
                    _clipExportStatus.value = "导出成功: $filename"
                    showOsd("切片导出", "已导出到下载目录")
                } else {
                    _clipExportStatus.value = "导出失败 (exit=$exitCode)"
                    showOsd("切片导出", "导出失败")
                }
            } catch (e: Exception) {
                Log.e(TAG, "exportClip failed", e)
                _clipExportStatus.value = "错误: ${e.message}"
                showOsd("切片导出", "错误: ${e.message}")
            }
        }
    }

    // -----------------------------------------------------------------
    // 音频可视化 — 频谱波形（与 PC 端 audio_visual 对齐）
    // -----------------------------------------------------------------

    fun toggleAudioVisualizer() {
        _audioVisualizerOpen.value = !_audioVisualizerOpen.value
        if (_audioVisualizerOpen.value) {
            // 检查 RECORD_AUDIO 权限
            val app = getApplication<Application>()
            val hasPermission = android.content.pm.PackageManager.PERMISSION_GRANTED ==
                androidx.core.content.ContextCompat.checkSelfPermission(app, android.Manifest.permission.RECORD_AUDIO)
            if (hasPermission) {
                startSpectrumSampling()
            } else {
                // 没有权限，直接用 MPV fallback 模式
                Log.w(TAG, "RECORD_AUDIO permission not granted, using MPV fallback for spectrum")
                startSpectrumSampling()
            }
        } else {
            stopSpectrumSampling()
            showControlsAutoHide()
        }
    }

    private var spectrumJob: kotlinx.coroutines.Job? = null
    private var visualizer: android.media.audiofx.Visualizer? = null

    private fun startSpectrumSampling() {
        spectrumJob?.cancel()
        // 尝试用 Android Visualizer API 获取真实音频频谱
        var visualizerStarted = false
        try {
            visualizer?.release()
            // 尝试获取 MPV 的 audio session id
            val audioSessionId = try {
                mpv.getPropertyInt("audio-params")?.let { 0 } ?: 0
            } catch (_: Exception) { 0 }
            
            visualizer = android.media.audiofx.Visualizer(audioSessionId)
            visualizer?.captureSize = android.media.audiofx.Visualizer.getCaptureSizeRange()[1]
            visualizer?.setDataCaptureListener(object : android.media.audiofx.Visualizer.OnDataCaptureListener {
                override fun onWaveFormDataCapture(v: android.media.audiofx.Visualizer?, waveform: ByteArray?, samplingRate: Int) {
                    if (waveform == null) return
                    // 波形数据不用做频谱，FFT 更适合。这里不处理。
                }
                override fun onFftDataCapture(v: android.media.audiofx.Visualizer?, fft: ByteArray?, samplingRate: Int) {
                    if (fft == null) return
                    val bands = 32
                    val spectrum = FloatArray(bands) { 0f }
                    val n = fft.size / 2  // FFT bin 数量（不含 DC）
                    // 跳过 bin 0（DC 分量，总是最大且无意义）
                    // 使用对数分频段：低频段窄、高频段宽，符合人耳感知
                    for (i in 0 until bands) {
                        // 对数映射：band i 对应的 bin 范围
                        val startBin = (Math.pow(n.toDouble(), i.toDouble() / bands) + 1).toInt()
                        val endBin = (Math.pow(n.toDouble(), (i + 1).toDouble() / bands) + 1).toInt().coerceAtMost(n)
                        var maxMag = 0f
                        for (j in startBin until endBin) {
                            val idx = j * 2
                            if (idx + 1 < fft.size) {
                                val re = fft[idx].toFloat()
                                val im = fft[idx + 1].toFloat()
                                val mag = kotlin.math.sqrt(re * re + im * im)
                                if (mag > maxMag) maxMag = mag
                            }
                        }
                        // 对数缩放：更灵敏，更像常见频谱仪
                        // mag 范围约 0~9052（Visualizer FFT 最大值），用 log 映射到 0~1
                        val normalized = if (maxMag > 0.1f) {
                            (kotlin.math.log10(maxMag + 1) / kotlin.math.log10(9052f)).coerceIn(0f, 1f)
                        } else 0f
                        spectrum[i] = normalized
                    }
                    _audioSpectrum.value = spectrum
                }
            }, android.media.audiofx.Visualizer.getMaxCaptureRate(), false, true)
            // 只用 FFT 数据（waveform=false, fft=true），最大采样率实现 60fps
            visualizer?.enabled = true
            visualizerStarted = true
            Log.i(TAG, "Visualizer started for real-time spectrum")
        } catch (e: Exception) {
            Log.w(TAG, "Visualizer not available: ${e.message}, using MPV peak level")
            visualizerStarted = false
        }
        
        if (!visualizerStarted) {
            // fallback：Visualizer 不可用时用模拟频谱
            spectrumJob = viewModelScope.launch {
                while (_audioVisualizerOpen.value) {
                    try {
                        if (mpv.fileLoaded.value) {
                            val volume = mpv.getPropertyDouble("volume") ?: 100.0
                            val volFactor = (volume / 100.0).coerceIn(0.0, 1.0).toFloat()
                            val timeMs = System.currentTimeMillis()
                            val spectrum = FloatArray(32) { i ->
                                // 模拟常见频谱：低频强高频弱 + 随机波动
                                val t = timeMs / 1000.0
                                // 基础衰减：低频高、高频低（模拟音乐能量分布）
                                val baseDecay = kotlin.math.exp(-i.toDouble() * 0.05)
                                // 多个频率叠加产生自然变化
                                val wave1 = kotlin.math.sin(t * 3.0 + i * 0.4) * 0.3
                                val wave2 = kotlin.math.sin(t * 7.0 + i * 0.9) * 0.2
                                val wave3 = kotlin.math.sin(t * 13.0 + i * 1.5) * 0.15
                                // 随机微波动
                                val noise = (kotlin.math.sin(t * 23.0 + i * 3.7) * 0.1)
                                val amp = ((baseDecay + wave1 + wave2 + wave3 + noise) * volFactor).toFloat()
                                amp.coerceIn(0.02f, 1f)
                            }
                            _audioSpectrum.value = spectrum
                        }
                    } catch (_: Exception) {}
                    kotlinx.coroutines.delay(16) // ~60fps
                }
            }
        }
    }

    private fun stopSpectrumSampling() {
        spectrumJob?.cancel()
        spectrumJob = null
        visualizer?.enabled = false
        visualizer?.release()
        visualizer = null
        _audioSpectrum.value = FloatArray(32) { 0f }
    }

    // -----------------------------------------------------------------
    // 歌词 — 加载/显示/同步（与 PC 端 LyricsWidget 对齐）
    // -----------------------------------------------------------------

    fun toggleLyricsPanel() {
        _lyricsOpen.value = !_lyricsOpen.value
        if (_lyricsOpen.value) {
            startLyricsSync()
        } else {
            stopLyricsSync()
            showControlsAutoHide()
        }
    }

    private var lyricsSyncJob: kotlinx.coroutines.Job? = null

    /** 从文件 URI 加载 LRC 歌词 */
    fun loadLyricsFromUri(uri: String) {
        viewModelScope.launch {
            try {
                val app = getApplication<Application>()
                val content = withContext(kotlinx.coroutines.Dispatchers.IO) {
                    if (uri.startsWith("content://")) {
                        app.contentResolver.openInputStream(android.net.Uri.parse(uri))?.bufferedReader()?.use { it.readText() }
                    } else if (uri.startsWith("http")) {
                        java.net.URL(uri).readText()
                    } else {
                        java.io.File(uri).readText()
                    }
                } ?: run {
                    showOsd("歌词", "无法读取文件")
                    return@launch
                }
                parseLrc(content)
                showOsd("歌词", "已加载 ${_lyricsLines.value.size} 行")
            } catch (e: Exception) {
                showOsd("歌词", "加载失败: ${e.message}")
            }
        }
    }

    /** 解析 LRC 格式歌词 [mm:ss.xx]文本 */
    private fun parseLrc(content: String) {
        val lines = mutableListOf<LyricsLine>()
        val pattern = Regex("""\[(\d+):(\d+)(?:\.(\d+))?\](.*)""")
        content.lines().forEach { line ->
            val matches = pattern.findAll(line)
            val text = if (matches.none()) line.trim() else {
                val lastMatch = matches.last()
                lastMatch.groupValues[4].trim()
            }
            matches.forEach { m ->
                val min = m.groupValues[1].toLongOrNull() ?: 0L
                val sec = m.groupValues[2].toLongOrNull() ?: 0L
                val ms = m.groupValues[3].let { if (it.isNotEmpty()) (it.toLongOrNull() ?: 0L) else 0L }
                val time = (min * 60 + sec) * 1000 + ms
                val lyricText = m.groupValues[4].trim()
                if (lyricText.isNotEmpty()) {
                    lines.add(LyricsLine(time, lyricText))
                }
            }
            // 无时间标签的行（如歌曲信息）
            if (matches.none() && text.isNotEmpty()) {
                lines.add(LyricsLine(0, text))
            }
        }
        lines.sortBy { it.time }
        _lyricsLines.value = lines
    }

    private fun startLyricsSync() {
        lyricsSyncJob?.cancel()
        lyricsSyncJob = viewModelScope.launch {
            while (_lyricsOpen.value) {
                try {
                    if (mpv.fileLoaded.value && _lyricsLines.value.isNotEmpty()) {
                        val posMs = (mpv.timePos.value * 1000).toLong()
                        val idx = _lyricsLines.value.indexOfLast { it.time <= posMs }
                        if (idx != _currentLyricLine.value) {
                            _currentLyricLine.value = idx
                        }
                    }
                } catch (e: Exception) {
                    // 忽略
                }
                kotlinx.coroutines.delay(200)
            }
        }
    }

    private fun stopLyricsSync() {
        lyricsSyncJob?.cancel()
        lyricsSyncJob = null
        _currentLyricLine.value = -1
    }

    /** 清除当前歌词 */
    fun clearLyrics() {
        _lyricsLines.value = emptyList()
        _currentLyricLine.value = -1
        showOsd("歌词", "已清除")
    }

    // -----------------------------------------------------------------
    // 从 URI 打开播放列表（文件关联入口）
    // -----------------------------------------------------------------

    /** 从外部 URI 导入播放列表 */
    fun openPlaylistFromUri(uri: String, name: String) {
        if (uri.startsWith("content://") || uri.startsWith("file://")) {
            val parsed = android.net.Uri.parse(uri)
            importPlaylist(parsed)
            return
        }
        viewModelScope.launch {
            showOsd("打开播放列表", name)
            try {
                val added = withContext(kotlinx.coroutines.Dispatchers.IO) {
                    repository.addSource(name, uri)
                }
                if (added.isSuccess) {
                    addRecentFile(uri, name, "playlist")
                    loadSources()
                    loadChannels()
                    showOsd("播放列表", "已导入: $name")
                } else {
                    showOsd("播放列表", "导入失败")
                }
            } catch (e: Exception) {
                showOsd("播放列表", "错误: ${e.message}")
            }
        }
    }

    // -----------------------------------------------------------------
    // HDR 模式切换（与 PC 端 _apply_hdr_on_file_loaded / _set_hdr_mode 对齐）
    //
    // Android 端 4 种模式：DISABLE / AUTO / TONEMAP / PASSTHROUGH
    // - 不改变 vo（保持用户持久化选择），只在文件加载时应用 HDR 配置
    // - PASSTHROUGH 使用 target-colorspace-hint 让 Android 系统自动切换 HDR 显示模式
    // - AUTO 模式：检测设备 HDR 能力，支持则直通，不支持则色调映射
    // - 支持 HDR10/HDR10+/HLG/WCG（bt.2020 色域）/杜比视界（8.1 版本兼容）
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
            HdrMode.AUTO -> "自动（按设备能力选择直通或色调映射）"
            HdrMode.TONEMAP -> "HDR→SDR 色调映射"
            HdrMode.PASSTHROUGH -> "HDR 直通（系统自动切换 HDR 显示）"
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
     *    - HDR 视频 + tonemap → 色调映射到 SDR（保留 bt.2020 广色域）
     *    - HDR 视频 + passthrough → 直通（清空 target 参数 + target-colorspace-hint）
     *    - HDR 视频 + auto → 检测设备 HDR 能力，支持则直通，不支持则色调映射
     */
    fun applyHdrOnFileLoaded() {
        val mode = _hdrMode.value
        val mpv = this.mpv
        if (!mpv.fileLoaded.value) return

        val currentVo = try { mpv.getPropertyString("vo") ?: "" } catch (_: Throwable) { "" }
        if (currentVo == "mediacodec_embed") {
            Log.i(TAG, "HDR 配置：跳过，vo=mediacodec_embed 不支持 GPU 色调映射属性")
            return
        }

        try {
            // disable 模式：直接重置 SDR 参数
            if (mode == HdrMode.DISABLE) {
                resetHdrParams(mpv)
                Log.i(TAG, "HDR 配置：disable → 重置 SDR 默认值")
                return
            }

            // 检测视频是否 HDR（与 PC 端统一逻辑）
            val gamma = (mpv.getPropertyString("video-params/gamma") ?: "").lowercase()
            val prim = (mpv.getPropertyString("video-params/primaries") ?: "").lowercase()
            val cm = (mpv.getPropertyString("video-params/colormatrix") ?: "").lowercase()
            val peak = mpv.getPropertyDouble("video-params/sig-peak") ?: 0.0
            val vf = (mpv.getPropertyString("video-format") ?: "").lowercase()

            val isPq = gamma.contains("pq") || gamma.contains("smpte2084")
            val isHlg = gamma.contains("hlg") || gamma.contains("arib-std-b67")
            val hasDovi = vf.contains("dovi") || vf.contains("dolbyvision") ||
                vf.contains("dvhe") || vf.contains("dvh1") || vf.contains("dav1")
            val isBt2020 = cm.contains("bt.2020") || cm.contains("bt2020") ||
                cm.contains("bt.2100") || prim.contains("bt.2020") ||
                prim.contains("bt2020") || prim.contains("bt.2100")
            val isHdr = isPq || isHlg || hasDovi
            val isWcg = !isHdr && isBt2020

            Log.i(TAG, "HDR 检测：gamma=$gamma, primaries=$prim, sig_peak=$peak, " +
                "isHdr=$isHdr, isWcg=$isWcg, isPq=$isPq, isHlg=$isHlg, hasDovi=$hasDovi")

            if (isWcg) {
                // WCG 视频（宽色域 SDR）：保持 bt.2020 色域（与 PC 端 _apply_wcg_config 对齐）
                applyWcgConfig(mpv)
                Log.i(TAG, "HDR 配置：WCG 视频 → 保持 bt.2020 色域")
                return
            }

            if (!isHdr) {
                // 非 HDR 视频也重置 SDR 参数（避免残留上次 HDR 配置）
                resetHdrParams(mpv)
                Log.i(TAG, "HDR 配置：非 HDR 视频 → 重置 SDR 默认值")
                return
            }

            when (mode) {
                HdrMode.TONEMAP -> applyTonemapConfig(mpv, isPq)
                HdrMode.PASSTHROUGH -> applyPassthroughConfig(mpv, isPq)
                HdrMode.AUTO -> {
                    // AUTO 模式：检测设备 HDR 能力
                    if (isDeviceHdrSupported()) {
                        applyPassthroughConfig(mpv, isPq)
                        Log.i(TAG, "HDR 配置：AUTO → 设备支持 HDR，使用直通")
                    } else {
                        applyTonemapConfig(mpv, isPq)
                        Log.i(TAG, "HDR 配置：AUTO → 设备不支持 HDR，使用色调映射")
                    }
                }
                else -> resetHdrParams(mpv)
            }
            Log.i(TAG, "HDR 配置：mode=$mode 应用完成")
        } catch (e: Exception) {
            Log.e(TAG, "应用 HDR 设置失败", e)
        }
    }

    /**
     * 检测设备是否支持 HDR 显示。
     * 通过 Display.getHdrCapabilities() 检测（Android 7.0+）。
     */
    private fun isDeviceHdrSupported(): Boolean {
        return try {
            val display = (getApplication() as android.app.Application)
                .getSystemService(android.content.Context.WINDOW_SERVICE)
                .let { it as? android.view.WindowManager }
                ?.defaultDisplay
            if (display == null) return false
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                val caps = display.hdrCapabilities
                val types = caps?.supportedHdrTypes ?: IntArray(0)
                // HDR_TYPE_DOLBY_VISION=1, HDR_TYPE_HDR10=2, HDR_TYPE_HLG=3, HDR_TYPE_HDR10_PLUS=4
                types.isNotEmpty()
            } else {
                false
            }
        } catch (e: Exception) {
            Log.w(TAG, "HDR 能力检测失败: ${e.message}")
            false
        }
    }

    /**
     * 安全设置 mpv 字符串属性：跳过不支持的属性，避免 native 层错误日志。
     *
     * mpv-android 使用 mediacodec_embed VO 时，以下属性不存在（桌面版 GPU VO 才有）：
     * - tone-mapping / tone-mapping-mode / tone-mapping-desat
     * - hdr10-opt / hdr-compute-peak
     * - target-peak / gamut-mapping-mode
     *
     * 这些属性在 mediacodec_embed（硬件直通）模式下无意义，
     * 设置时会产生 "property not found" 错误日志。此方法用 try-catch 静默处理。
     */
    private fun safeSetProperty(mpv: Player, name: String, value: String) {
        try {
            mpv.setPropertyString(name, value)
        } catch (e: Throwable) {
            // 属性不存在或格式不支持，静默忽略（mediacodec_embed VO 不支持 GPU 色调映射属性）
        }
    }

    /**
     * 重置 HDR 参数为 SDR 默认值（与 PC 端 _reset_hdr_params 对齐）。
     * 显式指定 SDR 目标，确保 bt.2020 色域（WCG）视频能正确映射到 bt.709。
     *
     * 注意：tone-mapping 系列属性仅在 GPU VO 模式下有效，
     * mediacodec_embed 模式下会被安全跳过。
     */
    private fun resetHdrParams(mpv: Player) {
        safeSetProperty(mpv, "tone-mapping", "")
        safeSetProperty(mpv, "tone-mapping-mode", "")
        safeSetProperty(mpv, "tone-mapping-desat", "")
        safeSetProperty(mpv, "hdr-compute-peak", "")
        safeSetProperty(mpv, "hdr10-opt", "no")
        safeSetProperty(mpv, "target-prim", "bt.709")
        safeSetProperty(mpv, "target-trc", "bt.1886")
        safeSetProperty(mpv, "target-colorspace-hint", "no")
        safeSetProperty(mpv, "gamut-mapping-mode", "auto")
    }

    /**
     * HDR→SDR 色调映射配置（与 PC 端 _apply_tonemap_config 对齐）。
     * 关键改进：
     * - target-prim=bt.2020 保留广色域（WCG），在支持广色域的设备上显示更丰富色彩
     * - target-trc=bt.1886 SDR 伽马，确保 SDR 显示正确
     * - tone-mapping=auto 让 mpv 自动选择算法（HDR10+→st2094-40, HDR10/HLG→bt.2390）
     * - hdr-compute-peak=no 信任 HDR10+ 动态元数据，不自行计算峰值
     * - gamut-mapping-mode=perceptual 感知映射，减少色域裁剪损失
     */
    private fun applyWcgConfig(mpv: Player) {
        // WCG 视频（宽色域 SDR）：保持 bt.2020 色域，SDR 亮度（与 PC 端 _apply_wcg_config 对齐）
        safeSetProperty(mpv, "tone-mapping", "")
        safeSetProperty(mpv, "tone-mapping-mode", "")
        safeSetProperty(mpv, "tone-mapping-desat", "")
        safeSetProperty(mpv, "hdr-compute-peak", "")
        safeSetProperty(mpv, "hdr10-opt", "no")
        safeSetProperty(mpv, "target-prim", "bt.2020")
        safeSetProperty(mpv, "target-trc", "bt.1886")
        safeSetProperty(mpv, "target-colorspace-hint", "no")
        safeSetProperty(mpv, "target-peak", "100")
        safeSetProperty(mpv, "gamut-mapping-mode", "relative")
    }

    private fun applyTonemapConfig(mpv: Player, isPq: Boolean) {
        // HDR→SDR 色调映射（与 PC 端 _apply_tonemap_config 统一）
        // target-prim=bt.2020 保留广色域（WCG），在支持广色域的设备上显示更丰富色彩
        // target-trc=bt.1886 SDR 伽马，确保 SDR 显示正确
        // hdr10-opt=yes(仅PQ) 传递 HDR10+ 动态元数据
        // gamut-mapping-mode=perceptual 感知映射，减少色域裁剪损失
        safeSetProperty(mpv, "tone-mapping", "auto")
        safeSetProperty(mpv, "tone-mapping-mode", "auto")
        safeSetProperty(mpv, "tone-mapping-desat", "0.5")
        safeSetProperty(mpv, "hdr-compute-peak", "no")
        safeSetProperty(mpv, "hdr10-opt", if (isPq) "yes" else "no")
        safeSetProperty(mpv, "target-prim", "bt.2020")
        safeSetProperty(mpv, "target-trc", "bt.1886")
        safeSetProperty(mpv, "target-colorspace-hint", "no")
        safeSetProperty(mpv, "gamut-mapping-mode", "perceptual")
    }

    /**
     * HDR 直通配置（与 PC 端 _apply_passthrough_config 对齐）。
     * - 清空 target-prim/target-trc，让 mpv 直通视频原生色彩空间（不转换）
     * - 启用 target-colorspace-hint=yes，让 Android 系统自动切换 HDR 显示模式
     * - PQ: tone-mapping=clip + hdr-compute-peak=no（直接直通）
     * - HLG: tone-mapping=auto + hdr-compute-peak=yes（让 mpv 平滑处理 HLG→PQ）
     * - hdr10-opt=yes(仅PQ) 保留 HDR10+ 动态元数据
     */
    private fun applyPassthroughConfig(mpv: Player, isPq: Boolean) {
        safeSetProperty(mpv, "tone-mapping", if (isPq) "clip" else "auto")
        safeSetProperty(mpv, "tone-mapping-mode", "")
        safeSetProperty(mpv, "tone-mapping-desat", "0")
        safeSetProperty(mpv, "hdr-compute-peak", if (isPq) "no" else "yes")
        safeSetProperty(mpv, "hdr10-opt", if (isPq) "yes" else "no")
        // 清空 target 参数，让 mpv 直通视频原生色彩空间（PQ/HLG 不转换）
        safeSetProperty(mpv, "target-prim", "")
        safeSetProperty(mpv, "target-trc", "")
        // 关键：启用 target-colorspace-hint 让 Android 系统自动切换 HDR 显示模式
        // mpv 会通过 SurfaceView 传递 HDR 元数据给系统，系统自动切换到 HDR 显示
        safeSetProperty(mpv, "target-colorspace-hint", "yes")
        safeSetProperty(mpv, "gamut-mapping-mode", "clip")
    }

    // -----------------------------------------------------------------
    // 文件操作（打开播放列表 / 打开网络流 / 打开本地视频）
    // 与 PC 端 文件 菜单组对齐
    // -----------------------------------------------------------------

    /**
     * 检查设备是否有 SAF（Storage Access Framework）文件选择器可用。
     *
     * TV 设备通常没有预装文件管理器，调用 ActivityResultContracts.OpenDocument()
     * 会提示"没有可执行的应用"。此方法在启动选择器前检查可用性，
     * 不可用时调用方应显示替代方案（如订阅源管理）。
     */
    fun isSafAvailable(): Boolean {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
        }
        val pm = getApplication<Application>().packageManager
        // Android TV 系统可能注册了 frameworkpackagestubs 桩 activity，
        // 它声明能处理 ACTION_OPEN_DOCUMENT 但实际启动时会提示"没有可执行的应用"。
        // 需要排除此类 stub，只认可真实的文件管理器 activity。
        val realActivities = pm.queryIntentActivities(intent, 0).filter { ri ->
            val name = ri.activityInfo.name
            val pkg = ri.activityInfo.packageName
            val isStub = name.contains("Stub", ignoreCase = true) ||
                pkg.contains("frameworkpackagestubs", ignoreCase = true)
            !isStub
        }
        Log.i(TAG, "isSafAvailable: ${realActivities.size} real activities found (filtered out stubs)")
        return realActivities.isNotEmpty()
    }

    /**
     * 播放本地音视频文件（直接调 mpv.playFile，不走频道列表）。
     *
     * @param uri SAF 返回的 content:// URI 或 file:// 路径或绝对文件路径
     *
     * 注意：libmpv 不识别 content:// 协议，SAF 返回的 content:// URI 必须先拷贝到
     * 缓存文件再传文件路径给 mpv，否则会触发 native 崩溃（参照 loadSubtitleFile 实现）。
     */
    fun playLocalVideo(uri: String) {
        Log.i(TAG, "playLocalVideo: $uri")
        viewModelScope.launch {
            _currentIdx.value = -1
            _channelDisplayInfo.value = ChannelDisplayInfo(
                name = uri.substringAfterLast('/').substringAfterLast('%'),
                idx = -1, isLocal = true
            )
            _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
            currentIsLocalFile = true

            // content:// URI 需要拷贝到缓存文件；file:// 和绝对路径直接用
            val playPath = withContext(Dispatchers.IO) {
                if (uri.startsWith("content://")) {
                    try {
                        val app = getApplication<Application>()
                        val resolver = app.contentResolver
                        val cacheDir = app.cacheDir
                        // 从 MIME 类型推断扩展名（mpv 需要正确扩展名识别容器格式）
                        val mime = try { resolver.getType(Uri.parse(uri)) } catch (_: Exception) { null }
                        val ext = when {
                            mime == null -> ".mp4"
                            mime.contains("matroska") -> ".mkv"
                            mime.contains("mp4") -> ".mp4"
                            mime.contains("mpeg") -> ".mpg"
                            mime.contains("webm") -> ".webm"
                            mime.contains("audio/mpeg") -> ".mp3"
                            mime.contains("audio/") -> ".m4a"
                            else -> ".mp4"
                        }
                        val tempFile = File(cacheDir, "local_video_${System.currentTimeMillis()}$ext")
                        resolver.openInputStream(Uri.parse(uri))?.use { input ->
                            tempFile.outputStream().use { input.copyTo(it) }
                        } ?: return@withContext null
                        tempFile.absolutePath
                    } catch (e: Exception) {
                        Log.e(TAG, "playLocalVideo copy content:// failed", e)
                        null
                    }
                } else {
                    // file:// 或绝对路径，去除 file:// 前缀
                    uri.removePrefix("file://")
                }
            }

            if (playPath == null) {
                showOsd("播放失败", "无法读取文件")
                return@launch
            }

            // 续播位置：记录本地文件信息（用缓存文件路径，便于下次恢复）
            currentPlaybackUrl = playPath
            currentPlaybackName = playPath.substringAfterLast('/').substringAfterLast('%')
            refreshCurrentBookmarks()

            try {
                mpv.playFile(playPath)
                showOsd("本地文件", currentPlaybackName)
                closeAllPanels()
                _showHome.value = false  // 切换到播放器界面

                // 保存到历史记录和本地频道列表（source='' 标记为本地）
                try {
                    val fileName = currentPlaybackName.ifBlank { playPath.substringAfterLast('/') }
                    val existingIdx = _channels.value.indexOfFirst { it.url == playPath }
                    if (existingIdx < 0) {
                        // 新文件：添加为本地频道（同步等待完成）
                        val addResult = repository.addChannel(playPath, fileName, "本地视频")
                        addResult.onSuccess { addedIdx ->
                            // 直接在当前频道列表中追加，不依赖异步 loadChannels
                            val newChannel = IptvChannel(
                                name = fileName, url = playPath, group = "本地视频",
                                source = ""
                            )
                            _channels.value = _channels.value + newChannel
                            val newIdx = _channels.value.indexOfLast { it.url == playPath }
                            if (newIdx >= 0) {
                                _currentIdx.value = newIdx
                                _channelDisplayInfo.value = ChannelDisplayInfo(
                                    name = fileName, group = "本地视频", idx = newIdx, isLocal = true
                                )
                                currentIsLocalFile = false
                                userPrefs.addToHistory(newIdx)
                                _history.value = userPrefs.getHistory()
                                Log.i(TAG, "playLocalVideo: added local channel idx=$newIdx, name=$fileName")
                            }
                        }.onFailure { e ->
                            Log.w(TAG, "playLocalVideo: addChannel failed: ${e.message}")
                        }
                    } else {
                        userPrefs.addToHistory(existingIdx)
                        _history.value = userPrefs.getHistory()
                        _currentIdx.value = existingIdx
                        _channelDisplayInfo.value = ChannelDisplayInfo(
                            name = _channels.value.getOrNull(existingIdx)?.name ?: "",
                            group = "本地视频", idx = existingIdx, isLocal = true
                        )
                        currentIsLocalFile = false
                        Log.i(TAG, "playLocalVideo: existing channel idx=$existingIdx")
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "playLocalVideo: failed to save history: ${e.message}")
                }
            } catch (e: Throwable) {
                Log.e(TAG, "playLocalVideo mpv.playFile failed", e)
                showOsd("播放失败", e.message ?: "无法播放此文件")
            }
        }
    }

    /**
     * 播放网络流 URL。
     * 同时将 URL 添加到本地频道列表（source='' 标记为本地频道），
     * 方便用户后续在本地列表中找到并再次播放。
     * @param url M3U/M3U8/HLS/RTSP/RTMP 等协议 URL
     */
    fun playUrl(url: String) {
        if (url.isBlank()) {
            showOsd("请输入 URL")
            return
        }
        Log.i(TAG, "playUrl: $url")
        _channelDisplayInfo.value = ChannelDisplayInfo(
            name = url.substringAfterLast('/').takeIf { it.isNotEmpty() } ?: url,
            idx = -1, isLocal = true
        )
        // 添加到本地频道列表（如果尚未存在）
        viewModelScope.launch {
            val existing = _channels.value.find { it.url == url }
            if (existing == null) {
                val name = url.substringAfterLast('/').takeIf { it.isNotEmpty() } ?: url
                repository.addChannel(url, name, "本地").onSuccess { idx ->
                    loadChannels()
                    _currentIdx.value = idx
                }
            } else {
                _currentIdx.value = _channels.value.indexOfFirst { it.url == url }
            }
        }
        _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
        currentPlaybackUrl = url
        currentPlaybackName = url
        currentIsLocalFile = true
        refreshCurrentBookmarks()
        // MPV 支持全部协议，直接播放
        mpv.playFile(url)
        showOsd("网络流", url)
        closeAllPanels()
        _showHome.value = false  // 切换到播放器界面
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
            showControlsAutoHide()
        }
    }

    fun setSourceTab(tab: SourceTab) { _sourceTab.value = tab }

/** 设置当前选中的订阅源（空=全部） */
fun setSelectedSource(source: String) {
    _selectedSource.value = source
    _selectedGroup.value = ""  // 切换订阅源时重置分组
}

/** 加载频道缩略图路径 */
fun loadThumbnailPaths() {
    val urls = _channels.value.map { it.url }.filter { it.isNotEmpty() }
    if (urls.isEmpty()) return
    viewModelScope.launch {
        try {
            val result = repository.getThumbnailPaths(urls)
            result.onSuccess { paths ->
                _thumbnailPaths.value = paths
                Log.i(TAG, "loadThumbnailPaths: loaded ${paths.size} thumbnails")
            }
        } catch (e: Exception) {
            Log.w(TAG, "loadThumbnailPaths failed: ${e.message}")
        }
    }
}

/** 播放时自动截取缩略图（延迟几秒让画面加载，切台时自动取消上一个截图任务） */
fun captureChannelThumbnail() {
    val idx = _currentIdx.value
    if (idx < 0) return
    val channel = _channels.value.getOrNull(idx) ?: return
    val url = channel.url
    if (url.isEmpty()) return

    thumbnailJob?.cancel()
    thumbnailJob = viewModelScope.launch {
        delay(3000)
        if (!mpv.fileLoaded.value) return@launch
        try {
            val app = getApplication<Application>()
            val cacheFile = File(app.cacheDir, "thumb_${System.currentTimeMillis()}.png")
            mpv.screenshotToFile(cacheFile.absolutePath, "video")
            // 等待截图写入
            var retry = 0
            while (!cacheFile.exists() && retry < 10) {
                delay(200)
                retry++
            }
            if (cacheFile.exists()) {
                // 上传截图到服务器（服务器保存到 cache/thumbnails/ 目录）
                repository.captureThumbnail(url, cacheFile.absolutePath)
                cacheFile.delete()
                // 上传后从服务器刷新路径（服务器会返回正确的缩略图路径）
                val result = repository.getThumbnailPaths(listOf(url))
                result.onSuccess { paths ->
                    if (paths.isNotEmpty()) {
                        _thumbnailPaths.value = _thumbnailPaths.value.toMutableMap().apply {
                            putAll(paths)
                        }
                    }
                }
                Log.i(TAG, "captureChannelThumbnail: saved for $url")
            }
        } catch (e: Exception) {
            Log.w(TAG, "captureChannelThumbnail failed: ${e.message}")
        }
    }
}

/**
 * 批量生成缺失的频道缩略图。
 *
 * 由于 Android 上 Python libmpv 不可靠，改为：
 * 1. 先检查哪些频道缺缩略图
 * 2. 如果当前正在播放的频道也缺缩略图，触发前台截图（captureChannelThumbnail）
 * 3. 其他频道的缩略图会在用户播放时自动生成
 */
fun generateMissingThumbnails(channelsToGen: List<IptvChannel>) {
    val existingPaths = _thumbnailPaths.value
    val missing = channelsToGen.filter { ch ->
        ch.url.isNotEmpty() && existingPaths[ch.url]?.let { !java.io.File(it).exists() } ?: true
    }
    if (missing.isEmpty()) {
        Log.i(TAG, "generateMissingThumbnails: no missing thumbnails")
        return
    }

    Log.i(TAG, "generateMissingThumbnails: ${missing.size} channels need thumbnails")

    // 如果当前正在播放的频道也缺缩略图，触发截图
    val currentChannel = _channels.value.getOrNull(_currentIdx.value)
    if (currentChannel != null && missing.any { it.url == currentChannel.url }) {
        Log.i(TAG, "generateMissingThumbnails: capturing current channel thumbnail")
        captureChannelThumbnail()
    }

    // 提示用户：播放频道时会自动生成缩略图
    showOsd("缩略图", "还有 ${missing.size} 个频道待生成，播放时自动截图")
}

    // -----------------------------------------------------------------
    // 播放器设置（vo / hwdec）
    //
    // 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
    // 用户可手动切换 vo（gpu / mediacodec_embed），立即生效并持久化。
    // -----------------------------------------------------------------

    fun togglePlayerSettings() {
        _playerSettingsOpen.value = !_playerSettingsOpen.value
        if (!_playerSettingsOpen.value) showControlsAutoHide()
    }

    /**
     * 切换 video output（gpu / gpu-next / mediacodec_embed）。
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
        } else if (vo == "gpu" || vo == "gpu-next") {
            // 切换到 gpu / gpu-next 时，清除 fallback 标记，重新启用黑屏检测
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
     * 切换 hwdec（auto-copy / auto / mediacodec / no）。
     * 注意：hwdec 必须与 vo 匹配：
     * - vo=gpu / gpu-next → hwdec=auto-copy（拷贝，兼容好）/ auto（直接输出，4K HDR 流畅）/ no（软解）
     * - vo=mediacodec_embed → hwdec=mediacodec
     */
    fun setPlayerHwdec(hwdec: String) {
        userPrefs.setHwdec(hwdec)
        _currentHwdec.value = hwdec
        (_player.value as? MpvController)?.setVoAndHwdec(_currentVo.value, hwdec)
        showOsd("播放器设置", "hwdec=$hwdec")
    }

    /**
     * 设置 RTSP 传输协议（tcp/udp）。
     * 下次播放 RTSP 流时生效（运行时切换需重新加载当前文件）。
     */
    fun setRtspTransport(transport: String) {
        userPrefs.setRtspTransport(transport)
        _currentRtspTransport.value = transport
        showOsd("播放器设置", "RTSP 传输: $transport")
    }

    /**
     * 设置反交错（no/auto）。
     * deinterlace 是运行时可改属性，立即生效无需重新加载文件。
     * 仅对 MPV 模式生效。
     */
fun setDeinterlace(value: String) {
if (_currentDeinterlace.value == value) return
userPrefs.setDeinterlace(value)
_currentDeinterlace.value = value
(_player.value as? MpvController)?.setDeinterlace(value)
showOsd("播放器设置", "反交错: ${if (value == "auto") "自动" else "关闭"}")
}

/**
* 设置日志等级（debug/info/warn/error）。
* 与 PC 端 core/log_manager.py 对齐：
* - mpv 的 msg-level 属性控制播放器日志输出量
* - Python logging 等级控制 app.log 文件和 logcat 输出
*
* 运行时切换：mpv 的 msg-level 既是启动选项也是运行时属性，
* 通过 MPVLib.setPropertyString("msg-level", ...) 可实时切换，无需重建 mpv 实例。
* 首次创建 mpv 实例时由 MPVView.initialize 通过 setOptionString 设置初始值。
* Python 日志等级通过 Chaquopy callAttr 调用 set_log_level 实时切换。
*/
fun setLogLevel(level: String) {
if (_logLevel.value == level) return
userPrefs.setLogLevel(level)
_logLevel.value = level
// 运行时切换 MPV 日志等级（立即生效，无需重启）
mpvSingleton.setMpvLogLevel(level)
// 同步切换 Python 日志等级（影响 app.log 文件和 logcat 输出）
viewModelScope.launch {
    withContext(Dispatchers.IO) {
        repository.setLogLevel(level)
    }
}
val levelName = when (level) {
"debug" -> "调试"
"info" -> "信息"
"warn" -> "警告"
"error" -> "错误"
else -> level
}
showOsd("播放器设置", "日志等级: $levelName")
}

    /**
     * 切换硬件/软件解码。
     *
     * MPV：通过 hwdec 属性切换（auto-copy/no），同时更新 _currentHwdec 状态
     *
     * @param enabled true=硬件解码，false=软件解码
     */
    fun setHardwareDecode(enabled: Boolean) {
        val player = _player.value ?: return
        val success = try {
            player.setHardwareDecode(enabled)
        } catch (e: Exception) {
            Log.e(TAG, "setHardwareDecode failed", e)
            false
        }
        if (success) {
            // MPV 模式下同步更新 _currentHwdec 状态（UI 显示用）
            if (player is MpvController) {
                val newHwdec = if (enabled) {
                    when {
                        _currentVo.value == "mediacodec_embed" -> "mediacodec"
                        // 保留用户之前的选择：auto（4K HDR 直接输出）或 auto-copy
                        _currentHwdec.value == "auto" -> "auto"
                        else -> "auto-copy"
                    }
                } else "no"
                userPrefs.setHwdec(newHwdec)
                _currentHwdec.value = newHwdec
            }
            // 更新通用硬件解码状态（UI 自动响应）
            _hardwareDecode.value = enabled
            showOsd("播放器设置", if (enabled) "硬件解码" else "软件解码")
        } else {
            showOsd("播放器设置", "切换失败（当前 vo 不支持软解）")
        }
    }

    /** 切换 VO（gpu/gpu-next/mediacodec_embed），切换后重新加载当前频道 */
    fun applyVoChange(vo: String) {
        val player = _player.value ?: return
        if (player !is MpvController) return
        try {
            player.setVoAndHwdec(vo, userPrefs.getHwdec())
            _currentVo.value = vo
            userPrefs.setVo(vo)
            // 重新加载当前频道
            val url = currentPlaybackUrl
            if (url.isNotEmpty()) {
                player.playFile(url)
            }
            Log.i(TAG, "applyVoChange: vo=$vo, reloading $url")
        } catch (e: Exception) {
            Log.e(TAG, "applyVoChange failed", e)
            showOsd("播放器设置", "切换失败: ${e.message}")
        }
    }

    /** 查询当前播放器是否使用硬件解码 */
    fun isHardwareDecodeEnabled(): Boolean {
        return _player.value?.isHardwareDecodeEnabled() ?: true
    }

    /**
     * 重置播放器设置为默认值（vo=gpu, hwdec=auto-copy）。
     * 用户换设备或想重新探测黑屏时调用。
     */
    fun resetPlayerSettings() {
        userPrefs.resetPlayerSettings()
        _currentVo.value = userPrefs.getVo()
        _currentHwdec.value = userPrefs.getHwdec()
        _currentDeinterlace.value = userPrefs.getDeinterlace()
        _hdrMode.value = HdrMode.DISABLE
        // 恢复默认应立即生效
        (_player.value as? MpvController)?.setVoAndHwdec(_currentVo.value, _currentHwdec.value)
        (_player.value as? MpvController)?.setDeinterlace(_currentDeinterlace.value)
        // 已加载视频时立即应用重置后的 HDR 配置（disable → SDR 默认值）
        if (mpv.fileLoaded.value) {
            applyHdrOnFileLoaded()
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
            result.onSuccess {
                loadSources()
                // 实时更新频道列表，不需要重启 APP
                loadChannels()
            }
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
                _adminServerToken.value = info.token
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
                        _adminServerToken.value = info.token
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
     * 若用户在设置中关闭了自动关闭，则不启动倒计时。
     * 无论是否自动关闭，都启动虚拟遥控器命令轮询。
     */
    private fun startAdminCountdown() {
        // 启动虚拟遥控器命令轮询（无论是否自动关闭）
        startRemoteCommandPolling()
        // 检查用户是否启用了自动关闭
        if (!userPrefs.getAdminAutoStop()) {
            _adminCountdown.value = 0  // 0 表示不自动关闭
            return
        }
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

    /** 设置局域网管理是否自动关闭 */
    fun setAdminAutoStop(enabled: Boolean) {
        userPrefs.setAdminAutoStop(enabled)
        if (enabled) {
            // 开启自动关闭：如果服务器正在运行，启动倒计时
            if (_adminServerRunning.value && _adminCountdown.value == 0) {
                startAdminCountdown()
            }
        } else {
            // 关闭自动关闭：取消倒计时
            adminCountdownJob?.cancel()
            _adminCountdown.value = 0
            if (_adminServerRunning.value) {
                showOsd("局域网管理", "已关闭自动停止")
            }
        }
    }

    /** 获取局域网管理是否自动关闭 */
    fun getAdminAutoStop(): Boolean = userPrefs.getAdminAutoStop()

    /**
     * 启动虚拟遥控器命令轮询。
     * 每 100ms 轮询 Python 端的命令队列，有命令时执行对应操作。
     * 在 admin 服务器启动后调用，停止时取消轮询。
     */
    private fun startRemoteCommandPolling() {
        remotePollJob?.cancel()
        remotePollJob = viewModelScope.launch {
            while (isActive) {
                try {
                    val result = withContext(Dispatchers.IO) { repository.pollRemoteCommand() }
                    result.onSuccess { resp ->
                        resp.cmd?.let { handleRemoteCommand(it) }
                    }
                } catch (e: Exception) {
                    // 轮询失败不中断，继续下一轮
                }
                delay(200)  // 200ms 轮询（原 100ms 过于频繁，导致 Chaquopy GIL 争用）
            }
        }
        // 同时启动播放状态上报（供 admin 遥控器页面显示）
        startPlayerStatusReport()
    }

    /** 停止虚拟遥控器命令轮询 */
    private fun stopRemoteCommandPolling() {
        remotePollJob?.cancel()
        remotePollJob = null
        stopPlayerStatusReport()
    }

    /**
     * 定期上报播放状态到 admin 服务器（每 2 秒），供遥控器页面显示。
     * 文件加载后也会立即上报（延迟 1.5 秒等 mpv 属性稳定）。
     */
    private fun startPlayerStatusReport() {
        playerStatusJob?.cancel()
        playerStatusJob = viewModelScope.launch {
            // 监听 fileLoaded 事件，文件加载后延迟上报
            launch {
                mpv.fileLoaded.collect { loaded ->
                    if (loaded) {
                        _switchingFrame.value = null
                        consecutiveTimeoutCount = 0
                        delay(1500)
                        try { reportPlayerStatus() } catch (e: Exception) {}
                    }
                }
            }
            // 定期轮询上报
            while (isActive) {
                try {
                    reportPlayerStatus()
                } catch (e: Exception) {
                    // 上报失败不中断
                }
                delay(2000)
            }
        }
    }

    private fun stopPlayerStatusReport() {
        playerStatusJob?.cancel()
        playerStatusJob = null
    }

    /** 收集当前播放状态并上报到 Python 端 */
    private suspend fun reportPlayerStatus() {
        val channel = currentChannel.value
        val state = _playbackState.value
        val prog = getCurrentProgram()
        val mediaInfo = mpv.getMediaInfo()
        // HDR 信息：与 PC/Web 端 detect_hdr_type 逻辑统一对齐
        val hdrGamma = (mpv.getPropertyString("video-params/gamma") ?: "").lowercase()
        val hdrPrim = (mpv.getPropertyString("video-params/primaries") ?: "").lowercase()
        val hdrCm = (mpv.getPropertyString("video-params/colormatrix") ?: "").lowercase()
        val hdrVf = (mpv.getPropertyString("video-format") ?: "").lowercase()
        val hdrPeak = mpv.getPropertyDouble("video-params/sig-peak") ?: 0.0
        val hasDovi = hdrVf.contains("dovi") || hdrVf.contains("dolbyvision") ||
            hdrVf.contains("dvhe") || hdrVf.contains("dvh1") || hdrVf.contains("dav1")
        val isPq = hdrGamma.contains("pq") || hdrGamma.contains("smpte2084")
        val isHlg = hdrGamma.contains("hlg") || hdrGamma.contains("arib-std-b67")
        val isBt2020 = hdrCm.contains("bt.2020") || hdrCm.contains("bt2020") || hdrCm.contains("bt.2100") ||
            hdrPrim.contains("bt.2020") || hdrPrim.contains("bt2020") || hdrPrim.contains("bt.2100")
        val hdrInfo = when {
            hasDovi -> "DV (基础层)"
            isPq -> "HDR10"
            isHlg -> "HLG"
            isBt2020 && hdrPeak <= 1.0 -> "WCG"
            isBt2020 && hdrPeak > 1.0 -> "HLG"
            else -> ""
        }
        // 帧率：使用 container-fps（mpv-android 不支持 estimated-vfps）
        val fpsStr = mediaInfo["fps"] ?: ""
        val fps = when {
            fpsStr.isNotEmpty() && fpsStr != "0" && fpsStr != "0.0" -> fpsStr
            else -> {
                val cf = mpv.getPropertyString("container-fps") ?: ""
                val cfNum = cf.toDoubleOrNull() ?: 0.0
                if (cfNum > 0) String.format("%.1f", cfNum) else ""
            }
        }
        val statusJson = buildJsonObject {
            put("channel_name", JsonPrimitive(channel?.name ?: ""))
            put("channel_group", JsonPrimitive(channel?.group ?: ""))
            put("is_playing", JsonPrimitive(mpv.fileLoaded.value && !mpv.paused.value))
            // is_paused 需同时满足 fileLoaded（文件未加载时 paused 可能是初始值 true，
            // 此时显示"已暂停"会误导用户；应为"未播放"）
            put("is_paused", JsonPrimitive(mpv.fileLoaded.value && mpv.paused.value))
            put("player_type", JsonPrimitive(_playerType.value.name))
            put("hardware_decode", JsonPrimitive(_hardwareDecode.value))
            put("play_mode", JsonPrimitive(state.mode.name.lowercase()))
            put("volume", JsonPrimitive(mpv.volume.value))
            put("muted", JsonPrimitive(mpv.muted.value))
            put("current_program", JsonPrimitive(prog?.title ?: ""))
            put("video_res", JsonPrimitive(mediaInfo["videoRes"] ?: ""))
            put("video_codec", JsonPrimitive(mediaInfo["videoCodec"] ?: ""))
            put("audio_codec", JsonPrimitive(mediaInfo["audioCodec"] ?: ""))
            put("fps", JsonPrimitive(fps))
            put("bitrate", JsonPrimitive(mediaInfo["bitrate"] ?: ""))
            put("hdr", JsonPrimitive(hdrInfo))
        }
        withContext(Dispatchers.IO) { repository.setPlayerStatus(statusJson.toString()) }
    }

    /**
     * 处理虚拟遥控器命令。
     * 与 MainActivityCompose.onKeyDown 的 DPAD 按键处理逻辑对齐。
     */
    private fun handleRemoteCommand(cmd: String) {
        when (cmd) {
            "up" -> prevChannel()
            "down" -> nextChannel()
            "left" -> {
                // 左键：快退（与 MainActivityCompose DPAD_LEFT 对齐）
                val mode = playbackState.value.mode
                if (mode.isCatchup || currentChannel.value == null) {
                    mpv.seekRelative(-10.0)
                } else {
                    seekLiveRelative(-10.0)
                }
            }
            "right" -> {
                // 右键：快进（与 MainActivityCompose DPAD_RIGHT 对齐）
                val mode = playbackState.value.mode
                if (mode.isCatchup || currentChannel.value == null) {
                    mpv.seekRelative(10.0)
                } else {
                    seekLiveRelative(10.0)
                }
            }
            "ok" -> {
                if (!controlsVisible.value) {
                    showControlsAutoHide()
                } else {
                    mpv.togglePause()
                }
            }
            "back" -> {
                if (closeAnyPanel()) return
                if (playbackState.value.mode.isCatchupOrTimeshift) {
                    exitCatchup()
                } else if (!_showHome.value) {
                    // 竖屏播放器模式，返回首页（视频继续播放）
                    showHomeScreen()
                } else {
                    showExitConfirm()
                }
            }
            "menu" -> {
                if (uiMode.value.isTV) {
                    if (_landscapeSidebarVisible.value) {
                        _landscapeSidebarVisible.value = false
                    } else {
                        _landscapeSidebarVisible.value = true
                    }
                } else toggleMenuPanel()
            }
            "play" -> mpv.setPause(false)
            "pause" -> mpv.setPause(true)
            "play_pause" -> mpv.togglePause()
            "stop" -> {
                if (playbackState.value.mode.isCatchupOrTimeshift) exitCatchup() else stopPlay()
            }
            "mute" -> mpv.toggleMute()
            "vol_up" -> mpv.adjustVolume(5)
            "vol_down" -> mpv.adjustVolume(-5)
            "seek_forward" -> mpv.seekRelative(30.0)
            "seek_backward" -> mpv.seekRelative(-30.0)
            "osd" -> toggleControlsPinned()
            "prev_channel" -> prevChannel()
            "next_channel" -> nextChannel()
            // 数字键：缓冲输入，1.5 秒无后续输入后切换到对应索引频道
            "num_0", "num_1", "num_2", "num_3", "num_4",
            "num_5", "num_6", "num_7", "num_8", "num_9" -> {
                val digit = cmd.removePrefix("num_").toIntOrNull() ?: return
                _channelInputBuffer = (_channelInputBuffer ?: "") + digit.toString()
                showOsd("频道: " + _channelInputBuffer!!)
                _channelInputJob?.cancel()
                _channelInputJob = viewModelScope.launch {
                    kotlinx.coroutines.delay(1500)
                    val num = _channelInputBuffer?.toIntOrNull()
                    _channelInputBuffer = null
                    if (num != null && num > 0) {
                        playChannel(num - 1)
                    }
                }
            }
            // 音量绝对值设置（供 Web 遥控器页面音量滑块使用）
            // 命令格式：set_volume:50
            else -> if (cmd.startsWith("set_volume:")) {
                val vol = cmd.removePrefix("set_volume:").toIntOrNull()
                if (vol != null) {
                    mpv.setVolume(vol)
                    Log.i(TAG, "Remote set volume: $vol")
                }
            } else if (cmd.startsWith("set_mute:")) {
                val mute = cmd.removePrefix("set_mute:").toBooleanStrictOrNull()
                if (mute != null) {
                    mpv.setMute(mute)
                    Log.i(TAG, "Remote set mute: $mute")
                }
            } else if (cmd.startsWith("play_url:")) {
                // 直接播放指定 URL（用于测试）
                val url = cmd.removePrefix("play_url:")
                if (url.isNotEmpty()) {
                    Log.i(TAG, "Remote play_url: $url")
                    _currentIdx.value = -1
                    _playbackState.value = PlaybackState(mode = PlayMode.LIVE)
                    currentPlaybackUrl = url
                    currentPlaybackName = "TEST: $url"
                    mpv.playFile(url)
                    startTimeoutSwitchSource(-1)
                    showOsd("测试播放", url)
                }
            } else {
                Log.w(TAG, "未知遥控命令: $cmd")
            }
        }
    }

    fun stopAdminServer() {
        adminCountdownJob?.cancel()
        _adminCountdown.value = 0
        // 停止虚拟遥控器命令轮询
        stopRemoteCommandPolling()
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
                _adminServerToken.value = info.token
                _adminServerRunning.value = info.running
            }
        }
    }

    /** 设置自定义访问令牌（仅在服务器未运行时生效） */
    fun setAdminToken(token: String) {
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) { repository.setAdminToken(token) }
            result.onSuccess { resp ->
                _adminServerToken.value = resp.token
                if (resp.token.isNotEmpty()) {
                    showOsd("访问令牌已设置", resp.token)
                } else {
                    showOsd("访问令牌", "已清除，启动时自动生成")
                }
            }.onFailure {
                showOsd("设置失败", it.message ?: "")
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
        // 关闭 FCC 持久化 UDP socket
        try { FccHelper.closeUdpSocket() } catch (_: Throwable) {}
        // 清理主播放器（MPV 需要 stop + detach，避免 native 资源泄漏）
        // Activity.onDestroy 已先调用一次，这里兜底确保释放
        try {
            val p = _player.value
            p.stop()
            p.detach()
        } catch (_: Throwable) {}
        // 清理副画面播放器（ExoPlayer 实例）
        try {
            releaseAllSubPlayers()
        } catch (_: Throwable) {}
        // 清理 APK 下载资源（避免 receiver 泄漏）
        try {
            apkProgressJob?.cancel()
            apkProgressJob = null
            if (apkDownloadId > 0) {
                val app = getApplication<Application>()
                val dm = app.getSystemService(Context.DOWNLOAD_SERVICE) as? DownloadManager
                dm?.remove(apkDownloadId)
                unregisterApkDownloadReceiver(app)
            }
        } catch (_: Throwable) {}
        // 退出前保存最后一次位置
        try { autoSaveResume() } catch (_: Exception) {}
        // 停止局域网管理服务器（避免退出后端口/socket 残留）
        // viewModelScope 已取消，用后台线程同步调用 Python 端 stop_admin_server
        try {
            adminCountdownJob?.cancel()
            stopRemoteCommandPolling()
            // 使用后台线程 + runBlocking + 超时，避免阻塞主线程
            Thread {
                try {
                    runBlocking {
                        withTimeoutOrNull(3000L) {
                            repository.stopAdminServer()
                        }
                    }
                } catch (_: Throwable) {}
            }.start()
        } catch (_: Throwable) {}
    }

    // -----------------------------------------------------------------
    // 工具函数
    // -----------------------------------------------------------------

    /** 类似 Kotlin 的 takeIf 但用于 if-else 表达式 */
    private fun <T> T.ifElse(other: T, predicate: () -> Boolean): T =
        if (predicate()) this else other

    companion object {
        private const val TAG = "AppViewModel"
        private const val GITHUB_LATEST_API = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"

        fun factory(app: Application): ViewModelProvider.AndroidViewModelFactory =
            object : ViewModelProvider.AndroidViewModelFactory(app) {}
    }
}
