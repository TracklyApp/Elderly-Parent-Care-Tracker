/* Shared care scheduling and migration rules. No medical recommendations. */
(function (root) {
  const id = () => crypto.randomUUID();
  const day = (date = new Date()) => {
    const d = new Date(date);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  };
  function addDays(date, count) {
    const d = new Date(date + 'T12:00:00'); d.setDate(d.getDate() + count); return day(d);
  }
  function freshProfile(name = 'Parent') {
    return { id: id(), name, allergies: '', emergency: '', entries: [], medications: [], doses: [], tasks: [], handoffs: [] };
  }
  function migrate(data) {
    if (data?.version === 2) { validate(data); return data; }
    if (!data?.profile || !Array.isArray(data.entries)) throw Error('Invalid backup');
    const p = freshProfile(data.profile.name);
    p.allergies = data.profile.allergies || ''; p.emergency = data.profile.emergency || ''; p.entries = data.entries;
    const result = { version: 2, profiles: [p] }; validate(result); return result;
  }
  function validate(data) {
    if (data?.version !== 2 || !Array.isArray(data.profiles) || !data.profiles.length || data.profiles.length > 50) throw Error('Invalid profiles');
    const ids = new Set();
    for (const p of data.profiles) {
      if (typeof p.id !== 'string' || ids.has(p.id) || typeof p.name !== 'string' || !p.name.trim() || typeof p.allergies !== 'string' || typeof p.emergency !== 'string') throw Error('Invalid profile');
      ids.add(p.id);
      for (const key of ['entries','medications','doses','tasks','handoffs']) {
        if (!Array.isArray(p[key]) || p[key].length > 30000) throw Error('Invalid records');
        const recordIds = new Set();
        for (const r of p[key]) { if (!r || typeof r.id !== 'string' || recordIds.has(r.id)) throw Error('Invalid record ID'); recordIds.add(r.id); }
      }
      for (const e of p.entries) if (!['medication','appointments','vitals','symptoms','meals','daily','mood','sleep','incidents','doctor','expenses','team','documents'].includes(e.category) || !['title','notes','author','date'].every(k=>typeof e[k]==='string') || !Number.isFinite(Date.parse(e.date)) || typeof e.done !== 'boolean' || typeof e.handoff !== 'boolean' || !(e.amount === null || Number.isFinite(e.amount) && e.amount >= 0) || typeof e.unit !== 'string') throw Error('Invalid journal entry');
      for (const m of p.medications) if (typeof m.name!=='string' || typeof m.dosage!=='string' || typeof m.instructions!=='string' || !Array.isArray(m.times) || !m.times.length || m.times.some(t=>!/^([01]\d|2[0-3]):[0-5]\d$/.test(t)) || !/^\d{4}-\d{2}-\d{2}$/.test(m.start) || (m.end && (!/^\d{4}-\d{2}-\d{2}$/.test(m.end) || m.end<m.start)) || typeof m.active!=='boolean') throw Error('Invalid medication');
      for (const d of p.doses) if (!['taken','skipped'].includes(d.status) || !['medicationId','scheduled','recordedAt','author','reason','name','dosage'].every(k=>typeof d[k]==='string') || !Number.isFinite(Date.parse(d.scheduled)) || !Number.isFinite(Date.parse(d.recordedAt)) || (d.status==='skipped'&&!d.reason.trim())) throw Error('Invalid dose');
      if(new Set(p.doses.map(d=>d.medicationId+'|'+d.scheduled)).size!==p.doses.length) throw Error('Duplicate dose');
      for (const t of p.tasks) if (!['title','date','assignee','notes'].every(k=>typeof t[k]==='string') || !Number.isFinite(Date.parse(t.date)) || !['none','daily','weekly'].includes(t.repeat) || !['care','refill','appointment'].includes(t.kind) || typeof t.active!=='boolean' || !Array.isArray(t.completed) || t.completed.some(x=>!x || typeof x.date!=='string' || typeof x.author!=='string' || typeof x.at!=='string')) throw Error('Invalid task');
      for (const h of p.handoffs) if (!['from','to','createdAt','summary','notes'].every(k=>typeof h[k]==='string') || !Number.isFinite(Date.parse(h.createdAt)) || !['pending','accepted'].includes(h.status) || (h.status==='accepted' && (typeof h.acceptedBy!=='string' || !Number.isFinite(Date.parse(h.acceptedAt))))) throw Error('Invalid handoff');
    }
    return true;
  }
  function dosesOn(p, date) {
    return p.medications.flatMap(m => (m.active && m.start <= date && (!m.end || date <= m.end)) ? m.times.map(time => {
      const scheduled = date+'T'+time;
      return { medication: m, scheduled, record: p.doses.find(d=>d.medicationId===m.id && d.scheduled===scheduled) };
    }) : []).sort((a,b)=>a.scheduled.localeCompare(b.scheduled));
  }
  function nextDose(p, now = new Date()) {
    const candidates = p.medications.filter(m=>m.active).flatMap(m=>{
      let date = day(now); if(m.start>date) date=m.start;
      const result=[];
      for(let i=0;i<2;i++,date=addDays(date,1)) if(!m.end||date<=m.end) for(const time of m.times){ const scheduled=date+'T'+time; if(new Date(scheduled)>=now&&!p.doses.some(d=>d.medicationId===m.id&&d.scheduled===scheduled))result.push({medication:m,scheduled}); }
      return result;
    });
    return candidates.sort((a,b)=>a.scheduled.localeCompare(b.scheduled))[0] || null;
  }
  function tasksOn(p, date) {
    return p.tasks.filter(t=>t.active && t.date.slice(0,10)<=date).filter(t=>{
      if(t.repeat==='none')return t.date.slice(0,10)===date;
      if(t.repeat==='daily')return true;
      return new Date(t.date).getDay()===new Date(date+'T12:00').getDay();
    }).map(t=>({...t, occurrence:date+'T'+t.date.slice(11,16),completion:t.completed.find(c=>c.date===date)}));
  }
  function recordDose(p, medicationId, scheduled, status, author, reason='', now=new Date()) {
    const m=p.medications.find(m=>m.id===medicationId);
    if(!m || !['taken','skipped'].includes(status) || !author.trim() || (status==='skipped'&&!reason.trim()))throw Error('A caregiver and a reason for skipped doses are required.');
    if(!dosesOn(p,scheduled.slice(0,10)).some(d=>d.medication.id===medicationId&&d.scheduled===scheduled))throw Error('This dose is no longer scheduled.');
    if(new Date(scheduled)>now)throw Error('Future doses cannot be marked taken or skipped.');
    if(p.doses.some(d=>d.medicationId===medicationId&&d.scheduled===scheduled))throw Error('This dose has already been recorded.');
    const record={id:id(),medicationId,scheduled,status,author:author.trim(),reason:reason.trim(),recordedAt:now.toISOString(),name:m.name,dosage:m.dosage};p.doses.push(record);return record;
  }
  function ics(events) {
    const escape = s=>String(s).replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
    const stamp=d=>new Date(d).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
    const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Kindred//Care Calendar//EN','CALSCALE:GREGORIAN'];
    for(const e of events)lines.push('BEGIN:VEVENT','UID:'+escape(e.id)+'@kindred','DTSTAMP:'+stamp(new Date()),'DTSTART:'+stamp(e.date),'DTEND:'+stamp(new Date(new Date(e.date).getTime()+1800000)),'SUMMARY:'+escape(e.title),'DESCRIPTION:'+escape(e.notes||''),'BEGIN:VALARM','TRIGGER:-PT15M','ACTION:DISPLAY','DESCRIPTION:Care reminder','END:VALARM','END:VEVENT');
    lines.push('END:VCALENDAR');
    return lines.map(line=>{let out='',length=0;for(const c of line){const bytes=new TextEncoder().encode(c).length;if(length+bytes>73){out+='\r\n ';length=1;}out+=c;length+=bytes;}return out;}).join('\r\n')+'\r\n';
  }
  root.Care={id,day,addDays,freshProfile,migrate,validate,dosesOn,nextDose,tasksOn,recordDose,ics};
})(globalThis);
