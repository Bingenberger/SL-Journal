import pytest
import pyotp
from werkzeug.security import generate_password_hash
from journal.app import create_app
from journal.db import get_db

@pytest.fixture
def app(tmp_path):
    app=create_app({'INSTANCE_PATH':str(tmp_path/'instance'),'TESTING':True})
    with app.app_context():
        get_db().execute('INSERT INTO account(id,password,totp,session_version) VALUES(1,?,?,?)',(generate_password_hash('ein-testpasswort-mit-20-zeichen'),pyotp.random_base32(),'test-version'))
        get_db().commit()
    return app

@pytest.fixture
def client(app):
    client=app.test_client()
    with client.session_transaction(base_url='https://localhost') as s:
        s.update(auth=True,version='test-version',csrf='test-csrf')
    return client

@pytest.fixture
def post(client):
    def request(path,data=None,**kwargs):
        return client.post(path,data={'csrf_token':'test-csrf',**(data or {})},base_url='https://localhost',headers={'X-Requested-With':'fetch'},**kwargs)
    return request
