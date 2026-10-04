"""Local PDF/Office text extraction and OCR. No external service calls."""
import shutil
import subprocess
import time

from .pdf_preview import OFFICE, office_to_pdf

IMAGES={'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}
MAX_TEXT=2_000_000


def run(program,args,content,deadline,seconds=30):
    executable=shutil.which(program)
    if not executable:
        raise ValueError(f'Für die Texterkennung fehlt {program}. Bitte die Installationshinweise beachten.')
    remaining=deadline-time.monotonic()
    if remaining<=0:
        raise ValueError('Zeitlimit der Texterkennung erreicht.')
    result=subprocess.run([executable,*args],input=content,stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,timeout=min(seconds,remaining),check=False)
    if result.returncode:
        raise ValueError(f'{program}: Datei ist beschädigt, geschützt oder nicht lesbar.')
    return result.stdout


def ocr(image,deadline):
    languages=run('tesseract',['--list-langs'],None,deadline).decode().splitlines()
    selected=[lang for lang in ('deu','eng') if lang in languages]
    if not selected:
        raise ValueError('Tesseract benötigt das Sprachpaket Deutsch (deu) oder Englisch (eng).')
    text=run('tesseract',['stdin','stdout','-l','+'.join(selected)],image,deadline,60).decode('utf-8',errors='replace').strip()
    return text, '' if 'deu' in selected else 'OCR nur mit Englisch; für deutsche Texte das Tesseract-Sprachpaket deu installieren.'


def pdf_text(content,deadline):
    if not content.lstrip().startswith(b'%PDF-'):
        raise ValueError('Keine gültige PDF-Datei.')
    raw=run('pdftotext',['-enc','UTF-8','-layout','-','-'],content,deadline).decode('utf-8',errors='replace')
    if len(raw)>MAX_TEXT:
        raise ValueError('Textumfang überschreitet die Grenze von 2 Millionen Zeichen.')
    chunks=raw.split('\f')
    if chunks and not chunks[-1].strip():chunks.pop()
    pages=[];warnings=[];failed=False;used=0;ocr_count=0
    for number,chunk in enumerate(chunks,1):
        text=chunk.strip()
        # Also covers scans with a small digital header/page number.
        if sum(c.isalnum() for c in text)<40:
            try:
                if ocr_count>=100:raise ValueError('OCR-Grenze von 100 Seiten pro Datei erreicht.')
                ocr_count+=1
                image=run('pdftoppm',['-f',str(number),'-l',str(number),'-singlefile','-scale-to','2800','-png','-'],content,deadline)
                recognized,warning=ocr(image,deadline)
                if recognized and recognized not in text:text='\n'.join(filter(None,[text,recognized]))
                if warning:warnings.append(warning)
            except (ValueError,subprocess.TimeoutExpired) as exc:
                failed=True
                warnings.append(str(exc) if isinstance(exc,ValueError) else 'Zeitlimit der OCR erreicht.')
        used+=len(text)
        if used>MAX_TEXT:raise ValueError('Textumfang überschreitet die Grenze von 2 Millionen Zeichen.')
        if text:pages.append((number,text))
    status=('partial' if pages else 'error') if failed else ('ready' if pages else 'empty')
    detail=' '.join(dict.fromkeys(warnings))
    if not pages and not detail:detail='Kein lesbarer Text erkannt, auch nicht durch OCR.'
    return pages,status,detail


def extract_document(suffix,content):
    deadline=time.monotonic()+240
    if suffix in IMAGES:
        text,warning=ocr(content,deadline)
        if len(text)>MAX_TEXT:raise ValueError('Textumfang überschreitet die Grenze von 2 Millionen Zeichen.')
        return ([(1,text)] if text else []),'ready' if text else 'empty',warning or ('' if text else 'Kein lesbarer Text erkannt.')
    if suffix in OFFICE:
        content=office_to_pdf(content,suffix)
    return pdf_text(content,deadline)
