from playwright.sync_api import expect
from journal.db import get_db,one
from journal.domain import save_entry,save_attachment
from scripts.pdf_fixture import sample_pdf


def check_pdf_preview(page,app,output):
    origin=page.url.split('/')[0]+'//'+page.url.split('/')[2]
    with app.app_context():
        eid=save_entry(dict(title='PDF-Vorschau prüfen',date='2026-09-22'),[1])
        save_attachment(eid,'Vorschau.pdf',sample_pdf(),'application/pdf')
        aid=one('SELECT id FROM attachments WHERE entry_id=?',(eid,))['id']
        save_attachment(eid,'Defekt.pdf',b'%PDF- broken','application/pdf')
        bad=one("SELECT id FROM attachments WHERE entry_id=? AND name='Defekt.pdf'",(eid,))['id']
        get_db().commit()
    preview_requests=[]
    page.on('request',lambda request:preview_requests.append(request.url) if '/preview' in request.url else None)
    page.goto(origin+f'/entry/{eid}')
    panel=page.locator('#pdf-preview')
    row=page.locator(f'[data-pdf-url="/attachment/{aid}/preview"]')
    assert not preview_requests
    row.locator('a.attachment').hover()
    expect(panel).to_be_visible()
    expect(panel.locator('img')).to_be_visible()
    assert panel.locator('img').evaluate('(img)=>img.naturalWidth>0')
    panel.hover()
    page.wait_for_timeout(400)
    expect(panel).to_be_visible()
    page.screenshot(path=str(output/'pdf-hover-desktop.png'),full_page=True)
    page.keyboard.press('Escape')
    expect(panel).not_to_be_visible()
    # Keyboard activation pins the window and restores focus when closed.
    button=row.get_by_role('button',name='PDF-Vorschau:',exact=False)
    button.focus()
    expect(panel).to_be_visible()
    button.press('Enter')
    expect(panel.get_by_role('button',name='PDF-Vorschau schließen')).to_be_focused()
    page.keyboard.press('Escape')
    expect(panel).not_to_be_visible()
    expect(button).to_be_focused()
    with page.expect_download() as download:
        row.locator('a.attachment').click()
    assert download.value.suggested_filename=='Vorschau.pdf'
    page.goto(origin+'/project/1')
    row.get_by_role('button',name='PDF-Vorschau:',exact=False).click()
    expect(panel.locator('img')).to_be_visible()
    panel.get_by_role('button',name='PDF-Vorschau schließen').click()
    page.locator(f'[data-pdf-url="/attachment/{bad}/preview"]').get_by_role('button',name='PDF-Vorschau:',exact=False).click()
    expect(panel.get_by_role('status')).to_contain_text('Keine Vorschau verfügbar')
    expect(panel.get_by_role('link',name='Herunterladen')).to_have_attribute('href',f'/attachment/{bad}')
    panel.get_by_role('button',name='PDF-Vorschau schließen').click()
    page.set_viewport_size({'width':390,'height':844})
    row.get_by_role('button',name='PDF-Vorschau:',exact=False).click()
    expect(panel.locator('img')).to_be_visible()
    assert panel.evaluate('(element)=>element.getBoundingClientRect().left>=0 && element.getBoundingClientRect().right<=window.innerWidth')
    page.screenshot(path=str(output/'pdf-preview-mobile.png'),full_page=True)
    panel.get_by_role('button',name='PDF-Vorschau schließen').click()
    expect(panel).not_to_be_visible()
    page.set_viewport_size({'width':1440,'height':1100})
    # „Öffnen“ liefert das PDF unverändert aus – der Browser zeigt es in seinem
    # eigenen Betrachter, in dem sich Text markieren lässt.
    page.goto(origin+f'/entry/{eid}')
    zeile=page.locator(f'[data-pdf-url="/attachment/{aid}/preview"]')
    betrachter=zeile.get_by_role('link',name='Öffnen')
    expect(betrachter).to_have_attribute('href',f'/attachment/{aid}/inline')
    expect(betrachter).to_have_attribute('target','_blank')
    antwort=page.request.get(origin+f'/attachment/{aid}/inline')
    assert antwort.status==200,antwort.status
    assert antwort.headers['content-type'].startswith('application/pdf'),antwort.headers['content-type']
    assert antwort.headers['content-disposition'].startswith('inline'),antwort.headers['content-disposition']
    assert "object-src 'self'" in antwort.headers['content-security-policy']
    # Der EML-Anhang bekommt diesen Weg nicht.
    assert page.request.get(origin+f'/attachment/{bad}/inline').status==200
    # Zweizeilig: Name über den Schaltflächen, nicht daneben.
    lage=zeile.evaluate("""(z)=>{const n=z.querySelector('.attachment').getBoundingClientRect();
      const a=z.querySelector('.attachment-actions').getBoundingClientRect();
      return {darunter:a.top>=n.bottom-1,breit:n.width>200};}""")
    assert lage['darunter'],'Die Schaltflächen gehören unter den Dateinamen'
    assert lage['breit'],'Der Dateiname soll die ganze Zeile bekommen'
    page.goto(origin+'/')
