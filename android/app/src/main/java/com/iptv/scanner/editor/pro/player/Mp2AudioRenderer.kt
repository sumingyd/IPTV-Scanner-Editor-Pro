package com.iptv.scanner.editor.pro.player

import android.os.Handler
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.decoder.CryptoConfig
import androidx.media3.exoplayer.audio.AudioRendererEventListener
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DecoderAudioRenderer

class Mp2AudioRenderer(
    eventHandler: Handler,
    eventListener: AudioRendererEventListener,
    audioSink: AudioSink
) : DecoderAudioRenderer<Mp2Decoder>(eventHandler, eventListener, audioSink) {

    override fun getName(): String = "Mp2AudioRenderer"

    override fun supportsFormatInternal(format: Format): Int {
        return if (MimeTypes.AUDIO_MPEG_L2 == format.sampleMimeType) {
            C.FORMAT_HANDLED
        } else {
            C.FORMAT_UNSUPPORTED_TYPE
        }
    }

    override fun createDecoder(format: Format, cryptoConfig: CryptoConfig?): Mp2Decoder {
        return Mp2Decoder(format.sampleRate, format.channelCount)
    }

    override fun getOutputFormat(decoder: Mp2Decoder): Format {
        return Format.Builder()
            .setSampleMimeType(MimeTypes.AUDIO_RAW)
            .setPcmEncoding(C.ENCODING_PCM_16BIT)
            .setSampleRate(decoder.sampleRate)
            .setChannelCount(decoder.channelCount)
            .build()
    }
}