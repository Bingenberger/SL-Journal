import io
import shutil
import time
import pytest
from PIL import Image, ImageDraw, ImageFont
from journal.document_text import pdf_text,extract_document
from journal.attachment_search import process_pending,summary
from journal.db import get_db
from test_attachment_search import seed


def scan():
    image=Image.new('RGB',(1600,600),'white')
    font=ImageFont.truetype('DejaVuSans.ttf',54)
    ImageDraw.Draw(image).text((60,100),'Leseband Schulkonferenz 2026',font=font,fill='black')
    return image


@pytest.mark.parametrize('suffix',['.png','.pdf'])
def test_real_scans_are_searchable(app,client,suffix):
    if not all(shutil.which(p) for p in ('tesseract','pdftoppm','pdftotext')):pytest.skip('OCR-Werkzeuge fehlen')
    output=io.BytesIO();scan().save(output,format='PDF' if suffix=='.pdf' else 'PNG')
    seed(app,'Scan'+suffix,output.getvalue(),'application/pdf' if suffix=='.pdf' else 'image/png')
    with app.app_context():
        process_pending();assert summary()=={'ready':1}
    hits=client.get('/api/search?q=Schulkonferenz',base_url='https://localhost').json['items']
    assert len(hits)==1 and hits[0]['kind']=='Anhang'


def test_real_office(app,client):
    if not (shutil.which('libreoffice') or shutil.which('soffice')):pytest.skip('LibreOffice fehlt')
    seed(app,'Plan.rtf',b'{\\rtf1\\ansi Konferenzplanung und Leseband. Gemeinsame Vorbereitung im Kollegium fuer das neue Schuljahr.}','application/rtf')
    with app.app_context():
        process_pending();assert summary()=={'ready':1}
    assert client.get('/api/search?q=Konferenzplanung',base_url='https://localhost').json['total']==1


def test_mixed_pdf_preserves_page_numbers_and_native_text(monkeypatch):
    calls=[]
    def run(program,args,content,deadline,seconds=30):
        calls.append((program,args))
        return ('Digitaler Text zum Leseband '*5+'\f\f').encode() if program=='pdftotext' else b'png'
    monkeypatch.setattr('journal.document_text.run',run)
    monkeypatch.setattr('journal.document_text.ocr',lambda *args:('Schulkonferenz',''))
    pages,status,detail=pdf_text(b'%PDF-demo',time.monotonic()+240)
    assert status=='ready' and pages[1]==(2,'Schulkonferenz')
    assert len([p for p,a in calls if p=='pdftoppm'])==1
    assert calls[1][1][:4]==['-f','2','-l','2']


def test_ocr_failure_retains_searchable_part(monkeypatch):
    monkeypatch.setattr('journal.document_text.run',lambda p,*a,**k:('Leseband '*12+'\f\f').encode() if p=='pdftotext' else b'png')
    def fail(*args):raise ValueError('Tesseract fehlt')
    monkeypatch.setattr('journal.document_text.ocr',fail)
    pages,status,detail=pdf_text(b'%PDF-demo',time.monotonic()+240)
    assert status=='partial' and len(pages)==1 and 'Tesseract fehlt' in detail


def test_office_missing_dependency_and_next_job(app,monkeypatch):
    seed(app,'Plan.docx',b'broken','application/octet-stream')
    seed(app)
    monkeypatch.setattr('journal.pdf_preview.shutil.which',lambda _:None)
    with app.app_context():
        process_pending();assert summary()=={'error':1,'ready':1}


def test_upgrade_requeues_old_index_once(app):
    from journal.db import set_setting
    from journal.attachment_search import init
    seed(app)
    with app.app_context():
        process_pending();set_setting('attachment_extractor_version',1);get_db().commit()
        init();assert summary()=={'pending':1}
        process_pending();init();assert summary()=={'ready':1}
