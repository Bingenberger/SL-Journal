# Schulleitungsjournal

Eine selbst gehostete Einzelplatz-Webanwendung nach dem beigefügten Lastenheft. Python 3.12+, Flask, SQLCipher/SQLite, serverseitige HTML-Oberfläche mit responsivem Layout. Keine CDN-Abhängigkeiten, externen Schriftarten oder Telemetrie.

## Lokal starten

Voraussetzungen: Python 3.12 oder neuer sowie `poppler-utils` (PDF-Vorschau) und optional LibreOffice (Vorschau von Word-, Excel- und PowerPoint-Dateien). Umgebung anlegen:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Einmalig initialisieren und starten:

```bash
.venv/bin/python manage.py init
.venv/bin/python manage.py run
```

**https://localhost:8443** öffnen. Den im Terminal ausgegebenen Einrichtungscode eingeben, „Authenticator einrichten“ wählen, QR-Code mit einer TOTP-App scannen und ein Passwort mit mindestens 14 Zeichen vergeben. Es gibt keine Standardzugangsdaten. Der Einrichtungscode wird beim Abschluss ungültig.

Der lokale Start bindet ausschließlich an 127.0.0.1. Beim ersten Start entsteht ein selbstsigniertes Zertifikat für localhost. Dieses Zertifikat muss für einen dauerhaft vertrauenswürdigen lokalen Betrieb im Browser/Betriebssystem als vertrauenswürdig eingerichtet werden; alternativ ein bereits vertrauenswürdiges Zertifikat übergeben:

```bash
.venv/bin/python manage.py run --cert /pfad/localhost.pem --key /pfad/localhost-key.pem
```

Für den Zugriff vom iPad den unten beschriebenen HTTPS-Server im freigegebenen Netz/VPN verwenden. Die lokale Entwicklungsinstanz ist nicht aus dem Netz erreichbar.

### Automatischer lokaler Betrieb unter Linux

Die Vorlagen in `deploy/local/` verwenden `%h/SL-Journal`. Bei anderem Projektpfad die beiden Pfade in jeder Service-Datei anpassen. Nach der ersten Einrichtung:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/local/journal* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now journal.service journal-sync.timer journal-maintenance.timer
```

Die Synchronisierung läuft alle fünf Minuten. Die tägliche Wartung wendet konfigurierte Löschfristen an und erstellt ein verschlüsseltes Backup. Ein ausgeschaltetes Dienstgerät kann keine Dienste ausführen; verpasste tägliche Wartung wird nachgeholt, wenn der Benutzerdienst wieder läuft. Ohne Timer bleibt der manuelle Synchronisieren-Button nutzbar.

## Bedienung

- **Tagescockpit:** Datum wählen oder vor-/zurückblättern, Termine, getrennte ein- und ausgehende Kommunikation, Gesprächsnotizen, Journal und Aufgaben sehen.
- **Einträge und Kommunikation:** Alle Karten zeigen dieselbe Reihenfolge — Betreff, Beteiligte, Zuordnungen, Aktionen. Vorgang, Projekt, Tag und Anhang tragen je ein eigenes Symbol und eine eigene Einfärbung; „Aufgabe“ und „An Notiz anhängen“ stehen als Schaltflächen unter einer Trennlinie; Beteiligte stehen hinter einem Personensymbol. Bei Mails zeigt jede Karte zusätzlich einen farbigen Rand und einen Richtungspfeil für eingegangen beziehungsweise gesendet: eingehend werden die Absender genannt, ausgehend die Empfänger — mit Namen statt Mailadressen, ab drei Beteiligten gekürzt. Von Hand eingetragene Beteiligte bleiben unverändert stehen.
- **Schnellerfassung:** Feste Buttons und Tastenkürzel `N` für Eintrag, `A` für Aufgabe, `/` für Suche. Einträge und Aufgaben werden in Dialogen erfasst; nach dem Speichern wird dieselbe Ansicht aktualisiert.
- **Journal:** Freitext direkt im Cockpit. Über „Erweitert“ sind mehrere Projekte, Kontakte, Tags, Anhänge und eine Aufgabe gleichzeitig möglich.
- **Einträge:** Markdown wird bereits während der Eingabe direkt im Schreibfeld formatiert und in der Detailansicht bereinigt dargestellt. Alle Typen sind editierbar. Text in der Detailansicht markieren und „Aufgabe aus Textauswahl“ wählen.
- **Projekte:** Mehrfachzuordnung von Einträgen, chronologische Übersicht, offene und erledigte Aufgaben sowie alle Anhänge. Beim Abschluss kann die Aufgabenliste als Jahresprozess gespeichert werden. Abgeschlossene Projekte bleiben durchsuchbar.
- **Aufgaben:** Fälligkeitsgruppen beziehen sich auf den angezeigten Tag. Ohne Datum gibt es eine eigene Liste. Erledigen und Wiederöffnen sind möglich; Klick auf den Aufgabentext öffnet die Bearbeitung. Bei mehreren Projekten im Herkunftseintrag wird standardmäßig das erste nach ID übernommen und kann geändert werden.
- **Kontakte:** Namen, Rolle/Institution und mehrere Mailadressen; beim Mailimport erfolgt die Zuordnung anhand der Adressen.
- **Suche:** Volltext in Titel, Text, Beteiligten, Absender und Tags, einschließlich archivierter Projektinhalte. Mehrere Suchwörter werden mit UND und Wortpräfixsuche kombiniert. Zusätzliche Typ- und Tagfilter. Anhangsinhalte werden nicht indexiert.
- **Jahresprozesse:** Anfang = ab 1., Mitte = ab 11., Ende = ab 21. des gewählten Monats. Eine fällige Erinnerung bleibt bis zur Bestätigung sichtbar. Die Bestätigung erzeugt genau ein Projekt je Prozess und Schuljahr sowie die Vorlagenaufgaben ohne festes Fälligkeitsdatum. Schuljahreswechsel ist am 1. August.

## Vorgänge im Schulalltag

**Vorgänge** stehen als eigener Menüpunkt neben den Projekten. Sie bündeln ungeplante Anliegen wie Elternbeschwerden, Rückfragen oder Probleme, deren nächste Schritte erst während der Bearbeitung entstehen. Projekte bleiben für geplante Vorhaben erhalten.

- Ein Vorgang hat einen Titel, optionale Markdown-Notizen, den Status **Offen / In Klärung / Erledigt** und eine optionale **Wiedervorlage**. Ein Schuljahr ist nicht erforderlich.
- Fällige und überfällige Wiedervorlagen offener Vorgänge erscheinen im Tagescockpit, bezogen auf den dort angezeigten Tag. Erledigte Vorgänge erscheinen im Filter „Erledigt“ und können wieder geöffnet werden.
- Auf der Vorgangsseite können Sie neue Einträge und Aufgaben anlegen oder vorhandene Einträge per Suche zuordnen. „Aus Vorgang lösen“ entfernt nur die Zuordnung.
- Einträge unterstützen mehrere Vorgänge sowie unabhängig davon Projekte und Tags. Die Auswahl verwendet Autovervollständigung, auch im Tagesjournal und bei Handzeichnungen.
- Aufgaben können einem Vorgang zugeordnet werden. Neue Aufgaben aus einem Eintrag und neue Unteraufgaben übernehmen dessen Vorgang als Ausgangswert; die Zuordnung kann geändert oder entfernt werden. Ein Statuswechsel des Vorgangs verändert den Erledigungsstand seiner Aufgaben nicht.
- Die Zuordnung einer importierten Mail zu einem Vorgang zählt ebenfalls als Bearbeitung. Im Posteingang kann direkt ein Projekt oder ein Vorgang ausgewählt werden.
- Vorgänge stehen in der Ressourcenverknüpfung und in der @-Suche der Markdown-Editoren bereit. Auf Vorgangsseiten werden auch Ressourcenverweise aus Einträgen angezeigt.

Bestehende Projekte, Einträge, Aufgaben und Ressourcenverknüpfungen werden beim Start erhalten; die neuen Tabellen und Spalten werden automatisch ergänzt.

## Handschriftliche Notizen und Skizzen

Über **Handschrift** in der oberen Leiste öffnen Sie ein großes Zeichenblatt mit lokal eingebundenem [Excalidraw](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/integration). Der Stift ist bereits ausgewählt; Radierer, Formen, Text, Farben, Verschieben und Rückgängig stehen in Excalidraw zur Verfügung. Mit Stift, Maus oder Touch schreiben; die Stifterkennung und Handballenunterdrückung hängen auch von Gerät und Browser ab.

- Nach einer kurzen Schreibpause wird automatisch gespeichert. Der Status zeigt an, ob alle Änderungen gesichert sind; „Jetzt speichern“ und Strg/Befehl+S speichern sofort.
- Eine neue Mitschrift wird als Notiz im Journal angelegt. Über „Zum Eintrag“ können Sie Projekte und Tags direkt unterhalb der Zeichenblätter zuordnen, jeweils mit Autovervollständigung. Neue Projektnamen werden als Vorschläge gesammelt. Beteiligte, Text und Aufgaben lassen sich ebenfalls ergänzen. Leere Anhangs- und Nextcloud-Bereiche werden bei Einträgen mit Handschrift ausgeblendet.
- An jedem bestehenden Eintrag, auch einem Protokoll, können Sie über „Zeichenblatt hinzufügen“ mehrere Blätter anlegen. Die Vorschau öffnet sich über „Weiterschreiben“ wieder im Editor.
- Unter den Zeichenblättern gibt es eine gemeinsame Ressourcensuche für den gesamten Eintrag: Gespräche, Protokolle, andere Einträge, Kontakte, Projekte, Tags, Aufgaben und Dokumentverweise. Rückverweise öffnen den gesamten Eintrag mit allen Zeichenblättern. Das Löschen einzelner Zeichenblätter verändert die Verknüpfungen nicht. Bestehende Blattverknüpfungen werden beim Start automatisch übernommen und doppelte Ziele zusammengefasst. „Entfernen“ löst nur die Verknüpfung; die Originale bleiben erhalten.
- „Zeichnung herunterladen“ sichert die bearbeitbare Excalidraw-Datei, auch bei einer unterbrochenen Verbindung. Am Eintrag steht ein PNG-Download bereit. Bei Speicherfehlern bleibt die Zeichnung geöffnet; bei ungesicherten Änderungen warnt der Browser vor dem Verlassen.
- Gleichzeitige Änderungen in mehreren Fenstern werden erkannt und überschreiben einander nicht. Bei einem Konflikt zuerst die lokale Zeichnung herunterladen.
- Zeichnungsdaten und Vorschauen liegen in der verschlüsselten Journal-Datenbank und sind Bestandteil der regulären Sicherungen. Skripte und Schriften werden ausschließlich lokal ausgeliefert. Es gibt keine Excalidraw-Cloud-Anbindung.
- Handschrift bleibt eine Zeichnung; automatische Texterkennung ist nicht enthalten. Bilder und Dateien können wie bisher am Eintrag angehängt werden.

Der Editor wird nur auf der Zeichenblattseite geladen. Nach Änderungen am Quellcode: `npm ci` und `npm run build:handwriting`. Die Builddatei entfernt ausdrücklich den Schrift-CDN-Fallback von Excalidraw und leert dessen mitgelieferte Dienstadressen samt öffentlichem Firebase-Schlüssel — Zusammenarbeit, Bibliothek und Cloud-Backend werden hier nicht verwendet, und solche Zeichenfolgen sollen nicht im Auslieferungsstand stehen. Beide Eingriffe brechen den Build ab, falls Excalidraw seinen Aufbau ändert; die CSP-Ausnahme für Style-Attribute gilt nur auf Zeichenblattseiten. Quellcode und Lizenzen liegen unter `frontend/handwriting*` bzw. `journal/static/excalidraw/`.

## Sitzungsprotokolle

Unter „Neuer Eintrag“ → „Art“ → „Protokoll“ stehen Tagesordnung, Text und Beschlüsse als getrennte Felder zur Verfügung. Alle drei unterstützen Live-Markdown und Ressourcenverlinkungen mit @. Beteiligte, Projekte, Tags, Anhänge, verknüpfte Dateien und mehrere Aufgaben funktionieren wie bei anderen Einträgen. Tagesordnung und Beschlüsse werden in der Volltextsuche berücksichtigt. „Protokoll anlegen“ bei einem Kalendertermin übernimmt Titel und Termin in ein neues Protokoll.

Bestehende Datenbanken werden beim Start automatisch erweitert; vorhandene Einträge und Verknüpfungen bleiben erhalten.

## Markdown direkt beim Schreiben

Tagesjournal, Eintragstext, Tagesordnung, Beschlüsse und Projektbeschreibung verwenden einen lokalen Live-Editor:

- `**fett**`, `*kursiv*`, Überschriften, Aufzählungen, nummerierte Listen, Zitate, Links und Code erhalten direkt im Eingabefeld ihre Formatierung.
- Markdown-Steuerzeichen werden ausgeblendet; beim Bewegen des Cursors in ein Steuerzeichen wird es zum Bearbeiten wieder sichtbar.
- Die kleine Werkzeugleiste bietet Fett, Kursiv, Überschrift, Listen und Zitat. `Strg/Befehl+B` und `Strg/Befehl+I` funktionieren für markierten Text.
- `Enter` setzt Listen fort. Rückgängig/Wiederholen bleiben im Editor verfügbar.
- Über „Markdown“ lässt sich im selben Feld auf den vollständigen Quelltext umschalten; „Formatiert“ aktiviert die Live-Darstellung wieder.
- Gespeichert wird weiterhin Markdown. Der Editor dekoriert den Originaltext, statt ihn in HTML umzuwandeln und zurückzukonvertieren. Tabellen, Fußnoten und sonstige importierte Syntax bleiben dadurch erhalten. Eingebettetes HTML und Bildverweise bleiben im Eingabefeld Text und laden keine externen Inhalte.

Die Bibliotheken werden lokal aus `journal/static/markdown-editor.js` ausgeliefert. Für den normalen Python-Start ist kein Node-Prozess erforderlich. Bei Änderungen am Editor-Quellcode:

```bash
npm ci
npm run build:editor
```

Quellcode: `frontend/markdown-editor.js`. Abhängigkeiten sind über `package-lock.json` festgeschrieben; Lizenzhinweise liegen neben dem Bundle. Der Editor verwendet [CodeMirror-Dekorationen](https://codemirror.net/examples/decoration/). Die nötigen Styles erhalten einen pro Antwort erzeugten CSP-Nonce; `unsafe-inline` wird nicht freigeschaltet. Zwei Angaben setzt der Editor als Style-Attribut (`tab-size`, `pointer-events`); solche Attribute bleiben gesperrt, beide stehen stattdessen in `journal/static/style.css`. Die Browserprüfung sammelt CSP-Verstöße über alle Seiten hinweg und lässt nur diesen Fall durchgehen.

## Symbole

Die Oberfläche verwendet [Phosphor Icons](https://phosphoricons.com) (MIT). Aus dem Paket werden nur die tatsächlich benötigten Symbole in ein Sprite geschrieben und mit jeder Seite ausgeliefert – als eigene Datei brächte das nichts, weil alle Antworten `Cache-Control: no-store` tragen.

```bash
npm ci
npm run build:icons
```

Die Oberfläche verwendet dabei eine feste Zuordnung von Handlung zu Symbol: Anlegen `+`, Speichern Haken, Abbrechen Kreuz, Bearbeiten Stift, Löschen Papierkorb, Suchen Lupe, Filtern Trichter, Zurücksetzen Pfeil, Verknüpfen Kettenglied, Aktualisieren Kreispfeile. Die Farbe zeigt den Rang: die Hauptaktion einer Ansicht ist gefüllt, Nebenaktionen sind umrandet, Aktionen in Karten und Listen klein umrandet, und Löschen ist rot und färbt sich beim Zeigen. Dieselben Zuordnungen kennzeichnen auch Inhalte — Vorgang, Projekt, Tag, Anhang und Beteiligte tragen überall dasselbe Symbol. `tests/test_button_language.py` prüft, dass keine beschriftete Schaltfläche ohne Symbol bleibt und dieselbe Handlung überall dasselbe Symbol trägt.

Das Skript `frontend/build-icons.mjs` erzeugt `journal/templates/icons.html` und den Lizenzhinweis `journal/static/icons.LICENSE.txt`; beide Dateien werden nicht von Hand bearbeitet. Im Template steht `{{ icon('projects') }}`: Die Namen benennen die Rolle im Programm, nicht die Form, sodass sich ein anderes Set allein in `frontend/build-icons.mjs` austauschen lässt. Symbole erben die Textfarbe und sind für Vorlesesoftware ausgeblendet – die Beschriftung steht im Text oder im `aria-label` der Schaltfläche. `tests/test_icons.py` stellt sicher, dass jedes verwendete Symbol im Sprite vorhanden ist.

## Archivpostfach

Unter Einstellungen Host, Benutzer, Passwort, Ordner und eigene erlaubte Mailadressen eintragen. TLS auf Port 993. Die App liest nur das Archivpostfach; sie setzt keine Gelesen-Markierung und löscht dort keine Nachricht.

Die unter „Eigene Mailadressen“ hinterlegten Adressen stehen auf jeder archivierten Mail und werden deshalb nicht als neuer Kontaktvorschlag gesammelt. Gibt es bereits einen Kontakt mit dieser Adresse, bleibt die Verknüpfung erhalten. Beim Speichern der Einstellungen werden früher gesammelte Vorschläge zu diesen Adressen entfernt.

Eingehende Nachrichten gezielt von einer eigenen Adresse weiterleiten; ausgehende Nachrichten per BCC an das Archivpostfach schicken. Nur die konfigurierten eigenen Absender werden verarbeitet. Unerlaubte Nachrichten werden beim Import übersprungen und bleiben auf dem Mailserver unverändert.

- Eigene Adresse als Originalabsender → ausgehende Mail.
- Als Anhang weitergeleitete Originalmails werden bevorzugt direkt ausgewertet.
- Thunderbird- und Apple-Mail-Weiterleitungsblöcke werden heuristisch verarbeitet, einschließlich typischer deutscher Datumsformate. Unklare Originalfelder bleiben leer und werden in der App zur Prüfung markiert; als Tageszuordnung dient ersatzweise das Datum der Archivmail.
- `[Projektname]` ordnet ein aktives Projekt mit genau diesem Namen zu und erhält die Kennung zusätzlich als Tag.
- Betreffähnlichkeit und frühere Absenderzuordnungen liefern im Eingangsstapel Vorschläge, die bestätigt werden.
- Originalmail und Anhänge werden verschlüsselt abgelegt.
- Message-ID, ersatzweise Inhalts-Hash, verhindert doppelte Importe. Importkennungen bleiben auch nach einer Löschung erhalten, damit ein Neuabruf gelöschte Inhalte nicht wieder einspielt.
- Pro Lauf höchstens 200 Mails. Eine Nachricht über 25 MB stoppt den Abruf vor dieser Nachricht; sie muss im Archiv geprüft/entfernt oder separat aufgeteilt werden.

Der Absenderfilter allein ersetzt keine Authentizitätsprüfung durch den Mailserver; die Archivadresse nicht veröffentlichen und auf dem Mailserver geeignete Annahmeregeln verwenden.

```bash
.venv/bin/python manage.py sync
```

Auch der Upload einzelner `.eml`-Dateien in den Einstellungen verwendet den Absenderfilter.

## Nextcloud

In Nextcloud einen App-Token erstellen. Unter Einstellungen CalDAV-URL (z. B. `https://cloud.example.de/remote.php/dav`), Benutzername und Token eintragen. Optional Kalendernamen zeilenweise auswählen; ohne Auswahl werden alle zugänglichen Kalender gelesen.

Dieselbe Verbindung dient dem Ansehen von Dokumenten (siehe unten). Beides liest nur; in Nextcloud wird nichts verändert.

Die Kalenderanbindung verwendet ausschließlich Kalenderabfragen. Serientermine werden server-/bibliotheksseitig aufgelöst; ganztägige und mehrtägige Termine werden auf den betreffenden Tagen dargestellt. Kalender haben unterschiedliche Farbmarkierungen und sichtbare Namen.

Die automatische Synchronisierung lädt die letzten 7 und die nächsten 23 Tage. „Aktualisieren“ im Tagescockpit lädt gezielt den angezeigten Tag. Bereits geladene Termine bleiben bei Verbindungsproblemen als verschlüsselter Cache mit Zeitstempel nutzbar; Cachedateien älter als 60 Tage werden bei erfolgreicher Synchronisierung entfernt. Termine sind keine persistierten Journalentitäten.

```bash
.venv/bin/python manage.py calendar --start 2026-09-01 --days 30
```

Live-IMAP und eine echte Nextcloud müssen mit den eigenen Zugangsdaten abschließend geprüft werden. Automatisierte Integrationstests verwenden Beispieldaten und einen simulierten CalDAV-Serverzugriff.

## Nextcloud-Dokumente im Journal ansehen

Ein verknüpftes Dokument lässt sich auf seiner Seite direkt lesen, ohne den Umweg über die Nextcloud-Anmeldung. Das Journal holt die Datei mit dem bereits hinterlegten App-Token **selbst** und zeigt sie an; der Browser spricht nie mit der Cloud.

| Dateiart | Darstellung |
| --- | --- |
| PDF | Alle Seiten, lokal gerendert, mit ‹ Zurück / Weiter › und den Pfeiltasten |
| Word, Excel, PowerPoint, OpenDocument, Text, CSV | Lokal nach PDF gewandelt und ebenso seitenweise lesbar |
| Bilder | Direkt angezeigt, auf eine sinnvolle Größe gebracht |
| Alles Übrige | Vorschaubild aus Nextcloud, sonst der Hinweis auf das Herunterladen |

### Dateien direkt aus der Nextcloud wählen

Im Dialog **Nextcloud-Dokument verknüpfen** öffnet **Aus Nextcloud wählen** einen Dateibrowser: Ordner anklicken zum Hineingehen, den Pfad oben zum Zurückgehen, ein Klick auf eine Datei übernimmt Link und Anzeigename. Das Suchfeld durchsucht ab zwei Zeichen den **gesamten** Bestand nach Dateinamen und zeigt zu jedem Treffer den Ordner, in dem er liegt. Versteckte Ordner der Synchronisierung (`.sync`, Papierkörbe und Ähnliches) werden übergangen. Den Link von Hand einzufügen bleibt möglich.

Gelesen wird ausschließlich Ihr eigener Dateibereich; Pfadangaben, die daraus hinausführen würden, weist das Journal ab, bevor eine Anfrage hinausgeht. Ohne eingerichtete Nextcloud erscheint die Auswahl gar nicht erst.

### An jeder Eintragsart

Dokumente hängen an Einträgen jeder Art – Protokoll, Gespräch, Notiz, Mail, Journal, Telefonat – und ebenso an Projekten. Zwei Wege führen dorthin:

* **Beim Schreiben**: der Eintragsdialog hat den Abschnitt **Nextcloud-Dokumente verknüpfen**. Der Dateibrowser bleibt hier offen, mehrere Dateien lassen sich nacheinander vormerken; bereits Gewähltes ist in der Liste markiert und darüber wieder zu entfernen. Gespeichert wird alles zusammen mit dem Eintrag: Schlägt ein Link fehl, entsteht auch kein halber Eintrag.
* **Auf der Eintragsseite**: der Abschnitt **Nextcloud-Dokumente** mit **Nextcloud-Dokument verknüpfen**.

Beide erscheinen nur, wenn eine Nextcloud eingerichtet ist.

An jedem verknüpften Dokument – am Eintrag, am Projekt, am Vorgang – steht **Vorschau** neben **In Nextcloud öffnen**. Die Vorschau erscheint im selben Hoverfenster wie bei PDF-Anhängen: beim Zeigen auf die Karte automatisch, per Klick auf die Schaltfläche festgestellt, mit Escape wieder zu. Darin führen **Herunterladen** und **Alle Seiten ansehen** weiter. Ein Klick auf den Titel öffnet wie bisher die Dokumentseite mit dem vollständigen Betrachter; von dort führt **Zurück zum Eintrag** genau dorthin, wo Sie hergekommen sind. Dokumente, deren Link nicht auf die eingerichtete Nextcloud zeigt, bekommen keine Vorschau angeboten.

**Herunterladen** liefert die Datei über das Journal aus — ebenfalls ohne Anmeldung in der Cloud. **In Nextcloud öffnen** führt wie bisher zum Original, wenn Sie dort bearbeiten wollen.

Erkannt werden alle Linkformen, die Nextcloud anbietet: der interne Link (`/index.php/f/123`), die Adresse aus der Dateiansicht (`/apps/files/files/123`, `?openfile=123`) und öffentliche Freigabelinks (`/s/token`). Links auf **andere** Server werden nie abgerufen — sonst könnte ein fremder Verweis das Journal dazu bringen, mit Ihrem Token anderswo anzufragen.

Für die Anzeige holt das Journal die Datei und hält sie höchstens 30 Minuten verschlüsselt unter `instance/cache/` vor, damit das Blättern nicht jedes Mal neu lädt; abgelaufene Einträge werden selbsttätig entfernt. Eine dauerhafte Kopie entsteht nicht, und die Sicherungen enthalten diesen Zwischenspeicher nicht.

Der Rückweg „Zurück zum Eintrag“ wertet die Herkunftsangabe des Browsers aus; dafür steht `Referrer-Policy` auf `same-origin`. Innerhalb des Journals wird die Herkunft also mitgesendet, an fremde Server – etwa beim Öffnen in Nextcloud – weiterhin nicht.

Für Office-Dateien wird LibreOffice auf dem Journal-Server benötigt (`soffice`); fehlt es, weicht die Anzeige auf das Vorschaubild aus Nextcloud aus. Nextcloud liefert solche Vorschauen allerdings nur sehr klein und einseitig — die lokale Wandlung ist der Grund, warum Tabellen und Texte hier lesbar sind. PDF-Vorschauen sind in Nextcloud häufig abgeschaltet; das Journal rendert sie ohnehin selbst.

## Obsidian migrieren

Zunächst prüfen, anschließend ausdrücklich importieren:

```bash
.venv/bin/python manage.py import-obsidian /pfad/zum/vault
.venv/bin/python manage.py import-obsidian /pfad/zum/vault --apply
```

Unterstützt werden UTF-8-Markdown, YAML-Frontmatter (`title/titel`, `date/datum`, `tags`, `projects/project`, `type`), Inline-Tags, Tagesnotizen mit ISO-Datum im Dateinamen, offene Markdown-Aufgaben mit `📅 YYYY-MM-DD` oder `[due:: YYYY-MM-DD]`, sowie direkt auflösbare lokale Markdown-/Wikilink-Anhänge. Notizen ohne Datum verwenden das Änderungsdatum der Quelldatei. Importierte Anhänge erscheinen in der Anhangsliste; Obsidian-spezifische Einbettungen und Plugin-Syntax bleiben im Text erhalten.

Bereits importierte relative Dateipfade werden übersprungen, auch wenn die Quelle später geändert wurde. Der Import ist eine einmalige Migration, keine laufende Vault-Synchronisierung. Er prüft jeden Eintrag einzeln und meldet ungültige Dateien, ohne die übrigen Importe abzubrechen. Dateien außerhalb des Vaults werden nicht als Anhänge übernommen. Vor dem Produktivimport eine Sicherung erstellen und den Prüfbericht ansehen.

## Einzelne Inhalte löschen

Neben dem Eintrag lassen sich auch Aufgabe, Projekt, Vorgang, Jahresprozess, Kontakt, einzelner Anhang und Dokumentverweis löschen. Jede Löschung fragt vorher nach und benennt, was bestehen bleibt.

| Was | Wo | Was bleibt |
| --- | --- | --- |
| Aufgabe | Aktionsmenü „…“ der Aufgabe | Unteraufgaben werden mitgelöscht. Gehört die Aufgabe zu einer Serie, bleiben bereits erzeugte Aufgaben; die Serie wird angehalten, wenn ihre Ausgangsaufgabe entfällt. |
| Projekt | Projektseite unten | Einträge und Aufgaben bleiben und verlieren nur die Zuordnung. |
| Vorgang | Vorgangsseite unter „Stand & Wiedervorlage“ | Einträge und Aufgaben bleiben und verlieren nur die Zuordnung. |
| Jahresprozess | Karte unter „Jahresprozesse“ | Bereits erzeugte Projekte und deren Aufgaben bleiben. |
| Kontakt | Kontaktseite | Einträge bleiben; der Name verschwindet aus ihrer Beteiligtenliste. |
| Anhang | Anhangszeile am Eintrag | Der Eintrag bleibt. Die verschlüsselte Datei wird vom Datenträger entfernt. |
| Dokumentverweis | Seite des Dokumentverweises | Die Datei in Nextcloud bleibt unverändert; nur der Verweis entfällt. |

Gelöschtes lässt sich nicht über die Oberfläche zurückholen. Der Weg dorthin führt über die verschlüsselte Sicherung (siehe „Wiederherstellen“).

## Verschlüsselung und Backup

- SQLCipher verschlüsselt die gesamte SQLite-Datei einschließlich Suchindex. Temporäre SQL-Daten liegen im Speicher.
- Anhänge und Kalendercache verwenden authentifizierte Fernet-Verschlüsselung.
- Schlüsseldatei standardmäßig `instance/master.key`, Dateimodus 0600. Mit `JOURNAL_KEY_FILE` kann der Schlüssel separat abgelegt werden.
- `instance/backup.key` schützt Sicherungsarchive mit einem unabhängigen Schlüssel. Diesen Schlüssel **separat vom Gerät und den Backups sicher verwahren**. Ein Backup enthält Datenbank, Anhänge und den Datenbankschlüssel innerhalb des verschlüsselten Archivs.
- Schlüssel dürfen nicht mit einem öffentlich zugänglichen Codeverzeichnis oder in Git veröffentlicht werden. Die Verschlüsselung schützt Dateien ohne Schlüssel; ein Angreifer mit Zugriff auf das laufende Benutzerkonto und dessen Schlüsseldateien wird dadurch nicht ausgeschlossen. Vollverschlüsselung des Dienstgeräts und restriktive Betriebssystemrechte gehören zum Betriebskonzept.
- Backups landen standardmäßig in `instance/backups`, alternativ über `JOURNAL_BACKUP_DIR` oder `--destination`. Für Schutz vor Geräteverlust die verschlüsselten Dateien zusätzlich auf ein separates zugelassenes Sicherungsziel übertragen.

```bash
.venv/bin/python manage.py backup
.venv/bin/python manage.py backup --destination /sicherungsziel/journal --keep-days 30
.venv/bin/python manage.py restore /pfad/journal-ZEIT.backup --key /sicher/backup.key --destination /pfad/neue-instanz
JOURNAL_INSTANCE=/pfad/neue-instanz .venv/bin/python manage.py run
```

Wiederherstellung überschreibt keine vorhandene Instanz. Danach werden alte Sitzungen ungültig; Passwort und Authenticator bleiben erhalten. Bei separat konfiguriertem `JOURNAL_KEY_FILE` den wiederhergestellten Datenbankschlüssel dort einsetzen. Die Backupimplementierung erstellt unter Schreibsperre eine konsistente verschlüsselte Datenbankkopie und packt nur referenzierte Anhänge. Das Archiv wird im Arbeitsspeicher aufgebaut; für sehr große Bestände ist entsprechend RAM erforderlich. Backupaufbewahrung: standardmäßig 30 Tage, ältere passende Dateien werden bei einem neuen erfolgreichen Backup entfernt.

### Löschfristen

In den Einstellungen je Eintragstyp Tage hinterlegen. Ohne Vorgabe erfolgt keine automatische Löschung. Die Fristen werden nicht als rechtliche Vorgabe vorgegeben; sie müssen aus dem schulischen Löschkonzept stammen.

```bash
.venv/bin/python manage.py purge
.venv/bin/python manage.py purge --apply
.venv/bin/python manage.py maintenance
```

Die Wartung entfernt fällige Einträge samt Anhängen und erstellt danach das neue Backup. Verknüpfte Aufgaben bleiben erhalten, deren Herkunftsverweis wird gelöst. Ältere Backups können gelöschte Inhalte bis zum Ende ihrer eigenen Aufbewahrungsfrist enthalten. Nach einer Wiederherstellung vor der erneuten Nutzung die aktuellen Löschfristen anwenden. Keine sichere Löschgarantie für externe Sicherungsmedien oder Dateisystem-Snapshots.

### Anmeldung zurücksetzen

Nur lokal mit Betriebssystemzugriff:

```bash
.venv/bin/python manage.py reset-auth
```

Dies ersetzt die Anmeldung über einen neuen Einrichtungscode; Inhalte bleiben erhalten. Ein verlorener Datenbankschlüssel kann dadurch nicht wiederhergestellt werden.

## Serverbetrieb: Ubuntu, nginx, systemd

Vorlagen liegen in `deploy/`; sie werden nicht automatisch auf dem System installiert. Betrieb und Netzfreigabe entsprechend der im Lastenheft offenen Entscheidung mit der zuständigen Stelle festlegen.

1. Eigenen Systembenutzer `journal` anlegen. Anwendung nach `/opt/schulleitungsjournal` kopieren, virtuelle Umgebung dort erstellen und `requirements.txt` installieren. Codeverzeichnis möglichst nur für den Administrator schreibbar.
2. `/var/lib/schulleitungsjournal` und `/var/backups/schulleitungsjournal` für den Benutzer `journal` mit Modus 0700 anlegen.
3. `/etc/schulleitungsjournal` als root mit Gruppe journal und Modus 0750 anlegen. `deploy/journal.env.example` als `journal.env` ablegen, Modus 0640. Den Datenbankschlüssel vor dem ersten Start erzeugen: beispielsweise mit `Fernet.generate_key()`, als `master.key` dort ablegen, Eigentümer root:journal, Modus 0640. Bei Übernahme einer bestehenden Instanz unbedingt deren Originalschlüssel verwenden.
4. Als Benutzer journal mit den Variablen aus `journal.env` `manage.py init` ausführen. Auch manuelle Verwaltungsbefehle müssen dieselben Instanz-/Schlüsselvariablen verwenden.
5. Die fünf Service-/Timerdateien aus `deploy/` nach `/etc/systemd/system/` kopieren, `systemctl daemon-reload`, anschließend `systemctl enable --now journal.service journal-sync.timer journal-maintenance.timer`.
6. nginx-Vorlage an Domain, Zertifikat und tatsächlichen VPN-Adressbereich anpassen; mittels `nginx -t` prüfen, dann aktivieren. Die Beispielkonfiguration verweigert alle anderen Adressen. Port 8088 bleibt an localhost gebunden — läuft nginx auf einem anderen Rechner, gilt stattdessen der folgende Abschnitt.
7. Einrichtung über HTTPS abschließen. Timerstatus und erste Sicherung prüfen: `systemctl list-timers 'journal-*'`, `journalctl -u journal-sync.service`, `journalctl -u journal-maintenance.service`.
8. Wiederherstellung auf einem separaten Testpfad erproben und verschlüsselte Sicherungen auf ein separates Ziel übernehmen.

### nginx auf einem anderen Rechner

Steht der Reverse Proxy nicht auf dem Anwendungsserver — etwa weil dieser in einem eigenen LXC-Container liegt und nginx den Netzzugang für mehrere Dienste regelt —, sind drei Stellen anzupassen. Die Vorlage dafür ist `deploy/journal-remote-proxy.conf`; sie kommt als Drop-in neben `journal.service`, damit ein späteres `git pull` die Anpassung nicht überschreibt:

```bash
mkdir -p /etc/systemd/system/journal.service.d
cp deploy/journal-remote-proxy.conf /etc/systemd/system/journal.service.d/override.conf
# beide Adressen darin eintragen, dann:
systemctl daemon-reload && systemctl restart journal.service
```

1. **`--listen`** bekommt die feste Adresse des Anwendungsservers statt `127.0.0.1`. Der Rechner braucht dafür eine feste IP; bei wechselnder Adresse startet der Dienst nicht mehr.
2. **`--trusted-proxy`** bekommt die Adresse des nginx-Rechners statt `127.0.0.1`. **Ohne diese Angabe verwirft waitress die Weiterleitungs-Header, die Anwendung sieht eine unverschlüsselte Verbindung und antwortet auf jeder Seite mit „HTTPS ist erforderlich" (400).** Wenn nach der Umstellung nichts mehr geht, liegt es fast immer hier und nicht an nginx.
3. **`proxy_pass`** in `deploy/nginx.conf` zeigt auf den Anwendungsserver. `proxy_set_header X-Forwarded-Proto https` muss gesetzt bleiben — fehlt es, erscheint dieselbe 400-Meldung. Die `allow`/`deny`-Regeln betreffen weiterhin die Clients und bleiben unverändert.

`JOURNAL_TRUST_PROXY=1` bleibt in der `journal.env` stehen.

Port 8088 spricht Klartext-HTTP und kennt keine eigene Zugangskontrolle: Wer ihn erreicht, spricht unmittelbar mit der Anwendung. Bisher lag er auf localhost, jetzt im Netz. Er gehört deshalb per Firewall auf die Adresse des nginx-Rechners beschränkt — in Proxmox über die Firewall am Container (zuverlässiger als `ufw` in einem unprivilegierten LXC): Input-Policy `DROP`, dazu `ACCEPT tcp/8088` von der nginx-Adresse und `ACCEPT tcp/22` von der Verwaltungsadresse.

Die Strecke zwischen nginx und Anwendungsserver läuft unverschlüsselt. Das ist vertretbar, solange dieses Netzsegment ausschließlich eigene Geräte umfasst; es ist aber ein Unterschied zum Betrieb auf einem einzelnen Rechner, bei dem die Daten das Gerät nie verlassen.

Prüfen lässt sich die Kette von der nginx-Maschine aus:

```bash
curl -I http://APP-ADRESSE:8088/
# 400 „HTTPS ist erforderlich" – an dieser Stelle richtig
curl -I -H 'X-Forwarded-Proto: https' -H 'X-Forwarded-Host: journal.schule.example' \
     http://APP-ADRESSE:8088/
# 302 zur Anmeldung – die Vertrauenskette steht
```

Bleibt es beim zweiten Aufruf bei 400, greift `--trusted-proxy` nicht; `journalctl -u journal.service` zeigt, mit welcher Quelladresse die Anfragen tatsächlich ankommen.

`JOURNAL_TRUST_PROXY=1` ist nur für den Betrieb hinter dem lokalen nginx vorgesehen. nginx ersetzt Forwarded-Header. Direkte externe Zugriffe auf den WSGI-Port sind nicht vorgesehen. Anmeldung benötigt HTTPS, starkes Passwort und TOTP. Cookies sind Secure/HttpOnly/SameSite=Strict, Formulare verwenden CSRF-Tokens, Fehlversuche werden serverseitig begrenzt. nginx-Zugriffslogs sind deaktiviert, damit Suchbegriffe nicht im Access-Log landen.

## Prüfen und Projektstruktur

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
node --check journal/static/app.js
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/browser_check.py
```

Die Browserprüfung erzeugt eine isolierte Instanz mit fiktiven Daten, prüft Einrichtung/Erfassung und responsive Ansichten und legt Screenshots unter `docs/screenshots/` ab. Sie verändert keine Produktivdaten.

| Datei | Zweck |
| --- | --- |
| `journal/app.py` | Webrouten, Authentifizierung, Eingaben |
| `journal/db.py` | Schema, SQLCipher, Einstellungen |
| `journal/domain.py` | Einträge, Aufgaben, Schuljahr, Jahresprozesse |
| `journal/integrations.py` | IMAP, Weiterleitungsparser, CalDAV-Cache |
| `journal/maintenance.py` | Backup, Wiederherstellung, Löschung, Migration |
| `journal/templates/`, `journal/static/` | Oberfläche |
| `manage.py` | Einrichtung und Verwaltungsbefehle |
| `deploy/` | Server- und lokale systemd-Vorlagen |
| `tests/` | Funktions- und Integrationstests |

Optionaler Beispielbestand, nur in einer eigenen leeren Instanz:

```bash
JOURNAL_INSTANCE=/tmp/journal-demo .venv/bin/python manage.py init
JOURNAL_INSTANCE=/tmp/journal-demo .venv/bin/python manage.py demo
JOURNAL_INSTANCE=/tmp/journal-demo .venv/bin/python manage.py run --port 8444
```

Die Implementierung verwendet die dokumentierten [SQLCipher-Schlüssel- und Integritätsfunktionen](https://www.zetetic.net/sqlcipher/sqlcipher-api/) und die lesende [CalDAV-Terminsuche mit Serienauflösung](https://caldav.readthedocs.io/stable/caldav/collection.html).

## Beteiligte und Autovervollständigung

Einträge erfassen Kontakte ausschließlich im Feld **Beteiligte**. Nach Name, Rolle oder Mailadresse suchen und einen Treffer auswählen; mehrere Beteiligte sind möglich. Die Vorschlagsliste zeigt höchstens zwölf Treffer und lässt sich mit Pfeiltasten, Enter und Tab bedienen. Unbekannte Namen können direkt eingegeben werden.

Beim Speichern erscheinen unbekannte Beteiligte unter **Kontakte → Kontaktvorschläge** mit Verweisen auf ihre Einträge. Dort lassen sie sich als Kontakt übernehmen, einem vorhandenen Kontakt zuordnen oder verwerfen. Eine Übernahme aktualisiert sämtliche betroffenen Einträge. Verworfene Vorschläge können wiederhergestellt werden; die ursprünglichen Beteiligten bleiben am Eintrag erhalten. Vorhandene Beteiligte und Kontaktverknüpfungen werden beim ersten Start der aktualisierten Version automatisch zusammengeführt.

**Tags** bieten vorhandene Begriffe an und erlauben neue Eingaben. **Projekte** bieten bestehende Projekte und offene Vorschläge an. Neue Namen lassen sich direkt eingeben und werden beim Speichern unter **Projekte → Vorschläge für neue Projekte** gesammelt. Das gilt für Einträge, die Schnellerfassung, Aufgaben und die Mailzuordnung. Vorschläge können als Projekt übernommen, einem bestehenden Projekt zugeordnet oder verworfen und wiederhergestellt werden. Zugehörige Einträge und Aufgaben werden bei der Übernahme automatisch verknüpft. Gleichnamige Vorschläge werden je Schuljahr zusammengefasst. Ausgewählte Werte lassen sich jeweils über das × entfernen.

### Rolle und Institution bei Kontakten

Rolle (z. B. Sachbearbeitung) und Institution (z. B. Schulamt) werden getrennt gespeichert. Das Institutionsfeld bietet bereits verwendete Namen zur Auswahl an. Im Kontaktbereich lässt sich nach einer Institution filtern und zusätzlich nach Namen oder Rolle suchen. Ein Klick auf die Institution eines Kontakts öffnet ebenfalls die gefilterte Liste. Die Beteiligten-Suche berücksichtigt auch Institutionen.

Vorhandene Angaben aus dem früheren Feld „Rolle / Institution“ bleiben unverändert in „Rolle“. Das neue Institutionsfeld bleibt bei diesen Kontakten zunächst leer und kann beim Bearbeiten ergänzt werden.

### Mehrere Aufgaben und Unteraufgaben

Im Eintragsdialog unter **Aufgaben aus diesem Eintrag anlegen** können mit **Weitere Aufgabe** mehrere Aufgaben samt eigenen Fälligkeitsdaten erfasst werden. Beim Bearbeiten eines bestehenden Eintrags werden neue Zeilen als zusätzliche Aufgaben angelegt; vorhandene Aufgaben bleiben erhalten. Leere Zeilen werden nicht gespeichert.

Aufgaben lassen sich über **Neue Unteraufgaben hinzufügen** im Aufgabendialog oder über **＋ Unteraufgabe** in der Aufgabenliste aufteilen. Unteraufgaben haben eine Ebene, eigene Termine und einen eigenen Erledigungsstatus. Sie übernehmen bei der Anlage Herkunftseintrag und Projekt beziehungsweise Projektvorschlag der Hauptaufgabe. Anschließend lassen sie sich einzeln bearbeiten. Die Liste zeigt den Fortschritt und Verweise zwischen Haupt- und Unteraufgaben.

Eine Hauptaufgabe kann erst abgeschlossen werden, wenn alle Unteraufgaben erledigt sind. Das Wiederöffnen einer Unteraufgabe oder Hinzufügen einer offenen Unteraufgabe öffnet auch eine bereits erledigte Hauptaufgabe wieder. Nach Abschluss der letzten Unteraufgabe wird die Hauptaufgabe ausdrücklich separat abgehakt.

### Ressourcen im Text verlinken

In Markdown-Textfeldern öffnet ein **@ direkt nach einem Leerzeichen** die Ressourcensuche, zum Beispiel **Siehe @Schulfest**. Danach Namen oder Suchbegriffe eingeben und einen Treffer anklicken oder mit Pfeiltasten und Enter/Tab auswählen. Escape schließt die Liste. Zur Auswahl stehen vorhandene Kontakte, Projekte (auch abgeschlossene), Tags, Einträge einschließlich Gesprächsprotokollen sowie Aufgaben. Typ, Institution, Schuljahr oder Datum helfen bei der Unterscheidung. Die Liste zeigt bis zu 20 Treffer; mit weiteren Suchbegriffen lässt sie sich eingrenzen.

Die Auswahl wird als normaler interner Markdown-Link gespeichert. Im gespeicherten Text ist der Link anklickbar; im Editor öffnet **Strg/Befehl + Klick** ihn in einem neuen Tab. Die Verlinkung ändert keine Kontakt- oder Projektzuordnungen des Eintrags. Mailadressen und ein @ ohne unmittelbar vorangestelltes Leerzeichen lösen keine Suche aus. Innerhalb von Code und bestehenden Links bleibt die Ressourcensuche deaktiviert.

### Nextcloud-Dokumente verknüpfen

Auf der Detailseite eines gespeicherten Eintrags oder Projekts steht neben den Anhängen **Nextcloud-Dokument verknüpfen** zur Verfügung. Den internen HTTPS-Link einer Datei oder eines Ordners aus Nextcloud kopieren und zusammen mit einem Anzeigenamen sowie optional einer Beschreibung speichern. Das Journal lädt die Datei nicht herunter und benötigt dafür keine Nextcloud-Zugangsdaten. **In Nextcloud öffnen** öffnet einen neuen Tab; die Anmeldung und Zugriffsrechte werden weiterhin von Nextcloud geprüft.

Derselbe Link kann an mehreren Einträgen und Projekten verwendet werden. Bereits hinterlegte Links werden als derselbe Dokumentverweis wiederverwendet; Name und Beschreibung bleiben dabei erhalten. Über **Bearbeiten** geänderte Angaben gelten für alle Verwendungen. Eine Projektseite zeigt sowohl direkt verknüpfte Dokumente als auch die Dokumente ihrer zugeordneten Einträge, jeweils ohne doppelte Karten.

Die @-Suche bietet die Verweise als **Nextcloud-Dokument** an. Ein solcher Textlink führt zur Dokumentseite im Journal und bleibt auch nach einer Änderung des hinterlegten Nextcloud-Links gültig. **Verknüpfung entfernen** löst nur die jeweilige Zuordnung. Die Datei in Nextcloud und der wiederverwendbare Dokumentverweis bleiben erhalten, damit bestehende Textlinks weiter funktionieren.

Die Journalsicherung enthält Namen, URLs, Beschreibungen und Zuordnungen, jedoch keine Kopien der Nextcloud-Dateien. Der Link öffnet den aktuellen Stand in Nextcloud; historische Dateiversionen werden dadurch nicht im Journal archiviert.

### Kontakte aus importierten Mails

Beim IMAP- und EML-Import werden Absender sowie Empfänger aus An, Cc und vorhandenen Bcc-Angaben als Beteiligte erfasst. Bekannte Mailadressen werden eindeutig passenden Kontakten zugeordnet; unbekannte Adressen erscheinen unter **Kontakte → Kontaktvorschläge**. Name und Mailadresse sind bei der Übernahme bereits ausgefüllt. Gleiche Adressen werden unabhängig von Großschreibung und unterschiedlichen Anzeigenamen wiederverwendet. Bei erkannten Weiterleitungen zählen die ursprünglichen Mailangaben. Der Absenderfilter des Archivpostfachs bleibt unverändert.

Beim ersten Start dieser Erweiterung werden bereits importierte Mails anhand ihrer gespeicherten Absender- und Empfängerangaben ergänzt. Vorhandene manuelle Kontaktzuordnungen bleiben erhalten.

### Weitergeleitete Mails als ursprüngliche Nachricht anzeigen

Erkannte Weiterleitungen werden mit ursprünglichem Betreff, Absender, Empfängern, Datum und Text gespeichert. Der äußere Weiterleitungsbetreff und der Weiterleitungskopf erscheinen dadurch nicht im angezeigten Nachrichtentext. Unterstützt sind unter anderem Thunderbird-Köpfe mit umgebrochenem Betreff und „Antwort an“, deutsch-/englischsprachige Weiterleitungsmarker, Outlook-Köpfe und Weiterleitungen als angehängte EML. Ein ursprünglicher Antwortbetreff wie „Re:“ bleibt erhalten. Die empfangene Archivmail bleibt unverändert als **Original.eml** am Eintrag.

Unvollständige oder nicht zuverlässig erkennbare Originalangaben werden weiterhin zur Prüfung markiert. Unveränderte, früher importierte Weiterleitungen lassen sich anhand ihrer gespeicherten Originaldateien korrigieren:

    .venv/bin/python manage.py repair-forwards
    .venv/bin/python manage.py repair-forwards --apply

Ohne --apply wird nur geprüft. Manuell geänderte Betreffzeilen oder Nachrichtentexte werden übersprungen; Projektzuordnungen, Aufgaben und Anhänge bleiben erhalten.

### PDF-Anhänge als Vorschau

Bei hochgeladenen oder per Mail importierten PDF-Anhängen erscheint nach kurzem Überfahren mit der Maus eine Vorschau der **ersten Seite**. Die Vorschau bleibt offen, solange sich der Zeiger über dem Anhang oder im Fenster befindet. Die Schaltfläche **Vorschau** öffnet das Fenster dauerhaft und funktioniert auch per Tastatur oder auf dem Handy. Escape, die Schließen-Schaltfläche oder ein Klick außerhalb schließen es. Der ursprüngliche Anhang kann weiterhin heruntergeladen werden.

Die erste Seite wird lokal mit Poppler gerendert und erst beim Öffnen angefordert. PDF-Datei und Vorschau gehen nicht an externe Dienste; Vorschauantworten werden nicht dauerhaft im Browser zwischengespeichert. Passwortgeschützte, beschädigte oder nicht innerhalb des Zeitlimits darstellbare PDFs zeigen einen Hinweis mit Downloadmöglichkeit. Nextcloud-Dokumentverweise werden weiterhin direkt in Nextcloud geöffnet.

Voraussetzung auf Ubuntu für die PDF-Vorschau:

    sudo apt install poppler-utils

Der lokale Entwicklungsrechner verfügt bereits über den Renderer. Die bestehende Serverkonfiguration benötigt keine zusätzliche Netzfreigabe.

### Wann eine Mail als bearbeitet gilt

Im Posteingang erscheinen nur Mails, die **weder einem Projekt zugeordnet sind noch Tags besitzen**. Bereits ein Tag genügt, um eine Mail als bearbeitet einzuordnen; eine Projektzuordnung ist dann optional. Das gilt auch für Tags, die beim Import aus dem Betreff übernommen wurden. Die Mail bleibt unter „Alle Einträge“, über die Suche und ihre Tags auffindbar. Werden alle Tags und Projektzuordnungen entfernt, erscheint sie wieder im Posteingang. Zähler und Hinweis im Tagescockpit verwenden dieselbe Regel.

### Tagübersicht

Der Menüpunkt **Tags** zeigt alle verwendeten Tags mit der Anzahl ihrer Einträge. Ein Klick öffnet die zugehörigen Inhalte; die Übersicht ist durchsuchbar. Groß-/Kleinschreibung wird beim Gruppieren und Filtern vereinheitlicht. Auch bereits bearbeitete Mails und Inhalte abgeschlossener Projekte bleiben dort erreichbar.

Neue Namen in der Vorgangsauswahl werden beim Speichern als **Vorgangsvorschläge** gesammelt. Unter „Vorgänge“ lassen sie sich als neuer Vorgang übernehmen oder einem vorhandenen Vorgang zuordnen. Alle betroffenen Einträge und Aufgaben werden dabei automatisch verknüpft. Vorschläge können verworfen und wiederhergestellt werden.

### Übersicht und Bedienung

Vorschlagsbereiche lassen sich aufklappen, größere Listen werden seitenweise angezeigt. In Aufgaben können Text, Projekt, Vorgang und Fälligkeit gemeinsam gefiltert werden. Tags lassen sich direkt im Posteingang vergeben. Auf schmalen Bildschirmen öffnet „Menü“ die Navigation; das Cockpit zeigt Aufgaben und Wiedervorlagen zuerst. Dialoge haben eine feste Speicherleiste und warnen beim Verwerfen ungespeicherter Änderungen. Unteraufgaben befinden sich im Aktionsmenü der Hauptaufgabe. Details und Bildschirmbeispiele: [UI-Verbesserungen](docs/UI-VERBESSERUNGEN.md).

### Wiederkehrende Aufgaben

Unter **Aufgaben → Wiederkehrende Aufgaben → Neue Aufgabenserie** oder im Aufgabendialog unter **Wiederkehrende Aufgabe** lässt sich eine Serie anlegen. Unterstützt werden wöchentliche und monatliche Wiederholungen mit wählbarem Abstand, quartalsweise Wiederholungen sowie **einzelne feste Termine** (ein Datum im Format `JJJJ-MM-TT` je Zeile). Ein optionales Enddatum begrenzt die Serie. Bei monatlichen Terminen wird beispielsweise der 31. Januar zum letzten Februartag und anschließend wieder zum 31. März.

Der Titel kann Platzhalter enthalten; eine Vorschau zeigt das Ergebnis. Sie beziehen sich immer auf die Fälligkeit der jeweiligen Aufgabe:

| Platzhalter | Bedeutung |
| --- | --- |
| `{KW}` | Kalenderwoche, zweistellig |
| `{KW_JAHR}` | Zur Kalenderwoche gehörendes ISO-Jahr |
| `{MONAT}` | Monatsnummer, zweistellig |
| `{MONATSNAME}` | Deutscher Monatsname |
| `{QUARTAL}` | Quartal 1 bis 4 |
| `{JAHR}` | Kalenderjahr |
| `{DATUM}` | Datum als TT.MM.JJJJ |

Beispiele: `Statistik KW{KW} abgeben`, `Auswertung {MONATSNAME} {JAHR}` oder `Quartalsbericht Q{QUARTAL}/{JAHR}`.

Die erste Aufgabe wird sofort angelegt. Weitere Aufgaben entstehen beim Öffnen der relevanten Journalansichten bis **14 Tage im Voraus**, unabhängig davon, ob ältere Aufgaben bereits erledigt sind. Projekt- und Vorgangszuordnungen, Herkunftseintrag und Unteraufgaben werden aus der ursprünglichen Aufgabe übernommen. Unteraufgaben erhalten einen eigenen offenen Status; ihre Termine behalten den Abstand zur Hauptaufgabe.

Die Serienübersicht bietet Bearbeiten, Pausieren und Fortsetzen. Änderungen an der Serie gelten für künftig erzeugte Aufgaben; bereits angelegte Aufgaben bleiben unverändert. Eine einzelne Aufgabe kann separat bearbeitet werden. Beim Fortsetzen werden noch nicht erzeugte Termine aus der Pause übersprungen. Bereits angelegte Aufgaben bleiben auch während der Pause erhalten.

Für die Erzeugung ohne geöffneten Browser kann `.venv/bin/python manage.py tasks` verwendet werden. Der vorhandene Wartungsbefehl `manage.py maintenance` erzeugt ebenfalls anstehende Aufgaben. Einzeltermine sind frei festgelegte Daten; eine Kopplung an externe Kalender ist damit nicht verbunden.

### Übergreifende Suche

Die Suchleiste im Kopfbereich durchsucht Einträge einschließlich ihres Volltexts, Aufgaben und Unteraufgaben, Projekte samt Beschreibung, Vorgänge samt Beschreibung sowie Kontakte nach Name, Rolle, Institution und Mailadresse. Tags und gespeicherte Nextcloud-Dokumentverweise werden ebenfalls gefunden. Erledigte Aufgaben und abgeschlossene Projekte bzw. Vorgänge bleiben auffindbar. Groß- und Kleinschreibung wird nicht unterschieden; mehrere Suchwörter werden gemeinsam berücksichtigt.

Während der Eingabe erscheinen bis zu zehn Vorschläge mit Ressourcentyp. Ein Klick öffnet das Ziel; mit Pfeiltasten und Enter lässt sich ein Vorschlag per Tastatur wählen. Escape schließt die Vorschläge. Enter ohne Auswahl bzw. „Alle Treffer anzeigen“ öffnet die gemeinsame Ergebnisliste mit 40 Treffern je Seite. Die Suchfelder innerhalb einzelner Fachbereiche behalten ihre jeweiligen Filterfunktionen. Inhalte von Anhängen, Nextcloud-Dateien und Zeichnungen werden nicht durchsucht.

### Vorschläge in Bereichssuchen und Kontaktfeldern

Auch die Suchfelder unter Aufgaben, Projekten, Vorgängen, Kontakten, Tags, Einträgen/Posteingang und auf der gemeinsamen Suchseite zeigen Vorschläge während der Eingabe. Die Bereichsvorschläge berücksichtigen die gesetzten Filter, beispielsweise Status, Institution, Projekt, Vorgang, Fälligkeit oder Eintragstyp. Ein Vorschlag öffnet den jeweiligen Inhalt; „Alle Treffer anzeigen“ und Enter ohne Auswahl führen die Suche mit den aktuellen Filtern aus.

Kontakte haben ein optionales Telefonnummernfeld, das in Kontaktliste und Kontaktansicht angezeigt und bei der Kontakt- sowie übergreifenden Suche berücksichtigt wird. Bestehende Kontakte erhalten zunächst ein leeres Feld. Beim Anlegen und Bearbeiten schlagen Name, Rolle, Institution, Mailadressen und Telefonnummer bereits verwendete Angaben vor. Jede Angabe bleibt frei eingebbar. Die Auswahl ergänzt nur das betreffende Feld und übernimmt keine anderen Kontaktangaben. Bei mehreren Mailadressen wird nur der gerade bearbeitete Teil ergänzt. Pfeiltasten und Enter wählen einen Vorschlag; Escape schließt die Liste.

### Unterlagen für einen Kalendertermin vormerken

An einem Eintrag, einem Anhang oder einem Nextcloud-Dokumentverweis steht **Für Termin vormerken** zur Verfügung. Besprechungspunkt ergänzen, einen Nextcloud-Termin über die Suche auswählen und **Vormerken** anklicken. Ein Protokoll für den Zieltermin ist dafür nicht erforderlich. Die Aufgabe erhält das Termindatum als Fälligkeit und verweist auf den Ursprungseintrag sowie die ausgewählte Unterlage. Dateien werden nicht kopiert.

Im Cockpit führt **Termine vorbereiten** zur Terminübersicht. Geladene Termine zeigen die Anzahl offener Besprechungspunkte; ein Klick öffnet die Aufgaben samt Unterlagen. Dort können weitere Punkte ergänzt, bearbeitet oder abgehakt werden. Mit **Protokoll zum Termin anlegen** entsteht ein Protokoll mit Datum, Uhrzeit und Titel des Termins sowie den zu diesem Zeitpunkt offenen Punkten als Tagesordnung. Erneutes Anklicken öffnet dasselbe Protokoll. Bereits erledigte Punkte bleiben in der Terminansicht erhalten. Die verknüpften Aufgaben und Unterlagen werden auch beim Protokoll angezeigt; später hinzugefügte Punkte sind dort im Aufgabenbereich sichtbar, ohne den bereits geschriebenen Protokolltext zu verändern.

Die Terminauswahl verwendet gespeicherte Kalenderdaten. Beim ersten Vormerken werden diese automatisch geladen, sofern Nextcloud eingerichtet ist. **Kalender aktualisieren** lädt 90 Tage ab dem wählbaren Startdatum. Für weiter entfernte Termine kann das Startdatum angepasst werden. Die bestehende Kalenderaktualisierung im Cockpit und über `manage.py sync` bleibt verfügbar. Nextcloud-Termine werden ausschließlich gelesen.

Die Verknüpfung verwendet Kalenderkennung, Termin-UID und bei Serien die jeweilige Wiederholung. Verschiebungen und Umbenennungen mit unveränderter Kennung erhalten die Zuordnung. Noch offene Aufgaben mit dem bisherigen Termindatum werden auf das neue Datum gesetzt; individuell abweichende Fälligkeiten und erledigte Aufgaben bleiben unverändert. Wird ein Termin bei einem erfolgreichen Abgleich nicht mehr gefunden, bleibt die Vorbereitung mit einem Hinweis erhalten. Ein Verbindungsfehler entfernt keine Termine. Wird eine ursprüngliche Unterlage gelöscht, bleibt der Besprechungspunkt mit dem Hinweis auf die fehlende Unterlage bestehen.

### Mails und andere Ressourcen an eine Notiz anhängen

An einem Eintrag und in den Eintragslisten steht **An Notiz anhängen** zur Verfügung. Eine vorhandene Notiz über die Autovervollständigung wählen oder einen neuen Namen eingeben, etwa **Wochenpost KW 42** — ein neuer Name legt beim Speichern eine Notiz mit diesem Titel an. Vorhandene Einträge behalten Titel, Text und Eintragstyp; Notizen stehen in der Vorschlagsliste vorn, andere Eintragsarten sind ebenfalls wählbar.

Der Verweis erscheint bei der Notiz unter **Verknüpfte Ressourcen**, die Quelle zeigt den Rückverweis. Mail, Anhänge und Text bleiben unverändert an ihrem Platz; es wird nichts kopiert. Dieselbe Quelle wird je Notiz nur einmal verknüpft, wiederholtes Anhängen erzeugt also keine Dubletten. **Entfernen** löst allein die Verknüpfung; Quelle und Notiz bleiben bestehen.

Aus der Notiz heraus funktioniert dieselbe Verbindung in der anderen Richtung: Unter **Ressource verknüpfen** lassen sich Einträge, Projekte, Vorgänge, Kontakte, Aufgaben, Tags und Nextcloud-Dokumentverweise auswählen. Den Text der Notiz — etwa die ausgearbeitete Wochenpost — schreiben Sie wie bei jedem Eintrag über **Eintrag bearbeiten**.

### Vorhandene Protokolle zu Kalenderterminen erkennen

Vor der Neuanlage wird zuerst die gespeicherte Terminzuordnung geprüft. Fehlt diese, sucht das Journal nach Protokollen mit gleichem Datum und Titel (ohne Beachtung der Groß-/Kleinschreibung). Wenn beide Uhrzeiten vorhanden sind, müssen sie übereinstimmen. Genau ein Treffer wird geöffnet und dauerhaft zugeordnet, ohne Text oder Tagesordnung zu verändern. Bei mehreren Treffern erscheint eine Auswahl mit Vorschau; ein zusätzliches Protokoll lässt sich dort nur ausdrücklich anlegen. Das gilt auch für ältere Kalenderdaten ohne dauerhafte Termin-ID. Einmal zugeordnete Protokolle bleiben nach einer Umbenennung erreichbar.

### Sprachi: kurze Audioaufnahme

In der Kopfzeile öffnet **Sprachi** den Aufnahmedialog. **Aufnahme starten** fragt den Mikrofonzugriff des Browsers an. Anschließend mit **Aufnahme stoppen** beenden, optional anhören und mit **Im Tagesjournal speichern** ablegen. Die Aufnahme wird als Journaleintrag am heutigen Datum (Europe/Berlin) gespeichert, unabhängig vom gerade betrachteten Journaltag. Im Tagesjournal und in der Eintragsansicht steht ein Audioplayer bereit; der Anhang lässt sich auch herunterladen.

Die Aufnahme läuft über HTTPS in einem Browser mit MediaRecorder-Unterstützung. Sie endet nach spätestens zehn Minuten; die Uploadgrenze beträgt 25 MB. Audio wird wie andere Anhänge verschlüsselt gespeichert. Beim Abbrechen wird eine ungespeicherte Aufnahme nach Rückfrage verworfen; bei einem Speicherfehler bleibt sie im geöffneten Dialog für einen erneuten Versuch erhalten.

## Lizenz und Mitwirkende

Der eigene Quellcode steht unter der MIT-Lizenz, siehe [LICENSE](LICENSE).

Mitgelieferte Fremdbestandteile behalten ihre eigenen Lizenzen; die Hinweise liegen jeweils neben dem Bundle:

| Bestandteil | Ort | Lizenzhinweis |
| --- | --- | --- |
| CodeMirror 6 (Markdown-Editor) | `journal/static/markdown-editor.js` | `journal/static/markdown-editor.LICENSE.txt` |
| Excalidraw (Zeichenblätter) | `journal/static/excalidraw/` | im selben Ordner |
| Phosphor Icons | `journal/templates/icons.html` | `journal/static/icons.LICENSE.txt` |

Python-Abhängigkeiten stehen in `requirements.txt`, die Frontend-Pakete sind über `package-lock.json` festgeschrieben.

## Hinweis für alle, die das Journal übernehmen

Dieses Repository enthält **keine** Daten. Der Ordner `instance/` — Datenbank, Schlüssel, Anhänge, Zertifikate, Sicherungen — entsteht erst bei `manage.py init` auf Ihrem eigenen Rechner und ist von der Versionsverwaltung ausgeschlossen. Legen Sie ihn niemals in ein Repository, auch nicht in ein privates: Er enthält die Schlüssel zur verschlüsselten Datenbank.

Die App ist für **eine** Schulleitung gedacht, hinter dem eigenen Netz oder VPN, mit Passwort und zweitem Faktor. Sie ist nicht darauf ausgelegt, offen im Internet zu stehen.
