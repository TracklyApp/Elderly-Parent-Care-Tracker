"""Restore an encrypted complete backup after stopping Kindred."""
import argparse
import os
from pathlib import Path
import socket
import sqlite3
import server
from cryptography.fernet import InvalidToken

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('backup',type=Path);parser.add_argument('--confirm',action='store_true');args=parser.parse_args()
    if not args.confirm:parser.error('Stop the server, then add --confirm to restore. The current database will be backed up first.')
    try:
        with socket.create_connection(('127.0.0.1',8877),timeout=1):parser.error('Kindred is still running on port 8877. Stop it before restoring.')
    except (ConnectionRefusedError,TimeoutError,OSError):pass
    if not (server.DB.parent/'master.key').exists():parser.error('The original data/master.key is required to decrypt this backup.')
    try:contents=server.advanced.cipher(server).decrypt(args.backup.read_bytes())
    except InvalidToken:parser.error('This backup is damaged or belongs to another encryption key.')
    pending=server.DB.parent/'restore-pending.sqlite3'
    try:
        pending.write_bytes(contents)
        with sqlite3.connect(pending) as restored:
            if restored.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity check failed.')
            restored.execute('SELECT id,state FROM families LIMIT 1');restored.execute('SELECT id,email FROM users LIMIT 1')
            restored.execute('DELETE FROM sessions')
            if restored.execute("SELECT name FROM sqlite_master WHERE name='push_subscriptions'").fetchone():restored.execute('DELETE FROM push_subscriptions')
        if server.DB.exists():server.advanced.encrypted_backup(server)
        os.replace(pending,server.DB)
    finally:
        if pending.exists():pending.unlink()
    print('Backup restored. Start Kindred, sign in again, and re-enable browser reminders.')

if __name__=='__main__':main()
