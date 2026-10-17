package com.loxpanel.spike

/** RTP v2 ohne Android-Abhaengigkeiten; alle Drahtwerte sind unsigned. */
object RtpAudio {
    data class Parsed(val payload: ByteArray, val sequence: Int, val timestamp: Long, val ssrc: Long)

    fun packet(payload: ByteArray, payloadType: Int, sequence: Int, timestamp: Long, ssrc: Long): ByteArray {
        require(payloadType in 0..127) { "RTP-Payload-Typ muss zwischen 0 und 127 liegen" }
        val data = ByteArray(12 + payload.size)
        data[0] = 0x80.toByte()
        data[1] = payloadType.toByte() // Marker bleibt aus, keine CSRC oder Erweiterung.
        data[2] = (sequence ushr 8).toByte()
        data[3] = sequence.toByte()
        write32(data, 4, timestamp)
        write32(data, 8, ssrc)
        payload.copyInto(data, 12)
        return data
    }

    fun parse(data: ByteArray, length: Int = data.size, payloadType: Int): Parsed? {
        if (payloadType !in 0..127 || length < 12 || length > data.size) return null
        val flags = unsigned(data[0])
        if ((flags ushr 6) != 2 || (unsigned(data[1]) and 0x7f) != payloadType) return null
        var start = 12 + (flags and 0x0f) * 4
        if (start > length) return null
        if ((flags and 0x10) != 0) {
            if (length - start < 4) return null
            val extensionLength = read16(data, start + 2) * 4
            start += 4
            if (extensionLength > length - start) return null
            start += extensionLength
        }
        var end = length
        if ((flags and 0x20) != 0) {
            val padding = unsigned(data[length - 1])
            if (padding == 0 || padding > end - start) return null
            end -= padding
        }
        // Kopieren: der Empfaenger verwendet seinen UDP-Puffer beim naechsten Paket erneut.
        return Parsed(data.copyOfRange(start, end), read16(data, 2), read32(data, 4), read32(data, 8))
    }

    private fun unsigned(value: Byte): Int = value.toInt() and 0xff

    private fun read16(data: ByteArray, offset: Int): Int =
        (unsigned(data[offset]) shl 8) or unsigned(data[offset + 1])

    private fun read32(data: ByteArray, offset: Int): Long =
        (unsigned(data[offset]).toLong() shl 24) or
            (unsigned(data[offset + 1]).toLong() shl 16) or
            (unsigned(data[offset + 2]).toLong() shl 8) or unsigned(data[offset + 3]).toLong()

    private fun write32(data: ByteArray, offset: Int, value: Long) {
        for (index in 0..3) data[offset + index] = (value ushr (24 - index * 8)).toByte()
    }
}
