"""Navigation must warn about user edits, never initial component setup."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import expect
from case_suggestion_checks import main


def check_unsaved_changes(page,app):
    origin=page.url.rstrip('/')
    prompts=[]
    page.on('dialog',lambda dialog:(prompts.append(dialog.type),dialog.accept()))
    def warns():
        return page.evaluate("""() => {
            const event=new Event('beforeunload',{cancelable:true});
            window.dispatchEvent(event);
            return event.defaultPrevented;
        }""")
    assert not warns(), 'Initial component setup marked forms as edited'
    page.locator('#main-navigation a[href="/tasks"]').click()
    expect(page).to_have_url(origin+'/tasks')
    assert prompts==[], prompts
    page.goto(origin+'/')
    page.evaluate("openDialog('task-dialog')")
    assert not warns(), 'Opening an unchanged form must not warn'
    page.locator('#task-dialog [name=text]').fill('Ungespeicherte Aufgabe')
    assert warns(), 'Actual edits must remain protected'
    page.locator('#task-dialog [data-close]').first.click()
    assert prompts==['confirm'], prompts
    assert not warns(), 'Discarded changes must not warn again'
    page.evaluate("openDialog('task-dialog',{repeat_frequency:'dates'})")
    page.locator('#task-dialog [data-repeat-date]').fill('2026-12-01')
    assert warns(), 'Date edits must remain protected'
    page.locator('#task-dialog [data-close]').first.click()
    page.goto(origin+'/settings')
    assert not warns(), 'Unchanged settings must not warn'
    page.locator('[name=imap_host]').fill('imap.example.org')
    assert warns(), 'Settings edits must remain protected'
    print('Navigation ohne Fehlwarnung; echte Aufgaben-, Termin- und Einstellungsänderungen bleiben geschützt.')


if __name__=='__main__':
    main(check_unsaved_changes,accept_dialogs=False)
