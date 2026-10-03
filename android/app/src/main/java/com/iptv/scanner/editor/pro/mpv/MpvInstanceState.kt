package com.iptv.scanner.editor.pro.mpv

/**
 * mpv native 实例状态。
 *
 * 由于 native mpv 是单例（一个 JNI 句柄），所有 MPVView/MPVTextureView 实例
 * 共享同一份 [MpvInstanceState]。多画面模式下通过 generation 机制确保只有
 * 最新创建的 View 能操作 native 实例。
 *
 * @see MPVView.instanceState
 */
class MpvInstanceState {
    @Volatile
    var nativeInstanceAlive: Boolean = false

    @Volatile
    var nativeInstanceCreated: Boolean = false

    @Volatile
    var nativeHandleCreated: Boolean = false

    @Volatile
    var activeGeneration: Int = 0

    @Volatile
    var forceRecreatePending: Boolean = false

    @Volatile
    var savedPlaybackPath: String? = null
}