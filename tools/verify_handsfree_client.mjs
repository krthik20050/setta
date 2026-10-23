// Deterministic browser-client logic checks with synthetic audio and DOM stubs.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('../src/handsfree.html',import.meta.url),'utf8');
const script=html.split('<script type="module">')[1].split('</script>')[0];
const elements=new Map();
const context=vm.createContext({
 document:{getElementById(id){if(!elements.has(id))elements.set(id,{style:{},textContent:'',disabled:false});return elements.get(id);}},
 window:{addEventListener(){}},console,Uint8Array,Float32Array,ArrayBuffer,DataView,TextDecoder,
 AbortController,Math,JSON,setTimeout(){},
 fetch:async()=>({ok:true,status:204}),
 btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary')
});
vm.runInContext(script,context);
const wave=vm.runInContext('wav(new Float32Array([0,.5,-.5]),24000)',context);
assert.equal(Buffer.from(wave).subarray(0,4).toString(),'RIFF');
assert.equal(new DataView(wave.buffer).getUint32(24,true),24000);
assert.equal(wave.length,50);
vm.runInContext(`globalThis.stops=0;globalThis.aborts=0;controller={abort(){aborts++}};nodes=[{stop(){stops++}}];ctx={currentTime:1};stopOutput();`,context);
assert.equal(context.stops,1);assert.equal(context.aborts,1);
assert.equal(vm.runInContext('nodes.length',context),0);
assert.equal(vm.runInContext('ticket',context),null);
vm.runInContext(`
 globalThis.starts=0;
 ctx={currentTime:1,destination:{},createBuffer(channels,length,rate){return {duration:length/rate,getChannelData(){return new Float32Array(length)}}},
 createBufferSource(){return {connect(){},start(){starts++},stop(){},buffer:null}}};
 playPCM({pcm:btoa('\\0\\0'.repeat(2400)),sample_rate:24000},generation);
`,context);
assert.equal(context.starts,1);
assert.equal(vm.runInContext('nodes.length',context),1);
console.log('Hands-free client: WAV framing, interrupt cancellation and progressive PCM scheduling passed.');
vm.runInContext(`
 ctx={sampleRate:100,currentTime:1};active=true;recording=false;parts=[];pre=[];nodes=[];
 $('pause').value='1.5';globalThis.sent=[];sendAudio=(bytes,limit)=>sent.push({bytes,limit});
 function frame(volume){audioFrame({inputBuffer:{getChannelData(){return new Float32Array(10).fill(volume)}}});}
 frame(.1);frame(.1);frame(.1);
 for(let i=0;i<9;i++)frame(0);
`,context);
assert.equal(vm.runInContext('recording',context),true,'A normal 0.9s mid-sentence pause must not send');
assert.equal(context.sent.length,0);
vm.runInContext(`frame(.1);frame(.1);for(let i=0;i<16;i++)frame(0);`,context);
assert.equal(context.sent.length,1,'Send the complete utterance after the final pause');
vm.runInContext(`$('pause').value='manual';frame(.1);frame(.1);frame(.1);for(let i=0;i<25;i++)frame(0);`,context);
assert.equal(context.sent.length,1,'Manual mode must wait through long pauses');
vm.runInContext(`$('send-now').onclick();`,context);
assert.equal(context.sent.length,2);
console.log('Endpointing: mid-sentence pause, continued speech and manual send passed.');
