"""Die Mailkarten im Tagescockpit: Richtung, Beteiligte, Zuordnungen, Aktionen."""
import re
from journal.db import get_db, one
from journal.domain import save_entry, save_attachment, now


def seed(app):
    with app.app_context():
        db = get_db()
        pid = db.execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')").lastrowid
        cid = db.execute("INSERT INTO cases(title,status) VALUES('Beschwerde 3a','open')").lastrowid
        heute = now().date().isoformat()
        ein = save_entry(dict(type='mail_in', date=heute, time='08:42', title='Rückmeldung zum Helferplan',
            sender='Sabine Meier <s.meier@fv.example>', recipients='leitung@schule.de',
            body='Text', tags='Organisation'), [pid])
        save_attachment(ein, 'Helferplan.pdf', b'%PDF-1.4 x', 'application/pdf')
        db.execute('INSERT INTO entry_cases VALUES(?,?)', (ein, cid))
        save_entry(dict(type='mail_out', date=heute, time='09:30', title='AW: Helferplan',
            sender='leitung@schule.de',
            recipients='Sabine Meier <s.meier@fv.example>, Förderverein <info@fv.example>, Hausmeister <h@x.de>',
            body='Danke'), [])
        db.commit()
        return ein


def karte(seite, titel):
    """Den Ausschnitt einer Mailkarte herausschneiden."""
    start = seite.index('<article class="mail-card')
    while start != -1:
        ende = seite.index('</article>', start)
        if titel in seite[start:ende]:
            return seite[start:ende]
        start = seite.find('<article class="mail-card', ende)
    raise AssertionError(f'Keine Mailkarte mit {titel!r}')


def test_direction_person_chips_and_actions(app, client):
    seed(app)
    seite = client.get('/', base_url='https://localhost').text
    eingang = karte(seite, 'Rückmeldung zum Helferplan')
    ausgang = karte(seite, 'AW: Helferplan')

    assert 'mail-card incoming' in eingang and 'mail-card outgoing' in ausgang
    assert '#i-mailin' in eingang and '#i-mailout' in ausgang
    assert 'Eingegangen von' in eingang and 'Gesendet an' in ausgang

    # Beteiligte: eingehend der Absender, ausgehend die Empfänger – als Namen, nicht als Adressen.
    assert re.search(r'entry-person.*?Sabine Meier', eingang, re.S)
    assert 's.meier@fv.example' not in eingang
    assert 'Sabine Meier, Förderverein und 1 weitere' in ausgang

    # Zuordnungen tragen je ein eigenes Symbol.
    for klasse, symbol, text in [('pill-case', 'cases', 'Beschwerde 3a'),
                                 ('pill-project', 'projects', 'Schulfest'),
                                 ('pill-tag', 'tags', 'Organisation'),
                                 ('pill-file', 'attachment', '1 Anhang')]:
        treffer = re.search(r'class="pill ' + klasse + r'"[^>]*>(.*?)</(?:a|span)>', eingang, re.S)
        assert treffer, klasse
        assert '#i-' + symbol in treffer.group(1) and text in treffer.group(1)
    assert '1 Anhänge' not in eingang, 'Einzahl bei genau einem Anhang'

    # Aktionen sind Schaltflächen, keine Textzeilen.
    aktionen = eingang[eingang.index('entry-actions'):]
    assert aktionen.count('class="mini-button"') == 2
    assert 'data-new-task' in aktionen and 'data-attach-note' in aktionen
    assert 'Uhrzeit' not in eingang and '08:42' in eingang
    assert '24.09' not in eingang and 'Mail · Eingang' not in eingang, 'Datum und Typ sind im Tagesbezug redundant'


def test_missing_sender_is_named_and_flagged(app, client):
    with app.app_context():
        save_entry(dict(type='mail_in', date=now().date().isoformat(), time='07:00',
                        title='Weiterleitung ohne Absender', sender='', needs_review=True))
        get_db().commit()
    eingang = karte(client.get('/', base_url='https://localhost').text, 'Weiterleitung ohne Absender')
    assert 'Beteiligte bitte ergänzen' in eingang
    assert 'Angaben prüfen' in eingang


def test_other_views_keep_the_full_entry_card(app, client):
    ein = seed(app)
    seite = client.get(f'/entries', base_url='https://localhost').text
    assert 'mail-card' not in seite and 'entry-card' in seite
    assert client.get(f'/entry/{ein}', base_url='https://localhost').status_code == 200


def test_name_filter_leaves_free_text_alone(app):
    """Beteiligte werden von Hand eingetragen; nur echte Kopfzeilen werden gekürzt."""
    filtern = app.jinja_env.filters['mail_names']
    assert filtern('Frau Klein; Herr Bauer', 3) == 'Frau Klein; Herr Bauer'
    assert filtern('Sabine Meier · Förderverein', 3) == 'Sabine Meier · Förderverein'
    assert filtern('Anna Müller <anna@x.de>; Herr Ohne Adresse', 3) == 'Anna Müller <anna@x.de>; Herr Ohne Adresse'
    assert filtern('"Sabine Meier" <s@x.de>; "Leitung" <l@y.de>', 3) == 'Sabine Meier, Leitung'
    assert filtern('A <a@x.de>, B <b@x.de>, C <c@x.de>, D <d@x.de>', 2) == 'A, B und 2 weitere'
    assert filtern('kollegium@schule.de', 3) == 'kollegium@schule.de'
    assert filtern('', 3) == '' and filtern(None, 3) == ''


def test_entry_cards_show_participants_verbatim(app, client):
    from journal.domain import save_entry
    with app.app_context():
        save_entry(dict(type='meeting', date=now().date().isoformat(), time='11:20',
                        title='Steuergruppe', participants='Frau Klein; Herr Bauer'))
        get_db().commit()
    seite = client.get('/', base_url='https://localhost').text
    assert 'Frau Klein; Herr Bauer' in seite
    assert '#i-person' in seite
