"""The one script the reader carries (spec §6.9, v1.1 §8.1). Opening a stop, a chip or
來源 is an in-page anchor jump that works with no script at all (Quick Look, LINE); this
script only polishes it where scripts run: after the jump it glides the opened stop to
the middle of the list card on a desktop (measured from the boxes, so the no-script
scroll-margin that roughly centres the jump does not skew it) (a stop taller than the card, or any phone,
keeps its title at the card's top, where the jump already put it), closes the other
stops' open alternative rows, and brings a just-opened alternative into view.

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
requestAnimationFrame(()=>d.scrollIntoView({block:'nearest',behavior:'smooth'}));},true);})();"""
