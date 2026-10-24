"""One shared, server-authoritative cute chat battle. No external dependencies."""
import math,random,re,secrets,threading,time
import core
RNG=random.Random();VISIBLE={};LAST=time.monotonic();ACC=0
GAME={'enabled':False,'phase':'off','round':0,'elapsed':0,'lobby':0,'radius':1.0,'players':[],'winner':'','message':'Type !play to join','paused':True}
MAX_PLAYERS=40

def snapshot():
 with core.LOCK:return {**GAME,'players':[dict(p) for p in GAME['players']]}
def emit():core.broadcast({'type':'arena','arena':snapshot()})
def presence(client,scene):
 if scene not in ['starting','break','ending']:return
 if not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',client):return
 with core.LOCK:
  now=time.monotonic()
  for k in list(VISIBLE):
   if now-VISIBLE[k]>10:del VISIBLE[k]
  if len(VISIBLE)<100 or client in VISIBLE:VISIBLE[client]=now

def command(action):
 with core.LOCK:
  if action=='hide':GAME['enabled']=False;GAME['phase']='off';GAME['players']=[];GAME['winner']=''
  elif action in ['lobby','reset']:
   GAME.update(enabled=True,phase='lobby',elapsed=0,lobby=0,radius=1.0,players=[],winner='',message='Type !play to join')
  elif action=='start':
   if not GAME['enabled'] or GAME['phase']!='lobby':raise ValueError('Open the lobby first.')
   if len(GAME['players'])<2:raise ValueError('At least two viewers must type !play.')
   GAME.update(phase='battle',elapsed=0,radius=1.0,winner='',round=GAME['round']+1,message='Bonk battle!')
  else:raise ValueError('Unknown arena control.')
  emit()

def join(packet):
 if packet.get('listener')!='message':return False
 event=packet.get('event') or {};d=event.get('data',event)
 if not isinstance(d,dict) or str(d.get('text','')).strip().lower()!='!play':return False
 with core.LOCK:
  if not GAME['enabled'] or GAME['phase']!='lobby' or GAME['paused']:return False
  name=str(d.get('displayName') or d.get('nick') or '').strip()[:24]
  identity=str(d.get('userId') or d.get('user-id') or d.get('nick') or name).casefold()
  if not name or not identity or len(GAME['players'])>=MAX_PLAYERS or any(p['id']==identity for p in GAME['players']):return False
  angle=RNG.random()*math.tau;r=RNG.random()**.5*.78
  GAME['players'].append({'id':identity,'name':name,'kind':RNG.randrange(4),'color':RNG.randrange(6),'x':math.cos(angle)*r,'y':math.sin(angle)*r,'hp':100,'weapon':RNG.randrange(3),'cool':RNG.random(),'hit':0,'wins':0})
  emit();return True

def step(dt):
 now=time.monotonic();active=any(now-t<8 for t in VISIBLE.values());GAME['paused']=not active
 if not active or not GAME['enabled']:return
 phase=GAME['phase']
 if phase=='lobby':
  if len(GAME['players'])>=2:
   GAME['lobby']+=dt
   if GAME['lobby']>=45:command('start')
  return
 if phase=='winner':
  GAME['elapsed']+=dt
  if GAME['elapsed']>=15:command('lobby')
  return
 if phase!='battle':return
 GAME['elapsed']+=dt;t=GAME['elapsed'];GAME['radius']=max(.08,1-t/145)
 alive=[p for p in GAME['players'] if p['hp']>0]
 for p in alive:
  p['cool']-=dt;p['hit']=max(0,p['hit']-dt)
  targets=[q for q in alive if q is not p and q['hp']>0]
  if not targets:continue
  q=min(targets,key=lambda q:(q['x']-p['x'])**2+(q['y']-p['y'])**2)
  dx,dy=q['x']-p['x'],q['y']-p['y'];dist=max(.001,math.hypot(dx,dy));speed=.12+RNG.random()*.025
  if math.hypot(p['x'],p['y'])>GAME['radius']*.8:dx,dy=-p['x'],-p['y'];dist=max(.001,math.hypot(dx,dy))
  p['x']+=dx/dist*speed*dt;p['y']+=dy/dist*speed*dt
  if math.hypot(p['x'],p['y'])>GAME['radius']:p['hp']=max(0,p['hp']-(8+t/15)*dt)
  distance=math.hypot(q['x']-p['x'],q['y']-p['y'])
  if distance<.18 and p['cool']<=0:
   q['hp']=max(0,q['hp']-RNG.uniform(7,13));q['hit']=.3;p['cool']=RNG.uniform(.6,1.3)
   q['x']=max(-1,min(1,q['x']+dx/max(dist,.001)*.045));q['y']=max(-1,min(1,q['y']+dy/max(dist,.001)*.045))
 alive=[p for p in GAME['players'] if p['hp']>0]
 if len(alive)<=1 or t>=160:
  winner=alive[0] if len(alive)==1 else max(alive,key=lambda p:p['hp']) if alive else None
  GAME.update(phase='winner',elapsed=0,winner=winner['name'] if winner else '',message=(winner['name']+' wins!' if winner else 'A spectacular draw!'))

def worker():
 while True:
  time.sleep(.1)
  with core.LOCK:
   if not GAME['enabled']:continue
   step(.1);emit()
threading.Thread(target=worker,daemon=True).start()
