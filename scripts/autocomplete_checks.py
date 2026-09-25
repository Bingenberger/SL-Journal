from playwright.sync_api import expect
from journal.db import get_db,one,rows


def choose(control, query, label):
    control.locator('.ac-input').fill(query)
    option=control.locator('.ac-option').filter(has_text=label).first
    expect(option).to_be_visible()
    option.click()


def check_autocomplete(page,app,output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        db=get_db()
        for i in range(105):
            db.execute('INSERT INTO people(name,role,emails) VALUES(?,?,?)',(f'Kontakt {i:03}',f'Gruppe {i}',f'kontakt{i}@example.org'))
        anna=db.execute("INSERT INTO people(name,role,emails) VALUES('Anna Müller','Sekretariat','anna@example.org')").lastrowid
        db.commit()
    page.goto(origin+'/')
    page.locator('.topbar [data-new-entry]').click()
    dialog=page.locator('#entry-dialog')
    participants=dialog.locator('[data-autocomplete-field=participants]')
    projects=dialog.locator('[data-autocomplete-field=projects]')
    tags=dialog.locator('[data-autocomplete-field=tags]')
    assert dialog.locator('[name=people]').count()==0
    dialog.locator('[name=title]').fill('Autovervollständigung prüfen')
    participants.locator('.ac-input').fill('Sekretariat')
    expect(participants.locator('.ac-option')).to_have_count(2)
    participants.locator('.ac-input').press('ArrowDown')
    participants.locator('.ac-input').press('Enter')
    expect(participants.locator('.ac-chip')).to_have_count(1)
    expect(participants.locator('.ac-chip')).to_contain_text('Anna Müller')
    participants.locator('.ac-input').fill('Neue Person Beispiel')
    participants.locator('.ac-input').press('Enter')
    expect(participants.locator('.ac-chip')).to_have_count(2)
    choose(projects,'Schulfest','Schulfest')
    choose(projects,'Schulentwicklung','Schulentwicklung')
    expect(projects.locator('.ac-chip')).to_have_count(2)
    choose(tags,'Organ','Organisation')
    tags.locator('.ac-input').fill('Rückmeldung')
    tags.locator('.ac-input').press('Enter')
    tags.locator('.ac-input').fill('rückmeldung')
    tags.locator('.ac-input').press('Enter')
    expect(tags.locator('.ac-chip')).to_have_count(2)
    dialog.screenshot(path=str(output/'autocomplete-entry.png'))
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(page.get_by_role('link',name='Autovervollständigung prüfen',exact=True)).to_be_visible()
    with app.app_context():
        entry=one("SELECT * FROM entries WHERE title='Autovervollständigung prüfen'")
        eid=entry['id']
        assert entry['participants']=='Anna Müller; Neue Person Beispiel'
        assert entry['tags']=='Organisation, Rückmeldung'
        assert len(rows('SELECT * FROM entry_projects WHERE entry_id=?',(eid,)))==2
        assert one('SELECT person_id FROM entry_people WHERE entry_id=?',(eid,))['person_id']==anna
        sid=one("SELECT id FROM contact_suggestions WHERE name='Neue Person Beispiel'")['id']
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    expect(participants.locator('.ac-chip')).to_have_count(2)
    expect(projects.locator('.ac-chip')).to_have_count(2)
    expect(tags.locator('.ac-chip')).to_have_count(2)
    projects.get_by_role('button',name='Schulentwicklung entfernen',exact=True).click()
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context(): assert len(rows('SELECT * FROM entry_projects WHERE entry_id=?',(eid,)))==1
    page.goto(origin+'/people')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    card=page.locator(f'[data-suggestion-id="{sid}"]')
    expect(card).to_contain_text('Neue Person Beispiel')
    card.get_by_role('button',name='Als Kontakt übernehmen',exact=True).click()
    person=page.locator('#person-dialog')
    expect(person.locator('[name=name]')).to_have_value('Neue Person Beispiel')
    person.locator('[name=role]').fill('Schulträger')
    person.get_by_role('button',name='Kontakt speichern',exact=True).click()
    expect(card).not_to_be_visible()
    with app.app_context():
        new_contact=one("SELECT id FROM people WHERE name='Neue Person Beispiel'")['id']
        assert one('SELECT person_id FROM entry_people WHERE entry_id=? AND person_id=?',(eid,new_contact))
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    expect(participants.locator('.ac-chip small')).to_have_count(0)
    participants.locator('.ac-input').fill('Alias Beispiel')
    participants.locator('.ac-input').press('Enter')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context(): alias=one("SELECT id FROM contact_suggestions WHERE name='Alias Beispiel'")['id']
    page.goto(origin+'/people')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    alias_card=page.locator(f'[data-suggestion-id="{alias}"]')
    alias_card.get_by_role('button',name='Vorhandenem Kontakt zuordnen',exact=True).click()
    merge=page.locator('#suggestion-link-dialog')
    choose(merge.locator('[data-autocomplete-field=person_id]'),'anna@example.org','Anna Müller')
    merge.get_by_role('button',name='Zuordnen',exact=True).click()
    expect(alias_card).not_to_be_visible()
    with app.app_context():
        assert len(rows('SELECT * FROM entry_people WHERE entry_id=?',(eid,)))==2
    page.set_viewport_size({'width':390,'height':844})
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    participants.locator('.ac-input').fill('kontakt104@example.org')
    expect(participants.locator('.ac-option').filter(has_text='Kontakt 104')).to_be_visible()
    participants.locator('.ac-option').filter(has_text='Kontakt 104').click()
    expect(participants.locator('.ac-chip')).to_have_count(3)
    assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth')
    dialog.screenshot(path=str(output/'autocomplete-mobile.png'))
    dialog.get_by_role('button',name='Abbrechen',exact=True).click()
    page.set_viewport_size({'width':1440,'height':1100})
    page.goto(origin+'/')
