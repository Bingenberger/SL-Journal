# SL-Journal unter Windows installieren und lokal nutzen

Diese Anleitung richtet sich an Einsteiger mit Windows 11 und einem 64-Bit-PC. Die App läuft auf Ihrem Rechner; bedient wird sie in Edge oder Chrome. Sie brauchen keinen eigenen Internetserver. Internet benötigen Sie für die Installation und später für optionale Mail- und Kalenderverbindungen.

Stand: 26. September 2026. Grundlage ist [Bingenberger/SL-Journal](https://github.com/Bingenberger/SL-Journal). Die Schritte wurden mit dem Quellcode und den angebotenen Python-Paketen abgeglichen; ein vollständiger Installationstest auf Windows steht noch aus.

## 1. Was Sie vorbereiten sollten

- Etwa 30–45 Minuten Zeit und die Berechtigung, Programme zu installieren.
- Einen aktuellen Browser und eine Authenticator-App mit TOTP-Unterstützung, zum Beispiel auf dem Smartphone.
- Einen lokalen Ordner, der nicht automatisch mit OneDrive synchronisiert wird. Wir verwenden `SL-Journal` direkt in Ihrem Benutzerordner.

Das Journal besteht aus einem kleinen Serverprogramm und der Browseroberfläche. Das Terminalfenster mit dem Server muss während der Benutzung geöffnet bleiben. Der Rechner muss eingeschaltet sein.

## 2. Python und Git installieren

1. Öffnen Sie die [offizielle Python-Downloadseite für Windows](https://www.python.org/downloads/windows/). Installieren Sie **Python 3.13**, möglichst die neueste angebotene 3.13-Unterversion, mit dem Windows-Installer für Ihre Rechnerarchitektur. Für übliche Intel-/AMD-PCs ist dies **64-bit**. Lassen Sie den Python-Launcher mitinstallieren.
2. Installieren Sie [Git für Windows](https://git-scm.com/downloads/win). Die Standardoptionen reichen aus.
3. Öffnen Sie anschließend ein **neues PowerShell-Fenster**: Startmenü → „PowerShell“ suchen → öffnen. Für die folgenden App-Befehle sind keine Administratorrechte nötig.

Prüfen Sie beide Installationen. Kopieren Sie jeweils eine Zeile und drücken Sie Enter:

```powershell
py -3.13 --version
git --version
```

Erwartet werden `Python 3.13.…` und eine Git-Versionsnummer. Bei „nicht gefunden“ PowerShell schließen und erneut öffnen. Erst fortfahren, wenn beide Befehle funktionieren.

## 3. App herunterladen

Alle folgenden Befehle gehören in PowerShell, nicht in die Python-Konsole oder die Adresszeile des Browsers.

```powershell
cd $env:USERPROFILE
git clone https://github.com/Bingenberger/SL-Journal.git
cd SL-Journal
```

Der letzte Befehl wechselt in den Projektordner. Hier müssen unter anderem `manage.py` und `requirements.txt` liegen. Prüfen können Sie das mit `dir`.

## 4. Abhängigkeiten installieren

Wir verwenden eine virtuelle Python-Umgebung. Sie hält die Pakete dieser App von anderen Programmen getrennt. Eine Aktivierung per PowerShell-Skript ist nicht erforderlich; deshalb müssen Sie auch keine Ausführungsrichtlinie ändern.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

**Besonderheit SQLCipher:** Die Projektdatei nennt derzeit `sqlcipher3-binary`. Für Windows verwenden wir stattdessen `sqlcipher3==0.6.2`, das ebenfalls das von der App importierte Modul `sqlcipher3` bereitstellt. Dafür gibt es fertige Windows-Pakete. Wir erstellen eine lokale Kopie der Paketliste; das Original bleibt unverändert. [Paketinformationen](https://pypi.org/project/sqlcipher3/0.6.2/#files)

Die folgende lange Zeile vollständig kopieren:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; p=Path('requirements.txt'); text=p.read_text(); Path('.venv/requirements-local.txt').write_text('\n'.join('sqlcipher3==0.6.2' if line.strip().startswith('sqlcipher3-binary') else line for line in text.splitlines())+'\n')"
.\.venv\Scripts\python.exe -m pip install -r .venv/requirements-local.txt
.\.venv\Scripts\python.exe -m pip install tzdata
.\.venv\Scripts\python.exe -m pip check
```

`tzdata` liefert unter Windows die Zeitzonendaten für `Europe/Berlin`, die das Journal für Datum und Uhrzeit benötigt. Am Ende sollte `No broken requirements found` erscheinen. Prüfen Sie zusätzlich die Datenbankverschlüsselung:

```powershell
.\.venv\Scripts\python.exe -c "from sqlcipher3 import dbapi2; db=dbapi2.connect(':memory:'); print(db.execute('PRAGMA cipher_version').fetchone()); db.close()"
```

Erwartet wird eine Versionsnummer, beispielsweise `('4.…',)`. Bei `None` oder einer Fehlermeldung noch keine Daten erfassen. Das normale Python-Modul `sqlite3` ist kein Ersatz für SQLCipher.

Node.js und `npm install` sind für die normale Benutzung nicht erforderlich: Die Browserdateien sind bereits im Repository enthalten.

## 5. Einmalig einrichten und erstmals starten

```powershell
.\.venv\Scripts\python.exe manage.py init
```

Kopieren Sie den ausgegebenen **Einrichtungscode** vorübergehend an einen sicheren Ort. Er wird im nächsten Schritt gebraucht. Anschließend:

```powershell
.\.venv\Scripts\python.exe manage.py run
```

Das Fenster wartet nun scheinbar: Das ist richtig, der Server läuft. Öffnen Sie im Browser **https://localhost:8443**.

Beim ersten Start erzeugt die App ein selbstsigniertes HTTPS-Zertifikat. Der Browser kann deshalb eine Zertifikatswarnung anzeigen. Für den ersten lokalen Test können Sie die Ausnahme über die angebotenen erweiterten Optionen bestätigen – ausschließlich für die gerade selbst gestartete Adresse `https://localhost:8443`. Wird keine Ausnahme angeboten, richten Sie ein vertrauenswürdiges lokales Zertifikat wie in Abschnitt 9 ein. Nicht auf `http://` wechseln: Die App verlangt HTTPS.

Auf der Einrichtungsseite:

1. Den Einrichtungscode eingeben.
2. **Authenticator einrichten** auswählen und den QR-Code mit Ihrer Authenticator-App scannen.
3. Ein eigenes Passwort mit mindestens **14 Zeichen** vergeben.
4. Den aktuellen sechsstelligen Code aus der Authenticator-App eingeben und die Einrichtung abschließen.

Es gibt kein Standardpasswort. Der Einrichtungscode ist danach verbraucht. Künftige Anmeldungen benötigen Ihr Passwort und einen jeweils aktuellen Authenticator-Code.

## 6. Jeden Tag starten und beenden

PowerShell öffnen und eingeben:

```powershell
cd "$env:USERPROFILE\SL-Journal"
.\.venv\Scripts\python.exe manage.py run
```

Danach **https://localhost:8443** öffnen und anmelden. `init` wird nicht erneut benötigt.

Zum Beenden erst offene Eingaben speichern, dann im Serverfenster **Strg+C** drücken. Nur den Browser zu schließen beendet den Server nicht. Ihre gespeicherten Daten bleiben erhalten.

Wenn Port 8443 schon belegt ist, die bereits laufende Journal-Instanz verwenden oder diese zuerst beenden. Alternativ:

```powershell
.\.venv\Scripts\python.exe manage.py run --port 8445
```

Dann lautet die Adresse `https://localhost:8445`.

## 7. Erste Schritte und optionale Funktionen

- Im Tagesjournal einen kurzen Text eingeben und **Festhalten** wählen.
- Über **Aufgabe** eine Aufgabe erstellen und probeweise abhaken.
- Unter **Projekte**, **Vorgänge** und **Kontakte** die eigenen Strukturen anlegen.
- Mail- und Nextcloud-Zugang erst bei Bedarf unter **Einstellungen** ergänzen. Für die lokale Nutzung sind sie nicht erforderlich.
- Der manuelle lokale Start richtet keinen Hintergrunddienst für Mailabruf, Kalenderabgleich oder Sicherung ein. Zunächst die Schaltflächen zum Aktualisieren verwenden.

**PDF-Vorschauen:** Sie benötigen zusätzlich Poppler mit `pdftoppm.exe` im Windows-PATH. Der PDF-Download funktioniert auch ohne Vorschau. Das [Poppler-Projekt](https://poppler.freedesktop.org/) verweist auf den Quellcode; Windows-Binärpakete stammen häufig von Drittanbietern. Lassen Sie bei einem verwalteten Rechner die IT ein geeignetes Paket bereitstellen. Prüfen Sie danach in einem neuen PowerShell-Fenster `pdftoppm -v`.

**Office-Vorschauen:** Zusätzlich [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) installieren. Die App muss `soffice` finden. Bei Installation im Standardordner können Sie es für das aktuelle PowerShell-Fenster ergänzen, bevor Sie den Server starten:

```powershell
$env:Path = "C:\Program Files\LibreOffice\program;" + $env:Path
```

Die Office-Vorschau benötigt auch Poppler. Die Office-Konvertierung ist auf Windows in dieser Anleitung nicht praktisch geprüft; Anhänge lassen sich unabhängig davon herunterladen.

## 8. Daten sichern und Updates installieren

Ihre Daten liegen im Unterordner **`instance`**, insbesondere `journal.db`, `master.key` und `attachments`. **Ohne den ursprünglichen `master.key` lässt sich die Datenbank nicht öffnen.** Der Ordner `.venv` enthält dagegen nur austauschbare Softwarepakete.

Einfache Sicherung: Server mit Strg+C beenden und den **gesamten Ordner `instance`** auf einen geschützten Sicherungsdatenträger kopieren. Nur `journal.db` zu kopieren reicht nicht aus.

Die eingebaute verschlüsselte Sicherung starten Sie im Projektordner so:

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

Den ausgegebenen Sicherungspfad aufbewahren und die Sicherungsdatei auf einen anderen Datenträger kopieren. Auch **`instance\backup.key` separat sichern**: Er wird für die Wiederherstellung dieser Sicherungsdatei benötigt. Eine vollständige Anleitung bietet [README.md](../README.md).

Für ein Update: Server stoppen, sichern, dann:

```powershell
git pull --ff-only
```

Anschließend die lokale Paketliste aus Abschnitt 4 erneut erzeugen, Pakete installieren und den Server starten. Bei einer Git-Meldung über eigene Änderungen nicht mit Lösch- oder Reset-Befehlen fortfahren. Zunächst die Meldung klären. Datenbankanpassungen erfolgen beim App-Start, daher immer vorher sichern.

## 9. Optional: HTTPS ohne Zertifikatswarnung

Für Mikrofonaufnahmen über **Sprachi** ist eine vom Browser als sicher anerkannte Verbindung wichtig. Ein lokales Zertifikat lässt sich mit [mkcert](https://github.com/FiloSottile/mkcert#installation) einrichten. Folgen Sie dort der Windows-Installation. Sobald `mkcert` in einem neuen PowerShell-Fenster verfügbar ist:

```powershell
cd "$env:USERPROFILE\SL-Journal"
mkcert -install
New-Item -ItemType Directory -Force certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
.\.venv\Scripts\python.exe manage.py run --cert certs/localhost.pem --key certs/localhost-key.pem
```

`mkcert -install` richtet eine lokale Zertifizierungsstelle ein und kann eine Windows-Rückfrage auslösen. Geben Sie deren privaten Schlüssel `rootCA-key.pem` niemals weiter. Bei späteren Starts dieselben `--cert`- und `--key`-Angaben verwenden. Falls der Browser noch warnt, komplett schließen und erneut öffnen. [Funktionsweise von mkcert](https://github.com/FiloSottile/mkcert)

## 10. Häufige Probleme

| Meldung oder Verhalten | Was Sie prüfen sollten |
| --- | --- |
| `py` oder `git` nicht gefunden | Installation prüfen und PowerShell neu öffnen. |
| `can't open file ... manage.py` | Zuerst `cd "$env:USERPROFILE\SL-Journal"` ausführen. |
| `No matching distribution found for sqlcipher3-binary` | Abschnitt 4 mit der lokalen Paketliste verwenden, nicht direkt die ursprüngliche `requirements.txt`. |
| `ModuleNotFoundError` | Immer `.\.venv\Scripts\python.exe` verwenden; Paketinstallation muss ohne Fehler beendet sein. |
| `ZoneInfoNotFoundError` mit `Europe/Berlin` | `.\.venv\Scripts\python.exe -m pip install tzdata` ausführen. |
| Browser meldet „Verbindung abgelehnt“ | Läuft der Server noch? Ist die Portnummer korrekt? HTTPS verwenden. |
| Authenticator-Code abgelehnt | Uhrzeit auf PC und Smartphone automatisch synchronisieren; einen neuen Code abwarten. |
| `file is not a database` / Schlüssel fehlt | Datenbank und ursprünglichen Schlüssel zusammen wiederherstellen. Nichts löschen oder neu initialisieren. |
| Keine Mail kommt automatisch an | Der manuelle Start richtet keine geplante Synchronisierung ein. Einstellungen und manuellen Abruf prüfen. |

Der Standardstart ist nur auf diesem Rechner erreichbar. Die folgenden Abschnitte ergänzen den automatischen Start und den Zugriff aus dem lokalen Netzwerk.

## 11. Automatisch bei der Windows-Anmeldung starten

Diese Variante startet das Journal, sobald **Sie sich bei Windows anmelden**. Sie ist kein Dienst vor der Benutzeranmeldung. Der PC muss eingeschaltet bleiben; im Energiesparmodus ist das Journal nicht erreichbar. Mailabruf und Backups werden dadurch nicht automatisch geplant.

Zuerst die Ersteinrichtung abschließen und die Zertifikate aus Abschnitt 9 erstellen. Einen laufenden manuellen Server mit Strg+C beenden, damit nicht zwei Prozesse denselben Port verwenden.

### Aufgabe anlegen

1. Im Startmenü **Aufgabenplanung** öffnen.
2. Rechts **Aufgabe erstellen…** wählen.
3. Unter **Allgemein** als Namen `SL-Journal` eintragen. Das eigene Benutzerkonto und **Nur ausführen, wenn der Benutzer angemeldet ist** wählen. **Mit höchsten Privilegien ausführen** bleibt ausgeschaltet.
4. Unter **Trigger → Neu…** den Start **Bei Anmeldung** für das eigene Benutzerkonto auswählen.
5. Unter **Aktionen → Neu…** die Aktion **Programm starten** wählen und die folgenden Felder ausfüllen.

Die tatsächlichen Pfade können Sie in PowerShell anzeigen:

```powershell
Write-Output "$env:USERPROFILE\SL-Journal\.venv\Scripts\python.exe"
Write-Output "$env:USERPROFILE\SL-Journal"
```

| Feld | Inhalt |
| --- | --- |
| Programm/Skript | Den ersten ausgegebenen Pfad zu `python.exe` einfügen; über „Durchsuchen…“ auswählbar. |
| Argumente hinzufügen | `manage.py run --host 127.0.0.1 --port 8443 --cert certs/localhost.pem --key certs/localhost-key.pem` |
| Starten in | Den zweiten ausgegebenen Pfad zum Projektordner, **ohne Anführungszeichen**, einfügen. |

6. Unter **Bedingungen** bei einem Notebook entscheiden, ob der Server auch im Akkubetrieb laufen soll. In diesem Fall die Optionen zum Starten nur bei Netzbetrieb und zum Beenden bei Akkubetrieb ausschalten.
7. Unter **Einstellungen** „Aufgabe bei Bedarf ausführen“ aktivieren. Eine vorgegebene maximale Laufzeit wie „Aufgabe beenden, falls sie länger als 3 Tage ausgeführt wird“ ausschalten. Bei bereits laufender Aufgabe **Keine neue Instanz starten** wählen.
8. Speichern. Die Aufgabe markieren und rechts **Ausführen** wählen. Danach `https://localhost:8443` öffnen.

Das Python-Fenster kann sichtbar bleiben; nicht schließen, solange das Journal laufen soll. Entscheidend ist, dass die Aufgabe weiterläuft. Ein als „Wird ausgeführt“ angezeigter Status ist bei einem Server normal.

### Stoppen, aktualisieren und wieder starten

In der Aufgabenplanung `SL-Journal` markieren und **Beenden** wählen. Vorher alle Eingaben speichern. Danach können Sie sichern und aktualisieren. Anschließend **Ausführen** wählen. Nicht zusätzlich `manage.py run` im Terminal starten, solange die Aufgabe läuft.

Zum dauerhaften Abschalten **Deaktivieren** wählen; einen bereits laufenden Prozess zusätzlich mit **Beenden** stoppen. **Aktivieren** schaltet den Autostart wieder ein. Die Aufgabe zu löschen entfernt nur den Autostart, nicht die Journaldaten.

Wenn die Aufgabe sofort endet: „Starten in“ und die Zertifikatspfade prüfen. Den Startbefehl aus Abschnitt 6 bzw. 9 einmal von Hand ausführen, um die Fehlermeldung zu sehen. Nach dem Verschieben des Projektordners müssen beide Pfade der Aufgabe angepasst werden.

## 12. Aus dem LAN oder vom iPad zugreifen

Hier geht es um einen lokalen Test im eigenen vertrauenswürdigen Netzwerk. Die App bleibt dieselbe Einzelplatzanwendung mit derselben Anmeldung. Keine Portweiterleitung im Router einrichten. Der eingebaute Flask-Server ist für lokale Tests gedacht; für einen dauerhaft betriebenen Schulserver gelten die Servervorlagen in [README.md](../README.md).

### A. Die richtige IP-Adresse feststellen

In PowerShell:

```powershell
ipconfig
```

Beim tatsächlich verwendeten WLAN- oder Ethernet-Adapter die **IPv4-Adresse** ablesen. VPN-, virtuelle und getrennte Adapter nicht verwenden. Das folgende Beispiel benutzt **`192.168.178.40`**: Ersetzen Sie diese Adresse in **allen** Befehlen durch Ihre eigene.

Im Router möglichst eine DHCP-Reservierung einrichten („Diesem Gerät immer dieselbe IP-Adresse zuweisen“). Dann ändern sich URL und Zertifikat nicht bei der nächsten Anmeldung im Netzwerk. In einem verwalteten Schulnetz übernimmt das die IT. iPad und PC müssen sich gegenseitig erreichen können; Gast-WLANs blockieren häufig Verbindungen zwischen Geräten.

### B. Das Zertifikat um die LAN-Adresse erweitern

Den laufenden Server beenden. `mkcert` muss wie in Abschnitt 9 eingerichtet sein. Im Projektordner:

```powershell
cd "$env:USERPROFILE\SL-Journal"
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1 192.168.178.40
```

Damit ersetzen Sie nur die HTTPS-Zertifikate, **nicht** `instance/master.key` oder die Datenbank. Die lokalen Adressen bleiben im Zertifikat enthalten. Der Dateiname `localhost.pem` ist frei gewählt und funktioniert auch für das enthaltene LAN-Ziel. Ändert sich die IP-Adresse, diesen Schritt mit der neuen Adresse wiederholen.

### C. Windows-Firewall gezielt freigeben

Das eigene vertrauenswürdige WLAN sollte in Windows als **Privates Netzwerk** eingestuft sein. In einem Schulnetz die Freigabe durch die IT vornehmen lassen; nicht eigenständig ein verwaltetes Profil umstellen.

PowerShell einmal **als Administrator** öffnen und ausführen:

```powershell
New-NetFirewallRule -Name "SL-Journal-LAN" -DisplayName "SL-Journal im privaten LAN" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -Profile Private -RemoteAddress LocalSubnet
```

Diese Regel erlaubt den Port nur im privaten Profil für Geräte aus dem lokalen Subnetz. Die Firewall eingeschaltet lassen. Bei einer anderen Portnummer den Befehl entsprechend ändern. Den Befehl nicht mehrfach ausführen, wenn die Regel bereits existiert. [Microsoft: Firewallregeln per PowerShell](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/configure-with-command-line)

### D. Mit LAN-Adresse starten

In einer normalen PowerShell im Projektordner zunächst manuell testen:

```powershell
.\.venv\Scripts\python.exe manage.py run --host 192.168.178.40 --port 8443 --cert certs/localhost.pem --key certs/localhost-key.pem
```

Auf dem PC und auf dem iPad öffnen Sie nun **`https://192.168.178.40:8443`**. Bei dieser Bindung ist der Server über die LAN-IP erreichbar, nicht über `localhost`. `localhost` auf dem iPad würde das iPad selbst bezeichnen.

Für den Autostart nach erfolgreichem Test den manuellen Server beenden und in Abschnitt 11 im Feld „Argumente hinzufügen“ `--host 127.0.0.1` durch `--host 192.168.178.40` ersetzen. Unter **Trigger → Bearbeiten** bei Bedarf eine Verzögerung von 30 Sekunden einstellen, damit WLAN und IP-Adresse nach der Anmeldung bereitstehen. Danach die Aufgabe ausführen. Der Start kann scheitern, wenn das betreffende Netzwerk noch nicht verbunden ist.

### E. HTTPS-Vertrauen auf dem iPad einrichten

Das iPad kennt die lokale Zertifizierungsstelle des PCs noch nicht. Nur deren **öffentliches** Zertifikat übertragen:

```powershell
$journalCaFolder = mkcert -CAROOT
Copy-Item (Join-Path $journalCaFolder "rootCA.pem") ".\certs\SL-Journal-CA.crt"
```

Die Datei `certs\SL-Journal-CA.crt` über einen eigenen, vertrauten Übertragungsweg auf das iPad bringen und dort zur Profilinstallation öffnen. **Niemals `rootCA-key.pem`, den HTTPS-Privatschlüssel oder `instance/master.key` übertragen.** [mkcert: lokale Zertifikate](https://github.com/FiloSottile/mkcert)

Auf dem iPad das geladene Profil unter **Einstellungen → Allgemein → VPN und Geräteverwaltung** installieren. Anschließend unter **Allgemein → Info → Zertifikatsvertrauenseinstellungen** das volle Vertrauen für diese eigene Zertifizierungsstelle einschalten. Die manuelle Profilinstallation allein genügt nicht für SSL-Vertrauen. Bei einem verwalteten iPad kann die IT erforderlich sein. [Apple-Anleitung](https://support.apple.com/de-de/102390)

Danach Safari neu öffnen und die LAN-URL aufrufen. Die normale Journal-Anmeldung bleibt erforderlich. Für **Sprachi** zusätzlich Mikrofonzugriff erlauben. Auf anderen Windows-/Mac-Geräten muss ebenfalls die eigene CA als vertrauenswürdig eingerichtet werden.

### F. Prüfen und wieder auf lokalen Betrieb umstellen

| Problem | Prüfung |
| --- | --- |
| Verbindung geht schon auf dem PC nicht | Richtige IP? Server gestartet? Fehlermeldung im Fenster? |
| PC funktioniert, iPad nicht | Gleiches erreichbares Netzwerk, Firewallprofil, Gastnetz-/Client-Isolation und Portnummer prüfen. |
| Zertifikatswarnung | IP muss im Zertifikat stehen; CA auf dem iPad installieren **und** voll vertrauen. |
| Autostart funktioniert nach Neustart nicht | Feste IP reserviert? WLAN verbunden? Aufgabe gegebenenfalls nach der Verbindung erneut ausführen. |

Zum Abschalten des LAN-Zugriffs den Server beenden, den Startparameter wieder auf `--host 127.0.0.1` setzen und neu starten. Die Firewallregel können Sie in einer administrativen PowerShell entfernen:

```powershell
Remove-NetFirewallRule -Name "SL-Journal-LAN"
```

Die erweiterten Zertifikate funktionieren weiterhin mit `https://localhost:8443`. Wird die CA auf dem iPad nicht mehr benötigt, das betreffende selbst installierte Profil dort wieder entfernen.
