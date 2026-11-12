'use strict';
const $ = id => document.getElementById(id);
const state = {items:[], visible:35};
const number = n => new Intl.NumberFormat('ja-JP').format(n);
const date = s => s ? new Date(s).toLocaleString('ja-JP',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Tokyo'}) : '—';
const element = (name,cls,text) => {const e=document.createElement(name);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};

function drawChart(daily){
  const svg=$('trend');svg.replaceChildren();const ns='http://www.w3.org/2000/svg';
  const add=(name,attrs,text)=>{const e=document.createElementNS(ns,name);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;svg.appendChild(e)};
  const end = new Date();const base=Date.UTC(end.getUTCFullYear(),end.getUTCMonth(),end.getUTCDate());
  const days=Array.from({length:14},(_,i)=>new Date(base-(13-i)*86400000).toISOString().slice(0,10));
  const byDate=new Map(daily.map(x=>[x.date,x]));
  const rows=days.map(d=>byDate.get(d)||{});const hi=Math.max(1,...rows.map(r=>(r.new_reactions||0)+(r.new_news||0)));
  const px=i=>38+i*824/13, py=y=>151-126*y/hi;
  for(let i=0;i<=3;i++){const v=i*hi/3;add('line',{x1:38,x2:879,y1:py(v),y2:py(v),stroke:'#314059','stroke-dasharray':'3 5'});add('text',{x:4,y:py(v)+4,fill:'#8397b0','font-size':11},String(Math.round(v)))}
  for(const [key,color] of [['new_reactions','#50e8d3'],['new_news','#9b87ff']]){
    add('polyline',{points:rows.map((r,i)=>px(i)+','+py(r[key]||0)).join(' '),fill:'none',stroke:color,'stroke-width':2.8,'stroke-linecap':'round','stroke-linejoin':'round'});
    rows.forEach((r,i)=>{if(r[key])add('circle',{cx:px(i),cy:py(r[key]),r:3,fill:color})});
  }
  [0,3,6,9,13].forEach(i=>add('text',{x:px(i),y:181,fill:'#93a5bf','font-size':11,'text-anchor':'middle'},days[i].slice(5).replace('-','/')));
  $('chart-empty').hidden = daily.length>0;
}
function filtered(){
  const q=$('search').value.trim().toLocaleLowerCase(),brand=$('brand').value,src=$('source').value,kind=$('kind').value;
  return state.items.filter(x=>(!brand||brand===x.brand)&&(!src||src===x.source)&&(!kind||kind===x.kind)&&(!q||(x.title+' '+(x.excerpt||'')+' '+x.brand).toLocaleLowerCase().includes(q)));
}
function drawItems(){
  const root=$('items');root.replaceChildren();const items=filtered();$('result-count').textContent=number(items.length)+' 件';$('more').hidden=items.length<=state.visible;
  if(!items.length){root.append(element('div','empty',state.items.length?'条件に合う投稿が見つかりません。':'まだ取得データはありません。'));return}
  for(const x of items.slice(0,state.visible)){
    if(!/^https:\/\/[^\s]+$/i.test(x.url||''))continue;
    const a=element('a','item');a.href=x.url;a.target='_blank';a.rel='noopener noreferrer';
    const body=element('div','item-content'), meta=element('div','item-meta');
    meta.append(element('span','tag '+(x.brand==='Unity Aura'?'aura':x.brand==='Industry'?'industry':''),x.brand),
      element('span','',x.source+(x.community?' · '+x.community:'')),element('span','',x.kind==='news'?'ニュース':'ユーザー投稿'),
      element('span','',date(x.published_at)));
    body.append(meta,element('div','item-title',x.title));if(x.excerpt&&x.excerpt!==x.title)body.append(element('div','item-excerpt',x.excerpt));
    a.append(body,element('span','outlink','↗'));root.append(a);
  }
}
async function load(){
  try{
    const res=await fetch('./data/monitor.json?ts='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);
    const data=await res.json();if(data.schema!==1||!Array.isArray(data.items))throw Error('Invalid store');
    state.items=data.items;
    $('updated').textContent=date(data.updated_at);
    $('reactions').textContent=number(data.items.filter(x=>x.kind==='reaction').length);
    $('reddit').textContent=number(data.items.filter(x=>x.source==='Reddit').length);
    $('news').textContent=number(data.items.filter(x=>x.kind==='news').length);
    const since=Date.now()-7*86400000;
    $('seven').textContent=number((data.daily||[]).filter(d=>Date.parse(d.date+'T00:00:00Z')>=since).reduce((n,d)=>n+(d.new_reactions||0)+(d.new_news||0),0));
    const run=(data.runs||[]).at(-1);$('sources').textContent=run?number(run.sources_ok)+'/'+number(run.sources_total):'—';
    const warning=(run?.errors||[]).length>0;
    $('state').textContent=data.updated_at?(warning?'一部の取得でエラー':'最終収集済み'):'未収集';
    if(data.updated_at)$('state').parentElement.querySelector('.dot').classList.add('ok');
    drawChart(data.daily||[]);drawItems();
  }catch(e){$('state').textContent='読み込み失敗';$('items').replaceChildren(element('div','empty','データを読み込めません。'));console.error(e)}
}
for(const id of ['search','brand','source','kind'])$(id).addEventListener(id==='search'?'input':'change',()=>{state.visible=35;drawItems()});
$('more').addEventListener('click',()=>{state.visible+=35;drawItems()});
load();
