"""Isolated browser exercise for task series and expanded title templates."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from datetime import timedelta
from playwright.sync_api import expect
from journal.db import one,rows
from journal.domain import now


def check_recurrence(page,app):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    day=now().date();expected=f'Statistik KW{day.isocalendar().week:02} abgeben'
    page.goto(origin+'/tasks')
    page.get_by_role('link',name='Wiederkehrende Aufgaben',exact=True).click()
    page.get_by_role('button',name='Neue Aufgabenserie',exact=True).click()
    dialog=page.locator('#task-dialog')
    expect(dialog.locator('[data-task-repeat-section]')).to_have_attribute('open','')
    expect(dialog.locator('[name=repeat_frequency]')).to_have_value('weekly')
    dialog.locator('[name=text]').fill('Statistik KW{KW} abgeben')
    dialog.locator('[name=due]').fill(day.isoformat())
    expect(dialog.locator('[data-repeat-preview]')).to_contain_text(expected)
    dialog.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context():
        sid=one('SELECT id FROM task_series')['id']
        tasks=rows('SELECT * FROM tasks ORDER BY due')
        assert len(tasks)==3 and tasks[0]['text']==expected
        tid=tasks[0]['id']
    page.goto(origin+f'/task-series/{sid}')
    expect(page.locator('.task-row')).to_have_count(3)
    page.reload()
    expect(page.locator('.task-row')).to_have_count(3)
    page.get_by_role('button',name=expected,exact=True).click()
    expect(dialog.locator('[data-task-repeat-section]')).not_to_be_visible()
    expect(dialog.locator('[data-task-series-note]')).to_be_visible()
    dialog.locator('[name=text]').fill('Einzeltermin angepasst')
    dialog.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button',name='Einzeltermin angepasst',exact=True)).to_be_visible()
    with app.app_context():assert one('SELECT template FROM task_series')['template']=='Statistik KW{KW} abgeben'
    page.get_by_role('button',name='Serie bearbeiten',exact=True).click()
    editor=page.locator('#series-dialog')
    editor.locator('[name=text]').fill('Bericht {MONATSNAME} Q{QUARTAL} {JAHR}')
    expect(editor.locator('[data-repeat-preview]')).not_to_contain_text('{MONATSNAME}')
    editor.get_by_role('button',name='Serie speichern',exact=True).click()
    expect(editor).not_to_be_visible()
    expect(page.get_by_role('button',name='Einzeltermin angepasst',exact=True)).to_be_visible()
    page.get_by_role('button',name='Serie pausieren',exact=True).click()
    expect(page.get_by_role('button',name='Serie fortsetzen',exact=True)).to_be_visible()
    page.get_by_role('button',name='Serie fortsetzen',exact=True).click()
    expect(page.get_by_role('button',name='Serie pausieren',exact=True)).to_be_visible()
    page.locator('.topbar [data-new-task]').click()
    dialog.locator('[name=text]').fill('Abgabe {DATUM}')
    dialog.locator('[data-task-repeat-section] > summary').click()
    dialog.locator('[name=repeat_frequency]').select_option('dates')
    expect(dialog.locator('[name=due]')).to_be_disabled()
    for index,offset in enumerate([2,9,23]):
        if index:dialog.locator('[data-add-date]').click()
        dialog.locator('[data-repeat-date]').nth(index).fill((day+timedelta(days=offset)).isoformat())
    expect(dialog.locator('[name=repeat_dates]')).to_have_value('\n'.join((day+timedelta(days=n)).isoformat() for n in [2,9,23]))
    expect(dialog.locator('[data-repeat-preview]')).to_contain_text((day+timedelta(days=2)).strftime('%d.%m.%Y'))
    dialog.get_by_role('button',name='Aufgabe speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context():
        fixed=one("SELECT * FROM task_series WHERE frequency='dates'")
        assert fixed['next_due']==(day+timedelta(days=23)).isoformat()
        assert len(rows('SELECT * FROM task_occurrences WHERE series_id=?',(fixed['id'],)))==2
    page.goto(origin+f'/task-series/{fixed["id"]}')
    page.get_by_role('button',name='Serie bearbeiten',exact=True).click()
    expect(editor.locator('[data-repeat-date]')).to_have_count(3)
    editor.locator('[data-repeat-dates] summary').click()
    editor.locator('[name=repeat_dates]').fill('\n'.join((day+timedelta(days=n)).isoformat() for n in [2,10,23]))
    expect(editor.locator('[data-repeat-date]').nth(1)).to_have_value((day+timedelta(days=10)).isoformat())
    editor.locator('.date-row').nth(1).get_by_role('button').click()
    editor.get_by_role('button',name='Serie speichern',exact=True).click()
    expect(editor).not_to_be_visible()
    with app.app_context():
        import json
        assert json.loads(one('SELECT dates FROM task_series WHERE id=?',(fixed['id'],))['dates'])==[(day+timedelta(days=n)).isoformat() for n in [2,23]]
    for width,height in [(1440,1000),(768,1024),(390,844)]:
        page.set_viewport_size(dict(width=width,height=height))
        for path in ['/tasks','/task-series',f'/task-series/{sid}']:
            page.goto(origin+path)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(path,width)
        page.get_by_role('button',name='Serie bearbeiten',exact=True).click()
        footer=editor.locator('.dialog-footer').bounding_box()
        assert footer['y']+footer['height']<=height
        assert editor.evaluate('e=>e.scrollWidth<=e.clientWidth')
        editor.get_by_role('button',name='Abbrechen',exact=True).click()
    Path('docs/screenshots').mkdir(exist_ok=True)
    page.screenshot(path='docs/screenshots/task-series-mobile.png')
    page.set_viewport_size(dict(width=1440,height=1000));page.goto(origin+'/task-series')
    page.screenshot(path='docs/screenshots/task-series-desktop.png')
    print('Serien im Browser geprüft: wöchentlich, Einzeltermine, Titelvorschau, Einzelbearbeitung, Serienänderung, Pause/Fortsetzung und responsive Ansichten.')


if __name__=='__main__':
    from case_suggestion_checks import main
    main(check_recurrence)
