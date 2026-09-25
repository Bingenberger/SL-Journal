"""Einheitliche Schaltflächensprache: Symbol für die Handlung, Farbe für den Rang."""
import re
from journal.db import get_db
from journal.domain import save_entry, now

SEITEN = ['/','/entries','/entries?inbox=1','/entry/1','/tasks','/task-series','/projects','/project/1',
          '/cases','/case/1','/people','/person/1','/tags','/processes','/appointments','/settings','/search?q=a']

# Beschriftung -> erwartetes Symbol. Deckt die wiederkehrenden Handlungen ab.
ERWARTET = {'Abbrechen':'close','Speichern':'check','Löschen':'delete','Bearbeiten':'edit',
            'Suchen':'search','Filtern':'filter','Wiederherstellen':'reset'}


def seed(app):
    with app.app_context():
        from journal.demo import seed as demo
        demo()
        db = get_db()
        db.execute("INSERT INTO cases(title,status) VALUES('Beschwerde','open')")
        db.execute("INSERT INTO people(name) VALUES('Sabine Meier')")
        db.execute("INSERT INTO processes(name,month,period,todos) VALUES('Martinszug',9,'early','[]')")
        db.execute("INSERT INTO documents(name,url) VALUES('Raumplan','https://cloud.example.org/f/1')")
        db.commit()


def buttons(text):
    for treffer in re.finditer(r'<button([^>]*)>(.*?)</button>', text, re.S):
        attrs, inhalt = treffer.group(1), treffer.group(2)
        if 'aria-label' in attrs and not re.sub(r'<[^>]+>', '', inhalt).strip():
            continue  # reine Symbolschaltflächen tragen ihre Bedeutung im Label
        if 'task-text' in attrs:
            continue  # der Aufgabentext ist Inhalt, keine Handlung
        yield attrs, inhalt, ' '.join(re.sub(r'<[^>]+>', ' ', inhalt).split())


def test_every_labelled_button_carries_an_icon(app, client):
    seed(app)
    ohne = []
    for pfad in SEITEN:
        antwort = client.get(pfad, base_url='https://localhost')
        assert antwort.status_code == 200, pfad
        for attrs, inhalt, beschriftung in buttons(antwort.text):
            if beschriftung and '<svg' not in inhalt:
                ohne.append((pfad, beschriftung[:40]))
    assert not ohne, f'Schaltflächen ohne Symbol: {ohne[:10]}'


def test_recurring_actions_use_the_same_icon(app, client):
    seed(app)
    gefunden = {}
    for pfad in SEITEN:
        for attrs, inhalt, beschriftung in buttons(client.get(pfad, base_url='https://localhost').text):
            for wort, symbol in ERWARTET.items():
                if wort in beschriftung:
                    treffer = re.search(r'href="#i-([a-z]+)"', inhalt)
                    gefunden.setdefault(wort, set()).add(treffer.group(1) if treffer else 'ohne')
    for wort, symbol in ERWARTET.items():
        if wort in gefunden:
            assert gefunden[wort] == {symbol}, f'{wort}: {gefunden[wort]} statt {{{symbol}}}'


def test_destructive_actions_are_marked(app, client):
    seed(app)
    with app.app_context():
        save_entry(dict(type='note', date=now().date().isoformat(), title='Mit Löschweg'))
        get_db().commit()
    for pfad in ['/entry/1', '/project/1', '/case/1', '/person/1', '/processes']:
        text = client.get(pfad, base_url='https://localhost').text
        loeschen = [(a, i) for a, i, b in buttons(text) if 'löschen' in b.lower() or 'Löschen' in b]
        assert loeschen, pfad
        for attrs, inhalt in loeschen:
            assert 'danger' in attrs, f'{pfad}: Löschen ohne Warnfarbe'
            assert '#i-delete' in inhalt, f'{pfad}: Löschen ohne Papierkorb'
