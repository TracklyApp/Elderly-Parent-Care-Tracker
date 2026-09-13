/* Bundled examples remain separate from saved family records and reminders. */
(()=>{
  const demo=KindredExamples.create(), realProfile=profile, priorNav=nav, priorRender=render,
    priorEditing=editingAllowed, priorSettings=settingsScreen;
  profile=function(){return activeProfileId===demo.id?demo:realProfile();};
  editingAllowed=function(){return !profile().isDemo&&priorEditing();};
  nav=function(){priorNav();const picker=$('#profilePicker');picker.insertAdjacentHTML('beforeend',`<option value="${demo.id}">Demo · Eleanor Brooks (20 records total)</option>`);picker.value=profile().id;};
  settingsScreen=function(){return card('Appearance',`<label>Color theme<select id="themePreference"><option value="system">Use device setting</option><option value="light">Light</option><option value="dark">Dark</option></select></label><p class="note">Your preference is remembered on this browser.</p>`)+priorSettings();};
  render=function(){
    priorRender();const isDemo=profile().isDemo===true;document.body.classList.toggle('demo-mode',isDemo);
    $('#exportButton').disabled=isDemo;$('#profileButton').disabled=isDemo;
    $('#demoBanner')?.remove();
    if(isDemo){
      $('#content').insertAdjacentHTML('beforebegin','<section id="demoBanner" class="demo-banner"><div><strong>Demo · Fictional, read-only examples</strong><p>20 fictional records total: 13 journal entries and 7 medication, task, shift, question and handoff records. Documents are register examples; no files are attached.</p></div><button class="secondary" data-leave-demo>Back to my care</button></section>');
      // Allow browsing, searching and printable reports, but no account or care actions.
      document.querySelectorAll('#content button, #addButton, #profileButton, #importButton, #exportButton').forEach(b=>{
        const allowed=b.hasAttribute('data-view')||b.hasAttribute('data-close')||b.hasAttribute('data-leave-demo')||b.hasAttribute('data-print')||b.hasAttribute('data-copy')||b.hasAttribute('data-download');
        if(!allowed)b.disabled=true;
      });
    }else if(view==='overview')$('#content').insertAdjacentHTML('afterbegin','<section class="demo-banner demo-launch"><div><strong>Explore a complete example</strong><p>Explore 20 fictional records in total in a separate demo profile.</p></div><button class="secondary" data-open-demo>Explore examples</button></section>');
    KindredTheme.apply();
  };
  document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-open-demo')){selectProfile(demo.id);render();}if(b.hasAttribute('data-leave-demo')){selectProfile(familyData.profiles[0].id);render();}});
  render();
})();
