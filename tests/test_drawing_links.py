import json
import pytest
from journal.db import get_db, one
from journal.domain import save_entry
from journal.entry_links import listed
from test_handwriting import payload


def setup_sheet(app,post):
    drawing=post('/handwriting/save',payload()).json
    with app.test_request_context():
        eid=save_entry(dict(type='protocol',title='Sitzung zur Verknüpfung',date='2026-09-23',tags='Organisation'))
        get_db().commit()
    return drawing,eid


def test_link_roundtrip_backlink_and_layout(app,client,post):
    drawing,eid=setup_sheet(app,post)
    did=drawing['id']
    owner=drawing['entry_id']
    with app.test_request_context():
        original=one('SELECT scene,preview,revision FROM drawings WHERE id=?',(did,))
    for _ in range(2):
        assert post(f'/entry/{owner}/link',{'resource_url':f'/entry/{eid}'}).status_code==200
    with app.test_request_context():
        links=listed(owner)
        assert len(links)==1 and links[0]['kind']=='Protokoll'
        assert one('SELECT scene,preview,revision FROM drawings WHERE id=?',(did,))==original
        get_db().execute("UPDATE entries SET title='Umbenanntes Protokoll' WHERE id=?",(eid,))
        get_db().commit()
        assert listed(owner)[0]['label']=='Umbenanntes Protokoll'
    source=client.get(f"/entry/{drawing['entry_id']}",base_url='https://localhost').text
    assert source.index('handwriting-sheets')<source.index('id="entry-classification"')<source.index('class="detail-grid"')
    assert 'Umbenanntes Protokoll' in source
    target=client.get(f'/entry/{eid}',base_url='https://localhost').text
    assert 'Verknüpfte Einträge' in target and f'/entry/{owner}' in target
    second=post('/handwriting/save',payload()).json
    lid=links[0]['id']
    assert post(f"/entry/{second['entry_id']}/link/{lid}/remove").status_code==404
    assert post(f'/entry/{owner}/link/{lid}/remove').status_code==200
    with app.test_request_context():
        assert not listed(owner)
        assert one('SELECT id FROM entries WHERE id=?',(eid,))
        assert one('SELECT id FROM drawings WHERE id=?',(did,))


def test_resource_kinds_and_target_deletion(app,post):
    drawing,eid=setup_sheet(app,post)
    did=drawing['id']
    owner=drawing['entry_id']
    with app.test_request_context():
        db=get_db()
        pid=db.execute("INSERT INTO people(name) VALUES('Kontakt')").lastrowid
        project=db.execute("INSERT INTO projects(name,school_year) VALUES('Projekt','2026/27')").lastrowid
        task=db.execute("INSERT INTO tasks(text) VALUES('Aufgabe')").lastrowid
        document=db.execute("INSERT INTO documents(name,url) VALUES('Dateiverweis','https://cloud.example/datei')").lastrowid
        db.commit()
    urls=[f'/entry/{eid}',f'/person/{pid}',f'/project/{project}',f'/tasks?filter=all#task-{task}',f'/document/{document}','/entries?tag=Organisation']
    for url in urls:
        assert post(f'/entry/{owner}/link',{'resource_url':url}).status_code==200,url
    with app.test_request_context():
        assert len(listed(owner))==6
        get_db().execute('DELETE FROM entries WHERE id=?',(eid,))
        get_db().commit()
        assert len(listed(owner))==4  # The tag disappeared along with its last entry.
        assert one('SELECT id FROM drawings WHERE id=?',(did,))
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
    assert post(f"/entry/{drawing['entry_id']}/delete").status_code==200
    with app.test_request_context():
        assert one('SELECT COUNT(*) n FROM entry_resource_links')['n']==0


@pytest.mark.parametrize('url',['https://example.org/entry/1','//example.org/entry/1','javascript:alert(1)','/entry/99999','/settings','/tasks#unknown','/entries?tag=Fehlt',''])
def test_invalid_links(app,post,url):
    drawing,_=setup_sheet(app,post)
    assert post(f"/entry/{drawing['entry_id']}/link",{'resource_url':url}).status_code==400
    with app.test_request_context():
        assert one('SELECT COUNT(*) n FROM entry_resource_links')['n']==0


def test_self_link_and_csrf(app,client,post):
    drawing,_=setup_sheet(app,post)
    route=f"/entry/{drawing['entry_id']}/link"
    assert post(route,{'resource_url':f"/entry/{drawing['entry_id']}"}).status_code==400
    assert client.post(route,data={'resource_url':'/entry/1'},base_url='https://localhost').status_code==400
    assert app.test_client().get(f"/entry/{drawing['entry_id']}",base_url='https://localhost').status_code==302

def test_migrate_multiple_sheets_without_losing_links(app,client,post):
    from journal.db import SCHEMA, init_db
    from journal.entry_links import incoming
    drawing,target=setup_sheet(app,post)
    owner=drawing['entry_id']
    second=post('/handwriting/save',payload(entry_id=str(owner))).json
    with app.test_request_context():
        db=get_db()
        # Recreate the former schema, with links on individual sheets.
        db.execute('DROP TABLE entry_resource_links')
        old=SCHEMA[SCHEMA.index('CREATE TABLE IF NOT EXISTS entry_resource_links ('):SCHEMA.index('CREATE TABLE IF NOT EXISTS settings (')]
        old=old.replace('entry_resource_links','drawing_links').replace('owner_entry_id','drawing_id')
        old=old.replace('drawing_id INTEGER NOT NULL REFERENCES entries(id)','drawing_id INTEGER NOT NULL REFERENCES drawings(id)')
        db.executescript(old)
        person=db.execute("INSERT INTO people(name) VALUES('Migrationskontakt')").lastrowid
        project=db.execute("INSERT INTO projects(name,school_year) VALUES('Migrationsprojekt','2026/27')").lastrowid
        task=db.execute("INSERT INTO tasks(text) VALUES('Migrationsaufgabe')").lastrowid
        document=db.execute("INSERT INTO documents(name,url) VALUES('Migration','https://cloud.example/migration')").lastrowid
        targets=[('entry_id',target),('person_id',person),('project_id',project),('task_id',task),('document_id',document),('tag','organisation')]
        for sheet_id in [drawing['id'],second['id']]:
            for column,value in targets:
                db.execute(f'INSERT INTO drawing_links(drawing_id,{column}) VALUES(?,?)',(sheet_id,value))
        db.commit()
        init_db()
        assert len(listed(owner))==6
        assert not one("SELECT name FROM sqlite_master WHERE name='drawing_links'")
        assert incoming(target)[0]['drawing_count']==2
        init_db()
        assert len(listed(owner))==6
        db.execute('DELETE FROM drawings WHERE entry_id=?',(owner,))
        db.commit()
        assert len(listed(owner))==6
        assert incoming(target)[0]['preview_id'] is None
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    page=client.get(f'/entry/{owner}',base_url='https://localhost').text
    assert 'id="entry-resources"' in page
    assert page.count('data-resource-picker')==1
    assert post(f'/entry/{owner}/delete').status_code==200
    with app.app_context():
        assert one('SELECT COUNT(*) n FROM entry_resource_links')['n']==0
        assert one('SELECT id FROM entries WHERE id=?',(target,))
