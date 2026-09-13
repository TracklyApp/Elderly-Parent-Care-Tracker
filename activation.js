/* Static access screen. The expected code is never shipped in plain text. */
window.KindredActivation=(function(){
 const expected='f99773655f200b4b3b93feaf392851c2d112be6e668d9aa719067b8cbaeda933',key='kindred-activation-v1';
 async function requireActivation(){
  if(localStorage.getItem(key)===expected){document.body.classList.remove('activation-pending');return;}
  const gate=document.createElement('section');gate.id='activationGate';gate.innerHTML='<form class="activation-card"><div class="eyebrow">KINDRED / YOUR FAMILY CARE SPACE</div><h1>Activate your care space</h1><p>Enter the activation code from the PDF included with your Etsy purchase.</p><label for="activationCode">Activation code<input id="activationCode" type="password" autocomplete="off" autocapitalize="characters" spellcheck="false" required maxlength="80" placeholder="Enter your purchase code"></label><label class="checkbox"><input id="showActivationCode" type="checkbox">Show the code I entered</label><div id="activationError" class="form-error" role="alert"></div><button type="submit" class="primary">Activate app</button><small>Activation is remembered in this browser. You may need the code again on another device or after clearing browser data.</small><details><summary>Where is my code?</summary><p>Open the access PDF from your Etsy order. If you need help, contact the seller through Etsy. The correct code is not displayed in this app.</p></details></form>';
  document.body.append(gate);document.body.inert=false;
  const form=gate.querySelector('form'),input=gate.querySelector('#activationCode'),button=form.querySelector('[type=submit]'),error=gate.querySelector('#activationError');
  gate.querySelector('#showActivationCode').onchange=e=>input.type=e.target.checked?'text':'password';input.focus();
  return new Promise(resolve=>{form.onsubmit=async event=>{event.preventDefault();button.disabled=true;error.textContent='';try{
   if(!crypto.subtle)throw Error('Open the app at its HTTPS address, or through the local launcher, to activate.');
   const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input.value.trim().toUpperCase()));const actual=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
   if(actual!==expected){error.textContent='That code does not match. Check the code in your Etsy PDF and try again.';input.focus();return;}
   localStorage.setItem(key,expected);try{await KindredStorage.flush();}catch(e){localStorage.removeItem(key);throw e;}
   input.value='';document.body.inert=true;gate.remove();document.body.classList.remove('activation-pending');resolve();
  }catch(e){error.textContent=e.message;}finally{button.disabled=false;}};});
 }
 return {require:requireActivation};
})();
