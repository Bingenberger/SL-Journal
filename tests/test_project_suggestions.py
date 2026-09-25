import json
from journal.db import get_db, one, rows
from journal.domain import school_year


def selection(name):
    return json.dumps([dict(kind='new_project', label=name)])


def entry(post, name='Schulgarten', **extra):
    return post('/entry/save', dict(title='Projektidee', date='2026-09-22', type='note', project_items=selection(name), **extra))


def test_shared_suggestion_accepts_entries_and_tasks(app, post, client):
    assert entry(post).status_code == 200
    assert entry(post, ' schulgarten ').status_code == 200
    assert post('/task/save', dict(text='Material bestellen', project_items=selection('Schulgarten'))).status_code == 200
    with app.app_context():
        assert one('SELECT count(*) n FROM project_suggestions')['n'] == 1
        sid=one('SELECT id FROM project_suggestions')['id']
        assert one('SELECT count(*) n FROM projects')['n'] == 0
    assert post('/project/save', dict(suggestion_id=sid, name='Schulgarten', school_year=school_year())).status_code == 200
    with app.app_context():
        pid=one('SELECT id FROM projects')['id']
        assert one('SELECT count(*) n FROM entry_projects')['n'] == 2
        assert one('SELECT project_id FROM tasks')['project_id'] == pid
        assert not rows('SELECT * FROM task_project_suggestions')
        assert not rows('SELECT * FROM entry_project_suggestions')
    assert post('/project/save', dict(suggestion_id=sid, name='Doppelt', school_year=school_year())).status_code == 400


def test_edit_ignore_restore_and_prune(app, post, client):
    entry(post)
    with app.app_context():
        eid=one('SELECT id FROM entries')['id']; sid=one('SELECT id FROM project_suggestions')['id']
    from journal.domain import entry_details
    with app.app_context():
        values=entry_details(one('SELECT * FROM entries WHERE id=?',(eid,)))['project_items']
        assert values[0]['label']=='Schulgarten'
    assert post(f'/project-suggestion/{sid}/status',dict(status='ignored')).status_code==200
    assert entry(post,id=eid).status_code==200
    with app.app_context(): assert one('SELECT status FROM project_suggestions')['status']=='ignored'
    assert post(f'/project-suggestion/{sid}/status',dict(status='pending')).status_code==200
    assert post('/entry/save',dict(id=eid,title='Keine Idee',date='2026-09-22',project_items='[]')).status_code==200
    with app.app_context(): assert not rows('SELECT * FROM project_suggestions')


def test_merge_existing_and_alias(app,post):
    post('/project/save',dict(name='Außengelände',school_year=school_year()))
    entry(post)
    with app.app_context():
        sid=one('SELECT id FROM project_suggestions')['id']; pid=one('SELECT id FROM projects')['id']
    assert post(f'/project-suggestion/{sid}/link',dict(project_id=pid)).status_code==200
    entry(post)
    with app.app_context():
        assert one('SELECT count(*) n FROM entry_projects')['n']==2
        assert not rows('SELECT * FROM entry_project_suggestions')


def test_task_edit_and_inheritance(app,post):
    entry(post,new_task='Pflanzen bestellen')
    with app.app_context():
        tid=one('SELECT id FROM tasks')['id']
        assert one('SELECT task_id FROM task_project_suggestions')['task_id']==tid
    assert post('/task/save',dict(id=tid,text='Planen',project_items=selection('Neues Vorhaben'))).status_code==200
    with app.app_context():
        assert one('SELECT s.name FROM project_suggestions s JOIN task_project_suggestions r ON r.suggestion_id=s.id')['name']=='Neues Vorhaben'


def test_inbox_assignment_and_validation_rollback(app,post):
    entry(post)
    with app.app_context(): eid=one('SELECT id FROM entries')['id']
    assert post(f'/entry/{eid}/assign',dict(project_items=selection('Weitere Idee'))).status_code==200
    with app.app_context(): assert one('SELECT count(*) n FROM entry_project_suggestions')['n']==2
    for bad in ('{', '{}', '[{"kind":"project","id":999}]', '[{"kind":"new_project","label":""}]'):
        assert post('/entry/save',dict(id=eid,title='Ungültig',date='2026-09-22',project_items=bad)).status_code==400
    with app.app_context():
        assert one('SELECT title FROM entries')['title']=='Projektidee'
        assert one('SELECT count(*) n FROM entry_project_suggestions')['n']==2


def test_search_proposals_and_exact_existing_name(app,post,client):
    entry(post)
    result=client.get('/api/autocomplete/projects?q=schulg',base_url='https://localhost').get_json()
    assert result['items'][0]['kind']=='new_project'
    assert client.get('/api/autocomplete/projects?q=schulg&existing_only=1',base_url='https://localhost').get_json()['items']==[]
    post('/project/save',dict(name='Bestehendes Projekt',school_year=school_year()))
    entry(post,'bestehendes projekt')
    with app.app_context():
        assert one('SELECT count(*) n FROM project_suggestions')['n']==1
        assert one('SELECT count(*) n FROM entry_projects')['n']==1


def test_manual_creation_resolves_same_year_only(app,post):
    entry(post)
    post('/project/save',dict(name='Schulgarten',school_year='2020/21'))
    with app.app_context(): assert one('SELECT project_id FROM project_suggestions')['project_id'] is None
    post('/project/save',dict(name='Schulgarten',school_year=school_year()))
    with app.app_context():
        assert one('SELECT project_id FROM project_suggestions')['project_id']
        assert one('SELECT count(*) n FROM entry_projects')['n']==1
