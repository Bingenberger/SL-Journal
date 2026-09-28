"""#Tags im Fließtext und das Feld „Gleiche Tags“ am Eintrag."""
from journal.db import get_db, one
from journal.domain import save_entry, save_task
from journal.tags import inline_tags, merge_tags, verwandte


def test_erkennung_im_text():
    assert inline_tags('#Schulfest steht an') == ['Schulfest']
    assert inline_tags('Wir planen #Schulfest und #Kollegium.') == ['Schulfest', 'Kollegium']
    assert inline_tags('## Beschlüsse', '# Titel') == []
    assert inline_tags('foo#bar', 'https://x.de/s#anker', '#1 Platz') == []
    assert inline_tags('#Über-Uns und #a_b') == ['Über-Uns', 'a_b']


def test_feld_und_text_werden_zusammengefuehrt():
    assert merge_tags('Organisation', 'Dazu #Schulfest planen') == 'Organisation, Schulfest'
    # Das Feld gewinnt die Schreibweise, das Doppel entfällt.
    assert merge_tags('Schulfest', 'Zum #schulfest') == 'Schulfest'
    assert merge_tags('', 'Nur #Kollegium') == 'Kollegium'


def test_eintrag_uebernimmt_tags_aus_dem_text(app):
    with app.app_context():
        eid = save_entry(dict(title='Notiz', date='2026-09-28', tags='Organisation',
                              body='Beim #Schulfest wird es eng.'))
        assert one('SELECT tags FROM entries WHERE id=?', (eid,))['tags'] == 'Organisation, Schulfest'


def test_protokollfelder_zaehlen_mit(app):
    with app.app_context():
        eid = save_entry(dict(title='Konferenz', date='2026-09-28', type='protocol',
                              agenda='TOP 1 #Schulfest', decisions='Beschlossen: #Kollegium informieren'))
        assert one('SELECT tags FROM entries WHERE id=?', (eid,))['tags'] == 'Schulfest, Kollegium'


def test_aufgabe_uebernimmt_tags_aus_dem_text(app):
    with app.app_context():
        tid = save_task(dict(text='Raumplan für #Schulfest abstimmen'))
        assert one('SELECT tags FROM tasks WHERE id=?', (tid,))['tags'] == 'Schulfest'


def test_darstellung(app):
    with app.test_request_context('/'):
        md = app.jinja_env.filters['md']
        assert '<a class="inline-tag" href="/entries?tag=Schulfest">#Schulfest</a>' in str(md('#Schulfest steht an'))
        assert str(md('# Echte Überschrift')) == '<h1>Echte Überschrift</h1>'
        assert str(md('## Beschlüsse')) == '<h2>Beschlüsse</h2>'
        assert '<code>#Schulfest</code>' in str(md('Code: `#Schulfest`'))


def anlegen(titel, datum, tags, typ='note'):
    return get_db().execute('INSERT INTO entries(date,type,title,tags,body) VALUES(?,?,?,?,?)',
                            (datum, typ, titel, tags, '')).lastrowid


def test_gleiche_tags_gruppiert_je_tag(app):
    with app.app_context():
        eid = anlegen('Abstimmung', '2026-09-25', 'Schulfest, Organisation')
        for n in range(6):
            anlegen(f'Fest {n}', f'2026-09-{10+n:02d}', 'Schulfest')
        anlegen('Dienstbesprechung', '2026-09-22', 'Organisation')
        anlegen('Ohne Bezug', '2026-09-24', 'Kollegium')
        get_db().commit()
        gruppen = verwandte(one('SELECT * FROM entries WHERE id=?', (eid,)))
        assert [g['name'] for g in gruppen] == ['Schulfest', 'Organisation']
        fest = gruppen[0]
        assert fest['gesamt'] == 6 and len(fest['eintraege']) == 5, 'höchstens fünf je Tag'
        assert [e['title'] for e in fest['eintraege']] == [f'Fest {n}' for n in (5, 4, 3, 2, 1)], 'neueste zuerst'
        assert all(e['id'] != eid for g in gruppen for e in g['eintraege']), 'ohne den Eintrag selbst'


def test_feld_erscheint_nur_bei_treffern(app, client):
    with app.app_context():
        allein = anlegen('Einsam', '2026-09-25', 'Einmalig')
        ohne = anlegen('Ohne Tags', '2026-09-25', '')
        get_db().commit()
    for eid in (allein, ohne):
        seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
        assert 'Gleiche Tags' not in seite


def test_feld_verlinkt_die_vollstaendige_liste(app, client):
    with app.app_context():
        eid = anlegen('Abstimmung', '2026-09-25', 'Schulfest')
        for n in range(6):
            anlegen(f'Fest {n}', f'2026-09-{10+n:02d}', 'Schulfest')
        get_db().commit()
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert 'Gleiche Tags' in seite
    assert 'Alle 6 ansehen' in seite
    assert 'tag=Schulfest' in seite
