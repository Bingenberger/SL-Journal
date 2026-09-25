import calendar
import json
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app
from .db import get_db, rows, one, cipher, atomic_write

TYPES = {'mail_in':'Mail · Eingang','mail_out':'Mail · Ausgang','meeting':'Gespräch','protocol':'Protokoll','phone':'Telefonat','journal':'Journal','note':'Notiz'}
# Shared by the inbox list, navigation badge and cockpit summary.
UNPROCESSED_MAIL = "e.type IN ('mail_in','mail_out') AND trim(e.tags, char(9)||char(10)||char(13)||' ,')='' AND NOT EXISTS(SELECT 1 FROM entry_projects WHERE entry_id=e.id) AND NOT EXISTS(SELECT 1 FROM entry_cases WHERE entry_id=e.id)"

MONTHS = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember']
PERIODS = {'early':'Anfang / erste Woche','middle':'Mitte','late':'Ende'}


def now():
    return datetime.now(ZoneInfo('Europe/Berlin'))


def school_year(day=None):
    day = day or now().date()
    year = day.year if day.month >= 8 else day.year - 1
    return f'{year}/{str(year+1)[-2:]}'


def valid_date(value, optional=False):
    if not value and optional:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise ValueError('Bitte ein gültiges Datum eingeben.')


def clean_tags(value):
    return ', '.join(dict.fromkeys(t.strip().lstrip('#') for t in re.split(r'[,\n]', value) if t.strip().lstrip('#')))


def entry_details(entry):
    from .cases import for_entry
    entry['cases'] = for_entry(entry['id'])
    from .case_suggestions import items as case_items
    entry['case_items'] = case_items('entry',entry['id'])
    entry['projects'] = rows('SELECT p.* FROM projects p JOIN entry_projects ep ON ep.project_id=p.id WHERE ep.entry_id=? ORDER BY p.name', (entry['id'],))
    from .project_suggestions import items
    entry['project_items'] = items('entry', entry['id'])
    entry['people'] = rows('SELECT p.* FROM people p JOIN entry_people ep ON ep.person_id=p.id WHERE ep.entry_id=?', (entry['id'],))
    from .participants import participant_items
    entry['participant_items'] = participant_items(entry['id'])
    entry['drawings'] = rows('SELECT id,title,revision FROM drawings WHERE entry_id=? ORDER BY id', (entry['id'],))
    entry['attachments'] = rows('SELECT * FROM attachments WHERE entry_id=?', (entry['id'],))
    return entry


def entries(sql='SELECT * FROM entries ORDER BY date DESC,time DESC,id DESC', params=()):
    return [entry_details(e) for e in rows(sql, params)]


def save_entry(data, project_ids=(), person_ids=(), entry_id=None):
    title = data.get('title', '').strip()
    if not title:
        raise ValueError('Ein Titel fehlt noch.')
    kind = data.get('type', 'note')
    if kind not in TYPES:
        raise ValueError('Unbekannter Eintragstyp.')
    entry_date = valid_date(data.get('date'))
    time = data.get('time', '')
    if time:
        try:
            datetime.strptime(time, '%H:%M')
        except ValueError:
            raise ValueError('Bitte eine gültige Uhrzeit eingeben.')
    values = (entry_date,time,kind,title,data.get('body',''),data.get('participants',''),data.get('sender',''),data.get('recipients',''),clean_tags(data.get('tags','')),int(bool(data.get('needs_review',False))))
    db = get_db()
    if entry_id:
        db.execute('UPDATE entries SET date=?,time=?,type=?,title=?,body=?,participants=?,sender=?,recipients=?,tags=?,needs_review=? WHERE id=?', (*values,entry_id))
        db.execute('DELETE FROM entry_projects WHERE entry_id=?',(entry_id,))
    else:
        entry_id = db.execute('INSERT INTO entries(date,time,type,title,body,participants,sender,recipients,tags,needs_review,source_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (*values,data.get('source_key'))).lastrowid
    previous = one('SELECT agenda,decisions FROM entries WHERE id=?',(entry_id,))
    db.execute('UPDATE entries SET agenda=?,decisions=? WHERE id=?',
        (data.get('agenda',previous['agenda']),data.get('decisions',previous['decisions']),entry_id))
    from .project_suggestions import parse, sync
    sync('entry', entry_id, parse(data, project_ids))
    from .participants import sync_participants
    sync_participants(entry_id, data, person_ids)
    from .cases import sync_entry
    sync_entry(entry_id, data)
    return entry_id


def save_task(data, task_id=None):
    text = data.get('text','').strip()
    if not text:
        raise ValueError('Der Aufgabentext fehlt noch.')
    due = valid_date(data.get('due'), optional=True)
    existing = one('SELECT * FROM tasks WHERE id=?',(task_id,)) if task_id else None
    parent_id = data.get('parent_id') or (existing['parent_id'] if existing else None)
    parent = None
    if parent_id:
        parent = one('SELECT * FROM tasks WHERE id=?',(parent_id,))
        if not parent or parent['parent_id'] or (task_id and int(parent_id)==int(task_id)):
            raise ValueError('Bitte eine gültige Hauptaufgabe wählen. Unteraufgaben haben eine Ebene.')
        if task_id and one('SELECT id FROM tasks WHERE parent_id=?',(task_id,)):
            raise ValueError('Eine Hauptaufgabe mit Unteraufgaben kann nicht selbst Unteraufgabe werden.')
    pid = data.get('project_id') or (parent['project_id'] if parent else None)
    eid = data.get('entry_id') or (parent['entry_id'] if parent else None)
    if eid:
        if not one('SELECT id FROM entries WHERE id=?',(eid,)):
            raise ValueError('Der Herkunftseintrag existiert nicht.')
        if not pid:
            context = one('SELECT project_id FROM entry_projects WHERE entry_id=? ORDER BY project_id LIMIT 1',(eid,))
            pid = context['project_id'] if context else None
    if pid and not one('SELECT id FROM projects WHERE id=?',(pid,)):
        raise ValueError('Das gewählte Projekt existiert nicht.')
    from .project_suggestions import parse, sync, items
    project_data = data
    if 'project_items' not in data and not data.get('project_id') and eid:
        project_data = dict(data)
        project_data['project_items'] = items('entry', eid)[:1]
    if parent and not data.get('project_id') and not data.get('project_items'):
        project_data = dict(data)
        project_data['project_items'] = items('task',parent['id'])
    selected = parse(project_data, [pid], single=True)
    if not selected and parent:
        selected = parse({'project_items': items('task',parent['id'])}, single=True)
    if not selected and eid:
        selected = parse({'project_items': items('entry', eid)[:1]}, single=True)
    if task_id:
        get_db().execute('UPDATE tasks SET text=?,due=?,project_id=?,entry_id=? WHERE id=?',(text,due,pid,eid,task_id))
    else:
        task_id = get_db().execute('INSERT INTO tasks(text,due,project_id,entry_id) VALUES(?,?,?,?)',(text,due,pid,eid)).lastrowid
    get_db().execute('UPDATE tasks SET parent_id=? WHERE id=?',(parent_id,task_id))
    if parent and not one('SELECT done FROM tasks WHERE id=?',(task_id,))['done']:
        get_db().execute('UPDATE tasks SET done=0,completed_at=NULL WHERE id=?',(parent_id,))
    sync('task', task_id, selected)
    from .cases import task_case
    from .case_suggestions import parse as parse_cases, sync as sync_cases, items as case_items
    if 'case_items' in data:
        chosen = parse_cases(data, single=True)
    elif 'case_id' in data:
        chosen = parse_cases({}, [task_case(data, existing, parent, eid)], single=True)
    else:
        inherited = case_items('task',existing['id']) if existing else case_items('task',parent['id']) if parent else case_items('entry',eid)[:1] if eid else []
        chosen = parse_cases({'case_items': inherited}, single=True)
    sync_cases('task',task_id,chosen)
    return task_id


def save_attachment(entry_id, name, content, mime):
    if len(content) > 25 * 1024 * 1024:
        raise ValueError('Ein Anhang darf höchstens 25 MB groß sein.')
    name = name.replace('\\','/').split('/')[-1].strip() or 'Anhang'
    path = uuid.uuid4().hex + '.enc'
    atomic_write(Path(current_app.instance_path)/'attachments'/path, cipher().encrypt(content))
    get_db().execute('INSERT INTO attachments(entry_id,name,path,mime,size) VALUES(?,?,?,?,?)',(entry_id,name,path,mime or 'application/octet-stream',len(content)))


def process_due(process, day):
    year = int(school_year(day).split('/')[0]) + (1 if process['month'] < 8 else 0)
    start = {'early':1,'middle':11,'late':21}[process['period']]
    anchor = date(year,process['month'],start)
    return day >= anchor and process['last_trigger'] != school_year(day)


def trigger_process(pid, day):
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    process = one('SELECT * FROM processes WHERE id=?',(pid,))
    if not process or not process_due(process, day):
        raise ValueError('Dieser Jahresprozess ist noch nicht fällig oder wurde bereits gestartet.')
    year = school_year(day)
    project_id = db.execute('INSERT INTO projects(name,description,school_year,process_id) VALUES(?,?,?,?)',(process['name'],f"Aus Jahresprozess: {PERIODS[process['period']]} {MONTHS[process['month']-1]}",year,pid)).lastrowid
    for text in json.loads(process['todos']):
        save_task({'text':text,'project_id':project_id})
    db.execute('UPDATE processes SET last_trigger=? WHERE id=?',(year,pid))
    db.commit()
    return project_id


def save_task_rows(texts, dates, entry_id=None, parent_id=None):
    if len(texts)>100 or len(texts)!=len(dates):
        raise ValueError('Bitte höchstens 100 Aufgaben mit gültigen Datumsfeldern erfassen.')
    for text, due in zip(texts, dates):
        if not text.strip():
            if due:
                raise ValueError('Zu einem Fälligkeitsdatum fehlt der Aufgabentext.')
            continue
        save_task({'text':text,'due':due,'entry_id':entry_id,'parent_id':parent_id})


def task_family(task_id):
    task = one('SELECT parent_id FROM tasks WHERE id=?',(task_id,))
    parent = one('SELECT id,text FROM tasks WHERE id=?',(task['parent_id'],)) if task and task['parent_id'] else None
    children = rows('SELECT id,text,done,due FROM tasks WHERE parent_id=? ORDER BY done,due IS NULL,due,id',(task_id,))
    return dict(parent=parent,children=children,completed=sum(t['done'] for t in children))


def toggle_task(task_id):
    task = one('SELECT * FROM tasks WHERE id=?',(task_id,))
    if not task:
        raise ValueError('Die Aufgabe existiert nicht.')
    if not task['done'] and one('SELECT id FROM tasks WHERE parent_id=? AND done=0',(task_id,)):
        raise ValueError('Bitte zuerst die offenen Unteraufgaben erledigen.')
    get_db().execute('UPDATE tasks SET done=?,completed_at=? WHERE id=?',(0 if task['done'] else 1,None if task['done'] else now().isoformat(),task_id))
    if task['done'] and task['parent_id']:
        get_db().execute('UPDATE tasks SET done=0,completed_at=NULL WHERE id=?',(task['parent_id'],))
