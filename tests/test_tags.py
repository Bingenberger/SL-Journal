from urllib.parse import urlencode
from flask import template_rendered
from journal.db import get_db
from journal.domain import save_entry


def context(app,client,url):
    contexts=[]
    def collect(sender,template,context,**kwargs): contexts.append(context)
    template_rendered.connect(collect,app)
    try:
        response=client.get(url,base_url='https://localhost')
        assert response.status_code==200
        return response,contexts[-1]
    finally: template_rendered.disconnect(collect,app)


def test_overview_counts_and_links_match_filtered_entries(app,client):
    with app.app_context():
        save_entry(dict(title='Mail',type='mail_in',date='2026-09-23',tags='Öffentlichkeit, 100%_Plan, Plan'))
        save_entry(dict(title='Notiz',date='2026-09-23',tags='öffentlichkeit, ÖFFENTLICHKEIT, Planung'))
        get_db().commit()
    response,data=context(app,client,'/tags')
    counts={tag['name']:tag['count'] for tag in data['tags']}
    assert counts=={'Öffentlichkeit':2,'100%_Plan':1,'Plan':1,'Planung':1}
    assert '<span class="nav-label">Tags</span>' in response.text
    for label,count in counts.items():
        response,filtered=context(app,client,'/entries?'+urlencode({'tag':label}))
        assert filtered['total']==count
        assert 'Alle Tags' in response.text
    _,search=context(app,client,'/tags?'+urlencode({'q':'ÖFFENT'}))
    assert len(search['tags'])==1


def test_empty_search_and_auth(app,client):
    response,data=context(app,client,'/tags')
    assert data['tags']==[] and 'Keine Tags gefunden' in response.text
    assert app.test_client().get('/tags',base_url='https://localhost').status_code==302
