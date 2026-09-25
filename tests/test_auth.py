import pyotp
from werkzeug.security import generate_password_hash
from journal.app import create_app
from journal.db import get_db,one,set_setting

def test_login_and_totp_replay(app):
    with app.app_context(): secret=one('SELECT totp FROM account')['totp']
    client=app.test_client();client.get('/login',base_url='https://localhost')
    with client.session_transaction(base_url='https://localhost') as session: token=session['csrf']
    data=dict(csrf_token=token,password='ein-testpasswort-mit-20-zeichen',otp=pyotp.TOTP(secret).now())
    assert client.post('/login',base_url='https://localhost',data=data).status_code==302
    assert client.get('/',base_url='https://localhost').status_code==200
    with client.session_transaction(base_url='https://localhost') as session: token=session['csrf']
    client.post('/logout',base_url='https://localhost',data={'csrf_token':token})
    client.get('/login',base_url='https://localhost')
    with client.session_transaction(base_url='https://localhost') as session: data['csrf_token']=session['csrf']
    assert client.post('/login',base_url='https://localhost',data=data).status_code==200
    assert client.get('/',base_url='https://localhost').status_code==302

def test_setup_requires_secret_and_verified_otp(tmp_path):
    app=create_app({'TESTING':True,'INSTANCE_PATH':str(tmp_path/'new')})
    secret=pyotp.random_base32()
    with app.app_context():
        set_setting('setup_token',generate_password_hash('local-code'));set_setting('setup_totp',secret);get_db().commit()
    client=app.test_client();client.get('/setup',base_url='https://localhost')
    with client.session_transaction(base_url='https://localhost') as s: csrf=s['csrf']
    assert client.post('/setup/qr',base_url='https://localhost',data={'csrf_token':csrf,'setup_code':'wrong'}).status_code==403
    response=client.post('/setup/qr',base_url='https://localhost',data={'csrf_token':csrf,'setup_code':'local-code'})
    assert response.json['secret']==secret
    response=client.post('/setup',base_url='https://localhost',data={'csrf_token':csrf,'setup_code':'local-code','password':'langes-sicheres-passwort','password_repeat':'langes-sicheres-passwort','otp':pyotp.TOTP(secret).now()})
    assert response.status_code==302
    assert client.get('/',base_url='https://localhost').status_code==200
    assert client.get('/setup',base_url='https://localhost').status_code==302

def test_rate_limit(app):
    client=app.test_client();client.get('/login',base_url='https://localhost')
    with client.session_transaction(base_url='https://localhost') as s: csrf=s['csrf']
    for _ in range(5): client.post('/login',base_url='https://localhost',data={'csrf_token':csrf,'password':'wrong','otp':'000000'})
    assert client.post('/login',base_url='https://localhost',data={'csrf_token':csrf,'password':'wrong','otp':'000000'}).status_code==429

def test_invalid_unicode_otp_is_rejected_without_server_error(app):
    client=app.test_client();client.get('/login',base_url='https://localhost')
    with client.session_transaction(base_url='https://localhost') as session: token=session['csrf']
    response=client.post('/login',base_url='https://localhost',data={'csrf_token':token,'password':'wrong','otp':'äöüß測試'})
    assert response.status_code==200
    assert client.get('/',base_url='https://localhost').status_code==302
