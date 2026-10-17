"""Welcher Stand von LoxPanel laeuft: Version, Commit und Bauzeit.

Die Builds legen bin/version.json neben den Code (die App packt bei jedem
Update genau bin/, webfrontend/ und deploy/ aus):
  - APK: Gradle-Task syncLoxpanelAssets (android/app/build.gradle.kts)
  - Docker: Dockerfile ueber `python bin/version_info.py schreiben [commit]`
  - .deb: packaging/deb/build.sh schreibt die Datei selbst (ohne Python)
Ohne die Datei, also beim Start aus einem Git-Checkout, kommt die Version aus
loxberry-plugin/plugin.cfg (VERSION=x.y.z, dieselbe Quelle wie versionCode der
App) und der Commit aus Git. Ist kein Commit bekannt (lokaler Build mit
`docker compose up --build`, der .git nicht ins Image nimmt; ein entpacktes
Archiv), kennzeichnet `inhalt` den Stand: ein Pruefwert ueber den Code, gleich
bei unveraendertem Code (Neustart, erneuter Build), neu bei jeder Aenderung.
Nur Standardbibliothek.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BIN = Path(__file__).resolve().parent
DATEI = "version.json"
FELDER = ("version", "commit", "gebaut", "inhalt")
# Was den Stand ausmacht, den Visu und Konfigurator vom Server laden (wie im Image)
CODE_ORDNER = ("bin", "webfrontend", "deploy", "agent")
_PLUGIN_CFG = Path("loxberry-plugin") / "plugin.cfg"
_VERSION_RE = re.compile(r"^VERSION=(\d+\.\d+\.\d+)\s*$", re.M)


def projekt_version(root: Path) -> str:
    """VERSION aus loxberry-plugin/plugin.cfg, leer ohne die Datei."""
    try:
        m = _VERSION_RE.search((root / _PLUGIN_CFG).read_text(encoding="utf-8"))
    except OSError:
        return ""
    return m.group(1) if m else ""


def git_commit(root: Path) -> str:
    """Commit des Checkouts (volle Kennung), leer ohne Git."""
    if not (root / ".git").exists():          # in einem Worktree ist .git eine Datei
        return ""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def inhalt_kennung(root: Path) -> str:
    """Pruefwert ueber die Dateien in CODE_ORDNER (Pfad und Inhalt, ohne
    bin/version.json und Python-Caches), leer ohne Code. Haengt nicht von
    Bauzeit oder Dateidatum ab: derselbe Code ergibt dieselbe Kennung."""
    dateien = []
    for ordner in CODE_ORDNER:
        basis = root / ordner
        if basis.is_dir():
            dateien += [f for f in basis.rglob("*") if f.is_file()
                        and "__pycache__" not in f.parts and f.suffix != ".pyc"]
    h, n = hashlib.sha256(), 0
    for f in sorted(dateien, key=lambda f: f.relative_to(root).as_posix()):
        rel = f.relative_to(root).as_posix()
        if rel == f"bin/{DATEI}":
            continue
        try:
            daten = f.read_bytes()
        except OSError:
            continue
        for teil in (rel.encode("utf-8"), daten):
            h.update(len(teil).to_bytes(8, "big"))
            h.update(teil)
        n += 1
    return h.hexdigest()[:16] if n else ""


def lesen(bin_dir: Path = BIN) -> dict:
    """-> {"version", "commit", "gebaut", "inhalt"} (gebaut: UTC, ISO 8601); leere
    Texte, wo nichts bekannt ist. `inhalt` nur ohne Commit (inhalt_kennung)."""
    try:
        d = json.loads((bin_dir / DATEI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if isinstance(d, dict):
        return {k: str(d.get(k) or "") for k in FELDER}
    root = bin_dir.parent
    commit = git_commit(root)
    return {"version": projekt_version(root), "commit": commit, "gebaut": "",
            "inhalt": "" if commit else inhalt_kennung(root)}


def schreiben(bin_dir: Path = BIN, commit: str = "") -> dict:
    """bin/version.json fuer einen Build schreiben; ohne commit der aus Git,
    ohne beides die Kennung des Inhalts."""
    root = bin_dir.parent
    commit = commit.strip() or git_commit(root)
    info = {"version": projekt_version(root), "commit": commit,
            "gebaut": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inhalt": "" if commit else inhalt_kennung(root)}
    (bin_dir / DATEI).write_text(json.dumps(info) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "schreiben":
        sys.exit("Aufruf: python bin/version_info.py schreiben [commit]")
    print(json.dumps(schreiben(commit=sys.argv[2] if len(sys.argv) > 2 else "")))
