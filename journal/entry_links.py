"""Validated references between entries and existing journal resources."""
import re
from urllib.parse import parse_qs, urlsplit
from flask import current_app, url_for
from .db import get_db, one, rows

TARGETS = {
    'case_view': ('case_id', 'cases', 'cid', 'title', 'Vorgang'),
    'entry_view': ('entry_id', 'entries', 'eid', 'title', None),
    'person_view': ('person_id', 'people', 'pid', 'name', 'Kontakt'),
    'project_view': ('project_id', 'projects', 'pid', 'name', 'Projekt'),
    'document_view': ('document_id', 'documents', 'did', 'name', 'Nextcloud-Dokument'),
}


def resolve(url):
    from werkzeug.exceptions import HTTPException
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError('Bitte eine vorhandene Ressource auswählen.')
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or url.startswith('//'):
        raise ValueError('Bitte eine Ressource aus diesem Journal auswählen.')
    try:
        endpoint, params = current_app.url_map.bind('').match(parsed.path, method='GET')
    except HTTPException:
        raise ValueError('Die ausgewählte Ressource existiert nicht.')
    if endpoint in TARGETS:
        column, table, param, _, _ = TARGETS[endpoint]
        value = params[param]
        if one(f'SELECT id FROM {table} WHERE id=?', (value,)):
            return column, value
    elif endpoint == 'task_list':
        match = re.fullmatch(r'task-([1-9][0-9]*)', parsed.fragment)
        if match and one('SELECT id FROM tasks WHERE id=?', (int(match[1]),)):
            return 'task_id', int(match[1])
    elif endpoint == 'entry_list':
        tag = parse_qs(parsed.query).get('tag', [''])[0].strip()
        if tag and one('SELECT id FROM entries WHERE has_tag(tags,?) LIMIT 1', (tag,)):
            # Casefold also deduplicates non-ASCII tag names.
            return 'tag', tag.casefold()
    raise ValueError('Die ausgewählte Ressource existiert nicht mehr. Bitte erneut suchen.')


def add(eid, url):
    if not one('SELECT id FROM entries WHERE id=?', (eid,)):
        raise ValueError('Der Eintrag existiert nicht mehr.')
    column, value = resolve(url)
    if column == 'entry_id' and value == eid:
        raise ValueError('Ein Eintrag kann nicht mit sich selbst verknüpft werden.')
    get_db().execute(f'INSERT OR IGNORE INTO entry_resource_links(owner_entry_id,{column}) VALUES(?,?)', (eid, value))


def listed(eid):
    from .domain import TYPES
    result = []
    for link in rows('SELECT * FROM entry_resource_links WHERE owner_entry_id=? ORDER BY id', (eid,)):
        for endpoint, (column, table, param, label, kind) in TARGETS.items():
            if link[column] is not None:
                item = one(f'SELECT * FROM {table} WHERE id=?', (link[column],))
                if item:
                    result.append(dict(id=link['id'],label=item[label],kind=kind or TYPES[item['type']],
                                       url=url_for(endpoint, **{param:link[column]})))
                break
        else:
            if link['task_id'] is not None:
                task = one('SELECT text FROM tasks WHERE id=?', (link['task_id'],))
                if task:
                    result.append(dict(id=link['id'],label=task['text'],kind='Aufgabe',
                                       url=url_for('task_list',filter='all',focus_task=link['task_id'],_anchor='task-'+str(link['task_id']))))
            elif link['tag'] and one('SELECT id FROM entries WHERE has_tag(tags,?) LIMIT 1', (link['tag'],)):
                result.append(dict(id=link['id'],label='#'+link['tag'],kind='Tag',
                                   url=url_for('entry_list',tag=link['tag'])))
    return result


def incoming(eid):
    return rows("""SELECT e.id,e.title,e.date,
        (SELECT COUNT(*) FROM drawings d WHERE d.entry_id=e.id) drawing_count,
        (SELECT MIN(id) FROM drawings d WHERE d.entry_id=e.id) preview_id
        FROM entry_resource_links l JOIN entries e ON e.id=l.owner_entry_id
        WHERE l.entry_id=? ORDER BY e.date DESC,e.id DESC""", (eid,))


def incoming_case(cid):
    return rows('''SELECT e.id,e.title,e.date FROM entry_resource_links l
        JOIN entries e ON e.id=l.owner_entry_id WHERE l.case_id=? ORDER BY e.date DESC,e.id DESC''',(cid,))
