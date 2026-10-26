"use strict";
(() => {
  const bubble=document.getElementById("bubble"),source=document.getElementById("source"),amount=document.getElementById("amount"),meta=document.getElementById("meta");
  const bridge=window.chrome&&window.chrome.webview;
  const send=action=>{if(bridge)bridge.postMessage({action});};
  const bounded=(value,max)=>typeof value==="string"?value.slice(0,max):"";
  if(bridge)bridge.addEventListener("message",event=>{
    const message=event.data;
    if(!message||message.t!=="metric"||!message.data)return;
    const data=message.data;
    source.textContent=bounded(data.source,40);amount.textContent=bounded(data.amount,256);meta.textContent=bounded(data.meta,160);
    const status=["normal","low","loading","stale","unavailable","off"].includes(data.status)?data.status:"unavailable";
    bubble.dataset.status=status;
    bubble.dataset.level=["green","yellow","red"].includes(data.level)?data.level:"unknown";
    bubble.title=bounded(data.detail,4096)||[source.textContent,amount.textContent,meta.textContent].join("\n");
    bubble.setAttribute("aria-label",[source.textContent,amount.textContent,meta.textContent].join("，"));
  });
  document.getElementById("more").addEventListener("click",()=>send("more"));
  document.getElementById("close").addEventListener("click",()=>send("close"));
  bubble.addEventListener("contextmenu",event=>{event.preventDefault();send("more");});
  bubble.addEventListener("pointerdown",event=>{if(event.button===0&&!event.target.closest("button"))send("drag");});
  bubble.addEventListener("keydown",event=>{if(event.key==="Escape"){event.preventDefault();send("close");}});
  // A missing stylesheet must not falsely acknowledge a healthy rendered page.
  if(getComputedStyle(document.documentElement).getPropertyValue("--metric-surface").trim()==="ready")send("ready");
})();
