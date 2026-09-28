"""#Tags im Fließtext und das Feld „Gleiche Tags“ am Eintrag."""
from journal.db import get_db, one
from journal.domain import entry_details, save_entry, save_task
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
        gruppen = verwandte(entry_details(one('SELECT * FROM entries WHERE id=?', (eid,))))['tags']
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
        assert 'Verwandte Einträge' not in seite


def test_feld_verlinkt_die_vollstaendige_liste(app, client):
    with app.app_context():
        eid = anlegen('Abstimmung', '2026-09-25', 'Schulfest')
        for n in range(6):
            anlegen(f'Fest {n}', f'2026-09-{10+n:02d}', 'Schulfest')
        get_db().commit()
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert 'Verwandte Einträge' in seite
    assert 'Alle 6 ansehen' in seite
    assert 'tag=Schulfest' in seite


def test_umschalter_nur_bei_mehreren_arten(app, client):
    with app.app_context():
        db = get_db()
        pid = db.execute("INSERT INTO projects(name,school_year) VALUES('Schulfest','2026/27')").lastrowid
        eid = anlegen('Abstimmung', '2026-09-25', 'Schulfest')
        weiterer = anlegen('Planung', '2026-09-20', 'Schulfest')
        for e in (eid, weiterer):
            db.execute('INSERT INTO entry_projects VALUES(?,?)', (e, pid))
        allein = anlegen('Nur Tag', '2026-09-24', 'Schulfest')
        db.commit()
        gruppen = verwandte(entry_details(one('SELECT * FROM entries WHERE id=?', (eid,))))
        assert [g['name'] for g in gruppen['tags']] == ['Schulfest']
        assert [g['name'] for g in gruppen['projects']] == ['Schulfest']
        assert gruppen['cases'] == []
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert 'data-relation="tags"' in seite and 'data-relation="projects"' in seite
    assert 'data-relation="cases"' not in seite, 'ohne Vorgang keine Schaltfläche'
    # Ein Eintrag mit nur einer Art bekommt gar keinen Umschalter.
    seite = client.get(f'/entry/{allein}', base_url='https://localhost').get_data(as_text=True)
    assert 'Verwandte Einträge' in seite and 'relation-switch' not in seite


def test_vorgang_gruppiert_und_verlinkt(app, client):
    with app.app_context():
        db = get_db()
        cid = db.execute("INSERT INTO cases(title,status) VALUES('Betreuung klären','open')").lastrowid
        eid = anlegen('Erstes Gespräch', '2026-09-25', '')
        for titel, datum in [('Rückruf Schulamt', '2026-09-22'), ('Elterngespräch', '2026-09-18')]:
            db.execute('INSERT INTO entry_cases VALUES(?,?)', (anlegen(titel, datum, ''), cid))
        db.execute('INSERT INTO entry_cases VALUES(?,?)', (eid, cid))
        db.commit()
        gruppen = verwandte(entry_details(one('SELECT * FROM entries WHERE id=?', (eid,))))
        assert gruppen['tags'] == []
        vorgang = gruppen['cases'][0]
        assert vorgang['name'] == 'Betreuung klären' and vorgang['gesamt'] == 2
        assert [e['title'] for e in vorgang['eintraege']] == ['Rückruf Schulamt', 'Elterngespräch']
    seite = client.get(f'/entry/{eid}', base_url='https://localhost').get_data(as_text=True)
    assert f'/case/{cid}' in seite
