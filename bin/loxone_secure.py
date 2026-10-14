"""Verschluesselte Befehle an den Miniserver ("Command Encryption", ab 8.1).

Manche Antworten gibt der Miniserver nur auf eine verschluesselte Anfrage
heraus, weil sie Zugangsdaten enthalten, etwa die gesicherten Details einer
Intercom (jdev/sps/io/{uuid}/securedDetails: Kamera- und SIP-Zugang). Ablauf
laut "Communicating with the Miniserver" (16.0), Abschnitt Command Encryption,
Variante fuer HTTP-Anfragen:

  1. jdev/sys/getPublicKey -> RSA-Schluessel des Miniservers. Er kommt als PEM
     mit der Beschriftung CERTIFICATE, enthaelt aber nur den oeffentlichen
     Schluessel (SubjectPublicKeyInfo).
  2. "salt/{salt}/{cmd}" mit AES-256-CBC verschluesseln, aufgefuellt mit
     Nullbytes, Base64 ohne Umbruch, URI-kodiert -> {chiffre}
  3. "{key}:{iv}" (hex) mit RSA PKCS#1 v1.5 verschluesseln, Base64, URI-kodiert
     -> {sitzungsschluessel}
  4. jdev/sys/fenc/{chiffre}?sk={sitzungsschluessel}. Mit fenc verschluesselt
     der Miniserver auch die Antwort (Base64, derselbe Schluessel und IV), die
     Zugangsdaten gehen also in keiner Richtung im Klartext uebers Netz.

Die Anmeldung steckt im verschluesselten Befehl selbst: "?autht={hash}&user=
{user}" (Abschnitt Authenticating using tokens), der Hash ist das Token als
HMAC mit dem Schluessel aus jdev/sys/getkey.
Benoetigt das Paket `cryptography` (requirements.txt).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from urllib.parse import quote

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding as _apadding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAVE_CRYPTO = True
except ImportError:            # Server laeuft weiter, nur ohne verschluesselte Befehle
    HAVE_CRYPTO = False

AES_BLOCK = 16
# Zufallssalz vor dem Befehl ("salt/{salt}/{cmd}"); die Doku nennt 2 Byte als Beispiel
SALZ_BYTES = 2
_PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----(?P<b64>.*?)-----END [A-Z ]+-----", re.S)


@dataclass(frozen=True)
class Verschluesselt:
    """Ein verschluesselter Befehl: der Pfad fuer die Anfrage und Schluessel
    und IV, mit denen die Antwort (fenc) zu entschluesseln ist."""
    pfad: str
    key: bytes
    iv: bytes


def public_key_from_pem(text) -> "object | None":
    """RSA-Schluessel aus der Antwort auf jdev/sys/getPublicKey. Der Miniserver
    liefert ihn als PEM mit der Beschriftung CERTIFICATE, der Inhalt ist aber ein
    SubjectPublicKeyInfo; ein echtes Zertifikat wird ebenso angenommen.
    None, wenn der Text keinen Schluessel enthaelt."""
    if not HAVE_CRYPTO or not isinstance(text, str):
        return None
    m = _PEM_RE.search(text)
    try:
        der = base64.b64decode("".join((m.group("b64") if m else text).split()), validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        return serialization.load_der_public_key(der)
    except ValueError:
        pass
    try:
        return x509.load_der_x509_certificate(der).public_key()
    except ValueError:
        return None


def token_hash(key_hex: str, token: str, hash_alg: str = "SHA1") -> str:
    """Token als HMAC mit dem Schluessel aus jdev/sys/getkey (hex), wie bei der
    Anmeldung ueber den WebSocket (loxone_ws). hash_alg aus getkey2."""
    digest = hashlib.sha256 if str(hash_alg).upper() == "SHA256" else hashlib.sha1
    return hmac.new(bytes.fromhex(key_hex), token.encode("utf-8"), digest).hexdigest()


def _aes(key: bytes, iv: bytes):
    return Cipher(algorithms.AES(key), modes.CBC(iv))


def encrypt_command(cmd: str, public_key) -> Verschluesselt:
    """cmd (etwa "jdev/sps/io/{uuid}/securedDetails?autht=...&user=...") als
    jdev/sys/fenc-Befehl verschluesseln."""
    if not HAVE_CRYPTO:
        raise RuntimeError("Paket 'cryptography' fehlt")
    key, iv = os.urandom(32), os.urandom(AES_BLOCK)
    # Nullbyte als Ende des Befehls, dann mit Nullbytes auf die Blockgroesse:
    # so endet der Text auch dann sauber, wenn er die Bloecke genau fuellt.
    klar = f"salt/{os.urandom(SALZ_BYTES).hex()}/{cmd}".encode("utf-8") + b"\0"
    klar += b"\0" * (-len(klar) % AES_BLOCK)
    enc = _aes(key, iv).encryptor()
    chiffre = base64.b64encode(enc.update(klar) + enc.finalize()).decode("ascii")
    sitzung = public_key.encrypt(f"{key.hex()}:{iv.hex()}".encode("ascii"), _apadding.PKCS1v15())
    sk = base64.b64encode(sitzung).decode("ascii")
    return Verschluesselt(f"jdev/sys/fenc/{quote(chiffre, safe='')}?sk={quote(sk, safe='')}", key, iv)


def decrypt_response(body, key: bytes, iv: bytes) -> str:
    """Antwort auf einen fenc-Befehl (Base64 des AES-verschluesselten Textes)
    entschluesseln. Wirft ValueError, wenn sie sich nicht entschluesseln laesst."""
    if not HAVE_CRYPTO:
        raise RuntimeError("Paket 'cryptography' fehlt")
    if isinstance(body, bytes):
        body = body.decode("ascii", "replace")
    try:
        roh = base64.b64decode("".join(str(body).split()).strip('"'), validate=True)
    except (binascii.Error, ValueError) as err:
        raise ValueError("Antwort ist kein Base64") from err
    if not roh or len(roh) % AES_BLOCK:
        raise ValueError("Antwort hat keine ganzen AES-Bloecke")
    dec = _aes(key, iv).decryptor()
    klar = (dec.update(roh) + dec.finalize()).rstrip(b"\0")
    try:
        return klar.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ValueError("Antwort laesst sich nicht entschluesseln") from err
