"""One participant input for both known contacts and unconfirmed names."""
import json
import re
import unicodedata
from email.utils import getaddresses, parseaddr

from .db import get_db, one, rows, set_setting, setting


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).split()).casefold()


def contact_match(label, people=None):
    people = people if people is not None else rows('SELECT * FROM people')
    key = normalized(label)
    email = parseaddr(label)[1].lower() if '@' in label else ''
    matches = []
    for person in people:
        emails = {address.lower() for _, address in getaddresses([person['emails']]) if '@' in address}
        if normalized(person['name']) == key or (email and email in emails):
            matches.append(person)
    # Names are not unique identifiers. Ambiguous names require an explicit choice.
    return matches[0] if len(matches) == 1 else None


def participant_items(entry_id):
    result = [
        dict(kind='person', id=p['id'], label=p['name'], detail=' · '.join(v for v in [p['role'],p['institution']] if v))
        for p in rows('SELECT p.* FROM people p JOIN entry_people ep ON ep.person_id=p.id WHERE ep.entry_id=? ORDER BY p.name', (entry_id,))
    ]
    result += [
        dict(kind='new', label=s['name'])
        for s in rows('SELECT s.name FROM contact_suggestions s JOIN entry_suggestions es ON es.suggestion_id=s.id WHERE es.entry_id=? AND s.person_id IS NULL ORDER BY s.name', (entry_id,))
    ]
    return result


def refresh_summary(entry_id):
    names = [item['label'] for item in participant_items(entry_id)]
    get_db().execute('UPDATE entries SET participants=? WHERE id=?', ('; '.join(names), entry_id))


def parse_legacy(text, people):
    labels = [s.strip() for s in re.split(r'[;\n]+', text or '') if s.strip()]
    result = []
    for label in labels:
        # Preserve free-form legacy text unless comma-separated parts are known contacts.
        parts = [s.strip() for s in label.split(',') if s.strip()]
        if not contact_match(label, people) and len(parts)>1 and all(contact_match(p, people) for p in parts):
            result.extend(parts)
        else:
            result.append(label)
    return [dict(kind='new', label=label) for label in result]


def sync_participants(entry_id, data, person_ids=()):
    db = get_db()
    people = rows('SELECT * FROM people ORDER BY id')
    by_id = {p['id']:p for p in people}
    if 'participant_items' in data:
        items = data['participant_items']
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except (ValueError, TypeError):
                raise ValueError('Die Beteiligten konnten nicht gelesen werden. Bitte erneut auswählen.')
        if not isinstance(items, list) or len(items)>200:
            raise ValueError('Bitte höchstens 200 Beteiligte je Eintrag angeben.')
    else:
        items = parse_legacy(data.get('participants', ''), people)
        items += [dict(kind='person', id=pid) for pid in person_ids if pid]

    existing_suggestions = rows('SELECT * FROM contact_suggestions ORDER BY id')
    selected = set()
    unknown = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Ungültige Beteiligtenangabe.')
        if item.get('kind') == 'person':
            try:
                pid = int(item['id'])
            except (ValueError, TypeError, KeyError):
                raise ValueError('Bitte einen gültigen Kontakt auswählen.')
            if pid not in by_id:
                raise ValueError('Der gewählte Kontakt existiert nicht mehr.')
            selected.add(pid)
        elif item.get('kind') == 'new':
            if not isinstance(item.get('label'), str):
                raise ValueError('Bitte einen Namen eingeben.')
            label = ' '.join(item['label'].split())
            if not label:
                continue
            if len(label)>500:
                raise ValueError('Ein Beteiligtenname darf höchstens 500 Zeichen enthalten.')
            match = contact_match(label, people)
            previous = one('SELECT * FROM contact_suggestions WHERE normalized=?', (normalized(label),))
            email = parseaddr(label)[1].lower() if '@' in label else ''
            if not previous and email:
                candidates = [s for s in existing_suggestions if '@' in s['name'] and parseaddr(s['name'])[1].lower() == email]
                resolved_ids = {s['person_id'] for s in candidates if s['person_id'] in by_id}
                if len(resolved_ids) <= 1:
                    previous = next((s for s in candidates if s['person_id'] in by_id), candidates[0] if candidates else None)
            if match:
                selected.add(match['id'])
            elif previous and previous['person_id'] in by_id:
                selected.add(previous['person_id'])
            else:
                label = previous['name'] if previous else label
                # Repeated addresses within the same message also share one proposal.
                duplicate = next((value for value in unknown.values() if email and '@' in value and parseaddr(value)[1].lower() == email), None)
                if not duplicate:
                    unknown.setdefault(normalized(label), label)
        else:
            raise ValueError('Ungültige Beteiligtenangabe.')

    # Validate all references before replacing an entry's relationships.
    db.execute('DELETE FROM entry_people WHERE entry_id=?', (entry_id,))
    db.execute('DELETE FROM entry_suggestions WHERE entry_id=?', (entry_id,))
    for pid in selected:
        db.execute('INSERT INTO entry_people VALUES(?,?)', (entry_id, pid))
    for key, label in unknown.items():
        db.execute('INSERT OR IGNORE INTO contact_suggestions(name,normalized) VALUES(?,?)', (label,key))
        suggestion = one('SELECT id FROM contact_suggestions WHERE normalized=?', (key,))
        db.execute('INSERT INTO entry_suggestions VALUES(?,?)', (entry_id,suggestion['id']))
    refresh_summary(entry_id)
    prune_suggestions()


def suggestions(status='pending'):
    items = rows('''SELECT s.*,count(es.entry_id) entry_count
        FROM contact_suggestions s JOIN entry_suggestions es ON es.suggestion_id=s.id
        WHERE s.status=? AND s.person_id IS NULL GROUP BY s.id ORDER BY s.name''', (status,))
    for item in items:
        item['entries'] = rows('SELECT e.id,e.title,e.date FROM entries e JOIN entry_suggestions es ON es.entry_id=e.id WHERE es.suggestion_id=? ORDER BY e.date DESC,e.id DESC LIMIT 3', (item['id'],))
        name, email = parseaddr(item['name'])
        item['contact_name'] = name or item['name']
        item['email'] = email if '@' in email else ''
    return items


def resolve_suggestion(suggestion_id, person_id):
    db = get_db()
    suggestion = one('SELECT * FROM contact_suggestions WHERE id=?', (suggestion_id,))
    person = one('SELECT * FROM people WHERE id=?', (person_id,))
    if not suggestion or not person:
        raise ValueError('Vorschlag oder Kontakt ist nicht mehr vorhanden.')
    if suggestion['person_id'] and suggestion['person_id'] != person_id:
        raise ValueError('Dieser Vorschlag wurde bereits einem anderen Kontakt zugeordnet.')
    affected = rows('SELECT entry_id FROM entry_suggestions WHERE suggestion_id=?', (suggestion_id,))
    db.execute("UPDATE contact_suggestions SET status='resolved',person_id=? WHERE id=?", (person_id,suggestion_id))
    for item in affected:
        db.execute('INSERT OR IGNORE INTO entry_people VALUES(?,?)', (item['entry_id'],person_id))
        refresh_summary(item['entry_id'])


def reconcile_person(person_id):
    # Also resolve matching suggestions after manually creating a contact.
    people = rows('SELECT * FROM people')
    for suggestion in rows('SELECT * FROM contact_suggestions WHERE person_id IS NULL'):
        match = contact_match(suggestion['name'], people)
        if match and match['id'] == person_id:
            resolve_suggestion(suggestion['id'], person_id)
    for entry in rows('SELECT entry_id FROM entry_people WHERE person_id=?', (person_id,)):
        refresh_summary(entry['entry_id'])


def drop_own_suggestions():
    """Remove unconfirmed proposals for the account's own addresses, including ones
    collected before an address was entered in the settings."""
    own = own_addresses()
    if not own:
        return 0
    removed = 0
    for suggestion in rows('SELECT * FROM contact_suggestions WHERE person_id IS NULL'):
        address = parseaddr(suggestion['name'])[1].lower()
        if address not in own:
            continue
        affected = [row['entry_id'] for row in rows('SELECT entry_id FROM entry_suggestions WHERE suggestion_id=?', (suggestion['id'],))]
        get_db().execute('DELETE FROM contact_suggestions WHERE id=?', (suggestion['id'],))
        for entry_id in affected:
            refresh_summary(entry_id)
        removed += 1
    return removed


def prune_suggestions():
    # No additional retention of names when their last entry has been removed.
    get_db().execute('DELETE FROM contact_suggestions WHERE person_id IS NULL AND NOT EXISTS (SELECT 1 FROM entry_suggestions WHERE suggestion_id=contact_suggestions.id)')


def migrate_participants():
    if setting('participants_migration_v1'):
        return
    for entry in rows('SELECT id,participants FROM entries ORDER BY id'):
        known = [p['person_id'] for p in rows('SELECT person_id FROM entry_people WHERE entry_id=?', (entry['id'],))]
        sync_participants(entry['id'],entry,known)
    set_setting('participants_migration_v1', True)


def institutions():
    labels = {}
    for person in rows("SELECT institution FROM people WHERE institution<>'' ORDER BY id"):
        value = ' '.join(person['institution'].split())
        if value:
            labels.setdefault(normalized(value), value)
    return sorted(labels.values(), key=normalized)


def own_addresses():
    return {value.strip().lower() for value in setting('imap', {}).get('own_addresses', []) if value.strip()}


def mail_participants(*headers, exclude=()):
    """Everyone on the message. Addresses in `exclude` are the account's own; they
    appear on every archived mail, so they only stay when they already belong to a
    saved contact and never become a new proposal."""
    result = []
    seen = set()
    own = {value.strip().lower() for value in exclude if value.strip()}
    people = rows('SELECT * FROM people') if own else []
    for name, email in getaddresses([value or '' for value in headers]):
        email = email.strip().lower()
        if '@' not in email or email in seen:
            continue
        if email in own and not contact_match(email, people):
            continue
        seen.add(email)
        # Preserve readable Unicode display names; quote commas and special characters.
        escaped = ' '.join(name.split()).replace(chr(92),chr(92)*2).replace('"',chr(92)+'"')
        label = '"'+escaped+'" <'+email+'>' if name else email
        result.append(dict(kind='new', label=label))
    return result


def backfill_mail_participants():
    if setting('mail_participants_v1'):
        return
    for entry in rows("SELECT id,sender,recipients FROM entries WHERE source_key LIKE 'mail:%' ORDER BY id"):
        combined = participant_items(entry['id'])
        known = {item['id'] for item in combined if item['kind']=='person'}
        existing_emails = {parseaddr(item['label'])[1].lower() for item in combined if item['kind']=='new' and '@' in item['label']}
        for item in mail_participants(entry['sender'],entry['recipients'],exclude=own_addresses()):
            match = contact_match(item['label'])
            if match and match['id'] in known:
                continue
            if parseaddr(item['label'])[1].lower() in existing_emails:
                continue
            combined.append(item)
        sync_participants(entry['id'],dict(participant_items=combined))
    set_setting('mail_participants_v1',True)
