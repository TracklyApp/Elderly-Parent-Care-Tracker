/* Static access screen. The expected code is never shipped in plain text. */
window.KindredActivation=(function(){
 const expected='f99773655f200b4b3b93feaf392851c2d112be6e668d9aa719067b8cbaeda933',key='kindred-activation-v1';
 const isActivated=()=>localStorage.getItem(key)===expected;
 async function requireActivation(){
  if(isActivated()||document.querySelector('#activationGate'))return;
  const opener=document.activeElement;
  const gate=document.createElement('dialog');gate.id='activationGate';gate.setAttribute('aria-labelledby','activationTitle');gate.innerHTML='<form class="activation-card"><div class="eyebrow">KINDRED / YOUR FAMILY CARE SPACE</div><h1 id="activationTitle">Make this care space yours</h1><p>Activate to create profiles and save your own care records. Enter the code from the PDF included with your Etsy purchase.</p><label for="activationCode">Activation code<input id="activationCode" type="password" autocomplete="off" autocapitalize="characters" spellcheck="false" required maxlength="80" placeholder="Enter your purchase code"></label><label class="checkbox"><input id="showActivationCode" type="checkbox">Show the code I entered</label><div id="activationError" class="form-error" role="alert"></div><button type="submit" class="primary">Activate app</button><button type="button" class="secondary" data-cancel-activation>Continue exploring demo</button><small>Activation is remembered in this browser. Keep your PDF for another device or after clearing browser data.</small><details><summary>Where is my code?</summary><p>Open the access PDF from your Etsy order. If you need help, contact the seller through Etsy.</p></details></form>';
  document.body.append(gate);gate.showModal();
  const form=gate.querySelector('form'),input=gate.querySelector('#activationCode'),button=form.querySelector('[type=submit]'),error=gate.querySelector('#activationError');
  gate.querySelector('#showActivationCode').onchange=e=>input.type=e.target.checked?'text':'password';input.focus();
  gate.addEventListener('close',()=>{gate.remove();opener?.focus();});
  gate.querySelector('[data-cancel-activation]').onclick=()=>gate.close();
  form.onsubmit=async event=>{event.preventDefault();button.disabled=true;error.textContent='';try{
   if(!crypto.subtle)throw Error('Open the app at its HTTPS address, or through the local launcher, to activate.');
   const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input.value.trim().toUpperCase()));const actual=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
   if(actual!==expected){error.textContent='That code does not match. Check the code in your Etsy PDF and try again.';input.focus();return;}
   // A previously selected demo must not keep a buyer in read-only mode after activation.
   const selections=['kindred-active-local'];
   try{const last=JSON.parse(localStorage.getItem('kindred-last-account'));if(last?.id)selections.push('kindred-active-'+last.id);}catch{}
   for(const selection of selections)if(localStorage.getItem(selection)==='kindred-demo-profile')localStorage.removeItem(selection);
   localStorage.setItem(key,expected);try{await KindredStorage.flush();}catch(e){localStorage.removeItem(key);throw e;}
   input.value='';location.reload();
  }catch(e){error.textContent=e.message;}finally{button.disabled=false;}};
 }
 function install(){
  if(isActivated())return;
  const previousRender=render;
  render=function(){activeProfileId=KindredExamples.id;previousRender();const picker=document.querySelector('#profilePicker');picker.innerHTML='<option value="kindred-demo-profile">Demo - Eleanor Brooks</option><option value="activate">Activate my care space...</option>';document.querySelector('#syncStatus').textContent='Demo trial: '+KindredDemo.added()+'/20 added';};
  document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;if(button.matches('[data-activate-app],[data-leave-demo]')||['family','history','settings'].includes(button.dataset.view)){event.preventDefault();event.stopImmediatePropagation();void requireActivation();}},true);
  document.addEventListener('change',event=>{if((event.target.id==='profilePicker'&&event.target.value!==KindredExamples.id)||(['mobileNavigation'].includes(event.target.id)&&['family','history','settings'].includes(event.target.value))){event.preventDefault();event.stopImmediatePropagation();render();void requireActivation();}},true);
  render();
 }
 return {require:requireActivation,isActivated,install};
})();
