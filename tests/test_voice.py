import io
from pathlib import Path
import pytest
from journal.db import one, cipher
from journal.domain import now


@pytest.mark.parametrize('mime',['audio/webm','audio/ogg','audio/mp4'])
def test_voice_saved_for_today_encrypted_and_playable(app,client,post,mime):
    content=b'fictional-audio-content'
    response=post('/voice/save',{'date':'2001-01-01','audio':(io.BytesIO(content),'voice',mime)})
    assert response.status_code==200
    with app.app_context():
        entry=one('SELECT * FROM entries')
        attachment=one('SELECT * FROM attachments')
        assert entry['type']=='journal' and entry['date']==now().date().isoformat()
        assert entry['title'].startswith('Sprachi · ')
        encrypted=(Path(app.instance_path)/'attachments'/attachment['path']).read_bytes()
        assert content not in encrypted and cipher().decrypt(encrypted)==content
    url=f'/attachment/{attachment["id"]}/audio'
    response=client.get(url,base_url='https://localhost')
    assert response.data==content and response.mimetype==mime
    assert client.get(url,base_url='https://localhost',headers={'Range':'bytes=0-4'}).status_code==206
    assert '/audio' in client.get(f'/entry/{entry["id"]}',base_url='https://localhost').text
    client.post('/logout',data={'csrf_token':'test-csrf'},base_url='https://localhost')
    assert client.get(url,base_url='https://localhost').status_code==302


@pytest.mark.parametrize('content,mime',[(b'','audio/webm'),(b'html','text/html'),(b'x'*(25*1024*1024+1),'audio/webm')])
def test_invalid_voice_does_not_create_entry(app,post,content,mime):
    assert post('/voice/save',{'audio':(io.BytesIO(content),'voice',mime)}).status_code==400
    with app.app_context():assert one('SELECT count(*) n FROM entries')['n']==0


def test_voice_requires_csrf(client):
    response=client.post('/voice/save',data={'audio':(io.BytesIO(b'audio'),'voice','audio/webm')},base_url='https://localhost')
    assert response.status_code==400
