"""The one script the reader carries (spec §6.9, v1.1 §8.1). Opening a stop, a chip or
來源 is an in-page anchor jump that works with no script at all (Quick Look, LINE); this
script only polishes it where scripts run: after the jump it glides the opened stop to
the middle of the list card on a desktop (measured from the boxes, so the no-script
scroll-margin that roughly centres the jump does not skew it) (a stop taller than the card, or any phone,
keeps its title at the card's top, where the jump already put it), closes the other
stops' open alternative rows, and brings a just-opened alternative into view. On a phone it
turns the calendar fold continuous (.jsfold, theme.py) and settles a scroll that stops
between open and folded to the nearer end (no finger down); a day the stepper opens folded
opens on its plain radio scrolled to the fold, so pulling down unfolds it (pg-dNf has no room).

export-gate admits a <script> only when its sha256 equals this constant's
(scripts/export_gate.py::_SCRIPT_SHA256); change the text here and the gate follows."""

CENTRE_JS = """(()=>{const go=()=>{const id=decodeURIComponent(location.hash.slice(1)),t=id&&document.getElementById(id);if(!t)return;
const L=t.closest('.plist');if(!L)return;const s=t.closest('.stop');
L.querySelectorAll('details[open]').forEach(d=>{if(!s||(!s.contains(d)&&d.dataset.stop!==s.id))d.open=false;});
if(t.classList.contains('tx')||t!==s)return;
if(matchMedia('(min-width:1024px)').matches&&s.offsetHeight<L.clientHeight)requestAnimationFrame(()=>{
const lr=L.getBoundingClientRect(),sr=s.getBoundingClientRect();
L.scrollTo({top:L.scrollTop+(sr.top+sr.height/2)-(lr.top+lr.height/2),behavior:'smooth'});});};
addEventListener('hashchange',go);
document.addEventListener('toggle',e=>{const d=e.target;if(!d.open||!d.matches('.plist .altrow'))return;
requestAnimationFrame(()=>d.scrollIntoView({block:'nearest',behavior:'smooth'}));},true);
if(matchMedia('(max-width:1023px)').matches&&CSS.supports('animation-timeline','scroll()')){document.documentElement.classList.add('jsfold');
let touch=0,t=0;addEventListener('touchstart',()=>{touch++},{passive:true,capture:true});
const up=()=>{touch=Math.max(0,touch-1)};addEventListener('touchend',up,{passive:true,capture:true});addEventListener('touchcancel',up,{passive:true,capture:true});
const settle=L=>{if(touch||document.querySelector('.pgf:checked'))return;const m=L.closest('.page').querySelector('.pcal .mini'),h=m&&m.offsetHeight,s=L.scrollTop;
if(!h||s<=0||s>=h)return;L.scrollTo({top:s<h/2?0:h,behavior:'smooth'});};
document.addEventListener('scroll',e=>{const L=e.target;if(!L.classList||!L.classList.contains('plist'))return;clearTimeout(t);t=setTimeout(()=>settle(L),140);},{passive:true,capture:true});
document.addEventListener('change',e=>{const r=e.target;if(!r.classList||!r.classList.contains('pgf')||!r.checked)return;const n=document.getElementById(r.id.slice(0,-1)),P=document.querySelector('.page[data-pg="'+n.id.slice(3)+'"]');n.checked=true;const L=P.querySelector('.plist'),m=P.querySelector('.pcal .mini');L.style.scrollBehavior='auto';L.scrollTop=m.offsetHeight;L.style.scrollBehavior='';});}})();"""
