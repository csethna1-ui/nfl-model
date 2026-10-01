
(function(){
'use strict';
/* =====/* ============================================================
   DATA pipeline — fetch-based (static hosting, no embedded data)
   The real V1 export lives under data/: data/versions.json holds
   the manifest, data/v1/<name>.json holds the nine v1 members, and
   data/v1/experimental_markets.json holds the experimental markets
   snapshot. fetchData() reconstructs the identical
   {manifest, data:{v1}} shape the rest of the app consumes, so every
   line of downstream app code is untouched.
   Fail-safe: if ANY data file fails to load or parse, boot aborts
   with a "data unavailable" error and renders nothing — never
   fabricated or partial predictions.
   ============================================================ */
const DATA_DIR='data';
const DATA_FILES=['meta','predictions','record','clv','backtest','teams','props','injuries','model_facts'];
let _SNAP=null, _EXP_SNAP=null;
async function fetchData(){
  const load=async(path)=>{
    let r;
    try{ r=await fetch(path,{cache:'no-store'}); }
    catch(e){ throw new Error('network failure while loading '+path); }
    if(!r.ok) throw new Error('HTTP '+r.status+' while loading '+path);
    try{ return await r.json(); }
    catch(e){ throw new Error('could not parse JSON in '+path); }
  };
  const manifest=await load(DATA_DIR+'/versions.json');
  const v1={};
  for(const n of DATA_FILES){ v1[n]=await load(DATA_DIR+'/v1/'+n+'.json'); }
  const snap={manifest:manifest,data:{v1:v1}};
  // Defensive normalization (per AGENTS.md build contract): the dashboard
  // reads pr.uncertainty, while the canonical exporter emits pr.confidence.
  // Accept either key so canonical exports work without a manual rename.
  const rows=snap&&snap.data&&snap.data.v1&&snap.data.v1.props&&snap.data.v1.props.props;
  if(Array.isArray(rows)){ for(const pr of rows){ if(pr&&typeof pr==='object') pr.uncertainty??=pr.confidence; } }
  _SNAP=snap;
  _EXP_SNAP=await load(DATA_DIR+'/v1/experimental_markets.json');
  return {snap:snap,exp:_EXP_SNAP};
}
function embeddedSnapshot(){ return _SNAP; }
function embeddedExperimentalMarkets(){ return _EXP_SNAP; }

const FILES=['meta','predictions','record','clv','backtest','teams','props','injuries'];
const PRIMARY=['Home','Games','Props','Teams'];
const SECONDARY=['Performance','Model','CLV'];
const MORE=['Data Health','About'];
const TABS=['Home','Games','Props','Teams','More'];
const state={page:'Home',overlay:null,status:'all',gap:'0',q:'',propMarket:'all',propTeam:'all',propUnc:'all',propUncOnly:false,propSort:'projDesc',propShown:120,expQ:'',expShown:12,experimental:null,teamLens:'elo',teamQuery:'',teamView:'current',modelVersion:null,manifest:null,data:null,loadError:''};
const app=document.getElementById('app'), ovl=document.getElementById('ovl');

/* ---------- formatting helpers ---------- */
const fmt=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
const fmtInt=(v)=>Number.isFinite(Number(v))?String(Math.round(Number(v))):'—';
const signed=(v,d=1)=>Number.isFinite(Number(v))?(Number(v)>0?'+':'')+Number(v).toFixed(d):'—';
const pct1=(v,d=1)=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(d)+'%':'—';
const esc=(v)=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const mLabel=(v)=>String(v||'').toUpperCase();
const homeLine=(g)=>g.market_spread>0?g.home+' −'+fmt(g.market_spread,1):g.market_spread<0?g.away+' −'+fmt(Math.abs(g.market_spread),1):'Pick’em';
const modelLine=(g)=>g.model_spread>0?g.home+' −'+fmt(g.model_spread,1):g.model_spread<0?g.away+' −'+fmt(Math.abs(g.model_spread),1):'Pick’em';
const titleCase=(s)=>String(s||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const versionEntry=(v)=>state.manifest?.versions.find(x=>mLabel(x.version)===mLabel(v));
const statusOf=(v)=>String(versionEntry(v)?.status||'experimental').toLowerCase()==='production'?'production':'experimental';
const TERMS={teamRating:'Team strength rating',offPerformance:'Offensive performance per play',defPerformance:'Defensive performance per play allowed',avgError:'Average prediction error',lineMovement:'Line Movement',uncertainty:'Uncertainty'};
function freshnessLabel(raw){ const d=new Date(String(raw||'').replace(' UTC','Z')); if(isNaN(d)) return 'Updated: '+String(raw||'—'); return 'Updated: '+new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',weekday:'long',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(d); }

const TEAM_NAMES={ARI:'Arizona Cardinals',ATL:'Atlanta Falcons',BAL:'Baltimore Ravens',BUF:'Buffalo Bills',CAR:'Carolina Panthers',CHI:'Chicago Bears',CIN:'Cincinnati Bengals',CLE:'Cleveland Browns',DAL:'Dallas Cowboys',DEN:'Denver Broncos',DET:'Detroit Lions',GB:'Green Bay Packers',HOU:'Houston Texans',IND:'Indianapolis Colts',JAX:'Jacksonville Jaguars',KC:'Kansas City Chiefs',LA:'Los Angeles Rams',LAC:'Los Angeles Chargers',LV:'Las Vegas Raiders',MIA:'Miami Dolphins',MIN:'Minnesota Vikings',NE:'New England Patriots',NO:'New Orleans Saints',NYG:'New York Giants',NYJ:'New York Jets',PHI:'Philadelphia Eagles',PIT:'Pittsburgh Steelers',SEA:'Seattle Seahawks',SF:'San Francisco 49ers',TB:'Tampa Bay Buccaneers',TEN:'Tennessee Titans',WAS:'Washington Commanders'};
const teamName=(a)=>TEAM_NAMES[a]||a;
const TEAM_SHORT={ARI:'ARI Cardinals',ATL:'ATL Falcons',BAL:'BAL Ravens',BUF:'BUF Bills',CAR:'CAR Panthers',CHI:'CHI Bears',CIN:'CIN Bengals',CLE:'CLE Browns',DAL:'DAL Cowboys',DEN:'DEN Broncos',DET:'DET Lions',GB:'GB Packers',HOU:'HOU Texans',IND:'IND Colts',JAX:'JAX Jaguars',KC:'KC Chiefs',LA:'LA Rams',LAC:'LAC Chargers',LV:'LV Raiders',MIA:'MIA Dolphins',MIN:'MIN Vikings',NE:'NE Patriots',NO:'NO Saints',NYG:'NYG Giants',NYJ:'NYJ Jets',PHI:'PHI Eagles',PIT:'PIT Steelers',SEA:'SEA Seahawks',SF:'SF 49ers',TB:'TB Buccaneers',TEN:'TEN Titans',WAS:'WAS Commanders'};
const TEAM_ACCENT={ARI:'#97233f',ATL:'#a7194b',BAL:'#9e7c0c',BUF:'#c60c30',CAR:'#0085ca',CHI:'#c83803',CIN:'#fb4f14',CLE:'#ff3c00',DAL:'#7d93b8',DEN:'#fb4f14',DET:'#0076b6',GB:'#ffb612',HOU:'#a7194b',IND:'#6ea8d6',JAX:'#006778',KC:'#e31837',LA:'#ffa300',LAC:'#ffc20e',LV:'#b8bcc0',MIA:'#008e97',MIN:'#6950a3',NE:'#c60c30',NO:'#d3bc8d',NYG:'#a7194b',NYJ:'#125740',PHI:'#199444',PIT:'#ffb612',SEA:'#69be28',SF:'#aa0000',TB:'#d50a0a',TEN:'#4b92db',WAS:'#7a2734'};
/* Byte-owned team logos with an initials-badge fallback (never a broken image) */
const logo=(abbr,cls)=>'<span class="tlogo '+(cls||'')+'" aria-hidden="true"><i>'+esc(abbr)+'</i></span>';
const avatar=(pl,tm,heroCls,espnId)=>{
  return '<span class="avatar'+(heroCls?' '+heroCls:'')+'" style="background:'+(TEAM_ACCENT[tm]||'#334')+'" aria-hidden="true">'+esc(String(pl||'--'))+'</span>';
};

/* ---------- shared game logic (data-only) ---------- */
const isVoid=(g)=>!!(g.void_reason&&String(g.void_reason).trim());
const decisionOf=(g)=>isVoid(g)?'void':(g.is_pick?'pick':'none');
const gapOf=(g)=>Math.abs(Number(g.edge??0));
function kickDay(k){const m=String(k||'').match(/^(\w{3})\s/);return m?m[1]:String(k||'');}
function decisionChip(g){
  const d=decisionOf(g);
  if(d==='void') return '<span class="chip void">Voided</span>';
  if(d==='pick') return '<span class="chip pick">Pick vs current line · '+esc(g.spread_pick_final||g.spread_pick||'')+'</span>';
  return '<span class="chip noplay">No play</span>';
}
/* Plain-English "why": generated ONLY from values present in the data. */
function edgeDirWord(g){
  const e=Number(g.edge??0);
  if(Math.abs(e)<0.05) return 'level with the market';
  return e>0?'stronger on '+teamName(g.home):'stronger on '+teamName(g.away);
}
function whyLineCompact(g){
  const m=state.data.meta, d=decisionOf(g);
  const core='Model '+esc(modelLine(g))+' vs market '+esc(homeLine(g))+' — a '+fmt(gapOf(g),1)+'-point gap';
  if(d==='pick') return '<b>'+core+',</b> clearing the '+fmt(m.threshold,1)+' paper line by '+fmt(gapOf(g)-m.threshold,1)+'.';
  if(d==='void') return '<b>'+core+'.</b> Raw signal <b>'+esc(g.spread_pick)+'</b> was voided on QB availability — a voided signal is never a play.';
  return '<b>'+core+',</b> below the '+fmt(m.threshold,1)+' paper line, so no play.';
}
function whyLineHero(g){
  const m=state.data.meta, gap=fmt(gapOf(g),1), thr=fmt(m.threshold,1), d=decisionOf(g);
  let s='The model is <b>'+gap+' points '+edgeDirWord(g)+'</b> — it makes '+esc(modelLine(g))+' where the market says '+esc(homeLine(g))+'.';
  if(d==='pick') s+=' That clears the '+thr+'-point paper line by '+fmt(gapOf(g)-m.threshold,1)+', so it is a paper play.';
  else if(d==='void') s+=' The raw model signal (<b>'+esc(g.spread_pick)+'</b>) cleared the '+thr+'-point paper line but was voided on QB availability — it is not a play.';
  else s+=' That is below the '+thr+'-point paper line, so it is not a play.';
  s+=' Current ratings fold in every game through Week 3.';
  if(g.qb_news) s+=' QB note: '+esc(g.qb_news)+'.';
  return s;
}
/* Football-first summary for the Home cards. Every sentence is derived from exported component margins and team metrics. */
function homeFootballWhy(g){
  const f=favOf(g), comp=g.components||{}, mm=metricMeta(), rk=rankMaps();
  if(!f) return 'The projection and market are both shown above; open the game for the underlying team data.';
  const opp=f.team===g.home?g.away:g.home;
  const strongest=[
    ['overall offensive performance',mm.off_epa.rank[f.team]],
    ['passing performance',mm.off_pass_epa.rank[f.team]],
    ['rushing performance',mm.off_rush_epa.rank[f.team]],
    ['defensive performance',mm.def_epa.rank[f.team]],
    ['pass defense',mm.def_pass_epa.rank[f.team]],
    ['rush defense',mm.def_rush_epa.rank[f.team]]
  ].filter(x=>Number.isFinite(x[1])).sort((a,b)=>a[1]-b[1])[0];
  const layers=[['team strength',comp.elo_margin],['play-by-play performance',comp.epa_margin],['matchup patterns',comp.gbm_margin]].filter(x=>Number.isFinite(Number(x[1])));
  const supporting=layers.filter(x=>marginTeam(g,Number(x[1]))===f.team);
  let s=supporting.length===layers.length?'Team strength, play-by-play performance, and matchup patterns all favor <b>'+esc(f.team)+'</b>. ':esc(supporting.map(x=>x[0]).join(' and '))+' favor <b>'+esc(f.team)+'</b>, while the other layer is less supportive. ';
  if(strongest) s+=esc(f.team)+'\u2019s biggest strength is <b>'+esc(strongest[0])+', ranked #'+strongest[1]+' in the NFL</b>. ';
  s+='The model ranks '+esc(f.team)+' <b>#'+rk.elo[f.team]+'</b> overall and '+esc(opp)+' <b>#'+rk.elo[opp]+'</b>. That leads to <b>'+esc(modelLine(g))+'</b>, while the current market line is <b>'+esc(homeLine(g))+'</b>.';
  return s;
}
/* Current-season ratings (not the baseline) back every "why". */
function teamBy(abbr){
  const ts=state.data.teams.teams, t=ts.find(x=>x.team===abbr);
  if(t) return t;
  return {team:abbr,elo:NaN,off_epa:NaN,def_epa:NaN,off_sr:NaN,def_sr:NaN};
}
function rankMaps(){
  const ts=state.data.teams.teams;
  const mk=(fn,desc)=>{const s=[...ts].sort((a,b)=>(fn(a)-fn(b))*(desc?-1:1));const r={};s.forEach((t,i)=>r[t.team]=i+1);return r;};
  return {elo:mk(t=>t.elo,true),off:mk(t=>t.off_epa,true),def:mk(t=>t.def_epa,false)};
}

/* ---------- version-stamped loading ---------- */
function validateVersionData(data,version){
  FILES.forEach(n=>{
    const v=(data[n]&&data[n].model_version)||'';
    if(!v||mLabel(v)!==mLabel(version)) throw new Error(n+' is not stamped for '+mLabel(version));
  });
  return data;
}
function renderContext(){
  const vs=document.getElementById('verSel'), ws=document.getElementById('weekSel');
  const vers=state.manifest?.versions||[];
  vs.innerHTML=vers.map(v=>'<option value="'+esc(v.version)+'">'+esc(mLabel(v.version))+' · '+esc((v.status||'experimental').toLowerCase())+'</option>').join('');
  if(state.modelVersion) vs.value=state.modelVersion;
  vs.title='Model version ('+statusOf(state.modelVersion)+' — production specification, never profitability)';
  const m=state.data?state.data.meta:null;
  ws.innerHTML=m?'<option value="'+m.latest_week+'">Week '+m.latest_week+'</option>':'<option>—</option>';
  const stamp=document.getElementById('vstText'), dot=document.getElementById('vstDot');
  if(m){ stamp.textContent=mLabel(m.model_version)+' · '+m.season+' · W'+m.latest_week;
    dot.className='dot'+(statusOf(m.model_version)==='production'?'':' exp');
    document.getElementById('vstStamp').title='Model '+mLabel(m.model_version)+' · '+statusOf(m.modelVersion)+' (production specification, never profitability)';
  } else { stamp.textContent='—'; dot.className='dot exp'; }
}
function loadVersion(version){
  const entry=versionEntry(version);
  state.modelVersion=mLabel(version); state.data=null; state.facts=null; state.loadError=''; state.overlay=null; ovl.className='';
  document.body.style.overflow='';
  renderContext();
  app.innerHTML='<div class="loading">Loading '+esc(state.modelVersion)+' model snapshot&hellip;</div>';
  if(!entry){state.loadError='This version is not present in the export manifest.';render();return;}
  const snap=embeddedSnapshot(), blob=snap&&snap.data?snap.data[entry.dir]:null;
  if(!blob||!FILES.every(n=>blob[n])){
    state.loadError='The '+esc(mLabel(version))+' snapshot is missing from the data directory — the dashboard must be served with its data files.';
    renderContext();render();return;
  }
  try{
    state.facts=blob.model_facts||null;
    state.data=validateVersionData(Object.fromEntries(FILES.map(n=>[n,blob[n]])),entry.version);
    state.experimental=embeddedExperimentalMarkets()||null;
    renderContext();render();
  }catch(err){ state.data=null;state.loadError=err.message;renderContext();render(); }
}
function selectVersion(v){ if(mLabel(v)===mLabel(state.modelVersion)&&state.data) return; loadVersion(v); }
const PAGES=[...PRIMARY,...SECONDARY,...MORE,'More'];
const MORE_DESC={'Data Health':'Validation statuses behind this snapshot.','About':'What the model does and refuses to claim.'};
const SECONDARY_DESC={'Performance':'How the model performed on games it had never seen.','Model':'How the model turns team data into a spread.','CLV':'How the line moved after each tracked pick.'};
const navLabel=x=>x==='CLV'?TERMS.lineMovement:x;
async function manifestInit(){
  try{
    await fetchData();
  }catch(err){
    state.loadError='Model data failed to load ('+String((err&&err.message)||err)+'). The dashboard cannot display predictions without its data files — no partial or stale data is shown.';
    state.manifest={versions:[]}; renderNav(); renderContext(); render(); return;
  }
  const snap=embeddedSnapshot();
  if(!snap||!snap.manifest){
    state.loadError='No model data was found. The dashboard must be served with its data directory.';
    state.manifest={versions:[]}; renderNav(); renderContext(); render(); return;
  }
  const m=snap.manifest;
  const vs=(m.versions||[]).filter(v=>v&&v.version&&v.dir);
  state.manifest={default:m.default,versions:vs};
  const init=vs.find(v=>mLabel(v.version)==='V1')||vs.find(v=>mLabel(v.version)===mLabel(m.default))||vs[0];
  if(!init){state.loadError='No exported model versions were found';state.manifest=state.manifest||{versions:[]};renderNav();renderContext();render();return;}
  state.modelVersion=mLabel(init.version);
  const h=decodeURIComponent(location.hash.slice(1))||'';
  const legacy={Dashboard:'Home',Picks:'Games'};
  const pg=legacy[h]||h;
  state.page=PAGES.includes(pg)?pg:'Home';
  renderNav(); renderContext(); loadVersion(state.modelVersion);
}

/* ============================================================
   NAVIGATION + OVERLAYS
   ============================================================ */
function renderNav(){
  const p=document.getElementById('navP'), s=document.getElementById('navS'), t=document.getElementById('tabBar');
  p.innerHTML=PRIMARY.map(x=>'<button type="button" data-page="'+x+'" class="'+(state.page===x?'active':'')+'">'+x+'</button>').join('');
  s.innerHTML=SECONDARY.map(x=>'<button type="button" data-page="'+x+'" class="'+(state.page===x?'active':'')+'" title="'+(SECONDARY_DESC[x]||x)+'">'+navLabel(x)+'</button>').join('');
  const mb=document.getElementById('moreBtn'), mm=document.getElementById('moreMenu');
  mb.classList.toggle('active',MORE.includes(state.page)&&state.page!=='More');
  mm.innerHTML=MORE.map(x=>'<button type="button" data-page="'+x+'"><span class="mt">'+x+'</span><span class="md">'+esc(MORE_DESC[x]||'')+'</span></button>').join('');
  const icons={
    Home:'<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7v9a2 2 0 0 1-2 2h-4v-6h-6v6H5a2 2 0 0 1-2-2z"/></svg>',
    Games:'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5M16 4v5"/></svg>',
    Props:'<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.5-6 8-6s8 2 8 6"/></svg>',
    Teams:'<svg viewBox="0 0 24 24"><path d="M4 20h16"/><path d="M6 20V10l6-6 6 6v10"/><path d="M10 20v-5h4v5"/></svg>',
    More:'<svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>'
  };
  t.innerHTML=TABS.map(x=>'<button type="button" data-page="'+x+'" class="'+((state.page===x)||(x==='More'&&!TABS.includes(state.page)&&!TABS.includes(state.page))?'active':'')+'" aria-label="'+x+'">'+(icons[x]||'')+'<span>'+x+'</span></button>').join('');
  document.querySelectorAll('#navP button,#navS button,#tabBar button,#moreMenu button').forEach(b=>b.onclick=()=>navigate(b.dataset.page));
  document.getElementById('verSel').onchange=e=>selectVersion(e.target.value);
  mb.onclick=(e)=>{e.stopPropagation();const open=mb.getAttribute('aria-expanded')==='true';mb.setAttribute('aria-expanded',String(!open));mm.hidden=open;};
  document.addEventListener('click',()=>{mb.setAttribute('aria-expanded','false');mm.hidden=true;},true);
  document.getElementById('moreMenu').addEventListener('click',e=>e.stopPropagation());
}
function navigate(page){
  state.page=page; closeOverlay(); location.hash=encodeURIComponent(page);
  renderNav(); render(); window.scrollTo({top:0,behavior:'smooth'});
}
window.addEventListener('hashchange',()=>{
  const h=decodeURIComponent(location.hash.slice(1))||'';
  if(PAGES.includes(h)&&h!==state.page){state.page=h;renderNav();render();window.scrollTo({top:0});}
});

/* ---------- overlays (game / prop / team detail) ---------- */
function openOverlay(html,label){
  state.overlay=label; ovl.setAttribute('aria-hidden','false');
  ovl.innerHTML='<div class="ovl-bg" data-close="1"></div><div class="ovl-panel" role="dialog" aria-modal="true" aria-label="'+esc(label||'Detail')+'">'+html+'</div>';
  ovl.className='open'; document.body.style.overflow='hidden';
  ovl.querySelectorAll('[data-close]').forEach(el=>el.onclick=closeOverlay);
  ovl.querySelector('.ovl-panel').scrollTop=0;
}
function closeOverlay(){ state.overlay=null; ovl.setAttribute('aria-hidden','true'); ovl.className=''; ovl.innerHTML=''; document.body.style.overflow=''; }
document.addEventListener('keydown',e=>{if(e.key==='Escape') closeOverlay();});
document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target&&e.target.matches('[role="button"]')){e.preventDefault();e.target.click();}});
const ovlHead=(kicker,title,sub)=>'<button class="ovl-x" data-close="1" aria-label="Close">✕</button><p class="ovl-kick">'+esc(kicker)+'</p><h2 class="ovl-title">'+esc(title)+'</h2>'+(sub?'<p class="ovl-sub">'+sub+'</p>':'');
const sectHead=(idx,title,tail)=>'<div class="section-head"><span class="idx">'+esc(idx)+'</span><h2>'+esc(title)+'</h2>'+(tail||'')+'</div>';
function bindDetailClicks(){
  app.querySelectorAll('[data-game]').forEach(el=>el.onclick=()=>openGame(el.dataset.game));
  app.querySelectorAll('[data-prop]').forEach(el=>el.onclick=()=>openProp(el.dataset.prop));
  app.querySelectorAll('[data-exp-prop]').forEach(el=>el.onclick=()=>openExperimentalProp(el.dataset.expProp));
  app.querySelectorAll('[data-team]').forEach(el=>el.onclick=e=>{e.stopPropagation();openTeam(el.dataset.team);});
  app.querySelectorAll('[data-goto]').forEach(el=>el.onclick=()=>navigate(el.dataset.goto));
}

/* ---------- market → model spread visual ---------- */
function sprViz(g,large){
  const a=Number(g.market_spread), b=Number(g.model_spread);
  const lo=Math.min(a,b)-1.6, hi=Math.max(a,b)+1.6, span=(hi-lo)||1;
  const pos=v=>((v-lo)/span*100);
  const mk=pos(a), md=pos(b);
  return '<div class="sprviz'+(large?' lg':'')+'" role="img" aria-label="Market spread '+fmt(a,1)+', model spread '+fmt(b,1)+'">'+
    '<div class="axis"><div class="track"></div>'+
    '<div class="band" style="left:'+Math.min(mk,md)+'%;width:'+Math.abs(md-mk)+'%"></div>'+
    '<div class="dot mk" style="left:'+mk+'%" title="Market '+fmt(a,1)+'"></div>'+
    '<div class="dot md" style="left:'+md+'%" title="Model '+fmt(b,1)+'"></div></div>'+
    '<div class="labs"><span style="left:'+mk+'%">MKT '+fmt(a,1)+'</span><span class="lab-model" style="left:'+md+'%">MDL '+fmt(b,1)+'</span></div></div>';
}

/* ============================================================
   RENDER SHELL
   ============================================================ */
function pageHead(kicker,title,desc){
  return '<div class="page-head"><p class="kicker">'+esc(kicker)+'</p><h1>'+esc(title)+'</h1>'+(desc?'<p class="desc">'+desc+'</p>':'')+'</div>';
}
function renderFooter(){
  const m=state.data?state.data.meta:null;
  document.getElementById('pageFooter').innerHTML=m?
    '<div class="br"><span class="edge-badge" style="font-size:11px"><span class="sq" aria-hidden="true"></span>No verified betting edge</span><span>Research model · paper tracking only · '+esc(freshnessLabel(m.generated_at))+'</span></div>'+
    '<details><summary>Technical details &amp; disclaimer</summary><div class="detail-body">'+esc(m.disclaimer)+'<br>Model '+esc(mLabel(m.model_version))+' · '+(statusOf(m.model_version)==='production'?'production specification':'experimental')+' · '+esc(m.ensemble)+' · threshold |edge| ≥ '+fmt(m.threshold,1)+'. Production describes the specification, not profitability.</div></details>':'';
}
function render(){
  if(state.loadError){ app.innerHTML='<div class="err-box"><h2 style="margin-top:0">Snapshot failed to load</h2><p>'+esc(state.loadError)+'</p></div>'; renderFooter(); return; }
  if(!state.data){ app.innerHTML='<div class="loading">Loading verified model snapshot&hellip;</div>'; return; }
  const fn={Home:renderHome,Games:renderGames,Props:renderProps,Teams:renderTeams,Performance:renderPerformance,Model:renderModel,CLV:renderCLV,'Data Health':renderHealth,About:renderAbout,More:renderMore}[state.page]||renderHome;
  app.innerHTML=fn(); bindDetailClicks(); bindPage(); renderFooter();
}
function bindPage(){ const f={Games:bindGames,Props:bindProps,Teams:bindTeams,More:bindMore}[state.page]; if(f) f(); }

/* ============================================================
   HOME — MODEL BOARD
   ============================================================ */
function weekCounts(){
  const gs=state.data.predictions.games;
  let picks=0,voids=0;
  gs.forEach(g=>{const d=decisionOf(g); if(d==='void')voids++; else if(d==='pick')picks++;});
  return {total:gs.length,picks,voids,none:gs.length-picks-voids};
}
function sigGlyph(g){
  return '<div class="sig-match"><div class="sig-team">'+logo(g.away)+'<div><div class="ab">'+esc(TEAM_SHORT[g.away]||g.away)+'</div><div class="nm">'+esc(g.kickoff)+'</div></div></div>'+
  '<span class="sig-at">VS</span>'+
  '<div class="sig-team">'+logo(g.home)+'<div><div class="ab">'+esc(TEAM_SHORT[g.home]||g.home)+'</div><div class="nm">'+esc(kickDay(g.kickoff))+'</div></div></div></div>';
}
function renderHome(){
  const m=state.data.meta, bt=state.data.backtest, rec=state.data.record, c=weekCounts();
  const picks=[...state.data.predictions.games].filter(g=>decisionOf(g)==='pick').sort((a,b)=>gapOf(b)-gapOf(a));
  const rest=[...state.data.predictions.games].filter(g=>decisionOf(g)!=='pick').sort((a,b)=>gapOf(b)-gapOf(a));
  const hero=picks[0]||rest[0];
  const sub=picks.slice(1);
  const accentA=TEAM_ACCENT[hero.away]||'#4f8dff', accentH=TEAM_ACCENT[hero.home]||'#4f8dff';
  const t3=bt.by_threshold['3.0'].test_2023_25;
  const eloTop=[...state.data.teams.teams].sort((a,b)=>b.elo-a.elo).slice(0,5);
  const eloTopLo=Math.min(...eloTop.map(t=>t.elo));
  const heroW=favOf(hero);

  let s='<section>'+
    '<div class="mast"><div><p class="kicker">Week '+m.latest_week+' overview</p>'+
    '<h1>Week '+m.latest_week+' <span class="week">Model Picks</span></h1>'+
    '<p class="desc">'+c.picks+' picks from '+c.total+' games. Open a matchup for its projection, football reasons, uncertainty, and technical details.</p>'+
    '<div class="freshness">'+esc(freshnessLabel(m.generated_at))+'</div></div></div>'+ 
    /* HERO — the strongest signal */
    (hero?
    sectHead('01','Top Model Pick','<span class="tail" data-goto="Games">All '+c.total+' games →</span>')+
    '<div class="hero-game home-hero" data-game="'+esc(hero.game)+'" role="button" tabindex="0" aria-label="Top Model Pick: '+esc(hero.game)+'" style="--hg-accent:linear-gradient(90deg,'+accentA+','+accentH+')">'+
      '<div class="hg-top"><span class="hg-kick">'+esc(hero.kickoff)+'</span><span class="sp"></span>'+decisionChip(hero)+'</div>'+ 
      '<div class="hg-match"><div class="hg-team">'+logo(hero.away,'xl')+'<div><div class="ab">'+esc(TEAM_SHORT[hero.away]||hero.away)+'</div><div class="tn">'+esc(teamName(hero.away).replace(/^\\S+\\s/,'')||hero.away)+'</div></div></div>'+
      '<span class="hg-at">VS</span>'+
      '<div class="hg-team right"><div><div class="ab">'+esc(TEAM_SHORT[hero.home]||hero.home)+'</div><div class="tn">'+esc(teamName(hero.home).replace(/^\\S+\\s/,'')||hero.home)+'</div></div>'+logo(hero.home,'xl')+'</div></div>'+
      '<div class="hg-nums"><div class="hg-num model"><div class="k">Model</div><div class="v">'+esc(modelLine(hero))+'</div></div>'+
      '<div class="hg-num win"><div class="k">Win probability</div><div class="v">'+(heroW?esc(heroW.team)+' '+pct1(heroW.prob,1):'—')+'</div><div class="wp-sub">derived from projected margin</div></div>'+
      '<div class="hg-num market"><div class="k">Market</div><div class="v">'+esc(homeLine(hero))+'</div></div>'+
      '<div class="hg-num gap"><div class="k">Point gap</div><div class="v">'+fmt(gapOf(hero),1)+' <small>pts from market</small></div></div></div>'+
      sprViz(hero,true)+
      '<div class="hg-why"><p class="wl">Why this pick</p><p>'+homeFootballWhy(hero)+'</p></div>'+ 
      '<div class="game-uncertainty"><b>Uncertainty:</b> no game-specific range is available. The model&rsquo;s average miss on unfamiliar games was '+fmt(bt.test_mae.model,2)+' points.</div><div class="hg-foot"><span class="list-link">Details →</span></div>'+ 
    '</div>':'')

    /* TOP SIGNALS — remaining paper plays */
    +(sub.length? sectHead('02','Other Model Picks','<span class="tail" data-goto="Games">All '+c.total+' games →</span>')+
    '<div class="sig-grid">'+sub.map(g=>
      '<article class="sig-card" data-game="'+esc(g.game)+'" role="button" tabindex="0" aria-label="'+esc(g.game)+'">'+
      '<div class="sig-top"><span class="sig-kick">'+esc(g.kickoff)+'</span>'+decisionChip(g)+'</div>'+
      '<div class="sig-match"><div class="sig-team">'+logo(g.away)+'<div><div class="ab">'+esc(TEAM_SHORT[g.away]||g.away)+'</div></div></div>'+
      '<span class="sig-at">VS</span>'+
      '<div class="sig-team">'+logo(g.home)+'<div><div class="ab">'+esc(TEAM_SHORT[g.home]||g.home)+'</div></div></div></div>'+
      '<div class="nums four"><div class="cell hero"><div class="k">Model</div><div class="v">'+esc(modelLine(g))+'</div></div>'+
      '<div class="cell"><div class="k">Win prob</div><div class="v winp" title="Model win probability, calibrated from the model margin — not a market-implied probability; no market probability exists in this dataset">'+winProbCell(g)+'</div></div>'+
      '<div class="cell"><div class="k">Market</div><div class="v">'+esc(homeLine(g))+'</div></div>'+
      '<div class="cell"><div class="k">Point gap</div><div class="v">'+fmt(gapOf(g),1)+'</div></div></div>'+
      sprViz(g,false)+
      '<p class="sig-why"><b>Why this pick:</b> '+homeFootballWhy(g)+'</p>'+ 
      '<div class="game-uncertainty"><b>Uncertainty:</b> no game-specific range is available. The model&rsquo;s average miss on unfamiliar games was '+fmt(bt.test_mae.model,2)+' points.</div><div class="sig-foot"><span class="chip na">'+fmt(Math.abs(Number(g.edge??0))-m.threshold,1)+' pts above the paper line</span><span style="flex:1"></span><span class="list-link">Details →</span></div>'+ 
      '</article>').join('')+'</div>':'')

    /* REST OF BOARD */
    +sectHead('03','Rest of the Board','<span class="tail" data-goto="Games">Full model board →</span>')+
    '<div class="rest-grid">'+rest.map(g=>'<div class="rest-row'+(decisionOf(g)==='void'?' is-void':'')+'" data-game="'+esc(g.game)+'" role="button" tabindex="0">'+
      '<div class="tl">'+logo(g.away,'xs')+logo(g.home,'xs')+'</div>'+
      '<div class="mid"><div class="m">'+esc(g.away)+' @ '+esc(g.home)+'</div><div class="k">'+esc(kickDay(g.kickoff))+' · '+esc(modelLine(g))+' vs '+esc(homeLine(g))+'</div></div>'+
      (decisionOf(g)==='void'?'<span class="chip void">Voided</span>':'<span class="chip noplay">No play</span>')+
      '<div class="rt"><div class="gapv">'+fmt(gapOf(g),1)+'</div><div class="gl">Gap</div></div>'+
    '</div>').join('')+'</div>'+

    outlookSection()+

    /* EXPLORE THE MODEL */
    sectHead('05','Explore the Model','')+
    '<div class="explore-grid">'+exploreHTML()+'</div>'+

    /* TECHNICAL AND RESEARCH MATERIAL — available on demand, not in the primary football flow */
    '<details class="page-sub home-technical"><summary><span>Technical &amp; research details</span><span class="ch"></span></summary><div class="sub-body">'+
    sectHead('06','Research Snapshot','')+
    '<div class="snapshot-strip">'+
      '<div class="item"><div class="v" style="color:var(--model-ink)">'+c.picks+'</div><div class="l">Paper plays</div><div class="s">|edge| ≥ '+fmt(m.threshold,1)+'</div></div><div class="sep"></div>'+
      '<div class="item"><div class="v">'+c.none+'</div><div class="l">No plays</div><div class="s">below the paper line</div></div><div class="sep"></div>'+
      '<div class="item"><div class="v" style="color:var(--bad)">'+c.voids+'</div><div class="l">Voided</div><div class="s">QB availability</div></div><div class="sep"></div>'+
      '<div class="item"><div class="v">'+rec.season.w+'–'+rec.season.l+'</div><div class="l">2026 track</div><div class="s">avg CLV '+signed(rec.season.avg_clv_pts,2)+' · n='+rec.season.clv_n+' (proxy)</div></div><div class="sep"></div>'+
      '<div class="item"><div class="v">'+fmt(bt.test_mae.model,2)+' <span style="color:var(--faint);font-weight:600;font-size:16px">/ '+fmt(bt.test_mae.market,2)+'</span></div><div class="l">Average prediction error · model / market</div><div class="s">the market remains the stronger baseline</div></div>'+
    '</div>'+
    '<div class="home-teasers">'+
      '<div class="teaser"><p class="th">Held-out performance</p><div class="tl"><div><div class="lab">Model average error</div><div class="big" style="color:var(--model-ink)">'+fmt(bt.test_mae.model,2)+'</div></div><div><div class="lab">Market average error</div><div class="big">'+fmt(bt.test_mae.market,2)+'</div></div></div>'+
      '<p>The market has lower locked-test MAE — it remains the stronger baseline. ATS at 3.0: <b>'+t3.w+'–'+t3.l+'</b> ('+pct1(t3.win_pct,1)+', n='+t3.n+'). <span class="list-link" data-goto="Performance">Research center →</span></p></div>'+
      '<div class="teaser"><p class="th"><span class="tooltip" title="A game-updated measure of team strength; higher is stronger. The technical name is ELO.">Current team strength</span> · top 5</p>'+
      eloTop.map((t,i)=>'<div class="rat-row" data-team="'+esc(t.team)+'"><span class="rk">'+(i+1)+'</span>'+logo(t.team,'xs')+'<span class="ab">'+esc(t.team)+'</span><span class="fin"><i style="width:'+Math.max(6,((t.elo-eloTopLo)/((eloTop[0].elo-eloTopLo)||1)*100))+'%"></i></span><span class="num">'+fmt(t.elo,0)+'</span></div>').join('')+
      '<p>Ratings fold in every game through Week 3. <span class="list-link" data-goto="Teams">Full power board →</span></p></div>'+
    '</div></div></details>'+
  '</section>';
  return s;
}
/* ============================================================
   GAMES
   ============================================================ */
function filteredGames(){
  let gs=[...state.data.predictions.games];
  if(state.status!=='all') gs=gs.filter(g=>decisionOf(g)===(state.status==='nono'?'none':state.status));
  const gt=parseFloat(state.gap);
  if(gt>0) gs=gs.filter(g=>gapOf(g)>=gt);
  gs.sort((a,b)=>gapOf(b)-gapOf(a));
  return gs;
}
function fc(group,val,label){return '<button class="fchip'+(state[group]===val?' on':'')+'" data-fg="'+group+'" data-fv="'+val+'">'+esc(label)+'</button>';}
function renderGames(){
  const m=state.data.meta, gs=filteredGames(), all=state.data.predictions.games;
  const counts={total:all.length,picks:all.filter(g=>decisionOf(g)==='pick').length,voids:all.filter(g=>decisionOf(g)==='void').length};
  return pageHead('Week '+m.latest_week+' · '+counts.picks+' picks','Games','Each card reads in the same order: pick, projection, why, uncertainty, then details. Open a game for the full team comparison.')+
  '<div class="chips" style="margin-bottom:10px"><span class="fgroup-label">Show</span>'+fc('status','all','All')+fc('status','pick','Paper plays')+fc('status','nono','No play')+fc('status','void','Voided')+
  '<span class="fgroup-label" style="margin-left:8px">Gap</span>'+fc('gap','0','All')+fc('gap','1','≥ 1.0')+fc('gap','2','≥ 2.0')+fc('gap','3','≥ 3.0')+'</div>'+
  '<p class="viz-note" style="margin:0 0 14px">'+counts.picks+' paper plays · '+(counts.total-counts.picks-counts.voids)+' no plays · '+counts.voids+' voided — showing '+gs.length+' of '+counts.total+' games</p>'+
  '<p class="viz-note wp-note" style="margin:0 0 14px">'+esc(MODEL_WIN_PROB_NOTE)+'</p>'+
  '<div class="board-grid">'+gs.map(gameCard).join('')+'</div>'+
  '<div class="games-mobile">'+renderGamesMobile(gs)+'</div>'+
  (gs.length?'':'<div class="info-empty" style="margin-top:14px">No games match these filters.</div>')+
  '<div class="legend"><span><span class="sw mk"></span>Market</span><span><span class="sw md"></span>Model</span><span>Difference — how far the model is from the market</span></div>';
}
/* QB availability overlay: full 8-step chain when a QB change is expected
   (V1 Prediction → Expected QB → QB Adjustment → Adjusted (experimental) →
   Market → Raw Edge → Adjusted Edge → Final Status), subtle expected-QBs
   line otherwise. V1 (model_spread) is never replaced by the adjusted number. */
const qbLine=(g,v)=>v>0?g.home+' −'+fmt(v,1):v<0?g.away+' −'+fmt(Math.abs(v),1):'Pick’em';
function qbOverlayHTML(g){
  const q=g.qb_overlay; if(!q) return '';
  const awayQB=q.expected_qb_away||'—', homeQB=q.expected_qb_home||'—';
  if(!q.qb_change_side) return '<div class="qbov-line">Expected QBs: '+esc(awayQB)+' @ '+esc(homeQB)+'</div>';
  const side=q.qb_change_side==='away'?'away':'home';
  const qbName=side==='away'?awayQB:homeQB;
  const step=(k,v,x)=>'<div class="qstep'+(x?' '+x:'')+'"><span class="qk">'+k+'</span><span class="qv">'+v+'</span></div>';
  const arr='<span class="qarrow" aria-hidden="true">→</span>';
  const badge=q.final_status==='PICK'?'good':(q.final_status==='VETOED'?'unc':'na');
  let h='<div class="qbov"><div class="qbov-head">QB availability</div>';
  if(q.qb_change_note) h+='<p class="qbov-note">'+esc(q.qb_change_note)+'</p>';
  h+='<div class="qbov-flow">'+
    step('V1 Prediction',esc(modelLine(g)),'v1')+arr+
    step('Expected QB',esc(qbName)+' <span style="color:var(--faint)">· '+(side==='away'?esc(g.away)+' (away)':esc(g.home)+' (home)')+'</span>')+arr+
    step('QB Adjustment',esc(signed(q.qb_shift_pts,1)+' pts'))+arr+
    '<div class="qstep exp"><span class="qk" title="Experimental derived overlay, not a V1 rerun.">Adjusted (experimental)</span><span class="qv">'+esc(q.model_spread_adj==null?'—':qbLine(g,q.model_spread_adj))+'</span></div>'+arr+
    step('Market',esc(homeLine(g)))+arr+
    step('Raw Edge',esc(signed(g.edge,1)))+arr+
    step('Adjusted Edge',esc(q.edge_adj==null?'—':signed(q.edge_adj,1)))+arr+
    '<div class="qstep"><span class="qk">Final Status</span><span class="qv"><span class="chip '+badge+'">'+esc(q.final_status)+'</span></span></div>'+
  '</div>';
  if(q.qb_double_count_risk) h+='<div class="dcwarn"><b>Double-count risk:</b><span>the backup already started games in the sample feeding V1\u2019s ratings, so the adjusted number is the conservative bound and raw V1 the aggressive bound.</span></div>';
  if(q.final_status==='VETOED'&&g.void_reason) h+='<p class="veto-why"><b>Veto reason:</b> '+esc(g.void_reason)+'</p>';
  h+='</div>';
  return h;
}
function gameCard(g){
  const d=decisionOf(g);
  const qbNote=g.qb_news?' QB availability is flagged and explained in the game detail.':'';
  const vb=(d==='void')?'<div class="voidblock"><b>Voided — '+esc(g.spread_pick)+' removed.</b><span class="r">'+esc(g.qb_news)+'</span><span class="r">'+esc(g.void_reason)+'</span></div>':'';
  return '<article class="gcard'+(d==='void'?' is-void':'')+'" data-game="'+esc(g.game)+'" role="button" tabindex="0" aria-label="'+esc(g.game)+'">'+
    '<div class="pick-flow-label" style="margin-top:0">Pick</div><div class="top"><span class="kick">'+esc(g.kickoff)+'</span>'+decisionChip(g)+'</div>'+
    '<div class="sig-match"><div class="sig-team">'+logo(g.away)+'<div><div class="ab">'+esc(TEAM_SHORT[g.away]||g.away)+'</div></div></div>'+
    '<span class="sig-at">VS</span>'+
    '<div class="sig-team">'+logo(g.home)+'<div><div class="ab">'+esc(TEAM_SHORT[g.home]||g.home)+'</div></div></div></div>'+
    '<div class="pick-flow-label">Projection</div><div class="nums four"><div class="cell hero"><div class="k">Model spread</div><div class="v">'+esc(modelLine(g))+'</div></div>'+
    '<div class="cell"><div class="k">Chance to win</div><div class="v winp" title="Derived from the projected margin; not a sportsbook probability">'+gamesWinProbHTML(g)+'</div>'+gamesWinProbNote(g)+'</div>'+
    '<div class="cell"><div class="k">Market spread</div><div class="v">'+esc(homeLine(g))+'</div></div>'+
    '<div class="cell"><div class="k">Difference</div><div class="v">'+fmt(gapOf(g),1)+' pts</div></div></div>'+
    '<div class="pick-flow-label">Why</div><div class="game-why">'+homeFootballWhy(g)+'</div>'+
    '<div class="pick-flow-label">Uncertainty</div><div class="game-uncertainty"><b>No game-specific range is available.</b> The model&rsquo;s average miss on games it had never seen was '+fmt(state.data.backtest.test_mae.model,2)+' points.'+qbNote+'</div>'+vb+
    '<div class="sig-foot"><span class="list-link">Details →</span></div>'+ 
  '</article>';
}
function renderGamesMobile(gs){
  const picks=gs.filter(g=>decisionOf(g)==='pick');
  const rail=picks.length?'<div class="section-head reset"><h2>Paper plays</h2></div><div class="rail">'+picks.map(g=>'<div class="rcard" data-game="'+esc(g.game)+'"><div class="hd"><span class="kick">'+esc(kickDay(g.kickoff))+'</span>'+decisionChip(g)+'</div><div class="mrow">'+logo(g.away,'sm')+'<span class="ab">'+esc(g.away)+'</span><span class="at">VS</span><span class="ab">'+esc(g.home)+'</span>'+logo(g.home,'sm')+'</div><div class="nums four"><div class="cell hero"><div class="k">Mdl</div><div class="v" style="font-size:14px">'+esc(modelLine(g))+'</div></div><div class="cell"><div class="k">Win</div><div class="v" style="font-size:14px">'+gamesWinProbHTML(g)+'</div>'+gamesWinProbNote(g)+'</div><div class="cell"><div class="k">Mkt</div><div class="v" style="font-size:14px">'+esc(homeLine(g))+'</div></div><div class="cell"><div class="k">Gap</div><div class="v" style="font-size:14px">'+fmt(gapOf(g),1)+'</div></div></div><div class="qbov-m" style="margin-top:8px">Expected QBs: '+esc((g.qb_overlay&&g.qb_overlay.expected_qb_away)||'—')+' @ '+esc((g.qb_overlay&&g.qb_overlay.expected_qb_home)||'—')+'</div></div>').join('')+'</div>':'';
  return rail+'<div class="section-head reset" style="margin-top:8px"><h2>All games</h2></div>'+gs.map(g=>{
    return '<div class="grow" data-game="'+esc(g.game)+'" role="button" tabindex="0"><div class="tl">'+logo(g.away,'sm')+logo(g.home,'sm')+'</div><div class="mid"><div class="m">'+esc(g.away)+' @ '+esc(g.home)+'</div><div class="k">'+esc(kickDay(g.kickoff))+' · '+esc(decisionChip(g).replace(/<[^>]+>/g,''))+'</div><div class="qbov-m">Expected QBs: '+esc((g.qb_overlay&&g.qb_overlay.expected_qb_away)||'—')+' @ '+esc((g.qb_overlay&&g.qb_overlay.expected_qb_home)||'—')+'</div></div><div class="rt"><div class="gap">'+fmt(gapOf(g),1)+'</div><div class="gl">Model gap</div></div>'+(g.qb_news?'<span class="qb-chip" style="padding:4px 8px">QB</span>':'')+'</div>';
  }).join('');
}
function bindGames(){
  app.querySelectorAll('[data-fg]').forEach(b=>b.onclick=()=>{state[b.dataset.fg]=b.dataset.fv;render();});
}
/* CP3 — Game page: prediction → components → stats → advanced. */
function openGame(gameId){
  const g=state.data.predictions.games.find(x=>x.game===gameId); if(!g) return;
  const m=state.data.meta, d=decisionOf(g), rk=rankMaps(), f=favOf(g);
  const a=teamBy(g.away)||{}, h=teamBy(g.home)||{};
  let html=ovlHead('Game detail','Week '+m.latest_week+' · '+gameId,'<span>Week '+m.latest_week+' · '+esc(m.season)+'</span> · <span>'+esc(g.kickoff)+'</span>');
  if(d==='void') html+='<div class="void-alert"><div class="ttl">Voided — paper play removed</div><div><b>Raw model signal:</b> '+esc(g.spread_pick)+'</div><div style="margin-top:4px"><b>QB status / reason:</b> '+esc(g.qb_news)+'</div><div style="margin-top:4px"><b>Final disposition:</b> '+esc(g.void_reason)+'</div></div>';
  html+=gameHeroHTML(g);
  if(f) html+='<h2 class="bk-h2">Why the model leans '+esc(f.team)+'</h2><div class="game-why">'+homeFootballWhy(g)+'</div>';
  html+='<div class="product-note"><b>Uncertainty:</b> the model&rsquo;s average miss on games it had never seen was '+fmt(state.data.backtest.test_mae.model,2)+' points. A '+fmt(gapOf(g),1)+'-point difference from the market is disagreement, not confidence or proof of an edge.</div>';
  if(g.qb_overlay) html+='<details class="page-sub"><summary><span>QB availability details</span><span class="ch"></span></summary><div class="sub-body"><div class="qbov-wrap">'+qbOverlayHTML(g)+'</div></div></details>';
  html+='<details class="page-sub"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body"><p class="bk-sub">The frozen model combines team-strength ratings, play-by-play performance, and a smaller nonlinear matchup layer. Open a component for its calculation and exported values.</p>'+ 
    '<div class="mb-top">'+
    '<div class="mb-cell model-v"><div class="k">Final V1 model</div><div class="v">'+esc(modelLine(g))+'</div></div>'+
    '<div class="mb-cell win-v"><div class="k">Model win probability</div><div class="v">'+(f?esc(f.team)+' '+pct1(f.prob,1):'\u2014')+'</div>'+(f?'<div class="o">'+esc(f.team===g.home?g.away:g.home)+' '+pct1(1-f.prob,1)+'</div>':'')+'</div></div>';
  html+=eloDetail(g,a,h,rk)+epaDetail(g,a,h)+gbmDetail(g,a,h);
  html+=compositionHTML(g);
  html+='<div class="viz-lg"><div class="section-head reset" style="margin:0 0 8px"><h2 style="font-size:18px">Model vs market</h2></div>'+sprViz(g,true)+
    '<p class="viz-note">The band between the markers is the model gap: <b>'+fmt(gapOf(g),1)+' points</b>. Disagreement is a comparison, not evidence of a betting edge.</p></div>';
  html+='<h2 class="bk-h2">Underlying team data</h2><p class="bk-sub">The actual NFL stats underneath the model — both teams, league-scaled, from the exported ratings snapshot.</p>'+underlyingHTML(g);
  html+='<details class="page-sub"><summary><span>Advanced model details</span><span class="ch"></span></summary>'+advDetailsHTML(g)+'</details>';
  html+='<details class="page-sub"><summary><span>Data &amp; methodology</span><span class="ch"></span></summary>'+dataMethodHTML(g)+'</details></div></details>';
  html+='<div style="padding:6px 0 14px;text-align:center"><button class="btn big full" data-goto="Games">All games →</button></div>';
  openOverlay(html,'Game: '+gameId);
}

/* ============================================================
   PROPS
   ============================================================ */
/* Visible label for the experimental player-projection model. The export's
   stored value (P.model) must not be changed; only the displayed label maps
   to 'Player Projection v2 · Experimental'. */
const propsModelLabel=(m)=>String(m||'').indexOf('Player Projection v2')===0?'Player Projection v2 · Experimental':m;
const MARKET_POS={pass_yards:'QB',rush_yards:'RB',receiving_yards:'WR/TE'};
const posOf=(pr)=>MARKET_POS[pr.market]||'?';
const marketLabel=(mk)=>({pass_yards:'Pass yards',rush_yards:'Rush yards',receiving_yards:'Receiving yards'}[mk]||mk);
const unitOf=(mk)=>({pass_yards:'pass yards',rush_yards:'rush yards',receiving_yards:'receiving yards'}[mk]||'yards');
function initialsOf(p){const t=String(p||'').replace(/^([A-Z])\.(.*)$/,'$1$2');return (t.replace(/[^A-Za-z]/g,'').slice(0,1)+(t.replace(/[^A-Za-z]/g,'').slice(1,2)||'')).toUpperCase();}
const SORTS={
  projDesc:'Projection: highest first',
  projAsc:'Projection: lowest first',
  marketPass:'Market: passing first',
  marketRush:'Market: rushing first',
  marketRcv:'Market: receiving first',
  uncDesc:'Uncertainty: highest first',
  lineGap:'Line gap: largest first',
  name:'Player A–Z'
};
function filteredProps(){
  const q=state.q.trim().toLowerCase();
  let rs=state.data.props.props.filter(pr=>{
    if(state.propMarket!=='all'&&pr.market!==state.propMarket) return false;
    if(state.propTeam!=='all'&&pr.team!==state.propTeam) return false;
    if(state.propUnc!=='all'&&pr.uncertainty!==state.propUnc) return false;
    if(state.propUncOnly&&!pr.uncertainty_flag) return false;
    if(q&&!(String(pr.player).toLowerCase().includes(q)||String(pr.team).toLowerCase().includes(q)||String(pr.opp).toLowerCase().includes(q))) return false;
    return true;
  });
  const mkFirst=state.propSort==='marketPass'?'pass_yards':state.propSort==='marketRush'?'rush_yards':state.propSort==='marketRcv'?'receiving_yards':null;
  if(state.propSort==='projDesc') rs.sort((a,b)=>b.projection-a.projection);
  else if(state.propSort==='projAsc') rs.sort((a,b)=>a.projection-b.projection);
  else if(mkFirst) rs.sort((a,b)=>((b.market===mkFirst?1:0)-(a.market===mkFirst?1:0))||(Number(b.projection)-Number(a.projection)));
  else if(state.propSort==='uncDesc') rs.sort((a,b)=>((b.uncertainty_flag?1:0)-(a.uncertainty_flag?1:0))||((Number(b.p75)-Number(b.p25))-(Number(a.p75)-Number(a.p25))));
  else if(state.propSort==='lineGap') rs.sort((a,b)=>((a.market_line==null?1:0)-(b.market_line==null?1:0))||(Math.abs(Number(b.projection)-Number(b.market_line))-Math.abs(Number(a.projection)-Number(a.market_line))));
  else rs.sort((a,b)=>String(a.player).localeCompare(String(b.player)));
  return rs;
}
function rangeViz(pr){
  const lo=Math.min(pr.p25,pr.projection)-1, hi=Math.max(pr.p75,pr.projection)+1, sp=(hi-lo)||1;
  const pos=v=>((v-lo)/sp*100);
  return '<div class="rangeviz"><div class="track"><div class="fill" style="left:'+pos(pr.p25)+'%;width:'+(pos(pr.p75)-pos(pr.p25))+'%"></div>'+
    '<div class="tick" style="left:'+pos(pr.median)+'%" title="Median '+fmt(pr.median,1)+'"></div>'+
    '<div class="pdot" style="left:'+Math.max(0,Math.min(100,pos(pr.projection)))+'%" title="Projection '+fmt(pr.projection,1)+'"></div></div>'+
    '<div class="rlab"><span>Lower <b>'+fmt(pr.p25,1)+'</b></span><span>Middle <b>'+fmt(pr.median,1)+'</b></span><span>Upper <b>'+fmt(pr.p75,1)+'</b></span></div></div>';
}
function propCard(pr){
  const uncCls=pr.uncertainty==='High'?'lo':pr.uncertainty==='Low'?'hi':'md';
  const gap=Number(pr.projection)-Number(pr.market_line);
  const hasLine=pr.market_line!=null&&Number.isFinite(gap);
  const line=hasLine
    ?'<span class="ln">Line '+fmt(pr.market_line,1)+'</span><span class="sep">·</span><span class="ln">Gap '+signed(gap,1)+'</span>'
    :'<span class="ln">No market line — projection only</span>';
  return '<article class="pcard" data-prop="'+esc(prid(pr))+'" role="button" tabindex="0" aria-label="'+esc(pr.player)+' '+esc(marketLabel(pr.market))+'">'+
    '<div class="ph">'+avatar(initialsOf(pr.player),pr.team,null,pr.espn_id)+'<div class="pid"><div class="pn">'+esc(pr.player)+'</div><div class="pm">'+esc(pr.team)+' · '+esc(posOf(pr))+' · vs '+esc(pr.opp)+'</div></div></div>'+
    '<div class="mmkt">'+esc(marketLabel(pr.market))+'</div>'+
    '<div class="hero"><span class="big">'+fmt(pr.projection,1)+'</span><span class="unit">projected '+esc(unitOf(pr.market))+'</span></div>'+
    '<div class="rng"><span>Lower range <b>'+fmt(pr.p25,1)+'</b></span><span>Middle <b>'+fmt(pr.median,1)+'</b></span><span>Upper range <b>'+fmt(pr.p75,1)+'</b></span></div>'+ 
    '<div class="pfoot"><span class="'+uncCls+' tooltip" title="Uncertainty describes the observed reliability of this interval bucket, not confidence or correctness.">'+esc(pr.uncertainty)+' uncertainty</span>'+(pr.uncertainty_flag?'<span class="sep">·</span><span class="unc">Elevated uncertainty</span>':'')+'<span class="sep">·</span>'+line+'</div>'+
  '</article>';
}
function prid(pr){ return pr._id; }
/* Featured — a few projections with stronger visual hierarchy, selected
   ONLY for uncertainty-bucket / data quality: high-uncertainty rows (the
   tightest P25–P75 ranges) that carry a real captured market line, ordered
   by the tightest P25–P75 range relative to the projection. Never on
   claimed edge. Labels renamed confidence → uncertainty per Expt 002. */
function featuredProps(P){
  const rows=P.props.filter(pr=>pr.uncertainty==='High'&&pr.market_line!=null&&Number.isFinite(Number(pr.projection))&&Number.isFinite(Number(pr.p25))&&Number.isFinite(Number(pr.p75)));
  rows.sort((a,b)=>{
    const ra=(Number(a.p75)-Number(a.p25))/Math.max(1,Number(a.projection));
    const rb=(Number(b.p75)-Number(b.p25))/Math.max(1,Number(b.projection));
    return (ra-rb)||(Number(b.projection)-Number(a.projection));
  });
  return rows.slice(0,4);
}
function featuredHTML(P){
  const rows=featuredProps(P); if(!rows.length) return '';
  const cards=rows.map(pr=>{
    const gap=Number(pr.projection)-Number(pr.market_line);
    return '<article class="fcard" data-prop="'+esc(prid(pr))+'" role="button" tabindex="0" aria-label="Featured: '+esc(pr.player)+' '+esc(marketLabel(pr.market))+'">'+
      '<div class="ph">'+avatar(initialsOf(pr.player),pr.team,'mini',pr.espn_id)+'<div class="pid"><div class="pn">'+esc(pr.player)+'</div><div class="pm">'+esc(pr.team)+' · '+esc(posOf(pr))+' · vs '+esc(pr.opp)+'</div></div></div>'+
      '<div class="mmkt">'+esc(marketLabel(pr.market))+'</div>'+
      '<div class="fbignum">'+fmt(pr.projection,1)+'</div>'+
      '<div class="funit">projected '+esc(unitOf(pr.market))+'</div>'+
      rangeViz(pr)+
      '<div class="fline"><span class="lo">High uncertainty</span><span>Line '+fmt(pr.market_line,1)+'</span><span>Gap '+signed(gap,1)+'</span></div>'+
    '</article>';
  }).join('');
  return '<section class="feat" aria-label="Featured projections"><div class="feat-head"><span class="tag">Featured</span><h3>Captured-line projections</h3></div>'+
    '<p class="feat-note">Projections with real captured lines, shown for comparison and ordered by interval width. This is a data-quality view, <b>not</b> a betting signal.</p>'+
    '<div class="feat-grid">'+cards+'</div></section>';
}
/* "Largest gaps" — descriptive comparison of each experimental Model D
   projection against its captured market line. Projection vs line only;
   never a bet, pick, lock, edge or +EV claim. */
function lineCapturedLabel(P){
  const src=P.market_lines_source, cap=P.market_lines_captured_at;
  const srcT=src?'Market lines: '+esc(String(src)):'Market lines';
  const capT=cap?' · captured '+esc(String(cap).replace('T',' ').replace(/(\.\d+).*$/,'').split('+')[0])+' UTC':'';
  return srcT+capT;
}
function gapSpotHTML(P,all){
  if(!P.props.some(pr=>pr.market_line!=null)) return '';
  const rows=all.filter(pr=>pr.market_line!=null&&Number.isFinite(Number(pr.projection))&&Number.isFinite(Number(pr.market_line)))
    .map(pr=>({pr:pr,gap:Number(pr.projection)-Number(pr.market_line)}))
    .sort((a,b)=>Math.abs(b.gap)-Math.abs(a.gap)).slice(0,8);
  if(!rows.length) return '';
  const r=rows.map(x=>{
    const pr=x.pr, g=x.gap, below=g<-0.049;
    const dir=g>0.049?'above the line':below?'below the line':'at the line';
    return '<div class="gro'+(below?' below':'')+'" data-prop="'+esc(prid(pr))+'" role="button" tabindex="0" aria-label="'+esc(pr.player)+' — projection '+fmt(pr.projection,1)+', market line '+fmt(pr.market_line,1)+', '+fmt(Math.abs(g),1)+' '+dir+'">'+
      avatar(initialsOf(pr.player),pr.team,'mini',pr.espn_id)+
      '<div class="gid"><div class="pn">'+esc(pr.player)+'</div><div class="pm">'+esc(pr.team)+' · '+esc(posOf(pr))+' · '+esc(marketLabel(pr.market))+' · vs '+esc(pr.opp)+'</div></div>'+
      '<div class="gn proj"><div class="k">Proj</div><div class="v">'+fmt(pr.projection,1)+'</div></div>'+
      '<div class="gn line"><div class="k">Line</div><div class="v">'+fmt(pr.market_line,1)+'</div></div>'+
      '<div class="gn gap'+(below?' below':'')+'"><div class="k">Gap</div><div class="v">'+signed(g,1)+' '+dir+'</div></div></div>';
  }).join('');
  return '<section class="gapspot" aria-label="Largest gaps"><div class="gs-h"><h3>Largest gaps</h3><span class="src">'+lineCapturedLabel(P)+'</span></div>'+
    '<p class="gs-note">Projection minus the captured market line, for props that ship with a real line. This is descriptive — it compares an experimental model output to a sportsbook line and is <b>not</b> a bet or a signal. Cards without a captured line remain projection-only below.</p>'+
    r+'</section>';
}

function topPropPicks(P){
  return P.props.filter(pr=>pr.market_line!=null&&Number.isFinite(Number(pr.projection))&&Number.isFinite(Number(pr.market_line)))
    .map(pr=>({pr:pr,gap:Number(pr.projection)-Number(pr.market_line)}))
    .sort((a,b)=>Math.abs(b.gap)-Math.abs(a.gap))
    .slice(0,6);
}
function compactPropWhy(pr,gap){
  const w=pr.why||{}, bits=[];
  const opp=Number(w.expected_opportunities), eff=Number(w.expected_efficiency);
  bits.push('The model projects '+fmt(pr.projection,1)+' '+unitOf(pr.market)+', compared with the captured line of '+fmt(pr.market_line,1)+'.');
  if(Number.isFinite(opp)&&Number.isFinite(eff)){
    bits.push('That projection uses '+fmt(opp,1)+' expected '+String(w.opportunity_unit||'opportunities')+' and '+fmt(eff,2)+' '+String(w.efficiency_unit||'efficiency')+'.');
  }
  const context=[];
  const usage={elevated:'recent usage is above its trailing baseline',reduced:'recent usage is below its trailing baseline',stable:'recent usage is in line with its trailing baseline'};
  if(usage[w.recent_usage_note]) context.push(usage[w.recent_usage_note]);
  if(w.team_environment==='favorable') context.push('the team environment is rated favorable');
  else if(w.team_environment==='unfavorable') context.push('the team environment is rated unfavorable');
  if(w.opponent_adjustment==='favorable') context.push('the opponent matchup is rated favorable');
  else if(w.opponent_adjustment==='tough') context.push('the opponent matchup is rated tough');
  if(context.length) bits.push('Among the exported inputs, '+context.slice(0,3).join(', ')+'.');
  bits.push('The result is '+fmt(Math.abs(gap),1)+' '+unitOf(pr.market)+' '+(gap>=0?'above':'below')+' the captured line; that difference is not proof of a betting edge.');
  return bits.slice(0,4).join(' ');
}
function topPropPickCard(x){
  const pr=x.pr,gap=x.gap,over=gap>=0;
  const uncertainty=pr.uncertainty||'Not classified';
  const hasRange=Number.isFinite(Number(pr.p25))&&Number.isFinite(Number(pr.p75));
  return '<article class="ppick" data-prop="'+esc(prid(pr))+'" role="button" tabindex="0" aria-label="'+esc(pr.player)+' '+esc(marketLabel(pr.market))+': model '+(over?'over ':'under ')+fmt(pr.market_line,1)+'">'+
    '<div class="ppick-head">'+avatar(initialsOf(pr.player),pr.team,'mini',pr.espn_id)+'<div class="ppick-id"><div class="ppick-name">'+esc(pr.player)+'</div><div class="ppick-match">'+esc(pr.team)+' · '+esc(posOf(pr))+' · vs '+esc(pr.opp)+'</div></div><span class="ppick-call">Model '+(over?'over ':'under ')+fmt(pr.market_line,1)+'</span></div>'+
    '<div class="ppick-market">'+esc(marketLabel(pr.market))+'</div>'+
    '<div class="pick-flow-label">Projection</div><div class="ppick-nums"><div class="ppick-num model"><div class="k">Model projection</div><div class="v">'+fmt(pr.projection,1)+'</div></div><div class="ppick-num"><div class="k">Market line</div><div class="v">'+fmt(pr.market_line,1)+'</div></div><div class="ppick-num"><div class="k">Difference</div><div class="v">'+signed(gap,1)+'</div></div></div>'+ 
    '<p class="ppick-why"><b>Why:</b> '+esc(compactPropWhy(pr,gap))+'</p>'+
    '<div class="pick-flow-label">Uncertainty</div><div class="ppick-foot"><span class="uncert">'+esc(uncertainty)+' uncertainty</span>'+(hasRange?'<span>· expected range '+fmt(pr.p25,1)+'–'+fmt(pr.p75,1)+'</span>':'')+'<span style="margin-left:auto">Details →</span></div></article>';
}
function topPropPicksHTML(P){
  const rows=topPropPicks(P);
  if(!rows.length) return '<div class="info-empty">No captured market lines are available, so there are no model picks to rank yet.</div>';
  return '<div class="prop-picks-intro"><div><h2>Top Model Picks</h2><p>Largest differences between the model projection and a captured market line. Ranked by absolute gap; research-only, not a claim of betting edge.</p></div><span class="prop-count">'+rows.length+' shown · '+P.props.filter(x=>x.market_line!=null).length+' lines captured</span></div><div class="prop-picks-grid">'+rows.map(topPropPickCard).join('')+'</div>';
}

function expFormatNgs(v){
  if(!v) return 'Not emitted — no live prediction';
  const latest=Array.isArray(v.latest_season_week)?'latest '+v.latest_season_week[0]+'-W'+v.latest_season_week[1]:'';
  const required=Array.isArray(v.required_release)?'required '+v.required_release[0]+'-W'+v.required_release[1]:'';
  return [v.pulled_at,latest,required,v.note].filter(Boolean).join(' · ');
}
function expFallbackLabel(pr){
  if(!pr) return 'Not applicable — no live prediction';
  if(pr.fallback_to_M1) return 'Yes — M1 fallback used';
  if(pr.stale_ngs_used) return 'Yes — stale NGS vector used';
  return 'No — current NGS used; no fallback';
}
function expLineSource(pr){
  if(!pr) return 'Not captured — no live prediction';
  return pr.market_line_source||pr.line_source||(pr.market_line==null?'Not captured':'Not supplied in export');
}
function expLineCaptured(pr){
  if(!pr) return 'Not captured — no live prediction';
  return pr.market_line_capture_timestamp||pr.market_line_captured_at||pr.line_captured_at||(pr.market_line==null?'Not captured':'Not supplied in export');
}
function expProvenanceHTML(pr,market){
  const rows=[
    ['Prediction timestamp',pr&&pr.prediction_timestamp||market&&market.prediction_timestamp||'Not generated — live integration pending'],
    ['NGS data as of',expFormatNgs(pr&&pr.ngs_data_as_of)],
    ['Latest player game included',pr&&pr.latest_game_included||'Not emitted — no live prediction'],
    ['Feature window',pr&&pr.feature_window||'Not emitted — no live prediction'],
    ['Model version',pr&&pr.model_version||market&&market.model_version||'—'],
    ['Market line source',expLineSource(pr)],
    ['Market line capture timestamp',expLineCaptured(pr)],
    ['Fallback / stale NGS used',expFallbackLabel(pr)]
  ];
  return '<div class="exp-prov">'+rows.map(r=>'<div class="pv"><div class="pk">'+esc(r[0])+'</div><div class="pvv">'+esc(r[1])+'</div></div>').join('')+'</div>';
}
function expMarketSummary(m){
  const live=m.status==='experimental'&&Number(m.n_projections)>0;
  return '<article class="exp-market'+(live?' live-market':'')+'"><div class="mh"><div><h3>'+esc(m.title)+' — Experimental</h3><p class="sub">This market is still being tested and does not have a fully validated track record yet.</p></div><span class="exp-badge'+(live?'':' pending')+'">'+(live?fmtInt(m.n_projections)+' live':'Pending integration')+'</span></div>'+
    '<div class="exp-meta"><span><b>'+fmtInt(m.n_projections||0)+'</b> current projections</span><span>Full data details are available on each projection</span></div>'+
    (!live?'<details class="exp-pending"><summary>Pending-market provenance</summary>'+expProvenanceHTML(null,m)+'</details>':'')+'</article>';
}
function expCard(pr,i,market){
  const id=market.market+':'+i;
  const isReceptions=market.market==='receptions';
  const unit=isReceptions?'receptions':'attempts';
  const pos=pr.position?' · '+esc(pr.position):market.market==='rush_attempts'?' · RB':'';
  const hasRange=isReceptions&&Number.isFinite(Number(pr.interval_p25))&&Number.isFinite(Number(pr.interval_p75));
  const uncertainty=hasRange?esc(pr.uncertainty||'Uncertainty available'):'Uncertainty not calibrated';
  const range=hasRange?'Expected range '+fmt(pr.interval_p25,1)+'–'+fmt(pr.interval_p75,1):'';
  pr._expId=id;
  return '<article class="expcard" data-exp-prop="'+id+'" role="button" tabindex="0" aria-label="Experimental '+esc(market.title.toLowerCase())+' projection for '+esc(pr.player)+'">'+
    '<div class="eh">'+avatar(initialsOf(pr.player),pr.team,'mini',null)+'<div class="eid"><div class="pn">'+esc(pr.player)+'</div><div class="pm">'+esc(pr.team)+pos+' · vs '+esc(pr.opp)+'</div></div><span class="exp-badge">Experimental</span></div>'+
    '<div class="ek">'+(isReceptions?'Player-tracking receptions':'Player-tracking rush attempts')+'</div><div class="ev">'+fmt(pr.projection,1)+'</div><div class="eu">projected '+unit+'</div>'+
    '<div class="ef"><span class="warn">'+uncertainty+'</span>'+(range?'<span>·</span><span>'+range+'</span>':'')+'<span>·</span><span>'+(pr.market_line==null?'No captured line':'Line '+fmt(pr.market_line,1))+'</span></div></article>';
}
function experimentalMarketsHTML(){
  const E=state.experimental;
  if(!E||!Array.isArray(E.markets)) return '<div class="exp-inline"><div class="info-empty">Experimental-market snapshot unavailable.</div></div>';
  const receptions=E.markets.find(m=>m.market==='receptions');
  const rush=E.markets.find(m=>m.market==='rush_attempts');
  const markets=[receptions,rush].filter(Boolean);
  const q=state.expQ.trim().toLowerCase();
  const rows=[];
  markets.forEach(m=>(Array.isArray(m.projections)?m.projections:[]).forEach((pr,i)=>{
    if(!q||String(pr.player).toLowerCase().includes(q)||String(pr.team).toLowerCase().includes(q)||String(pr.opp).toLowerCase().includes(q)||String(m.title).toLowerCase().includes(q)) rows.push({pr:pr,i:i,market:m});
  }));
  const shown=rows.slice(0,state.expShown);
  const pending=markets.filter(m=>m.status!=='experimental'||!Number(m.n_projections)).map(m=>m.title);
  return '<div class="exp-inline" aria-label="Experimental player projections">'+
    '<div class="exp-note"><b>Experimental — still being tested.</b> Research projection only. No verified betting edge established.</div>'+
    '<div class="exp-markets">'+markets.map(expMarketSummary).join('')+'</div>'+
    (rows.length||q?'<div class="exp-proj-head"><div><h3>Experimental projections</h3><p>'+fmtInt(rows.length)+' live projections · provenance available in every card detail</p></div><input id="expQ" class="exp-search" type="search" placeholder="Search experimental projections…" value="'+esc(state.expQ)+'" aria-label="Search experimental player projections"></div>'+
    '<div class="exp-grid">'+shown.map(x=>expCard(x.pr,x.i,x.market)).join('')+'</div>'+
    (rows.length>shown.length?'<div class="showmore"><button class="btn" id="expMore">Show all '+fmtInt(rows.length)+' experimental projections</button></div>':'')+
    (rows.length?'':'<div class="info-empty">No experimental projections match this search.</div>'):'')+
    '<p class="viz-note">'+(rush&&Number(rush.n_projections)?'Rush Attempts is live as an experimental projection. ':'')+(receptions&&Number(receptions.n_projections)?'Receptions is live as an experimental projection. ':pending.length?pending.join(' and ')+' remains pending integration. ':'')+'Both markets stay research-only until prospective timestamped line tracking supports a separate conclusion.</p></div>';
}
function openExperimentalProp(id){
  const E=state.experimental;
  let market=null,pr=null;
  (E&&E.markets||[]).some(m=>{
    const found=Array.isArray(m.projections)&&m.projections.find(x=>x._expId===id);
    if(found){market=m;pr=found;return true;}
    return false;
  });
  if(!pr||!market) return;
  const comp=pr.projection_components||{};
  const isReceptions=market.market==='receptions';
  const unit=isReceptions?'receptions':'rush attempts';
  const pos=pr.position?' · '+esc(pr.position):market.market==='rush_attempts'?' · RB':'';
  const hasRange=isReceptions&&Number.isFinite(Number(pr.interval_p25))&&Number.isFinite(Number(pr.interval_p75));
  const uncertainty=hasRange?esc(pr.uncertainty||'Uncertainty available'):'Uncertainty not calibrated';
  const componentA=comp.A_two_stage_ridge??comp.A_ridge;
  let html=ovlHead('Experimental projection',pr.player,esc(pr.team)+pos+' · vs '+esc(pr.opp));
  html+='<div class="exp-note"><b>Still being tested.</b> Research projection only. No verified betting edge established.</div>'+
    '<div class="ova-head">'+avatar(initialsOf(pr.player),pr.team,'hero-ava',null)+'<div style="flex:1;min-width:180px"><div style="font-size:58px;font-weight:900;letter-spacing:-.03em;line-height:1">'+fmt(pr.projection,1)+'</div><div style="color:var(--faint);font-size:13px;margin-top:6px">projected '+unit+'</div></div><span class="chip unc">'+uncertainty+'</span></div>'+
    '<div class="why-box"><p>'+(hasRange?'The model&rsquo;s expected range is <b>'+fmt(pr.interval_p25,1)+'–'+fmt(pr.interval_p75,1)+' receptions</b>.':'This market has a point projection only; no player-specific range was calibrated.')+'</p><p class="smallfoot">'+(hasRange?'This range shows how widely the projection can vary; it is not a probability of being correct.':'The uncertainty label is not a calibrated player-specific assessment.')+'</p></div>'+
    '<div class="section-head reset" style="margin-top:20px"><h2 style="font-size:18px">Data details</h2></div>'+expProvenanceHTML(pr,market)+
    '<details class="page-sub" style="margin-top:14px"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body"><p><b>Model components:</b> A '+fmt(componentA,2)+' · B '+fmt(comp.B_gbm,2)+' · median '+fmt(comp.C_quantile_median,2)+'.</p><p class="smallfoot">'+esc(comp.D||'The displayed projection combines the exported component values.')+'</p><p class="smallfoot">'+esc(pr.uncertainty_note||'No calibrated uncertainty interval is available for this experimental market.')+'</p></div></details>'+
    '<div class="section-head reset" style="margin-top:20px"><h2 style="font-size:18px">Market line</h2></div><div class="why-box"><p>'+(pr.market_line==null?'No market line is captured for this projection — <b>projection only, no lean</b>.':'Captured line: <b>'+fmt(pr.market_line,1)+'</b>.')+'</p><p class="smallfoot">Timestamped market capture is kept separate from the projection and does not turn it into a betting recommendation.</p></div>';
  openOverlay(html,'Experimental projection: '+pr.player);
}

function renderProps(){
  const P=state.data.props;
  if(!P.props[0]._id) P.props.forEach((pr,i)=>pr._id='px'+i);
  const teams=[...new Set(P.props.map(pr=>pr.team))].sort();
  const all=filteredProps(), shown=all.slice(0,state.propShown);
  const withLines=P.props.filter(x=>x.market_line!=null).length;
  const withEspn=P.props.filter(x=>x.espn_id).length;
  const wk=state.data.meta&&state.data.meta.latest_week?state.data.meta.latest_week:4;
  const lineStatus=withLines?fmtInt(withLines)+' of '+fmtInt(P.props.length)+' projections have a captured market line.':'Market lines have not been captured yet, so every card is projection-only.';
  const sortOpts=Object.keys(SORTS).map(k=>'<option value="'+k+'"'+(state.propSort===k?' selected':'')+'>'+esc(SORTS[k])+'</option>').join('');
  return '<section class="pboard"><div class="page-head" style="margin-bottom:0"><p class="kicker">Week '+wk+' · research only</p><h1>Player Props</h1>'+
    '<p class="desc">Start with the model’s largest projection-to-line differences, then search the complete board. '+lineStatus+'</p></div>'+
    topPropPicksHTML(P)+
    '<div class="prop-browser-head"><div><h2>All Player Projections</h2><p>Filter by market, uncertainty, team, or player. Open any card for its inputs and full explanation.</p></div><span class="prop-count">'+fmtInt(P.props.length)+' projections</span></div>'+
    '<div class="pboard-markets"><span class="fgroup-label">Market</span>'+fc('propMarket','all','All')+fc('propMarket','pass_yards','Passing')+fc('propMarket','rush_yards','Rushing')+fc('propMarket','receiving_yards','Receiving')+'</div></section>'+
  '<div class="chips" style="margin:12px 0 10px"><span class="fgroup-label">Uncertainty</span>'+fc('propUnc','all','All')+fc('propUnc','High','High')+fc('propUnc','Medium','Medium')+fc('propUnc','Low','Low')+
  '<button class="fchip'+(state.propUncOnly?' on':'')+'" data-unc="1">High only</button></div>'+
  '<div class="search-row"><input id="propQ" type="search" placeholder="Search player, team, or opponent…" value="'+esc(state.q)+'" aria-label="Search projections">'+
  '<select id="propTeamSel" class="sel" aria-label="Team"><option value="all">All teams</option>'+teams.map(t=>'<option value="'+t+'"'+(state.propTeam===t?' selected':'')+'>'+t+'</option>').join('')+'</select>'+
  '<select id="propSortSel" class="sel" aria-label="Sort">'+sortOpts+'</select></div>'+
  '<p class="viz-note" style="margin:12px 0 14px">Showing '+shown.length+' of '+all.length+' projections · sorted '+(SORTS[state.propSort]||'').toLowerCase()+'</p>'+
  '<div class="prop-grid">'+shown.map(propCard).join('')+'</div>'+
  (all.length>shown.length?'<div class="showmore"><button class="btn" id="propMore">Show more ('+fmtInt(shown.length)+' of '+fmtInt(all.length)+')</button></div>':'')+
  (all.length?'':'<div class="info-empty" style="margin-top:14px">No projections match these filters.</div>')+
  '<details class="page-sub" style="margin-top:30px"><summary><span>Experimental receptions &amp; rush attempts</span><span class="ch"></span></summary><div class="sub-body">'+experimentalMarketsHTML()+'</div></details>'+
  '<details class="page-sub"><summary><span>Technical details: how to read this board</span><span class="ch"></span></summary><div class="sub-body"><p><b>Research only.</b> '+esc(P.disclaimer)+'</p><p>Top Model Picks are ranked only by the absolute difference between the model projection and the captured line. A larger difference is not proof of a betting edge.</p><p>Uncertainty describes interval reliability, not correctness. The calibration check found the narrowest P25–P75 buckets had the highest realized error, so a <b>High uncertainty</b> label never means a higher chance of being right.</p><p>'+fmtInt(withLines)+' projections have captured lines; '+fmtInt(P.props.length-withLines)+' remain projection-only. Player IDs are available for '+fmtInt(withEspn)+' rows.</p></div></details>';
}
function bindProps(){
  app.querySelectorAll('[data-fg]').forEach(b=>b.onclick=()=>{state[b.dataset.fg]=b.dataset.fv;state.propShown=120;render();});
  const u=app.querySelector('[data-unc]'); if(u) u.onclick=()=>{state.propUncOnly=!state.propUncOnly;state.propShown=120;render();};
  const ts=app.querySelector('#propTeamSel'); if(ts) ts.onchange=()=>{state.propTeam=ts.value;state.propShown=120;render();};
  const ss=app.querySelector('#propSortSel'); if(ss){ss.value=state.propSort; ss.onchange=()=>{state.propSort=ss.value;render();};}
  const qq=app.querySelector('#propQ');
  if(qq){ let t; qq.oninput=()=>{clearTimeout(t); t=setTimeout(()=>{state.q=qq.value;state.propShown=120;render();const q2=document.getElementById('propQ'); if(q2){q2.focus();q2.setSelectionRange(q2.value.length,q2.value.length);}},220);}; }
  const more=app.querySelector('#propMore'); if(more) more.onclick=()=>{state.propShown+=200;render();};
  const eq=app.querySelector('#expQ');
  if(eq){ let et; eq.oninput=()=>{clearTimeout(et); et=setTimeout(()=>{state.expQ=eq.value;state.expShown=12;render();const q2=document.getElementById('expQ'); if(q2){q2.focus();q2.setSelectionRange(q2.value.length,q2.value.length);}},220);}; }
  const em=app.querySelector('#expMore'); if(em) em.onclick=()=>{state.expShown=100;render();};
}
/* Plain-English "WHY THIS PROJECTION?" — generated ONLY from the export's
   why fields and the row's sibling fields, and only when the data supports
   the statement. Tokens never seen in the export fall back to printing the
   raw token rather than inventing a meaning for it. */
const WHY_USAGE={elevated:'is elevated relative to the trailing baseline',reduced:'runs below the trailing baseline',stable:'is in line with the trailing baseline'};
const WHY_NOUN={pass_yards:'passing volume',rush_yards:'rushing workload',receiving_yards:'receiving usage'};
function whySentences(pr){
  const w=pr.why||{}, out=[];
  const noun=WHY_NOUN[pr.market]||'usage';
  const tg=Number(pr.trailing_games);
  const scope=Number.isFinite(tg)&&tg>0?' ('+fmtInt(tg)+' games trailing)':'';
  const uv=w.recent_usage_note;
  if(uv&&WHY_USAGE[uv]) out.push({k:'Recent usage',s:'Recent '+noun+' '+WHY_USAGE[uv]+scope+'.'});
  else if(uv) out.push({k:'Recent usage',s:'The export ships the usage token \u201C'+uv+'\u201D, which is not a supported description, so no plain-English statement is drawn from it.'});
  if(w.team_environment==='favorable') out.push({k:'Team environment',s:'The team environment is rated favorable.'});
  else if(w.team_environment==='unfavorable') out.push({k:'Team environment',s:'The team environment is rated unfavorable, a drag on the projection.'});
  if(w.opponent_adjustment==='tough') out.push({k:'Opponent',s:'The opponent matchup is rated tough.'});
  else if(w.opponent_adjustment==='favorable') out.push({k:'Opponent',s:'The opponent matchup is rated favorable.'});
  if(pr.uncertainty_flag){ let h='Projection uncertainty is elevated.'; if(pr.uncertainty_note) h+=' '+String(pr.uncertainty_note).trim(); out.push({k:'Uncertainty',s:h}); }
  const pb=Number(pr.projection), bl=Number(pr.baseline_ewma), d=pb-bl;
  if(Number.isFinite(pb)&&Number.isFinite(bl)) out.push({k:'Model D vs baseline',s:'Model D\u2019s '+fmt(pb,1)+' sits '+fmt(Math.abs(d),1)+' '+(unitOf(pr.market)||'yards')+' '+(d>0.049?'above':d<-0.049?'below':'about level with')+' the EWMA baseline of '+fmt(bl,1)+'.'});
  return out;
}
function whySentHtml(pr){
  const w=pr.why||{};
  const list=whySentences(pr).map(r=>'<li><span class="k">'+esc(r.k)+'</span><span>'+esc(r.s)+'</span></li>').join('');
  return '<ul class="why-sent">'+list+'</ul>'+
    '<p class="viz-note">Why tokens shipped with the export: usage \u201C'+esc(String(w.recent_usage_note||'—'))+'\u201D · team environment \u201C'+esc(String(w.team_environment||'—'))+'\u201D · opponent \u201C'+esc(String(w.opponent_adjustment||'—'))+'\u201D.</p>';
}
function marketLineSection(pr){
  const gap=Number(pr.projection)-Number(pr.market_line);
  const head='<div class="section-head reset" style="margin-top:20px"><h2 style="font-size:18px">Projection vs market line</h2></div>';
  if(pr.market_line==null||!Number.isFinite(gap))
    return head+'<div class="why-box"><p>No market line is captured for this projection yet — <b>projection only, no lean</b>. Projection, line, and lean are kept as separate concepts; without a market line there is nothing to compare the projection against.</p><p class="smallfoot">No calibrated probabilities are produced. This is experimental paper tracking only.</p></div>';
  const kv=(l,v)=>'<div class="kv"><div class="k">'+l+'</div><div class="v">'+v+'</div></div>';
  return head+'<div class="kv-grid">'+kv('Model D projection',fmt(pr.projection,1))+kv('Market line',fmt(pr.market_line,1))+kv('Gap (projection − line)',signed(gap,1))+'</div>'+
    '<p class="viz-note">A gap is a comparison, not a lean. This product makes no betting recommendations.</p>';
}
function openProp(pid){
  const pr=state.data.props.props.find(x=>x._id===pid); if(!pr) return;
  const unit=unitOf(pr.market), w=pr.why||{};
  const gap=Number(pr.projection)-Number(pr.market_line), hasLine=pr.market_line!=null&&Number.isFinite(gap);
  let html=ovlHead('Player projection · '+esc(marketLabel(pr.market)),pr.player,esc(pr.team)+' · '+esc(posOf(pr))+' · vs '+esc(pr.opp));
  html+='<div class="pick-flow-label">Pick</div><div class="ova-head">'+avatar(initialsOf(pr.player),pr.team,'hero-ava',pr.espn_id)+'<div style="flex:1;min-width:180px">'+(hasLine?'<span class="chip pick">Model '+(gap>=0?'over ':'under ')+fmt(pr.market_line,1)+'</span>':'<span class="chip noplay">Projection only · no line</span>')+'</div></div>'+
  '<div class="pick-flow-label">Projection</div><div class="kv-grid"><div class="kv hero-kv"><div class="k">Model projection</div><div class="v">'+fmt(pr.projection,1)+'</div></div><div class="kv"><div class="k">Captured line</div><div class="v">'+(hasLine?fmt(pr.market_line,1):'—')+'</div></div><div class="kv"><div class="k">Difference</div><div class="v">'+(hasLine?signed(gap,1):'—')+'</div></div></div>'+
  '<div class="pick-flow-label">Why</div><div class="game-why">'+esc(hasLine?compactPropWhy(pr,gap):'The model projects '+fmt(pr.projection,1)+' '+unit+'. No market line is captured, so there is no model-versus-market comparison.')+'</div>'+
  '<div class="pick-flow-label">Uncertainty</div><div class="game-uncertainty"><b>'+esc(pr.uncertainty)+' uncertainty.</b> Expected range '+fmt(pr.p25,1)+'–'+fmt(pr.p75,1)+'. This range describes variation, not the chance that the projection is correct.</div>'+
  '<details class="page-sub" style="margin-top:18px"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body">'+rangeViz(pr)+
  '<div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0">'+(pr.uncertainty_flag?'<span class="chip unc">Elevated uncertainty</span>':'')+(pr.uncertainty_note?'<span class="chip na">'+esc(pr.uncertainty_note)+'</span>':'')+'<span class="chip na">EWMA baseline '+fmt(pr.baseline_ewma,1)+'</span><span class="chip na">Trailing '+fmtInt(pr.trailing_games)+' games</span></div>'+
  '<div class="section-head reset" style="margin-top:20px"><h2 style="font-size:18px">Opportunity × efficiency</h2></div><div class="decomp"><div class="decomp-row"><div class="decomp-cell"><div class="n">'+fmt(w.expected_opportunities,1)+'</div><div class="d">'+esc(w.opportunity_unit||'opportunities')+'</div></div><div class="decomp-x">×</div><div class="decomp-cell"><div class="n">'+fmt(w.expected_efficiency,2)+'</div><div class="d">'+esc(w.efficiency_unit||'efficiency')+'</div></div></div><p class="viz-note">These are exported explanation fields; they are not recomputed in the page.</p></div>'+whySentHtml(pr)+marketLineSection(pr)+'</div></details>';
  openOverlay(html,'Prop: '+pr.player);
}

/* ============================================================
   TEAMS — POWER BOARD
   ============================================================ */
const teamNetSR=(t)=>Number(t.off_sr)-Number(t.def_sr);
const pctS=(v,d=1)=>{const x=Number(v);return Number.isFinite(x)?(x*100>=0?'+':'')+(x*100).toFixed(d)+'%':'—';};
/* Metric catalog — every entry is an exported teams.json field, except net_sr
   which is derived as off_sr − def_sr. No other team statistics exist in the
   export, so no other metrics are displayed anywhere on this page. */
const METRICS={
  elo:{label:'Team rating',full:'Overall team strength',lowGood:false,f:v=>fmt(v,0)},
  off_epa:{label:'Offense/play',full:'Offensive performance per play',lowGood:false,f:v=>signed(v,3)},
  def_epa:{label:'Defense/play',full:'Defensive performance allowed per play',lowGood:true,f:v=>signed(v,3)},
  off_pass_epa:{label:'Pass offense',full:'Passing performance per play',lowGood:false,f:v=>signed(v,3)},
  off_rush_epa:{label:'Rush offense',full:'Rushing performance per play',lowGood:false,f:v=>signed(v,3)},
  def_pass_epa:{label:'Pass defense',full:'Passing performance allowed per play',lowGood:true,f:v=>signed(v,3)},
  def_rush_epa:{label:'Rush defense',full:'Rushing performance allowed per play',lowGood:true,f:v=>signed(v,3)},
  off_sr:{label:'Offense rate',full:'Offensive success rate',lowGood:false,f:v=>pct1(v,1)},
  def_sr:{label:'Defense rate',full:'Defensive success rate allowed',lowGood:true,f:v=>pct1(v,1)},
  net_sr:{label:'Net rate',full:'Net success rate',lowGood:false,f:v=>pctS(v,1)}
};
const metricVal=(t,key)=>key==='net_sr'?teamNetSR(t):Number(t[key]);
const LENSES={
  elo:{rating:'elo',metrics:['off_epa','def_epa','net_sr'],ratedLabel:'overall team strength — higher is stronger, #1 is the league\u2019s top rating'},
  offense:{rating:'off_epa',metrics:['off_pass_epa','off_rush_epa','off_sr'],ratedLabel:'offensive performance per play — higher is better, #1 is the league\u2019s top offense'},
  defense:{rating:'def_epa',metrics:['def_pass_epa','def_rush_epa','def_sr'],ratedLabel:'defensive performance allowed per play — lower is better, #1 is the league\u2019s top defense'}
};
/* Ranks and league context always cover the full visible rating set. */
function scopedRanks(teams,key,lowGood){
  const s=[...teams].sort((a,b)=>(Number(metricVal(a,key))-Number(metricVal(b,key)))*(lowGood?1:-1));
  const r={};s.forEach((t,i)=>r[t.team]=i+1);return r;
}
function leagueStats(teams,key){
  const vals=teams.map(t=>metricVal(t,key)).filter(Number.isFinite);
  const lo=Math.min.apply(null,vals),hi=Math.max.apply(null,vals);
  return {lo:lo,hi:hi,sp:(hi-lo)||1,avg:vals.reduce((s,v)=>s+v,0)/vals.length};
}
function fmtSnapshotTs(iso){
  const m=String(iso||'').match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m?m[1]+' '+m[2]+' UTC':String(iso||'—');
}
function teamsActive(){
  const T=state.data.teams, baseline=state.teamView==='baseline';
  if(baseline&&T.preseason_baseline){
    const pb=T.preseason_baseline;
    return {baseline:true,teams:pb.teams,label:pb.label||'Preseason Baseline — 2026',
      dataThrough:'Preseason 2026 (2025 final pre-game ratings)',
      generated:String(pb.data_as_of||'').replace(' 00:00:00','')||'—',note:pb.note||''};
  }
  return {baseline:false,teams:T.teams,label:T.label||'Current Ratings',
    dataThrough:T.data_through||'—',generated:fmtSnapshotTs(T.snapshot_generated_at),
    latestGame:T.latest_game_included||'',note:T.note||''};
}
function rankClass(rk,n){return rk<=8?' top':(rk>=n-7?' bot':'');}
function seg(group,val,label){return '<button class="sseg'+(state[group]===val?' on':'')+'" data-fg="'+group+'" data-fv="'+val+'">'+esc(label)+'</button>';}
function rankWords(rank,total){
  if(rank<=6) return 'Strong';
  if(rank<=13) return 'Above average';
  if(rank<=20) return 'Middle of the league';
  if(rank<=27) return 'Below average';
  return 'Struggling';
}
function teamLeadHTML(t,all,tv){
  if(!t) return '';
  const overall=scopedRanks(all,'elo',false)[t.team];
  const offense=scopedRanks(all,'off_epa',false)[t.team];
  const defense=scopedRanks(all,'def_epa',true)[t.team];
  const g=state.data.predictions.games.find(x=>x.away===t.team||x.home===t.team);
  const opp=g?(g.away===t.team?g.home:g.away):null;
  return '<section class="team-lead" aria-label="Plain-language team summary">'+
    '<div class="identity">'+logo(t.team,'lg')+'<div><div class="name">'+esc(teamName(t.team))+'</div><div class="overall">'+esc(rankWords(overall,all.length))+' team overall · #'+overall+' of '+all.length+'</div></div></div>'+
    '<div><div class="k">Offense</div><div class="v">'+esc(rankWords(offense,all.length))+' · #'+offense+'</div></div>'+
    '<div><div class="k">Defense</div><div class="v">'+esc(rankWords(defense,all.length))+' · #'+defense+'</div></div>'+
    '<div><div class="k">Recent form</div><div class="v">Not available in this snapshot</div></div>'+
    '<div><div class="k">Next matchup</div><div class="v">'+(opp?esc(teamName(opp)):'No game listed')+'</div></div></section>';
}
function renderTeams(){ 
  if(state.teamView==='winprob') return winProbBoard();
  const tv=teamsActive(), all=tv.teams, nv=all.length;
  const L=LENSES[state.teamLens]||LENSES.elo;
  const RM=METRICS[L.rating];
  const q=String(state.teamQuery||'').trim().toLowerCase();
  const rows=all.filter(t=>!q||t.team.toLowerCase().indexOf(q)>=0||teamName(t.team).toLowerCase().indexOf(q)>=0);
  const rRank=scopedRanks(all,L.rating,RM.lowGood);
  const mets=L.metrics.map(k=>({key:k,M:METRICS[k],r:scopedRanks(all,k,METRICS[k].lowGood),st:leagueStats(all,k)}));
  const sorted=[...rows].sort((a,b)=>rRank[a.team]-rRank[b.team]);
  const prov=
    '<div class="teams-prov'+(tv.baseline?' ref':'')+'">'+
      '<div class="status-line">'+(tv.baseline
        ? '<span class="chip refmark">Reference only</span><span class="chip refmark">NOT the ratings driving current predictions</span>'
        : '<span class="chip live">Live rating set</span><span class="chip na">The exact ratings V1 used for this week\u2019s predictions</span>')+'</div>'+
      '<div class="grid">'+
        '<div><div class="k">Data through</div><div class="v">'+esc(tv.dataThrough)+'</div></div>'+
        '<div><div class="k">'+(tv.baseline?'Data as of':'Generated')+'</div><div class="v">'+esc(tv.generated)+'</div></div>'+
        (!tv.baseline&&tv.latestGame?'<div><div class="k">Latest game included</div><div class="v verstamp vstamp" style="font-size:14px">'+esc(tv.latestGame)+'</div></div>':'')+
      '</div>'+
      (tv.note?'<p class="note">'+esc(tv.note)+'</p>':'')+
    '</div>';
  return pageHead(tv.baseline?'Teams · Reference':'Teams',tv.label,
    tv.baseline
      ? 'A preseason reference kept only for comparison. Start with the plain-language summary; detailed ratings and league comparisons follow below.'
      : 'Start with a plain-language team read. The rating board and comparison bars below provide the supporting detail.')+
  teamLeadHTML(sorted[0],all,tv)+
  '<div class="rtoggle">'+seg('teamView','current','Current ratings — through Week 3')+seg('teamView','baseline','Preseason reference')+seg('teamView','winprob','Win chances · Week 4')+'</div>'+ 
  prov+
  '<div class="board-ctrl"><div class="lens-row"><span class="fgroup-label">Lens</span>'+fc('teamLens','elo','Team strength')+fc('teamLens','offense','Offense')+fc('teamLens','defense','Defense')+'</div>'+
  '<input id="teamQ" class="team-search" type="search" autocomplete="off" spellcheck="false" placeholder="Search team" value="'+esc(state.teamQuery)+'" aria-label="Search teams"></div>'+
  '<p class="lens-note">Board ranked by '+esc(L.ratedLabel)+'. Each metric shows value + NFL rank; bars are the league range.'+(q?' Showing '+rows.length+' of '+nv+' teams.':'')+'</p>'+
  '<div class="power-board'+(tv.baseline?' ref':'')+'">'+sorted.map(t=>{
    const rk=rRank[t.team];
    const ms=mets.map(mt=>{
      const v=metricVal(t,mt.key), r=mt.r[t.team];
      const qp=mt.M.lowGood?(mt.st.hi-v)/mt.st.sp:(v-mt.st.lo)/mt.st.sp;
      return '<span class="met"><span class="ml">'+esc(mt.M.label)+'</span><span class="mvr"><span class="mv">'+esc(mt.M.f(v))+'</span><span class="rkb'+rankClass(r,nv)+'">#'+r+'</span></span><span class="bar"><i style="width:'+Math.max(4,qp*100)+'%"></i></span></span>';
    }).join('');
    return '<div class="prow'+(rk<=3?' top3':'')+'" data-team="'+esc(t.team)+'" role="button" tabindex="0" aria-label="'+esc(teamName(t.team))+'"><span class="rk">'+rk+'</span>'+
    '<span class="tm">'+logo(t.team,'lg')+'<span class="idname"><span class="ab">'+esc(t.team)+'</span><span class="fn">'+esc(teamName(t.team))+'</span></span></span>'+
    '<span class="rating"><span class="rl tooltip" title="'+(L.rating==='elo'?'A game-updated measure of team strength; higher is stronger.':'The ranking metric for this view.')+'">'+esc(RM.full)+'</span><span class="rv">'+esc(RM.f(metricVal(t,L.rating)))+'</span><span class="rr">#'+rk+' NFL</span></span>'+
    '<span class="met-set">'+ms+'</span></div>';
  }).join('')+'</div>'+
  (rows.length?'':'<div class="info-empty" style="margin-top:14px">No teams match \u201C'+esc(state.teamQuery)+'\u201D.</div>')+
  '<p class="sort-cap">Bars are scaled to the league range — for allowed metrics, a fuller bar means a stronger defense. Every rank is across all '+nv+' teams in the active set. Explosive play rate and points per drive are not carried in the export, so they are unavailable here.</p>';
}
function bindTeams(){
  app.querySelectorAll('[data-fg]').forEach(b=>b.onclick=()=>{state[b.dataset.fg]=b.dataset.fv;render();});
  const tq=app.querySelector('#teamQ');
  if(tq){ tq.oninput=()=>{state.teamQuery=tq.value;render();};
    tq.onkeydown=e=>{ if(e.key==='Enter') e.preventDefault(); };
    tq.value=state.teamQuery; tq.focus(); tq.setSelectionRange(tq.value.length,tq.value.length);
  }
}
/* Team detail — rich profile with league-average context for every metric. */
function mblock(ab,key,t,all){
  const M=METRICS[key], nv=all.length;
  const v=metricVal(t,key), st=leagueStats(all,key);
  const rk=scopedRanks(all,key,M.lowGood)[ab];
  const diff=v-st.avg;
  const ctx=diff===0?'equal to':(M.lowGood?(diff<0):(diff>0))?'above':'below';
  const tpct=((v-st.lo)/st.sp*100).toFixed(1), apct=((st.avg-st.lo)/st.sp*100).toFixed(1);
  return '<div class="mblock"><div class="mk">'+esc(M.full)+'</div>'+
    '<div class="mr0"><div class="mv"><span class="tb">'+esc(ab)+'</span>'+esc(M.f(v))+'</div><span class="rkc'+rankClass(rk,nv)+'">#'+rk+' NFL</span></div>'+
    '<div class="avg">League average <b>'+esc(M.f(st.avg))+'</b> \u00b7 '+esc(ctx)+' the league average</div>'+
    '<div class="cmpbar"><div class="fl" style="width:'+Math.max(2,tpct)+'%"></div><div class="avgm" style="left:'+apct+'%"></div><div class="td" style="left:'+tpct+'%"></div></div>'+
    '<div class="lr">League range '+esc(M.f(st.lo))+' \u2192 '+esc(M.f(st.hi))+' \u00b7 '+(M.lowGood?'lower is better':'higher is better')+'</div></div>';
}
function missingBlock(label){
  return '<div class="mblock miss"><div class="mk">'+esc(label)+'</div><div class="mv">\u2014</div><div class="lr">Not carried in this export \u2014 unavailable</div></div>';
}
function formRows(abbr,t,T,tv){
  const rows=[];
  rows.push('<div class="frow"><div class="fk">Data through</div><div class="fd">'+esc(tv.dataThrough)+'</div></div>');
  rows.push('<div class="frow"><div class="fk">'+(tv.baseline?'Data as of':'Generated')+'</div><div class="fd">'+esc(tv.generated)+(tv.latestGame?' \u00b7 latest game included '+esc(tv.latestGame):'')+'</div></div>');
  if(!tv.baseline&&T.preseason_baseline){
    const b=T.preseason_baseline.teams.find(x=>x.team===abbr);
    if(b){
      rows.push('<div class="frow"><div class="fk">2026 preseason reference</div><div class="fd">Comparing the current rating against the preseason baseline from before the season.</div></div>');
      ['elo','off_epa','def_epa'].forEach(key=>{
        const M=METRICS[key], cur=metricVal(t,key), bs=metricVal(b,key), d=cur-bs;
        const good=M.lowGood?(d<0):(d>0);
        const cls=d===0?'delta-eq':(good?'delta-pos':'delta-neg');
        rows.push('<div class="frow"><div class="fk">'+esc(M.full)+'</div><div class="fd">Preseason reference '+esc(M.f(bs))+'</div><div class="fvv"><span class="'+cls+'">'+esc(M.f(cur))+' ('+signed(d,key==='elo'?0:3)+')</span></div></div>');
      });
    }
  }
  rows.push('<div class="frow"><div class="fk">Recent performance</div><div class="fd">No game-by-game record is carried in the export \u2014 this dashboard only receives the current rating snapshot, so recent form cannot be shown.</div></div>');
  return rows.join('');
}
function openTeam(abbr){
  const tv=teamsActive(), all=tv.teams, T=state.data.teams;
  const t=all.find(x=>x.team===abbr); if(!t) return;
  const m=state.data.meta;
  const g=state.data.predictions.games.find(x=>x.away===abbr||x.home===abbr);
  const headNum=(k)=>{const M=METRICS[k];const rk=scopedRanks(all,k,M.lowGood)[abbr];return '<div class="n"><div class="k">'+esc(M.full)+'</div><div class="v">'+esc(M.f(metricVal(t,k)))+'</div><div class="r">#'+rk+' NFL</div></div>';};
  let html=ovlHead('Team detail \u00b7 '+(tv.baseline?'reference baseline (not current predictions)':'current ratings'),teamName(abbr),'');
  html+='<div class="tprof-head">'+logo(abbr,'lg')+'<div class="tid"><div class="tn">'+esc(teamName(abbr)).toUpperCase()+'</div><div class="ts">'+esc(abbr)+' \u00b7 '+esc(tv.label)+'</div></div></div>';
  html+='<div class="tprof-nums">'+headNum('elo')+headNum('off_epa')+headNum('def_epa')+'</div>';
  html+='<div class="tsec-title">Offense</div><div class="mgrid">'+
    mblock(abbr,'off_epa',t,all)+mblock(abbr,'off_pass_epa',t,all)+mblock(abbr,'off_rush_epa',t,all)+mblock(abbr,'off_sr',t,all)+
    missingBlock('Explosive play rate')+missingBlock('Points / drive')+'</div>';
  html+='<div class="tsec-title">Defense</div><div class="mgrid">'+
    mblock(abbr,'def_epa',t,all)+mblock(abbr,'def_pass_epa',t,all)+mblock(abbr,'def_rush_epa',t,all)+mblock(abbr,'def_sr',t,all)+
    missingBlock('Explosive play rate allowed')+missingBlock('Points / drive allowed')+'</div>';
  html+='<div class="tsec-title">Form / context</div><div class="fctx">'+formRows(abbr,t,T,tv)+'</div>';
  html+='<div class="section-head reset" style="margin-top:24px"><h2 style="font-size:18px">Week '+m.latest_week+' game</h2></div>'+
  (g?'<div class="gcard" data-game="'+esc(g.game)+'" role="button" style="margin:0"><div class="top"><span class="kick">'+esc(g.kickoff)+'</span>'+decisionChip(g)+'</div><div class="sig-match"><div class="sig-team">'+logo(g.away)+'<div><div class="ab">'+esc(g.away)+'</div></div></div><span class="sig-at">VS</span><div class="sig-team">'+logo(g.home)+'<div><div class="ab">'+esc(g.home)+'</div></div></div></div><div class="nums"><div class="cell"><div class="k">Market</div><div class="v">'+esc(homeLine(g))+'</div></div><div class="cell hero"><div class="k">Model</div><div class="v">'+esc(modelLine(g))+'</div></div><div class="cell"><div class="k">Model gap</div><div class="v">'+fmt(gapOf(g),1)+'</div></div></div></div>'
   :'<div class="info-empty">No week '+m.latest_week+' game found for '+esc(abbr)+'.</div>')+
  '<p class="viz-note">Detail uses only exported metrics: elo, off_epa, def_epa, off_sr, def_sr, off_pass_epa, off_rush_epa, def_pass_epa, def_rush_epa.</p>';
  openOverlay(html,'Team: '+abbr);
  ovl.querySelectorAll('[data-game]').forEach(el=>el.onclick=()=>openGame(el.dataset.game));
}

/* ============================================================
   MODEL WIN PROBABILITY — validated calibration layer
   P(home win) = sigma(0.12274 * margin + 0.09099), fit on 2021-22
   walk-forward predictions, validated on locked 2023-25.
   Never presented as a "true" win probability — it is a
   calibration of the model's predicted margin only.
   ============================================================ */
const MODEL_WIN_PROB_NOTE='Model win probability — derived from the model\u2019s predicted margin via historical calibration (fit 2021–22, validated on locked 2023–25).';
const WP_FORMULA={a:0.12274,b:0.09099};
function winProbOf(g){
  if(Number.isFinite(g.model_win_prob)) return Number(g.model_win_prob);
  if(!Number.isFinite(g.model_spread)) return null;
  const x=WP_FORMULA.a*Number(g.model_spread)+WP_FORMULA.b;
  return 1/(1+Math.exp(-x));
}
function favOf(g){
  const p=winProbOf(g); if(p==null) return null;
  return p>=0.5?{team:g.home,prob:p}:{team:g.away,prob:1-p};
}
/* CP4 — calibration figures are read from the exported model_math.win_probability
   block (a/b coefficients + the validated Brier string), never re-typed. */
function calibWinProb(){
  const wp=((state.data.predictions||{}).model_math||{}).win_probability||{};
  return {
    a:Number.isFinite(Number(wp.a))?Number(wp.a):WP_FORMULA.a,
    b:Number.isFinite(Number(wp.b))?Number(wp.b):WP_FORMULA.b,
    validated:String(wp.validated||'')
  };
}
function winProbCalcHTML(g){
  const cw=calibWinProb(), ph=winProbOf(g);
  const a=String(Number.isFinite(cw.a)?cw.a:WP_FORMULA.a);
  const b=String(Number.isFinite(cw.b)?cw.b:WP_FORMULA.b);
  let s='<details class="wp-calc"><summary><span>How is this calculated?</span><span class="ch"></span></summary><div class="calc-body">';
  s+='<p class="step"><b>1. V1 predicts a margin.</b> For this game the V1 model spread is <b>'+esc(modelLine(g))+'</b>. That margin is the prediction \u2014 the probability below is a calibrated transformation of it, a related but distinct output.</p>';
  s+='<p class="step"><b>2. The margin is mapped to a probability.</b> <span class="fn">P(home win) = 1 / (1 + exp(\u2212('+esc(a)+' \u00b7 margin + '+esc(b)+')))</span>. Coefficients come from the calibration artifact on this snapshot\u2019s exact export. This game: P('+esc(g.home)+' win) = <b>'+pct1(ph,1)+'</b>.</p>';
  if(cw.validated) s+='<p class="step"><b>3. The mapping was checked on locked data.</b> <span class="fn">'+esc(cw.validated)+'</span> \u2014 fit on 2021\u201322 walk-forward V1 margins; reliability deciles within 0.09 of observed win rates, monotonic.</p>';
  s+='<p class="step"><b>Display layer only.</b> This probability never alters the V1 spread, pick, or edge. Historical market win probability unavailable because this dataset does not contain moneyline prices.</p>';
  return s+'</div></details>';
}
function winProbCell(g){
  const f=favOf(g); if(!f) return '<span style="color:var(--faint)">\u2014</span>';
  return '<span class="wp-team">'+esc(f.team)+'</span>'+pct1(f.prob,1);
}
/* Games page — on QB-change games the win probability is shown as a range
   "raw% → adj%", where the second number is calibrated from the QB-adjusted
   (experimental overlay) margin. The range keeps the raw favorite's team
   perspective so the two values are directly comparable.
   model_win_prob_adj comes from the exported qb_overlay block. */
const QB_WP_NOTE='2nd number: QB-adjusted (experimental) prediction';
function qbWinProbAdj(g){
  const q=g.qb_overlay;
  if(q&&q.model_win_prob_adj!=null){
    const a=Number(q.model_win_prob_adj);
    if(Number.isFinite(a)) return a;
  }
  return null;
}
function gamesWinProbHTML(g){
  const f=favOf(g); if(!f) return '<span style="color:var(--faint)">\u2014</span>';
  const raw='<span class="wp-team">'+esc(f.team)+'</span>'+pct1(f.prob,1);
  const adj=qbWinProbAdj(g);
  if(adj==null) return raw;
  const adjSameSide=(f.team===g.home)?adj:1-adj;
  return raw+' <span class="wp-arr">\u2192</span> '+pct1(adjSameSide,1);
}
function gamesWinProbNote(g){
  return qbWinProbAdj(g)!=null?'<div class="wp-sub">'+QB_WP_NOTE+'</div>':'';
}

/* ============================================================
   CP3 — MODEL BREAKDOWN (game-page transparency layer)
   Every number comes from the exported snapshot. Component
   margins are the production per-game values (full precision);
   anything not exported is labeled, never estimated.
   ============================================================ */
const WP_LAYER_NOTE='Probability is a calibrated display layer derived from the validated V1 margin model. It does not change the V1 spread, pick, or edge.';
const facts=()=>state.facts||{identity:{},architecture:{components:[]},training_periods:{},features:{epa_differentials:[],gbm_extra:[]},elo_methodology:{},epa_methodology:{},validation:{}};
function blendWeights(){
  const w=((state.data.predictions||{}).provenance||{}).weights;
  return (w&&Number.isFinite(w.elo)&&Number.isFinite(w.epa)&&Number.isFinite(w.gbm))?w:{elo:0.4,epa:0.5,gbm:0.1};
}
function weightPct(w){ return Math.round(w*100)+'%'; }
/* A per-component margin (home-margin convention) as a favored-team line: "BUF −2.1". */
function marginLine(g,v){
  if(!Number.isFinite(v)) return '—';
  if(v>0.049) return g.home+' −'+fmt(v,1);
  if(v<-0.049) return g.away+' −'+fmt(Math.abs(v),1);
  return 'Pick\u2019em';
}
const marginTeam=(g,v)=>(Number.isFinite(v)&&v>0)?g.home:(Number.isFinite(v)&&v<0)?g.away:null;
const favorTxt=(g,v)=>{const t=marginTeam(g,v);return t?'favors '+t:'dead even';};
/* League ranks + averages for every shipped EPA/success-rate metric. */
function metricMeta(){
  if(metricMeta._c) return metricMeta._c;
  const ts=state.data.teams.teams;
  const mk=(key,higher)=>{const s=[...ts].sort((a,b)=>(Number(a[key])-Number(b[key]))*(higher?-1:1));const r={};s.forEach((t,i)=>r[t.team]=i+1);const vals=ts.map(t=>Number(t[key]));return {rank:r,avg:vals.reduce((x,y)=>x+y,0)/vals.length,lo:Math.min(...vals),hi:Math.max(...vals)};};
  metricMeta._c={off_epa:mk('off_epa',true),off_pass_epa:mk('off_pass_epa',true),off_rush_epa:mk('off_rush_epa',true),off_sr:mk('off_sr',true),
    def_epa:mk('def_epa',false),def_pass_epa:mk('def_pass_epa',false),def_rush_epa:mk('def_rush_epa',false),def_sr:mk('def_sr',false)};
  return metricMeta._c;
}
const isDefKey=k=>String(k).slice(0,4)==='def_';
const strengthPct=(v,inv,lo,hi)=>{const s=inv?(hi-v):(v-lo);return Math.max(4,Math.min(100,(s/((hi-lo)||1))*100));};
/* One value-vs-value duel row: team abbr, value, league rank, league-scaled bar. */
function udRow(label,aT,aV,aK,hT,hV,hK,mm){
  const A=mm[aK],H=mm[hK];
  const cell=(t,v,M,k,hm)=>'<span class="u'+(hm?' hm':'')+'"><b>'+esc(t)+'</b>&nbsp; <span class="vv">'+signed(v,3)+'</span><span class="rk">#'+(M.rank[t]||'—')+' NFL</span><div class="br"><i style="width:'+strengthPct(v,isDefKey(k),M.lo,M.hi).toFixed(1)+'%"></i></div><div class="av">'+(isDefKey(k)?'allowed · ':'')+'NFL avg '+signed(M.avg,3)+'</div></span>';
  return '<div class="urow"><span class="ul">'+esc(label)+'</span>'+cell(aT,aV,A,aK,false)+cell(hT,hV,H,hK,true)+'</div>';
}
const subD=(t,body)=>'<details class="subd"><summary><span>'+t+'</span><span class="ch"></span></summary><div class="sub-body">'+body+'</div></details>';
const cmpWrap=(title,wt,line,desc,body)=>'<details class="cmp"><summary><div class="cmp-l"><div><span class="n">'+title+'</span><span class="w">'+wt+'</span></div><div class="d">'+desc+'</div></div><div class="cmp-r"><div class="ml">'+line+'<small>Component margin</small></div></div><span class="chev" aria-hidden="true"></span></summary><div class="cmp-body">'+body+'</div></details>';

/* ---------- ELO detail ---------- */
function eloDetail(g,a,h,rk){
  const F=facts().elo_methodology||{}, w=blendWeights(), comp=g.components||{};
  const diff=Number.isFinite(g.elo_diff)?g.elo_diff:(h.elo-a.elo);
  const hfa=Number.isFinite(F.home_field_advantage_elo)?F.home_field_advantage_elo:55;
  let s='<h3>What is ELO?</h3>'+
    '<p class="what"><b>ELO is a team-strength rating that updates after games.</b> Beating a stronger opponent moves a team&rsquo;s rating more than beating a weaker opponent.</p>'+
    '<h3>The actual values</h3><div class="vgrid">'+
    '<div class="vcard"><div class="k">'+esc(g.away)+' ELO</div><div class="v">'+fmt(a.elo,1)+'</div><div class="s">league rank #'+(rk.elo[g.away]||'—')+' of 32</div></div>'+
    '<div class="vcard"><div class="k">'+esc(g.home)+' ELO</div><div class="v">'+fmt(h.elo,1)+'</div><div class="s">league rank #'+(rk.elo[g.home]||'—')+' of 32</div></div>'+
    '<div class="vcard"><div class="k">Rating difference (home − away)</div><div class="v">'+signed(diff,2)+'</div><div class="s">'+esc(g.home)+' '+fmt(h.elo,1)+' − '+esc(g.away)+' '+fmt(a.elo,1)+' — '+esc(favorTxt(g,diff))+'</div></div>'+
    '<div class="vcard"><div class="k">Home-field adjustment</div><div class="v">+'+fmt(hfa,0)+' ELO</div><div class="s">applied to the home team in ELO expectation and update mechanics</div></div></div>'+
    '<h3>See the calculation</h3>'+
    '<div class="bk-calc" style="margin-top:0">'+esc(g.home)+' '+fmt(h.elo,1)+' − '+esc(g.away)+' '+fmt(a.elo,1)+' = '+signed(diff,2)+' rating points<br>→ ELO component margin: <b>'+esc(marginLine(g,comp.elo_margin))+'</b> ('+esc(weightPct(w.elo))+' of the V1 blend)</div>'+
    '<h3>How it is calculated</h3>'+
    '<div class="flow"><div class="step">Previous ELO rating</div><div class="arr">→</div><div class="step">Game result</div><div class="arr">→</div><div class="step">Opponent strength</div><div class="arr">→</div><div class="step">Margin-of-victory adjustment</div><div class="arr">→</div><div class="step">Updated ELO</div></div>'+
    subD('Advanced: ELO parameters &amp; update methodology',
      '<b>K factor:</b> <span class="fn">'+fmt(F.K,1)+'</span><br>'+
      '<b>Home-field adjustment:</b> <span class="fn">+'+fmt(hfa,0)+'</span> ELO, added to the home team&rsquo;s rating when computing win expectancy and updates.<br>'+
      '<b>Margin-of-victory methodology:</b> '+esc(F.update||'win/loss outcome scaled by a margin-of-victory multiplier')+'<br>'+
      '<b>Offseason regression:</b> '+esc(F.offseason_regression||'1/3 toward 1500 at each week 1')+'<br>'+
      '<b>Current-season update state:</b> '+esc(F.update||'')+'. Ratings are recomputed from scratch on every scored game before this week — there is no cached/stale ratings file.<br>'+
      '<b>From rating to margin:</b> a linear regression maps the ELO differential onto a game margin. The regression&rsquo;s coefficients are not part of this export — the component margin shown above is the verified production value, used as-is. Source: scripts/03_ratings.py (via model_facts.json).')+
    '<p class="viz-note">Ratings shown are the exact snapshot V1 used for this week&rsquo;s predictions. The ELO component margin is the production value — it is displayed, never re-derived in the browser.</p>';
  return cmpWrap('Team strength',weightPct(w.elo)+' of the blend',esc(marginLine(g,comp.elo_margin)),'Team-strength ratings from game history',s);
}

/* ---------- EPA detail ---------- */
function epaTeamCols(g,a,h,which){
  const mm=metricMeta();
  const offItems=[['EPA / play','off_epa'],['Pass EPA / play','off_pass_epa'],['Rush EPA / play','off_rush_epa'],['Success rate','off_sr']];
  const defItems=[['EPA allowed / play','def_epa'],['Pass EPA allowed / play','def_pass_epa'],['Rush EPA allowed / play','def_rush_epa'],['Success rate allowed','def_sr']];
  const items=which==='def'?defItems:offItems;
  return items.map(it=>udRow(it[0],g.away,a[it[1]],it[1],g.home,h[it[1]],it[1],mm)).join('');
}
function epaMatchups(g,a,h){
  const mm=metricMeta();
  const pairs=[['EPA / play','off','def'],['Pass EPA / play','off_pass_epa','def_pass_epa'],['Rush EPA / play','off_rush_epa','def_rush_epa'],['Success rate','off_sr','def_sr']];
  const fix=k=>k==='off'?'off_epa':k==='def'?'def_epa':k;
  let s='<div class="u-block"><h4>'+esc(g.away)+' offense vs '+esc(g.home)+' defense</h4>'+
    pairs.map(p=>udRow(p[0],g.away,a[fix(p[1])],fix(p[1]),g.home,h[fix(p[2])],fix(p[2]),mm)).join('')+'</div>';
  s+='<div class="u-block"><h4>'+esc(g.home)+' offense vs '+esc(g.away)+' defense</h4>'+
    pairs.map(p=>udRow(p[0],g.away,a[fix(p[2])],fix(p[2]),g.home,h[fix(p[1])],fix(p[1]),mm)).join('')+'</div>';
  return s;
}
function epaAdvTable(g,a,h){
  const rows=[
    ['off_epa_diff','Offensive EPA/play, home minus away',a.off_epa,h.off_epa],
    ['def_epa_diff','Defensive EPA/play allowed, home minus away',a.def_epa,h.def_epa],
    ['off_pass_diff','Pass EPA/play differential',a.off_pass_epa,h.off_pass_epa],
    ['off_rush_diff','Rush EPA/play differential',a.off_rush_epa,h.off_rush_epa],
    ['def_pass_diff','Pass EPA allowed differential',a.def_pass_epa,h.def_pass_epa],
    ['def_rush_diff','Rush EPA allowed differential',a.def_rush_epa,h.def_rush_epa],
    ['sr_off_diff','Offensive success-rate differential',a.off_sr,h.off_sr],
    ['sr_def_diff','Defensive success-rate differential (allowed)',a.def_sr,h.def_sr]
  ];
  let s='<table class="feat-t"><thead><tr><th>Feature</th><th>'+esc(g.away)+'</th><th>'+esc(g.home)+'</th><th>Differential</th></tr></thead><tbody>'+
    rows.map(r=>'<tr><td class="fn">'+r[0]+'</td><td class="nu">'+signed(r[2],3)+'</td><td class="nu">'+signed(r[3],3)+'</td><td class="nu">'+signed(r[3]-r[2],3)+'</td></tr>').join('')+'</tbody></table>'+
    '<p class="viz-note">Feature definitions from the production model: '+rows.map(r=>'<span class="fn" style="font-family:var(--mono);font-size:11.5px">'+r[0]+'</span>').join(' · ')+'. All differentials are home minus away. Regression coefficients and intercepts are not part of this export, so per-feature weighted contributions cannot be reconstructed here — only the exported component margin itself.</p>';
  return s;
}
function epaDetail(g,a,h){
  const F=facts(), w=blendWeights(), comp=g.components||{};
  let s='<h3>What is EPA?</h3>'+
    '<p class="what"><b>Expected Points Added measures how much a play changes a team&rsquo;s expected scoring value.</b> Positive EPA generally means the play improved the team&rsquo;s scoring position/value; negative EPA means it reduced it.</p>'+
    '<h3>Offense — actual values</h3>'+epaTeamCols(g,a,h,'off')+
    '<h3>Defense — actual values</h3>'+epaTeamCols(g,a,h,'def')+
    '<p class="viz-note">Explosive play rate and points/drive are not carried in this export — they are omitted here rather than estimated.</p>'+
    '<h3>Matchup</h3>'+epaMatchups(g,a,h)+
    '<h3>EPA-linear component</h3><div class="vgrid"><div class="vcard"><div class="k">EPA-linear component margin</div><div class="v">'+esc(marginLine(g,comp.epa_margin))+'</div><div class="s">carries '+esc(weightPct(w.epa))+' of the V1 blend</div></div></div>'+
    '<p class="what">The linear EPA model <b>converts the EPA-derived matchup differentials into a predicted margin</b> — efficiency, pass/rush splits and success rates on both sides of the ball, weighted by the fitted regression.</p>'+
    subD('Advanced: exact features, team values, differentials',epaAdvTable(g,a,h)+
      '<b>EPA pipeline:</b> nflverse play-by-play, EWMA α=0.25 on each week&rsquo;s per-team means, 35% offseason regression toward league average (0.0). Source: scripts/07_update_weekly.py (via model_facts.json).')+
    '<p class="viz-note">Bars are league-scaled across all 32 teams; longer is stronger. Ranks reflect this snapshot&rsquo;s ratings, not the preseason baseline.</p>';
  return cmpWrap('Play-by-play performance',weightPct(w.epa)+' of the blend',esc(marginLine(g,comp.epa_margin)),'The football-stats layer — matchup efficiency',s);
}

/* ---------- GBM detail ---------- */
function gbmDetail(g,a,h){
  const prov=state.data.predictions.provenance||{}, w=blendWeights(), comp=g.components||{};
  const diffs=[
    ['elo_diff','ELO differential (home − away)',a.elo,h.elo,true],
    ['off_epa_diff','Offensive EPA/play differential',a.off_epa,h.off_epa,true],
    ['def_epa_diff','Defensive EPA/play-allowed differential',a.def_epa,h.def_epa,true],
    ['off_pass_diff','Pass EPA/play differential',a.off_pass_epa,h.off_pass_epa,true],
    ['off_rush_diff','Rush EPA/play differential',a.off_rush_epa,h.off_rush_epa,true],
    ['def_pass_diff','Pass EPA-allowed differential',a.def_pass_epa,h.def_pass_epa,true],
    ['def_rush_diff','Rush EPA-allowed differential',a.def_rush_epa,h.def_rush_epa,true],
    ['sr_off_diff','Offensive success-rate differential',a.off_sr,h.off_sr,true],
    ['sr_def_diff','Defensive success-rate differential',a.def_sr,h.def_sr,true],
    ['rest_diff','Rest-day differential',null,null,false],
    ['div_game','Division-game flag',null,null,false],
    ['week','Week number',null,null,false]
  ];
  const m=state.data.meta;
  let trows=diffs.map(r=>{
    if(r[1]==='Week number') return '<tr><td class="fn">'+r[0]+'</td><td colspan="3" class="why"><b style="color:var(--text)">Week '+m.latest_week+'</b> — a season-context feature, not a differential</td></tr>';
    if(!r[4]) return '<tr><td class="fn">'+r[0]+'</td><td colspan="3"><span class="unav">Not carried in this export</span></td></tr>';
    return '<tr><td class="fn">'+r[0]+'</td><td class="nu">'+signed(r[2],r[0]==='elo_diff'?1:3)+'</td><td class="nu">'+signed(r[3],r[0]==='elo_diff'?1:3)+'</td><td class="nu">'+signed(r[3]-r[2],r[0]==='elo_diff'?1:3)+'</td></tr>';
  }).join('');
  let s='<h3>How to read this layer</h3>'+
    '<p class="what"><b>The Gradient Boosting Model combines multiple football features and learns nonlinear relationships between team/matchup statistics and game margin.</b> This is not a hand calculation — the GBM&rsquo;s output only exists as the prediction of a trained model, and it gets a deliberately small voice in the blend ('+esc(weightPct(w.gbm))+').</p>'+
    '<div class="vgrid"><div class="vcard"><div class="k">GBM component margin</div><div class="v">'+esc(marginLine(g,comp.gbm_margin))+'</div><div class="s">the verified production value, used as-is</div></div></div>'+
    '<h3>Top model contributions</h3><p class="what"><b>Per-game GBM feature contributions are not currently exported.</b> Showing a fake attribution here would be fabricated — so the layer stays at the component-margin level.</p>'+
    '<h3>GBM inputs</h3>'+
    '<p class="what">The actual feature names the production GBM reads. Differential features are <b>home minus away</b>.</p>'+
    '<table class="feat-t"><thead><tr><th>Feature</th><th>'+esc(g.away)+'</th><th>'+esc(g.home)+'</th><th>Difference</th></tr></thead><tbody>'+trows+'</tbody></table>'+
    '<p class="viz-note">Engine: '+esc(prov.gbm_backend||'sklearn-hgbr')+', retrained weekly on the expanding window of '+fmtInt(prov.gbm_n_train)+' scored games (through '+esc(prov.gbm_train_through||'')+'). No SHAP or feature-importance values are shipped in this export — no feature is claimed as the cause of the prediction.</p>';
  return cmpWrap('Matchup patterns',weightPct(w.gbm)+' of the blend',esc(marginLine(g,comp.gbm_margin)),'Gradient boosting — nonlinear matchup patterns',s);
}

/* ---------- Final-model composition ---------- */
function compositionHTML(g){
  const w=blendWeights(), comp=g.components||{};
  const em=Number(comp.elo_margin), pm=Number(comp.epa_margin), gm=Number(comp.gbm_margin);
  const blend=w.elo*em+w.epa*pm+w.gbm*gm;
  const f=favOf(g);
  return '<div class="comp"><div class="cap">Weighted blend — full exported precision</div>'+
    '<div class="arith">ELO '+signed(em,2)+'<span class="op"> × </span>'+fmt(w.elo,2)+'<span class="op"> + </span>EPA '+signed(pm,2)+'<span class="op"> × </span>'+fmt(w.epa,2)+'<span class="op"> + </span>GBM '+signed(gm,2)+'<span class="op"> × </span>'+fmt(w.gbm,2)+'<span class="op"> = </span>'+signed(blend,3)+'</div>'+
    '<div class="res"><span class="rl">V1 model</span><span class="rv">'+esc(modelLine(g))+'</span></div>'+
    '<p class="viz-note" style="text-align:center">The blend is '+signed(blend,3)+' before rounding ('+signed(blend,1)+' → '+esc(modelLine(g))+'). Intermediate values are not re-rounded.</p>'+
    '<div class="wp"><div class="k">Model win probability</div><div class="v">'+(f?esc(f.team)+' '+pct1(f.prob,1):'—')+'</div>'+
    (f?'<div class="o">'+esc(f.team===g.home?g.away:g.home)+' '+pct1(1-f.prob,1)+'</div>':'')+
    '<p class="n">'+esc(WP_LAYER_NOTE)+'</p><p class="n">The spread above is the prediction — the probability is a calibrated transformation of it.</p></div></div>';
}

/* ---------- "Why the model leans" — generated ONLY from verified model data ---------- */
function whyLeanHTML(g){
  const m=state.data.meta, w=blendWeights(), comp=g.components||{}, rk=rankMaps();
  const a=teamBy(g.away), h=teamBy(g.home), mm=metricMeta(), f=favOf(g);
  if(!f) return '';
  if(!Number.isFinite(comp.elo_margin)||!Number.isFinite(comp.epa_margin)||!Number.isFinite(comp.gbm_margin))
    return '<div class="why-lean"><p>Component margins are not exported for this game in this snapshot, so the why-layer stays quiet rather than guessing.</p></div>';
  const opp=f.team===g.home?g.away:g.home;
  const comps=[['ELO',w.elo,comp.elo_margin],['EPA-linear',w.epa,comp.epa_margin],['GBM',w.gbm,comp.gbm_margin]];
  const agree=comps.filter(c=>marginTeam(g,c[2])===f.team).length;
  let s='<div class="why-lean">';
  if(agree===3) s+='<p>Every component of the model points the same way — <b>'+esc(f.team)+'</b>: <b>'+esc(marginLine(g,comp.elo_margin))+'</b> from the ELO layer ('+esc(weightPct(w.elo))+' of the blend), <b>'+esc(marginLine(g,comp.epa_margin))+'</b> from the EPA-linear layer ('+esc(weightPct(w.epa))+'), and <b>'+esc(marginLine(g,comp.gbm_margin))+'</b> from the GBM layer ('+esc(weightPct(w.gbm))+').</p>';
  else if(agree===0) s+='<p>No component favors the model&rsquo;s winning team outright — the blend lands on <b>'+esc(modelLine(g))+'</b> from mixed signals: '+comps.map(c=>esc(c[0])+' '+esc(marginLine(g,c[2]))).join(', ')+'.</p>';
  else s+='<p>The components disagree: '+comps.map(c=>esc(c[0])+' <b>'+esc(marginLine(g,c[2]))+'</b>').join(', ')+'. The '+(fmt(w.elo,0))+'/'+(fmt(w.epa,0))+'/'+(fmt(w.gbm,0))+' blend lands on <b>'+esc(modelLine(g))+'</b>.</p>';
  const fe=f.team===g.home?h:a, oe=f.team===g.home?a:h, dElo=fe.elo-oe.elo;
  s+='<p>On ratings, '+esc(f.team)+' sits at <b>'+fmt(fe.elo,0)+' ELO</b> (rank #'+rk.elo[f.team]+' of 32), <b>'+fmt(Math.abs(dElo),0)+'</b> points '+(dElo>=0?'ahead of':'behind')+' '+esc(opp)+' (rank #'+rk.elo[opp]+').</p>';
  const frow=f.team===g.home?h:a;
  const cand=[['off_epa','EPA/play on offense'],['off_pass_epa','pass EPA/play on offense'],['off_rush_epa','rush EPA/play on offense'],['off_sr','offensive success rate'],
    ['def_epa','EPA/play allowed on defense'],['def_pass_epa','pass EPA/play allowed'],['def_rush_epa','rush EPA/play allowed'],['def_sr','success rate allowed on defense']];
  const best=cand.map(c=>({k:c[0],n:c[1],r:mm[c[0]].rank[f.team],v:frow[c[0]]})).sort((x,y)=>x.r-y.r)[0];
  if(best&&best.r<=10) s+='<p>The strongest supporting stat for '+esc(f.team)+' is <b>'+esc(best.n)+' ranked #'+best.r+' in the NFL</b> ('+signed(best.v,3)+').</p>';
  s+='<p class="sml">Blended at '+esc(weightPct(w.elo))+'/'+esc(weightPct(w.epa))+'/'+esc(weightPct(w.gbm))+', these give the V1 model <b>'+esc(modelLine(g))+'</b>, with a calibrated model win probability of '+esc(f.team)+' '+pct1(f.prob,1)+'. The gap to the market ('+esc(homeLine(g))+') is '+signed(g.edge,1)+' points — disagreement is a comparison, not evidence of a betting edge.</p></div>';
  return s;
}

/* ---------- Underlying team data ---------- */
function underlyingHTML(g){
  const a=teamBy(g.away), h=teamBy(g.home), mm=metricMeta(), mData=state.data.meta;
  const pb=(state.data.teams.preseason_baseline||{}).teams||[];
  const pbT={}; pb.forEach(t=>pbT[t.team]=t);
  const offItems=[['EPA / play','off_epa'],['Pass EPA / play','off_pass_epa'],['Rush EPA / play','off_rush_epa'],['Success rate','off_sr']];
  const defItems=[['EPA allowed / play','def_epa'],['Pass EPA allowed / play','def_pass_epa'],['Rush EPA allowed / play','def_rush_epa'],['Success rate allowed','def_sr']];
  let s='<div class="uwrap"><div class="u-block"><h4>Offense</h4>'+
    offItems.map(it=>udRow(it[0],g.away,a[it[1]],it[1],g.home,h[it[1]],it[1],mm)).join('')+'</div>'+
    '<div class="u-block"><h4>Defense</h4>'+
    defItems.map(it=>udRow(it[0],g.away,a[it[1]],it[1],g.home,h[it[1]],it[1],mm)).join('')+'</div></div>'+
    '<p class="viz-note">Explosive play rate and points/drive are not carried in this export.</p>';
  s+='<div class="u-block"><h4>Current season vs preseason baseline</h4>'+
    [g.away,g.home].map(t=>{
      const cur=t===g.home?h:a, base=pbT[t];
      const dElo=base?cur.elo-base.elo:NaN;
      return '<div class="urow"><span class="ul">'+esc(t)+' ELO</span><span class="u"><span class="vv">'+fmt(cur.elo,0)+'</span><span class="rk">now</span></span><span class="u'+(t===g.home?' hm':'')+'"><span class="vv">'+(base?fmt(base.elo,0):'—')+'</span><span class="rk">baseline</span><div class="av">'+(Number.isFinite(dElo)?('Δ '+signed(dElo,0)): '')+'</div></span></div>';
    }).join('')+'</div>';
  s+='<p class="viz-note">Ratings fold in every scored game through Week '+(mData.latest_week-1)+'; Week '+mData.latest_week+' is not yet played. Recent-game form is not tracked separately in this export — current ratings already incorporate recent weeks via the EWMA/ELO updates.</p>';
  return s;
}

/* ---------- Advanced model details / Data & methodology ---------- */
function advDetailsHTML(g){
  const F=facts(), prov=state.data.predictions.provenance||{}, cw=calibWinProb();
  const tp=F.training_periods||{}, comp=(F.architecture&&F.architecture.components)||[];
  return '<div class="sub-body">'+
    '<b>Ensemble.</b> <span class="fn">'+fmtBlendMath()+'</span> — '+comp.map(c=>esc(c.name)+' ('+Math.round(Number(c.weight)*100)+'%)').join(' · ')+'. Weights tuned by MAE on the 2021–2022 validation window and frozen since.<br>'+
    '<b>Pick rule.</b> <span class="fn">|model spread − market spread| ≥ 3.0</span> marks a paper play; QB availability voids can only remove plays, never create or flip them.<br>'+
    '<b>Training.</b> Linear components fit '+esc(tp.linear_components||'2018–2020')+'; ensemble weights and threshold tuned on '+esc(tp.ensemble_weights_and_threshold||'2021–2022 validation')+'; GBM ('+esc(prov.gbm_backend||'sklearn-hgbr')+') retrained weekly on the expanding window of '+fmtInt(prov.gbm_n_train)+' scored games (through '+esc(prov.gbm_train_through||'')+').<br>'+
    '<b>Calibration.</b> Model win probability is the display layer <span class="fn">P(home win) = 1 / (1 + exp(−('+esc(String(cw.a))+' · margin + '+esc(String(cw.b))+')))</span> — fit on 2021–22 walk-forward margins (n=566), then validated on the locked 2023–25 set (n=854): <span class="fn">'+esc(cw.validated||'')+'</span>, reliability deciles within 0.09 of observed and monotonic. It is not an independent probability model and cannot change any V1 spread, pick, or edge.<br>'+
    '<b>Locked test.</b> '+esc(tp.locked_test||'2023–2025 — never used for any selection decision')+'. Honest verdict: '+esc((F.validation||{}).honest_verdict||'')+
    '</div>';
}
function fmtBlendMath(){const w=blendWeights();return fmt(w.elo,1)+'·ELO + '+fmt(w.epa,1)+'·EPA + '+fmt(w.gbm,1)+'·GBM';}
function dataMethodHTML(g){
  const prov=state.data.predictions.provenance||{};
  const T=state.data.teams, m=state.data.meta;
  const sg=((prov.season_games_included||{})['2026'])||{};
  const row=(k,v)=>'<tr><td class="k">'+k+'</td><td class="vv">'+v+'</td></tr>';
  return '<div class="sub-body">'+
    '<table class="prov-table"><tbody>'+
    row('Snapshot generated',esc(prov.generated_at||''))+
    row('Data as of',esc(prov.data_as_of||''))+
    row('Ratings used',esc(prov.ratings_as_of||''))+
    row('Games included',esc(String(sg.n_games||''))+' (2026 weeks '+esc((sg.weeks||[]).join(', '))+') — ratings window: '+esc(prov.ratings_window||''))+
    row('Latest game included',esc(prov.latest_game_included||''))+
    row('ELO source',esc(prov.elo_source||''))+
    row('EPA source',esc(prov.epa_source||''))+
    row('Market lines',esc(m.lines_note||''))+
    row('GBM fit',esc(prov.gbm_backend||'')+' on '+fmtInt(prov.gbm_n_train)+' games')+
    '</tbody></table>'+
    '<b>Methodology in brief.</b> ELO: K=20, HFA +55, weekly batching, offseason ⅓ regression to 1500, margin-of-victory multiplier. EPA: EWMA α=0.25 weekly updates, 35% offseason regression to 0.0. nflverse play-by-play underlies both; the threshold and blend are frozen researchers&rsquo; choices, never retuned on test outcomes.'+
    '</div>';
}

/* ---------- Game page hero ---------- */
function gameHeroHTML(g){
  const m=state.data.meta, d=decisionOf(g), f=favOf(g);
  let s='<div class="gh-head">';
  s+='<div class="gh-chips">'+decisionChip(g)+
    ((d==='pick')?'<span class="gh-final" style="margin:0;display:inline">Final pick: <b style="color:var(--text)">'+esc(g.spread_pick_final)+'</b></span>':'')+
    ((g.qb_news&&d!=='void')?'<span class="qb-chip">'+esc(g.qb_news)+'</span>':'')+'</div>';
  s+='<div class="gh-match"><div class="gh-team">'+logo(g.away,'lg')+'<div><div class="ab">'+esc(TEAM_SHORT[g.away]||g.away)+'</div><div class="nm">'+esc(kickDay(g.kickoff))+'</div></div></div>'+
    '<span class="gh-at">VS</span>'+
    '<div class="gh-team">'+logo(g.home,'lg')+'<div><div class="ab">'+esc(TEAM_SHORT[g.home]||g.home)+'</div><div class="nm">home</div></div></div></div>';
  if(f){
    const ph=Number(winProbOf(g)), pa=1-ph;
    s+='<div class="gh-prob"><div class="k">Model Win Probability</div><div class="v"><span class="tm">'+esc(f.team)+'</span> '+pct1(f.prob,1)+'</div>'+
      '<div class="pr-bar"><i style="width:'+(pa*100).toFixed(1)+'%;background:#4a5d8a" title="'+esc(g.away)+' '+pct1(pa,1)+'"></i><i style="width:'+(ph*100).toFixed(1)+'%;background:var(--good)" title="'+esc(g.home)+' '+pct1(ph,1)+'"></i></div>'+
      '<div class="pr-ends"><span class="away">'+esc(g.away)+' '+pct1(pa,1)+'</span><span>'+esc(g.home)+' '+pct1(ph,1)+'</span></div>'+
      '<p class="wp-label"><b>Calibrated probability derived from the validated V1 margin model. Not a market-implied probability.</b></p>'+
      '<p class="note">The V1 spread is the prediction \u2014 the probability is a calibrated transformation of that margin. It never alters the V1 spread, pick, or edge.</p>'+
      '<p class="note">Historical market win probability unavailable because this dataset does not contain moneyline prices.</p>'+
      winProbCalcHTML(g)+'</div>';
  }
  s+='<div class="gh-nums"><div class="gh-num model"><div class="k">Model</div><div class="v">'+esc(modelLine(g))+'</div></div>'+
    '<div class="gh-num"><div class="k">Market</div><div class="v">'+esc(homeLine(g))+'</div></div>'+
    '<div class="gh-num gap"><div class="k">Model gap</div><div class="v">'+signed(g.edge,1)+'</div></div></div>';
  if(d==='void') s+='<p class="viz-note" style="text-align:center">Raw signal '+esc(g.spread_pick)+' was voided on QB availability — a voided signal is never a play.</p>';
  else s+='<p class="viz-note" style="text-align:center">A paper pick requires at least a '+fmt(m.threshold,1)+'-point difference. The team shown with a minus sign is favored.</p>';
  return s+'</div>';
}

/* ============================================================
   HOME — MODEL OUTLOOK + EXPLORE THE MODEL
   ============================================================ */
function exploreHTML(){
  const items=[
    ['01','Games','Every matchup, model spread, win probability, market comparison, and explanation.'],
    ['02','Teams','Current team strength and the underlying football numbers.'],
    ['03','Props','Player projections and uncertainty.'],
    ['04','Model','How the prediction engine actually works.']
  ];
  return items.map(x=>'<button class="explore-card" data-goto="'+x[1]+'" aria-label="Explore '+x[1]+'">'+
    '<span class="ex-num">'+x[0]+'</span><span class="ex-t">'+x[1]+'</span><span class="ex-d">'+esc(x[2])+'</span><span class="ex-go">Open '+x[1].toLowerCase()+' →</span></button>').join('');
}
function outlookSection(){
  const rows=[...state.data.predictions.games].map(g=>({g:g,f:favOf(g)})).filter(x=>x.f).sort((a,b)=>b.f.prob-a.f.prob).slice(0,4);
  if(!rows.length) return '';
  return sectHead('04','Model outlook','<span class="tail" data-goto="Games">All '+state.data.predictions.games.length+' games →</span>')+
  '<div class="outlook-grid">'+rows.map(x=>{
    const g=x.g, f=x.f, opp=f.team===g.home?g.away:g.home, where=f.team===g.home?'vs':'at';
    return '<div class="out-card" data-game="'+esc(g.game)+'" role="button" tabindex="0" aria-label="Model outlook: '+esc(g.game)+', '+esc(f.team)+' '+pct1(f.prob,1)+' win probability">'+
      '<div class="oc-top">'+logo(f.team,'sm')+'<div class="oc-fv">'+pct1(f.prob,1)+'<small> '+esc(f.team)+'</small></div></div>'+
      '<div class="oc-sub">'+where+' '+esc(teamName(opp))+'</div>'+
      '<div class="oc-m">Model '+esc(modelLine(g))+' · gap '+fmt(gapOf(g),1)+'</div></div>';
  }).join('')+'</div>'+
  '<p class="viz-note">These are the teams the model gives the best chance to win this week. The percentages come from the projected margins, not from sportsbook prices; technical calibration details are available on the Model page.</p>';
}

/* ============================================================
   TEAMS — MODEL WIN PROBABILITY BOARD
   ============================================================ */
function winProbBoard(){
  const m=state.data.meta, gs=state.data.predictions.games;
  const rows=state.data.teams.teams.map(t=>{
    const g=gs.find(x=>x.home===t.team||x.away===t.team);
    const p=g?winProbOf(g):null;
    const prob=(p==null||!g)?null:(g.home===t.team?p:1-p);
    return {t:t,g:g,prob:prob};
  }).sort((a,b)=>((b.prob??-1)-(a.prob??-1)));
  let s=pageHead('Teams','Model win probability — Week 4','Every team\u2019s model win probability for week '+m.latest_week+', ranked. A calibrated display layer derived from the V1 predicted margin — there is no market-implied probability in this dataset (no historical moneyline prices).');
  s+='<div class="rtoggle">'+seg('teamView','current','Current ratings — through Week 3')+seg('teamView','baseline','Preseason baseline · reference')+seg('teamView','winprob','Model win prob · Week 4')+'</div>';
  s+='<p class="viz-note">'+esc(MODEL_WIN_PROB_NOTE)+'</p>';
  s+='<div class="wprob-rows">'+rows.map((r,i)=>{
    const t=r.t, g=r.g, opp=g?(t.team===g.home?g.away:g.home):null, where=g?(t.team===g.home?'vs':'at'):'';
    return '<div class="wprob-row" data-team="'+esc(t.team)+'" role="button" tabindex="0"><span class="rk">'+(i+1)+'</span>'+
      '<span class="tm">'+logo(t.team,'sm')+'<span>'+esc(t.team)+'</span>'+(opp?'<span class="opp">'+where+' '+esc(opp)+'</span>':'')+'</span>'+
      '<span class="bar" aria-hidden="true"><i style="width:'+(r.prob==null?0:(r.prob*100).toFixed(1))+'%"></i></span>'+
      '<span class="pv">'+(r.prob==null?'—':pct1(r.prob,1))+'</span></div>';
  }).join('')+'</div>';
  s+='<p class="viz-note">Win probability never changes the V1 spread, pick, or edge — it is a calibrated restatement of the model margin.</p>';
  return s;
}

/* ============================================================
   PERFORMANCE
   ============================================================ */
function cumSVG(rows){
  const pts=rows.map((r,i)=>({i:i,d:r.w-r.l}));
  const W=920,H=240,pad=34;
  const lo=Math.min(0,...pts.map(p=>p.d))-2, hi=Math.max(0,...pts.map(p=>p.d))+2;
  const X=i=>pad+i/pts.length*(W-2*pad), Y=d=>H-pad-(d-lo)/(hi-lo)*(H-2*pad);
  const line=pts.map((p,i)=>(i?'L':'M')+X(p.i).toFixed(1)+' '+Y(p.d).toFixed(1)).join(' ');
  const marks=[2023,2024,2025].map(s=>{const idx=pts.findIndex((p,i)=>rows[i].season===s);return idx<0?'':'<text x="'+X(idx)+'" y="'+(H-8)+'" fill="var(--faint)" font-size="10" font-family="var(--mono)">'+s+'</text>';}).join('');
  /* Final-point label: render only when the value is a real number (never NaN). Note: keep the (W-pad) parentheses — bare W-pad in this concatenation would make the whole string NaN. */
  const endD=pts.length?pts[pts.length-1].d:NaN;
  const endLbl=Number.isFinite(endD)?'<text x="'+(W-pad)+'" y="'+(Y(endD)-10)+'" fill="var(--text)" font-size="11" font-family="var(--mono)" text-anchor="end">'+(endD>0?'+':'')+endD+' cumulative W−L</text>':'';
  return '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Cumulative record chart">'+
    '<line x1="'+pad+'" y1="'+Y(0)+'" x2="'+(W-pad)+'" y2="'+Y(0)+'" stroke="var(--border)" stroke-width="1" stroke-dasharray="4 4"/>'+
    '<path d="'+line+'" fill="none" stroke="var(--model)" stroke-width="2"/>'+
    '<circle cx="'+X(pts.length-1)+'" cy="'+Y(pts[pts.length-1].d)+'" r="4" fill="var(--model)"/>'+endLbl+
    '<text x="'+pad+'" y="14" fill="var(--faint)" font-size="10" font-family="var(--mono)">Cumulative record, threshold |edge| ≥ 3.0 · 2023–2025 locked test</text>'+marks+'</svg>';
}
function renderPerformance(){
  const bt=state.data.backtest, rec=state.data.record, c=weekCounts();
  const t3=bt.by_threshold['3.0'], t3t=t3.test_2023_25;
  const thRows=['1.5','2.0','2.5','3.0'].map(th=>{
    const v=bt.by_threshold[th].validation_2021_22, t=bt.by_threshold[th].test_2023_25;
    return '<tr class="'+(th==='3.0'?'hl':'')+'"><td class="num" data-th="Threshold">≥ '+th+'</td><td class="num" data-th="Val n">'+v.n+'</td><td class="num" data-th="Val W–L">'+v.w+'–'+v.l+'</td><td class="num" data-th="Val ATS">'+pct1(v.win_pct,1)+'</td><td class="num" data-th="Test n">'+t.n+'</td><td class="num" data-th="Test W–L">'+t.w+'–'+t.l+'</td><td class="num" data-th="Test ATS">'+pct1(t.win_pct,1)+'</td></tr>';
  }).join('');
  const seasonRows=Object.keys(bt.test_by_season_at_3).sort().map(s=>{
    const r=bt.test_by_season_at_3[s];
    return '<tr><td class="num" data-th="Season">'+s+'</td><td class="num" data-th="n">'+r.n+'</td><td class="num" data-th="W–L">'+r.w+'–'+r.l+'</td><td class="num" data-th="ATS">'+pct1(r.win_pct,1)+'</td></tr>';
  }).join('');
  /* 2026 per-pick results (record.json picks array, displayed verbatim, grouped by week). */
  const wk2026={}; rec.weeks.forEach(w=>wk2026[w.week]=w);
  const resSpan=(res,isVoid)=>{
    if(isVoid) return '<span class="res" style="color:var(--warn);background:var(--warn-soft)">Void</span>';
    if(res==='win') return '<span class="res win">Win</span>';
    if(res==='loss') return '<span class="res loss">Loss</span>';
    if(res==='push') return '<span class="res" style="color:var(--muted);background:var(--surface2)">Push</span>';
    return '<span class="res" style="color:var(--faint);background:var(--surface2)">Ungraded</span>';
  };
  let pickWeek=null;
  const pickRows=(rec.picks||[]).map(p=>{
    let head='';
    if(p.week!==pickWeek){pickWeek=p.week;const w=wk2026[p.week];
      head='<tr><td colspan="6" class="wkhead" style="color:var(--faint);font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;padding:16px 14px 4px;border-bottom:1px solid var(--border)">Week '+p.week+(w?'&nbsp;<span style="letter-spacing:0;text-transform:none;font-weight:600">'+w.w+'–'+w.l+'</span>':'')+'</td></tr>';}
    const isVoid=p.void===true||p.result==='void';
    const gameCell=isVoid
      ?'<td data-th="Game" style="white-space:normal">'+esc(p.game)+'<br><span style="font-size:11.5px;color:var(--faint);white-space:normal">'+esc(p.void_reason||'Voided — not graded')+'</span></td>'
      :'<td data-th="Game">'+esc(p.game)+'</td>';
    return head+'<tr>'+gameCell+'<td data-th="Pick">'+esc(p.pick)+'</td><td class="num" data-th="Market">'+signed(p.market_spread,1)+'</td><td class="num" data-th="Model edge">'+signed(p.edge,1)+'</td><td class="num" data-th="Final">'+(p.final?esc(p.final):'—')+'</td><td class="num" data-th="Result">'+resSpan(p.result,isVoid)+'</td></tr>';
  }).join('');
  const picksSection=(rec.picks&&rec.picks.length)
    ?'<div class="sec-title">Per-pick results · 2026 season</div><div class="tbl-wrap"><table class="plain"><thead><tr><th>Game</th><th>Pick</th><th class="num">Market</th><th class="num">Model edge</th><th class="num">Final</th><th class="num">Result</th></tr></thead><tbody>'+pickRows+'</tbody></table></div><p class="viz-note">Voided picks are not counted in the weekly or season W–L.</p>'
    :'';
  return pageHead('How it did on unfamiliar games','Performance','The model was tested on the 2023–2025 seasons without changing it after seeing those results. The first question is simple: how many points did each forecast miss by, on average?')+
  '<div class="sec-title">Average miss in points</div>'+
  '<div class="mae-duo"><div class="mae-card model-card"><div class="lab">Model prediction</div><div class="v">'+fmt(bt.test_mae.model,2)+'</div><div class="sub">average points away from the final margin</div></div>'+
  '<div class="mae-card"><div class="lab">Market line</div><div class="v">'+fmt(bt.test_mae.market,2)+'</div><div class="sub">average points away from the final margin</div></div></div>'+
  '<div class="verdict"><b>The market was more accurate on games the model had never seen.</b> Its average miss was '+fmt(bt.test_mae.market,2)+' points versus '+fmt(bt.test_mae.model,2)+' for the model. The difference is real in this test, but it does not establish a betting edge.</div>'+
  '<div class="sec-title">2026 paper tracking</div><div class="weeks2026">'+
    rec.weeks.map(w=>'<div class="wk"><div class="h">Week '+w.week+'</div><div class="r">'+w.w+'–'+w.l+(w.pending?' <span style="font-size:12px;color:var(--faint)">+'+w.pending+' pending</span>':'')+'</div><div class="c">'+(w.clv_n?'Line movement tracked on '+w.clv_n+' picks':'No graded line movement yet')+'</div></div>').join('')+
    '<div class="wk" style="border-color:var(--model)"><div class="h">Season</div><div class="r" style="color:var(--model-ink)">'+rec.season.w+'–'+rec.season.l+'</div><div class="c">Paper results only · '+rec.season.clv_n+' picks with line tracking</div></div>'+
  '</div>'+
  '<details class="page-sub" style="margin-top:22px"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body">'+
  '<div class="sec-title">Against-the-spread history by threshold</div><div class="tbl-wrap"><table class="plain"><thead><tr><th class="num">Threshold</th><th class="num">Validation n</th><th class="num">Validation W–L</th><th class="num">Validation ATS</th><th class="num">Test n</th><th class="num">Test W–L</th><th class="num">Test ATS</th></tr></thead><tbody>'+thRows+'</tbody></table></div>'+
  '<p class="viz-note">Validation 2021–2022 · locked test 2023–2025. Production threshold is |edge| ≥ 3.0 (highlighted): '+t3t.w+'–'+t3t.l+', '+pct1(t3t.win_pct,1)+' on n='+t3t.n+'. Breakeven at −110 is '+pct1(bt.breakeven_at_minus110,1)+'.</p>'+
  '<div class="sec-title">Season splits · locked test at 3.0</div><div class="tbl-wrap"><table class="plain"><thead><tr><th class="num">Season</th><th class="num">n</th><th class="num">W–L</th><th class="num">ATS</th></tr></thead><tbody>'+seasonRows+'</tbody></table></div>'+
  '<div class="sec-title">Cumulative record · locked test at 3.0</div><p class="viz-note">This chart shows how wins minus losses accumulated over the held-out test.</p><div class="chart-card">'+cumSVG(bt.test_cumulative_at_3)+'</div>'+picksSection+
  '<p class="viz-note">'+esc(state.data.meta.lines_note)+'</p></div></details>';
}

/* ============================================================
   MODEL
   ============================================================ */
function ensembleSVG(){
  const W=920,H=330;
  const node=(x,y,w,h,t1,t2,hl)=>'<g><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="10" fill="'+(hl?'rgba(91,140,255,.14)':'var(--surface2)')+'" stroke="'+(hl?'var(--model)':'var(--border)')+'" stroke-width="'+(hl?2:1)+'"/>'+
    '<text x="'+(x+w/2)+'" y="'+(y+30)+'" fill="var(--text)" font-size="16" font-weight="700" text-anchor="middle" font-family="var(--sans)">'+t1+'</text>'+
    '<text x="'+(x+w/2)+'" y="'+(y+52)+'" fill="var(--faint)" font-size="12" text-anchor="middle" font-family="var(--mono)">'+t2+'</text></g>';
  const lane=(x1,y1,x2,y2,l)=>'<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="var(--model)" stroke-width="2.5"/><text x="'+((x1+x2)/2+6)+'" y="'+((y1+y2)/2-6)+'" fill="var(--model-ink)" font-size="13" font-family="var(--mono)" font-weight="700">'+l+'</text>';
  const cy=120, xw=10, xn=290, xx=520;
  return '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Ensemble: 40 percent ELO, 50 percent EPA-linear, 10 percent GBM">'+
    node(xw,20,170,70,'ELO','rating system')+node(xw,120,170,70,'EPA-linear','linear model')+node(xw,220,170,70,'GBM','gradient boosting')+
    lane(xw+170,55,xn,80,'40%')+lane(xw+170,155,xn,165,'50%')+lane(xw+170,255,xn,250,'10%')+
    node(xn,110,180,110,'V1 blend','0.4·ELO + 0.5·EPA + 0.1·GBM',true)+
    '<line x1="'+(xn+180)+'" y1="165" x2="'+xx+'" y2="165" stroke="var(--market)" stroke-width="2.5"/>'+
    node(xx,110,240,110,'Model spread','home-spread convention',false)+
    '<text x="10" y="310" fill="var(--faint)" font-size="11.5" font-family="var(--sans)">Frozen weights · frozen threshold |edge| ≥ 3.0 · frozen information set</text></svg>';
}
function renderModel(){
  const m=state.data.meta;
  return pageHead('How it works','Model','The model produces one expected game margin from team strength, recent play-by-play performance, and matchup patterns.')+
  '<div class="quick-read"><div class="q"><div class="k">What it predicts</div><div class="v">Game margin</div><div class="s">Shown as a spread, then compared with the market.</div></div><div class="q"><div class="k">When a pick appears</div><div class="v">3.0+ pts</div><div class="s">The model must differ from the market by at least three points; QB news may remove a pick.</div></div><div class="q"><div class="k">Honest verdict</div><div class="v">No verified edge</div><div class="s">The market had the smaller average miss on games the model had never seen.</div></div></div>'+
  '<div class="sentence">This is the strongest version found with the available pregame information.<small>Its choices were fixed using 2021–2022 games, then checked once on 2023–2025 games without changing the model afterward.</small></div>'+ 
  '<details class="page-sub"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body">'+
  '<div class="sec-title">Model flow</div><p class="details-note">The diagram shows how the three component margins are blended into the final model spread.</p><div class="diagram">'+ensembleSVG()+'</div>'+
  '<div class="sec-title">Training periods</div><div class="timeline">'+
    '<div class="tl-card"><div class="t">Train</div><div class="y">2018–2020</div><div class="d">Linear components fit.</div></div>'+
    '<div class="tl-card"><div class="t">Validation</div><div class="y">2021–2022</div><div class="d">Weights and threshold selected here.</div></div>'+
    '<div class="tl-card" style="border-color:var(--model)"><div class="t">Locked test</div><div class="y">2023–2025</div><div class="d">Reported once. Basis for "no verified edge".</div></div>'+
  '</div>'+
  '<div class="sec-title">Specification</div><div class="spec-grid">'+
    '<div class="card"><div class="sec-title" style="margin-bottom:8px">Blend</div><p class="mono" style="margin:0">'+esc(m.ensemble)+'</p><p class="viz-note">Model version '+esc(mLabel(m.model_version))+' · status: '+(statusOf(m.model_version)==='production'?'production':'experimental')+'.</p></div>'+
    '<div class="card"><div class="sec-title" style="margin-bottom:8px">Decision rule</div><p class="mono" style="margin:0">paper play ⇔ |edge| ≥ '+fmt(m.threshold,1)+'</p><p class="viz-note">edge = model spread − market spread (home-spread convention). QB vetoes can only remove plays, never create or flip them.</p></div>'+
  '</div></div></details>';
}

/* ============================================================
   CLV
   ============================================================ */
function renderCLV(){
  const clv=state.data.clv, a=clv.aggregate;
  const posCls=v=>v>0?'pos':v<0?'neg':'zero';
  return pageHead('After the pick','Line Movement','How each tracked pick moved against the nflverse closing-line proxy. This is descriptive and the sample is small.')+
  '<span class="proxy-line">nflverse close proxy — not a verified close.</span>'+
  '<div class="clv-agg">'+
    '<div class="stat"><div class="v">'+a.n+'</div><div class="l">Graded picks</div></div>'+
    '<div class="stat"><div class="v" style="color:var(--good)">'+signed(a.avg_clv_pts,2)+'</div><div class="l">Average line movement</div></div>'+
    '<div class="stat"><div class="v">'+pct1(a.hit_rate,0)+'</div><div class="l">Positive movement rate</div></div>'+
  '</div>'+
  '<div class="sec-title">Movement by pick</div><div class="clv-list">'+
    clv.picks.map(p=>'<div class="clv-pick"><span class="wk-t">W'+p.week+'</span><span class="g">'+esc(p.game)+'<small>'+esc(p.pick)+'</small></span><span class="res '+p.result+'">'+(p.result==='win'?'Win':'Loss')+'</span><span class="pts '+posCls(p.clv_pts)+'">'+signed(p.clv_pts,1)+'</span></div>').join('')+
  '</div><p class="viz-note">Line movement here is measured against a public closing-line proxy, not a book-verified close. A sample of '+a.n+' picks is too small for a verdict; it is shown for transparency, not triumph.</p>';
}

/* ============================================================
   DATA HEALTH
   ============================================================ */
function daysOld(isoish){
  const t=Date.parse(String(isoish||'').replace(' UTC','Z'));
  return isNaN(t)?null:Math.floor((Date.now()-t)/86400000);
}
function pill(label,cls){return '<span class="stat-pill '+cls+'">'+esc(label)+'</span>';}
function renderHealth(){
  const m=state.data.meta, P=state.data.props, inj=state.data.injuries, prs=state.data.predictions.games;
  const linesN=prs.filter(g=>Number.isFinite(Number(g.market_spread))).length;
  const propLines=P.props.filter(x=>x.market_line!=null).length;
  const age=daysOld(m.generated_at), iage=daysOld(inj.as_of);
  const hcard=(t,status,big,meta,rule)=>'<div class="hcard"><div class="hd"><span class="t">'+t+'</span>'+status+'</div><div class="big">'+big+'</div><div class="meta">'+meta+'</div><div class="rule">Rule: '+rule+'</div></div>';
  return pageHead('Integrity','Data health','Statuses come from actual validation of this snapshot — never manufactured.')+
  '<div class="health-grid">'+
    hcard('Weekly game snapshot', age!=null&&age<=7?pill('Current','cur'):pill('Stale','stl'), 'Week '+m.latest_week+' · '+prs.length+' games', 'Generated '+esc(m.generated_at)+' ('+(age===0?'today':age+' days ago')+')',
      'Current = generated ≤ 7 days ago and week == '+m.latest_week+'.')+
    hcard('Market lines', linesN===prs.length?pill('Current','cur'):pill('Missing','mis'), fmtInt(linesN)+' / '+prs.length+' games', 'Every game carries a market spread in the export.',
      'Current = all '+prs.length+' games have a finite market spread.')+
    hcard('Injury feed', inj.available&&iage!=null&&iage<=7?pill('Current','cur'):pill('Stale','stl'), fmtInt(inj.snapshot_rows)+' snapshot rows', 'As of '+esc(inj.as_of)+' ('+(iage===0?'today':iage+' days ago')+'). Statuses: '+inj.status_counts.out+' out · '+inj.status_counts.doubtful+' doubtful · '+inj.status_counts.questionable+' questionable.',
      'Current = feed available ≤ 7 days ago. Note: snapshot rows have no per-row date_modified.')+
    hcard('Player projections', propLines>0?pill('Current','cur'):pill('No market lines captured yet','warnst'), fmtInt(P.props.length)+' projections', 'Market lines captured: '+propLines+'. Model: '+esc(propsModelLabel(P.model))+'.',
      'Amber until at least one market line is captured; projections are then projection-only by construction.')+
    hcard('Unfamiliar-game test', pill('Current','cur'), fmtInt(state.data.backtest.by_threshold['3.0'].test_2023_25.n)+' graded picks', 'The 2023–2025 results were checked without changing the model after seeing them.',
      'Current = the saved test results are present for every comparison threshold.')+
    hcard('Model snapshot', pill('Current','cur'), esc(mLabel(state.modelVersion)), 'Status: '+statusOf(state.modelVersion)+'. '+esc(String((state.manifest.versions||[]).length))+' exported version(s).',
      'Current = the snapshot list loads and the active version is present.')
  +'</div>'+
  '<p class="viz-note">The injury feed is a weekly snapshot. It does not include a trustworthy timestamp for each player update, so this page cannot know when the market learned the news. Friday snapshots included: '+fmtInt((inj.friday_frozen_files||[]).length)+'.</p>';
}

/* ============================================================
   ABOUT
   ============================================================ */
function renderAbout(){
  const m=state.data.meta, bt=state.data.backtest, t3=bt.by_threshold['3.0'].test_2023_25;
  const sec=(t,body,cls)=>'<section class="about-sec'+(cls?' '+cls:'')+'"><h3>'+t+'</h3>'+body+'</section>';
  return pageHead('Read me','About','What this research can tell you, what it cannot, and how to read the results honestly.')+
  '<div class="about-grid">'+
  sec('What it does','<p>Each week, the model estimates the scoring margin for every NFL game and compares that estimate with the market spread. It also produces player yardage projections. Everything is tracked on paper; there are no real-money recommendations.</p>')+
  sec('How it was checked','<p>The model learned from older seasons, made its choices using 2021–2022 games, then was tested on the 2023–2025 seasons without changing it after seeing those results. On those unfamiliar games, the market&rsquo;s average miss was '+fmt(bt.test_mae.market,2)+' points versus '+fmt(bt.test_mae.model,2)+' for the model.</p>')+
  sec('What it does not claim','<p>It does not claim a betting edge. A difference between the model and market is not proof of predictive advantage. Green marks favorable observed outcomes or positive line movement; it never means certainty.</p>','warn-sec')+
  sec('Important limits','<ul><li>The market was the more accurate baseline on unfamiliar games.</li><li>Closing lines use a public proxy rather than a book-verified close.</li><li>The injury feed cannot show exactly when the market learned each update.</li><li>Player projection ranges remain experimental and are not probabilities of being correct.</li></ul>','amber-sec')+
  '</div><details class="page-sub" style="margin-top:16px"><summary><span>Technical details</span><span class="ch"></span></summary><div class="sub-body">'+
  '<p><b>Model version:</b> '+esc(mLabel(m.model_version))+' · '+esc(m.ensemble)+' · paper threshold |edge| ≥ '+fmt(m.threshold,1)+'.</p>'+
  '<p><b>Training and evaluation:</b> linear components fit on 2018–2020; blend weights and threshold selected on 2021–2022; locked 2023–2025 test reported once. At 3.0, the ATS record was '+t3.w+'–'+t3.l+' ('+pct1(t3.win_pct,1)+') on n='+t3.n+'. Locked-test MAE was '+fmt(bt.test_mae.model,2)+' for the model and '+fmt(bt.test_mae.market,2)+' for the market.</p>'+
  '<p><b>Architecture:</b> ELO + EPA-linear + GBM. Player projections use Model D from Player Projection v2 · Experimental. The exported uncertainty labels are High, Medium, and Low; High means more uncertainty, never more confidence.</p>'+
  '<p><b>Snapshot:</b> '+m.season+' week '+m.latest_week+', generated '+esc(m.generated_at)+'. Nothing on this page updates itself.</p></div></details>';
}

/* ============================================================
   MORE (mobile utility hub)
   ============================================================ */
function renderMore(){
  const items=[
    ['Performance','Results on unfamiliar games and this season’s paper record.'],
    ['Model','How the model turns team information into a projected margin.'],
    ['CLV','How the line moved after each tracked pick.'],
    ['Data Health','Validation statuses behind this snapshot.'],
    ['About','What the model does and refuses to claim.']
  ];
  return pageHead('More','More','Utility sections.')+
  '<div class="more-list">'+items.map(x=>'<button class="more-item" data-goto="'+x[0]+'"><span><span class="t">'+(x[0]==='CLV'?TERMS.lineMovement:x[0])+'</span><br><span class="d">'+esc(x[1])+'</span></span><span class="chev">›</span></button>').join('')+'</div>';
}
function bindMore(){}

/* ---------- boot ---------- */
manifestInit();
})();
