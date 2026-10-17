"""Die Routen-Handler des Servers, ein Modul je Thema: oberflaeche (Dateien der
Oberflaeche), visu (WebSocket /ws), konfigurator, einstellungen, intercom,
geraete (Geraete und Agenten), medien (Icons, Cover, Klingelbilder) und system
(/api/health, /api/diagnose); gemeinsam.py haelt, was mehrere davon brauchen.

main() in webvisu.py importiert die Handler und traegt sie in die
Routentabelle ein. Die Module importieren webvisu nicht (App nur als
Typangabe unter TYPE_CHECKING, tests/test_schichten.py)."""
