from playwright.sync_api import expect
from journal.db import get_db,one
from journal.domain import school_year


def check_resources(page,app,output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        db=get_db()
        pid=db.execute("INSERT INTO people(name,institution) VALUES('Ressource [Person]','Testinstitution')").lastrowid
        project=db.execute("INSERT INTO projects(name,school_year) VALUES('Ressourcenprojekt',?)",(school_year(),)).lastrowid
        db.commit()
    page.goto(origin+'/')
    page.locator('.topbar [data-new-entry]').click()
    dialog=page.locator('#entry-dialog')
    body=dialog.locator('[data-md-content=body]')
    raw=dialog.locator('[name=body]')
    options=page.locator('.resource-completions [role=option]')
    requests=[]
    page.on('request',lambda request: requests.append(request.url) if '/api/resources' in request.url else None)
    def write(text):
        body.fill('')
        body.press_sequentially(text,delay=3)
    write('mail@example.org')
    page.wait_for_timeout(400)
    expect(options).to_have_count(0)
    assert not requests
    write('@Ressource')
    page.wait_for_timeout(400)
    expect(options).to_have_count(0)
    assert not requests
    write('Siehe @Ressource')
    expect(options.filter(has_text='Ressource [Person]')).to_be_visible()
    options.filter(has_text='Ressource [Person]').click()
    expected='Siehe [Ressource \\[Person\\]](/person/'+str(pid)+') '
    expect(raw).to_have_value(expected)
    expect(body.locator('a.md-resource-link')).to_have_attribute('href',f'/person/{pid}')
    body.press('Control+z')
    expect(raw).to_have_value('Siehe @Ressource')
    body.press('Control+y')
    expect(raw).to_have_value(expected)
    body.press('Control+End')
    body.press_sequentially('und @Ressourcenprojekt',delay=3)
    expect(options.filter(has_text='Ressourcenprojekt')).to_be_visible()
    page.wait_for_timeout(100)
    body.press('Tab')
    expect(raw).to_have_value(expected+f'und [Ressourcenprojekt](/project/{project}) ')
    body.press_sequentially('sowie @Ressource',delay=3)
    expect(options.first).to_be_visible()
    body.press('Escape')
    expect(options).to_have_count(0)
    expect(dialog).to_be_visible()
    # Remove the unfinished query and save two links.
    body.fill(expected+f'und [Ressourcenprojekt](/project/{project}) ')
    dialog.locator('[name=title]').fill('Verlinkte Ressourcen')
    dialog.get_by_role('button',name='Eintrag speichern',exact=True).click()
    expect(dialog).not_to_be_visible()
    with app.app_context(): eid=one("SELECT id FROM entries WHERE title='Verlinkte Ressourcen'")['id']
    page.goto(origin+f'/entry/{eid}')
    expect(page.locator('#entry-body a').filter(has_text='Ressource [Person]')).to_have_attribute('href',f'/person/{pid}')
    page.get_by_role('button',name='Eintrag bearbeiten',exact=True).click()
    expect(raw).to_have_value(expected+f'und [Ressourcenprojekt](/project/{project}) ')
    with page.expect_popup() as popup:
        body.locator('a.md-resource-link').first.click(modifiers=['Control'])
    popup.value.close()
    # Code and existing Markdown links never trigger resource lookup.
    write(chr(96)+'code '+chr(96))
    body.press('ArrowLeft')
    body.press_sequentially('@Ressource',delay=3)
    page.wait_for_timeout(400)
    expect(options).to_have_count(0)
    write(chr(96)*3+'\n @Ressource')
    page.wait_for_timeout(400)
    expect(options).to_have_count(0)
    page.set_viewport_size({'width':390,'height':844})
    write('Siehe @Ressource')
    expect(options.first).to_be_visible()
    dialog.screenshot(path=str(output/'resource-links-mobile.png'))
    assert dialog.evaluate('(element)=>element.scrollWidth<=element.clientWidth')
    page.wait_for_timeout(100)
    body.press('Enter')
    expect(raw).to_have_value(expected)
    dialog.get_by_role('button',name='Abbrechen',exact=True).click()
    page.set_viewport_size({'width':1440,'height':1100})
    page.goto(origin+'/')
