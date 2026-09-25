import json

from journal.db import get_db, one, rows, init_db
from journal.domain import save_entry
from journal.participants import participant_items, suggestions


def entry_data(items,title='Abstimmung'):
    return dict(title=title,date='2026-09-22',type='meeting',participant_items=json.dumps(items))


def test_known_and_new_participants_are_single_source(app,post,client):
    post('/person/save',dict(name='Anna Müller',role='Sekretariat',emails='anna@example.org'))
    response=post('/entry/save',entry_data([
        dict(kind='person',id=1,label='Manipulierter Anzeigename'),
        dict(kind='new',label='Anna Müller'),
        dict(kind='new',label='  Ben   Beispiel '),
        dict(kind='new',label='ben beispiel'),
    ]))
    assert response.status_code==200
    with app.app_context():
        assert one('SELECT participants FROM entries')['participants']=='Anna Müller; Ben Beispiel'
        assert len(rows('SELECT * FROM entry_people'))==1
        assert len(rows('SELECT * FROM contact_suggestions'))==1
        assert len(rows('SELECT * FROM people'))==1
        assert len(participant_items(1))==2
    detail=client.get('/api/entry/1',base_url='https://localhost').json
    assert detail['participant_items'][0]['kind']=='person'
    assert detail['participant_items'][1]['kind']=='new'


def test_suggestion_acceptance_links_all_entries_and_is_idempotent(app,post,client):
    for title in ('Besprechung','Telefonat'):
        assert post('/entry/save',entry_data([dict(kind='new',label='Ben Beispiel')],title)).status_code==200
    with app.app_context():
        suggestion=suggestions()[0]
        assert suggestion['entry_count']==2 and len(suggestion['entries'])==2
    accepted=post('/person/save',dict(suggestion_id=suggestion['id'],name='Benjamin Beispiel',role='Schulträger',emails='ben@example.org'))
    assert accepted.status_code==200
    assert post('/person/save',dict(suggestion_id=suggestion['id'],name='Ben erneut')).status_code==400
    with app.app_context():
        assert len(rows('SELECT * FROM people'))==1
        assert len(rows('SELECT * FROM entry_people'))==2
        assert suggestions()==[]
        assert all(e['participants']=='Benjamin Beispiel' for e in rows('SELECT participants FROM entries'))
    assert 'Besprechung' in client.get('/person/1',base_url='https://localhost').text
    post('/entry/save',entry_data([dict(kind='new',label='Ben Beispiel')],'Folgetermin'))
    with app.app_context():
        assert one('SELECT person_id FROM entry_people WHERE entry_id=3')['person_id']==1
        assert not suggestions()


def test_suggestion_merge_into_existing_and_contact_rename(app,post,client):
    post('/entry/save',entry_data([dict(kind='new',label='Frau Beispiel')]))
    post('/person/save',dict(name='Beate Beispiel',emails='beate@example.org'))
    assert post('/suggestion/1/link',{'person_id':'999'}).status_code==400
    assert post('/suggestion/1/link',{'person_id':'1'}).status_code==200
    with app.app_context():
        assert len(rows('SELECT * FROM people'))==1
        assert one('SELECT participants FROM entries')['participants']=='Beate Beispiel'
    post('/person/save',dict(id=1,name='Beate Neu',role='Kollegium'))
    with app.app_context():
        assert one('SELECT participants FROM entries')['participants']=='Beate Neu'
    assert 'Abstimmung' in client.get('/entries?q=Neu',base_url='https://localhost').text


def test_manual_contact_creation_resolves_matching_suggestions(app,post):
    post('/entry/save',entry_data([dict(kind='new',label='Max Muster')]))
    post('/person/save',dict(name='max muster'))
    with app.app_context():
        assert suggestions()==[]
        assert one('SELECT person_id FROM entry_people')['person_id']==1


def test_ignored_suggestion_survives_edit_and_can_be_restored(app,post):
    post('/entry/save',entry_data([dict(kind='new',label='Kein Kontakt')]))
    assert post('/suggestion/1/status',{'status':'ignored'}).status_code==200
    post('/entry/save',dict(entry_data([dict(kind='new',label='Kein Kontakt')]),id=1))
    with app.app_context():
        assert suggestions()==[]
        assert len(suggestions('ignored'))==1
        assert participant_items(1)[0]['label']=='Kein Kontakt'
    assert post('/suggestion/1/status',{'status':'pending'}).status_code==200
    with app.app_context(): assert len(suggestions())==1


def test_removing_or_deleting_participants_cleans_pending_names(app,post):
    post('/entry/save',entry_data([dict(kind='new',label='Entfernen')]))
    post('/entry/save',dict(entry_data([]),id=1))
    with app.app_context():
        assert rows('SELECT * FROM contact_suggestions')==[]
        assert participant_items(1)==[]
    post('/entry/save',entry_data([dict(kind='new',label='Löschen')]))
    post('/entry/2/delete')
    with app.app_context(): assert rows('SELECT * FROM contact_suggestions')==[]


def test_invalid_participants_roll_back_edit(app,post):
    post('/entry/save',entry_data([dict(kind='new',label='Vorhanden')],'Original'))
    for invalid in ('oops','{}',json.dumps([dict(kind='person',id=777)])):
        assert post('/entry/save',dict(id=1,title='Falsch',date='2026-09-22',participant_items=invalid)).status_code==400
    with app.app_context():
        assert one('SELECT title FROM entries')['title']=='Original'
        assert participant_items(1)[0]['label']=='Vorhanden'


def test_authenticated_bounded_search_for_100_contacts_projects_and_tags(app,post,client):
    with app.app_context():
        for i in range(105):
            get_db().execute('INSERT INTO people(name,role,emails) VALUES(?,?,?)',(f'Kontakt {i:03}','Sekretariat' if i==104 else 'Kollegium',f'kontakt{i}@example.org'))
        get_db().commit()
    assert len(client.get('/api/autocomplete/participants',base_url='https://localhost').json['items'])==12
    assert client.get('/api/autocomplete/participants',base_url='https://localhost').json['more']
    for query in ['Sekretariat','kontakt104@example.org','Kontakt 104']:
        result=client.get('/api/autocomplete/participants',query_string={'q':query},base_url='https://localhost').json['items']
        assert len(result)==1 and result[0]['id']==105
    assert app.test_client().get('/api/autocomplete/participants',base_url='https://localhost').status_code==302
    post('/project/save',dict(name='Schulfest',school_year='2026/27'))
    post('/entry/save',dict(entry_data([]),tags='Öffentlichkeit, Schule',projects='1'))
    assert client.get('/api/autocomplete/tags?q=öffentlich',base_url='https://localhost').json['items'][0]['label']=='Öffentlichkeit'
    assert client.get('/api/autocomplete/projects?q=schul',base_url='https://localhost').json['items'][0]['id']==1
    post('/project/1/status')
    assert client.get('/api/autocomplete/projects?q=schul',base_url='https://localhost').json['items']==[]
    assert client.get('/api/autocomplete/projects?q=schul&include_closed=1',base_url='https://localhost').json['items'][0]['id']==1


def test_existing_text_and_contact_links_are_migrated_without_duplicates(app):
    with app.app_context():
        db=get_db()
        db.execute("INSERT INTO people(name,role,emails) VALUES('Anna Müller','Lehrkraft','anna@example.org')")
        eid=db.execute("INSERT INTO entries(date,type,title,participants) VALUES('2026-09-22','meeting','Alt','Anna Müller; Ben Beispiel')").lastrowid
        db.execute('INSERT INTO entry_people VALUES(?,1)',(eid,))
        db.execute("DELETE FROM settings WHERE key='participants_migration_v1'")
        db.commit()
        init_db()
        assert len(participant_items(eid))==2
        assert len(rows('SELECT * FROM entry_people'))==1
        assert suggestions()[0]['name']=='Ben Beispiel'
        init_db()
        assert len(participant_items(eid))==2


def test_ambiguous_names_are_not_linked_to_arbitrary_people(app,post):
    post('/person/save',dict(name='Alex Muster',role='Vater'))
    post('/person/save',dict(name='Alex Muster',role='Lehrkraft'))
    post('/entry/save',entry_data([dict(kind='new',label='Alex Muster')]))
    with app.app_context():
        assert len(rows('SELECT * FROM entry_people'))==0
        assert len(suggestions())==1
    post('/entry/save',dict(entry_data([dict(kind='person',id=2)]),id=1))
    with app.app_context():
        assert one('SELECT person_id FROM entry_people')['person_id']==2
        assert suggestions()==[]
