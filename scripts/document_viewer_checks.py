"""Nextcloud-Dokumente im Journal: Hovervorschau, Detailseite, Rückweg.

Die Cloud wird nicht angesprochen – die einzige Stelle, die nach außen geht,
liefert hier feste Antworten.
"""
from playwright.sync_api import expect

from case_suggestion_checks import main
from journal import nextcloud
from journal.db import get_db, set_setting
from pdf_fixture import sample_pdf

PDF = sample_pdf()


def _ordner(*eintraege, wurzel='/remote.php/dav/files/leitung/'):
    teile = [f'<d:response><d:href>{wurzel}</d:href><d:propstat><d:prop>'
             '<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>']
    for name, ordner, kennung in eintraege:
        typ = ('<d:resourcetype><d:collection/></d:resourcetype>' if ordner
               else '<d:resourcetype/><d:getcontenttype>application/pdf</d:getcontenttype>')
        teile.append(f'<d:response><d:href>{wurzel}{name}{"/" if ordner else ""}</d:href><d:propstat><d:prop>'
                     f'{typ}<oc:fileid>{kennung}</oc:fileid><oc:size>2048</oc:size>'
                     '<d:getlastmodified>Fri, 25 Sep 2026 08:00:00 GMT</d:getlastmodified>'
                     '</d:prop></d:propstat></d:response>')
    xml = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
           + ''.join(teile) + '</d:multistatus>')
    return 207, 'application/xml', xml.encode()


def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=0):
    if methode == 'PROPFIND' and pfad.endswith('/Schulleitung/'):
        return _ordner(('Raumplan Schulfest.pdf', False, 4711),
                       wurzel='/remote.php/dav/files/leitung/Schulleitung/')
    if methode == 'PROPFIND' and pfad.endswith('/files/leitung/'):
        return _ordner(('.sync', True, 1), ('Schulleitung', True, 2), ('Jahresplan.pdf', False, 3))
    # Namenssuche (d:like) gegen Kennungssuche (d:eq) unterscheiden.
    if methode == 'SEARCH' and rumpf and b'<d:like>' in rumpf:
        return _ordner(('Protokoll Mai.pdf', False, 99),
                       wurzel='/remote.php/dav/files/leitung/Konferenzen/2026/')
    if methode in ('SEARCH', 'PROPFIND'):
        xml = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response>'
               '<d:href>/remote.php/dav/files/leitung/Schulleitung/Raumplan Schulfest.pdf</d:href>'
               '<d:propstat><d:prop><d:getcontenttype>application/pdf</d:getcontenttype></d:prop>'
               '</d:propstat></d:response></d:multistatus>')
        return 207, 'application/xml', xml.encode()
    if pfad.endswith('.pdf'):
        return 200, 'application/pdf', PDF
    return 404, '', b''


nextcloud._abruf = _abruf


def check(page, app):
    origin = page.url.split('/')[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        db = get_db()
        set_setting('caldav', dict(url='https://cloud.example.org/remote.php/dav',
                                   username='leitung', password='token', calendars=[]))
        eid = db.execute("INSERT INTO entries(date,type,title) VALUES('2026-09-25','meeting','Abstimmung Schulfest')").lastrowid
        did = db.execute("INSERT INTO documents(name,url,description) VALUES('Raumplan Schulfest',"
                         "'https://cloud.example.org/index.php/f/4711','Aufbauplan für die Stände.')").lastrowid
        db.execute("INSERT INTO documents(name,url) VALUES('Fremde Datei','https://fremde.example.net/f/9')")
        db.execute('INSERT INTO entry_documents VALUES(?,?)', (eid, did))
        db.execute('INSERT INTO entry_documents VALUES(?,?)', (eid, 2))
        db.commit()

    # Am Eintrag: Vorschau im Hoverfenster, ohne die Seite zu verlassen.
    page.goto(origin+f'/entry/{eid}')
    karte = page.locator(f'[data-document-id="{did}"]')
    expect(karte.get_by_role('button', name='Vorschau: Raumplan Schulfest')).to_be_visible()
    panel = page.locator('#pdf-preview')
    karte.hover()
    expect(panel).to_be_visible(timeout=15000)
    expect(panel.locator('img')).to_be_visible(timeout=15000)
    panel.locator('img').evaluate('(i)=>i.complete||new Promise(f=>{i.onload=f;i.onerror=f})')
    assert panel.locator('img').evaluate('(i)=>i.naturalWidth>0'), 'Die Vorschau bleibt leer'
    expect(panel.get_by_role('link', name='Alle Seiten ansehen')).to_have_attribute('href', f'/document/{did}')
    expect(panel.get_by_role('link', name='Herunterladen')).to_have_attribute('href', f'/document/{did}/file')
    page.screenshot(path='docs/screenshots/dokument-hovervorschau.png')
    page.keyboard.press('Escape')
    expect(panel).not_to_be_visible()

    # Ein Link ohne Bezug zur eingerichteten Cloud bekommt keine Vorschau angeboten.
    fremde = page.locator('[data-document-id="2"]')
    expect(fremde.get_by_role('button', name='Vorschau', exact=False)).to_have_count(0)

    # Der Titel führt weiter zur Detailseite – und von dort zurück zum Eintrag.
    karte.get_by_role('link', name='Raumplan Schulfest').click()
    expect(page).to_have_url(origin+f'/document/{did}')
    expect(page.locator('[data-viewer-image]')).to_be_visible(timeout=15000)
    expect(page.locator('[data-viewer-count]')).to_have_text('Seite 1 von 2')
    zurueck = page.locator('[data-context-back]')
    expect(zurueck).to_have_text('Zurück zum Eintrag')
    zurueck.click()
    expect(page).to_have_url(origin+f'/entry/{eid}')

    # Dateibrowser: Ordner öffnen, Datei wählen, außerdem im ganzen Bestand suchen.
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button', name='Nextcloud-Dokument verknüpfen').click()
    dialog = page.locator('#document-dialog')
    expect(dialog).to_be_visible()
    dialog.get_by_role('button', name='Aus Nextcloud wählen').click()
    browser = dialog.locator('[data-cloud-picker]')
    expect(browser.get_by_role('button', name='Schulleitung')).to_be_visible(timeout=10000)
    expect(browser.get_by_role('button', name='.sync')).to_have_count(0)
    page.screenshot(path='docs/screenshots/nextcloud-dateibrowser.png')
    browser.get_by_role('button', name='Schulleitung').first.click()
    expect(browser.get_by_role('button', name='Raumplan Schulfest.pdf')).to_be_visible(timeout=10000)
    browser.get_by_role('button', name='Raumplan Schulfest.pdf').click()
    expect(browser).not_to_be_visible()
    expect(dialog.locator('[name=url]')).to_have_value('https://cloud.example.org/index.php/f/4711')
    expect(dialog.locator('[name=name]')).to_have_value('Raumplan Schulfest')

    dialog.get_by_role('button', name='Aus Nextcloud wählen').click()
    browser.locator('[data-cloud-search]').fill('protokoll')
    expect(browser.get_by_role('button', name='Protokoll Mai.pdf')).to_be_visible(timeout=10000)
    browser.get_by_role('button', name='Protokoll Mai.pdf').click()
    expect(dialog.locator('[name=url]')).to_have_value('https://cloud.example.org/index.php/f/99')
    dialog.get_by_role('button', name='Abbrechen').click()

    # Aus dem Eintragsdialog heraus: Dokumente an eine Notiz hängen, nicht nur an Protokolle.
    page.goto(origin+'/')
    page.get_by_role('button', name='Erfassen').first.click()
    dialog = page.locator('#entry-dialog')
    expect(dialog).to_be_visible()
    dialog.locator('[name=title]').fill('Telefonat mit dem Schulamt')
    dialog.locator('[name=type]').select_option('phone')
    dialog.get_by_text('Nextcloud-Dokumente verknüpfen').click()
    dialog.get_by_role('button', name='Aus Nextcloud wählen').click()
    auswahl = dialog.locator('[data-cloud-picker]')
    expect(auswahl.get_by_role('button', name='Jahresplan.pdf')).to_be_visible(timeout=10000)
    auswahl.get_by_role('button', name='Jahresplan.pdf').click()
    korb = dialog.locator('[data-chosen-documents] .chosen-document')
    expect(korb).to_have_count(1)
    auswahl.get_by_role('button', name='Jahresplan.pdf').click()  # kein Doppeleintrag
    expect(korb).to_have_count(1)
    dialog.get_by_role('button', name='Eintrag speichern').click()
    expect(dialog).not_to_be_visible(timeout=10000)
    with app.app_context():
        neu_id = get_db().execute("SELECT id FROM entries WHERE title='Telefonat mit dem Schulamt'").fetchone()[0]
    page.goto(origin+f'/entry/{neu_id}')
    expect(page.get_by_role('link', name='Jahresplan')).to_be_visible()

    print('Dokumente geprüft: Hovervorschau, Detailseite, Rückweg, Dateibrowser, Eintragsdialog mit Dokumenten.')


if __name__ == '__main__':
    main(check)
