"""JSON-Schnittstelle für die Android-Begleit-App.

Die App meldet sich einmal mit Passwort und Einmalcode an und erhält ein
Gerätetoken. Gespeichert wird nur dessen SHA-256-Wert; das Token selbst kennt
allein das Gerät. Tokens verfallen nach 90 Tagen ohne Nutzung, beim Widerruf
in den Einstellungen und wenn die Sitzungsversion des Kontos wechselt
(z. B. nach „alle Sitzungen beenden“ in der Wartung).

Anfragen tragen das Token als ``Authorization: Bearer …``. Cookies spielen
keine Rolle, deshalb entfällt hier die CSRF-Prüfung der Browseroberfläche.
"""
import hashlib
import hmac
import secrets
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, g, jsonify, request

from .auth import login_failed, rate_limit, valid_code, verify
from .db import get_db, one, rows
from .domain import TYPES, UNPROCESSED_MAIL, clean_tags, entries, entry_details, now, save_attachment, save_entry, save_task, school_year, valid_date

bp = Blueprint('mobile_api', __name__, url_prefix='/api/v1')

API_VERSION = 1
TOKEN_PREFIX = 'slj_'
IDLE_DAYS = 90
PAGE = 40

SCHEMA = '''
CREATE TABLE IF NOT EXISTS api_tokens (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
 session_version TEXT NOT NULL, created_at TEXT NOT NULL, last_used TEXT NOT NULL);
'''


def init():
    get_db().executescript(SCHEMA)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def devices():
    """Angemeldete Geräte für die Einstellungsseite, neueste Nutzung zuerst."""
    return rows('SELECT id,name,created_at,last_used FROM api_tokens ORDER BY last_used DESC,id DESC')


def revoke(did):
    return get_db().execute('DELETE FROM api_tokens WHERE id=?', (did,)).rowcount


def stamp():
    return now().isoformat(timespec='seconds')


def expired(last_used):
    try:
        last = datetime.fromisoformat(last_used)
    except (TypeError, ValueError):
        return True
    return now() - last > timedelta(days=IDLE_DAYS)


@bp.before_request
def authenticate():
    if request.endpoint == 'mobile_api.login':
        return
    header = request.headers.get('Authorization', '')
    token = header[7:].strip() if header[:7].lower() == 'bearer ' else ''
    if not token.startswith(TOKEN_PREFIX):
        abort(401, 'Bitte in der App erneut anmelden.')
    device = one('SELECT * FROM api_tokens WHERE token_hash=?', (digest(token),))
    account = one('SELECT session_version FROM account WHERE id=1')
    if not device or not account or expired(device['last_used']) \
            or not hmac.compare_digest(device['session_version'], account['session_version']):
        if device:
            revoke(device['id'])
            get_db().commit()
        abort(401, 'Die Anmeldung dieses Geräts ist abgelaufen oder wurde widerrufen. Bitte erneut anmelden.')
    get_db().execute('UPDATE api_tokens SET last_used=? WHERE id=?', (stamp(), device['id']))
    get_db().commit()
    g.device = device


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Die Anfrage enthält keine gültigen Daten.')
    return data


def ok(payload=None, status=200):
    get_db().commit()
    return jsonify(payload if payload is not None else {'ok': True}), status


# ---------------------------------------------------------------- Anmeldung

@bp.post('/login')
def login():
    account = one('SELECT * FROM account WHERE id=1')
    if not account:
        abort(409, 'Das Journal ist noch nicht eingerichtet. Bitte zuerst im Browser einrichten.')
    rate_limit()
    data = request.get_json(silent=True) or {}
    code = data.get('otp', '')
    if not valid_code(code) or not isinstance(data.get('password'), str) \
            or not verify(account, data['password'], code):
        login_failed()
        abort(401, 'Passwort oder Einmalcode ungültig. Bereits verwendete Codes können nicht erneut genutzt werden.')
    name = ' '.join(str(data.get('device') or '').split())[:80] or 'Android-Gerät'
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    get_db().execute('INSERT INTO api_tokens(name,token_hash,session_version,created_at,last_used) VALUES(?,?,?,?,?)',
                     (name, digest(token), account['session_version'], stamp(), stamp()))
    return ok(dict(token=token, device=name, api=API_VERSION), 201)


@bp.post('/logout')
def logout():
    revoke(g.device['id'])
    return ok()


@bp.get('/me')
def me():
    from .cases import STATUSES
    return jsonify(api=API_VERSION, device=g.device['name'], today=now().date().isoformat(),
                   school_year=school_year(), types=TYPES, case_statuses=STATUSES,
                   inbox_count=one('SELECT count(*) n FROM entries e WHERE ' + UNPROCESSED_MAIL)['n'])


# ---------------------------------------------------------------- Darstellung

def entry_summary(entry):
    """Knappe Kartenansicht eines Eintrags für Listen."""
    text = ' '.join((entry.get('body') or '').split())
    return dict(id=entry['id'], date=entry['date'], time=entry['time'], type=entry['type'],
                type_label=TYPES[entry['type']], title=entry['title'], excerpt=text[:240],
                sender=entry['sender'], recipients=entry['recipients'], participants=entry['participants'],
                tags=[t for t in (x.strip() for x in entry['tags'].split(',')) if t],
                projects=[dict(id=p['id'], name=p['name']) for p in entry.get('projects', [])],
                cases=[dict(id=c['id'], title=c['title']) for c in entry.get('cases', [])],
                attachment_count=len(entry.get('attachments', [])),
                drawing_count=len(entry.get('drawings', [])))


def entry_full(entry):
    result = entry_summary(entry)
    result.update(body=entry['body'], agenda=entry['agenda'], decisions=entry['decisions'],
                  needs_review=bool(entry['needs_review']),
                  participant_items=entry['participant_items'], project_items=entry['project_items'],
                  case_items=entry['case_items'],
                  attachments=[dict(id=a['id'], name=a['name'], mime=a['mime'], size=a['size']) for a in entry['attachments']],
                  drawings=[dict(id=d['id'], title=d['title']) for d in entry['drawings']],
                  tasks=[task_json(t) for t in rows('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE t.entry_id=? ORDER BY t.done,t.due IS NULL,t.due,t.id', (entry['id'],))])
    return result


def task_json(task):
    case = one('SELECT id,title FROM cases WHERE id=?', (task['case_id'],)) if task.get('case_id') else None
    return dict(id=task['id'], text=task['text'], due=task['due'], done=bool(task['done']),
                completed_at=task['completed_at'], parent_id=task['parent_id'], entry_id=task['entry_id'],
                project=dict(id=task['project_id'], name=task.get('project_name') or '') if task['project_id'] else None,
                case=case,
                subtasks=rows('SELECT id,text,done,due FROM tasks WHERE parent_id=? ORDER BY done,due IS NULL,due,id', (task['id'],)))


TASK_SQL = 'SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id'


# ---------------------------------------------------------------- Tagesansicht

@bp.get('/day')
def day():
    from .recurrence import generate
    generate()
    current = date.fromisoformat(valid_date(request.args.get('date', now().date().isoformat())))
    iso = current.isoformat()
    open_tasks = rows(TASK_SQL + ' WHERE t.done=0 ORDER BY t.due,t.id')
    soon = (current + timedelta(days=14)).isoformat()
    completed = rows(TASK_SQL + ' WHERE t.done=1 AND substr(t.completed_at,1,10)=? ORDER BY t.completed_at DESC,t.id DESC', (iso,))
    from .integrations import cached_events
    events, calendar_status = cached_events(current)
    get_db().commit()
    return jsonify(
        date=iso, previous=(current - timedelta(days=1)).isoformat(), following=(current + timedelta(days=1)).isoformat(),
        entries=[entry_summary(e) for e in entries('SELECT * FROM entries WHERE date=? ORDER BY time DESC,id DESC', (iso,))],
        task_groups=[
            dict(key='overdue', label='Überfällig', tasks=[task_json(t) for t in open_tasks if t['due'] and t['due'] < iso]),
            dict(key='today', label='Heute fällig', tasks=[task_json(t) for t in open_tasks if t['due'] == iso]),
            dict(key='soon', label='In den nächsten 14 Tagen', tasks=[task_json(t) for t in open_tasks if t['due'] and iso < t['due'] <= soon]),
        ],
        undated_count=sum(t['due'] is None for t in open_tasks),
        completed_tasks=[task_json(t) for t in completed],
        case_reminders=rows("SELECT id,title,status,follow_up FROM cases WHERE status<>'done' AND follow_up<=? ORDER BY follow_up,title", (iso,)),
        events=[dict(title=e.get('title', ''), time=e.get('time', ''), end=e.get('end', ''), location=e.get('location', ''),
                     calendar=e.get('calendar', ''), all_day=bool(e.get('all_day'))) for e in events],
        calendar_status=calendar_status,
    )


# ---------------------------------------------------------------- Einträge

@bp.get('/entries')
def entry_list():
    params, clauses = [], []
    if request.args.get('inbox') == '1':
        clauses.append(UNPROCESSED_MAIL)
    if request.args.get('type') in TYPES:
        clauses.append('e.type=?'); params.append(request.args['type'])
    if request.args.get('q', '').strip():
        terms = request.args['q'][:200].split()
        clauses.append('e.id IN (SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?)')
        params.append(' AND '.join('"' + t.replace('"', '""') + '"*' for t in terms))
    if request.args.get('tag'):
        clauses.append('has_tag(e.tags,?)'); params.append(request.args['tag'])
    for key, table in (('project_id', 'entry_projects'), ('case_id', 'entry_cases')):
        value = request.args.get(key, type=int)
        if value:
            clauses.append(f'e.id IN (SELECT entry_id FROM {table} WHERE {key}=?)'); params.append(value)
    page = max(1, request.args.get('page', 1, type=int))
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    total = one('SELECT count(*) n FROM entries e' + where, params)['n']
    data = entries('SELECT e.* FROM entries e' + where + ' ORDER BY date DESC,time DESC,id DESC LIMIT ? OFFSET ?', (*params, PAGE, (page - 1) * PAGE))
    return jsonify(items=[entry_summary(e) for e in data], total=total, page=page, pages=max(1, -(-total // PAGE)))


def load_entry(eid):
    entry = one('SELECT * FROM entries WHERE id=?', (eid,))
    if not entry:
        abort(404, 'Der Eintrag existiert nicht mehr.')
    return entry_details(entry)


@bp.get('/entries/<int:eid>')
def entry_view(eid):
    return jsonify(entry_full(load_entry(eid)))


def entry_payload(data, existing=None):
    """JSON der App in die Form bringen, die save_entry erwartet. Fehlende
    Felder behalten beim Bearbeiten ihren bisherigen Wert."""
    base = {}
    if existing:
        base = {key: existing[key] for key in ('type', 'date', 'time', 'title', 'body', 'agenda', 'decisions', 'sender', 'recipients', 'tags')}
        base.update(participant_items=existing['participant_items'], project_items=existing['project_items'], case_items=existing['case_items'])
    else:
        stamp_ = now()
        base.update(type='note', date=stamp_.date().isoformat(), time=stamp_.strftime('%H:%M'),
                    participant_items=[], project_items=[], case_items=[])
    for key in ('type', 'date', 'time', 'title', 'body', 'agenda', 'decisions', 'sender', 'recipients'):
        if key in data:
            if not isinstance(data[key], str):
                raise ValueError('Ungültige Angabe im Feld „' + key + '“.')
            base[key] = data[key]
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, list):
            tags = ', '.join(str(t) for t in tags)
        if not isinstance(tags, str):
            raise ValueError('Die Tags sind ungültig.')
        base['tags'] = clean_tags(tags)
    for key in ('participant_items', 'project_items', 'case_items'):
        if key in data:
            if not isinstance(data[key], list):
                raise ValueError('Die Auswahl ist ungültig.')
            base[key] = data[key]
    for key in ('title', 'body', 'agenda', 'decisions'):
        if len(base.get(key) or '') > 200_000:
            raise ValueError('Der Text ist zu lang.')
    base['needs_review'] = False
    return base


def new_tasks(data, eid):
    tasks = data.get('tasks') or []
    if not isinstance(tasks, list) or len(tasks) > 100:
        raise ValueError('Bitte höchstens 100 Aufgaben mitschicken.')
    from .domain import save_task_rows
    texts = [str((t or {}).get('text') or '') for t in tasks]
    dates = [str((t or {}).get('due') or '') for t in tasks]
    save_task_rows(texts, dates, entry_id=eid)


@bp.post('/entries')
def entry_create():
    data = body()
    get_db().execute('BEGIN IMMEDIATE')
    eid = save_entry(entry_payload(data))
    new_tasks(data, eid)
    get_db().commit()
    return ok(entry_full(load_entry(eid)), 201)


@bp.put('/entries/<int:eid>')
def entry_update(eid):
    data = body()
    get_db().execute('BEGIN IMMEDIATE')
    existing = load_entry(eid)
    save_entry(entry_payload(data, existing), entry_id=eid)
    new_tasks(data, eid)
    get_db().commit()
    return ok(entry_full(load_entry(eid)))


@bp.post('/entries/<int:eid>/attachments')
def attachment_upload(eid):
    load_entry(eid)
    uploads = [u for u in request.files.getlist('file') if u.filename]
    if not uploads:
        raise ValueError('Bitte eine Datei auswählen.')
    for upload in uploads:
        save_attachment(eid, upload.filename, upload.read(25 * 1024 * 1024 + 1), upload.mimetype)
    return ok(entry_full(load_entry(eid)), 201)


@bp.get('/attachments/<int:aid>')
def attachment_download(aid):
    import io
    from pathlib import Path
    from flask import send_file
    from .db import cipher
    item = one('SELECT * FROM attachments WHERE id=?', (aid,))
    if not item:
        abort(404, 'Der Anhang existiert nicht mehr.')
    path = Path(current_app.instance_path) / 'attachments' / item['path']
    if not path.exists():
        abort(404, 'Die Anhangsdatei fehlt.')
    return send_file(io.BytesIO(cipher().decrypt(path.read_bytes())), as_attachment=True,
                     download_name=item['name'], mimetype='application/octet-stream')


# ---------------------------------------------------------------- Aufgaben

@bp.get('/tasks')
def task_list():
    from .participants import normalized
    from .recurrence import generate
    generate()
    mode = request.args.get('filter', 'open')
    where = {'open': 't.done=0', 'undated': 't.done=0 AND t.due IS NULL', 'done': 't.done=1', 'all': '1=1'}.get(mode, 't.done=0')
    data = rows(TASK_SQL + ' WHERE ' + where + ' ORDER BY t.done,t.due IS NULL,t.due,t.id')
    query = normalized(request.args.get('q', ''))[:200]
    if query:
        data = [t for t in data if all(word in normalized(t['text']) for word in query.split())]
    if mode == 'done':
        data = sorted(data, key=lambda t: t['completed_at'] or '', reverse=True)[:200]
    get_db().commit()
    return jsonify(items=[task_json(t) for t in data if not t['parent_id']] if request.args.get('top') == '1' else [task_json(t) for t in data])


def task_payload(data, existing=None):
    result = {}
    if existing:
        # Nicht mitgeschickte Zuordnungen bleiben erhalten, auch Projektvorschläge.
        from .project_suggestions import items
        result.update(text=existing['text'], due=existing['due'] or '', project_items=items('task', existing['id']))
    for key in ('text', 'due'):
        if key in data:
            value = data[key] or ''
            if not isinstance(value, str):
                raise ValueError('Ungültige Angabe im Feld „' + key + '“.')
            result[key] = value
    for key in ('project_id', 'case_id', 'entry_id', 'parent_id'):
        if key in data:
            value = data[key]
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError('Ungültige Zuordnung.')
            result[key] = value or ''
    if 'project_id' in result:
        result['project_items'] = [dict(kind='project', id=result['project_id'])] if result['project_id'] else []
    return result


@bp.post('/tasks')
def task_create():
    get_db().execute('BEGIN IMMEDIATE')
    tid = save_task(task_payload(body()))
    return ok(task_json(one(TASK_SQL + ' WHERE t.id=?', (tid,))), 201)


@bp.put('/tasks/<int:tid>')
def task_update(tid):
    data = body()
    get_db().execute('BEGIN IMMEDIATE')
    existing = one('SELECT * FROM tasks WHERE id=?', (tid,))
    if not existing:
        abort(404, 'Die Aufgabe existiert nicht mehr.')
    save_task(task_payload(data, existing), tid)
    return ok(task_json(one(TASK_SQL + ' WHERE t.id=?', (tid,))))


@bp.post('/tasks/<int:tid>/toggle')
def task_toggle(tid):
    from .domain import toggle_task
    get_db().execute('BEGIN IMMEDIATE')
    if not one('SELECT id FROM tasks WHERE id=?', (tid,)):
        abort(404, 'Die Aufgabe existiert nicht mehr.')
    toggle_task(tid)
    return ok(task_json(one(TASK_SQL + ' WHERE t.id=?', (tid,))))


# ---------------------------------------------------------------- Auswahlhilfen

@bp.get('/autocomplete/<kind>')
def autocomplete(kind):
    """Dieselben Vorschläge wie in den Formularen der Weboberfläche."""
    if kind not in ('participants', 'people', 'projects', 'cases', 'tags', 'entries'):
        abort(404)
    return current_app.view_functions['autocomplete'](kind)


@bp.get('/projects')
def project_list():
    return jsonify(items=rows("SELECT id,name,school_year,status FROM projects WHERE status='active' ORDER BY name"))


@bp.get('/cases')
def case_list():
    return jsonify(items=rows("SELECT id,title,status,follow_up FROM cases WHERE status<>'done' ORDER BY follow_up IS NULL,follow_up,title"))
