"""Private Spotify OAuth PKCE and shared playback polling. Standard library only."""
import base64,hashlib,hmac,json,os,re,secrets,threading,time
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import core
FILE=core.STATE_DIR/'spotify-private.json'
LOCK=threading.RLock();PENDING={};ERROR='';NEXT=0;TOUCH=0
try:DATA=json.loads(FILE.read_text())
except (OSError,ValueError):DATA={}
class SpotifyError(ValueError):pass

def save():
 temp=FILE.with_suffix('.tmp')
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump(DATA,f)
 os.replace(temp,FILE)

def status():
 global TOUCH
 with LOCK:
  TOUCH=time.time()
  return {'client_id':DATA.get('client_id',''),'connected':bool(DATA.get('refresh_token')),'error':ERROR,'playing':bool(core.STATE.get('media',{}).get('playing'))}

def configure(client):
 global ERROR
 if not isinstance(client,str) or not re.fullmatch('[a-fA-F0-9]{32}',client):raise SpotifyError('Paste the 32-character Spotify Client ID.')
 with LOCK:
  if DATA.get('client_id')!=client:DATA.clear();DATA['client_id']=client;clear_media()
  save();ERROR=''

def clear_media():
 with core.LOCK:
  core.STATE['media']={'playing':False,'title':'','artist':'','updated':time.time()}
  core.broadcast({'type':'state','state':core.snapshot()})

def disconnect():
 global ERROR
 with LOCK:
  client=DATA.get('client_id','');DATA.clear();DATA['client_id']=client;PENDING.clear();save();ERROR='';clear_media()

def begin(redirect):
 with LOCK:
  client=DATA.get('client_id')
  if not client:raise SpotifyError('Save your Spotify Client ID first.')
  now=time.time()
  for k in list(PENDING):
   if PENDING[k]['until']<now:del PENDING[k]
  state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
  PENDING[state]={'verifier':verifier,'redirect':redirect,'until':now+600}
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
  return state,'https://accounts.spotify.com/authorize?'+urlencode({'client_id':client,'response_type':'code','redirect_uri':redirect,'scope':'user-read-currently-playing user-read-playback-state user-modify-playback-state','state':state,'code_challenge_method':'S256','code_challenge':challenge})

def request(url,method='GET',data=None,headers=None):
 global NEXT
 try:
  with urlopen(Request(url,data=data,headers=headers or {},method=method),timeout=10) as r:
   raw=r.read();return json.loads(raw) if raw else {}
 except HTTPError as e:
  code=e.code
  if code==429:
   try:delay=int(e.headers.get('Retry-After','60'))
   except ValueError:delay=60
   NEXT=time.time()+max(5,min(delay,86400))
  messages={401:'Spotify authorization expired. Reconnect Spotify.',403:'Spotify denied access. Check Premium, app access and granted permissions.',404:'Open Spotify and play a track on your PC first.',429:'Spotify request limit reached. Retrying automatically.'}
  raise SpotifyError(messages.get(code,'Spotify is unavailable (HTTP '+str(code)+').')) from None
 except (URLError,TimeoutError,OSError,ValueError):raise SpotifyError('Cannot reach Spotify. Retrying shortly.') from None

def token(form):
 result=request('https://accounts.spotify.com/api/token','POST',urlencode(form).encode(),{'Content-Type':'application/x-www-form-urlencoded'})
 if not result.get('access_token'):raise SpotifyError('Spotify did not return an access token. Reconnect.')
 DATA['access_token']=result['access_token'];DATA['expires']=time.time()+float(result.get('expires_in',3600))-60
 if result.get('refresh_token'):DATA['refresh_token']=result['refresh_token']
 save()

def callback(state,code,cookie):
 global ERROR,NEXT,TOUCH
 with LOCK:
  if not state or not cookie or not hmac.compare_digest(state,cookie):raise SpotifyError('Spotify sign-in expired. Try Connect Spotify again.')
  pending=PENDING.pop(state,None)
  if not pending or pending['until']<time.time():raise SpotifyError('Spotify sign-in expired. Try again.')
  if not code:raise SpotifyError('Spotify connection cancelled. You can try again.')
  token({'grant_type':'authorization_code','client_id':DATA['client_id'],'code':code,'redirect_uri':pending['redirect'],'code_verifier':pending['verifier']})
  ERROR='';NEXT=0;TOUCH=time.time()
  with core.LOCK:core.STATE['manualMusic']={'enabled':False,'title':'','artist':''};core.save()

def api(path,method='GET'):
 if time.time()<NEXT:raise SpotifyError('Spotify is cooling down after a request limit. Try shortly.')
 if not DATA.get('refresh_token'):raise SpotifyError('Connect Spotify first.')
 if DATA.get('expires',0)<time.time():token({'grant_type':'refresh_token','refresh_token':DATA['refresh_token'],'client_id':DATA['client_id']})
 return request('https://api.spotify.com/v1/me/player'+path,method,headers={'Authorization':'Bearer '+DATA['access_token']})

def poll():
 global ERROR
 with LOCK:
  if not DATA.get('refresh_token'):return
  result=api('/currently-playing');item=result.get('item') or {}
  images=(item.get('album') or {}).get('images') or []
  art=images[-1].get('url','') if images else ''
  if urlsplit(art).scheme!='https':art=''
  media={'playing':bool(result.get('is_playing')) and item.get('type')=='track','title':str(item.get('name',''))[:200],'artist':', '.join(a.get('name','') for a in item.get('artists',[]))[:200],'art':art,'url':item.get('external_urls',{}).get('spotify',''),'source':'spotify','updated':time.time()}
  with core.LOCK:
   core.STATE['media']=media;core.broadcast({'type':'state','state':core.snapshot()})
  ERROR=''

def control(action):
 global NEXT
 paths={'play':('/play','PUT'),'pause':('/pause','PUT'),'next':('/next','POST'),'previous':('/previous','POST')}
 if action not in paths:raise SpotifyError('Unknown Spotify control.')
 with LOCK:api(*paths[action]);NEXT=max(NEXT,time.time()+1)

def worker():
 global ERROR,NEXT
 while True:
  time.sleep(1)
  if time.time()<NEXT:continue
  if not core.CLIENTS and time.time()-TOUCH>90:continue
  try:poll()
  except SpotifyError as e:ERROR=str(e);clear_media();NEXT=max(NEXT,time.time()+15)
  except Exception:ERROR='Spotify connection needs attention.';clear_media();NEXT=max(NEXT,time.time()+30)
  NEXT=max(NEXT,time.time()+5)
threading.Thread(target=worker,daemon=True).start()
