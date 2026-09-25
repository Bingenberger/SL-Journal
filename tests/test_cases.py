import json
from pathlib import Path
from cryptography.fernet import Fernet
from journal.app import create_app
from journal.db import SCHEMA,connect,get_db,one,init_db
from journal.domain import save_entry,save_task,UNPROCESSED_MAIL


def make_case(post,title='Elternbeschwerde Mittagessen',follow_up='2026-09-23'):
    response=post('/case/save',dict(title=title,description='Anlass festhalten',status='open',follow_up=follow_up))
    assert response.status_code==200
    return int(response.json['redirect'].rsplit('/',1)[1])


def test_case_lifecycle_reminder_and_independent_projects(app,client,post):
    cid=make_case(post)
    assert client.get('/cases',base_url='https://localhost').status_code==200
    assert b'Elternbeschwerde Mittagessen' in client.get('/?date=2026-09-23',base_url='https://localhost').data
    for status in ['clarifying','done','open']:
        assert post(f'/case/{cid}/status',dict(status=status,follow_up='2026-09-22',description='Nicht ersetzen')).status_code==200
        with app.app_context():
            row=one('SELECT * FROM cases WHERE id=?',(cid,))
            assert row['status']==status and row['description']=='Anlass festhalten'
            assert one('SELECT COUNT(*) n FROM projects')['n']==0
        cockpit=client.get('/?date=2026-09-23',base_url='https://localhost').text
        assert ('class="panel case-reminders"' in cockpit)==(status!='done')
    assert post(f'/case/{cid}/status',dict(status='bad')).status_code==400
    assert post('/case/save',dict(title=' ',status='open')).status_code==400
    assert post('/case/save',dict(title='Test',follow_up='2026-02-30')).status_code==400
    assert client.post('/case/save',data={'title':'Ohne CSRF'},base_url='https://localhost').status_code==400
    assert app.test_client().get('/cases',base_url='https://localhost').status_code==302
    assert post(f'/case/{cid}/status',dict(status='open',follow_up='')).status_code==200
    with app.app_context():
        assert one('SELECT follow_up FROM cases WHERE id=?',(cid,))['follow_up'] is None


def test_entry_task_subtask_inheritance_and_inbox(app,client,post):
    cid=make_case(post)
    with app.app_context():
        pid=get_db().execute("INSERT INTO projects(name,school_year) VALUES('Projekt','2026/27')").lastrowid
        eid=save_entry(dict(type='mail_in',title='Anfrage',date='2026-09-23',body='Original'))
        get_db().commit()
        assert one('SELECT id FROM entries e WHERE '+UNPROCESSED_MAIL)
    assert post(f'/entry/{eid}/assign',dict(case_id=cid)).status_code==200
    with app.app_context():
        assert not one('SELECT id FROM entries e WHERE '+UNPROCESSED_MAIL)
        tid=save_task(dict(text='Nachfragen',entry_id=eid,project_id=pid))
        sid=save_task(dict(text='Rückmeldung',parent_id=tid))
        get_db().commit()
        assert one('SELECT case_id,project_id FROM tasks WHERE id=?',(tid,))==dict(case_id=cid,project_id=pid)
        assert one('SELECT case_id FROM tasks WHERE id=?',(sid,))['case_id']==cid
        save_task(dict(text='Nachfragen geändert',entry_id=eid,case_id=''),tid)
        get_db().commit()
        assert one('SELECT case_id FROM tasks WHERE id=?',(tid,))['case_id'] is None
    page=client.get(f'/case/{cid}',base_url='https://localhost').text
    assert 'Anfrage' in page and 'Rückmeldung' in page
    assert post(f'/case/{cid}/entry/{eid}/remove').status_code==200
    with app.app_context():
        assert one('SELECT body FROM entries WHERE id=?',(eid,))['body']=='Original'
        assert one('SELECT id FROM entries e WHERE '+UNPROCESSED_MAIL)
        assert one('SELECT case_id FROM tasks WHERE id=?',(sid,))['case_id']==cid


def test_multi_case_entry_updates_resources_and_validation(app,client,post):
    first=make_case(post,'Anfrage')
    second=make_case(post,'Beschwerde')
    data=dict(type='protocol',title='Gespräch',date='2026-09-23',case_ids=json.dumps([first,second]))
    assert post('/entry/save',data).status_code==200
    with app.app_context():
        eid=one("SELECT id FROM entries WHERE title='Gespräch'")['id']
        assert one('SELECT COUNT(*) n FROM entry_cases WHERE entry_id=?',(eid,))['n']==2
    assert post(f'/entry/{eid}/classification',dict(case_ids=json.dumps([second]),tags='Besprechung',project_items='[]')).status_code==200
    assert post(f'/entry/{eid}/classification',dict(case_ids='[99999]',tags='Fehler',project_items='[]')).status_code==400
    with app.app_context():
        assert one('SELECT case_id FROM entry_cases WHERE entry_id=?',(eid,))['case_id']==second
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']=='Besprechung'
    assert post(f'/entry/{eid}/link',dict(resource_url=f'/case/{first}')).status_code==200
    assert 'Gespräch' in client.get(f'/case/{first}',base_url='https://localhost').text
    resources=client.get('/api/resources?q=Anfrage',base_url='https://localhost').json
    assert any(item['kind']=='Vorgang' and item['url']==f'/case/{first}' for item in resources['items'])
    assert client.get('/api/autocomplete/cases?q=Beschwerde',base_url='https://localhost').json['items'][0]['id']==second
    assert post(f'/case/{second}/entry',dict(entry_id=eid)).status_code==200
    assert post(f'/case/{second}/entry',dict(entry_id=eid)).status_code==200
    assert post(f'/case/{second}/entry',dict(entry_id=99999)).status_code==400
    assert post('/task/save',dict(text='Ungültig',case_id=99999)).status_code==400


def test_old_database_migrates_without_losing_links_or_tasks(tmp_path):
    instance=tmp_path/'old';instance.mkdir()
    key=Fernet.generate_key();(instance/'master.key').write_bytes(key)
    old=SCHEMA
    start=old.index('CREATE TABLE IF NOT EXISTS cases (');end=old.index('CREATE TABLE IF NOT EXISTS entries (')
    old=old[:start]+old[end:]
    old=old.replace(',\n case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL','')
    old=old.replace(' case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,\n','')
    old=old.replace('+(case_id IS NOT NULL)','').replace(' UNIQUE(owner_entry_id,case_id),','')
    db=connect(instance/'journal.db',key);db.executescript(old)
    db.execute("INSERT INTO entries(id,date,type,title) VALUES(42,'2026-09-23','note','Bestand'),(43,'2026-09-23','protocol','Protokoll')")
    db.execute("INSERT INTO tasks(id,text,entry_id) VALUES(9,'Altaufgabe',42)")
    db.execute("INSERT INTO entry_resource_links(id,owner_entry_id,entry_id) VALUES(19,42,43)")
    db.commit();db.close()
    app=create_app({'INSTANCE_PATH':str(instance),'TESTING':True})
    with app.app_context():
        for _ in range(2):
            init_db()
            assert one('SELECT entry_id FROM tasks WHERE id=9')['entry_id']==42
            assert one('SELECT case_id FROM tasks WHERE id=9')['case_id'] is None
            assert one('SELECT entry_id FROM entry_resource_links WHERE id=19')['entry_id']==43
            assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
        cid=get_db().execute("INSERT INTO cases(title) VALUES('Neuer Vorgang')").lastrowid
        get_db().execute('INSERT INTO entry_resource_links(owner_entry_id,case_id) VALUES(42,?)',(cid,))
        get_db().commit()
        assert one('SELECT COUNT(*) n FROM entry_resource_links')['n']==2


def test_case_suggestions_shared_entries_tasks_and_resolution(app,client,post):
    from journal.case_suggestions import items
    proposal=json.dumps([dict(kind='new_case',label='  Anfrage   Mensa  ')])
    with app.app_context():
        first=save_entry(dict(type='note',title='Erste Notiz',date='2026-09-23',case_items=proposal))
        second=save_entry(dict(type='note',title='Zweite Notiz',date='2026-09-23',case_items=json.dumps([dict(kind='new_case',label='anfrage mensa')])))
        task=save_task(dict(text='Rückfrage',entry_id=first))
        child=save_task(dict(text='Unteraufgabe',parent_id=task))
        get_db().commit()
        sid=one('SELECT id FROM case_suggestions')['id']
        assert one('SELECT count(*) n FROM case_suggestions')['n']==1
        assert items('entry',first)[0]['label']=='Anfrage Mensa'
        assert items('task',child)[0]['kind']=='new_case'
        assert not one('SELECT id FROM cases')
    assert 'Anfrage Mensa' in client.get('/cases',base_url='https://localhost').text
    results=client.get('/api/autocomplete/cases?q=mensa',base_url='https://localhost').json['items']
    assert results[0]['kind']=='new_case'
    assert client.get('/api/autocomplete/cases?q=mensa&existing_only=1',base_url='https://localhost').json['items']==[]
    assert post(f'/case-suggestion/{sid}/status',dict(status='ignored')).status_code==200
    assert post(f'/case-suggestion/{sid}/status',dict(status='pending')).status_code==200
    response=post(f'/case-suggestion/{sid}/resolve')
    assert response.status_code==200
    cid=int(response.json['redirect'].rsplit('/',1)[1])
    with app.app_context():
        assert one('SELECT count(*) n FROM entry_cases WHERE case_id=?',(cid,))['n']==2
        assert one('SELECT count(*) n FROM tasks WHERE case_id=?',(cid,))['n']==2
        assert not one('SELECT * FROM entry_case_suggestions')
        assert not one('SELECT * FROM task_case_suggestions')
        save_entry(dict(type='note',title='Dritte Notiz',date='2026-09-23',case_items=proposal))
        assert one('SELECT count(*) n FROM entry_cases WHERE case_id=?',(cid,))['n']==3
    assert post(f'/case-suggestion/{sid}/resolve').status_code==404


def test_case_suggestion_validation_preservation_removal_and_existing_link(app,client,post):
    payload=json.dumps([dict(kind='new_case',label='Ungeklärter Anlass')])
    with app.app_context():
        eid=save_entry(dict(type='mail_in',title='Mail',date='2026-09-23'))
        get_db().commit()
    assert post(f'/entry/{eid}/assign',dict(case_items=payload)).status_code==200
    with app.app_context():
        sid=one('SELECT id FROM case_suggestions')['id']
    for bad in ['null','{}','[null]',json.dumps([dict(kind='new_case',label=' '*3)]),json.dumps([dict(kind='new_case',label='x'*501)]),'[{"kind":"case","id":99999}]']:
        assert post(f'/entry/{eid}/classification',dict(case_items=bad,tags='Fehler')).status_code==400
    with app.app_context():
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']==''
        save_entry(dict(type='mail_in',title='Mail geändert',date='2026-09-23'),entry_id=eid)
        assert one('SELECT suggestion_id FROM entry_case_suggestions WHERE entry_id=?',(eid,))['suggestion_id']==sid
        get_db().commit()
    assert client.post(f'/case-suggestion/{sid}/resolve',base_url='https://localhost').status_code==400
    assert post(f'/case-suggestion/{sid}/status',dict(status='resolved')).status_code==400
    assert post(f'/case-suggestion/{sid}/resolve',dict(case_id=99999)).status_code==400
    cid=make_case(post,'Bestehender Anlass')
    assert post(f'/case-suggestion/{sid}/resolve',dict(case_id=cid)).status_code==200
    with app.app_context():
        assert one('SELECT case_id FROM entry_cases WHERE entry_id=?',(eid,))['case_id']==cid
        task=save_task(dict(text='Aufgabe',case_items=payload))
        assert one('SELECT case_id FROM tasks WHERE id=?',(task,))['case_id']==cid
        save_task(dict(text='Aufgabe',case_items='[]'),task)
        assert one('SELECT case_id FROM tasks WHERE id=?',(task,))['case_id'] is None


def test_case_suggestions_reconcile_on_manual_creation(app,post):
    with app.app_context():
        save_entry(dict(type='note',title='Notiz',date='2026-09-23',case_items=json.dumps([dict(kind='new_case',label='Elternanfrage')])) )
        get_db().commit()
    cid=make_case(post,'Elternanfrage')
    with app.app_context():
        assert one('SELECT case_id FROM entry_cases')['case_id']==cid
        assert one('SELECT status FROM case_suggestions')['status']=='resolved'
