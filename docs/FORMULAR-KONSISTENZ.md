# Prüfung der Eingabemasken

Stand: 24. September 2026. Die unten dokumentierten Befunde wurden anschließend behoben.

## Umsetzung

- Aufgaben gruppieren Projekt und Vorgang unter „Zuordnungen“, getrennt von der Fälligkeit.
- Pflichtfelder tragen ein Sternchen; die Dialoge erklären die Kennzeichnung. Beschriftungszusätze stehen gemeinsam mit dem Feldnamen statt auf einer zusätzlichen Zeile. Verbindungsabhängige Anforderungen werden in den Einstellungen gesondert erläutert.
- Dokumentbeschreibungen verwenden den gemeinsamen Markdown-Editor und werden auf der Dokumentseite als Markdown ausgegeben.
- Kontakt, Projekt, Vorgang, Aufgabe, Unteraufgabe und Jahresprozess unterscheiden Anlegen und Bearbeiten in der Überschrift.
- Einzelne Wiederholungstermine besitzen Datumsauswahl-Zeilen mit Hinzufügen/Entfernen. Die zusätzliche Texteingabe bleibt mit diesen Zeilen synchronisiert.
- Der Nextcloud-Dialog fokussiert zuerst den Link.
- Mailadresslisten verwenden kompakte Eingabefelder und denselben Hinweis zur Kommatrennung. Die Kontakt-Autovervollständigung bleibt erhalten.
- Auswahlmasken sind kompakter; vergleichbare Standardmasken verwenden dieselbe Breite.

Validierung: alle 162 automatisierten Tests erfolgreich; isolierte Browserprüfungen für Wiederholungsserien einschließlich Speichern, Wiederöffnen, Texteingabe und Entfernen von Terminen sowie Dokumentbearbeitung, Anfangsfokus und Dialogüberschriften. Erneute Prüfung aller 13 Dialoge bei 1440 und 390 Pixeln: kein horizontaler Überlauf, Fußleisten sichtbar. Die verlinkten Screenshots zeigen den überarbeiteten Stand. Die folgende Befundliste dokumentiert den Ausgangszustand.

## Umfang und Ergebnis

Die 13 vorhandenen Dialoge wurden in einer isolierten Testinstanz bei 1440 × 1000 und 390 × 844 Pixeln geöffnet und hinsichtlich Aufbau, Felddarstellung und erreichbarer Aktionen geprüft. Ergänzend wurden die Vorlagen für Einstellungen, Eintragsansicht und Handzeichnungen sowie die gemeinsamen Formular-, Editor- und Autovervollständigungs-Komponenten gelesen. Produktive Daten wurden dafür nicht verwendet. Die Prüfung ersetzt keine vollständigen Tests aller Speichervorgänge, Validierungen oder der Bedienung mit Screenreadern.

Die gemeinsame gestalterische Grundlage ist konsistent: Schrift, Farben, Feldrahmen, Fokusdarstellung und die Anordnung der Dialogaktionen werden weitgehend wiederverwendet. In allen 26 geprüften Dialogansichten gab es keinen horizontalen Überlauf; die Fußleisten waren sichtbar. Alle Dialoge besitzen einen Bereich für Fehlermeldungen. Die Kontaktmaske trennt Rolle, Institution und Telefonnummer auch auf schmalen Bildschirmen übersichtlich.

Bei der Struktur und bei vergleichbaren Eingaben bestehen jedoch folgende Unterschiede:

## Befunde und Empfehlungen

| Priorität | Befund | Konkretes Beispiel | Empfehlung |
| --- | --- | --- | --- |
| Hoch | Zuordnungen sind unterschiedlich gruppiert. | Einträge besitzen einen eigenen Block „Zuordnungen“. Bei Aufgaben stehen Fälligkeit und Projekt nebeneinander, der Vorgang folgt separat. | Projekt und Vorgang gemeinsam als Zuordnungen darstellen; Terminangaben davon trennen. Vergleichbare Gruppen über die Masken hinweg gleich anordnen. |
| Hoch | Pflichtfelder und optionale Angaben sind nicht einheitlich erkennbar. | Namen und Titel sind technisch verpflichtend, aber nicht entsprechend gekennzeichnet. Nur einzelne freiwillige Felder tragen „optional“. Dieser Zusatz steht durch das Label-Layout teilweise auf einer eigenen Zeile. | Eine gemeinsame Kennzeichnungsregel festlegen. Zusätze einheitlich neben der Beschriftung oder als Hilfetext unter dem Feld darstellen; dadurch auch die Ausrichtung nebeneinanderliegender Felder verbessern. |
| Mittel | Beschreibungen bieten unterschiedliche Bearbeitungsfunktionen. | Projektbeschreibung und Vorgangsnotizen verwenden den Markdown-Editor; die Beschreibung eines Nextcloud-Dokuments ist ein einfaches Textfeld. | Für beschreibende Freitexte denselben Editor mit einer kompakten und einer größeren Variante verwenden. Eine Umstellung muss auch Speicherung und Ausgabe der Formatierung berücksichtigen. |
| Mittel | Dialogüberschriften unterscheiden Anlegen und Bearbeiten uneinheitlich. | Einträge heißen „Neuer Eintrag“ bzw. „Eintrag bearbeiten“. Bei Kontakt, Projekt, Vorgang und Aufgabe bleibt die Überschrift allgemein. | Vergleichbare Objektmasken nach demselben Muster benennen, beispielsweise „Neuer Kontakt“ und „Kontakt bearbeiten“. |
| Mittel | Die Eingabe einzelner Wiederholungstermine weicht von anderen Datumsfeldern ab. | Sonst gibt es Datumsauswahlfelder; einzelne Fälligkeitstermine einer Serie werden zeilenweise im Format JJJJ-MM-TT eingetragen. | Wiederholbare Zeilen mit Datumsauswahl und Hinzufügen/Entfernen anbieten. Texteingabe für das Einfügen vieler Termine kann ergänzend bestehen bleiben. |
| Mittel | Anfangsfokus und sichtbare Feldreihenfolge passen nicht immer zusammen. | Beim Nextcloud-Dokument steht der Link zuerst, fokussiert wird jedoch der folgende Anzeigename. | Den Anfangsfokus auf den ersten vorgesehenen Arbeitsschritt setzen, hier auf das Einfügen des Links. |
| Niedrig | Mehrere Mailadressen werden unterschiedlich eingegeben. | Kontakte verwenden ein mehrzeiliges Feld mit Vorschlägen, Empfänger ein normales Eingabefeld, eigene Adressen in den Einstellungen eine kommagetrennte Eingabe. | Für Listen von Mailadressen eine gemeinsame Eingabekomponente oder zumindest gleiche Trennzeichen und Hinweise verwenden. Ein einzelner Absender darf weiterhin anders aussehen. |
| Niedrig | Dialogbreiten folgen keinem erkennbaren Umfangsschema. | Einfache Zuordnungsdialoge mit einem Auswahlfeld sind am Desktop breiter als die vollständige Kontaktmaske. | Wenige Breitenklassen nach Inhalt definieren: kompakte Auswahl, Standardformular, umfangreicher Editor. |

## Sinnvolle Unterschiede beibehalten

- Ein kurzer Aufgabentitel benötigt nicht dieselbe Werkzeugleiste wie ein Protokolltext.
- Strukturierte Listen wie Mailadressen oder Datumswerte sind keine Markdown-Texte.
- Einfach- und Mehrfachauswahl dürfen sich unterscheiden; Beschriftungen sollten die Auswahlmöglichkeiten deutlich machen.
- Handzeichnungen benötigen wegen Zeichenfläche und automatischer Speicherung einen eigenen Aufbau.
- Fachliche Bezeichnungen wie „Fällig am“, „Wiedervorlage“ und „Termine ab“ beschreiben unterschiedliche Zwecke und sollten erhalten bleiben.

Als gemeinsames Grundmuster bietet sich an: Name/Titel, Inhalt, Zeit und Status, Zuordnungen, zusätzliche Optionen. Kontextabhängige Abweichungen bleiben sinnvoll, sollten aber die Position wiederkehrender Gruppen möglichst beibehalten.

## Belege

- [Aufgabenmaske auf dem Desktop](screenshots/form-audit-task-dialog-1440.png): Gruppierung von Fälligkeit, Projekt und Vorgang sowie Darstellung des Optional-Zusatzes.
- [Nextcloud-Dokument auf dem Desktop](screenshots/form-audit-document-dialog-1440.png): Feldreihenfolge, Fokus und einfacher Beschreibungseditor.
- [Kontaktmaske auf dem Smartphone](screenshots/form-audit-person-dialog-390.png): gut lesbare, einspaltige Anordnung.
- Relevante Implementierung: `journal/templates/dialogs.html`, `journal/templates/case_fields.html`, `journal/templates/recurrence_fields.html`, `journal/templates/settings.html`, `journal/templates/handwriting.html`, `journal/static/app.js`, `journal/static/style.css` und `journal/static/search.js`.

Empfohlene Reihenfolge einer späteren Überarbeitung: zuerst Zuordnungsgruppen und Feldkennzeichnung, anschließend Editor-Verhalten, Dialogüberschriften und Anfangsfokus; danach Datumseingabe und kleinere Darstellungsunterschiede.
