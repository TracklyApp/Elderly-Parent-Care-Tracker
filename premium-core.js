/* Pure helpers for local care planning, search, and profile personalization. */
(function(root){
 const C=root.Care,previousValidate=C.validate;
 const limits={preferredName:80,preferences:2000,routine:3000,goals:2000,communication:1500};
 C.validate=function(state){previousValidate(state);for(const p of state.profiles){
  if(p.careDetails!==undefined){const d=p.careDetails;if(!d||typeof d!=='object'||Array.isArray(d))throw Error('Invalid personal care details.');
   for(const [key,max] of Object.entries(limits))if(d[key]!==undefined&&(typeof d[key]!=='string'||d[key].length>max))throw Error('Invalid '+key+'.');
   if(d.photo!==undefined&&(typeof d.photo!=='string'||d.photo.length>160000||(d.photo&&!/^data:image\/jpeg;base64,[A-Za-z0-9+/]+=*$/.test(d.photo))))throw Error('Invalid profile photo.');
  }
 }return true;};
 function agenda(p,now=new Date()){
  const day=C.day(now),rows=[];
  const status=(date,done)=>done?'recorded':new Date(date)<now?'needs-record':'upcoming';
  for(const d of C.dosesOn(p,day))rows.push({kind:'medication',id:d.medication.id,date:d.scheduled,title:d.medication.name,detail:d.medication.dosage,assignee:d.medication.responsibleId||'',status:status(d.scheduled,!!d.record),result:d.record?.status||''});
  // Carry forward unfinished one-time tasks, but do not duplicate recurring tasks.
  const tasks=[...C.tasksOn(p,day),...p.tasks.filter(t=>t.active&&t.repeat==='none'&&t.date.slice(0,10)<day&&!t.completed.some(c=>c.date===t.date.slice(0,10))).map(t=>({...t,occurrence:t.date}))];
  for(const t of tasks)rows.push({kind:'task',id:t.id,date:t.occurrence,title:t.title,detail:t.notes,assignee:t.assignee,status:status(t.occurrence,!!t.completion),result:t.completion?'completed':''});
  for(const e of p.entries.filter(e=>e.category==='appointments'&&(e.date.slice(0,10)===day||(!e.done&&e.date.slice(0,10)<day))))rows.push({kind:'appointment',id:e.id,date:e.date,title:e.title,detail:e.notes,assignee:e.author,status:status(e.date,e.done),result:e.done?'completed':''});
  return rows.sort((a,b)=>a.date.localeCompare(b.date));
 }
 function search(p,f={}){const query=(f.query||'').trim().toLowerCase();return p.entries.filter(e=>(!query||[e.title,e.notes,e.author].some(s=>s.toLowerCase().includes(query)))&&(!f.category||e.category===f.category)&&(!f.author||e.author===f.author)&&(!f.from||e.date.slice(0,10)>=f.from)&&(!f.to||e.date.slice(0,10)<=f.to)&&(!f.handoff||e.handoff)).sort((a,b)=>b.date.localeCompare(a.date));}
 root.KindredPremium={agenda,search,limits};
})(globalThis);
