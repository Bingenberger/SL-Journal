from email.message import EmailMessage
from email.utils import parseaddr
from journal.db import get_db,one,rows,set_setting,init_db
from journal.integrations import import_message
from journal.participants import suggestions,mail_participants


def message(mid='one'):
    mail=EmailMessage()
    mail['From']='Leitung <leitung@example.org>'
    mail['To']='Anna Müller <anna@example.org>, Ben Beispiel <ben@example.org>'
    mail['Cc']='Anderer Anzeigename <ANNA@example.org>, Carol <carol@example.org>'
    mail['Bcc']='David <david@example.org>'
    mail['Subject']='Kontaktimport'
    mail['Message-ID']=f'<{mid}@example.org>'
    mail['Date']='Tue, 22 Sep 2026 10:00:00 +0200'
    mail.set_content('Testnachricht')
    return mail


def test_all_address_headers_and_known_contacts(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,emails) VALUES('Ben','ben@example.org')")
        db.commit()
        assert import_message(message().as_bytes(),['leitung@example.org'])=='imported'
        proposals=suggestions()
        # Die eigene Adresse wird nicht mehr vorgeschlagen; die übrigen Beteiligten schon.
        assert {p['email'] for p in proposals}=={'anna@example.org','carol@example.org','david@example.org'}
        assert next(p for p in proposals if p['email']=='anna@example.org')['contact_name']=='Anna Müller'
        assert len(rows('SELECT * FROM entry_people'))==1
        assert 'carol@example.org' in one('SELECT recipients FROM entries')['recipients']
        assert import_message(message().as_bytes(),['leitung@example.org'])=='duplicate'
        assert len(suggestions())==3


def test_same_email_different_names_and_acceptance(app,post):
    with app.app_context():
        import_message(message().as_bytes(),['leitung@example.org'])
        mail=message('two');mail.replace_header('To','A. Müller <anna@example.org>')
        import_message(mail.as_bytes(),['leitung@example.org'])
        proposal=next(p for p in suggestions() if p['email']=='anna@example.org')
        assert proposal['entry_count']==2
        sid=proposal['id']
    assert post('/person/save',dict(suggestion_id=sid,name='Anna Müller',emails='anna@example.org')).status_code==200
    with app.app_context():
        person=one("SELECT id FROM people WHERE emails='anna@example.org'")
        assert len(rows('SELECT * FROM entry_people WHERE person_id=?',(person['id'],)))==2
        mail=message('three');import_message(mail.as_bytes(),['leitung@example.org'])
        assert not [p for p in suggestions() if p['email']=='anna@example.org']


def test_forwarded_original_addresses_and_cc(app):
    original=message()
    original.replace_header('From','Extern <extern@example.org>')
    outer=EmailMessage();outer['From']='leitung@example.org';outer['To']='archive@example.org'
    outer.set_content('Weiterleitung');outer.add_attachment(original)
    with app.app_context():
        import_message(outer.as_bytes(),['leitung@example.org'])
        emails={p['email'] for p in suggestions()}
        assert 'extern@example.org' in emails and 'carol@example.org' in emails
        assert 'archive@example.org' not in emails


def test_existing_import_backfill_is_idempotent_preserves_manual_people(app):
    with app.app_context():
        db=get_db()
        eid=db.execute("INSERT INTO entries(date,type,title,sender,recipients,source_key) VALUES('2026-09-22','mail_in','Alt','Sender <sender@example.org>','Recipient <recipient@example.org>','mail:legacy')").lastrowid
        pid=db.execute("INSERT INTO people(name) VALUES('Manuell zugeordnet')").lastrowid
        db.execute('INSERT INTO entry_people VALUES(?,?)',(eid,pid))
        set_setting('mail_participants_v1',False);db.commit()
        init_db();init_db()
        assert {p['email'] for p in suggestions()}=={'sender@example.org','recipient@example.org'}
        assert one('SELECT person_id FROM entry_people')['person_id']==pid


def test_address_names_and_rejected_mail(app):
    label=mail_participants('"Müller, Anna" <anna@example.org>')[0]['label']
    assert parseaddr(label)==('Müller, Anna','anna@example.org')
    with app.app_context():
        assert import_message(message().as_bytes(),['someoneelse@example.org'])=='rejected'
        assert not suggestions()


def test_own_addresses_never_become_contact_suggestions(app,post):
    with app.app_context():
        set_setting('imap',{'own_addresses':['leitung@example.org']})
        get_db().commit()
        assert import_message(message('eigen').as_bytes(),['leitung@example.org'])=='imported'
        vorschlaege={parseaddr(item['name'])[1] for item in suggestions()}
        assert 'leitung@example.org' not in vorschlaege
        assert {'anna@example.org','ben@example.org','carol@example.org','david@example.org'} <= vorschlaege
        assert 'leitung@example.org' not in one('SELECT participants FROM entries')['participants']


def test_existing_own_suggestions_disappear_when_the_address_is_configured(app,post):
    with app.app_context():
        # Altbestand: importiert, bevor die eigene Adresse hinterlegt war.
        assert import_message(message('vorher').as_bytes(),[],enforce_sender=False)=='imported'
        assert 'leitung@example.org' in {parseaddr(item['name'])[1] for item in suggestions()}
    assert post('/settings/save',{'imap_host':'imap.example.org','imap_username':'archiv',
        'imap_password':'geheim','own_addresses':'leitung@example.org'}).status_code==200
    with app.app_context():
        uebrig={parseaddr(item['name'])[1] for item in suggestions()}
        assert 'leitung@example.org' not in uebrig
        assert 'anna@example.org' in uebrig
        assert 'leitung@example.org' not in one('SELECT participants FROM entries')['participants']
