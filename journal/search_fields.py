"""Suggestions for filtered lists and reusable contact field values."""
from datetime import timedelta
from email.utils import getaddresses
from flask import abort, url_for
from .db import rows
from .participants import normalized
from .domain import TYPES, UNPROCESSED_MAIL, now


def contact_values(field, query):
    if field not in ('name','role','institution','emails','phone'):
        abort(404)
    words=normalized(query)[:200].split()
    values={}
    for person in rows('SELECT * FROM people ORDER BY name,id'):
        candidates=[person[field]]
        if field=='emails':
            candidates=[address for _,address in getaddresses([person[field]]) if address]
        for value in candidates:
            key=normalized(value)
            if key and key not in values and all(word in key for word in words):
                values[key]=dict(label=value,kind='Vorhandene Angabe',detail=person['name'] if field in ('emails','phone') else '')
    items=sorted(values.values(),key=lambda item:(not normalized(item['label']).startswith(normalized(query)),normalized(item['label'])))
    return dict(items=items[:12],total=len(items),more=len(items)>12)


def suggestions(scope,args):
    query=args.get('q','').strip()[:200]
    words=normalized(query).split()
    if not words:
        return dict(items=[],total=0,more=False)
    items=[]
    def add(row,label,kind,url,fields,detail=''):
        if all(word in normalized(' '.join(row[field] or '' for field in fields)) for word in words):
            items.append(dict(label=row[label],kind=kind,url=url,detail=detail))
    if scope=='people':
        institution=normalized(args.get('institution',''))
        for p in rows('SELECT * FROM people ORDER BY name,id'):
            if institution and institution!=normalized(p['institution']):continue
            add(p,'name','Kontakt',url_for('person_view',pid=p['id']),('name','role','institution','emails','phone'),' · '.join(v for v in (p['role'],p['institution']) if v))
    elif scope=='projects':
        status='closed' if args.get('status')=='closed' else 'active'
        for p in rows('SELECT * FROM projects WHERE status=? ORDER BY name,id',(status,)):
            add(p,'name','Projekt',url_for('project_view',pid=p['id']),('name','description'),p['school_year'])
    elif scope=='cases':
        from .cases import STATUSES
        mode=args.get('status','active')
        for c in rows('SELECT * FROM cases ORDER BY follow_up IS NULL,follow_up,title,id'):
            if not (mode=='all' or mode=='active' and c['status']!='done' or c['status']==mode):continue
            add(c,'title','Vorgang',url_for('case_view',cid=c['id']),('title','description'),STATUSES[c['status']])
    elif scope=='tasks':
        mode=args.get('filter','open')
        where={'open':'done=0','undated':'done=0 AND due IS NULL','done':'done=1','all':'1=1'}.get(mode,'done=0')
        today=now().date()
        for t in rows('SELECT * FROM tasks WHERE '+where+' ORDER BY done,due IS NULL,due,id'):
            if any(args.get(key,type=int) and t[key]!=args.get(key,type=int) for key in ('project_id','case_id')):continue
            due=args.get('due','')
            if due=='overdue' and not (t['due'] and t['due']<today.isoformat()):continue
            if due=='today' and t['due']!=today.isoformat():continue
            if due=='week' and not (t['due'] and today.isoformat()<=t['due']<=(today+timedelta(days=7)).isoformat()):continue
            if due=='undated' and t['due']:continue
            add(t,'text','Aufgabe',url_for('task_list',filter='all',focus_task=t['id'],_anchor='task-'+str(t['id'])),('text',),t['due'] or '')
    elif scope=='entries':
        clauses=['e.id IN (SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?)']
        params=[' AND '.join('"'+word.replace('"','""')+'"*' for word in query.split())]
        if args.get('inbox'):clauses.append(UNPROCESSED_MAIL)
        if args.get('type') in TYPES:clauses.append('e.type=?');params.append(args['type'])
        if args.get('tag'):clauses.append('has_tag(e.tags,?)');params.append(args['tag'])
        for e in rows('SELECT e.id,e.title,e.date,e.type FROM entries e WHERE '+' AND '.join(clauses)+' ORDER BY date DESC,time DESC,id DESC',params):
            items.append(dict(label=e['title'],kind=TYPES[e['type']],url=url_for('entry_view',eid=e['id']),detail=e['date']))
    elif scope=='appointments':
        from .meetings import listing
        from .domain import valid_date
        start=valid_date(args.get('from',now().date().isoformat()))
        items=[dict(label=e['title'],kind='Termin',url=url_for('appointment_view',aid=e['id']),detail=e['date']+' '+e['time']+' · '+e['calendar']) for e in listing(query,start,include_prepared=True)]
    elif scope=='tags':
        from .tags import overview
        items=[dict(label=t['name'],kind='Tag',url=url_for('entry_list',tag=t['name']),detail=str(t['count'])+' Einträge') for t in overview(query)]
    else:
        abort(404)
    return dict(items=items[:10],total=len(items),more=len(items)>10)
