/* Presentation only: all dashboard figures come from the selected care profile. */
(()=>{
 const previousRender=render;
 function dashboard(){
  const p=profile(),today=Care.day(),doses=Care.dosesOn(p,today),recorded=doses.filter(d=>d.record).length;
  const percent=doses.length?Math.round(recorded/doses.length*100):0;
  const firstName=p.name==='Parent'?'your loved one':p.name.replace(/^Demo · /,'').split(' ')[0];
  const welcome=$('.welcome');
  if(welcome)welcome.innerHTML=`<div class="hero-copy"><div class="hero-label"><span></span> YOUR FAMILY CARE SPACE</div><h2>A clearer day.<br>A little more care.</h2><p>Everything that matters for ${esc(firstName)}, thoughtfully kept together.</p><div class="hero-links"><button class="primary" data-view="calendar">View today’s plan <span aria-hidden="true">↗</span></button><button class="text-button" data-view="handoff">Caregiver handoff →</button></div></div><div class="daily-ring-panel"><div class="daily-ring" data-progress="${percent}"><div><strong>${recorded}<span> / ${doses.length}</span></strong><small>Doses recorded</small></div></div><p>${doses.length?`${doses.filter(d=>d.record?.status==='taken').length} taken · ${doses.filter(d=>d.record?.status==='skipped').length} skipped`:'No doses scheduled today'}</p><span class="hero-date">TODAY · ${esc(new Date().toLocaleDateString('en-US',{month:'short',day:'numeric'}))}</span></div>`;
  const days=Array.from({length:7},(_,i)=>{const date=Care.addDays(today,i-6);return {date,count:p.entries.filter(e=>e.date.slice(0,10)===date).length};});
  const max=Math.max(1,...days.map(d=>d.count)),total=days.reduce((s,d)=>s+d.count,0);
  const lastVital=sorted(p.entries.filter(e=>e.category==='vitals'&&e.date<=localDate()&&e.vitals&&Object.keys(e.vitals).length))[0];
  const v=lastVital?.vitals||{};
  const values=[['Blood pressure',v.systolic!=null&&v.diastolic!=null?`${v.systolic}/${v.diastolic}`:'—','mmHg'],['Pulse',v.pulse??'—','bpm'],['Temperature',v.temperature??'—','°C']];
  const panel=`<div class="insight-grid"><section class="card activity-card"><div class="card-head"><div><div class="eyebrow">THE PAST SEVEN DAYS</div><h2>A week of everyday care</h2></div><span class="badge">${total} journal entries</span></div><div class="activity-chart" role="img" aria-label="${esc(days.map(d=>`${d.date}: ${d.count} entries`).join('; '))}">${days.map(d=>`<div class="activity-day ${d.date===today?'is-today':''}"><span class="activity-count">${d.count}</span><div class="activity-track"><div data-height="${d.count/max*100}"></div></div><span>${esc(new Date(d.date+'T12:00').toLocaleDateString('en-US',{weekday:'short'}))}</span></div>`).join('')}</div></section><section class="card latest-vitals"><div class="card-head"><div><div class="eyebrow">LATEST RECORDED</div><h2>Health at a glance</h2></div><button class="text-button" data-view="vitals">View log ↗</button></div><div class="vital-values">${values.map(([label,value,unit])=>`<div><span>${label}</span><strong>${esc(value)}</strong><small>${unit}</small></div>`).join('')}</div><p class="note">${lastVital?'Recorded '+esc(fmt(lastVital.date))+' · '+esc(lastVital.author):'Add a structured measurement in Vital Signs to see it here.'}</p></section></div>`;
  $('.stats')?.insertAdjacentHTML('afterend',panel);
  document.querySelectorAll('.daily-ring').forEach(el=>el.style.setProperty('--progress',el.dataset.progress+'%'));
  document.querySelectorAll('.activity-track>div').forEach(el=>el.style.height=el.dataset.height+'%');
 }
 render=function(){
  previousRender();document.body.dataset.view=view;
  if(view==='overview'){
   $('#pageTitle').textContent='Your care overview';
   $('#pageSubtitle').textContent='Small updates. A shared picture. More peace of mind.';
   dashboard();
  }
  document.querySelectorAll('nav button[data-view]').forEach(b=>{if(b.dataset.view===view)b.setAttribute('aria-current','page');});
 };
 render();
})();
