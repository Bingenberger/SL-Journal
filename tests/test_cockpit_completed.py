from journal.db import get_db, one


def test_completed_tasks_follow_completion_day_not_due_date(app,client):
    with app.app_context():
        db=get_db()
        for title,done,completed,due in [
            ('Früh geschafft',1,'2026-09-24T00:01:00+02:00',None),
            ('Spät geschafft',1,'2026-09-24T23:59:00+02:00','2026-10-10'),
            ('Gestern geschafft',1,'2026-09-23T23:59:00+02:00','2026-09-24'),
            ('Morgen geschafft',1,'2026-09-25T00:00:00+02:00',None),
            ('Wieder offen',0,None,'2026-09-24'),
            ('Ohne Abschlussdatum',1,None,None),
        ]:
            db.execute('INSERT INTO tasks(text,done,completed_at,due) VALUES(?,?,?,?)',(title,done,completed,due))
        db.commit()
    html=client.get('/?date=2026-09-24',base_url='https://localhost').text
    section=html.split('class="task-group completed-today"',1)[1].split('<a class="panel-link"',1)[0]
    assert 'An diesem Tag geschafft' in section
    assert '<span class="number">2</span>' in section
    assert section.index('Spät geschafft')<section.index('Früh geschafft')
    for text in ['Gestern geschafft','Morgen geschafft','Wieder offen','Ohne Abschlussdatum']:
        assert text not in section


def test_complete_and_reopen_updates_today_section(app,client,post):
    post('/task/save',{'text':'Heute abschließen'})
    with app.app_context():tid=one('SELECT id FROM tasks')['id']
    post(f'/task/{tid}/toggle')
    html=client.get('/',base_url='https://localhost').text
    section=html.split('class="task-group completed-today"',1)[1]
    assert 'Heute geschafft' in section and f'id="task-{tid}"' in section
    post(f'/task/{tid}/toggle')
    html=client.get('/',base_url='https://localhost').text
    section=html.split('class="task-group completed-today"',1)[1]
    assert f'id="task-{tid}"' not in section
    assert 'Noch keine erledigten Aufgaben' in section
