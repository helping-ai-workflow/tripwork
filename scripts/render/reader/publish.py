"""The publish build's second script (v1.2 spec section 5). Appended by
render_reader(build="publish") only; the check build never carries it.

On a phone the day's fold is rebuilt on native scroll + position:sticky and the
day-to-day swipe becomes a stacked glide. The H1c fold animated transform / clip-path
and desynced on iOS and Chromium with the map open. Lessons from the v4 regression,
kept in the script: never widen .pmap, translate only while a swipe is in flight, and
no per-frame variable inherited down the tree. Everything that restructures or adds a
gesture is gated by (max-width:1023px); the desktop publish page is the check page.

Whitelisted for the export gate by hash (scripts/export_gate.py::_script_hashes).
The theme carry is not here: it runs at every width and lives with the page (v1.2 Task 7).
"""

PUBLISH_JS = r"""(()=>{if(!matchMedia('(max-width:1023px)').matches)return;
const days=[...document.querySelectorAll('section.page.day')];if(days.length<1)return;
document.documentElement.classList.add('v4');
// one native scroller per day holds the calendar, the title row, the map and the list card: the calendar
// scrolls away, the title row + map + card's top edge stick (position:sticky), the list passes under them.
// Scrolling and sticking are done by the browser's scrolling thread together (iOS and Android alike),
// so nothing can drift apart -- no scroll-driven transform or clip-path is left in the fold.
const T=document.createElement('div');T.className='track';days[0].before(T);
days.forEach(d=>{T.appendChild(d);const dash=d.querySelector('.dash'),pcal=d.querySelector('.pcal'),ym=pcal.querySelector('.ymrow'),
  dh=pcal.querySelector('.dh'),pmap=d.querySelector('.pmap'),lcap=d.querySelector('.lcap'),card=d.querySelector('.plist'),lfoot=d.querySelector('.lfoot');
  const vs=document.createElement('div');vs.className='vs plist';const body=document.createElement('div');body.className='vbody';
  const stk=document.createElement('div');stk.className='stk';card.classList.add('pcard');
  dash.prepend(ym);const pw=document.createElement('div');pw.className='pwrap';pw.append(pmap);stk.append(dh,pw,lcap);body.append(stk,card);vs.append(pcal,body);lfoot.before(vs);
  // a stop opened is an anchor jump: it lands below what covers the list's top -- .stk (the title
  // row, the map) and, hanging under it, the card's top edge and its fade (.lcap's ::after and
  // ::before, read from the page) -- kept as the map row opens and closes
  const reach=()=>{const f=getComputedStyle(lcap,'::before');return (parseFloat(f.top)||0)+(parseFloat(f.height)||0)};
  const pad=()=>{vs.style.scrollPaddingTop=(stk.offsetHeight+reach())+'px'};pad();if(window.ResizeObserver)new ResizeObserver(pad).observe(stk);
  const n=dh.querySelector('.dn');if(n)n.innerHTML=n.textContent.replace(/(\d+)/,'<span class="dg"><i>$1</i></span>')});
const st=document.createElement('style');st.textContent=`
@media (max-width:1023px){
.v4 .track{display:none;position:fixed;inset:0;background:var(--bg)}
.v4 body:has(.pgr[id^="pg-d"]:checked) .track{display:block}
.v4 .track>.page.day{display:block!important;position:absolute;inset:0;background:transparent;opacity:0;pointer-events:none}
.v4 .track>.page.day.on{opacity:1;pointer-events:auto;z-index:1}.v4 .track>.page.day.to{opacity:1;z-index:2}
/* the fold, rebuilt: nothing is animated by the scroll position any more */
.v4 .page.day :is(.mini,.mini .g,.dh,.pmap,.lcap){animation:none!important;transform:none!important;clip-path:none!important}
.v4 .page.day .vs.plist{flex:1 1 auto;min-height:0;margin:0 -1px;padding:0 1px;overflow-y:auto;overscroll-behavior:contain;
  background:transparent;box-shadow:none;border-radius:0 0 15px 15px;clip-path:none!important;animation:none!important;scroll-timeline:--lst y}
.v4 .page.day .vs.plist::after{content:none}
/* the calendar lies over the title row: the current day's glow reaches past its foot as it always has;
   by the time the title row sticks, the calendar has left the scroller */
.v4 .page.day .pcal{position:relative;z-index:4}
/* folded, the glow must not hang below the scroller's top: the window closes over the first half */
.v4 .page.day .pcal{clip-path:inset(-30px -30px -18px -30px);animation:glowclip linear both;animation-timeline:--lst;animation-range:0px calc(var(--fold) / 2)}
@keyframes glowclip{to{clip-path:inset(-30px -30px 0px -30px)}}
.v4 .page.day .vbody{min-height:100%;display:flex;flex-direction:column}
.v4 .page.day .stk{position:sticky;top:0;z-index:3;flex:none}
/* what the list passes under is opaque, 1 px wider each side (the card's side lines run there) */
.v4 .page.day .dh{margin:0 -1px;padding:8px 1px 12px;background:var(--bg)}
.v4 .page.day .pwrap{margin:0 -1px;padding:0 1px 8px;background:var(--bg);position:relative}
/* ...and under the card's cap, whose rounded corners would show the card's straight side lines */
.v4 .page.day .pwrap::after{content:"";position:absolute;left:0;right:0;top:100%;height:14px;background:var(--bg)}
.v4 .page.day .pmap{margin:0}
.v4 .page.day .pcard.plist{flex:1 0 auto;margin-top:0;padding-top:12px;overflow:visible;min-height:0;clip-path:none!important;animation:none!important;scroll-timeline:none}
.v4 .page.day .pcard.plist::after{content:none}
.v4 .page.day .lfoot::after{content:"";position:absolute;left:0;right:0;bottom:0;height:16px;border-radius:0 0 14px 14px;box-shadow:0 0 0 1px var(--rule);clip-path:inset(0 -2px -2px -2px);pointer-events:none}
.v4 .page.day:has(.zck:checked) .stk{z-index:10}.v4 .page.day:has(.drv:target,.pz:checked) :is(.stk,.pcal){z-index:auto}
.v4 .page.day .dg{display:inline-block;overflow:hidden;vertical-align:top;height:1.25em;line-height:1.25em;position:relative;top:1px}
.v4 .page.day .dg i{display:inline-block;font-style:normal}
/* while a swipe runs the moving parts get their own layers; nothing else is restyled per frame */
.v4 .track>.page.day.sw :is(.pwrap,.lcap,.pcard,.lfoot){will-change:translate}
.v4 .track>.page.day.to:not(.half) :is(.ymrow,.pcal,.dh){opacity:0}
.v4 .track>.page.day.on.half :is(.ymrow,.pcal,.dh){opacity:0}
}`;document.head.appendChild(st);
const radio=d=>document.getElementById('pg-'+d.dataset.pg);
const fold=d=>{const m=d.querySelector('.pcal .mini');return m?m.offsetHeight:0};
const vsOf=d=>d.querySelector('.vs');
let cur=-1;
const show=i=>{days.forEach((d,j)=>{d.classList.toggle('on',j===i);d.classList.remove('to')});cur=i};
const prep=(i,j)=>{const a=vsOf(days[i]),b=vsOf(days[j]),away=a.scrollTop>=fold(days[i])/2;   // the neighbour opens as this day is
  b.style.scrollBehavior='auto';b.scrollTop=away?fold(days[j]):0;b.style.scrollBehavior='';days[j].classList.add('to')};
const MOVE='.pwrap,.lcap,.pcard,.lfoot',DUR=240,EASE='cubic-bezier(.2,.7,.2,1)';
const parts=d=>[...d.querySelectorAll(MOVE)];
// f: 0..1 of the way to day j in direction dir (+1 next, -1 previous); the edge gives a little, nothing behind
const paint=(i,j,dir,f)=>{const W=innerWidth,a=days[i];
  parts(a).forEach(e=>e.style.translate=(-dir*f*W)+'px 0');
  {const h=j!=null&&f>=.5;if(a.classList.contains('half')!==h){a.classList.toggle('half',h);if(j!=null)days[j].classList.toggle('half',h)}}
  const ta=a.querySelector('.dht'),ga=a.querySelector('.dg i');
  if(j==null){if(ta)ta.style.opacity='';if(ga)ga.style.translate='';return}
  const b=days[j];parts(b).forEach(e=>e.style.translate=(dir*(1-f)*W)+'px 0');
  const tb=b.querySelector('.dht'),gb=b.querySelector('.dg i');
  if(ta)ta.style.opacity=Math.max(0,1-2*f);if(tb)tb.style.opacity=Math.max(0,2*f-1);
  if(ga)ga.style.translate='0 '+(-110*dir*Math.min(1,2*f))+'%';if(gb)gb.style.translate='0 '+(110*dir*Math.min(1,Math.max(0,2-2*f)))+'%'};
const clear=d=>{parts(d).forEach(e=>{e.style.translate='';e.getAnimations().forEach(x=>x.cancel())});
  [d.querySelector('.dht'),d.querySelector('.dg i')].forEach(e=>{if(e){e.style.opacity='';e.style.translate='';e.getAnimations().forEach(x=>x.cancel())}})};
let busyGlide=false;
// glide from f0 to 1 (commit) or 0 (back) with compositor animations; the header swaps when the glide crosses the half
const glide=(i,j,dir,f0,commit)=>{busyGlide=true;days[i].classList.add('sw');if(j!=null)days[j].classList.add('sw');const W=innerWidth,f1=commit?1:0,o={duration:DUR,easing:EASE,fill:'forwards'};
  const run=(els,from,to)=>els.forEach(e=>e.animate([{translate:from+'px 0'},{translate:to+'px 0'}],o));
  run(parts(days[i]),-dir*f0*W,-dir*f1*W);
  if(j!=null){run(parts(days[j]),dir*(1-f0)*W,dir*(1-f1)*W);
    const ta=days[i].querySelector('.dht'),tb=days[j].querySelector('.dht'),ga=days[i].querySelector('.dg i'),gb=days[j].querySelector('.dg i');
    if(commit){if(ta)ta.animate([{opacity:Math.max(0,1-2*f0)},{opacity:0,offset:f0<.5?.5:1}].concat(f0<.5?[{opacity:0}]:[]),o);
      if(tb)tb.animate([{opacity:Math.max(0,2*f0-1)},{opacity:1}],o);
      if(ga)ga.animate([{translate:'0 '+(-110*dir*Math.min(1,2*f0))+'%'},{translate:'0 '+(-110*dir)+'%'}],o);
      if(gb)gb.animate([{translate:'0 '+(110*dir*Math.min(1,Math.max(0,2-2*f0)))+'%'},{translate:'0 0%'}],o)}
    else{if(ta)ta.animate([{opacity:Math.max(0,1-2*f0)},{opacity:1}],o);if(tb)tb.animate([{opacity:Math.max(0,2*f0-1)},{opacity:0}],o);
      if(ga)ga.animate([{translate:'0 '+(-110*dir*Math.min(1,2*f0))+'%'},{translate:'0 0%'}],o);
      if(gb)gb.animate([{translate:'0 '+(110*dir*Math.min(1,Math.max(0,2-2*f0)))+'%'},{translate:'0 '+(110*dir)+'%'}],o)}
    // the top row / calendar / title row swap where the slide crosses the half (time read off the easing, close enough)
    const hh=on=>[days[i],days[j]].forEach(d=>d.classList.toggle('half',on));
    if(commit&&f0<.5)setTimeout(()=>hh(true),DUR*.35*(.5-f0)/.5);if(!commit&&f0>=.5)setTimeout(()=>hh(false),DUR*.35*(f0-.5)/.5)}
  setTimeout(()=>{if(commit&&j!=null){show(j);const r=radio(days[j]);if(!r.checked)r.checked=true}
    days.forEach(clear);days.forEach(d=>d.classList.remove('to','sw','half'));busyGlide=false},DUR+20)};
// a day chosen elsewhere: the ‹ › and the stamps glide to it, the home just shows it
document.addEventListener('change',e=>{const r=e.target;if(!r.classList||!r.classList.contains('pgr'))return;
  const id=r.id.replace(/^pg-/,'').replace(/f$/,''),j=days.findIndex(d=>d.dataset.pg===id);
  if(j<0){cur=-1;return}
  if(cur<0||busyGlide||j===cur){show(j);return}
  const i=cur;prep(i,j);glide(i,j,j>i?1:-1,0,true)});
const init=days.findIndex(d=>radio(d).checked);if(init>=0)show(init);
// the swipe: sideways only within 30 deg of horizontal; anything steeper is the day's own scroll
const ANG=Math.tan(30*Math.PI/180);let s=null;
// Z1: a zoomed map follows a downward drag, its backdrop fades, past half (or a flick) it closes
// (a photo has its own layer since v2.2, below)
// -- only from the top: a split day's zoomed view scrolls, and scrolled down a downward drag scrolls it back
let z=null;
document.addEventListener('touchstart',e=>{z=null;const box=document.querySelector('.zck:checked');if(!box||e.touches.length!==1||e.target.closest('.zbar a'))return;
  const layer=box.closest('.mv'),q=e.touches[0];if(!layer||layer.scrollTop>0)return;z={box,layer,bg:layer.querySelector('.zbg'),y:q.clientY,x:q.clientX,mode:null,v:[],dy:0}},{passive:true});
document.addEventListener('touchmove',e=>{if(!z||z.mode==='n')return;if(e.touches.length!==1){if(z.mode==='y')zEnd();else z=null;return}
  const q=e.touches[0],dy=q.clientY-z.y,dx=q.clientX-z.x;
  if(!z.mode){if(Math.abs(dx)<4&&Math.abs(dy)<4)return;z.mode=(dy>0&&Math.abs(dx)<=Math.abs(dy)*ANG)?'y':'n';if(z.mode==='n')return}
  e.preventDefault();z.dy=Math.max(0,dy);const H=innerHeight;z.layer.style.translate='0 '+z.dy+'px';if(z.bg)z.bg.style.opacity=String(Math.max(0,1-z.dy/H));
  z.v.push([e.timeStamp,q.clientY]);if(z.v.length>5)z.v.shift()},{passive:false});
function zEnd(){if(!z||z.mode!=='y'){z=null;return}const s=z,H=innerHeight,v=s.v;z=null;
  const vel=v.length>1?(v[v.length-1][1]-v[0][1])/Math.max(1,v[v.length-1][0]-v[0][0]):0,go=s.dy>H/2||vel>.5,o={duration:200,easing:'cubic-bezier(.2,.7,.2,1)',fill:'forwards'};
  const a=s.layer.animate([{translate:'0 '+s.dy+'px'},{translate:'0 '+(go?H:0)+'px'}],o);if(s.bg)s.bg.animate([{opacity:Math.max(0,1-s.dy/H)},{opacity:go?0:1}],o);
  a.onfinish=()=>{if(go)s.box.checked=false;s.layer.getAnimations().forEach(x=>x.cancel());if(s.bg)s.bg.getAnimations().forEach(x=>x.cancel());s.layer.style.translate='';if(s.bg)s.bg.style.opacity=''}}
document.addEventListener('touchend',zEnd,{passive:true});document.addEventListener('touchcancel',zEnd,{passive:true});
const blocked=t=>t.closest('.chips')||document.querySelector('.zck:checked,.pzx,.drv:target');
// a touch that starts at the screen edge is the phone's own back gesture (iOS: the left edge; Android
// gesture navigation: either edge): the page's swipes leave it alone, or both run and the pages stack
const edge=p=>p.clientX<24||p.clientX>innerWidth-24;
T.addEventListener('touchstart',e=>{s=null;if(busyGlide||e.touches.length!==1||cur<0||blocked(e.target)||edge(e.touches[0]))return;
  const p=e.touches[0];s={x:p.clientX,y:p.clientY,mode:null,v:[],j:null}},{passive:true});
T.addEventListener('touchmove',e=>{if(!s||s.mode==='y')return;const p=e.touches[0],dx=p.clientX-s.x,dy=p.clientY-s.y;
  if(!s.mode){if(Math.abs(dx)<4&&Math.abs(dy)<4)return;s.mode=Math.abs(dy)<=Math.abs(dx)*ANG?'x':'y';if(s.mode==='y')return;days[cur].classList.add('sw')}
  e.preventDefault();const dir=dx<0?1:-1,j=cur+dir,W=innerWidth;
  if(j!==s.j){if(s.j!=null){clear(days[s.j]);days[s.j].classList.remove('to','sw','half')}s.j=(j>=0&&j<days.length)?j:null;if(s.j!=null){prep(cur,s.j);days[s.j].classList.add('sw')}}
  s.dir=dir;s.f=s.j==null?Math.min(.12,Math.abs(dx)/4/W):Math.min(1,Math.abs(dx)/W);paint(cur,s.j,dir,s.f);
  s.v.push([e.timeStamp,p.clientX]);if(s.v.length>5)s.v.shift();s.dx=dx},{passive:false});
const fin=()=>{if(!s||s.mode!=='x'){s=null;return}const W=innerWidth,v=s.v,f=s.f||0;
  const vel=v.length>1?(v[v.length-1][1]-v[0][1])/Math.max(1,v[v.length-1][0]-v[0][0]):0;
  const go=s.j!=null&&(Math.abs(s.dx)>W/2||(Math.abs(vel)>.5&&Math.sign(vel)===Math.sign(s.dx)));
  const j=s.j,dir=s.dx<0?1:-1;s=null;days.forEach(clear);glide(cur,j,dir,f,go)};
T.addEventListener('touchend',fin,{passive:true});T.addEventListener('touchcancel',fin,{passive:true});
// a sub-screen (住宿 / 入境規定 / 行前清單) slides off to the right over the home, iOS-style
const SUBS=['lodging','advisory','checklist'],home=document.querySelector('.page.home');let u=null;
const subOn=()=>{const r=document.querySelector('input[name=pg]:checked');const id=r&&r.id.slice(3);return SUBS.includes(id)?document.querySelector('.page[data-pg="'+id+'"]'):null};
document.addEventListener('touchstart',e=>{u=null;const p=subOn();if(!p||e.touches.length!==1||e.target.closest('.chips,input,textarea')||edge(e.touches[0]))return;
  const q=e.touches[0];u={p,x:q.clientX,y:q.clientY,mode:null,v:[],dx:0}},{passive:true});
document.addEventListener('touchmove',e=>{if(!u||u.mode==='y')return;const q=e.touches[0],dx=q.clientX-u.x,dy=q.clientY-u.y;
  if(!u.mode){if(Math.abs(dx)<4&&Math.abs(dy)<4)return;u.mode=(dx>0&&Math.abs(dy)<=Math.abs(dx)*ANG)?'x':'y';if(u.mode==='y')return;
    home.style.display='block';home.style.position='fixed';home.style.inset='0';home.style.zIndex='1';
    u.p.style.position='fixed';u.p.style.inset='0';u.p.style.zIndex='2';u.p.style.boxShadow='-8px 0 24px rgba(0,0,0,.12)'}
  e.preventDefault();u.dx=Math.max(0,dx);u.p.style.translate=u.dx+'px 0';u.v.push([e.timeStamp,q.clientX]);if(u.v.length>5)u.v.shift()},{passive:false});
const subEnd=()=>{if(!u||u.mode!=='x'){u=null;return}const s=u,W=innerWidth,v=s.v;u=null;
  const vel=v.length>1?(v[v.length-1][1]-v[0][1])/Math.max(1,v[v.length-1][0]-v[0][0]):0,go=s.dx>W/2||vel>.5;
  const a=s.p.animate([{translate:s.dx+'px 0'},{translate:(go?W:0)+'px 0'}],{duration:240,easing:'cubic-bezier(.2,.7,.2,1)',fill:'forwards'});
  a.onfinish=()=>{if(go){const r=document.getElementById('pg-home');r.checked=true;r.dispatchEvent(new Event('change',{bubbles:true}))}
    a.cancel();['translate','position','inset','zIndex','boxShadow'].forEach(k=>s.p.style[k]='');['display','position','inset','zIndex'].forEach(k=>home.style[k]='')}};
document.addEventListener('touchend',subEnd,{passive:true});document.addEventListener('touchcancel',subEnd,{passive:true});
})();
// every width: the theme is carried, today opens during the trip (T1), 返回 lands on the overview (B1)
(()=>{const th=document.getElementById('theme');
if(th){try{if(localStorage.getItem('tripwork-theme')==='dark')th.checked=true}catch(e){}
  th.addEventListener('change',()=>{try{localStorage.setItem('tripwork-theme',th.checked?'dark':'light')}catch(e){}})}
const cur=()=>{const r=document.querySelector('input[name=pg]:checked');return r?r.id.slice(3).replace(/f$/,''):'home'};
const open=id=>{const r=document.getElementById('pg-'+id);if(r&&!r.checked){r.checked=true;r.dispatchEvent(new Event('change',{bubbles:true}))}};
// a link into the page wins; a fragment that names no place in it (the share link's
// #staticrypt_pwd=..., which staticrypt leaves in the address bar after the unlock) does not
const at=(()=>{try{const h=decodeURIComponent(location.hash.slice(1));return !!h&&!!document.getElementById(h)}catch(e){return false}})();
{const n=new Date(),t=n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');
  const s=document.querySelector('section.page.day[data-date="'+t+'"]');
  // v2.2: today's home stamp wears its tape (tapes.py), whichever page the link opens
  if(s)document.querySelectorAll('.page.home label.stamp[for="pg-'+s.dataset.pg+'"]').forEach(e=>e.classList.add('today'));
  if(s&&!at)open(s.dataset.pg)}
// history (B1): 返回 always lands on the overview. The overview is the entry beneath every page.
let last=cur(),popping=false;history.replaceState({pg:'home'},'');
if(last!=='home')history.pushState({pg:last},'');
// in-page anchors (stops, 來源, 給司機看, map chips) replace the entry instead of stacking one
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[href^="#"]');
  if(!a||a.hash.length<2||e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  e.preventDefault();location.replace(a.hash);history.replaceState({pg:cur()},'')},true);
addEventListener('hashchange',()=>history.replaceState({pg:cur()},''));
document.addEventListener('change',e=>{const r=e.target;if(!r.classList||!r.classList.contains('pgr')||popping)return;const id=cur();
  if(id===last)return;const was=last;last=id;
  if(was==='home')history.pushState({pg:id},'');
  else if(id==='home'&&history.state&&history.state.pg&&history.state.pg!=='home')history.back();
  else history.replaceState({pg:id},'')});
// a fragment jump (a script setting location.hash) also fires popstate, with no state of ours: leave it be
addEventListener('popstate',e=>{if(!e.state)return;popping=true;open('home');last='home';popping=false});})();
// v2.2 every width: a photo grows out of its thumbnail and goes back into it (picks B + O2). The
// layer is the page's own (.pzx, theme.py): the figure keeps its place, so nothing underneath
// moves -- the checkbox's full-screen figure (no script) left a hole in its card. A tap on the
// photo, ✕ or the dark layer, Esc, or a downward drag (touch) all close it the same way.
// it plays with reduced motion on too (the user's pick M1: short, and only where a finger asked for it)
(()=>{const ANG=Math.tan(30*Math.PI/180);
const EASE='cubic-bezier(.2,.85,.25,1)',FULL='inset(0px 0px 0px 0px)';let ov=null,g=null;
const tf=(x,y,k)=>`translate(${x}px,${y}px) scale(${k})`;
// the open photo: contained in 92 % of the height above the bar (10 + 38), the whole centred
const box=()=>{const W=innerWidth,H=innerHeight,h=H*.92;return {w:W,h,y:(H-h-48)/2}};
// the part of the thumbnail that shows: under the map row or the list's cap it is covered, not
// clipped, so ask what is on top along its middle (the figure shown, our layer let through, for the probe)
function shown(r){const f=ov.fig,v=f.style.visibility;f.style.visibility='';ov.root.style.pointerEvents='none';
  const x=r.left+r.width/2,own=y=>{const e=document.elementFromPoint(x,y);return !!e&&f.contains(e)};
  let t=Math.max(0,Math.ceil(r.top)),b=Math.min(innerHeight,Math.floor(r.bottom));
  while(t<b&&!own(t+.5))t++;while(b>t&&!own(b-.5))b--;f.style.visibility=v;ov.root.style.pointerEvents='';return [t,b]}
// the thumbnail as a transform of the open photo, the crop that makes it cover, the window it shows through
function slot(){const r=ov.fig.querySelector('.bpz').getBoundingClientRect(),C=ov.C,sc=Math.max(r.width/ov.iw,r.height/ov.ih),
  cw=ov.iw*sc,ch=ov.ih*sc,k=cw/C.w,[t,b]=shown(r);
  return {x:r.left+(r.width-cw)/2,y:r.top+(r.height-ch)/2,k,clip:`inset(${(ch-r.height)/2/k}px ${(cw-r.width)/2/k}px)`,
    win:`inset(${t}px 0px ${innerHeight-b}px 0px)`,f:ov.filter}}
function open(fig){const cs=getComputedStyle(fig.querySelector('.bpi')),im=new Image();
  im.onload=()=>{if(ov)return;const iw=im.naturalWidth||1,ih=im.naturalHeight||1,B=box(),k=Math.min(B.w/iw,B.h/ih);
    const C={w:iw*k,h:ih*k};C.x=(B.w-C.w)/2;C.y=B.y+(B.h-C.h)/2;
    const root=document.createElement('div');root.className='pzx';
    root.innerHTML='<div class="pzb"></div><div class="pzw"><div class="pzi"></div></div><div class="zbar"><span class="zc"></span><label class="zx">✕ 關閉</label></div>';
    const bg=root.children[0],win=root.children[1],hero=win.firstChild,bar=root.children[2],zc=fig.querySelector('.zbar .zc');
    if(zc)bar.firstChild.innerHTML=zc.innerHTML;
    hero.style.cssText=`width:${C.w}px;height:${C.h}px;background-image:${cs.backgroundImage};transform:${tf(C.x,C.y,1)}`;
    bar.style.top=(B.y+B.h+10)+'px';document.body.append(root);
    ov={fig,root,bg,win,hero,bar,C,iw,ih,filter:cs.filter==='none'?'none':cs.filter,busy:true};
    const t=slot(),o={duration:300,easing:EASE};fig.style.visibility='hidden';
    hero.animate([{transform:tf(t.x,t.y,t.k),clipPath:t.clip,filter:t.f},{transform:tf(C.x,C.y,1),clipPath:'inset(0px 0px)',filter:'none'}],o);
    win.animate([{clipPath:t.win},{clipPath:FULL,offset:.55},{clipPath:FULL}],o);
    bg.animate([{opacity:0},{opacity:1}],o);
    bar.animate([{opacity:0},{opacity:0,offset:.5},{opacity:1}],o).onfinish=()=>{if(ov&&ov.root===root)ov.busy=false}};
  im.src=cs.backgroundImage.replace(/^url\(["']?|["']?\)$/g,'')}
// back into the thumbnail from where the photo is now (c); the window closes onto the shown part by
// 45 % of the way, so a thumbnail half under the cap is not drawn over the cap
function close(c){if(!ov||ov.busy)return;const s=ov;s.busy=true;g=null;
  const t=slot(),o={duration:340,easing:EASE,fill:'forwards'},bo=+getComputedStyle(s.bg).opacity;s.bar.style.opacity='0';
  const a=s.hero.animate([{transform:tf(c.x,c.y,c.k),clipPath:'inset(0px 0px)',filter:'none'},{transform:tf(t.x,t.y,t.k),clipPath:t.clip,filter:t.f}],o);
  s.win.animate([{clipPath:FULL},{clipPath:t.win,offset:.45},{clipPath:t.win}],o);s.bg.animate([{opacity:bo},{opacity:0}],o);
  // landed: the thumbnail comes back under it (with the card's outline, edge fade and credit drawn
  // over it) and the flying copy fades off, so nothing pops at the hand-over
  a.onfinish=()=>{s.fig.style.visibility='';s.hero.animate([{opacity:1},{opacity:0}],{duration:120,fill:'forwards'})
    .onfinish=()=>{s.root.remove();if(ov===s)ov=null}}}
const still=()=>({x:ov.C.x,y:ov.C.y,k:1});
addEventListener('click',e=>{const t=e.target;
  if(ov){if(!ov.root.contains(t))return;e.stopPropagation();if(t.closest('.zc a'))return;e.preventDefault();close(still());return}
  const l=t.closest&&t.closest('label.bpz');if(!l)return;e.preventDefault();e.stopPropagation();open(l.closest('figure.bp'))},true);
addEventListener('keydown',e=>{if(ov&&e.key==='Escape')close(still())});
// the drag (touch): the photo follows the finger and shrinks about it, the dark layer thins; let go
// moving down (or past 100 px) and it goes back into its thumbnail, else it springs back. Our
// handlers run first and stop the touch, so the page's own swipes never see it.
addEventListener('touchstart',e=>{if(!ov)return;e.stopPropagation();g=null;
  if(ov.busy||e.touches.length!==1||e.target.closest('.zc a'))return;const q=e.touches[0];
  g={x0:q.clientX,y0:q.clientY,mode:null,v:[[e.timeStamp,q.clientY]],dy:0,cur:null}},{capture:true,passive:true});
addEventListener('touchmove',e=>{if(!ov)return;e.stopPropagation();e.preventDefault();if(!g||e.touches.length!==1)return;
  const q=e.touches[0],dx=q.clientX-g.x0,dy=q.clientY-g.y0;
  if(!g.mode){if(Math.abs(dx)<4&&Math.abs(dy)<4)return;g.mode=dy>0&&Math.abs(dx)<=dy*ANG?'y':'n'}
  if(g.mode!=='y')return;const H=innerHeight,C=ov.C,k=1-.4*Math.min(1,Math.max(0,dy)/(H*.6));
  g.cur={x:q.clientX-k*(g.x0-C.x),y:q.clientY-k*(g.y0-C.y),k};g.dy=dy;ov.hero.style.transform=tf(g.cur.x,g.cur.y,k);
  ov.bg.style.opacity=String(1-Math.min(1,Math.max(0,dy)/(H*.45)));ov.bar.style.opacity='0';
  g.v.push([e.timeStamp,q.clientY]);if(g.v.length>5)g.v.shift()},{capture:true,passive:false});
const end=e=>{if(!ov)return;e.stopPropagation();const s=g;g=null;if(!s||s.mode!=='y'||!s.cur)return;
  const v=s.v,vel=v.length>1?(v[v.length-1][1]-v[0][1])/Math.max(1,v[v.length-1][0]-v[0][0]):0;
  if((vel>.25&&s.dy>0)||(s.dy>100&&vel>-.1)){close(s.cur);return}
  const C=ov.C,c=s.cur,o={duration:260,easing:'cubic-bezier(.3,1.2,.4,1)'},bo=+getComputedStyle(ov.bg).opacity;
  ov.hero.style.transform=tf(C.x,C.y,1);ov.bg.style.opacity='';ov.bar.style.opacity='';
  ov.hero.animate([{transform:tf(c.x,c.y,c.k)},{transform:tf(C.x,C.y,1)}],o);ov.bg.animate([{opacity:bo},{opacity:1}],o);
  ov.bar.animate([{opacity:0},{opacity:1}],o)};
addEventListener('touchend',end,{capture:true,passive:true});addEventListener('touchcancel',end,{capture:true,passive:true});})();
"""
