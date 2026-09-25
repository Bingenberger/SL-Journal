from playwright.sync_api import expect
from journal.db import get_db,one
from journal.domain import now,save_entry
from autocomplete_checks import choose


def check_cases(page,app,output):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    title='Anfrage zum Ganztag Browser'
    page.goto(origin+'/cases')
    if page.locator('#suggestions').count() and not page.locator('#suggestions').evaluate('(el)=>el.open'): page.locator('#suggestions > summary').click()
    page.get_by_role('button',name='Neuer Vorgang',exact=True).click()
    dialog=page.locator('#case-dialog')
    dialog.locator('[name=title]').fill(title)
    dialog.locator('[data-md-content=description]').fill('**Anlass:** Eine Rückfrage klären.')
    dialog.locator('[name=follow_up]').fill(now().date().isoformat())
    dialog.get_by_role('button',name='Vorgang speichern',exact=True).click()
    expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
    with app.app_context():
        cid=one('SELECT id FROM cases WHERE title=?',(title,))['id']
        old=save_entry(dict(type='mail_in',title='Vorhandene Anfrage Browser',date=now().date().isoformat()))
        get_db().commit()
    page.get_by_role('button',name='Eintrag',exact=True).click()
    entry=page.locator('#entry-dialog')
    expect(entry.locator('[data-autocomplete-field=cases] .ac-chip')).to_contain_text(title)
    entry.locator('[name=title]').fill('Gespräch zum Vorgang Browser')
    entry.locator('[name=type]').select_option('meeting')
    body=entry.locator('[data-md-content=body]')
    body.fill('Siehe @Anfrage zum Ganztag')
    option=page.locator('.resource-completions [role=option]').filter(has_text=title)
    expect(option).to_be_visible()
    option.click()
    assert f'/case/{cid}' in entry.locator('[name=body]').input_value()
    entry.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(entry).not_to_be_visible()
    expect(page.locator('.entry-card').filter(has_text='Gespräch zum Vorgang Browser')).to_be_visible()
    page.get_by_role('button',name='Neu',exact=True).click()
    task=page.locator('#task-dialog')
    expect(task.locator('[data-autocomplete-field=case_id] .ac-chip')).to_contain_text(title)
    task.locator('[name=text]').fill('Vorgangsaufgabe Browser')
    task.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(task).not_to_be_visible()
    expect(page.get_by_role('button',name='Vorgangsaufgabe Browser',exact=True)).to_be_visible()
    existing=page.locator('[data-autocomplete-field=entry_id]')
    choose(existing,'Vorhandene Anfrage Browser','Vorhandene Anfrage Browser')
    page.get_by_role('button',name='Eintrag zuordnen',exact=True).click()
    expect(page.locator('.entry-card').filter(has_text='Vorhandene Anfrage Browser')).to_be_visible()
    with app.app_context():
        assert one('SELECT case_id FROM tasks WHERE text=?',('Vorgangsaufgabe Browser',))['case_id']==cid
        assert one('SELECT COUNT(*) n FROM entry_cases WHERE case_id=?',(cid,))['n']==2
    page.goto(origin+'/')
    expect(page.locator('.case-reminders').get_by_role('link',name=title,exact=False)).to_be_visible()
    page.goto(origin+f'/case/{cid}')
    status=page.locator(f'form[action="/case/{cid}/status"]')
    status.locator('[name=status]').select_option('done')
    status.get_by_role('button',name='Stand speichern',exact=True).click()
    expect(page.locator('.page-heading .eyebrow')).to_contain_text('Erledigt')
    page.goto(origin+'/')
    expect(page.locator('.case-reminders').get_by_role('link',name=title,exact=False)).to_have_count(0)
    page.goto(origin+'/cases?status=done')
    expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
    page.goto(origin+f'/case/{cid}')
    status.locator('[name=status]').select_option('clarifying')
    status.get_by_role('button',name='Stand speichern',exact=True).click()
    expect(page.locator('.page-heading .eyebrow')).to_contain_text('In Klärung')
    page.screenshot(path=str(output/'case-desktop.png'),full_page=True)
    for width,height in [(768,1024),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        for path in ['/cases',f'/case/{cid}','/entries?inbox=1']:
            page.goto(origin+path)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),path
    page.set_viewport_size({'width':1440,'height':1100})
    page.goto(origin+'/')
