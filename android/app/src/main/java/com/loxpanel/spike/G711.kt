package com.loxpanel.spike

/** G.711 fuer einzelne PCM16-Mono-Samples; Takt und Paketlaenge bestimmt der Aufrufer. */
object G711 {
    fun encode(samples: ShortArray, codec: String): ByteArray {
        val alaw = isAlaw(codec)
        return ByteArray(samples.size) { index ->
            (if (alaw) encodeAlaw(samples[index].toInt()) else encodeUlaw(samples[index].toInt())).toByte()
        }
    }

    fun decode(payload: ByteArray, codec: String): ShortArray {
        val alaw = isAlaw(codec)
        return ShortArray(payload.size) { index ->
            val value = payload[index].toInt() and 0xff
            (if (alaw) decodeAlaw(value) else decodeUlaw(value)).toShort()
        }
    }

    private fun isAlaw(codec: String): Boolean = when (codec) {
        "PCMA" -> true
        "PCMU" -> false
        else -> throw IllegalArgumentException("Unbekannter G.711-Codec: $codec")
    }

    private fun encodeAlaw(sample: Int): Int {
        // Die Referenz rechnet mit 13 Bit; vor dem Vorzeichenwechsel abrunden.
        var value = sample shr 3
        val mask = if (value >= 0) 0xd5 else 0x55
        if (value < 0) value = -value - 1
        val segment = segment(value, 0x1f)
        if (segment >= 8) return 0x7f xor mask
        val mantissa = (value shr (if (segment < 2) 1 else segment)) and 0x0f
        return ((segment shl 4) or mantissa) xor mask
    }

    private fun decodeAlaw(encoded: Int): Int {
        val value = encoded xor 0x55
        val segment = (value ushr 4) and 0x07
        var sample = (value and 0x0f) shl 4
        sample = when (segment) {
            0 -> sample + 8
            1 -> sample + 0x108
            else -> (sample + 0x108) shl (segment - 1)
        }
        return if ((value and 0x80) != 0) sample else -sample
    }

    private fun encodeUlaw(sample: Int): Int {
        // 14-Bit-Eingang und Bias 33 entsprechen der G.711-Referenz.
        var value = sample shr 2
        val mask = if (value < 0) 0x7f else 0xff
        if (value < 0) value = -value
        value = value.coerceAtMost(8159) + 33
        val segment = segment(value, 0x3f)
        if (segment >= 8) return 0x7f xor mask
        return ((segment shl 4) or ((value shr (segment + 1)) and 0x0f)) xor mask
    }

    private fun decodeUlaw(encoded: Int): Int {
        val value = encoded xor 0xff
        val sample = (((value and 0x0f) shl 3) + 0x84) shl ((value ushr 4) and 0x07)
        return if ((value and 0x80) != 0) 0x84 - sample else sample - 0x84
    }

    private fun segment(value: Int, firstLimit: Int): Int {
        var limit = firstLimit
        for (segment in 0..7) {
            if (value <= limit) return segment
            limit = (limit shl 1) or 1
        }
        return 8
    }
}
