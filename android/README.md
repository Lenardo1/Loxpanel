# LoxPanel — Chaquopy-Machbarkeits-Spike (Android)

Beantwortet **eine** Frage: Läuft der LoxPanel-Server (Python) eingebettet in einer
Android-App? Konkret werden auf dem Gerät geprüft:

1. `cryptography` importieren **und** eine native AES-GCM-Operation ausführen
2. `aiohttp` importieren
3. `loxone-api` importieren
4. einen echten `aiohttp`-Server auf `127.0.0.1:8099` starten und lokal abfragen

Das Ergebnis erscheint als PASS/FAIL-Liste direkt auf dem App-Bildschirm.
Kein UI-Framework, kein WebView — nur der Tragfähigkeits-Test.

## Voraussetzungen (hast du durch thermobreeze schon)
- Android SDK: `C:\Users\Lenar\AppData\Local\Android\sdk`
- JDK 17 (kommt mit Android Studio / Flutter JBR)
- Ein **echtes Android-Tablet** (arm64) per USB, Entwickleroptionen + USB-Debugging an
  (der Emulator ginge auch, dann zählt der `x86_64`-ABI).

## Bauen & Starten — einfachster Weg: Android Studio
1. Android Studio → **File ▸ Open** → diesen Ordner (`loxpanel-android-spike`) wählen.
2. Beim ersten Sync bietet Studio an, den **Gradle-Wrapper** zu erzeugen → zulassen.
   (Diese Vorlage enthält absichtlich **keine** `gradle-wrapper.jar` — die ist binär.
   Alternativ auf der Kommandozeile einmalig: `gradle wrapper --gradle-version 8.7`.)
3. Tablet auswählen → **Run ▶**. Der erste Build lädt die Python-Wheels (dauert).
4. Auf dem Tablet erscheint die Ergebnisliste.

## Was das Ergebnis bedeutet
- **Alle vier OK** → Android-Variante ist grundsätzlich bestätigt; der Rest
  (WebView-Kiosk, Foreground-Service, Android-Display-Steuerung statt Agent) ist Fleißarbeit.
- **`cryptography` FAIL** → der erwartete Knackpunkt. Dann Optionen: andere
  Chaquopy-Version, Krypto-Nutzung im Server kapseln/ersetzen, oder Krypto-Feature
  (Audioserver-Login) auf Android optional machen.
- **`loxone-api` FAIL** → meist nur der Import-Name; im Test sind mehrere Namen
  hinterlegt. Zur Not das Paket weglassen — es ist reines Python auf aiohttp.

## Version und Release-Signierung
Die App übernimmt die Release-Version des Projekts aus
`loxberry-plugin/plugin.cfg` (`VERSION=x.y.z` → `versionName` x.y.z,
`versionCode` x·10000 + y·100 + z). Gebaut wird darum immer `android/` im
Repo-Checkout, nicht eine Kopie des Ordners. Der Workflow prüft, dass ein
Release-Tag zur Version passt (`v0.6.0` ↔ `VERSION=0.6.0`).

Welcher Stand in einer APK steckt, schreibt `syncLoxpanelAssets` nach
`bin/version.json` (Version, Commit, Bauzeit); der Konfigurator zeigt es in der
Seitenleiste, Android unter App-Info (`versionName` „0.6.0 (abc1234)“). Den
Commit nimmt der Build aus `LOXPANEL_COMMIT` oder, wenn die fehlt, aus Git. Wer
aus einem Export ohne `.git` baut (`git archive`), setzt `LOXPANEL_COMMIT`.

Release-APKs tragen immer denselben Schlüssel. Nur dann installiert Android ein
Update über die vorhandene App. Mit einem anderen Schlüssel müsste man sie erst
deinstallieren, und das löscht ihre Konfiguration samt Miniserver-Zugang.

Einmalig einrichten:
1. Schlüssel erzeugen und sicher aufbewahren (Passwort-Manager, Backup):
   `keytool -genkeypair -keystore loxpanel.jks -alias loxpanel -keyalg RSA -keysize 4096 -validity 36500`
2. Die Datei als Base64-Text ausgeben, unter Linux/macOS mit
   `base64 -w0 loxpanel.jks`, unter Windows (PowerShell) mit
   `[Convert]::ToBase64String([IO.File]::ReadAllBytes("loxpanel.jks"))`.
3. Im Repo unter *Settings → Secrets and variables → Actions* anlegen:

   | Secret | Inhalt |
   |---|---|
   | `LOXPANEL_KEYSTORE_B64` | der Base64-Text aus Schritt 2 |
   | `LOXPANEL_KEYSTORE_PASSWORD` | Passwort des Schlüsselspeichers |
   | `LOXPANEL_KEY_ALIAS` | `loxpanel` (der Alias aus Schritt 1) |
   | `LOXPANEL_KEY_PASSWORD` | Passwort des Schlüssels |

Fehlen die Secrets, bricht der Workflow ab, statt eine nicht aktualisierbare APK
zu veröffentlichen. Er gibt den SHA-256-Fingerabdruck des Zertifikats aus, der
bei jedem Release gleich bleiben muss. Geht der Schlüssel verloren, lässt sich
die App nicht mehr aktualisieren.

Lokal signiert bauen: die vier Werte als Umgebungsvariablen setzen
(`LOXPANEL_KEYSTORE` = Pfad zur `.jks`, die übrigen heißen wie die Secrets) und
`gradle assembleRelease`. Zum Ausprobieren reicht `gradle assembleDebug`, das
braucht keinen Schlüssel.

## Typische Stolpersteine (bewusst offen gelassen — an deiner Toolchain justieren)
- **Versionskonflikt beim Sync**: In `build.gradle.kts` (Root) die drei Plugin-
  Versionen an dein Android Studio anpassen — AGP (`com.android.application`),
  Kotlin, Chaquopy müssen zueinander passen. Aktuell: AGP 8.5.2 / Kotlin 1.9.24 /
  Chaquopy 16.0.0 / Gradle 8.7.
- **"buildPython" nicht gefunden** (Windows): Chaquopy braucht evtl. ein lokales
  Python 3.x auf dem PC (für reine sdists). Dann in `app/build.gradle.kts` im
  `chaquopy { defaultConfig { } }`-Block `buildPython("py", "-3.12")` (oder Pfad
  zur `python.exe`) setzen.
- **ABI**: Für ein ARM-Tablet reicht `arm64-v8a`; `x86_64` nur für Emulator.
  In `app/build.gradle.kts` unter `ndk.abiFilters` reduzieren = schnellerer Build.

## Start-Adresse der Anzeige
Port und Adresse des eingebetteten Servers stehen in `Visu.kt`. Die Anzeige lädt
beim Start die zuletzt angezeigte Visu-Adresse, beim allerersten Start die Visu mit
dem Standardprofil. Wechselt die Ansicht über *Displays* oder die
Betriebsmodus-Automatik, lädt sich die Visu mit neuem `?panel=`. Die App merkt
sich diese Adresse, nach einem Neustart steht also dieselbe Ansicht da. Welche
Adressen als Visu gelten, prüft `gradle testDebugUnitTest`.

## Wenn der Spike grün ist
Nächste Schritte für die echte App (separat, kein Teil dieses Spikes):
- WebView auf `http://127.0.0.1:8099/?panel=...&device=...`
- Server als **Foreground-Service** (dauerhafte Notification) statt in der Activity
- Display-Steuerung über Android-APIs (Brightness/WakeLock) statt des Linux-Agents
- LoxPanel-Code (`bin/`, `webfrontend/`, `config/`) als Python-Assets bündeln

## Schnittstelle zur Visu (`LoxKiosk`)
Die App hängt das Objekt `LoxKiosk` in die WebView. Die Visu erkennt es wie
`window.fully` von Fully Kiosk und meldet sich beim Server mit `kiosk=loxpanel`.
Unter *Displays* erscheint das Gerät dann als „LoxPanel-App“, mit „Display aus“
und „Display an“.

| Funktion | Wer ruft sie | Wirkung in der App |
|---|---|---|
| `setDisplayOff(sekunden)` | Visu beim Laden der Einstellungen (`dpmsOff`) und wenn der Präsenzmelder des Geräts wechselt | Leerlaufzeit bis zum Bildschirmschoner, `0` schaltet ihn ab |
| `setDisplayBrightness(prozent)` | Visu im Nachtmodus (*Nachts abdunkeln*) und beim Aufhellen per Berührung | Helligkeit in Prozent der eingestellten Systemhelligkeit, `100` = unverändert; `false` bei automatischer Helligkeit, dann dunkelt die Visu selbst ab |
| `turnScreenOn()` | Visu bei Klingel, Wecker, Notify, Goto und wenn der Server das Display einschaltet | Schoner weg, Leerlaufzeit beginnt neu |
| `turnScreenOff()` | Visu, wenn der Server das Display abschaltet (*Displays*, `/api/display`) | Schoner an |
| `isScreenOn()` | Visu vor `turnScreenOn()` | `true`, solange kein Schoner zu sehen ist |

Die drei letzten heißen wie bei Fully Kiosk, damit die Visu beide Apps gleich
behandelt.

Hat das Gerät unter *Displays* einen Präsenzmelder, gibt die Visu der App
`setDisplayOff(0)`, solange er jemanden meldet: Der Schoner wartet, bis der
Raum leer ist. Dann bekommt die App wieder die eingestellte Leerlaufzeit und
gleich `turnScreenOff()`; kommt jemand, `turnScreenOn()`.

Nachts senkt die Visu über `setDisplayBrightness` die echte Helligkeit, statt
eine dunkle Fläche über sich zu legen. Schwarz leuchtet dann nicht mehr grau.
Sie rechnet „Nachts abdunkeln“ so um, dass die Leuchtdichte dieselbe ist wie
mit der Fläche: 70 % abdunkeln ergibt 7 % der eingestellten Helligkeit. Die
App setzt nur die Helligkeit ihres Fensters, die Einstellung des Geräts
bleibt. Bei automatischer Helligkeit kennt sie die tatsächliche Helligkeit
nicht und lehnt ab; dann dunkelt die Visu wie im Browser ab.
