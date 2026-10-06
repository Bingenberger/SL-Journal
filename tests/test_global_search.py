from journal.db import get_db


def seed(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role,institution,emails) VALUES('Änne Müller','Leitung','Schulamt','anne@example.org')")
        db.execute("INSERT INTO projects(name,description,school_year,status) VALUES('Bauplanung','Versteckter Prüfbegriff','2026/27','closed')")
        db.execute("INSERT INTO cases(title,description,status) VALUES('Anfrage','Versteckter Prüfbegriff','done')")
        db.execute("INSERT INTO tasks(text,done) VALUES('PRÜFBEGRIFF erledigen',1)")
        db.execute("INSERT INTO entries(date,type,title,body,agenda,decisions) VALUES('2026-09-24','protocol','Sitzung','Versteckter Prüfbegriff','Tagesordnungspunkt','Beschlussinhalt')")
        db.commit()


def test_global_search_scope_and_case(app,client):
    seed(app)
    def search(q):
        response=client.get('/api/search',query_string={'q':q},base_url='https://localhost')
        assert response.status_code==200
        return response.json
    lower=search('prüfbegriff')
    assert lower==search('PRÜFBEGRIFF')
    assert {'Aufgabe','Projekt','Vorgang'} <= {r['kind'] for r in lower['items']}
    assert any(r['label']=='Sitzung' for r in lower['items'])
    for query in ['ÄNNE MÜLLER','SCHULAMT','LEITUNG','ANNE@EXAMPLE.ORG']:
        assert any(r['kind']=='Kontakt' for r in search(query)['items'])
    for query in ['TAGESORDNUNGSPUNKT','BESCHLUSSINHALT']:
        assert any(r['label']=='Sitzung' for r in search(query)['items'])
    assert search('versteckter prüfbegriff')['total']==3
    assert search('')['total']==0
    for query in ['"','*','OR NOT','<script>alert(1)</script>']:
        search(query)


def test_search_pagination_auth_and_escaping(app,client):
    with app.app_context():
        db=get_db()
        db.executemany('INSERT INTO tasks(text) VALUES(?)',[(f'Treffer {i}',) for i in range(45)])
        db.execute("INSERT INTO tasks(text) VALUES('<script>Treffer</script>')")
        db.commit()
    response=client.get('/api/search?q=TREFFER',base_url='https://localhost').json
    assert len(response['items'])==10 and response['more'] and response['total']==46
    first=client.get('/search?q=treffer',base_url='https://localhost').text
    second=client.get('/search?q=treffer&page=2',base_url='https://localhost').text
    assert first.count('class="search-result"')==40
    assert second.count('class="search-result"')==6
    assert '<script>Treffer</script>' not in first+second
    assert '&lt;script&gt;Treffer&lt;/script&gt;' in first+second
    anonymous=app.test_client()
    for path in ['/search?q=treffer','/api/search?q=treffer']:
        assert anonymous.get(path,base_url='https://localhost').status_code==302


def test_entry_results_stay_in_date_order(app,client):
    with app.app_context():
        db=get_db()
        db.executemany("INSERT INTO entries(date,type,title) VALUES(?,'note',?)",
            [('2026-01-05','Ordnung alt'),('2026-09-20','Ordnung neu'),('2026-05-10','Ordnung mitte')])
        db.commit()
    items=client.get('/api/search?q=Ordnung',base_url='https://localhost').json['items']
    assert [item['label'] for item in items]==['Ordnung neu','Ordnung mitte','Ordnung alt']


def arten(client,**args):
    from urllib.parse import urlencode
    seite=client.get('/search?'+urlencode(args),base_url='https://localhost')
    return seite


def test_trefferfilter_nach_art(app,client):
    from journal.db import get_db
    from journal.domain import save_entry,save_task
    from journal.resources import search
    with app.test_request_context('/'):
        for titel,typ in [('Konferenz Betreuung','protocol'),('Nachlese Betreuung','protocol'),
                          ('Betreuung besprochen','meeting'),('Notiz Betreuung','note')]:
            save_entry(dict(title=titel,date='2026-10-06',type=typ))
        save_task(dict(text='Betreuung klären'))
        get_db().commit()
        offen=search('Betreuung',fulltext=True,limit=40)
        zaehlung={a['name']:a['count'] for a in offen['kinds']}
        assert zaehlung=={'Protokoll':2,'Gespräch':1,'Notiz':1,'Aufgabe':1}
        assert offen['total']==5 and offen['all_total']==5
        # Die Reihenfolge folgt den Eintragsarten, danach das Übrige.
        assert [a['name'] for a in offen['kinds']]==['Gespräch','Protokoll','Notiz','Aufgabe']

        gefiltert=search('Betreuung',fulltext=True,limit=40,kind='Protokoll')
        assert gefiltert['total']==2, 'nur die Protokolle'
        assert gefiltert['all_total']==5, 'die Zahlen der Chips bleiben die des ganzen Bestands'
        assert {i['kind'] for i in gefiltert['items']}=={'Protokoll'}
        assert {a['name'] for a in gefiltert['kinds']}==set(zaehlung), 'alle Arten bleiben wählbar'

        assert search('Betreuung',fulltext=True,limit=40,kind='Gibtsnicht')['total']==0


def test_filter_in_der_oberflaeche(app,client):
    from journal.db import get_db
    from journal.domain import save_entry
    with app.app_context():
        save_entry(dict(title='Konferenz Betreuung',date='2026-10-06',type='protocol'))
        save_entry(dict(title='Notiz Betreuung',date='2026-10-06',type='note'))
        get_db().commit()
    seite=arten(client,q='Betreuung').get_data(as_text=True)
    assert 'kind-filter' in seite and 'kind=Protokoll' in seite
    gefiltert=arten(client,q='Betreuung',kind='Protokoll').get_data(as_text=True)
    assert 'Konferenz Betreuung' in gefiltert and 'Notiz Betreuung' not in gefiltert
    assert '1 Treffer von 2' in gefiltert
    # Das Blättern muss den Filter mitnehmen.
    assert 'kind=Protokoll' in gefiltert
    leer=arten(client,q='Betreuung',kind='Telefonat').get_data(as_text=True)
    assert 'Keine Treffer der Art' in leer and 'Filter aufheben' in leer


def test_ein_einziger_treffertyp_bekommt_keinen_filter(app,client):
    from journal.db import get_db
    from journal.domain import save_entry
    with app.app_context():
        save_entry(dict(title='Einzelstück',date='2026-10-06',type='note'))
        get_db().commit()
    seite=arten(client,q='Einzelstück').get_data(as_text=True)
    assert 'kind-filter' not in seite, 'eine Art allein braucht keine Auswahl'
