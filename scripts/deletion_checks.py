"""Löschen in der Oberfläche: Bestätigung, Wirkung und was erhalten bleibt."""
from playwright.sync_api import expect
from journal.db import get_db, one, rows
from journal.domain import save_entry, save_attachment, school_year


def check_deletion(page, app, output):
    origin = page.url.split('/')[0]+'//'+page.url.split('/')[2]
    fragen = []

    # browser_check bestätigt Rückfragen bereits; hier wird ihr Text nur mitgeschrieben.
    page.on('dialog', lambda dialog: fragen.append(dialog.message))

    def bestaetigen(button):
        button.click()

    with app.app_context():
        pid = get_db().execute('INSERT INTO projects(name,school_year) VALUES(?,?)',
                               ('Löschprüfung Projekt', school_year())).lastrowid
        eid = save_entry(dict(date='2026-09-24', type='note', title='Löschprüfung Eintrag',
                              body='Bleibt erhalten.'), [pid])
        save_attachment(eid, 'Löschprüfung.txt', b'Inhalt', 'text/plain')
        aid = one('SELECT id FROM attachments WHERE name=?', ('Löschprüfung.txt',))['id']
        get_db().commit()

    # Anhang am Eintrag löschen; der Eintrag bleibt.
    page.goto(origin+f'/entry/{eid}')
    bestaetigen(page.get_by_role('button', name='Anhang löschen: Löschprüfung.txt'))
    expect(page.get_by_role('heading', name='Löschprüfung Eintrag')).to_be_visible()
    expect(page.get_by_text('Löschprüfung.txt')).to_have_count(0)
    with app.app_context():
        assert not one('SELECT id FROM attachments WHERE id=?', (aid,))
        assert one('SELECT id FROM entries WHERE id=?', (eid,))
    assert any('Anhang' in frage for frage in fragen), fragen

    # Aufgabe über das Aktionsmenü löschen.
    page.goto(origin+'/tasks')
    page.locator('.topbar [data-new-task]').click()
    task = page.locator('#task-dialog')
    task.locator('[name=text]').fill('Aufgabe zum Löschen')
    task.get_by_role('button', name='Aufgabe speichern', exact=True).click()
    expect(page.get_by_role('button', name='Aufgabe zum Löschen', exact=True)).to_be_visible()
    zeile = page.locator('.task-row').filter(has_text='Aufgabe zum Löschen')
    zeile.locator('.task-actions summary').click()
    expect(zeile.get_by_role('button', name='Aufgabe löschen', exact=True)).to_be_visible()
    page.screenshot(path=str(output/'aufgabenmenue.png'))
    bestaetigen(zeile.get_by_role('button', name='Aufgabe löschen', exact=True))
    expect(page.get_by_role('button', name='Aufgabe zum Löschen', exact=True)).to_have_count(0)
    with app.app_context():
        assert not one('SELECT id FROM tasks WHERE text=?', ('Aufgabe zum Löschen',))

    # Projekt löschen; der zugeordnete Eintrag bleibt bestehen.
    page.goto(origin+f'/project/{pid}')
    bestaetigen(page.get_by_role('button', name='Projekt löschen', exact=True))
    expect(page.get_by_role('heading', name='Projekte', exact=True)).to_be_visible()
    with app.app_context():
        assert not one('SELECT id FROM projects WHERE id=?', (pid,))
        assert one('SELECT id FROM entries WHERE id=?', (eid,))
    assert any('Einträge und Aufgaben bleiben erhalten' in frage for frage in fragen), fragen
    page.screenshot(path=str(output/'loeschen-projekt.png'), full_page=True)

    # Kontakt löschen; der Eintrag bleibt und verliert nur den Namen.
    page.goto(origin+'/people')
    page.get_by_role('button', name='Neuer Kontakt', exact=False).click()
    person = page.locator('#person-dialog')
    person.locator('[name=name]').fill('Löschprüfung Kontakt')
    person.get_by_role('button', name='Kontakt speichern', exact=True).click()
    expect(person).not_to_be_visible()
    with app.app_context():
        kontakt = one('SELECT id FROM people WHERE name=?', ('Löschprüfung Kontakt',))['id']
    page.goto(origin+f'/person/{kontakt}')
    bestaetigen(page.get_by_role('button', name='Kontakt löschen', exact=True))
    expect(page.get_by_role('heading', name='Kontakte', exact=True)).to_be_visible()
    with app.app_context():
        assert not one('SELECT id FROM people WHERE id=?', (kontakt,))

    # Jahresprozess löschen; ein daraus erzeugtes Projekt bliebe bestehen.
    page.goto(origin+'/processes')
    page.get_by_role('button', name='Neuer Jahresprozess', exact=False).click()
    prozess = page.locator('#process-dialog')
    prozess.locator('[name=name]').fill('Löschprüfung Prozess')
    prozess.locator('[name=month]').select_option('9')
    prozess.get_by_role('button', name='Prozess speichern', exact=True).click()
    karte = page.locator('.process-card').filter(has_text='Löschprüfung Prozess')
    expect(karte).to_be_visible()
    bestaetigen(karte.get_by_role('button', name='Löschen', exact=True))
    expect(page.locator('.process-card').filter(has_text='Löschprüfung Prozess')).to_have_count(0)
    with app.app_context():
        assert not rows('SELECT id FROM processes WHERE name=?', ('Löschprüfung Prozess',))
    assert len(fragen) >= 5, fragen
    # Die nachfolgenden Prüfungen erwarten wieder das Cockpit.
    page.goto(origin+'/')
