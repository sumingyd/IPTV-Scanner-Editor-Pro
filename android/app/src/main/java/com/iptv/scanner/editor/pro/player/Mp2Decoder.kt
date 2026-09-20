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
import javazoom.jl.decoder.SampleBuffer
import java.io.ByteArrayInputStream
import java.nio.ByteOrder

class Mp2Decoder(
    var sampleRate: Int = 0,
    var channelCount: Int = 0
) : SimpleDecoder<DecoderInputBuffer, SimpleDecoderOutputBuffer, DecoderException>(
    emptyArray(),
    emptyArray()
), DecoderOutputBuffer.Owner<SimpleDecoderOutputBuffer> {

    companion object {
        private const val TAG = "Mp2Decoder"
    }

    private val jlayerDecoder = Decoder()

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
        val inputData = inputBuffer.data
        if (inputData == null || !inputData.hasRemaining()) {
            outputBuffer.addFlag(C.BUFFER_FLAG_END_OF_STREAM)
            return null
        }

        val bytes = ByteArray(inputData.remaining())
        inputData.get(bytes)

        return try {
            val bitstream = Bitstream(ByteArrayInputStream(bytes))
            val header = bitstream.readFrame()
            if (header == null) {
                outputBuffer.addFlag(C.BUFFER_FLAG_END_OF_STREAM)
                bitstream.close()
                return null
            }

            val output = jlayerDecoder.decodeFrame(header, bitstream) as SampleBuffer
            val pcmShorts = output.buffer
            val numSamples = output.bufferLength

            if (numSamples > 0) {
                sampleRate = output.sampleFrequency
                channelCount = output.channelCount

                val pcmByteSize = numSamples * 2
                val outBuf = outputBuffer.init(inputBuffer.timeUs, pcmByteSize)
                outBuf.order(ByteOrder.LITTLE_ENDIAN)
                val shortBuf = outBuf.asShortBuffer()
                shortBuf.put(pcmShorts, 0, numSamples)
                outBuf.position(pcmByteSize)
            }

            bitstream.closeFrame()
            null
        } catch (e: Exception) {
            Log.w(TAG, "decode failed: ${e.message}")
            DecoderException(e)
        }
    }

    override fun releaseOutputBuffer(outputBuffer: SimpleDecoderOutputBuffer) {
        super.releaseOutputBuffer(outputBuffer)
    }
}
