from email.message import EmailMessage
from playwright.sync_api import expect
from journal.db import one


def check_forward_cleanup(page,app,output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    mail=EmailMessage()
    mail['From']='leitung@example.org';mail['To']='archiv@example.org'
    mail['Subject']='Fwd: Originalbetreff mit Fortsetzung'
    mail['Date']='Tue, 22 Sep 2026 11:00:00 +0200'
    mail['Message-ID']='<browser-forward-cleanup@example.org>'
    mail.set_content('Zur Ablage\n\n-------- Weitergeleitete Nachricht --------\nBetreff: Originalbetreff\nmit Fortsetzung\nDatum: Tue, 22 Sep 2026 09:00:00 +0200\nVon: Ursprüngliche Person <ursprung@example.org>\nAntwort an: ursprung@example.org\nAn: leitung@example.org\n\nDies ist der ursprüngliche Nachrichtentext.')
    page.goto(origin+'/settings')
    page.locator('[name=eml]').set_input_files({'name':'weiterleitung.eml','mimeType':'message/rfc822','buffer':mail.as_bytes()})
    page.get_by_role('button',name='Mail importieren',exact=True).click()
    expect(page.locator('#toast')).to_contain_text('Mail importiert.')
    with app.app_context(): eid=one("SELECT id FROM entries WHERE title='Originalbetreff mit Fortsetzung'")['id']
    page.goto(origin+f'/entry/{eid}')
    expect(page.get_by_role('heading',name='Originalbetreff mit Fortsetzung',exact=True)).to_be_visible()
    expect(page.locator('#entry-body')).to_have_text('Dies ist der ursprüngliche Nachrichtentext.')
    expect(page.locator('.metadata')).to_contain_text('ursprung@example.org')
    expect(page.locator('.page-heading')).to_contain_text('09:00')
    expect(page.get_by_role('link',name='Original.eml',exact=False)).to_be_visible()
    page.goto(origin+'/')
