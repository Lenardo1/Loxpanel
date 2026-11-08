"""Gegensprechen fuer Displays im Netz (intercom_geraete, SipCall media_host,
Routen /api/intercom/talk/* und /api/intercom/geraete).

Start im Repo:  python -m pytest tests/test_gegensprechen_netz.py
Braucht aiohttp, pytest und pytest-aiohttp."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import intercom_geraete as G  # noqa: E402
import sip_call  # noqa: E402
from routen import intercom as R  # noqa: E402
from intercom_talk import IntercomTalk  # noqa: E402

SCHLUESSEL = "a" * 64
ANDERER = "b" * 64


@pytest.fixture
def cfg(monkeypatch):
    """loxpanel.cfg im Speicher statt auf der Platte."""
    speicher: dict = {"miniserver": {"host": "x"}}
    monkeypatch.setattr(G, "_load_cfg", lambda: __import__("copy").deepcopy(speicher))
    monkeypatch.setattr(G, "_write_cfg", lambda c: (speicher.clear(), speicher.update(c)))
    return speicher


# ---- intercom_geraete ----

def test_unbekannter_schluessel_wartet_und_nur_hash_gespeichert(cfg):
    assert G.pruefen(SCHLUESSEL, "10.0.0.5", "X2i") == G.WARTET
    assert not G.ist_frei(SCHLUESSEL)
    assert SCHLUESSEL not in str(cfg)
    (e,) = G.liste()
    assert e["status"] == G.WARTET and e["ip"] == "10.0.0.5" and e["name"] == "X2i"
    assert cfg["miniserver"] == {"host": "x"}   # andere Abschnitte bleiben


def test_freigeben_sperren_entfernen(cfg):
    G.pruefen(SCHLUESSEL, "10.0.0.5")
    kid = G.liste()[0]["id"]
    assert G.setzen(kid, "freigeben") and G.ist_frei(SCHLUESSEL)
    assert G.pruefen(SCHLUESSEL, "10.0.0.6") == G.FREI
    assert not G.ist_frei(ANDERER)
    assert G.setzen(kid, "sperren") and not G.ist_frei(SCHLUESSEL)
    assert G.setzen(kid, "entfernen") and G.liste() == []
    assert not G.setzen(kid, "freigeben")
    assert not G.setzen("zzz", "freigeben")


def test_wartende_sind_begrenzt_freigegebene_bleiben(cfg):
    G.pruefen(SCHLUESSEL, "10.0.0.5")
    G.setzen(G.liste()[0]["id"], "freigeben")
    for i in range(G.WARTEND_MAX + 5):
        G.pruefen(f"{i:064d}", "10.0.0.9")
    stati = [e["status"] for e in G.liste()]
    assert stati.count(G.WARTET) == G.WARTEND_MAX and stati.count(G.FREI) == 1


@pytest.mark.parametrize("roh,erwartet", [
    ("10.10.5.237", "10.10.5.237"), ("::ffff:192.168.1.4", "192.168.1.4"),
    ("127.0.0.1", None), ("::1", None), ("fe80::1", None), ("", None), (None, None), ("0.0.0.0", None)])
def test_ton_adresse(roh, erwartet):
    assert G.ton_adresse(roh) == erwartet


def test_schluesselformat():
    assert G.gueltiger_schluessel(SCHLUESSEL)
    assert not G.gueltiger_schluessel("kurz")
    assert not G.gueltiger_schluessel("a" * 63 + "\n")
    assert not G.gueltiger_schluessel(None)


# ---- SipCall: SDP nennt das Display ----

class _Tuerstation(asyncio.DatagramProtocol):
    """Antwortet auf INVITE mit 200 OK und SDP, auf BYE mit 200 OK."""
    def __init__(self):
        self.invite_sdp = ""

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        text = data.decode()
        methode = text.split(" ", 1)[0]
        kopf = {}
        for zeile in text.split("\r\n")[1:]:
            if not zeile:
                break
            name, _, wert = zeile.partition(":")
            kopf[name.strip().lower()] = wert.strip()
        if methode == "ACK":
            return
        port = self.transport.get_extra_info("sockname")[1]
        rumpf = ""
        zeilen = ["SIP/2.0 200 OK", f"Via: {kopf['via']}", f"From: {kopf['from']}",
                  f"To: {kopf['to']};tag=tuer1", f"Call-ID: {kopf['call-id']}", f"CSeq: {kopf['cseq']}",
                  f"Contact: <sip:105@127.0.0.1:{port}>"]
        if methode == "INVITE":
            self.invite_sdp = text.split("\r\n\r\n", 1)[1]
            rumpf = ("v=0\r\no=2N 1 1 IN IP4 127.0.0.1\r\ns=-\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\n"
                     "m=audio 40000 RTP/AVP 8\r\na=rtpmap:8 PCMA/8000\r\na=ptime:20\r\na=sendrecv\r\n")
            zeilen.append("Content-Type: application/sdp")
        zeilen += [f"Content-Length: {len(rumpf)}", "", rumpf]
        self.transport.sendto("\r\n".join(zeilen).encode(), addr)


async def _tuerstation():
    loop = asyncio.get_running_loop()
    transport, tuer = await loop.create_datagram_endpoint(_Tuerstation, local_addr=("127.0.0.1", 0))
    return transport, tuer, transport.get_extra_info("sockname")[1]


@pytest.mark.parametrize("media_host", [None, "10.10.5.237"])
async def test_sdp_nennt_display_oder_eigenes_geraet(media_host):
    transport, tuer, port = await _tuerstation()
    try:
        call = sip_call.SipCall(f"127.0.0.1:{port}", "105", "", 41000, timeout=3, media_host=media_host)
        media = await call.start()
        assert call.state == "connected" and media["remotePort"] == 40000
        c = re.search(r"c=IN IP4 (\S+)", tuer.invite_sdp).group(1)
        assert c == (media_host or "127.0.0.1")
        assert "m=audio 41000 " in tuer.invite_sdp
        await call.stop()
    finally:
        transport.close()


async def test_ungueltige_ton_adresse():
    call = sip_call.SipCall("127.0.0.1:5060", "105", "", 41000, timeout=1, media_host="kein-ip")
    with pytest.raises(ValueError, match="Audioadresse"):
        await call.start()


# ---- Routen ----

class _FakeTalk:
    def __init__(self):
        self.aufrufe = []

    async def start(self, session, uuid, port, media_host=None):
        self.aufrufe.append(("start", session, uuid, port, media_host))
        return {"ok": True, "session": session, "uuid": uuid, "state": "connecting", "message": ""}

    def status(self, session):
        return {"ok": True, "session": session, "uuid": "", "state": "idle", "message": ""}

    async def stop(self, session):
        self.aufrufe.append(("stop", session))
        return {"ok": True, "session": session, "uuid": "", "state": "idle", "message": ""}


class _FakeApp:
    def __init__(self):
        self.controls = {"ic1": {"type": "Intercom"}}
        self.intercom_talk = _FakeTalk()

    def device_list(self):
        return {"devices": [{"name": "X2i", "ip": "127.0.0.1"}]}


@pytest.fixture
async def client(aiohttp_client, cfg, monkeypatch):
    app = web.Application()
    fake = _FakeApp()
    app["app"] = fake
    app.router.add_post("/api/intercom/talk/start", R.api_intercom_talk_start)
    app.router.add_get("/api/intercom/talk/status", R.api_intercom_talk_status)
    app.router.add_post("/api/intercom/talk/stop", R.api_intercom_talk_stop)
    app.router.add_get("/api/intercom/geraete", R.api_intercom_geraete)
    app.router.add_post("/api/intercom/geraete", R.api_intercom_geraete)
    # Der Testclient kommt ueber Loopback; so tut er, als kaeme er aus dem Heimnetz
    monkeypatch.setattr(G, "ton_adresse", lambda remote: "10.10.5.237")
    monkeypatch.delenv("LOXPANEL_INTERCOM_TOKEN", raising=False)
    c = await aiohttp_client(app)
    c.fake = fake
    return c


START = {"session": "s" * 20, "uuid": "ic1", "rtpPort": 41000}


async def test_ohne_schluessel_kein_gespraech(client):
    r = await client.post("/api/intercom/talk/start", json=START)
    assert r.status == 403 and "LoxPanel-App" in (await r.json())["message"]
    assert client.fake.intercom_talk.aufrufe == []


async def test_erst_freigabe_dann_ton_an_das_display(client):
    kopf = {G.KOPF: SCHLUESSEL}
    r = await client.post("/api/intercom/talk/start", json=START, headers=kopf)
    assert r.status == 403 and "freigegeben" in (await r.json())["message"]
    r = await client.get("/api/intercom/talk/status?session=" + "s" * 20, headers=kopf)
    assert r.status == 403

    liste = (await (await client.get("/api/intercom/geraete")).json())["geraete"]
    assert len(liste) == 1 and liste[0]["status"] == G.WARTET
    r = await client.post("/api/intercom/geraete", json={"id": liste[0]["id"], "aktion": "freigeben"})
    assert r.status == 200

    r = await client.post("/api/intercom/talk/start", json=START, headers=kopf)
    assert r.status == 200 and (await r.json())["state"] == "connecting"
    assert client.fake.intercom_talk.aufrufe[-1] == ("start", "s" * 20, "ic1", 41000, "10.10.5.237")
    r = await client.post("/api/intercom/talk/stop", json={"session": "s" * 20}, headers=kopf)
    assert r.status == 200


async def test_eigene_app_unveraendert(client, monkeypatch):
    monkeypatch.setenv("LOXPANEL_INTERCOM_TOKEN", "t" * 40)
    r = await client.post("/api/intercom/talk/start", json=START, headers={"X-LoxPanel-Intercom": "t" * 40})
    assert r.status == 200
    assert client.fake.intercom_talk.aufrufe[-1][-1] is None   # Ton wie bisher an dieses Geraet


async def test_konfigurator_unbekannte_kennung(client):
    r = await client.post("/api/intercom/geraete", json={"id": "0" * 12, "aktion": "freigeben"})
    assert r.status == 404


# ---- IntercomTalk reicht die Adresse an SipCall ----

async def test_intercom_talk_reicht_media_host_weiter():
    erzeugt = []

    class Call:
        def __init__(self, host, user, pw, port, **extra):
            erzeugt.append(extra)
            self.state, self.error, self.media = "connected", "", {}

        async def start(self):
            return {}

        async def stop(self):
            pass

    async def zugang(uuid):
        return {"host": "h", "user": "u", "pass": ""}

    talk = IntercomTalk(zugang, factory=Call)
    await talk.start("s" * 20, "ic1", 41000, "10.10.5.237")
    await asyncio.sleep(0.05)
    await talk.close()
    talk = IntercomTalk(zugang, factory=Call)
    await talk.start("t" * 20, "ic1", 41000)
    await asyncio.sleep(0.05)
    await talk.close()
    assert erzeugt == [{"media_host": "10.10.5.237"}, {}]
