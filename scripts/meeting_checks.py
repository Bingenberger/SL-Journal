"""Meeting preparation from a presentation through protocol creation."""
import json
from datetime import timedelta
from case_suggestion_checks import main
from journal.db import get_db,one,rows,cipher,atomic_write
from journal.domain import save_entry,save_attachment,now
from journal.meetings import store_events
from journal.integrations import cache_file
from playwright.sync_api import expect


def check(page,app):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    tomorrow=now().date()+timedelta(days=1)
    with app.app_context():
        ev=dict(calendar_key='https://cloud.test/cal/1',uid='demo',occurrence='',title='Besprechung Konrektorin',calendar='Schule',location='Büro',start_at=tomorrow.isoformat()+'T10:00:00+02:00',end_at=tomorrow.isoformat()+'T11:00:00+02:00',date=tomorrow.isoformat(),time='10:00',all_day=0,color=0)
        store_events([ev],now().date().isoformat(),(tomorrow+timedelta(days=2)).isoformat())
        aid=one('SELECT id FROM calendar_events')['id']
        source=save_entry(dict(type='protocol',title='Gestern – Sitzung',date=(now().date()-timedelta(days=1)).isoformat(),body='Originalprotokoll'))
        save_attachment(source,'Präsentation.pptx',b'fake test presentation','application/vnd.openxmlformats-officedocument.presentationml.presentation')
        attachment=one('SELECT id FROM attachments')['id']
        did=get_db().execute("INSERT INTO documents(name,url) VALUES('Weiterer Plan','https://cloud.test/f/1')").lastrowid
        get_db().execute('INSERT INTO entry_documents(entry_id,document_id) VALUES(?,?)',(source,did));get_db().commit()
        atomic_write(cache_file(tomorrow),cipher().encrypt(json.dumps(dict(updated=now().isoformat(),events=[dict(ev,id=aid,end='11:00')])).encode()))
    page.goto(origin+f'/entry/{source}')
    page.locator(f'[data-attachment-id="{attachment}"]').click()
    dialog=page.locator('#meeting-dialog');expect(dialog).to_be_visible()
    expect(dialog.locator('[name=text]')).to_have_value('Präsentation.pptx besprechen')
    field=dialog.locator('.ac-input');field.fill('KONREKTORIN')
    option=dialog.get_by_role('option').filter(has_text='Besprechung Konrektorin');expect(option).to_be_visible();option.click()
    dialog.locator('[name=text]').fill('Präsentation mit Konrektorin besprechen')
    for width in [1440,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
        footer=dialog.locator('.dialog-footer').bounding_box();assert footer['y']+footer['height']<=1000
    dialog.get_by_role('button',name='Vormerken',exact=True).click()
    expect(page).to_have_url(__import__('re').compile(f'/appointment/{aid}#task-'))
    expect(page.locator('.task-row')).to_have_count(1)
    expect(page.locator(f'a[href="/attachment/{attachment}"]')).to_be_visible()
    expect(page.locator(f'a[href="/entry/{source}"]')).to_be_visible()
    page.goto(origin+'/?date='+tomorrow.isoformat())
    page.get_by_role('link',name='1 offene Besprechungspunkte',exact=True).click()
    page.get_by_role('button',name='Protokoll zum Termin anlegen',exact=True).click()
    expect(page.locator('#entry-agenda')).to_contain_text('Präsentation mit Konrektorin besprechen')
    expect(page.locator(f'a[href="/attachment/{attachment}"]')).to_be_visible()
    with app.app_context():
        protocol=one('SELECT protocol_entry_id FROM calendar_events')['protocol_entry_id']
        assert protocol!=source and len(rows('SELECT * FROM attachments'))==1
    page.get_by_role('button',name='Erledigen: Präsentation mit Konrektorin besprechen').click()
    expect(page.locator('.task-row.completed')).to_have_count(1)
    page.goto(origin+f'/appointment/{aid}')
    expect(page.get_by_role('link',name='Protokoll öffnen',exact=True)).to_be_visible()
    expect(page.locator('.panel-heading')).to_contain_text('0 offen')
    page.goto(origin+f'/entry/{source}')
    page.locator(f'[data-meeting-document-id="{did}"][data-plan-meeting]').click()
    field=dialog.locator('.ac-input');field.fill('Konrektorin');dialog.get_by_role('option').first.click()
    dialog.get_by_role('button',name='Vormerken',exact=True).click()
    expect(page.locator('.task-row')).to_have_count(2)
    expect(page.locator(f'a[href="/document/{did}"]')).to_be_visible()
    page.get_by_role('button',name='Punkt vormerken',exact=False).click()
    expect(dialog.locator('.ac-chip')).to_contain_text('Konrektorin')
    dialog.locator('[name=text]').fill('Weiteren Punkt klären')
    dialog.get_by_role('button',name='Vormerken',exact=True).click()
    expect(page.locator('.task-row')).to_have_count(3)
    for width in [1440,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path='docs/screenshots/meeting-preparation-mobile.png',full_page=True)
    page.set_viewport_size({'width':1440,'height':1000})
    page.screenshot(path='docs/screenshots/meeting-preparation-desktop.png',full_page=True)
    print('Präsentation → Termin → Aufgabe → Cockpit → Protokoll, Nextcloud-Verweise und responsive Bedienung geprüft.')


if __name__=='__main__':main(check)
