"""Local meeting preparation; calendars are read only, resources remain in place."""
import hashlib
import json
from datetime import datetime, timezone
from flask import url_for
from .db import get_db, one, rows
from .domain import save_task, save_entry
from .participants import normalized


def occurrence_key(value):
    if isinstance(value,datetime):
        if value.tzinfo is not None:value=value.astimezone(timezone.utc)
    return value.isoformat() if value is not None else ''


def event_key(calendar_key,uid,occurrence):
    return hashlib.sha256(json.dumps([calendar_key,uid,occurrence]).encode()).hexdigest()


def store_events(events,begin,end):
    db=get_db();own=not db.in_transaction
    if own:db.execute('BEGIN IMMEDIATE')
    try:
        # Only a successful, complete calendar read may mark events as missing.
        db.execute("UPDATE calendar_events SET state='missing' WHERE start_at<? AND end_at>?",(end,begin))
        ids={}
        for event in events:
            key=event_key(event['calendar_key'],event['uid'],event['occurrence'])
            old=one('SELECT id,date FROM calendar_events WHERE event_key=?',(key,))
            fields=('calendar_key','uid','occurrence','title','calendar','location','start_at','end_at','date','time','all_day','color')
            values=[event[field] for field in fields]
            db.execute('INSERT INTO calendar_events(event_key,'+','.join(fields)+') VALUES('+','.join('?' for _ in range(len(fields)+1))+') ON CONFLICT(event_key) DO UPDATE SET '+','.join(field+'=excluded.'+field for field in fields)+",state='active'",(key,*values))
            eid=one('SELECT id FROM calendar_events WHERE event_key=?',(key,))['id'];ids[key]=eid
            if old and old['date']!=event['date']:
                db.execute('UPDATE tasks SET due=? WHERE done=0 AND due=? AND id IN (SELECT task_id FROM meeting_points WHERE event_id=?)',(event['date'],old['date'],eid))
        if own:db.commit()
        return ids
    except Exception:
        if own:db.rollback()
        raise


def get(event_id):
    return one('SELECT e.*,(SELECT count(*) FROM meeting_points mp JOIN tasks t ON t.id=mp.task_id WHERE mp.event_id=e.id AND t.done=0) open_count FROM calendar_events e WHERE e.id=?',(event_id,))


def listing(query='',start='',include_prepared=False):
    words=normalized(query).split()
    data=rows('SELECT e.*,(SELECT count(*) FROM meeting_points mp JOIN tasks t ON t.id=mp.task_id WHERE mp.event_id=e.id AND t.done=0) open_count FROM calendar_events e ORDER BY start_at,id')
    return [e for e in data if ((e['state']=='active' and e['date']>=start) or (include_prepared and e['open_count'])) and all(w in normalized(e['title']+' '+e['calendar']+' '+e['location']+' '+e['date']) for w in words)]


def for_task(tid):
    return one('SELECT e.*,mp.attachment_id,mp.document_id,mp.source_entry_id,mp.resource_label FROM meeting_points mp JOIN calendar_events e ON e.id=mp.event_id WHERE mp.task_id=?',(tid,))


def points(event_id):
    return rows('SELECT t.*,p.name project_name FROM meeting_points mp JOIN tasks t ON t.id=mp.task_id LEFT JOIN projects p ON p.id=t.project_id WHERE mp.event_id=? ORDER BY t.done,t.id',(event_id,))


def create_point(data):
    event=get(data.get('event_id'))
    if not event or event['state']!='active':raise ValueError('Bitte einen verfügbaren Kalendertermin auswählen.')
    text=data.get('text','').strip()
    if not text or len(text)>2000:raise ValueError('Bitte einen Besprechungspunkt mit höchstens 2000 Zeichen eingeben.')
    key=data.get('request_key','')
    if not key or len(key)>100:raise ValueError('Bitte den Dialog erneut öffnen.')
    previous=one('SELECT task_id,event_id FROM meeting_points WHERE request_key=?',(key,))
    if previous:return previous['event_id'],previous['task_id']
    source=data.get('source_entry_id') or None
    attachment=data.get('attachment_id') or None
    document=data.get('document_id') or None
    label=''
    if attachment and document:raise ValueError('Bitte eine Unterlage auswählen.')
    if attachment:
        item=one('SELECT * FROM attachments WHERE id=?',(attachment,))
        if not item:raise ValueError('Der Anhang existiert nicht mehr.')
        if source and int(source)!=item['entry_id']:raise ValueError('Der Anhang gehört zu einem anderen Eintrag.')
        source=item['entry_id'];label=item['name']
    if document:
        item=one('SELECT * FROM documents WHERE id=?',(document,))
        if not item:raise ValueError('Der Dokumentverweis existiert nicht mehr.')
        if source and not one('SELECT 1 FROM entry_documents WHERE entry_id=? AND document_id=?',(source,document)):
            raise ValueError('Das Dokument ist diesem Eintrag nicht zugeordnet.')
        label=item['name']
    if source and not one('SELECT id FROM entries WHERE id=?',(source,)):raise ValueError('Der Ursprungseintrag existiert nicht mehr.')
    tid=save_task(dict(text=text,due=event['date'],entry_id=source))
    get_db().execute('INSERT INTO meeting_points(task_id,event_id,source_entry_id,attachment_id,document_id,resource_label,request_key) VALUES(?,?,?,?,?,?,?)',(tid,event['id'],source,attachment,document,label,key))
    return event['id'],tid


def protocol_candidates(event):
    candidates=rows("SELECT e.id,e.title,e.date,e.time,e.body,e.agenda FROM entries e WHERE e.type='protocol' AND e.date=? AND NOT EXISTS (SELECT 1 FROM calendar_events ce WHERE ce.protocol_entry_id=e.id AND ce.id<>?) ORDER BY e.id",(event['date'],event.get('id',-1)))
    return [e for e in candidates if normalized(e['title'])==normalized(event['title']) and (not e['time'] or not event.get('time') or e['time']==event['time'])]


def legacy_protocol_key(event):
    return 'calendar-protocol:'+event_key(event.get('calendar',''),event.get('uid') or event['title'],event['date']+' '+event.get('time',''))


def protocol_key(event):
    return 'calendar-event-protocol:'+event['event_key'] if event.get('event_key') else legacy_protocol_key(event)


def linked_protocol(event):
    if event.get('protocol_entry_id'):return event['protocol_entry_id']
    mapped=one('SELECT entry_id FROM calendar_protocol_links WHERE event_key=?',(protocol_key(event),))
    if not mapped and event.get('id'):
        mapped=one('SELECT cp.entry_id FROM calendar_protocol_links cp WHERE cp.event_key=? AND NOT EXISTS (SELECT 1 FROM calendar_events ce WHERE ce.protocol_entry_id=cp.entry_id AND ce.id<>?)',(legacy_protocol_key(event),event['id']))
    return mapped['entry_id'] if mapped else None


def cached_meeting(event):
    if event.get('id'):return get(event['id'])
    matches=rows('SELECT id FROM calendar_events WHERE uid=? AND calendar=? AND date=? AND time=?',(event.get('uid',''),event.get('calendar',''),event['date'],event.get('time','')))
    return get(matches[0]['id']) if len(matches)==1 else None


def create_protocol(event_id=None, *, event=None, existing_id=None, force_new=False):
    event=get(event_id) if event_id is not None else event
    if not event:raise ValueError('Der Termin existiert nicht.')
    key=protocol_key(event)
    previous=linked_protocol(event)
    if previous:
        if event_id is not None:get_db().execute('UPDATE calendar_events SET protocol_entry_id=? WHERE id=?',(previous,event_id))
        return previous
    candidates=protocol_candidates(event)
    if existing_id:
        selected=next((e for e in candidates if str(e['id'])==str(existing_id)),None)
        if not selected:raise ValueError('Das gewählte Protokoll passt nicht mehr zu diesem Termin. Bitte erneut auswählen.')
        eid=selected['id']
    elif len(candidates)==1 and not force_new:
        eid=candidates[0]['id']
    elif candidates and not force_new:
        raise ValueError('Mehrere passende Protokolle gefunden. Bitte ein vorhandenes Protokoll auswählen.')
    else:
        items=points(event_id) if event_id is not None else []
        def escape(value):
            for char in '\\`*_{}[]<>()#+-.!|':value=value.replace(char,'\\'+char)
            return value.replace('\n',' ')
        agenda='\n'.join('- '+escape(t['text']) for t in items if not t['done'])
        eid=save_entry(dict(type='protocol',title=event['title'],date=event['date'],time=event.get('time',''),agenda=agenda,body='',source_key=key))
    get_db().execute('INSERT INTO calendar_protocol_links(event_key,entry_id) VALUES(?,?) ON CONFLICT(event_key) DO UPDATE SET entry_id=excluded.entry_id',(key,eid))
    if event_id is not None:
        get_db().execute('UPDATE calendar_events SET protocol_entry_id=? WHERE id=?',(eid,event_id))
    return eid
