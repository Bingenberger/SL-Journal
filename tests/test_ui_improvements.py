from datetime import timedelta
from urllib.parse import urlencode
from journal.db import get_db,one,setting
from journal.domain import save_entry,save_task,now,UNPROCESSED_MAIL
from test_tags import context


def test_inbox_tags_preserve_assignments_and_remove_processed_mail(app,client,post):
    with app.app_context():
        eid=save_entry(dict(title='Eingang',type='mail_in',date=now().date().isoformat()))
        get_db().commit()
    assert post(f'/entry/{eid}/assign',dict(tags='Organisation, Organisation')).status_code==200
    with app.app_context():
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']=='Organisation'
        assert not one('SELECT id FROM entries e WHERE '+UNPROCESSED_MAIL)
    assert post(f'/entry/{eid}/assign',dict(tags='Betreuung')).status_code==200
    assert post(f'/entry/{eid}/assign',dict(tags='Fehler',case_items='[{"kind":"case","id":9999}]')).status_code==400
    with app.app_context():
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']=='Organisation, Betreuung'
    assert post(f'/entry/{eid}/assign',dict(tags=' ')).status_code==400


def test_filters_pagination_and_task_deep_links(app,client):
    with app.app_context():
        db=get_db()
        pid=db.execute("INSERT INTO projects(name,description,school_year) VALUES('Raumplanung','Neuer Standort','2026/27')").lastrowid
        cid=db.execute("INSERT INTO cases(title) VALUES('Rückfrage')").lastrowid
        for i in range(65):
            db.execute('INSERT INTO people(name,institution,role) VALUES(?,?,?)',(f'Kontakt {i:03}','Schulamt' if i%2 else 'Schule','Referat'))
            save_task(dict(text=f'Aufgabe {i:03}',due=now().date().isoformat(),project_id=pid,case_id=cid))
        target=save_task(dict(text='Besondere Rückfrage',due=(now().date()-timedelta(days=1)).isoformat(),case_id=cid))
        save_task(dict(text='Ohne Frist'))
        db.commit()
    response,data=context(app,client,'/people?page=2&institution=Schulamt')
    assert data['total']==32 and len(data['people'])==2 and data['page']==2
    assert 'institution=Schulamt' in response.text
    _,data=context(app,client,'/people?page=999')
    assert data['page']==3 and len(data['people'])==5
    _,data=context(app,client,'/projects?q=standort')
    assert data['total']==1 and data['projects'][0]['id']==pid
    _,data=context(app,client,'/tasks?'+urlencode(dict(q='Rückfrage',case_id=cid,due='overdue')))
    assert len(data['tasks'])==1 and data['tasks'][0]['id']==target
    _,data=context(app,client,'/tasks?'+urlencode(dict(project_id=pid,due='today',page=2)))
    assert len(data['tasks'])==30 and data['total']==65
    _,data=context(app,client,'/tasks?due=undated')
    assert [t['text'] for t in data['tasks']]==['Ohne Frist']
    _,data=context(app,client,'/tasks?filter=all&focus_task=60')
    assert any(t['id']==60 for t in data['tasks']) and data['page']>1
    assert 'focus_task=' in client.get('/api/resources?q=Aufgabe+059',base_url='https://localhost').json['items'][0]['url']


def test_chronicles_and_compact_empty_entries(app,client):
    with app.app_context():
        db=get_db();cid=db.execute("INSERT INTO cases(title) VALUES('Verlauf')").lastrowid
        for i in range(35):
            eid=save_entry(dict(title=f'Notiz {i:02}',date=now().date().isoformat(),case_ids=f'[{cid}]'))
        db.commit()
    response,data=context(app,client,f'/case/{cid}?page=2')
    assert data['total']==35 and len(data['items'])==5
    response=client.get(f'/entry/{eid}',base_url='https://localhost')
    assert 'class="panel padded handwriting-sheets"' not in response.text
    assert 'Zeichenblatt hinzufügen' in response.text
    assert '<h2>Anhänge' not in response.text


def test_save_and_check_uses_new_settings_and_validates_first(app,post,monkeypatch):
    calls=[]
    def check():
        calls.append(setting('imap')['host'])
        return 'Verbindung geprüft'
    monkeypatch.setattr('journal.integrations.sync_all',check)
    response=post('/settings/save',dict(imap_host='imap.example.org',imap_username='test',imap_password='secret',own_addresses='test@example.org',intent='sync'))
    assert response.status_code==200 and calls==['imap.example.org']
    assert 'Verbindung geprüft' in response.json['message']
    assert post('/settings/save',dict(imap_host='other.example.org',intent='sync')).status_code==400
    assert len(calls)==1
    with app.app_context(): assert setting('imap')['host']=='imap.example.org'


def test_case_suggestion_can_be_named_before_adopting(app,post):
    import json
    with app.app_context():
        eid=save_entry(dict(title='Anfrage',date=now().date().isoformat(),case_items=json.dumps([dict(kind='new_case',label='Arbeitstitel')])))
        sid=one('SELECT id FROM case_suggestions')['id']
        get_db().commit()
    response=post('/case/save',dict(suggestion_id=sid,title='Klärung Betreuung',status='clarifying'))
    assert response.status_code==200
    with app.app_context():
        cid=one('SELECT case_id FROM entry_cases WHERE entry_id=?',(eid,))['case_id']
        assert one('SELECT title,status FROM cases WHERE id=?',(cid,))==dict(title='Klärung Betreuung',status='clarifying')
    assert post('/case/save',dict(suggestion_id=sid,title='Doppelter Vorgang')).status_code==404
