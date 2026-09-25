from datetime import date,datetime
from types import SimpleNamespace
from icalendar import Calendar
from journal.db import get_db,one,rows,set_setting,init_db
from journal.domain import save_entry,save_attachment
from journal.meetings import store_events,create_point,create_protocol,points,get,occurrence_key
from journal.integrations import sync_calendar,cached_events


def event(**changes):
    return dict(calendar_key='https://cloud.test/cal/1',uid='meeting-1',occurrence='',title='Termin Konrektorin',calendar='Schule',location='Büro',start_at='2026-09-25T10:00:00+02:00',end_at='2026-09-25T11:00:00+02:00',date='2026-09-25',time='10:00',all_day=0,color=0,**changes)


def setup(app):
    with app.app_context():
        store_events([event()],'2026-09-01','2026-10-01')
        aid=one('SELECT id FROM calendar_events')['id']
        source=save_entry(dict(type='protocol',date='2026-09-24',title='Gestern',body='Original',agenda='Agenda'))
        save_attachment(source,'Präsentation.pdf',b'original','application/pdf')
        attachment=one('SELECT id FROM attachments')['id']
        get_db().commit()
        return aid,source,attachment


def test_point_protocol_and_resource_preservation(app,client,post):
    aid,source,attachment=setup(app)
    data=dict(event_id=aid,source_entry_id=source,attachment_id=attachment,text='Präsentation besprechen',request_key='unique')
    r=post('/meeting-point/save',data);assert r.status_code==200
    assert post('/meeting-point/save',data).status_code==200
    with app.app_context():
        assert len(rows('SELECT * FROM tasks'))==1
        tid=one('SELECT id FROM tasks')['id']
        assert get(aid)['open_count']==1
        assert one('SELECT due,entry_id FROM tasks')['due']=='2026-09-25'
    r=post(f'/appointment/{aid}/protocol');assert r.status_code==200
    eid=int(r.json['redirect'].split('/')[-1])
    assert post(f'/appointment/{aid}/protocol').json['redirect']==r.json['redirect']
    with app.app_context():
        protocol=one('SELECT * FROM entries WHERE id=?',(eid,))
        assert protocol['type']=='protocol' and 'Präsentation besprechen' in protocol['agenda']
        assert one('SELECT entry_id FROM attachments')['entry_id']==source
        assert one('SELECT entry_id FROM tasks')['entry_id']==source
        assert len(rows('SELECT * FROM attachments'))==1
        assert one('SELECT body FROM entries WHERE id=?',(source,))['body']=='Original'
    html=client.get(f'/entry/{eid}',base_url='https://localhost').text
    assert f'/attachment/{attachment}' in html and 'Präsentation besprechen' in html
    assert post(f'/task/{tid}/toggle').status_code==200
    with app.app_context():assert get(aid)['open_count']==0


def test_reschedule_cancel_and_recurrence_isolation(app):
    with app.app_context():
        ev=event();second=dict(ev,occurrence='2026-10-02T08:00:00+00:00',date='2026-10-02',start_at='2026-10-02T10:00:00+02:00',end_at='2026-10-02T11:00:00+02:00')
        ev['occurrence']='2026-09-25T08:00:00+00:00'
        store_events([ev,second],'2026-09-01','2026-11-01')
        ids=[e['id'] for e in rows('SELECT * FROM calendar_events ORDER BY date')]
        _,tid=create_point(dict(event_id=ids[0],text='Punkt',request_key='one'));get_db().commit()
        ev.update(date='2026-09-26',start_at='2026-09-26T12:00:00+02:00',end_at='2026-09-26T13:00:00+02:00',time='12:00',title='Neuer Titel')
        store_events([ev,second],'2026-09-01','2026-11-01')
        assert get(ids[0])['title']=='Neuer Titel' and get(ids[0])['open_count']==1
        assert not points(ids[1])
        assert one('SELECT due FROM tasks WHERE id=?',(tid,))['due']=='2026-09-26'
        get_db().execute("UPDATE tasks SET due='2026-12-01' WHERE id=?",(tid,));get_db().commit()
        ev.update(date='2026-09-27',start_at='2026-09-27T12:00:00+02:00',end_at='2026-09-27T13:00:00+02:00')
        store_events([ev,second],'2026-09-01','2026-11-01')
        assert one('SELECT due FROM tasks WHERE id=?',(tid,))['due']=='2026-12-01'
        store_events([second],'2026-09-01','2026-11-01')
        assert get(ids[0])['state']=='missing' and get(ids[0])['open_count']==1
        store_events([ev,second],'2026-09-01','2026-11-01')
        assert get(ids[0])['state']=='active' and len(rows('SELECT * FROM calendar_events'))==2
        assert occurrence_key(datetime.fromisoformat('2026-09-25T10:00:00+02:00'))==occurrence_key(datetime.fromisoformat('2026-09-25T08:00:00+00:00'))


def test_validation_auth_csrf_and_deletions(app,client,post):
    aid,source,attachment=setup(app)
    good=dict(event_id=aid,source_entry_id=source,attachment_id=attachment,text='Punkt',request_key='valid')
    for bad in [dict(good,event_id=999),dict(good,attachment_id=999),dict(good,source_entry_id=999),dict(good,text=''),dict(good,request_key=''),dict(good,text='a'*2001)]:
        assert post('/meeting-point/save',bad).status_code==400
    assert client.post('/meeting-point/save',data=good,base_url='https://localhost').status_code==400
    assert app.test_client().get('/api/autocomplete/appointments',base_url='https://localhost').status_code==302
    with app.app_context():assert not rows('SELECT * FROM tasks')
    assert post('/meeting-point/save',good).status_code==200
    assert post(f'/entry/{source}/delete').status_code==200
    with app.app_context():
        point=one('SELECT * FROM meeting_points')
        assert point['source_entry_id'] is None and point['attachment_id'] is None
        assert get(aid)['open_count']==1
        assert point['resource_label']=='Präsentation.pdf'
        init_db();init_db()
        assert len(rows('SELECT * FROM meeting_points'))==1
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()


def test_nextcloud_document_and_completed_agenda(app,post):
    aid,source,_=setup(app)
    with app.app_context():
        db=get_db();did=db.execute("INSERT INTO documents(name,url) VALUES('Plan','https://cloud.test/f/1')").lastrowid
        db.execute('INSERT INTO entry_documents(entry_id,document_id) VALUES(?,?)',(source,did));db.commit()
    assert post('/meeting-point/save',dict(event_id=aid,source_entry_id=source,document_id=did,text='Plan besprechen',request_key='doc')).status_code==200
    with app.app_context():
        db=get_db();tid=one('SELECT id FROM tasks')['id'];db.execute('UPDATE tasks SET done=1 WHERE id=?',(tid,))
        eid=create_protocol(aid);db.commit()
        assert one('SELECT agenda FROM entries WHERE id=?',(eid,))['agenda']==''
        assert len(points(aid))==1
        assert one('SELECT url FROM documents WHERE id=?',(did,))['url']=='https://cloud.test/f/1'


def test_real_series_expansion_and_single_event_moves(app,monkeypatch):
    import caldav
    raw=['BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:series\r\nDTSTART:20260925T080000Z\r\nDTEND:20260925T090000Z\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\nSUMMARY:Wiederholung\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n', 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:single\r\nDTSTART:20260925T120000Z\r\nDTEND:20260925T130000Z\r\nSUMMARY:Einzeltermin\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n']
    class Cal:
        name='Schule';url='https://cloud.test/calendar/1'
        def search(self,**kwargs):
            assert kwargs['expand'] is False
            return [SimpleNamespace(icalendar_instance=Calendar.from_ical(value)) for value in raw]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def principal(self):return self
        def calendars(self):return [Cal()]
    monkeypatch.setattr(caldav,'DAVClient',Client)
    with app.app_context():
        set_setting('caldav',{'url':'https://cloud.test','username':'user','password':'secret'});get_db().commit()
        sync_calendar(date(2026,9,24),30)
        assert len(rows('SELECT * FROM calendar_events'))==3
        original=one("SELECT id FROM calendar_events WHERE uid='single'")['id']
        create_point(dict(event_id=original,text='Punkt',request_key='single'));get_db().commit()
        raw[1]=raw[1].replace('20260925','20260926')
        sync_calendar(date(2026,9,24),30)
        assert one("SELECT id FROM calendar_events WHERE uid='single'")['id']==original
        assert get(original)['date']=='2026-09-26'
        assert len(cached_events(date(2026,9,25))[0])==1
        assert get(original)['open_count']==1
        before=[dict(e) for e in rows('SELECT * FROM calendar_events')]
        def fail(**kwargs):raise OSError('SECRET')
        monkeypatch.setattr(caldav,'DAVClient',fail)
        try:sync_calendar(date(2026,9,24),30)
        except OSError:pass
        assert before==[dict(e) for e in rows('SELECT * FROM calendar_events')]


def test_calendar_refresh_endpoint_and_error_privacy(app,client,post,monkeypatch):
    aid,_,_=setup(app)
    with app.app_context():
        set_setting('caldav',{'url':'https://cloud.test','username':'user','password':'private'});get_db().commit()
    def refresh(start,days):
        assert start==date(2026,9,25) and days==90
        return '1 Kalender aktualisiert'
    monkeypatch.setattr('journal.integrations.sync_calendar',refresh)
    assert post('/appointments/sync',{'start_date':'2026-09-25'}).status_code==200
    def fail(*args):raise OSError('PRIVATE CALENDAR TOKEN')
    monkeypatch.setattr('journal.integrations.sync_calendar',fail)
    response=post('/appointments/sync',{'start_date':'2026-09-25'})
    assert response.status_code==400 and 'PRIVATE' not in response.text
    with app.app_context():assert get(aid)['state']=='active'
    assert client.post('/appointments/sync',base_url='https://localhost').status_code==400
    suggestions=client.get('/api/autocomplete/appointments?q=KONREKTORIN&from=2026-09-01',base_url='https://localhost').json
    assert suggestions['items'][0]['id']==aid


def test_existing_manual_protocol_is_reused_without_overwrite(app,post):
    aid,_,_=setup(app)
    with app.app_context():
        eid=save_entry(dict(type='protocol',title='TERMIN KONREKTORIN',date='2026-09-25',time='10:00',body='Bestehender Inhalt',agenda='Meine Tagesordnung'));get_db().commit()
    response=post(f'/appointment/{aid}/protocol')
    assert response.json['redirect']==f'/entry/{eid}'
    with app.app_context():
        assert get(aid)['protocol_entry_id']==eid
        p=one('SELECT * FROM entries WHERE id=?',(eid,));assert p['body']=='Bestehender Inhalt' and p['agenda']=='Meine Tagesordnung'
        get_db().execute("UPDATE entries SET title='Anderer Titel' WHERE id=?",(eid,));get_db().commit()
    assert post(f'/appointment/{aid}/protocol').json['redirect']==f'/entry/{eid}'


def test_ambiguous_protocols_require_choice_and_ignore_wrong_time(app,post):
    aid,_,_=setup(app)
    with app.app_context():
        ids=[save_entry(dict(type='protocol',title='Termin Konrektorin',date='2026-09-25',time=t,body='Bestehend')) for t in ['10:00','','16:00']];get_db().commit()
        count=one('SELECT count(*) n FROM entries')['n']
    response=post(f'/appointment/{aid}/protocol')
    assert 'Vorhandenes Protokoll auswählen' in response.text
    with app.app_context():assert one('SELECT count(*) n FROM entries')['n']==count
    assert post(f'/appointment/{aid}/protocol',dict(existing_id=ids[2])).status_code==400
    assert post(f'/appointment/{aid}/protocol',dict(existing_id=ids[0])).json['redirect']==f'/entry/{ids[0]}'


def test_old_calendar_cache_existing_protocol_and_renamed_retry(app,client,post):
    import json
    from journal.db import cipher,atomic_write
    from journal.integrations import cache_file
    from journal.meetings import legacy_protocol_key
    from journal.domain import now
    ev=dict(uid='old',calendar='Schule',title='Älterer Termin',date='2026-09-25',time='09:00',all_day=False,end='10:00',color=0,location='')
    with app.app_context():
        eid=save_entry(dict(type='protocol',title=ev['title'],date=ev['date'],time=ev['time'],body='Notizen'))
        atomic_write(cache_file(date(2026,9,25)),cipher().encrypt(json.dumps(dict(updated=now().isoformat(),events=[ev])).encode()));get_db().commit()
    data=dict(date=ev['date'],event_index=0,event_key=legacy_protocol_key(ev))
    assert post('/calendar/protocol',data).json['redirect']==f'/entry/{eid}'
    with app.app_context():
        get_db().execute("UPDATE entries SET title='Umbenannt' WHERE id=?",(eid,));get_db().commit()
    assert post('/calendar/protocol',data).json['redirect']==f'/entry/{eid}'
    assert post('/calendar/protocol',dict(data,event_key='stale')).status_code==400
    assert 'Protokoll öffnen' in client.get('/?date=2026-09-25',base_url='https://localhost').text


def test_distinct_occurrences_at_same_actual_time_keep_separate_protocols(app):
    with app.app_context():
        first=event();first['occurrence']='2026-09-24T08:00:00Z'
        second=dict(first,occurrence='2026-09-25T08:00:00Z')
        store_events([first,second],'2026-09-01','2026-10-01')
        ids=[e['id'] for e in rows('SELECT id FROM calendar_events ORDER BY id')]
        a=create_protocol(ids[0]);b=create_protocol(ids[1]);get_db().commit()
        assert a!=b
        assert create_protocol(ids[0])==a and create_protocol(ids[1])==b
