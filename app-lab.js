// 先.一四八-1（2026-11-04）：研究室「前向模擬」看板（先.一四七-0）由 app.js 原封不動搬出，研究室點到才載入（首頁首次載入 ≤350KB）。
// 由 app.js 的 hydrateLab() 以 _lazyCall('lab','_labForward') 載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // ══════ 先.一四七-0（2026-11-04，Cowork 收件匣 036 A）研究室「前向模擬」看板 ══════
  // 14 支前向紙上追蹤，每支只讀自己的 data/paper_N.json（追蹤程式寫的 board 欄＋既有摘要欄），前端不寫死任何數字。
  // 下面這份清單只是「要讀哪些檔」，名稱、說明、起跑日、判定日、淨值全部來自檔案；一支壞掉只影響自己那張卡（allSettled）。
  const FWD_FILES=['paper_5','paper_6','paper_7','paper_8','paper_9','paper_10','paper_11','paper_12','paper_13','paper_14','paper_15','paper_16','paper_17','paper_18'];
  const FWD_DD_WARN=30,FWD_DD_ALERT=40;  // 收件匣 036：回撤超過 30% 黃、40% 紅（硬上限 50%）
  let FWD_DOCS=null;
  function _fwClean(t){
    // 資料檔說明裡的佇列編號／試驗編號／程式檔名只放設定頁進階（docs/UI_GLOSSARY.md），卡片上拿掉
    let s=String(t==null?'':t);
    s=s.replace(/[（(][^（()）]*(先[.．]|#\d{3}|\.py|PREREG|常備\.開發)[^（()）]*[）)]/g,'');
    s=s.replace(/#\d{3}\b/g,'').replace(/\bMDD\b/g,'最大跌幅').replace(/天條一/g,'回撤上限').replace(/\bNAV\b/g,'淨值');
    return uiPlain(s);
  }
  function _fwPct(v,sign){if(v==null||isNaN(v))return '—';const x=+v;return (sign&&x>0?'+':'')+x.toFixed(2)+'%'}
  function _fwPctCls(v){return v==null||isNaN(v)?'':(+v>0?'color:var(--up)':(+v<0?'color:var(--down)':''))}
  function _fwYmd(x){return x?String(x).slice(0,10).replace(/-/g,'/'):'—'}
  function _fwDaysTo(d){if(!d)return null;const t=Date.parse(_evYmd(new Date())+'T00:00:00+08:00'),j=Date.parse(String(d).slice(0,10)+'T00:00:00+08:00');return isNaN(j)?null:Math.round((j-t)/86400000)}
  async function _fwFetch(k){
    const r=await fetch('data/'+k+'.json?t='+Math.floor(Date.now()/600000));
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    if(!d||typeof d!=='object'||!d.label)throw new Error('格式不對（缺 label）');
    return d;
  }
  function _fwStatus(d){
    if(d.verdict||d.judged)return 'done';
    return d.started?'run':'wait';
  }
  function _fwNums(d){
    const b=(d.board&&!d.board.error)?d.board:{};
    const init=d.initial_virtual_capital||b.nav_start||null;
    const ret=d.total_return_pct!=null?+d.total_return_pct:((d.nav!=null&&init)?(d.nav/init-1)*100:null);
    const mdd=d.max_drawdown_pct!=null?+d.max_drawdown_pct:(b.max_drawdown_pct!=null?+b.max_drawdown_pct:null);
    const nh=b.n_holdings!=null?b.n_holdings:(Array.isArray(d.holdings)?d.holdings.length:null);
    return {b,init,ret,mdd,nh,navIdx:(d.nav!=null&&init)?d.nav/init*100:null,bench:b.bench_0050_tr_pct!=null?+b.bench_0050_tr_pct:null};
  }
  function _fwChart(b){
    const ns=(b.nav_series||[]).filter(p=>p&&p[1]>0),bm={};(b.bench_0050||[]).forEach(p=>{if(p&&p[1]>0)bm[p[0]]=p[1]});
    if(ns.length<2)return '<div class="note">走勢要累積 2 個交易日以上才畫得出來</div>';
    const n0=ns[0][1],b0d=ns.map(p=>p[0]).find(x=>bm[x]),b0=b0d?bm[b0d]:null;
    const a=ns.map(p=>p[1]/n0*100),bb=ns.map(p=>(b0&&bm[p[0]])?bm[p[0]]/b0*100:null);
    const all=a.concat(bb.filter(x=>x!=null)),mn=Math.min(...all),mx=Math.max(...all),rg=(mx-mn)||1,W=300,H=90,P=6;
    const X=i=>P+i*(W-2*P)/(ns.length-1),Y=v=>H-P-(v-mn)/rg*(H-2*P);
    const pl=arr=>arr.map((v,i)=>v==null?null:X(i).toFixed(1)+','+Y(v).toFixed(1)).filter(Boolean).join(' ');
    return `<svg data-fwd-chart viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" role="img" aria-label="近 30 日淨值與 0050 含息走勢">`+
      `<line x1="0" x2="${W}" y1="${Y(100).toFixed(1)}" y2="${Y(100).toFixed(1)}" stroke="var(--line-zero)" stroke-dasharray="3 3"/>`+
      (bb.some(x=>x!=null)?`<polyline points="${pl(bb)}" fill="none" stroke="var(--ink-3)" stroke-width="1.8"/>`:'')+
      `<polyline points="${pl(a)}" fill="none" stroke="var(--accent)" stroke-width="2.2"/></svg>`+
      `<div class="note" style="margin-top:2px"><b style="color:var(--accent)">━</b> 這支模擬　<b style="color:var(--ink-3)">━</b> 0050 含息　（${_fwYmd(ns[0][0])} 起＝100）</div>`;
  }
  function _fwHoldings(d){
    const esc=_uiEsc;
    if(d.open_position){const p=d.open_position;
      return `<div class="note">持有：台指選擇權 ${esc(p.contract||'')} 月合約、履約價 ${esc(p.strike!=null?p.strike:'—')}，${esc(p.expiry?_fwYmd(p.expiry)+' 到期':'')}${p.wing?`（保護翼 ±${esc(p.wing)} 點）`:''}</div>`}
    const h=Array.isArray(d.holdings)?d.holdings:[];
    if(!h.length)return '<div class="note">目前沒有持股</div>';
    return '<div style="display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-size:var(--fs-sm)">'+
      h.map(x=>`<span>${esc(x.code||'')} ${esc(x.name||'')}</span><span class="num" style="color:var(--ink-3)">${x.weight_pct!=null?(+x.weight_pct).toFixed(1)+'%':(x.since?_fwYmd(x.since)+' 進':'')}</span>`).join('')+'</div>';
  }
  function _fwCard(k,d,err){
    const esc=_uiEsc;
    if(err||!d)return `<div class="fwd-row" data-fwd="${k}" data-fwd-state="missing" style="padding:12px 0;border-bottom:1px solid var(--hairline);min-height:44px"><div style="font-weight:600">${esc(k.replace('paper_','第 ')+' 支')}</div><div class="note">資料尚未產生</div></div>`;
    const st=_fwStatus(d),nm=_fwNums(d),today=_evYmd(new Date());
    const start=d.start_not_before||d.start||null,judge=d.judge_after||null,dj=_fwDaysTo(judge);
    const ddAbs=nm.mdd!=null?Math.abs(nm.mdd):null,lvl=ddAbs==null?'':(ddAbs>=FWD_DD_ALERT?'alert':(ddAbs>=FWD_DD_WARN?'warn':''));
    const stTxt={run:'進行中',wait:'未起跑',done:'已判定'}[st],stCol={run:'var(--accent)',wait:'var(--ink-3)',done:'var(--good)'}[st];
    const bar=lvl==='alert'?'border-left:4px solid var(--critical);padding-left:8px':(lvl==='warn'?'border-left:4px solid var(--warn);padding-left:8px':'');
    const judgeLine=`判定 ${judge?(d.judge_after_estimated?'約 ':'')+_fwYmd(judge):'未定'}${dj!=null?(dj>0?`・還有 ${dj} 天`:'・已到判定日'):''}`;
    let line2='';
    if(st==='wait')line2=(start&&start<=today)?`<div class="note">還沒起跑：${esc(_fwClean(d.why_not_started||d.why||'等起跑條件'))}</div>`:'';
    else if(st==='done')line2=`<div class="note">${esc(_fwClean(d.verdict||d.judged||''))}</div>`;
    else line2=`<div class="num" style="font-size:var(--fs-sm);line-height:1.7">淨值 ${nm.navIdx!=null?nm.navIdx.toFixed(2):'—'}（<span style="${_fwPctCls(nm.ret)}">${_fwPct(nm.ret,1)}</span>）・同期 0050 含息 <span style="${_fwPctCls(nm.bench)}">${_fwPct(nm.bench,1)}</span><br>`+
      `最大跌幅 <span data-fwd-dd="${lvl||'ok'}" style="${lvl==='alert'?'color:var(--critical);font-weight:700':(lvl==='warn'?'color:var(--warn);font-weight:700':'')}">${nm.mdd!=null?_fwPct(nm.mdd):'—'}</span>${lvl?'（上限 50%）':''}・持有 ${nm.nh!=null?nm.nh:'—'} ${d.open_position?'組':'檔'}・資料 ${_fwYmd(d.as_of_date||d.last_date||nm.b.as_of)}</div>`;
    const detail=`<div class="fwd-detail" hidden style="margin-top:8px">`+
      `<div class="note" style="margin-bottom:6px">${esc(_fwClean(d.note||''))}</div>`+
      (st==='run'?_fwChart(nm.b)+`<div style="font-weight:600;margin:8px 0 4px">持股</div>`+_fwHoldings(d)+(nm.b.series_note?`<div class="note" style="margin-top:4px">${esc(_fwClean(nm.b.series_note))}</div>`:''):'')+
      (d.judge?`<details data-ui-detail style="margin-top:6px"><summary style="cursor:pointer;min-height:44px;display:flex;align-items:center">ⓘ 判定規則</summary><div class="note">${esc(_fwClean(d.judge))}</div>${d.known_limit?`<div class="note" style="margin-top:4px">已知限制：${esc(_fwClean(d.known_limit))}</div>`:''}</details>`:'')+
      `</div>`;
    return `<div class="fwd-row" data-fwd="${k}" data-fwd-state="${st}" style="padding:12px 0;border-bottom:1px solid var(--hairline);${bar}">`+
      `<div style="display:flex;justify-content:space-between;gap:8px;align-items:baseline"><span style="font-weight:600">${esc(_fwClean(d.label))}</span><span style="font-size:var(--fs-xs);color:${stCol};white-space:nowrap">${stTxt}</span></div>`+
      line2+`<div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="note" style="margin:0">${esc(start?'起跑 '+_fwYmd(start)+'・':'')}${esc(judgeLine)}</span>`+
      `<button type="button" class="fwd-toggle" aria-expanded="false" style="min-height:44px;min-width:64px;padding:0 10px;border:1px solid var(--hairline);border-radius:var(--r-sm);background:transparent;color:var(--accent);font-size:var(--fs-sm);cursor:pointer;white-space:nowrap">看細節 ›</button></div>`+detail+`</div>`;
  }
  async function _labForward(){
    const el=document.getElementById('lab-forward-list');if(!el)return;
    const rs=await Promise.allSettled(FWD_FILES.map(_fwFetch));
    FWD_DOCS={};
    const cnt={run:0,wait:0,done:0,missing:0};
    el.innerHTML=rs.map((r,i)=>{
      const k=FWD_FILES[i];
      if(r.status==='rejected'){console.warn('[labForward] '+k,r.reason);recordGlobalError('labForward:'+k,r.reason);cnt.missing++;return _fwCard(k,null,r.reason)}
      FWD_DOCS[k]=r.value;
      try{cnt[_fwStatus(r.value)]++;return _fwCard(k,r.value)}
      catch(e){console.warn('[labForward] '+k,e);recordGlobalError('labForward:'+k,e);cnt.missing++;return _fwCard(k,null,e)}
    }).join('');
    const sm=document.getElementById('lab-forward-summary');
    if(sm)sm.textContent=`共 ${FWD_FILES.length} 支：進行中 ${cnt.run}、未起跑 ${cnt.wait}、已判定 ${cnt.done}${cnt.missing?`、資料尚未產生 ${cnt.missing}`:''}`;
    el.querySelectorAll('.fwd-toggle').forEach(b=>b.addEventListener('click',()=>{
      try{const det=b.closest('.fwd-row').querySelector('.fwd-detail');if(!det)return;det.hidden=!det.hidden;b.setAttribute('aria-expanded',String(!det.hidden));b.textContent=det.hidden?'看細節 ›':'收起'}
      catch(e){console.warn('[labForward toggle]',e);recordGlobalError('labForwardToggle',e)}
    }));
  }
