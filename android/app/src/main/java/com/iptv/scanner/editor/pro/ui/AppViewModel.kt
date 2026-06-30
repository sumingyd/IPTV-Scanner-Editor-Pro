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
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.mpv.MpvController
import com.iptv.scanner.editor.pro.player.CatchupHelper
import com.iptv.scanner.editor.pro.player.CatchupProgram
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.PlaybackState
import com.iptv.scanner.editor.pro.player.ProgressHelper
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
    val mpv = MpvController.getInstance()
    private val userPrefs = UserPrefs.getInstance().also { it.init(app) }

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

    /** 加载用户偏好（收藏/历史/队列） */
    private fun loadUserPrefs() {
        _favorites.value = userPrefs.getFavorites()
        _history.value = userPrefs.getHistory()
        _queue.value = userPrefs.getQueue()
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

    /** 上一频道 */
    fun prevChannel() {
        val cur = _currentIdx.value
        if (cur < 0) return
        val next = if (cur > 0) cur - 1 else _channels.value.lastIndex
        if (next >= 0 && next < _channels.value.size) playChannel(next)
    }

    /** 下一频道 */
    fun nextChannel() {
        val cur = _currentIdx.value
        if (cur < 0) return
        val next = if (cur < _channels.value.lastIndex) cur + 1 else 0
        if (next in _channels.value.indices) playChannel(next)
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
        val channel = currentChannel.value ?: return

        when (state.mode) {
            PlayMode.CATCHUP -> {
                // 回看模式：基于 mpv timePos 直接 seek
                val program = state.catchupProgram ?: return
                val targetSec = (percent / 100f * program.durationSec).toDouble()
                mpv.seekAbsolute(targetSec)
            }
            PlayMode.TIMESHIFT, PlayMode.LIVE -> {
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
    fun toggleControls() { _controlsVisible.value = !_controlsVisible.value }

    fun closeAllPanels() {
        _channelsPanelOpen.value = false
        _epgPanelOpen.value = false
        _menuPanelOpen.value = false
        _sourceManagerOpen.value = false
        _playerSettingsOpen.value = false
        // 关闭所有面板后自动显示控制层
        _controlsVisible.value = true
    }

    /**
     * 关闭任意打开的面板。返回 true 表示关闭了面板（用于 BACK 键消费判断）。
     * 与 PC 端 closeFuncPanel 对齐：有关闭任何面板时返回 true，无面板时返回 false。
     */
    fun closeAnyPanel(): Boolean {
        val hadOpen = _channelsPanelOpen.value || _epgPanelOpen.value ||
                _menuPanelOpen.value || _sourceManagerOpen.value ||
                _playerSettingsOpen.value
        _channelsPanelOpen.value = false
        _epgPanelOpen.value = false
        _menuPanelOpen.value = false
        _sourceManagerOpen.value = false
        _playerSettingsOpen.value = false
        // 关闭面板后自动显示控制层
        if (hadOpen) _controlsVisible.value = true
        return hadOpen
    }

    fun showChannelsPanel() { _channelsPanelOpen.value = true }
    fun showEpgPanel() { _epgPanelOpen.value = true }
    fun showMenuPanel() { _menuPanelOpen.value = true }

    fun hideControls() { _controlsVisible.value = false }
    fun showControls() { _controlsVisible.value = true }

    // -----------------------------------------------------------------
    // 订阅源管理（主菜单 → 文件 → 订阅源管理）
    // -----------------------------------------------------------------

    fun toggleSourceManager() {
        _sourceManagerOpen.value = !_sourceManagerOpen.value
        if (_sourceManagerOpen.value) {
            loadSources()
            loadEpgSources()
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
        val hasFile = mpv.setVoAndHwdec(vo, hwdec)
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
        mpv.setVoAndHwdec(_currentVo.value, hwdec)
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
        mpv.setVoAndHwdec(_currentVo.value, _currentHwdec.value)
        showOsd("播放器设置", "已重置为默认值（重启后生效）")
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
    // ViewModel 生命周期
    // -----------------------------------------------------------------

    override fun onCleared() {
        super.onCleared()
        statusPollJob?.cancel()
        osdHideJob?.cancel()
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
