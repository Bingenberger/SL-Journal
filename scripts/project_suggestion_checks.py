from playwright.sync_api import expect
from journal.db import get_db, one
from autocomplete_checks import choose


def check_project_suggestions(page, app, output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    page.goto(origin+'/')
    page.locator('.topbar [data-new-entry]').click()
    dialog=page.locator('#entry-dialog')
    control=dialog.locator('[data-autocomplete-field=projects]')
    dialog.locator('[name=title]').fill('Eintrag mit Projektvorschlag')
    control.locator('.ac-input').fill('Schulgarten Browser')
    control.locator('.ac-input').press('Enter')
    expect(control.locator('.ac-chip')).to_contain_text('Schulgarten Browser')
    expect(control.locator('.ac-chip small')).to_have_text('neu')
    dialog.locator('summary').filter(has_text='Aufgaben aus diesem Eintrag').click()
    dialog.locator('[name=new_task]').fill('Pflanzen für den Schulgarten')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context():
        eid=one("SELECT id FROM entries WHERE title='Eintrag mit Projektvorschlag'")['id']
        sid=one("SELECT id FROM project_suggestions WHERE name='Schulgarten Browser'")['id']
    page.goto(origin+f'/entry/{eid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    expect(control.locator('.ac-chip')).to_contain_text('Schulgarten Browser')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    page.goto(origin+'/tasks')
    page.get_by_role('button',name='Pflanzen für den Schulgarten',exact=True).click()
    task=page.locator('#task-dialog')
    expect(task.locator('.ac-chip')).to_contain_text('Schulgarten Browser')
    task.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(task).not_to_be_visible()
    page.goto(origin+'/projects')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    card=page.locator(f'[data-project-suggestion-id="{sid}"]')
    expect(card).to_contain_text('1 Einträge · 1 Aufgaben')
    page.screenshot(path=str(output/'project-suggestions.png'),full_page=True)
    card.get_by_role('button',name='Als Projekt übernehmen',exact=True).click()
    project=page.locator('#project-dialog')
    expect(project.locator('[name=name]')).to_have_value('Schulgarten Browser')
    project.get_by_role('button',name='Projekt speichern',exact=True).click()
    expect(project).not_to_be_visible()
    with app.app_context():
        pid=one("SELECT id FROM projects WHERE name='Schulgarten Browser'")['id']
        assert one('SELECT project_id FROM entry_projects WHERE entry_id=?',(eid,))['project_id']==pid
        assert one("SELECT project_id FROM tasks WHERE text='Pflanzen für den Schulgarten'")['project_id']==pid
    page.goto(origin+'/tasks')
    page.locator('.topbar [data-new-task]').click()
    task.locator('[name=text]').fill('Neue Projektidee aus einer Aufgabe')
    task_control=task.locator('[data-autocomplete-field=project_id]')
    task_control.locator('.ac-input').fill('Garten Alias')
    task_control.locator('.ac-input').press('Enter')
    task.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(task).not_to_be_visible()
    page.goto(origin+'/projects')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    with app.app_context(): alias=one("SELECT id FROM project_suggestions WHERE name='Garten Alias'")['id']
    alias_card=page.locator(f'[data-project-suggestion-id="{alias}"]')
    alias_card.get_by_role('button',name='Vorhandenem Projekt zuordnen',exact=True).click()
    merge=page.locator('#project-suggestion-link-dialog')
    choose(merge.locator('[data-autocomplete-field=project_id]'),'Schulgarten Browser','Schulgarten Browser')
    merge.get_by_role('button',name='Zuordnen',exact=True).click()
    expect(alias_card).not_to_be_visible()
    with app.app_context():
        assert one("SELECT project_id FROM tasks WHERE text='Neue Projektidee aus einer Aufgabe'")['project_id']==pid
    page.goto(origin+'/')
