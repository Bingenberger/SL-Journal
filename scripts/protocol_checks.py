from playwright.sync_api import expect
from journal.db import one


def check_protocols(page, app):
    page.locator('.topbar [data-new-entry]').click()
    dialog=page.locator('#entry-dialog')
    expect(dialog.locator('[data-md-content=agenda]')).not_to_be_visible()
    dialog.locator('[name=type]').select_option('protocol')
    dialog.locator('[name=title]').fill('Protokoll Browserprüfung')
    for field,text in [('agenda','**Tagesordnungspunkt**'),('body','Sitzungsverlauf'),('decisions','**Beschluss gefasst**')]:
        editor=dialog.locator(f'[data-md-content={field}]')
        expect(editor).to_be_visible()
        editor.fill(text)
    dialog.locator('[name=type]').select_option('note')
    expect(dialog.locator('[data-md-content=agenda]')).not_to_be_visible()
    dialog.locator('[name=type]').select_option('protocol')
    expect(dialog.locator('[name=agenda]')).to_have_value('**Tagesordnungspunkt**')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context():
        entry=one("SELECT * FROM entries WHERE title='Protokoll Browserprüfung'")
        assert entry['decisions']=='**Beschluss gefasst**'
    page.goto(page.url.split('/',3)[0]+'//'+page.url.split('/')[2]+f"/entry/{entry['id']}")
    expect(page.locator('#entry-agenda strong')).to_have_text('Tagesordnungspunkt')
    expect(page.locator('#entry-decisions strong')).to_have_text('Beschluss gefasst')
    page.locator('[data-edit-entry]').click()
    expect(dialog.locator('[name=agenda]')).to_have_value('**Tagesordnungspunkt**')
    expect(dialog.locator('[name=decisions]')).to_have_value('**Beschluss gefasst**')
    dialog.locator('[data-md-content=decisions]').fill('Geänderter Beschluss')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(page.locator('#entry-decisions')).to_have_text('Geänderter Beschluss')
    page.locator('.topbar [data-new-entry]').click()
    dialog.locator('[name=type]').select_option('protocol')
    expect(dialog.locator('[name=agenda]')).to_have_value('')
    expect(dialog.locator('[name=decisions]')).to_have_value('')
    dialog.get_by_role('button',name='Abbrechen',exact=True).click()
    page.goto(page.url.split('/',3)[0]+'//'+page.url.split('/')[2]+'/')
