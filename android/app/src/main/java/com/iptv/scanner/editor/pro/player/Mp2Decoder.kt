package com.iptv.scanner.editor.pro.player

import android.util.Log
import androidx.media3.common.C
import androidx.media3.decoder.DecoderException
import androidx.media3.decoder.DecoderInputBuffer
import androidx.media3.decoder.DecoderOutputBuffer
import androidx.media3.decoder.SimpleDecoder
import androidx.media3.decoder.SimpleDecoderOutputBuffer
import javazoom.jl.decoder.Bitstream
import javazoom.jl.decoder.Decoder
import javazoom.jl.decoder.Header
import javazoom.jl.decoder.SampleBuffer
import java.io.ByteArrayInputStream
import java.nio.ByteOrder

/**
 * MPEG-1/2 Layer 1/2/3 软解（基于 JLayer）。
 *
 * 关键设计（修复 EXO 播放时钟不走的回归）：
 * - TS 解复用器喂来的缓冲可能包含多帧、半帧或带垃圾前缀，不能假设"一缓冲一帧"。
 *   这里自维护跨缓冲 carry 缓冲 + 同步字扫描 + 帧长计算，按完整帧逐帧解码。
 * - 只有 inputBuffer 携带真实 EOS 标志时才输出 EOS；垃圾/半帧一律吞掉继续，
 *   否则音频渲染器瞬间"结束"，播放时钟（由音频渲染器驱动）停在 0，
 *   视频渲染器只渲染第一帧后永远等待（表现为"停在第一帧、pos=0"）。
 * - 每帧输出独立时间戳：后续帧 = 首帧 timeUs + 已解码样本累计时长。
 */
class Mp2Decoder(
    appContext: android.content.Context,
    var sampleRate: Int = 0,
    var channelCount: Int = 0
) : SimpleDecoder<DecoderInputBuffer, SimpleDecoderOutputBuffer, DecoderException>(
    emptyArray(),
    emptyArray()
), DecoderOutputBuffer.Owner<SimpleDecoderOutputBuffer> {

    companion object {
        private const val TAG = "Mp2Decoder"

        /** MPEG 各版本比特率表（kbps），索引 = [版本][层][比特率索引] */
        private val BITRATES = arrayOf(
            // MPEG 1（V1）
            intArrayOf(0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448), // Layer 1
            intArrayOf(0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384),   // Layer 2
            intArrayOf(0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)     // Layer 3
        )
        private val BITRATES_V2 = arrayOf(
            // MPEG 2 / 2.5（V2）
            intArrayOf(0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256), // Layer 1
            intArrayOf(0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),      // Layer 2
            intArrayOf(0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)       // Layer 3
        )
        private val SAMPLE_RATES_V1 = intArrayOf(44100, 48000, 32000)
        private val SAMPLE_RATES_V2 = intArrayOf(22050, 24000, 16000)
        private val SAMPLE_RATES_V25 = intArrayOf(11025, 12000, 8000)

    }

    private val jlayerDecoder = Decoder()


    // 解码链路文件诊断（EMUI logd 限流，写文件保证可回溯）
    private val diagFile = java.io.File(appContext.getExternalFilesDir(null), "mp2_diag.log")
    private val diagLock = Any()
    private var inputCount = 0
    init {
        mLog("created rate=$sampleRate ch=$channelCount")
    }
    private fun mLog(msg: String) {
        try {
            synchronized(diagLock) {
                if (diagFile.length() > 512 * 1024) diagFile.delete()
                val ts = java.text.SimpleDateFormat("MM-dd HH:mm:ss.SSS", java.util.Locale.US)
                    .format(java.util.Date())
                diagFile.appendText("$ts $msg\n")
            }
        } catch (_: Exception) {}
    }

    /** 跨缓冲的字节续接缓冲（TS 包可能把音频帧切在任意位置） */
    private val carry = java.io.ByteArrayOutputStream()

    /** carry 中已确认的字节数（含垃圾跳过后的有效区起点处理，见 consume） */
    private var pendingTimeUs = java.lang.Long.MIN_VALUE

    override fun getName(): String = "Mp2Decoder"

    override fun createInputBuffer(): DecoderInputBuffer =
        DecoderInputBuffer(DecoderInputBuffer.BUFFER_REPLACEMENT_MODE_NORMAL)

    override fun createOutputBuffer(): SimpleDecoderOutputBuffer =
        SimpleDecoderOutputBuffer(this)

    override fun createUnexpectedDecodeException(throwable: Throwable): DecoderException =
        DecoderException(throwable)

    override fun decode(
        inputBuffer: DecoderInputBuffer,
        outputBuffer: SimpleDecoderOutputBuffer,
        reset: Boolean
    ): DecoderException? {
        if (reset) {
            carry.reset()
            pendingTimeUs = java.lang.Long.MIN_VALUE
        }

        val inputData = inputBuffer.data
        // 直播流不依赖音频 EOS；空缓冲不产出也不设 EOS（防音频渲染器提前"结束"拖死播放时钟）
        if (inputData == null || !inputData.hasRemaining()) {
            // 无新数据（纯 flush 轮询），不产出、也绝不设置 EOS
            return null
        }

        // 把新输入并入 carry
        val chunk = ByteArray(inputData.remaining())
        inputData.get(chunk)
        carry.write(chunk, 0, chunk.size)
        inputCount++
        mLog("input#$inputCount bytes=${chunk.size} timeUs=${inputBuffer.timeUs} carryNow=${carry.size()}")
        val bytes = carry.toByteArray()

        var frameTimeUs = if (pendingTimeUs != java.lang.Long.MIN_VALUE) {
            pendingTimeUs
        } else {
            inputBuffer.timeUs
        }

        // 在 carry 中逐帧解码
        var pos = 0
        var produced = false
        var decodeError: DecoderException? = null

        while (true) {
            // 跳过垃圾字节（找 11 位同步字 0xFFE）
            while (pos + 1 < bytes.size) {
                val sync = (bytes[pos].toInt() and 0xFF) == 0xFF &&
                    (bytes[pos + 1].toInt() and 0xE0) == 0xE0
                if (sync) break
                pos++
            }
            if (pos + 4 > bytes.size) break // 头都不完整，等下个缓冲

            val header = parseHeader(bytes, pos)
            if (header == null) {
                pos++ // 同步字误报，前移一位继续找
                continue
            }
            val frameLen = header.second
            if (pos + frameLen > bytes.size) break // 半帧，等下个缓冲

            // 用恰好一帧的字节构造 JLayer 流并解码
            val out = decodeOneFrame(bytes, pos, frameLen)
            mLog("frame@pos=$pos len=$frameLen out=${if (out != null) out.length else -1}")
            if (out != null) {
                val (pcmShorts, numSamples, rate, channels) = out
                if (numSamples > 0) {
                    sampleRate = rate
                    channelCount = channels
                    val pcmByteSize = numSamples * 2
                    val outBuf = outputBuffer.init(frameTimeUs, pcmByteSize)
                    outBuf.order(ByteOrder.LITTLE_ENDIAN)
                    val shortBuf = outBuf.asShortBuffer()
                    shortBuf.put(pcmShorts, 0, numSamples)
                    outBuf.position(pcmByteSize)
                    produced = true
                    // 每帧时长（1152/576 样本）
                    val samplesPerFrame = if ((bytes[pos + 1].toInt() and 0x08) != 0) 1152 else 576
                    frameTimeUs += samplesPerFrame * 1_000_000L / rate
                    break // 一个输出缓冲只装一帧（SimpleDecoder 模式），余下帧留待下次
                }
            } else {
                decodeError = decodeError // keep null-safe
            }
            // 该帧解完（或解失败），推进位置
            pos += frameLen
        }

        // 保留未消费的尾部
        if (pos > 0) {
            val remain = ByteArray(bytes.size - pos)
            System.arraycopy(bytes, pos, remain, 0, remain.size)
            carry.reset()
            carry.write(remain, 0, remain.size)
        }
        pendingTimeUs = if (produced) frameTimeUs else java.lang.Long.MIN_VALUE

        if (!produced) {
            // 无完整可解帧（半帧/垃圾）：不产出也不设 EOS，等下一个输入缓冲
            mLog("no frame produced, carry=${carry.size()}")
            return null
        }
        return decodeError
    }

    override fun releaseOutputBuffer(outputBuffer: SimpleDecoderOutputBuffer) {
        super.releaseOutputBuffer(outputBuffer)
    }

    /** 解码 carry 中 [pos, pos+frameLen) 的单个音频帧，返回 PCM 与参数 */
    private fun decodeOneFrame(
        bytes: ByteArray,
        pos: Int,
        frameLen: Int
    ): Tuple4? {
        return try {
            val frameBytes = ByteArray(frameLen)
            System.arraycopy(bytes, pos, frameBytes, 0, frameLen)
            val bitstream = Bitstream(ByteArrayInputStream(frameBytes))
            val header = bitstream.readFrame() ?: run {
                bitstream.closeFrame()
                return null
            }
            val output = jlayerDecoder.decodeFrame(header, bitstream) as SampleBuffer
            bitstream.closeFrame()
            Tuple4(output.buffer, output.bufferLength, output.sampleFrequency, output.channelCount)
        } catch (e: Exception) {
            mLog("decodeOneFrame EX: ${e.javaClass.simpleName}: ${e.message}")
            Log.w(TAG, "decode failed: ${e.message}")
            null
        }
    }

    /** 解析 MPEG 帧头，返回 (样本率, 帧总长)，非法返回 null */
    private fun parseHeader(b: ByteArray, off: Int): Pair<Int, Int>? {
        val b1 = b[off + 1].toInt() and 0xFF
        val b2 = b[off + 2].toInt() and 0xFF
        val b3 = b[off + 3].toInt() and 0xFF

        val versionBits = (b1 shr 3) and 0x03 // 0=2.5, 2=2, 3=1
        val layerBits = (b1 shr 1) and 0x03   // 1=Layer3, 2=Layer2, 3=Layer1
        if (versionBits == 1 || layerBits == 0) return null
        val bitrateIdx = (b2 shr 4) and 0x0F
        val rateIdx = (b2 shr 2) and 0x03
        val padding = (b2 shr 1) and 0x01
        if (bitrateIdx == 0 || bitrateIdx == 15 || rateIdx == 3) return null

        val sampleRate = when (versionBits) {
            3 -> SAMPLE_RATES_V1[rateIdx]
            2 -> SAMPLE_RATES_V2[rateIdx]
            else -> SAMPLE_RATES_V25[rateIdx]
        }
        val layer = when (layerBits) { 3 -> 0; 2 -> 1; else -> 2 } // 0=L1,1=L2,2=L3
        val bitrateKbps = if (versionBits == 3) BITRATES[layer][bitrateIdx] else BITRATES_V2[layer][bitrateIdx]
        if (bitrateKbps <= 0) return null

        val frameLen = if (layer == 0) {
            (12 * bitrateKbps * 1000 / sampleRate + padding) * 4
        } else if (versionBits == 3) {
            144 * bitrateKbps * 1000 / sampleRate + padding
        } else {
            72 * bitrateKbps * 1000 / sampleRate + padding
        }
        if (frameLen < 24 || frameLen > 2048) return null
        return Pair(sampleRate, frameLen)
    }

    private data class Tuple4(
        val pcm: ShortArray,
        val length: Int,
        val rate: Int,
        val channels: Int
    )
}
