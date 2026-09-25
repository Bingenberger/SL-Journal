import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import time
from datetime import date, timedelta
from pathlib import Path

import bleach
import markdown
import pyotp
import qrcode
from cryptography.fernet import Fernet
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from .db import atomic_write, cipher, close_db, get_db, init_db, one, rows, set_setting, setting
from .domain import clean_tags, UNPROCESSED_MAIL, MONTHS, PERIODS, TYPES, entries, entry_details, now, process_due, save_attachment, save_entry, save_task, school_year, trigger_process, valid_date


def render_icon(name, extra=''):
    """SVG-Symbol aus dem Sprite in journal/templates/icons.html."""
    if not name.isalpha():
        raise ValueError('Unbekanntes Symbol.')
    classes = 'icon ' + extra if extra else 'icon'
    return Markup(f'<svg class="{classes}" aria-hidden="true" focusable="false"><use href="#i-{name}"></use></svg>')


def create_app(test_config=None):
    instance = Path(os.environ.get('JOURNAL_INSTANCE', Path(__file__).resolve().parent.parent/'instance')).resolve()
    if test_config and test_config.get('INSTANCE_PATH'):
        instance = Path(test_config['INSTANCE_PATH'])
    instance.mkdir(parents=True, exist_ok=True, mode=0o700)
    for folder in ('attachments','cache','backups'):
        (instance/folder).mkdir(exist_ok=True, mode=0o700)
    key_path = Path(os.environ.get('JOURNAL_KEY_FILE', str(instance/'master.key')))
    if not key_path.exists():
        if (instance/'journal.db').exists():
            raise RuntimeError('Der Schlüssel zur vorhandenen Datenbank fehlt. Originalschlüssel wiederherstellen.')
        key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(key_path, 'xb') as f:
            os.chmod(key_path,0o600)
            f.write(Fernet.generate_key())
    key = key_path.read_bytes().strip()
    Fernet(key)
    app = Flask(__name__, instance_path=str(instance))
    app.config.update(DATA_KEY=key, SECRET_KEY=hmac.new(key,b'session',hashlib.sha256).digest(),
        MAX_CONTENT_LENGTH=30*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=True, PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        REQUIRE_HTTPS=True)
    if test_config:
        app.config.update(test_config)
    if os.environ.get('JOURNAL_TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from .handwriting import bp as handwriting_bp
    app.register_blueprint(handwriting_bp)

    @app.template_filter('md')
    def render_markdown(text):
        html = markdown.markdown(text or '', extensions=['fenced_code','tables','nl2br'])
        return Markup(bleach.clean(html, tags={'p','br','strong','em','ul','ol','li','blockquote','code','pre','h1','h2','h3','h4','hr','a','table','thead','tbody','tr','th','td','del'}, attributes={'a':['href','title']}, protocols=['https','http','mailto'], strip=True))

    @app.template_filter('mail_names')
    def mail_names(value, limit=2):
        """Aus Mailkopfzeilen lesbare Namen machen: Anzeigename, sonst Adresse.
        Freitext wie „Frau Klein; Herr Bauer“ bleibt unangetastet — die
        Adressgrammatik zerlegt solche Angaben sonst falsch."""
        from email.utils import getaddresses
        text=' '.join(str(value or '').split())
        if not text:
            return ''
        parsed=getaddresses([text.replace(';',',')])
        if not parsed or not all('@' in address for _,address in parsed):
            return text
        names=[]
        for name,address in parsed:
            label=' '.join((name or address).split())
            if label and label not in names:
                names.append(label)
        if len(names)<=limit:
            return ', '.join(names)
        return ', '.join(names[:limit])+f' und {len(names)-limit} weitere'

    @app.template_filter('de_date')
    def de_date(value):
        return date.fromisoformat(str(value)[:10]).strftime('%d.%m.%Y') if value else 'Ohne Datum'

    @app.context_processor
    def context():
        logged_in = bool(session.get('auth'))
        from .participants import institutions
        from .project_suggestions import items as project_items
        from .documents import listed as listed_documents
        from .domain import task_family
        from .cases import STATUSES
        from .case_suggestions import items as case_items
        from .ui import query_url
        from .recurrence import for_task as task_series, FREQUENCIES
        from .meetings import for_task as task_meeting, legacy_protocol_key
        from .nextcloud import referenz as nextcloud_reference, konto as nextcloud_account
        return dict(document_preview=lambda url: bool(nextcloud_reference(url)),nextcloud_ready=bool(nextcloud_account()) if logged_in else False,legacy_protocol_key=legacy_protocol_key,task_meeting=task_meeting,task_series=task_series, recurrence_frequencies=FREQUENCIES, query_url=query_url, task_case_items=lambda tid: case_items('task',tid), case_statuses=STATUSES, all_cases=rows('SELECT * FROM cases ORDER BY status,title,id') if logged_in else [], case_by_id=lambda cid: one('SELECT id,title FROM cases WHERE id=?',(cid,)) if cid else None, icon=render_icon,listed_documents=listed_documents,task_family=task_family,task_project_items=lambda tid: project_items('task',tid), csrf_token=session.setdefault('csrf', secrets.token_urlsafe(32)), types=TYPES, months=MONTHS, periods=PERIODS,
            today=now().date().isoformat(), current_year=school_year(),
            nav_projects=rows("SELECT * FROM projects WHERE status='active' ORDER BY name") if logged_in else [],
            all_projects=rows('SELECT * FROM projects ORDER BY status,name') if logged_in else [],
            all_people=[], all_institutions=institutions() if logged_in else [],
            inbox_count=one('SELECT count(*) n FROM entries e WHERE '+UNPROCESSED_MAIL)['n'] if logged_in else 0)

    @app.before_request
    def protect():
        g.style_nonce = secrets.token_urlsafe(24)
        if app.config['REQUIRE_HTTPS'] and not request.is_secure:
            return 'HTTPS ist erforderlich. Bitte die HTTPS-Adresse verwenden.', 400
        if request.method == 'POST':
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token','')
            if not token or not hmac.compare_digest(token,session.get('csrf','')):
                abort(400, 'Die Sitzung ist abgelaufen. Bitte die Seite neu laden.')
        if request.endpoint in ('static','login','setup','setup_qr'):
            return
        account = one('SELECT session_version FROM account WHERE id=1')
        if not account:
            return redirect(url_for('setup'))
        if not session.get('auth') or session.get('version') != account['session_version']:
            session.pop('auth',None)
            return redirect(url_for('login'))

        if request.method=='GET' and request.endpoint in ('cockpit','task_list','entry_view','project_view','case_view','task_series_list','task_series_view'):
            from .recurrence import generate
            generate()

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = f"default-src 'self'; script-src 'self'; style-src 'self' 'nonce-{g.style_nonce}'; img-src 'self' data:; media-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.endpoint in ('handwriting.new', 'handwriting.edit'):
            # Excalidraw positions its controls with React style attributes.
            # Keep script and stylesheet restrictions; allow only these attributes here.
            response.headers['Content-Security-Policy'] += "; style-src-attr 'unsafe-inline'; font-src 'self' data:"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Innerhalb des Journals erlaubt, damit der Weg zurück zur vorherigen Ansicht
        # funktioniert; an fremde Server geht weiterhin keine Adresse.
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        get_db().rollback()
        if request.headers.get('X-Requested-With') == 'fetch':
            return jsonify(error=str(error)),400
        return render_template('error.html', message=str(error)),400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return render_template('error.html',message=error.description),error.code

    def rate_limit():
        limit = one('SELECT * FROM login_limit WHERE id=1')
        if limit['until'] > time.time():
            abort(429,'Zu viele Anmeldeversuche. Bitte in 15 Minuten erneut versuchen.')

    def login_failed():
        db = get_db()
        db.execute('UPDATE login_limit SET failures=failures+1 WHERE id=1')
        if one('SELECT failures FROM login_limit WHERE id=1')['failures'] >= 5:
            db.execute('UPDATE login_limit SET until=?, failures=0 WHERE id=1',(time.time()+900,))
        db.commit()

    @app.route('/setup', methods=['GET','POST'])
    def setup():
        if one('SELECT id FROM account'):
            return redirect(url_for('login'))
        if request.method == 'POST':
            rate_limit()
            token_hash = setting('setup_token')
            if not token_hash or not check_password_hash(token_hash,request.form.get('setup_code','')):
                login_failed()
                flash('Der Einrichtungscode ist ungültig.','error')
            else:
                password = request.form.get('password','')
                if len(password) < 14:
                    raise ValueError('Bitte mindestens 14 Zeichen für das Passwort verwenden.')
                if password != request.form.get('password_repeat'):
                    raise ValueError('Die Passwörter stimmen nicht überein.')
                secret = setting('setup_totp')
                if not secret or not pyotp.TOTP(secret).verify(request.form.get('otp',''),valid_window=1):
                    login_failed()
                    flash('Bitte den aktuellen sechsstelligen Code aus der Authenticator-App eingeben.','error')
                else:
                    version = secrets.token_hex(16)
                    db = get_db()
                    matched=max(c for c in range(int(time.time())//30-1,int(time.time())//30+2) if hmac.compare_digest(pyotp.TOTP(secret).at(c*30),request.form.get('otp','')))
                    db.execute('INSERT INTO account(id,password,totp,session_version,last_totp) VALUES(1,?,?,?,?)',(generate_password_hash(password),secret,version,matched))
                    db.execute("DELETE FROM settings WHERE key IN ('setup_token','setup_totp')")
                    db.execute('UPDATE login_limit SET failures=0,until=0 WHERE id=1')
                    db.commit()
                    session.clear()
                    session.update(auth=True,version=version)
                    session.permanent=True
                    return redirect(url_for('cockpit'))
        return render_template('setup.html')

    @app.route('/setup/qr', methods=['POST'])
    def setup_qr():
        if one('SELECT id FROM account'):
            abort(404)
        rate_limit()
        if not setting('setup_token') or not check_password_hash(setting('setup_token'),request.form.get('setup_code','')):
            login_failed()
            abort(403,'Ungültiger Einrichtungscode.')
        secret = setting('setup_totp')
        uri = pyotp.TOTP(secret).provisioning_uri('Schulleitung',issuer_name='Schulleitungsjournal')
        buf = io.BytesIO()
        qrcode.make(uri).save(buf,format='PNG')
        return jsonify(image='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),secret=secret)

    @app.route('/login', methods=['GET','POST'])
    def login():
        account = one('SELECT * FROM account WHERE id=1')
        if not account:
            return redirect(url_for('setup'))
        if request.method == 'POST':
            rate_limit()
            code = request.form.get('otp','')
            if not code.isascii() or len(code)!=6 or not code.isdigit():
                login_failed()
                flash('Bitte einen sechsstelligen Einmalcode eingeben.','error')
                return render_template('login.html')
            totp = pyotp.TOTP(account['totp'])
            counter = int(time.time())//30
            matched = next((c for c in range(counter-1,counter+2) if hmac.compare_digest(totp.at(c*30),code)),None)
            if check_password_hash(account['password'],request.form.get('password','')) and matched is not None:
                cursor = get_db().execute('UPDATE account SET last_totp=? WHERE id=1 AND last_totp<?',(matched,matched))
                if cursor.rowcount:
                    get_db().execute('UPDATE login_limit SET failures=0,until=0 WHERE id=1')
                    get_db().commit()
                    session.clear()
                    session.update(auth=True,version=account['session_version'])
                    session.permanent=True
                    return redirect(url_for('cockpit'))
                get_db().rollback()
            login_failed()
            flash('Passwort oder Einmalcode ungültig. Bereits verwendete Codes können nicht erneut genutzt werden.','error')
        return render_template('login.html')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    def result(message, target=None):
        get_db().commit()
        if request.headers.get('X-Requested-With') == 'fetch':
            return jsonify(ok=True, message=message, redirect=target)
        flash(message,'success')
        return redirect(target or url_for('cockpit'))

    @app.get('/')
    def cockpit():
        day = date.fromisoformat(valid_date(request.args.get('date',now().date().isoformat())))
        day_entries = entries('SELECT * FROM entries WHERE date=? ORDER BY time DESC,id DESC',(day.isoformat(),))
        tasks = rows('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE done=0 ORDER BY due,id')
        completed_tasks = rows("SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE t.done=1 AND substr(t.completed_at,1,10)=? ORDER BY t.completed_at DESC,t.id DESC",(day.isoformat(),))
        groups = [('Überfällig',[t for t in tasks if t['due'] and t['due'] < day.isoformat()]),('Heute fällig',[t for t in tasks if t['due'] == day.isoformat()]),('In den nächsten 14 Tagen',[t for t in tasks if t['due'] and day.isoformat() < t['due'] <= (day+timedelta(days=14)).isoformat()])]
        from .integrations import cached_events
        events, calendar_status = cached_events(day)
        from .meetings import cached_meeting, linked_protocol
        for event in events:
            linked=cached_meeting(event)
            event['meeting']=linked
            from .meetings import protocol_candidates
            event['protocol_matches']=protocol_candidates(linked or event)
            event['existing_protocol_id']=linked_protocol(linked or event)

        return render_template('cockpit.html',case_reminders=rows("SELECT * FROM cases WHERE status<>'done' AND follow_up<=? ORDER BY follow_up,title",(day.isoformat(),)),day=day,previous=(day-timedelta(days=1)).isoformat(),following=(day+timedelta(days=1)).isoformat(),day_entries=day_entries,groups=groups,completed_tasks=completed_tasks,undated=sum(t['due'] is None for t in tasks),events=events,calendar_status=calendar_status,reminders=[p for p in rows('SELECT * FROM processes ORDER BY month') if process_due(p,now().date())])

    @app.get('/tags')
    def tag_list():
        from .tags import overview
        return render_template('tags.html',tags=overview(request.args.get('q','')))

    @app.get('/entries')
    def entry_list():
        params=[]
        clauses=[]
        if request.args.get('inbox'):
            clauses.append(UNPROCESSED_MAIL)
        if request.args.get('type') in TYPES:
            clauses.append('e.type=?'); params.append(request.args['type'])
        if request.args.get('q','').strip():
            terms = request.args['q'].split()
            query = ' AND '.join('"'+t.replace('"','""')+'"*' for t in terms)
            clauses.append('e.id IN (SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?)'); params.append(query)
        if request.args.get('tag'):
            clauses.append('has_tag(e.tags,?)')
            params.append(request.args['tag'])
        page = max(1,request.args.get('page',1,type=int))
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        total=one('SELECT count(*) n FROM entries e'+where,params)['n']
        data=entries('SELECT e.* FROM entries e'+where+' ORDER BY date DESC,time DESC,id DESC LIMIT 40 OFFSET ?',(*params,(page-1)*40))
        suggestions={}
        if request.args.get('inbox'):
            from .integrations import suggest_projects
            suggestions={e['id']:suggest_projects(e['title'],e['sender']) for e in data}
        return render_template('entries.html',items=data,total=total,page=page,suggestions=suggestions)

    @app.get('/entry/<int:eid>')
    def entry_view(eid):
        entry=one('SELECT * FROM entries WHERE id=?',(eid,))
        if not entry: abort(404)
        entry = entry_details(entry)
        from .entry_links import listed, incoming
        entry['resource_links'] = listed(eid)
        entry['related_entries'] = incoming(eid)
        return render_template('entry.html',entry=entry,meeting=one('SELECT * FROM calendar_events WHERE protocol_entry_id=?',(eid,)),tasks=rows('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE entry_id=? OR t.id IN (SELECT mp.task_id FROM meeting_points mp JOIN calendar_events ce ON ce.id=mp.event_id WHERE ce.protocol_entry_id=?) ORDER BY done,due',(eid,eid)))

    @app.get('/api/entry/<int:eid>')
    def entry_json(eid):
        entry=one('SELECT * FROM entries WHERE id=?',(eid,))
        if not entry: abort(404)
        return jsonify(entry_details(entry))

    @app.post('/voice/save')
    def voice_save():
        upload=request.files.get('audio')
        formats={'audio/webm':'webm','audio/ogg':'ogg','audio/mp4':'m4a'}
        if not upload or upload.mimetype not in formats:
            raise ValueError('Bitte eine Audioaufnahme aufnehmen.')
        content=upload.read(25*1024*1024+1)
        if not content or len(content)>25*1024*1024:
            raise ValueError('Die Aufnahme muss zwischen 1 Byte und 25 MB groß sein.')
        stamp=now()
        eid=save_entry(dict(type='journal',date=stamp.date().isoformat(),time=stamp.strftime('%H:%M'),title='Sprachi · '+stamp.strftime('%d.%m.%Y · %H:%M'),body=''))
        save_attachment(eid,'Sprachi-'+stamp.strftime('%Y-%m-%d-%H%M%S')+'.'+formats[upload.mimetype],content,upload.mimetype)
        return result('Sprachi im Tagesjournal gespeichert.',url_for('cockpit',date=stamp.date().isoformat()))

    @app.get('/attachment/<int:aid>/audio')
    def attachment_audio(aid):
        item=one('SELECT * FROM attachments WHERE id=?',(aid,))
        if not item or item['mime'] not in ('audio/webm','audio/ogg','audio/mp4'):
            abort(404)
        path=Path(app.instance_path)/'attachments'/item['path']
        if not path.exists(): abort(404)
        return send_file(io.BytesIO(cipher().decrypt(path.read_bytes())),mimetype=item['mime'],conditional=True)

    @app.post('/entry/save')
    def entry_save():
        eid=request.form.get('id',type=int)
        if eid and not one('SELECT id FROM entries WHERE id=?',(eid,)): abort(404)
        data=request.form.to_dict()
        data['needs_review']=False
        eid=save_entry(data,request.form.getlist('projects'),request.form.getlist('people'),eid)
        for upload in request.files.getlist('attachments'):
            if upload.filename:
                save_attachment(eid,upload.filename,upload.read(),upload.mimetype)
        verknuepfe_dokumente(eid,request.form.getlist('document_url'),request.form.getlist('document_name'))
        from .domain import save_task_rows
        texts=request.form.getlist('new_task')
        dates=request.form.getlist('task_due') or ['']*len(texts)
        save_task_rows(texts,dates,entry_id=eid)
        return result('Eintrag gespeichert.')

    def verknuepfe_dokumente(eid, adressen, namen):
        """Im Eintragsdialog gewählte Nextcloud-Dateien mit dem Eintrag verbinden."""
        from .documents import save as dokument_speichern, associate as dokument_zuordnen
        adressen=[a.strip() for a in adressen if a.strip()]
        if len(adressen)>25:
            raise ValueError('Bitte höchstens 25 Dokumente auf einmal verknüpfen.')
        namen=namen+['']*len(adressen)
        for adresse,name in zip(adressen,namen):
            name=name.strip() or adresse.rstrip('/').split('/')[-1] or 'Nextcloud-Dokument'
            dokument_zuordnen(dokument_speichern(dict(name=name,url=adresse)),'entry',eid)

    @app.post('/entry/<int:eid>/delete')
    def entry_delete(eid):
        if not one('SELECT id FROM entries WHERE id=?',(eid,)): abort(404)
        paths=rows('SELECT path FROM attachments WHERE entry_id=?',(eid,))
        get_db().execute('DELETE FROM entries WHERE id=?',(eid,))
        from .participants import prune_suggestions
        prune_suggestions()
        from .project_suggestions import prune
        prune()
        get_db().commit()
        for p in paths: (Path(app.instance_path)/'attachments'/p['path']).unlink(missing_ok=True)
        return result('Eintrag und Anhänge gelöscht.',url_for('entry_list'))

    @app.post('/entry/<int:eid>/link')
    def entry_link(eid):
        if not one('SELECT id FROM entries WHERE id=?', (eid,)):
            abort(404)
        from .entry_links import add
        add(eid, request.form.get('resource_url', ''))
        return result('Ressource mit dem Eintrag verknüpft.',
                      url_for('entry_view', eid=eid, _anchor='entry-resources'))

    @app.post('/entry/<int:eid>/link/<int:lid>/remove')
    def entry_unlink(eid, lid):
        if not one('SELECT id FROM entry_resource_links WHERE id=? AND owner_entry_id=?', (lid, eid)):
            abort(404)
        get_db().execute('DELETE FROM entry_resource_links WHERE id=? AND owner_entry_id=?', (lid, eid))
        return result('Verknüpfung entfernt.',
                      url_for('entry_view', eid=eid, _anchor='entry-resources'))

    @app.post('/entry/<int:eid>/classification')
    def entry_classification(eid):
        if not one('SELECT id FROM entries WHERE id=?', (eid,)):
            abort(404)
        from .domain import clean_tags
        from .project_suggestions import parse, sync, prune
        selected = parse(request.form, request.form.getlist('projects'))
        sync('entry', eid, selected)
        from .cases import sync_entry
        sync_entry(eid, request.form)
        get_db().execute('UPDATE entries SET tags=? WHERE id=?',
                         (clean_tags(request.form.get('tags', '')), eid))
        prune()
        return result('Zuordnungen gespeichert.', url_for('entry_view', eid=eid))

    @app.post('/entry/<int:eid>/assign')
    def entry_assign(eid):
        if not one('SELECT id FROM entries WHERE id=?',(eid,)): abort(404)
        from .project_suggestions import parse, sync
        selected=parse(request.form,[request.form.get('project_id')],single=True)
        from .case_suggestions import parse as parse_cases, sync as sync_cases
        selected_cases=parse_cases(request.form,[request.form.get('case_id')],single=True)
        tags=clean_tags(request.form.get('tags',''))
        if not selected and not selected_cases and not tags: raise ValueError('Bitte ein Projekt, einen Vorgang oder Tags auswählen.')
        if tags:
            previous=one('SELECT tags FROM entries WHERE id=?',(eid,))['tags']
            get_db().execute('UPDATE entries SET tags=? WHERE id=?',(clean_tags(previous+', '+tags),eid))
        sync('entry',eid,selected,append=True)
        sync_cases('entry',eid,selected_cases,append=True)
        return result('Vorschlag vorgemerkt. Bitte im jeweiligen Bereich übernehmen.' if not tags and not any(kind=='project' for kind,_ in selected) and not any(kind=='case' for kind,_ in selected_cases) else 'Mail zugeordnet und bearbeitet.')

    @app.get('/attachment/<int:aid>/preview')
    def attachment_preview(aid):
        from .pdf_preview import render_pdf
        item=one('SELECT * FROM attachments WHERE id=?',(aid,))
        if not item: abort(404)
        if item['mime']!='application/pdf' and not item['name'].lower().endswith('.pdf'):
            abort(415,'Für diesen Anhang ist keine PDF-Vorschau verfügbar.')
        path=Path(app.instance_path)/'attachments'/item['path']
        if not path.exists(): abort(404,'Die Anhangsdatei fehlt.')
        try:
            content=render_pdf(cipher().decrypt(path.read_bytes()))
        except RuntimeError as error:
            return jsonify(error=str(error)),503
        return send_file(io.BytesIO(content),mimetype='image/png')

    @app.get('/attachment/<int:aid>')
    def attachment(aid):
        item=one('SELECT * FROM attachments WHERE id=?',(aid,))
        if not item: abort(404)
        path=Path(app.instance_path)/'attachments'/item['path']
        if not path.exists(): abort(404,'Die Anhangsdatei fehlt.')
        return send_file(io.BytesIO(cipher().decrypt(path.read_bytes())),as_attachment=True,download_name=item['name'],mimetype='application/octet-stream')

    @app.post('/attachment/<int:aid>/delete')
    def attachment_delete(aid):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        item=one('SELECT * FROM attachments WHERE id=?',(aid,))
        if not item: abort(404)
        db.execute('DELETE FROM attachments WHERE id=?',(aid,))
        answer=result('Anhang gelöscht.')
        (Path(app.instance_path)/'attachments'/item['path']).unlink(missing_ok=True)
        return answer

    @app.get('/tasks')
    def task_list():
        from .participants import normalized
        from .ui import page_items
        mode=request.args.get('filter','open')
        where={'open':'done=0','undated':'done=0 AND due IS NULL','done':'done=1','all':'1=1'}.get(mode,'done=0')
        data=rows('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE '+where+' ORDER BY done,due IS NULL,due,t.id')
        query=normalized(request.args.get('q',''))
        if query: data=[t for t in data if all(word in normalized(t['text']) for word in query.split())]
        for key in ('project_id','case_id'):
            value=request.args.get(key,type=int)
            if value: data=[t for t in data if t[key]==value]
        due=request.args.get('due','')
        today=now().date()
        if due=='overdue': data=[t for t in data if t['due'] and t['due']<today.isoformat()]
        elif due=='today': data=[t for t in data if t['due']==today.isoformat()]
        elif due=='week': data=[t for t in data if t['due'] and today.isoformat()<=t['due']<=(today+timedelta(days=7)).isoformat()]
        elif due=='undated': data=[t for t in data if not t['due']]
        data,paging=page_items(data,focus=request.args.get('focus_task',type=int))
        return render_template('tasks.html',tasks=data,mode=mode,**paging)

    @app.post('/task/save')
    def task_save():
        get_db().execute('BEGIN IMMEDIATE')
        tid=request.form.get('id',type=int)
        if tid and not one('SELECT id FROM tasks WHERE id=?',(tid,)): abort(404)
        from .recurrence import parse, create, generate
        config=parse(request.form) if request.form.get('repeat_frequency') else None
        data=request.form.to_dict()
        if config: data['due']=config['start_date']
        tid=save_task(data,tid)
        from .domain import save_task_rows
        texts=request.form.getlist('subtask_text')
        dates=request.form.getlist('subtask_due') or ['']*len(texts)
        save_task_rows(texts,dates,parent_id=tid)
        if config:
            create(tid,config)
            generate()
        return result('Aufgabe gespeichert.')

    @app.get('/task-series')
    def task_series_list():
        return render_template('task_series.html',series=rows('''SELECT s.*,
            (SELECT count(*) FROM task_occurrences o JOIN tasks t ON t.id=o.task_id WHERE o.series_id=s.id AND t.done=0) open_count
            FROM task_series s ORDER BY s.active DESC,s.template,s.id'''))

    @app.get('/task-series/<int:sid>')
    def task_series_view(sid):
        series=one('SELECT * FROM task_series WHERE id=?',(sid,))
        if not series: abort(404)
        from .ui import page_items
        tasks,paging=page_items(rows('SELECT t.*,p.name project_name FROM task_occurrences o JOIN tasks t ON t.id=o.task_id LEFT JOIN projects p ON p.id=t.project_id WHERE o.series_id=? ORDER BY o.due DESC',(sid,)))
        return render_template('task_series_detail.html',series=series,tasks=tasks,**paging)

    @app.post('/task-series/<int:sid>/save')
    def task_series_save(sid):
        from .recurrence import update,generate
        get_db().execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM task_series WHERE id=?',(sid,)): abort(404)
        update(sid,request.form);generate()
        return result('Serie gespeichert. Bereits angelegte Aufgaben bleiben unverändert.',url_for('task_series_view',sid=sid))

    @app.post('/task-series/<int:sid>/status')
    def task_series_status(sid):
        from .recurrence import set_active,generate
        if request.form.get('active') not in ('0','1'): raise ValueError('Ungültiger Serienstatus.')
        get_db().execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM task_series WHERE id=?',(sid,)): abort(404)
        active=request.form['active']=='1'
        set_active(sid,active)
        if active: generate()
        return result('Serie fortgesetzt.' if active else 'Serie pausiert. Bereits angelegte Aufgaben bleiben erhalten.')

    @app.post('/task/<int:tid>/toggle')
    def task_toggle(tid):
        get_db().execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM tasks WHERE id=?',(tid,)): abort(404)
        from .domain import toggle_task
        toggle_task(tid)
        return result('Aufgabe aktualisiert.')

    def render_chronicle(template, **values):
        from .ui import page_items
        values['items'],paging=page_items(values['items'])
        return render_template(template,**values,**paging)

    @app.post('/task/<int:tid>/delete')
    def task_delete(tid):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM tasks WHERE id=?',(tid,)): abort(404)
        series=one('SELECT id FROM task_series WHERE source_task_id=?',(tid,))
        # Unteraufgaben gehören zur Hauptaufgabe und gehen mit ihr.
        db.execute('DELETE FROM tasks WHERE parent_id=?',(tid,))
        db.execute('DELETE FROM tasks WHERE id=?',(tid,))
        if series:
            db.execute('UPDATE task_series SET active=0 WHERE id=?',(series['id'],))
        return result('Aufgabe gelöscht.'+(' Die Aufgabenserie wurde angehalten.' if series else ''))

    @app.get('/cases')
    def case_list():
        from .cases import STATUSES
        from .participants import normalized
        mode=request.args.get('status','active')
        query=normalized(request.args.get('q',''))
        data=rows('''SELECT c.*,
            (SELECT count(*) FROM entry_cases ec WHERE ec.case_id=c.id) entry_count,
            (SELECT count(*) FROM tasks t WHERE t.case_id=c.id AND t.done=0) open_tasks
            FROM cases c ORDER BY c.follow_up IS NULL,c.follow_up,c.title,c.id''')
        data=[c for c in data if (mode=='all' or (mode=='active' and c['status']!='done') or c['status']==mode)
              and all(word in normalized(c['title']+' '+c['description']) for word in query.split())]
        from .case_suggestions import suggestions
        from .ui import page_items
        data,paging=page_items(data)
        return render_template('cases.html',suggestions=suggestions(),ignored=suggestions('ignored'),cases=data,mode=mode,query=request.args.get('q',''),**paging)

    @app.get('/case/<int:cid>')
    def case_view(cid):
        case=one('SELECT * FROM cases WHERE id=?',(cid,))
        if not case: abort(404)
        from .entry_links import incoming_case
        return render_chronicle('case.html',case=case,
            items=entries('SELECT e.* FROM entries e JOIN entry_cases ec ON ec.entry_id=e.id WHERE ec.case_id=? ORDER BY e.date DESC,e.time DESC,e.id DESC',(cid,)),
            tasks=rows('SELECT t.*,p.name project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE t.case_id=? ORDER BY t.done,t.due IS NULL,t.due,t.id',(cid,)),
            resource_entries=incoming_case(cid))

    @app.post('/case/save')
    def case_save():
        from .cases import save
        cid=request.form.get('id',type=int)
        if cid and not one('SELECT id FROM cases WHERE id=?',(cid,)): abort(404)
        sid=request.form.get('suggestion_id',type=int)
        if sid and not one('SELECT id FROM case_suggestions WHERE id=? AND case_id IS NULL',(sid,)): abort(404)
        cid=save(request.form,cid)
        if sid:
            from .case_suggestions import resolve
            resolve(sid,cid)
        from .case_suggestions import reconcile
        reconcile(cid)
        return result('Vorgang gespeichert.',url_for('case_view',cid=cid))

    @app.post('/case-suggestion/<int:sid>/resolve')
    def case_suggestion_resolve(sid):
        from .case_suggestions import resolve
        from .cases import save
        proposal=one('SELECT * FROM case_suggestions WHERE id=? AND case_id IS NULL',(sid,))
        if not proposal: abort(404)
        cid=request.form.get('case_id',type=int)
        if not cid: cid=save({'title':proposal['name']})
        resolve(sid,cid)
        return result('Vorgang übernommen und Zuordnungen gespeichert.',url_for('case_view',cid=cid))

    @app.post('/case-suggestion/<int:sid>/status')
    def case_suggestion_status(sid):
        status=request.form.get('status')
        if status not in ('pending','ignored'): raise ValueError('Ungültiger Vorschlagsstatus.')
        if not one('SELECT id FROM case_suggestions WHERE id=? AND case_id IS NULL',(sid,)): abort(404)
        get_db().execute('UPDATE case_suggestions SET status=? WHERE id=?',(status,sid))
        return result('Vorschlag aktualisiert.')

    @app.post('/case/<int:cid>/status')
    def case_status(cid):
        from .cases import STATUSES
        if not one('SELECT id FROM cases WHERE id=?',(cid,)): abort(404)
        status=request.form.get('status')
        if status not in STATUSES: raise ValueError('Bitte einen gültigen Vorgangsstatus auswählen.')
        follow_up=valid_date(request.form.get('follow_up'),optional=True)
        get_db().execute('UPDATE cases SET status=?,follow_up=? WHERE id=?',(status,follow_up,cid))
        return result('Stand und Wiedervorlage gespeichert.',url_for('case_view',cid=cid))

    @app.post('/case/<int:cid>/entry')
    def case_entry(cid):
        eid=request.form.get('entry_id',type=int)
        if not one('SELECT id FROM cases WHERE id=?',(cid,)): abort(404)
        if not eid or not one('SELECT id FROM entries WHERE id=?',(eid,)):
            raise ValueError('Bitte einen vorhandenen Eintrag auswählen.')
        get_db().execute('INSERT OR IGNORE INTO entry_cases(entry_id,case_id) VALUES(?,?)',(eid,cid))
        return result('Eintrag dem Vorgang zugeordnet.',url_for('case_view',cid=cid))

    @app.post('/case/<int:cid>/entry/<int:eid>/remove')
    def case_entry_remove(cid,eid):
        if not one('SELECT id FROM cases WHERE id=?',(cid,)): abort(404)
        get_db().execute('DELETE FROM entry_cases WHERE entry_id=? AND case_id=?',(eid,cid))
        return result('Eintragszuordnung entfernt.',url_for('case_view',cid=cid))

    @app.post('/case/<int:cid>/delete')
    def case_delete(cid):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM cases WHERE id=?',(cid,)): abort(404)
        db.execute('DELETE FROM cases WHERE id=?',(cid,))
        return result('Vorgang gelöscht. Einträge und Aufgaben bleiben erhalten.',url_for('case_list'))

    @app.get('/projects')
    def projects():
        status='closed' if request.args.get('status')=='closed' else 'active'
        from .project_suggestions import suggestions
        from .participants import normalized
        from .ui import page_items
        data=rows('SELECT p.*,(SELECT count(*) FROM tasks WHERE project_id=p.id AND done=0) open_tasks,(SELECT count(*) FROM entry_projects WHERE project_id=p.id) entry_count FROM projects p WHERE status=? ORDER BY name',(status,))
        query=normalized(request.args.get('q',''))
        if query: data=[p for p in data if all(word in normalized(p['name']+' '+p['description']) for word in query.split())]
        data,paging=page_items(data)
        return render_template('projects.html',suggestions=suggestions(),ignored=suggestions('ignored'),projects=data,status=status,**paging)

    @app.post('/project/save')
    def project_save():
        from .project_suggestions import resolve
        get_db().execute('BEGIN IMMEDIATE')
        sid=request.form.get('suggestion_id',type=int)
        if sid:
            proposal=one('SELECT * FROM project_suggestions WHERE id=?',(sid,))
            if not proposal or proposal['project_id']: raise ValueError('Dieser Vorschlag wurde bereits übernommen oder entfernt.')
        name=request.form.get('name','').strip()
        if not name: raise ValueError('Der Projektname fehlt noch.')
        year=request.form.get('school_year','').strip() or school_year()
        import re
        if not re.fullmatch(r'\d{4}/\d{2}',year): raise ValueError('Schuljahr bitte als 2026/27 angeben.')
        pid=request.form.get('id',type=int)
        if pid:
            if not one('SELECT id FROM projects WHERE id=?',(pid,)): abort(404)
            get_db().execute('UPDATE projects SET name=?,description=?,school_year=? WHERE id=?',(name,request.form.get('description',''),year,pid))
        else:
            pid=get_db().execute('INSERT INTO projects(name,description,school_year) VALUES(?,?,?)',(name,request.form.get('description',''),year)).lastrowid
        if sid: resolve(sid,pid)
        from .project_suggestions import reconcile
        reconcile(pid)
        return result('Projekt gespeichert.',url_for('project_view',pid=pid))

    @app.post('/project-suggestion/<int:sid>/link')
    def project_suggestion_link(sid):
        from .project_suggestions import resolve
        get_db().execute('BEGIN IMMEDIATE')
        resolve(sid,request.form.get('project_id',type=int))
        return result('Projektvorschlag zugeordnet.')

    @app.post('/project-suggestion/<int:sid>/status')
    def project_suggestion_status(sid):
        status=request.form.get('status')
        if status not in ('pending','ignored'): raise ValueError('Ungültiger Vorschlagsstatus.')
        if not one('SELECT id FROM project_suggestions WHERE id=? AND project_id IS NULL',(sid,)): abort(404)
        get_db().execute('UPDATE project_suggestions SET status=? WHERE id=?',(status,sid))
        return result('Projektvorschlag aktualisiert.')

    @app.get('/project/<int:pid>')
    def project_view(pid):
        project=one('SELECT * FROM projects WHERE id=?',(pid,))
        if not project: abort(404)
        return render_chronicle('project.html',project=project,items=entries('SELECT e.* FROM entries e JOIN entry_projects ep ON ep.entry_id=e.id WHERE ep.project_id=? ORDER BY date DESC,time DESC,id DESC',(pid,)),tasks=rows('SELECT t.*,NULL project_name FROM tasks t WHERE project_id=? ORDER BY done,due IS NULL,due',(pid,)),attachments=rows('SELECT a.* FROM attachments a JOIN entry_projects ep ON ep.entry_id=a.entry_id WHERE ep.project_id=?',(pid,)))

    @app.post('/project/<int:pid>/status')
    def project_status(pid):
        project=one('SELECT * FROM projects WHERE id=?',(pid,))
        if not project: abort(404)
        status='active' if project['status']=='closed' else 'closed'
        if status=='closed' and request.form.get('template'):
            month=request.form.get('month',type=int)
            period=request.form.get('period','early')
            if month not in range(1,13) or period not in PERIODS: raise ValueError('Bitte einen gültigen Zeitraum wählen.')
            todos=[t['text'] for t in rows('SELECT text FROM tasks WHERE project_id=? ORDER BY id',(pid,))]
            if project['process_id']:
                get_db().execute('UPDATE processes SET todos=?,month=?,period=? WHERE id=?',(json.dumps(todos),month,period,project['process_id']))
            else:
                process=get_db().execute('INSERT INTO processes(name,month,period,todos,last_trigger) VALUES(?,?,?,?,?)',(project['name'],month,period,json.dumps(todos),school_year())).lastrowid
                get_db().execute('UPDATE projects SET process_id=? WHERE id=?',(process,pid))
        get_db().execute('UPDATE projects SET status=? WHERE id=?',(status,pid))
        return result('Projektstatus aktualisiert.',url_for('project_view',pid=pid))

    @app.post('/project/<int:pid>/delete')
    def project_delete(pid):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM projects WHERE id=?',(pid,)): abort(404)
        db.execute('DELETE FROM projects WHERE id=?',(pid,))
        from .project_suggestions import prune
        prune()
        return result('Projekt gelöscht. Einträge und Aufgaben bleiben erhalten.',url_for('projects'))

    @app.post('/document/save')
    def document_save():
        from .documents import save, associate
        get_db().execute('BEGIN IMMEDIATE')
        did=request.form.get('id',type=int)
        owner=request.form.get('owner','')
        owner_id=request.form.get('owner_id',type=int)
        if not did and (owner not in ('entry','project') or not owner_id):
            raise ValueError('Bitte einen Eintrag oder ein Projekt für das Dokument wählen.')
        did=save(request.form,did)
        if owner: associate(did,owner,owner_id)
        return result('Dokumentverweis gespeichert.')

    @app.post('/document/<int:did>/detach')
    def document_detach(did):
        owner=request.form.get('owner')
        if owner not in ('entry','project'): raise ValueError('Ungültige Zuordnung.')
        get_db().execute(f'DELETE FROM {owner}_documents WHERE document_id=? AND {owner}_id=?',(did,request.form.get('owner_id',type=int)))
        return result('Verknüpfung entfernt. Die Datei in Nextcloud bleibt erhalten.')

    @app.post('/document/<int:did>/delete')
    def document_delete(did):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM documents WHERE id=?',(did,)): abort(404)
        db.execute('DELETE FROM documents WHERE id=?',(did,))
        return result('Dokumentverweis gelöscht. Die Datei in Nextcloud bleibt erhalten.',url_for('cockpit'))

    @app.get('/api/nextcloud/files')
    def nextcloud_files():
        """Ordner der eigenen Nextcloud auflisten oder darin nach Namen suchen."""
        from .nextcloud import blaettern, dateien_suchen
        begriff=request.args.get('q','').strip()
        return jsonify(dateien_suchen(begriff) if begriff else blaettern(request.args.get('path','')))

    @app.get('/document/<int:did>/info')
    def document_info(did):
        from .nextcloud import referenz, infos
        document=one('SELECT url FROM documents WHERE id=?',(did,))
        if not document: abort(404)
        ref=referenz(document['url'])
        if not ref: abort(404,'Dieser Link gehört nicht zur eingerichteten Nextcloud.')
        return jsonify(infos(ref))

    @app.get('/document/<int:did>/page/<int:page>')
    def document_page(did,page):
        """Ein Seitenbild aus der Nextcloud – gerendert im Journal, nicht im Browser."""
        from .nextcloud import referenz, vorschau
        document=one('SELECT url FROM documents WHERE id=?',(did,))
        if not document: abort(404)
        ref=referenz(document['url'])
        if not ref: abort(404,'Dieser Link gehört nicht zur eingerichteten Nextcloud.')
        if not 1<=page<=2000: raise ValueError('Diese Seite gibt es nicht.')
        ergebnis=vorschau(ref,page)
        return send_file(io.BytesIO(ergebnis['bild']),mimetype='image/png')

    @app.get('/document/<int:did>/file')
    def document_file(did):
        """Die Originaldatei über das Journal ausliefern – ohne Anmeldung in der Nextcloud."""
        from .nextcloud import referenz, datei
        document=one('SELECT * FROM documents WHERE id=?',(did,))
        if not document: abort(404)
        ref=referenz(document['url'])
        if not ref: abort(404,'Dieser Link gehört nicht zur eingerichteten Nextcloud.')
        inhalt=datei(ref)
        return send_file(io.BytesIO(inhalt['inhalt']),as_attachment=True,
                         download_name=inhalt['name'] or document['name'],mimetype='application/octet-stream')

    @app.get('/document/<int:did>')
    def document_view(did):
        from .nextcloud import referenz, konto
        document=one('SELECT * FROM documents WHERE id=?',(did,))
        if not document: abort(404)
        return render_template('document.html',document=document,
            nextcloud=bool(konto()),lesbar=bool(referenz(document['url'])),
            document_entries=rows('SELECT e.id,e.title FROM entries e JOIN entry_documents ed ON ed.entry_id=e.id WHERE ed.document_id=? ORDER BY e.date DESC',(did,)),
            document_projects=rows('SELECT p.id,p.name FROM projects p JOIN project_documents pd ON pd.project_id=p.id WHERE pd.document_id=? ORDER BY p.name',(did,)))

    @app.get('/search')
    def global_search():
        from .resources import search
        query=request.args.get('q','').strip()[:200]
        page=max(1,request.args.get('page',1,type=int))
        found=search(query,fulltext=True,limit=40,offset=(page-1)*40)
        return render_template('search.html',query=query,page=page,**found)

    @app.get('/api/search')
    def global_search_suggestions():
        from .resources import search
        return jsonify(search(request.args.get('q',''),fulltext=True,limit=10))

    @app.get('/api/search/<scope>')
    def scoped_search_suggestions(scope):
        from .search_fields import suggestions
        return jsonify(suggestions(scope,request.args))

    @app.get('/api/contact-values/<field>')
    def contact_field_suggestions(field):
        from .search_fields import contact_values
        return jsonify(contact_values(field,request.args.get('q','')))

    @app.get('/api/resources')
    def resource_search():
        from .resources import search
        return jsonify(search(request.args.get('q','')))

    @app.post('/note/attach')
    def note_attach():
        """Hängt eine vorhandene Ressource an eine Notiz; ein neuer Name legt sie an."""
        from .entry_links import add
        from .participants import normalized
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        source=request.form.get('resource_url','').strip()
        if not source:
            raise ValueError('Bitte eine Quelle auswählen.')
        target=request.form.get('target_id',type=int)
        if target:
            if not one('SELECT id FROM entries WHERE id=?',(target,)): abort(404)
        else:
            title=' '.join(request.form.get('target_title','').split())
            if not title or len(title)>500:
                raise ValueError('Bitte eine Notiz auswählen oder einen Namen mit höchstens 500 Zeichen eingeben.')
            matches=[e for e in rows('SELECT id,title FROM entries') if normalized(e['title'])==normalized(title)]
            if len(matches)>1:
                raise ValueError('Mehrere Einträge tragen diesen Namen. Bitte einen davon aus der Vorschlagsliste wählen.')
            target=matches[0]['id'] if matches else save_entry(dict(type='note',title=title,date=now().date().isoformat(),body=''))
        add(target,source)
        return result('An die Notiz angehängt.',url_for('entry_view',eid=target,_anchor='entry-resources'))

    @app.get('/appointments')
    def appointment_list():
        from .meetings import listing
        from .ui import page_items
        start=valid_date(request.args.get('from',now().date().isoformat()))
        events,paging=page_items(listing(request.args.get('q',''),start,include_prepared=True))
        return render_template('appointments.html',events=events,start=start,**paging)

    @app.get('/appointment/<int:aid>')
    def appointment_view(aid):
        from .meetings import get, points
        event=get(aid)
        if not event:abort(404)
        from .meetings import protocol_candidates
        return render_template('appointment.html',event=event,tasks=points(aid),protocol_matches=protocol_candidates(event))

    @app.post('/appointments/sync')
    def appointments_sync():
        from .integrations import sync_calendar
        if not setting('caldav',{}).get('url'):
            raise ValueError('Bitte zuerst den Nextcloud-Kalender in den Einstellungen verbinden.')
        start=date.fromisoformat(valid_date(request.form.get('start_date') or now().date().isoformat()))
        try:
            message=sync_calendar(start,90)
        except Exception:
            get_db().rollback()
            raise ValueError('Kalender konnte nicht aktualisiert werden. Gespeicherte Termine bleiben erhalten. Bitte die Verbindung in den Einstellungen prüfen.') from None
        return result(message)

    @app.post('/meeting-point/save')
    def meeting_point_save():
        from .meetings import create_point
        get_db().execute('BEGIN IMMEDIATE')
        event_id,tid=create_point(request.form)
        return result('Besprechungspunkt vorgemerkt.',url_for('appointment_view',aid=event_id,_anchor='task-'+str(tid)))

    def open_calendar_protocol(event,event_id=None):
        from .meetings import create_protocol,protocol_candidates,linked_protocol
        candidates=protocol_candidates(event)
        chosen=request.form.get('existing_id')
        force=request.form.get('create_new')=='1'
        previous=linked_protocol(event)
        if len(candidates)>1 and not chosen and not force and not previous:
            get_db().rollback()
            return render_template('protocol_choice.html',event=event,candidates=candidates)
        eid=create_protocol(event_id,event=event,existing_id=chosen,force_new=force)
        return result('Protokoll zum Termin geöffnet.',url_for('entry_view',eid=eid))

    @app.post('/appointment/<int:aid>/protocol')
    def appointment_protocol(aid):
        from .meetings import get
        get_db().execute('BEGIN IMMEDIATE')
        event=get(aid)
        if not event:abort(404)
        return open_calendar_protocol(event,aid)

    @app.post('/calendar/protocol')
    def cached_calendar_protocol():
        from .integrations import cached_events
        day=date.fromisoformat(valid_date(request.form.get('date')))
        events,_=cached_events(day)
        index=request.form.get('event_index',type=int)
        if index is None or not 0<=index<len(events):raise ValueError('Der Termin wurde aktualisiert. Bitte die Terminübersicht neu laden.')
        event=events[index]
        # Reject stale forms instead of selecting a different event after a refresh.
        from .meetings import legacy_protocol_key,cached_meeting
        if request.form.get('event_key')!=legacy_protocol_key(event):raise ValueError('Der Termin wurde aktualisiert. Bitte die Terminübersicht neu laden.')
        get_db().execute('BEGIN IMMEDIATE')
        linked=cached_meeting(event)
        return open_calendar_protocol(linked or event,linked['id'] if linked else None)

    @app.get('/api/autocomplete/<kind>')
    def autocomplete(kind):
        from .participants import normalized
        query=normalized(request.args.get('q',''))[:200]
        result=[]
        if kind=='notes':
            for e in rows("SELECT id,title,date,type FROM entries ORDER BY type<>'note',date DESC,id DESC"):
                if all(word in normalized(e['title']) for word in query.split()):
                    result.append(dict(kind='entry',id=e['id'],label=e['title'],detail=TYPES[e['type']]+' · '+e['date']))
            return jsonify(items=result[:12],more=len(result)>12)
        if kind=='appointments':
            from .meetings import listing
            start=valid_date(request.args.get('from',now().date().isoformat()))
            events=listing(query,start)
            return jsonify(items=[dict(kind='appointment',id=e['id'],label=e['date']+' '+e['time']+' · '+e['title'],detail=e['calendar']+(' · '+e['location'] if e['location'] else '')) for e in events[:12]],more=len(events)>12,loaded=one('SELECT count(*) n FROM calendar_events')['n'],configured=bool(setting('caldav',{}).get('url')))
        if kind in ('participants','people'):
            aliases={}
            for alias in rows('SELECT normalized,person_id FROM contact_suggestions WHERE person_id IS NOT NULL'):
                aliases.setdefault(alias['person_id'],[]).append(alias['normalized'])
            for person in rows('SELECT * FROM people ORDER BY name,id'):
                haystack=normalized(' '.join([person['name'],person['role'],person['institution'],person['emails'],person['phone'],*aliases.get(person['id'],[])]))
                if not query or all(word in haystack for word in query.split()):
                    result.append(dict(kind='person',id=person['id'],label=person['name'],detail=' · '.join(v for v in [person['role'],person['institution'],person['emails']] if v)))
            if kind=='participants':
                for proposal in rows("SELECT s.* FROM contact_suggestions s WHERE s.status='pending' AND EXISTS(SELECT 1 FROM entry_suggestions es WHERE es.suggestion_id=s.id) ORDER BY s.name"):
                    if not query or query in normalized(proposal['name']):
                        result.append(dict(kind='new',label=proposal['name'],detail='Kontaktvorschlag'))
        elif kind=='projects':
            include_closed=request.args.get('include_closed')=='1'
            for project in rows('SELECT * FROM projects ORDER BY status,name,school_year DESC'):
                if project['status']=='closed' and not include_closed:
                    continue
                if not query or all(word in normalized(project['name']+' '+project['school_year']) for word in query.split()):
                    detail=project['school_year']+(' · abgeschlossen' if project['status']=='closed' else '')
                    result.append(dict(kind='project',id=project['id'],label=project['name'],detail=detail))
            if request.args.get('existing_only')!='1':
                from .project_suggestions import suggestions
                for proposal in suggestions():
                    if not query or all(word in normalized(proposal['name']+' '+proposal['school_year']) for word in query.split()):
                        result.append(dict(kind='new_project',label=proposal['name'],school_year=proposal['school_year'],detail=proposal['school_year']+' · Projektvorschlag'))
        elif kind=='cases':
            from .cases import STATUSES
            for case in rows('SELECT * FROM cases ORDER BY status,title,id'):
                if case['status']=='done' and request.args.get('include_closed')!='1':
                    continue
                if not query or all(word in normalized(case['title']+' '+STATUSES[case['status']]) for word in query.split()):
                    result.append(dict(kind='case',id=case['id'],label=case['title'],detail=STATUSES[case['status']]))
            if request.args.get('existing_only')!='1':
                from .case_suggestions import suggestions
                for proposal in suggestions():
                    if not query or all(word in normalized(proposal['name']) for word in query.split()):
                        result.append(dict(kind='new_case',label=proposal['name'],detail='Vorgangsvorschlag'))
        elif kind=='entries':
            for entry in rows('SELECT id,title,date,type FROM entries ORDER BY date DESC,id DESC'):
                if not query or all(word in normalized(entry['title']+' '+TYPES[entry['type']]+' '+entry['date']) for word in query.split()):
                    result.append(dict(kind='entry',id=entry['id'],label=entry['title'],detail=TYPES[entry['type']]+' · '+entry['date']))
        elif kind=='tags':
            seen=set()
            for entry in rows("SELECT tags FROM entries WHERE tags<>''"):
                for tag in entry['tags'].split(','):
                    tag=tag.strip()
                    key=normalized(tag)
                    if key and key not in seen and (not query or query.lstrip('#') in key):
                        seen.add(key)
                        result.append(dict(kind='tag',label=tag,detail='Tag'))
        else:
            abort(404)
        result.sort(key=lambda item:(not normalized(item['label']).startswith(query),item.get('kind')=='new',normalized(item['label'])))
        return jsonify(items=result[:12],more=len(result)>12)

    @app.get('/people')
    def people():
        from .participants import normalized, suggestions
        query=normalized(request.args.get('q',''))
        people=rows('SELECT p.*,(SELECT count(*) FROM entry_people WHERE person_id=p.id) entry_count FROM people p ORDER BY name')
        if query:
            people=[p for p in people if all(word in normalized(p['name']+' '+p['role']+' '+p['institution']+' '+p['emails']+' '+p['phone']) for word in query.split())]
        institution=request.args.get('institution','').strip()
        if institution:
            people=[p for p in people if normalized(p['institution'])==normalized(institution)]
        from .ui import page_items
        people,paging=page_items(people)
        return render_template('people.html',selected_institution=institution,people=people,suggestions=suggestions(),ignored=suggestions('ignored'),**paging)

    @app.post('/person/save')
    def person_save():
        from .participants import reconcile_person, resolve_suggestion
        name=request.form.get('name','').strip()
        if not name:
            raise ValueError('Der Name fehlt noch.')
        pid=request.form.get('id',type=int)
        sid=request.form.get('suggestion_id',type=int)
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if sid:
            proposal=one('SELECT * FROM contact_suggestions WHERE id=?',(sid,))
            if not proposal or proposal['person_id']:
                raise ValueError('Dieser Kontaktvorschlag wurde bereits bearbeitet.')
        from .participants import institutions, normalized
        institution=' '.join(request.form.get('institution','').split())
        if pid and 'institution' not in request.form:
            existing=one('SELECT institution FROM people WHERE id=?',(pid,))
            institution=existing['institution'] if existing else ''
        institution=next((value for value in institutions() if normalized(value)==normalized(institution)),institution)
        existing=one('SELECT phone FROM people WHERE id=?',(pid,)) if pid else None
        phone=request.form.get('phone',existing['phone'] if existing else '').strip()
        if len(phone)>200: raise ValueError('Die Telefonnummer darf höchstens 200 Zeichen enthalten.')
        values=(name,request.form.get('role','').strip(),institution,request.form.get('emails','').lower(),phone)
        if pid:
            if not one('SELECT id FROM people WHERE id=?',(pid,)):
                abort(404)
            db.execute('UPDATE people SET name=?,role=?,institution=?,emails=?,phone=? WHERE id=?',(*values,pid))
        else:
            pid=db.execute('INSERT INTO people(name,role,institution,emails,phone) VALUES(?,?,?,?,?)',values).lastrowid
        if sid:
            resolve_suggestion(sid,pid)
        reconcile_person(pid)
        return result('Kontakt gespeichert und zugehörige Einträge verknüpft.')

    @app.post('/suggestion/<int:sid>/link')
    def suggestion_link(sid):
        from .participants import resolve_suggestion
        get_db().execute('BEGIN IMMEDIATE')
        resolve_suggestion(sid,request.form.get('person_id',type=int))
        return result('Vorschlag dem Kontakt zugeordnet.')

    @app.post('/suggestion/<int:sid>/status')
    def suggestion_status(sid):
        status=request.form.get('status')
        if status not in ('pending','ignored'):
            raise ValueError('Ungültiger Vorschlagsstatus.')
        if not one('SELECT id FROM contact_suggestions WHERE id=? AND person_id IS NULL',(sid,)):
            abort(404)
        get_db().execute('UPDATE contact_suggestions SET status=? WHERE id=?',(status,sid))
        return result('Kontaktvorschlag verworfen.' if status=='ignored' else 'Kontaktvorschlag wiederhergestellt.')

    @app.get('/person/<int:pid>')
    def person_view(pid):
        person=one('SELECT * FROM people WHERE id=?',(pid,))
        if not person: abort(404)
        return render_chronicle('person.html',person=person,items=entries('SELECT e.* FROM entries e JOIN entry_people ep ON ep.entry_id=e.id WHERE ep.person_id=? ORDER BY date DESC,time DESC',(pid,)))

    @app.post('/person/<int:pid>/delete')
    def person_delete(pid):
        from .participants import refresh_summary
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM people WHERE id=?',(pid,)): abort(404)
        affected=[row['entry_id'] for row in rows('SELECT entry_id FROM entry_people WHERE person_id=?',(pid,))]
        # Vorschläge, die auf diesen Kontakt zeigten, entfallen mit ihm.
        db.execute('DELETE FROM contact_suggestions WHERE person_id=?',(pid,))
        db.execute('DELETE FROM people WHERE id=?',(pid,))
        for entry_id in affected:
            refresh_summary(entry_id)
        return result('Kontakt gelöscht. Einträge und Aufgaben bleiben erhalten.',url_for('people'))

    @app.get('/processes')
    def processes():
        data=rows('SELECT * FROM processes ORDER BY month,period,name')
        for p in data:
            p['tasks']=json.loads(p['todos']); p['due']=process_due(p,now().date())
        return render_template('processes.html',processes=data)

    @app.post('/process/save')
    def process_save():
        name=request.form.get('name','').strip()
        month=request.form.get('month',type=int)
        period=request.form.get('period')
        if not name or month not in range(1,13) or period not in PERIODS: raise ValueError('Bitte Name und Zeitraum vollständig angeben.')
        todos=json.dumps([line.strip() for line in request.form.get('todos','').splitlines() if line.strip()])
        pid=request.form.get('id',type=int)
        if pid:
            get_db().execute('UPDATE processes SET name=?,month=?,period=?,todos=? WHERE id=?',(name,month,period,todos,pid))
        else:
            get_db().execute('INSERT INTO processes(name,month,period,todos) VALUES(?,?,?,?)',(name,month,period,todos))
        return result('Jahresprozess gespeichert.')

    @app.post('/process/<int:pid>/trigger')
    def process_trigger(pid):
        project=trigger_process(pid,now().date())
        return result('Projekt und Aufgaben angelegt.',url_for('project_view',pid=project))

    @app.post('/process/<int:pid>/delete')
    def process_delete(pid):
        db=get_db()
        db.execute('BEGIN IMMEDIATE')
        if not one('SELECT id FROM processes WHERE id=?',(pid,)): abort(404)
        db.execute('DELETE FROM processes WHERE id=?',(pid,))
        return result('Jahresprozess gelöscht. Bereits erzeugte Projekte bleiben erhalten.',url_for('processes'))

    @app.get('/settings')
    def settings():
        return render_template('settings.html',imap=setting('imap',{}),caldav=setting('caldav',{}),retention=setting('retention',{}),sync_status=setting('sync_status',{}),backup_status=setting('backup_status'),has_backup_key=(Path(app.instance_path)/'backup.key').exists())

    @app.post('/settings/save')
    def settings_save():
        from urllib.parse import urlparse
        form=request.form
        imap=setting('imap',{})
        imap.update(host=form.get('imap_host','').strip(),username=form.get('imap_username','').strip(),folder=form.get('imap_folder','INBOX').strip() or 'INBOX',own_addresses=[v.strip().lower() for v in form.get('own_addresses','').split(',') if v.strip()])
        if form.get('imap_password'): imap['password']=form['imap_password']
        if imap['host'] and (not imap['own_addresses'] or not imap['username'] or not imap.get('password')): raise ValueError('Für IMAP sind Benutzername, Passwort und eigene Mailadressen erforderlich.')
        cal=setting('caldav',{})
        cal.update(url=form.get('caldav_url','').strip(),username=form.get('caldav_username','').strip(),calendars=[s.strip() for s in form.get('calendars','').splitlines() if s.strip()])
        if cal['url'] and (urlparse(cal['url']).scheme!='https' or not urlparse(cal['url']).hostname): raise ValueError('Die CalDAV-Adresse muss eine gültige HTTPS-Adresse sein.')
        if form.get('caldav_password'): cal['password']=form['caldav_password']
        if cal['url'] and (not cal['username'] or not cal.get('password')): raise ValueError('Für CalDAV sind Benutzername und App-Token erforderlich.')
        retention={}
        for kind in TYPES:
            value=form.get('retention_'+kind,'').strip()
            if value:
                try: days=int(value)
                except ValueError: raise ValueError('Aufbewahrungsfristen bitte in Tagen eingeben.')
                if days<1: raise ValueError('Aufbewahrungsfristen müssen mindestens einen Tag betragen.')
                retention[kind]=days
        set_setting('imap',imap); set_setting('caldav',cal); set_setting('retention',retention)
        from .participants import drop_own_suggestions
        drop_own_suggestions()
        if form.get('intent')=='sync':
            from .integrations import sync_all
            get_db().commit()
            return result('Einstellungen gespeichert. '+sync_all())
        return result('Einstellungen gespeichert.')

    @app.post('/sync')
    def sync():
        from .integrations import sync_all
        day=date.fromisoformat(valid_date(request.form['date'])) if request.form.get('date') else None
        report=sync_all(day)
        return result(report)

    @app.post('/mail/import')
    def import_mail():
        from .integrations import import_message
        upload=request.files.get('eml')
        if not upload or not upload.filename: raise ValueError('Bitte eine .eml-Datei auswählen.')
        status=import_message(upload.read(),setting('imap',{}).get('own_addresses',[]),enforce_sender=True)
        return result({'imported':'Mail importiert.','duplicate':'Diese Mail wurde bereits importiert.','rejected':'Nicht importiert: Der Absender gehört nicht zu den konfigurierten eigenen Adressen.'}[status])

    return app
