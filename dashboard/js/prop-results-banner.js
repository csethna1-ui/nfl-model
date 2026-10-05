/* Prop results banner — standalone companion to js/app.js.
   Fetches data/v1/prop_results.json and injects a Week-results summary at the
   top of the Props page. Re-injects after SPA re-renders (filters, paging).
   Kept separate because app.js exceeds the API push size limit. */
(function(){
  var DATA_URL='data/v1/prop_results.json';
  var R=null;
  function esc(s){return String(s==null?'':s).replace(/[&<>'"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c];});}
  function titleCase(s){return String(s||'').replace(/_/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase();});}
  function rows(obj){
    return Object.keys(obj||{}).sort().map(function(k){
      var d=obj[k], p=d.win_pct==null?'—':(d.win_pct*100).toFixed(1)+'%';
      return '<div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0"><span>'+esc(titleCase(k))+'</span><span><b>'+d.wins+'–'+d.losses+(d.pushes?'–'+d.pushes:'')+'</b> · '+p+'</span></div>';
    }).join('');
  }
  function html(){
    var s=R.summary, wpct=s.win_pct==null?'—':(s.win_pct*100).toFixed(1)+'%';
    return '<div class="why-box" style="margin:0 0 16px"><h2 style="margin:0 0 2px;font-size:20px">Week '+esc(R.week)+' Results · '+s.wins+'–'+s.losses+' ('+wpct+')</h2>'+
      '<p class="desc" style="margin:0 0 10px">'+esc(R.note||'')+' '+s.graded+' leans graded against Friday 18:00 CT lines; '+s.dnps+' DNPs excluded (never scored as zero). Experimental paper-track — no verified edge.</p>'+
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 22px">'+
      '<div><span class="fgroup-label">By market</span>'+rows(R.by_market)+'</div>'+
      '<div><span class="fgroup-label">By model</span>'+rows(R.by_model)+'</div>'+
      '</div></div>';
  }
  function inject(){
    var app=document.getElementById('app');
    if(!app||!R) return;
    if(app.querySelector('.prb-banner')) return;
    var head=app.querySelector('.pboard .page-head');
    if(!head) return;
    var div=document.createElement('div');
    div.className='prb-banner';
    div.innerHTML=html();
    head.after(div);
  }
  fetch(DATA_URL,{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(d){R=d;inject();}).catch(function(){});
  var appEl=document.getElementById('app');
  if(appEl&&window.MutationObserver){
    new MutationObserver(function(){inject();}).observe(appEl,{childList:true,subtree:true});
  }
})();
