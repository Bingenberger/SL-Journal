# SL-Journal für Android

Begleit-App zum Schulleitungsjournal. Sie verbindet sich mit Ihrer eigenen Journal-Instanz und macht die häufigsten Handgriffe unterwegs möglich:

- **Sprachi:** Mikrofon-Knopf auf „Heute“ und „Einträge“ oder direkt vom Startbildschirm (lange auf das App-Symbol drücken › *Sprachi*). Aufnehmen (höchstens 10 Minuten), anhören, im Tagesjournal speichern – wie im Browser als Journaleintrag „Sprachi · Datum · Uhrzeit“ mit verschlüsseltem Audioanhang. Sprachis lassen sich in der Eintragsansicht direkt abspielen, auch die im Browser aufgenommenen.
- **Heute:** Tagesübersicht mit Terminen, Einträgen des Tages, fälligen Aufgaben und Wiedervorlagen; vor- und zurückblättern oder ein Datum wählen. Ein Schnellfeld schreibt direkt ins Tagesjournal.
- **Einträge:** Volltextsuche, Filter nach Typ und Posteingang, Detailansicht mit Markdown-Text, Aufgaben und Anhängen.
- **Neuer Eintrag / Bearbeiten:** alle Eintragstypen, Datum und Uhrzeit, Beteiligte, Projekte, Vorgänge und Tags mit derselben Autovervollständigung wie im Browser (neue Namen werden dort als Vorschlag gesammelt), neue Aufgaben, Fotos von der Kamera und Dateien als Anhang.
- **Aufgaben:** offen, ohne Datum oder erledigt; nach Fälligkeit gruppiert, abhaken und neu anlegen.
- **Teilen:** Aus jeder anderen App Text, Links, Fotos oder PDFs über „Teilen › Ins Journal“ als neuen Eintrag übernehmen.

Handschrift, Projekt- und Kontaktverwaltung, Jahresprozesse und Einstellungen bleiben der Weboberfläche vorbehalten.

## Telefon und Tablet

Die Oberfläche richtet sich nach der verfügbaren Breite, auch im geteilten Bildschirm:

| | Telefon | Tablet |
|---|---|---|
| Navigation | Leiste unten | Navigationsschiene links |
| Heute | eine Spalte | links Journal, Termine und Einträge, rechts Aufgaben und Wiedervorlagen |
| Einträge | Liste, Tipp öffnet die Detailansicht | Liste und Detail nebeneinander |
| Eintrag lesen | eine Spalte | Text links, Aufgaben und Anhänge rechts |
| Editor | Vollbild, alles untereinander | großes Blatt über der Ansicht, Text links, Zuordnungen rechts |
| Aufgaben | Gruppen untereinander | Gruppen als Karten im Raster nebeneinander |
| Anmeldung | Formular | Erklärung links, Formular rechts |

Hell- und Dunkelmodus folgen der Systemeinstellung; die Farben entsprechen der Weboberfläche.

## Voraussetzungen auf dem Server

Die App nutzt die JSON-Schnittstelle unter `/api/v1` (siehe `journal/mobile_api.py`). Sie ist ab dieser Version im Journal enthalten; nach dem Update genügt ein Neustart des Dienstes, die Tabelle für Gerätetokens entsteht automatisch.

Die App verbindet sich **nur per HTTPS**. Für den Zugriff von unterwegs gilt dasselbe wie für das iPad: den HTTPS-Server im freigegebenen Netz oder VPN verwenden (`deploy/nginx.conf`). Die lokale Entwicklungsinstanz auf `127.0.0.1` ist vom Telefon aus nicht erreichbar.

Verwendet das Journal ein Zertifikat einer eigenen Zertifizierungsstelle (Schul-CA, selbstsigniert), muss diese CA einmalig auf dem Gerät installiert werden: *Einstellungen › Sicherheit › Weitere Sicherheitseinstellungen › Verschlüsselung und Anmeldedaten › Zertifikat installieren › CA-Zertifikat* (Bezeichnungen je nach Hersteller leicht abweichend). Die App vertraut System- und vom Nutzer installierten Zertifizierungsstellen, sonst keinen.

## Anmeldung und Sicherheit

- Anmeldung mit **Serveradresse, Passwort und Einmalcode** aus der Authenticator-App – wie im Browser. Fehlversuche zählen zur selben Sperre (5 Versuche, dann 15 Minuten Pause); jeder Einmalcode gilt nur einmal.
- Danach erhält das Gerät ein eigenes **Gerätetoken**. Der Server speichert nur dessen SHA-256-Wert. In der App liegt das Token AES-verschlüsselt, der Schlüssel im Android-Keystore. Datensicherung und Geräteübertragung sind für die App abgeschaltet.
- Tokens verfallen nach **90 Tagen ohne Nutzung** und sofort, wenn die Sitzungsversion des Kontos wechselt.
- Im Journal unter **Einstellungen › Angemeldete Geräte** sehen Sie alle Geräte mit letzter Nutzung und können jedes einzeln abmelden – etwa bei Verlust.
- Anhänge werden nur zum Öffnen im App-Cache abgelegt und beim nächsten Öffnen ersetzt; Sprachis nur für die Dauer der Wiedergabe.
- Das Mikrofon wird erst bei der ersten Sprachi-Aufnahme angefragt. Die Aufnahme liegt bis zum Speichern im App-Cache und wird danach oder beim Verwerfen gelöscht.

## Bauen

Voraussetzung: Android Studio (Ladybug oder neuer) bzw. JDK 17 mit Android-SDK 35.

```bash
cd android
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

Oder in Android Studio den Ordner `android/` öffnen und auf *Run* klicken.

Bei jedem Push mit Änderungen unter `android/` baut GitHub Actions (`.github/workflows/android.yml`) eine Debug-APK. Sie steht in der Übersicht des jeweiligen Workflow-Laufs unter *Artifacts* zum Herunterladen bereit und lässt sich nach Erlauben von „Unbekannte Apps installieren“ direkt auf dem Gerät installieren.

Für eine dauerhafte Verteilung eine Release-Version mit eigenem Signaturschlüssel bauen (`./gradlew assembleRelease` mit `signingConfigs`, siehe Android-Dokumentation) – der Schlüssel gehört nicht ins Repository.

## Aufbau

```
app/src/main/java/de/sljournal/android/
├── MainActivity.kt          Einstieg, „Teilen“-Empfang
├── AppViewModel.kt          Anmeldung, Sitzung, Aktualisierung nach Änderungen
├── data/
│   ├── JournalApi.kt        HTTP-Client (OkHttp, kotlinx.serialization)
│   ├── Models.kt            Datenklassen der Schnittstelle
│   └── SessionStore.kt      Token im Android-Keystore
└── ui/
    ├── JournalRoot.kt       adaptive Navigation, Detail- und Editor-Ebene
    ├── login/  today/  entries/  editor/  tasks/
    └── components/          Karten, Markdown, Datumsfelder, Dateien
```

Technik: Kotlin, Jetpack Compose mit Material 3, `material3-adaptive` (ListDetailPaneScaffold) und `material3-adaptive-navigation-suite`. Mindestversion Android 8.0 (API 26).
