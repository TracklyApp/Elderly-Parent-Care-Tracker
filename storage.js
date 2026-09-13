/* Transparent, lossless compaction when Kindred's localStorage quota is reached. */
(function(root){
 const prefix='KINDRED-LZW1:';
 function pack(text){const bytes=new TextEncoder().encode(text),dict=new Map(),codes=[];let next=256,word='';
  for(const byte of bytes){const ch=String.fromCharCode(byte),combined=word+ch;if(dict.has(combined)||combined.length===1){word=combined;continue;}codes.push(word.length===1?word.charCodeAt(0):dict.get(word));if(next<65535)dict.set(combined,next++);word=ch;}
  if(word)codes.push(word.length===1?word.charCodeAt(0):dict.get(word));let binary='';for(const code of codes)binary+=String.fromCharCode(code>>8,code&255);return prefix+btoa(binary);
 }
 function unpack(text){if(!text?.startsWith(prefix))return text;const raw=atob(text.slice(prefix.length));if(raw.length%2)throw Error('Invalid compacted Kindred data.');const dict=[];for(let i=0;i<256;i++)dict[i]=String.fromCharCode(i);let next=256,previous='',size=0;const parts=[];
  for(let i=0;i<raw.length;i+=2){const code=raw.charCodeAt(i)*256+raw.charCodeAt(i+1),word=dict[code]??(code===next&&previous?previous+previous[0]:null);if(word===null)throw Error('Invalid compacted Kindred data.');size+=word.length;if(size>30000000)throw Error('Compacted Kindred data is too large.');parts.push(word);if(previous&&next<65535)dict[next++]=previous+word[0];previous=word;}
  return new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(parts.join(''),c=>c.charCodeAt(0)));
 }
 root.KindredStorage={pack,unpack};
 if(typeof Storage==='undefined')return;
 const get=Storage.prototype.getItem,set=Storage.prototype.setItem,isOurs=key=>String(key).startsWith('kindred-');
 Storage.prototype.getItem=function(key){const value=get.call(this,key);return isOurs(key)?unpack(value):value;};
 Storage.prototype.setItem=function(key,value){
  if(!isOurs(key))return set.call(this,key,value);const text=String(value);
  try{return set.call(this,key,text);}catch(error){
   if(!['QuotaExceededError','NS_ERROR_DOM_QUOTA_REACHED'].includes(error.name))throw error;
   // Replace only with a verified smaller representation. Never remove any key.
   for(let i=0;i<this.length;i++){const k=this.key(i);if(!isOurs(k))continue;const raw=get.call(this,k);if(!raw||raw.startsWith(prefix))continue;
    try{const compact=pack(raw);if(compact.length<raw.length&&unpack(compact)===raw)set.call(this,k,compact);}catch{/* Keep the original value intact if compaction fails. */}
   }
   const compact=pack(text),candidate=compact.length<text.length&&unpack(compact)===text?compact:text;return set.call(this,key,candidate);
  }
 };
})(globalThis);
