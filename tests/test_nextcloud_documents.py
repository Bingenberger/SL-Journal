"""Nextcloud-Dokumente im Journal ansehen – ohne Anmeldung in der Cloud.

Die Cloud wird dabei nicht angesprochen: `_abruf` ist die einzige Stelle, die
nach außen geht, und wird hier durch feste Antworten ersetzt.
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

from journal import nextcloud
from journal.db import get_db, one, set_setting

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
from pdf_fixture import sample_pdf  # noqa: E402

CLOUD = dict(url='https://cloud.example.org/remote.php/dav', username='leitung', password='token', calendars=[])


def verbinde(app, mit_cloud=True):
    with app.app_context():
        if mit_cloud:
            set_setting('caldav', CLOUD)
        get_db().execute("INSERT INTO documents(name,url) VALUES('Raumplan','https://cloud.example.org/index.php/f/4711')")
        get_db().commit()


def antwortet(monkeypatch, suche=None, **antworten):
    """Feste Antworten: `suche` beantwortet die WebDAV-Suche, der Rest geht nach Pfadteil."""
    aufrufe = []

    def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=0):
        aufrufe.append((methode, pfad))
        if methode in ('SEARCH', 'PROPFIND'):
            return suche or (404, '', b'')
        for teil, antwort in antworten.items():
            if teil in pfad:
                return antwort
        return 404, '', b''
    monkeypatch.setattr(nextcloud, '_abruf', _abruf)
    return aufrufe


def such_antwort(pfad='/remote.php/dav/files/leitung/Plaene/Raumplan.pdf', mime='application/pdf'):
    xml = f'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response><d:href>{pfad}</d:href>' \
          f'<d:propstat><d:prop><d:getcontenttype>{mime}</d:getcontenttype></d:prop></d:propstat></d:response></d:multistatus>'
    return 207, 'application/xml', xml.encode()


def test_only_links_to_the_configured_cloud_are_resolved(app):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
        for adresse, erwartet in [
                ('https://cloud.example.org/index.php/f/4711', ('datei', '4711')),
                ('https://cloud.example.org/f/4711', ('datei', '4711')),
                ('https://cloud.example.org/apps/files/files/4711?dir=/Plaene', ('datei', '4711')),
                ('https://cloud.example.org/apps/files/?dir=/&openfile=4711', ('datei', '4711')),
                ('https://cloud.example.org/s/AbCdEf123456', ('freigabe', 'AbCdEf123456')),
                ('https://cloud.example.org/apps/files/', None),
                # Fremde Server dürfen nie mit dem Token abgefragt werden.
                ('https://fremde.example.net/index.php/f/4711', None),
                ('https://cloud.example.org.angreifer.test/f/1', None),
                ('http://cloud.example.org/index.php/f/4711', None)]:
            assert nextcloud.referenz(adresse) == erwartet, adresse


def test_without_a_connection_nothing_is_resolved(app):
    with app.app_context():
        assert nextcloud.referenz('https://cloud.example.org/index.php/f/4711') is None


def test_pdf_pages_are_rendered_in_the_journal(app, client, monkeypatch):
    verbinde(app)
    aufrufe = antwortet(monkeypatch, suche=such_antwort(),
                        **{'Raumplan.pdf': (200, 'application/pdf', sample_pdf())})
    auskunft = client.get('/document/1/info', base_url='https://localhost')
    assert auskunft.status_code == 200 and auskunft.json['seiten'] == 2, 'Die Seitenzahl kommt aus der Datei'
    assert auskunft.json['name'] == 'Raumplan.pdf'
    erste = client.get('/document/1/page/1', base_url='https://localhost')
    assert erste.status_code == 200 and erste.mimetype == 'image/png'
    assert Image.open(io.BytesIO(erste.data)).size[0] > 400

    zweite = client.get('/document/1/page/2', base_url='https://localhost')
    assert zweite.status_code == 200 and zweite.data != erste.data, 'Seite 2 sieht anders aus'
    assert not any(pfad.startswith('/index.php/core/preview') for _, pfad in aufrufe), \
        'PDFs rendert das Journal selbst, weil die Cloud dafür keine Vorschau liefert'

    fehlend = client.get('/document/1/page/9', base_url='https://localhost')
    assert fehlend.status_code == 400


def test_office_documents_are_converted_locally(app, client, monkeypatch):
    """Die Cloud liefert für Tabellen nur ein winziges Vorschaubild; lokal gewandelt
    wird daraus ein lesbares, seitenweise blätterbares Dokument."""
    verbinde(app)
    from journal import pdf_preview
    gewandelt = []
    monkeypatch.setattr(pdf_preview, 'office_to_pdf',
                        lambda inhalt, endung: gewandelt.append(endung) or sample_pdf())
    aufrufe = antwortet(monkeypatch,
                        suche=such_antwort('/remote.php/dav/files/leitung/Liste.ods',
                                           'application/vnd.oasis.opendocument.spreadsheet'),
                        **{'Liste.ods': (200, 'application/vnd.oasis.opendocument.spreadsheet', b'ODS-Inhalt')})
    auskunft = client.get('/document/1/info', base_url='https://localhost')
    assert auskunft.status_code == 200 and auskunft.json['seiten'] == 2
    assert gewandelt == ['.ods'], 'Die Endung entscheidet über die Umwandlung'
    zweite = client.get('/document/1/page/2', base_url='https://localhost')
    assert zweite.status_code == 200 and zweite.mimetype == 'image/png'
    assert not any('core/preview' in pfad for _, pfad in aufrufe), 'Das kleine Vorschaubild der Cloud wird nicht gebraucht'


def test_without_libreoffice_the_cloud_preview_is_used(app, client, monkeypatch):
    verbinde(app)
    from journal import pdf_preview

    def fehlt(inhalt, endung):
        raise RuntimeError('Für Office-Dokumente fehlt LibreOffice auf dem Server.')
    monkeypatch.setattr(pdf_preview, 'office_to_pdf', fehlt)
    bild = io.BytesIO()
    Image.new('RGB', (80, 110), 'white').save(bild, format='PNG')
    aufrufe = antwortet(monkeypatch,
                        suche=such_antwort('/remote.php/dav/files/leitung/Liste.ods',
                                           'application/vnd.oasis.opendocument.spreadsheet'),
                        **{'Liste.ods': (200, 'application/vnd.oasis.opendocument.spreadsheet', b'ODS'),
                           '/index.php/core/preview': (200, 'image/png', bild.getvalue())})
    antwort = client.get('/document/1/page/1', base_url='https://localhost')
    assert antwort.status_code == 200 and antwort.mimetype == 'image/png'
    assert any('fileId=4711' in pfad for _, pfad in aufrufe), 'Dann springt die Cloud-Vorschau ein'


def test_images_are_re_encoded_in_the_journal(app, client, monkeypatch):
    verbinde(app)
    gross = io.BytesIO()
    Image.new('RGB', (2400, 1600), 'white').save(gross, format='JPEG')
    antwortet(monkeypatch,
              suche=such_antwort('/remote.php/dav/files/leitung/Unterschrift.jpg', 'image/jpeg'),
              **{'Unterschrift.jpg': (200, 'image/jpeg', gross.getvalue())})
    antwort = client.get('/document/1/page/1', base_url='https://localhost')
    assert antwort.status_code == 200 and antwort.mimetype == 'image/png'
    assert max(Image.open(io.BytesIO(antwort.data)).size) <= 1400, 'Bilder werden auf ein vernünftiges Maß gebracht'


def test_unsupported_types_point_to_the_download(app, client, monkeypatch):
    verbinde(app)
    antwortet(monkeypatch,
              suche=such_antwort('/remote.php/dav/files/leitung/Archiv.zip', 'application/zip'),
              **{'/index.php/core/preview': (404, 'application/json', b'[]')})
    antwort = client.get('/document/1/info', base_url='https://localhost',
                         headers={'X-Requested-With': 'fetch'})
    assert antwort.status_code == 400 and 'herunterladen' in antwort.json['error'].lower()


def test_the_file_is_served_through_the_journal(app, client, monkeypatch):
    verbinde(app)
    antwortet(monkeypatch, suche=such_antwort(),
              **{'Raumplan.pdf': (200, 'application/pdf', b'%PDF-1.4 Inhalt')})
    antwort = client.get('/document/1/file', base_url='https://localhost')
    assert antwort.status_code == 200
    assert antwort.data == b'%PDF-1.4 Inhalt'
    assert antwort.mimetype == 'application/octet-stream'
    assert 'attachment' in antwort.headers['Content-Disposition']
    assert 'Raumplan.pdf' in antwort.headers['Content-Disposition']


def test_a_foreign_link_is_never_fetched(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().execute("INSERT INTO documents(name,url) VALUES('Fremd','https://fremde.example.net/f/1')")
        get_db().commit()
    aufrufe = antwortet(monkeypatch, **{'/': (200, 'text/plain', b'x')})
    for pfad in ['/document/1/info', '/document/1/page/1', '/document/1/file']:
        assert client.get(pfad, base_url='https://localhost').status_code == 404, pfad
    assert not aufrufe, 'Für fremde Links darf keine Anfrage hinausgehen'


def test_missing_connection_is_explained(app, client):
    verbinde(app, mit_cloud=False)
    antwort = client.get('/document/1/page/1', base_url='https://localhost')
    assert antwort.status_code == 404
    seite = client.get('/document/1', base_url='https://localhost').text
    assert 'Einstellungen verbunden' in seite


def test_viewer_and_file_need_a_session(app):
    verbinde(app)
    anonym = app.test_client()
    for pfad in ['/document/1/info', '/document/1/page/1', '/document/1/file']:
        assert anonym.get(pfad, base_url='https://localhost').status_code == 302, pfad


def test_pages_come_from_the_cache_without_asking_again(app, client, monkeypatch):
    verbinde(app)
    aufrufe = antwortet(monkeypatch, suche=such_antwort(),
                        **{'Raumplan.pdf': (200, 'application/pdf', sample_pdf())})

    def downloads():
        return [pfad for methode, pfad in aufrufe if methode == 'GET' and pfad.endswith('.pdf')]

    assert client.get('/document/1/info', base_url='https://localhost').json['seiten'] == 2
    assert len(downloads()) == 1, 'Die Datei wird genau einmal geholt'
    erste = client.get('/document/1/page/1', base_url='https://localhost')
    assert erste.status_code == 200

    nochmal = client.get('/document/1/page/1', base_url='https://localhost')
    assert nochmal.data == erste.data
    zweite = client.get('/document/1/page/2', base_url='https://localhost')
    assert zweite.status_code == 200 and zweite.data != erste.data
    assert len(downloads()) == 1, 'Beim Blättern wird die Datei nicht erneut geladen'
    assert client.get('/document/1/info', base_url='https://localhost').json['seiten'] == 2, \
        'Auch aus dem Zwischenspeicher bleibt die Seitenzahl bekannt'


def test_cached_pages_expire(app, client, monkeypatch):
    verbinde(app)
    antwortet(monkeypatch, suche=such_antwort(),
              **{'Raumplan.pdf': (200, 'application/pdf', sample_pdf())})
    assert client.get('/document/1/page/1', base_url='https://localhost').status_code == 200
    with app.app_context():
        dateien = list((Path(app.instance_path)/'cache').glob('doc-*.enc'))
        assert dateien, 'Vorschau und Datei liegen verschlüsselt im Zwischenspeicher'
        for alt in dateien:
            import os
            os.utime(alt, (0, 0))
        from journal import nextcloud as nc
        nc._aufraeumen()
        assert not list((Path(app.instance_path)/'cache').glob('doc-*.enc')), 'Abgelaufenes wird entfernt'


def dokumentkarte(app):
    """Ein Dokument an einem Eintrag – so, wie es an Einträgen und Projekten erscheint."""
    with app.app_context():
        set_setting('caldav', CLOUD)
        db = get_db()
        eid = db.execute("INSERT INTO entries(date,type,title) VALUES('2026-09-25','note','Mit Dokument')").lastrowid
        did = db.execute("INSERT INTO documents(name,url) VALUES('Raumplan','https://cloud.example.org/index.php/f/4711')").lastrowid
        fremd = db.execute("INSERT INTO documents(name,url) VALUES('Fremd','https://fremde.example.net/f/9')").lastrowid
        db.execute('INSERT INTO entry_documents VALUES(?,?)', (eid, did))
        db.execute('INSERT INTO entry_documents VALUES(?,?)', (eid, fremd))
        db.commit()
        return eid, did, fremd


def test_the_card_offers_a_preview_next_to_the_nextcloud_link(app, client):
    eid, did, fremd = dokumentkarte(app)
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').text
    karte = seite[seite.index(f'data-document-id="{did}"'):seite.index('</article>', seite.index(f'data-document-id="{did}"'))]
    assert f'data-pdf-url="/document/{did}/page/1"' in karte, 'Die Vorschau hängt am Hoverfenster'
    assert f'data-pdf-download="/document/{did}/file"' in karte
    assert f'data-pdf-more="/document/{did}"' in karte, 'Von der Vorschau führt ein Weg zu allen Seiten'
    assert 'pdf-preview-button' in karte and 'Vorschau' in karte
    assert f'href="/document/{did}"' in karte, 'Der Titel führt weiter zur Detailseite'

    fremde = seite[seite.index(f'data-document-id="{fremd}"'):seite.index('</article>', seite.index(f'data-document-id="{fremd}"'))]
    assert 'data-pdf-url' not in fremde and 'pdf-preview-button' not in fremde, \
        'Ohne auflösbaren Link wird keine Vorschau angeboten'


def test_the_way_back_needs_the_referrer(app, client):
    """Der Rückweg lebt von der Herkunftsangabe – die darf im Journal nicht unterdrückt sein."""
    antwort = client.get('/entry/1', base_url='https://localhost')
    assert antwort.headers['Referrer-Policy'] == 'same-origin'
    eid, did, _ = dokumentkarte(app)
    seite = client.get(f'/document/{did}', base_url='https://localhost').text
    assert 'data-context-back' in seite


def ordner_antwort(*eintraege, wurzel='/remote.php/dav/files/leitung/'):
    """Eine PROPFIND-Antwort wie sie Nextcloud für einen Ordner liefert."""
    teile = [f'<d:response><d:href>{wurzel}</d:href><d:propstat><d:prop>'
             f'<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>']
    for name, ordner, kennung, groesse in eintraege:
        typ = '<d:resourcetype><d:collection/></d:resourcetype>' if ordner else \
              '<d:resourcetype/><d:getcontenttype>application/pdf</d:getcontenttype>'
        teile.append(f'<d:response><d:href>{wurzel}{name}{"/" if ordner else ""}</d:href><d:propstat><d:prop>'
                     f'{typ}<oc:fileid>{kennung}</oc:fileid><oc:size>{groesse}</oc:size>'
                     f'<d:getlastmodified>Fri, 25 Sep 2026 08:00:00 GMT</d:getlastmodified>'
                     f'</d:prop></d:propstat></d:response>')
    xml = '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">' + ''.join(teile) + '</d:multistatus>'
    return 207, 'application/xml', xml.encode()


def test_the_file_browser_lists_folders_first(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    gefragt = []

    def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=0):
        gefragt.append((methode, pfad))
        return ordner_antwort(('Zeugnisse', True, 11, 0), ('anlage.pdf', False, 12, 2048),
                              ('Protokolle', True, 13, 0), ('Bericht.pdf', False, 14, 4096))
    monkeypatch.setattr(nextcloud, '_abruf', _abruf)

    daten = client.get('/api/nextcloud/files', base_url='https://localhost').json
    assert [e['name'] for e in daten['eintraege']] == ['Protokolle', 'Zeugnisse', 'anlage.pdf', 'Bericht.pdf']
    assert [e['ordner'] for e in daten['eintraege']] == [True, True, False, False]
    datei_eintrag = daten['eintraege'][-1]
    assert datei_eintrag['url'] == 'https://cloud.example.org/index.php/f/14', 'Der Eintrag bringt den fertigen Link mit'
    assert datei_eintrag['groesse'] == 4096 and datei_eintrag['geaendert']
    assert gefragt == [('PROPFIND', '/remote.php/dav/files/leitung/')]


def test_subfolders_are_requested_with_encoded_names(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    gefragt = []

    def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=0):
        gefragt.append(pfad)
        return ordner_antwort(('Bericht.pdf', False, 21, 100),
                              wurzel='/remote.php/dav/files/leitung/Schulleitung%20A/Gr%C3%BCne%20Schule/')
    monkeypatch.setattr(nextcloud, '_abruf', _abruf)
    daten = client.get('/api/nextcloud/files?path=Schulleitung A/Grüne Schule',
                       base_url='https://localhost').json
    assert gefragt == ['/remote.php/dav/files/leitung/Schulleitung%20A/Gr%C3%BCne%20Schule/']
    assert daten['teile'] == ['Schulleitung A', 'Grüne Schule']
    assert [e['name'] for e in daten['eintraege']] == ['Bericht.pdf']


def test_the_browser_never_leaves_the_own_folder(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    gefragt = []
    monkeypatch.setattr(nextcloud, '_abruf',
                        lambda *a, **k: gefragt.append(a[0]) or ordner_antwort())
    for boese in ['../andere', 'Schule/../../etc', '..', '/../../']:
        antwort = client.get('/api/nextcloud/files', query_string={'path': boese},
                             base_url='https://localhost', headers={'X-Requested-With': 'fetch'})
        assert antwort.status_code == 400, boese
        assert 'außerhalb' in antwort.json['error']
    assert not gefragt, 'Für solche Pfade geht keine Anfrage hinaus'


def test_searching_finds_files_anywhere(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    rumpfe = []

    def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=0):
        rumpfe.append(rumpf.decode())
        return ordner_antwort(('Protokoll Mai.pdf', False, 31, 700),
                              wurzel='/remote.php/dav/files/leitung/Schulleitung/Sitzungen/')
    monkeypatch.setattr(nextcloud, '_abruf', _abruf)
    daten = client.get('/api/nextcloud/files?q=protokoll', base_url='https://localhost').json
    assert [e['name'] for e in daten['eintraege']] == ['Protokoll Mai.pdf']
    assert daten['eintraege'][0]['pfad'] == 'Schulleitung/Sitzungen/Protokoll Mai.pdf', 'Der Fundort wird mitgeliefert'
    assert '<d:literal>%protokoll%</d:literal>' in rumpfe[0]

    # Sonderzeichen dürfen die Suchanfrage nicht zerlegen.
    client.get('/api/nextcloud/files?q=<b>&"lauf', base_url='https://localhost')
    assert '<b>' not in rumpfe[1] and '&lt;b&gt;' in rumpfe[1]

    kurz = client.get('/api/nextcloud/files?q=a', base_url='https://localhost').json
    assert kurz['eintraege'] == [] and len(rumpfe) == 2, 'Ein einzelner Buchstabe fragt nicht die Cloud'


def test_the_browser_needs_a_connection_and_a_session(app, client):
    antwort = client.get('/api/nextcloud/files', base_url='https://localhost', headers={'X-Requested-With': 'fetch'})
    assert antwort.status_code == 400 and 'Einstellungen' in antwort.json['error']
    assert app.test_client().get('/api/nextcloud/files', base_url='https://localhost').status_code == 302


def test_hidden_system_entries_stay_out_of_the_way(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    monkeypatch.setattr(nextcloud, '_abruf',
                        lambda *a, **k: ordner_antwort(('.sync', True, 41, 0), ('.lock', True, 42, 0),
                                                       ('Schulleitung', True, 43, 0), ('Plan.pdf', False, 44, 10)))
    namen = [e['name'] for e in client.get('/api/nextcloud/files', base_url='https://localhost').json['eintraege']]
    assert namen == ['Schulleitung', 'Plan.pdf'], 'Systemordner der Synchronisierung stören die Auswahl nur'


def test_search_skips_hidden_folders(app, client, monkeypatch):
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    monkeypatch.setattr(nextcloud, '_abruf',
                        lambda *a, **k: ordner_antwort(('Protokoll.pdf', False, 51, 10),
                                                       wurzel='/remote.php/dav/files/leitung/logseq/.recycle/'))
    daten = client.get('/api/nextcloud/files?q=protokoll', base_url='https://localhost').json
    assert daten['eintraege'] == [], 'Treffer aus Papierkörben und Sync-Ordnern helfen nicht'


def test_the_picker_only_appears_with_a_connection(app, client):
    ohne = client.get('/entry/1', base_url='https://localhost').text
    assert 'data-cloud-open' in ohne and 'cloud-choice" hidden' in ohne, \
        'Ohne Verbindung bleibt die Auswahl verborgen'
    with app.app_context():
        set_setting('caldav', CLOUD)
        get_db().commit()
    mit = client.get('/entry/1', base_url='https://localhost').text
    assert 'cloud-choice" hidden' not in mit and 'Aus Nextcloud wählen' in mit
