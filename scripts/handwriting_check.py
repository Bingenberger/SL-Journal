"""Isolated browser exercise for the local Excalidraw integration."""
import json
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
from autocomplete_checks import choose


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='journal-drawing-') as temp:
        app=create_app({'INSTANCE_PATH':temp,'TESTING':True})
        with app.app_context():
            get_db().execute("INSERT INTO account(id,password,totp,session_version) VALUES(1,'test','test','test')")
            get_db().commit()
        client=app.test_client()
        with client.session_transaction(base_url='https://localhost') as session:
            session.update(auth=True,version='test',csrf='drawing-test')
        cookie=client.get_cookie('session',domain='localhost').value
        cert,key=local_certificate(Path(temp))
        server=make_server('127.0.0.1',0,app,threaded=True,ssl_context=(str(cert),str(key)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        origin=f'https://localhost:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(ignore_https_errors=True,viewport={'width':1280,'height':900})
                context.add_cookies([{'name':'session','value':cookie,'url':origin,'secure':True}])
                page=context.new_page()
                page.on('dialog',lambda dialog:dialog.accept())
                errors=[];external=[];violations=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('console',lambda m:print(m.type,m.text[:250]) if m.type=='error' else None)
                page.on('request',lambda r:external.append(r.url) if not r.url.startswith((origin,'data:','blob:')) else None)
                # Über alle Navigationen hinweg melden, nicht erst am Ende der Seite auslesen.
                context.expose_function('journalCspVerstoss',lambda eintrag: violations.append(eintrag['seite']+': '+eintrag['direktive']))
                page.add_init_script("document.addEventListener('securitypolicyviolation',e=>window.journalCspVerstoss({seite:location.pathname,direktive:e.violatedDirective}));")
                page.goto(origin+'/handwriting/new')
                expect(page.locator('#sheet-save')).to_be_enabled(timeout=20000)
                page.locator('#sheet-title').fill('Handschrift Browser')
                canvas=page.locator('canvas.interactive')
                expect(canvas).to_be_visible()
                bounds=canvas.bounding_box()
                x=bounds['x']+bounds['width']*.5;y=bounds['y']+bounds['height']*.5
                page.mouse.move(x,y);page.mouse.down()
                page.mouse.move(x+40,y+30,steps=10)
                page.mouse.move(x+90,y-10,steps=10);page.mouse.up()
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=20000)
                with app.app_context():
                    drawing=one('SELECT * FROM drawings')
                    scene=json.loads(drawing['scene'])
                    assert any(e['type']=='freedraw' and len(e['points'])>2 for e in scene['elements'])
                    did=drawing['id'];eid=drawing['entry_id']
                page.reload()
                expect(page.locator('#sheet-save')).to_be_enabled()
                expect(page.locator('#sheet-title')).to_have_value('Handschrift Browser')
                # Real pen pointer events (pressure and stylus pointer type) in Chromium.
                cdp=context.new_cdp_session(page)
                for event in [
                    dict(type='mousePressed',x=x,y=y+100,button='left',buttons=1,clickCount=1,force=.3),
                    dict(type='mouseMoved',x=x+70,y=y+130,button='left',buttons=1,force=.8),
                    dict(type='mouseReleased',x=x+70,y=y+130,button='left',buttons=0,clickCount=1,force=0),
                ]:
                    cdp.send('Input.dispatchMouseEvent',dict(event,pointerType='pen'))
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=20000)
                with app.app_context():
                    updated=one('SELECT * FROM drawings WHERE id=?',(did,))
                    assert updated['revision']>drawing['revision']
                    assert len([e for e in json.loads(updated['scene'])['elements'] if not e.get('isDeleted')])==2
                page.keyboard.press('Control+z')
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=10000)
                with app.app_context():
                    undone=json.loads(one('SELECT scene FROM drawings WHERE id=?',(did,))['scene'])
                    assert len([e for e in undone['elements'] if not e.get('isDeleted')])==1
                page.keyboard.press('Control+Shift+z')
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=10000)
                with app.app_context():
                    redone=json.loads(one('SELECT scene FROM drawings WHERE id=?',(did,))['scene'])
                    assert len([e for e in redone['elements'] if not e.get('isDeleted')])==2
                page.keyboard.press('e')
                for event in [
                    dict(type='mousePressed',x=x+40,y=y+117,button='left',buttons=1,clickCount=1,force=.5),
                    dict(type='mouseMoved',x=x+70,y=y+130,button='left',buttons=1,force=.5),
                    dict(type='mouseReleased',x=x+70,y=y+130,button='left',buttons=0,clickCount=1,force=0),
                ]:
                    cdp.send('Input.dispatchMouseEvent',dict(event,pointerType='pen'))
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=10000)
                with app.app_context():
                    erased=json.loads(one('SELECT scene FROM drawings WHERE id=?',(did,))['scene'])
                    assert len([e for e in erased['elements'] if not e.get('isDeleted')])==1
                page.keyboard.press('Control+z')
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=10000)
                page.keyboard.press('t')
                page.mouse.click(x,y+200)
                page.keyboard.type('Besprechung 2026')
                page.keyboard.press('Escape')
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=10000)
                with app.app_context():
                    with_text=json.loads(one('SELECT scene FROM drawings WHERE id=?',(did,))['scene'])
                    assert any(e.get('text')=='Besprechung 2026' for e in with_text['elements'])
                page.locator('#sheet-back').click()
                expect(page.locator('.handwriting-sheet img')).to_be_visible()
                # Die Vorschau lädt verzögert; erst auf das Laden warten, dann prüfen.
                page.locator('.handwriting-sheet img').evaluate('(e)=>e.complete||new Promise(done=>{e.onload=done;e.onerror=done})')
                assert page.locator('.handwriting-sheet img').evaluate('(e)=>e.complete&&e.naturalWidth>0')
                from drawing_link_checks import check_drawing_links
                check_drawing_links(page,app,eid,did)
                with app.app_context():
                    pid=get_db().execute("INSERT INTO projects(name,school_year) VALUES('Zeichenprojekt','2026/27')").lastrowid
                    case_id=get_db().execute("INSERT INTO cases(title) VALUES('Handschriftvorgang')").lastrowid
                    get_db().commit()
                page.reload()
                classification=page.locator('#entry-classification')
                projects=classification.locator('[data-autocomplete-field=projects]')
                tags=classification.locator('[data-autocomplete-field=tags]')
                choose(projects,'Zeichenprojekt','Zeichenprojekt')
                choose(classification.locator('[data-autocomplete-field=cases]'),'Handschriftvorgang','Handschriftvorgang')
                projects.locator('.ac-input').fill('Neue Skizzenidee')
                projects.locator('.ac-input').press('Enter')
                tags.locator('.ac-input').fill('Handnotiz')
                tags.locator('.ac-input').press('Enter')
                with page.expect_navigation():
                    classification.get_by_role('button',name='Zuordnung speichern').click()
                expect(projects.locator('.ac-chip')).to_have_count(2)
                expect(tags.locator('.ac-chip')).to_contain_text('Handnotiz')
                with app.app_context():
                    assert one('SELECT project_id FROM entry_projects WHERE entry_id=?',(eid,))['project_id']==pid
                    assert one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']=='Handnotiz'
                    assert one('SELECT case_id FROM entry_cases WHERE entry_id=?',(eid,))['case_id']==case_id
                expect(page.get_by_role('heading',name='Nextcloud-Dokumente')).to_have_count(0)
                expect(page.get_by_role('heading',name='Anhänge',exact=False)).to_have_count(0)
                page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
                expect(page.locator('#entry-dialog [name=attachments]')).not_to_be_visible()
                page.get_by_role('button',name='Abbrechen',exact=True).click()
                page.reload()
                expect(projects.locator('.ac-chip')).to_have_count(2)
                expect(projects.locator('.ac-chip').filter(has_text='Neue Skizzenidee')).to_be_visible()
                with page.expect_navigation():
                    classification.get_by_role('button',name='Zuordnung speichern').click()
                expect(tags.locator('.ac-chip')).to_contain_text('Handnotiz')
                page.get_by_role('link',name='Weiterschreiben',exact=True).click()
                expect(page.locator('#sheet-save')).to_be_enabled()
                # A failed request must remain unsaved and recover on explicit retry.
                page.route('**/handwriting/save',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Test: Verbindung unterbrochen"}'))
                page.locator('#sheet-title').fill('Nach Verbindungsausfall')
                expect(page.locator('#sheet-status')).to_have_text('Test: Verbindung unterbrochen',timeout=10000)
                page.unroute('**/handwriting/save')
                page.locator('#sheet-save').click()
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert')
                with page.expect_download() as download:
                    page.locator('#sheet-download').click()
                assert download.value.suggested_filename.endswith('.excalidraw')
                page.screenshot(path='docs/screenshots/handwriting-desktop.png')
                for width,height in [(768,1024),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height})
                    expect(canvas).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
                assert not external,external[:5]
                assert not violations,sorted(set(violations))
                Path('docs/screenshots').mkdir(parents=True,exist_ok=True)
                recenter=page.get_by_role('button',name='Zurück zum Inhalt',exact=True)
                if recenter.is_visible():recenter.click()
                page.screenshot(path='docs/screenshots/handwriting-mobile.png')
                browser.close()
                print('Handschrift geprüft: Maus und Stift, Autospeichern, Wiederöffnen, Vorschau, Ausfall und Wiederholung, Export, Mobilansicht; keine externen Requests oder CSP-Verstöße.')
        finally:server.shutdown()


if __name__=='__main__':main()
