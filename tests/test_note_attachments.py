"""Ressourcen an eine Notiz anhängen: Ziel anlegen, verknüpfen, Quelle unangetastet lassen."""
from journal.db import get_db, one, rows, init_db
from journal.domain import save_entry, save_attachment


def seed(app):
    with app.app_context():
        source = save_entry(dict(type='mail_in', title='Information für das Kollegium',
                                 date='2026-09-24', body='Unveränderter Mailtext'))
        save_attachment(source, 'Info.pdf', b'Originalanhang', 'application/pdf')
        get_db().commit()
        return source


def ziel(response):
    assert response.status_code == 200, response.text
    return int(response.json['redirect'].split('/entry/')[1].split('#')[0])


def test_attaching_a_mail_creates_the_note_and_leaves_the_source_alone(app, client, post):
    source = seed(app)
    note = ziel(post('/note/attach', dict(target_title='Wochenpost KW 42', resource_url=f'/entry/{source}')))
    with app.app_context():
        angelegt = one('SELECT type,title,body FROM entries WHERE id=?', (note,))
        assert angelegt['type'] == 'note' and angelegt['title'] == 'Wochenpost KW 42'
        assert one('SELECT body FROM entries WHERE id=?', (source,))['body'] == 'Unveränderter Mailtext'
        assert one('SELECT entry_id FROM attachments')['entry_id'] == source
        verweis = one('SELECT owner_entry_id,entry_id FROM entry_resource_links')
        assert verweis['owner_entry_id'] == note and verweis['entry_id'] == source
    seite = client.get(f'/entry/{note}', base_url='https://localhost').text
    assert 'Verknüpfte Ressourcen' in seite and 'Information für das Kollegium' in seite
    # Die Quelle zeigt den Rückverweis.
    assert 'Wochenpost KW 42' in client.get(f'/entry/{source}', base_url='https://localhost').text


def test_existing_note_is_reused_and_repeating_the_request_adds_nothing(app, post):
    source = seed(app)
    with app.app_context():
        vorhanden = save_entry(dict(type='note', title='Wochenpost KW 42', date='2026-09-24', body='Bestehender Entwurf'))
        get_db().commit()
    daten = dict(target_title='WOCHENPOST KW 42', resource_url=f'/entry/{source}')
    assert ziel(post('/note/attach', daten)) == vorhanden
    assert ziel(post('/note/attach', daten)) == vorhanden
    assert ziel(post('/note/attach', dict(target_id=str(vorhanden), resource_url=f'/entry/{source}'))) == vorhanden
    with app.app_context():
        assert len(rows('SELECT * FROM entry_resource_links')) == 1
        assert one('SELECT body FROM entries WHERE id=?', (vorhanden,))['body'] == 'Bestehender Entwurf'
        assert len(rows('SELECT * FROM entries')) == 2


def test_other_resources_can_be_attached_and_detached(app, post, client):
    with app.app_context():
        pid = get_db().execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')").lastrowid
        get_db().commit()
    note = ziel(post('/note/attach', dict(target_title='Wochenpost', resource_url=f'/project/{pid}')))
    with app.app_context():
        link = one('SELECT id,project_id FROM entry_resource_links')
        assert link['project_id'] == pid
    assert post(f"/entry/{note}/link/{link['id']}/remove").status_code == 200
    with app.app_context():
        assert not rows('SELECT * FROM entry_resource_links')
        assert one('SELECT id FROM projects WHERE id=?', (pid,)), 'Das Projekt bleibt erhalten'
        assert one('SELECT id FROM entries WHERE id=?', (note,)), 'Die Notiz bleibt erhalten'


def test_invalid_targets_and_sources_are_refused(app, client, post):
    source = seed(app)
    for daten in [dict(target_title='Neue Notiz', resource_url='/entry/999'),
                  dict(target_title='Neue Notiz', resource_url='https://outside.test/'),
                  dict(target_title='Neue Notiz'),
                  dict(target_title='', resource_url=f'/entry/{source}'),
                  dict(target_title='x'*501, resource_url=f'/entry/{source}')]:
        assert post('/note/attach', daten).status_code == 400, daten
    assert post('/note/attach', dict(target_id='999', resource_url=f'/entry/{source}')).status_code == 404
    # Ein Eintrag kann nicht an sich selbst hängen.
    assert post('/note/attach', dict(target_id=str(source), resource_url=f'/entry/{source}')).status_code == 400
    with app.app_context():
        assert not rows('SELECT * FROM entry_resource_links')
    assert client.post('/note/attach', base_url='https://localhost').status_code == 400
    assert app.test_client().post('/note/attach', base_url='https://localhost').status_code == 400


def test_a_deleted_source_takes_its_link_with_it(app, client, post):
    source = seed(app)
    note = ziel(post('/note/attach', dict(target_title='Wochenpost', resource_url=f'/entry/{source}')))
    assert post(f'/entry/{source}/delete').status_code == 200
    with app.app_context():
        init_db(); init_db()
        assert not rows('SELECT * FROM entry_resource_links')
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
    assert client.get(f'/entry/{note}', base_url='https://localhost').status_code == 200


def test_suggestions_offer_notes_first(app, client):
    with app.app_context():
        save_entry(dict(type='mail_in', title='Zielsuche Mail', date='2026-09-20'))
        save_entry(dict(type='note', title='Zielsuche Notiz', date='2026-09-01'))
        get_db().commit()
    items = client.get('/api/autocomplete/notes?q=Zielsuche', base_url='https://localhost').json['items']
    assert [item['label'] for item in items] == ['Zielsuche Notiz', 'Zielsuche Mail']
    assert items[0]['detail'].startswith('Notiz')


def test_old_collections_are_retired_without_losing_written_text(app):
    """Bestandsdaten aus der abgelösten Sammlungsfunktion: Verweise bleiben,
    selbst geschriebene Hinweise wandern in den Text der Notiz."""
    with app.app_context():
        db = get_db()
        note = save_entry(dict(type='note', title='Wochenpost KW 42', date='2026-09-24', body='Erster Absatz'))
        leer = save_entry(dict(type='note', title='Wochenpost KW 43', date='2026-09-24', body=''))
        source = save_entry(dict(type='mail_in', title='Schulamt', date='2026-09-24'))
        db.executescript('''
            CREATE TABLE collections (entry_id INTEGER PRIMARY KEY REFERENCES entries(id) ON DELETE CASCADE);
            CREATE TABLE collection_items (id INTEGER PRIMARY KEY, collection_id INTEGER NOT NULL,
             link_id INTEGER, source_label TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
             done INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE collection_requests (request_key TEXT PRIMARY KEY, collection_id INTEGER NOT NULL, item_id INTEGER);''')
        db.execute('INSERT INTO entry_resource_links(owner_entry_id,entry_id) VALUES(?,?)', (note, source))
        link = one('SELECT id FROM entry_resource_links')['id']
        db.executemany('INSERT INTO collections(entry_id) VALUES(?)', [(note,), (leer,)])
        db.executemany('INSERT INTO collection_items(collection_id,link_id,source_label,note) VALUES(?,?,?,?)', [
            (note, link, 'Schulamt', 'Kurz ankündigen'),
            (note, None, '', 'Eigene Idee: Geburtstage'),
            (leer, None, '', 'Nur eine Idee')])
        db.commit()
        init_db(); init_db()
        assert not rows("SELECT name FROM sqlite_master WHERE name LIKE 'collection%'")
        text = one('SELECT body FROM entries WHERE id=?', (note,))['body']
        assert text.startswith('Erster Absatz')
        assert '## Gesammelte Hinweise' in text
        assert '**Schulamt**' in text and 'Kurz ankündigen' in text and 'Eigene Idee: Geburtstage' in text
        assert one('SELECT body FROM entries WHERE id=?', (leer,))['body'] == '## Gesammelte Hinweise\n\nNur eine Idee'
        assert one('SELECT entry_id FROM entry_resource_links')['entry_id'] == source, 'Der Verweis bleibt bestehen'
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
