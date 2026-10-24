
(()=>{
if(!window.LORAII_BRIDGE||!window.loraii||document.querySelector('#controls'))return;
const stage=document.querySelector('#stage');let state=null;const baseMode=stage.dataset.scene;
const indicator=document.createElement('div');indicator.id='controlStatus';indicator.textContent='CONTROL OFFLINE';stage.append(indicator);
const events=new EventSource('/events');
events.onopen=()=>{indicator.textContent='';window.LORAII_EVENTS_READY=true;dispatchEvent(new Event('loraii-events-ready'));};events.onerror=()=>{indicator.textContent='CONTROL OFFLINE';window.LORAII_EVENTS_READY=false;dispatchEvent(new Event('loraii-events-offline'));};
function timer(){if(!state||!['starting','break'].includes(stage.dataset.scene))return;const node=document.querySelector('#countdown');if(!node)return;const t=state.timer;const left=Math.max(0,Math.ceil(t.running?t.deadline-Date.now()/1000:t.remaining));const signature=[left,t.running,stage.dataset.scene].join('|');if(node.dataset.timerSignature===signature)return;node.dataset.timerSignature=signature;node.replaceChildren();const label=document.createElement('small');label.textContent=left===0?(stage.dataset.scene==='break'?'BACK SHORTLY':'STARTING SHORTLY'):t.running?(stage.dataset.scene==='break'?'BACK IN':'LIVE IN'):'COUNTDOWN READY';const span=document.createElement('span');span.textContent=left===0?'':String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');node.append(label,span);}

function stack(){if(!state)return;const now=Date.now()/1000;const u=document.querySelector('#streamUptime'),n=document.querySelector('#nowPlaying');const stream=state.stream||{};const media=state.media||{};
if(u){u.hidden=!(stream.active&&now-stream.updated<10);if(!u.hidden){let seconds=Math.max(0,Math.floor(stream.duration/1000+now-stream.updated));u.querySelector('time').textContent=String(Math.floor(seconds/3600)).padStart(2,'0')+':'+String(Math.floor(seconds/60)%60).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}}
if(n){n.hidden=!(media.playing&&media.title&&now-media.updated<10);if(!n.hidden){const text=[media.artist,media.title].filter(Boolean).join(' — ');const label=n.querySelector('p');if(label.textContent!==text)label.textContent=text;label.title=text;let art=n.querySelector('.spotifyArt');if(!art){art=document.createElement('img');art.className='spotifyArt';art.alt='Album cover';art.width=40;art.height=40;n.prepend(art);}const url=media.source==='spotify'&&/^https:\/\//.test(media.art||'')?media.art:'';art.hidden=!url;if(url&&art.getAttribute('src')!==url)art.src=url;if(!url)art.removeAttribute('src');n.querySelector('b').hidden=!!url;let credit=n.querySelector('.spotifyCredit');if(!credit){credit=document.createElement('a');credit.className='spotifyCredit';credit.textContent='Spotify';credit.target='_blank';credit.rel='noopener';n.querySelector('small').append(' · ',credit);}credit.hidden=media.source!=='spotify';credit.href=/^https:\/\/open\.spotify\.com\//.test(media.url||'')?media.url:'https://open.spotify.com';}}}
setInterval(stack,500);

let lastStateAt=0;function apply(){lastStateAt=Date.now();window.applySessionStats?.(state);Object.assign(window.LORAII_CONFIG,state.config);window.applyLoraiiPreferences();if(stage.dataset.scene==='starting')stage.style.setProperty('--starting-photo-opacity',String(Math.max(.22,Math.min(.35,Number(state.config.background||0)/100))));window.loraiiEmotes?.set(state.config.sevenTVSet||'')?.catch(()=>{});timer();stack();window.renderStreamScene?.(state);}
events.onmessage=e=>{let m;try{m=JSON.parse(e.data)}catch{return}if(m.type==='state'){state=m.state;apply();return}if(m.type==='live'){window.onStreamLive?.(m.packet);return;}if(m.type!=='command'||(m.target!=='all'&&m.target!==stage.dataset.scene&&m.target!==baseMode))return;const d=m.data||{};
if(m.action==='moment-test')window.testEmoteMoment?.();
if(m.action==='visitor')window.loraiiEmotes?.peek();
if(m.action==='toss')try{window.loraiiEmotes?.toss(d.emote);}catch{}
if(m.action==='chat')window.loraii.message({displayName:String(d.name||'alex'),text:String(d.text||'great to see you live')});
if(m.action==='test'){const kind=d.kind||'follow';const name=String(d.name||'alex');const types={follow:['NEW FOLLOW','welcome, '+name],sub:['NEW SUB',name+' · 3 months'],gift:['GIFTED SUBS',name+' · 5 gifted subs'],raid:['RAID INCOMING',name+' + 24 friends'],tip:['THANK YOU',name+' · €5'],bits:['THANK YOU',name+' · 500 bits']};const a=types[kind];if(a)window.loraii.alert(...a);}
if(m.action==='feature')window.loraii.feature(String(d.name||'alex'),String(d.text||'thanks for hanging out'));
if(m.action==='hide-feature')document.querySelector('#featured')?.classList.remove('show');
if(m.action==='clear')window.loraii.clear();if(m.action==='skip')window.loraii.receive({listener:'event:skip'});
};setInterval(timer,250);setInterval(async()=>{if(Date.now()-lastStateAt<4000)return;try{const r=await fetch('/api/state',{cache:'no-store'});if(r.ok){state=(await r.json()).state;apply();indicator.textContent='';}}catch{}},2000);
})();
