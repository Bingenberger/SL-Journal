"""Repair untouched imported forwards from their encrypted original EML."""
import re
from pathlib import Path
from email import policy
from email.parser import BytesParser
from cryptography.fernet import InvalidToken
from flask import current_app
from .db import get_db,rows,setting,cipher
from .integrations import addresses,body_text,parse_forward
from .participants import participant_items,mail_participants,own_addresses,sync_participants


def repair_forwarded_mails(apply=False):
    db=get_db()
    if apply: db.execute('BEGIN IMMEDIATE')
    result={'recognized':0,'updated':0,'edited_skipped':0,'unreadable':0}
    own=set(setting('imap',{}).get('own_addresses',[]))
    try:
        for entry in rows("""SELECT e.*,a.path FROM entries e JOIN attachments a ON a.entry_id=e.id
                WHERE e.source_key LIKE 'mail:%' AND a.name='Original.eml'
                AND a.id=(SELECT min(a2.id) FROM attachments a2 WHERE a2.entry_id=e.id AND a2.name='Original.eml') ORDER BY e.id"""):
            try:
                raw=cipher().decrypt((Path(current_app.instance_path)/'attachments'/entry['path']).read_bytes())
                message=BytesParser(policy=policy.default).parsebytes(raw)
                if any(part.get_content_type()=='message/rfc822' for part in message.walk()): continue
                outer_subject=str(message.get('Subject','')) or '(Ohne Betreff)'
                outer_sender=str(message.get('From',''))
                text=body_text(message)
                parsed=parse_forward(text,allow_header_only=bool(re.match(r'^(?:fwd?|wg):',outer_subject,re.I)))
            except (OSError,ValueError,TypeError,InvalidToken):
                result['unreadable']+=1
                continue
            if not parsed or parsed['uncertain']: continue
            if entry['title']==parsed['title'] and entry['body']==parsed['body']: continue
            result['recognized']+=1
            if entry['title']!=outer_subject or entry['body'] not in (text,f'Archivweiterleitung von {outer_sender}\n\n{text}'):
                result['edited_skipped']+=1
                continue
            if not apply: continue
            envelope=set()
            for key in ('From','To','Cc','Bcc'): envelope.update(addresses(str(message.get(key,''))))
            people={p['id']:p for p in rows('SELECT * FROM people')}
            kept=[]
            for participant in participant_items(entry['id']):
                emails=addresses(people[participant['id']]['emails']) if participant['kind']=='person' else addresses(participant['label'])
                if not emails or not emails <= envelope: kept.append(participant)
            participants=kept+mail_participants(parsed['sender'],parsed['recipients'],exclude=own_addresses())
            dt=parsed['datetime']
            kind='mail_out' if addresses(parsed['sender']) & own else 'mail_in'
            db.execute('UPDATE entries SET title=?,body=?,sender=?,recipients=?,date=?,time=?,type=?,needs_review=0 WHERE id=?',
                (parsed['title'],parsed['body'],parsed['sender'],parsed['recipients'],dt.date().isoformat(),dt.strftime('%H:%M'),kind,entry['id']))
            sync_participants(entry['id'],dict(participant_items=participants))
            result['updated']+=1
        if apply: db.commit()
    except Exception:
        if apply: db.rollback()
        raise
    return result
