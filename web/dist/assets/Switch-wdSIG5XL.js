import{d as I,D as a,aU as ce,bM as ue,bB as he,Z as A,a0 as o,aH as L,X as T,$ as l,am as E,bN as K,aK as y,J as be,a4 as X,aG as fe,r as M,a6 as ve,aL as ge,bH as we,p as V,a9 as W,aN as x,bE as H,b7 as s,ab as me}from"./index-C01jxU0r.js";import{u as pe}from"./Popover-CLtsHgBo.js";const Re=I({props:{onFocus:Function,onBlur:Function},setup(e){return()=>a("div",{style:"width: 0; height: 0",tabindex:0,onFocus:e.onFocus,onBlur:e.onBlur})}});function ye(e){const{primaryColor:d,opacityDisabled:f,borderRadius:n,textColor3:v}=e;return Object.assign(Object.assign({},ue),{iconColor:v,textColor:"white",loadingColor:d,opacityDisabled:f,railColor:"rgba(0, 0, 0, .14)",railColorActive:d,buttonBoxShadow:"0 1px 4px 0 rgba(0, 0, 0, 0.3), inset 0 0 1px 0 rgba(0, 0, 0, 0.05)",buttonColor:"#FFF",railBorderRadiusSmall:n,railBorderRadiusMedium:n,railBorderRadiusLarge:n,buttonBorderRadiusSmall:n,buttonBorderRadiusMedium:n,buttonBorderRadiusLarge:n,boxShadowFocus:`0 0 0 2px ${he(d,{alpha:.2})}`})}const xe={common:ce,self:ye},ke=A("switch",`
 height: var(--n-height);
 min-width: var(--n-width);
 vertical-align: middle;
 user-select: none;
 -webkit-user-select: none;
 display: inline-flex;
 outline: none;
 justify-content: center;
 align-items: center;
`,[o("children-placeholder",`
 height: var(--n-rail-height);
 display: flex;
 flex-direction: column;
 overflow: hidden;
 pointer-events: none;
 visibility: hidden;
 `),o("rail-placeholder",`
 display: flex;
 flex-wrap: none;
 `),o("button-placeholder",`
 width: calc(1.75 * var(--n-rail-height));
 height: var(--n-rail-height);
 `),A("base-loading",`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 font-size: calc(var(--n-button-width) - 4px);
 color: var(--n-loading-color);
 transition: color .3s var(--n-bezier);
 `,[L({left:"50%",top:"50%",originalTransform:"translateX(-50%) translateY(-50%)"})]),o("checked, unchecked",`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 box-sizing: border-box;
 position: absolute;
 white-space: nowrap;
 top: 0;
 bottom: 0;
 display: flex;
 align-items: center;
 line-height: 1;
 `),o("checked",`
 right: 0;
 padding-right: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),o("unchecked",`
 left: 0;
 justify-content: flex-end;
 padding-left: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),T("&:focus",[o("rail",`
 box-shadow: var(--n-box-shadow-focus);
 `)]),l("round",[o("rail","border-radius: calc(var(--n-rail-height) / 2);",[o("button","border-radius: calc(var(--n-button-height) / 2);")])]),E("disabled",[E("icon",[l("rubber-band",[l("pressed",[o("rail",[o("button","max-width: var(--n-button-width-pressed);")])]),o("rail",[T("&:active",[o("button","max-width: var(--n-button-width-pressed);")])]),l("active",[l("pressed",[o("rail",[o("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])]),o("rail",[T("&:active",[o("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])])])])])]),l("active",[o("rail",[o("button","left: calc(100% - var(--n-button-width) - var(--n-offset))")])]),o("rail",`
 overflow: hidden;
 height: var(--n-rail-height);
 min-width: var(--n-rail-width);
 border-radius: var(--n-rail-border-radius);
 cursor: pointer;
 position: relative;
 transition:
 opacity .3s var(--n-bezier),
 background .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-rail-color);
 `,[o("button-icon",`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 font-size: calc(var(--n-button-height) - 4px);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 display: flex;
 justify-content: center;
 align-items: center;
 line-height: 1;
 `,[L()]),o("button",`
 align-items: center; 
 top: var(--n-offset);
 left: var(--n-offset);
 height: var(--n-button-height);
 width: var(--n-button-width-pressed);
 max-width: var(--n-button-width);
 border-radius: var(--n-button-border-radius);
 background-color: var(--n-button-color);
 box-shadow: var(--n-button-box-shadow);
 box-sizing: border-box;
 cursor: inherit;
 content: "";
 position: absolute;
 transition:
 background-color .3s var(--n-bezier),
 left .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 `)]),l("active",[o("rail","background-color: var(--n-rail-color-active);")]),l("loading",[o("rail",`
 cursor: wait;
 `)]),l("disabled",[o("rail",`
 cursor: not-allowed;
 opacity: .5;
 `)])]),Se=Object.assign(Object.assign({},X.props),{size:String,value:{type:[String,Number,Boolean],default:void 0},loading:Boolean,defaultValue:{type:[String,Number,Boolean],default:!1},disabled:{type:Boolean,default:void 0},round:{type:Boolean,default:!0},"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],checkedValue:{type:[String,Number,Boolean],default:!0},uncheckedValue:{type:[String,Number,Boolean],default:!1},railStyle:Function,rubberBand:{type:Boolean,default:!0},spinProps:Object,onChange:[Function,Array]});let $;const $e=I({name:"Switch",props:Se,slots:Object,setup(e){$===void 0&&(typeof CSS<"u"?typeof CSS.supports<"u"?$=CSS.supports("width","max(1px)"):$=!1:$=!0);const{mergedClsPrefixRef:d,inlineThemeDisabled:f,mergedComponentPropsRef:n}=be(e),v=X("Switch","-switch",ke,xe,e,d),g=fe(e,{mergedSize(t){var c,u;if(e.size!==void 0)return e.size;if(t)return t.mergedSize.value;const p=(u=(c=n==null?void 0:n.value)===null||c===void 0?void 0:c.Switch)===null||u===void 0?void 0:u.size;return p||"medium"}}),{mergedSizeRef:S,mergedDisabledRef:w}=g,C=M(e.defaultValue),z=me(e,"value"),m=pe(z,C),F=V(()=>m.value===e.checkedValue),i=M(!1),r=M(!1),B=V(()=>{const{railStyle:t}=e;if(t)return t({focused:r.value,checked:F.value})});function _(t){const{"onUpdate:value":c,onChange:u,onUpdateValue:p}=e,{nTriggerFormInput:j,nTriggerFormChange:D}=g;c&&W(c,t),p&&W(p,t),u&&W(u,t),C.value=t,j(),D()}function Y(){const{nTriggerFormFocus:t}=g;t()}function G(){const{nTriggerFormBlur:t}=g;t()}function J(){e.loading||w.value||(m.value!==e.checkedValue?_(e.checkedValue):_(e.uncheckedValue))}function Z(){r.value=!0,Y()}function q(){r.value=!1,G(),i.value=!1}function Q(t){e.loading||w.value||t.key===" "&&(m.value!==e.checkedValue?_(e.checkedValue):_(e.uncheckedValue),i.value=!1)}function ee(t){e.loading||w.value||t.key===" "&&(t.preventDefault(),i.value=!0)}const U=V(()=>{const{value:t}=S,{self:{opacityDisabled:c,railColor:u,railColorActive:p,buttonBoxShadow:j,buttonColor:D,boxShadowFocus:te,loadingColor:oe,textColor:ie,iconColor:ae,[x("buttonHeight",t)]:h,[x("buttonWidth",t)]:ne,[x("buttonWidthPressed",t)]:re,[x("railHeight",t)]:b,[x("railWidth",t)]:R,[x("railBorderRadius",t)]:le,[x("buttonBorderRadius",t)]:se},common:{cubicBezierEaseInOut:de}}=v.value;let N,O,P;return $?(N=`calc((${b} - ${h}) / 2)`,O=`max(${b}, ${h})`,P=`max(${R}, calc(${R} + ${h} - ${b}))`):(N=H((s(b)-s(h))/2),O=H(Math.max(s(b),s(h))),P=s(b)>s(h)?R:H(s(R)+s(h)-s(b))),{"--n-bezier":de,"--n-button-border-radius":se,"--n-button-box-shadow":j,"--n-button-color":D,"--n-button-width":ne,"--n-button-width-pressed":re,"--n-button-height":h,"--n-height":O,"--n-offset":N,"--n-opacity-disabled":c,"--n-rail-border-radius":le,"--n-rail-color":u,"--n-rail-color-active":p,"--n-rail-height":b,"--n-rail-width":R,"--n-width":P,"--n-box-shadow-focus":te,"--n-loading-color":oe,"--n-text-color":ie,"--n-icon-color":ae}}),k=f?ve("switch",V(()=>S.value[0]),U,e):void 0;return{handleClick:J,handleBlur:q,handleFocus:Z,handleKeyup:Q,handleKeydown:ee,mergedRailStyle:B,pressed:i,mergedClsPrefix:d,mergedValue:m,checked:F,mergedDisabled:w,cssVars:f?void 0:U,themeClass:k==null?void 0:k.themeClass,onRender:k==null?void 0:k.onRender}},render(){const{mergedClsPrefix:e,mergedDisabled:d,checked:f,mergedRailStyle:n,onRender:v,$slots:g}=this;v==null||v();const{checked:S,unchecked:w,icon:C,"checked-icon":z,"unchecked-icon":m}=g,F=!(K(C)&&K(z)&&K(m));return a("div",{role:"switch","aria-checked":f,class:[`${e}-switch`,this.themeClass,F&&`${e}-switch--icon`,f&&`${e}-switch--active`,d&&`${e}-switch--disabled`,this.round&&`${e}-switch--round`,this.loading&&`${e}-switch--loading`,this.pressed&&`${e}-switch--pressed`,this.rubberBand&&`${e}-switch--rubber-band`],tabindex:this.mergedDisabled?void 0:0,style:this.cssVars,onClick:this.handleClick,onFocus:this.handleFocus,onBlur:this.handleBlur,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},a("div",{class:`${e}-switch__rail`,"aria-hidden":"true",style:n},y(S,i=>y(w,r=>i||r?a("div",{"aria-hidden":!0,class:`${e}-switch__children-placeholder`},a("div",{class:`${e}-switch__rail-placeholder`},a("div",{class:`${e}-switch__button-placeholder`}),i),a("div",{class:`${e}-switch__rail-placeholder`},a("div",{class:`${e}-switch__button-placeholder`}),r)):null)),a("div",{class:`${e}-switch__button`},y(C,i=>y(z,r=>y(m,B=>a(ge,null,{default:()=>this.loading?a(we,Object.assign({key:"loading",clsPrefix:e,strokeWidth:20},this.spinProps)):this.checked&&(r||i)?a("div",{class:`${e}-switch__button-icon`,key:r?"checked-icon":"icon"},r||i):!this.checked&&(B||i)?a("div",{class:`${e}-switch__button-icon`,key:B?"unchecked-icon":"icon"},B||i):null})))),y(S,i=>i&&a("div",{key:"checked",class:`${e}-switch__checked`},i)),y(w,i=>i&&a("div",{key:"unchecked",class:`${e}-switch__unchecked`},i)))))}});export{Re as F,$e as N};
