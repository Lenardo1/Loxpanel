package com.loxpanel.spike

/** Verwirft alte/duplizierte Pakete auch am Ueberlauf der 16-Bit-Sequenz. */
class RtpOrder {
    private var lastSequence: Int? = null
    private var source: Long? = null

    fun accept(sequence: Int, ssrc: Long): Boolean {
        val last = lastSequence
        if (source == ssrc && last != null) {
            val distance = (sequence - last) and 0xffff
            if (distance == 0 || distance >= 0x8000) return false
        }
        source = ssrc
        lastSequence = sequence and 0xffff
        return true
    }
}
