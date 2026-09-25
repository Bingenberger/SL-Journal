"""Create an isolated, fictional video instance; never overwrite existing data."""
import argparse
import io
import json
import os
from pathlib import Path
import secrets
import sys
from datetime import timedelta, datetime, time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'video-demo')
    parser.add_argument('--code',action='store_true',help='Demo-Passwort und aktuellen Einmalcode anzeigen')
    args=parser.parse_args();target=args.directory.resolve()
    import pyotp
    if args.code:
        credentials=json.loads((target/'demo-access.json').read_text())
        print('Demo-Passwort:',credentials['password'])
        print('Aktueller Einmalcode:',pyotp.TOTP(credentials['totp']).now())
        return
    if target.exists():
        raise SystemExit('Ziel existiert bereits. Bitte für einen neuen Bestand ein anderes --directory wählen.')
    os.umask(0o077)
    target.mkdir(parents=True,mode=0o700)
    # Explicitly override inherited production paths before constructing the app.
    os.environ['JOURNAL_INSTANCE']=str(target)
    os.environ['JOURNAL_KEY_FILE']=str(target/'master.key')
    os.environ['JOURNAL_TRUST_PROXY']='0'
    from journal.app import create_app
    from journal.db import get_db,one,atomic_write,cipher
    from journal.domain import now,school_year,save_entry,save_task,save_attachment
    from werkzeug.security import generate_password_hash
    app=create_app();stamp=now();day=stamp.date();year=school_year()
    password='Video-'+secrets.token_urlsafe(12)
    secret=pyotp.random_base32()
    with app.app_context():
        db=get_db()
        db.execute('INSERT INTO account(id,password,totp,session_version) VALUES(1,?,?,?)',(generate_password_hash(password),secret,secrets.token_hex(16)))
        projects=[]
        for title,body in [
            ('Leseband gemeinsam gestalten','## Ziel\nTäglich zwanzig Minuten Lesezeit in allen Klassen.\n\n- Materialien sammeln\n- Tandemlesen erproben\n- Erfahrungen im Kollegium auswerten'),
            ('Herbstfest auf dem Schulhof','Ein gemeinsamer Nachmittag mit Spielstationen, Büchertausch und Waffelstand.'),
            ('Digitale Elternkommunikation','Informationswege bündeln und verständliche Vorlagen entwickeln.'),
            ('Ankommen in Klasse 1','Rückblick auf die ersten Schulwochen und Ideen für das kommende Jahr.')]:
            projects.append(db.execute('INSERT INTO projects(name,description,school_year) VALUES(?,?,?)',(title,body,year)).lastrowid)
        db.execute("UPDATE projects SET status='closed' WHERE id=?",(projects[-1],))
        people=[]
        names=[('Mara Linden','Konrektorin','Grundschule Sonnenbogen'),('Jonas Bergfeld','Lehrer','Grundschule Sonnenbogen'),('Lea Winterhain','OGS-Leitung','Ganztag Sonnenbogen'),('Samira Morgenstern','Schulsozialarbeit','Grundschule Sonnenbogen'),('Felix Sommerfeld','Vorsitz Förderverein','Förderverein Sonnenbogen'),('Nora Eichenbach','Schulpflegschaft','Elternvertretung Sonnenbogen'),('Tim Falkenberg','Hausmeister','Schulträger Musterstadt'),('Clara Birkenau','Sekretariat','Grundschule Sonnenbogen'),('David Wiesenbach','Fachberatung Medien','Medienzentrum Musterstadt'),('Lina Rosenfeld','Büchereileitung','Stadtbücherei Musterstadt'),('Paul Abendroth','Lehrer','Grundschule Sonnenbogen'),('Amira Sternwald','Schulverwaltung','Schulträger Musterstadt')]
        for index,(name,role,institution) in enumerate(names):
            email=f'kontakt{index+1}@sonnenbogen.example'
            people.append(db.execute('INSERT INTO people(name,role,institution,emails,phone) VALUES(?,?,?,?,?)',(name,role,institution,email,f'030 23125{index:02}')).lastrowid)
        cases=[]
        for title,status,delta in [('Rückmeldung zur Abholsituation','clarifying',0),('Zusätzliche Fahrradständer','open',2),('Raumbelegung für die Theater-AG','open',-1),('Vertretung beim Büchereidienst','done',-3)]:
            cases.append(db.execute('INSERT INTO cases(title,description,status,follow_up) VALUES(?,?,?,?)',(title,'Rückmeldungen bündeln, Zuständigkeiten klären und die vereinbarte Lösung dokumentieren.',status,(day+timedelta(days=delta)).isoformat())).lastrowid)
        def entry(kind,title,body,offset=0,clock='09:15',project=None,case=None,tags='',contacts=(),**extra):
            data=dict(type=kind,title=title,body=body,date=(day+timedelta(days=offset)).isoformat(),time=clock,tags=tags,**extra)
            if case:data['case_ids']=json.dumps([case])
            return save_entry(data,[project] if project else [],[people[i] for i in contacts])
        protocol=entry('protocol','Steuergruppe: Leseband',
            'Die ersten Erfahrungen mit dem Tandemlesen sind positiv. Besonders hilfreich sind feste Rollen und eine kurze gemeinsame Reflexion.\n\n**Nächster Schritt:** Ein gemeinsames Materialregal im Teamraum einrichten.',
            -1,project=projects[0],tags='Leseförderung, Kollegium',contacts=(0,1,10),
            agenda='1. Erfahrungen aus den Klassen\n2. Materialauswahl\n3. Zeitplan und Zuständigkeiten',
            decisions='- Jede Jahrgangsstufe wählt zwei Lesetexte aus.\n- Jonas sammelt die Rückmeldungen bis Freitag.\n- Die Erprobung läuft zunächst vier Wochen.')
        entry('journal','Ein guter Schritt für das Leseband','Die Rückmeldungen aus den Klassen zeigen: Kleine, verlässliche Routinen helfen. Heute konnten wir die Materialfrage klären und die nächsten Schritte verteilen.',project=projects[0],tags='Leseförderung',clock='11:10')
        entry('journal','Zeit für den gemeinsamen Blick','Im kurzen Austausch mit der OGS zwei praktische Ideen für ruhigere Übergänge gesammelt. Das nehmen wir in die nächste Teamsitzung mit.',clock='12:20',tags='Ganztag')
        mail=entry('mail_in','Bücherei bringt Lesekisten vorbei',
            'Guten Morgen,\n\nwir haben drei Lesekisten mit kurzen Geschichten und Sachbüchern zusammengestellt. Die Lieferung ist am Dienstag möglich. Für das Tandemlesen liegen außerdem einfache Lesekarten bei.\n\nViele Grüße\nLina Rosenfeld',
            clock='08:35',project=projects[0],tags='Leseförderung',contacts=(9,),sender='Lina Rosenfeld <kontakt10@sonnenbogen.example>')
        entry('mail_in','Helferinnen und Helfer für das Herbstfest','Hallo zusammen,\n\nfür den Waffelstand sind bereits vier Teams gefunden. Können wir den Aufbau ab 13 Uhr einplanen? Den Büchertausch würden wir gern neben dem Haupteingang aufstellen.\n\nHerzliche Grüße\nFelix Sommerfeld',clock='09:05',project=projects[1],contacts=(4,),sender='Felix Sommerfeld <kontakt5@sonnenbogen.example>')
        entry('mail_in','Anfrage: Theater-AG im Mehrzweckraum','Für die nächste Probe brauchen wir etwas mehr Platz. Wäre der Mehrzweckraum am Donnerstag ab 14 Uhr frei? Wir räumen danach alles wieder zurück.',clock='10:15',case=cases[2],sender='Theaterteam <theater@sonnenbogen.example>')
        entry('mail_out','Vielen Dank für die Rückmeldungen zum Schulweg','Liebe Elternvertretung,\n\nvielen Dank für die konkreten Hinweise. Wir besprechen die Abholsituation gemeinsam mit der OGS und melden uns mit einem Vorschlag für die kommende Woche.',clock='11:45',case=cases[0],contacts=(5,),recipients='Nora Eichenbach <kontakt6@sonnenbogen.example>',sender='Schulleitung <leitung@sonnenbogen.example>')
        entry('meeting','Abholsituation gemeinsam sortiert','Mit OGS und Schulsozialarbeit die Beobachtungen gesammelt. Ein klarer Treffpunkt und ein sichtbares Schild sollen den Übergang erleichtern.',case=cases[0],contacts=(2,3),tags='Ganztag, Organisation',clock='10:40')
        entry('phone','Abstimmung zur Fahrradfläche','Der Schulträger prüft zwei mögliche Standorte. Eine Skizze mit den Laufwegen wird nachgereicht.',case=cases[1],contacts=(11,),clock='13:00')
        entry('note',f'Wochenpost KW {day.isocalendar().week}','## Für die nächste Wochenpost\n\n- Neue Lesekisten sind unterwegs.\n- Helferplan für das Herbstfest ergänzen.\n- Danke für die Unterstützung bei der Einschulung!',tags='Wochenpost, Kollegium')
        for i in range(14):
            project=projects[i%3]
            entry(['journal','mail_in','note','meeting'][i%4],
                ['Erfahrungen aus der Erprobung','Rückmeldung aus dem Jahrgang','Ideen für die nächste Runde','Kurze Abstimmung im Team'][i%4],
                ['Die Materialauswahl funktioniert gut. Für die nächste Runde wünschen sich die Teams noch mehr kurze Sachtexte.','Wir haben die Zuständigkeiten geklärt und die nächsten Termine abgestimmt. Die Ergebnisse sind im gemeinsamen Protokoll festgehalten.','Eine kleine Sammlung praktischer Ideen: feste Ansprechpersonen, kurze Checklisten und ein gemeinsamer Rückblick.'][i%3],
                offset=-(i//2+1),project=project,tags=['Leseförderung','Organisation','Digitalisierung'][i%3],contacts=(i%len(people),))
        for i,title in enumerate(['Fortbildung: kreative Leseförderung','Neue Angebote der Stadtbücherei','Idee für eine Bewegungsstation']):
            entry('mail_in',title,'Guten Tag,\n\nanbei unsere Idee für die Zusammenarbeit. Wir freuen uns über eine kurze Rückmeldung und können Einzelheiten gern telefonisch abstimmen.',clock=f'0{7+i}:25',sender=f'Beispielteam <angebot{i}@partner.example>')
        def task(title,delta=0,project=None,case=None,source=None,parent=None,done=False):
            data=dict(text=title,due=(day+timedelta(days=delta)).isoformat() if delta is not None else '',project_id=project,entry_id=source,parent_id=parent)
            if case:data['case_id']=case
            tid=save_task(data)
            if done:db.execute('UPDATE tasks SET done=1,completed_at=? WHERE id=?',(datetime.combine(day,time(10,15),stamp.tzinfo).isoformat(),tid))
            return tid
        parent=task('Materialregal für das Leseband vorbereiten',0,projects[0],source=protocol)
        task('Beschriftungen für die Lesekisten drucken',0,parent=parent,done=True)
        task('Ablagefächer mit dem Jahrgangsteam abstimmen',1,parent=parent)
        for title,delta,pid,cid in [('Helferplan an den Förderverein senden',0,projects[1],None),('Treffpunkt für die Abholung abstimmen',0,None,cases[0]),('Rückmeldung zur Raumbelegung geben',-1,None,cases[2]),('Skizze der Fahrradfläche weitergeben',3,None,cases[1]),('Vorlage für Elterninformationen überarbeiten',5,projects[2],None),('Büchertausch beim Herbstfest einplanen',7,projects[1],None),('Ideen für den pädagogischen Tag sammeln',None,projects[0],None)]:
            task(title,delta,pid,cid)
        for title in ['Lesekisten bei der Bücherei bestellt','Rückmeldung zur OGS-Besprechung verschickt','Unterlagen für die Steuergruppe sortiert']:
            task(title,done=True)
        db.execute('INSERT INTO task_series(template,frequency,start_date,next_due) VALUES(?,?,?,?)',('Wochenpost KW{KW} vorbereiten','weekly',day.isoformat(),day.isoformat()))
        from journal.recurrence import generate
        generate()
        from PIL import Image,ImageDraw,ImageFont
        pdf=Image.new('RGB',(1240,1754),'white');draw=ImageDraw.Draw(pdf)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',28)
        for i,line in enumerate(['Grundschule Sonnenbogen','Leseband: Gemeinsam lesen lernen','','1. Jeden Tag zwanzig Minuten Lesezeit','2. Tandemlesen mit festen Rollen','3. Lesekisten aus der Stadtbuecherei','4. Rueckblick nach vier Wochen','','Fiktive Unterlage fuer die Videodemonstration']):draw.text((85,100+i*65),line,font=font,fill='#244b42')
        buffer=io.BytesIO();pdf.save(buffer,format='PDF');save_attachment(protocol,'Leseband-Konzept.pdf',buffer.getvalue(),'application/pdf')
        from journal.documents import save,associate
        doc=save(dict(name='Helferplan Herbstfest',url='https://cloud.sonnenbogen.example/f/123',description='Fiktiver Nextcloud-Verweis für die Videodemonstration.'))
        associate(doc,'project',projects[1])
        for offset,title,clock,minutes in [(0,'Abstimmung mit der Konrektorin','09:00',30),(0,'OGS: Übergänge gestalten','14:00',45),(1,'Planung Herbstfest','10:00',60),(3,'Jahrgangsteams: Leseband','13:30',45)]:
            date_=day+timedelta(days=offset);begin=datetime.combine(date_,time.fromisoformat(clock),stamp.tzinfo);end=begin+timedelta(minutes=minutes);uid=f'video-{offset}-{clock}'
            aid=db.execute('INSERT INTO calendar_events(event_key,calendar_key,uid,title,calendar,location,start_at,end_at,date,time) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,'demo',uid,title,'Schulleitung · Demo','Besprechungsraum',begin.isoformat(),end.isoformat(),date_.isoformat(),clock)).lastrowid
            point=task('Lesekisten und nächste Schritte besprechen' if offset==0 else 'Materialien und Zuständigkeiten abstimmen',offset,source=mail)
            db.execute('INSERT INTO meeting_points(task_id,event_id,source_entry_id,resource_label,request_key) VALUES(?,?,?,?,?)',(point,aid,mail,'Bücherei bringt Lesekisten vorbei',secrets.token_hex(16)))
        from journal.db import rows
        for offset in range(8):
            date_=day+timedelta(days=offset)
            events=[dict(event,end=datetime.fromisoformat(event['end_at']).strftime('%H:%M')) for event in rows('SELECT * FROM calendar_events WHERE date=?',(date_.isoformat(),))]
            atomic_write(target/'cache'/f'{date_.isoformat()}.enc',cipher().encrypt(json.dumps(dict(updated=stamp.isoformat(),events=events)).encode()))
        db.execute('INSERT INTO processes(name,month,period,todos) VALUES(?,?,?,?)',('Herbstfest vorbereiten',day.month,'late',json.dumps(['Helferplan abstimmen','Stationen planen','Eltern informieren'])))
        db.commit()
        counts={table:one(f'SELECT count(*) n FROM {table}')['n'] for table in ['entries','tasks','projects','cases','people','calendar_events']}
        assert not rows('PRAGMA foreign_key_check')
    atomic_write(target/'demo-access.json',json.dumps(dict(password=password,totp=secret),indent=2).encode())
    command=f'JOURNAL_INSTANCE="{target}" JOURNAL_KEY_FILE="{target}/master.key" JOURNAL_TRUST_PROXY=0 .venv/bin/python manage.py run --port 8444'
    guide=f'''# Videodemo – ausschließlich fiktive Daten

Erstellt für den {day.strftime('%d.%m.%Y')}. Beispielschule: Grundschule Sonnenbogen.

## Start

Im Projektordner:

```bash
{command}
```

Öffnen: https://127.0.0.1:8444 (lokales, selbstsigniertes Zertifikat).
Die separate Adresse hält die Demo-Anmeldung von localhost getrennt.

## Anmeldung

Passwort: `{password}`

Den aktuellen Authenticator-Code im Terminal ausgeben:

```bash
.venv/bin/python scripts/create_video_demo.py --directory "{target}" --code
```

Alternativ den Schlüssel aus `demo-access.json` in eine Authenticator-App eintragen.
Ein Code kann nur einmal zur Anmeldung verwendet werden; anschließend den nächsten abwarten.

## Rundgang

1. Tagescockpit: Termine, offene Aufgaben und „Heute geschafft“.
2. E-Mail mit Vorschautext öffnen, Aufgabe daraus anlegen und einem Vorgang zuordnen.
3. Projekt „Leseband gemeinsam gestalten“: Chronik und Protokoll mit Tagesordnung, Beschlüssen und PDF.
4. Termin „Abstimmung mit der Konrektorin“: vorgemerkte Besprechungspunkte.
5. Kontakte nach Institution, Tags, Aufgabenserie und Unteraufgaben zeigen.
6. Neue Notiz, Handschrift oder Sprachi während der Aufnahme selbst anlegen.

Die Kalendertermine sind lokal vorbereitet. IMAP und CalDAV sind nicht eingerichtet; der Nextcloud-Link ist absichtlich fiktiv. Namen, E-Mail-Adressen und Inhalte wurden frei erfunden. Keine produktiven Daten wurden übernommen.

Bestand: {json.dumps(counts,ensure_ascii=False)}.
Für eine Aufnahme an einem anderen Tag die Tagesauswahl auf {day.isoformat()} stellen oder mit `--directory` eine neue Demo erzeugen.
Zum Übertragen den gesamten Ordner einschließlich `master.key`, Anhängen und Cache verwenden; die verschlüsselte Datenbank allein reicht nicht aus.
'''
    atomic_write(target/'ANLEITUNG.md',guide.encode())
    print('Videodemo erstellt:',target)
    print(json.dumps(counts,ensure_ascii=False))
    print('Start:',command)
    print('Zugang und Rundgang:',target/'ANLEITUNG.md')


if __name__=='__main__':main()
