"""Account security, audit trail, snapshots, documents and background reminders."""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import struct
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RUNTIME_STATUS={'lastBackup':None,'backupError':None,'pushError':None,'pushMessagesSent':0}

def init_schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS security(user TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,secret TEXT,enabled INTEGER DEFAULT 0,pending TEXT,last_step INTEGER DEFAULT -1,recovery TEXT DEFAULT '[]');
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,family TEXT,profile TEXT,collection TEXT,record TEXT,action TEXT,actor TEXT,at TEXT,before TEXT,after TEXT,reason TEXT);
    CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,family TEXT,revision INTEGER,state TEXT,actor TEXT,at TEXT,label TEXT);
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,family TEXT,profile TEXT,name TEXT,mime TEXT,body BLOB,doctor TEXT,date TEXT,author TEXT,at TEXT,archived INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS push_subscriptions(id TEXT PRIMARY KEY,user TEXT REFERENCES users(id) ON DELETE CASCADE,subscription TEXT,enabled INTEGER DEFAULT 1,timezone TEXT,escalate INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS push_deliveries(subscription TEXT,event TEXT,at REAL,PRIMARY KEY(subscription,event));
    ''')
    if 'role' not in [r[1] for r in db.execute('PRAGMA table_info(invites)')]:db.execute("ALTER TABLE invites ADD COLUMN role TEXT NOT NULL DEFAULT 'caregiver'")

def cipher(server):
    from cryptography.fernet import Fernet
    path=server.DB.parent/'master.key'
    if not path.exists():
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(path.read_bytes())

def totp(secret,step=None):
    step=int(time.time()//30) if step is None else step
    key=base64.b32decode(secret+'='*((8-len(secret)%8)%8));raw=hmac.new(key,struct.pack('>Q',step),hashlib.sha1).digest();offset=raw[-1]&15
    return str((struct.unpack('>I',raw[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)

def verify_totp(db,server,user,code,secret=None):
    sec=db.execute('SELECT * FROM security WHERE user=?',(user['id'],)).fetchone()
    if not sec:return False
    secret=secret or cipher(server).decrypt(sec['secret'].encode()).decode()
    for step in range(int(time.time()//30)-1,int(time.time()//30)+2):
        if step>sec['last_step'] and hmac.compare_digest(totp(secret,step),str(code)):
            db.execute('UPDATE security SET last_step=? WHERE user=?',(step,user['id']));return True
    return False

def login_check(handler,db,server,user,data):
    sec=db.execute('SELECT * FROM security WHERE user=?',(user['id'],)).fetchone()
    if sec and sec['enabled'] and not verify_totp(db,server,user,data.get('otp','')):
        handler.reply(401,{'error':'Enter a current authenticator code.','requiresOtp':True});return False
    return True

def timestamp():return datetime.now(timezone.utc).isoformat()
def log(db,user,collection,record,action,before=None,after=None,reason='',profile=''):
    db.execute('INSERT INTO audit(family,profile,collection,record,action,actor,at,before,after,reason) VALUES(?,?,?,?,?,?,?,?,?,?)',(user['family'],profile,collection,record,action,user['name'],timestamp(),json.dumps(before) if before is not None else None,json.dumps(after) if after is not None else None,reason))

COLLECTIONS=('entries','medications','doses','tasks','handoffs','shifts','questions')
def changed_records(previous,new):
    old={p['id']:p for p in previous['profiles']};current={p['id']:p for p in new['profiles']}
    for pid in old.keys()|current.keys():
        a,b=old.get(pid),current.get(pid)
        if a is None or b is None:
            yield pid,'profiles',pid,a,b;continue
        meta=lambda p:{k:v for k,v in p.items() if k not in COLLECTIONS}
        if meta(a)!=meta(b):yield pid,'profiles',pid,meta(a),meta(b)
        for key in COLLECTIONS:
            am={r['id']:r for r in a.get(key,[])};bm={r['id']:r for r in b.get(key,[])}
            for rid in am.keys()|bm.keys():
                if am.get(rid)!=bm.get(rid):yield pid,key,rid,am.get(rid),bm.get(rid)

def save_audit(db,user,previous,new,revision,reason='Care record updated'):
    # Server timestamps and session identity cannot be supplied by the client.
    db.execute('INSERT INTO snapshots(family,revision,state,actor,at,label) VALUES(?,?,?,?,?,?)',(user['family'],revision,json.dumps(previous),user['name'],timestamp(),'Automatic snapshot before change'))
    for pid,key,rid,a,b in changed_records(previous,new):log(db,user,key,rid,'added' if a is None else 'deleted' if b is None else 'updated',a,b,reason,pid)
    db.execute('DELETE FROM snapshots WHERE family=? AND id NOT IN (SELECT id FROM snapshots WHERE family=? ORDER BY id DESC LIMIT 100)',(user['family'],user['family']))

def state_rules(previous,new,user):
    for pid,key,rid,a,b in changed_records(previous,new):
        if key=='doses' and a and b:
            for k in ('medicationId','scheduled','recordedAt','author','name','dosage'):
                if a.get(k)!=b.get(k):return 'Original medication administration details cannot be overwritten.'
            if a.get('status')!=b.get('status') or a.get('reason')!=b.get('reason'):
                correction=b.get('corrections',[])
                old=a.get('corrections',[])
                if len(correction)!=len(old)+1 or correction[:-1]!=old or not correction[-1].get('reason','').strip():return 'A dose correction must include a reason and preserve its history.'
        if key=='doses' and a and b is None:return 'Medication administrations must be corrected, not deleted.'
    return ''

def valid_extras(s):
    try:
        for p in s['profiles']:
            if 'timezone' in p:ZoneInfo(p['timezone'])
            for key in ('shifts','questions'):
                rows=p.get(key,[])
                if not isinstance(rows,list) or len(rows)>30000 or len({x['id'] for x in rows})!=len(rows):return False
            for shift in p.get('shifts',[]):
                if not all(isinstance(shift.get(k),str) for k in ('id','caregiver','backup','start','end','notes')) or not shift['caregiver'].strip() or datetime.fromisoformat(shift['end'])<=datetime.fromisoformat(shift['start']):return False
            for q in p.get('questions',[]):
                if not all(isinstance(q.get(k),str) for k in ('id','title','answer','doctor','date','author')) or q.get('status') not in ('open','answered'):return False
            for m in p['medications']:
                if 'weekdays' in m and (not m['weekdays'] or not isinstance(m['weekdays'],list) or any(type(x)!=int or x<0 or x>6 for x in m['weekdays'])):return False
                for k in ('stockInitial','unitsPerDose','lowStockAt'):
                    value=m.get(k)
                    if value is not None and (type(value) not in (int,float) or not 0<=value<10000000):return False
                if any(not isinstance(r,dict) or not isinstance(r.get('id'),str) or type(r.get('quantity')) not in (int,float) or not 0<r['quantity']<10000000 for r in m.get('restocks',[])):return False
        return True
    except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):return False

def recovery_post(handler,db,server,path,data):
    if path!='/api/reset-password':return False
    ip=handler.client_address[0];db.execute('DELETE FROM attempts WHERE at<?',(time.time()-900,))
    if db.execute('SELECT count(*) FROM attempts WHERE ip=?',(ip,)).fetchone()[0]>=30:handler.reply(429,{'error':'Try again in 15 minutes.'});return True
    db.execute('INSERT INTO attempts VALUES(?,?)',(ip,time.time()))
    user=db.execute('SELECT * FROM users WHERE email=?',(str(data.get('email','')).lower().strip(),)).fetchone();sec=db.execute('SELECT * FROM security WHERE user=?',(user['id'],)).fetchone() if user else None
    code=server.digest(str(data.get('recovery','')).strip());password=str(data.get('password',''))
    codes=json.loads(sec['recovery']) if sec else []
    if not 12<=len(password)<=256 or not any(hmac.compare_digest(code,x) for x in codes):handler.reply(400,{'error':'The email, recovery code, or new password is invalid.'});return True
    codes.remove(code);db.execute('UPDATE security SET recovery=?,enabled=0,secret=NULL,pending=NULL,last_step=-1 WHERE user=?',(json.dumps(codes),user['id']))
    db.execute('UPDATE users SET password=? WHERE id=?',(server.password_hash(password),user['id']));db.execute('DELETE FROM sessions WHERE user=?',(user['id'],));log(db,user,'security',user['id'],'password recovered',reason='Recovery code used; sessions revoked; authenticator reset');db.commit();handler.reply(200,{'ok':True});return True

def get(handler,db,server,user,path):
    if path=='/api/system-status':handler.reply(200,dict(RUNTIME_STATUS));return True
    if path=='/api/security':
        sec=db.execute('SELECT enabled,recovery FROM security WHERE user=?',(user['id'],)).fetchone();handler.reply(200,{'enabled':bool(sec and sec['enabled']),'recoveryCodes':len(json.loads(sec['recovery'])) if sec else 0});return True
    if path=='/api/audit':
        rows=[dict(r) for r in db.execute('SELECT * FROM audit WHERE family=? ORDER BY id DESC LIMIT 500',(user['family'],))]
        for r in rows:
            for key in ('before','after'):r[key]=json.loads(r[key]) if r[key] else None
        handler.reply(200,{'records':rows});return True
    if path=='/api/backups':handler.reply(200,{'backups':[dict(r) for r in db.execute('SELECT id,revision,actor,at,label FROM snapshots WHERE family=? ORDER BY id DESC',(user['family'],))]});return True
    if path=='/api/documents':handler.reply(200,{'documents':[dict(r) for r in db.execute('SELECT id,profile,name,mime,length(body) AS size,doctor,date,author,at,archived FROM documents WHERE family=? ORDER BY at DESC',(user['family'],))]});return True
    if path.startswith('/api/document/'):
        document=db.execute('SELECT * FROM documents WHERE id=? AND family=?',(path.rsplit('/',1)[-1],user['family'])).fetchone()
        if not document:handler.reply(404,{'error':'Document not found.'});return True
        handler.send_response(200);handler.headers_common();handler.send_header('Content-Type',document['mime']);handler.send_header('Content-Length',str(len(document['body'])));handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(document['name']));handler.end_headers();handler.wfile.write(document['body']);return True
    if path=='/api/push-config':
        try:public=push_keys(server)[1]
        except ImportError:public=''
        handler.reply(200,{'available':bool(public),'publicKey':public,'subscriptions':db.execute('SELECT count(*) FROM push_subscriptions WHERE user=? AND enabled=1',(user['id'],)).fetchone()[0]});return True
    return False

def post(handler,db,server,user,path,data):
    if path.startswith('/api/security/'):
        password=str(data.get('password',''))
        if not hmac.compare_digest(server.password_hash(password,user['password'].split(':')[0]),user['password']):handler.reply(403,{'error':'Your current password is incorrect.'});return True
        db.execute('INSERT OR IGNORE INTO security(user) VALUES(?)',(user['id'],));sec=db.execute('SELECT * FROM security WHERE user=?',(user['id'],)).fetchone()
        if path!='/api/security/enable' and sec['enabled'] and not verify_totp(db,server,user,data.get('otp','')):handler.reply(403,{'error':'Enter a current authenticator code.'});return True
        if path=='/api/security/setup':
            if sec['enabled']:handler.reply(400,{'error':'Disable your current authenticator before replacing it.'});return True
            secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=');encrypted=cipher(server).encrypt(secret.encode()).decode();db.execute('UPDATE security SET pending=? WHERE user=?',(encrypted,user['id']));db.commit();handler.reply(200,{'secret':secret,'uri':'otpauth://totp/Kindred:'+quote(user['email'])+'?secret='+secret+'&issuer=Kindred'});return True
        if path=='/api/security/enable':
            if not sec['pending']:handler.reply(400,{'error':'Set up an authenticator first.'});return True
            secret=cipher(server).decrypt(sec['pending'].encode()).decode()
            if not verify_totp(db,server,user,data.get('otp',''),secret):handler.reply(400,{'error':'Authenticator code is incorrect or already used.'});return True
            db.execute('UPDATE security SET secret=pending,pending=NULL,enabled=1 WHERE user=?',(user['id'],))
        elif path=='/api/security/disable':db.execute('UPDATE security SET enabled=0,secret=NULL,pending=NULL,last_step=-1 WHERE user=?',(user['id'],))
        elif path=='/api/security/recovery':
            codes=[secrets.token_hex(10) for _ in range(8)];db.execute('UPDATE security SET recovery=? WHERE user=?',(json.dumps([server.digest(x) for x in codes]),user['id']));log(db,user,'security',user['id'],'recovery codes replaced');db.commit();handler.reply(200,{'codes':codes});return True
        elif path=='/api/security/password':
            new=str(data.get('newPassword',''))
            if not 12<=len(new)<=256:handler.reply(400,{'error':'Use 12–256 characters for the new password.'});return True
            db.execute('UPDATE users SET password=? WHERE id=?',(server.password_hash(new),user['id']));db.execute('DELETE FROM sessions WHERE user=? AND token<>?',(user['id'],user['token']))
        else:handler.reply(404,{'error':'Unknown security operation.'});return True
        log(db,user,'security',user['id'],path.rsplit('/',1)[-1]);db.commit();handler.reply(200,{'ok':True});return True
    if path=='/api/member-role':
        if user['role']!='owner' or data.get('id')==user['id'] or data.get('role') not in ('caregiver','viewer'):handler.reply(403,{'error':'Only the owner can change another member’s permissions.'});return True
        db.execute('UPDATE users SET role=? WHERE id=? AND family=? AND role<>?',(data['role'],data['id'],user['family'],'owner'));log(db,user,'members',data['id'],'role changed',after={'role':data['role']});db.commit();handler.reply(200,{'ok':True});return True
    if path in ('/api/restore-backup','/api/restore-record'):
        if user['role']!='owner':handler.reply(403,{'error':'Only the owner can restore shared records.'});return True
        family=db.execute('SELECT * FROM families WHERE id=?',(user['family'],)).fetchone()
        if data.get('revision')!=family['revision']:handler.reply(409,{'error':'The family has changed. Refresh before restoring.'});return True
        previous=json.loads(family['state']);new=json.loads(family['state']);reason=str(data.get('reason','')).strip()
        if not reason:handler.reply(400,{'error':'Enter a reason for restoring.'});return True
        if path=='/api/restore-backup':
            snapshot=db.execute('SELECT * FROM snapshots WHERE id=? AND family=?',(data.get('id'),user['family'])).fetchone()
            if not snapshot:handler.reply(404,{'error':'Backup not found.'});return True
            new=json.loads(snapshot['state'])
        else:
            row=db.execute("SELECT * FROM audit WHERE id=? AND family=? AND action='deleted'",(data.get('id'),user['family'])).fetchone()
            if not row:handler.reply(404,{'error':'Deleted record not found.'});return True
            record=json.loads(row['before']);collection=row['collection']
            if collection=='profiles':target=new['profiles']
            else:
                p=next((p for p in new['profiles'] if p['id']==row['profile']),None)
                if not p or collection not in COLLECTIONS:handler.reply(400,{'error':'Restore the parent profile first.'});return True
                target=p.setdefault(collection,[])
            if any(r['id']==record['id'] for r in target):handler.reply(409,{'error':'This record already exists.'});return True
            target.append(record)
        if not server.valid_state(new):handler.reply(400,{'error':'This snapshot cannot be restored.'});return True
        save_audit(db,user,previous,new,family['revision'],'Restore: '+reason);db.execute('UPDATE families SET state=?,revision=revision+1 WHERE id=?',(json.dumps(new),user['family']));db.commit();handler.reply(200,{'ok':True});return True
    if path in ('/api/upload-document','/api/archive-document'):
        if user['role']=='viewer':handler.reply(403,{'error':'Your account has view-only access.'});return True
        if path=='/api/archive-document':
            row=db.execute('SELECT id,name,profile FROM documents WHERE id=? AND family=?',(data.get('id'),user['family'])).fetchone()
            if not row:handler.reply(404,{'error':'Document not found.'});return True
            archived=1 if data.get('archived') else 0;db.execute('UPDATE documents SET archived=? WHERE id=?',(archived,row['id']));log(db,user,'documents',row['id'],'archived' if archived else 'restored',reason=row['name'],profile=row['profile']);db.commit();handler.reply(200,{'ok':True});return True
        try:body=base64.b64decode(data.get('body',''),validate=True)
        except (ValueError,TypeError):handler.reply(400,{'error':'Invalid document.'});return True
        name=Path(str(data.get('name','document'))).name[:180];mime='application/pdf' if body.startswith(b'%PDF-') else 'image/png' if body.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if body.startswith(b'\xff\xd8\xff') else None
        if not mime or not 0<len(body)<=5*1024*1024:handler.reply(400,{'error':'Choose a PDF, PNG, or JPEG up to 5 MB.'});return True
        family=json.loads(db.execute('SELECT state FROM families WHERE id=?',(user['family'],)).fetchone()[0])
        if data.get('profile') not in [p['id'] for p in family['profiles']]:handler.reply(400,{'error':'Sync this parent profile before uploading documents.'});return True
        if db.execute('SELECT coalesce(sum(length(body)),0) FROM documents WHERE family=?',(user['family'],)).fetchone()[0]+len(body)>250*1024*1024:handler.reply(400,{'error':'This family has reached its 250 MB document limit.'});return True
        rid=secrets.token_hex(16);db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,0)',(rid,user['family'],data['profile'],name,mime,body,str(data.get('doctor',''))[:200],str(data.get('date',''))[:30],user['name'],timestamp()));log(db,user,'documents',rid,'uploaded',after={'name':name,'size':len(body)},profile=data['profile']);db.commit();handler.reply(200,{'id':rid});return True
    if path=='/api/push-subscribe':
        sub=data.get('subscription',{});endpoint=sub.get('endpoint','');host=urlparse(endpoint).hostname or ''
        allowed=host in ('fcm.googleapis.com','updates.push.services.mozilla.com','web.push.apple.com') or host.endswith('.notify.windows.com') or host.endswith('.push.apple.com') or host.endswith('.push.services.mozilla.com')
        if not endpoint.startswith('https://') or not allowed or not isinstance(sub.get('keys'),dict) or not all(isinstance(sub['keys'].get(k),str) for k in ('auth','p256dh')):handler.reply(400,{'error':'Unsupported or invalid browser push subscription.'});return True
        try:ZoneInfo(str(data.get('timezone','UTC')))
        except (ValueError,ZoneInfoNotFoundError):handler.reply(400,{'error':'Invalid time zone.'});return True
        rid=server.digest(endpoint);db.execute('INSERT INTO push_subscriptions VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET user=excluded.user,subscription=excluded.subscription,enabled=1,timezone=excluded.timezone,escalate=excluded.escalate',(rid,user['id'],json.dumps(sub),1,data.get('timezone','UTC'),int(bool(data.get('escalate')))));db.commit();handler.reply(200,{'ok':True});return True
    if path=='/api/push-disable':db.execute('UPDATE push_subscriptions SET enabled=0 WHERE user=?',(user['id'],));db.commit();handler.reply(200,{'ok':True});return True
    return False

def push_keys(server):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    path=server.DB.parent/'vapid.pem'
    if not path.exists():
        key=ec.generate_private_key(ec.SECP256R1());pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        try:
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(pem)
        except FileExistsError:pass
    key=serialization.load_pem_private_key(path.read_bytes(),password=None);public=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    return str(path),base64.urlsafe_b64encode(public).decode().rstrip('=')

def due_events(state,now,subscription,user_id):
    events=[]
    for p in state['profiles']:
        try:zone=ZoneInfo(p.get('timezone') or subscription['timezone'])
        except ZoneInfoNotFoundError:zone=timezone.utc
        local=now.astimezone(zone);date=local.date().isoformat()
        for m in p['medications']:
            for scheduled_day in (local.date(),(local-timedelta(days=1)).date()):
                medication_date=scheduled_day.isoformat()
                if not m['active'] or m['start']>medication_date or (m['end'] and medication_date>m['end']) or (scheduled_day.weekday()+1)%7 not in m.get('weekdays',range(7)):continue
                for at in m['times']:
                    scheduled=medication_date+'T'+at
                    if any(d['medicationId']==m['id'] and d['scheduled']==scheduled for d in p['doses']):continue
                    delta=(datetime.fromisoformat(scheduled).replace(tzinfo=zone)-local).total_seconds()
                    if 0<=delta<=900:events.append((p['id']+m['id']+scheduled,'A scheduled medication is due soon. Open Kindred to review it.'))
                    if subscription['escalate'] and -3900<=delta<=-3600 and m.get('responsibleId')==user_id:events.append(('late-'+p['id']+m['id']+scheduled,'A scheduled medication is still unrecorded. Please review the care journal.'))
        for t in p['tasks']:
            start=datetime.fromisoformat(t['date']);same_day=t['date'][:10]==date
            if not t['active'] or t['date'][:10]>date or any(c['date']==date for c in t['completed']):continue
            if t['repeat']=='none' and not same_day:continue
            if t['repeat']=='weekly' and start.weekday()!=local.weekday():continue
            scheduled=datetime.combine(local.date(),start.time(),tzinfo=zone);delta=(scheduled-local).total_seconds()
            if 0<=delta<=900:events.append((p['id']+t['id']+date,'A care task or prescription renewal is due soon.'))
        for e in p['entries']:
            if e['category']=='appointments' and not e['done']:
                at=datetime.fromisoformat(e['date']);at=at.replace(tzinfo=zone) if at.tzinfo is None else at
                if 0<=(at-local).total_seconds()<=900:events.append((p['id']+e['id']+e['date'],'A care appointment is coming up soon.'))
    return events

def encrypted_backup(server):
    folder=server.DB.parent/'backups';folder.mkdir(exist_ok=True)
    name='server-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    temp=folder/(name+'.tmp')
    try:
        with server.connect() as source,sqlite3.connect(temp) as destination:source.backup(destination)
        output=folder/(name+'.sqlite3.enc');output.write_bytes(cipher(server).encrypt(temp.read_bytes()))
    finally:
        if temp.exists():temp.unlink()
    for old in sorted(folder.glob('server-*.sqlite3.enc'))[:-14]:old.unlink()

def background(server):
    def work():
        last_backup=0
        while True:
            try:
                if time.time()-last_backup>86400:
                    try:encrypted_backup(server);last_backup=time.time();RUNTIME_STATUS['lastBackup']=timestamp();RUNTIME_STATUS['backupError']=None
                    except Exception:RUNTIME_STATUS['backupError']='The automatic encrypted backup could not be created.'
                from pywebpush import webpush,WebPushException
                private,_=push_keys(server)
                with server.connect() as db:subscriptions=[dict(r) for r in db.execute("SELECT p.*,u.family,(SELECT email FROM users owner WHERE owner.family=u.family AND owner.role='owner' LIMIT 1) AS contact FROM push_subscriptions p JOIN users u ON u.id=p.user WHERE p.enabled=1")]
                for sub in subscriptions:
                    with server.connect() as db:
                        state=json.loads(db.execute('SELECT state FROM families WHERE id=?',(sub['family'],)).fetchone()[0]);events=due_events(state,datetime.now(timezone.utc),sub,sub['user'])
                    for event,body in events:
                        with server.connect() as db:
                            if db.execute('SELECT 1 FROM push_deliveries WHERE subscription=? AND event=?',(sub['id'],event)).fetchone():continue
                        try:
                            webpush(json.loads(sub['subscription']),json.dumps({'body':body,'tag':event}),vapid_private_key=private,vapid_claims={'sub':os.environ.get('KINDRED_PUSH_CONTACT') or 'mailto:'+sub['contact']},ttl=900,timeout=10)
                            RUNTIME_STATUS['pushMessagesSent']+=1;RUNTIME_STATUS['pushError']=None
                            with server.connect() as db:db.execute('INSERT OR IGNORE INTO push_deliveries VALUES(?,?,?)',(sub['id'],event,time.time()))
                        except WebPushException as error:
                            RUNTIME_STATUS['pushError']='A browser push service could not be reached. Calendar export remains available.'
                            if error.response is not None and error.response.status_code in (404,410):
                                with server.connect() as db:db.execute('DELETE FROM push_subscriptions WHERE id=?',(sub['id'],))
            except Exception:
                # Never include care contents, encryption keys or subscription URLs in logs.
                RUNTIME_STATUS['pushError']='The background reminder service is unavailable.'
            time.sleep(30)
    threading.Thread(target=work,daemon=True,name='kindred-reminders-backups').start()
