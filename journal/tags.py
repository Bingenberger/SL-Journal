"""Shared tag matching for overview counts and entry filtering."""
import unicodedata


def tag_key(value):
    return unicodedata.normalize('NFKC',value or '').strip().casefold()


def has_tag(value, tag):
    key=tag_key(tag)
    return int(bool(key) and any(tag_key(part)==key for part in (value or '').split(',')))


def overview(query=''):
    """Alle vergebenen Tags mit der Zahl der Einträge und der Aufgaben dahinter."""
    from .db import rows
    found={}
    for feld,quelle in (('entries',"SELECT tags FROM entries WHERE tags<>'' ORDER BY id"),
                        ('tasks',"SELECT tags FROM tasks WHERE tags<>'' ORDER BY id")):
        for zeile in rows(quelle):
            seen=set()
            for label in zeile['tags'].split(','):
                label=label.strip()
                key=tag_key(label)
                if not key or key in seen: continue
                seen.add(key)
                item=found.setdefault(key,dict(name=label,entries=0,tasks=0))
                item[feld]+=1
    for item in found.values():
        item['count']=item['entries']+item['tasks']
    search=tag_key(query).lstrip('#')
    return sorted((item for key,item in found.items() if search in key),key=lambda item:tag_key(item['name']))
