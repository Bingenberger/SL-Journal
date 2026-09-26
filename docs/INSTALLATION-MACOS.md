# SL-Journal auf dem Mac installieren und lokal nutzen

Diese Anleitung richtet sich an Einsteiger mit einem Intel-Mac oder einem Mac mit Apple-Chip und einer von Homebrew unterstützten macOS-Version, derzeit macOS 14 oder neuer. Die App läuft lokal auf Ihrem Mac und wird in Safari oder Chrome bedient. Für die Installation ist Internet nötig; ein eigener Internetserver ist nicht erforderlich. [Homebrew-Systemvoraussetzungen](https://brew.sh/)

Stand: 26. September 2026. Grundlage ist [Bingenberger/SL-Journal](https://github.com/Bingenberger/SL-Journal). Die Befehle sind mit Quellcode, Paketverfügbarkeit und Herstellerdokumentation abgeglichen; ein vollständiger Installationstest auf einem Mac steht noch aus.

## 1. Vorbereitung

Planen Sie etwa 30–45 Minuten ein. Sie benötigen die Berechtigung, Programme zu installieren, und eine Authenticator-App mit TOTP-Unterstützung, beispielsweise auf dem Smartphone.

Öffnen Sie **Terminal** über Spotlight: **⌘+Leertaste**, „Terminal“ eingeben, Enter. Kopieren Sie die folgenden Befehle blockweise hinein. Warten Sie jeweils, bis der Befehl beendet ist. Bei einer Passwortabfrage werden keine Zeichen angezeigt; das ist normal.

Wir verwenden den Ordner `SL-Journal` direkt in Ihrem Benutzerordner. Er liegt damit nicht in „Schreibtisch“ oder „Dokumente“, die möglicherweise mit iCloud synchronisiert werden.

## 2. Homebrew, Python und Git installieren

Homebrew installiert und verwaltet die benötigten Programme. Falls es bereits eingerichtet ist, prüfen Sie `brew --version` und überspringen die Installation.

Öffnen Sie ansonsten [brew.sh](https://brew.sh/) und verwenden Sie die dort angebotene Installation. Der offizielle Terminalbefehl lautet:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Lesen Sie die Rückfragen. Falls die Apple Command Line Tools benötigt werden, folgen Sie dem Installationsdialog. Führen Sie anschließend die unter **Next steps** ausgegebenen Befehle aus: Sie machen `brew` im Terminal verfügbar. Diese Befehle unterscheiden sich zwischen Intel und Apple-Chips. Öffnen Sie danach ein neues Terminal und prüfen Sie:

```bash
brew --version
```

Nun die Programme installieren:

```bash
brew install python@3.13 git poppler mkcert
```

- Python führt die App aus.
- Git lädt das Projekt und spätere Updates.
- Poppler ermöglicht PDF-Vorschauen.
- mkcert sorgt für eine vertrauenswürdige lokale HTTPS-Verbindung.

Prüfen:

```bash
"$(brew --prefix python@3.13)/bin/python3.13" --version
git --version
pdftoppm -v
```

Die Pfadabfrage mit `brew --prefix` funktioniert sowohl für Intel als auch für Apple-Chips. Es ist kein manuelles Ändern von `/usr/local` in `/opt/homebrew` erforderlich.

## 3. App herunterladen

```bash
cd ~
git clone https://github.com/Bingenberger/SL-Journal.git
cd SL-Journal
```

Hier müssen nun `manage.py` und `requirements.txt` liegen. Mit `ls` können Sie die Dateien anzeigen. Alle folgenden App-Befehle werden aus diesem Projektordner ausgeführt.

## 4. Python-Umgebung und Pakete einrichten

```bash
"$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

Die virtuelle Umgebung `.venv` hält die Pakete der App von anderen Python-Programmen getrennt. Sie muss nicht mit `source` aktiviert werden, solange Sie die angegebenen vollständigen Python-Pfade verwenden.

**Besonderheit SQLCipher:** In `requirements.txt` steht derzeit `sqlcipher3-binary`. Das ist nicht das passende Paket für diesen macOS-Installationsweg. Wir erzeugen eine lokale Kopie mit `sqlcipher3==0.6.2`. Dieses Paket stellt ebenfalls das Modul `sqlcipher3` bereit und bietet fertige Pakete für Intel- und Apple-Chip-Macs. Ein eigener SQLCipher-Build ist dadurch nicht nötig. [Verfügbare Pakete](https://pypi.org/project/sqlcipher3/0.6.2/#files)

Die folgende lange Zeile vollständig kopieren:

```bash
.venv/bin/python -c "from pathlib import Path; p=Path('requirements.txt'); text=p.read_text(); Path('.venv/requirements-local.txt').write_text('\n'.join('sqlcipher3==0.6.2' if line.strip().startswith('sqlcipher3-binary') else line for line in text.splitlines())+'\n')"
.venv/bin/python -m pip install -r .venv/requirements-local.txt
.venv/bin/python -m pip check
```

Erwartet wird zuletzt `No broken requirements found`. Anschließend prüfen:

```bash
.venv/bin/python -c "from sqlcipher3 import dbapi2; db=dbapi2.connect(':memory:'); print(db.execute('PRAGMA cipher_version').fetchone()); db.close()"
```

Es muss eine Versionsnummer erscheinen, etwa `('4.…',)`, nicht `None`. Bei einem Fehler nicht einfach auf das unverschlüsselte Python-Modul `sqlite3` ausweichen.

Die Browserdateien einschließlich des Zeicheneditors sind bereits enthalten. Node.js oder ein eigener Frontend-Build sind für die Benutzung nicht nötig.

## 5. Lokales HTTPS vorbereiten

Die App verlangt HTTPS. Wir erzeugen deshalb ein Zertifikat für Ihren eigenen Rechner:

```bash
mkcert -install
mkdir -p certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
```

Bestätigen Sie gegebenenfalls die macOS-Rückfrage. `mkcert -install` richtet eine lokale Zertifizierungsstelle im Vertrauensspeicher ein. Deren privaten Schlüssel `rootCA-key.pem` niemals weitergeben. Die Zertifikate gehören nur zu Ihrer lokalen Installation. [mkcert-Dokumentation](https://github.com/FiloSottile/mkcert)

Für diese Anleitung Safari oder Chrome verwenden. Firefox kann eine zusätzliche Einrichtung des Zertifikatsspeichers benötigen. Eine vertrauenswürdige HTTPS-Verbindung ist insbesondere für die Mikrofonaufnahme **Sprachi** wichtig.

## 6. Journal einmalig einrichten

```bash
.venv/bin/python manage.py init
```

Kopieren Sie den ausgegebenen **Einrichtungscode** vorübergehend an einen sicheren Ort. Anschließend den Server starten:

```bash
.venv/bin/python manage.py run --cert certs/localhost.pem --key certs/localhost-key.pem
```

Das Terminal bleibt nun belegt: Der Server läuft. Öffnen Sie **https://localhost:8443** in Safari oder Chrome.

1. Den Einrichtungscode eingeben.
2. **Authenticator einrichten** wählen und den QR-Code mit Ihrer Authenticator-App scannen.
3. Ein eigenes Passwort mit mindestens **14 Zeichen** festlegen.
4. Den aktuellen sechsstelligen Authenticator-Code eingeben und die Einrichtung abschließen.

Es gibt keine Standardzugangsdaten. Der Einrichtungscode ist danach ungültig. Bei späteren Anmeldungen verwenden Sie Ihr Passwort und einen neuen Code aus der Authenticator-App.

## 7. Im Alltag starten, nutzen und beenden

Terminal öffnen und eingeben:

```bash
cd ~/SL-Journal
.venv/bin/python manage.py run --cert certs/localhost.pem --key certs/localhost-key.pem
```

Danach **https://localhost:8443** öffnen und anmelden. `init` und `mkcert -install` müssen nicht jedes Mal wiederholt werden. Der Mac muss eingeschaltet und das Serverfenster geöffnet bleiben; im Ruhezustand steht die App nicht zuverlässig zur Verfügung.

Zum Ausprobieren:

- Einen Text im Tagesjournal festhalten.
- Über **Aufgabe** eine Aufgabe anlegen und abhaken.
- Ein Projekt und einen Vorgang anlegen, anschließend Einträge zuordnen.
- Über **Handschrift** eine Skizze erstellen.
- Für **Sprachi** den Mikrofonzugriff im Browser und gegebenenfalls in den macOS-Systemeinstellungen erlauben.

Mailabruf und Nextcloud-Kalender sind optional und können später unter **Einstellungen** eingerichtet werden. Der manuelle Start legt keine Hintergrundjobs für Abruf oder Backups an; verwenden Sie zunächst die Schaltflächen zum Aktualisieren.

Zum Beenden alle Eingaben speichern und im Terminal **Control+C** drücken – auf dem Mac ist dies die Control-Taste, nicht ⌘. Nur den Browser zu schließen beendet den Server nicht.

## 8. Optional: Word-, Excel- und PowerPoint-Vorschauen

PDF-Vorschauen sind mit Poppler bereits vorbereitet. Für Office-Dateien zusätzlich LibreOffice installieren:

```bash
brew install --cask libreoffice
```

Die App sucht das Programm `soffice`. Ergänzen Sie bei Bedarf vor dem Start dessen Ordner im Terminal:

```bash
export PATH="/Applications/LibreOffice.app/Contents/MacOS:$PATH"
command -v soffice
```

Wird der Pfad angezeigt, starten Sie den Server in genau diesem Terminal. Die PATH-Ergänzung gilt nur für dieses Fenster; in einem neuen Terminal erneut ausführen. LibreOffice gegebenenfalls einmal regulär öffnen und den macOS-Erststart bestätigen. Ohne diese Erweiterung können Office-Anhänge weiterhin heruntergeladen werden. [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)

## 9. Daten sichern und aktualisieren

Die persönlichen Daten liegen unter **`~/SL-Journal/instance`**. Dazu gehören die verschlüsselte Datenbank `journal.db`, der Schlüssel `master.key` und die Anhänge. **Den ursprünglichen Schlüssel unbedingt zusammen mit den Daten erhalten.** Eine einzelne Kopie von `journal.db` reicht nicht aus.

Für eine einfache Sicherung: Server beenden und im Finder über **Gehe zu → Gehe zum Ordner …** den Pfad `~/SL-Journal` öffnen. Den gesamten Ordner `instance` auf einen geschützten Sicherungsdatenträger kopieren.

Alternativ die integrierte Sicherung ausführen:

```bash
cd ~/SL-Journal
.venv/bin/python manage.py backup
```

Die ausgegebene Sicherungsdatei auf einen anderen Datenträger kopieren. Den Schlüssel **`instance/backup.key` separat aufbewahren**; er wird für die Wiederherstellung dieser Sicherung benötigt. Weitere Hinweise stehen in [README.md](../README.md).

Für Updates zuerst den Server stoppen und sichern. Dann:

```bash
cd ~/SL-Journal
git pull --ff-only
```

Die lokale Paketliste aus Abschnitt 4 erneut erzeugen, die Pakete installieren und den Server mit dem Befehl aus Abschnitt 7 starten. Bei Git-Konflikten oder lokalen Änderungen anhalten und die Meldung klären; nicht unbesehen Dateien zurücksetzen. Änderungen an der Datenbankstruktur werden beim Start automatisch angewendet.

## 10. Häufige Probleme

| Meldung oder Verhalten | Lösung |
| --- | --- |
| `brew: command not found` | Die Homebrew-„Next steps“ ausführen und ein neues Terminal öffnen. |
| Python-Version stimmt nicht | Den angegebenen Pfad über `brew --prefix python@3.13` verwenden, nicht das macOS-System-Python. |
| `No matching distribution found for sqlcipher3-binary` | Die lokale Paketliste aus Abschnitt 4 verwenden. |
| `manage.py` nicht gefunden | Zuerst `cd ~/SL-Journal` ausführen. |
| `ModuleNotFoundError` | `.venv/bin/python` verwenden und Fehler bei der Paketinstallation beheben. |
| Port 8443 belegt | Bereits laufendes Journal verwenden oder stoppen. Alternativ dem Startbefehl `--port 8445` hinzufügen und `https://localhost:8445` öffnen. |
| Zertifikatswarnung | Beide `--cert`-/`--key`-Argumente verwenden, `mkcert -install` prüfen und Browser neu öffnen. |
| Mikrofon bleibt stumm | Browserberechtigung und Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon prüfen; über vertrauenswürdiges HTTPS öffnen. |
| Authenticator-Code ungültig | Datum und Uhrzeit auf Mac und Smartphone automatisch einstellen; nächsten Code abwarten. |
| Datenbank oder Schlüssel nicht lesbar | Originalen `instance`-Ordner samt `master.key` wiederherstellen. Nicht löschen oder neu initialisieren. |

Der normale Start ist nur auf Ihrem Mac erreichbar. Die folgenden Abschnitte ergänzen Autostart und LAN-Zugriff.

## 11. Automatisch bei der Mac-Anmeldung starten

Ein **LaunchAgent** startet das Journal automatisch, sobald Sie sich mit Ihrem Benutzerkonto am Mac anmelden. Er ist kein Serverdienst vor der Anmeldung. Beim Abmelden oder Ausschalten steht das Journal nicht zur Verfügung; auch Ruhezustand kann den Zugriff unterbrechen. Der Agent plant keine Synchronisierung oder Backups. [Apple: Verwaltung mit launchd](https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac)

### Agent einmalig erstellen

Zuerst die Installation und HTTPS-Einrichtung abschließen. Einen manuellen Server mit Control+C beenden. Die folgenden Befehle erzeugen die Konfiguration mit Ihren tatsächlichen Benutzerpfaden; Sie müssen keinen Benutzernamen in einer XML-Datei ersetzen.

```bash
cd ~/SL-Journal
.venv/bin/python - <<'PY'
from pathlib import Path
import os
import plistlib

root = Path.cwd().resolve()
python = root / '.venv/bin/python'
assert python.exists() and (root / 'manage.py').exists(), 'Bitte im Projektordner ausführen.'
assert (root / 'certs/localhost.pem').exists(), 'Zuerst Abschnitt 5 ausführen.'
assert (root / 'certs/localhost-key.pem').exists(), 'HTTPS-Schlüssel fehlt.'
logs = Path.home() / 'Library/Logs/SL-Journal'
logs.mkdir(parents=True, exist_ok=True)
target = Path.home() / 'Library/LaunchAgents/de.sl-journal.local.plist'
target.parent.mkdir(parents=True, exist_ok=True)
config = {
    'Label': 'de.sl-journal.local',
    'ProgramArguments': [str(python), str(root / 'manage.py'), 'run',
        '--host', '127.0.0.1', '--port', '8443',
        '--cert', str(root / 'certs/localhost.pem'),
        '--key', str(root / 'certs/localhost-key.pem')],
    'WorkingDirectory': str(root),
    'EnvironmentVariables': {
        'JOURNAL_INSTANCE': str(root / 'instance'),
        'JOURNAL_KEY_FILE': str(root / 'instance/master.key'),
        'JOURNAL_TRUST_PROXY': '0',
        'PYTHONUNBUFFERED': '1',
        'PATH': '/Applications/LibreOffice.app/Contents/MacOS:' + os.environ['PATH'],
    },
    'RunAtLoad': True,
    'KeepAlive': True,
    'ThrottleInterval': 30,
    'StandardOutPath': str(logs / 'server.log'),
    'StandardErrorPath': str(logs / 'error.log'),
}
with target.open('wb') as output:
    plistlib.dump(config, output)
target.chmod(0o600)
print('Erstellt:', target)
PY
plutil -lint ~/Library/LaunchAgents/de.sl-journal.local.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

Der letzte Befehl lädt den Agenten und startet die App sofort. Nun **https://localhost:8443** öffnen. Bei künftigen Anmeldungen erfolgt der Start automatisch, ohne geöffnetes Terminal. Kein `sudo` verwenden: Der Agent gehört zu Ihrem Benutzerkonto.

Den Erstellungsblock nicht nochmals über einen laufenden Agenten schreiben. Für Änderungen erst wie unten beschrieben stoppen. Wenn Sie den Projektordner verschieben oder die Python-Umgebung neu anlegen, Pfade prüfen und die Konfiguration bei gestopptem Agenten neu erzeugen.

### Zustand und Fehler ansehen

```bash
launchctl print "gui/$(id -u)/de.sl-journal.local"
tail -n 40 ~/Library/Logs/SL-Journal/error.log
```

Die erste Ausgabe enthält unter anderem den Prozesszustand, die zweite Startfehler. Die Logdateien können im Laufe der Zeit wachsen; bei gestopptem Agenten können alte Logs archiviert werden. Bei „Address already in use“ läuft meist noch ein manuell gestartetes Journal.

### Für Updates stoppen und wieder starten

Erst Eingaben speichern, dann:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

Anschließend sichern und aktualisieren. Der Agent ist jetzt für die laufende Anmeldung entladen. Danach erneut laden:

```bash
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

`KeepAlive` startet einen unerwartet beendeten Prozess erneut. Deshalb zum bewussten Stoppen `bootout` verwenden und nicht nur den Python-Prozess beenden. Eine Meldung beim erneuten `bootstrap` kann bedeuten, dass der Agent bereits geladen ist; Zustand mit `launchctl print` prüfen.

### Autostart dauerhaft abschalten

Erst `bootout` wie oben ausführen. Dann die Datei aus dem automatisch geladenen Ordner verschieben:

```bash
mkdir -p ~/Library/SL-Journal-disabled
mv ~/Library/LaunchAgents/de.sl-journal.local.plist ~/Library/SL-Journal-disabled/
```

Das Journal und seine Daten bleiben bestehen. Zum Einschalten die Datei zurückverschieben und laden:

```bash
mv ~/Library/SL-Journal-disabled/de.sl-journal.local.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

## 12. Aus dem LAN oder vom iPad zugreifen

Die folgenden Schritte dienen dem Test im eigenen vertrauenswürdigen Netzwerk. Es ist weiterhin dieselbe Einzelplatz-App mit derselben Anmeldung. Keine Router-Portweiterleitung einrichten. Für einen dauerhaft betriebenen Schulserver die Serverbereitstellung aus [README.md](../README.md) verwenden; der hier gestartete Flask-Server ist für lokale Tests gedacht.

### A. LAN-Adresse bestimmen und beibehalten

Unter **Systemeinstellungen → Netzwerk → WLAN bzw. Ethernet → Details → TCP/IP** die IPv4-Adresse des aktiven Anschlusses ablesen. Das folgende Beispiel verwendet **`192.168.178.40`**. Ersetzen Sie diese Adresse überall durch die Ihres Macs.

Im Router möglichst eine DHCP-Reservierung für den Mac einrichten („immer dieselbe IP-Adresse“). Im Schulnetz hilft die IT. Mac und iPad müssen einander im Netzwerk erreichen können; ein Gast-WLAN oder eine Client-Isolation kann dies verhindern, auch wenn beide Geräte Internet haben.

### B. Zertifikat für die LAN-Adresse erzeugen

Den Server stoppen – bei Autostart mit `launchctl bootout` aus Abschnitt 11, bei manuellem Start mit Control+C. Dann:

```bash
cd ~/SL-Journal
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1 192.168.178.40
```

Das Zertifikat enthält jetzt zusätzlich die LAN-IP. Datenbank und `instance/master.key` bleiben unberührt. Bei einer IP-Änderung das Zertifikat mit der neuen Adresse erneut ausstellen. [mkcert-Dokumentation](https://github.com/FiloSottile/mkcert)

### C. Manuell testen und Firewall einstellen

```bash
.venv/bin/python manage.py run --host 192.168.178.40 --port 8443 --cert certs/localhost.pem --key certs/localhost-key.pem
```

Auf dem Mac und später auf dem iPad **`https://192.168.178.40:8443`** öffnen. Bei dieser Bindung verwenden Sie auch auf dem Mac die LAN-IP statt `localhost`; `localhost` auf dem iPad meint das iPad selbst.

Wenn macOS nach eingehenden Verbindungen für Python fragt, im eigenen vertrauenswürdigen Netz zulassen. Unter **Systemeinstellungen → Netzwerk → Firewall → Optionen** kann der Python-Prozess freigegeben werden. Falls er manuell hinzugefügt werden muss, den verwendeten Interpreter mit diesem Befehl ermitteln:

```bash
.venv/bin/python -c "import sys; from pathlib import Path; print(Path(sys.executable).resolve())"
```

In der Dateiauswahl mit **⌘+Shift+G** den ausgegebenen Pfad öffnen. Die macOS-App-Firewall ist keine port- und subnetzgenaue Windows-Regel; die Freigabe gilt für das betreffende Programm. Die explizite LAN-Bindung beibehalten und die Firewall nicht pauschal ausschalten. Bei aktiver Option „Alle eingehenden Verbindungen blockieren“ oder verwalteten Netzrichtlinien die IT einbeziehen. [Apple: Firewall-Einstellungen](https://support.apple.com/guide/mac-help/block-connections-to-your-mac-with-a-firewall-mh34041/mac)

### D. LAN-Adresse im Autostart verwenden

Nach erfolgreichem Test den manuellen Server mit Control+C stoppen. Der Agent aus Abschnitt 11 muss weiterhin entladen sein. In seiner Konfiguration die Bind-Adresse ersetzen:

```bash
plutil -replace ProgramArguments.4 -string 192.168.178.40 ~/Library/LaunchAgents/de.sl-journal.local.plist
plutil -lint ~/Library/LaunchAgents/de.sl-journal.local.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

Der Index `.4` bezieht sich genau auf die Argumentliste aus Abschnitt 11. Die übrigen Argumente und Zertifikatspfade bleiben gleich. Wird die WLAN-Adresse erst nach der Anmeldung verfügbar, versucht `KeepAlive` den Start erneut; dabei können vorübergehend Bind-Fehler im Log stehen. Eine dauerhaft geänderte IP muss in Zertifikat und Konfiguration angepasst werden.

### E. Zertifikat auf dem iPad vertrauenswürdig machen

Nur das öffentliche Zertifikat der eigenen lokalen Zertifizierungsstelle exportieren:

```bash
cd ~/SL-Journal
cp "$(mkcert -CAROOT)/rootCA.pem" certs/SL-Journal-CA.crt
open certs
```

`SL-Journal-CA.crt` beispielsweise per AirDrop an das eigene iPad übertragen und zur Profilinstallation öffnen. **Nicht** `rootCA-key.pem`, `localhost-key.pem` oder `instance/master.key` übertragen.

Das Profil unter **Einstellungen → Allgemein → VPN und Geräteverwaltung** installieren. Danach unter **Allgemein → Info → Zertifikatsvertrauenseinstellungen** das volle Vertrauen für die eigene CA aktivieren. Eine manuelle Profilinstallation allein aktiviert SSL-Vertrauen noch nicht. Bei verwalteten iPads ist gegebenenfalls die IT zuständig. [Apple-Anleitung](https://support.apple.com/de-de/102390)

Safari neu öffnen und `https://192.168.178.40:8443` aufrufen. Mit Journal-Passwort und Authenticator-Code anmelden. Für **Sprachi** zusätzlich Mikrofonzugriff erlauben. Andere zugreifende Geräte benötigen ebenfalls das Vertrauen in diese CA.

### F. Fehler eingrenzen und LAN-Zugriff abschalten

| Problem | Prüfung |
| --- | --- |
| Schon auf dem Mac keine Verbindung | Serverstatus, aktuelle IP und Port prüfen. |
| Mac funktioniert, iPad nicht | WLAN-Isolation, Firewallfreigabe und Erreichbarkeit zwischen den Netzen prüfen. |
| Zertifikatswarnung | IP im Zertifikat enthalten? Eigene CA auf dem iPad installiert und voll vertraut? |
| Nach Netzwerkwechsel nicht erreichbar | Bind-Adresse und Zertifikat passen nur zur eingetragenen IP. Im anderen Netzwerk neu konfigurieren oder lokal starten. |
| Mac im Ruhezustand | Mac aufwecken; ein schlafender Rechner ist kein verfügbarer Server. |

Zum Zurückstellen den Agenten mit `bootout` entladen und die Adresse ändern:

```bash
plutil -replace ProgramArguments.4 -string 127.0.0.1 ~/Library/LaunchAgents/de.sl-journal.local.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/de.sl-journal.local.plist
```

Danach wieder **https://localhost:8443** verwenden. Bei manuellem Betrieb einfach mit `--host 127.0.0.1` starten. Die Python-Firewallfreigabe bei Bedarf in den Systemeinstellungen zurücknehmen und ein nicht mehr benötigtes CA-Profil auf dem iPad entfernen.
