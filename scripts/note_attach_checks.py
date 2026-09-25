"""Eine Mail an eine noch nicht vorhandene Notiz anhängen."""
from case_suggestion_checks import main
from journal.db import get_db,one,rows
from journal.domain import save_entry
from playwright.sync_api import expect


def check(page,app):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        source=save_entry(dict(type='mail_in',title='Schulamt: Fortbildung',date='2026-09-24',body='Mailinhalt bleibt unverändert'))
        get_db().commit()
    page.goto(origin+f'/entry/{source}')
    page.get_by_role('button',name='An Notiz anhängen',exact=True).click()
    dialog=page.locator('#note-dialog');field=dialog.locator('.ac-input');field.fill('Wochenpost KW 42')
    expect(dialog.get_by_role('option').filter(has_text='Als neue Notiz anlegen')).to_be_visible()
    # Speichern übernimmt den eingetippten Namen auch ohne Klick auf den Vorschlag.
    dialog.get_by_role('button',name='Anhängen',exact=True).click();expect(dialog).not_to_be_visible()
    with app.app_context():
        note=one("SELECT id FROM entries WHERE title='Wochenpost KW 42'")['id']
        assert one('SELECT type FROM entries WHERE id=?',(note,))['type']=='note'
    expect(page).to_have_url(origin+f'/entry/{note}#entry-resources')
    liste=page.locator('#entry-resources')
    expect(liste.get_by_role('link',name='Schulamt: Fortbildung',exact=False)).to_be_visible()

    # Zweite Quelle an dieselbe Notiz, diesmal über den Vorschlag.
    with app.app_context():
        zweite=save_entry(dict(type='mail_in',title='Elternbrief Herbst',date='2026-09-24'))
        get_db().commit()
    page.goto(origin+f'/entry/{zweite}')
    page.get_by_role('button',name='An Notiz anhängen',exact=True).click()
    field.fill('wochenpost');dialog.get_by_role('option').filter(has_text='Wochenpost KW 42').click()
    dialog.get_by_role('button',name='Anhängen',exact=True).click();expect(dialog).not_to_be_visible()
    expect(liste.locator('li')).to_have_count(2)

    # Die Quelle zeigt den Rückverweis; ihr Text bleibt unverändert.
    page.goto(origin+f'/entry/{source}')
    expect(page.get_by_role('link',name='Wochenpost KW 42',exact=False)).to_be_visible()
    for width in [1440,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto(origin+f'/entry/{note}')
    page.screenshot(path='docs/screenshots/notiz-mit-verweisen.png',full_page=True)
    with app.app_context():
        assert len(rows('SELECT * FROM entry_resource_links'))==2
        assert one('SELECT body FROM entries WHERE id=?',(source,))['body']=='Mailinhalt bleibt unverändert'
        assert not rows("SELECT name FROM sqlite_master WHERE name LIKE 'collection%'")
    print('Mail → neue Notiz, zweite Quelle, Rückverweis und mobile Ansicht geprüft.')


if __name__=='__main__':main(check)
