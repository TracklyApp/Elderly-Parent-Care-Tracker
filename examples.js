/* Trial records live in their own browser store and never enter the family data. */
(()=>{
  const starter=KindredExamples.create(),collections=['entries','medications','doses','tasks','shifts','questions','handoffs'],trialKey='kindred-demo-trial-v1';
  const starterIds=Object.fromEntries(collections.map(k=>[k,new Set(starter[k].map(r=>r.id))]));
  let demo=starter;
  const added=p=>collections.reduce((sum,k)=>sum+(p[k]||[]).filter(r=>!starterIds[k].has(r.id)).length,0);
  function validate(p){Care.validate({version:2,profiles:[p]});if(p.id!==starter.id||!p.isDemo)throw Error('Invalid demo profile.');for(const k of collections)if([...starterIds[k]].some(id=>!p[k].some(r=>r.id===id)))throw Error('The 20 starter examples stay in the demo. You can delete records you added.');if(added(p)>20)throw Error('Demo limit reached: 20 additional records. Activate full app to use your own care profile, or delete a trial record to free a space.');}
  try{const saved=localStorage.getItem(trialKey);if(saved){const restored=JSON.parse(saved);validate(restored);demo=restored;}}catch{toast('The saved trial could not be loaded. The starter examples are shown; personal records are unchanged.');}
  let snapshot=structuredClone(demo);
  function restore(copy){Object.keys(demo).forEach(k=>delete demo[k]);Object.assign(demo,structuredClone(copy));}
  const realProfile=profile,priorNav=nav,priorRender=render,priorEditing=editingAllowed,priorSettings=settingsScreen,priorPersist=persist;
  profile=function(){return activeProfileId===demo.id?demo:realProfile();};
  if(!KindredActivation.isActivated()){familyData={version:2,profiles:[demo]};activeProfileId=demo.id;}
  editingAllowed=function(){return profile().isDemo?true:priorEditing();};
  persist=function(){if(!profile().isDemo)return priorPersist();try{validate(demo);localStorage.setItem(trialKey,JSON.stringify(demo));snapshot=structuredClone(demo);return true;}catch(error){restore(snapshot);if(error.message.startsWith('Demo limit reached'))setTimeout(()=>KindredActivation.require(),0);throw error;}};
  window.KindredDemo={added:()=>added(demo),restore,save:persist};
  const submitEntry=$('#entryForm').onsubmit;
  $('#entryForm').onsubmit=async function(event){try{await submitEntry.call(this,event);}catch(error){if(!profile().entries.some(r=>r.id===this.dataset.id))delete this.dataset.id;let note=this.querySelector('.trial-error');if(!note){note=document.createElement('p');note.className='form-error trial-error';note.setAttribute('role','alert');this.append(note);}note.textContent=error.message;}};
  const openOriginal=openEntry;openEntry=function(...args){$('#entryForm .trial-error')?.remove();openOriginal(...args);};
  nav=function(){priorNav();const picker=$('#profilePicker');if(!picker.querySelector('option[value="'+demo.id+'"]'))picker.insertAdjacentHTML('beforeend',`<option value="${demo.id}">Demo - Eleanor Brooks</option>`);picker.value=profile().id;};
  settingsScreen=function(){return card('Appearance',`<label>Color theme<select id="themePreference"><option value="system">Use device setting</option><option value="light">Light</option><option value="dark">Dark</option></select></label><p class="note">Your preference is remembered on this browser.</p>`)+priorSettings();};
  render=function(){
    priorRender();const isDemo=profile().isDemo===true;document.body.classList.toggle('demo-mode',isDemo);
    $('#exportButton').disabled=isDemo;$('#profileButton').disabled=isDemo;$('#importButton').disabled=isDemo||!editingAllowed();
    $('#demoBanner')?.remove();
    if(isDemo){
      $('#content').insertAdjacentHTML('beforebegin',`<section id="demoBanner" class="demo-banner"><div><strong>Demo: 20 examples + ${added(demo)}/20 trial records</strong><p>Add up to 20 records across all categories and care tools. Trial changes are saved separately in this browser. Use fictional information. Activate to start your own care profile.</p></div><button class="primary" data-leave-demo>${KindredActivation.isActivated()?'Back to my care':'Activate full app'}</button></section>`);
      document.querySelectorAll('[data-new-parent],[data-premium-delete-parent],[data-upload-document],[data-auth],[data-premium-backup],[data-notifications],[data-enable-push]').forEach(b=>b.disabled=true);
    }else if(view==='overview')$('#content').insertAdjacentHTML('afterbegin','<section class="demo-banner demo-launch"><div><strong>Try Kindred with examples</strong><p>20 starter examples plus space for 20 trial records, separate from your personal care data.</p></div><button class="secondary" data-open-demo>Explore examples</button></section>');
    KindredTheme.apply();
  };
  document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-open-demo')){selectProfile(demo.id);render();}if(b.hasAttribute('data-leave-demo')){selectProfile(familyData.profiles[0].id);render();}});
  render();
})();
