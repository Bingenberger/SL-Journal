import pyotp
import pytest

from journal.db import get_db, one

BASE = 'https://localhost'


def login(app, client, device='Pixel Tablet'):
    with app.app_context():
        secret = one('SELECT totp FROM account')['totp']
        # Einmalcodes gelten nur einmal: für jede Anmeldung einen neuen Zeitschritt nehmen.
        get_db().execute('UPDATE account SET last_totp=-1'); get_db().commit()
    return client.post('/api/v1/login', base_url=BASE, json=dict(
        password='ein-testpasswort-mit-20-zeichen', otp=pyotp.TOTP(secret).now(), device=device))


@pytest.fixture
def api(app):
    client = app.test_client()
    token = login(app, client).json['token']

    def call(method, path, **kwargs):
        headers = {'Authorization': 'Bearer ' + token, **kwargs.pop('headers', {})}
        return client.open('/api/v1' + path, method=method, base_url=BASE, headers=headers, **kwargs)
    call.token = token
    call.client = client
    return call


def test_login_issues_hashed_token_and_rejects_replay(app):
    client = app.test_client()
    with app.app_context():
        secret = one('SELECT totp FROM account')['totp']
    code = pyotp.TOTP(secret).now()
    data = dict(password='ein-testpasswort-mit-20-zeichen', otp=code, device='Galaxy Tab')
    response = client.post('/api/v1/login', base_url=BASE, json=data)
    assert response.status_code == 201
    token = response.json['token']
    assert token.startswith('slj_')
    with app.app_context():
        stored = one('SELECT * FROM api_tokens')
    assert stored['name'] == 'Galaxy Tab' and token not in stored['token_hash']
    replay = client.post('/api/v1/login', base_url=BASE, json=data)
    assert replay.status_code == 401 and 'error' in replay.json


def test_wrong_password_counts_towards_rate_limit(app):
    client = app.test_client()
    for _ in range(5):
        assert client.post('/api/v1/login', base_url=BASE, json=dict(password='falsch', otp='000000')).status_code == 401
    assert client.post('/api/v1/login', base_url=BASE, json=dict(password='falsch', otp='000000')).status_code == 429


def test_requests_without_token_are_refused_as_json(app):
    client = app.test_client()
    response = client.get('/api/v1/day', base_url=BASE)
    assert response.status_code == 401 and response.json['error']
    assert client.get('/api/v1/day', base_url=BASE, headers={'Authorization': 'Bearer slj_unbekannt'}).status_code == 401


def test_session_cookie_does_not_unlock_api(client):
    assert client.get('/api/v1/me', base_url=BASE).status_code == 401


def test_https_is_required(app):
    assert app.test_client().get('/api/v1/me').status_code == 400


def test_create_and_edit_entry_with_assignments(api, app):
    with app.app_context():
        pid = get_db().execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')").lastrowid
        person = get_db().execute("INSERT INTO people(name) VALUES('Frau Klein')").lastrowid
        get_db().commit()
    response = api('POST', '/entries', json=dict(
        type='phone', date='2026-09-20', time='09:15', title='Anruf Elternbeirat', body='Termin **Schulfest** besprochen',
        tags=['Eltern', '#Fest'], participant_items=[dict(kind='person', id=person), dict(kind='new', label='Herr Bauer')],
        project_items=[dict(kind='project', id=pid)], case_items=[dict(kind='new_case', label='Parkplatzsituation')],
        tasks=[dict(text='Einladung schreiben', due='2026-09-25')]))
    assert response.status_code == 201, response.json
    entry = response.json
    assert entry['type_label'] == 'Telefonat'
    assert entry['tags'] == ['Eltern', 'Fest']
    assert [p['name'] for p in entry['projects']] == ['Schulfest']
    assert {p['label'] for p in entry['participant_items']} == {'Frau Klein', 'Herr Bauer'}
    assert entry['case_items'][0]['kind'] == 'new_case'
    assert entry['tasks'][0]['text'] == 'Einladung schreiben' and entry['tasks'][0]['project']['name'] == 'Schulfest'

    edited = api('PUT', f"/entries/{entry['id']}", json=dict(title='Anruf Elternbeirat (Rückruf)'))
    assert edited.status_code == 200
    # Nicht mitgeschickte Felder und Zuordnungen bleiben erhalten.
    assert edited.json['title'] == 'Anruf Elternbeirat (Rückruf)'
    assert edited.json['body'] == 'Termin **Schulfest** besprochen'
    assert [p['name'] for p in edited.json['projects']] == ['Schulfest']
    assert len(edited.json['participant_items']) == 2

    listing = api('GET', '/entries?q=Elternbeirat').json
    assert listing['total'] == 1 and listing['items'][0]['id'] == entry['id']
    day = api('GET', '/day?date=2026-09-20').json
    assert [e['title'] for e in day['entries']] == ['Anruf Elternbeirat (Rückruf)']


def test_entry_validation_error_is_json(api):
    response = api('POST', '/entries', json=dict(title='', type='note'))
    assert response.status_code == 400 and 'Titel' in response.json['error']
    assert api('POST', '/entries', json=dict(title='x', type='unbekannt')).status_code == 400
    assert api('GET', '/entries/999').status_code == 404


def test_new_entry_defaults_to_now(api):
    response = api('POST', '/entries', json=dict(title='Kurznotiz'))
    assert response.status_code == 201
    assert response.json['type'] == 'note' and response.json['date'] and response.json['time']


def test_attachment_upload_and_download(api):
    import io
    eid = api('POST', '/entries', json=dict(title='Foto Tafelbild')).json['id']
    response = api('POST', f'/entries/{eid}/attachments', data={'file': (io.BytesIO(b'\x89PNG-daten'), 'tafel.png', 'image/png')},
                   content_type='multipart/form-data')
    assert response.status_code == 201
    attachment = response.json['attachments'][0]
    assert attachment['name'] == 'tafel.png'
    download = api('GET', f"/attachments/{attachment['id']}")
    assert download.status_code == 200 and download.data == b'\x89PNG-daten'


def test_tasks_create_toggle_update(api):
    created = api('POST', '/tasks', json=dict(text='Hausmeister anrufen', due='2026-09-21'))
    assert created.status_code == 201
    tid = created.json['id']
    assert any(t['id'] == tid for t in api('GET', '/tasks').json['items'])
    toggled = api('POST', f'/tasks/{tid}/toggle')
    assert toggled.json['done'] is True
    assert any(t['id'] == tid for t in api('GET', '/tasks?filter=done').json['items'])
    updated = api('PUT', f'/tasks/{tid}', json=dict(text='Hausmeister zurückrufen'))
    assert updated.json['text'] == 'Hausmeister zurückrufen' and updated.json['due'] == '2026-09-21'


def test_autocomplete_delegates_to_web_suggestions(api, app):
    with app.app_context():
        get_db().execute("INSERT INTO people(name,role) VALUES('Frau Klein','Elternbeirat')"); get_db().commit()
    items = api('GET', '/autocomplete/participants?q=klein').json['items']
    assert items[0]['label'] == 'Frau Klein'
    assert api('GET', '/autocomplete/unbekannt').status_code == 404


def test_logout_and_revocation(api, app, client):
    assert api('GET', '/me').status_code == 200
    with app.app_context():
        did = one('SELECT id FROM api_tokens')['id']
    page = client.get('/settings', base_url=BASE)
    assert b'Pixel Tablet' in page.data
    response = client.post(f'/device/{did}/revoke', base_url=BASE, data={'csrf_token': 'test-csrf'}, headers={'X-Requested-With': 'fetch'})
    assert response.json['ok']
    assert api('GET', '/me').status_code == 401


def test_session_version_change_invalidates_tokens(api, app):
    with app.app_context():
        get_db().execute("UPDATE account SET session_version='neu'"); get_db().commit()
    assert api('GET', '/me').status_code == 401
    with app.app_context():
        assert one('SELECT count(*) n FROM api_tokens')['n'] == 0


def test_idle_tokens_expire(api, app):
    with app.app_context():
        get_db().execute("UPDATE api_tokens SET last_used='2020-01-01T00:00:00+01:00'"); get_db().commit()
    assert api('GET', '/me').status_code == 401


def test_own_logout(api):
    assert api('POST', '/logout').status_code == 200
    assert api('GET', '/me').status_code == 401


def test_voice_note_from_app(api, app):
    import io
    from pathlib import Path
    from journal.db import cipher
    from journal.domain import now
    response = api('POST', '/voice', data={'audio': (io.BytesIO(b'm4a-audio'), 'Sprachi', 'audio/mp4')},
                   content_type='multipart/form-data')
    assert response.status_code == 201
    entry = response.json
    assert entry['type'] == 'journal' and entry['date'] == now().date().isoformat()
    assert entry['title'].startswith('Sprachi · ')
    attachment = entry['attachments'][0]
    assert attachment['name'].endswith('.m4a') and attachment['mime'] == 'audio/mp4'
    with app.app_context():
        stored = one('SELECT path FROM attachments WHERE id=?', (attachment['id'],))['path']
        encrypted = (Path(app.instance_path) / 'attachments' / stored).read_bytes()
        assert b'm4a-audio' not in encrypted and cipher().decrypt(encrypted) == b'm4a-audio'
    assert api('GET', f"/attachments/{attachment['id']}").data == b'm4a-audio'


@pytest.mark.parametrize('content,mime', [(b'', 'audio/mp4'), (b'html', 'text/html')])
def test_invalid_voice_note_from_app(api, app, content, mime):
    import io
    response = api('POST', '/voice', data={'audio': (io.BytesIO(content), 'Sprachi', mime)}, content_type='multipart/form-data')
    assert response.status_code == 400 and response.json['error']
    with app.app_context():
        assert one('SELECT count(*) n FROM entries')['n'] == 0
