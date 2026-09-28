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


# --- Tags im Fließtext: #Schulfest ------------------------------------------

import re

# Nach dem Doppelkreuz muss ein Buchstabe stehen – so werden weder „#1“ noch
# Überschriften („## Beschlüsse“) noch Anker in Adressen zu Tags.
INLINE = re.compile(r'(?<![\w#])#([^\W\d_][\w-]{0,63})')


def inline_tags(*texte):
    """Alle im Fließtext geschriebenen Tags, in der Reihenfolge ihres Auftretens."""
    gefunden = []
    for text in texte:
        gefunden.extend(INLINE.findall(text or ''))
    return gefunden


def merge_tags(feld, *texte):
    """Tags aus dem Eingabefeld und aus dem Text zusammenführen.

    Das Feld hat Vorrang: Steht ein Tag dort bereits, bleibt dessen
    Schreibweise erhalten und die aus dem Text wird verworfen.
    """
    from .domain import clean_tags
    ergebnis = []
    bekannt = set()
    for label in clean_tags(feld or '').split(', ') + inline_tags(*texte):
        label = label.strip()
        key = tag_key(label)
        if not key or key in bekannt:
            continue
        bekannt.add(key)
        ergebnis.append(label)
    return ', '.join(ergebnis)


def markdown_extension():
    """Macht #Tags im Fließtext anklickbar – und verhindert, dass sie am
    Zeilenanfang als Markdown-Überschrift gelesen werden."""
    import xml.etree.ElementTree as ET
    from markdown.extensions import Extension
    from markdown.inlinepatterns import InlineProcessor

    def ziel(name):
        try:
            from flask import url_for
            return url_for('entry_list', tag=name)
        except Exception:
            from urllib.parse import quote
            return '/entries?tag=' + quote(name)

    class TagVerweis(InlineProcessor):
        def handleMatch(self, treffer, daten):
            element = ET.Element('a')
            element.text = '#' + treffer.group(1)
            element.set('href', ziel(treffer.group(1)))
            element.set('class', 'inline-tag')
            return element, treffer.start(0), treffer.end(0)

    class Tags(Extension):
        def extendMarkdown(self, md):
            # Eine Überschrift braucht jetzt das Leerzeichen („# Titel“), wie es
            # auch die Werkzeugleiste einfügt. Ohne diese Änderung würde
            # „#Schulfest“ am Zeilenanfang zur Überschrift statt zum Tag.
            md.parser.blockprocessors['hashheader'].RE = re.compile(
                r'(?:^|\n)(?P<level>#{1,6})[ \t]+(?P<header>(?:\\.|[^\\])*?)#*(?:\n|$)')
            # Nach den Code-Abschnitten (190), damit `#Tag` in Code Code bleibt.
            md.inlinePatterns.register(TagVerweis(INLINE.pattern, md), 'journal-tag', 185)

    return Tags()


def verwandte(entry, je_gruppe=5):
    """Andere Einträge, die mit diesem etwas teilen – nach Tag, Vorgang, Projekt.

    Gruppiert statt vermischt: Ein Eintrag trägt oft mehrere Tags und gehört zu
    mehreren Vorhaben; beim Lesen verfolgt man einen Faden davon.
    """
    from .db import one, rows
    SPALTEN = 'e.id,e.title,e.date,e.type'
    ORDNUNG = ' ORDER BY e.date DESC,e.time DESC,e.id DESC LIMIT ?'

    def gruppe(name, bedingung, wert, route, kwargs):
        treffer = rows(f'SELECT {SPALTEN} FROM entries e {bedingung} AND e.id<>?' + ORDNUNG,
                       (wert, entry['id'], je_gruppe))
        if not treffer:
            return None
        gesamt = one(f'SELECT count(*) n FROM entries e {bedingung} AND e.id<>?', (wert, entry['id']))['n']
        return dict(name=name, eintraege=treffer, gesamt=gesamt, route=route, kwargs=kwargs)

    von_tags = []
    gesehen = set()
    for label in (entry['tags'] or '').split(','):
        label = label.strip()
        key = tag_key(label)
        if not key or key in gesehen:
            continue
        gesehen.add(key)
        gefunden = gruppe(label, 'WHERE has_tag(e.tags,?)', label, 'entry_list', dict(tag=label))
        if gefunden:
            von_tags.append(gefunden)

    def ueber(tabelle, schluessel, posten, name_feld, route, kwarg):
        gefunden = (gruppe(posten_eintrag[name_feld],
                           f'JOIN {tabelle} v ON v.entry_id=e.id WHERE v.{schluessel}=?',
                           posten_eintrag['id'], route, {kwarg: posten_eintrag['id']})
                    for posten_eintrag in posten)
        return [g for g in gefunden if g]

    return dict(tags=von_tags,
                cases=ueber('entry_cases', 'case_id', entry.get('cases') or [], 'title', 'case_view', 'cid'),
                projects=ueber('entry_projects', 'project_id', entry.get('projects') or [], 'name', 'project_view', 'pid'))
