"""Read-only IMAP and CalDAV integrations. No remote messages or events are changed."""
import hashlib
import html
import imaplib
import json
import re
from datetime import date, datetime, time, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app
from .db import atomic_write, cipher, get_db, one, rows, set_setting, setting
from .domain import now, save_attachment, save_entry

TZ=ZoneInfo('Europe/Berlin')


def addresses(value):
    return {address.lower() for _,address in getaddresses([value or '']) if '@' in address}


def mail_date(value):
    try:
        dt=parsedate_to_datetime(value)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except (TypeError,ValueError,OverflowError):
        # Apple Mail and Thunderbird may localize the date inside forwarded text.
        value=str(value or '').strip()
        months={'Januar':'January','Februar':'February','März':'March','April':'April','Mai':'May','Juni':'June','Juli':'July','August':'August','September':'September','Oktober':'October','November':'November','Dezember':'December'}
        for german,english in months.items():
            value=re.sub(r'\b'+german+r'\b',english,value,flags=re.I)
        value=re.sub(r'^(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|Mo|Di|Mi|Do|Fr|Sa|So)[,.]?\s*','',value,flags=re.I)
        value=re.sub(r'\s+um\s+',' ',value,flags=re.I)
        value=re.sub(r'(\d)\.\s+(?=[A-Za-z])',r'\1 ',value)
        try:
            from dateutil.parser import parse
            dt=parse(value,dayfirst=True,fuzzy=False,tzinfos={'MEZ':3600,'MESZ':7200,'CET':3600,'CEST':7200})
            # Require an explicit year to avoid silently inventing an original date.
            if not re.search(r'\b(?:19|20)\d{2}\b',value): return None
            return (dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt).astimezone(TZ)
        except (ValueError,TypeError,OverflowError):
            return None


def body_text(message):
    body=message.get_body(preferencelist=('plain','html'))
    if body is None: return ''
    try: text=body.get_content()
    except (LookupError,UnicodeError): text=(body.get_payload(decode=True) or b'').decode('utf-8','replace')
    if body.get_content_type()=='text/html':
        text=re.sub(r'<(script|style)\b[^>]*>.*?</\1>','',text,flags=re.S|re.I)
        text=re.sub(r'<(?:br\s*/?|/?(?:p|div|tr|table))\b[^>]*>','\n',text,flags=re.I)
        text=html.unescape(re.sub(r'<[^>]+>','',text))
    return text.strip()


def parse_forward(text, allow_header_only=False):
    marker=re.search(r'(?:[-–—_]{2,}\s*(?:Weitergeleitete Nachricht|Forwarded Message|Original Message|Ursprüngliche Nachricht)\s*[-–—_]{2,}|Anfang der weitergeleiteten Nachricht:|Begin forwarded message:)',text,re.I)
    aliases={'von':'sender','from':'sender','an':'recipients','to':'recipients','betreff':'title','subject':'title',
             'datum':'date','date':'date','gesendet':'date','sent':'date','sent on':'date','cc':'cc','bcc':'bcc',
             'antwort an':'reply_to','antwort-an':'reply_to','reply-to':'reply_to','reply to':'reply_to',
             'importance':'importance','wichtigkeit':'importance','priorität':'importance','priority':'importance'}
    def clean(line):
        return re.sub(r'^(?:[ \t]*>[ \t]?)+','',line).strip()
    def header(line):
        match=re.match(r'^\*{0,2}([^:]+):\*{0,2}\s*(.*)$',clean(line))
        if match and match[1].strip().lower() in aliases:
            return aliases[match[1].strip().lower()],match[2].strip()
        return None
    if marker:
        block=text[marker.end():].lstrip('\r\n ')
    elif allow_header_only:
        lines=text.splitlines(keepends=True)
        start=next((i for i,line in enumerate(lines[:80]) if header(line) and header(line)[0]=='sender'),None)
        if start is None: return None
        block=''.join(lines[start:])
    else:
        return None
    lines=block.splitlines(keepends=True)
    fields={};last=None;end=0
    for index,line in enumerate(lines[:80]):
        value=clean(line)
        if not value:
            following=next((header(part) for part in lines[index+1:] if clean(part)),None)
            if not fields or (following and following[0] not in fields):
                end+=len(line);continue
            end+=len(line);break
        parsed_header=header(line)
        if parsed_header:
            field,value=parsed_header
            if field in fields: break
            fields[field]=value;last=field;end+=len(line);continue
        if not last: break
        # Thunderbird also wraps long subjects without indentation.
        ahead=[]
        for following in lines[index+1:]:
            if not clean(following): break
            ahead.append(following)
        next_header=any(header(part) for part in ahead)
        if next_header or line[:1].isspace() or (last in ('sender','recipients','cc','bcc') and '@' in value):
            fields[last]+=' '+value
            end+=len(line)
        else:
            break
    parsed=mail_date(fields.get('date'))
    if not addresses(fields.get('sender')) or not fields.get('title') or not parsed:
        return {'uncertain':True}
    fields['recipients']=', '.join(fields[key] for key in ('recipients','cc','bcc') if fields.get(key))
    body=block[end:].strip()
    # Remove one transport quote level only if the whole original body is quoted.
    body_lines=body.splitlines()
    if body_lines and all(not line.strip() or re.match(r'^\s*>',line) for line in body_lines):
        body='\n'.join(re.sub(r'^[ \t]*>[ \t]?','',line) for line in body_lines).strip()
    fields.update(datetime=parsed,body=body,uncertain=False)
    return fields

def subject_base(subject):
    return re.sub(r'^(?:(?:re|aw|fwd?|wg):\s*)+','',subject,flags=re.I).strip().lower()


def suggest_projects(title,sender):
    projects=rows("SELECT * FROM projects WHERE status='active' ORDER BY name")
    labels={v.casefold() for v in re.findall(r'\[([^\]]+)\]',title)}
    matches=[]
    for p in projects:
        if p['name'].casefold() in labels:
            matches.append(dict(p,reason='Kennung im Betreff',certain=True))
        elif p['name'].casefold() in title.casefold():
            matches.append(dict(p,reason='Projektname im Betreff',certain=False))
    previous=rows("SELECT e.sender,e.title,p.* FROM entries e JOIN entry_projects ep ON ep.entry_id=e.id JOIN projects p ON p.id=ep.project_id WHERE p.status='active' AND e.type IN ('mail_in','mail_out') ORDER BY e.date DESC LIMIT 1000")
    seen={p['id'] for p in matches}
    for p in previous:
        same_subject=bool(subject_base(title)) and subject_base(p['title'])==subject_base(title)
        same_sender=bool(addresses(sender) & addresses(p['sender']))
        if p['id'] not in seen and (same_subject or same_sender):
            matches.append(dict(p,reason='Früherer Betreff' if same_subject else 'Frühere Absenderzuordnung',certain=False)); seen.add(p['id'])
    return matches[:5]


def import_message(raw,own_addresses,enforce_sender=True):
    own={a.lower() for a in own_addresses}
    outer=BytesParser(policy=policy.default).parsebytes(raw)
    if enforce_sender and (not own or not addresses(str(outer.get('From',''))) <= own or not addresses(str(outer.get('From','')))):
        return 'rejected'
    original=outer
    for part in outer.walk():
        if part.get_content_type()=='message/rfc822':
            payload=part.get_payload()
            if isinstance(payload,list) and payload:
                original=payload[0]
                break
    digest=hashlib.sha256(original.as_bytes() if original is not outer else raw).hexdigest()
    message_id=str(original.get('Message-ID','')).strip()
    identity='mail:'+hashlib.sha256(message_id.encode()).hexdigest() if message_id else 'mail:'+digest
    db=get_db()
    db.execute('BEGIN IMMEDIATE')
    if one('SELECT source_key FROM imports WHERE source_key=?',(identity,)):
        db.rollback(); return 'duplicate'
    body=body_text(original)
    sender=str(original.get('From',''))
    recipients=', '.join(str(original.get(header,'')) for header in ('To','Cc','Bcc') if original.get(header))
    title=str(original.get('Subject','')) or '(Ohne Betreff)'
    dt=mail_date(str(original.get('Date','')))
    uncertain=dt is None
    forward=parse_forward(body,allow_header_only=bool(re.match(r'^(?:fwd?|wg):',title,re.I))) if original is outer else None
    if forward:
        if forward['uncertain']:
            # Keep the envelope for traceability but leave original fields for review.
            body=f"Archivweiterleitung von {sender}\n\n{body}"
            sender=''; recipients=''; uncertain=True
        else:
            sender=forward['sender']; recipients=forward.get('recipients','')
            title=forward['title']; dt=forward['datetime']; body=forward['body']
    dt=dt or now()
    kind='mail_out' if addresses(sender) & own and not (forward and forward['uncertain']) else 'mail_in'
    suggestions=suggest_projects(title,sender)
    projects=[p['id'] for p in suggestions if p['certain']]
    tags=', '.join(re.findall(r'\[([^\]]+)\]',title))
    from .participants import mail_participants
    participants=mail_participants(sender,recipients,exclude=own)
    eid=save_entry(dict(date=dt.date().isoformat(),time=dt.strftime('%H:%M'),type=kind,title=title,body=body,sender=sender,recipients=recipients,participant_items=participants,tags=tags,source_key=identity,needs_review=uncertain),projects)
    try:
        for part in original.walk():
            if part.get_content_maintype()=='multipart': continue
            if part.get_filename() and part.get_content_type()!='message/rfc822':
                save_attachment(eid,part.get_filename(),part.get_payload(decode=True) or b'',part.get_content_type())
        save_attachment(eid,'Original.eml',raw,'message/rfc822')
        db.execute('INSERT INTO imports(source_key) VALUES(?)',(identity,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return 'imported'


def sync_imap():
    config=setting('imap',{})
    if not config.get('host'): return 'IMAP nicht eingerichtet'
    counts={'imported':0,'duplicate':0,'rejected':0}
    with imaplib.IMAP4_SSL(config['host'],993,timeout=20) as box:
        box.login(config['username'],config['password'])
        status,_=box.select(config.get('folder','INBOX'),readonly=True)
        if status!='OK': raise ValueError('Archivordner nicht erreichbar.')
        valid=box.response('UIDVALIDITY')[1]
        validity=(valid[0] or b'unknown').decode() if valid else 'unknown'
        mailbox=hashlib.sha256((config['host']+config['username']+config.get('folder','INBOX')+validity).encode()).hexdigest()
        cursor=setting('imap_cursor_'+mailbox,0)
        status,data=box.uid('search',None,'UID',f'{cursor+1}:*')
        if status!='OK': raise ValueError('IMAP-Suche fehlgeschlagen.')
        uids=sorted(int(x) for x in data[0].split() if int(x)>cursor)
        for uid in uids[:200]:
            status,size_data=box.uid('fetch',str(uid),'(RFC822.SIZE)')
            info=b' '.join(x for x in size_data if isinstance(x,bytes))
            size=re.search(rb'RFC822.SIZE (\d+)',info)
            if status!='OK' or not size: raise ValueError('Mailgröße konnte nicht gelesen werden.')
            if int(size[1])>25*1024*1024:
                raise ValueError('Eine Mail überschreitet 25 MB. Bitte das Archivpostfach prüfen.')
            status,data=box.uid('fetch',str(uid),'(BODY.PEEK[])')
            if status!='OK': raise ValueError('Mail konnte nicht gelesen werden.')
            raw=next((v[1] for v in data if isinstance(v,tuple)),None)
            if raw is None: raise ValueError('Leere IMAP-Antwort.')
            counts[import_message(raw,config['own_addresses'])]+=1
            set_setting('imap_cursor_'+mailbox,uid); get_db().commit()
    return f"{counts['imported']} neue Mails · {counts['duplicate']} bereits vorhanden · {counts['rejected']} herausgefiltert"


def cache_file(day):
    return Path(current_app.instance_path)/'cache'/f'{day.isoformat()}.enc'


def cached_events(day):
    path=cache_file(day)
    if not path.exists():
        return [],'Noch keine Kalenderdaten geladen' if setting('caldav',{}).get('url') else 'Nextcloud noch nicht verbunden'
    try:
        data=json.loads(cipher().decrypt(path.read_bytes()))
        stamp=datetime.fromisoformat(data['updated'])
        stale=(now()-stamp).total_seconds()>1800
        events=[]
        for event in data['events']:
            if event.get('id'):
                linked=one('SELECT * FROM calendar_events WHERE id=?',(event['id'],))
                if not linked or linked['state']!='active':continue
                begin=datetime.combine(day,time.min,TZ)
                if datetime.fromisoformat(linked['start_at'])>=begin+timedelta(days=1) or datetime.fromisoformat(linked['end_at'])<=begin:continue
                event.update({k:linked[k] for k in ('title','calendar','location','time','all_day','color')})
                event['end']='' if linked['all_day'] else datetime.fromisoformat(linked['end_at']).strftime('%H:%M')
            events.append(event)
        return events,('Zwischengespeichert · ' if stale else 'Aktualisiert · ')+stamp.strftime('%d.%m. %H:%M')
    except (ValueError,KeyError):
        return [],'Kalendercache nicht lesbar – bitte synchronisieren'


def sync_calendar(start=None,days=30):
    import caldav
    import recurring_ical_events
    config=setting('caldav',{})
    if not config.get('url'): return 'CalDAV nicht eingerichtet'
    start=start or now().date()-timedelta(days=7)
    buckets={(start+timedelta(days=i)).isoformat():[] for i in range(days)}
    begin=datetime.combine(start,time.min,TZ)
    end=begin+timedelta(days=days)
    durable=[]
    from .meetings import store_events, occurrence_key, event_key
    with caldav.DAVClient(url=config['url'],username=config['username'],password=config['password'],timeout=20) as client:
        calendars=client.principal().calendars()
        selected=config.get('calendars',[])
        found=set()
        for index,cal in enumerate(calendars):
            name=cal.name or 'Kalender'
            if selected and name not in selected: continue
            found.add(name)
            for event in cal.search(start=begin,end=end,event=True,expand=False):
                calendar=event.icalendar_instance
                components=calendar.walk('VEVENT')
                # Expand only true series: generic expansion invents recurrence IDs
                # for single events, which would break links when they move.
                if any(c.get('RRULE') or c.get('RDATE') or c.get('RECURRENCE-ID') for c in components):
                    components=recurring_ical_events.of(calendar).between(begin,end)
                for component in components:
                    if str(component.get('STATUS','')).upper()=='CANCELLED': continue
                    value=component.get('DTSTART')
                    if value is None: continue
                    event_start=value.dt
                    all_day=not isinstance(event_start,datetime)
                    if all_day:
                        event_start=datetime.combine(event_start,time.min,TZ)
                    elif event_start.tzinfo is None: event_start=event_start.replace(tzinfo=TZ)
                    else: event_start=event_start.astimezone(TZ)
                    finish=component.get('DTEND')
                    event_end=finish.dt if finish else event_start+(component.get('DURATION').dt if component.get('DURATION') else timedelta(days=1) if all_day else timedelta(minutes=1))
                    if not isinstance(event_end,datetime): event_end=datetime.combine(event_end,time.min,TZ)
                    elif event_end.tzinfo is None: event_end=event_end.replace(tzinfo=TZ)
                    else: event_end=event_end.astimezone(TZ)
                    if event_start>=end or event_end<=begin:continue
                    uid=str(component.get('UID',''))
                    if not uid:continue
                    calendar_key=str(getattr(cal,'url','') or config['url'].rstrip('/')+'/'+name)
                    rid=component.get('RECURRENCE-ID')
                    occurrence=occurrence_key(rid.dt if rid else event_start if component.get('RRULE') else None)
                    stable_key=event_key(calendar_key,uid,occurrence)
                    durable.append(dict(calendar_key=calendar_key,uid=uid,occurrence=occurrence,title=str(component.get('SUMMARY','Ohne Titel')),calendar=name,location=str(component.get('LOCATION','')),start_at=event_start.isoformat(),end_at=event_end.isoformat(),date=event_start.date().isoformat(),time='' if all_day else event_start.strftime('%H:%M'),all_day=int(all_day),color=index%5))
                    for key,bucket in buckets.items():
                        day_begin=datetime.combine(date.fromisoformat(key),time.min,TZ)
                        if event_start < day_begin+timedelta(days=1) and event_end > day_begin:
                            bucket.append(dict(event_key=stable_key,title=str(component.get('SUMMARY','Ohne Titel')),date=key,time='' if all_day else event_start.strftime('%H:%M'),end='' if all_day else event_end.strftime('%H:%M'),all_day=all_day,calendar=name,color=index%5,location=str(component.get('LOCATION','')),uid=str(component.get('UID',''))))
        if selected and set(selected)-found: raise ValueError('Mindestens ein konfigurierter Kalender wurde nicht gefunden.')
    ids=store_events(durable,begin.isoformat(),end.isoformat())
    for key,events in buckets.items():
        for event in events:event['id']=ids[event.pop('event_key')]

        unique={e['id']:e for e in events}
        atomic_write(cache_file(date.fromisoformat(key)),cipher().encrypt(json.dumps(dict(updated=now().isoformat(),events=sorted(unique.values(),key=lambda e:e['time']))).encode()))
    for old in (Path(current_app.instance_path)/'cache').glob('*.enc'):
        if old.stem < (now().date()-timedelta(days=60)).isoformat(): old.unlink()
    return f'{len(found)} Kalender aktualisiert'


def sync_all(calendar_day=None):
    report=[]
    statuses={}
    for name,fn in [('imap',sync_imap),('caldav',lambda: sync_calendar(calendar_day,1) if calendar_day else sync_calendar())]:
        try:
            message=fn()
            statuses[name]=dict(ok=True,message=message,at=now().isoformat())
        except Exception as exc:
            get_db().rollback()
            # Never expose credentials, remote message bodies or URL tokens in logs/UI.
            message=f'{name.upper()}: Verbindung fehlgeschlagen ({type(exc).__name__}). Zugangsdaten und Erreichbarkeit prüfen.'
            statuses[name]=dict(ok=False,message=message,at=now().isoformat())
        report.append(message)
    set_setting('sync_status',statuses); get_db().commit()
    return ' · '.join(report)
