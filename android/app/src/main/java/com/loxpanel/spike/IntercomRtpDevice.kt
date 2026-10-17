package com.loxpanel.spike

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.os.Handler
import android.os.Process
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.random.Random

/** Ein gebundener RTP-Port fuer beide Richtungen, 20 ms G.711 je Paket. */
@Suppress("DEPRECATION")
class IntercomRtpDevice(context: Context, private val ui: Handler,
                        private val socket: DatagramSocket, private val media: IntercomMedia,
                        private val onError: (String) -> Unit) {
    private val manager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val alive = AtomicBoolean(false)
    private val released = AtomicBoolean(false)
    private var recorder: AudioRecord? = null
    private var player: AudioTrack? = null
    private var echo: AcousticEchoCanceler? = null
    private var noise: NoiseSuppressor? = null
    private var focus: AudioFocusRequest? = null
    private var focusHeld = false
    private var previousMode = manager.mode
    private var previousSpeaker = manager.isSpeakerphoneOn
    private var previousDevice: AudioDeviceInfo? = null
    private var routeChanged = false
    private var modeChanged = false
    @Volatile private var focusLost = false
    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        focusLost = change < 0
        if (focusLost && alive.get()) onError("Das Gespräch wurde durch eine andere Audioanwendung beendet")
    }

    fun start() {
        try {
            socket.connect(InetSocketAddress(media.remoteHost, media.remotePort))
            socket.soTimeout = 500
            socket.receiveBufferSize = 4096
            val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
            val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                    .setAudioAttributes(attributes).setOnAudioFocusChangeListener(focusListener, ui).build()
                manager.requestAudioFocus(focus!!)
            } else manager.requestAudioFocus(focusListener, AudioManager.STREAM_VOICE_CALL,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            if (granted != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
                throw IllegalStateException("Audio wird gerade von einer anderen Anwendung verwendet")
            }
            focusHeld = true
            previousMode = manager.mode
            previousSpeaker = manager.isSpeakerphoneOn
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) previousDevice = manager.communicationDevice
            manager.mode = AudioManager.MODE_IN_COMMUNICATION
            modeChanged = true
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val speaker = manager.availableCommunicationDevices.firstOrNull {
                    it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
                }
                if (speaker == null || !manager.setCommunicationDevice(speaker)) {
                    throw IllegalStateException("Der Gerätelautsprecher ist nicht verfügbar")
                }
            } else manager.isSpeakerphoneOn = true
            routeChanged = true

            val inputBuffer = AudioRecord.getMinBufferSize(8000, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT)
            val outputBuffer = AudioTrack.getMinBufferSize(8000, AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT)
            if (inputBuffer <= 0 || outputBuffer <= 0) {
                throw IllegalStateException("Das Gerät unterstützt kein Sprach-Audio mit 8 kHz")
            }
            recorder = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, 8000,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(inputBuffer, 640))
            player = AudioTrack.Builder().setAudioAttributes(attributes).setAudioFormat(AudioFormat.Builder()
                .setSampleRate(8000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(maxOf(outputBuffer, 960)).build()
            if (recorder?.state != AudioRecord.STATE_INITIALIZED || player?.state != AudioTrack.STATE_INITIALIZED) {
                throw IllegalStateException("Mikrofon oder Lautsprecher konnte nicht geöffnet werden")
            }
            val audioSession = recorder!!.audioSessionId
            if (AcousticEchoCanceler.isAvailable()) runCatching {
                echo = AcousticEchoCanceler.create(audioSession)
                echo?.enabled = true
            }
            if (NoiseSuppressor.isAvailable()) runCatching {
                noise = NoiseSuppressor.create(audioSession)
                noise?.enabled = true
            }
            recorder!!.startRecording()
            if (recorder!!.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                throw IllegalStateException("Das Mikrofon konnte nicht gestartet werden")
            }
            player!!.play()
            alive.set(true)
            if (focusLost) throw IllegalStateException("Audio wird gerade von einer anderen Anwendung verwendet")
            thread("loxpanel-rtp-send") { send() }
            thread("loxpanel-rtp-receive") { receive() }
        } catch (e: Exception) {
            close()
            throw e
        }
    }

    private fun thread(name: String, action: () -> Unit) {
        Thread({
            try {
                Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
                action()
            } catch (e: Exception) {
                if (alive.get()) onError("Audioverbindung abgebrochen: ${e.message ?: "Netzwerkfehler"}")
            }
        }, name).apply { isDaemon = true }.start()
    }

    private fun send() {
        val samples = ShortArray(160)
        var sequence = Random.nextInt(65536)
        var timestamp = Random.nextLong().and(0xffffffffL)
        val ssrc = Random.nextLong().and(0xffffffffL)
        while (alive.get()) {
            var count = 0
            while (count < samples.size && alive.get()) {
                val n = recorder?.read(samples, count, samples.size - count, AudioRecord.READ_BLOCKING) ?: return
                if (n < 0) throw IllegalStateException("Mikrofonfehler $n")
                if (n == 0 && alive.get()) throw IllegalStateException("Das Mikrofon liefert keine Audiodaten")
                count += n
            }
            if (!alive.get()) return
            val packet = RtpAudio.packet(G711.encode(samples, media.codec), media.payloadType, sequence, timestamp, ssrc)
            socket.send(DatagramPacket(packet, packet.size))
            sequence = (sequence + 1) and 0xffff
            timestamp = (timestamp + 160) and 0xffffffffL
        }
    }

    private fun receive() {
        val bytes = ByteArray(2048)
        val packet = DatagramPacket(bytes, bytes.size)
        val order = RtpOrder()
        while (alive.get()) {
            try {
                packet.length = bytes.size
                socket.receive(packet)
            } catch (_: SocketTimeoutException) { continue }
            val rtp = RtpAudio.parse(bytes, packet.length, media.payloadType) ?: continue
            if (rtp.payload.isEmpty() || rtp.payload.size > 800) continue
            // Keine Duplikate oder alten Pakete abspielen; neue SSRC startet neu.
            if (!order.accept(rtp.sequence, rtp.ssrc)) continue
            val samples = G711.decode(rtp.payload, media.codec)
            var count = 0
            while (count < samples.size && alive.get()) {
                val n = player?.write(samples, count, samples.size - count, AudioTrack.WRITE_BLOCKING) ?: return
                if (n < 0) throw IllegalStateException("Lautsprecherfehler $n")
                if (n == 0 && alive.get()) throw IllegalStateException("Der Lautsprecher nimmt keine Audiodaten an")
                count += n
            }
        }
    }

    fun close() {
        if (!released.compareAndSet(false, true)) return
        alive.set(false)
        socket.close()
        try { recorder?.stop() } catch (_: Exception) { /* nicht gestartet */ }
        try { player?.stop() } catch (_: Exception) { /* nicht gestartet */ }
        runCatching { echo?.release() }
        runCatching { noise?.release() }
        runCatching { recorder?.release() }
        runCatching { player?.release() }
        recorder = null
        player = null
        if (routeChanged) runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val previous = previousDevice
                if (previous == null) manager.clearCommunicationDevice() else manager.setCommunicationDevice(previous)
            } else manager.isSpeakerphoneOn = previousSpeaker
        }
        if (modeChanged) runCatching { manager.mode = previousMode }
        if (focusHeld) runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) focus?.let { manager.abandonAudioFocusRequest(it) }
            else manager.abandonAudioFocus(focusListener)
        }
    }
}
