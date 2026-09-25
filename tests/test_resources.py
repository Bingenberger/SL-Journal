from journal.db import get_db
from journal.domain import school_year


def test_resource_search_types_metadata_and_local_links(app,post,client):
    post('/person/save',dict(name='Anna Linktest',role='Leitung',institution='Schulamt'))
    post('/project/save',dict(name='Projekt Linktest',school_year=school_year()))
    post('/entry/save',dict(title='Konferenz Linktest',type='meeting',date='2026-09-22',tags='Linktest & Planung'))
    post('/task/save',dict(text='Aufgabe Linktest'))
    data=client.get('/api/resources?q=Linktest',base_url='https://localhost').get_json()
    assert {item['kind'] for item in data['items']}=={'Kontakt','Projekt','Gespräch','Tag','Aufgabe'}
    assert all(item['url'].startswith('/') and not item['url'].startswith('//') for item in data['items'])
    for item in data['items']:
        assert client.get(item['url'],base_url='https://localhost').status_code==200
    assert client.get('/api/resources?q=Schulamt',base_url='https://localhost').get_json()['items'][0]['kind']=='Kontakt'
    assert client.get('/api/resources?q=Sitzungsprotokoll',base_url='https://localhost').get_json()['items'][0]['kind']=='Gespräch'


def test_resources_bounded_and_authenticated(app,client):
    with app.app_context():
        db=get_db()
        db.executemany('INSERT INTO people(name) VALUES(?)',[(f'Kontakt {i}',) for i in range(40)])
        db.commit()
    data=client.get('/api/resources',base_url='https://localhost').get_json()
    assert len(data['items'])==20 and data['more']
    assert client.get('/api/resources?q=unbekannt',base_url='https://localhost').get_json()['items']==[]
    anonymous=app.test_client().get('/api/resources',base_url='https://localhost')
    assert anonymous.status_code in (302,401)


def test_resource_labels_preserve_special_characters(app,post,client):
    name='Test [A] *B* <C>'
    post('/person/save',dict(name=name))
    data=client.get('/api/resources?q=Test',base_url='https://localhost').get_json()
    assert data['items'][0]['label']==name
    assert data['items'][0]['url']=='/person/1'
