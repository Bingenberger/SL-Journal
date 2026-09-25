import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from flask import current_app, g
from sqlcipher3 import dbapi2 as sqlite


SCHEMA = '''
CREATE TABLE IF NOT EXISTS account (
 id INTEGER PRIMARY KEY CHECK(id=1), password TEXT NOT NULL, totp TEXT NOT NULL,
 last_totp INTEGER NOT NULL DEFAULT -1, session_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_limit (id INTEGER PRIMARY KEY CHECK(id=1), failures INTEGER DEFAULT 0, until REAL DEFAULT 0);
INSERT OR IGNORE INTO login_limit(id) VALUES(1);
CREATE TABLE IF NOT EXISTS processes (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
 period TEXT NOT NULL CHECK(period IN ('early','middle','late')), todos TEXT NOT NULL DEFAULT '[]', last_trigger TEXT);
CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed')), school_year TEXT NOT NULL,
 process_id INTEGER REFERENCES processes(id) ON DELETE SET NULL,
 UNIQUE(process_id, school_year));
CREATE TABLE IF NOT EXISTS cases (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','clarifying','done')),
 follow_up TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS case_suggestions (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ignored','resolved')),
 case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS entry_case_suggestions (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
 suggestion_id INTEGER REFERENCES case_suggestions(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,suggestion_id));
CREATE TABLE IF NOT EXISTS task_case_suggestions (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
 suggestion_id INTEGER REFERENCES case_suggestions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS entry_cases (
 entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
 case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,case_id));
CREATE INDEX IF NOT EXISTS entry_cases_case ON entry_cases(case_id);
CREATE TABLE IF NOT EXISTS entries (
 id INTEGER PRIMARY KEY, date TEXT NOT NULL, time TEXT NOT NULL DEFAULT '',
 type TEXT NOT NULL CHECK(type IN ('mail_in','mail_out','meeting','phone','journal','note','protocol')),
 title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', agenda TEXT NOT NULL DEFAULT '', decisions TEXT NOT NULL DEFAULT '', participants TEXT NOT NULL DEFAULT '',
 sender TEXT NOT NULL DEFAULT '', recipients TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '',
 source_key TEXT UNIQUE, needs_review INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS entry_projects (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE, project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,project_id));
CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', institution TEXT NOT NULL DEFAULT '', emails TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS entry_people (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE, person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,person_id));
CREATE TABLE IF NOT EXISTS contact_suggestions (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ignored','resolved')),
 person_id INTEGER REFERENCES people(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS entry_suggestions (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
 suggestion_id INTEGER REFERENCES contact_suggestions(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,suggestion_id));
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, text TEXT NOT NULL, due TEXT, done INTEGER NOT NULL DEFAULT 0,
 project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
 entry_id INTEGER REFERENCES entries(id) ON DELETE SET NULL, completed_at TEXT,
 parent_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
 case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS calendar_events (
 id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
 calendar_key TEXT NOT NULL, uid TEXT NOT NULL, occurrence TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL, calendar TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 start_at TEXT NOT NULL, end_at TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL DEFAULT '',
 all_day INTEGER NOT NULL DEFAULT 0, color INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','missing')),
 protocol_entry_id INTEGER REFERENCES entries(id) ON DELETE SET NULL);
CREATE INDEX IF NOT EXISTS calendar_events_start ON calendar_events(start_at);
CREATE TABLE IF NOT EXISTS calendar_protocol_links (
 event_key TEXT PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS meeting_points (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
 event_id INTEGER NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
 source_entry_id INTEGER REFERENCES entries(id) ON DELETE SET NULL,
 attachment_id INTEGER REFERENCES attachments(id) ON DELETE SET NULL,
 document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
 resource_label TEXT NOT NULL DEFAULT '', request_key TEXT NOT NULL UNIQUE);
CREATE INDEX IF NOT EXISTS meeting_points_event ON meeting_points(event_id);
CREATE TABLE IF NOT EXISTS task_series (
 id INTEGER PRIMARY KEY, template TEXT NOT NULL,
 frequency TEXT NOT NULL CHECK(frequency IN ('weekly','monthly','quarterly','dates')),
 interval INTEGER NOT NULL DEFAULT 1 CHECK(interval BETWEEN 1 AND 52),
 start_date TEXT NOT NULL, until_date TEXT, dates TEXT NOT NULL DEFAULT '[]', next_due TEXT,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 source_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS task_occurrences (
 series_id INTEGER NOT NULL REFERENCES task_series(id) ON DELETE CASCADE,
 due TEXT NOT NULL, task_id INTEGER UNIQUE REFERENCES tasks(id) ON DELETE SET NULL,
 PRIMARY KEY(series_id,due));
CREATE TABLE IF NOT EXISTS task_series_children (
 series_id INTEGER NOT NULL REFERENCES task_series(id) ON DELETE CASCADE,
 source_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 template TEXT NOT NULL, PRIMARY KEY(series_id,source_task_id));
CREATE INDEX IF NOT EXISTS task_series_due ON task_series(active,next_due);
CREATE TABLE IF NOT EXISTS project_suggestions (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized TEXT NOT NULL, school_year TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ignored','resolved')),
 project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
 UNIQUE(normalized,school_year));
CREATE TABLE IF NOT EXISTS entry_project_suggestions (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
 suggestion_id INTEGER REFERENCES project_suggestions(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,suggestion_id));
CREATE TABLE IF NOT EXISTS task_project_suggestions (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
 suggestion_id INTEGER REFERENCES project_suggestions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS attachments (
 id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
 name TEXT NOT NULL, path TEXT NOT NULL UNIQUE, mime TEXT NOT NULL, size INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
 description TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS entry_documents (
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
 document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
 PRIMARY KEY(entry_id,document_id));
CREATE TABLE IF NOT EXISTS project_documents (
 project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
 document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
 PRIMARY KEY(project_id,document_id));
CREATE TABLE IF NOT EXISTS drawings (
 id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
 client_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL, scene TEXT NOT NULL, preview BLOB NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS drawing_entry ON drawings(entry_id);
CREATE TABLE IF NOT EXISTS entry_resource_links (
 id INTEGER PRIMARY KEY, owner_entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
 entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
 person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
 project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
 task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
 document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
 case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
 tag TEXT COLLATE NOCASE,
 CHECK((entry_id IS NOT NULL)+(person_id IS NOT NULL)+(project_id IS NOT NULL)+
       (task_id IS NOT NULL)+(document_id IS NOT NULL)+(case_id IS NOT NULL)+(tag IS NOT NULL)=1),
 UNIQUE(owner_entry_id,entry_id), UNIQUE(owner_entry_id,person_id), UNIQUE(owner_entry_id,project_id),
 UNIQUE(owner_entry_id,task_id), UNIQUE(owner_entry_id,document_id), UNIQUE(owner_entry_id,case_id), UNIQUE(owner_entry_id,tag));
CREATE INDEX IF NOT EXISTS entry_resource_links_entry ON entry_resource_links(entry_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imports (source_key TEXT PRIMARY KEY, imported_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS entry_date ON entries(date);
CREATE INDEX IF NOT EXISTS task_due ON tasks(done,due);
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(title,body,participants,sender,tags,agenda,decisions,content='entries',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
 INSERT INTO entries_fts(rowid,title,body,participants,sender,tags,agenda,decisions) VALUES(new.id,new.title,new.body,new.participants,new.sender,new.tags,new.agenda,new.decisions); END;
CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
 INSERT INTO entries_fts(entries_fts,rowid,title,body,participants,sender,tags,agenda,decisions) VALUES('delete',old.id,old.title,old.body,old.participants,old.sender,old.tags,old.agenda,old.decisions); END;
CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
 INSERT INTO entries_fts(entries_fts,rowid,title,body,participants,sender,tags,agenda,decisions) VALUES('delete',old.id,old.title,old.body,old.participants,old.sender,old.tags,old.agenda,old.decisions);
 INSERT INTO entries_fts(rowid,title,body,participants,sender,tags,agenda,decisions) VALUES(new.id,new.title,new.body,new.participants,new.sender,new.tags,new.agenda,new.decisions); END;
'''


def connect(path, key):
    db = sqlite.connect(str(path), timeout=20)
    db.row_factory = sqlite.Row
    from .tags import has_tag
    db.create_function('has_tag',2,has_tag,deterministic=True)
    raw = base64.urlsafe_b64decode(key).hex()
    db.execute(f'''PRAGMA key = "x'{raw}'"''')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA secure_delete=ON')
    db.execute('PRAGMA temp_store=MEMORY')
    return db


def get_db():
    if 'db' not in g:
        g.db = connect(Path(current_app.instance_path) / 'journal.db', current_app.config['DATA_KEY'])
    return g.db


def migrate_protocol_schema(db):
    existing=db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'").fetchone()
    if existing and "'protocol'" not in existing['sql']:
        # Rebuild the CHECK constraint with foreign keys disabled only for this
        # transaction. Child tables continue to reference the final name entries.
        db.commit()
        db.execute('PRAGMA foreign_keys=OFF')
        try:
            db.execute('BEGIN IMMEDIATE')
            statement=SCHEMA[SCHEMA.index('CREATE TABLE IF NOT EXISTS entries ('):SCHEMA.index('CREATE TABLE IF NOT EXISTS entry_projects')]
            db.execute(statement.replace('IF NOT EXISTS entries (','entries_protocol_new ('))
            columns=[row['name'] for row in db.execute('PRAGMA table_info(entries)')]
            names=','.join('"'+name+'"' for name in columns)
            db.execute(f'INSERT INTO entries_protocol_new ({names}) SELECT {names} FROM entries')
            db.execute('DROP TABLE entries')
            db.execute('ALTER TABLE entries_protocol_new RENAME TO entries')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Die Protokollmigration würde Verknüpfungen beschädigen.')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute('PRAGMA foreign_keys=ON')
    if existing:
        columns={row['name'] for row in db.execute('PRAGMA table_info(entries)')}
        for name in ('agenda','decisions'):
            if name not in columns:
                db.execute(f"ALTER TABLE entries ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        db.commit()
    fts_columns={row['name'] for row in db.execute('PRAGMA table_info(entries_fts)')}
    rebuild=not {'agenda','decisions'} <= fts_columns
    if rebuild:
        for trigger in ('entries_ai','entries_ad','entries_au'):
            db.execute(f'DROP TRIGGER IF EXISTS {trigger}')
        db.execute('DROP TABLE IF EXISTS entries_fts')
        db.commit()
    return rebuild


def init_db():
    rebuild=migrate_protocol_schema(get_db())
    get_db().executescript(SCHEMA)
    db = get_db()
    if 'case_id' not in {row['name'] for row in db.execute('PRAGMA table_info(tasks)')}:
        db.execute('ALTER TABLE tasks ADD COLUMN case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL')
    db.execute('CREATE INDEX IF NOT EXISTS task_case ON tasks(case_id)')
    if 'case_id' not in {row['name'] for row in db.execute('PRAGMA table_info(entry_resource_links)')}:
        statement = SCHEMA[SCHEMA.index('CREATE TABLE IF NOT EXISTS entry_resource_links ('):SCHEMA.index('CREATE INDEX IF NOT EXISTS entry_resource_links_entry')]
        db.execute(statement.replace('IF NOT EXISTS entry_resource_links (','entry_resource_links_new ('))
        columns = ','.join(row['name'] for row in db.execute('PRAGMA table_info(entry_resource_links)'))
        db.execute(f'INSERT INTO entry_resource_links_new ({columns}) SELECT {columns} FROM entry_resource_links')
        db.execute('DROP TABLE entry_resource_links')
        db.execute('ALTER TABLE entry_resource_links_new RENAME TO entry_resource_links')
        db.execute('CREATE INDEX entry_resource_links_entry ON entry_resource_links(entry_id)')

    if get_db().execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='drawing_links'").fetchone():
        # All sheets of an entry share its references now. Unique constraints
        # merge duplicate targets. Copy and removal are one transaction.
        get_db().execute('''INSERT OR IGNORE INTO entry_resource_links
            (owner_entry_id,entry_id,person_id,project_id,task_id,document_id,tag)
            SELECT d.entry_id,l.entry_id,l.person_id,l.project_id,l.task_id,l.document_id,l.tag
            FROM drawing_links l JOIN drawings d ON d.id=l.drawing_id
            WHERE l.entry_id IS NULL OR l.entry_id<>d.entry_id''')
        get_db().execute('DROP TABLE drawing_links')

    if rebuild:
        get_db().execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
    if 'phone' not in {column['name'] for column in get_db().execute('PRAGMA table_info(people)')}:
        get_db().execute("ALTER TABLE people ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
    if 'institution' not in {column['name'] for column in get_db().execute('PRAGMA table_info(people)')}:
        get_db().execute("ALTER TABLE people ADD COLUMN institution TEXT NOT NULL DEFAULT ''")
    if 'parent_id' not in {column['name'] for column in get_db().execute('PRAGMA table_info(tasks)')}:
        get_db().execute('ALTER TABLE tasks ADD COLUMN parent_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL')
    get_db().execute('CREATE INDEX IF NOT EXISTS task_parent ON tasks(parent_id)')
    retire_collections(db)
    from .participants import migrate_participants
    migrate_participants()
    from .participants import backfill_mail_participants
    backfill_mail_participants()
    if not setting('own_suggestions_removed'):
        from .participants import drop_own_suggestions
        drop_own_suggestions()
        set_setting('own_suggestions_removed', True)
    get_db().commit()


def retire_collections(db):
    """Sammlungen sind entfallen: Verweise bleiben als Ressourcenverknüpfung bestehen,
    selbst geschriebene Hinweise wandern in den Text der Notiz, dann gehen die Tabellen."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_items'").fetchone():
        return
    gesammelt = {}
    for row in db.execute("""SELECT collection_id, source_label, note FROM collection_items
        WHERE note<>'' ORDER BY id"""):
        zeile = ('**'+row['source_label']+'**  \n'+row['note']) if row['source_label'] else row['note']
        gesammelt.setdefault(row['collection_id'], []).append(zeile)
    for entry_id, zeilen in gesammelt.items():
        alt = db.execute('SELECT body FROM entries WHERE id=?', (entry_id,)).fetchone()
        if alt is None:
            continue
        text = (alt['body']+'\n\n' if alt['body'].strip() else '')+'## Gesammelte Hinweise\n\n'+'\n\n'.join(zeilen)
        db.execute('UPDATE entries SET body=? WHERE id=?', (text, entry_id))
    for table in ('collection_requests', 'collection_items', 'collections'):
        db.execute('DROP TABLE IF EXISTS '+table)


def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def rows(sql, params=()):
    return [dict(r) for r in get_db().execute(sql, params).fetchall()]


def one(sql, params=()):
    row = get_db().execute(sql, params).fetchone()
    return dict(row) if row else None


def setting(key, default=None):
    r = one('SELECT value FROM settings WHERE key=?', (key,))
    return json.loads(r['value']) if r else default


def set_setting(key, value):
    get_db().execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))


def cipher():
    return Fernet(current_app.config['DATA_KEY'])


def atomic_write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.' + os.urandom(8).hex() + '.tmp')
    try:
        with open(temp, 'xb') as f:
            os.chmod(temp, 0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
