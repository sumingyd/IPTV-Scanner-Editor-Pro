package com.iptv.scanner.editor.pro.mpv

import android.content.Context
import android.graphics.PixelFormat
import android.util.AttributeSet
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView
import `is`.xyz.mpv.MPVLib

/**
 * 基于 SurfaceView 的 MPV 视频渲染视图。
 *
 * 为什么不用 TextureView？
 * - mpv 的 vo=gpu 在 Android 用 EGL 直接绑定 ANativeWindow 进行渲染
 * - SurfaceView 的 Surface 内部由 ANativeWindow 支撑，可以直接被 mpv vo=gpu 渲染
 * - TextureView 的 Surface 由 SurfaceTexture 支撑，渲染内容进入 BufferQueue 后需要外部
 *   消费 GL_TEXTURE_EXTERNAL_OES 纹理才能显示，而 mpv vo=gpu 不会消费 SurfaceTexture
 * - 实测：TextureView + mpv vo=gpu 表现为黑屏（有声音无画面）
 *
 * SurfaceView 默认 Z-order 在普通 View 之后，会通过 View 树里的"洞"显示画面。
 * 因此 Compose 容器不能画不透明 background，否则会遮挡 SurfaceView 画面。
 * 这是 mpv-android 官方实现方式（参考 is.xyz.mpv.BaseMPVView）。
 */
class MPVView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : SurfaceView(context, attrs), SurfaceHolder.Callback {

    /**
     * mpv 渲染配置。与 PC 端 services/mpv_player_service.py 对齐。
     *
     * 设计原则：
     * - 不在代码里硬编码任何针对特定 GPU/CPU 的 workaround
     * - vo/hwdec 由调用方传入，默认值与 PC 端一致（vo=gpu, hwdec=auto-copy）
     * - 若某设备 vo=gpu 出现兼容性问题（如 Mali-G76 黑屏），调用方可传入
     *   vo=mediacodec_embed + hwdec=mediacodec 作为 fallback
     * - 后续集成 IJK/Exo/VLC 时，本类可作为 Player 抽象层的一个实现
     *
     * @param vo video output，默认 "gpu"（与 PC 端一致）
     *        - "gpu"：基于 EGL 的 GPU 渲染，支持 shader/HDR/OSD，兼容大多数 GPU
     *        - "mediacodec_embed"：MediaCodec 直接渲染到 Surface，绕过 EGL
     *          （GPU EGL 兼容性问题时的 fallback，但不支持 OSD/HDR）
     * @param hwdec 硬件解码，默认 "auto-copy"（自动选择 + 拷贝到 CPU 内存）
     *        - "auto-copy"：自动选择硬件解码器，拷贝到 CPU 内存（兼容性好）
     *        - "mediacodec"：MediaCodec 硬件解码（需配合 vo=mediacodec_embed）
     *        - "no"：纯软件解码（兼容性最好，但耗电）
     */
    @JvmOverloads
    fun initialize(
        configDir: String,
        cacheDir: String,
        vo: String = DEFAULT_VO,
        hwdec: String = DEFAULT_HWDEC
    ) {
        voInUse = vo
        // 切换播放器（MPV → EXO/IJK/VLC → MPV）时，Compose 的 onRelease 是异步的，
        // 上次 MPVView.destroy() 可能还未执行，native mpv 实例仍存活。
        // 此时 MPVLib.create() 会在已存在的实例上调用，导致 native 崩溃（SIGSEGV）。
        // 用 nativeInstanceAlive 标志位检测残留实例，先 destroy 再 create。
        if (nativeInstanceAlive) {
            Log.w(TAG, "initialize: native mpv instance still alive, destroying first")
            try {
                MPVLib.destroy()
            } catch (e: Throwable) {
                Log.w(TAG, "initialize: destroy previous instance failed: ${e.message}")
            }
            nativeInstanceAlive = false
        }
        MPVLib.create(context)

        MPVLib.setOptionString("config", "yes")
        MPVLib.setOptionString("config-dir", configDir)
        for (opt in arrayOf("gpu-shader-cache-dir", "icc-cache-dir"))
            MPVLib.setOptionString(opt, cacheDir)

        /* VO/HWDEC：与 PC 端 services/mpv_player_service.py 对齐。
         * 默认 vo=gpu + hwdec=auto-copy，兼容大多数设备。
         * 调用方可传入不同的 vo/hwdec 以适配特定设备。 */
        MPVLib.setOptionString("vo", vo)
        MPVLib.setOptionString("hwdec", hwdec)
        MPVLib.setOptionString("keep-open", "yes")

        /* 视频比例保持（关键：解决竖屏下视频被拉伸铺满的问题）：
         * - keepaspect=yes：视频在 surface 内部保持原始比例（默认值，显式设置确保）
         * - keepaspect-window=no：不让窗口管理器试图保持视频比例
         *   原因：Android 上 SurfaceView 的 surface 尺寸由 layout 决定（fillMaxSize=全屏），
         *   keepaspect-window=yes（默认）会让 mpv 请求保持比例的窗口，与全屏 surface 冲突，
         *   导致视频被拉伸铺满整个竖屏（1440x2984），破坏 16:9 比例。
         *   设为 no 后，surface 用全屏尺寸，mpv 在 surface 内部按 keepaspect 计算显示区域，
         *   视频会居中显示并保持比例（上下黑边）。
         *   PC 端桌面版 mpv 不需要此设置（窗口管理器正确处理比例）。 */
        MPVLib.setOptionString("keepaspect", "yes")
        MPVLib.setOptionString("keepaspect-window", "no")

        /* FBO 格式：部分 GPU（如 Mali-G76）不支持 rgba16f 浮点 FBO，
         * 导致 vo=gpu 黑屏（有声音无画面）。使用 rgba8 整数格式确保兼容性。 */
        MPVLib.setOptionString("fbo-format", "rgba8")

        /* 性能与音画同步（与 PC 端 _ensure_mpv_initialized 行 339-363 对齐，但 framedrop 调整）：
         * - framedrop=all：解码慢或输出慢时都丢帧
         *   PC 端用 framedrop=vo（只在输出慢时丢帧），但 Android 模拟器/低端设备解码慢，
         *   仅 vo 模式会导致解码队列积压、视频帧延迟显示（音频比画面快）。
         *   改用 all 模式在解码阶段就丢帧，减少积压延迟。性能充足时不会丢帧，无害。
         * - video-sync=audio：以音频时钟为同步基准，视频帧迟到时丢帧而非阻塞
         * - cache-pause-initial=no：初始缓存阶段不暂停，避免直播流启动卡顿 */
        MPVLib.setOptionString("framedrop", "all")
        MPVLib.setOptionString("video-sync", "audio")
        MPVLib.setOptionString("cache-pause-initial", "no")

        /* 音画同步增强：
         * 注意：不启用 audio-stream-silence（PC 端没有），该参数会让音频提前播放导致音画不同步
         * 注意：不启用 video-latency-hacks（PC 端也没有），该参数可能导致 PTS 处理偏差 */

        /* 缓冲与预读：与 PC 端 _load_playback_settings 默认值完全对齐
         * PC 端默认：cache-secs=1.0, demuxer-max-bytes=16MiB, demuxer-max-back-bytes=4MiB
         * 之前 Android 端设为 readahead=10s/max=50MiB/back=25MiB，导致视频解码队列过长产生 600ms 延迟
         * 现在完全对齐 PC 端的小缓冲策略，保持低延迟 */
        MPVLib.setOptionString("demuxer-max-bytes", "16MiB")
        MPVLib.setOptionString("demuxer-max-back-bytes", "4MiB")
        MPVLib.setOptionString("demuxer-readahead-secs", "1")
        MPVLib.setOptionString("demuxer-seekable-cache", "yes")
        MPVLib.setOptionString("force-seekable", "yes")

        /* 网络/直播优化（与 PC 端对齐，但 source-timeout 更宽松避免移动网络抖动） */
        MPVLib.setOptionString("network-timeout", "30")
        MPVLib.setOptionString("source-timeout", "10")
        MPVLib.setOptionString("stream-open-timeout", "30")

        /* TLS 兼容性修复：
         * mpv-android 用 mbedtls 作为 TLS 后端，部分 HTTPS 服务器（如非标准端口 8895 的 IPTV 源）
         * 会 handshake 失败（mbedtls_ssl_handshake returned -0x4e = FATAL_ALERT_MESSAGE）。
         * PC 端用 OpenSSL 无此问题。
         * 临时方案：禁用 TLS 证书验证（verify=0），通过 stream-lavf-o 传给 ffmpeg。
         * 风险：中间人攻击可替换流内容。对 IPTV 直播流可接受，敏感内容不适用。
         * 根本方案：CI 工作流切换到 OpenSSL 版本的 mpv-android（或自行编译）。 */
        MPVLib.setOptionString("stream-lavf-o", "verify=0")
        MPVLib.setOptionString("tls-verify", "no")

        /* 移动端解码优化：动态获取 CPU 核数（与 PC 端 _ensure_mpv_initialized 行 361-363 一致）
         * PC 端：threads = max(2, cpu_count // 2)
         * 之前 Android 端固定为 2，在多核设备上解码线程不足导致解码队列积压 */
        val cpuCount = Runtime.getRuntime().availableProcessors()
        val threads = maxOf(2, cpuCount / 2)
        MPVLib.setOptionString("vd-lavc-threads", threads.toString())

        /* 注意：不启用 vd-queue-enable/ad-queue-enable
         * 这两个参数会让解码器队列化数据，增加延迟导致音画不同步
         * PC 端也没有这两个参数 */

        MPVLib.init()

        MPVLib.setOptionString("force-window", "no")
        MPVLib.setOptionString("idle", "once")

        // native mpv 实例已创建并初始化，标记为存活（供下次 initialize 检测残留实例）
        nativeInstanceAlive = true

        // 显式设置 SurfaceHolder 像素格式为 RGBA_8888。
        // 与 mpv-android 官方 BaseMPVView 对齐（其 init 块中调用 holder.setFormat(PixelFormat.RGBA_8888)）。
        // SurfaceView 默认格式是 OPAQUE，与 mpv vo=gpu 通过 eglChooseConfig 请求的
        // RGBA8888 EGL config 不匹配，可能导致 eglSwapBuffers 提交的 buffer 被错误解析。
        // 这是通用配置，不是针对特定 GPU 的 workaround。
        holder.setFormat(PixelFormat.RGBA_8888)

        // 不使用 setZOrderOnTop(true)：让 SurfaceView 用默认 Z-order（在普通 View 之下）。
        // 这样 Compose 控制层可以显示在 SurfaceView 之上。
        // 前提：Compose 容器不能有不透明 background，否则会遮挡视频。
        // MainPlayerScreen 的根 Box 没有设置 background，IptvTheme 也没有用 Surface 包装，
        // 所以 Compose 层是透明的，SurfaceView 的视频可以透过 Compose 层可见。
        // 之前用 setZOrderOnTop(true) 会导致 SurfaceView 遮挡所有 Compose 控制层。
        holder.addCallback(this)
        observeProperties()
    }

    fun destroy() {
        // 先移除回调，防止 surfaceDestroyed 在 MPVLib.destroy() 之后触发
        // 导致 use-after-destroy（MPVLib.setPropertyString/detachSurface）
        holder.removeCallback(this)
        // 防止 double-destroy：onRelease 可能与 MpvController.detach 或
        // Activity.onDestroy 多次调用 destroy，double-destroy 会导致 native 崩溃
        if (nativeInstanceAlive) {
            try {
                MPVLib.destroy()
            } catch (e: Throwable) {
                Log.w(TAG, "destroy: MPVLib.destroy failed: ${e.message}")
            }
            nativeInstanceAlive = false
        }
    }

    private fun observeProperties() {
        MPVLib.observeProperty("time-pos", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("duration", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("pause", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("eof-reached", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("volume", MPVLib.MpvFormat.MPV_FORMAT_INT64)
        MPVLib.observeProperty("mute", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("media-title", MPVLib.MpvFormat.MPV_FORMAT_STRING)
        MPVLib.observeProperty("track-list", MPVLib.MpvFormat.MPV_FORMAT_NODE)
    }

    private var filePath: String? = null
    private var voInUse: String = DEFAULT_VO

    /**
     * 更新 voInUse（运行时切换 vo 时调用）。
     * 下次 surfaceCreated 时会用新 vo 设置 mpv，确保 surface 重建后渲染正确。
     */
    fun setVoInUse(vo: String) {
        voInUse = vo
    }

    /** 提供给外部查询 surface 状态（替代 SurfaceView 的 holder.surface?.isValid） */
    val isSurfaceValid: Boolean
        get() = holder.surface != null && holder.surface.isValid

    fun playFile(path: String) {
        val s = holder.surface
        if (s != null && s.isValid) {
            MPVLib.command(arrayOf("loadfile", path))
            // 显式解除暂停：keep-open=yes 会让 mpv 在 stop/idle 后保留 pause=true，
            // 不显式恢复会导致新文件加载后不播放（一直显示已暂停）
            MPVLib.setPropertyBoolean("pause", false)
        } else {
            filePath = path
        }
    }

    fun stop() {
        MPVLib.command(arrayOf("stop"))
    }

    // ---- SurfaceHolder.Callback ----

    override fun surfaceCreated(holder: SurfaceHolder) {
        Log.i(TAG, "surfaceCreated: attaching surface")
        try {
            MPVLib.attachSurface(holder.surface)
            MPVLib.setOptionString("force-window", "yes")
            Log.i(TAG, "attachSurface OK (SurfaceView)")
        } catch (e: Throwable) {
            Log.e(TAG, "attachSurface FAILED", e)
        }

        // 关键：surfaceCreated 必须总是把 vo 切回有效值。
        // surfaceDestroyed 时会把 vo 设为 "null"（见下方），如果 surface 重建后
        // 走 filePath 分支只 loadfile 不设置 vo，mpv 会停留在 vo=null 不渲染画面。
        // 与 mpv-android 官方 BaseMPVView 对齐：始终在 surfaceCreated 中设置 vo。
        MPVLib.setPropertyString("vo", voInUse)

        if (filePath != null) {
            Log.i(TAG, "surfaceCreated: 播放缓存的 filePath=$filePath")
            MPVLib.command(arrayOf("loadfile", filePath as String))
            MPVLib.setPropertyBoolean("pause", false)
            filePath = null
        }
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        MPVLib.setPropertyString("android-surface-size", "${width}x$height")
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        // 防御 use-after-destroy：destroy() 中先 removeCallback 再 destroy，
        // 但若 surfaceDestroyed 已在事件队列中排队，仍可能在 destroy 之后触发。
        // 此时 native 实例已销毁，调用 setPropertyString/detachSurface 会 native 崩溃。
        if (!nativeInstanceAlive) {
            Log.i(TAG, "surfaceDestroyed: native instance already destroyed, skipping")
            return
        }
        Log.i(TAG, "surfaceDestroyed: detaching surface")
        MPVLib.setPropertyString("vo", "null")
        MPVLib.setPropertyString("force-window", "no")
        MPVLib.detachSurface()
    }

    companion object {
        private const val TAG = "mpv"

        /** 默认 video output，与 PC 端 services/mpv_player_service.py 对齐 */
        const val DEFAULT_VO = "gpu"

        /**
         * 默认硬件解码模式。
         * auto-copy：自动选择硬件解码器，解码后的帧拷贝到 CPU 内存再上传 GPU。
         * 兼容性好（不依赖 vo surface），与 vo=gpu 配合使用。
         */
        const val DEFAULT_HWDEC = "auto-copy"

        /**
         * 跟踪 native mpv 实例是否存活（MPVLib 是全局单例，create/destroy 管理同一个 native 实例）。
         *
         * 用途：切换播放器（MPV → EXO/IJK → MPV）时，Compose 的 onRelease 是异步的，
         * 上次 MPVView.destroy() 可能还未执行。切回 MPV 时 MPVView.initialize() 调用
         * MPVLib.create()，如果 native 实例仍存活会导致 native 崩溃（double-create）。
         * 此标志位让 initialize 检测残留实例并先 destroy，destroy 防止 double-destroy。
         */
        @Volatile
        private var nativeInstanceAlive = false
    }
}
