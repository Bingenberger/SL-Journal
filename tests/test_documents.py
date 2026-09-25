from pathlib import Path
from cryptography.fernet import Fernet
import pytest
from journal.db import get_db,one,rows,connect
from journal.documents import listed
from journal.domain import school_year


def seed(post):
    post('/project/save',dict(name='Schulfest',school_year=school_year()))
    post('/entry/save',dict(title='Planung',date='2026-09-22',projects=['1']))


def link(post,**extra):
    return post('/document/save',dict(owner='entry',owner_id=1,name='Raumplan',url='https://cloud.example.org/f/123',description='Plan der Räume',**extra))


def test_shared_documents_project_aggregation_and_detach(app,post,client):
    seed(post)
    assert link(post).status_code==200
    assert post('/document/save',dict(owner='project',owner_id=1,name='Anderer Name',url='https://CLOUD.example.org:443/f/123')).status_code==200
    with app.app_context():
        assert one('SELECT count(*) n FROM documents')['n']==1
        assert one('SELECT name FROM documents')['name']=='Raumplan'
        docs=listed('project',1)
        assert len(docs)==1 and docs[0]['direct']==1 and len(docs[0]['origins'])==1
    assert post('/document/1/detach',dict(owner='project',owner_id=1)).status_code==200
    with app.app_context(): assert listed('project',1)[0]['direct']==0
    assert post('/document/1/detach',dict(owner='entry',owner_id=1)).status_code==200
    with app.app_context():
        assert not listed('entry',1) and not listed('project',1)
        assert one('SELECT id FROM documents')['id']==1
    assert client.get('/document/1',base_url='https://localhost').status_code==200
    data=client.get('/api/resources?q=Raumplan',base_url='https://localhost').get_json()
    assert data['items'][0]['url']=='/document/1'
    assert data['items'][0]['kind']=='Nextcloud-Dokument'


def test_update_keeps_resource_link_and_escapes_metadata(app,post,client):
    seed(post);link(post)
    assert post('/document/save',dict(id=1,name='<script>Plan</script>',description='<img src=x onerror=alert(1)>',url='https://cloud.example.org/f/456')).status_code==200
    html=client.get('/document/1',base_url='https://localhost').get_data(as_text=True)
    assert '<script>Plan</script>' not in html and '<img src=x' not in html
    assert 'https://cloud.example.org/f/456' in html
    assert 'rel="noopener noreferrer"' in html
    with app.app_context(): assert listed('entry',1)[0]['id']==1


@pytest.mark.parametrize('url',[
    'javascript:alert(1)','http://cloud.example.org/f/1','//cloud.example.org/f/1',
    'https://user:password@cloud.example.org/f/1','https://cloud.example.org/%0d%0aLocation:x',
    'https://cloud.example.org/a b','https://cloud.example.org:99999/f/1','https://cloud.example.org:0/f/1',
    'https://cloud.example.org'+chr(92)+'@evil.test/f/1',
])
def test_invalid_links_are_rejected_atomically(app,post,url):
    seed(post)
    assert post('/document/save',dict(owner='entry',owner_id=1,name='Plan',url=url)).status_code==400
    with app.app_context(): assert not rows('SELECT * FROM documents')


def test_invalid_owner_duplicate_edit_and_no_file_upload(app,post):
    seed(post)
    assert post('/document/save',dict(owner='entry',owner_id=999,name='Plan',url='https://cloud.example.org/f/1')).status_code==400
    with app.app_context(): assert not rows('SELECT * FROM documents')
    link(post)
    post('/document/save',dict(owner='entry',owner_id=1,name='Zweiter Plan',url='https://cloud.example.org/f/2'))
    assert post('/document/save',dict(id=2,name='Doppelt',url='https://cloud.example.org/f/123')).status_code==400
    with app.app_context():
        assert not rows('SELECT * FROM attachments')
        assert len(rows('SELECT * FROM documents'))==2
    assert not list((Path(app.instance_path)/'attachments').iterdir())


def test_entry_delete_preserves_project_document_and_backup(app,post,tmp_path):
    from journal.maintenance import backup,restore
    seed(post);link(post)
    post('/document/save',dict(owner='project',owner_id=1,name='Raumplan',url='https://cloud.example.org/f/123'))
    post('/entry/1/delete')
    with app.app_context():
        assert len(listed('project',1))==1
        key_path=Path(app.instance_path)/'backup.key'
        key_path.write_bytes(Fernet.generate_key())
        archive=backup()
        restored=restore(archive,key_path,tmp_path/'restored')
        db=connect(restored/'journal.db',(restored/'master.key').read_bytes())
        assert db.execute('SELECT url FROM documents').fetchone()[0]=='https://cloud.example.org/f/123'
        assert db.execute('SELECT count(*) FROM project_documents').fetchone()[0]==1
        db.close()


def test_document_routes_require_authentication_and_csrf(app,post):
    seed(post);link(post)
    anonymous=app.test_client()
    assert anonymous.get('/document/1',base_url='https://localhost').status_code==302
    assert anonymous.post('/document/1/detach',base_url='https://localhost',data={'owner':'entry','owner_id':1}).status_code==400
