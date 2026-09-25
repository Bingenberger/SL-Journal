"""Usability regression checks against an isolated, fictional journal."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import expect
from journal.db import get_db,one
from journal.demo import seed
from journal.domain import now,save_entry,save_task


def check_ui(page,app):
    output=Path('docs/ui-improved');output.mkdir(exist_ok=True)
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        seed();db=get_db();day=now().date().isoformat()
        for i in range(100):
            db.execute('INSERT INTO people(name,role,institution) VALUES(?,?,?)',(f'Kontakt {i:03}','Klassenleitung','Schule'))
        cid=db.execute('INSERT INTO cases(title,follow_up) VALUES(?,?)',('Anfrage Betreuung',day)).lastrowid
        eid=save_entry(dict(title='Protokoll ohne Zeichnung',type='protocol',date=day,body='Inhalt zuerst',agenda='Situation',decisions='Rückmeldung',case_ids=json.dumps([cid])))
        for i in range(8):
            save_entry(dict(title=f'Mail {i}',type='mail_in',date=day,participants=f'Neue Person {i}',case_items=json.dumps([dict(kind='new_case',label=f'Anliegen {i}')]),project_items=json.dumps([dict(kind='new_project',label=f'Projektidee {i}')])) )
        mail=save_entry(dict(title='Mail direkt taggen',type='mail_in',date=day))
        save_task(dict(text='Dringende Rückmeldung',case_id=cid,due=day))
        for i in range(35):save_task(dict(text=f'Seitentest {i:02}'))
        target=one("SELECT id FROM tasks WHERE text='Seitentest 34'")['id']
        db.commit()
    for width,height in [(1440,1000),(768,1024),(390,844)]:
        page.set_viewport_size(dict(width=width,height=height))
        for name,path in [('cockpit','/'),('inbox','/entries?inbox=1'),('tasks','/tasks'),('people','/people'),('projects','/projects'),('cases','/cases'),('case',f'/case/{cid}'),('protocol',f'/entry/{eid}'),('settings','/settings')]:
            page.goto(origin+path)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(name,width)
            if name in ('people','projects','cases'):
                expect(page.locator('#suggestions')).not_to_have_attribute('open','')
                assert page.locator('.filter-bar').bounding_box()['y']<height
            if name=='people':expect(page.locator('.contact-row')).to_have_count(30)
            if name=='cockpit' and width<=1000:
                assert page.locator('.tasks-panel').bounding_box()['y']<page.locator('.journal-panel').bounding_box()['y']
                assert page.locator('.case-reminders').bounding_box()['y']<page.locator('.journal-panel').bounding_box()['y']
            if name=='inbox' and width==390:
                assert page.locator('.filter-bar [name=type]').bounding_box()['width']>200
            if name=='cases' and width==390:
                expect(page.locator('.mobile-nav-toggle')).to_contain_text('Vorgänge')
                expect(page.locator('#main-navigation')).not_to_be_visible()
                page.locator('.mobile-nav-toggle').click()
                expect(page.locator('#main-navigation')).to_be_visible()
                expect(page.locator('#main-navigation a.active')).to_be_visible()
                page.locator('.mobile-nav-toggle').click()
            if name=='protocol':expect(page.locator('.handwriting-sheets')).to_have_count(0)
            page.screenshot(path=str(output/f'{name}-{width}.png'))
        page.goto(origin+'/')
        page.locator('.topbar [data-new-entry]').click()
        dialog=page.locator('#entry-dialog')
        footer=dialog.locator('.dialog-footer')
        rect=footer.bounding_box()
        assert rect['y']>=0 and rect['y']+rect['height']<=height
        expect(dialog.locator('[name=title]')).to_be_focused()
        dialog.screenshot(path=str(output/f'dialog-{width}.png'))
        dialog.get_by_role('button',name='Abbrechen',exact=True).click()
        expect(dialog).not_to_be_visible()
    # No confirmation for an unchanged form; reject discarding a changed form.
    confirmations=[]
    def preserve(dialog):
        confirmations.append(dialog.message);dialog.dismiss()
    page.on('dialog',preserve)
    page.locator('.topbar [data-new-entry]').click()
    dialog=page.locator('#entry-dialog')
    dialog.locator('[name=title]').fill('Geschützter Entwurf')
    dialog.locator('[data-md-content=body]').fill('Der geschriebene Text bleibt erhalten.')
    dialog.locator('[name=title]').focus()
    page.keyboard.press('Escape')
    page.wait_for_timeout(100)
    expect(dialog).to_be_visible()
    expect(dialog.locator('[name=title]')).to_have_value('Geschützter Entwurf')
    assert len(confirmations)==1,confirmations
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    assert len(confirmations)==1,'Saving must not trigger an unsaved-data warning'
    page.remove_listener('dialog',preserve)
    # Direct tag assignment does not require the long entry dialog.
    page.goto(origin+'/entries?inbox=1')
    form=page.locator(f'form[action="/entry/{mail}/assign"]')
    form.locator('[data-autocomplete-field=tags] .ac-input').fill('Betreuung')
    form.get_by_role('button',name='Zuordnen',exact=True).click()
    expect(form).to_have_count(0)
    with app.app_context():assert one('SELECT tags FROM entries WHERE id=?',(mail,))['tags']=='Betreuung'
    # Existing resource links to tasks beyond page one continue to work.
    page.goto(origin+f'/tasks?filter=all#task-{target}')
    expect(page.locator(f'#task-{target}')).to_be_visible()
    page.goto(origin+'/tasks?q=Seitentest&due=undated')
    expect(page.locator('.task-row')).to_have_count(30)
    page.get_by_role('link',name='Weiter',exact=True).click()
    expect(page.locator('.task-row')).to_have_count(5)
    assert 'q=Seitentest' in page.url and 'due=undated' in page.url
    # Zuordnungen bleiben kompakt: zwei Spalten am Schreibtisch, eine auf dem Telefon.
    page.set_viewport_size({'width':1280,'height':960})
    page.goto(origin+'/')
    page.get_by_role('button',name='Erfassen').first.click()
    zuordnungen=page.locator('#entry-dialog .association-fields')
    expect(zuordnungen).to_be_visible()
    lage=page.evaluate("""()=>{
      const kinder=[...document.querySelectorAll('#entry-dialog .assoc-grid>*')].map(k=>k.getBoundingClientRect());
      const block=document.querySelector('#entry-dialog .association-fields').getBoundingClientRect();
      return {spalten:kinder.length,reihe:Math.abs(kinder[0].top-kinder[1].top)<2,
              breit:kinder[2].width>kinder[0].width*1.8,hoehe:Math.round(block.height)};}""")
    assert lage['spalten']==3 and lage['reihe'], 'Projekte und Vorgänge gehören nebeneinander'
    assert lage['breit'], 'Tags sollen über die volle Breite laufen'
    assert lage['hoehe']<260, f"Zuordnungen zu hoch: {lage['hoehe']} px"
    zuordnungen.screenshot(path='docs/screenshots/zuordnungen-kompakt.png')
    page.set_viewport_size({'width':390,'height':844})
    gestapelt=page.evaluate("""()=>{
      const k=[...document.querySelectorAll('#entry-dialog .assoc-grid>*')].map(e=>e.getBoundingClientRect());
      return k[1].top-k[0].top>20;}""")
    assert gestapelt, 'Auf dem Telefon gehören die Felder untereinander'
    page.keyboard.press('Escape')
    page.set_viewport_size({'width':1280,'height':960})

    # Seitenleiste: eigener Bildlauf auf flachen Bildschirmen, Ein-/Ausklappen
    # mit erhaltenen Bedienbaumnamen, und auf dem Telefon ohne Wirkung.
    page.set_viewport_size({'width':1024,'height':768})
    page.goto(origin+'/')
    lage=page.evaluate("""()=>{const s=document.querySelector('.sidebar');
      return {laeuft:s.scrollHeight>s.clientHeight,bildlauf:getComputedStyle(s).overflowY};}""")
    assert lage['bildlauf']=='auto', 'Die Seitenleiste braucht einen eigenen Bildlauf'
    if lage['laeuft']:
        page.evaluate("()=>document.querySelector('.sidebar').scrollTo(0,9999)")
        unten=page.evaluate("()=>Math.round(document.querySelector('.profile').getBoundingClientRect().bottom)<=innerHeight+1")
        assert unten, 'Das untere Ende der Seitenleiste bleibt unerreichbar'
    page.get_by_role('button',name='Seitenleiste einklappen').click()
    schmal=page.evaluate("""()=>({breite:Math.round(document.querySelector('.sidebar').getBoundingClientRect().width),
      rand:getComputedStyle(document.querySelector('.workspace')).marginLeft,
      sichtbar:document.querySelector('.sidebar nav a .nav-label').getBoundingClientRect().width})""")
    assert schmal['breite']<90 and schmal['rand']==f"{schmal['breite']}px", f'Eingeklappt unerwartet: {schmal}'
    assert schmal['sichtbar']<=1, 'Eingeklappt sollen nur die Symbole zu sehen sein'
    for name in ('Tagescockpit','Posteingang','Einstellungen'):
        expect(page.get_by_role('link',name=name).first).to_have_count(1)
    page.screenshot(path='docs/screenshots/seitenleiste-eingeklappt.png')
    page.reload()
    assert page.evaluate("()=>document.body.classList.contains('sidebar-collapsed')"), 'Der Zustand soll erhalten bleiben'
    # Auf dem Telefon hebt das Layout den eingeklappten Zustand auf.
    page.set_viewport_size({'width':390,'height':844})
    page.reload()
    mobil=page.evaluate("""()=>({breite:Math.round(document.querySelector('.sidebar').getBoundingClientRect().width),
      ueberlauf:document.documentElement.scrollWidth-innerWidth,
      label:getComputedStyle(document.querySelector('.sidebar nav a .nav-label')).position})""")
    # Die Navigation steckt mobil hinter „Menü", daher die Stilangabe statt der Größe.
    assert mobil['breite']>300 and mobil['ueberlauf']<=0, f'Mobil unerwartet: {mobil}'
    assert mobil['label']=='static', 'Mobil sollen die Beschriftungen wieder mitlaufen'
    page.set_viewport_size({'width':1280,'height':960})
    page.goto(origin+'/')
    page.get_by_role('button',name='Seitenleiste ausklappen').click()

    print('UI geprüft: 27 responsive Ansichten, 100 Kontakte, Speichern im Sichtbereich, Entwurfsschutz, mobile Prioritäten, Filter, direkte Tags, kompakte Zuordnungen und die ein-/ausklappbare Seitenleiste.')


if __name__=='__main__':
    import case_suggestion_checks as harness
    harness.main(check_ui,accept_dialogs=False)
