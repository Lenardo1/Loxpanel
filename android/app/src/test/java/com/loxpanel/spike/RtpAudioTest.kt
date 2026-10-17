package com.loxpanel.spike

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class RtpAudioTest {
    private fun header() = bytes(0x80, 0x08, 0x12, 0x34, 0x89, 0xab, 0xcd, 0xef, 0xfe, 0xdc, 0xba, 0x98)

    @Test
    fun bautFestenNetzwerkHeaderOhneMarker() {
        assertArrayEquals(header() + bytes(0xd5, 0x55),
            RtpAudio.packet(bytes(0xd5, 0x55), 8, 0x1234, 0x89abcdefL, 0xfedcba98L))
    }

    @Test
    fun liestHeaderUnsignedUndKopiertPayload() {
        val data = header() + bytes(0xd5, 0x55)
        val parsed = RtpAudio.parse(data, payloadType = 8)!!
        assertEquals(0x1234, parsed.sequence)
        assertEquals(0x89abcdefL, parsed.timestamp)
        assertEquals(0xfedcba98L, parsed.ssrc)
        data[12] = 0
        assertArrayEquals(bytes(0xd5, 0x55), parsed.payload)
    }

    @Test
    fun zaehlerLaufenAufIhreDrahtbreiteUeber() {
        val data = RtpAudio.packet(byteArrayOf(), 0, 0x10001, 0x100000002L, -1L)
        assertArrayEquals(bytes(0x80, 0, 0, 1, 0, 0, 0, 2, 0xff, 0xff, 0xff, 0xff), data)
        val parsed = RtpAudio.parse(data, payloadType = 0)!!
        assertEquals(1, parsed.sequence)
        assertEquals(2L, parsed.timestamp)
        assertEquals(0xffffffffL, parsed.ssrc)
        assertArrayEquals(byteArrayOf(), parsed.payload)
        val negative = RtpAudio.parse(RtpAudio.packet(byteArrayOf(), 127, -1, -1L, 0L), payloadType = 127)!!
        assertEquals(65535, negative.sequence)
        assertEquals(0xffffffffL, negative.timestamp)
    }

    @Test
    fun ueberspringtCsrcErweiterungUndPadding() {
        val data = header().apply { this[0] = 0xb2.toByte(); this[1] = 0x88.toByte() } +
            bytes(0, 0, 0, 1, 0, 0, 0, 2) + // Zwei CSRC.
            bytes(0xbe, 0xde, 0, 2) + // Erweiterung mit zwei 32-Bit-Worten.
            bytes(1, 2, 3, 4, 5, 6, 7, 8) + bytes(0xd5, 0x55) + bytes(0, 0, 0, 4)
        val parsed = RtpAudio.parse(data, payloadType = 8)!!
        assertArrayEquals(bytes(0xd5, 0x55), parsed.payload)
        assertEquals(0x1234, parsed.sequence)
    }

    @Test
    fun leereErweiterungUndAlleCsrcSindErlaubt() {
        val data = header().apply { this[0] = 0x9f.toByte() } + ByteArray(15 * 4) +
            bytes(0xab, 0xcd, 0, 0) + bytes(0x42)
        assertArrayEquals(bytes(0x42), RtpAudio.parse(data, payloadType = 8)!!.payload)
    }

    @Test
    fun nutztDatagrammLaengeStattPufferLaenge() {
        val data = header().apply { this[0] = 0xa0.toByte() } + bytes(0xd5, 0, 2)
        val receiveBuffer = data + ByteArray(40) { 0xff.toByte() }
        assertArrayEquals(bytes(0xd5), RtpAudio.parse(receiveBuffer, data.size, 8)!!.payload)
    }

    @Test
    fun lehntUngueltigeLaengenVersionenUndPayloadTypenAb() {
        val data = header() + bytes(1)
        for (length in -1..11) assertNull(RtpAudio.parse(data, length, 8))
        assertNull(RtpAudio.parse(data, data.size + 1, 8))
        assertNull(RtpAudio.parse(data, payloadType = 0))
        assertNull(RtpAudio.parse(data, payloadType = -1))
        assertNull(RtpAudio.parse(data, payloadType = 128))
        for (version in listOf(0x00, 0x40, 0xc0)) {
            assertNull(RtpAudio.parse(data.copyOf().apply { this[0] = version.toByte() }, payloadType = 8))
        }
    }

    @Test
    fun lehntAbgeschnitteneCsrcUndErweiterungenAb() {
        assertNull(RtpAudio.parse(header().apply { this[0] = 0x81.toByte() }, payloadType = 8))
        val extended = header().apply { this[0] = 0x90.toByte() }
        for (size in 0..3) assertNull(RtpAudio.parse(extended + ByteArray(size), payloadType = 8))
        assertNull(RtpAudio.parse(extended + bytes(0, 0, 0, 1) + bytes(1, 2, 3), payloadType = 8))
        assertNull(RtpAudio.parse(extended + bytes(0, 0, 0xff, 0xff), payloadType = 8))
    }

    @Test
    fun paddingDarfHeaderUndErweiterungNichtEinschliessen() {
        val padded = header().apply { this[0] = 0xa0.toByte() }
        assertNull(RtpAudio.parse(padded + bytes(0), payloadType = 8))
        assertNull(RtpAudio.parse(padded + bytes(1, 3), payloadType = 8))
        assertNull(RtpAudio.parse(padded, payloadType = 8))
        val extended = header().apply { this[0] = 0xb0.toByte() } + bytes(0, 0, 0, 1) + bytes(1, 2, 3, 4)
        assertNull(RtpAudio.parse(extended + bytes(2), payloadType = 8))
        // Ein gueltiges Padding darf die gesamte Nutzlast fuellen.
        assertNotNull(RtpAudio.parse(padded + bytes(1), payloadType = 8))
        assertArrayEquals(byteArrayOf(), RtpAudio.parse(padded + bytes(1), payloadType = 8)!!.payload)
    }

    @Test(expected = IllegalArgumentException::class)
    fun builderLehntZuGrossenPayloadTypAb() {
        RtpAudio.packet(byteArrayOf(), 128, 0, 0, 0)
    }

    @Test(expected = IllegalArgumentException::class)
    fun builderLehntNegativenPayloadTypAb() {
        RtpAudio.packet(byteArrayOf(), -1, 0, 0, 0)
    }

    private fun bytes(vararg values: Int) = ByteArray(values.size) { values[it].toByte() }
}
