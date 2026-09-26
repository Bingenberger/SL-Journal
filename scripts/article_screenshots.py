"""Capture editorial screenshots using a fresh, wholly fictional instance."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    from playwright.sync_api import sync_playwright,expect
    from werkzeug.serving import make_server
    output=ROOT/'docs/screenshots/artikel';output.mkdir(parents=True,exist_ok=True)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='journal-article-') as folder:
        instance=Path(folder)/'demo'
        subprocess.run([sys.executable,str(ROOT/'scripts/create_video_demo.py'),'--directory',str(instance)],check=True,capture_output=True)
        os.environ.update(JOURNAL_INSTANCE=str(instance),JOURNAL_KEY_FILE=str(instance/'master.key'),JOURNAL_TRUST_PROXY='0')
        from journal.app import create_app
        from journal.db import get_db,one
        from manage import local_certificate
        app=create_app()
        with app.app_context():
            db=get_db()
            note=one("SELECT id FROM entries WHERE title LIKE 'Wochenpost KW %'")['id']
            mail=one("SELECT id FROM entries WHERE title='Bücherei bringt Lesekisten vorbei'")['id']
            db.execute('INSERT INTO entry_resource_links(owner_entry_id,entry_id) VALUES(?,?)',(note,mail))
            version=one('SELECT session_version FROM account')['session_version'];db.commit()
        client=app.test_client()
        with client.session_transaction(base_url='https://localhost') as session:
            session.update(auth=True,version=version,csrf='article-demo')
        cookie=client.get_cookie('session',domain='localhost').value
        cert,key=local_certificate(instance)
        server=make_server('127.0.0.1',0,app,threaded=True,ssl_context=(str(cert),str(key)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        origin=f'https://localhost:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1060},locale='de-DE',device_scale_factor=1)
                context.add_cookies([dict(name='session',value=cookie,url=origin,secure=True)])
                page=context.new_page();page.on('dialog',lambda dialog:dialog.accept())
                def shot(name,path=None,selector=None,full=False):
                    if path:
                        response=page.goto(origin+path);assert response.status==200,(path,response.status)
                    page.evaluate('document.fonts.ready');page.wait_for_timeout(350)
                    if selector:page.locator(selector).screenshot(path=str(output/name))
                    else:page.screenshot(path=str(output/name),full_page=full)
                    print(name,flush=True)
                shot('01-tagescockpit.png','/')
                shot('02-mailkarten.png','/', '.communication-columns')
                shot('03-vorgang.png','/case/1')
                shot('04-projekt.png','/project/1')
                shot('05-heute-geschafft.png','/','.completed-today')
                page.evaluate("openDialog('task-dialog',{text:'Wochenpost KW{KW} vorbereiten',due:document.querySelector('.date-controls input').value,repeat_frequency:'weekly'})")
                shot('06-wiederkehrende-aufgabe.png',selector='#task-dialog')
                page.locator('#task-dialog').evaluate('e=>e.close()')
                page.goto(origin+'/entry/1');page.evaluate('document.fonts.ready')
                panel=page.locator('.detail-grid>section').first.bounding_box()
                heading=page.locator('.page-heading').bounding_box()
                page.screenshot(path=str(output/'07-protokoll.png'),clip=dict(x=panel['x'],y=heading['y'],width=panel['width'],height=800))
                shot('08-terminvorbereitung.png','/appointment/1')
                shot('09-wochenpost.png',f'/entry/{note}')
                shot('10-kontakte.png','/people')
                page.goto(origin+'/');page.locator('.global-search input').fill('Leseband')
                expect(page.locator('#search-suggestions')).to_be_visible()
                page.screenshot(path=str(output/'11-suche.png'),clip=dict(x=250,y=0,width=1190,height=620))
                page.keyboard.press('Escape');page.locator('[data-voice-open]').click()
                shot('12-sprachi.png',selector='#voice-dialog')
                page.locator('#voice-dialog [data-voice-close]').first.click()
                page.goto(origin+'/handwriting/new')
                expect(page.locator('#sheet-save')).to_be_enabled(timeout=30000)
                page.locator('#sheet-title').fill('Herbstfest – erste Raumideen')
                canvas=page.locator('canvas.interactive');expect(canvas).to_be_visible()
                bounds=canvas.bounding_box();x=bounds['x']+330;y=bounds['y']+220
                page.locator('#sheet-title').press('Tab');page.mouse.click(x-100,y-80);page.keyboard.press('Escape')
                for dx,label in [(0,'Büchertausch'),(360,'Waffelstand')]:
                    page.keyboard.press('r');page.mouse.move(x+dx,y);page.mouse.down();page.mouse.move(x+dx+270,y+170,steps=12);page.mouse.up()
                    page.keyboard.press('Escape');page.keyboard.press('t');page.mouse.click(x+dx+30,y+70);page.keyboard.insert_text(label);page.keyboard.press('Escape')
                page.keyboard.press('p');page.mouse.move(x+50,y+270);page.mouse.down();page.mouse.move(x+200,y+240,steps=15);page.mouse.move(x+410,y+280,steps=15);page.mouse.up();page.keyboard.press('Escape')
                page.locator('#sheet-save').click()
                expect(page.locator('#sheet-status')).to_have_text('Gespeichert',timeout=30000)
                shot('13-handschrift.png')
                browser.close()
        finally:server.shutdown()
    print('Nur fiktive Daten; temporäre Instanz wieder entfernt.')


if __name__=='__main__':main()
