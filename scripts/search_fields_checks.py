"""Scoped search suggestions and contact field suggestions in an isolated browser."""
from case_suggestion_checks import main
from journal.db import get_db,one
from playwright.sync_api import expect


def check(page,app):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role,institution,emails,phone) VALUES('Suchprobe Person','Leitung','Schulamt','anna@example.org','0221 123456')")
        db.execute("INSERT INTO projects(name,school_year) VALUES('Suchprobe Projekt','2026/27')")
        db.execute("INSERT INTO cases(title) VALUES('Suchprobe Vorgang')")
        db.execute("INSERT INTO tasks(text) VALUES('Suchprobe Aufgabe')")
        db.execute("INSERT INTO entries(date,type,title,tags) VALUES('2026-09-24','note','Suchprobe Notiz','Suchprobe')")
        db.commit()
    for path in ['people','projects','cases','tasks','entries','tags','search']:
        page.goto(origin+'/'+path)
        field=page.locator('[data-search-scope]');field.fill('SUCHPROBE')
        popup=field.locator('..').locator('[role=listbox]')
        expect(popup).to_be_visible();expect(popup.get_by_role('option').first).to_contain_text('Suchprobe')
        field.press('Escape');expect(popup).not_to_be_visible()
        field.fill('suchprob');expect(popup).to_be_visible()
        popup.get_by_role('option').last.click()
        expect(field).to_have_value('suchprob')
    page.goto(origin+'/people')
    page.get_by_role('button',name='Neuer Kontakt').click()
    dialog=page.locator('#person-dialog')
    for field_name,query,value in [('name','SUCH','Suchprobe Person'),('role','LEI','Leitung'),('institution','SCHU','Schulamt'),('phone','123','0221 123456')]:
        field=dialog.locator('[name='+field_name+']');field.fill(query)
        popup=field.locator('..').locator('[role=listbox]');expect(popup).to_be_visible()
        field.press('ArrowDown');field.press('Enter');expect(field).to_have_value(value)
    dialog.locator('[name=name]').fill('Neue Person')
    emails=dialog.locator('[name=emails]');emails.fill('first@example.org, ANN')
    popup=emails.locator('..').locator('[role=listbox]');expect(popup).to_be_visible()
    popup.get_by_role('option').first.click();expect(emails).to_have_value('first@example.org, anna@example.org')
    dialog.get_by_role('button',name='Kontakt speichern',exact=True).click();expect(dialog).not_to_be_visible()
    with app.app_context():
        p=one("SELECT * FROM people WHERE name='Neue Person'");assert p['phone']=='0221 123456';pid=p['id']
    page.goto(origin+'/person/'+str(pid));page.get_by_role('button',name='Bearbeiten',exact=True).click()
    expect(dialog.locator('[name=phone]')).to_have_value('0221 123456')
    for width in [1440,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        field=dialog.locator('[name=institution]');field.fill('SCHU')
        expect(field.locator('..').locator('[role=listbox]')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
        field.press('Escape');expect(dialog).to_be_visible()
    print('Bereichssuchen, freie Kontakteingabe, Vorschläge, mehrere Mailadressen, Telefonnummer und responsive Dialoge geprüft.')


if __name__=='__main__':main(check,accept_dialogs=True)
