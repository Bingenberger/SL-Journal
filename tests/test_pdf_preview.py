import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from journal.db import get_db,rows
from journal.domain import save_attachment,save_entry
from journal.pdf_preview import render_pdf
from scripts.pdf_fixture import sample_pdf


def seed(app,content=None,name='Plan.PDF',mime='application/octet-stream'):
    with app.app_context():
        eid=save_entry(dict(title='PDF',date='2026-09-22'))
        save_attachment(eid,name,content if content is not None else sample_pdf(),mime)
        get_db().commit()


def test_first_page_preview_authentication_and_download(app,client):
    original=sample_pdf()
    seed(app,original)
    response=client.get('/attachment/1/preview',base_url='https://localhost')
    assert response.status_code==200 and response.mimetype=='image/png'
    assert response.headers['Cache-Control']=='no-store'
    assert "object-src 'none'" in response.headers['Content-Security-Policy']
    image=Image.open(io.BytesIO(response.data))
    assert max(image.size)==1100
    assert image.convert('RGB').getpixel((50,image.height-30))==(255,255,255)
    download=client.get('/attachment/1',base_url='https://localhost')
    assert download.data==original
    assert download.headers['Content-Disposition'].startswith('attachment;')
    assert app.test_client().get('/attachment/1/preview',base_url='https://localhost').status_code==302
    assert client.get('/attachment/999/preview',base_url='https://localhost').status_code==404
    with app.app_context():
        files=list((Path(app.instance_path)/'attachments').iterdir())
        assert len(files)==1 and not files[0].read_bytes().startswith(b'%PDF-')
    assert not list((Path(app.instance_path)/'cache').iterdir())


def test_invalid_non_pdf_and_missing_attachment(app,client):
    seed(app,b'not a PDF')
    assert client.get('/attachment/1/preview',base_url='https://localhost').status_code==400
    with app.app_context():
        path=rows('SELECT path FROM attachments')[0]['path']
        (Path(app.instance_path)/'attachments'/path).unlink()
    assert client.get('/attachment/1/preview',base_url='https://localhost').status_code==404
    seed(app,b'plain text','Notiz.txt','text/plain')
    assert client.get('/attachment/2/preview',base_url='https://localhost').status_code==415


def test_renderer_missing_timeout_and_error(monkeypatch):
    monkeypatch.setattr('journal.pdf_preview.shutil.which',lambda name:None)
    with pytest.raises(RuntimeError): render_pdf(sample_pdf())
    monkeypatch.setattr('journal.pdf_preview.shutil.which',lambda name:'/usr/bin/pdftoppm')
    def timeout(*args,**kwargs): raise subprocess.TimeoutExpired('pdftoppm',15)
    monkeypatch.setattr('journal.pdf_preview.subprocess.run',timeout)
    with pytest.raises(ValueError,match='dauert zu lange'): render_pdf(sample_pdf())
    monkeypatch.setattr('journal.pdf_preview.subprocess.run',lambda *args,**kwargs:subprocess.CompletedProcess(args,1,b''))
    with pytest.raises(ValueError,match='geschützt oder beschädigt'): render_pdf(sample_pdf())
