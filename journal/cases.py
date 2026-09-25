"""Unplanned day-to-day matters, separate from planned projects."""
import json
from .db import get_db, one, rows
from .domain import valid_date

STATUSES = {'open':'Offen', 'clarifying':'In Klärung', 'done':'Erledigt'}


def save(data, cid=None):
    title = data.get('title','').strip()
    if not title or len(title)>500:
        raise ValueError('Bitte einen Titel mit höchstens 500 Zeichen für den Vorgang eingeben.')
    status = data.get('status','open')
    if status not in STATUSES:
        raise ValueError('Bitte einen gültigen Vorgangsstatus auswählen.')
    follow_up = valid_date(data.get('follow_up'), optional=True)
    values = (title,data.get('description',''),status,follow_up)
    if cid:
        if not one('SELECT id FROM cases WHERE id=?',(cid,)):
            raise ValueError('Der Vorgang existiert nicht mehr.')
        get_db().execute('UPDATE cases SET title=?,description=?,status=?,follow_up=? WHERE id=?',(*values,cid))
    else:
        cid=get_db().execute('INSERT INTO cases(title,description,status,follow_up) VALUES(?,?,?,?)',values).lastrowid
    return cid


def for_entry(eid):
    return rows('SELECT c.* FROM cases c JOIN entry_cases ec ON ec.case_id=c.id WHERE ec.entry_id=? ORDER BY c.title,c.id',(eid,))


def sync_entry(eid, data):
    if not any(key in data for key in ('case_items','case_ids','cases')):
        return
    from .case_suggestions import parse, sync
    try:
        ids=json.loads(data['case_ids']) if 'case_ids' in data else ([data['cases']] if data.get('cases') else [])
        if not isinstance(ids,list):
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError('Die Vorgangsauswahl ist ungültig.')
    sync('entry',eid,parse(data,ids))


def task_case(data, existing, parent, eid):
    if 'case_id' in data:
        cid=data.get('case_id') or None
    elif existing:
        cid=existing['case_id']
    elif parent and parent['case_id']:
        cid=parent['case_id']
    elif eid:
        match=one('SELECT case_id FROM entry_cases WHERE entry_id=? ORDER BY case_id LIMIT 1',(eid,))
        cid=match['case_id'] if match else None
    else:
        cid=None
    if cid and not one('SELECT id FROM cases WHERE id=?',(cid,)):
        raise ValueError('Der gewählte Vorgang existiert nicht.')
    return cid
