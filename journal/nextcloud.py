"""Dateien aus der eigenen Nextcloud lesen und im Journal darstellen.

Alle Abrufe laufen serverseitig mit dem hinterlegten App-Token; der Browser
holt nie etwas aus der Cloud. Es wird ausschließlich gelesen.
"""
import base64
import hashlib
import re
from pathlib import Path
from urllib import request as http
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

from flask import current_app

from .db import atomic_write, cipher, setting
from .domain import now

ZEITLIMIT = 30
GROESSTE_DATEI = 40 * 1024 * 1024
VORSCHAU_GUELTIG = 1800  # Sekunden, bis eine zwischengespeicherte Seite neu geholt wird


def konto():
    """Zugangsdaten der Nextcloud; sie stehen bereits für den Kalender bereit."""
    daten = setting('caldav', {})
    adresse = (daten.get('url') or '').strip()
    if not adresse or not daten.get('username') or not daten.get('password'):
        return None
    teile = urlsplit(adresse)
    return dict(basis=f'{teile.scheme}://{teile.netloc}', host=teile.netloc.lower(),
                benutzer=daten['username'], geheim=daten['password'])


def referenz(adresse):
    """Aus einem gespeicherten Link die Nextcloud-Kennung lesen.

    Erlaubt sind nur Links auf den eingerichteten Server – sonst könnte ein
    fremder Link das Journal dazu bringen, mit dem Token woanders anzufragen.
    """
    zugang = konto()
    if not zugang:
        return None
    teile = urlsplit(adresse or '')
    if teile.scheme != 'https' or teile.netloc.lower() != zugang['host']:
        return None
    pfad = unquote(teile.path)
    datei = (re.search(r'/(?:index\.php/)?f/(\d+)', pfad)
             or re.search(r'/apps/files/files/(\d+)', pfad)
             or re.search(r'[?&]openfile=(\d+)', teile.query))
    if datei:
        return ('datei', datei.group(1))
    freigabe = re.search(r'/(?:index\.php/)?s/([A-Za-z0-9_\-]{4,64})', pfad)
    if freigabe:
        return ('freigabe', freigabe.group(1))
    return None


def _abruf(pfad, methode='GET', kopf=None, rumpf=None, anmeldung=None, grenze=GROESSTE_DATEI):
    zugang = konto()
    if not zugang:
        raise ValueError('Für die Anzeige fehlt die Nextcloud-Verbindung. Bitte in den Einstellungen eintragen.')
    benutzer, geheim = anmeldung or (zugang['benutzer'], zugang['geheim'])
    anfrage = http.Request(zugang['basis'] + pfad, method=methode, data=rumpf)
    anfrage.add_header('Authorization', 'Basic ' + base64.b64encode(f'{benutzer}:{geheim}'.encode()).decode())
    anfrage.add_header('OCS-APIRequest', 'true')
    anfrage.add_header('User-Agent', 'Schulleitungsjournal')
    for name, wert in (kopf or {}).items():
        anfrage.add_header(name, wert)
    try:
        with http.urlopen(anfrage, timeout=ZEITLIMIT) as antwort:
            laenge = antwort.headers.get('Content-Length')
            if laenge and int(laenge) > grenze:
                raise ValueError('Die Datei ist zu groß für die Anzeige im Journal. Bitte in Nextcloud öffnen.')
            inhalt = antwort.read(grenze + 1)
            if len(inhalt) > grenze:
                raise ValueError('Die Datei ist zu groß für die Anzeige im Journal. Bitte in Nextcloud öffnen.')
            return antwort.status, antwort.headers.get('Content-Type', ''), inhalt
    except HTTPError as fehler:
        return fehler.code, fehler.headers.get('Content-Type', ''), b''
    except (URLError, OSError):
        raise ValueError('Die Nextcloud ist gerade nicht erreichbar.')


def angaben(ref):
    """Pfad, Name und Typ zu einer Kennung ermitteln."""
    art, wert = ref
    if art == 'datei':
        rumpf = f'''<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:basicsearch>
<d:select><d:prop><d:getcontenttype/><d:getcontentlength/><d:displayname/></d:prop></d:select>
<d:from><d:scope><d:href>/files/{konto()['benutzer']}</d:href><d:depth>infinity</d:depth></d:scope></d:from>
<d:where><d:eq><d:prop><oc:fileid/></d:prop><d:literal>{wert}</d:literal></d:eq></d:where>
<d:orderby/></d:basicsearch></d:searchrequest>'''.encode()
        status, _, inhalt = _abruf('/remote.php/dav/', 'SEARCH', {'Content-Type': 'text/xml'}, rumpf, grenze=200000)
        if status != 207:
            raise ValueError('Die Datei ist in der Nextcloud nicht mehr auffindbar.')
        text = inhalt.decode('utf8', 'replace')
        pfad = re.search(r'<d:href>([^<]+)</d:href>', text)
        typ = re.search(r'<d:getcontenttype>([^<]*)</d:getcontenttype>', text)
        if not pfad:
            raise ValueError('Die Datei ist in der Nextcloud nicht mehr auffindbar.')
        return dict(pfad=pfad.group(1), mime=(typ.group(1) if typ else ''),
                    name=unquote(pfad.group(1)).rstrip('/').split('/')[-1])
    rumpf = b'''<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>
<d:getcontenttype/><d:getcontentlength/><d:displayname/></d:prop></d:propfind>'''
    status, _, inhalt = _abruf('/public.php/webdav/', 'PROPFIND', {'Depth': '0', 'Content-Type': 'application/xml'},
                               rumpf, anmeldung=(wert, ''), grenze=200000)
    if status != 207:
        raise ValueError('Der Freigabelink ist nicht mehr gültig.')
    text = inhalt.decode('utf8', 'replace')
    typ = re.search(r'<d:getcontenttype>([^<]*)</d:getcontenttype>', text)
    name = re.search(r'<d:displayname>([^<]*)</d:displayname>', text)
    return dict(pfad='/public.php/webdav/', mime=(typ.group(1) if typ else ''),
                name=(name.group(1) if name else 'Freigegebene Datei'), anmeldung=(wert, ''))


def _schluessel(ref, zweck):
    return hashlib.sha256(f'{ref[0]}:{ref[1]}:{zweck}'.encode()).hexdigest()[:32]


def datei(ref, zwischenspeichern=False, daten=None):
    """Die Datei selbst holen – für die PDF-Darstellung und zum Herunterladen."""
    daten = daten or angaben(ref)
    if zwischenspeichern:
        # Beim Blättern wird sonst für jede Seite dieselbe Datei erneut geladen.
        gespeichert = _aus_cache(_schluessel(ref, 'datei'))
        if gespeichert:
            return dict(daten, inhalt=gespeichert, mime=daten['mime'])
    status, typ, inhalt = _abruf(daten['pfad'], anmeldung=daten.get('anmeldung'))
    if status != 200 or not inhalt:
        raise ValueError('Die Datei konnte nicht geladen werden.')
    if zwischenspeichern and len(inhalt) <= 20 * 1024 * 1024:
        _in_cache(_schluessel(ref, 'datei'), inhalt)
    return dict(daten, inhalt=inhalt, mime=daten['mime'] or typ)


def _cache(schluessel):
    return Path(current_app.instance_path)/'cache'/f'doc-{schluessel}.enc'


def _aus_cache(schluessel):
    pfad = _cache(schluessel)
    if not pfad.exists() or (now().timestamp() - pfad.stat().st_mtime) > VORSCHAU_GUELTIG:
        return None
    try:
        return cipher().decrypt(pfad.read_bytes())
    except Exception:
        return None


def _in_cache(schluessel, inhalt):
    atomic_write(_cache(schluessel), cipher().encrypt(inhalt))
    _aufraeumen()


def _aufraeumen():
    """Abgelaufene Zwischenspeicher entfernen – Dateien aus der Cloud bleiben nicht liegen."""
    grenze = now().timestamp() - VORSCHAU_GUELTIG
    for alt in (Path(current_app.instance_path)/'cache').glob('doc-*.enc'):
        try:
            if alt.stat().st_mtime < grenze:
                alt.unlink(missing_ok=True)
        except OSError:
            pass


def seitenzahl(inhalt):
    import subprocess
    try:
        ergebnis = subprocess.run(['pdfinfo', '-'], input=inhalt, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, timeout=20, check=False)
        treffer = re.search(rb'Pages:\s+(\d+)', ergebnis.stdout or b'')
        return max(1, int(treffer.group(1))) if treffer else 1
    except (subprocess.TimeoutExpired, OSError):
        return 1


def _art(daten):
    """Wie wird diese Datei dargestellt: als PDF, als Bild oder über die Cloud-Vorschau?"""
    from .pdf_preview import OFFICE
    mime = (daten['mime'] or '').lower()
    endung = ('.' + daten['name'].rsplit('.', 1)[-1].lower()) if '.' in daten['name'] else ''
    if mime == 'application/pdf' or endung == '.pdf':
        return 'pdf', endung
    if mime.startswith('image/'):
        return 'bild', endung
    if endung in OFFICE or 'opendocument' in mime or 'officedocument' in mime or mime.startswith('text/'):
        return 'office', endung
    return 'cloud', endung


def _als_pdf(ref, daten, endung):
    """PDF-Fassung besorgen – Originale unverändert, Office-Dateien lokal gewandelt."""
    art, _ = _art(daten)
    if art == 'pdf':
        return datei(ref, zwischenspeichern=True, daten=daten)['inhalt']
    gespeichert = _aus_cache(_schluessel(ref, 'pdf'))
    if gespeichert:
        return gespeichert
    from .pdf_preview import office_to_pdf
    gewandelt = office_to_pdf(datei(ref, zwischenspeichern=True, daten=daten)['inhalt'], endung)
    _in_cache(_schluessel(ref, 'pdf'), gewandelt)
    return gewandelt


def _cloud_vorschau(ref):
    if ref[0] == 'datei':
        pfad = f'/index.php/core/preview?fileId={ref[1]}&x=1400&y=1980&a=1'
    else:
        pfad = f'/index.php/apps/files_sharing/publicpreview/{ref[1]}?x=1400&y=1980&a=1'
    status, typ, inhalt = _abruf(pfad, grenze=8 * 1024 * 1024)
    if status != 200 or not typ.startswith('image/') or typ.endswith('svg+xml'):
        raise ValueError('Für diesen Dateityp gibt es keine Vorschau. Die Datei lässt sich herunterladen.')
    return inhalt


def infos(ref):
    """Name, Typ und Seitenzahl – und ob überhaupt eine Vorschau möglich ist."""
    daten = angaben(ref)
    art, endung = _art(daten)
    if art in ('pdf', 'office'):
        try:
            return dict(name=daten['name'], mime=daten['mime'], seiten=seitenzahl(_als_pdf(ref, daten, endung)))
        except RuntimeError:
            pass  # ohne LibreOffice bleibt die Vorschau aus der Cloud
    vorschau(ref, 1)  # meldet sich mit einer Erklärung, wenn es keine Vorschau gibt
    return dict(name=daten['name'], mime=daten['mime'], seiten=1)


def vorschau(ref, seite=1):
    """Ein Seitenbild liefern: PDFs und Office-Dateien seitenweise, sonst ein Vorschaubild."""
    bildschluessel = _schluessel(ref, f'bild-{seite}')
    zahlschluessel = _schluessel(ref, 'seitenzahl')
    gespeichert = _aus_cache(bildschluessel)
    if gespeichert:
        gemerkt = _aus_cache(zahlschluessel)
        return dict(bild=gespeichert, seiten=int(gemerkt) if gemerkt else None)
    daten = angaben(ref)
    art, endung = _art(daten)
    if art in ('pdf', 'office'):
        try:
            from .pdf_preview import render_pdf
            inhalt = _als_pdf(ref, daten, endung)
            bild = render_pdf(inhalt, seite=seite, kantenlaenge=1400)
            seiten = seitenzahl(inhalt)
            _in_cache(bildschluessel, bild)
            _in_cache(zahlschluessel, str(seiten).encode())
            return dict(bild=bild, seiten=seiten)
        except RuntimeError:
            art = 'cloud'  # Werkzeug fehlt: dann eben das Vorschaubild der Cloud
    if seite != 1:
        raise ValueError('Diese Datei hat nur eine Vorschauseite.')
    if art == 'bild':
        bild = _bildseite(datei(ref, zwischenspeichern=True, daten=daten)['inhalt'])
    else:
        bild = _cloud_vorschau(ref)
    _in_cache(bildschluessel, bild)
    _in_cache(zahlschluessel, b'1')
    return dict(bild=bild, seiten=1)


def _bildseite(inhalt):
    """Bilder neu berechnen: begrenzte Größe, keine fremden Metadaten."""
    import io
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(inhalt)) as bild:
            bild.load()
            kopie = bild.convert('RGB')
            kopie.thumbnail((1400, 1980))
            ausgabe = io.BytesIO()
            kopie.save(ausgabe, format='PNG')
            return ausgabe.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('Dieses Bild lässt sich nicht anzeigen. Die Datei lässt sich herunterladen.')


# --- Dateibrowser -----------------------------------------------------------

EINTRAEGE_JE_ORDNER = 500

PROPS = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
         '<d:prop><d:getcontenttype/><d:resourcetype/><d:getcontentlength/>'
         '<d:getlastmodified/><oc:fileid/><oc:size/></d:prop></d:propfind>').encode()


def _sicherer_pfad(pfad):
    """Nur Pfade innerhalb des eigenen Nextcloud-Ordners zulassen."""
    teile = []
    for stueck in str(pfad or '').replace('\\', '/').split('/'):
        stueck = stueck.strip()
        if not stueck or stueck == '.':
            continue
        if stueck == '..':
            raise ValueError('Dieser Ordner liegt außerhalb Ihrer Dateien.')
        teile.append(stueck)
    return teile


def _eintrag(block, wurzel):
    """Einen PROPFIND-Abschnitt in einen Listeneintrag übersetzen."""
    adresse = re.search(r'<d:href>([^<]+)</d:href>', block)
    if not adresse:
        return None
    pfad = unquote(adresse.group(1))
    if not pfad.startswith(wurzel):
        return None
    rest = pfad[len(wurzel):].strip('/')
    if not rest:
        return None  # der Ordner selbst
    kennung = re.search(r'<oc:fileid>(\d+)</oc:fileid>', block)
    typ = re.search(r'<d:getcontenttype>([^<]*)</d:getcontenttype>', block)
    groesse = (re.search(r'<oc:size>(\d+)</oc:size>', block)
               or re.search(r'<d:getcontentlength>(\d+)</d:getcontentlength>', block))
    geaendert = re.search(r'<d:getlastmodified>([^<]*)</d:getlastmodified>', block)
    return dict(name=rest.split('/')[-1], pfad=rest, ordner='<d:collection/>' in block,
                mime=(typ.group(1) if typ else ''),
                groesse=int(groesse.group(1)) if groesse else 0,
                geaendert=(geaendert.group(1) if geaendert else ''),
                url=f"{konto()['basis']}/index.php/f/{kennung.group(1)}" if kennung else '')


def blaettern(pfad=''):
    """Einen Ordner der Nextcloud auflisten – Ordner zuerst, dann Dateien."""
    zugang = konto()
    if not zugang:
        raise ValueError('Für den Dateibrowser fehlt die Nextcloud-Verbindung. Bitte in den Einstellungen eintragen.')
    teile = _sicherer_pfad(pfad)
    wurzel = f"/remote.php/dav/files/{zugang['benutzer']}/"
    ziel = wurzel + ''.join(quote(stueck) + '/' for stueck in teile)
    status, _, inhalt = _abruf(ziel, 'PROPFIND', {'Depth': '1', 'Content-Type': 'application/xml'},
                               PROPS, grenze=8 * 1024 * 1024)
    if status == 404:
        raise ValueError('Diesen Ordner gibt es in der Nextcloud nicht mehr.')
    if status != 207:
        raise ValueError('Der Ordner ließ sich nicht öffnen.')
    aktuell = '/'.join(teile)
    eintraege = []
    for block in inhalt.decode('utf8', 'replace').split('<d:response>')[1:]:
        gelesen = _eintrag(block, wurzel)
        # Der geöffnete Ordner steht selbst mit in der Antwort und gehört nicht in die Liste;
        # versteckte Systemordner wie .sync blendet auch Nextcloud selbst aus.
        if gelesen and gelesen['pfad'] != aktuell and not gelesen['name'].startswith('.'):
            eintraege.append(gelesen)
    eintraege.sort(key=lambda e: (not e['ordner'], e['name'].casefold()))
    return dict(pfad='/'.join(teile), teile=teile, eintraege=eintraege[:EINTRAEGE_JE_ORDNER],
                gekuerzt=len(eintraege) > EINTRAEGE_JE_ORDNER)


def dateien_suchen(begriff, grenze=40):
    """Im gesamten eigenen Bestand nach Dateinamen suchen."""
    zugang = konto()
    if not zugang:
        raise ValueError('Für die Suche fehlt die Nextcloud-Verbindung.')
    begriff = ' '.join(str(begriff or '').split())[:80]
    if len(begriff) < 2:
        return dict(pfad='', teile=[], eintraege=[], gekuerzt=False, suche=begriff)
    muster = '%' + begriff.replace('\\', '').replace('%', '').replace('_', '') + '%'
    rumpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:basicsearch>'
        '<d:select><d:prop><d:getcontenttype/><d:resourcetype/><d:getcontentlength/>'
        '<d:getlastmodified/><oc:fileid/><oc:size/></d:prop></d:select>'
        f"<d:from><d:scope><d:href>/files/{zugang['benutzer']}</d:href>"
        '<d:depth>infinity</d:depth></d:scope></d:from>'
        '<d:where><d:like><d:prop><d:displayname/></d:prop>'
        f'<d:literal>{escape(muster)}</d:literal></d:like></d:where>'
        f'<d:orderby/><d:limit><d:nresults>{int(grenze)}</d:nresults></d:limit>'
        '</d:basicsearch></d:searchrequest>').encode()
    status, _, inhalt = _abruf('/remote.php/dav/', 'SEARCH', {'Content-Type': 'text/xml'},
                               rumpf, grenze=8 * 1024 * 1024)
    if status != 207:
        raise ValueError('Die Suche in der Nextcloud ist fehlgeschlagen.')
    wurzel = f"/remote.php/dav/files/{zugang['benutzer']}/"
    eintraege = []
    for block in inhalt.decode('utf8', 'replace').split('<d:response>')[1:]:
        gelesen = _eintrag(block, wurzel)
        if gelesen and not gelesen['ordner'] and not gelesen['name'].startswith('.') \
                and not any(teil.startswith('.') for teil in gelesen['pfad'].split('/')):
            eintraege.append(gelesen)
    eintraege.sort(key=lambda e: e['name'].casefold())
    return dict(pfad='', teile=[], eintraege=eintraege, gekuerzt=len(eintraege) >= grenze, suche=begriff)
