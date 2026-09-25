"""Optional fictional sample content; never loaded automatically."""
from datetime import timedelta
from .db import get_db, one
from .domain import now,save_entry,save_task,school_year


def seed():
    if one('SELECT id FROM entries LIMIT 1') or one('SELECT id FROM projects LIMIT 1'):
        raise ValueError('Beispieldaten nur in einer leeren Datenbank anlegen.')
    db=get_db();day=now().date();year=school_year()
    project_ids=[]
    for name,description in [('Schulfest','Gemeinsam einen schönen Tag für die Schulgemeinschaft gestalten.'),('Schulentwicklung','Unterricht weiterdenken und gemeinsame Ziele verfolgen.'),('Martinszug','Vorbereitungen und Absprachen für unseren Martinszug.')]:
        project_ids.append(db.execute('INSERT INTO projects(name,description,school_year) VALUES(?,?,?)',(name,description,year)).lastrowid)
    save_entry(dict(date=day.isoformat(),time='09:15',type='phone',title='Abstimmung zur Organisation des Schulfests',participants='Beispielkontakt · Förderverein',body='Aufbau und Helferplan besprochen. Der Förderverein übernimmt die Koordination der Getränkestände.\n\n**Nächster Schritt:** Raumplan gemeinsam abstimmen.',tags='Organisation'),[project_ids[0]])
    save_entry(dict(date=day.isoformat(),time='10:30',type='journal',title='Ein guter Start in die Woche',body='Heute die Rückmeldungen aus dem Kollegium gesichtet und die nächste Steuergruppensitzung vorbereitet.\n\n- Schwerpunkte für das Schuljahr sortiert\n- Ideen zur Leseförderung gesammelt',tags='Kollegium'),[project_ids[1]])
    save_entry(dict(date=day.isoformat(),time='08:42',type='mail_in',title='Rückmeldung zum Helferplan',sender='Beispielkontakt <beispiel@example.org>',body='Die ersten Rückmeldungen sind da. Wir können die Standplanung in der nächsten Besprechung konkretisieren.',tags='Organisation'))
    for text,delta,pid in [('Rückmeldung zum Raumplan geben',-2,project_ids[0]),('Agenda für die Steuergruppe vorbereiten',0,project_ids[1]),('Helferplan mit dem Förderverein abstimmen',0,project_ids[0]),('Materialbedarf für Laternen sammeln',3,project_ids[2]),('Ideen zur Leseförderung bündeln',7,project_ids[1]),('Rückblick auf das letzte Schulfest lesen',None,project_ids[0])]:
        save_task(dict(text=text,due=(day+timedelta(days=delta)).isoformat() if delta is not None else None,project_id=pid))
    db.commit()
