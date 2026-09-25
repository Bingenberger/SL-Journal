import re
from pathlib import Path

SPRITE = Path(__file__).resolve().parent.parent/'journal'/'templates'/'icons.html'
TEMPLATES = SPRITE.parent
# Zeichen, die früher als Symbol dienten und jetzt aus dem Sprite kommen.
LEGACY = '＋↗→←↻✓○↧↳◫▱☑▤≡♧⌕✉☏▦✎✧‹›↪⚙'


def symbols():
    return set(re.findall(r'id="i-([a-z]+)"', SPRITE.read_text()))


def test_every_referenced_symbol_exists(app, client):
    from journal.demo import seed
    with app.app_context():
        seed()
    used = set()
    for path in ['/','/projects','/project/1','/entries','/entries?inbox=1','/entry/1','/tasks',
                 '/tasks?filter=all','/tags','/people','/processes','/settings']:
        response = client.get(path, base_url='https://localhost')
        assert response.status_code == 200, path
        used |= set(re.findall(r'href="#i-([a-z]+)"', response.text))
    assert used, 'Es wurde kein einziges Symbol gerendert.'
    assert used <= symbols(), f'Ohne Symbol im Sprite: {sorted(used-symbols())}'


def test_templates_use_the_sprite_instead_of_glyphs():
    for template in TEMPLATES.glob('*.html'):
        if template.name == 'icons.html':
            continue
        found = {c for c in template.read_text() if c in LEGACY}
        assert not found, f'{template.name} enthält noch Zeichen-Symbole: {sorted(found)}'


def test_sprite_is_delivered_with_the_page(client):
    page = client.get('/', base_url='https://localhost').text
    assert '<symbol id="i-cockpit"' in page, 'Das Sprite fehlt in der Seite.'
    assert 'fill="currentColor"' not in page.split('</svg>')[0], 'Symbole sollen die Textfarbe erben.'
