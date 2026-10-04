"""Durable, encrypted attachment text index; extraction runs outside requests."""
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from flask import current_app
from .db import cipher, get_db, one, rows, setting, set_setting
from .document_text import IMAGES, OFFICE, extract_document

TEXT = {'.txt', '.csv', '.md', '.markdown', '.log'}
MAX_TEXT = 2_000_000
SCHEMA = '''
CREATE TABLE IF NOT EXISTS attachment_index (
 attachment_id INTEGER PRIMARY KEY REFERENCES attachments(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'pending', detail TEXT NOT NULL DEFAULT '',
 claimed REAL NOT NULL DEFAULT 0, token TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS attachment_text (
 id INTEGER PRIMARY KEY, attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
 page INTEGER NOT NULL, name TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS attachment_text_owner ON attachment_text(attachment_id);
CREATE VIRTUAL TABLE IF NOT EXISTS attachments_fts USING fts5(name,body,
 content='attachment_text',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS attachment_text_insert AFTER INSERT ON attachment_text BEGIN
 INSERT INTO attachments_fts(rowid,name,body) VALUES(new.id,new.name,new.body); END;
CREATE TRIGGER IF NOT EXISTS attachment_text_delete AFTER DELETE ON attachment_text BEGIN
 INSERT INTO attachments_fts(attachments_fts,rowid,name,body) VALUES('delete',old.id,old.name,old.body); END;
CREATE TRIGGER IF NOT EXISTS attachment_queue AFTER INSERT ON attachments BEGIN
 INSERT INTO attachment_index(attachment_id) VALUES(new.id); END;
INSERT OR IGNORE INTO attachment_index(attachment_id) SELECT id FROM attachments;
'''


def init():
    get_db().executescript(SCHEMA)
    if setting('attachment_extractor_version',0)<2:
        get_db().execute("UPDATE attachment_index SET status='pending' WHERE status<>'processing'")
        set_setting('attachment_extractor_version',2)
        get_db().commit()


def extract(item, content):
    suffix = Path(item['name']).suffix.lower()
    if suffix == '.pdf' or item['mime'] == 'application/pdf':
        return extract_document('.pdf',content)
    elif suffix in (OFFICE - TEXT) | IMAGES:
        return extract_document(suffix,content)
    elif suffix in TEXT or item['mime'] in ('text/plain', 'text/csv', 'text/markdown'):
        if content.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = content.decode('utf-16')
        else:
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('cp1252')
        if '\x00' in text:
            raise ValueError('Die Datei enthält Binärdaten statt lesbarem Text.')
    else:
        return [], 'unsupported', 'Für dieses Dateiformat ist keine Textextraktion eingerichtet.'
    if len(text) > MAX_TEXT:
        raise ValueError('Textumfang überschreitet die Grenze von 2 Millionen Zeichen.')
    # Reiner Text kennt keine Seiten; PDF, Office und Bilder sind oben schon
    # abgezweigt und bringen ihre Seitenaufteilung selbst mit.
    text = text.strip()
    return ([(1, text)] if text else []), 'ready' if text else 'empty', '' if text else 'Die Datei enthält keinen Text.'


def process_pending(retry=False):
    """Atomically claim jobs; expired claims recover after an interrupted process."""
    db = get_db()
    if retry:
        db.execute("UPDATE attachment_index SET status='pending' WHERE status IN ('error','empty','unsupported','partial') OR (status='ready' AND detail<>'')")
        db.commit()
    count = 0
    while True:
        db.execute('BEGIN IMMEDIATE')
        item = one("SELECT a.* FROM attachments a JOIN attachment_index i ON i.attachment_id=a.id "
                   "WHERE i.status='pending' OR (i.status='processing' AND i.claimed<?) ORDER BY a.id LIMIT 1", (time.time()-600,))
        if not item:
            db.commit()
            return count
        token = uuid.uuid4().hex
        db.execute("UPDATE attachment_index SET status='processing',claimed=?,token=? WHERE attachment_id=?", (time.time(),token,item['id']))
        db.commit()
        try:
            suffix = Path(item['name']).suffix.lower()
            if suffix not in TEXT | OFFICE | IMAGES | {'.pdf'} and item['mime'] not in ('application/pdf','text/plain','text/csv','text/markdown'):
                pages,status,detail = [],'unsupported','Für dieses Dateiformat ist keine Textextraktion eingerichtet.'
            else:
                content = cipher().decrypt((Path(current_app.instance_path)/'attachments'/item['path']).read_bytes())
                pages,status,detail = extract(item,content)
        except (ValueError,RuntimeError) as exc:
            pages,status,detail = [],'error',str(exc)
        except subprocess.TimeoutExpired:
            pages,status,detail = [],'error','Die Textextraktion hat das Zeitlimit überschritten.'
        except Exception:
            pages,status,detail = [],'error','Datei konnte nicht gelesen oder verarbeitet werden.'
        db.execute('BEGIN IMMEDIATE')
        # Deletion or a newer claimant wins, even while extraction was running.
        if one('SELECT 1 FROM attachment_index WHERE attachment_id=? AND token=?', (item['id'],token)):
            db.execute('DELETE FROM attachment_text WHERE attachment_id=?',(item['id'],))
            db.executemany('INSERT INTO attachment_text(attachment_id,page,name,body) VALUES(?,?,?,?)',
                           [(item['id'],page,item['name'],body) for page,body in pages])
            db.execute('UPDATE attachment_index SET status=?,detail=? WHERE attachment_id=?',(status,detail,item['id']))
        db.commit()
        count += 1


RUHE = 5


def kick(app, sofort=False):
    """Den Hintergrundlauf anstoßen.

    Nach einer schreibenden Anfrage sofort, beim reinen Lesen höchstens alle
    fünf Sekunden: Ein Seitenaufruf zieht ein Dutzend Dateien nach sich, und
    für jede einen Faden zu starten, der nichts findet, ist verschenkt.
    """
    if app.testing:
        return
    if not sofort and time.monotonic() - app.extensions.get('attachment_search_seen', -RUHE) < RUHE:
        return
    app.extensions['attachment_search_seen'] = time.monotonic()
    lock = app.extensions['attachment_search_lock']
    if not lock.acquire(blocking=False):
        return
    def work():
        try:
            with app.app_context():
                process_pending()
        except Exception:
            app.logger.error('Anhangsindexierung unterbrochen; wird beim nächsten Aufruf fortgesetzt.')
        finally:
            lock.release()
    threading.Thread(target=work, name='attachment-search', daemon=True).start()


def matches(query):
    fts = ' AND '.join('"'+word.replace('"','""')+'"*' for word in query.split())
    if not fts:
        return []
    return rows("SELECT a.id,a.entry_id,a.name,a.mime,e.title,t.page,"
                "snippet(attachments_fts,1,'','',' … ',28) excerpt "
                "FROM attachments_fts JOIN attachment_text t ON t.id=attachments_fts.rowid "
                "JOIN attachments a ON a.id=t.attachment_id JOIN entries e ON e.id=a.entry_id "
                "WHERE attachments_fts MATCH ? ORDER BY rank,a.id,t.page", (fts,))


def summary():
    return {row['status']:row['n'] for row in rows('SELECT status,count(*) n FROM attachment_index GROUP BY status')}
