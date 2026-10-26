/* Verified dragon Live2D controller. Local assets, one model, shared host ticker. */
(() => {
 'use strict';
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
 const reactions={nod:{group:'ReactionNod',duration:2.6},curious:{group:'ReactionCurious',duration:3.4},chuckle:{group:'ReactionChuckle',duration:3}};
 const names={'呆呆眼':'thinking','开心兴奋':'working','感叹号':'waiting','方眼镜':'review','流汗':'syncing','生气':'blocked','哭':'error','爱心眼':'done','悲伤':'interrupted','脸红':'blush','星星眼':'star','调皮':'playful','吐舌':'tongue','心跳':'heartbeat','圆眼镜':'round','阴暗':'gloom'};
 const DEFAULT_TAIL_GAIN=1.8;
 let generation=0;
 async function create(){
  const base='appearances/dragon-live/';
  const read=async file=>{const r=await fetch(base+file);if(!r.ok)throw Error('Dragon asset unavailable: '+file);return r.json();};
  const [spec,catalog,rigMap]=await Promise.all([read('dragon.states.model3.json'),read('catalog.json'),read('rig-map.json')]);
  const token=++generation;spec.url=base+'dragon.states.model3.json';
  // Destroying a superseded load must never destroy another instance's atlases.
  spec.FileReferences.Textures=spec.FileReferences.Textures.map(file=>file+'?dragonInstance='+token);
  const m=await PIXI.live2d.Live2DModel.from(spec,{autoInteract:false});
  let disposed=false;
  try{
  const im=m.internalModel,manager=im.motionManager,nativeMotion=m.motion.bind(m),nativeDestroy=m.destroy.bind(m);
  const styles={normal:{eye:1,mouth:0,browL:0,browR:0,gazeX:0,gazeY:0,gazeWeight:0,z:0,open:0,width:0,round:0,cheek:0,corner:0}};
  const artFlags=Object.keys(catalog.find(e=>e.id==='idle').values).filter(id=>id.startsWith('ParamArt')||id.startsWith('ParamRefine'));
  Object.assign(styles.normal,{eyeL:1,eyeR:1,browAngleL:0,browAngleR:0,browFormL:0,browFormR:0});
  for(const id of artFlags)styles.normal[id]=0;
  for(const e of catalog){if(e.type!=='expression')continue;const v=e.values;styles[e.id]={...styles.normal,eyeL:v.ParamEyeLOpen,eyeR:v.ParamEyeROpen,mouth:v.ParamMouthForm,open:v.ParamMouthOpenY,width:v.ParamMouthWidth,round:v.ParamMouthRound,browL:v.ParamBrowLY,browR:v.ParamBrowRY,browAngleL:v.ParamBrowLAngle,browAngleR:v.ParamBrowRAngle,browFormL:v.ParamBrowLForm,browFormR:v.ParamBrowRForm,cheek:v.ParamCheekRaiseL,corner:v.ParamMouthCornerL,gazeX:v.ParamEyeBallX,gazeY:v.ParamEyeBallY,gazeWeight:(v.ParamEyeBallX||v.ParamEyeBallY)?0.45:0,z:v.ParamAngleZ,...Object.fromEntries(artFlags.map(id=>[id,v[id]||0]))};}
  let status='idle',expression='idle',reaction=null,reactionAt=0,time=0,blinkAt=-100,patAt=-100,mouthAt=-100;
  let animated=true,tailGain=DEFAULT_TAIL_GAIN,gazeFollow=true,aim=null,lastPose={},cfg={},frames=0;
  const style={...styles.idle},gaze={x:0,y:0};
  function blinkValue(t){return t<0||t>.34?1:t<.09?1-smooth(t/.09):t<.15?0:smooth((t-.15)/.19);}
  function cancelReaction(){if(reaction){reaction=null;if(animated)nativeMotion('Idle',0,3).catch(console.warn);}}
  function select(id){if(!styles[id])return false;cancelReaction();expression=id;return true;}
  async function playReaction(id){
   if(!animated||!reactions[id]||disposed)return false;
   const r=reactions[id];reaction=id;reactionAt=time;patAt=mouthAt=-100;
   try{await nativeMotion(r.group,0,3);return true;}catch(error){reaction=null;throw error;}
  }
  const update=im.update.bind(im);
  im.update=(dt,now)=>{
   if(disposed)return;
   const elapsed=Math.min(50,Math.max(0,dt));
   if(animated)time+=elapsed/1000;
   if(reaction&&time-reactionAt>=reactions[reaction].duration){reaction=null;nativeMotion('Idle',0,3).catch(console.warn);}
   const target=styles[expression]||styles.idle,k=1-Math.exp(-elapsed/180);
   for(const key of Object.keys(style))style[key]+=(target[key]-style[key])*k;
   update(elapsed,now);frames++;
  };
  const afterMotion=()=>{
  const c=m.internalModel.coreModel;
  if(!animated){for(const id of ['ParamAngleX','ParamAngleY','ParamAngleZ'])c.setParameterValueById(id,0);c.setParameterValueById('ParamEyeLOpen',1);c.setParameterValueById('ParamEyeROpen',1);}
  const authoredFace=reaction?Object.fromEntries(['ParamMouthForm','ParamMouthOpenY','ParamMouthWidth','ParamMouthRound','ParamJawDrop','ParamMouthCornerL','ParamMouthCornerR','ParamCheekRaiseL','ParamCheekRaiseR','ParamBrowLY','ParamBrowRY','ParamBrowLAngle','ParamBrowRAngle','ParamBrowLForm','ParamBrowRForm','ParamTongueHeight','ParamTongueWidth'].map(id=>[id,c.getParameterValueById(id)])):null;
  const face=(id,fallback)=>authoredFace?authoredFace[id]:fallback;
  const pat=time-patAt,nod=pat<0||pat>1.7?0:pat<.5?smooth(pat/.5):pat<.9?1:1-smooth((pat-.9)/.8);
  c.setParameterValueById('ParamAngleY',c.getParameterValueById('ParamAngleY')+nod*8);
  c.setParameterValueById('ParamAngleZ',c.getParameterValueById('ParamAngleZ')+style.z);
  const close=Math.min(blinkValue(time-blinkAt),nod>.1?1-smooth(nod*2):1);
  for(const id of ['ParamEyeLOpen','ParamEyeROpen'])c.setParameterValueById(id,Math.min(c.getParameterValueById(id),(id==='ParamEyeLOpen'?style.eyeL:style.eyeR),close));
  let gx=aim&&gazeFollow?aim.x:c.getParameterValueById('ParamEyeBallX'),gy=aim&&gazeFollow?aim.y:c.getParameterValueById('ParamEyeBallY');
  gx=gx*(1-style.gazeWeight)+style.gazeX*style.gazeWeight;gy=gy*(1-style.gazeWeight)+style.gazeY*style.gazeWeight;
  gaze.x+=(gx-gaze.x)*.18;gaze.y+=(gy-gaze.y)*.18;
  c.setParameterValueById('ParamEyeBallX',clamp(gaze.x,-.8,.8));c.setParameterValueById('ParamEyeBallY',clamp(gaze.y,-.6,.6));
  c.setParameterValueById('ParamBrowLY',face('ParamBrowLY',style.browL));c.setParameterValueById('ParamBrowRY',face('ParamBrowRY',style.browR));c.setParameterValueById('ParamMouthForm',face('ParamMouthForm',clamp(style.mouth+nod*.25,-1,1)));
  c.setParameterValueById('ParamBrowLAngle',face('ParamBrowLAngle',style.browAngleL));c.setParameterValueById('ParamBrowRAngle',face('ParamBrowRAngle',style.browAngleR));
  c.setParameterValueById('ParamBrowLForm',face('ParamBrowLForm',style.browFormL));c.setParameterValueById('ParamBrowRForm',face('ParamBrowRForm',style.browFormR));

  const mouthT=time-mouthAt;
  const pulse=(a,b)=>mouthT<a||mouthT>b?0:Math.sin((mouthT-a)/(b-a)*Math.PI)**2;
  const demo=.62*pulse(0,1.1)+.4*pulse(1.2,2.4);
  const opening=clamp(face('ParamMouthOpenY',style.open)+demo+nod*.08,0,.85);
  c.setParameterValueById('ParamMouthOpenY',opening);
  c.setParameterValueById('ParamMouthWidth',clamp(face('ParamMouthWidth',style.width)+.025*Math.sin(time*1.4),-.6,.6));
  c.setParameterValueById('ParamMouthRound',face('ParamMouthRound',style.round));
  c.setParameterValueById('ParamJawDrop',face('ParamJawDrop',opening*.65));
  c.setParameterValueById('ParamJawShift',clamp(c.getParameterValueById('ParamAngleX')/45,-1,1)*.12);
  c.setParameterValueById('ParamMouthCornerL',face('ParamMouthCornerL',style.corner));
  c.setParameterValueById('ParamMouthCornerR',face('ParamMouthCornerR',style.corner*.85));
  c.setParameterValueById('ParamCheekRaiseL',face('ParamCheekRaiseL',style.cheek));
  c.setParameterValueById('ParamCheekRaiseR',face('ParamCheekRaiseR',style.cheek));
  c.setParameterValueById('ParamTongueHeight',face('ParamTongueHeight',style.open*.3));c.setParameterValueById('ParamTongueWidth',face('ParamTongueWidth',style.open*.4));
  c.setParameterValueById('ParamNeckFollow',clamp(c.getParameterValueById('ParamAngleX')/45,-1,1));
  for(const id of artFlags)c.setParameterValueById(id,style[id]);
  for(const id of ['ParamBodyAngleX','ParamBodyAngleY','ParamBodyAngleZ','ParamBreath'])c.setParameterValueById(id,0);
  };
  const beforeModel=()=>{
  const c=m.internalModel.coreModel;
  c.setParameterValueById('ParamFacePitch',clamp(c.getParameterValueById('ParamAngleY')/30,-1,1));
  for(const id of ['ParamTailBase','ParamTailMid','ParamTailTip'])c.setParameterValueById(id,animated?clamp(c.getParameterValueById(id)*tailGain,-.9,.9):0);
  for(const id of ['ParamBowSway','ParamLockLeft','ParamLockRight','ParamAhoge','ParamHairFront','ParamHairBack'])if(!animated)c.setParameterValueById(id,0);
  lastPose=Object.fromEntries(['ParamAngleX','ParamAngleY','ParamFacePitch','ParamAngleZ','ParamBrowLAngle','ParamBrowRAngle','ParamTongueHeight','ParamEyeLOpen','ParamEyeROpen','ParamEyeBallX','ParamEyeBallY','ParamMouthForm','ParamMouthOpenY','ParamJawDrop','ParamNeckFollow','ParamTailBase','ParamTailMid','ParamTailTip','ParamBowSway','ParamAhoge',...artFlags].map(id=>[id,c.getParameterValueById(id)]));
  };
  im.on('afterMotionUpdate',afterMotion);im.on('beforeModelUpdate',beforeModel);
  m.appearanceId='dragon';m.rendererKind='live2d';
  m.expression=async name=>select(names[name]||status);
  m.setStatus=async key=>{status=styles[key]?key:'idle';select(status);};
  m.supportsExpression=name=>Object.hasOwn(names,name);
  manager.expressionManager.definitions=Object.keys(names).map(name=>({name}));
  manager.expressionManager.resetExpression=()=>select(status);
  m.configure=options=>{
   cfg=options||{};const was=animated;animated=cfg.autoMotion!==false;
   tailGain=DEFAULT_TAIL_GAIN;gazeFollow=Number(cfg.gazeRange??320)>0;
   if(!animated){reaction=null;blinkAt=patAt=mouthAt=-100;manager.stopAllMotions();}
   else if(!was)nativeMotion('Idle',0,3).catch(console.warn);
  };
  m.setPointer=data=>{
   const range=Number(cfg.gazeRange??320),cx=m.x+m.width/2,cy=m.y+m.height*.43;
   aim=data&&Number.isFinite(data.x)&&Number.isFinite(data.y)&&range>0&&Math.hypot(data.x-cx,data.y-cy)<=range
    ?{x:clamp((data.x-cx)/(m.width*.35),-.8,.8),y:clamp(-(data.y-cy)/(m.height*.35),-.6,.6)}:null;
  };
  m.playInteraction=kind=>{
   if(!animated)return true;
   if(kind==='pat'){cancelReaction();patAt=time;return true;}
   if(kind==='drag'){blinkAt=time;return true;}
   const id=kind==='poke'?'curious':kind==='drop'?'chuckle':'nod';
   playReaction(id).catch(console.warn);return true;
  };
  m.motion=(group,index,priority)=>{
   if(!animated)return Promise.resolve(false);
   if(group==='Tap')return playReaction('nod');
   if(group==='Show')return playReaction('chuckle');
   if(Object.values(reactions).some(r=>r.group===group))return playReaction(Object.keys(reactions).find(id=>reactions[id].group===group));
   return nativeMotion(group,index,priority);
  };
  m.getAnimationStatus=()=>({renderer:'live2d',tailGain,expression,status,reaction,frames,animated,lastPose,parameters:im.coreModel._model.parameters.count,drawables:im.coreModel._model.drawables.count});
  m.rigMap=rigMap;
  m.destroy=(options)=>{
   if(disposed)return;disposed=true;manager.stopAllMotions();
   im.removeListener('afterMotionUpdate',afterMotion);im.removeListener('beforeModelUpdate',beforeModel);
   nativeDestroy(options||{children:true,texture:true,baseTexture:true});
  };
  const loaded=await Promise.all(Object.values(reactions).map(r=>manager.loadMotion(r.group,0)));
  if(loaded.some(x=>!x))throw Error('Dragon reaction motion missing');
  await nativeMotion('Idle',0,3);
  return m;
  }catch(error){m.destroy({children:true,texture:true,baseTexture:true});throw error;}
 }
 window.PetDragonLive={create,DEFAULT_TAIL_GAIN};
})();
