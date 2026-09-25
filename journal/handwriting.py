"""Local, editable Excalidraw sheets stored in the encrypted journal database."""
import io
import json
import math
import uuid

from flask import Blueprint, abort, jsonify, render_template, request, send_file, url_for
from PIL import Image, UnidentifiedImageError

from .db import get_db, one
from .domain import now, save_entry, valid_date

bp = Blueprint('handwriting', __name__)
ELEMENT_TYPES = {'freedraw', 'line', 'arrow', 'rectangle', 'diamond', 'ellipse', 'text', 'frame'}


def sheet(did):
    result = one('SELECT * FROM drawings WHERE id=?', (did,))
    if not result:
        abort(404)
    return result


def editor(drawing=None, entry_id=None):
    entry = one('SELECT id,title,date FROM entries WHERE id=?', (entry_id,)) if entry_id else None
    if entry_id and not entry:
        abort(404)
    return render_template('handwriting.html', boot=dict(
        id=drawing['id'] if drawing else None,
        revision=drawing['revision'] if drawing else 0,
        client_key=drawing['client_key'] if drawing else str(uuid.uuid4()),
        entry_id=entry_id,
        title=drawing['title'] if drawing else 'Handschriftliche Notiz',
        date=entry['date'] if entry else now().date().isoformat(),
        scene=json.loads(drawing['scene']) if drawing else None,
        back=url_for('entry_view', eid=entry_id) if entry_id else url_for('cockpit'),
        save=url_for('handwriting.save'),
    ), entry=entry)


@bp.get('/handwriting/new')
def new():
    return editor(entry_id=request.args.get('entry', type=int))


@bp.get('/handwriting/<int:did>')
def edit(did):
    drawing = sheet(did)
    return editor(drawing, drawing['entry_id'])


def validate_scene(raw):
    if len(raw.encode('utf8')) > 4 * 1024 * 1024:
        raise ValueError('Das Zeichenblatt ist zu groß. Bitte ein weiteres Blatt anlegen.')
    try:
        scene = json.loads(raw, parse_constant=lambda _: None)
    except (ValueError, RecursionError):
        raise ValueError('Das Zeichenblatt konnte nicht gelesen werden.')
    if not isinstance(scene, dict) or scene.get('type') != 'excalidraw':
        raise ValueError('Ungültiges Zeichenblatt.')
    elements = scene.get('elements')
    if not isinstance(elements, list) or len(elements) > 10000:
        raise ValueError('Das Zeichenblatt enthält zu viele Elemente.')
    if scene.get('files'):
        raise ValueError('Bilder bitte als Anhang zum Eintrag hinzufügen.')
    points = 0
    ids = set()
    for el in elements:
        if not isinstance(el, dict) or el.get('type') not in ELEMENT_TYPES:
            raise ValueError('Dieses Element wird auf dem Zeichenblatt nicht unterstützt.')
        eid = el.get('id')
        if not isinstance(eid, str) or not eid or eid in ids:
            raise ValueError('Ungültige Elementkennung.')
        ids.add(eid)
        for name in ('x', 'y', 'width', 'height'):
            val = el.get(name)
            if not isinstance(val, (float, int)) or isinstance(val, bool) or not math.isfinite(val) or abs(val) > 1e7:
                raise ValueError('Ungültige Abmessungen im Zeichenblatt.')
        if not isinstance(el.get('points', []), list):
            raise ValueError('Ungültige Stiftstriche.')
        points += len(el.get('points', []))
        if points > 250000:
            raise ValueError('Das Zeichenblatt ist voll. Bitte ein weiteres Blatt anlegen.')
    if not isinstance(scene.get('appState', {}), dict):
        raise ValueError('Ungültige Blatteinstellungen.')
    scene['files'] = {}
    return json.dumps(scene, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def validate_preview(upload):
    if not upload:
        raise ValueError('Die Blattvorschau fehlt.')
    data = upload.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('Die Blattvorschau ist zu groß.')
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format != 'PNG' or not (0 < img.width <= 1600 and 0 < img.height <= 1600):
                raise ValueError('Ungültige Blattvorschau.')
            img.load()
            out = io.BytesIO()
            img.convert('RGB').save(out, format='PNG')
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('Ungültige Blattvorschau.')


def saved(drawing):
    return jsonify(id=drawing['id'], revision=drawing['revision'], entry_id=drawing['entry_id'],
                   edit=url_for('handwriting.edit', did=drawing['id']),
                   back=url_for('entry_view', eid=drawing['entry_id']),
                   png=url_for('handwriting.preview', did=drawing['id'], download=1))


@bp.post('/handwriting/save')
def save():
    title = request.form.get('title', '').strip()
    if not title or len(title) > 500:
        raise ValueError('Bitte einen Blatttitel mit höchstens 500 Zeichen eingeben.')
    try:
        client_key = str(uuid.UUID(request.form.get('client_key', '')))
        revision = int(request.form.get('revision', '0'))
    except (ValueError, TypeError):
        raise ValueError('Ungültige Blattkennung.')
    scene = validate_scene(request.form.get('scene', ''))
    preview = validate_preview(request.files.get('preview'))
    db = get_db()
    # Serialize creation and revision checks, including retries after a lost response.
    db.execute('BEGIN IMMEDIATE')
    current = one('SELECT * FROM drawings WHERE client_key=?', (client_key,))
    if current:
        if current['scene'] == scene and current['title'] == title:
            db.rollback()
            return saved(current)
        if current['revision'] != revision:
            db.rollback()
            return jsonify(error='Das Blatt wurde in einem anderen Fenster geändert. Bitte die lokale Zeichnung herunterladen, bevor Sie die Seite neu laden.'), 409
        db.execute('UPDATE drawings SET title=?,scene=?,preview=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   (title, scene, preview, current['id']))
        did = current['id']
    else:
        if revision != 0:
            abort(404)
        entry_id = request.form.get('entry_id', type=int)
        if entry_id:
            if not one('SELECT id FROM entries WHERE id=?', (entry_id,)):
                abort(404)
        else:
            entry_id = save_entry(dict(title=title, date=valid_date(request.form.get('date')), type='note'))
        did = db.execute('INSERT INTO drawings(entry_id,client_key,title,scene,preview) VALUES(?,?,?,?,?)',
                         (entry_id, client_key, title, scene, preview)).lastrowid
    db.commit()
    return saved(sheet(did))


@bp.get('/handwriting/<int:did>/preview')
def preview(did):
    drawing = sheet(did)
    return send_file(io.BytesIO(drawing['preview']), mimetype='image/png',
                     as_attachment=request.args.get('download') == '1',
                     download_name=f"Notiz-{did}.png")


@bp.post('/handwriting/<int:did>/delete')
def delete(did):
    drawing = sheet(did)
    revision = request.form.get('revision', type=int)
    db = get_db()
    result = db.execute('DELETE FROM drawings WHERE id=? AND revision=?', (did, revision))
    if result.rowcount != 1:
        db.rollback()
        raise ValueError('Das Blatt wurde inzwischen geändert. Bitte zuerst die Seite neu laden.')
    db.commit()
    from flask import redirect
    return redirect(url_for('entry_view', eid=drawing['entry_id']))

