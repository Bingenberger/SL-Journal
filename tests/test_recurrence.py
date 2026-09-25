import json
from datetime import date,datetime,timezone
import pytest
from journal.db import get_db,one,rows,init_db
from journal.domain import save_task,save_entry
from journal.recurrence import parse,title,next_on_or_after,following,generate,for_task


def freeze(monkeypatch,day):
    monkeypatch.setattr('journal.recurrence.now',lambda:datetime.fromisoformat(day).replace(tzinfo=timezone.utc))


def plan(post,**overrides):
    response=post('/task/save',dict(text='Statistik KW{KW} {KW_JAHR} abgeben',due='2026-01-01',repeat_frequency='weekly',repeat_interval='1',**overrides))
    assert response.status_code==200,response.text


def test_placeholders_iso_year_and_unknown():
    assert title('KW{KW}/{KW_JAHR}, {JAHR}, {MONAT}, {MONATSNAME}, Q{QUARTAL}, {DATUM}','2021-01-01')=='KW53/2020, 2021, 01, Januar, Q1, 01.01.2021'
    assert title('Statistik KW{KW}','2026-12-31')=='Statistik KW53'
    assert title('{QUARTAL}', '2026-10-01')=='4'
    for value in ['KW{XY}','{KW','{KW:02}','{__class__}','{}']:
        with pytest.raises(ValueError):title(value,'2026-01-01')


def test_calendar_boundaries_and_intervals():
    monthly=parse(dict(text='{MONATSNAME}',due='2024-01-31',repeat_frequency='monthly'))
    assert following(monthly,'2024-01-31')==date(2024,2,29)
    assert following(monthly,'2024-02-29')==date(2024,3,31)
    assert next_on_or_after(monthly,date(2025,2,1))==date(2025,2,28)
    quarterly=parse(dict(text='Q{QUARTAL}',due='2026-01-31',repeat_frequency='quarterly'))
    assert following(quarterly,'2026-01-31')==date(2026,4,30)
    assert following(quarterly,'2026-04-30')==date(2026,7,31)
    weekly=parse(dict(text='{KW}',due='2026-01-01',repeat_frequency='weekly',repeat_interval='2'))
    assert following(weekly,'2026-01-01')==date(2026,1,15)
    weekly['until_date']='2026-01-14'
    assert following(weekly,'2026-01-01') is None
    assert following(monthly,'9999-12-31') is None


def test_fixed_dates_sorted_deduplicated_and_bounded():
    config=parse(dict(text='{DATUM}',repeat_frequency='dates',repeat_dates='2026-05-02\n2026-04-01;2026-05-02',repeat_until='2026-05-01'))
    assert config['start_date']=='2026-04-01'
    assert json.loads(config['dates'])==['2026-04-01','2026-05-02']
    assert following(config,'2026-04-01') is None
    for values in [dict(repeat_dates=''),dict(repeat_dates='2026-02-30'),dict(repeat_dates='2026-01-01',repeat_until='2025-01-01')]:
        with pytest.raises(ValueError):parse(dict(text='Test',repeat_frequency='dates',**values))


def test_generation_is_independent_idempotent_and_preserves_context(app,client,post,monkeypatch):
    freeze(monkeypatch,'2026-01-01')
    with app.app_context():
        db=get_db();pid=db.execute("INSERT INTO projects(name,school_year) VALUES('Statistik','2025/26')").lastrowid
        cid=db.execute("INSERT INTO cases(title) VALUES('Rückmeldung')").lastrowid
        eid=save_entry(dict(title='Auslöser',date='2026-01-01'))
        db.commit()
    plan(post,project_id=pid,case_id=cid,entry_id=eid,subtask_text='Daten KW{KW} prüfen',subtask_due='2025-12-31')
    with app.app_context():
        assert len(rows('SELECT * FROM task_occurrences'))==3
        assert [t['due'] for t in rows('SELECT due FROM tasks WHERE parent_id IS NULL ORDER BY due')]==['2026-01-01','2026-01-08','2026-01-15']
        assert all(t['project_id']==pid and t['case_id']==cid and t['entry_id']==eid for t in rows('SELECT * FROM tasks'))
        assert one("SELECT due FROM tasks WHERE text='Daten KW02 prüfen'")['due']=='2026-01-07'
        first=one('SELECT task_id FROM task_occurrences ORDER BY due')['task_id']
        assert for_task(first)['frequency']=='weekly'
        assert generate(date(2026,1,1))==0
        # Still open: later calendar weeks must nevertheless be generated.
        assert generate(date(2026,1,22))==3
        assert one('SELECT done FROM tasks WHERE id=?',(first,))['done']==0
        assert generate(date(2026,1,22))==0
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
    assert client.get('/task-series',base_url='https://localhost').status_code==200
    assert client.get('/task-series/1',base_url='https://localhost').status_code==200


def test_pause_resume_skips_paused_dates_and_preserves_existing(app,post,monkeypatch):
    freeze(monkeypatch,'2026-01-01');plan(post)
    with app.app_context():before=rows('SELECT * FROM tasks ORDER BY id')
    assert post('/task-series/1/status',dict(active='0')).status_code==200
    freeze(monkeypatch,'2026-03-01')
    with app.app_context():assert generate()==0
    assert post('/task-series/1/status',dict(active='1')).status_code==200
    with app.app_context():
        assert rows('SELECT * FROM tasks WHERE id<=3 ORDER BY id')==before
        dates=[r['due'] for r in rows('SELECT due FROM task_occurrences ORDER BY due')]
        assert '2026-01-22' not in dates and '2026-03-05' in dates and '2026-03-12' in dates
    assert post('/task-series/1/status',dict(active='x')).status_code==400


def test_edit_occurrence_and_series_have_separate_effects(app,post,monkeypatch):
    freeze(monkeypatch,'2026-01-01');plan(post)
    with app.app_context():first=one('SELECT * FROM tasks ORDER BY id')
    assert post('/task/save',dict(id=first['id'],text='Einmalige Änderung',due=first['due'])).status_code==200
    assert post(f"/task/{first['id']}/toggle").status_code==200
    assert post('/task-series/1/save',dict(text='Bericht KW{KW}',due='2026-01-01',repeat_frequency='weekly',repeat_interval='1')).status_code==200
    with app.app_context():
        assert one('SELECT template FROM task_series')['template']=='Bericht KW{KW}'
        assert one('SELECT text,done FROM tasks WHERE id=?',(first['id'],))==dict(text='Einmalige Änderung',done=1)
        generate(date(2026,1,22))
        assert one("SELECT text FROM tasks WHERE due='2026-01-22'")['text']=='Bericht KW04'
        assert len(rows('SELECT * FROM task_occurrences'))==6


def test_invalid_series_rolls_back_and_auth_is_required(app,client,post,monkeypatch):
    freeze(monkeypatch,'2026-01-01')
    for changes in [dict(due=''),dict(repeat_frequency='daily'),dict(repeat_interval='0'),dict(repeat_interval='1.5'),dict(text='KW{nope}'),dict(repeat_until='2025-12-31')]:
        data=dict(text='KW{KW}',due='2026-01-01',repeat_frequency='weekly',repeat_interval='1');data.update(changes)
        assert post('/task/save',data).status_code==400
    with app.app_context():assert not one('SELECT * FROM tasks') and not one('SELECT * FROM task_series')
    assert app.test_client().get('/task-series',base_url='https://localhost').status_code==302
    assert client.post('/task-series/1/status',data=dict(active='1'),base_url='https://localhost').status_code==400
    assert post('/task-series/99/save',dict(text='Test')).status_code==404
    plan(post)
    assert post('/task/save',dict(id=1,text='Zweite Serie',due='2026-01-01',repeat_frequency='weekly')).status_code==400
    with app.app_context():assert len(rows('SELECT * FROM task_series'))==1


def test_fixed_dates_future_first_task_and_schema_idempotence(app,post,monkeypatch):
    freeze(monkeypatch,'2026-01-01')
    response=post('/task/save',dict(text='Termin {DATUM}',repeat_frequency='dates',repeat_dates='2026-05-01\n2026-07-01'))
    assert response.status_code==200
    with app.app_context():
        assert one('SELECT text,due FROM tasks')==dict(text='Termin 01.05.2026',due='2026-05-01')
        for _ in range(2):init_db()
        assert generate(date(2026,6,20))==1
        assert len(rows('SELECT * FROM task_occurrences'))==2
        assert one('SELECT next_due FROM task_series')['next_due'] is None
        # Deleting a generated task must not recreate the same occurrence.
        db=get_db();db.execute('DELETE FROM tasks WHERE due=?',('2026-07-01',));db.commit()
        assert generate(date(2026,7,1))==0


def test_two_generators_cannot_duplicate_occurrences(app,post,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    freeze(monkeypatch,'2026-01-01');plan(post)
    def run():
        with app.app_context():return generate(date(2026,1,22))
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts=list(pool.map(lambda _:run(),range(2)))
    assert sum(counts)==3
    with app.app_context():
        assert len(rows('SELECT * FROM task_occurrences'))==6
        assert len(rows('SELECT * FROM tasks'))==6
