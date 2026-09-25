import io
from datetime import date,timedelta
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from journal.db import connect,get_db,one,rows,set_setting
from journal.domain import now,save_entry,save_task,process_due,school_year,trigger_process

def test_all_pages_render_and_security_headers(app,client):
    from journal.demo import seed
    with app.app_context(): seed()
    for path in ['/','/?date=2026-01-01','/projects','/projects?status=closed','/project/1','/entries','/entries?inbox=1','/entry/1','/tasks','/tasks?filter=undated','/tasks?filter=done','/people','/processes','/settings']:
        response=client.get(path,base_url='https://localhost')
        assert response.status_code==200,(path,response.data.decode())
        assert 'frame-ancestors' in response.headers['Content-Security-Policy']
        assert response.headers['Cache-Control']=='no-store'

def test_https_auth_csrf_and_no_public_attachment(app,client):
    assert client.get('/').status_code==400
    assert app.test_client().get('/',base_url='https://localhost').status_code==302
    assert app.test_client().get('/attachment/1',base_url='https://localhost').status_code==302
    assert client.post('/task/save',data={'text':'test'},base_url='https://localhost').status_code==400

def test_entry_context_fts_attachments_archive(app,client,post):
    assert post('/project/save',{'name':'Schulfest','school_year':'2026/27'}).status_code==200
    response=post('/entry/save',{'date':'2026-09-21','type':'meeting','title':'Planung','body':'Vertrauliche Laternenbesprechung <script>alert(1)</script>','projects':'1','tags':'Ideen, #Herbst','new_task':'Raumplan abstimmen','task_due':'2026-09-22','attachments':(io.BytesIO(b'geheimer Inhalt'),'Raumplan.txt')})
    assert response.status_code==200,response.data
    with app.app_context():
        task=one('SELECT * FROM tasks')
        assert task['project_id']==1 and task['entry_id']==1
        attachment=one('SELECT * FROM attachments')
        assert b'geheimer Inhalt' not in (Path(app.instance_path)/'attachments'/attachment['path']).read_bytes()
        assert b'Laternenbesprechung' not in (Path(app.instance_path)/'journal.db').read_bytes()
    assert client.get('/attachment/1',base_url='https://localhost').data==b'geheimer Inhalt'
    assert b'<script>alert' not in client.get('/entry/1',base_url='https://localhost').data
    assert 'Planung' in client.get('/entries?q=Laternen',base_url='https://localhost').text
    assert post('/project/1/status',{}).status_code==200
    assert 'Planung' in client.get('/entries?q=Laternen',base_url='https://localhost').text
    assert 'Planung' in client.get('/project/1',base_url='https://localhost').text
    assert post('/task/1/toggle').status_code==200
    with app.app_context(): assert one('SELECT * FROM tasks')['completed_at']
    assert post('/task/1/toggle').status_code==200
    with app.app_context(): assert one('SELECT * FROM tasks')['completed_at'] is None

def test_edit_reindexes_and_deleting_entry_preserves_task(app,client,post):
    assert post('/entry/save',{'date':'2026-09-21','type':'journal','title':'Alt','body':'Banane','projects':'','new_task':'Weiterarbeiten'}).status_code==200
    assert post('/entry/save',{'id':'1','date':'2026-09-21','type':'journal','title':'Neu','body':'Apfel'}).status_code==200
    assert 'Neu' in client.get('/entries?q=Apfel',base_url='https://localhost').text
    assert '0 Einträge' in client.get('/entries?q=Banane',base_url='https://localhost').text
    assert post('/entry/1/delete').status_code==200
    with app.app_context():
        assert not one('SELECT id FROM entries')
        assert one('SELECT * FROM tasks')['entry_id'] is None

def test_task_groups_and_invalid_dates(app,client,post):
    with app.app_context():
        for text,due in [('OVER','2026-09-20'),('TODAY','2026-09-21'),('SOON','2026-10-05'),('LATER','2026-10-06'),('UNDATED',None)]:
            save_task(dict(text=text,due=due))
        get_db().commit()
    text=client.get('/?date=2026-09-21',base_url='https://localhost').text
    assert all(s in text for s in ['OVER','TODAY','SOON'])
    assert 'LATER' not in text and 'UNDATED' not in text
    assert 'UNDATED' in client.get('/tasks?filter=undated',base_url='https://localhost').text
    assert post('/task/save',{'text':'bad','due':'2026-02-30'}).status_code==400
    assert client.get('/?date=nonsense',base_url='https://localhost').status_code==400

def test_multiple_projects_person_and_validation_rollback(app,post,client):
    for name in ['Projekt A','Projekt B']: post('/project/save',{'name':name})
    post('/person/save',{'name':'Kontakt','emails':'kontakt@example.org'})
    assert post('/entry/save',{'title':'Test','date':'2026-09-21','projects':['1','2'],'people':['1']}).status_code==200
    assert client.get('/person/1',base_url='https://localhost').status_code==200
    assert post('/entry/save',{'id':'1','title':'Ungültig','date':'2026-09-21','projects':['99']}).status_code==400
    with app.app_context():
        assert one('SELECT title FROM entries')['title']=='Test'
        assert len(rows('SELECT * FROM entry_projects'))==2

def test_process_school_year_idempotency(app,post):
    assert school_year(date(2026,7,31))=='2025/26'
    assert school_year(date(2026,8,1))=='2026/27'
    with app.app_context():
        db=get_db()
        pid=db.execute("""INSERT INTO processes(name,month,period,todos) VALUES('Martinszug',9,'early','["Helfer anfragen"]')""").lastrowid
        db.commit()
        assert not process_due(one('SELECT * FROM processes'),date(2026,8,31))
        assert process_due(one('SELECT * FROM processes'),date(2026,9,1))
        project=trigger_process(pid,date(2026,9,21))
        assert one('SELECT * FROM tasks')['project_id']==project
        with pytest.raises(ValueError): trigger_process(pid,date(2026,9,21))
        db.rollback()
        assert process_due(one('SELECT * FROM processes'),date(2027,9,1))

def test_project_completion_creates_process_template(app,post):
    post('/project/save',{'name':'Schulfest'})
    post('/task/save',{'text':'Einladung versenden','project_id':'1'})
    assert post('/project/1/status',{'template':'1','month':'9','period':'early'}).status_code==200
    with app.app_context():
        assert one('SELECT * FROM processes')['todos']=='["Einladung versenden"]'
        assert one('SELECT * FROM projects')['status']=='closed'

def test_backup_roundtrip_and_retention(app,tmp_path):
    from journal.maintenance import backup,restore,purge
    from journal.domain import save_attachment
    with app.app_context():
        Path(app.instance_path,'backup.key').write_bytes(Fernet.generate_key())
        eid=save_entry(dict(title='Privat',body='Geheim',date=(now().date()-timedelta(days=60)).isoformat(),type='phone'))
        save_attachment(eid,'datei.txt',b'Vertraulich','text/plain')
        save_task(dict(text='Offene Aufgabe',entry_id=eid))
        get_db().commit()
        output=backup()
        assert b'Geheim' not in output.read_bytes()
        target=restore(output,Path(app.instance_path)/'backup.key',tmp_path/'restored')
        db=connect(target/'journal.db',(target/'master.key').read_bytes())
        assert db.execute('SELECT body FROM entries').fetchone()[0]=='Geheim';db.close()
        assert len(list((target/'attachments').glob('*.enc')))==1
        set_setting('retention',{'phone':30});get_db().commit()
        assert len(purge())==1 and one('SELECT id FROM entries')
        assert len(purge(True))==1 and not one('SELECT id FROM entries')
        assert one('SELECT entry_id FROM tasks')['entry_id'] is None
        assert not list((Path(app.instance_path)/'attachments').glob('*.enc'))

def test_obsidian_dry_run_dedup_and_frontmatter(app,tmp_path):
    from journal.maintenance import import_obsidian
    vault=tmp_path/'vault';vault.mkdir()
    (vault/'2026-09-21.md').write_text('---\ntags: [Schule, Planung]\nprojects: [Schulfest]\n---\n# Mein Tag\nNotiz #Kollegium\n- [ ] Einladung schreiben 📅 2026-09-25\n- [x] Schon erledigt\n![[plan.txt]]',encoding='utf-8')
    (vault/'plan.txt').write_text('Plan')
    with app.app_context():
        preview=import_obsidian(vault)
        assert preview['entries']==1 and preview['tasks']==1 and preview['attachments']==1
        assert not one('SELECT id FROM entries')
        imported=import_obsidian(vault,True)
        assert not imported['errors']
        assert one('SELECT * FROM entries')['type']=='journal'
        assert one('SELECT * FROM tasks')['due']=='2026-09-25'
        assert one('SELECT * FROM tasks')['project_id']==1
        assert import_obsidian(vault,True)['skipped']==1
