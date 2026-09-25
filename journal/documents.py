"""Metadata and associations only; external files are never fetched."""
from urllib.parse import urlsplit, urlunsplit, unquote
from .db import get_db,one,rows


def validate_url(value):
    value=value.strip()
    if len(value)>4096 or any(ord(c)<33 or ord(c)==127 for c in value) or chr(92) in value:
        raise ValueError('Bitte einen gültigen HTTPS-Link ohne Leerzeichen eingeben.')
    if any(ord(c)<32 or ord(c)==127 for c in unquote(value)):
        raise ValueError('Der Link enthält ungültige Steuerzeichen.')
    try:
        parsed=urlsplit(value)
        port=parsed.port
        host=parsed.hostname
        if port==0: raise ValueError()
        if parsed.scheme.lower()!='https' or not host or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        host=host.encode('idna').decode('ascii').lower()
        if '%' in host or any(c in host for c in '<>"'): raise ValueError()
        if ':' in host: host='['+host+']'
        netloc=host+(':'+str(port) if port and port!=443 else '')
        return urlunsplit(('https',netloc,parsed.path or '/',parsed.query,parsed.fragment))
    except (ValueError,UnicodeError):
        raise ValueError('Bitte einen vollständigen HTTPS-Link ohne Zugangsdaten verwenden.')


def save(data, document_id=None):
    name=data.get('name','').strip()
    description=data.get('description','').strip()
    if not name or len(name)>500 or len(description)>4000:
        raise ValueError('Bitte einen Namen (maximal 500 Zeichen) und eine Beschreibung mit maximal 4000 Zeichen eingeben.')
    url=validate_url(data.get('url',''))
    duplicate=one('SELECT id FROM documents WHERE url=?',(url,))
    if document_id:
        if not one('SELECT id FROM documents WHERE id=?',(document_id,)):
            raise ValueError('Der Dokumentverweis existiert nicht.')
        if duplicate and duplicate['id']!=document_id:
            raise ValueError('Dieser Link ist bereits als Dokument hinterlegt. Bitte den vorhandenen Verweis verwenden.')
        get_db().execute('UPDATE documents SET name=?,url=?,description=? WHERE id=?',(name,url,description,document_id))
        return document_id
    if duplicate:
        return duplicate['id']
    return get_db().execute('INSERT INTO documents(name,url,description) VALUES(?,?,?)',(name,url,description)).lastrowid


def associate(document_id, owner, owner_id):
    if owner not in ('entry','project'):
        raise ValueError('Bitte einen Eintrag oder ein Projekt wählen.')
    table='entries' if owner=='entry' else 'projects'
    if not one(f'SELECT id FROM {table} WHERE id=?',(owner_id,)):
        raise ValueError('Der Eintrag oder das Projekt existiert nicht.')
    get_db().execute(f'INSERT OR IGNORE INTO {owner}_documents VALUES(?,?)',(owner_id,document_id))


def listed(owner, owner_id):
    if owner=='entry':
        result=rows('SELECT d.*,1 direct FROM documents d JOIN entry_documents ed ON ed.document_id=d.id WHERE ed.entry_id=? ORDER BY d.name',(owner_id,))
    else:
        result=rows("""SELECT d.*,EXISTS(SELECT 1 FROM project_documents pd WHERE pd.document_id=d.id AND pd.project_id=?) direct
        FROM documents d WHERE EXISTS(SELECT 1 FROM project_documents pd WHERE pd.document_id=d.id AND pd.project_id=?)
        OR EXISTS(SELECT 1 FROM entry_documents ed JOIN entry_projects ep ON ep.entry_id=ed.entry_id WHERE ed.document_id=d.id AND ep.project_id=?) ORDER BY d.name""",(owner_id,owner_id,owner_id))
    for item in result:
        item['origins']=rows('SELECT e.id,e.title FROM entries e JOIN entry_documents ed ON ed.entry_id=e.id JOIN entry_projects ep ON ep.entry_id=e.id WHERE ed.document_id=? AND ep.project_id=? ORDER BY e.date DESC',(item['id'],owner_id)) if owner=='project' else []
    return result
