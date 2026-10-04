from pathlib import Path
import subprocess
from journal.attachment_search import init, process_pending, summary
from journal.db import get_db, one
from journal.domain import save_entry, save_attachment


def seed(app, name='Unterlage.txt', content=b'Leseband Foerderplanung', mime='text/plain'):
    with app.app_context():
        eid=save_entry(dict(title='Besprechung',date='2026-10-04'))
        save_attachment(eid,name,content,mime)
        get_db().commit()
        return eid


def test_text_search_and_cascade(app,client):
    eid=seed(app,content='Leseförderung <script>alert(1)</script>'.encode())
    with app.app_context():
        assert summary()=={'pending':1}
        assert process_pending()==1
        assert process_pending()==0
        assert summary()=={'ready':1}
        assert b'Lesef' not in (Path(app.instance_path)/'journal.db').read_bytes()
    hit=client.get('/api/search?q=LESEFÖRDERUNG',base_url='https://localhost').json['items'][0]
    assert hit['kind']=='Anhang' and hit['url']==f'/entry/{eid}#attachment-1'
    assert 'Leseförderung' in hit['excerpt']
    html=client.get('/search?q=leseförderung',base_url='https://localhost').text
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert client.get(f'/entry/{eid}',base_url='https://localhost').status_code==200
    assert app.test_client().get('/api/search?q=leseförderung',base_url='https://localhost').status_code==302
    with app.app_context():
        get_db().execute('DELETE FROM entries WHERE id=?',(eid,));get_db().commit()
        assert summary()=={}
        assert one('SELECT count(*) n FROM attachment_text')['n']==0
    assert client.get('/api/search?q=leseförderung',base_url='https://localhost').json['total']==0


def test_pdf_pages_dedup(app,client,monkeypatch):
    monkeypatch.setattr('journal.document_text.ocr',lambda *a: ('',''))
    seed(app,'Raumplan.pdf',b'%PDF-demo','application/pdf')
    monkeypatch.setattr('journal.attachment_search.shutil.which',lambda _: '/usr/bin/pdftotext')
    monkeypatch.setattr('journal.attachment_search.subprocess.run',lambda *a,**k:subprocess.CompletedProcess(a,0,b'Erste Seite\fLeseband Foerderung\fLeseband\f'))
    with app.app_context(): process_pending()
    hits=client.get('/api/search?q=leseband',base_url='https://localhost').json['items']
    assert len(hits)==1 and 'Seite ' in hits[0]['detail']
    assert '#page=' in hits[0]['file_url']
    assert client.get('/api/search?q=Raumplan',base_url='https://localhost').json['total']==1


def test_old_attachments_recovery_and_retry(app,monkeypatch):
    monkeypatch.setattr('journal.document_text.ocr',lambda *a: ('',''))
    seed(app,'Scan.pdf',b'%PDF-demo','application/pdf')
    seed(app,'Ton.mp4',b'audio','audio/mp4')
    with app.app_context():
        get_db().execute('DELETE FROM attachment_index');get_db().commit();init()
        get_db().execute("UPDATE attachment_index SET status='processing',claimed=1 WHERE attachment_id=1");get_db().commit()
        monkeypatch.setattr('journal.attachment_search.shutil.which',lambda _:None)
        assert process_pending()==2
        assert summary()=={'error':1,'unsupported':1}
        monkeypatch.setattr('journal.attachment_search.shutil.which',lambda _: '/usr/bin/pdftotext')
        monkeypatch.setattr('journal.attachment_search.subprocess.run',lambda *a,**k:subprocess.CompletedProcess(a,0,b'\f'))
        process_pending(retry=True)
        assert summary()=={'empty':1,'unsupported':1}


def test_bad_file_does_not_block_following_job(app):
    seed(app,'Kaputt.txt',b'a\x00b')
    seed(app,content='Grüße aus Köln'.encode('utf-16'))
    with app.app_context():
        assert process_pending()==2
        assert summary()=={'error':1,'ready':1}


def test_deleted_during_extraction(app,monkeypatch):
    seed(app)
    def remove(item,content):
        get_db().execute('DELETE FROM attachments WHERE id=?',(item['id'],));get_db().commit()
        return [(1,'stale')],'ready',''
    monkeypatch.setattr('journal.attachment_search.extract',remove)
    with app.app_context():
        process_pending()
        assert summary()=={}
        assert one('SELECT count(*) n FROM attachment_text')['n']==0


def text_pdf():
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    # Mehr als 40 Buchstaben: Darunter hält pdf_text die Seite für einen Scan
    # und schickt sie durch die OCR – dieser Test soll aber allein den
    # Textauszug aus der PDF prüfen, auch ohne Tesseract.
    stream=b'BT /F1 12 Tf 20 250 Td (Leseband im Schulalltag der Grundschule Sonnenbogen) Tj ET'
    objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    data=b'%PDF-1.4\n';offsets=[0]
    for n,obj in enumerate(objects,1):
        offsets.append(len(data));data+=str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(data);data+=b'xref\n0 6\n0000000000 65535 f \n'
    for offset in offsets[1:]:data+=f'{offset:010d} 00000 n \n'.encode()
    return data+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()


def test_real_pdf_extractor(app,client):
    import shutil,pytest
    if not shutil.which('pdftotext'):pytest.skip('Poppler fehlt')
    seed(app,'Echter Text.pdf',text_pdf(),'application/pdf')
    with app.app_context():
        process_pending()
        assert summary()=={'ready':1}
    hit=client.get('/api/search?q=Schulalltag',base_url='https://localhost').json['items'][0]
    assert 'Seite 1' in hit['detail'] and 'Leseband' in hit['excerpt']


def test_background_worker(app,client):
    import time
    seed(app)
    app.testing=False
    client.get('/search',base_url='https://localhost')
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        with app.app_context():
            if summary()=={'ready':1}:break
        time.sleep(.02)
    with app.app_context():assert summary()=={'ready':1}
    assert app.extensions['attachment_search_lock'].acquire(timeout=5)
    app.extensions['attachment_search_lock'].release()


def test_reiner_text_bleibt_eine_seite(app):
    """Seitenumbrüche gehören zu PDF; in einer Textdatei sind sie Inhalt."""
    from journal.attachment_search import extract
    with app.app_context():
        seiten,status,detail=extract({'name':'A.txt','mime':'text/plain'},'Zeile eins\fZeile zwei'.encode())
    assert seiten==[(1,'Zeile eins\fZeile zwei')] and status=='ready' and detail==''


def test_leere_textdatei_meldet_sich_ehrlich(app):
    from journal.attachment_search import extract
    with app.app_context():
        assert extract({'name':'B.txt','mime':'text/plain'},b'  \n ')==([],'empty','Die Datei enthält keinen Text.')


def test_lesende_aufrufe_werden_gedrosselt(app,monkeypatch):
    """Ein Seitenaufruf zieht viele Dateien nach sich; für jede einen Faden zu
    starten, der nichts findet, wäre verschenkt. Schreiben läuft sofort."""
    from journal.attachment_search import kick
    starts=[]
    monkeypatch.setattr('journal.attachment_search.threading.Thread',
                        lambda **kw: type('Fake',(),{'start':lambda self: starts.append(1)})())
    sperre=app.extensions['attachment_search_lock']
    frei=lambda: sperre.locked() and sperre.release()
    app.testing=False
    try:
        kick(app);frei();kick(app);frei()
        assert len(starts)==1,'der zweite Leseaufruf fällt in die Ruhezeit'
        kick(app,sofort=True);frei()
        assert len(starts)==2,'nach einer schreibenden Anfrage sofort'
        app.extensions['attachment_search_seen']-=10
        kick(app);frei()
        assert len(starts)==3,'nach Ablauf der Ruhezeit wieder möglich'
    finally:
        app.testing=True


def test_statische_dateien_stossen_nichts_an(app,client,monkeypatch):
    import journal.attachment_search as suche
    gerufen=[]
    monkeypatch.setattr(suche,'kick',lambda a,sofort=False: gerufen.append(sofort))
    client.get('/static/style.css',base_url='https://localhost')
    assert gerufen==[],'Stylesheets und Skripte brauchen keinen Hintergrundlauf'
    client.get('/',base_url='https://localhost')
    assert gerufen==[False],'die Seite selbst schon, aber ohne Eile'
