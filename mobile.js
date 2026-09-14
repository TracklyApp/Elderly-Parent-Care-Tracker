/* Responsive navigation and platform-aware installation help. */
(()=>{
  const sidebar=$('.sidebar'),brand=sidebar.querySelector('.brand'),menu=document.createElement('div'),toggle=document.createElement('button');
  menu.id='mobileMenuPanel';toggle.id='mobileMenuToggle';toggle.type='button';toggle.setAttribute('aria-controls',menu.id);toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-label','Open navigation menu');toggle.innerHTML='<span></span><span></span><span></span>';
  for(const child of [...sidebar.children])if(child!==brand)menu.append(child);
  sidebar.append(toggle,menu);
  const phone=matchMedia('(max-width:700px)');
  function closeMenu(focus=false){sidebar.classList.remove('mobile-menu-open');toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-label','Open navigation menu');if(focus&&phone.matches)toggle.focus();}
  toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';sidebar.classList.toggle('mobile-menu-open',open);toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Close navigation menu':'Open navigation menu');});
  document.addEventListener('click',event=>{if(!phone.matches)return;if(!sidebar.contains(event.target)){closeMenu();return;}if(menu.contains(event.target)&&event.target.closest('[data-view]'))closeMenu(true);},true);
  document.addEventListener('change',event=>{if(phone.matches&&menu.contains(event.target)&&['journalNavigation','mobileNavigation','profilePicker'].includes(event.target.id))closeMenu(true);},true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&toggle.getAttribute('aria-expanded')==='true'){event.preventDefault();closeMenu(true);}});
  phone.addEventListener('change',()=>closeMenu());
  const previousNav=nav;
  nav=function(){
    previousNav();
    const links=[...$('#navigation').querySelectorAll('button[data-view]')].map(b=>[b.dataset.view,b.textContent.replace(b.querySelector('.nav-icon')?.textContent||'','').trim()]);
    const option=([id,title])=>`<option value="${esc(id)}" ${view===id?'selected':''}>${esc(title)}</option>`;
    $('#navigation').insertAdjacentHTML('afterbegin',`<label class="mobile-navigation" for="mobileNavigation">Go to<select id="mobileNavigation"><optgroup label="Daily care">${links.slice(0,3).map(option).join('')}</optgroup><optgroup label="Care journal">${categories.map(option).join('')}</optgroup><optgroup label="Resources & settings">${links.slice(3).map(option).join('')}</optgroup></select></label>`);
  };
  document.addEventListener('change',event=>{
    if(event.target.id!=='mobileNavigation')return;
    view=event.target.value;render();$('#mobileNavigation').focus();
    if(['history','settings','documents'].includes(view))void loadPanels().catch(error=>toast(error.message));
  });
  const standalone=matchMedia('(display-mode: standalone)');
  function installed(){return standalone.matches||navigator.standalone===true;}
  function updateInstall(){const b=$('#installAppButton');b.textContent=installed()?'App installed':'Install app';b.setAttribute('aria-label',installed()?'App installation information':'Install Kindred app');}
  async function install(){
    if(installed()){openWorkflow('Kindred is installed','<p>You are using the app in its own window. Your saved records stay in this browser on this device.</p>',()=>{},'Done');return;}
    if(installPrompt){
      const prompt=installPrompt;installPrompt=null;
      await prompt.prompt();const choice=await prompt.userChoice;
      if(choice?.outcome==='dismissed')toast('Installation dismissed. You can try again from Install app.');
      return;
    }
    const file=location.protocol==='file:',local=['localhost','127.0.0.1','[::1]'].includes(location.hostname);
    let content=file?'<p>Open Kindred through its local launcher before installing.</p><ol><li>Open <strong>Start Kindred.cmd</strong> on your computer.</li><li>Open <strong>http://localhost:8877</strong> in Chrome or Edge on that computer.</li><li>Choose <strong>Install app</strong>, or use the browser’s installation menu.</li></ol>':'';
    if(!file)content+='<p>If your browser offers installation, use its Install app or Add to Home Screen command.</p><ul><li><strong>Android:</strong> in Chrome, open the browser menu and choose Install app or Add to Home screen when available.</li><li><strong>iPhone / iPad:</strong> in Safari, open Share and choose Add to Home Screen. Enable Open as Web App if offered, then tap Add.</li><li><strong>Computer:</strong> use the install icon in the address bar or the browser’s app menu.</li></ul>';
    if(file||local)content+='<p><strong>Using another device?</strong> This copy runs only on this computer. The localhost address does not connect a phone or tablet to your computer. Mobile installation needs an HTTPS address reachable from that device. No such address is configured for this local copy.</p>';
    else if(!isSecureContext)content+='<p>Installation requires an HTTPS address. This connection does not support app installation.</p>';
    content+='<p class="note">Offline pages become available after the first successful load. Family synchronization and server features require the local server connection.</p>';
    openWorkflow('Install Kindred',content,()=>{},'Done');
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-install-app]');if(!button)return;
    event.preventDefault();event.stopImmediatePropagation();void install().catch(error=>toast(error.message));
  },true);
  window.addEventListener('appinstalled',()=>{installPrompt=null;updateInstall();toast('Kindred installed.');});
  standalone.addEventListener('change',updateInstall);
  updateInstall();render();
})();
