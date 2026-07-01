package com.iptv.scanner.editor.pro.player

import kotlinx.coroutines.flow.StateFlow

/**
 * 播放器类型枚举。
 *
 * - [MPV]：mpv (libmpv)，通过 JNI 调用，功能最完整（EQ/AB循环/逐帧/章节/截图/HDR等）
 * - [EXO]：ExoPlayer (androidx.media3)，Google 官方播放器，HLS/DASH/SmoothStreaming 支持好
 * - [VLC]：libVLC (VLC for Android)，协议支持广（RTSP/RTMP/UDP/HTTP），解码器全
 * - [IJK]：IJKPlayer (Bilibili)，基于 FFmpeg，轻量灵活
 */
enum class PlayerType(val displayName: String, val description: String) {
    MPV("mpv", "功能最完整（EQ/AB循环/逐帧/截图/HDR）"),
    EXO("ExoPlayer", "Google 官方，HLS/DASH 支持好"),
    VLC("VLC", "协议支持广（RTSP/RTMP/UDP）"),
    IJK("IJKPlayer", "基于 FFmpeg，轻量灵活")
}

/**
 * 播放器能力声明。
 *
 * UI 层根据 [Player.capabilities] 决定是否显示高级功能面板。
 * MPV 全部为 true；ExoPlayer/VLC/IJK 部分为 true。
 */
data class PlayerCapabilities(
    val supportsBrightness: Boolean = false,
    val supportsContrast: Boolean = false,
    val supportsSaturation: Boolean = false,
    val supportsHue: Boolean = false,
    val supportsGamma: Boolean = false,
    val supportsVideoRotate: Boolean = false,
    val supportsVideoFlip: Boolean = false,
    val supportsVideoCrop: Boolean = false,
    val supportsAudioDelay: Boolean = false,
    val supportsAudioEq: Boolean = false,
    val supportsSubDelay: Boolean = false,
    val supportsSubScale: Boolean = false,
    val supportsSubPos: Boolean = false,
    val supportsAbLoop: Boolean = false,
    val supportsLoopFile: Boolean = false,
    val supportsFrameStep: Boolean = false,
    val supportsChapters: Boolean = false,
    val supportsScreenshot: Boolean = false,
    val supportsOsd: Boolean = false,
    val supportsAddSubtitleFile: Boolean = false,
    val supportsSpeedControl: Boolean = true,
    val supportsTrackList: Boolean = false
) {
    /** 是否支持任何画面调整（亮度/对比度/饱和度/色调/Gamma） */
    val supportsVideoEq: Boolean
        get() = supportsBrightness || supportsContrast || supportsSaturation ||
                supportsHue || supportsGamma
}

/**
 * 播放器抽象接口。
 *
 * 统一 MPV / ExoPlayer / VLC / IJK 四种播放器的 API。
 *
 * 设计原则：
 * 1. 通用状态用 [StateFlow] 暴露，与 MpvController 现有 StateFlow 对齐
 * 2. 核心播放控制方法是抽象的（每个实现必须提供）
 * 3. 高级功能有默认实现（返回 false / no-op），UI 通过 [capabilities] 判断是否可用
 * 4. mpv 专属的 `getPropertyX` / `command` 有默认实现（返回 null / no-op），
 *    UI 代码无需修改即可在非 MPV 播放器上运行（属性显示为 N/A）
 * 5. 切换播放器时通过 [savePlaybackState] / [restorePlaybackState] 保持播放连续性
 *
 * @see MpvController 完整实现
 * @see ExoPlayerController ExoPlayer 实现
 * @see VlcController VLC 实现
 * @see IjkController IJK 实现
 */
interface Player {

    // -----------------------------------------------------------------
    // 可观察状态（与 MpvController StateFlow 对齐）
    // -----------------------------------------------------------------

    /** 当前播放位置（秒） */
    val timePos: StateFlow<Double>

    /** 总时长（秒），直播流为 0 或无穷 */
    val duration: StateFlow<Double>

    /** 是否暂停 */
    val paused: StateFlow<Boolean>

    /** 音量（0-130，mpv 标准；其他播放器映射到 0-100） */
    val volume: StateFlow<Int>

    /** 是否静音 */
    val muted: StateFlow<Boolean>

    /** 媒体标题 */
    val mediaTitle: StateFlow<String>

    /** 轨道列表 JSON（mpv track-list 格式；其他播放器转换为兼容格式） */
    val trackListJson: StateFlow<String>

    /** 是否播放结束（EOF） */
    val eofReached: StateFlow<Boolean>

    /** 文件是否已加载 */
    val fileLoaded: StateFlow<Boolean>

    /** 视频宽度（px） */
    val videoWidth: StateFlow<Int>

    /** 视频高度（px） */
    val videoHeight: StateFlow<Int>

    /** 播放速度 */
    val speed: StateFlow<Double>

    /** 当前章节（-1 表示无章节） */
    val currentChapter: StateFlow<Int>

    /** 章节总数（0 表示无章节） */
    val chapterCount: StateFlow<Int>

    // -----------------------------------------------------------------
    // 能力声明
    // -----------------------------------------------------------------

    /** 该播放器支持的功能，UI 层据此决定是否显示高级功能面板 */
    val capabilities: PlayerCapabilities

    /** 播放器类型 */
    val playerType: PlayerType

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------

    /**
     * 绑定 View（MPVView / ExoPlayerView / VlcVideoView / IjkVideoView）。
     * @param view 平台特定的 View 实例
     */
    fun attachView(view: Any)

    /** 解绑 View，释放资源（移除监听器、释放 native 引用等） */
    fun detach()

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------

    /** 播放文件或 URL（HLS/RTSP/RTMP/HTTP/content:// 等） */
    fun playFile(url: String)

    /** 停止播放 */
    fun stop()

    /** 切换暂停/播放 */
    fun togglePause()

    /** 设置暂停状态 */
    fun setPause(p: Boolean)

    /** 跳转到指定位置（秒） */
    fun seekTo(seconds: Double)

    /** 相对跳转（正数前进，负数后退） */
    fun seekRelative(seconds: Double)

    /** 绝对跳转（与 seekTo 类似，mpv 用 absolute seek flags） */
    fun seekAbsolute(seconds: Double)

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------

    /** 设置音量（0-130） */
    fun setVolume(v: Int)

    /** 增减音量 */
    fun adjustVolume(delta: Int)

    /** 切换静音 */
    fun toggleMute()

    /** 设置静音状态 */
    fun setMute(m: Boolean)

    /** 设置播放速度 */
    fun setSpeed(s: Double)

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------

    /** 循环切换音轨 */
    fun cycleAudio()

    /** 循环切换字幕轨 */
    fun cycleSub()

    /** 设置音轨 ID */
    fun setAudioTrack(id: Int)

    /** 设置字幕轨 ID */
    fun setSubTrack(id: Int)

    /** 加载外挂字幕文件（本地路径） */
    fun addSubtitleFile(path: String)

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------

    /** 设置字幕显示开关 */
    fun setSubVisibility(v: Boolean)

    /** 切换字幕显示 */
    fun toggleSubVisibility()

    /** 设置字幕延迟（秒，正数延后，负数提前） */
    fun setSubDelay(delaySec: Double)

    /** 调整字幕延迟（增量） */
    fun adjustSubDelay(delta: Double)

    /** 设置字幕缩放（1.0 = 原始大小） */
    fun setSubScale(scale: Double)

    /** 设置字幕位置（0-100，距底部百分比） */
    fun setSubPos(pos: Int)

    // -----------------------------------------------------------------
    // 画面调整（高级功能，默认不支持）
    // -----------------------------------------------------------------

    /** 设置亮度（-100~100），返回是否成功 */
    fun setBrightness(v: Int): Boolean = false

    /** 设置对比度（-100~100） */
    fun setContrast(v: Int): Boolean = false

    /** 设置饱和度（-100~100） */
    fun setSaturation(v: Int): Boolean = false

    /** 设置色调（-100~100） */
    fun setHue(v: Int): Boolean = false

    /** 设置 Gamma（-100~100） */
    fun setGamma(v: Int): Boolean = false

    /** 设置视频旋转角度（0/90/180/270） */
    fun setVideoRotate(degree: Int): Boolean = false

    /** 设置视频翻转（""/"horizontal"/"vertical"/"both"） */
    fun setVideoFlip(mode: String): Boolean = false

    /** 设置视频裁剪 */
    fun setVideoCrop(x: Int, y: Int, w: Int, h: Int): Boolean = false

    /** 清除视频裁剪 */
    fun clearVideoCrop() {}

    /** 清除所有视频滤镜 */
    fun clearAllVideoFilters() {}

    /** 设置 3D 立体模式（mono/sbs/sbs2/ab/ab2），与 PC 端 set_video_stereo_mode 对齐 */
    fun setVideoStereoMode(mode: String): Boolean = false

    /** 获取当前 3D 立体模式，与 PC 端 get_video_stereo_mode 对齐 */
    fun getVideoStereoMode(): String? = null

    /**
     * 设置 360° 视角（panorama 滤镜），与 PC 端 set_360_view 对齐。
     * @param yaw 偏航（-180~180）
     * @param pitch 俯仰（-90~90）
     * @param roll 滚转（-180~180）
     * @param projection 投影方式（flat/equirect/cubemap）
     */
    fun set360View(yaw: Double, pitch: Double, roll: Double, projection: String): Boolean = false

    /** 清除 360° 滤镜，与 PC 端 clear_360_filter 对齐 */
    fun clear360Filter() {}

    // -----------------------------------------------------------------
    // 音频调整（高级功能，默认不支持）
    // -----------------------------------------------------------------

    /** 设置音频延迟（秒） */
    fun setAudioDelay(delaySec: Double): Boolean = false

    /** 调整音频延迟（增量） */
    fun adjustAudioDelay(delta: Double): Boolean = false

    /** 设置 10 段均衡器（gains 列表，-12~12 dB） */
    fun setAudioEq(gains: List<Float>): Boolean = false

    /** 重置均衡器 */
    fun resetAudioEq(): Boolean = false

    /** 设置音频音调（0.0~2.0，1.0=正常，变调不变速），与 PC 端 set_audio_pitch 对齐 */
    fun setAudioPitch(pitch: Double): Boolean = false

    // -----------------------------------------------------------------
    // 截图（高级功能，默认不支持）
    // -----------------------------------------------------------------

    /**
     * 截图到文件。
     * @param path 文件路径
     * @param mode "video"（仅画面）/ "subtitles"（含字幕）/ "window"（含 OSD）
     * @return 是否成功
     */
    fun screenshotToFile(path: String, mode: String = "video"): Boolean = false

    // -----------------------------------------------------------------
    // A/B 循环 / 逐帧 / 章节（高级功能，默认不支持）
    // -----------------------------------------------------------------

    /** 设置 AB 循环 A 点（当前位置） */
    fun setAbLoopA(): Boolean = false

    /** 设置 AB 循环 B 点（当前位置） */
    fun setAbLoopB(): Boolean = false

    /** 清除 AB 循环 */
    fun clearAbLoop() {}

    /** 设置单文件循环模式（"no"/"inf"/"yes"） */
    fun setLoopFile(mode: String): Boolean = false

    /** 设置播放列表循环模式（"no"/"inf"/"force"） */
    fun setLoopPlaylist(mode: String): Boolean = false

    /** 逐帧前进 */
    fun frameStep(): Boolean = false

    /** 逐帧后退 */
    fun frameBackStep(): Boolean = false

    /** 设置章节 */
    fun setChapter(idx: Int): Boolean = false

    /** 下一章 */
    fun chapterNext(): Boolean = false

    /** 上一章 */
    fun chapterPrev(): Boolean = false

    // -----------------------------------------------------------------
    // OSD（默认 no-op）
    // -----------------------------------------------------------------

    /** 显示 OSD 文本 */
    fun showOsd(text: String, durationMs: Int = 3000) {}

    // -----------------------------------------------------------------
    // 通用属性读写（mpv 专属，其他播放器默认返回 null / no-op）
    // -----------------------------------------------------------------

    /** 读取字符串属性（mpv 专属，其他播放器返回 null） */
    fun getPropertyString(name: String): String? = null

    /** 读取整数属性 */
    fun getPropertyInt(name: String): Int? = null

    /** 读取浮点属性 */
    fun getPropertyDouble(name: String): Double? = null

    /** 读取布尔属性 */
    fun getPropertyBoolean(name: String): Boolean? = null

    /** 设置字符串属性 */
    fun setPropertyString(name: String, value: String) {}

    /** 设置整数属性 */
    fun setPropertyInt(name: String, value: Int) {}

    /** 设置浮点属性 */
    fun setPropertyDouble(name: String, value: Double) {}

    /** 设置布尔属性 */
    fun setPropertyBoolean(name: String, value: Boolean) {}

    /** 执行原始命令（mpv 专属） */
    fun command(args: Array<String>) {}

    // -----------------------------------------------------------------
    // 媒体信息（通用）
    // -----------------------------------------------------------------

    /**
     * 获取媒体信息（codec/bitrate/fps/cacheDuration 等）。
     * 各播放器从各自 API 获取，返回统一的 Map。
     * UI 层的 MediaBadgesRow 通过 key 读取，缺失的 key 显示 N/A。
     */
    fun getMediaInfo(): Map<String, String?> = emptyMap()

    // -----------------------------------------------------------------
    // 播放状态保存/恢复（用于切换播放器时保持连续性）
    // -----------------------------------------------------------------

    /** 保存当前播放状态（url + timePos），无文件时返回 null */
    fun savePlaybackState(): Pair<String, Double>? = null

    /** 恢复播放状态（加载 url 并 seek 到 timePosSec） */
    fun restorePlaybackState(url: String, timePosSec: Double) {}
}
