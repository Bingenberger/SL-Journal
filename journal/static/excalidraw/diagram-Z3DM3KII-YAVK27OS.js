import{a as E}from"./chunk-CDENLQJG.js";import{a as z}from"./chunk-G5B7OHEB.js";import{a as F}from"./chunk-D4N6SRUP.js";import"./chunk-VYX34G4C.js";import"./chunk-WPKWQJMT.js";import"./chunk-UEKIUVVZ.js";import"./chunk-36ENJ6S6.js";import"./chunk-QUCZOWIA.js";import"./chunk-KOUKY6ZC.js";import"./chunk-OPKNLR4R.js";import"./chunk-ZZA6CFQW.js";import"./chunk-6YKTDOWX.js";import"./chunk-7EWZUIZS.js";import"./chunk-PIV4NBPT.js";import"./chunk-P54JAKKL.js";import"./chunk-OBUWUL4L.js";import"./chunk-Y7H4BMLT.js";import"./chunk-ZMHBSON2.js";import"./chunk-3ZVXHM4A.js";import{o as w}from"./chunk-R4P3DRJI.js";import"./chunk-ONAQMBED.js";import{O as y,T as $,U as B,V as C,W as S,X as D,Y as T,Z as P,k as v,u as x}from"./chunk-E6MBOXOE.js";import{b as u}from"./chunk-BBQ3I4IX.js";import{a as h}from"./chunk-YUSHYV7C.js";import"./chunk-RJ2R4FVC.js";var L=v.packet,b,A=(b=class{constructor(){this.packet=[],this.setAccTitle=B,this.getAccTitle=C,this.setDiagramTitle=T,this.getDiagramTitle=P,this.getAccDescription=D,this.setAccDescription=S}getConfig(){let t=w({...L,...x().packet});return t.showBits&&(t.paddingY+=10),t}getPacket(){return this.packet}pushWord(t){t.length>0&&this.packet.push(t)}clear(){$(),this.packet=[]}},h(b,"PacketDB"),b),M=1e4,Y=h((e,t)=>{E(e,t);let a=-1,o=[],n=1,{bitsPerRow:l}=t.getConfig();for(let{start:r,end:i,bits:c,label:d}of e.blocks){if(r!==void 0&&i!==void 0&&i<r)throw new Error(`Packet block ${r} - ${i} is invalid. End must be greater than start.`);if(r??(r=a+1),r!==a+1)throw new Error(`Packet block ${r} - ${i??r} is not contiguous. It should start from ${a+1}.`);if(c===0)throw new Error(`Packet block ${r} is invalid. Cannot have a zero bit field.`);for(i??(i=r+(c??1)-1),c??(c=i-r+1),a=i,u.debug(`Packet block ${r} - ${a} with label ${d}`);o.length<=l+1&&t.getPacket().length<M;){let[p,s]=I({start:r,end:i,bits:c,label:d},n,l);if(o.push(p),p.end+1===n*l&&(t.pushWord(o),o=[],n++),!s)break;({start:r,end:i,bits:c,label:d}=s)}}t.pushWord(o)},"populate"),I=h((e,t,a)=>{if(e.start===void 0)throw new Error("start should have been set during first phase");if(e.end===void 0)throw new Error("end should have been set during first phase");if(e.start>e.end)throw new Error(`Block start ${e.start} is greater than block end ${e.end}.`);if(e.end+1<=t*a)return[e,void 0];let o=t*a-1,n=t*a;return[{start:e.start,end:o,label:e.label,bits:o-e.start},{start:n,end:e.end,label:e.label,bits:e.end-n}]},"getNextFittingBlock"),W={parser:{yy:void 0},parse:h(async e=>{let t=await F("packet",e),a=W.parser?.yy;if(!(a instanceof A))throw new Error("parser.parser?.yy was not a PacketDB. This is due to a bug within Mermaid, please report this issue at https://github.com/mermaid-js/mermaid/issues.");u.debug(t),Y(t,a)},"parse")},O=h((e,t,a,o)=>{let n=o.db,l=n.getConfig(),{rowHeight:r,paddingY:i,bitWidth:c,bitsPerRow:d}=l,p=n.getPacket(),s=n.getDiagramTitle(),f=r+i,g=f*(p.length+1)-(s?0:r),k=c*d+2,m=z(t);m.attr("viewBox",`0 0 ${k} ${g}`),y(m,g,k,l.useMaxWidth);for(let[_,N]of p.entries())j(m,N,_,l);m.append("text").text(s).attr("x",k/2).attr("y",g-f/2).attr("dominant-baseline","middle").attr("text-anchor","middle").attr("class","packetTitle")},"draw"),j=h((e,t,a,{rowHeight:o,paddingX:n,paddingY:l,bitWidth:r,bitsPerRow:i,showBits:c})=>{let d=e.append("g"),p=a*(o+l)+l;for(let s of t){let f=s.start%i*r+1,g=(s.end-s.start+1)*r-n;if(d.append("rect").attr("x",f).attr("y",p).attr("width",g).attr("height",o).attr("class","packetBlock"),d.append("text").attr("x",f+g/2).attr("y",p+o/2).attr("class","packetLabel").attr("dominant-baseline","middle").attr("text-anchor","middle").text(s.label),!c)continue;let k=s.end===s.start,m=p-2;d.append("text").attr("x",f+(k?g/2:0)).attr("y",m).attr("class","packetByte start").attr("dominant-baseline","auto").attr("text-anchor",k?"middle":"start").text(s.start),k||d.append("text").attr("x",f+g).attr("y",m).attr("class","packetByte end").attr("dominant-baseline","auto").attr("text-anchor","end").text(s.end)}},"drawWord"),G={draw:O},H={byteFontSize:"10px",startByteColor:"black",endByteColor:"black",labelColor:"black",labelFontSize:"12px",titleColor:"black",titleFontSize:"14px",blockStrokeColor:"black",blockStrokeWidth:"1",blockFillColor:"#efefef"},K=h(({packet:e}={})=>{let t=w(H,e);return`
	.packetByte {
		font-size: ${t.byteFontSize};
	}
	.packetByte.start {
		fill: ${t.startByteColor};
	}
	.packetByte.end {
		fill: ${t.endByteColor};
	}
	.packetLabel {
		fill: ${t.labelColor};
		font-size: ${t.labelFontSize};
	}
	.packetTitle {
		fill: ${t.titleColor};
		font-size: ${t.titleFontSize};
	}
	.packetBlock {
		stroke: ${t.blockStrokeColor};
		stroke-width: ${t.blockStrokeWidth};
		fill: ${t.blockFillColor};
	}
	`},"styles"),Z={parser:W,get db(){return new A},renderer:G,styles:K};export{Z as diagram};
