package com.loxpanel.spike

import org.json.JSONObject
import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec

/**
 * BLE-Presence-Scanner (eigene Version, Marco): dieselbe Logik wie das
 * Shelly-Skript „BLE Presence - Shelly Scanner“ des LoxBerry-Plugins
 * ble_presence (Dieter Schmidberger), damit das Wall Display X2i – das keine
 * Shelly-Skripte kann – als Scanner arbeitet. Ohne Android-Abhaengigkeiten,
 * damit sie sich auf dem PC testen laesst; Funk und HTTP macht BlePresenceService.
 */
class BleLogik(var scanIntervall: Int = 5, val offlineNach: Int = 30) {
    companion object {
        const val CALIB_UUID = "b1e0cafe-ca1b-4000-8000-beac0000c0de"
        const val PEND_MAX = 20
        private val TASTEN = arrayOf("none", "press", "double_press", "triple_press", "long_press")
    }

    data class IBeacon(val uuid: String, val major: Int, val minor: Int, val txpower: Int)
    data class BtHome(val pid: Int, val battery: Int, val button: Int)

    /** Ein Fund vom Funk: MAC "AA:BB:..", RSSI, Name und die Rohdaten der Werbung. */
    data class Fund(val mac: String, val rssi: Int, val name: String,
                    val btHome: ByteArray? = null, val eddystone: ByteArray? = null,
                    val apple: ByteArray? = null)

    private class Geraet(var online: Boolean = false, var gesehen: Long = 0, var mac: String = "",
                         var gemeldet: Long = 0, var batterie: Int = -1,
                         val istUuid: Boolean = false, var uuid: String = "", val irk: String = "")

    private var bekannt = HashSet<String>()       // 12 Zeichen, klein
    private var bekanntUuid = HashSet<String>()   // 36 Zeichen, klein
    private val geraete = HashMap<String, Geraet>()
    // IRK-Geraete (rotierende Adressen, z. B. Handys): IRK hex klein -> AES-Schluessel.
    // Das Plugin loest sie beim ESP32 genauso auf (irk_monitor.py: Schluessel umgedreht).
    private var irks = LinkedHashMap<String, SecretKeySpec>()
    // Schon geprueft: Adresse -> IRK ("" = gehoert zu keinem), begrenzt
    private val aufgeloest = object : LinkedHashMap<String, String>(256, 0.75f, true) {
        override fun removeEldestEntry(e: MutableMap.MutableEntry<String, String>?) = size > 512
    }
    private val letztePid = HashMap<String, Int>()
    private val kalib = HashMap<String, IntArray>()   // "major:minor" -> [summe, anzahl, txpower]
    val warteschlange = ArrayList<JSONObject>()
    var verloren = 0
        private set

    fun anzahlBekannt() = bekannt.size + bekanntUuid.size + irks.size

    fun setzeIrks(liste: List<String>) {
        val neu = LinkedHashMap<String, SecretKeySpec>()
        for (roh in liste) {
            val h = roh.trim().lowercase()
            if (h.length != 32 || h.any { it !in "0123456789abcdef" }) continue
            val k = ByteArray(16) { h.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
            k.reverse()
            neu[h] = SecretKeySpec(k, "AES")
        }
        if (neu.keys != irks.keys) aufgeloest.clear()
        irks = neu
    }

    /** IRK zu einer aufloesbaren privaten Adresse (oberste Bits 01), sonst null. */
    fun irkFuer(mac: String): String? {
        if (irks.isEmpty()) return null
        aufgeloest[mac]?.let { return it.ifEmpty { null } }
        val a = mac.split(":").mapNotNull { it.toIntOrNull(16) }
        var treffer = ""
        if (a.size == 6 && (a[0] and 0xC0) == 0x40) {
            val klar = ByteArray(16).also { it[13] = a[0].toByte(); it[14] = a[1].toByte(); it[15] = a[2].toByte() }
            for ((h, k) in irks) {
                val c = Cipher.getInstance("AES/ECB/NoPadding").apply { init(Cipher.ENCRYPT_MODE, k) }.doFinal(klar)
                if ((c[13].toInt() and 0xff) == a[3] && (c[14].toInt() and 0xff) == a[4] && (c[15].toInt() and 0xff) == a[5]) {
                    treffer = h; break
                }
            }
        }
        aufgeloest[mac] = treffer
        return treffer.ifEmpty { null }
    }
    fun anzahlOnline() = geraete.values.count { it.online }
    /** Wann zuletzt ein bekanntes Geraet gesehen wurde (Sekunden), 0 = nie. */
    var zuletztErkannt = 0L
        private set

    fun setzeBekannt(liste: List<String>) {
        bekannt = HashSet(); bekanntUuid = HashSet()
        for (roh in liste) {
            val e = roh.lowercase()
            if (e.length == 12) bekannt.add(e)
            else if (e.length == 36 && e.indexOf('-') > 0) bekanntUuid.add(e)
        }
    }

    private fun macKey(mac: String) = mac.replace(":", "").lowercase()

    private fun dazu(scan: JSONObject): Boolean {
        if (warteschlange.size >= PEND_MAX) { verloren++; return false }
        warteschlange.add(scan); return true
    }

    /** Nimmt einen Fund an. Rueckgabe: Ereignis fuer /shelly/event (Taste) oder
     *  null; sofortSenden sagt, ob die Warteschlange gleich raus soll. */
    class Ergebnis(val ereignis: JSONObject? = null, val sofortSenden: Boolean = false)

    fun fund(f: Fund, jetzt: Long): Ergebnis {
        val ib = f.apple?.let { iBeacon(it) }
        if (ib != null && ib.uuid == CALIB_UUID) {
            val k = "${ib.major}:${ib.minor}"
            val e = kalib.getOrPut(k) { intArrayOf(0, 0, ib.txpower) }
            e[0] += f.rssi; e[1]++
            return Ergebnis()
        }
        val mac = f.mac.uppercase()
        val mk = macKey(mac)
        var istUuid = false
        var irk = ""
        var key = mk
        if (mk !in bekannt) {
            if (ib != null && ib.uuid in bekanntUuid) { istUuid = true; key = ib.uuid }
            else { irk = irkFuer(mac) ?: return Ergebnis(); key = "irk:$irk" }
        }
        val d = geraete.getOrPut(key) { Geraet(mac = mac, istUuid = istUuid, irk = irk) }
        d.gesehen = jetzt; d.mac = mac; zuletztErkannt = jetzt
        if (istUuid && ib != null) d.uuid = ib.uuid
        val bth = f.btHome?.let { btHome(it) }
        if (bth != null && bth.pid >= 0) {
            if (letztePid[key] == bth.pid) return Ergebnis()
            letztePid[key] = bth.pid
        }
        if (bth != null && bth.battery in 0..100) d.batterie = bth.battery
        if (d.batterie < 0) f.eddystone?.let { eddystoneBatterie(it) }?.takeIf { it >= 0 }?.let { d.batterie = it }
        var ereignis: JSONObject? = null
        if (bth != null && bth.button >= 1) {
            ereignis = JSONObject().put("mac", mac)
                .put("event", if (bth.button in 1..4) TASTEN[bth.button] else "unknown")
                .put("rssi", f.rssi).put("pid", bth.pid).put("timestamp", jetzt)
        }
        val warAus = !d.online
        d.online = true
        val scan = JSONObject().put("address", mac).put("rssi", f.rssi).put("is_online", 1).put("local_name", "")
        if (d.batterie >= 0) scan.put("battery", d.batterie)
        if (irk.isNotEmpty()) scan.put("irk", irk)
        if (istUuid && ib != null) {
            scan.put("ibeacon_uuid", ib.uuid).put("ibeacon_major", ib.major)
                .put("ibeacon_minor", ib.minor).put("ibeacon_txpower", ib.txpower)
        }
        if (warAus) {
            dazu(scan); d.gemeldet = jetzt
            return Ergebnis(ereignis, true)
        }
        if (jetzt - d.gemeldet >= scanIntervall) { dazu(scan); d.gemeldet = jetzt }
        return Ergebnis(ereignis, false)
    }

    /** Alle offline melden, die laenger als offlineNach nicht gesehen wurden;
     *  lange Vermisste vergessen. */
    fun pruefeOffline(jetzt: Long) {
        val weg = ArrayList<String>()
        for ((k, d) in geraete) {
            val alter = jetzt - d.gesehen
            if (d.online && alter >= offlineNach) {
                d.online = false; d.gemeldet = jetzt
                val s = JSONObject().put("address", d.mac).put("rssi", -100).put("is_online", 0).put("local_name", "")
                if (d.istUuid && d.uuid.isNotEmpty()) s.put("ibeacon_uuid", d.uuid)
                if (d.irk.isNotEmpty()) s.put("irk", d.irk)
                dazu(s)
            }
            if (!d.online && alter >= offlineNach * 3L) weg.add(k)
        }
        weg.forEach { geraete.remove(it); letztePid.remove(it) }
    }

    /** Nach dem Start einmal: alle Bekannten, die nie auftauchten, offline melden. */
    fun meldeNieGesehene() {
        for (mk in bekannt) if (mk !in geraete)
            dazu(JSONObject().put("address", mk).put("rssi", -100).put("is_online", 0).put("local_name", ""))
        for (uu in bekanntUuid) if (uu !in geraete)
            dazu(JSONObject().put("address", uu.replace("-", "")).put("rssi", -100).put("is_online", 0)
                .put("local_name", "").put("ibeacon_uuid", uu))
    }

    fun nimmWarteschlange(): List<JSONObject> { val l = ArrayList(warteschlange); warteschlange.clear(); return l }

    /** Mittelwerte der Kalibrier-Beacons seit dem letzten Abruf. */
    fun nimmKalibrierung(): List<JSONObject> {
        val out = kalib.map { (k, e) ->
            val (major, minor) = k.split(":").map { it.toInt() }
            val avg = Math.round(e[0].toDouble() / e[1]).toInt()
            JSONObject().put("major", major).put("minor", minor).put("rssi", avg)
                .put("distance", Math.round(Math.pow(10.0, (e[2] - avg) / 25.0) * 100) / 100.0)
        }
        kalib.clear(); return out
    }

    // ---- Werbedaten lesen (wie im Shelly-Skript) ----

    /** Apple-Herstellerdaten OHNE Firmenkennung (Android liefert sie getrennt). */
    fun iBeacon(d: ByteArray): IBeacon? {
        if (d.size < 23 || d[0].toInt() != 0x02 || d[1].toInt() != 0x15) return null
        val sb = StringBuilder()
        for (i in 2 until 18) {
            sb.append("%02x".format(d[i].toInt() and 0xff))
            if (i == 5 || i == 7 || i == 9 || i == 11) sb.append('-')
        }
        fun u(i: Int) = d[i].toInt() and 0xff
        return IBeacon(sb.toString(), (u(18) shl 8) or u(19), (u(20) shl 8) or u(21), d[22].toInt())
    }

    private fun objGroesse(id: Int): Int = when (id) {
        0x04, 0x05, 0x0A, 0x42, 0x4B, 0x4C -> 3
        0x3E, 0x4D, 0x4E, 0x4F, 0x50 -> 4
        0x02, 0x03, 0x06, 0x07, 0x08, 0x0B, 0x0C, 0x0E, 0x12, 0x13, 0x14, 0x3D, 0x40, 0x41,
        0x43, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x51, 0x52 -> 2
        else -> if (id <= 0x53) 1 else -1
    }

    fun btHome(raw: ByteArray): BtHome? {
        if (raw.size < 2 || (raw[0].toInt() and 0x01) != 0) return null
        var pid = -1; var bat = -1; var btn = -1
        var i = 1
        while (i < raw.size) {
            val id = raw[i].toInt() and 0xff; i++
            if (id == 0x53) { if (i >= raw.size) break; i += 1 + (raw[i].toInt() and 0xff); continue }
            val g = objGroesse(id)
            if (g < 0 || i + g > raw.size) break
            if (id == 0x00 || id == 0x01 || id == 0x3A) {
                var v = 0
                for (b in 0 until g) v += (raw[i + b].toInt() and 0xff) shl (b * 8)
                when (id) { 0x00 -> pid = v; 0x01 -> bat = v; else -> btn = v }
            }
            i += g
        }
        return BtHome(pid, bat, btn)
    }

    fun eddystoneBatterie(raw: ByteArray): Int {
        if (raw.size < 4 || (raw[0].toInt() and 0xff) != 0x20) return -1
        val mv = ((raw[2].toInt() and 0xff) shl 8) or (raw[3].toInt() and 0xff)
        if (mv == 0) return -1
        return Math.round((mv - 2000) / 10.0).toInt().coerceIn(0, 100)
    }
}
