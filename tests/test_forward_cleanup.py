from email.message import EmailMessage
from datetime import date
import pytest
from journal.integrations import parse_forward,import_message,body_text
from journal.db import get_db,one,rows,set_setting
from journal.mail_repair import repair_forwarded_mails


HEADER='Betreff: Ein langer Betreff\nmit einer zweiten Zeile\nDatum: Tue, 22 Sep 2026 09:00:00 +0200\nVon: Person <person@example.org>\nAntwort an: Rueckfrage <reply@example.org>\nAn: leitung@example.org\nCc: Weitere Person <cc@example.org>\n\nOriginaltext\n\nWeitere Nachricht.'
def forwarded():
    mail=EmailMessage()
    mail['From']='leitung@example.org';mail['To']='archiv@example.org'
    mail['Subject']='Fwd: Ein langer Betreff mit einer zweiten Zeile'
    mail['Date']='Tue, 22 Sep 2026 11:00:00 +0200';mail['Message-ID']='<cleanup@example.org>'
    mail.set_content('Zur Ablage\n\n-------- Weitergeleitete Nachricht --------\n'+HEADER)
    return mail


@pytest.mark.parametrize('marker',['-------- Weitergeleitete Nachricht --------','---------- Forwarded message ---------','-----Original Message-----','Anfang der weitergeleiteten Nachricht:'])
def test_multiline_subject_reply_to_and_cc(marker):
    result=parse_forward(marker+'\n'+HEADER)
    assert not result['uncertain']
    assert result['title']=='Ein langer Betreff mit einer zweiten Zeile'
    assert result['sender']=='Person <person@example.org>'
    assert result['recipients']=='leitung@example.org, Weitere Person <cc@example.org>'
    assert result['body']=='Originaltext\n\nWeitere Nachricht.'
    assert result['datetime'].hour==9


def test_outlook_header_only_requires_forward_context():
    text='From: Sender <sender@example.org>\nSent: Tuesday, 22 September 2026 09:00:00 +0200\nTo: leitung@example.org\nSubject: Re: Ursprünglicher Betreff\n\nOriginalinhalt'
    assert parse_forward(text) is None
    result=parse_forward(text,allow_header_only=True)
    assert result['title']=='Re: Ursprünglicher Betreff' and result['body']=='Originalinhalt'


def test_html_and_quoted_headers():
    mail=EmailMessage()
    mail.set_content('<div>----- Forwarded Message -----</div><div><b>From:</b> Sender &lt;sender@example.org&gt;</div><div>Date: Tue, 22 Sep 2026 09:00:00 +0200</div><div>Subject: Original</div><div>To: leitung@example.org</div><p>Text</p>',subtype='html')
    result=parse_forward(body_text(mail))
    assert result and not result['uncertain'] and result['body']=='Text'
    quoted='\n'.join('> '+line for line in ('----- Forwarded Message -----\n'+HEADER).splitlines())
    assert parse_forward(quoted)['body']=='Originaltext\n\nWeitere Nachricht.'


def test_import_uses_original_fields_and_retains_eml(app):
    with app.app_context():
        assert import_message(forwarded().as_bytes(),['leitung@example.org'])=='imported'
        entry=one('SELECT * FROM entries')
        assert entry['title']=='Ein langer Betreff mit einer zweiten Zeile'
        assert entry['sender']=='Person <person@example.org>'
        assert entry['type']=='mail_in' and entry['time']=='09:00'
        assert entry['needs_review']==0
        assert 'Weitergeleitete' not in entry['body']
        assert one("SELECT id FROM attachments WHERE name='Original.eml'")
        assert import_message(forwarded().as_bytes(),['leitung@example.org'])=='duplicate'


def test_repair_only_untouched_imports_preserves_associations(app):
    mail=forwarded()
    with app.app_context():
        set_setting('imap',{'own_addresses':['leitung@example.org']});get_db().commit()
        import_message(mail.as_bytes(),['leitung@example.org'])
        db=get_db()
        db.execute("INSERT INTO projects(name,school_year) VALUES('Manuelle Zuordnung','2026/27')")
        db.execute('INSERT INTO entry_projects VALUES(1,1)')
        db.execute("INSERT INTO tasks(text,entry_id) VALUES('Aufgabe bleibt',1)")
        db.execute('UPDATE entries SET title=?,body=?,sender=?,recipients=?,needs_review=1 WHERE id=1',
            (str(mail['Subject']),f"Archivweiterleitung von {mail['From']}\n\n{body_text(mail)}",'',''))
        db.commit()
        assert repair_forwarded_mails()['recognized']==1
        assert one('SELECT title FROM entries')['title'].startswith('Fwd:')
        assert repair_forwarded_mails(True)['updated']==1
        assert one('SELECT title FROM entries')['title']=='Ein langer Betreff mit einer zweiten Zeile'
        assert one('SELECT entry_id FROM tasks')['entry_id']==1
        assert one('SELECT project_id FROM entry_projects')['project_id']==1
        assert repair_forwarded_mails(True)['updated']==0
        db.execute("UPDATE entries SET title='Eigener Titel'");db.commit()
        result=repair_forwarded_mails(True)
        assert result['edited_skipped']==1
        assert one('SELECT title FROM entries')['title']=='Eigener Titel'
