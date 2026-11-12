'use strict';
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('ja-JP').format(n);
const state={data:null,tone:'all',limit:35};
const el=(tag,cls,content)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(content!==undefined)node.textContent=String(content);return node;};
const date=s=>s?new Date(s).toLocaleDateString('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'short',day:'numeric'}):'—';
const label=x=>['positive','negative','neutral','unclear'].includes(x.sentiment)?x.sentiment:'unclear';
const cutoff=()=>{const n=$('period').value;return n==='all'?-Infinity:Date.now()-(n==='year'?365:Number(n))*86400000;};
function selectItems(kind='reaction'){
  const b=$('brand').value,s=$('source').value,c=cutoff();
  return (state.data?.items||[]).filter(x=>x.kind===kind&&(!b||x.brand===b)&&(!s||x.source===s)&&Date.parse(x.published_at)>=c);
}
function stats(){
  const items=selectItems(),count={positive:0,negative:0,neutral:0,unclear:0};
  items.forEach(x=>count[label(x)]++);
  const total=items.length,neutral=count.neutral+count.unclear;
  $('total').textContent=fmt(total);$('positive').textContent=fmt(count.positive);$('negative').textContent=fmt(count.negative);$('other').textContent=fmt(neutral);
  $('positive-detail').textContent=total?(100*count.positive/total).toFixed(1)+'% of all posts':'全投稿に対する割合';
  $('negative-detail').textContent=total?(100*count.negative/total).toFixed(1)+'% of all posts':'全投稿に対する割合';
  $('balance-total').textContent=fmt(total);
  const dist=$('distribution');dist.replaceChildren();
  for(const [key,n,cls] of [['positive',count.positive,'pos'],['negative',count.negative,'neg'],['neutral',neutral,'other']]){
    if(!n)continue;const bar=el('span',cls);bar.style.width=(total?100*n/total:0)+'%';
    bar.title=key+': '+n+'件';dist.append(bar);
  }
  $('dist-pos').textContent=fmt(count.positive)+' / '+(total?Math.round(count.positive*100/total):0)+'%';
  $('dist-neg').textContent=fmt(count.negative)+' / '+(total?Math.round(count.negative*100/total):0)+'%';
  $('dist-other').textContent=fmt(neutral)+' / '+(total?Math.round(neutral*100/total):0)+'%';
  const totals={};
  items.forEach(x=>{totals[x.source]=(totals[x.source]||0)+1;});
  const root=$('sources');root.replaceChildren();
  const series=Object.entries(totals).sort((a,b)=>b[1]-a[1]);
  if(!series.length)root.append(el('div','source-row','対象期間の投稿はありません'));
  const max=series.length?series[0][1]:1;
  for(const [source,n] of series){
    const row=el('div','source-row');const track=el('div','mini-track'),bar=el('span','mini-fill');
    bar.style.width=(n/max*100)+'%';track.append(bar);
    row.append(el('span','',source),track,el('strong','',fmt(n)));root.append(row);
  }
  drawTrend(items);
}
function periodBucket(item,period){
  const d=new Date(item.published_at);if(isNaN(d))return null;
  const y=d.getUTCFullYear(),m=d.getUTCMonth();
  if(period==='all')return y+'-Q'+(Math.floor(m/3)+1);
  if(period==='year')return y+'-'+String(m+1).padStart(2,'0');
  const mon=new Date(Date.UTC(y,m,d.getUTCDate()));mon.setUTCDate(mon.getUTCDate()-(mon.getUTCDay()+6)%7);
  return mon.toISOString().slice(0,10);
}
function trendKeys(period,items){
  const now=new Date();
  if(period==='all'){
    const years=items.map(x=>new Date(x.published_at).getUTCFullYear()).filter(Number.isFinite);
    const begin=Math.min(2022,...years);
    const out=[];
    for(let y=begin;y<=now.getUTCFullYear();y++)for(let q=1;q<=4;q++)
      if(y<now.getUTCFullYear()||q<=Math.floor(now.getUTCMonth()/3)+1)out.push(y+'-Q'+q);
    return out;
  }
  if(period==='year'){
    const out=[];for(let i=11;i>=0;i--){
      const d=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth()-i,1));
      out.push(d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0'));
    }return out;
  }
  const windowDays=period==='30'?30:90;
  const origin=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()-windowDays));
  origin.setUTCDate(origin.getUTCDate()-(origin.getUTCDay()+6)%7);
  const out=[],end=now.getTime();
  for(const d=new Date(origin);d.getTime()<=end;d.setUTCDate(d.getUTCDate()+7))out.push(d.toISOString().slice(0,10));
  return out;
}
function drawTrend(items){
  const svg=$('trend');svg.replaceChildren();const ns='http://www.w3.org/2000/svg';
  const add=(type,attrs,value)=>{const node=document.createElementNS(ns,type);
    Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));
    if(value!==undefined)node.textContent=value;svg.append(node);return node;};
  const period=$('period').value,keys=trendKeys(period,items),groups=new Map();
  items.forEach(x=>{const k=periodBucket(x,period);if(!k||!keys.includes(k))return;
    if(!groups.has(k))groups.set(k,{positive:0,negative:0});const t=label(x);
    if(t==='positive'||t==='negative')groups.get(k)[t]++;});
  const rows=keys.map(k=>Object.assign({key:k,positive:0,negative:0},groups.get(k)||{}));
  $('chart-granularity').textContent=period==='all'?'四半期別':period==='year'?'月別':'週別';
  const top=14,bottom=197,left=38,right=705;
  const max=Math.max(1,...rows.map(x=>Math.max(x.negative,x.positive)));
  for(let i=0;i<=4;i++){const y=bottom-(bottom-top)*i/4;
    add('line',{x1:left,y1:y,x2:right,y2:y,stroke:'#e9eef3','stroke-width':1});
    add('text',{x:30,y:y+3,'text-anchor':'end','font-size':10,fill:'#a2adbb'},Math.round(max*i/4));
  }
  const step=(right-left)/Math.max(rows.length,1),w=Math.max(3,Math.min(13,step*.26));
  rows.forEach((r,i)=>{
    const center=left+(i+.5)*step;
    for(const [t,fill,offset] of [['positive','#1b9b78',-1],['negative','#d95c61',0.2]]){
      const value=r[t];if(!value)continue;
      const h=value/max*(bottom-top),x=center+offset*w-1;
      const rect=add('rect',{x,y:bottom-h,width:w,height:h,rx:1.5,fill});
      const tip=document.createElementNS(ns,'title');tip.textContent=r.key+' / '+t+' '+value+'件';rect.append(tip);
    }
    const skip=rows.length>22?4:rows.length>13?3:rows.length>8?2:1;
    if(i%skip===0&&i<rows.length-skip||i===rows.length-1){
      const text=period==='all'?r.key.replace('-Q',' Q'):period==='year'?Number(r.key.slice(5))+'月':r.key.slice(5).replace('-','/');
      add('text',{x:center,y:221,'text-anchor':'middle','font-size':9.5,fill:'#8996a6'},text);
    }
  });
  if(!items.length)add('text',{x:375,y:113,'text-anchor':'middle','font-size':13,fill:'#95a3b4'},'対象期間の投稿がありません');
}
function table(){
  const kind=$('kind').value,news=kind==='news',q=$('query').value.trim().toLocaleLowerCase();
  let items=selectItems(kind);
  if(!news&&state.tone!=='all')items=items.filter(x=>state.tone==='neutral'?['neutral','unclear'].includes(label(x)):label(x)===state.tone);
  if(q)items=items.filter(x=>[x.title,x.excerpt,x.brand,x.community].join(' ').toLocaleLowerCase().includes(q));
  items.sort((a,b)=>String(b.published_at).localeCompare(String(a.published_at)));
  $('results').textContent=fmt(items.length)+' posts';
  $('shown').textContent=fmt(Math.min(state.limit,items.length))+' / '+fmt(items.length)+' 件';
  $('more').hidden=items.length<=state.limit;
  const root=$('rows');root.replaceChildren();
  if(!items.length){const tr=el('tr'),td=el('td','empty','該当する投稿がありません');td.colSpan=5;tr.append(td);root.append(tr);return;}
  const names={positive:'ポジティブ',negative:'ネガティブ',neutral:'中立',unclear:'判定保留',news:'ニュース'};
  items.slice(0,state.limit).forEach(x=>{
    if(!/^https:\/\/[^\s]+$/.test(x.url||''))return;
    const tr=el('tr'),one=el('td'),two=el('td'),three=el('td'),four=el('td'),five=el('td'),t=news?'news':label(x);
    one.append(el('span','tone-pill '+t,names[t]));
    const excerpt=(x.id||'').startsWith('reddit:c:')?(x.excerpt||x.title):(x.title||x.excerpt);
    two.append(el('div','post-head',(excerpt||'本文なし').slice(0,320)));
    three.append(el('div','source-name',x.brand+' / '+x.source+(x.community?' · '+x.community:'')));
    four.append(el('span','date-col',date(x.published_at)));
    const a=el('a','open-post','↗');a.href=x.url;a.target='_blank';a.rel='noopener noreferrer';a.title='投稿を開く';five.append(a);
    tr.append(one,two,three,four,five);root.append(tr);
  });
}
function coverage(){
  const b=state.data.backfill||{},done=b.completed_windows||0,total=b.total_windows||0;
  const partial=(b.saturated||[]).length,errors=(b.errors||[]).length;
  $('coverage').textContent=total
    ?'Reddit過去データ：'+fmt(done)+'/'+fmt(total)+'検索範囲を処理。'+
      (partial?'取得上限に達した範囲 '+fmt(partial)+'件は継続取得の対象。':'')+
      (errors?' 一部の検索が失敗・再試行待ち。':'')+
      ' 全投稿を保証する数字ではありません。'
    :'過去データの取得準備中。欠落する期間があります。';
  $('backfill-fraction').textContent=total?fmt(done)+' / '+fmt(total):'—';
  $('backfill-progress').style.width=(total?100*done/total:0).toFixed(1)+'%';
}
function refresh(){if(!state.data)return;stats();table();coverage();}
async function load(){
  try{
    const response=await fetch('./data/monitor.json?t='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error(response.status);
    const d=await response.json();if(d.schema!==1||!Array.isArray(d.items))throw Error('data format');
    state.data=d;
    $('updated').textContent=d.updated_at?'最終更新 '+date(d.updated_at):'未収集';
    $('footer-date').textContent=d.updated_at?'Data updated: '+d.updated_at:'';
    $('sync-dot').classList.toggle('ok',Boolean(d.updated_at));
    refresh();
  }catch(err){$('updated').textContent='データ読み込み失敗';$('coverage').textContent='取得できませんでした。GitHub Actionsをご確認ください。';console.error(err);}
}
for(const key of ['period','brand','source','kind'])$(key).addEventListener('change',()=>{state.limit=35;refresh();});
$('query').addEventListener('input',()=>{state.limit=35;table();});
document.querySelectorAll('.segments button').forEach(btn=>btn.addEventListener('click',()=>{
  state.tone=btn.dataset.tone;document.querySelectorAll('.segments button').forEach(b=>b.classList.toggle('active',b===btn));
  state.limit=35;table();
}));
$('more').addEventListener('click',()=>{state.limit+=35;table();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
setInterval(()=>{if(!document.hidden)load();},30*60*1000);
load();
