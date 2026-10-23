#!/usr/bin/env python3
"""Local overlay control service. Standard library only; binds loopback."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import secrets,hmac,socket,re
from urllib.parse import urlsplit,parse_qs
from http.cookies import SimpleCookie
import json,queue,threading,time,os,math,base64,zlib,mimetypes,subprocess,tempfile,sys
ROOT=Path(__file__).resolve().parent
STATE_DIR=Path(os.environ.get('LORAII_DATA_DIR','/tmp/loraii-online'))
STATE_DIR.mkdir(parents=True,exist_ok=True)
STATE_FILE=STATE_DIR/'settings.json'
RELAY_KEY=os.environ['LORAII_RELAY_KEY']
LOCK=threading.RLock(); CLIENTS=set()
DEFAULT={'config':{'accent':'#c62832','chatSize':20,'chatLimit':6,'chatLifetime':30,'alertDuration':6,'clock':True,'sound':True,'motion':True,'background':12,'persistentChat':False,'hideCommands':True,'hideBots':True,'sevenTVSet':'','emoteToss':False},'timer':{'remaining':300,'running':False,'deadline':0},'privacy':False,'cameraEnabled':False,'stream':{'active':False,'duration':0,'updated':0},'media':{'playing':False,'title':'','artist':'','updated':0}}
DEFAULT.update({'plan':{'tonight':[],'upNext':'','recap':[],'highlight':'','raid':''},'credits':{'chatters':[],'followers':[],'subs':[],'gifts':[],'raids':[],'supporters':[]},'creditsStart':0,'momentUntil':0,'lastMoment':0,'liveSeen':0,'relaySeen':0})
if not STATE_FILE.exists():
 old=STATE_DIR.parent/'loraii-overlay'/'settings.json'
 if old.exists():
  try:STATE_FILE.write_bytes(old.read_bytes())
  except OSError:pass
try:
 STATE=json.loads(STATE_FILE.read_text()); STATE={**DEFAULT,**STATE};STATE['config']={**DEFAULT['config'],**STATE['config']};STATE['timer']={**DEFAULT['timer'],**STATE.get('timer',{})}
except (OSError,ValueError):STATE=json.loads(json.dumps(DEFAULT))
for group in ['plan','credits','config','timer']:
 if not isinstance(STATE.get(group),dict):STATE[group]=json.loads(json.dumps(DEFAULT[group]))
if not isinstance(STATE.get('show'),dict):STATE['show']={'index':0,'completed':[],'moments':[]}
if not isinstance(STATE.get('emoteStats'),dict):STATE['emoteStats']={}
STATE['plan']={**DEFAULT['plan'],**STATE.get('plan',{})}
STATE['credits']={**DEFAULT['credits'],**STATE.get('credits',{})}
STATE.setdefault('show',{'index':0,'completed':[],'moments':[]})
STATE['director']={'scene':'01 - Starting Soon','updated':0,'bridge':'','result':''}
STATE.setdefault('emoteStats',{})
try:
 if any(not math.isfinite(float(STATE['timer'][k])) or float(STATE['timer'][k])<0 for k in ['remaining','deadline']):raise ValueError('timer')
except (ValueError,TypeError,KeyError):STATE['timer']=dict(DEFAULT['timer'])
STATE['stream']=dict(DEFAULT['stream']);STATE['media']=dict(DEFAULT['media']);STATE['liveSeen']=0;STATE['relaySeen']=0
STATE['creditsStart']=0;STATE['momentUntil']=0
REMOTE_QUEUE=[];PREVIEW={'image':'','at':0};EMOTE_SEEN={}
PHONE_ENABLED='--phone' in sys.argv
PHONE_TOKEN=secrets.token_urlsafe(24)
SCENES=['01 - Starting Soon','02 - Gameplay','03 - Browsing','04 - Break','05 - Ending','06 - Just Chatting','07 - Instant Replay','08 - Highlights']
RECENT_LIVE={}
def snapshot():
 with LOCK:
  result=json.loads(json.dumps(STATE))
  music=result.get('manualMusic',{})
  if music.get('enabled'):result['media']={'playing':bool(music.get('title')),'title':music.get('title',''),'artist':music.get('artist',''),'updated':time.time()}
  return result
def broadcast(value):
 with LOCK:
  for q in list(CLIENTS):
   try:q.put_nowait(value)
   except queue.Full:CLIENTS.discard(q)
def save():
 with LOCK:
  temp=STATE_DIR/'settings.tmp';temp.write_text(json.dumps(STATE));os.replace(temp,STATE_FILE)
def valid_config(c):
 out={};bounds={'chatSize':(14,30),'chatLimit':(2,12),'chatLifetime':(5,120),'alertDuration':(3,15),'background':(0,30)}
 for k,(lo,hi) in bounds.items():
  if k in c:
   v=c[k]
   if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError('invalid '+k)
   out[k]=max(lo,min(hi,v))
 for k in ['clock','sound','motion','persistentChat','hideCommands','hideBots','emoteToss']:
  if k in c:
   if not isinstance(c[k],bool):raise ValueError('invalid '+k)
   out[k]=c[k]
 if 'sevenTVSet' in c:
  import re
  v=str(c['sevenTVSet']).strip()
  if v and not re.fullmatch(r'(?:https://7tv.app/emote-sets/)?[a-zA-Z0-9]{24,32}/?',v):raise ValueError('7TV set link')
  out['sevenTVSet']=v
 if 'accent' in c:
  import re
  if not re.fullmatch(r'#[0-9a-fA-F]{6}',str(c['accent'])):raise ValueError('invalid accent')
  out['accent']=c['accent']
 return out
WEB=ROOT/'overlays'
FILES={p.relative_to(WEB).as_posix():base64.b64encode(zlib.compress(p.read_bytes())).decode() for p in WEB.rglob('*') if p.is_file()}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def log_message(self,*args):pass
 def reply(self,obj,status=200):
  b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def paired(self):
  if self.client_address[0] in ['127.0.0.1','::1']:return True
  if not PHONE_ENABLED:return False
  c=SimpleCookie()
  try:c.load(self.headers.get('Cookie',''));return hmac.compare_digest(c.get('loraii_pair').value,PHONE_TOKEN) if c.get('loraii_pair') else False
  except:return False
 def do_GET(self):
  route=self.path.split('?')[0]
  if route=='/pair':
   token=parse_qs(urlsplit(self.path).query).get('key',[''])[0]
   if not PHONE_ENABLED or not hmac.compare_digest(token,PHONE_TOKEN):return self.reply({'error':'Invalid pairing link'},403)
   self.send_response(302);self.send_header('Set-Cookie','loraii_pair='+PHONE_TOKEN+'; HttpOnly; SameSite=Strict; Path=/');self.send_header('Location','/phone.html');self.send_header('Cache-Control','no-store');self.end_headers();return
  if not self.paired():return self.reply({'error':'Use the pairing URL printed by START-PHONE.cmd'},403)
  if self.client_address[0] not in ['127.0.0.1','::1'] and route not in ['/phone.html','/phone.js','/api/state','/api/preview']:return self.reply({'error':'Local only'},403)
  if route=='/api/health':return self.reply({'app':'loraii-html','version':'2.1.0','ok':True})
  if route=='/api/preview':return self.reply(PREVIEW)
  if route=='/api/state':return self.reply({'state':snapshot(),'clients':len(CLIENTS)})
  if route=='/events':
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.end_headers();q=queue.Queue(maxsize=64)
   with LOCK:CLIENTS.add(q)
   try:
    self.wfile.write(('data: '+json.dumps({'type':'state','state':snapshot()})+'\n\n').encode());self.wfile.flush()
    while True:
     try:payload=q.get(timeout=15);msg='data: '+json.dumps(payload)+'\n\n'
     except queue.Empty:msg=': keepalive\n\n'
     self.wfile.write(msg.encode());self.wfile.flush()
   except (BrokenPipeError,ConnectionResetError):pass
   finally:
    with LOCK:CLIENTS.discard(q)
   return
  if route=='/':route='/control.html'
  key=route.lstrip('/')
  preview=key.startswith('previews/')
  if preview:
   key=key[len('previews/'):]
   if key not in ['starting.html','gameplay.html','browser.html','break.html','ending.html','justchat.html','replay.html','highlights.html']:return self.send_error(404)
  if key not in FILES:return self.send_error(404)
  data=zlib.decompress(base64.b64decode(FILES[key]))
  if preview:
   page=data.decode()
   page=re.sub(r'<script>(.*?)</script>',lambda m:'' if ('frame.src=' in m[1] or 'window.LORAII_SE_URL=' in m[1] or "'loraii-session'" in m[1]) else m[0],page,flags=re.S)
   page=page.replace('<script src="/session-stats.js"></script>','').replace('<script src="/se-connection.js"></script>','')
   page=re.sub(r'<script src="/se-config.js[^"]*"></script>','',page)
   page=page.replace('</body>','<script src="/preview-client.js"></script></body>')
   if '/preview-client.js' not in page:page+='<script src="/preview-client.js"></script>'
   data=page.encode()
  self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(key)[0] or 'application/octet-stream');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_POST(self):
  if self.path!='/api/control':return self.send_error(404)
  # A custom header plus exact same-origin requests protects browser-based controls.
  if not self.paired():return self.reply({'error':'Pair this phone first'},403)
  local=self.client_address[0] in ['127.0.0.1','::1']
  origin=self.headers.get('Origin')
  if self.headers.get('X-Loraii-Control')!='1' or origin not in (None,'http://127.0.0.1:4462','http://localhost:4462','http://'+self.headers.get('Host','')):return self.reply({'error':'Forbidden'},403)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=(1000000 if local else 16384):raise ValueError('request size')
   event=json.loads(self.rfile.read(length));action=event.get('action');target=event.get('target','all')
   if target not in ['all','live','camera-top-right','browser','browser-no-cam','starting','break','ending','justchat','replay','highlights']:raise ValueError('target')
   if not local and action not in ['remote','show','timer','moment','feature','hide-feature']:return self.reply({'error':'Desktop-only action'},403)
   if not local and action=='show' and event.get('op') not in ['mark','next']:return self.reply({'error':'Desktop-only operation'},403)
   with LOCK:
    if action=='config':STATE['config'].update(valid_config(event.get('config',{})));save();broadcast({'type':'state','state':snapshot()})
    elif action=='director':
     if not local:raise ValueError('Local bridge only')
     op=event.get('op');d=STATE['director'];identifier=str(event.get('id',''))[:100]
     if op=='heartbeat':
      while REMOTE_QUEUE and time.time()-REMOTE_QUEUE[0].get('at',0)>30:REMOTE_QUEUE.pop(0)
      if d['bridge'] not in ['',identifier] and time.time()-d['updated']<5:return self.reply({'ok':True,'leader':False})
      d['bridge']=identifier;d['updated']=time.time()
      if event.get('scene') in SCENES:d['scene']=event['scene']
      broadcast({'type':'state','state':snapshot()});return self.reply({'ok':True,'leader':True,'command':REMOTE_QUEUE[0] if REMOTE_QUEUE else None})
     if identifier!=d['bridge']:raise ValueError('Not the active bridge')
     if op=='preview':
      image=str(event.get('image',''))
      if not image.startswith(('data:image/jpeg;base64,','data:image/jpg;base64,')) or len(image)>900000:raise ValueError('Invalid preview')
      PREVIEW.update(image=image,at=time.time())
     elif op=='ack':
      if REMOTE_QUEUE and REMOTE_QUEUE[0]['id']==event.get('commandId'):REMOTE_QUEUE.pop(0)
      d['result']=str(event.get('message',''))[:250];broadcast({'type':'state','state':snapshot()})
     else:raise ValueError('Bridge operation')
    elif action=='remote':
     if time.time()-STATE['director']['updated']>5:raise ValueError('Open the desktop controller and connect OBS first')
     kind=event.get('kind');value=str(event.get('value',''))[:100]
     if kind not in ['clip','playlast']:raise ValueError('Switch scenes directly in OBS')
     if len(REMOTE_QUEUE)>=5:raise ValueError('Command queue is full')
     REMOTE_QUEUE.append({'id':secrets.token_hex(12),'kind':kind,'value':value,'at':time.time()});STATE['director']['result']='Queued for OBS'
    elif action=='emote-stats':
     identifier=str(event.get('id') or '')[:220]
     if not identifier:return self.reply({'ok':True})
     now=time.time()
     for k in list(EMOTE_SEEN):
      if now-EMOTE_SEEN[k]>120:del EMOTE_SEEN[k]
     if identifier in EMOTE_SEEN:return self.reply({'ok':True})
     EMOTE_SEEN[identifier]=now
     counts=event.get('counts',{})
     if not isinstance(counts,dict) or len(counts)>100:raise ValueError('Counts')
     for name,count in counts.items():
      if not isinstance(count,int) or isinstance(count,bool) or not 1<=count<=100:continue
      name=str(name)[:80]
      if name in STATE['emoteStats'] or len(STATE['emoteStats'])<2000:STATE['emoteStats'][name]=STATE['emoteStats'].get(name,0)+count
     save();broadcast({'type':'state','state':snapshot()})
    elif action=='show':
     op=event.get('op');show=STATE['show'];items=STATE.get('plan',{}).get('tonight',[])
     if op=='next':
      index=show['index']
      if index<len(items):
       label=items[index]
       if label not in show['completed']:show['completed'].append(label)
       show['index']=min(len(items),index+1)
     elif op=='restart':show['index']=0;show['completed']=[]
     elif op=='mark':
      entry={'id':str(time.time_ns()),'at':time.time(),'title':str(event.get('title') or 'Stream moment')[:100],'path':str(event.get('path') or '')[:1000]}
      show['moments'].append(entry);show['moments']=show['moments'][-100:]
     elif op=='remove':show['moments']=[m for m in show['moments'] if m['id']!=event.get('id')]
     elif op=='reset':STATE['show']={'index':0,'completed':[],'moments':[]};STATE['emoteStats']={}
     else:raise ValueError('show operation')
     save();broadcast({'type':'state','state':snapshot()})
    elif action=='plan':
     v=event.get('plan',{});STATE['plan']={'tonight':[str(x)[:100] for x in v.get('tonight',[])[:3] if str(x).strip()],'upNext':str(v.get('upNext',''))[:120],'recap':[str(x)[:120] for x in v.get('recap',[])[:3] if str(x).strip()],'highlight':str(v.get('highlight',''))[:160],'raid':str(v.get('raid',''))[:100]};save();broadcast({'type':'state','state':snapshot()})
    elif action=='credits':
     op=event.get('op')
     if op=='start' and not any(STATE['credits'].values()):raise ValueError('No live session names recorded yet.')
     if op=='start':STATE['creditsSnapshot']=json.loads(json.dumps(STATE['credits']));STATE['creditsStart']=time.time();broadcast({'type':'state','state':snapshot()})
     elif op=='stop':STATE['creditsStart']=0;broadcast({'type':'state','state':snapshot()})
     elif op=='reset':STATE['credits']={k:[] for k in DEFAULT['credits']};STATE['creditsStart']=0;STATE['emoteStats']={};STATE['show']={'index':0,'completed':[],'moments':[]};save();broadcast({'type':'state','state':snapshot()})
     else:raise ValueError('credits operation')
    elif action=='moment':
     if event.get('enabled'):
      if time.time()-STATE.get('lastMoment',0)<30:raise ValueError('Emote moment has a 30-second cooldown.')
      STATE['lastMoment']=time.time();STATE['momentUntil']=time.time()+20
     else:STATE['momentUntil']=0
     broadcast({'type':'state','state':snapshot()})
    elif action=='relay-ready':
     if event.get('key')!=RELAY_KEY:raise ValueError('Invalid session relay')
     STATE['relaySeen']=time.time();broadcast({'type':'state','state':snapshot()})
    elif action=='live':
     if event.get('key')!=RELAY_KEY:raise ValueError('Invalid session relay')
     packet=event.get('data',{});kind=packet.get('listener','');e=packet.get('event',{});now=time.time()
     if kind not in ['message','delete-message','delete-messages','follower-latest','subscriber-latest','raid-latest','cheer-latest','tip-latest']:raise ValueError('event type')
     STATE['liveSeen']=now;STATE['relaySeen']=now
     identifier=str(packet.get('id') or ((e.get('data') or e).get('msgId') if isinstance(e,dict) else '') or e.get('_id') or '')[:220]
     for k in list(RECENT_LIVE):
      if now-RECENT_LIVE[k]>60:del RECENT_LIVE[k]
     if identifier and identifier in RECENT_LIVE:return self.reply({'ok':True,'duplicate':True})
     if identifier:RECENT_LIVE[identifier]=now
     credit=None;name=''
     if kind=='message':
      d=e.get('data',e);name=str(d.get('displayName') or d.get('nick') or '')[:100];credit='chatters'
     else:
      name=str((e.get('sender') or e.get('name','')) if e.get('gifted') or e.get('bulkGifted') else e.get('name',''))[:100]
      credit={'follower-latest':'followers','subscriber-latest':'gifts' if e.get('gifted') or e.get('bulkGifted') else 'subs','raid-latest':'raids','cheer-latest':'supporters','tip-latest':'supporters'}.get(kind)
     if credit and name and len(STATE['credits'][credit])<300 and name.lower() not in ['streamelements','nightbot','streamlabs','moobot']:
      if not any(x.lower()==name.lower() for x in STATE['credits'][credit]):STATE['credits'][credit].append(name);save()
     broadcast({'type':'live','packet':packet});broadcast({'type':'state','state':snapshot()})
    elif action=='stream':
     v=event.get('data',{});duration=float(v.get('duration',0))
     if not math.isfinite(duration) or duration<0:raise ValueError('duration')
     STATE['stream']={'active':bool(v.get('active')),'duration':duration,'updated':time.time()};broadcast({'type':'state','state':snapshot()})
    elif action=='music-override':
     m=event.get('music',{})
     if type(m.get('enabled')) is not bool or not isinstance(m.get('title',''),str) or not isinstance(m.get('artist',''),str):raise ValueError('Invalid music override')
     STATE['manualMusic']={'enabled':m['enabled'],'title':m.get('title','')[:200],'artist':m.get('artist','')[:200]};save();broadcast({'type':'state','state':snapshot()})
    elif action=='media':
     v=event.get('data',{});STATE['media']={'playing':bool(v.get('playing')),'title':str(v.get('title',''))[:200],'artist':str(v.get('artist',''))[:200],'updated':time.time()};broadcast({'type':'state','state':snapshot()})
    elif action=='camera':
     if not isinstance(event.get('enabled'),bool):raise ValueError('camera switch')
     STATE['cameraEnabled']=event['enabled'];broadcast({'type':'state','state':snapshot()})
    elif action=='privacy':STATE['privacy']=bool(event.get('enabled'));broadcast({'type':'state','state':snapshot()})
    elif action=='timer':
     t=STATE['timer'];remaining=max(0,t['deadline']-time.time()) if t['running'] else t['remaining'];op=event.get('op')
     if op=='start':
      duration=float(event.get('seconds',300))
      if not math.isfinite(duration) or not 1<=duration<=7200:raise ValueError('Timer duration must be 1–7200 seconds')
      remaining=duration;t.update(remaining=remaining,running=True,deadline=time.time()+remaining)
     elif op=='pause':t.update(remaining=remaining,running=False)
     elif op=='resume':t.update(running=True,deadline=time.time()+remaining)
     elif op=='add':remaining=min(7200,remaining+60);t.update(remaining=remaining,deadline=time.time()+remaining)
     elif op=='reset':
      duration=float(event.get('seconds',300))
      if not math.isfinite(duration) or not 1<=duration<=7200:raise ValueError('Timer duration must be 1–7200 seconds')
      t.update(remaining=duration,running=False,deadline=0)
     else:raise ValueError('timer operation')
     save();broadcast({'type':'state','state':snapshot()})
    elif action in ['test','chat','feature','clear','skip','hide-feature','toss','visitor','moment-test']:
     broadcast({'type':'command','target':target,'action':action,'data':event.get('data',{})})
    else:raise ValueError('action')
   self.reply({'ok':True})
  except (ValueError,TypeError,AttributeError,OverflowError) as e:self.reply({'error':str(e)},400)
