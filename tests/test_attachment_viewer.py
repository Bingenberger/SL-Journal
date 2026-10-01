"""PDF-Anhänge im Betrachter des Browsers öffnen."""
from journal.db import get_db, one
from journal.domain import save_attachment, save_entry

import sys
sys.path.insert(0, 'scripts')
from pdf_fixture import sample_pdf


def anhaenge(app):
    with app.app_context():
        eid = save_entry(dict(title='Mail mit Anhang', date='2026-10-01', type='mail_in'))
        save_attachment(eid, 'Bildungschancen.pdf', sample_pdf(), 'application/pdf')
        save_attachment(eid, 'Original.eml', b'Von: a@b.de\n\nText', 'message/rfc822')
        get_db().commit()
        kennung = lambda name: one('SELECT id FROM attachments WHERE name=?', (name,))['id']
        return eid, kennung('Bildungschancen.pdf'), kennung('Original.eml')


def test_pdf_wird_inline_mit_eigenem_typ_ausgeliefert(app, client):
    _, pdf, _ = anhaenge(app)
    antwort = client.get(f'/attachment/{pdf}/inline', base_url='https://localhost')
    assert antwort.status_code == 200
    assert antwort.mimetype == 'application/pdf'
    assert antwort.headers['Content-Disposition'].startswith('inline')
    assert 'Bildungschancen.pdf' in antwort.headers['Content-Disposition']
    assert antwort.headers['X-Content-Type-Options'] == 'nosniff'


def test_betrachter_bekommt_eine_eigene_richtlinie(app, client):
    _, pdf, _ = anhaenge(app)
    richtlinie = client.get(f'/attachment/{pdf}/inline', base_url='https://localhost') \
        .headers['Content-Security-Policy']
    # Der eingebettete Betrachter braucht object-src; alles Übrige bleibt zu.
    assert "object-src 'self'" in richtlinie
    assert "default-src 'none'" in richtlinie
    assert "script-src" not in richtlinie


def test_nur_pdf_wird_inline_gereicht(app, client):
    """Eine inline ausgelieferte HTML- oder EML-Datei wäre ein fremdes Dokument
    auf der eigenen Herkunft."""
    _, _, eml = anhaenge(app)
    assert client.get(f'/attachment/{eml}/inline', base_url='https://localhost').status_code == 415


def test_herunterladen_bleibt_ein_download(app, client):
    _, pdf, _ = anhaenge(app)
    antwort = client.get(f'/attachment/{pdf}', base_url='https://localhost')
    assert antwort.headers['Content-Disposition'].startswith('attachment')
    assert antwort.mimetype == 'application/octet-stream'


def test_zeile_zeigt_beide_wege(app, client):
    eid, pdf, eml = anhaenge(app)
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert f'/attachment/{pdf}/inline' in seite
    assert 'attachment-actions' in seite
    assert f'/attachment/{eml}/inline' not in seite, 'nur PDF bekommt den Betrachter'


def test_betrachter_verlangt_anmeldung(app):
    _, pdf, _ = anhaenge(app)
    anonym = app.test_client()
    antwort = anonym.get(f'/attachment/{pdf}/inline', base_url='https://localhost')
    assert antwort.status_code in (302, 401, 403)
