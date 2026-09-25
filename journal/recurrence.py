"""Calendar-based task series with idempotent occurrence generation."""
import calendar
import json
import re
from datetime import date, timedelta
from .db import get_db, one, rows
from .domain import MONTHS, now, valid_date

FREQUENCIES={'weekly':'Wöchentlich','monthly':'Monatlich','quarterly':'Quartalsweise','dates':'Einzelne Termine'}
TOKENS={'KW','KW_JAHR','MONAT','MONATSNAME','QUARTAL','JAHR','DATUM'}


def title(template, due, strict=True):
    day=date.fromisoformat(due) if isinstance(due,str) else due
    iso=day.isocalendar()
    values=dict(KW=f'{iso.week:02}',KW_JAHR=str(iso.year),MONAT=f'{day.month:02}',MONATSNAME=MONTHS[day.month-1],QUARTAL=str((day.month-1)//3+1),JAHR=str(day.year),DATUM=day.strftime('%d.%m.%Y'))
    if strict:
        rest=re.sub(r'\{('+'|'.join(TOKENS)+r')\}','',template)
        if '{' in rest or '}' in rest:
            raise ValueError('Unbekannter Platzhalter. Möglich sind {KW}, {KW_JAHR}, {MONAT}, {MONATSNAME}, {QUARTAL}, {JAHR} und {DATUM}.')
    return re.sub(r'\{([A-Z_]+)\}',lambda m:values.get(m[1],m[0]),template)


def parse(data):
    frequency=data.get('repeat_frequency','')
    if frequency not in FREQUENCIES: raise ValueError('Bitte eine gültige Wiederholung auswählen.')
    template=data.get('text','').strip()
    if not template or len(template)>2000: raise ValueError('Bitte einen Aufgabentitel mit höchstens 2000 Zeichen angeben.')
    try: interval=int(data.get('repeat_interval') or 1)
    except (ValueError,TypeError): raise ValueError('Das Wiederholungsintervall muss eine ganze Zahl sein.')
    if not 1<=interval<=52: raise ValueError('Das Wiederholungsintervall muss zwischen 1 und 52 liegen.')
    if frequency in ('quarterly','dates'): interval=1
    dates=[]
    if frequency=='dates':
        raw=data.get('repeat_dates','')
        if not isinstance(raw,str): raise ValueError('Bitte gültige Termine eingeben.')
        values=re.split(r'[\s,;]+',raw.strip())
        if not raw.strip() or len(values)>365: raise ValueError('Bitte zwischen 1 und 365 Termine angeben.')
        dates=sorted(set(valid_date(value) for value in values))
        start=dates[0]
    else:
        if not data.get('due'): raise ValueError('Für eine wiederkehrende Aufgabe fehlt der erste Fälligkeitstermin.')
        start=valid_date(data['due'])
    until=valid_date(data.get('repeat_until'),optional=True)
    if until and until<start: raise ValueError('Das Serienende darf nicht vor dem ersten Termin liegen.')
    title(template,start)
    return dict(template=template,frequency=frequency,interval=interval,start_date=start,until_date=until,dates=json.dumps(dates))


def next_on_or_after(series, lower):
    start=date.fromisoformat(series['start_date'])
    lower=max(start,lower)
    frequency=series['frequency']
    if frequency=='dates':
        result=next((date.fromisoformat(value) for value in json.loads(series['dates']) if value>=lower.isoformat()),None)
    elif frequency=='weekly':
        step=7*series['interval'];distance=(lower-start).days
        try: result=start+timedelta(days=((distance+step-1)//step)*step)
        except OverflowError: result=None
    else:
        step=(3 if frequency=='quarterly' else 1)*series['interval']
        distance=(lower.year-start.year)*12+lower.month-start.month
        index=max(0,distance//step)
        result=None
        for _ in range(2):
            month=start.year*12+start.month-1+index*step
            year,month0=divmod(month,12)
            if year>9999: break
            candidate=date(year,month0+1,min(start.day,calendar.monthrange(year,month0+1)[1]))
            if candidate>=lower:
                result=candidate;break
            index+=1
    if result and series['until_date'] and result.isoformat()>series['until_date']: return None
    return result


def following(series, due):
    day=date.fromisoformat(due)
    return next_on_or_after(series,day+timedelta(days=1)) if day<date.max else None


def for_task(tid):
    return one('SELECT s.*,o.due occurrence_date FROM task_series s JOIN task_occurrences o ON o.series_id=s.id WHERE o.task_id=?',(tid,))


def create(tid, config):
    task=one('SELECT * FROM tasks WHERE id=?',(tid,))
    if not task or task['parent_id'] or task['done'] or for_task(tid):
        raise ValueError('Eine Serie kann nur aus einer offenen Hauptaufgabe ohne bestehende Serie entstehen.')
    db=get_db()
    cursor=following(config,config['start_date'])
    sid=db.execute('''INSERT INTO task_series(template,frequency,interval,start_date,until_date,dates,next_due,source_task_id)
        VALUES(?,?,?,?,?,?,?,?)''',(config['template'],config['frequency'],config['interval'],config['start_date'],config['until_date'],config['dates'],cursor.isoformat() if cursor else None,tid)).lastrowid
    db.execute('UPDATE tasks SET text=?,due=? WHERE id=?',(title(config['template'],config['start_date']),config['start_date'],tid))
    db.execute('INSERT INTO task_occurrences(series_id,due,task_id) VALUES(?,?,?)',(sid,config['start_date'],tid))
    # Store child title templates separately, because the visible task contains expanded text.
    for child in rows('SELECT id,text FROM tasks WHERE parent_id=?',(tid,)):
        db.execute('INSERT INTO task_series_children(series_id,source_task_id,template) VALUES(?,?,?)',(sid,child['id'],child['text']))
        db.execute('UPDATE tasks SET text=? WHERE id=?',(title(child['text'],config['start_date'],strict=False),child['id']))
    return sid


def generate(today=None):
    """Generate all missed occurrences and 14 days ahead; never require completion."""
    from .domain import save_task
    from .project_suggestions import items as projects
    from .case_suggestions import items as cases
    today=today or now().date()
    horizon=min(date.max,today+timedelta(days=min(14,(date.max-today).days)))
    db=get_db()
    if not one('SELECT id FROM task_series WHERE active=1 AND next_due<=? LIMIT 1',(horizon.isoformat(),)): return 0
    own=not db.in_transaction
    if own: db.execute('BEGIN IMMEDIATE')
    count=0
    for series in rows('SELECT * FROM task_series WHERE active=1 AND next_due<=? ORDER BY next_due,id',(horizon.isoformat(),)):
        source=one('SELECT * FROM tasks WHERE id=?',(series['source_task_id'],))
        if not source:
            db.execute('UPDATE task_series SET active=0 WHERE id=?',(series['id'],));continue
        cursor=series['next_due']
        while cursor and cursor<=horizon.isoformat() and count<1000:
            if not one('SELECT 1 FROM task_occurrences WHERE series_id=? AND due=?',(series['id'],cursor)):
                tid=save_task(dict(text=title(series['template'],cursor),due=cursor,entry_id=source['entry_id'],project_items=projects('task',source['id']),case_items=cases('task',source['id'])))
                db.execute('INSERT INTO task_occurrences(series_id,due,task_id) VALUES(?,?,?)',(series['id'],cursor,tid))
                for child in rows('SELECT * FROM tasks WHERE parent_id=? ORDER BY id',(source['id'],)):
                    stored=one('SELECT template FROM task_series_children WHERE series_id=? AND source_task_id=?',(series['id'],child['id']))
                    text=stored['template'] if stored else child['text']
                    due=None
                    if child['due'] and source['due']:
                        offset=date.fromisoformat(child['due'])-date.fromisoformat(source['due'])
                        try: due=(date.fromisoformat(cursor)+offset).isoformat()
                        except OverflowError: due=None
                    save_task(dict(text=title(text,cursor,strict=False),due=due,parent_id=tid,project_items=projects('task',child['id']),case_items=cases('task',child['id'])))
                count+=1
            next_date=following(series,cursor)
            cursor=next_date.isoformat() if next_date else None
        db.execute('UPDATE task_series SET next_due=? WHERE id=?',(cursor,series['id']))
    if own: db.commit()
    return count


def update(sid,data):
    series=one('SELECT * FROM task_series WHERE id=?',(sid,))
    if not series: raise ValueError('Diese Aufgabenserie existiert nicht.')
    config=parse(data)
    # Existing tasks, including manually edited occurrences, remain unchanged.
    latest=one('SELECT max(due) due FROM task_occurrences WHERE series_id=?',(sid,))['due']
    lower=max(now().date(),date.fromisoformat(latest)+timedelta(days=1)) if latest and latest<'9999-12-31' else date.max if latest else now().date()
    cursor=next_on_or_after(config,lower)
    get_db().execute('''UPDATE task_series SET template=?,frequency=?,interval=?,start_date=?,until_date=?,dates=?,next_due=? WHERE id=?''',(config['template'],config['frequency'],config['interval'],config['start_date'],config['until_date'],config['dates'],cursor.isoformat() if cursor else None,sid))


def set_active(sid,active):
    series=one('SELECT * FROM task_series WHERE id=?',(sid,))
    if not series: raise ValueError('Diese Aufgabenserie existiert nicht.')
    cursor=series['next_due']
    if active and cursor:
        resumed=next_on_or_after(series,max(now().date(),date.fromisoformat(cursor)))
        cursor=resumed.isoformat() if resumed else None
    get_db().execute('UPDATE task_series SET active=?,next_due=? WHERE id=?',(int(active),cursor,sid))
