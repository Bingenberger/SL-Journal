"""Vorgangsvorschläge und ihre zugehörigen Einträge und Aufgaben."""
import json
from .db import get_db, one, rows
from .participants import normalized


def items(owner, oid):
    query = ('SELECT c.* FROM cases c JOIN entry_cases r ON r.case_id=c.id WHERE r.entry_id=?'
             if owner == 'entry' else 'SELECT c.* FROM cases c JOIN tasks r ON r.case_id=c.id WHERE r.id=?')
    result = [dict(kind='case', id=c['id'], label=c['title']) for c in rows(query, (oid,))]
    result += [dict(kind='new_case', label=s['name'], detail='Vorgangsvorschlag') for s in rows(
        f'SELECT s.* FROM case_suggestions s JOIN {owner}_case_suggestions r ON r.suggestion_id=s.id WHERE r.{owner}_id=? AND s.case_id IS NULL', (oid,))]
    return result


def parse(data, fallback=(), single=False):
    try:
        raw = data.get('case_items')
        values = json.loads(raw) if isinstance(raw, str) else raw
        if raw is None:
            values = [dict(kind='case', id=cid) for cid in fallback if cid]
        if not isinstance(values, list) or len(values) > (1 if single else 100):
            raise ValueError()
        selected = []
        for item in values:
            if not isinstance(item, dict):
                raise ValueError()
            if item.get('kind') == 'case':
                cid = item.get('id')
                if isinstance(cid, bool) or not isinstance(cid, (str, int)) or not one('SELECT id FROM cases WHERE id=?', (cid,)):
                    raise ValueError()
                selected.append(('case', int(cid)))
            elif item.get('kind') == 'new_case':
                label = item.get('label')
                if not isinstance(label, str) or not label.strip() or len(label)>500:
                    raise ValueError()
                label = ' '.join(label.split())
                matches = [c for c in rows('SELECT id,title FROM cases') if normalized(c['title']) == normalized(label)]
                if len(matches)==1:
                    selected.append(('case', matches[0]['id']))
                    continue
                get_db().execute('INSERT OR IGNORE INTO case_suggestions(name,normalized) VALUES(?,?)', (label, normalized(label)))
                proposal = one('SELECT * FROM case_suggestions WHERE normalized=?', (normalized(label),))
                selected.append(('case', proposal['case_id']) if proposal['case_id'] else ('suggestion', proposal['id']))
            else:
                raise ValueError()
        return list(dict.fromkeys(selected))
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Bitte einen vorhandenen Vorgang oder einen neuen Namen mit höchstens 500 Zeichen eingeben.')


def sync(owner, oid, selected, append=False):
    db=get_db()
    if not append:
        db.execute(f'DELETE FROM {owner}_case_suggestions WHERE {owner}_id=?', (oid,))
        if owner=='entry':
            db.execute('DELETE FROM entry_cases WHERE entry_id=?', (oid,))
        else:
            db.execute('UPDATE tasks SET case_id=NULL WHERE id=?', (oid,))
    for kind, value in selected:
        if kind=='case':
            if owner=='entry':
                db.execute('INSERT OR IGNORE INTO entry_cases VALUES(?,?)', (oid,value))
            else:
                db.execute('UPDATE tasks SET case_id=? WHERE id=?', (value,oid))
        else:
            db.execute(f'INSERT OR IGNORE INTO {owner}_case_suggestions VALUES(?,?)', (oid,value))


def suggestions(status='pending'):
    return rows("""SELECT s.*,
        (SELECT count(*) FROM entry_case_suggestions WHERE suggestion_id=s.id) entry_count,
        (SELECT count(*) FROM task_case_suggestions WHERE suggestion_id=s.id) task_count
        FROM case_suggestions s WHERE s.status=? AND s.case_id IS NULL
        AND (EXISTS(SELECT 1 FROM entry_case_suggestions WHERE suggestion_id=s.id)
        OR EXISTS(SELECT 1 FROM task_case_suggestions WHERE suggestion_id=s.id)) ORDER BY s.name""", (status,))


def resolve(sid, cid):
    proposal=one('SELECT * FROM case_suggestions WHERE id=?', (sid,))
    if not proposal or proposal['case_id'] or not one('SELECT id FROM cases WHERE id=?', (cid,)):
        raise ValueError('Vorschlag oder Vorgang existiert nicht mehr oder wurde bereits übernommen.')
    db=get_db()
    db.execute('INSERT OR IGNORE INTO entry_cases SELECT entry_id,? FROM entry_case_suggestions WHERE suggestion_id=?', (cid,sid))
    db.execute('UPDATE tasks SET case_id=? WHERE id IN (SELECT task_id FROM task_case_suggestions WHERE suggestion_id=?)', (cid,sid))
    for owner in ('entry','task'):
        db.execute(f'DELETE FROM {owner}_case_suggestions WHERE suggestion_id=?', (sid,))
    db.execute("UPDATE case_suggestions SET status='resolved',case_id=? WHERE id=?", (cid,sid))


def reconcile(cid):
    case=one('SELECT title FROM cases WHERE id=?', (cid,))
    matches=[c for c in rows('SELECT id,title FROM cases') if normalized(c['title'])==normalized(case['title'])]
    if len(matches)==1:
        for proposal in rows('SELECT id FROM case_suggestions WHERE normalized=? AND case_id IS NULL', (normalized(case['title']),)):
            resolve(proposal['id'],cid)
