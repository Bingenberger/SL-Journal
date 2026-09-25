from journal.db import get_db, one, init_db
from journal.participants import institutions


def test_separate_fields_filter_search_and_edit(app,post,client):
    assert post('/person/save',dict(name='Anna Beispiel',role='Leitung',institution='Schulamt Nord')).status_code==200
    post('/person/save',dict(name='Berta Beispiel',role='Sachbearbeitung',institution=' schulamt   nord '))
    post('/person/save',dict(name='Carla Anders',role='Leitung',institution='Schulamt Süd'))
    with app.app_context():
        assert institutions()==['Schulamt Nord','Schulamt Süd']
        person=one("SELECT * FROM people WHERE name='Anna Beispiel'")
        pid=person['id']
        assert person['role']=='Leitung' and person['institution']=='Schulamt Nord'
    response=client.get('/people',query_string={'institution':'SCHULAMT NORD','q':'Leitung'},base_url='https://localhost')
    html=response.get_data(as_text=True)
    assert 'Anna Beispiel' in html and 'Berta Beispiel' not in html and 'Carla Anders' not in html
    data=client.get('/api/autocomplete/participants?q=Schulamt+Nord',base_url='https://localhost').get_json()
    assert len(data['items'])==2
    assert 'Schulamt Nord' in data['items'][0]['detail']
    assert 'Anna Beispiel' in client.get('/people?q=Schulamt+Nord',base_url='https://localhost').get_data(as_text=True)
    post('/person/save',dict(id=pid,name='Anna Beispiel',role='Referentin',institution='Ministerium'))
    with app.app_context():
        assert one('SELECT institution FROM people WHERE id=?',(pid,))['institution']=='Ministerium'
    post('/person/save',dict(id=pid,name='Anna Beispiel',role='Referentin',institution=''))
    with app.app_context(): assert one('SELECT institution FROM people WHERE id=?',(pid,))['institution']==''


def test_existing_combined_values_survive_migration(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role) VALUES('Altbestand','Leitung / Schulamt')")
        db.execute('ALTER TABLE people DROP COLUMN institution')
        db.commit()
        init_db()
        init_db()
        person=one("SELECT * FROM people WHERE name='Altbestand'")
        assert person['role']=='Leitung / Schulamt'
        assert person['institution']==''


def test_legacy_form_preserves_institution(app,post):
    post('/person/save',dict(name='Name',institution='Schulamt'))
    with app.app_context(): pid=one('SELECT id FROM people')['id']
    post('/person/save',dict(id=pid,name='Name',role='Neue Rolle'))
    with app.app_context(): assert one('SELECT institution FROM people')['institution']=='Schulamt'
