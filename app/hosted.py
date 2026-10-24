"""Single-instance hosted loraii server with admin and OBS-viewer capabilities."""
import base64,hashlib,hmac,json,os,re,secrets,sys,time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs,urlsplit,urlencode
from http.server import ThreadingHTTPServer
ADMIN_KEY=os.environ.get('ADMIN_KEY','')
VIEW_KEY=os.environ.get('VIEW_KEY','')
if len(ADMIN_KEY)<24 or len(VIEW_KEY)<24 or hmac.compare_digest(ADMIN_KEY,VIEW_KEY):
 raise SystemExit('Set separate ADMIN_KEY and VIEW_KEY secrets (at least 24 characters each).')
RELAY_KEY=os.environ.get('LORAII_RELAY_KEY') or hmac.new(ADMIN_KEY.encode(),b'loraii-relay-v1',hashlib.sha256).hexdigest()
os.environ['LORAII_RELAY_KEY']=RELAY_KEY
import core
ROOT=Path(__file__).resolve().parent
CONNECTION_FILE=core.STATE_DIR/'connections.json'
SCENE_ROUTES=['starting','gameplay','browser','break','ending','justchat','replay','highlights']
SE_SCENES=['starting','gameplay','browser','break','ending']
def valid_links(data):
 if not isinstance(data,dict):raise ValueError('Expected StreamElements settings object')
 out={}
 for name in SE_SCENES:
  link=data.get(name,'')
  if not isinstance(link,str) or len(link)>1500:raise ValueError('Invalid StreamElements link')
  if link:
   u=urlsplit(link)
   if u.scheme!='https' or u.hostname!='streamelements.com' or not re.fullmatch(r'/overlay/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/?',u.path) or u.username or u.password or u.port not in (None,443):raise ValueError('Use a full HTTPS StreamElements overlay URL')
  out[name]=link
 return out
try:connections=valid_links(json.loads(CONNECTION_FILE.read_text()))
except (OSError,ValueError,TypeError):connections=valid_links(json.loads(os.environ.get('SE_URLS_JSON','{}')))
LOGIN_ATTEMPTS={}
COOKIE_SECRET=hmac.new(ADMIN_KEY.encode(),b'loraii-cookie-v1',hashlib.sha256).digest()
def login_token():
 payload=str(int(time.time()))+':'+secrets.token_hex(16)
 return payload+':'+hmac.new(COOKIE_SECRET,payload.encode(),hashlib.sha256).hexdigest()
def valid_login_token(token):
 try:
  timestamp,nonce,signature=token.split(':');payload=timestamp+':'+nonce
  return 0<=time.time()-int(timestamp)<=900 and hmac.compare_digest(signature,hmac.new(COOKIE_SECRET,payload.encode(),hashlib.sha256).hexdigest())
 except (ValueError,TypeError,AttributeError):return False
def session(role):return hmac.new(COOKIE_SECRET,(role+(':'+VIEW_KEY if role=='viewer' else '')).encode(),hashlib.sha256).hexdigest()
VIEW_STATIC={'replay.html','se-connection.js','control-client.js','scene-copy.js','stream-scenes.js','session-stats.js','motion.js','motion.css','layout-fixes.css','emotes.js'}|{s+'.html' for s in SCENE_ROUTES}
class Handler(core.Handler):
 def public_origin(self):
  configured=os.environ.get('PUBLIC_URL') or os.environ.get('RENDER_EXTERNAL_URL')
  if configured:return configured.rstrip('/')
  return ('https' if self.headers.get('X-Forwarded-Proto')=='https' else 'http')+'://'+self.headers.get('Host','localhost')
 def role(self):
  c=SimpleCookie()
  try:c.load(self.headers.get('Cookie',''))
  except:return ''
  for name,role in [('loraii_admin','admin'),('loraii_view','viewer')]:
   if c.get(name) and hmac.compare_digest(c[name].value,session(role)):return role
  return ''
 def cookie(self,name,value):
  secure='; Secure' if self.public_origin().startswith('https://') else ''
  return name+'='+value+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000'+secure
 def redirect(self,path,cookie=None):
  self.send_response(303)
  if cookie:self.send_header('Set-Cookie',cookie)
  self.send_header('Location',path);self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers()
 def send(self,data,kind='text/html; charset=utf-8',status=200):
  if isinstance(data,str):data=data.encode()
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass
 def paired(self):return bool(self.role())
 def base_get(self):
  previous=self.client_address;self.client_address=('127.0.0.1',previous[1])
  try:return super().do_GET()
  finally:self.client_address=previous
 def do_GET(self):
  parsed=urlsplit(self.path);path=parsed.path
  if path=='/healthz':return self.reply({'ok':True,'app':'loraii-online'})
  if path=='/login':return self.send('''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>loraii / Sign in</title><style>body{margin:0;background:#09090b;color:#efede8;font:16px Arial;display:grid;min-height:100vh;place-items:center}form{width:min(360px,80vw);border-top:3px solid #c62832;padding-top:24px}input,button{box-sizing:border-box;width:100%;padding:14px;background:#161619;border:1px solid #444;color:white;margin:10px 0;font:inherit}button{background:#c62832;cursor:pointer}small{color:#aaa}</style></head><body><form action="/auth/login" method="post"><input type="hidden" name="login_token" value="__LOGIN_TOKEN__"><h1>LORAII_</h1><p>Your stream desk, online.</p><label>Controller access key<input type="password" name="key" required autocomplete="current-password"></label><button>Open controller</button><small>Use the ADMIN_KEY from your hosting service.</small></form></body></html>'''.replace('__LOGIN_TOKEN__',login_token()))
  role=self.role();view=parse_qs(parsed.query).get('view',[''])[0]
  if view:
   if not hmac.compare_digest(view,VIEW_KEY):return self.reply({'error':'Invalid OBS link'},401)
   if path not in ['/'+s+'.html' for s in SCENE_ROUTES]:return self.reply({'error':'Use a scene-specific OBS link'},403)
   args=parse_qs(parsed.query);args.pop('view',None);query=urlencode(args,doseq=True)
   return self.redirect(path+('?' + query if query else ''),self.cookie('loraii_view',session('viewer')))
  if not role:
   if path in ['/','/control.html']:return self.redirect('/login')
   return self.reply({'error':'Sign in or use a private OBS link'},401)
  if path=='/auth/logout':
   if role!='admin':return self.reply({'error':'Controller login required'},403)
   return self.send('<!doctype html><form method="post" action="/auth/logout"><button>Sign out</button></form>')
  if path=='/api/hosting':
   if role!='admin':return self.reply({'error':'Controller login required'},403)
   origin=self.public_origin();return self.reply({'scene_urls':{n:origin+'/'+n+'.html?'+urlencode({'view':VIEW_KEY}) for n in SCENE_ROUTES},'se_urls':connections,'persistent':os.environ.get('PERSISTENT_STORAGE')=='1'})
  if path=='/api/obs-collection':
   if role!='admin':return self.reply({'error':'Controller login required'},403)
   collection=json.loads((ROOT/'scene-template.json').read_text())
   collection['name']='loraii - Online HTML'
   for source in collection['sources']:
    if source.get('id')=='browser_source':
     scene=urlsplit(source['settings']['url']).path.rsplit('/',1)[-1]
     source['settings']['url']=self.public_origin()+'/'+scene+'?'+urlencode({'view':VIEW_KEY})
   return self.send(json.dumps(collection,indent=2),'application/json')
  if path=='/se-config.js':
   scene=parse_qs(parsed.query).get('scene',['gameplay'])[0];scene=scene if scene in SE_SCENES else 'gameplay'
   link=connections.get(scene) or connections.get('gameplay','')
   return self.send('window.LORAII_SE_URL='+json.dumps(link)+';window.LORAII_RELAY_KEY='+json.dumps(RELAY_KEY)+';','text/javascript; charset=utf-8')
  if path=='/session-connect.html':
   if role!='admin':return self.reply({'error':'Controller login required'},403)
   page=(ROOT/'overlays/session-connect.html').read_text();m=re.search(r'const code=(".*?");const box=',page,re.S);code=json.loads(m[1])
   code=re.sub(r'const key="[^"]+"','const key='+json.dumps(RELAY_KEY),code,count=1)
   origins=json.dumps([self.public_origin()]);code=code.replace("['http://127.0.0.1:4462','http://localhost:4462']",origins)
   page=page[:m.start(1)]+json.dumps(code)+page[m.end(1):]
   return self.send(page)
  if role=='viewer':
   key=path.lstrip('/')
   if path not in ['/api/state','/events','/api/health'] and key not in VIEW_STATIC and not key.startswith('assets/'):return self.reply({'error':'Controller login required'},403)
  return self.base_get()
 def do_POST(self):
  path=urlsplit(self.path).path;origin=self.headers.get('Origin')
  if path!='/auth/login' and origin and origin!=self.public_origin():return self.reply({'error':'Origin rejected','received_origin':origin,'expected_origin':self.public_origin(),'help':'Open the controller directly at the expected origin in a browser tab.'},403)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<=size<=1000000 or (size==0 and path!='/auth/logout'):raise ValueError('Invalid request size')
   raw=self.rfile.read(size)
   if path=='/auth/login':
    form=parse_qs(raw.decode())
    if not valid_login_token(form.get('login_token',[''])[0]):return self.send('Login page expired. <a href="/login">Open a fresh sign-in page</a> and try again.',status=403)
    address=self.client_address[0]
    now=time.time()
    with core.LOCK:
     recent=[t for t in LOGIN_ATTEMPTS.get(address,[]) if now-t<600]
     if len(recent)>=20:return self.reply({'error':'Too many failed sign-ins. Try again later.'},429)
     LOGIN_ATTEMPTS[address]=recent
    provided=form.get('key',[''])[0]
    if not hmac.compare_digest(provided,ADMIN_KEY):
     with core.LOCK:LOGIN_ATTEMPTS[address].append(now)
     return self.send('Invalid access key. <a href="/login">Try again</a>',status=401)
    with core.LOCK:LOGIN_ATTEMPTS.pop(address,None)
    return self.redirect('/control.html',self.cookie('loraii_admin',session('admin')))
   role=self.role()
   if not role:return self.reply({'error':'Sign in first'},401)
   if path=='/auth/logout':
    if role!='admin':return self.reply({'error':'Controller login required'},403)
    return self.redirect('/login','loraii_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
   if self.headers.get('X-Loraii-Control')!='1':return self.reply({'error':'Missing control header'},403)
   event=json.loads(raw)
   if not isinstance(event,dict):raise ValueError('Expected object')
   if path=='/api/connections':
    if role!='admin':return self.reply({'error':'Controller login required'},403)
    updated=valid_links(event)
    with core.LOCK:
     connections.update(updated);temp=CONNECTION_FILE.with_suffix('.tmp');temp.write_text(json.dumps(connections));temp.replace(CONNECTION_FILE)
    return self.reply({'ok':True})
   if path!='/api/control':return self.reply({'error':'Not found'},404)
   if role=='viewer' and event.get('action') not in ['live','relay-ready','emote-stats']:return self.reply({'error':'This OBS link cannot control the stream'},403)
   if event.get('action') in ['director','remote','camera','stream']:return self.reply({'error':'Desktop bridge feature is unavailable in this hosted release'},400)
   # Delegate the existing tested actions after capability/origin checks.
   import io
   original_file=self.rfile;previous=self.client_address
   self.rfile=io.BytesIO(raw);self.client_address=('127.0.0.1',previous[1]);original_origin=self.headers.get('Origin')
   if original_origin:self.headers.replace_header('Origin','http://127.0.0.1:4462')
   try:return super().do_POST()
   finally:
    self.rfile=original_file;self.client_address=previous
    if original_origin:self.headers.replace_header('Origin',original_origin)
  except (ValueError,TypeError,AttributeError) as e:return self.reply({'error':str(e)},400)
if __name__=='__main__':
 port=int(os.environ.get('PORT','10000'))
 print('loraii online listening on port '+str(port),flush=True)
 server=ThreadingHTTPServer(('0.0.0.0',port),Handler)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
