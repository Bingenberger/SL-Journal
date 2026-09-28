"""Tags an Aufgaben: speichern, erben, filtern, in der Übersicht zählen."""
from journal.db import get_db, one, rows
from journal.domain import save_entry, save_task
from journal.tags import overview


def aufgabe(post, text, **felder):
    antwort = post('/task/save', dict(text=text, **felder))
    assert antwort.status_code == 200, antwort.get_json()
    return one('SELECT id FROM tasks WHERE text=?', (text,))['id']


def test_tags_werden_gespeichert_und_normalisiert(app, post):
    with app.app_context():
        tid = aufgabe(post, 'Raumplan abstimmen', tags='#Schulfest, Organisation, Schulfest')
        assert one('SELECT tags FROM tasks WHERE id=?', (tid,))['tags'] == 'Schulfest, Organisation'


def test_unteraufgabe_erbt_tags_und_eigene_gehen_vor(app, post):
    with app.app_context():
        haupt = aufgabe(post, 'Schulfest vorbereiten', tags='Schulfest')
        geerbt = aufgabe(post, 'Stände planen', parent_id=haupt)
        eigen = aufgabe(post, 'Technik klären', parent_id=haupt, tags='Technik')
        assert one('SELECT tags FROM tasks WHERE id=?', (geerbt,))['tags'] == 'Schulfest'
        assert one('SELECT tags FROM tasks WHERE id=?', (eigen,))['tags'] == 'Technik'


def test_bearbeiten_ersetzt_die_tags(app, post):
    with app.app_context():
        tid = aufgabe(post, 'Elternbrief', tags='Kommunikation')
        post('/task/save', dict(id=tid, text='Elternbrief', tags='Organisation'))
        assert one('SELECT tags FROM tasks WHERE id=?', (tid,))['tags'] == 'Organisation'


def test_aufgabenliste_filtert_nach_tag(app, client, post):
    with app.app_context():
        aufgabe(post, 'Mit Tag', tags='Schulfest')
        aufgabe(post, 'Ohne Tag')
        aufgabe(post, 'Andere Schreibweise', tags='schulfest')
    seite = client.get('/tasks?filter=all&tag=Schulfest', base_url='https://localhost').get_data(as_text=True)
    assert 'Mit Tag' in seite and 'Andere Schreibweise' in seite
    assert 'Ohne Tag' not in seite


def test_uebersicht_zaehlt_eintraege_und_aufgaben_getrennt(app, post):
    with app.app_context():
        save_entry(dict(title='Notiz', date='2026-09-28', tags='Schulfest, Kollegium'))
        get_db().commit()
        aufgabe(post, 'Raumplan', tags='Schulfest')
        gefunden = {t['name']: t for t in overview()}
        assert gefunden['Schulfest']['entries'] == 1
        assert gefunden['Schulfest']['tasks'] == 1
        assert gefunden['Schulfest']['count'] == 2
        assert gefunden['Kollegium']['tasks'] == 0


def test_tagseite_verlinkt_beide_listen(app, client, post):
    with app.app_context():
        save_entry(dict(title='Notiz', date='2026-09-28', tags='Schulfest'))
        get_db().commit()
        aufgabe(post, 'Raumplan', tags='Schulfest')
    seite = client.get('/tags', base_url='https://localhost').get_data(as_text=True)
    assert 'tag=Schulfest' in seite
    assert '/tasks?filter=all&amp;tag=Schulfest' in seite or '/tasks?tag=Schulfest&amp;filter=all' in seite


def test_journal_schnelleingabe_nimmt_tags_auf(app, post):
    antwort = post('/entry/save', dict(title='Journal · 28.09.2026', type='journal',
                                       date='2026-09-28', body='Kurz notiert', tags='Schulfest'))
    assert antwort.status_code == 200
    with app.app_context():
        assert one('SELECT tags FROM entries WHERE title=?', ('Journal · 28.09.2026',))['tags'] == 'Schulfest'


def test_schnelleingabe_und_dialog_bieten_das_feld_an(app, client):
    cockpit = client.get('/', base_url='https://localhost').get_data(as_text=True)
    assert 'data-label="Tags zum Journaleintrag"' in cockpit
    assert cockpit.count('data-autocomplete="tags"') >= 2, 'Journalfeld und Aufgabendialog'
