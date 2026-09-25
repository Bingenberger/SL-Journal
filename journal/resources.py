"""Search existing resources for inline Markdown links."""
from flask import url_for
from .db import get_db, rows
from .participants import normalized


def search(query, *, fulltext=False, limit=20, offset=0):
    from .domain import TYPES
    query=query.strip()[:200]
    words=normalized(query).split()
    if fulltext and not words:
        return dict(items=[],more=False,total=0)
    groups=[[],[],[],[],[],[],[]]
    # Candidates keep only their label and how to build the link. The address is
    # assembled after paging, so a keystroke never builds thousands of URLs.
    def add(group,label,kind,endpoint,values,detail='',search_text='',matched=False):
        if not matched and words:
            haystack=normalized(' '.join([label,kind,detail,search_text]))
            if not all(word in haystack for word in words):
                return
        groups[group].append((label,kind,detail,endpoint,values))
    for p in rows('SELECT * FROM people ORDER BY name,id'):
        add(0,p['name'],'Kontakt','person_view',dict(pid=p['id']),' · '.join(v for v in [p['role'],p['institution']] if v),p['emails']+' '+p['phone'])
    for p in rows('SELECT * FROM projects ORDER BY status,name,id'):
        add(1,p['name'],'Projekt','project_view',dict(pid=p['id']),p['school_year']+(' · abgeschlossen' if p['status']=='closed' else ''),p['description'] if fulltext else '')
    entry_matches=set()
    if fulltext:
        fts_query=' AND '.join('"'+word.replace('"','""')+'"*' for word in query.split())
        entry_matches={e['rowid'] for e in rows('SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?', (fts_query,))}
    seen=set()
    # The entry table is the largest one, so it is read as tuples and tested inline.
    # Type name, date and tags repeat across thousands of rows: normalising them once
    # per distinct value keeps the scan close to the cost of reading the rows.
    entry_group=groups[2]
    rest_cache={}
    tag_cache={}
    # Read in storage order: sorting the whole table by date costs more than the scan
    # itself. Only the matches are put into date order afterwards.
    for eid,title,day,kind,tags in get_db().execute('SELECT id,title,date,type,tags FROM entries ORDER BY id DESC'):
        label=TYPES[kind]
        if (fulltext and eid in entry_matches) or not words:
            entry_group.append((title,label,day,'entry_view',dict(eid=eid)))
        else:
            key=(label,day,kind)
            rest=rest_cache.get(key)
            if rest is None:
                rest=rest_cache[key]=normalized(' '.join([label,day,'Sitzungsprotokoll Protokoll' if kind in ('meeting','protocol') else '']))
            # A search word never contains a space, so it always lies inside one part.
            title_key=normalized(title)
            if all(word in title_key or word in rest for word in words):
                entry_group.append((title,label,day,'entry_view',dict(eid=eid)))
        if not tags: continue
        for tag in tags.split(','):
            tag=tag.strip()
            key=tag_cache.get(tag)
            if key is None:
                key=tag_cache[tag]=normalized(tag)
            if key and key not in seen:
                seen.add(key)
                add(3,'#'+tag,'Tag','entry_list',dict(tag=tag))
    entry_group.sort(key=lambda item:(item[2],item[4]['eid']),reverse=True)
    for tid,text,done,due in get_db().execute('SELECT id,text,done,due FROM tasks ORDER BY done,due IS NULL,due,id'):
        add(4,text,'Aufgabe','task_list',dict(filter='all',focus_task=tid,_anchor='task-'+str(tid)),'erledigt' if done else (due or 'offen'))
    from .cases import STATUSES
    for case in rows('SELECT * FROM cases ORDER BY status,title,id'):
        add(6,case['title'],'Vorgang','case_view',dict(cid=case['id']),STATUSES[case['status']],case['description'])
    for document in rows('SELECT * FROM documents ORDER BY name,id'):
        add(5,document['name'],'Nextcloud-Dokument','document_view',dict(did=document['id']),document['description'],'Datei Ordner '+document['url'])
    prefix=normalized(query).lstrip('#')
    for group in groups:
        group.sort(key=lambda item: not normalized(item[0]).lstrip('#').startswith(prefix))
    result=[]
    for index in range(max(map(len,groups),default=0)):
        for group in groups:
            if index<len(group): result.append(group[index])
    page=[dict(label=label,kind=kind,url=url_for(endpoint,**values),detail=detail)
          for label,kind,detail,endpoint,values in result[offset:offset+limit]]
    return dict(items=page,more=len(result)>offset+limit,total=len(result))
