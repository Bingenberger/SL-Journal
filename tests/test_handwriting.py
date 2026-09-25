import io
import json
import uuid
import pytest
from PIL import Image
from journal.db import get_db, one
from journal.domain import save_entry


def payload(**kwargs):
    image=io.BytesIO()
    Image.new('RGB',(100,60),'white').save(image,format='PNG')
    image.seek(0)
    scene=dict(type='excalidraw',version=2,elements=[dict(
        id='stroke1',type='freedraw',x=0,y=0,width=100,height=50,points=[[0,0],[100,50]])],
        appState={},files={})
    return dict(client_key=str(uuid.uuid4()),revision='0',title='Mitschrift',date='2026-09-23',
                scene=json.dumps(scene),preview=(image,'preview.png'),**kwargs)


def test_create_edit_retry_conflict_and_cascade(app,client,post):
    data=payload()
    key=data['client_key']
    response=post('/handwriting/save',data)
    assert response.status_code==200
    result=response.json
    with app.app_context():
        entry=one('SELECT * FROM entries WHERE id=?',(result['entry_id'],))
        assert entry['type']=='note'
        assert entry['title']=='Mitschrift'
        assert one('SELECT COUNT(*) n FROM drawings')['n']==1
    assert client.get(result['edit'],base_url='https://localhost').status_code==200
    preview=client.get(result['png'],base_url='https://localhost')
    assert preview.mimetype=='image/png'
    assert preview.headers['Cache-Control']=='no-store'
    assert 'attachment' in preview.headers['Content-Disposition']
    retry=payload();retry['client_key']=key
    assert post('/handwriting/save',retry).json['id']==result['id']
    edited=payload();edited.update(client_key=key,revision='1',title='Neuer Blatttitel')
    assert post('/handwriting/save',edited).json['revision']==2
    stale=payload();stale.update(client_key=key,revision='1',title='Veraltete Fassung')
    assert post('/handwriting/save',stale).status_code==409
    assert post(f"/handwriting/{result['id']}/delete",{'revision':1}).status_code==400
    assert post(f"/entry/{result['entry_id']}/delete").status_code==200
    with app.app_context():
        assert not one('SELECT * FROM drawings WHERE id=?',(result['id'],))


def test_add_multiple_sheets_to_protocol(app,post):
    with app.app_context():
        eid=save_entry(dict(type='protocol',title='Sitzung',date='2026-09-23',decisions='Beschluss'))
        get_db().commit()
    ids=[]
    for _ in range(2):
        response=post('/handwriting/save',payload(entry_id=str(eid)))
        assert response.status_code==200
        assert response.json['entry_id']==eid
        ids.append(response.json['id'])
    with app.app_context():
        assert one('SELECT COUNT(*) n FROM entries')['n']==1
        assert one('SELECT decisions FROM entries WHERE id=?',(eid,))['decisions']=='Beschluss'
    assert post(f'/handwriting/{ids[0]}/delete',{'revision':1}).status_code==302
    with app.app_context():
        assert one('SELECT COUNT(*) n FROM drawings')['n']==1


@pytest.mark.parametrize('bad',[
    '{}', '{"type":"excalidraw","elements":"bad"}',
    '{"type":"excalidraw","elements":[{"type":"image"}]}',
    '{"type":"excalidraw","elements":[],"files":{"a":{"dataURL":"https://example.com"}}}',
    '{"type":"excalidraw","elements":[{"id":"x","type":"freedraw","x":1e999,"y":0,"width":1,"height":1}]}',
])
def test_bad_scenes_leave_no_entry(app,post,bad):
    data=payload();data['scene']=bad
    assert post('/handwriting/save',data).status_code==400
    with app.app_context():
        assert one('SELECT COUNT(*) n FROM entries')['n']==0


def test_auth_csrf_and_invalid_preview(app,client,post):
    anon=app.test_client()
    for route in ['/handwriting/new','/handwriting/1','/handwriting/1/preview']:
        assert anon.get(route,base_url='https://localhost').status_code==302
    assert client.post('/handwriting/save',data=payload(),base_url='https://localhost').status_code==400
    data=payload();data['preview']=(io.BytesIO(b'<svg onload="bad()"/>'),'bad.png')
    assert post('/handwriting/save',data).status_code==400
    assert client.get('/handwriting/new?entry=9999',base_url='https://localhost').status_code==404
    policy=client.get('/handwriting/new',base_url='https://localhost').headers['Content-Security-Policy']
    assert "script-src 'self';" in policy
    assert "style-src-attr 'unsafe-inline'" in policy
    assert "style-src-attr 'unsafe-inline'" not in client.get('/',base_url='https://localhost').headers['Content-Security-Policy']


def test_backup_restores_editable_sheet(app,post,tmp_path):
    from cryptography.fernet import Fernet
    from journal.maintenance import backup,restore
    from journal.db import connect
    from pathlib import Path
    result=post('/handwriting/save',payload()).json
    with app.app_context():
        instance=Path(app.instance_path)
        backup_key=instance/'backup.key'
        backup_key.write_bytes(Fernet.generate_key())
        saved_file=backup()
        original=one('SELECT scene,preview FROM drawings WHERE id=?',(result['id'],))
    target=tmp_path/'restored'
    restore(saved_file,backup_key,target)
    restored=connect(target/'journal.db',(target/'master.key').read_bytes())
    row=restored.execute('SELECT scene,preview FROM drawings WHERE id=?',(result['id'],)).fetchone()
    assert row['scene']==original['scene']
    assert row['preview']==original['preview']
    restored.close()


def test_classify_handwriting_preserves_content(app,client,post):
    result=post('/handwriting/save',payload()).json
    eid=result['entry_id']
    with app.app_context():
        db=get_db()
        pid=db.execute("INSERT INTO projects(name,school_year) VALUES('Handschriftprojekt','2026/27')").lastrowid
        db.execute("UPDATE entries SET body='Zusatztext',decisions='Beschluss' WHERE id=?",(eid,))
        db.commit()
        drawing=one('SELECT scene,preview,revision FROM drawings WHERE id=?',(result['id'],))
    url=f'/entry/{eid}/classification'
    selected=[dict(kind='project',id=pid),dict(kind='new_project',label='Neue Idee',school_year='2026/27')]
    response=post(url,dict(project_items=json.dumps(selected),tags='#Sitzung, Planung, Sitzung',body='Nicht übernehmen'))
    assert response.status_code==200
    with app.app_context():
        assert one('SELECT tags,body,decisions FROM entries WHERE id=?',(eid,))==dict(tags='Sitzung, Planung',body='Zusatztext',decisions='Beschluss')
        assert one('SELECT scene,preview,revision FROM drawings WHERE id=?',(result['id'],))==drawing
        assert one('SELECT project_id FROM entry_projects WHERE entry_id=?',(eid,))['project_id']==pid
        assert one('SELECT COUNT(*) n FROM entry_project_suggestions WHERE entry_id=?',(eid,))['n']==1
        assert one("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'Planung'")['rowid']==eid
    page=client.get(f'/entry/{eid}',base_url='https://localhost').text
    assert 'id="entry-classification"' in page
    assert 'data-project-items=' in page and 'Neue Idee' in page
    assert '<h2>Anhänge' not in page and '<h2>Nextcloud-Dokumente' not in page
    assert client.post(url,data={'tags':'ohne CSRF'},base_url='https://localhost').status_code==400
    assert post(url,dict(project_items='[{"kind":"project","id":999999}]',tags='Fehler')).status_code==400
    with app.app_context():
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']=='Sitzung, Planung'
    assert post(url,dict(project_items='[]',tags='')).status_code==200
    with app.app_context():
        assert not one('SELECT * FROM entry_projects WHERE entry_id=?',(eid,))
        assert not one('SELECT * FROM entry_project_suggestions WHERE entry_id=?',(eid,))
        assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']==''
    assert post('/entry/999999/classification',dict(tags='Test')).status_code==404


def test_existing_files_remain_accessible_on_drawings(app,client,post):
    result=post('/handwriting/save',payload()).json
    eid=result['entry_id']
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO attachments(entry_id,name,path,mime,size) VALUES(?,'Vorhanden.pdf','existing.enc','application/pdf',10)",(eid,))
        did=db.execute("INSERT INTO documents(name,url) VALUES('Vorhandene Datei','https://cloud.example/datei')").lastrowid
        db.execute('INSERT INTO entry_documents VALUES(?,?)',(eid,did))
        db.commit()
    page=client.get(f'/entry/{eid}',base_url='https://localhost').text
    assert '<h2>Anhänge' in page
    assert '<h2>Nextcloud-Dokumente' in page
