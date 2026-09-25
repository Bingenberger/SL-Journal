"""Render a page locally through stdin/stdout, without plaintext files."""
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import BoundedSemaphore

_render_slots=BoundedSemaphore(2)


def render_pdf(content, seite=1, kantenlaenge=1100):
    if not content.lstrip().startswith(b'%PDF-'):
        raise ValueError('Der Anhang ist keine lesbare PDF-Datei.')
    executable=shutil.which('pdftoppm')
    if not executable:
        raise RuntimeError('Für die PDF-Vorschau fehlt poppler-utils auf dem Server.')
    if not _render_slots.acquire(timeout=2):
        raise RuntimeError('Die PDF-Vorschau ist gerade ausgelastet. Bitte erneut versuchen.')
    try:
        seite=max(1,int(seite))
        process=subprocess.run([executable,'-f',str(seite),'-l',str(seite),'-singlefile','-scale-to',str(kantenlaenge),'-png','-'],
            input=content,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15,check=False)
        if process.returncode or not process.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Keine Vorschau verfügbar. Die Seite fehlt, oder die Datei ist geschützt oder beschädigt.')
        return process.stdout
    except subprocess.TimeoutExpired:
        raise ValueError('Die PDF-Vorschau dauert zu lange. Bitte die Datei herunterladen.')
    finally:
        _render_slots.release()


_office_slots=BoundedSemaphore(1)
# Dateitypen, die LibreOffice zuverlässig in ein PDF wandelt.
OFFICE={'.odt','.ods','.odp','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.rtf','.txt','.csv'}


def office_to_pdf(content, endung):
    """Ein Office-Dokument lokal in ein PDF wandeln, damit es seitenweise lesbar wird."""
    programm=shutil.which('soffice') or shutil.which('libreoffice')
    if not programm:
        raise RuntimeError('Für Office-Dokumente fehlt LibreOffice auf dem Server.')
    if not _office_slots.acquire(timeout=90):
        raise ValueError('Es wird gerade ein anderes Dokument umgewandelt. Bitte kurz erneut versuchen.')
    try:
        with tempfile.TemporaryDirectory() as ordner:
            quelle=Path(ordner)/('dokument'+(endung if endung in OFFICE else '.odt'))
            quelle.write_bytes(content)
            # Eigenes Benutzerprofil je Lauf: kein gemeinsamer Zustand, keine Makros.
            ergebnis=subprocess.run([programm,'--headless','--norestore',
                f'-env:UserInstallation=file://{Path(ordner)/"profil"}',
                '--convert-to','pdf','--outdir',ordner,str(quelle)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,check=False)
            fertig=list(Path(ordner).glob('*.pdf'))
            if ergebnis.returncode or not fertig:
                raise ValueError('Dieses Dokument ließ sich nicht für die Anzeige umwandeln.')
            return fertig[0].read_bytes()
    except subprocess.TimeoutExpired:
        raise ValueError('Die Umwandlung dauert zu lange. Bitte die Datei herunterladen.')
    finally:
        _office_slots.release()
