import io
import uuid
from pathlib import Path
from journal.db import get_db,one


def upload(post,**data):
    return post('/attachments/upload',{'mode':'new','title':'Unterlagen','date':'2026-10-04','request_key':str(uuid.uuid4()),'attachments':(io.BytesIO(b'Leseband'),'Plan.txt'),**data})


def test_create_associate_and_retry(app,post):
    with app.app_context():
        get_db().execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')")
        get_db().execute("INSERT INTO cases(title) VALUES('Anfrage')");get_db().commit()
    key=str(uuid.uuid4())
    result=upload(post,request_key=key,projects='1',cases='1',tags='Planung')
    assert result.status_code==200
    eid=result.json['entry_id']
    assert upload(post,request_key=key).json['entry_id']==eid
    with app.app_context():
        assert one('SELECT count(*) n FROM entries')['n']==1
        assert one('SELECT count(*) n FROM attachments')['n']==1
        assert one('SELECT tags FROM entries')['tags']=='Planung'
        assert one('SELECT project_id FROM entry_projects')['project_id']==1
        assert one('SELECT case_id FROM entry_cases')['case_id']==1
        assert one('SELECT status FROM attachment_index')['status']=='pending'


def test_attach_preserves_existing_content(app,post):
    eid=upload(post).json['entry_id']
    assert upload(post,mode='existing',target_id=str(eid),title='Nicht überschreiben',tags='Andere').status_code==200
    with app.app_context():
        assert one('SELECT title FROM entries')['title']=='Unterlagen'
        assert one('SELECT count(*) n FROM attachments')['n']==2


def test_validation_auth_and_atomicity(app,post,client,monkeypatch):
    assert upload(post,mode='existing',target_id='999').status_code==400
    assert upload(post,title='').status_code==400
    assert upload(post,attachments=[]).status_code==400
    assert upload(post,attachments=(io.BytesIO(b'x'*(25*1024*1024+1)),'gross.txt')).status_code==400
    assert client.post('/attachments/upload',base_url='https://localhost').status_code==400
    from journal import app as module
    original=module.save_attachment
    count=0
    def fail(*args):
        nonlocal count
        count+=1
        if count==2:raise ValueError('Speicherfehler')
        return original(*args)
    monkeypatch.setattr(module,'save_attachment',fail)
    assert upload(post,attachments=[(io.BytesIO(b'a'),'a.txt'),(io.BytesIO(b'b'),'b.txt')]).status_code==400
    with app.app_context():
        assert one('SELECT count(*) n FROM entries')['n']==0
        assert one('SELECT count(*) n FROM attachments')['n']==0
        assert not list((Path(app.instance_path)/'attachments').iterdir())


def test_upload_widget_context(app,client,post):
    eid=upload(post).json['entry_id']
    assert 'id="upload-drop"' in client.get('/',base_url='https://localhost').text
    html=client.get(f'/entry/{eid}',base_url='https://localhost').text
    assert f'data-entry="{eid}"' in html and 'id="upload-attachments"' in html
    assert 'id="upload-drop"' not in app.test_client().get('/login',base_url='https://localhost').text


def test_quittungen_tragen_ein_datum_und_bleiben_begrenzt(app,post):
    import time
    upload(post,title='Erster')
    with app.app_context():
        assert 'created' in {c['name'] for c in get_db().execute('PRAGMA table_info(upload_receipts)')}
        assert one('SELECT created FROM upload_receipts')['created']>0
        get_db().execute('UPDATE upload_receipts SET created=?',(time.time()-8*86400,))
        get_db().commit()
    upload(post,title='Zweiter')
    with app.app_context():
        anzahl=one('SELECT count(*) n FROM upload_receipts')['n']
    assert anzahl==1,'die abgelaufene Quittung wird beim nächsten Upload entfernt'
