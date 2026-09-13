(function(root){
  const C=root.Care,baseValidate=C.validate;
  C.upgrade=function(s){for(const p of s.profiles){p.shifts??=[];p.questions??=[];p.timezone??=Intl.DateTimeFormat().resolvedOptions().timeZone;for(const m of p.medications){m.weekdays??=[0,1,2,3,4,5,6];m.restocks??=[];}}return s;};
  C.validate=function(s){baseValidate(s);for(const p of s.profiles){
    for(const key of ['shifts','questions'])if(p[key]!==undefined&&(!Array.isArray(p[key])||new Set(p[key].map(x=>x.id)).size!==p[key].length))throw Error('Invalid '+key);
    for(const m of p.medications){if(m.weekdays&&(!Array.isArray(m.weekdays)||!m.weekdays.length||m.weekdays.some(d=>!Number.isInteger(d)||d<0||d>6)))throw Error('Select valid medication days.');for(const k of ['stockInitial','unitsPerDose','lowStockAt'])if(m[k]!=null&&(!Number.isFinite(m[k])||m[k]<0))throw Error('Invalid medication stock.');if(m.restocks&&(!Array.isArray(m.restocks)||m.restocks.some(r=>!r.id||!Number.isFinite(r.quantity)||r.quantity<=0)))throw Error('Invalid restock.');}
    for(const s of p.shifts||[])if(!s.id||!s.caregiver||!Number.isFinite(Date.parse(s.start))||!Number.isFinite(Date.parse(s.end))||s.end<=s.start)throw Error('A shift needs a caregiver and an end after its start.');
    for(const q of p.questions||[])if(!q.id||!q.title||!['open','answered'].includes(q.status))throw Error('Invalid consultation question.');
  }return true;};
  const baseDoses=C.dosesOn;
  C.dosesOn=(p,date)=>baseDoses(p,date).filter(d=>(d.medication.weekdays||[0,1,2,3,4,5,6]).includes(new Date(date+'T12:00').getDay()));
  C.nextDose=function(p,now=new Date()){const candidates=[];for(const m of p.medications.filter(m=>m.active)){let date=C.day(now);if(m.start>date)date=m.start;for(let i=0;i<8;i++,date=C.addDays(date,1)){for(const d of C.dosesOn({...p,medications:[m]},date))if(!d.record&&new Date(d.scheduled)>=now)candidates.push(d);}}return candidates.sort((a,b)=>a.scheduled.localeCompare(b.scheduled))[0]||null;};
  const baseRecord=C.recordDose;
  C.recordDose=function(p,id,at,...args){if(!C.dosesOn(p,at.slice(0,10)).some(d=>d.medication.id===id&&d.scheduled===at))throw Error('No dose is scheduled for this day.');return baseRecord(p,id,at,...args);};
  C.stock=(p,m)=>m.stockInitial==null?null:Math.round((m.stockInitial+(m.restocks||[]).reduce((s,r)=>s+r.quantity,0)-p.doses.filter(d=>d.medicationId===m.id&&d.status==='taken').length*(m.unitsPerDose||1))*100)/100;
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  C.merge=function(base,local,remote,choices={}){
    const conflicts=[];
    function merge(b,l,r,path){
      if(same(l,r))return l;if(same(b,l))return r;if(same(b,r))return l;
      if(l&&r&&b&&typeof l==='object'&&typeof r==='object'&&typeof b==='object'){
        if(Array.isArray(l)&&Array.isArray(r)&&Array.isArray(b)&&[...l,...r,...b].every(x=>x&&typeof x==='object'&&typeof x.id==='string')){
          const bm=new Map(b.map(x=>[x.id,x])),lm=new Map(l.map(x=>[x.id,x])),rm=new Map(r.map(x=>[x.id,x]));return [...new Set([...bm.keys(),...lm.keys(),...rm.keys()])].map(id=>merge(bm.get(id),lm.get(id),rm.get(id),path+'/'+id)).filter(x=>x!==undefined);
        }
        if(!Array.isArray(l)&&!Array.isArray(r)&&!Array.isArray(b)){const out={};for(const k of new Set([...Object.keys(b),...Object.keys(l),...Object.keys(r)])){const v=merge(b[k],l[k],r[k],path+'/'+k);if(v!==undefined)out[k]=v;}return out;}
      }
      if(choices[path])return choices[path]==='local'?l:r;
      conflicts.push({path,local:l,remote:r});return l;
    }
    return {state:merge(base,local,remote,''),conflicts};
  };
})(globalThis);
