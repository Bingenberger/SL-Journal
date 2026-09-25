from datetime import date
from email.message import EmailMessage
from types import SimpleNamespace
from journal.db import get_db,one,rows,set_setting
from journal.integrations import import_message,parse_forward,cached_events,sync_calendar,sync_all

def make_mail(sender='leitung@example.org',subject='[Schulfest] Helferplan',body='Ein neuer Plan',mid='<test@example.org>'):
    message=EmailMessage();message['From']=sender;message['To']='archiv@example.org';message['Subject']=subject;message['Date']='Mon, 21 Sep 2026 09:15:00 +0200';message['Message-ID']=mid;message.set_content(body)
    return message

def test_import_filter_direction_tags_dedup_contacts(app):
    with app.app_context():
        db=get_db();db.execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')")
        db.execute("INSERT INTO people(name,emails) VALUES('Leitung','leitung@example.org')");db.commit()
        assert import_message(make_mail('spam@example.org').as_bytes(),['leitung@example.org'])=='rejected'
        good=make_mail();good.add_attachment(b'Sensibler Plan',maintype='application',subtype='pdf',filename='plan.pdf')
        assert import_message(good.as_bytes(),['leitung@example.org'])=='imported'
        entry=one('SELECT * FROM entries')
        assert entry['type']=='mail_out' and entry['tags']=='Schulfest'
        assert len(rows('SELECT * FROM entry_projects'))==1
        assert len(rows('SELECT * FROM entry_people'))==1
        assert len(rows('SELECT * FROM attachments'))==2
        assert import_message(good.as_bytes(),['leitung@example.org'])=='duplicate'

def test_forward_parsers_and_uncertain_fields(app):
    block='Von: Person <person@example.org>\nDatum: Mon, 21 Sep 2026 08:00:00 +0200\nBetreff: Nachricht\nAn: leitung@example.org\n\nOriginalinhalt'
    for marker in ['-------- Weitergeleitete Nachricht --------','Anfang der weitergeleiteten Nachricht:']:
        parsed=parse_forward(marker+'\n'+block)
        assert parsed['sender']=='Person <person@example.org>'
        assert parsed['body']=='Originalinhalt' and not parsed['uncertain']
    with app.app_context():
        message=make_mail(body='Anfang der weitergeleiteten Nachricht:\nVon: unklar\n\nHallo')
        assert import_message(message.as_bytes(),['leitung@example.org'])=='imported'
        entry=one('SELECT * FROM entries')
        assert entry['sender']=='' and entry['needs_review']==1 and entry['type']=='mail_in'

def test_forward_as_eml_retains_original(app):
    original=make_mail('extern@example.org',mid='<original@example.org>')
    original.add_attachment(b'PDF Inhalt',maintype='application',subtype='pdf',filename='Anlage.pdf')
    outer=make_mail(mid='<wrapper@example.org>');outer.add_attachment(original)
    with app.app_context():
        assert import_message(outer.as_bytes(),['leitung@example.org'])=='imported'
        entry=one('SELECT * FROM entries')
        assert entry['sender']=='extern@example.org' and entry['type']=='mail_in'
        assert len(rows('SELECT * FROM attachments'))==2

def test_calendar_readonly_multiday_and_failure_cache(app,monkeypatch):
    import caldav
    from icalendar import Calendar
    event=Calendar.from_ical('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:abc\r\nDTSTART;VALUE=DATE:20260921\r\nDTEND;VALUE=DATE:20260923\r\nSUMMARY:Schulprojekt\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
    class CalendarStub:
        name='Schule'
        def search(self,**kwargs):
            assert kwargs['event'] and not kwargs['expand']
            return [SimpleNamespace(icalendar_instance=event)]
    class ClientStub:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def principal(self): return self
        def calendars(self): return [CalendarStub()]
    monkeypatch.setattr(caldav,'DAVClient',ClientStub)
    with app.app_context():
        set_setting('caldav',{'url':'https://cloud.example.org','username':'user','password':'secret'});get_db().commit()
        assert sync_calendar(date(2026,9,21),3)=='1 Kalender aktualisiert'
        assert len(cached_events(date(2026,9,21))[0])==1
        assert len(cached_events(date(2026,9,22))[0])==1
        assert not cached_events(date(2026,9,23))[0]
        def fail(**kwargs): raise OSError('SECRET MUST NOT LEAK')
        monkeypatch.setattr(caldav,'DAVClient',fail)
        result=sync_all()
        assert 'SECRET MUST NOT LEAK' not in result
        assert len(cached_events(date(2026,9,21))[0])==1

def test_german_forward_dates():
    from journal.integrations import mail_date
    for value in ['21. September 2026 um 09:15:00 MESZ','Montag, 21. September 2026 09:15','21.09.2026, 09:15']:
        result=mail_date(value)
        assert result.date()==date(2026,9,21) and result.hour==9
    assert mail_date('unklar') is None
