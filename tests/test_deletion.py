"""Löschen einzelner Objekte: Was verschwindet, und was ausdrücklich bleibt."""
from pathlib import Path
import io
from journal.db import get_db, one, rows
from journal.domain import school_year


def test_task_deletion_removes_subtasks_and_stops_a_series(app, post, client):
    assert post('/task/save', dict(text='Statistik KW{KW}', due='2026-09-24',
        repeat='1', repeat_frequency='weekly', repeat_interval='1')).status_code == 200
    with app.app_context():
        source = one('SELECT id FROM tasks ORDER BY id')['id']
        spaeter = one('SELECT id FROM tasks WHERE id<>? ORDER BY id DESC', (source,))['id']
    assert post('/task/save', dict(text='Zahlen zusammenstellen', parent_id=str(source))).status_code == 200
    assert post(f'/task/{source}/delete').status_code == 200
    with app.app_context():
        assert not one('SELECT id FROM tasks WHERE id=?', (source,))
        assert not one('SELECT id FROM tasks WHERE text=?', ('Zahlen zusammenstellen',)), 'Unteraufgabe muss mitgehen'
        assert one('SELECT active FROM task_series')['active'] == 0, 'Serie ohne Ausgangsaufgabe wird angehalten'
        assert one('SELECT id FROM tasks WHERE id=?', (spaeter,)), 'Bereits erzeugte Folgeaufgabe bleibt'
    assert client.get('/tasks', base_url='https://localhost').status_code == 200


def test_project_and_case_deletion_keep_entries_and_tasks(app, post, client):
    assert post('/project/save', dict(name='Schulfest', school_year=school_year())).status_code == 200
    assert post('/case/save', dict(title='Beschwerde 3a', status='open')).status_code == 200
    assert post('/entry/save', dict(title='Telefonat', type='phone', date='2026-09-24',
        projects='1', case_ids='[1]')).status_code == 200
    assert post('/task/save', dict(text='Rückruf', project_id='1', case_id='1')).status_code == 200
    assert post('/project/1/delete').status_code == 200
    assert post('/case/1/delete').status_code == 200
    with app.app_context():
        assert not rows('SELECT id FROM projects') and not rows('SELECT id FROM cases')
        assert one('SELECT id FROM entries WHERE title=?', ('Telefonat',)), 'Eintrag bleibt erhalten'
        task = one('SELECT * FROM tasks WHERE text=?', ('Rückruf',))
        assert task and task['project_id'] is None and task['case_id'] is None
        assert not rows('SELECT * FROM entry_projects') and not rows('SELECT * FROM entry_cases')
    for path in ['/', '/projects', '/cases', '/tasks', '/entry/1']:
        assert client.get(path, base_url='https://localhost').status_code == 200, path


def test_attachment_deletion_removes_the_file_and_keeps_the_entry(app, post, client):
    assert post('/entry/save', dict(title='Angebot', type='mail_in', date='2026-09-24',
        attachments=(io.BytesIO(b'Inhalt'), 'Angebot.pdf'))).status_code == 200
    with app.app_context():
        item = one('SELECT * FROM attachments')
        pfad = Path(app.instance_path)/'attachments'/item['path']
        assert pfad.exists()
    assert post(f"/attachment/{item['id']}/delete").status_code == 200
    with app.app_context():
        assert not rows('SELECT id FROM attachments')
        assert one('SELECT id FROM entries WHERE title=?', ('Angebot',))
    assert not pfad.exists(), 'Die verschlüsselte Datei muss vom Datenträger verschwinden'
    assert client.get('/entry/1', base_url='https://localhost').status_code == 200


def test_person_deletion_clears_the_participant_summary(app, post, client):
    assert post('/person/save', dict(name='Frau Beispiel', emails='beispiel@example.org')).status_code == 200
    assert post('/entry/save', dict(title='Gespräch', type='meeting', date='2026-09-24',
        participants='Frau Beispiel')).status_code == 200
    with app.app_context():
        assert 'Frau Beispiel' in one('SELECT participants FROM entries')['participants']
    assert post('/person/1/delete').status_code == 200
    with app.app_context():
        assert not rows('SELECT id FROM people')
        assert one('SELECT participants FROM entries')['participants'] == ''
        assert one('SELECT id FROM entries WHERE title=?', ('Gespräch',))
    assert client.get('/people', base_url='https://localhost').status_code == 200


def test_process_and_document_deletion_keep_what_they_produced(app, post, client):
    assert post('/process/save', dict(name='Martinszug', month='9', period='early',
        todos='Kirche anfragen')).status_code == 200
    assert post('/process/1/trigger').status_code == 200
    assert post('/process/1/delete').status_code == 200
    with app.app_context():
        assert not rows('SELECT id FROM processes')
        projekt = one('SELECT * FROM projects')
        assert projekt and projekt['process_id'] is None, 'Das erzeugte Projekt bleibt bestehen'
        assert rows('SELECT id FROM tasks'), 'Die erzeugten Aufgaben bleiben bestehen'
    assert post('/entry/save', dict(title='Notiz', type='note', date='2026-09-24')).status_code == 200
    assert post('/document/save', dict(name='Raumplan', url='https://cloud.example.org/f/1',
        owner='entry', owner_id='1')).status_code == 200
    assert post('/document/1/delete').status_code == 200
    with app.app_context():
        assert not rows('SELECT id FROM documents') and not rows('SELECT * FROM entry_documents')
        assert one('SELECT id FROM entries WHERE title=?', ('Notiz',))
    for path in ['/processes', '/projects', '/entry/1']:
        assert client.get(path, base_url='https://localhost').status_code == 200, path


def test_deletion_needs_the_session_and_a_token(app, client, post):
    assert post('/task/99/delete').status_code == 404
    assert post('/project/99/delete').status_code == 404
    assert post('/case/99/delete').status_code == 404
    assert post('/person/99/delete').status_code == 404
    assert post('/process/99/delete').status_code == 404
    assert post('/document/99/delete').status_code == 404
    assert post('/attachment/99/delete').status_code == 404
    assert client.post('/task/1/delete', base_url='https://localhost').status_code == 400, 'ohne Token'
    # Ohne Sitzung greift bereits die Tokenprüfung, deshalb 400 statt einer Weiterleitung.
    anonym = app.test_client()
    assert anonym.post('/task/1/delete', base_url='https://localhost').status_code == 400
