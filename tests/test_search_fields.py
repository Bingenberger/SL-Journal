from journal.db import get_db,one,init_db


def test_phone_lifecycle_and_existing_contacts(app,client,post):
    assert post('/person/save',{'name':'Änne','role':'Leitung','institution':'Schulamt','emails':'a@example.org','phone':'+49 221 123456'}).status_code==200
    with app.app_context():pid=one("SELECT id FROM people WHERE name='Änne'")['id']
    assert post('/person/save',{'id':pid,'name':'Änne','role':'Leitung','emails':'a@example.org'}).status_code==200
    with app.app_context():
        init_db();init_db()
        assert one('SELECT phone FROM people WHERE id=?',(pid,))['phone']=='+49 221 123456'
    for path in ['/people?q=123456','/person/'+str(pid)]:
        assert '+49 221 123456' in client.get(path,base_url='https://localhost').text
    for path in ['/api/search?q=123456','/api/search/people?q=123456','/api/autocomplete/people?q=123456']:
        assert client.get(path,base_url='https://localhost').json['items'][0]['label']=='Änne'
    assert post('/person/save',{'id':pid,'name':'Änne','phone':'x'*201}).status_code==400
    assert post('/person/save',{'id':pid,'name':'Änne','phone':''}).status_code==200
    with app.app_context():assert one('SELECT phone FROM people WHERE id=?',(pid,))['phone']==''


def test_migration_old_people_table(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role,institution,emails) VALUES('Bestand','Rolle','Ort','x@example.org')")
        db.commit()
        db.execute('ALTER TABLE people DROP COLUMN phone');db.commit()
        init_db();init_db()
        p=one("SELECT * FROM people WHERE name='Bestand'")
        assert (p['role'],p['institution'],p['emails'],p['phone'])==('Rolle','Ort','x@example.org','')


def test_field_values_scopes_and_auth(app,client):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role,institution,emails,phone) VALUES('Änne','Leitung','Schulamt','a@example.org, b@example.org','0221 1234')")
        db.execute("INSERT INTO people(name,role,institution) VALUES('Berta','leitung','Andere')")
        for status in ['active','closed']:
            db.execute('INSERT INTO projects(name,description,status,school_year) VALUES(?,?,?,?)',('Treffer '+status,'Inhalt',status,'2026/27'))
        for status in ['open','clarifying','done']:
            db.execute('INSERT INTO cases(title,status) VALUES(?,?)',('Treffer '+status,status))
        for done in [0,1]:db.execute('INSERT INTO tasks(text,done) VALUES(?,?)',('Treffer '+str(done),done))
        db.execute("INSERT INTO entries(date,type,title,body,tags) VALUES('2026-09-24','note','Titel','Volltextprobe','Schule')")
        db.commit()
    def get(path):
        r=client.get(path,base_url='https://localhost');assert r.status_code==200;return r.json['items']
    assert len(get('/api/contact-values/role?q=LEIT'))==1
    assert get('/api/contact-values/name?q=ÄNNE')[0]['label']=='Änne'
    assert get('/api/contact-values/emails?q=B@')[0]['label']=='b@example.org'
    assert get('/api/contact-values/phone?q=1234')[0]['label']=='0221 1234'
    assert get('/api/search/people?q=leitung&institution=schulamt')[0]['label']=='Änne'
    assert len(get('/api/search/people?q=leitung&institution=schulamt'))==1
    assert get('/api/search/projects?q=TREFFER&status=closed')[0]['label']=='Treffer closed'
    assert len(get('/api/search/cases?q=TREFFER'))==2
    assert get('/api/search/cases?q=TREFFER&status=done')[0]['label']=='Treffer done'
    assert get('/api/search/tasks?q=TREFFER&filter=done')[0]['label']=='Treffer 1'
    assert not get('/api/search/tasks?q=TREFFER&due=today')
    assert not get('/api/search/tasks?q=TREFFER&project_id=999')
    assert get('/api/search/entries?q=VOLLtext')[0]['label']=='Titel'
    assert not get('/api/search/entries?q=VOLLtext&type=protocol')
    assert not get('/api/search/entries?q=VOLLtext&inbox=1')
    assert not get('/api/search/entries?q=VOLLtext&tag=andere')
    assert get('/api/search/tags?q=SCHU')[0]['label']=='Schule'
    assert client.get('/api/contact-values/password',base_url='https://localhost').status_code==404
    anon=app.test_client()
    for path in ['/api/contact-values/name?q=a','/api/search/people?q=a']:
        assert anon.get(path,base_url='https://localhost').status_code==302
