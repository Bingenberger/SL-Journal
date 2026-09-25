import io
import os
import json
import re
import tarfile
import tempfile
from datetime import date, timedelta
from pathlib import Path

import yaml
from cryptography.fernet import Fernet
from flask import current_app
from .db import atomic_write, connect, get_db, one, rows, set_setting, setting
from .domain import TYPES, now, save_attachment, save_entry, save_task, school_year


def backup(destination=None,keep_days=30):
    instance=Path(current_app.instance_path)
    key_file=instance/'backup.key'
    if not key_file.exists():
        raise ValueError('Backupschlüssel fehlt. Zuerst „python manage.py init“ ausführen.')
    destination=Path(destination or os.environ.get('JOURNAL_BACKUP_DIR') or instance/'backups')
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    db=get_db()
    db.commit()
    db.execute('BEGIN IMMEDIATE')
    try:
        with tempfile.TemporaryDirectory(dir=instance) as temp:
            snapshot=Path(temp)/'journal.db'
            reader=connect(instance/'journal.db',current_app.config['DATA_KEY'])
            target=connect(snapshot,current_app.config['DATA_KEY'])
            try: reader.backup(target)
            finally: target.close(); reader.close()
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode='w:gz') as archive:
                archive.add(snapshot,arcname='journal.db')
                secret=current_app.config['DATA_KEY']
                item=tarfile.TarInfo('master.key'); item.size=len(secret); item.mode=0o600
                archive.addfile(item,io.BytesIO(secret))
                for item in rows('SELECT path FROM attachments'):
                    file=instance/'attachments'/item['path']
                    archive.add(file,arcname='attachments/'+item['path'])
            encrypted=Fernet(key_file.read_bytes().strip()).encrypt(buf.getvalue())
    finally:
        db.rollback()
    output=destination/f'journal-{now().strftime("%Y%m%d-%H%M%S-%f")}.backup'
    atomic_write(output,encrypted)
    cutoff=now().timestamp()-keep_days*86400
    for file in destination.glob('journal-*.backup'):
        if file.stat().st_mtime < cutoff: file.unlink()
    set_setting('backup_status',now().strftime('%d.%m.%Y %H:%M'));db.commit()
    return output


def restore(backup_path,key_path,destination):
    destination=Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Wiederherstellung nur in ein neues oder leeres Verzeichnis möglich.')
    key=Path(key_path).read_bytes().strip()
    payload=Fernet(key).decrypt(Path(backup_path).read_bytes())
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
        members=archive.getmembers()
        names={item.name for item in members}
        if not {'journal.db','master.key'} <= names: raise ValueError('Unvollständige Sicherung.')
        for item in members:
            if not item.isfile() or not re.fullmatch(r'(journal\.db|master\.key|attachments/[a-f0-9]{32}\.enc)',item.name):
                raise ValueError('Ungültiger Sicherungsinhalt.')
        destination.mkdir(parents=True,exist_ok=True,mode=0o700)
        for item in members:
            path=destination/item.name
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            atomic_write(path,archive.extractfile(item).read())
    atomic_write(destination/'backup.key',key)
    db=connect(destination/'journal.db',(destination/'master.key').read_bytes())
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Die wiederhergestellte Datenbank ist beschädigt.')
        if db.execute('PRAGMA cipher_integrity_check').fetchall(): raise ValueError('Die Datenbankverschlüsselung konnte nicht validiert werden.')
        # Restores invalidate every previously issued session.
        import secrets
        db.execute('UPDATE account SET session_version=?',(secrets.token_hex(16),)); db.commit()
    finally: db.close()
    return destination


def purge(apply=False):
    expired=[]
    for kind,days in setting('retention',{}).items():
        if kind not in TYPES or not isinstance(days,int) or days<1: continue
        cutoff=(now().date()-timedelta(days=days)).isoformat()
        expired.extend(rows('SELECT id,title,type,date FROM entries WHERE type=? AND date<=?',(kind,cutoff)))
    if apply:
        files=[]
        for entry in expired:
            files.extend(rows('SELECT path FROM attachments WHERE entry_id=?',(entry['id'],)))
            get_db().execute('DELETE FROM entries WHERE id=?',(entry['id'],))
        from .participants import prune_suggestions
        prune_suggestions()
        from .project_suggestions import prune
        prune()
        get_db().commit()
        for file in files: (Path(current_app.instance_path)/'attachments'/file['path']).unlink(missing_ok=True)
        # Remove files left behind by an interrupted import, only after a grace period.
        known={a['path'] for a in rows('SELECT path FROM attachments')}
        for path in (Path(current_app.instance_path)/'attachments').glob('*.enc'):
            if path.name not in known and path.stat().st_mtime<now().timestamp()-86400: path.unlink()
    return expired


def as_list(value):
    if isinstance(value,list): return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip().lstrip('#') for v in re.split(r'[,\s]+',str(value or '')) if v.strip()]


def import_obsidian(vault,apply=False):
    import hashlib
    import mimetypes
    vault=Path(vault).resolve()
    if not vault.is_dir(): raise ValueError('Der Vault-Ordner existiert nicht.')
    report={'entries':0,'tasks':0,'attachments':0,'skipped':0,'errors':[]}
    for file in sorted(vault.rglob('*.md')):
        if file.is_symlink() or any(p.startswith('.') for p in file.relative_to(vault).parts): continue
        source='obsidian:'+hashlib.sha256(str(file.relative_to(vault)).encode()).hexdigest()
        if one('SELECT source_key FROM imports WHERE source_key=?',(source,)):
            report['skipped']+=1;continue
        try:
            text=file.read_text(encoding='utf-8-sig')
            meta={}
            match=re.match(r'^---\s*\n(.*?)\n---\s*\n',text,re.S)
            if match:
                meta=yaml.safe_load(match[1]) or {}
                if not isinstance(meta,dict): raise ValueError('Frontmatter ist kein Objekt.')
                text=text[match.end():]
            filename_date=re.search(r'\d{4}-\d{2}-\d{2}',file.stem)
            raw_day=str(meta.get('date') or meta.get('datum') or (filename_date[0] if filename_date else date.fromtimestamp(file.stat().st_mtime)))[:10]
            day=date.fromisoformat(raw_day)
            tags=as_list(meta.get('tags'))
            tags+=re.findall(r'(?<!\w)#([\w/-]+)',text)
            title=str(meta.get('title') or meta.get('titel') or file.stem)
            task_data=[]
            for match in re.finditer(r'^\s*[-*] \[ \]\s+(.+)$',text,re.M):
                task_text=match[1]
                due_match=re.search(r'(?:📅\s*|\[due::\s*)(\d{4}-\d{2}-\d{2})\]?',task_text)
                due=date.fromisoformat(due_match[1]).isoformat() if due_match else None
                if due_match: task_text=task_text[:due_match.start()]+task_text[due_match.end():]
                task_data.append(dict(text=task_text.strip(),due=due))
            linked=[]
            links=re.findall(r'!?\[\[([^\]|]+)(?:\|[^\]]+)?\]\]',text)+re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text)
            for link in dict.fromkeys(links):
                from urllib.parse import unquote
                link=unquote(link).split('#')[0]
                candidate=(file.parent/link).resolve()
                if not candidate.exists(): candidate=(vault/link).resolve()
                if candidate.suffix.lower()=='.md' or not candidate.is_file() or not candidate.is_relative_to(vault): continue
                if candidate.stat().st_size>25*1024*1024: raise ValueError('Anhang größer als 25 MB.')
                linked.append(candidate)
            if apply:
                db=get_db(); db.execute('BEGIN IMMEDIATE')
                if one('SELECT source_key FROM imports WHERE source_key=?',(source,)):
                    db.rollback();report['skipped']+=1;continue
                project_ids=[]
                project_names=meta.get('projects',meta.get('project',[]))
                if isinstance(project_names,str): project_names=[project_names]
                for name in project_names or []:
                    name=str(name).strip()
                    if not name: continue
                    p=one('SELECT id FROM projects WHERE name=? AND school_year=?',(name,school_year(day)))
                    project_ids.append(p['id'] if p else db.execute('INSERT INTO projects(name,school_year) VALUES(?,?)',(name,school_year(day))).lastrowid)
                kind=str(meta.get('type','journal' if filename_date else 'note'))
                if kind not in TYPES: kind='note'
                eid=save_entry(dict(date=day.isoformat(),type=kind,title=title,body=text,tags=', '.join(tags),source_key=source),project_ids)
                for task in task_data: save_task(dict(task,entry_id=eid))
                for attached in linked: save_attachment(eid,attached.name,attached.read_bytes(),mimetypes.guess_type(attached.name)[0])
                db.execute('INSERT INTO imports(source_key) VALUES(?)',(source,));db.commit()
            report['entries']+=1;report['tasks']+=len(task_data);report['attachments']+=len(linked)
        except Exception as exc:
            get_db().rollback()
            report['errors'].append(f'{file.relative_to(vault)}: {type(exc).__name__}: {exc}')
    return report
