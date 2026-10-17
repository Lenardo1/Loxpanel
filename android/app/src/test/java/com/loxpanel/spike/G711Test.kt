package com.loxpanel.spike

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class G711Test {
    // Feste Vektoren der G.711-Referenz (mit Python audioop gegengeprueft),
    // einschliesslich Segmentgrenzen und der Rundung kleiner negativer Samples.
    private val samples = intArrayOf(
        -32768, -32124, -16384, -4096, -1000, -256, -129, -128, -33, -32, -17,
        -16, -9, -8, -1, 0, 1, 7, 8, 15, 16, 17, 31, 32, 127, 128, 255, 256,
        1000, 4096, 16384, 32124, 32767
    ).map { it.toShort() }.toShortArray()

    @Test
    fun pcmaEncodeReferenz() {
        assertArrayEquals(bytes(
            42, 42, 58, 26, 122, 90, 93, 82, 87, 84, 84, 85, 85, 85, 85,
            213, 213, 213, 213, 213, 212, 212, 212, 215, 210, 221, 218, 197,
            250, 133, 165, 170, 170
        ), G711.encode(samples, "PCMA"))
    }

    @Test
    fun pcmuEncodeReferenz() {
        assertArrayEquals(bytes(
            0, 0, 15, 47, 78, 103, 111, 111, 122, 123, 124, 125, 125, 126, 126,
            255, 255, 254, 254, 253, 253, 253, 251, 251, 239, 239, 231, 231,
            206, 175, 143, 128, 128
        ), G711.encode(samples, "PCMU"))
    }

    @Test
    fun pcmaDecodeReferenz() {
        assertArrayEquals(shorts(
            -5504, -5248, -6784, -32256, -8, -880, -848, 5504, 5248, 6784,
            32256, 8, 880, 848
        ), G711.decode(referenceCodes(), "PCMA"))
    }

    @Test
    fun pcmuDecodeReferenz() {
        assertArrayEquals(shorts(
            -32124, -31100, -16764, -5372, -716, -8, 0, 32124, 31100, 16764,
            5372, 716, 8, 0
        ), G711.decode(referenceCodes(), "PCMU"))
    }

    @Test
    fun alleCodewoerterBleibenNachDecodeEncodeStabil() {
        val codes = ByteArray(256) { it.toByte() }
        assertArrayEquals(codes, G711.encode(G711.decode(codes, "PCMA"), "PCMA"))
        // Mu-Law hat zwei Nullwerte; PCM16 kann deren Vorzeichen nicht bewahren.
        val canonicalUlaw = codes.copyOf().apply { this[0x7f] = 0xff.toByte() }
        assertArrayEquals(canonicalUlaw, G711.encode(G711.decode(codes, "PCMU"), "PCMU"))
    }

    @Test
    fun einByteJePcmSampleUndLeereFrames() {
        for (codec in listOf("PCMA", "PCMU")) {
            assertEquals(160, G711.encode(ShortArray(160), codec).size)
            assertEquals(160, G711.decode(ByteArray(160), codec).size)
            assertArrayEquals(byteArrayOf(), G711.encode(shortArrayOf(), codec))
            assertArrayEquals(shortArrayOf(), G711.decode(byteArrayOf(), codec))
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun unbekanntenEncoderAblehnen() {
        G711.encode(shortArrayOf(), "OPUS")
    }

    @Test(expected = IllegalArgumentException::class)
    fun unbekanntenDecoderAblehnen() {
        G711.decode(byteArrayOf(), "")
    }

    private fun referenceCodes() = bytes(0x00, 0x01, 0x0f, 0x2a, 0x55, 0x7e, 0x7f, 0x80, 0x81, 0x8f, 0xaa, 0xd5, 0xfe, 0xff)
    private fun bytes(vararg values: Int) = ByteArray(values.size) { values[it].toByte() }
    private fun shorts(vararg values: Int) = ShortArray(values.size) { values[it].toShort() }
}
