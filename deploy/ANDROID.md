# LoxPanel auf Android-Panels und Tablets (ohne Agent)

Der Panel-Agent läuft nur auf Linux. Auf Android übernimmt eine Kiosk-App seine
Aufgaben, und die Visu selbst steuert das Display. Damit eignen sich
Android-Wandpanels, Tablets in einer Wandhalterung und das SONOFF NSPanel Pro
als Anzeigegeräte.

## Was ohne Agent funktioniert

| Funktion | Android mit Kiosk-App | Linux mit Agent |
|---|---|---|
| Visu, Kacheln, Detailseiten, PIN, Weckton | ja | ja |
| Betriebsmodus-Umschaltung, Reload, Goto, Notify | ja, per WebSocket-Push | ja |
| Neu laden gegen Einfrieren (*Auto-Neustart alle (Std.)*, leer = jede Nacht um 3 Uhr) | ja, die Seite lädt sich selbst neu, nur während die Uhr-Seite steht | ja, Chromium-Neustart nach der Zahl, leer nach `RELOAD_HOURS` der kiosk.conf |
| Display aus nach `dpmsOff`, Wecken bei Klingel / Wecker / Notify / Goto | ja, mit Fully Kiosk (JavaScript-Schnittstelle oder Remote Admin) und WallPanel (HTTP) | ja, per DPMS und Backlight |
| Anzeige unter *Displays* mit Name, Typ, Online-Status und Ansicht | ja | ja |
| Ansicht wechseln und neu laden unter *Displays* | ja, per WebSocket-Push | ja |
| Display aus/an unter *Displays* oder per HTTP (`/api/display`) | ja, mit Fully Kiosk und WallPanel | nein, der Agent regelt das selbst |
| Fernstart / Stopp des Kiosks unter *Displays* | nein, das macht die Kiosk-App | ja |
| Installationsskript | nein, Kiosk-App von Hand einrichten | ja |

Für die Display-Steuerung gibt es zwei Wege, die sich ergänzen:

1. **Aus der Seite heraus** über die JavaScript-Schnittstelle der Kiosk-App.
   Das kann derzeit Fully Kiosk Browser (`window.fully`). Kein weiteres Setup
   außer dem Schalter in Fully.
2. **Vom Server aus** über die HTTP-Schnittstelle der Kiosk-App, den
   sogenannten Display-Treiber. Er wird je Gerät unter *Geräte* in der
   Karte des Geräts, Teil *Display-Steuerung*, eingetragen (Treiber, IP,
   Port, bei Fully das Passwort). Damit schaltet der Server das Display auch,
   wenn die Seite gerade nicht läuft, und WallPanel wird voll unterstützt.
   Meldet die Seite Leerlauf, schaltet der Server über den Treiber aus;
   Klingel, Wecker, Notify und Goto schalten ein.

In einem normalen Browser ohne Kiosk-App und ohne Treiber bleibt es beim
Screensaver mit Uhr.

## Fully Kiosk Browser einrichten

Fully Kiosk Browser gibt es im Play Store und als APK vom Hersteller. Die
JavaScript-Schnittstelle und die Fernverwaltung brauchen die kostenpflichtige
PLUS-Lizenz (einmalig pro Gerät), ohne sie läuft die Visu trotzdem, nur ohne
Display-Steuerung.

1. **Start-URL** setzen:
   `http://<server-ip>:8099/?panel=<profil-id>&device=<gerätename>`
   Der Gerätename ist frei wählbar und erscheint unter *Displays*.
   Ohne `panel=` startet das Profil `default`.
2. **JavaScript-Schnittstelle aktivieren:** *Advanced Web Settings → Enable
   JavaScript Interface (PLUS)*. Ohne diesen Schalter gibt es kein
   `window.fully`, und die Seite kann das Display nicht schalten.
3. **Eigene Bildschirm-Timer von Fully abschalten**, damit sich beide nicht in
   die Quere kommen: *Device Management → Screen Off Timer* auf 0, *Keep Screen
   On* einschalten. Die Abschaltzeit kommt aus dem Panel-Profil
   (*Konfigurator → Darstellung → Display aus nach*).
4. **Aufwachen durch Berühren:** In Fully unter *Device Management* den Modus
   wählen, bei dem ein Tippen den Bildschirm wieder einschaltet (bei vielen
   Geräten die weiche Abschaltung, nicht *Real Screen Off*). Klingel, Wecker,
   Notify und Goto schalten das Display zusätzlich aus der Seite heraus ein.
5. **Autostart:** *Device Management → Launch on Boot*.
6. **Ton:** *Web Content Settings → Autoplay Videos/Audio* erlauben, sonst
   bleibt der Weckton stumm.
7. **Kiosk-Modus** mit PIN sperren, damit niemand die App verlässt.

Die Bezeichnungen der Einstellungen können je nach Fully-Version leicht
abweichen.

## Gerät benennen und steuern

Ein Gerät bekommt unter *Geräte* eine eigene Karte, sobald es die Visu mit
`?device=<name>` öffnet. Fehlt die Kennung in der URL, steht das Gerät dort
unter „Ohne Kennung" mit seiner IP. Dort einen Namen eintragen und „Namen
vergeben" klicken: Die Visu merkt sich den Namen im Browser und verbindet sich
neu, ab dann ist das Gerät dauerhaft gelistet und per Betriebsmodus schaltbar.
Der Name bleibt auch ohne `?device=` in der URL erhalten, solange die
Browserdaten der Kiosk-App nicht gelöscht werden.

Je Gerät gibt es in der Liste: Ansicht wechseln (Profil wählen, Browser lädt
sich neu), Neu laden, und bei Fully Kiosk „Display aus" / „Display an". Das
Display lässt sich auch aus Loxone oder einem Skript schalten:

```
GET http://<server-ip>:8099/api/display?on=0&device=<name>   # aus
GET http://<server-ip>:8099/api/display?on=1&device=<name>   # an
GET http://<server-ip>:8099/api/display?on=0                 # alle Panels
```

`device=` oder `panel=` grenzen ein, ohne Filter sind alle offenen Visus
gemeint. Die Antwort nennt, wie viele Verbindungen erreicht wurden.

## Fully Kiosk vom Server aus steuern (Remote Admin)

Alternativ oder zusätzlich zur JavaScript-Schnittstelle: In Fully unter *Remote
Administration (PLUS)* die Fernverwaltung einschalten und ein Passwort setzen.
Dann in LoxPanel unter *Geräte* die Karte des Geräts aufklappen und unter
*Display-Steuerung* den Display-Treiber „Fully Kiosk (Remote Admin)" wählen, IP des
Geräts, Port 2323 und das Passwort eintragen, speichern. Der Server ruft dann
`http://<ip>:2323/?cmd=screenOn` bzw. `screenOff` auf.

## WallPanel

WallPanel ist quelloffen, kostenlos und auf F-Droid verfügbar. Es hat keine
JavaScript-Schnittstelle in der Seite, dafür einen HTTP-Server. Einrichtung:

1. In WallPanel unter *Einstellungen → HTTP* den Server einschalten (Port
   2971) und unter *Bildschirmschoner* die gewünschte Abschaltung nach
   Inaktivität wählen (Dimmen oder Schwarz).
2. Start-URL wie oben mit `?panel=&device=` eintragen.
3. In LoxPanel beim Gerät den Display-Treiber „WallPanel (HTTP)" mit IP und
   Port 2971 eintragen.

Der Server schickt `{"wake": true}` zum Einschalten und `{"wake": false}`
nach der Abschaltzeit. Letzteres gibt den Bildschirmschoner von WallPanel
frei, der dann nach seiner eigenen Inaktivitätszeit greift. Ein sofortiges
Abschalten kennt WallPanel nicht.

## Display nach Präsenzmelder

Statt nach fester Leerlaufzeit kann ein Präsenzmelder aus Loxone das Display
steuern: Solange er jemanden meldet, bleibt es hell, und die Leerlaufzeit ist
ausgesetzt. Wird der Raum leer, geht es aus, kommt jemand, geht es wieder an.

1. Das Gerät braucht eine Kennung (`?device=<name>`, siehe oben) und eine der
   Display-Steuerungen: die JavaScript-Schnittstelle von Fully Kiosk, Fully
   Remote Admin oder WallPanel.
2. In LoxPanel unter *Geräte* die Karte des Geräts aufklappen und unter
   „Präsenzmelder" den Baustein wählen und speichern. Zur
   Auswahl stehen alle Bausteine mit einem Zustand „aktiv", neben dem
   Präsenzmelder also auch Schalter oder digitale Statusbausteine – nützlich,
   wenn die Anwesenheit in Loxone erst über eine Logik entsteht.
3. Neben der Auswahl steht der aktuelle Stand („gerade: jemand da" bzw.
   „gerade: Raum leer"). So lässt sich die Kopplung prüfen, ohne vor dem
   Panel zu stehen.

Wie lange das Display nach dem Verlassen des Raums noch an bleibt, bestimmt
die Nachlaufzeit des Präsenzmelders in Loxone Config. Eine Berührung weckt
ein dunkles Display weiterhin, danach gilt wieder die Leerlaufzeit, bis der
Melder erneut jemanden sieht. Bei WallPanel gibt „Raum leer" wie oben nur den
Bildschirmschoner frei. Linux-Panels mit Agent steuern ihr Display selbst,
dort wirkt der Präsenzmelder nicht.

## Geräte

- **Android-Wandpanels** (4 Zoll, 480×480, PoE, Unterputz) von deutschen
  Händlern: Fully Kiosk installieren, fertig. Das ist das Format, für das die
  Visu entworfen wurde.
- **Tablets** in einer Wandhalterung: größer, günstig, überall erhältlich. Das
  4×3-Kachel-Layout und *Bildschirm füllen* im Panel-Profil nutzen den Platz.
  Hochkant aufgehängt liegen Visu und Zusatzfläche übereinander statt
  nebeneinander, Tabs ohne Zusatzfläche bekommen doppelt so viele Zeilen, und
  die Uhr-Seite zeigt ihre zweite Fläche unter Uhr und Wetter. Die Ausrichtung
  in Fully Kiosk fest einstellen (*Screen Orientation* unter *Device
  Management*), sonst dreht die Anzeige mit dem Lagesensor.
- **SONOFF NSPanel Pro:** Android, unterstützt F-Droid ab Firmware 4.0. Für
  Fully Kiosk ist meist der Entwicklermodus und ADB nötig, was die Garantie
  berührt. Zigbee, Matter und Relais des Geräts bleiben mit Loxone ungenutzt.

## Start-URL aus dem Konfigurator

Unter *Geräte → ＋ Gerät einrichten*, Schritt *Gerät* → *Neues Gerät
verbinden* → *Start-Adresse oder Agent*, gibt es für Android-Geräte einen
Generator: Gerätename und Startansicht wählen, „Start-URL erzeugen", kopieren
und in die Kiosk-App eintragen. Sobald sich das Gerät meldet, steht es im
selben Schritt zur Wahl und der Assistent führt weiter bis zur Ansicht.

## Testen ohne Kauf

Jedes vorhandene Android-Handy oder -Tablet mit Fully Kiosk reicht, um den
Ablauf zu prüfen: Start-URL eintragen, JavaScript-Schnittstelle einschalten,
im Konfigurator *Display aus nach* auf 30 Sekunden setzen. Nach 30 Sekunden
ohne Berührung muss der Bildschirm ausgehen; ein `GET
http://<server-ip>:8099/api/notify?device=<gerätename>&text=Hallo` muss ihn
wieder einschalten.
