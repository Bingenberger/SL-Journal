# UI-Verbesserungen vom 24.09.2026

Die Befunde aus dem UI-Review wurden umgesetzt:

- **Formularschutz:** Beim Schließen eines geänderten Dialogs wird vor dem Verwerfen gewarnt. Abbrechen erhält die Eingaben. Beim Verlassen einer Seite mit ungespeicherten Eintrags-, Journal-, Zuordnungs- oder Einstellungsänderungen greift ebenfalls eine Warnung. Nach erfolgreichem Speichern erscheint keine unnötige Warnung. Es wurde kein zusätzlicher unverschlüsselter Entwurfsspeicher eingeführt; dies ist kein Autosave für normale Texte.
- **Dialoge:** Kopf und Speicherleiste bleiben sichtbar, nur der Formularinhalt scrollt. Titel und Text stehen vor ergänzenden Angaben. Anhänge sind einklappbar; Projekt und Vorgang stehen im Aufgabendialog zusammen. Lange Fehlerhinweise werden in den sichtbaren Bereich gescrollt.
- **Vorschläge:** Kontakte, Projekte und Vorgänge zeigen kompakte, einklappbare Vorschlagsbereiche nach den Filtern. Der Aufklappzustand bleibt innerhalb der Sitzung erhalten. Vorgangsvorschläge können vor der Übernahme benannt und mit Status/Wiedervorlage ergänzt werden; Zuordnung zu bestehenden Vorgängen funktioniert über einen eigenen Dialog wie bei Kontakten und Projekten.
- **Mobile Navigation:** Ein Menü mit sichtbarem aktuellem Bereich ersetzt die horizontal verschobenen Menüpunkte. Filter stehen untereinander mit lesbaren Auswahlwerten.
- **Cockpit:** Auf Tablet und Smartphone stehen Wiedervorlagen und Aufgaben vor Journal und Kommunikation. Leere Terminbereiche sind kompakter. Allgemeine Aufgaben-Neuanlage bleibt im Header.
- **Inhaltsansichten:** Bei Einträgen ohne Zeichnung erscheint nur „Zeichenblatt hinzufügen“. Leere Anhangsbereiche entfallen; leere Nextcloud-Bereiche werden zu einer kompakten Aktion. Bestehende Zeichnungen und Ressourcenrückverweise bleiben sichtbar.
- **Listen:** Kontakte werden als kompakte Zeilen dargestellt. Kontakte, Aufgaben, Projekte, Vorgänge und ihre Chroniken zeigen 30 Ergebnisse pro Seite. Aufgabenfilter kombinieren Text, Projekt, Vorgang und Fälligkeit. Projekte besitzen eine Textsuche. Filter bleiben beim Seitenwechsel erhalten. Alte und neue Aufgaben-Direktlinks öffnen auch Ziele außerhalb der ersten Ergebnisseite.
- **Aufgabenaktionen:** Unteraufgaben werden über ein kompaktes Menü mit beschriftetem Symbol angelegt. Größere Klickflächen, dunklere Metadaten und eine ausgeschriebene Kennzeichnung überfälliger Aufgaben verbessern die Bedienung.
- **Posteingang:** Tags können direkt an der Mail zugeordnet werden. Bestehende Tags und Zuordnungen bleiben erhalten. Vorgemerkte Vorschläge werden in der Rückmeldung von tatsächlichen Zuordnungen unterschieden.
- **Orientierung:** Die Kopfsuche heißt jetzt „Einträge durchsuchen“, entsprechend ihrem Suchumfang. Detailansichten bieten nach interner Navigation einen Rückweg zur vorherigen Ansicht mit deren Filtern. Die Leseposition wird nach Aktionen auf derselben Seite wiederhergestellt.
- **Einstellungen:** „Speichern und Verbindung prüfen“ verwendet die gerade eingetragenen Daten. „Gespeicherte Verbindungen abrufen“ ist eindeutig benannt. Löschfristen sind ein separater einklappbarer Abschnitt; vorhandene Dienststatus bleiben direkt an den Verbindungen sichtbar.

## Prüfung

122 Python-Tests bestanden. Vollständige bestehende Browserprüfung, Vorgangsvorschlagsprüfung und Handschriftprüfung bestanden. Zusätzliche UI-Prüfung mit 100 fiktiven Kontakten: 27 Ansichten bei 1440, 768 und 390 Pixeln, keine horizontalen Seitenüberläufe. Geprüft wurden außerdem Entwurfsschutz, sichtbare Speicherleiste, Filterkombinationen, Seitennavigation, direkte Tagzuordnung und ältere Aufgabenlinks. Testinstanzen waren vom echten Datenbestand getrennt.

## Bildschirmbeispiele

- [Eintragsdialog auf dem Smartphone](ui-improved/dialog-390.png)
- [Kontaktliste auf dem Smartphone](ui-improved/people-390.png)
- [Cockpit auf dem Smartphone](ui-improved/cockpit-390.png)
- [Aufgaben mit Filtern](ui-improved/tasks-1440.png)
- [Protokoll ohne leere Zusatzbereiche](ui-improved/protocol-1440.png)
