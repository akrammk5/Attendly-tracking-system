(function(){
  'use strict';
  var toggle=document.querySelector('[data-toggle-sidebar]');
  var side=document.getElementById('sidebar');
  var scrim=document.querySelector('[data-sidebar-scrim]');
  var lastFocus=null;
  function closeNav(restoreFocus){
    if(!side||!toggle)return;
    side.classList.remove('is-open');
    if(scrim)scrim.classList.remove('is-visible');
    toggle.setAttribute('aria-expanded','false');
    document.body.classList.remove('nav-open');
    if(restoreFocus)toggle.focus();
  }
  function openNav(){
    if(!side||!toggle)return;
    lastFocus=document.activeElement;
    side.classList.add('is-open');
    if(scrim)scrim.classList.add('is-visible');
    toggle.setAttribute('aria-expanded','true');
    document.body.classList.add('nav-open');
    var target=side.querySelector('a, button');
    if(target)target.focus();
  }
  if(toggle&&side){
    toggle.addEventListener('click',function(){if(side.classList.contains('is-open'))closeNav(true);else openNav();});
    if(scrim)scrim.addEventListener('click',function(){closeNav(true);});
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&side.classList.contains('is-open')){e.preventDefault();closeNav(true);}
      if(e.key==='Tab'&&side.classList.contains('is-open')){
        var els=Array.prototype.slice.call(side.querySelectorAll('a[href],button:not([disabled]),input:not([disabled])')).filter(function(el){return el.getClientRects().length>0;});
        if(!els.length)return;
        var first=els[0],last=els[els.length-1];
        if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
        if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
      }
    });
    var mq=window.matchMedia('(min-width: 921px)');
    function onResize(){if(mq.matches)closeNav(false);}
    if(mq.addEventListener)mq.addEventListener('change',onResize);else mq.addListener(onResize);
  }
  var clock=document.querySelector('[data-local-clock]');
  if(clock){
    var format=new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    var tick=function(){clock.textContent=format.format(new Date());};
    tick();
    window.setInterval(tick,1000);
  }
  document.querySelectorAll('.clock-form').forEach(function(form){
    var submitted=false;
    form.addEventListener('submit',function(e){
      if(submitted){e.preventDefault();return;}
      submitted=true;
      var button=e.submitter;
      if(button){
        button.setAttribute('aria-busy','true');
        button.classList.add('is-submitting');
      }
    });
  });
})();