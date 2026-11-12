'use strict';
const $=id=>document.getElementById(id), fmt=n=>new Intl.NumberFormat('ja-JP').format(n);
const state={data:null,tone:'all',limit:40};
const elem=(tag,cls,txt)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(txt!==undefined)x.textContent=String(txt);return x;};
const shownDate=s=>s?new Date(s).toLocaleDateString('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'short',day:'numeric'}):'—';
const tone=x=>['positive','negative','neutral','unclear'].includes(x.sentiment)?x.sentiment:'unclear';
function cutoff(){const p=$('period').value;return p==='all'?-Infinity:Date.now()-(p==='year'?365:Number(p))*86400000;}
function candidates(kind='reaction'){const brand=$('brand').value,source=$('source').value,c=cutoff();
  return (state.data?.items||[]).filter(x=>x.kind===kind&&(!brand||x.brand===brand)&&(!source||x.source===source)&&Date.parse(x.published_at)>=c);
}
function summaries(){
  const items=candidates(),counts={negative:0,positive:0,neutral:0,unclear:0};
  items.forEach(x=>counts[tone(x)]++);
  $('total').textContent=fmt(items.length);$('negative').textContent=fmt(counts.negative);
  $('positive').textContent=fmt(counts.positive);$('other').textContent=fmt(counts.neutral+counts.unclear);
  const rated=counts.negative+counts.positive;
  $('negative-detail').textContent=rated?'明確な評価のうち '+Math.round(counts.negative*100/rated)+'%':'否定的な表現がある投稿';
  $('positive-detail').textContent=rated?'明確な評価のうち '+Math.round(counts.positive*100/rated)+'%':'好意的な表現がある投稿';
  const topicCounts={};
  items.filter(x=>tone(x)==='negative').forEach(x=>{const t=x.topic||'その他';topicCounts[t]=(topicCounts[t]||0)+1;});
  const topics=Object.entries(topicCounts).sort((a,b)=>b[1]-a[1]);
  if(topics.length){
    $('insight').textContent='もっとも多い不満：「'+topics[0][0]+'」';
    $('insight-detail').textContent='ネガティブ投稿'+fmt(counts.negative)+'件のうち'+fmt(topics[0][1])+'件でこの問題が見られました。自動判定のため元投稿もご確認ください。';
  }else{
    $('insight').textContent='否定的な傾向はまだ十分に観測されていません';
    $('insight-detail').textContent='取得データや分析期間を確認してください。過去データは段階的に取り込んでいます。';
  }
  drawTopics(topics);drawChart(items);
}
function drawTopics(entries){
  const root=$('topics');root.replaceChildren();
  if(!entries.length){root.append(elem('p','muted','分類できるネガティブ投稿がありません。'));return;}
  const max=entries[0][1];
  entries.slice(0,6).forEach(([label,value])=>{
    const row=elem('div','topic-row'),meta=elem('div','topic-meta');
    meta.append(elem('span','',label),elem('span','num',fmt(value)+' 件'));
    const bg=elem('div','bar-bg'),bar=elem('div','bar-fill');bar.style.width=100*value/max+'%';bg.append(bar);row.append(meta,bg);root.append(row);
  });
}
function groupKey(x,p){
  const d=new Date(x.published_at);if(isNaN(d))return null;
  const y=d.getUTCFullYear(),m=d.getUTCMonth();
  if(p==='all')return y+'-Q'+(Math.floor(m/3)+1);
  if(p==='year')return y+'-'+String(m+1).padStart(2,'0');
  const mon=new Date(Date.UTC(y,m,d.getUTCDate()));mon.setUTCDate(mon.getUTCDate()-(mon.getUTCDay()+6)%7);
  return mon.toISOString().slice(0,10);
}
function drawChart(items){
  const svg=$('trend'),ns='http://www.w3.org/2000/svg';svg.replaceChildren();
  const add=(tag,attrs,value)=>{const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(value!==undefined)n.textContent=value;svg.append(n);return n;};
  const p=$('period').value,groups=new Map();
  items.forEach(x=>{const k=groupKey(x,p);if(!k)return;
    if(!groups.has(k))groups.set(k,{negative:0,positive:0,neutral:0});const t=tone(x);groups.get(k)[t==='positive'?'positive':t==='negative'?'negative':'neutral']++;
  });
  let keys=[...groups.keys()].sort();
  if(p==='all'){
    const from=keys.length?Math.min(2022,Number(keys[0].slice(0,4))):2022,now=new Date();
    keys=[];for(let y=from;y<=now.getUTCFullYear();y++)for(let q=1;q<=4;q++)
      if(y<now.getUTCFullYear()||q<=Math.floor(now.getUTCMonth()/3)+1)keys.push(y+'-Q'+q);
  }else if(p==='year'){
    const d=new Date();keys=[];for(let i=11;i>=0;i--){const x=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()-i,1));keys.push(x.getUTCFullYear()+'-'+String(x.getUTCMonth()+1).padStart(2,'0'));}
  }
  const rows=keys.map(k=>Object.assign({key:k,negative:0,positive:0,neutral:0},groups.get(k)||{}));
  const max=Math.max(1,...rows.map(r=>r.negative+r.positive+r.neutral)),left=36,right=677,base=195,top=15;
  for(let j=0;j<=4;j++){const y=base-(base-top)*j/4;add('line',{x1:left,x2:right,y1:y,y2:y,stroke:'#e9edf2'});
    add('text',{x:left-9,y:y+4,fill:'#91a0b0','text-anchor':'end','font-size':10},String(Math.round(max*j/4)));}
  const step=(right-left)/Math.max(1,rows.length),width=Math.max(3,Math.min(32,step*.56));
  rows.forEach((r,i)=>{const x=left+(i+.5)*step-width/2;let y=base;
    for(const [key,color] of [['negative','#ce514f'],['positive','#2c9b7e'],['neutral','#bfc7d2']]){
      const height=(base-top)*r[key]/max;if(!height)continue;y-=height;
      const rect=add('rect',{x,y,width,height,rx:width<6?1:2,fill:color});
      const title=document.createElementNS(ns,'title');title.textContent=r.key+' '+key+' '+r[key]+' 件';rect.append(title);
    }
    const skip=rows.length>18?3:rows.length>11?2:1;
    if((i%skip===0&&i<rows.length-skip)||i===rows.length-1){
      const label=p==='all'?r.key.replace('-',' '):p==='year'?Number(r.key.slice(5))+'月':r.key.slice(5).replace('-','/');
      add('text',{x:x+width/2,y:218,'text-anchor':'middle','font-size':10,fill:'#8290a1'},label);
    }
  });
  $('trend-empty').hidden=items.length>0;
}
function table(){
  const kind=$('kind').value,isNews=kind==='news',q=$('query').value.trim().toLocaleLowerCase();
  let items=candidates(kind);
  if(!isNews&&state.tone!=='all')items=items.filter(x=>state.tone==='neutral'?['neutral','unclear'].includes(tone(x)):tone(x)===state.tone);
  if(q)items=items.filter(x=>[x.title,x.excerpt,x.topic,x.community].join(' ').toLocaleLowerCase().includes(q));
  items.sort((a,b)=>String(b.published_at).localeCompare(String(a.published_at)));
  $('results').textContent=fmt(items.length)+' 件';
  $('shown').textContent=fmt(Math.min(items.length,state.limit))+' / '+fmt(items.length)+' 件';
  $('more').hidden=items.length<=state.limit;
  const root=$('rows');root.replaceChildren();
  if(!items.length){const tr=elem('tr'),td=elem('td','table-empty','該当する投稿がありません。');td.colSpan=5;tr.append(td);root.append(tr);return;}
  const names={negative:'ネガティブ',positive:'ポジティブ',neutral:'中立',unclear:'判定保留',news:'ニュース'};
  items.slice(0,state.limit).forEach(x=>{
    if(!/^https:\/\/[^\s]+$/.test(x.url||''))return;
    const tr=elem('tr'),a=elem('td'),b=elem('td'),c=elem('td'),d=elem('td'),e=elem('td'),t=isNews?'news':tone(x);
    a.append(elem('span','sentiment-pill '+(t==='news'?'neutral':t),names[t]));
    b.append(elem('div','post-topic',isNews?x.brand:(x.topic||'その他')+' · '+x.brand));
    b.append(elem('div','post-title',(x.title||x.excerpt||'本文なし').slice(0,280)));
    if(!isNews&&x.reason)b.append(elem('div','post-reason',x.reason));
    c.append(elem('span','source-name',x.source+(x.community?' · '+x.community:'')));
    d.append(elem('span','post-date',shownDate(x.published_at)));
    const link=elem('a','open-post','↗');link.href=x.url;link.target='_blank';link.rel='noopener noreferrer';link.title='元投稿を見る';e.append(link);
    tr.append(a,b,c,d,e);root.append(tr);
  });
}
function refresh(){
  if(!state.data)return;
  const data=state.data,b=data.backfill||{},progress=b.total_windows?fmt(b.completed_windows||0)+' / '+fmt(b.total_windows)+'検索窓':''; 
  $('coverage').textContent=progress
    ?'Redditの2022年以降の履歴を段階的に収集中：'+progress+'を処理。未収集・欠落・取得上限に達した期間があります。'
    :'Redditの2022年以降の履歴を取り込み準備中。現在の時系列は不完全です。';
  if((data.runs||[]).at(-1)?.errors?.length)$('coverage').textContent+=' 一部の取得に失敗しています。';
  summaries();table();
}
async function load(){
  try{
    const res=await fetch('./data/monitor.json?t='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);
    const data=await res.json();if(data.schema!==1||!Array.isArray(data.items))throw Error('invalid data');
    state.data=data;
    $('updated').textContent='更新 '+shownDate(data.updated_at);
    $('footer-date').textContent='最終収集 '+(data.updated_at||'—');
    document.querySelector('.status-dot').classList.add('ok');refresh();
  }catch(e){$('updated').textContent='読み込みに失敗しました';$('coverage').textContent='データの取得に失敗しました。GitHub Actionsを確認してください。';console.error(e);}
}
for(const id of ['period','brand','source','kind'])$(id).addEventListener('change',()=>{state.limit=40;refresh();});
$('query').addEventListener('input',()=>{state.limit=40;table();});
document.querySelectorAll('.segmented button').forEach(b=>b.addEventListener('click',()=>{
  state.tone=b.dataset.tone;document.querySelectorAll('.segmented button').forEach(x=>x.classList.toggle('active',x===b));state.limit=40;table();
}));
$('more').addEventListener('click',()=>{state.limit+=40;table();});
load();
