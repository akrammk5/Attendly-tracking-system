(function(){
  'use strict';
  var toggle=document.querySelector('[data-toggle-sidebar]');
  var side=document.getElementById('sidebar');
  if(toggle&&side){
    toggle.addEventListener('click',function(){var open=side.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(open));});
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&side.classList.contains('is-open')){side.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');toggle.focus();}});
    document.addEventListener('click',function(e){if(!side.contains(e.target)&&!toggle.contains(e.target)){side.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');}});
  }
  var clock=document.querySelector('[data-local-clock]');
  if(clock){
    var tick=function(){clock.textContent=new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());};
    tick();window.setInterval(tick,1000);
  }
  document.querySelectorAll('.clock-form').forEach(function(form){
    form.addEventListener('submit',function(){form.querySelectorAll('button[type=submit]').forEach(function(button){button.setAttribute('aria-disabled','true');});});
  });
})();