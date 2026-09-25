# Abgleich mit dem Lastenheft

Umgesetzt sind beide im Lastenheft beschriebenen Ausbaustände. Die folgende Zuordnung beschreibt den implementierten Stand; Infrastruktur und externe Konten werden erst bei der Einrichtung verbunden.

| Abschnitt | Umsetzung | Prüfung |
| --- | --- | --- |
| Rahmenbedingungen | Flask, SQLCipher/SQLite, Einzelnutzer, responsive Weboberfläche; lokaler HTTPS-Start und nginx/systemd-Vorlagen | Python- und Browserstart |
| Datenmodell | Einträge, Projekte, Aufgaben, Kontakte, Anhänge, Jahresprozesse; Mehrfachzuordnung; optionaler Herkunftseintrag | Datenbank-/Funktionsprüfungen |
| Tagescockpit | Tagwechsel, Kalender, getrennte Kommunikation, Gespräche/Telefonate/Notizen, Journal, Fälligkeitsgruppen, Eingangsstapel | Seiten- und Browserprüfungen |
| Mail | IMAP über TLS, erlaubte eigene Absender, Richtung, Original-EML, Weiterleitungsparser, Tags, Projektzuordnung/Vorschläge, Anhänge, Duplikatschutz | MIME-/Parsertests; echter Mailserver noch einzurichten |
| Erfassung | Gemeinsamer Dialog, Live-Markdown-Eingabe, Beteiligte mit Kontaktvorschlägen, Autovervollständigung für Kontakte/Projekte/Tags, Anhänge, Aufgabe im selben Vorgang, Textauswahl, Terminübernahme | Browserprüfung |
| Projekte | Chronik, alle Aufgaben, Anhänge, Archivierung, Vorlagenübernahme | Funktions- und Browserprüfungen |
| Aufgaben | Erfassung aus verschiedenen Kontexten, Projektübernahme, Datum optional, Bearbeitung, Erledigungsdatum, Wiederöffnen | Funktions- und Browserprüfungen |
| Kalender | Lesende CalDAV-Abfragen, mehrere Kalender, Serienterminanfrage, ganztägige/mehrtägige Termine, verschlüsselter Cache, Protokollübernahme | Simulierte CalDAV-Abfragen und Browserprüfung; echte Nextcloud noch einzurichten |
| Schuljahresgedächtnis | Monat und Zeitraum, Erinnerung, bestätigtes Erzeugen von Projekt und Aufgaben, einmal je Schuljahr | Schuljahresgrenzen, Wiederholungsschutz, Browserprüfung |
| Sicherheit | SQLCipher, verschlüsselte Dateien, HTTPS, Passwort/TOTP, Anmeldebegrenzung, CSRF, bereinigtes Markdown, VPN-Beschränkung in nginx-Vorlage | Authentifizierungs-, Zugriffs-, Inhalts- und Sicherungstests |
| Backup/Löschung | Eigenständig verschlüsseltes Backup, Wiederherstellung in leeren Pfad, Zeitsteuerung, Aufbewahrung je Typ | Backup-Rundlauf, Löschung und Erhalt verknüpfter Aufgaben |
| Obsidian | Vorschau/Import, Frontmatter, Tags, Tagesnotizen, offene Aufgaben mit Datum, lokale Anhänge, Wiederholungsschutz | Migration eines Beispielvaults |
| Suche | FTS5-Volltextindex, Wortpräfixe, Typ-/Tagfilter, Suche auch in abgeschlossenen Projekten | Suche, Bearbeitung und Neuindexierung |

## Bewusste Festlegungen

- Kontakte sind bereits eigene Objekte.
- Schuljahre laufen vom 1. August bis 31. Juli.
- Anfang/erste Woche wird ab dem 1., Mitte ab dem 11. und Ende ab dem 21. eines Monats erinnert. Die Erinnerung bleibt bis zur Bestätigung bestehen.
- Mehrfach-Projektkontext einer Aufgabe wird auf ein Projekt reduziert: standardmäßig das erste zugeordnete Projekt nach ID, im Dialog änderbar.
- Der Kalender bleibt ausschließlich Cache; keine Bearbeitung oder Rückschreibung nach Nextcloud.
- Der Obsidian-Import ist eine einmalige Migration, kein bidirektionaler Sync. Pluginsyntax bleibt im Text erhalten.
- Aufbewahrungsfristen werden nicht erfunden, sondern müssen in den Einstellungen aus dem freigegebenen Löschkonzept übernommen werden.
- Die Anwendung enthält keine echten Schul-, Kontakt-, Mail- oder Kalenderdaten. Browser-Screenshots verwenden einen isolierten fiktiven Beispielbestand.

## Noch bei der Inbetriebnahme

1. Passwort und Authenticator mit dem einmaligen Einrichtungscode einrichten.
2. IMAP- und Nextcloud-App-Zugangsdaten hinterlegen und mit realen Beispielnachrichten/-terminen prüfen.
3. Aufbewahrungsfristen und freigegebenen Betriebsort festlegen.
4. Zertifikate, VPN-Netz und Dienstpfade anpassen; Timer aktivieren.
5. Backupschlüssel separat verwahren und verschlüsselte Sicherungen auf ein zweites geeignetes Speichermedium übernehmen.

Die Servervorlagen sind vorbereitet, aber nicht als Systemdienste installiert. Die SQLCipher- und Dateiverschlüsselung ersetzt keinen Schutz des laufenden Betriebssystemkontos; Datenbankschlüssel und Backupschlüssel benötigen die in der README beschriebenen Dateirechte und getrennte Sicherung.

## Ergänzung: Live-Markdown

Browserprüfungen decken die Formatierung während des Tippens, Listenfortsetzung, Rückgängig/Wiederholen, Quelltextwechsel, Speicherung des ursprünglichen Markdown-Inhalts, Bearbeiten bestehender Einträge und das Zurücksetzen zwischen unterschiedlichen Einträgen ab. Eingefügtes HTML wird nicht ausgeführt; externe Bilder werden im Editor nicht geladen.

## Ergänzung: Autovervollständigung und Kontaktvorschläge

29 automatisierte Tests prüfen unter anderem die eindeutige Kontaktzuordnung, Namens- und Mailadresssuche bei über 100 Kontakten, begrenzte Trefferlisten, neue Vorschläge, Übernahme und Zusammenführung, Verwerfen/Wiederherstellen, Datenmigration sowie die Aktualisierung der Volltextsuche. Browserprüfungen decken Tastaturbedienung, Mehrfachauswahl, neue Tags, Speichern und erneutes Bearbeiten, Übernahme und Zuordnung von Kontaktvorschlägen sowie mobile Darstellung ab. Die doppelte Kontaktliste im Erfassungsdialog entfällt.

## Ergänzung: Projektvorschläge

Alle erfassenden Projektfelder erlauben neue Namen. Vorschläge bleiben bei erneutem Bearbeiten erhalten, werden je Name und Schuljahr zusammengeführt und lassen sich im Projektbereich übernehmen, einem bestehenden Projekt zuordnen, verwerfen oder wiederherstellen. Automatisierte Tests prüfen die Verknüpfung sämtlicher betroffener Einträge und Aufgaben, Aufgabenübernahme aus Einträgen, Mailzuordnung, ungültige Eingaben mit Rücknahme der Transaktion und die Trennung nach Schuljahr. Die Browserprüfung umfasst neue Projektnamen, erneutes Bearbeiten und Übernahme beziehungsweise Zuordnung.

## Ergänzung: Mehrfachaufgaben und Unteraufgaben

Mehrere Aufgaben je Eintrag mit individuellen Fälligkeiten; Unteraufgaben mit Herkunfts-/Projektübernahme, Fortschrittsanzeige, eigener Bearbeitung und Abschlussregeln. Tests prüfen gemeinsames Speichern mit vollständiger Rücknahme bei ungültigen Angaben, Verhinderung von Zyklen und tieferer Verschachtelung, Wiederöffnen, Projektvorschläge, Erhalt nach Löschung des Herkunftseintrags sowie Migration bestehender Aufgaben. Browserprüfungen decken zusätzliche und entfernte Aufgabenzeilen, Zurücksetzen der Dialoge, mehrere Unteraufgaben, Abschluss und Wiederöffnen sowie mobile Anzeige ab.

## Ergänzung: Ressourcenlinks im Editor

@-Vervollständigung nach einem Leerzeichen für Kontakte, Projekte, Tags, Einträge und Aufgaben. Geprüft sind authentifizierte und begrenzte Suche, Ressourcentypen, lokale Linkziele, Sonderzeichen, Vermeidung der Auslösung bei Mailadressen oder fehlendem Leerzeichen, Codebereiche, Maus-/Tastaturauswahl, Rückgängig/Wiederholen, Speichern und erneutes Bearbeiten sowie mobile Darstellung. Links bleiben im Markdown-Format erhalten.

## Ergänzung: Nextcloud-Dokumentverweise

Verknüpfung vorhandener Dateien und Ordner über HTTPS-Links an Einträgen und Projekten; keine Dateiübertragung und keine zusätzlichen Nextcloud-Zugangsdaten. Mehrfachzuordnung, Wiederverwendung vorhandener URLs, gemeinsame Metadaten, Dokumentseiten und @-Suche sind umgesetzt. Projektseiten berücksichtigen auch Dokumente ihrer Einträge. Getestet sind URL-Validierung, Dublettenvermeidung, sichere Textausgabe, Authentifizierung/CSRF, Entfernen einzelner Zuordnungen, Erhalt von Textlinkzielen und Wiederherstellung der Verweise aus der verschlüsselten Sicherung. Browserprüfungen verwenden fiktive URLs und kontrollieren, dass keine Dateien automatisch abgerufen werden.

## Ergänzung: PDF-Vorschau

Erste Seite lokaler PDF-Anhänge als Hover-Fenster auf Eintrags- und Projektseiten, mit dauerhaftem Öffnen per Schaltfläche, Tastaturbedienung, Escape und mobiler Anzeige. Automatisierte Tests rendern eine echte mehrseitige PDF und prüfen die Auswahl der ersten Seite, Anmeldung, Cache-Verbot, unveränderten Download, ungültige Dateien, fehlenden Renderer und Zeitüberschreitungen. Browserprüfungen decken verzögertes Laden, Wechsel des Mauszeigers ins Fenster, Fokus-Rückgabe, Download, Fehlerhinweis und mobile Positionierung ab.


## Ergänzung: Sitzungsprotokolle

Eigener Eintragstyp mit Tagesordnung, Text und Beschlüssen. Automatisierte Tests prüfen Speicherung, Markdown-Ausgabe, Volltextsuche nach neuen und geänderten Inhalten sowie die wiederholbare Migration alter Datenbanken unter Erhalt bestehender Projekt-, Kontakt-, Aufgaben-, Anhang- und Dokumentverknüpfungen. Browserprüfungen decken Typwechsel, Live-Editoren, Bearbeitung, leere Felder bei neuen Einträgen und Terminübernahme als Protokoll ab. Ergebnis: 87 Tests und vollständige Browserprüfung bestanden.


## Ergänzung: Handschrift mit Excalidraw

Lokal gebündeltes Excalidraw mit Stift als Startwerkzeug, mehreren Zeichenblättern pro Eintrag, Vorschauen, PNG- und bearbeitbarem Excalidraw-Download. Zeichnung und Vorschau werden gemeinsam in der verschlüsselten Datenbank gespeichert. Geprüft: Anmeldung/CSRF, ungültige Nutzdaten, wiederholte Speicheranfragen ohne Duplikate, Versionskonflikte, Löschen und Sicherungswiederherstellung. Der isolierte Browsertest scripts/handwriting_check.py prüft Maus- und simulierte druckabhängige Stifteingaben, Radierer, Rückgängig/Wiederholen, Textwerkzeug, Autospeichern, Wiederöffnen, Ausfall mit anschließendem Speichern, Export und mobile Anzeige. Keine externen Requests oder CSP-Verstöße im Zeichenablauf. 96 Python-Tests und vollständige Browserprüfung bestanden. Ein physischer Apple Pencil wurde nicht getestet.


### Direkte Zuordnung handschriftlicher Notizen

Projekt- und Tagfelder direkt in der Eintragsansicht, inklusive Autovervollständigung und Erhalt neuer Projektvorschläge beim Neuladen. Leere Anhangs- und Nextcloud-Bereiche werden ausgeblendet; vorhandene Dateien bleiben erreichbar. Getestet sind Speicherung ohne Veränderung von Zeichnung/Text, Entfernen von Zuordnungen, ungültige Projekte, CSRF sowie die Bedienung im Browser. 98 Python-Tests und erweiterte Handschrift-Browserprüfung bestanden.


### Ressourcenverknüpfungen an Zeichenblättern

Projekte und Tags stehen unter dem Zeichenblock. Jedes Zeichenblatt kann bestehende Einträge (einschließlich Gesprächen und Protokollen), Kontakte, Projekte, Tags, Aufgaben und Dokumentverweise verknüpfen. Einträge zeigen Rückverweise mit Vorschau. Keine Kopien der Zeichnung; Bezeichnungen folgen Umbenennungen. Getestet: alle Ressourcentypen, Duplikate, ungültige/externe Ziele, Eigenverweise, CSRF, Entfernen, Löschen von Zielen und Ursprungseinträgen, unveränderte Zeichnungen, Reihenfolge, Tastatur- und Mausauswahl sowie Desktop/Tablet/Mobilansicht. 109 Tests und beide Browserprüfungen bestanden.


### Ressourcenverknüpfungen auf Eintragsebene

Ein gemeinsamer Ressourcenbereich für den gesamten Eintrag, unabhängig von der Anzahl seiner Zeichenblätter. Vorhandene Blattverknüpfungen werden in einer Transaktion übernommen und doppelte Ziele zusammengefasst. Rückverweise öffnen den ganzen Eintrag mit Blattanzahl und optionaler Vorschau. Das Löschen einzelner oder aller Blätter erhält die Verknüpfungen; erst das Löschen des Eintrags entfernt sie. Migration, Wiederholbarkeit, Fremdschlüssel und Browserbedienung mit mehreren Blättern geprüft. 110 Tests und Handschrift-Browserprüfung bestanden.


### Vorgänge im Schulalltag

Eigener Bereich neben Projekten mit Offen, In Klärung, Erledigt und optionaler Wiedervorlage im Cockpit. Einträge einschließlich Handschrift lassen sich mehreren Vorgängen zuordnen; Aufgaben und Unteraufgaben übernehmen den Vorgang ihres Ursprungs. Vorgänge sind per Autovervollständigung, @-Verweis und Ressourcenverknüpfung erreichbar. Zugeordnete Eingangsmails gelten als bearbeitet. Geprüft: Validierung, CSRF, Zuordnung und Entfernen, Aufgabenvererbung, Ressourcenverweise, Statuswechsel, Wiedervorlagen sowie wiederholbare Migration mit Erhalt vorhandener IDs und Beziehungen. 114 Python-Tests, vollständige Browserprüfung und erweiterte Handschrift-Browserprüfung bestanden; Vorgangsansichten auch bei 768 und 390 Pixeln geprüft. Vor Aktivierung wurde eine verschlüsselte Datenbanksicherung erstellt. Lokaler HTTPS-Start erfolgreich; vorhandene Datensätze nach Migration unverändert, Integritäts- und Fremdschlüsselprüfung ohne Fehler.

### Vorgangsvorschläge

Freie Namen in der Vorgangsauswahl von Einträgen, Handschrift und Aufgaben werden als gemeinsame Vorschläge gespeichert. Übernahme als neuer Vorgang, Zuordnung zu einem bestehenden Vorgang, Verwerfen und Wiederherstellen; automatische Verknüpfung aller betroffenen Einträge und Aufgaben. Normalisierte Namen verhindern doppelte Vorschläge. Bestehende Vorschläge bleiben beim Bearbeiten erhalten. 117 Python-Tests bestanden; zusätzlicher isolierter Browsercheck prüft freie Eingabe ohne vorherige Auswahl, erneutes Bearbeiten, Aufgaben, Übernahme und Mobilansicht.

Auch die vollständige bestehende Browserprüfung und die Handschriftprüfung bestanden. Vor dem lokalen Neustart wurde eine verschlüsselte Sicherung angelegt; die vorhandenen Einträge, Projekte, Vorgänge, Zuordnungen, Aufgaben, Zeichnungen und Ressourcenverknüpfungen wurden unverändert übernommen. HTTPS-Erreichbarkeit und Datenbankintegrität geprüft.

### UI-Überarbeitung: Übersichtlichkeit und Bedienbarkeit

Siehe `UI-VERBESSERUNGEN.md`. 122 Python-Tests, vollständige Browserprüfung, Vorgangsvorschlagsprüfung, Handschriftprüfung sowie 27 zusätzliche responsive UI-Prüfungen mit 100 fiktiven Kontakten bestanden. Geprüft: Schutz ungespeicherter Eingaben, dauerhaft sichtbares Speichern, kompakte Vorschläge und Kontaktlisten, mobile Navigation und Aufgabenpriorisierung, kombinierte Filter, Pagination einschließlich alter Aufgabenlinks, direkte Tags im Posteingang und Speichern mit Verbindungsprüfung. Bestehende Ressourcenrückverweise und Handschriftzuordnungen bleiben erhalten.

### Wiederkehrende Aufgaben

131 Python-Tests bestanden. Neue Prüfungen decken Kalenderwochen und ISO-Jahreswechsel, Monatsende einschließlich Schaltjahr, Quartale, feste Termine, Enddatum, Validierung, CSRF, Zuordnungen und Unteraufgaben, parallele Erzeugung ohne Duplikate, Pausieren/Fortsetzen und getrennte Bearbeitung von Einzelaufgabe und Serie ab. Der isolierte Browsercheck `scripts/recurrence_checks.py` prüft Anlage, Titelvorschau, Einzelbearbeitung, Serienänderung, Pause/Fortsetzung sowie Ansichten bei 1440, 768 und 390 Pixeln. Bildschirmbeispiele: `screenshots/task-series-desktop.png` und `screenshots/task-series-mobile.png`.

Auch die vollständige bestehende Browserprüfung wurde erfolgreich durchlaufen. Vor Aktivierung wurde die verschlüsselte Sicherung `instance/backups/pre-task-series-20260924-085653.db` erstellt. Die lokale App ist unter https://localhost:8443 mit der Erweiterung erreichbar. Bestehende Datensätze wurden unverändert übernommen; Datenbankintegrität und Fremdschlüssel wurden nach dem Neustart geprüft.

### Übergreifende Suche und Live-Vorschläge

133 Python-Tests bestanden. Geprüft wurden Ressourcentypen, Volltext einschließlich Tagesordnung/Beschlüssen, Beschreibungen, Kontaktfelder, Groß-/Kleinschreibung einschließlich Umlauten, kombinierte Suchbegriffe, Sonderzeichen, Pagination, HTML-Escaping und Zugriffsschutz. `scripts/search_checks.py` prüft Live-Vorschläge, Pfeiltasten, Enter, Escape, direkte Navigation und die Darstellung bei 1440, 768 und 390 Pixeln in einer isolierten Datenbank. Die vorhandene @-Ressourcensuche bleibt erhalten.

### Bereichssuchen, Kontaktvorschläge und Telefonnummern

136 Python-Tests bestanden. Zusätzliche Prüfungen decken die wiederholbare Migration bestehender Kontakte, Speicherung/Änderung/Entfernung der Telefonnummer, Erhalt bei älteren Formularanfragen, Telefonnummernsuche, Unicode-Groß-/Kleinschreibung, eindeutige Feldvorschläge, Bereichsfilter und Zugriffsschutz ab. `scripts/search_fields_checks.py` prüft sämtliche Bereichssuchen, freie Kontakteingabe, Auswahl per Tastatur und Maus, mehrere Mailadressen, Speichern und erneutes Bearbeiten sowie Dialoge bei 1440, 768 und 390 Pixeln. Die bestehende globale Browser-Suchprüfung wurde erneut ausgeführt.

### Besprechungspunkte zu Nextcloud-Terminen

141 Python-Tests im vollständigen Lauf bestanden; nach dem ergänzten Test für den Kalender-Aktualisierungsendpunkt wurden die elf Kalender- und Terminvorbereitungstests erneut erfolgreich ausgeführt. Geprüft: dauerhafte Zuordnung über Kalenderkennung/UID/Wiederholung, echte Serienexpansion, verschobene Einzeltermine, manuell abweichende Fälligkeiten, fehlende/erneut auftauchende Termine, Verbindungsfehler, Zugriffsschutz und CSRF, wiederholte Speicheranfragen ohne Duplikate, Protokollübernahme ohne Doppelanlage, unveränderte Originaleinträge und Unterlagen, Nextcloud-Dokumentverweise sowie gelöschte Ursprungsunterlagen.

`scripts/meeting_checks.py` prüft mit fiktiven Kalenderdaten den vollständigen Ablauf Präsentation → Termin → Aufgabe → Cockpit → Protokoll, außerdem Abhaken, weitere Punkte, Nextcloud-Verweise und Desktop/Tablet/Mobil. Die vollständige bestehende Browserprüfung ist ebenfalls bestanden. PDF-Vorschau und Terminvorbereitung können gemeinsam bedient werden. Bildschirmbeispiele: `screenshots/meeting-preparation-desktop.png` und `screenshots/meeting-preparation-mobile.png`.

### Sammlungen für Ressourcen und Ideen (ersetzt)

**Überholt:** Dieser Stand wurde durch „Ressourcen an eine Notiz anhängen“ abgelöst; die eigenen Sammlungstabellen sind entfallen.

146 Python-Tests sowie die vollständige bestehende Browserprüfung und `scripts/collection_checks.py` bestanden. Geprüft: Mail in noch nicht vorhandene Wochenpost vormerken, freie Namen ohne vorherigen Klick übernehmen, Auswahl bestehender Ziele, eigene Ideen, Bearbeiten und Übernahmestatus, Rückverweise, Quellenerhalt einschließlich Anhängen, weitere Ressourcentypen, Entfernen ohne Löschen der Quelle, Verhalten bei gelöschten Quellen, Zugriffsschutz/CSRF, wiederholbare Schemaeinrichtung und Duplikatschutz. Die Autovervollständigung übernimmt freie Angaben beim Verlassen des Felds, ohne den Fokus aus dem nächsten Eingabefeld zurückzuholen. Desktop-, Tablet- und Mobilansicht geprüft; Bildschirmbeispiel: `screenshots/collection-mobile.png`.

### Ressourcen an eine Notiz anhängen (ersetzt die Sammlungen)

161 Python-Tests sowie die vollständige Browserprüfung, `scripts/handwriting_check.py` und `scripts/note_attach_checks.py` bestanden. Die Sammlungen als eigenes Objekt sind entfallen: kein Menüpunkt, keine Übersichtsseite, kein Übernahmestatus, keine quellenlosen Ideen; die Tabellen `collections`, `collection_items` und `collection_requests` werden beim Start abgelegt, zuvor geschriebene Hinweise wandern unter „Gesammelte Hinweise“ in den Text der jeweiligen Notiz. An ihre Stelle tritt **An Notiz anhängen** auf Basis der vorhandenen Ressourcenverknüpfungen. Geprüft: neue Notiz aus einem freien Namen ohne vorherigen Klick auf den Vorschlag, Wiederverwendung eines vorhandenen Ziels ohne Textänderung, Groß-/Kleinschreibung beim Abgleich, mehrfaches Anhängen ohne Dubletten, weitere Ressourcentypen, Lösen der Verknüpfung ohne Verlust von Quelle oder Notiz, gelöschte Quellen, Selbstverknüpfung, ungültige Ziele, Zugriffsschutz und CSRF, Vorschlagsreihenfolge mit Notizen zuerst sowie Desktop-, Tablet- und Mobilansicht. Bildschirmbeispiel: `screenshots/notiz-mit-verweisen.png`.

### Duplikatschutz bei Kalenderprotokollen

149 Python-Tests im vollständigen Lauf bestanden; anschließend zehn Terminvorbereitungstests einschließlich eines zusätzlichen Tests für zwei Serienvorkommen zur gleichen tatsächlichen Uhrzeit bestanden. Geprüft: Wiederverwendung manueller Protokolle, unveränderter Text und Tagesordnung, dauerhafte Zuordnung nach Umbenennung, Auswahl bei mehreren passenden Protokollen, Ausschluss abweichender Uhrzeiten, alte Kalendercaches und Ablehnung veralteter Terminformulare. Die Browserprüfung kontrolliert auch zwei aufeinanderfolgende Protokollaufrufe aus dem Tagescockpit.
