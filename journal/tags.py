"""Shared tag matching for overview counts and entry filtering."""
import unicodedata


def tag_key(value):
    return unicodedata.normalize('NFKC',value or '').strip().casefold()


def has_tag(value, tag):
    key=tag_key(tag)
    return int(bool(key) and any(tag_key(part)==key for part in (value or '').split(',')))


def overview(query=''):
    from .db import rows
    found={}
    for entry in rows("SELECT tags FROM entries WHERE tags<>'' ORDER BY id"):
        seen=set()
        for label in entry['tags'].split(','):
            label=label.strip()
            key=tag_key(label)
            if not key or key in seen: continue
            seen.add(key)
            item=found.setdefault(key,dict(name=label,count=0))
            item['count']+=1
    search=tag_key(query).lstrip('#')
    return sorted((item for key,item in found.items() if search in key),key=lambda item:tag_key(item['name']))
