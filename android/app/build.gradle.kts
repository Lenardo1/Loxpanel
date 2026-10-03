plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Version der App = Release-Version des Projekts. Sie steht in
// loxberry-plugin/plugin.cfg (VERSION=x.y.z) und wird bei jedem Release
// hochgezählt. versionCode muss bei jedem Update steigen: x*10000 + y*100 + z.
val projektVersion: List<Int> = run {
    val cfg = rootProject.projectDir.parentFile.resolve("loxberry-plugin/plugin.cfg")
    val treffer = cfg.takeIf { it.isFile }?.readLines()
        ?.firstNotNullOfOrNull { Regex("""VERSION=(\d+)\.(\d+)\.(\d+)""").matchEntire(it.trim()) }
        ?: throw GradleException("${cfg.path}: keine Zeile VERSION=x.y.z gefunden")
    val teile = treffer.groupValues.drop(1).map { it.toInt() }
    if (teile[1] > 99 || teile[2] > 99) {
        throw GradleException("VERSION=${teile.joinToString(".")}: Neben- und Patch-Version je hoechstens 99 (versionCode)")
    }
    teile
}

android {
    namespace = "com.loxpanel.spike"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.loxpanel.spike"
        minSdk = 24
        targetSdk = 34
        versionCode = projektVersion[0] * 10000 + projektVersion[1] * 100 + projektVersion[2]
        versionName = projektVersion.joinToString(".")

        // WICHTIG: Für ein echtes ARM-Tablet reicht arm64-v8a. x86_64 nur für den
        // Emulator. Mehr ABIs = längerer Build + größeres APK.
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    // Release-Builds tragen immer denselben Schlüssel. Nur dann lässt sich die
    // installierte App aktualisieren, ohne sie zu deinstallieren (das löscht ihre
    // Konfiguration samt Miniserver-Zugang). Schlüssel und Passwörter kommen aus
    // der Umgebung, im Workflow aus den Repo-Secrets (siehe android/README.md).
    signingConfigs {
        create("release") {
            System.getenv("LOXPANEL_KEYSTORE")?.let { storeFile = file(it) }
            storePassword = System.getenv("LOXPANEL_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("LOXPANEL_KEY_ALIAS")
            keyPassword = System.getenv("LOXPANEL_KEY_PASSWORD")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

// ---- Chaquopy: Python einbetten + die kritischen Pakete via pip ----
// Ab Chaquopy 15/16 EIGENER Top-Level-Block (NICHT mehr in android.defaultConfig,
// das war <=14 und verursacht "Unresolved reference: python").
chaquopy {
    defaultConfig {
        version = "3.11"                 // passend zum auf dem PC installierten Python 3.11
        // buildPython nicht gesetzt: Chaquopy nutzt automatisch 'python' vom PATH (muss 3.11 sein)       // Chaquopy nutzt dieses Python zum Bauen reiner sdists
        pip {
            // LoxPanel-Laufzeitabhängigkeiten aus der requirements.txt des Repos:
            // dieselben Pakete und Versionsgrenzen wie Docker und LoxBerry, keine
            // zweite Liste. aiohttp kommt über loxone-api; native Pakete
            // (cryptography, aiohttp) liefert der Chaquopy-Paketindex als Wheel.
            install("-r", rootProject.projectDir.parentFile.resolve("requirements.txt").path)
        }
    }
}

dependencies {
    // bewusst minimal: kein AppCompat nötig, wir nutzen android.app.Activity
    // Unit-Tests auf dem PC (gradle testDebugUnitTest), nicht in der APK
    testImplementation("junit:junit:4.13.2")
}

// ---- LoxPanel-Code IMMER aus dem Repo in die App-Assets synchronisieren ----
// So wird die APK stets aus dem aktuellen Repo-Stand gebaut (keine Handkopie,
// keine Divergenz). Erwartet das Android-Projekt unter <repo>/android/ -> der
// Repo-Wurzelordner ist das Elternverzeichnis der Gradle-Wurzel. config wird OHNE
// echte Zugangsdaten gebuendelt (nur .example/Schema); jeder traegt Miniserver/
// Kamera/Kalender selbst ueber /config bzw. /settings ein.
val loxRepoRoot = rootProject.projectDir.parentFile
tasks.register<Copy>("syncLoxpanelAssets") {
    val dest = layout.projectDirectory.dir("src/main/assets/loxpanel").asFile
    doFirst { dest.deleteRecursively() }
    into(dest)
    from(loxRepoRoot.resolve("bin")) { into("bin") }
    from(loxRepoRoot.resolve("webfrontend")) { into("webfrontend") }
    from(loxRepoRoot.resolve("deploy")) { into("deploy") }
    from(loxRepoRoot.resolve("config")) {
        into("config")
        exclude("loxpanel.cfg", "panels.json", "theme.json")   // keine echten Daten/Layouts
    }
    // Ausserhalb des Repos gebaut -> nicht synchronisieren (vorhandene Assets gelten).
    onlyIf { loxRepoRoot.resolve("bin/webvisu.py").exists() }
}
tasks.named("preBuild") { dependsOn("syncLoxpanelAssets") }
