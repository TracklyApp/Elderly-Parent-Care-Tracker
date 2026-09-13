"""Kindred family server. Python 3.10+, standard library only."""
import argparse
import hashlib
import hmac
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import advanced_server as advanced
DB = ROOT / 'data' / 'kindred.sqlite3'
ORIGIN = 'http://localhost:8877'
SECURE = False
STATIC = {'/':'index.html','/index.html':'index.html','/style.css':'style.css','/app.js':'app.js','/care-core.js':'care-core.js','/family.js':'family.js'}
STATIC.update({('/'+name):name for name in ('activation.js','activation.css','guide.js','guide-data.js','guide.css','output/pdf/Kindred-User-Guide.pdf','database.js','bootstrap.js','storage.js','premium-core.js','premium.js','premium.css','design.js','design.css','mobile.js','mobile.css','theme.js','theme.css','examples-data.js','examples.js','enhancements-core.js','enhancements.js','sw.js','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png')})

def connect():
    db=sqlite3.connect(DB,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');return db

def init():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS families(id TEXT PRIMARY KEY,state TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,family TEXT NOT NULL REFERENCES families(id),role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY,family TEXT NOT NULL REFERENCES families(id),expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(ip TEXT NOT NULL,at REAL NOT NULL);
        ''')
        advanced.init_schema(db)

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def valid_state(s):
    if not isinstance(s,dict) or s.get('version')!=2 or not isinstance(s.get('profiles'),list) or not 1<=len(s['profiles'])<=50:return False
    profile_ids=set()
    for p in s['profiles']:
        if not isinstance(p,dict) or not all(isinstance(p.get(k),str) for k in ('id','name','allergies','emergency')) or not p['name'].strip() or p['id'] in profile_ids:return False
        profile_ids.add(p['id'])
        details=p.get('careDetails',{})
        if not isinstance(details,dict):return False
        for key,limit in (('preferredName',80),('preferences',2000),('routine',3000),('goals',2000),('communication',1500)):
            if key in details and (not isinstance(details[key],str) or len(details[key])>limit):return False
        photo=details.get('photo','')
        if not isinstance(photo,str) or len(photo)>160000 or (photo and not re.fullmatch(r'data:image/jpeg;base64,[A-Za-z0-9+/]+=*',photo)):return False
        for key in ('entries','medications','doses','tasks','handoffs'):
            rows=p.get(key)
            if not isinstance(rows,list) or len(rows)>30000 or not all(isinstance(r,dict) and isinstance(r.get('id'),str) for r in rows):return False
            if len({r['id'] for r in rows})!=len(rows):return False
        if any(not all(isinstance(e.get(k),str) for k in ('category','title','date','author','notes','unit')) or not isinstance(e.get('done'),bool) or not isinstance(e.get('handoff'),bool) for e in p['entries']):return False
        if any(not all(isinstance(m.get(k),str) for k in ('name','dosage','instructions','start','end')) or not isinstance(m.get('active'),bool) or not isinstance(m.get('times'),list) or not m['times'] or not all(isinstance(t,str) for t in m['times']) for m in p['medications']):return False
        if any(d.get('status') not in ('taken','skipped') or not all(isinstance(d.get(k),str) for k in ('medicationId','scheduled','recordedAt','author','reason','name','dosage')) or (d['status']=='skipped' and not d['reason'].strip()) for d in p['doses']):return False
        if len({(d['medicationId'],d['scheduled']) for d in p['doses']})!=len(p['doses']):return False
        if any(not all(isinstance(t.get(k),str) for k in ('title','date','assignee','notes')) or t.get('repeat') not in ('none','daily','weekly') or t.get('kind') not in ('care','refill','appointment') or not isinstance(t.get('active'),bool) or not isinstance(t.get('completed'),list) for t in p['tasks']):return False
        if any(not all(isinstance(h.get(k),str) for k in ('from','to','createdAt','summary','notes')) or h.get('status') not in ('pending','accepted') for h in p['handoffs']):return False
        def date_ok(value):
            try:return isinstance(value,str) and bool(datetime.fromisoformat(value.replace('Z','+00:00')))
            except (ValueError,TypeError):return False
        for e in p['entries']:
            if e['category'] not in ('medication','appointments','vitals','symptoms','meals','daily','mood','sleep','incidents','doctor','expenses','team','documents') or not date_ok(e['date']):return False
            amount=e.get('amount')
            if amount is not None and (isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0):return False
            if 'vitals' in e and (not isinstance(e['vitals'],dict) or any(k not in ('systolic','diastolic','pulse','temperature','oxygen','weight') or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for k,v in e['vitals'].items())):return False
        for m in p['medications']:
            if not date_ok(m['start']) or (m['end'] and (not date_ok(m['end']) or m['end']<m['start'])) or any(not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',t) for t in m['times']) or len(set(m['times']))!=len(m['times']):return False
        for d in p['doses']:
            if not date_ok(d['scheduled']) or not date_ok(d['recordedAt']):return False
        for t in p['tasks']:
            if not date_ok(t['date']) or any(not isinstance(c,dict) or not date_ok(c.get('date')) or not date_ok(c.get('at')) or not isinstance(c.get('author'),str) for c in t['completed']):return False
        for h in p['handoffs']:
            if not date_ok(h['createdAt']) or (h['status']=='accepted' and (not isinstance(h.get('acceptedBy'),str) or not date_ok(h.get('acceptedAt')))):return False
    return advanced.valid_extras(s)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):pass  # Avoid logging care data or invitation tokens.
    def reply(self,status,data,cookie=None):
        body=json.dumps(data).encode();self.send_response(status);self.headers_common();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(body)
    def headers_common(self):
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    def auth(self,db):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return None
        token=cookie.get('kindred_session')
        if not token:return None
        return db.execute('SELECT users.*,sessions.csrf,sessions.token FROM sessions JOIN users ON users.id=sessions.user WHERE sessions.token=? AND expires>?',(digest(token.value),time.time())).fetchone()
    def session(self,db,user):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user['id'],csrf,time.time()+86400*7))
        return {'id':user['id'],'name':user['name'],'email':user['email'],'role':user['role'],'csrf':csrf},f'kindred_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800'+('; Secure' if SECURE else '')
    def do_GET(self):
        path=urlparse(self.path).path
        if path in STATIC:
            body=(ROOT/STATIC[path]).read_bytes();self.send_response(200);self.headers_common();self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'text/javascript; charset=utf-8','webmanifest':'application/manifest+json','svg':'image/svg+xml','png':'image/png','pdf':'application/pdf'}[STATIC[path].split('.')[-1]]);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if path=='/api/health':self.reply(200,{'ok':True});return
        with connect() as db:
            user=self.auth(db)
            if not user:self.reply(401,{'error':'Sign in to access your family.'});return
            if advanced.get(self,db,sys.modules[__name__],user,path):return
            if path=='/api/me':self.reply(200,{'id':user['id'],'name':user['name'],'email':user['email'],'role':user['role'],'csrf':user['csrf']})
            elif path=='/api/state':
                family=db.execute('SELECT state,revision FROM families WHERE id=?',(user['family'],)).fetchone();self.reply(200,{'state':json.loads(family['state']),'revision':family['revision']})
            elif path=='/api/members':self.reply(200,{'members':[dict(r) for r in db.execute('SELECT id,name,email,role FROM users WHERE family=?',(user['family'],))]})
            else:self.reply(404,{'error':'Not found.'})
    def do_POST(self):
        if self.headers.get('Origin')!=ORIGIN:self.reply(403,{'error':'Origin not allowed.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=10000000:raise ValueError()
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError()
        except (ValueError,UnicodeError):self.reply(400,{'error':'Invalid request.'});return
        path=urlparse(self.path).path
        try:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if advanced.recovery_post(self,db,sys.modules[__name__],path,data):return
                if path in ('/api/register','/api/login'):
                    db.execute('DELETE FROM attempts WHERE at<?',(time.time()-900,))
                    if db.execute('SELECT count(*) FROM attempts WHERE ip=?',(self.client_address[0],)).fetchone()[0]>=30:self.reply(429,{'error':'Too many attempts. Try again in 15 minutes.'});return
                    db.execute('INSERT INTO attempts VALUES(?,?)',(self.client_address[0],time.time()))
                    email=str(data.get('email','')).strip().lower();password=str(data.get('password',''))
                    if len(email)>254 or '@' not in email or len(password)<12 or len(password)>256:self.reply(400,{'error':'Enter an email and a password of 12–256 characters.'});return
                    if path=='/api/register':
                        name=str(data.get('name','')).strip()
                        if not name or len(name)>80:self.reply(400,{'error':'Enter your name (up to 80 characters).'});return
                        if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():self.reply(400,{'error':'Unable to create this account. Try signing in.'});return
                        invite=str(data.get('invite','')).strip();role='caregiver'
                        if invite:
                            invitation=db.execute('SELECT * FROM invites WHERE token=? AND expires>?',(digest(invite),time.time())).fetchone()
                            if not invitation:self.reply(400,{'error':'This invitation is invalid or expired.'});return
                            family=invitation['family'];role=invitation['role'];db.execute('DELETE FROM invites WHERE token=?',(digest(invite),))
                        else:
                            initial=data.get('state')
                            if not valid_state(initial):self.reply(400,{'error':'Invalid initial family data.'});return
                            family=secrets.token_hex(16);role='owner';db.execute('INSERT INTO families(id,state) VALUES(?,?)',(family,json.dumps(initial)))
                        uid=secrets.token_hex(16);db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,email,name,password_hash(password),family,role))
                    user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not user or not hmac.compare_digest(password_hash(password,user['password'].split(':')[0]),user['password']):self.reply(401,{'error':'Email or password is incorrect.'});return
                    if not advanced.login_check(self,db,sys.modules[__name__],user,data):return
                    result,cookie=self.session(db,user);db.commit();self.reply(200,result,cookie);return
                user=self.auth(db)
                if not user:self.reply(401,{'error':'Please sign in again.'});return
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),user['csrf']):self.reply(403,{'error':'Session verification failed. Reload and sign in again.'});return
                if advanced.post(self,db,sys.modules[__name__],user,path,data):return
                if path=='/api/logout':db.execute('DELETE FROM sessions WHERE token=?',(user['token'],));db.commit();self.reply(200,{'ok':True},'kindred_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');return
                if path=='/api/invite':
                    if user['role']!='owner':self.reply(403,{'error':'Only the family owner can create invitations.'});return
                    role=data.get('role','caregiver')
                    if role not in ('caregiver','viewer'):self.reply(400,{'error':'Choose caregiver or view-only access.'});return
                    token=secrets.token_urlsafe(24);db.execute('INSERT INTO invites(token,family,expires,role) VALUES(?,?,?,?)',(digest(token),user['family'],time.time()+172800,role));db.commit();self.reply(200,{'token':token,'expiresIn':'48 hours'});return
                if path=='/api/remove-member':
                    target=data.get('id')
                    if user['role']!='owner' or target==user['id']:self.reply(403,{'error':'Only the owner can remove another caregiver.'});return
                    member=db.execute('SELECT id FROM users WHERE id=? AND family=?',(target,user['family'])).fetchone()
                    if not member:self.reply(404,{'error':'Member not found.'});return
                    db.execute('DELETE FROM sessions WHERE user=?',(target,));db.execute('DELETE FROM users WHERE id=?',(target,));db.commit();self.reply(200,{'ok':True});return
                if path=='/api/state':
                    if user['role']=='viewer':self.reply(403,{'error':'Your account has view-only access.'});return
                    if not valid_state(data.get('state')):self.reply(400,{'error':'Invalid care data.'});return
                    row=db.execute('SELECT state,revision FROM families WHERE id=?',(user['family'],)).fetchone()
                    if data.get('revision')!=row['revision']:self.reply(409,{'error':'Another caregiver updated the journal. Review the conflicting changes.'});return
                    previous=json.loads(row['state'])
                    violation=advanced.state_rules(previous,data['state'],user)
                    if violation:self.reply(400,{'error':violation});return
                    old_handoffs={h['id']:h for p in previous['profiles'] for h in p['handoffs']}
                    for p in data['state']['profiles']:
                        for h in p['handoffs']:
                            old=old_handoffs.get(h['id'])
                            if old and old['status']=='pending' and h['status']=='accepted':
                                if old.get('toId') and old['toId']!=user['id']:self.reply(403,{'error':'Only the assigned caregiver can accept this handoff.'});return
                                if h['acceptedBy']!=user['name']:self.reply(403,{'error':'Handoff acceptance must use your signed-in name.'});return
                    changed=db.execute('UPDATE families SET state=?,revision=revision+1 WHERE id=? AND revision=?',(json.dumps(data['state']),user['family'],data.get('revision'))).rowcount
                    if not changed:self.reply(409,{'error':'Another caregiver updated the journal. Your copy is preserved; load the latest family version before continuing.'});return
                    advanced.save_audit(db,user,previous,data['state'],row['revision'],str(data.get('reason','Care record updated'))[:1000])
                    revision=db.execute('SELECT revision FROM families WHERE id=?',(user['family'],)).fetchone()[0];db.commit();self.reply(200,{'revision':revision});return
                self.reply(404,{'error':'Not found.'})
        except sqlite3.Error:self.reply(503,{'error':'Storage is temporarily unavailable. Please retry.'})
        except ImportError:self.reply(503,{'error':'Run Install dependencies.cmd to enable account encryption and push notifications.'})

def main():
    global DB,ORIGIN,SECURE
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8877);parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--origin');parser.add_argument('--db',type=Path);args=parser.parse_args()
    DB=args.db or DB;ORIGIN=args.origin or f'http://localhost:{args.port}';SECURE=ORIGIN.startswith('https://');init()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    advanced.background(sys.modules[__name__])
    print(f'Kindred is ready at {ORIGIN}',flush=True);server.serve_forever()

if __name__=='__main__':main()
