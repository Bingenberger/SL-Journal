"""Nextcloud-Dokumente lassen sich an jeder Eintragsart verknüpfen."""
import pytest
from werkzeug.datastructures import MultiDict

from journal.db import get_db, one, rows
from journal.domain import TYPES

LINK = 'https://cloud.schule.de/index.php/f/4711'


def eintrag(post, typ, **felder):
    antwort = post('/entry/save', dict(title=f'Test {typ}', type=typ, date='2026-09-25', **felder))
    assert antwort.status_code == 200, antwort.get_json()
    return antwort


def dokumente(app, titel):
    with app.app_context():
        return rows('SELECT d.name,d.url FROM documents d JOIN entry_documents ed ON ed.document_id=d.id '
                    'JOIN entries e ON e.id=ed.entry_id WHERE e.title=? ORDER BY d.name', (titel,))


@pytest.mark.parametrize('typ', list(TYPES))
def test_jede_eintragsart_nimmt_ein_dokument_auf(app, post, typ):
    eintrag(post, typ, document_url=LINK, document_name='Raumplan Schulfest')
    assert dokumente(app, f'Test {typ}') == [dict(name='Raumplan Schulfest', url=LINK)]


def test_mehrere_dokumente_auf_einmal(app, post, client):
    antwort = client.post('/entry/save', base_url='https://localhost',
                          headers={'X-Requested-With': 'fetch'},
                          data=MultiDict([('csrf_token', 'test-csrf'), ('title', 'Test mehrfach'),
                                ('type', 'phone'), ('date', '2026-09-25'),
                                ('document_url', LINK), ('document_name', 'Raumplan'),
                                ('document_url', LINK + '2'), ('document_name', 'Einladung')]))
    assert antwort.status_code == 200, antwort.get_json()
    assert [d['name'] for d in dokumente(app, 'Test mehrfach')] == ['Einladung', 'Raumplan']


def test_ohne_namen_wird_der_dateiname_verwendet(app, post):
    eintrag(post, 'note', document_url=LINK, document_name='   ')
    assert dokumente(app, 'Test note') == [dict(name='4711', url=LINK)]


def test_leere_zeile_wird_uebergangen(app, post):
    eintrag(post, 'journal', document_url='   ', document_name='')
    assert dokumente(app, 'Test journal') == []


def test_fehlerhafter_link_verwirft_den_ganzen_eintrag(app, post):
    antwort = post('/entry/save', dict(title='Test kaputt', type='meeting', date='2026-09-25',
                                       document_url='http://cloud.schule.de/f/1', document_name='Egal'))
    assert antwort.status_code == 400
    with app.app_context():
        assert one('SELECT id FROM entries WHERE title=?', ('Test kaputt',)) is None


def test_zu_viele_dokumente_werden_abgelehnt(app, client):
    daten = [('csrf_token', 'test-csrf'), ('title', 'Test viele'), ('type', 'note'), ('date', '2026-09-25')]
    daten += [(feld, f'{LINK}{n}' if feld == 'document_url' else f'Datei {n}')
              for n in range(26) for feld in ('document_url', 'document_name')]
    antwort = client.post('/entry/save', data=MultiDict(daten), base_url='https://localhost',
                          headers={'X-Requested-With': 'fetch'})
    assert antwort.status_code == 400
    assert 'höchstens 25' in antwort.get_json()['error']
    with app.app_context():
        assert one('SELECT id FROM entries WHERE title=?', ('Test viele',)) is None


@pytest.mark.parametrize('typ', list(TYPES))
def test_verknuepfen_ist_auf_jeder_eintragsseite_erreichbar(app, client, post, typ):
    with app.app_context():
        from journal.db import set_setting
        set_setting('caldav', dict(url='https://cloud.schule.de/remote.php/dav',
                                   username='leitung', password='token', calendars=[]))
        get_db().commit()
    eintrag(post, typ)
    with app.app_context():
        eid = one('SELECT id FROM entries WHERE title=?', (f'Test {typ}',))['id']
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert 'Nextcloud-Dokument verknüpfen' in seite
