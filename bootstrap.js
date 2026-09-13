(async()=>{
 document.body.inert=true;
 try{
  await KindredStorage.ready;
  KindredTheme.set(localStorage.getItem('kindred-theme')||'system');
  for(const name of ['care-core.js','enhancements-core.js','premium-core.js','app.js','family.js','enhancements.js','examples-data.js','examples.js','mobile.js','design.js','premium.js','guide-data.js','guide.js'])await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=name;script.onload=resolve;script.onerror=()=>reject(Error('Could not load '+name+'. Reload this page.'));document.body.append(script);});
  await KindredStorage.flush();
 }catch(error){const box=document.createElement('section');box.className='card';const title=document.createElement('h2');title.textContent='Kindred could not open your saved data';const message=document.createElement('p');message.textContent=error.message;box.append(title,message);document.querySelector('#content').replaceChildren(box);}finally{document.body.inert=false;window.kindredBooted=true;}
})();
window.addEventListener('kindred-storage-error',event=>{let box=document.querySelector('#storageFailure');if(!box){box=document.createElement('div');box.id='storageFailure';box.className='conflict-banner';box.setAttribute('role','alert');document.querySelector('.page').prepend(box);}box.textContent=event.detail+' Keep this tab open and download a backup before closing it.';});

window.addEventListener('kindred-storage-saved',()=>document.querySelector('#storageFailure')?.remove());
