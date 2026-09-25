from cryptography.fernet import Fernet
from journal.db import SCHEMA, connect, get_db, init_db, one
from journal.domain import save_entry
from journal.app import create_app


def test_protocol_fields_and_search(app, client, post):
    data=dict(type='protocol', title='Sitzung', date='2026-09-23',
              body='**Protokolltext**', agenda='- Haushaltsberatung',
              decisions='**Einstimmigkeitsbeschluss**')
    assert post('/entry/save', data).status_code == 200
    with app.app_context():
        entry=one("SELECT * FROM entries WHERE title='Sitzung'")
        eid=entry['id']
        assert entry['agenda']==data['agenda']
        assert entry['decisions']==data['decisions']
        for term in ('Haushaltsberatung','Einstimmigkeitsbeschluss'):
            assert one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?",(term,))['rowid']==eid
    page=client.get(f'/entry/{eid}',base_url='https://localhost').get_data(as_text=True)
    assert '<strong>Einstimmigkeitsbeschluss</strong>' in page
    assert '<li>Haushaltsberatung</li>' in page
    assert '<strong>Protokolltext</strong>' in page
    assert post('/entry/save',dict(data,id=eid,decisions='Vertagungsbeschluss')).status_code==200
    with app.app_context():
        assert not one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'Einstimmigkeitsbeschluss'")
        assert one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'Vertagungsbeschluss'")
        save_entry(dict(type='protocol',title='Sitzung',date='2026-09-23'),entry_id=eid)
        assert one('SELECT decisions FROM entries WHERE id=?',(eid,))['decisions']=='Vertagungsbeschluss'


def test_legacy_migration_preserves_relations_and_search(tmp_path):
    instance=tmp_path/'legacy'
    instance.mkdir()
    key=Fernet.generate_key()
    (instance/'master.key').write_bytes(key)
    db=connect(instance/'journal.db',key)
    legacy=SCHEMA.replace(",'protocol'",'').replace(" agenda TEXT NOT NULL DEFAULT '', decisions TEXT NOT NULL DEFAULT '',",'')
    legacy=legacy.replace(',agenda,decisions','').replace(',new.agenda,new.decisions','').replace(',old.agenda,old.decisions','')
    db.executescript(legacy)
    db.execute("INSERT INTO entries(id,date,type,title,body) VALUES(42,'2026-09-23','meeting','Altbestand','Suchbestand')")
    db.execute("INSERT INTO projects(id,name,school_year) VALUES(7,'Projekt','2026/27')")
    db.execute("INSERT INTO entry_projects VALUES(42,7)")
    db.execute("INSERT INTO people(id,name) VALUES(8,'Person')")
    db.execute("INSERT INTO entry_people VALUES(42,8)")
    db.execute("INSERT INTO tasks(id,text,entry_id) VALUES(9,'Auftrag',42)")
    db.execute("INSERT INTO attachments(id,entry_id,name,path,mime,size) VALUES(10,42,'PDF','test.enc','application/pdf',50)")
    db.execute("INSERT INTO documents(id,name,url) VALUES(11,'Datei','https://cloud.example/test')")
    db.execute("INSERT INTO entry_documents VALUES(42,11)")
    db.commit()
    db.close()
    app=create_app({'INSTANCE_PATH':str(instance),'TESTING':True})
    with app.app_context():
        db=get_db()
        for _ in range(2):
            init_db()
            assert db.execute('PRAGMA foreign_keys').fetchone()[0]==1
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            assert one('SELECT * FROM entries WHERE id=42')['agenda']==''
            assert one('SELECT * FROM entry_projects WHERE entry_id=42')['project_id']==7
            assert one('SELECT * FROM entry_people WHERE entry_id=42')['person_id']==8
            assert one('SELECT * FROM tasks WHERE id=9')['entry_id']==42
            assert one('SELECT * FROM attachments WHERE id=10')['entry_id']==42
            assert one('SELECT * FROM entry_documents WHERE entry_id=42')['document_id']==11
            assert one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'Suchbestand'")['rowid']==42
        eid=save_entry(dict(type='protocol',title='Neu',date='2026-09-23',agenda='Neutagesordnung',decisions='Neubeschluss'))
        assert one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'Neubeschluss'")['rowid']==eid
