"""Unconfirmed project names shared by entries and tasks."""
import json
import re
from .db import get_db, one, rows
from .participants import normalized


def items(owner, owner_id):
    if owner == 'entry':
        projects = rows('SELECT p.* FROM projects p JOIN entry_projects ep ON ep.project_id=p.id WHERE ep.entry_id=?', (owner_id,))
    else:
        projects = rows('SELECT p.* FROM projects p JOIN tasks t ON t.project_id=p.id WHERE t.id=?', (owner_id,))
    result = [dict(kind='project', id=p['id'], label=p['name'], detail=p['school_year']) for p in projects]
    for p in rows(f'SELECT s.* FROM project_suggestions s JOIN {owner}_project_suggestions r ON r.suggestion_id=s.id WHERE r.{owner}_id=? AND s.project_id IS NULL', (owner_id,)):
        result.append(dict(kind='new_project', label=p['name'], school_year=p['school_year'], detail=p['school_year']+' · Projektvorschlag'))
    return result


def parse(data, fallback=(), single=False):
    from .domain import school_year
    raw = data.get('project_items')
    if raw is None:
        values = [dict(kind='project', id=pid) for pid in fallback if pid]
    else:
        try:
            values = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            raise ValueError('Die Projektauswahl ist ungültig.')
    if not isinstance(values, list) or len(values) > (1 if single else 200):
        raise ValueError('Die Projektauswahl ist ungültig.')
    selected = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError('Die Projektauswahl ist ungültig.')
        if item.get('kind') == 'project':
            pid = item.get('id')
            if not isinstance(pid, (str, int)) or not one('SELECT id FROM projects WHERE id=?', (pid,)):
                raise ValueError('Das gewählte Projekt existiert nicht.')
            selected.append(('project', int(pid)))
        elif item.get('kind') == 'new_project':
            label = item.get('label')
            year = item.get('school_year') or school_year()
            if not isinstance(label, str) or not label.strip() or len(label) > 500 or not isinstance(year, str) or not re.fullmatch(r'\d{4}/\d{2}', year):
                raise ValueError('Bitte einen gültigen Projektnamen und ein Schuljahr angeben.')
            label = ' '.join(label.split())
            matches = [p for p in rows('SELECT id,name FROM projects WHERE school_year=?', (year,)) if normalized(p['name']) == normalized(label)]
            if len(matches) == 1:
                selected.append(('project', matches[0]['id']))
                continue
            db = get_db()
            db.execute('INSERT OR IGNORE INTO project_suggestions(name,normalized,school_year) VALUES(?,?,?)', (label, normalized(label), year))
            proposal = one('SELECT * FROM project_suggestions WHERE normalized=? AND school_year=?', (normalized(label), year))
            selected.append(('project', proposal['project_id']) if proposal['project_id'] else ('suggestion', proposal['id']))
        else:
            raise ValueError('Die Projektauswahl ist ungültig.')
    return list(dict.fromkeys(selected))


def sync(owner, owner_id, selected, append=False):
    db = get_db()
    if not append:
        db.execute(f'DELETE FROM {owner}_project_suggestions WHERE {owner}_id=?', (owner_id,))
        if owner == 'entry':
            db.execute('DELETE FROM entry_projects WHERE entry_id=?', (owner_id,))
        else:
            db.execute('UPDATE tasks SET project_id=NULL WHERE id=?', (owner_id,))
    for kind, value in selected:
        if kind == 'project':
            if owner == 'entry':
                db.execute('INSERT OR IGNORE INTO entry_projects VALUES(?,?)', (owner_id,value))
            else:
                db.execute('UPDATE tasks SET project_id=? WHERE id=?', (value,owner_id))
        else:
            db.execute(f'INSERT OR IGNORE INTO {owner}_project_suggestions VALUES(?,?)', (owner_id,value))
    prune()


def prune():
    get_db().execute("""DELETE FROM project_suggestions WHERE project_id IS NULL
        AND NOT EXISTS(SELECT 1 FROM entry_project_suggestions WHERE suggestion_id=project_suggestions.id)
        AND NOT EXISTS(SELECT 1 FROM task_project_suggestions WHERE suggestion_id=project_suggestions.id)""")


def suggestions(status='pending'):
    result = rows("""SELECT s.*,
        (SELECT count(*) FROM entry_project_suggestions WHERE suggestion_id=s.id) entry_count,
        (SELECT count(*) FROM task_project_suggestions WHERE suggestion_id=s.id) task_count
        FROM project_suggestions s WHERE s.status=? AND s.project_id IS NULL
        AND (EXISTS(SELECT 1 FROM entry_project_suggestions WHERE suggestion_id=s.id)
          OR EXISTS(SELECT 1 FROM task_project_suggestions WHERE suggestion_id=s.id)) ORDER BY s.name""", (status,))
    for s in result:
        s['entries'] = rows('SELECT e.id,e.title FROM entries e JOIN entry_project_suggestions r ON r.entry_id=e.id WHERE r.suggestion_id=? ORDER BY e.date DESC LIMIT 3', (s['id'],))
    return result


def resolve(sid, pid):
    db = get_db()
    proposal = one('SELECT * FROM project_suggestions WHERE id=?', (sid,))
    if not proposal or not one('SELECT id FROM projects WHERE id=?', (pid,)):
        raise ValueError('Vorschlag oder Projekt existiert nicht.')
    if proposal['project_id']:
        raise ValueError('Dieser Vorschlag wurde bereits übernommen.')
    db.execute('INSERT OR IGNORE INTO entry_projects SELECT entry_id,? FROM entry_project_suggestions WHERE suggestion_id=?', (pid,sid))
    db.execute('UPDATE tasks SET project_id=? WHERE id IN (SELECT task_id FROM task_project_suggestions WHERE suggestion_id=?)', (pid,sid))
    db.execute('DELETE FROM task_project_suggestions WHERE suggestion_id=?', (sid,))
    db.execute('DELETE FROM entry_project_suggestions WHERE suggestion_id=?', (sid,))
    db.execute("UPDATE project_suggestions SET status='resolved',project_id=? WHERE id=?", (pid,sid))


def reconcile(pid):
    project = one('SELECT * FROM projects WHERE id=?', (pid,))
    matches = [p for p in rows('SELECT id,name FROM projects WHERE school_year=?', (project['school_year'],)) if normalized(p['name']) == normalized(project['name'])]
    if len(matches) != 1:
        return
    for proposal in rows('SELECT id FROM project_suggestions WHERE normalized=? AND school_year=? AND project_id IS NULL', (normalized(project['name']),project['school_year'])):
        resolve(proposal['id'],pid)
