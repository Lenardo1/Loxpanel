package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BleLogikTest {
    private fun b(vararg x: Int) = ByteArray(x.size) { x[it].toByte() }

    // Apple-Herstellerdaten ohne Firmenkennung: 02 15, UUID, Major, Minor, TxPower
    private fun ibeacon(uuidHex: String, major: Int, minor: Int, tx: Int): ByteArray {
        val u = uuidHex.replace("-", "").chunked(2).map { it.toInt(16) }
        return b(0x02, 0x15, *u.toIntArray(), major shr 8, major and 0xff, minor shr 8, minor and 0xff, tx and 0xff)
    }

    @Test fun unbekannteGeraeteWerdenIgnoriert() {
        val l = BleLogik(); l.setzeBekannt(listOf("aabbccddeeff"))
        l.fund(BleLogik.Fund("11:22:33:44:55:66", -60, ""), 100)
        assertTrue(l.warteschlange.isEmpty())
    }

    @Test fun bekanntesGeraetKommtOnlineUndGehtOffline() {
        val l = BleLogik(scanIntervall = 5, offlineNach = 30); l.setzeBekannt(listOf("AABBCCDDEEFF"))
        val e = l.fund(BleLogik.Fund("aa:bb:cc:dd:ee:ff", -60, ""), 100)
        assertTrue(e.sofortSenden)
        val s = l.nimmWarteschlange().single()
        assertEquals("AA:BB:CC:DD:EE:FF", s.getString("address")); assertEquals(1, s.getInt("is_online"))
        l.fund(BleLogik.Fund("aa:bb:cc:dd:ee:ff", -61, ""), 102)        // innerhalb scanIntervall: nichts
        assertTrue(l.warteschlange.isEmpty())
        l.fund(BleLogik.Fund("aa:bb:cc:dd:ee:ff", -62, ""), 106)        // danach wieder gemeldet
        assertEquals(1, l.nimmWarteschlange().size)
        l.pruefeOffline(140)
        assertEquals(0, l.nimmWarteschlange().single().getInt("is_online"))
    }

    @Test fun iBeaconUeberUuid() {
        val uuid = "12345678-1234-1234-1234-123456789abc"
        val l = BleLogik(); l.setzeBekannt(listOf(uuid))
        l.fund(BleLogik.Fund("01:02:03:04:05:06", -70, "", apple = ibeacon(uuid, 1, 2, -59)), 10)
        val s = l.nimmWarteschlange().single()
        assertEquals(uuid, s.getString("ibeacon_uuid")); assertEquals(1, s.getInt("ibeacon_major"))
        assertEquals(2, s.getInt("ibeacon_minor")); assertEquals(-59, s.getInt("ibeacon_txpower"))
    }

    @Test fun kalibrierBeaconWirdGemittelt() {
        val l = BleLogik()
        val ib = ibeacon(BleLogik.CALIB_UUID, 7, 9, -59)
        l.fund(BleLogik.Fund("01:02:03:04:05:06", -60, "", apple = ib), 1)
        l.fund(BleLogik.Fund("01:02:03:04:05:06", -64, "", apple = ib), 2)
        val k = l.nimmKalibrierung().single()
        assertEquals(-62, k.getInt("rssi")); assertEquals(7, k.getInt("major"))
        assertTrue(l.warteschlange.isEmpty())
    }

    @Test fun btHomeTasteUndBatterie() {
        val l = BleLogik(); l.setzeBekannt(listOf("aabbccddeeff"))
        // Geraeteinfo 0x40, pid(0x00)=5, Batterie(0x01)=87, Taste(0x3A)=1
        val raw = b(0x40, 0x00, 5, 0x01, 87, 0x3A, 1)
        val e = l.fund(BleLogik.Fund("AA:BB:CC:DD:EE:FF", -50, "", btHome = raw), 1)
        assertNotNull(e.ereignis); assertEquals("press", e.ereignis!!.getString("event"))
        assertEquals(87, l.nimmWarteschlange().single().getInt("battery"))
        // gleiche Paket-ID: Wiederholung, wird ignoriert
        assertNull(l.fund(BleLogik.Fund("AA:BB:CC:DD:EE:FF", -50, "", btHome = raw), 2).ereignis)
    }

    @Test fun verschluesseltesBtHomeIgnoriert() {
        assertNull(BleLogik().btHome(b(0x41, 0x00, 1)))
    }

    @Test fun eddystoneBatterie() {
        assertEquals(100, BleLogik().eddystoneBatterie(b(0x20, 0x00, 0x0B, 0xB8)))   // 3000 mV
        assertEquals(-1, BleLogik().eddystoneBatterie(b(0x10, 0, 0, 0)))
    }

    // Testvektor mit Python/cryptography wie im Plugin (irk_monitor.resolve_irk) erzeugt
    private val IRK = "0123456789abcdef0123456789abcdef"
    private val RPA = "5A:12:34:80:C9:78"

    @Test fun irkLoestRotierendeAdresseAuf() {
        val l = BleLogik(); l.setzeIrks(listOf(IRK.uppercase()))
        assertEquals(IRK, l.irkFuer(RPA))
        assertNull(l.irkFuer("5A:12:34:80:C9:79"))      // falscher Hash
        assertNull(l.irkFuer("1A:12:34:80:C9:78"))      // keine aufloesbare Adresse
    }

    @Test fun irkGeraetWirdMitIrkGemeldet() {
        val l = BleLogik(offlineNach = 30); l.setzeIrks(listOf(IRK))
        l.fund(BleLogik.Fund(RPA, -55, ""), 10)
        val s = l.nimmWarteschlange().single()
        assertEquals(IRK, s.getString("irk")); assertEquals(RPA, s.getString("address"))
        l.pruefeOffline(50)
        val aus = l.nimmWarteschlange().single()
        assertEquals(0, aus.getInt("is_online")); assertEquals(IRK, aus.getString("irk"))
    }
}
