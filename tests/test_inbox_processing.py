import pytest
from flask import template_rendered
from journal.db import get_db,one
from journal.domain import save_entry


def page_context(app,client,url):
    captured=[]
    def record(sender,template,context,**extra): captured.append(context)
    template_rendered.connect(record,app)
    try:
        assert client.get(url,base_url='https://localhost').status_code==200
        return captured[-1]
    finally:
        template_rendered.disconnect(record,app)


@pytest.mark.parametrize('kind',['mail_in','mail_out'])
def test_tags_mark_mail_processed_and_removal_reopens(app,client,post,kind):
    post('/entry/save',dict(title='Testmail',type=kind,date='2026-09-23'))
    with app.app_context(): eid=one('SELECT id FROM entries')['id']
    inbox=page_context(app,client,'/entries?inbox=1')
    assert inbox['total']==inbox['inbox_count']==1
    post('/entry/save',dict(id=eid,title='Testmail',type=kind,date='2026-09-23',tags='Organisation'))
    inbox=page_context(app,client,'/entries?inbox=1')
    assert inbox['total']==inbox['inbox_count']==0 and inbox['items']==[]
    assert page_context(app,client,'/')['inbox_count']==0
    assert page_context(app,client,'/entries?tag=Organisation')['total']==1
    post('/entry/save',dict(id=eid,title='Testmail',type=kind,date='2026-09-23',tags=''))
    assert page_context(app,client,'/entries?inbox=1')['total']==1


def test_project_or_tag_is_sufficient_and_blank_tags_do_not_count(app,client):
    with app.app_context():
        db=get_db()
        pid=db.execute("INSERT INTO projects(name,school_year) VALUES('Vorhaben','2026/27')").lastrowid
        base=dict(date='2026-09-23',type='mail_in')
        save_entry(dict(base,title='Nur Projekt'),[pid])
        save_entry(dict(base,title='Nur Tags',tags='Organisation'))
        save_entry(dict(base,title='Beides',tags='Kollegium'),[pid])
        blank=save_entry(dict(base,title='Leer'))
        db.execute('UPDATE entries SET tags=? WHERE id=?',(' \t\r\n, ',blank))
        save_entry(dict(date='2026-09-23',type='note',title='Notiz'))
        db.commit()
    inbox=page_context(app,client,'/entries?inbox=1')
    assert inbox['total']==inbox['inbox_count']==1
    assert [e['id'] for e in inbox['items']]==[blank]
    assert page_context(app,client,'/')['inbox_count']==1
    assert page_context(app,client,'/entries')['total']==5
