"""Search existing resources for inline Markdown links."""
from flask import url_for
from .db import get_db, rows
from .participants import normalized


def search(query, *, fulltext=False, limit=20, offset=0, kind=''):
    from .domain import TYPES
    query=query.strip()[:200]
    words=normalized(query).split()
    if fulltext and not words:
        return dict(items=[],more=False,total=0)
    groups=[[],[],[],[],[],[],[],[]]
    attachment_details={}
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
    # Nicht „kind“ nennen: Das ist der Filterparameter dieser Funktion.
    for eid,title,day,typ,tags in get_db().execute('SELECT id,title,date,type,tags FROM entries ORDER BY id DESC'):
        label=TYPES[typ]
        if (fulltext and eid in entry_matches) or not words:
            entry_group.append((title,label,day,'entry_view',dict(eid=eid)))
        else:
            key=(label,day,typ)
            rest=rest_cache.get(key)
            if rest is None:
                rest=rest_cache[key]=normalized(' '.join([label,day,'Sitzungsprotokoll Protokoll' if typ in ('meeting','protocol') else '']))
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
    if fulltext:
        from .attachment_search import matches
        for hit in matches(query):
            aid=hit['id']
            if aid in attachment_details:
                continue
            pdf=hit['mime']=='application/pdf' or hit['name'].lower().endswith('.pdf')
            detail=hit['title'] + (f" · Seite {hit['page']}" if pdf else '')
            add(7,hit['name'],'Anhang','entry_view',dict(eid=hit['entry_id'],_anchor='attachment-'+str(aid)),detail,matched=True)
            attachment_details[aid]=dict(excerpt=hit['excerpt'],file_url=url_for('attachment_inline' if pdf else 'attachment',aid=aid,**({'_anchor':'page='+str(hit['page'])} if pdf else {})))
    prefix=normalized(query).lstrip('#')
    for group in groups:
        group.sort(key=lambda item: not normalized(item[0]).lstrip('#').startswith(prefix))
    result=[]
    for index in range(max(map(len,groups),default=0)):
        for group in groups:
            if index<len(group): result.append(group[index])
    # Die Plakette am Treffer nennt bereits die Art – Protokoll, Aufgabe, Anhang.
    # Genau danach wird gefiltert, mit den Zahlen des ungefilterten Bestands.
    bestand={}
    for eintrag in result:
        bestand[eintrag[1]]=bestand.get(eintrag[1],0)+1
    reihenfolge=list(TYPES.values())+['Aufgabe','Vorgang','Projekt','Kontakt','Tag','Nextcloud-Dokument','Anhang']
    arten=[dict(name=name,count=bestand[name])
           for name in sorted(bestand,key=lambda name:(reihenfolge.index(name) if name in reihenfolge else len(reihenfolge),name))]
    gesamt=len(result)
    if kind:
        result=[eintrag for eintrag in result if eintrag[1]==kind]
    page=[dict(label=label,kind=kind,url=url_for(endpoint,**values),detail=detail)
          for label,kind,detail,endpoint,values in result[offset:offset+limit]]
    for item in page:
        if item['kind']=='Anhang':
            aid=int(item['url'].rsplit('attachment-',1)[1])
            item.update(attachment_details[aid])
    return dict(items=page,more=len(result)>offset+limit,total=len(result),kinds=arten,all_total=gesamt)
