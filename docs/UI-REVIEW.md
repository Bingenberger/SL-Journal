# UI-Review: Übersichtlichkeit und Bedienbarkeit

Stand des Reviews: 23.09.2026. Die nachfolgend beschriebenen Befunde beziehen sich auf die damalige Oberfläche. Umsetzung am 24.09.2026: siehe [UI-Verbesserungen](UI-VERBESSERUNGEN.md).

## Umfang und Methode

Browserprüfung mit einer isolierten Datenbank und ausschließlich fiktiven Daten: 100 Kontakte, acht neue Projekt- und Vorgangsvorschläge, neun Kontaktvorschläge, Aufgaben, Mails und ein Protokoll. 15 Ansichten jeweils bei 1440, 768 und 390 Pixeln Breite: Cockpit, Posteingang, Einträge, Aufgaben, Projekte und Projektdetail, Vorgänge und Vorgangsdetail, Kontakte und Kontaktdetail, Tags, Protokoll, Jahresprozesse, Einstellungen und Dokumentdetails. Zusätzlich Eintragsdialog und Handschrift visuell geprüft; weitere Dialoge, Anmeldung, Einrichtung und Fehlerseite anhand der Vorlagen geprüft.

Alle 45 Seitenaufrufe erfolgreich, keine JavaScript-Laufzeitfehler, kein horizontaler Seitenüberlauf in diesen Ansichten. Das allein belegt keine gute Bedienbarkeit: einzelne Felder und wichtige Inhalte können trotzdem schlecht erreichbar sein. Keine vollständige Screenreader-, Kontrast- oder Prüfung mit physischem Touch/Stift durchgeführt. Native Datumsfelder in Screenshots folgen der Sprache des Testbrowsers.

[Messwerte](ui-review/measurements.json) und Screenshots im Ordner `ui-review/` dokumentieren die Prüfung.

## Priorisierte Befunde

### 1. Hoch: Ungespeicherte Eingaben gehen beim Schließen verloren

Reproduziert: Neuer Eintrag → Titel eingeben → Esc → erneut Neuer Eintrag. Das Titelfeld ist leer, eine Warnung erscheint nicht. `openDialog()` setzt das Formular zurück; Schließen und Esc sichern den Entwurf nicht. Bei längeren Gesprächsnotizen oder Protokollen ist das besonders ärgerlich.

**Änderung:** Geänderte Formulare vor unbeabsichtigtem Schließen schützen. Wiederaufnahme eines Entwurfs anbieten; dauerhafte Entwürfe gegebenenfalls in der vorhandenen verschlüsselten Speicherung ablegen. Dieselbe Regel für Einträge, Aufgaben und Bearbeitungsdialoge verwenden. Handschrift hat bereits eine eigene Sicherungs- und Warnlogik.

### 2. Hoch: Vorschläge verdrängen die eigentlichen Listen und deren Suche

Kontakte, Projekte und Vorgänge zeigen sämtliche Vorschläge vor dem Bestand. Bereits bei neun Kontaktvorschlägen beginnt der Kontaktfilter auf dem Desktop bei rund 1412 Pixeln, auf dem Smartphone bei 2455 Pixeln. Bei acht Vorgangsvorschlägen beginnt die mobile Vorgangsliste erst bei rund 2239 Pixeln. Auch ein leerer Vorschlagsbereich beansprucht dauerhaft Platz.

**Änderung:** Suche, Filter und Bestand zuerst. Vorschläge als kompakte, aufklappbare Zeile „9 neue Vorschläge“ oder eigener Reiter. Zahl direkt am jeweiligen Bereich anzeigen. Übernehmen, bestehendem Objekt zuordnen und Verwerfen bei Kontakten, Projekten und Vorgängen gleich bedienen.

Belege: [Kontakte Desktop](ui-review/people-1440.png), [Vorgänge mobil](ui-review/cases-390.png).

### 3. Hoch: Mobile Cockpit-Reihenfolge versteckt dringende Aufgaben

Bei schmalen Ansichten rutscht die gesamte rechte Cockpitspalte unter Journal und Kommunikation. Im Beispielbestand erscheint die erste Aufgabe auf dem Tablet erst bei rund 3778 Pixeln, auf dem Smartphone bei 4221 Pixeln. Wiedervorlagen stehen ebenfalls erst in dieser späten Spalte.

**Änderung:** Auf Tablet und Smartphone zuerst „Heute wichtig“ mit überfälligen/heutigen Aufgaben und Wiedervorlagen, anschließend Termine und schnelle Erfassung. Längere Tageschronik dahinter oder einklappbar. Leere Terminbereiche kompakt halten.

### 4. Hoch: Erfassungsdialoge sind lang, Speichern ist außer Sicht

Der normale Eintragsdialog hat im Test auf dem Desktop 1284 Pixel Scrollinhalt bei 898 Pixel sichtbarer Höhe. Mobil sind es 1429 bei 791 Pixeln. Die Speicherschaltflächen liegen zunächst außerhalb des sichtbaren Dialogbereichs; Protokolle ergänzen weitere Textfelder.

**Änderung:** Speichern/Abbrechen in einer dauerhaft sichtbaren Dialogfußzeile. Titel und Inhalt priorisieren; Zuordnungen als gemeinsame Gruppe, Anhänge und zusätzliche Aufgaben einklappbar. Datum/Uhrzeit kompakter. Im Aufgabendialog Projekt und Vorgang zusammenstellen: Der Vorgang steht derzeit erst nach den Unteraufgaben. Geerbte Zuordnungen konkret anzeigen, statt sie nur in einem Hilfetext zu erklären.

Beleg: [Eintragsdialog mobil](ui-review/entry-dialog-390.png).

### 5. Hoch: Leerer Handschriftbereich steht vor Texten und Protokollen

Auch ein reines Protokoll ohne Zeichnung beginnt mit einer großen Box „Handschrift & Skizzen“. Der eigentliche Text folgt darunter. Leere Anhangs- und Dokumentbereiche erzeugen zusätzliche Flächen ohne Inhalt.

**Änderung:** Ohne vorhandene Zeichnungen nur eine dezente Aktion „Zeichenblatt hinzufügen“ zeigen. Bei tatsächlichen Handzeichnungen den großen Zeichenbereich erhalten. Leere Zusatzbereiche auf kompakte Aktionen reduzieren; vorhandene Inhalte weiterhin direkt anzeigen.

Beleg: [Protokoll Desktop](ui-review/protocol-1440.png).

### 6. Hoch: Mobile Navigation und Filter sind schwer erfassbar

Bei 390 Pixeln ist die Navigationsleiste 358 Pixel breit, ihr Inhalt aber 1011 Pixel. Sichtbar sind im Wesentlichen Cockpit, Posteingang und Aufgaben; auch auf der Vorgangsseite bleibt der aktive Bereich zunächst außerhalb des sichtbaren Ausschnitts. Im Posteingang schrumpft der Typfilter auf einen schmalen Pfeil ohne lesbare Auswahl. Kein Seitenüberlauf bedeutet hier nicht, dass alle Bedienelemente sinnvoll nutzbar sind.

**Änderung:** Eindeutiges mobiles Navigationsmenü mit sichtbarem aktuellem Bereich. Filter mobil untereinander oder in einem beschrifteten Filterbereich anordnen und ausgewählte Filter als verständliche Chips zeigen. Kopfbereich kompakter halten.

Belege: [Vorgangsdetail mobil](ui-review/case-390.png), [Posteingang mobil](ui-review/inbox-390.png).

### 7. Mittel: Lesbarkeit und Trefferflächen verbessern

Metadaten, Tags und Hinweise sind häufig nur 9–11 Pixel groß und sehr hell. Aufgaben-Checkboxen messen 16 × 16 Pixel am Desktop und 20 × 20 Pixel mobil. Gerade beim schnellen Arbeiten mit Touch oder Stift sind diese Ziele klein.

**Änderung:** Relevante Metadaten größer und dunkler setzen. Klickflächen unabhängig von der sichtbaren Icongröße vergrößern. Fälligkeit und Bearbeitungsstatus nicht ausschließlich durch Farbe hervorheben. Farben anschließend gezielt auf Kontrast prüfen.

### 8. Mittel: Listen auf wachsende Bestände vorbereiten

100 Kontakte werden als große Karten auf einer einzigen Seite dargestellt; im Test ist die mobile Kontaktseite über 31.000 Pixel hoch. Suche und Institutionenfilter existieren, werden aber durch die Vorschläge verdeckt. Aufgaben haben Statusreiter, jedoch keine Textsuche oder Projekt-/Vorgangsfilter. Projekte haben keine eigene Suche. Chroniken können unbegrenzt lang werden.

**Änderung:** Kontakte standardmäßig als kompakte Liste mit Name, Rolle und Institution, bei Bedarf Kartenansicht. Aufgaben nach Text, Vorgang, Projekt und Fälligkeit filtern. Projekte durchsuchen können. Größere Listen und Chroniken portionsweise anzeigen; Trefferzahl und Filterzustand sichtbar halten.

### 9. Mittel: Häufige Aktionen vereinheitlichen und reduzieren

Die Aufgabenübersicht besitzt weiterhin „Neue Aufgabe“ im Hauptteil und „Aufgabe“ im Header. Jede Hauptaufgabe zeigt dauerhaft „+ Unteraufgabe“, auch wenn man nur die Liste überblicken möchte. Beschriftungen wechseln zwischen „Neu“, „Eintrag“, „Erweitert“ und „Neuer Eintrag“.

**Änderung:** Allgemeine Neuanlage im Header belassen. Lokale Aktionen behalten, wenn sie einen konkreten Kontext übernehmen, beispielsweise „Aufgabe zu diesem Vorgang“. Seltenere Aktionen in Details oder ein Aktionsmenü verlagern. „Erweitert“ durch eine verständliche Bezeichnung wie „Ausführlichen Eintrag schreiben“ ersetzen.

Beleg: [Aufgabenübersicht](ui-review/tasks-1440.png).

### 10. Mittel: Posteingang sollte Tags direkt zuordnen können

Projekt und Vorgang können direkt an der Mail ausgewählt werden. Für Tags muss man „Bearbeiten / Vorgang / Tags“ öffnen und das umfangreiche Formular nutzen, obwohl ein Tag für die Bearbeitung ausreicht. Neue Vorgangs-/Projektvorschläge erscheinen bereits als Chips, die Mail bleibt bis zur tatsächlichen Zuordnung aber unbearbeitet.

**Änderung:** Kompakte gemeinsame Zuordnung mit Projekt, Vorgang und Tags. Klar zwischen „Vorschlag vorgemerkt“ und „zugeordnet/bearbeitet“ unterscheiden. Optional mehrere Mails gemeinsam zuordnen. Filter und Leseposition nach einer Aktion erhalten.

### 11. Mittel: Suchumfang und Rückwege klarer machen

Die Kopfsuche heißt „Journal durchsuchen“, öffnet aber ausschließlich die Volltextsuche in Einträgen. Aufgaben, Projekte, Vorgänge und Kontakte sind keine eigenständigen Treffer. Kontakt- und Dokumentdetails haben keinen vergleichbaren Rücklink wie Projekte/Vorgänge. Eintragsdetails führen „Zum Tag“, auch wenn man aus einem anderen Zusammenhang gekommen ist.

**Änderung:** Kurzfristig „Einträge durchsuchen“ nennen; perspektivisch eine gemeinsame Suche mit nach Typ gruppierten Treffern. Kontextbezogene Rückwege inklusive vorheriger Filter anbieten.

### 12. Niedriger: Einstellungen und Hinweise stärker an Abläufen ausrichten

„Jetzt synchronisieren“ steht außerhalb des Einstellungsformulars und verwendet daher die zuletzt gespeicherten Daten. Nach dem Eingeben neuer Zugangsdaten ist dieser Zusammenhang nicht offensichtlich. Die Einstellungen kombinieren Verbindungen, Löschfristen, Import und Sicherung auf einer langen Seite. Hilfetexte zu Unteraufgaben nennen nur das Projekt, obwohl auch der Vorgang übernommen wird.

**Änderung:** „Speichern und Verbindung prüfen“ sowie Status direkt am betreffenden Dienst. Einstellungen in klar getrennte Abschnitte gliedern. Kurze Hilfetexte an tatsächliches Verhalten anpassen. Bei der Handschrift optional Export unter weitere Aktionen verschieben, um Schreibfläche zu gewinnen; die bestehende Speicheranzeige erhalten.

## Bewährte Elemente erhalten

- Einheitliche Farben, Karten und gut erkennbare Seitenüberschriften.
- Inhaltlich sinnvolle Trennung zwischen Projekten, Vorgängen und Tags.
- Autovervollständigung mit Vorschlägen und erkennbare Zuordnungs-Chips.
- Protokollgliederung in Tagesordnung, Text und Beschlüsse.
- Handschrift mit automatischem Speichern und erkennbarem Speicherstatus.
- Eigene Institutionenfilterung und direkte Ressourcenverweise.
- Beschriftete Passwort-/Authenticatorfelder und Tastatur-Fokusmarkierungen.

## Empfohlene Reihenfolge

1. Schutz ungespeicherter Eingaben und ständig erreichbares Speichern.
2. Vorschläge kompakt darstellen; leere Zusatzbereiche reduzieren.
3. Mobile Navigation, Filter und Cockpit-Reihenfolge korrigieren.
4. Lesbarkeit, Trefferflächen und Aufgabenaktionen verbessern.
5. Kompakte Listen, zusätzliche Filter, direkte Tagzuordnung und gemeinsame Suche.

Abnahmekriterien für eine Umsetzung: Suche bei Kontakten/Vorgängen ohne vorheriges Scrollen erreichbar; Speichern in langen Dialogen sichtbar; kein kommentarloser Entwurfsverlust; dringende Cockpit-Inhalte mobil vor der langen Chronik; Typfilter mit lesbarem Wert; vorhandene Zuordnungen und Daten bleiben erhalten.
