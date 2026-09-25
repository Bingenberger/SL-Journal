from journal.db import get_db, one, rows, init_db
from journal.domain import school_year
from journal.project_suggestions import items
import json


def test_multiple_entry_tasks_and_atomic_validation(app,post):
    data=dict(type='meeting',date='2026-09-22',title='Konferenz',new_task=['Protokoll senden','Termin abstimmen',''],task_due=['2026-10-01','',''])
    assert post('/entry/save',data).status_code==200
    with app.app_context():
        tasks=rows('SELECT * FROM tasks ORDER BY id')
        assert len(tasks)==2 and tasks[0]['due']=='2026-10-01' and tasks[1]['due'] is None
        assert tasks[0]['entry_id']==tasks[1]['entry_id']
        eid=tasks[0]['entry_id']
    assert post('/entry/save',dict(id=eid,title='Konferenz',date='2026-09-22',new_task=['Weitere Aufgabe'],task_due=[''])).status_code==200
    assert post('/entry/save',dict(title='Fehler',date='2026-09-22',new_task=['Gültig','Ungültig'],task_due=['','kein-datum'])).status_code==400
    assert post('/entry/save',dict(title='Fehler',date='2026-09-22',new_task=[''],task_due=['2026-10-01'])).status_code==400
    with app.app_context():
        assert one('SELECT count(*) n FROM tasks')['n']==3
        assert one('SELECT count(*) n FROM entries')['n']==1


def test_subtasks_inherit_context_progress_and_reopening(app,post,client):
    post('/project/save',dict(name='Planung',school_year=school_year()))
    post('/entry/save',dict(title='Mail',type='mail_in',date='2026-09-22',projects=['1']))
    assert post('/task/save',dict(text='Veranstaltung organisieren',entry_id=1,subtask_text=['Raum buchen','Einladung senden'],subtask_due=['2026-10-01',''])).status_code==200
    with app.app_context():
        tasks=rows('SELECT * FROM tasks ORDER BY id')
        assert [t['parent_id'] for t in tasks]==[None,1,1]
        assert all(t['entry_id']==1 and t['project_id']==1 for t in tasks)
    assert post('/task/1/toggle').status_code==400
    assert post('/task/2/toggle').status_code==200
    assert post('/task/3/toggle').status_code==200
    assert post('/task/1/toggle').status_code==200
    assert post('/task/2/toggle').status_code==200
    with app.app_context():
        parent=one('SELECT * FROM tasks WHERE id=1')
        assert parent['done']==0 and parent['completed_at'] is None
    html=client.get('/tasks?filter=all',base_url='https://localhost').get_data(as_text=True)
    assert '1/2 Unteraufgaben erledigt' in html
    assert post('/task/save',dict(text='Neue Unteraufgabe',parent_id=1)).status_code==200
    assert post('/task/save',dict(text='Zu tief',parent_id=2)).status_code==400
    assert post('/task/save',dict(id=1,text='Zyklus',parent_id=1)).status_code==400
    assert post('/task/save',dict(text='Verwaist',parent_id=9999)).status_code==400
    assert post('/task/save',dict(id=2,text='Raum reservieren',due='2026-10-02')).status_code==200
    with app.app_context(): assert one('SELECT parent_id FROM tasks WHERE id=2')['parent_id']==1


def test_subtasks_inherit_project_suggestion_and_survive_entry_delete(app,post):
    post('/entry/save',dict(title='Notiz',date='2026-09-22'))
    post('/task/save',dict(text='Planen',entry_id=1,project_items=json.dumps([dict(kind='new_project',label='Neue Planung')]),subtask_text=['Prüfen'],subtask_due=['']))
    with app.app_context():
        assert items('task',1)==items('task',2)
        sid=one('SELECT id FROM project_suggestions')['id']
    post('/project/save',dict(name='Neue Planung',school_year=school_year(),suggestion_id=sid))
    post('/entry/1/delete')
    with app.app_context():
        tasks=rows('SELECT * FROM tasks ORDER BY id')
        assert len(tasks)==2 and all(t['entry_id'] is None for t in tasks)
        assert tasks[1]['parent_id']==tasks[0]['id']
        assert tasks[1]['project_id']==tasks[0]['project_id']==1


def test_task_batch_rollback_and_reopen_completed_parent(app,post):
    assert post('/task/save',dict(text='Fehlerhaft',subtask_text=['Gültig','Ungültig'],subtask_due=['','falsch'])).status_code==400
    with app.app_context(): assert not rows('SELECT * FROM tasks')
    post('/task/save',dict(text='Hauptaufgabe'))
    post('/task/1/toggle')
    post('/task/save',dict(id=1,text='Hauptaufgabe',subtask_text=['Nacharbeit'],subtask_due=['']))
    with app.app_context(): assert one('SELECT done FROM tasks WHERE id=1')['done']==0


def test_task_migration_preserves_existing(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO tasks(text,done,completed_at) VALUES('Altbestand',1,'2026-09-20')")
        db.execute('DROP INDEX task_parent')
        db.execute('ALTER TABLE tasks DROP COLUMN parent_id')
        db.commit()
        init_db();init_db()
        task=one('SELECT * FROM tasks')
        assert task['text']=='Altbestand' and task['done']==1 and task['completed_at']=='2026-09-20'
        assert task['parent_id'] is None
