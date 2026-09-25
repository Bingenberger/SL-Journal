#!/usr/bin/env python3
"""Local administration. Run `python manage.py --help`."""
import argparse
import ipaddress
import json
import os
import secrets
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description='Schulleitungsjournal verwalten')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init',help='Einrichtungscode und Backupschlüssel anlegen')
    run=sub.add_parser('run',help='Lokal mit HTTPS starten')
    run.add_argument('--port',type=int,default=8443)
    run.add_argument('--host',default='127.0.0.1',help='Bind-Adresse; für LAN-Tests die lokale LAN-IP angeben')
    run.add_argument('--cert',type=Path,help='Eigenes PEM-Zertifikat')
    run.add_argument('--key',type=Path,help='Schlüssel zum eigenen Zertifikat')
    repair=sub.add_parser('repair-forwards',help='Unveränderte importierte Weiterleitungen aus Original.eml korrigieren')
    repair.add_argument('--apply',action='store_true',help='Korrekturen speichern')
    sub.add_parser('tasks',help='Fällige Aufgaben aus Serien bis 14 Tage im Voraus anlegen')
    sub.add_parser('sync',help='IMAP und CalDAV synchronisieren')
    calendar=sub.add_parser('calendar',help='Kalendercache für einen Zeitraum laden')
    calendar.add_argument('--start',required=True);calendar.add_argument('--days',type=int,default=30)
    backup_cmd=sub.add_parser('backup',help='Verschlüsselte Sicherung erstellen')
    backup_cmd.add_argument('--destination',type=Path);backup_cmd.add_argument('--keep-days',type=int,default=30)
    restore_cmd=sub.add_parser('restore',help='In ein leeres Verzeichnis wiederherstellen')
    restore_cmd.add_argument('backup',type=Path);restore_cmd.add_argument('--key',type=Path,required=True);restore_cmd.add_argument('--destination',type=Path,required=True)
    obsidian=sub.add_parser('import-obsidian',help='Obsidian-Vault prüfen oder importieren')
    obsidian.add_argument('vault',type=Path);obsidian.add_argument('--apply',action='store_true',help='Import tatsächlich ausführen')
    purge_cmd=sub.add_parser('purge',help='Fällige Löschungen prüfen oder ausführen')
    purge_cmd.add_argument('--apply',action='store_true')
    sub.add_parser('maintenance',help='Löschfristen anwenden und Backup erstellen')
    sub.add_parser('reset-auth',help='Anmeldung lokal zurücksetzen; Daten bleiben erhalten')
    sub.add_parser('demo',help='Getrennten Beispielbestand für die lokale Vorschau anlegen')
    args=parser.parse_args()
    os.umask(0o077)
    if args.command=='restore':
        from journal.maintenance import restore
        print(restore(args.backup,args.key,args.destination)); return
    from journal.app import create_app
    from journal.db import atomic_write, get_db, one, set_setting
    from cryptography.fernet import Fernet
    from werkzeug.security import generate_password_hash
    import pyotp
    app=create_app()
    with app.app_context():
        instance=Path(app.instance_path)
        if args.command in ('init','reset-auth'):
            if args.command=='reset-auth':
                if input('Anmeldung zurücksetzen und alle Sitzungen beenden? RESET eingeben: ')!='RESET': return
                get_db().execute('DELETE FROM account');get_db().execute('UPDATE login_limit SET failures=0,until=0')
            elif one('SELECT id FROM account'):
                print('Die Anmeldung ist bereits eingerichtet.');return
            code=secrets.token_urlsafe(24)
            set_setting('setup_token',generate_password_hash(code));set_setting('setup_totp',pyotp.random_base32());get_db().commit()
            if not (instance/'backup.key').exists(): atomic_write(instance/'backup.key',Fernet.generate_key())
            print('Einrichtungscode (einmalig verwenden): '+code)
            print('Start: .venv/bin/python manage.py run')
            print('Adresse: https://localhost:8443/setup')
            print('Backupschlüssel separat und sicher verwahren: '+str(instance/'backup.key'))
        elif args.command=='run':
            if bool(args.cert)!=bool(args.key): raise ValueError('--cert und --key müssen zusammen angegeben werden.')
            cert,key=(args.cert,args.key) if args.cert else local_certificate(instance)
            address='localhost' if args.host=='127.0.0.1' else args.host
            print(f'Journal erreichbar unter https://{address}:{args.port}')
            # Local testing, optionally on a LAN address. Production uses waitress + nginx.
            import logging
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
            app.run(host=args.host,port=args.port,ssl_context=(str(cert),str(key)),debug=False,use_reloader=False)
        elif args.command=='repair-forwards':
            from journal.mail_repair import repair_forwarded_mails
            print(json.dumps(repair_forwarded_mails(args.apply),ensure_ascii=False))
        elif args.command=='tasks':
            from journal.recurrence import generate
            print(f'{generate()} neue Serienaufgaben angelegt.')
        elif args.command=='sync':
            from journal.integrations import sync_all
            print(sync_all())
        elif args.command=='calendar':
            from datetime import date
            from journal.integrations import sync_calendar
            if not 1<=args.days<=366: raise ValueError('Zeitraum: 1 bis 366 Tage.')
            print(sync_calendar(date.fromisoformat(args.start),args.days))
        elif args.command in ('backup','maintenance'):
            from journal.maintenance import backup,purge
            if args.command=='maintenance':
                if not (instance/'backup.key').exists(): raise ValueError('Backupschlüssel fehlt. Wartung abgebrochen.')
                from journal.recurrence import generate
                generate()
                print(f'{len(purge(apply=True))} Einträge nach Löschfrist entfernt.');print(backup())
            else:
                if args.keep_days<1: raise ValueError('Backupaufbewahrung mindestens 1 Tag.')
                print(backup(args.destination,args.keep_days))
        elif args.command=='purge':
            from journal.maintenance import purge
            results=purge(args.apply)
            print(json.dumps(results,ensure_ascii=False,indent=2));print('Gelöscht.' if args.apply else 'Vorschau. Mit --apply ausführen.')
        elif args.command=='import-obsidian':
            from journal.maintenance import import_obsidian
            print(json.dumps(import_obsidian(args.vault,args.apply),ensure_ascii=False,indent=2))
            if not args.apply: print('Vorschau. Mit --apply importieren.')
        elif args.command=='demo':
            from journal.demo import seed
            seed();print('Beispieldaten angelegt. Die Anmeldung wird regulär mit „init“ eingerichtet.')


def local_certificate(instance):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from journal.db import atomic_write
    cert_file=instance/'localhost.pem';key_file=instance/'localhost-key.pem'
    if cert_file.exists() and key_file.exists(): return cert_file,key_file
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=365))
          .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
    atomic_write(key_file,key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
    atomic_write(cert_file,cert.public_bytes(serialization.Encoding.PEM))
    return cert_file,key_file


if __name__=='__main__':
    try: main()
    except (ValueError,FileNotFoundError) as exc: raise SystemExit(str(exc))
