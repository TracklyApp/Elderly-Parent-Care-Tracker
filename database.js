/* Awaited IndexedDB persistence; keeps original localStorage data as a migration copy. */
(function(root){
 const get=Storage.prototype.getItem,set=Storage.prototype.setItem,remove=Storage.prototype.removeItem,clear=Storage.prototype.clear;
 const data=new Map(),dirty=new Map();let db,active=false,inFlight=null;
 const ours=k=>String(k).startsWith('kindred-');
 function notify(error){root.dispatchEvent(new CustomEvent('kindred-storage-error',{detail:error.message}));}
 function flush(){
  if(inFlight)return inFlight.then(()=>dirty.size?flush():undefined);
  if(!dirty.size)return Promise.resolve();
  const batch=new Map(dirty);dirty.clear();
  inFlight=new Promise((resolve,reject)=>{
   const tx=db.transaction('records','readwrite'),store=tx.objectStore('records');
   for(const [key,value] of batch)value===null?store.delete(key):store.put({key,value});
   tx.oncomplete=()=>{if(!dirty.size)root.dispatchEvent(new Event('kindred-storage-saved'));resolve();};tx.onerror=()=>{};
   tx.onabort=()=>{for(const [key,value] of batch)if(!dirty.has(key))dirty.set(key,value);reject(Error('The browser could not save to the local database. Your form is still available. '+(tx.error?.message||'')));};
  }).catch(error=>{for(const [key,value] of batch)if(!dirty.has(key))dirty.set(key,value);throw error;}).finally(()=>{inFlight=null;});return inFlight;
 }
 function change(key,value){key=String(key);if(value===null)data.delete(key);else data.set(key,String(value));dirty.set(key,value===null?null:String(value));queueMicrotask(()=>flush().catch(notify));}
 Storage.prototype.getItem=function(key){return active&&this===localStorage&&ours(key)?data.get(String(key))??null:get.call(this,key);};
 Storage.prototype.setItem=function(key,value){if(active&&this===localStorage&&ours(key)){change(key,value);return;}return set.call(this,key,value);};
 Storage.prototype.removeItem=function(key){if(active&&this===localStorage&&ours(key)){change(key,null);return;}return remove.call(this,key);};
 Storage.prototype.clear=function(){if(active&&this===localStorage){for(const key of data.keys())change(key,null);}return clear.call(this);};
 KindredStorage.flush=flush;KindredStorage.backend=()=>active?'IndexedDB':'localStorage';
 KindredStorage.ready=new Promise((resolve,reject)=>{
  const request=indexedDB.open('kindred-care-storage',1);
  request.onupgradeneeded=()=>request.result.createObjectStore('records',{keyPath:'key'});
  request.onerror=()=>reject(Error('Cannot open the local care database. Allow site storage in this browser. Existing data has not been removed.'));
  request.onblocked=()=>reject(Error('Close other Kindred tabs and reload to open the local database.'));
  request.onsuccess=async()=>{db=request.result;db.onversionchange=()=>db.close();try{
   const rows=await new Promise((yes,no)=>{const r=db.transaction('records').objectStore('records').getAll();r.onsuccess=()=>yes(r.result);r.onerror=()=>no(r.error);});
   if(rows.some(r=>r.key==='__initialized')){for(const r of rows)if(ours(r.key))data.set(r.key,r.value);}
   else{
    for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(ours(key)){const value=get.call(localStorage,key);data.set(key,value);dirty.set(key,value);}}
    dirty.set('__initialized','1');await flush();
   }
   active=true;resolve();
  }catch(error){reject(error);}};
 });
 // Bootstrap observes initialization failures and displays recovery instructions.
 KindredStorage.ready.catch(()=>{});
 root.addEventListener('beforeunload',event=>{if(dirty.size||inFlight){event.preventDefault();event.returnValue='';}});
})(globalThis);
