from email.message import EmailMessage
from playwright.sync_api import expect
from journal.db import get_db,set_setting,one


def check_mail_contacts(page,app,output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        set_setting('imap',{'own_addresses':['leitung@example.org']})
        get_db().commit()
    mail=EmailMessage()
    mail['From']='Leitung <leitung@example.org>'
    mail['To']='Neue Mailperson <neue-mailperson@example.org>'
    mail['Cc']='Weitere Mailperson <weitere-mailperson@example.org>'
    mail['Subject']='Mail-Kontaktvorschläge prüfen'
    mail['Date']='Tue, 22 Sep 2026 10:00:00 +0200'
    mail['Message-ID']='<browser-mail-contacts@example.org>'
    mail.set_content('Eine Testnachricht.')
    page.goto(origin+'/settings')
    page.locator('[name=eml]').set_input_files({'name':'test.eml','mimeType':'message/rfc822','buffer':mail.as_bytes()})
    page.get_by_role('button',name='Mail importieren',exact=True).click()
    expect(page.locator('#toast')).to_contain_text('Mail importiert.')
    page.goto(origin+'/people')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    with app.app_context():
        sid=one("SELECT id FROM contact_suggestions WHERE name LIKE '%neue-mailperson@example.org%'")['id']
        eid=one("SELECT id FROM entries WHERE title='Mail-Kontaktvorschläge prüfen'")['id']
    card=page.locator(f'[data-suggestion-id="{sid}"]')
    expect(card).to_contain_text('Neue Mailperson')
    expect(card).to_contain_text('Mail-Kontaktvorschläge prüfen')
    card.get_by_role('button',name='Als Kontakt übernehmen',exact=True).click()
    dialog=page.locator('#person-dialog')
    expect(dialog.locator('[name=name]')).to_have_value('Neue Mailperson')
    expect(dialog.locator('[name=emails]')).to_have_value('neue-mailperson@example.org')
    dialog.get_by_role('button',name='Kontakt speichern',exact=True).click()
    expect(card).not_to_be_visible()
    page.goto(origin+f'/entry/{eid}')
    expect(page.locator('.metadata')).to_contain_text('Neue Mailperson')
    expect(page.locator('.metadata')).to_contain_text('Weitere Mailperson')
    page.goto(origin+'/')
