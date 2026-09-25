"""Browser checks for newly typed case names, using an isolated database."""
import logging
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright,expect
from werkzeug.serving import make_server
from journal.app import create_app
from journal.db import get_db,one
from manage import local_certificate


def check_case_suggestions(page,app):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    label='Neue Anfrage Schulhof Browser'
    page.goto(origin+'/')
    page.locator('[data-new-entry]').first.click()
    dialog=page.locator('#entry-dialog')
    dialog.locator('[name=title]').fill('Notiz mit neuem Vorgang')
    field=dialog.locator('[data-autocomplete-field=cases]')
    field.locator('input').fill(label)
    expect(field.get_by_role('option').filter(has_text='Als Vorgangsvorschlag übernehmen')).to_be_visible()
    # Save directly while text is still uncommitted.
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context():
        eid=one("SELECT id FROM entries WHERE title='Notiz mit neuem Vorgang'")['id']
        sid=one('SELECT id FROM case_suggestions WHERE name=?',(label,))['id']
        assert one('SELECT suggestion_id FROM entry_case_suggestions WHERE entry_id=?',(eid,))['suggestion_id']==sid
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    expect(dialog.locator('[data-autocomplete-field=cases] .ac-chip')).to_contain_text(label)
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    page.locator('[data-new-task]').first.click()
    task=page.locator('#task-dialog')
    task.locator('[name=text]').fill('Aufgabe zum Vorgangsvorschlag')
    field=task.locator('[data-autocomplete-field=case_id]')
    field.locator('input').fill(label)
    expect(field.get_by_role('option').filter(has_text=label)).to_be_visible()
    field.get_by_role('option').filter(has_text=label).click()
    task.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(task).not_to_be_visible()
    page.goto(origin+'/tasks?filter=all')
    page.get_by_role('button',name='Aufgabe zum Vorgangsvorschlag',exact=True).click()
    expect(task.locator('[data-autocomplete-field=case_id] .ac-chip')).to_contain_text(label)
    task.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(task).not_to_be_visible()
    page.goto(origin+'/cases')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    card=page.locator(f'[data-case-suggestion-id="{sid}"]')
    expect(card).to_contain_text('1 Einträge · 1 Aufgaben')
    for width in [390,768,1440]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    card.get_by_role('button',name='Als Vorgang übernehmen').click()
    expect(page.locator('#case-dialog [name=title]')).to_have_value(label)
    page.locator('#case-dialog').get_by_role('button',name='Vorgang speichern',exact=True).click()
    expect(page.get_by_role('heading',name=label,exact=True)).to_be_visible()
    with app.app_context():
        cid=one('SELECT id FROM cases WHERE title=?',(label,))['id']
        assert one('SELECT case_id FROM entry_cases WHERE entry_id=?',(eid,))['case_id']==cid
        assert one("SELECT case_id FROM tasks WHERE text='Aufgabe zum Vorgangsvorschlag'")['case_id']==cid


def main(check=None, accept_dialogs=True):
    check=check or check_case_suggestions
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='journal-case-suggestions-') as temp:
        app=create_app({'INSTANCE_PATH':temp,'TESTING':True})
        with app.app_context():
            get_db().execute("INSERT INTO account(id,password,totp,session_version) VALUES(1,'test','test','test')")
            get_db().commit()
        client=app.test_client()
        with client.session_transaction(base_url='https://localhost') as session:
            session.update(auth=True,version='test',csrf='case-test')
        cookie=client.get_cookie('session',domain='localhost').value
        cert,key=local_certificate(Path(temp))
        server=make_server('127.0.0.1',0,app,threaded=True,ssl_context=(str(cert),str(key)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        origin=f'https://localhost:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000})
                context.add_cookies([{'name':'session','value':cookie,'url':origin,'secure':True}])
                page=context.new_page()
                if accept_dialogs: page.on('dialog',lambda dialog:dialog.accept())
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'/')
                check(page,app)
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown()
    print('Isolierte Browserprüfung erfolgreich abgeschlossen.')


if __name__=='__main__':
    main()
