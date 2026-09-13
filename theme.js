/* Apply the saved appearance before the page paints. */
(function(){
  const media=matchMedia('(prefers-color-scheme: dark)');
  let preference='system';
  try{const saved=localStorage.getItem('kindred-theme');if(['light','dark','system'].includes(saved))preference=saved;}catch{}
  function apply(){
    const dark=preference==='dark'||(preference==='system'&&media.matches);
    document.documentElement.dataset.theme=dark?'dark':'light';
    document.documentElement.style.colorScheme=dark?'dark':'light';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',dark?'#14211c':'#34765b');
    const toggle=document.querySelector('#themeToggle');
    if(toggle){toggle.textContent=dark?'☀ Light':'☾ Dark';toggle.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');toggle.setAttribute('aria-pressed',String(dark));}
    const select=document.querySelector('#themePreference');if(select)select.value=preference;
  }
  window.KindredTheme={get preference(){return preference;},set(value){if(!['light','dark','system'].includes(value))return;preference=value;try{localStorage.setItem('kindred-theme',value);}catch{}apply();},apply};
  media.addEventListener('change',()=>{if(preference==='system')apply();});
  document.addEventListener('DOMContentLoaded',apply);
  document.addEventListener('click',event=>{if(event.target.closest('#themeToggle'))window.KindredTheme.set(document.documentElement.dataset.theme==='dark'?'light':'dark');});
  document.addEventListener('change',event=>{if(event.target.id==='themePreference')window.KindredTheme.set(event.target.value);});
  apply();
})();
