function toast(message,type="info",duration=6000){
const box=document.createElement("div"),icon=document.createElement("span"),text=document.createElement("span"),close=document.createElement("button"),progress=document.createElement("i");
box.className=`toast toast-${type}`;box.setAttribute("role",type==="error"?"alert":"status");
icon.className="toast-icon";icon.setAttribute("aria-hidden","true");icon.textContent={error:"!",success:"✓",info:"i"}[type]||"i";
text.className="toast-message";text.textContent=message;
close.className="toast-close";close.type="button";close.setAttribute("aria-label","Cerrar notificación");close.textContent="×";
box.append(icon,text,close);
if(duration>0){progress.className="toast-progress";progress.style.setProperty("--toast-duration",`${duration}ms`);box.append(progress)}
document.querySelector("#toasts").append(box);
let timer;if(duration>0)timer=setTimeout(dismiss,duration);
close.onclick=dismiss;
function dismiss(){clearTimeout(timer);box.classList.add("toast-leaving");box.addEventListener("animationend",()=>box.remove(),{once:true});setTimeout(()=>box.remove(),250)}
return{dismiss}
}
