"""Anmeldeprüfung, die Browser-Anmeldung und Mobil-App gemeinsam nutzen."""
import hmac
import time

import pyotp
from flask import abort
from werkzeug.security import check_password_hash

from .db import get_db, one


def rate_limit():
    limit = one('SELECT * FROM login_limit WHERE id=1')
    if limit['until'] > time.time():
        abort(429,'Zu viele Anmeldeversuche. Bitte in 15 Minuten erneut versuchen.')


def login_failed():
    db = get_db()
    db.execute('UPDATE login_limit SET failures=failures+1 WHERE id=1')
    if one('SELECT failures FROM login_limit WHERE id=1')['failures'] >= 5:
        db.execute('UPDATE login_limit SET until=?, failures=0 WHERE id=1',(time.time()+900,))
    db.commit()


def valid_code(code):
    return isinstance(code, str) and code.isascii() and len(code)==6 and code.isdigit()


def verify(account, password, code):
    """Passwort und Einmalcode prüfen. Ein Code gilt nur einmal; bei Erfolg
    ist der Zähler gesetzt, aber noch nicht gespeichert."""
    totp = pyotp.TOTP(account['totp'])
    counter = int(time.time())//30
    matched = next((c for c in range(counter-1,counter+2) if hmac.compare_digest(totp.at(c*30),code)),None)
    if check_password_hash(account['password'],password or '') and matched is not None:
        cursor = get_db().execute('UPDATE account SET last_totp=? WHERE id=1 AND last_totp<?',(matched,matched))
        if cursor.rowcount:
            get_db().execute('UPDATE login_limit SET failures=0,until=0 WHERE id=1')
            return True
        get_db().rollback()
    return False
