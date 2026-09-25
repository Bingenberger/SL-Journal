from playwright.sync_api import expect
from journal.db import get_db,one
from journal.domain import save_entry


def check_drawing_links(page,app,eid,did):
    origin=page.url.split('/',3)[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        meeting=save_entry(dict(type='meeting',title='Gespräch zur Zeichnung',date='2026-09-23'))
        protocol=save_entry(dict(type='protocol',title='Protokoll zur Zeichnung',date='2026-09-23'))
        get_db().commit()
        before=one('SELECT scene,revision FROM drawings WHERE id=?',(did,))
        import uuid
        second=get_db().execute('''INSERT INTO drawings(entry_id,client_key,title,scene,preview)
            SELECT entry_id,?,'Zweites Blatt',scene,preview FROM drawings WHERE id=?''',(str(uuid.uuid4()),did)).lastrowid
        get_db().commit()
    page.goto(origin+f'/entry/{eid}')
    sheet=page.locator('.handwriting-sheets')
    classification=page.locator('#entry-classification')
    assert sheet.bounding_box()['y']+sheet.bounding_box()['height']<=classification.bounding_box()['y']
    form=page.locator('#entry-resources [data-resource-picker]')
    expect(page.locator('[data-resource-picker]')).to_have_count(1)
    expect(page.locator('.handwriting-sheet [data-resource-picker]')).to_have_count(0)
    query=form.locator('[data-resource-query]')
    query.fill('Gespräch zur Zeichnung')
    option=form.get_by_role('option').filter(has_text='Gespräch zur Zeichnung')
    expect(option).to_be_visible()
    query.press('ArrowDown');query.press('Enter')
    with page.expect_navigation():
        form.get_by_role('button',name='Verknüpfen',exact=True).click()
    expect(page.locator('.drawing-resource-list').get_by_role('link',name='Gespräch zur Zeichnung',exact=False)).to_be_visible()
    query.fill('Protokoll zur Zeichnung')
    form.get_by_role('option').filter(has_text='Protokoll zur Zeichnung').click()
    with page.expect_navigation():
        form.get_by_role('button',name='Verknüpfen',exact=True).click()
    page.reload()
    expect(page.locator('.drawing-resource-list li')).to_have_count(2)
    page.locator('.drawing-resource-list').get_by_role('link',name='Protokoll zur Zeichnung',exact=False).click()
    expect(page.locator('.related-drawings')).to_be_visible()
    expect(page.locator(f'.related-drawings a[href="/entry/{eid}"]')).to_be_visible()
    expect(page.locator('.related-drawings')).to_contain_text('2 Zeichenblätter')
    page.locator('.related-drawings').get_by_role('link',name='Zum verknüpften Eintrag',exact=False).click()
    with page.expect_navigation():
        page.get_by_role('button',name='Verknüpfung zu Gespräch zur Zeichnung entfernen',exact=True).click()
    expect(page.locator('.drawing-resource-list li')).to_have_count(1)
    with page.expect_navigation():
        page.locator(f'#drawing-{second}').get_by_role('button',name='Blatt löschen').click()
    expect(page.locator('.drawing-resource-list li')).to_have_count(1)
    expect(page.locator('[data-resource-picker]')).to_have_count(1)
    for width,height in [(768,1024),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.set_viewport_size({'width':1280,'height':900})
    with app.app_context():
        assert one('SELECT scene,revision FROM drawings WHERE id=?',(did,))==before
        assert one('SELECT id FROM entries WHERE id=?',(meeting,))
        assert one('SELECT entry_id FROM entry_resource_links WHERE owner_entry_id=?',(eid,))['entry_id']==protocol
