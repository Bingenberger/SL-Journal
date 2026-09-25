"""End-to-end checks against an isolated TLS instance with fictional sample data."""
import logging
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright,expect
from werkzeug.serving import make_server
from werkzeug.security import generate_password_hash
from journal.app import create_app
from journal.db import get_db,set_setting,atomic_write,cipher
from journal.demo import seed
from journal.domain import now
from manage import local_certificate
import json
import pyotp


def main():
    output=Path(__file__).resolve().parent.parent/'docs'/'screenshots'
    output.mkdir(parents=True,exist_ok=True)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='journal-browser-') as temp:
        instance=Path(temp)
        app=create_app({'INSTANCE_PATH':str(instance),'TESTING':True})
        secret=pyotp.random_base32()
        with app.app_context():
            seed()
            set_setting('setup_token',generate_password_hash('browser-check-code'))
            set_setting('setup_totp',secret)
            get_db().commit()
            day=now().date().isoformat()
            events=[
                dict(title='Steuergruppe · Leseförderung',date=day,time='09:00',end='10:00',all_day=False,calendar='Schulleitung',color=0,location='Besprechungsraum',uid='demo-1'),
                dict(title='Abstimmung mit dem Förderverein',date=day,time='14:00',end='14:30',all_day=False,calendar='Schulgemeinschaft',color=1,location='',uid='demo-2'),
            ]
            atomic_write(instance/'cache'/f'{day}.enc',cipher().encrypt(json.dumps(dict(updated=now().isoformat(),events=events)).encode()))
        cert,key=local_certificate(instance)
        server=make_server('127.0.0.1',0,app,threaded=True,ssl_context=(str(cert),str(key)))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        origin=f'https://localhost:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1100},locale='de-DE')
                page=context.new_page()
                page.on('dialog',lambda dialog:dialog.accept())
                # Jede Navigation setzt die Seitenvariablen zurück. Die Verstöße werden
                # deshalb sofort nach außen gemeldet und über alle Seiten gesammelt.
                violations=[]
                context.expose_function('journalCspVerstoss',lambda eintrag: violations.append(eintrag))
                page.add_init_script("document.addEventListener('securitypolicyviolation',e=>window.journalCspVerstoss({seite:location.pathname,direktive:e.violatedDirective,quelle:e.sourceFile||''}));")
                errors=[]
                page.on('pageerror',lambda error: errors.append(str(error)))
                page.on('console',lambda message: print('Browser:',message.text) if message.type=='error' else None)
                page.goto(origin+'/setup')
                page.locator('[name=setup_code]').fill('browser-check-code')
                page.get_by_role('button',name='Authenticator einrichten').click()
                expect(page.locator('#qr-image')).to_be_visible()
                page.locator('[name=password]').fill('browser-test-password-very-long')
                page.locator('[name=password_repeat]').fill('browser-test-password-very-long')
                page.locator('[name=otp]').fill(pyotp.TOTP(secret).now())
                page.get_by_role('button',name='Arbeitsbereich einrichten').click()
                # Die Tagesüberschrift trägt den Wochentag; geprüft wird der Sprung ins Cockpit.
                expect(page.locator('.cockpit-date-toolbar h1')).to_be_visible()
                from case_checks import check_cases
                check_cases(page,app,output)
                from protocol_checks import check_protocols
                check_protocols(page,app)
                from editor_checks import check_editor
                check_editor(page,app,output)
                from autocomplete_checks import check_autocomplete, choose
                check_autocomplete(page,app,output)
                from project_suggestion_checks import check_project_suggestions
                check_project_suggestions(page,app,output)
                from institution_checks import check_institutions
                check_institutions(page,app,output)
                from task_group_checks import check_task_groups
                check_task_groups(page,app,output)
                from resource_checks import check_resources
                check_resources(page,app,output)
                from document_checks import check_documents
                check_documents(page,app,output)
                from mail_contact_checks import check_mail_contacts
                check_mail_contacts(page,app,output)
                from forward_checks import check_forward_cleanup
                check_forward_cleanup(page,app,output)
                from pdf_checks import check_pdf_preview
                check_pdf_preview(page,app,output)
                from deletion_checks import check_deletion
                check_deletion(page,app,output)
                page.screenshot(path=str(output/'cockpit-desktop.png'),full_page=True)
                page.get_by_role('button',name='Neuer Eintrag',exact=False).first.click()
                dialog=page.locator('#entry-dialog')
                expect(dialog).to_be_visible()
                dialog.locator('[name=title]').fill('Browserprüfung – Gespräch')
                dialog.locator('[name=type]').select_option('meeting')
                dialog.locator('[data-md-content=body]').fill('**Ergebnis:** Gemeinsam besprochen.\n\nNächsten Schritt festhalten.')
                choose(dialog.locator('[data-autocomplete-field=projects]'),'Schulfest','Schulfest')
                dialog.locator('summary').filter(has_text='Aufgaben aus diesem Eintrag').click()
                dialog.locator('[name=new_task]').fill('Aufgabe aus Browserprüfung')
                dialog.get_by_role('button',name='Eintrag speichern').click()
                expect(page.get_by_role('link',name='Browserprüfung – Gespräch')).to_be_visible()
                page.get_by_role('link',name='Browserprüfung – Gespräch').click()
                expect(page.get_by_role('button',name='Aufgabe aus Browserprüfung',exact=True)).to_be_visible()
                page.get_by_role('button',name='Eintrag bearbeiten').click()
                expect(dialog).to_be_visible()
                expect(dialog.locator('[name=title]')).to_have_value('Browserprüfung – Gespräch')
                expect(dialog.locator('.md-bold')).to_have_text('Ergebnis:')
                expect(dialog.locator('[name=body]')).to_have_value('**Ergebnis:** Gemeinsam besprochen.\n\nNächsten Schritt festhalten.')
                dialog.locator('[name=title]').fill('Browserprüfung – bearbeitet')
                dialog.get_by_role('button',name='Eintrag speichern').click()
                expect(page.get_by_role('heading',name='Browserprüfung – bearbeitet')).to_be_visible()
                page.get_by_role('button',name='Aufgabe aus Browserprüfung',exact=True).click()
                task=page.locator('#task-dialog')
                expect(task).to_be_visible()
                task.locator('[name=due]').fill(day)
                task.get_by_role('button',name='Aufgabe speichern').click()
                expect(task).not_to_be_visible()
                page.get_by_role('button',name='Erledigen: Aufgabe aus Browserprüfung',exact=True).click()
                expect(page.get_by_role('button',name='Wieder öffnen: Aufgabe aus Browserprüfung',exact=True)).to_be_visible()
                page.goto(origin+'/projects')
                page.get_by_role('button',name='Neues Projekt',exact=False).click()
                project=page.locator('#project-dialog')
                project.locator('[name=name]').fill('Browserprojekt')
                project.get_by_role('button',name='Projekt speichern').click()
                expect(page.get_by_role('heading',name='Browserprojekt',exact=True)).to_be_visible()
                page.get_by_role('button',name='Projekt abschließen',exact=True).click()
                close=page.locator('#close-dialog')
                close.locator('[name=template]').check()
                close.get_by_role('button',name='Abschließen',exact=True).click()
                expect(page.get_by_role('button',name='Projekt wieder öffnen')).to_be_visible()
                page.goto(origin+'/')
                page.get_by_role('button',name='Protokoll anlegen',exact=False).first.click()
                expect(page.get_by_role('heading',name='Steuergruppe · Leseförderung',exact=True)).to_be_visible()
                protocol_url=page.url
                page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
                expect(dialog.locator('[name=title]')).to_have_value('Steuergruppe · Leseförderung')
                expect(dialog.locator('[name=date]')).to_have_value(day)
                expect(dialog.locator('[name=type]')).to_have_value('protocol')
                dialog.get_by_role('button',name='Abbrechen').click()
                page.goto(origin+'/')
                page.get_by_role('button',name='Protokoll öffnen',exact=True).first.click()
                expect(page).to_have_url(protocol_url)
                page.wait_for_load_state('load')
                page.keyboard.press('a')
                expect(task).to_be_visible()
                task.get_by_role('button',name='Abbrechen').click()
                for name,width,height in [('ipad',1024,1366),('ipad-portrait',768,1024),('mobile',390,844)]:
                    page.set_viewport_size({'width':width,'height':height})
                    for path in ['/','/projects','/settings','/entries','/tasks']:
                        page.goto(origin+path)
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),(name,path,'horizontal overflow')
                    page.goto(origin+'/')
                    page.screenshot(path=str(output/f'cockpit-{name}.png'),full_page=True)
                    page.locator('.topbar [data-new-entry]').click()
                    expect(dialog).to_be_visible()
                    assert dialog.evaluate('(e) => e.getBoundingClientRect().right <= innerWidth')
                    dialog.get_by_role('button',name='Abbrechen').click()
                # Style-Attribute sind bewusst gesperrt; der mitgelieferte Editor setzt
                # zwei (tab-size, pointer-events), die journal/static/style.css ersetzt.
                # Alles andere wäre ein echter Fund.
                unerwartet=[v for v in violations if v['direktive']!='style-src-attr']
                assert not unerwartet,unerwartet
                if violations:
                    print('Hinweis: '+str(len(violations))+' blockierte Style-Attribute auf '
                          +', '.join(sorted({v['seite'] for v in violations}))+' (im Stylesheet abgedeckt).')
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
    print('Browserprüfungen bestanden: Einrichtung, QR, Eintrag, Bearbeitung, Aufgabe, Projektabschluss, Terminübernahme, Tastenkürzel; Desktop/iPad/Mobil ohne horizontalen Überlauf.')
    print('Screenshots: '+str(output))


if __name__=='__main__':
    main()
