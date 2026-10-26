/* PNG appearance adapter. Original assets and the Live2D model remain untouched. */
(() => {
  'use strict';
  const expressions = Object.freeze({
    '呆呆眼':'02-thinking.png', '开心兴奋':'03-working.png', '感叹号':'04-waiting.png',
    '方眼镜':'05-review-square.png', '流汗':'06-syncing.png', '生气':'07-blocked.png',
    '哭':'08-error.png', '爱心眼':'09-done-heart.png', '悲伤':'10-interrupted.png',
    '脸红':'11-blush.png', '星星眼':'12-star.png', '调皮':'13-playful.png',
    '吐舌':'14-tongue.png', '心跳':'15-heartbeat.png', '圆眼镜':'16-review-round.png', '阴暗':'17-gloom.png',
  });
  const states = Object.freeze({idle:'01-idle.png', thinking:'02-thinking.png', working:'03-working.png',
    waiting:'04-waiting.png', review:'05-review-square.png', syncing:'06-syncing.png',
    blocked:'07-blocked.png', error:'08-error.png', done:'09-done-heart.png', interrupted:'10-interrupted.png'});
  let instanceId=0;

  function softDisplayFilter() {
    // One small GPU pass: soften subpixel line transitions, retain the centre
    // alpha exactly, then compress RGB contrast. Source PNGs remain unchanged.
    const fragment = `
      precision highp float;
      varying vec2 vTextureCoord;
      uniform sampler2D uSampler;
      uniform vec4 inputSize;
      uniform vec4 inputClamp;
      uniform float uContrast;
      uniform float uSoftness;
      void main(void) {
        vec2 p=vTextureCoord;
        vec2 d=inputSize.zw*0.45;
        vec4 c=texture2D(uSampler,p);
        vec4 soft=c*0.4;
        soft+=texture2D(uSampler,clamp(p+vec2(d.x,0.0),inputClamp.xy,inputClamp.zw))*0.15;
        soft+=texture2D(uSampler,clamp(p-vec2(d.x,0.0),inputClamp.xy,inputClamp.zw))*0.15;
        soft+=texture2D(uSampler,clamp(p+vec2(0.0,d.y),inputClamp.xy,inputClamp.zw))*0.15;
        soft+=texture2D(uSampler,clamp(p-vec2(0.0,d.y),inputClamp.xy,inputClamp.zw))*0.15;
        vec3 rgb=c.rgb/max(c.a,0.0001);
        vec3 softRgb=soft.rgb/max(soft.a,0.0001);
        rgb=mix(rgb,softRgb,uSoftness);
        rgb=clamp((rgb-0.5)*uContrast+0.5,0.0,1.0);
        gl_FragColor=vec4(rgb*c.a,c.a);
      }`;
    const filter=new PIXI.Filter(undefined,fragment,{uContrast:0.94,uSoftness:0.28});
    filter.resolution=window.devicePixelRatio||1;
    filter.padding=0;
    return filter;
  }

  class Dragon extends PIXI.Sprite {
    constructor(texture, file, token) {
      super(texture);
      this.appearanceId='dragon';
      this._displayFilter=softDisplayFilter();
      this.filters=[this._displayFilter];
      this._token=token;
      this._textures=new Map([[file,texture]]);
      this._loads=new Map();
      this._serial=0; this._disposed=false; this._status='idle'; this._expression=null;
      this.internalModel={width:1317,height:1194,motionManager:{
        definitions:{}, _motions:[], isFinished:()=>true, stopAllMotions:()=>{},
        expressionManager:{definitions:Object.keys(expressions).map(name=>({name})),
          resetExpression:()=>this.expression(null)},
      }};
    }
    async _load(file) {
      if(this._textures.has(file))return this._textures.get(file);
      if(this._loads.has(file))return this._loads.get(file);
      const pending=PIXI.Texture.fromURL('appearances/dragon/'+file+'?pet='+this._token).then(texture=>{
        if(this._disposed){texture.destroy(true);return null;}
        this._textures.set(file,texture); return texture;
      }).finally(()=>this._loads.delete(file));
      this._loads.set(file,pending);return pending;
    }
    _trim() {
      for(const [file,texture] of this._textures){
        if(this._textures.size<=3)break;
        if(texture!==this.texture){this._textures.delete(file);texture.destroy(true);}
      }
    }
    async expression(name) {
      this._expression=expressions[name]?name:null;
      const file=expressions[name]||states[this._status]||states.idle;
      const serial=++this._serial;
      const texture=await this._load(file);
      if(!this._disposed&&serial===this._serial&&texture){this.texture=texture;}
      this._trim();
    }
    setStatus(key) {
      this._status=states[key]?key:'idle';
      return this.expression(null);
    }
    supportsExpression(name){return Object.hasOwn(expressions,name);}
    motion(){return false;}
    cachedTextureCount(){return this._textures.size;}
    destroy() {
      this._disposed=true; this._serial++;
      this.filters=null;
      super.destroy({texture:false,baseTexture:false});
      this._displayFilter.destroy();
      for(const texture of this._textures.values())texture.destroy(true);
      this._textures.clear();
    }
  }
  async function createDragonStatic() {
    const file=states.idle;
    // PIXI caches by URL. Give each adapter ownership of its textures so cancelling
    // an earlier load cannot destroy a later model's shared texture.
    const token=++instanceId;
    return new Dragon(await PIXI.Texture.fromURL('appearances/dragon/'+file+'?pet='+token),file,token);
  }
  async function createDragon() {
    return window.PetDragonLive ? PetDragonLive.create() : createDragonStatic();
  }
  class Switcher {
    constructor(load,onChange,onError){this.load=load;this.onChange=onChange;this.onError=onError;this.current=null;this.currentId=null;this.requested=null;this.serial=0;}
    async select(id){
      id=id==='dragon'?'dragon':'legacy';
      this.requested=id;
      const serial=++this.serial;
      if(this.currentId===id)return true;
      let next;
      try{
        next=await this.load(id);
        if(serial!==this.serial){next.destroy({children:true,texture:true,baseTexture:true});return false;}
        const old=this.current;
        this.onChange(next,id,old);
        this.current=next;this.currentId=id;
        if(old)old.destroy({children:true,texture:true,baseTexture:true});
        return true;
      }catch(error){
        if(next&&next!==this.current)next.destroy();
        if(serial===this.serial)this.onError(error,id);
        return false;
      }
    }
  }
  window.PetAppearance={createDragon,createDragonStatic,Switcher,expressions,states};
})();
