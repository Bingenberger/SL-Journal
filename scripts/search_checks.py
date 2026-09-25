"""Check global search interaction against an isolated journal database."""
from case_suggestion_checks import main
from journal.db import get_db
from playwright.sync_api import expect


def check(page,app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,institution) VALUES('Suchprobe Kontakt','Schulamt')")
        db.execute("INSERT INTO tasks(text) VALUES('Suchprobe Aufgabe')")
        db.commit()
    field=page.locator('.global-search input')
    field.fill('SUCHPROBE')
    options=page.locator('#search-suggestions')
    expect(options).to_be_visible()
    expect(options).to_contain_text('Suchprobe Kontakt')
    expect(options).to_contain_text('Suchprobe Aufgabe')
    field.press('Escape')
    expect(options).not_to_be_visible()
    field.fill('Suchprob')
    expect(options).to_be_visible()
    field.press('ArrowDown')
    field.press('Enter')
    expect(page).to_have_url(__import__('re').compile(r'/person/\d+$'))
    field.fill('suchprobe')
    expect(options).to_be_visible()
    field.press('Enter')
    expect(page.locator('h1')).to_have_text('Journal durchsuchen')
    expect(page.locator('.search-result')).to_have_count(2)
    for width in [1440,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        field.fill('SUCHPROB')
        expect(options).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        field.press('Escape')
    field.fill('SCHULAMT')
    expect(options).to_be_visible()
    options.get_by_role('option').filter(has_text='Suchprobe Kontakt').click()
    expect(page).to_have_url(__import__('re').compile(r'/person/\d+$'))
    print('Globale Suche: Live-Vorschläge, Enter, Pfeiltasten, Escape, Klick und responsive Darstellung geprüft.')


if __name__=='__main__':
    main(check)
