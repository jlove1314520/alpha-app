// 常備.開發-20 丙案（2026-10-11 先.六十五）：交易頁專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('trade') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // 2026-09-10（深讀一.3）影子帳本狀態要秀MDD／交易數，但後端equity_curve/ledger
  // 沒有現成欄位，兩個都用前端從真實cum_return_pct序列/逐日買賣明細算出來，不補假值。
  function calcEquityCurveMddPct(curve){
    if(!curve||curve.length<1)return null;
    let peak=0,mdd=0; // cum_return_pct=0視為起點淨值基準100
    for(const p of curve){
      const v=p.cum_return_pct;
      if(v==null)continue;
      if(v>peak)peak=v;
      const dd=(1+v/100)/(1+peak/100)*100-100;
      if(dd<mdd)mdd=dd;
    }
    return mdd;
  }
  function calcLedgerTradeCount(ledger){
    if(!ledger||!ledger.length)return 0;
    return ledger.reduce((n,e)=>n+(e.buys||[]).length+(e.sells||[]).length,0);
  }
  function onTradeInit(){renderMktToggle('trade');onTradeToggleChange();_safeAsync('loadTradeBots',loadTradeBots)}
  function autoLastResultText(lr){
    if(!lr)return '尚無紀錄';
    const c=lr.counts||{};
    const parts=Object.keys(c).map(k=>_autoStatusTxt(k)+' '+c[k]);
    return String(lr.date||'').slice(5).replace('-','/')+' '+(lr.batch||'')+'：'+parts.join('、')+(lr.reason_codes&&lr.reason_codes.length?'（'+_autoCodesTxt(lr.reason_codes)+'）':'');
  }
  // 先.七十八-2：「明天會買」——晚間唯讀預檢算出的下一期計畫（純計算，非委託）。可用餘額只顯示夠／不足。
  function renderPlanPreview(pv){
    const el=document.getElementById('bot-plan-preview');if(!el)return;
    if(!pv||!(pv.orders||pv.error)){el.hidden=true;el.innerHTML='';return}
    const esc=_autoEsc,n=v=>Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
    if(pv.error){el.hidden=false;el.innerHTML=`<div class="note">明天會買：算不出來（${esc(pv.error)}）</div>`;return}
    const rows=(pv.orders||[]).map(o=>`<div class="plan-row" style="display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:3px 0;border-bottom:1px solid var(--hairline)">`+
      `<span>${esc(o.symbol)} ${o.lot==='IntradayOdd'?'零股':'整股'} ${n(o.qty)} 股</span><span>限價 ${n(o.limit_price)}${o.dev_pct!=null?`（昨收上限 +${n(o.dev_pct)}%）`:''}　${n(o.amount)} 元 ${o.cap_ok?'✓':'⚠ 超過單筆上限'}</span></div>`).join('');
    const cash=pv.available_ok===true?'夠':pv.available_ok===false?'不足':'未知';
    el.hidden=false;
    el.innerHTML=`<div style="font-weight:600;font-size:13px;margin-bottom:4px">明天會買（${esc(pv.label||'')}）</div>${rows}`+
      `<div class="note" data-ui-keep style="margin-top:4px">合計含緩衝 ${n(pv.need_with_buffer)} 元；可用餘額：${cash}</div>`+
      `<div class="note" data-ui-keep style="margin-top:2px;color:var(--ink-3)">預覽，非委託；明早依平盤價重算</div>`;
  }
  async function loadTradeBots(){
    const note=document.getElementById('bot-bb90-note'),rec=document.getElementById('bot-recent-orders');
    if(!note)return;
    if(!LIVE.configured||!LIVE.url){note.textContent='連上電腦才看得到';if(rec)rec.textContent='連上電腦才看得到';return}
    try{
      const r=await liveFetch('/auto/status',6000);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      setTxt('bot-mode',(d.drill?'演練 · ':'')+(AUTO_MODE_LABEL[d.mode]||d.mode||'—'));
      setTxt('bot-next',autoNextText(d));
      setTxt('bot-last',autoLastResultText(d.last_result));
      const st=d.status||{};
      const fz=autoFreezeText(d),fp=autoFlowPlanText(d);
      const card=document.getElementById('bot-freeze');
      if(card){card.hidden=!(fz||fp);card.textContent=fz?('⏸ '+fz):fp;card.dataset.state=fz?'frozen':(fp?'plan':'')}
      note.textContent=(fz?'':(d.stopped?'⛔ 緊急停止中（一律拒單）　':''))+(st.last_error?'最近錯誤：'+st.last_error:'目前無錯誤')+(st.updated_at?'　狀態更新：'+st.updated_at:'');
      _safeSync('renderPlanPreview',()=>renderPlanPreview(st.t1_plan_preview));
    }catch(e){console.warn('[loadTradeBots]',e);recordGlobalError('loadTradeBots',e);
      // 先.八十-2：電腦離線時整張卡收成一行，帳本與預覽都不再各自報錯
      if(_isOfflineErr(e)){note.textContent=liveOfflineText();if(rec)rec.hidden=true;_safeSync('renderPlanPreview',()=>renderPlanPreview(null));return}
      note.textContent='讀取自動交易狀態失敗（本機伺服器是舊版或回應錯誤）'}
    if(rec)rec.hidden=false;
    if(!rec)return;
    try{
      const lg=await loadAutoLedger();
      const rows=(lg&&lg.rows||[]).slice(0,5);
      rec.innerHTML=rows.length?rows.map(autoLedgerRowHtml).join(''):'首批尚未執行';
    }catch(e){console.warn('[loadTradeBots ledger]',e);recordGlobalError('loadTradeBots ledger',e);rec.textContent=_isOfflineErr(e)?liveOfflineText():'讀取帳本失敗（本機伺服器是舊版或回應錯誤）'}
  }

  // ── 交易頁子分頁（機器人／策略，2026-08-25 新增，不佔用底部導覽）──
  document.querySelectorAll('#trade-tabs button').forEach(b=>{
    b.addEventListener('click',()=>{
      if(b.dataset.sub==='journal'){go('journal');return}  // 先.一一二-1：日誌併入交易頁成為子分頁，內容仍在日誌頁
      document.querySelectorAll('#trade-tabs button').forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
      document.getElementById('trade-sub-bots').classList.remove('active');
      document.getElementById('trade-sub-strategy').classList.remove('active');
      document.getElementById('trade-sub-monitor').classList.remove('active');
      document.getElementById('trade-sub-picks').classList.remove('active');
      document.getElementById('trade-sub-'+b.dataset.sub).classList.add('active');
      if(b.dataset.sub==='strategy'){loadStrategies();loadPaper7030();}
      if(b.dataset.sub==='monitor')loadStrategyMonitor();
      if(b.dataset.sub==='bots')_safeAsync('loadTradeBots',loadTradeBots);
      if(b.dataset.sub==='picks'){loadPicksReportCard();_safeAsync('loadNonEtfLines',loadNonEtfLines)}
    });
  });
  // 2026-08-25 新增：策略紙上前測系統。目前沒有任何策略通過完整驗證(含holdout解鎖)，
  // data/paper_trades.json 的 strategies 是空陣列，這裡誠實顯示「目前無上架策略」，
  // 不放任何示範/假績效。完整架構規格見 research/PAPER_TRADING_ARCHITECTURE.md
  // （JSON格式、事前產生訊號不可回填的鐵律、每日排程流程）。
  function strategyCardHtml(s){
    const m=s.metrics||{};
    return `<div class="card press" style="cursor:pointer" onclick="openStrategyReport('${String(s.id||'').replace(/[^\w.-]/g,'')}')">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
        <div><b style="font-size:15px">${s.name||s.id}</b><div class="note" style="margin-top:2px">${s.market||'—'} · 上架 ${s.listed_date||'—'} · 前測起始 ${s.paper_start_date||'—'}</div></div>
      </div>
      <div class="bot-stats" style="margin-top:10px">
        <div class="s"><span>累計報酬</span><b class="${(m.cum_return_pct||0)>=0?'pos':'neg'}">${m.cum_return_pct!=null?(m.cum_return_pct>=0?'+':'')+m.cum_return_pct.toFixed(1)+'%':'—'}</b></div>
        <div class="s"><span>MDD</span><b>${m.mdd_pct!=null?m.mdd_pct.toFixed(1)+'%':'—'}</b></div>
        <div class="s"><span>Sortino</span><b>${m.sortino!=null?m.sortino.toFixed(2):'—'}</b></div>
        <div class="s"><span>交易筆數</span><b>${m.n_trades??0}</b></div>
      </div>
      <div class="note" style="margin-top:8px">目前部位：${s.current_position||'無'}</div>
    </div>`;
  }
  function _paperNextRebalance(asOf){
    try{
      const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(asOf||'');if(!m)return null;
      const lastWd=(y,mo)=>{const d=new Date(Date.UTC(y,mo,0));while(d.getUTCDay()===0||d.getUTCDay()===6)d.setUTCDate(d.getUTCDate()-1);return d;};
      const iso=d=>d.toISOString().slice(0,10);
      let y=+m[1],mo=+m[2],d=lastWd(y,mo);
      if(iso(d)<=asOf){mo+=1;if(mo>12){mo=1;y+=1;}d=lastWd(y,mo);}
      return iso(d);
    }catch(e){console.warn('[_paperNextRebalance]',e);recordGlobalError('_paperNextRebalance',e);return null;}
  }
  function _paperCardHtml(title,sub,rowsHtml){
    return '<div class="card" style="margin:0;padding:10px;min-width:0">'
      +'<b style="font-size:13px;line-height:1.3;display:block">'+_paperEsc(title)+'</b>'
      +'<div class="note" style="margin-top:2px;font-size:11px">'+_paperEsc(sub)+'</div>'
      +rowsHtml+'</div>';
  }
  function _paperRow(k,v,cls){
    return '<div style="display:flex;justify-content:space-between;gap:6px;margin-top:6px;font-size:12px"><span class="note" style="margin:0">'+_paperEsc(k)+'</span><b class="'+(cls||'')+'" style="text-align:right">'+v+'</b></div>';
  }
  // 先.一〇三-5：累積報酬與資料日改讀 data/strategy_curves.json（與首頁「跟 0050 比」、週覆盤同一份）；
  // 讀不到才退回各自 paper_*.json 的數字，並在卡上標來源。
  let _PAPER_SC=null;
  function _paperScLine(id){return _PAPER_SC&&id?(_PAPER_SC.lines||[]).find(x=>x.id===id&&x.started)||null:null}
  function _paperCommonRows(j,weightsHtml,scId){
    const ln=_paperScLine(scId);
    const ret=ln?(ln.metrics||{}).cum_pct:j.total_return_pct;
    const asOf=ln?ln.as_of:j.as_of_date;
    const nx=_paperNextRebalance(j.as_of_date);
    return _paperRow(ln?'NAV（月底記帳）':'NAV',j.nav!=null?Math.round(j.nav).toLocaleString():'—')
      +_paperRow('累積報酬',ret!=null?(ret>=0?'+':'')+Number(ret).toFixed(2)+'%':'—',(ret||0)>=0?'pos':'neg')
      +_paperRow('目前權重',weightsHtml)
      +_paperRow('下次再平衡',nx?_paperEsc(nx)+'<span class="note" style="margin:0 0 0 3px">預計</span>':'—')
      +'<div class="note" style="margin-top:6px;font-size:11px">截至 '+_paperEsc(asOf||'—')+' · 已記'+(j.history_months||0)+'筆'+(ln?'':(scId?' · 報酬取自帳本檔（跟 0050 比資料未就緒）':''))+'</div>';
  }
  async function _fetchPaperJson(url){
    const r=await fetch(url+'?t='+Date.now());
    if(!r.ok)return {started:false};
    return await r.json();
  }
  async function _renderPaper7030(){
    try{
      const j=await _fetchPaperJson('data/paper_7030.json');
      if(!j.started)return _paperCardHtml('模擬 A 穩健','0050＋定存','<div class="note" style="margin-top:8px">'+_paperEsc(j.note||'尚未啟動：預定2026-10第一個交易日起')+'</div>');
      const w=(j.stock_weight!=null?'0050 '+(j.stock_weight*100).toFixed(0)+'%':'—')+' / 定存 '+(j.bond_weight!=null?(j.bond_weight*100).toFixed(0)+'%':'—');
      return _paperCardHtml('模擬 A 穩健','0050 70% · 定存 30%',_paperCommonRows(j,w,'paper_1'));
    }catch(e){
      console.warn('[_renderPaper7030]',e);recordGlobalError('_renderPaper7030',e);
      return _paperCardHtml('模擬 A 穩健','0050＋定存','<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
    }
  }
  async function _renderPaper1b(){
    try{
      const j=await _fetchPaperJson('data/paper_1b.json');
      if(!j.started)return _paperCardHtml('模擬 D 三檔分散','0050 45% · 00646 45% · 00697B 10%','<div style="margin-top:10px;font-size:14px;font-weight:700;color:var(--warn)">2026-11-02 啟動</div><div class="note" style="margin-top:4px;font-size:11px">啟動前不顯示任何數字</div>');
      const wp=j.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml('模擬 D 三檔分散','0050 / 00646 / 00697B',_paperCommonRows(j,w||'—','paper_1b'));
    }catch(e){
      console.warn('[_renderPaper1b]',e);recordGlobalError('_renderPaper1b',e);
      return _paperCardHtml('模擬 D 三檔分散','0050 / 00646 / 00697B','<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
    }
  }
  // 2026-10-07（先.四十七-二）：紙.三 S3-C6（信用利差危機閘門×槓桿版 Bb-90 C6）前進式紙上追蹤。
  // 只讀 data/paper_3.json；顯示虛擬淨值、閘門目前狀態（BAA10Y 月底值 vs 12 個月底平均）、與 Bb-90／0050 對照。
  function _paperGateHtml(g,pend){
    if(!g)return '—';
    const st=g.gate_open?'<span class="pos">開（持有槓桿腿）</span>':'<span class="neg">關（槓桿腿改持現金）</span>';
    let t=st+'<div class="note" style="margin:2px 0 0;font-size:11px">'+_paperEsc(g.month_end)+' BAA10Y '+_paperEsc(g.baa10y)+'％ vs 12月平均 '+_paperEsc(g.avg12)+'％</div>';
    if(pend)t+='<div class="note" style="margin:2px 0 0;font-size:11px;color:var(--warn)">已判定下個交易日切換為「'+(pend.to_open?'開':'關')+'」</div>';
    return t;
  }
  async function _renderPaper3(){
    const title='模擬 B 景氣閘門',sub='00631L/00647L 各25%·0050/00646 各15%·00697B 20%（閘門關時2倍腿改現金）';
    try{
      const j=await _fetchPaperJson('data/paper_3.json');
      const err=j.last_error?'<div class="note" style="margin-top:6px;font-size:11px;color:var(--down,#e5534b)">最近一次未記帳：'+_paperEsc(j.last_error.reason||j.last_error.status)+'</div>':'';
      // 先.四十八 二：樣本外警示（#428，數字已以結果檔程式核對）
      const oos='<div class="note" style="margin-top:6px;font-size:11px;color:var(--warn)">⚠ 樣本外（2025-01～2026-09，#428）：閘門 21 個持有月中 13 個月關閉，累積 +41.9%，落後 Bb-90 34.3pp、落後 0050 96.6pp。21 個月檢定力低，好壞都不構成證明。模擬 B 期間若閘門關閉占比 >50% 且落後 Bb-90 >10pp，進槓桿階段 1 須總司令另行裁示。</div>';
      if(!j.started)return _paperCardHtml(title,sub,_paperRow('閘門目前',_paperGateHtml(j.gate_now,null))+'<div style="margin-top:8px;font-size:14px;font-weight:700;color:var(--warn)">2026-10 月底建倉</div><div class="note" style="margin-top:4px;font-size:11px">建倉前不顯示淨值</div>'+err+oos);
      const sg=v=>v==null?'—':(v>=0?'+':'')+Number(v).toFixed(2)+'%';
      const wp=j.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k==='CASH'?'現金':k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml(title,sub,
        _paperRow('閘門目前',_paperGateHtml(j.gate_now,j.pending_switch))
        +_paperCommonRows(j,w||'—','paper_3')
        +_paperRow('對照 Bb-90（同日起算）',sg(j.bench_bb90_return_pct))
        +_paperRow('對照 0050 全持有',sg(_paperScLine('paper_3')?(_paperScLine('paper_3').metrics||{}).bench_cum_pct:j.bench_0050_return_pct))+err+oos+_paperKillHtml());
    }catch(e){
      console.warn('[_renderPaper3]',e);recordGlobalError('_renderPaper3',e);
      return _paperCardHtml(title,sub,'<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
    }
  }
  // 2026-10-10（先.五十九-A1／A2）：紙.四 R1（0050＋信用利差閘門×00631L），R1-C 為主、R1-A 並列。
  // 只讀 data/paper_4.json（兩本帳）與 data/paper_3.json（對照紙.三累積報酬）；揭露文字固定顯示。
  // 先.八十一-5（2026-10-13 總司令裁示①）：模擬 B（紙.三 S3-C6）／模擬 C（紙.四 R1）共用的信用利差閘門在 1990–2003 殺測失敗，
  // 繼續紙上追蹤但不再是真錢候選。試驗編號照裁示原文保留——用 data-ui-cite 標成引用，前台用詞守門與文案稽核不改寫、不計違規。
  const PAPER_KILL_LABEL='閘門殺測失敗（#435/#436），不再是真錢候選';
  const _paperKillHtml=()=>'<div class="note paper-kill" data-ui-cite data-ui-keep style="margin-top:6px;font-size:11.5px;font-weight:600;color:var(--critical,#e5534b)">⛔ '+PAPER_KILL_LABEL+'</div>';
  const PAPER4_DISCLOSURE='看過 2025–26 結果後才設計；回測 2003–2024 年化 15.1%／MDD −36.2%；同一閘門在 2025–26 樣本外 21 個月中有 13 個月關閉並大幅落後 0050；無樣本外驗證，僅紙上追蹤';
  async function _renderPaper4(){
    const title='模擬 C 加速',sub='主：R1-C 0050 50%＋00631L 50%｜並列：R1-A 70%／30%（閘門關時 00631L 改現金）';
    const disc='<div class="note" id="paper4-disclosure" style="margin-top:6px;font-size:11px;color:var(--warn)">⚠ '+_paperEsc(PAPER4_DISCLOSURE)+'。</div>'+_paperKillHtml();
    try{
      const [j,p3]=await Promise.all([_fetchPaperJson('data/paper_4.json'),_fetchPaperJson('data/paper_3.json').catch(e=>{console.warn('[_renderPaper4] paper_3',e);return {started:false}})]);
      const err=j.last_error?'<div class="note" style="margin-top:6px;font-size:11px;color:var(--down,#e5534b)">最近一次未記帳：'+_paperEsc(j.last_error.reason||j.last_error.status)+'</div>':'';
      if(!j.started||!j.books)return _paperCardHtml(title,sub,_paperRow('閘門目前',_paperGateHtml(j.gate_now,null))+'<div style="margin-top:8px;font-size:14px;font-weight:700;color:var(--warn)">2026-10 月底建倉（與模擬 B 同日）</div><div class="note" style="margin-top:4px;font-size:11px">建倉前不顯示淨值</div>'+err+disc);
      const sg=v=>v==null?'—':(v>=0?'+':'')+Number(v).toFixed(2)+'%';
      const pri=j.books[j.primary||'R1-C']||Object.values(j.books)[0];
      const a=j.books['R1-A'];
      const wp=pri.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k==='CASH'?'現金':k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml(title,sub,
        _paperRow('閘門目前',_paperGateHtml(j.gate_now,pri.pending_switch))
        +_paperCommonRows(Object.assign({},pri,{history_months:pri.rows}),w||'—','paper_4')
        +(a?_paperRow('並列 R1-A（70/30）',sg(a.total_return_pct)):'')
        +_paperRow('對照 0050 全持有',sg(_paperScLine('paper_4')?(_paperScLine('paper_4').metrics||{}).bench_cum_pct:pri.bench_0050_return_pct))
        +_paperRow('對照 Bb-90（同日起算）',sg(pri.bench_bb90_return_pct))
        +_paperRow('對照 模擬 B',_paperScLine('paper_3')?sg((_paperScLine('paper_3').metrics||{}).cum_pct):(p3&&p3.started?sg(p3.total_return_pct):'—'))+err+disc);
    }catch(e){
      console.warn('[_renderPaper4]',e);recordGlobalError('_renderPaper4',e);
      return _paperCardHtml(title,sub,'<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>'+disc);
    }
  }
  async function loadPaper7030(){
    const el=document.getElementById('paper-7030-card');if(!el)return;
    try{
      try{const r=await fetch('data/strategy_curves.json?t='+Math.floor(Date.now()/60000));_PAPER_SC=r.ok?await r.json():null}
      catch(e){console.warn('[loadPaper7030] strategy_curves',e);recordGlobalError('loadPaper7030.strategy_curves',e);_PAPER_SC=null}
      const [a,b,c,d]=await Promise.all([_renderPaper7030(),_renderPaper1b(),_renderPaper3(),_renderPaper4()]);
      el.innerHTML='<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:10px">'+a+b+'<div style="grid-column:1 / -1">'+c+'</div><div style="grid-column:1 / -1" id="paper4-card">'+d+'</div></div>'
        +'<div class="note" style="margin:-4px 0 10px;text-align:center;color:var(--warn)">⚠ 紙上追蹤：虛擬帳戶，未使用真實資金。</div>';
    }catch(e){
      console.warn('[loadPaper7030]',e);recordGlobalError('loadPaper7030',e);
      el.innerHTML='<div class="note">載入失敗：'+_paperEsc(e.message)+'</div>';
    }
  }

  async function loadStrategies(){
    const el=document.getElementById('strategy-list');if(!el)return;
    try{
      const r=await fetch('data/paper_trades.json?t='+Date.now());
      const json=r.ok?await r.json():{strategies:[]};
      const list=json.strategies||[];
      if(!list.length){
        el.innerHTML=`<div class="card" style="text-align:center;padding:28px 16px">
          <div style="font-size:32px;margin-bottom:10px">📋</div>
          <div style="font-weight:700;margin-bottom:6px">目前無上架策略，等待驗證通過</div>
          <div class="note">只有通過完整驗證（含最後一段保留驗證資料的測試）的策略才會上架這裡。研究進度看「策略監控台」分頁。</div>
        </div>`;
        return;
      }
      el.innerHTML=list.map(strategyCardHtml).join('');
    }catch(e){
      console.warn('[loadStrategies]',e);recordGlobalError('loadStrategies',e);
      el.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
    }
  }

  // 2026-08-29策略監控台升級（簡約卡片＋前向績效曲線＋點進看明細＋排行）：
  // 卡片本身只放「策略名/狀態徽章/主數字(forward_return_todate)/sparkline/
  // 樣本不足小標」，原本卡片上的長段文字說明全部移到點開的詳情區塊。排序
  // 由後端(generate_strategies_json.py)決定，這裡純粹依陣列順序渲染，不
  // 額外排序。曲線只用data/strategy_performance.json的真實equity_curve，
  // 不得畫假線——沒有forward_paper就不畫曲線，顯示「尚無前向數據」而不是
  // 補一條假的平線。
  const STRATEGY_STATUS_COLOR={
    '回測通過':'var(--good)','回測未通過':'var(--critical)','回測中':'var(--warn)',
    '紙上交易中':'var(--accent)','規格完成':'var(--ink-2)','草稿':'var(--ink-3)',
  };
  function strategyDetailHtml(s){
    const fp=s.forward_paper;
    let html='';
    if(fp){
      const fpMdd=calcEquityCurveMddPct(fp.equity_curve);
      const fpTrades=calcLedgerTradeCount(fp.ledger);
      const fpRet=fp.forward_return_todate_pct;
      html+=`<div class="bot-stats" style="margin-bottom:8px">
        <div class="s"><span>起始日</span><b>${fp.inception_date||'—'}</b></div>
        <div class="s"><span>累積報酬</span><b class="${(fpRet||0)>=0?'pos':'neg'}">${fpRet!=null?(fpRet>=0?'+':'')+fpRet.toFixed(2)+'%':'—'}</b></div>
        <div class="s"><span>MDD</span><b>${fpMdd!=null?fpMdd.toFixed(1)+'%':'—'}</b></div>
        <div class="s"><span>交易數</span><b>${fpTrades}</b></div>
      </div>`;
      html+=`<div class="note" style="margin-bottom:8px">前向模擬起始：${fp.inception_date||'—'} · 累積交易日：${fp.trading_days_count??'—'}天`
           +`${fp.sample_sufficient?'':'（未達20天樣本門檻，數字仍在累積中）'}</div>`;
      if(fp.ledger&&fp.ledger.length){
        const recent=fp.ledger.slice(-10).slice().reverse();
        html+=`<div style="font-size:11px;font-weight:600;color:var(--ink-2);margin-bottom:4px">每日進出明細（最近${recent.length}筆，逐日累積不可回填）</div>`;
        html+=recent.map(e=>{
          const pnl=e.daily_pnl_pct;
          return `<div class="note" style="padding:4px 0;border-bottom:1px solid var(--hairline)">
            ${e.date} · 買${(e.buys||[]).length}檔/賣${(e.sells||[]).length}檔 · 當日<b class="${(pnl||0)>=0?'pos':'neg'}">${pnl!=null?(pnl>=0?'+':'')+pnl.toFixed(2)+'%':'—'}</b> · 持股${e.n_holdings??'—'}檔
          </div>`;
        }).join('');
      }
    }else{
      html+=`<div class="note" style="color:var(--ink-3)">尚無前向模擬資料（這個策略沒有每日更新的評分引擎可以模擬）</div>`;
    }
    if(s.backtest){
      const b=s.backtest;
      html+=`<div class="note" style="margin-top:10px;padding:8px;background:rgba(250,178,25,.08);border:1px solid rgba(250,178,25,.25);border-radius:8px">
        ⚠ 以下是歷史回測結果，不是前向模擬，不代表未來績效<br>
        年化(VAL)=${b['年化報酬_validation_pct']!=null?b['年化報酬_validation_pct'].toFixed(1)+'%':'—'} ·
        Sharpe×0.7=${b['sharpe_x0.7']!=null?b['sharpe_x0.7'].toFixed(2):'—'} ·
        MDD=${b['mdd_pct']!=null?b['mdd_pct'].toFixed(1)+'%':'—'} ·
        alpha p值=${b['alpha_p值']!=null?b['alpha_p值'].toFixed(4):'—'}（${b['alpha顯著']?'顯著':'不顯著'}）·
        期間=${b['期間']||'—'}
      </div>`;
    }else if(s.trials_summary){
      const t=s.trials_summary;
      html+=`<div class="note" style="margin-top:10px;padding:8px;background:rgba(208,59,59,.08);border-radius:8px">
        已測試 <b>${t['已測試假說數']??'—'}</b> 個策略假說，通過統計驗證 <b>${t['通過統計驗證數']??'—'}</b> 個 —— 誠實記錄，不是還沒開始做
      </div>`;
    }else if(s.status!=='回測中'){
      html+=`<div class="note" style="margin-top:10px;color:var(--ink-3)">尚未回測</div>`;
    }
    if(s.limitations&&s.limitations.length){
      html+=`<div style="font-size:11px;font-weight:600;color:var(--ink-2);margin-top:10px;margin-bottom:4px">局限說明</div>`;
      html+=`<div class="note" style="color:var(--ink-3);font-size:11px;line-height:1.6">${s.limitations.map(l=>'• '+l).join('<br>')}</div>`;
    }
    html+=`<div class="note" style="margin-top:8px;font-size:10px">規格：${s.spec||'—'}<br>最後更新：${s.last_updated?fmtTzMMDDHHMM(new Date(s.last_updated),'Asia/Taipei'):'—'}</div>`;
    return html;
  }
  function strategyMonitorCardHtml(s,idx){
    const color=STRATEGY_STATUS_COLOR[s.status]||'var(--ink-3)';
    const fp=s.forward_paper;
    const ret=fp&&fp.forward_return_todate_pct!=null?fp.forward_return_todate_pct:null;
    const mainNumHtml=ret!=null
      ?`<b class="${ret>=0?'pos':'neg'}" style="font-size:22px">${ret>=0?'+':''}${ret.toFixed(2)}%</b>`
      :`<b style="font-size:14px;color:var(--ink-3)">尚無前向數據</b>`;
    const curve=(fp&&fp.equity_curve)?fp.equity_curve.map(p=>p.cum_return_pct):[];
    const up=curve.length>1?curve[curve.length-1]>=curve[0]:true;
    const sparkHtml=curve.length>=2?spark(curve,up):'';
    const sampleTag=(fp&&!fp.sample_sufficient)
      ?`<div class="note" style="color:var(--warn);font-size:10px;margin-top:2px">樣本不足(&lt;20交易日，目前${fp.trading_days_count}天)，排名僅供參考</div>`:'';
    const cardId=`sm-detail-${idx}`;
    return `<div class="card press" data-sid="${String(s.id||'').replace(/[^\w.-]/g,'')}" style="cursor:pointer" onclick="toggleStrategyDetail('${cardId}')">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
        <div style="flex:1;min-width:0">
          <b style="font-size:15px">${s.name||s.id}</b>
          <div style="margin-top:4px">${mainNumHtml}</div>
          ${sampleTag}
        </div>
        <div style="flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-end;gap:6px">
          <span style="padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;color:${color};border:1px solid ${color}">${s.status}</span>
          ${sparkHtml}
        </div>
      </div>
      <div id="${cardId}" style="display:none;margin-top:12px;border-top:1px solid var(--hairline);padding-top:12px">
        ${strategyDetailHtml(s)}
      </div>
    </div>`;
  }
  // 先.六十-A2：策略卡點下去 → 切到「策略監控台」並展開同一策略的報告段落（回測／前向／局限說明）
  async function openStrategyReport(id){
    try{
      const btn=document.querySelector('#trade-tabs button[data-sub="monitor"]');if(btn)btn.click();
      await loadStrategyMonitor();
      const card=document.querySelector('#strategy-monitor-list [data-sid="'+id+'"]');
      if(!card){const el=document.getElementById('strategy-monitor-list');if(el)uiScrollIntoView(el);return}  // 先.八十-6：監控台改用曲線檔的線編號，對不到就停在清單頂端
      const det=card.querySelector('[id^="sm-detail-"]');if(det)det.style.display='';
      uiScrollIntoView(card);
    }catch(e){console.warn('[openStrategyReport]',e);recordGlobalError('openStrategyReport',e)}
  }
  function toggleStrategyDetail(id){
    const el=document.getElementById(id);if(!el)return;
    el.style.display=el.style.display==='none'?'':'none';
    if(el.style.display!=='none')el.querySelectorAll('[data-holdings-src]:not([data-loaded])').forEach(h=>{_safeAsync('loadPaperHoldings',()=>loadPaperHoldings(h))});
  }
  // 先.一一八-2c（2026-10-18）：模擬 G 卡片點開看持股明細（讀曲線檔指定的摘要檔 holdings；不寫死、未開始照實寫原因）
  async function loadPaperHoldings(el){
    el.setAttribute('data-loaded','1');
    const esc=_autoEsc;
    try{
      const r=await fetch(el.getAttribute('data-holdings-src')+'?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const j=await r.json(),hs=j.holdings||[];
      const head=`<div style="font-size:11px;font-weight:600;color:var(--ink-2);margin:10px 0 4px">持股明細</div>`;
      if(!j.started||!hs.length){el.innerHTML=head+`<div class="note">${esc(j.why_not_started||'還沒有持股')}</div>`;return}
      el.innerHTML=head+`<div class="note" style="margin-bottom:4px">上次再平衡 ${esc(j.last_rebalance||'—')} · 下次 ${esc(j.next_rebalance_month||'—')} · 共 ${hs.length} 檔（點股票看個股）</div>`
        +hs.map(h=>`<div style="display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid var(--hairline);font-size:12px;cursor:pointer" onclick="event.stopPropagation();openStock('${String(h.code||'').replace(/[^0-9A-Za-z]/g,'')}')">`
          +`<span>${h.rank_at_rebalance!=null?esc(h.rank_at_rebalance)+'. ':''}${esc(h.name||'')} <span class="note">${esc(h.code)}</span></span>`
          +`<span class="note" style="margin:0;text-align:right">${h.weight_pct!=null?Number(h.weight_pct).toFixed(1)+'%':'—'} · 營收 ${esc(String(h.rev_month||'—').replace('-','/'))} · ${esc(String(h.since||'').slice(5).replace('-','/'))} 起</span></div>`).join('')
        +((j.last_entered||[]).length||(j.last_exited||[]).length?`<div class="note" style="margin-top:4px">這次新進 ${(j.last_entered||[]).length} 檔、出場 ${(j.last_exited||[]).length} 檔</div>`:'');
    }catch(e){console.warn('[loadPaperHoldings]',e);recordGlobalError('loadPaperHoldings',e);el.innerHTML='<div class="note">持股明細讀不到：'+esc(e.message)+'</div>'}
  }
  // 先.八十-6（2026-10-12）：策略監控台改讀 data/strategy_curves.json（與首頁「跟 0050 比」同一份、同一套名稱與口徑），
  // 停用 data/strategy_performance.json（舊前向紙上績效，與紙上追蹤口徑不一致）。名稱照檔內 label（UI_GLOSSARY 定案名），
  // 不在前台再自己命名；主數字＝累積報酬，旁邊同時列同期 0050；未開始的線只寫一行原因，不畫空白圖。
  function smPct(v){return v==null?'—':(v>0?'+':'')+Number(v).toFixed(2)+'%'}
  function strategyCurveMonitorCardHtml(l,idx){
    const m=l.metrics||{},started=l.started&&(l.nav||[]).length>0;
    const color=STRATEGY_STATUS_COLOR[l.status]||'var(--ink-3)';
    const nav=(l.nav||[]).map(Number).filter(v=>isFinite(v));
    const sparkHtml=nav.length>=2?spark(nav,nav[nav.length-1]>=nav[0]):'';
    const main=started
      ?`<b class="${(m.cum_pct||0)>=0?'pos':'neg'}" style="font-size:22px">${smPct(m.cum_pct)}</b><span class="note" style="margin-left:6px">0050 ${smPct(m.bench_cum_pct)}</span>`
      :`<b style="font-size:14px;color:var(--ink-3)">${_autoEsc(l.note||'尚未開始')}</b>`;
    const cardId=`sm-detail-${idx}`;
    const det=started?`<div class="bot-stats" style="margin-bottom:8px">
        <div class="s"><span>起始日</span><b>${_autoEsc(l.start_date||'—')}</b></div>
        <div class="s"><span>交易日</span><b>${m.days??'—'}</b></div>
        <div class="s"><span>最大跌幅</span><b>${m.mdd_pct!=null?Number(m.mdd_pct).toFixed(1)+'%':'—'}</b></div>
        <div class="s"><span>0050 最大跌幅</span><b>${m.bench_mdd_pct!=null?Number(m.bench_mdd_pct).toFixed(1)+'%':'—'}</b></div>
      </div>
      <div class="note">判定：${_autoEsc(m.verdict||'—')}（資料到 ${_autoEsc(l.as_of||'—')}）</div>
      <div class="note" data-ui-explain style="margin-top:4px">${_autoEsc(l.note||'')}</div>`
      :`<div class="note">${_autoEsc(l.why||l.note||'尚未開始')}</div>`;
    const hold=l.holdings_file?`<div data-holdings-src="${_autoEsc(l.holdings_file)}" onclick="event.stopPropagation()"><div class="note" style="margin-top:8px">持股明細載入中…</div></div>`:'';
    return `<div class="card press" data-sid="${String(l.id||'').replace(/[^\w.-]/g,'')}" style="cursor:pointer" onclick="toggleStrategyDetail('${cardId}')">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
        <div style="flex:1;min-width:0">
          <b style="font-size:15px">${_autoEsc(l.label||l.id)}</b>
          <div style="margin-top:4px">${main}</div>
        </div>
        <div style="flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-end;gap:6px">
          <span style="padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;color:${color};border:1px solid ${color}">${_autoEsc(l.status||'')}</span>
          ${sparkHtml}
        </div>
      </div>
      <div id="${cardId}" style="display:none;margin-top:12px;border-top:1px solid var(--hairline);padding-top:12px">${det}${hold}</div>
    </div>`;
  }
  async function loadStrategyMonitor(){
    const el=document.getElementById('strategy-monitor-list');if(!el)return;
    try{
      const r=await fetch('data/strategy_curves.json?t='+Date.now());
      if(!r.ok){el.innerHTML='<div class="note">策略曲線資料暫時讀不到</div>';return}
      const json=await r.json();
      const list=json.lines||[];
      if(!list.length){el.innerHTML='<div class="note">查無策略資料</div>';return}
      el.innerHTML=(json.meta&&json.meta.correction?'<div class="note" data-ui-explain style="margin-bottom:8px">'+_autoEsc(json.meta.correction)+'</div>':'')
        +list.map((l,i)=>strategyCurveMonitorCardHtml(l,i)).join('');
    }catch(e){
      console.warn('[loadStrategyMonitor]',e);recordGlobalError('loadStrategyMonitor',e);
      el.innerHTML='<div class="note">策略曲線資料暫時讀不到</div>';
    }
  }

  // 2026-09-01新增：選股成績單——三榜Top20快照的前向紙上追蹤成績（不是回測）。
  // 資料100%來自data/picks_ledger.json，聚合全部在前端做（後端只負責逐日快照+
  // 逐日回填T+N報酬，不做聚合統計，避免兩邊各算一套數字互相對不齊）。
  // 樣本數門檻(20筆)沿用策略監控台forward_paper「<20天樣本不足」同一個量級的
  // 保守判斷精神，但這裡量的是「已回填的個股筆數」不是「交易日數」，兩者單位
  // 不同，各自獨立設門檻。地雷門檻(單筆虧損≥30%)是這裡新定義的顯示用途門檻，
  // 不是統計顯著性檢定，純粹給使用者一個「多慘算地雷」的直覺標準，UI上會把
  // 門檻數字直接寫出來，不藏在程式碼裡。
  const PICKS_BOARD_TITLES={value:'價值成長榜',momentum:'題材動能榜',future:'未來性濾網'};
  const PICKS_MIN_SAMPLE=20;
  const PICKS_DOUBLE_THRESHOLD=100;   // 翻倍：單筆報酬≥100%
  const PICKS_LANDMINE_THRESHOLD=-30; // 地雷：單筆報酬≤-30%

  function _picksAggregateWindow(snapshots, board, windowKey){
    const filled=[];
    for(const snap of snapshots){
      if(snap.board!==board||snap.non_trading_day_duplicate)continue; // 先.一〇三-11：休市日重複快照不計
      for(const pick of (snap.picks||[])){
        const r=pick.returns&&pick.returns[windowKey];
        if(r&&r.return_pct!=null)filled.push(r);
      }
    }
    const n=filled.length;
    if(n<PICKS_MIN_SAMPLE)return {n, sufficient:false};
    const avgReturn=filled.reduce((a,r)=>a+r.return_pct,0)/n;
    const excessVals=filled.filter(r=>r.excess_vs_taiex_pct!=null).map(r=>r.excess_vs_taiex_pct);
    const avgExcess=excessVals.length?excessVals.reduce((a,v)=>a+v,0)/excessVals.length:null;
    const doubleRate=filled.filter(r=>r.return_pct>=PICKS_DOUBLE_THRESHOLD).length/n*100;
    const landmineRate=filled.filter(r=>r.return_pct<=PICKS_LANDMINE_THRESHOLD).length/n*100;
    return {n, sufficient:true, avgReturn, avgExcess, excessN:excessVals.length, doubleRate, landmineRate};
  }

  function picksReportCardHtml(board, snapshotCount, windows){
    const rows=Object.entries(windows).map(([key,label])=>{
      const agg=picksWindowData[board][key];
      if(!agg.sufficient){
        return `<div class="s"><span>${label}</span><b style="color:var(--ink-3);font-size:11px">樣本還太少，需累積（目前${agg.n}筆，門檻${PICKS_MIN_SAMPLE}筆）</b></div>`;
      }
      const ret=agg.avgReturn, exc=agg.avgExcess;
      return `<div class="s"><span>${label}（n=${agg.n}）</span><b class="${ret>=0?'pos':'neg'}">${ret>=0?'+':''}${ret.toFixed(1)}%${exc!=null?`　vs大盤${exc>=0?'+':''}${exc.toFixed(1)}%`:''}</b></div>`;
    }).join('');
    // 翻倍率/地雷率取樣本數最多的那個窗口代表（通常是t5，累積最快）
    const bestWindow=Object.keys(windows).map(k=>picksWindowData[board][k]).filter(a=>a.sufficient).sort((a,b)=>b.n-a.n)[0];
    const rateLine=bestWindow
      ?`<div class="note" style="margin-top:8px">翻倍率(單筆≥+${PICKS_DOUBLE_THRESHOLD}%)：<b>${bestWindow.doubleRate.toFixed(1)}%</b>　·　地雷率(單筆≤${PICKS_LANDMINE_THRESHOLD}%)：<b>${bestWindow.landmineRate.toFixed(1)}%</b>（樣本n=${bestWindow.n}）</div>`
      :`<div class="note" style="margin-top:8px;color:var(--ink-3)">翻倍率/地雷率：樣本還太少，需累積</div>`;
    return `<div class="card">
      <h3>${PICKS_BOARD_TITLES[board]||board}</h3>
      <div class="note" style="margin-bottom:8px">已累積 ${snapshotCount} 筆快照</div>
      <div class="bot-stats" style="flex-direction:column;align-items:stretch;gap:6px">${rows}</div>
      ${rateLine}
    </div>`;
  }

  let picksWindowData={};
  async function loadPicksReportCard(){
    const el=document.getElementById('picks-report-list');if(!el)return;
    try{
      const r=await fetch('data/picks_ledger.json?t='+Date.now());
      if(!r.ok){el.innerHTML='<div class="note">查無資料（data/picks_ledger.json尚未產生）</div>';return}
      const json=await r.json();
      const snapshots=json.snapshots||[];
      if(!snapshots.length){el.innerHTML='<div class="note">尚無快照，累積中</div>';return}
      const windows={t5:'T+5交易日',t20:'T+20交易日',t60:'T+60交易日',t120:'T+120交易日'};
      const boards=Object.keys(PICKS_BOARD_TITLES);
      picksWindowData={};
      const html=boards.map(board=>{
        const snapshotCount=snapshots.filter(s=>s.board===board&&!s.non_trading_day_duplicate).length;
        picksWindowData[board]={};
        for(const key of Object.keys(windows))picksWindowData[board][key]=_picksAggregateWindow(snapshots, board, key);
        return picksReportCardHtml(board, snapshotCount, windows);
      }).join('');
      el.innerHTML=html;
    }catch(e){
      console.warn('[loadPicksReportCard]',e);recordGlobalError('loadPicksReportCard',e);
      el.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
    }
  }

  // 先.一一六-4（2026-10-18）：排序成績單頂部一行——三條非 ETF 研究線的進度與預計結果時間（讀小狀態檔，不寫死）
  async function loadNonEtfLines(){
    const el=document.getElementById('nonetf-lines');if(!el)return;
    try{
      const r=await fetch('data/non_etf_research_lines.json?t='+Math.floor(Date.now()/600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json(),ls=d.lines||[],esc=_autoEsc;
      el.innerHTML=`<b>非 ETF 研究線</b>：${ls.map(x=>`${esc(x.name)}（${esc(x.short||'')}）`).join('／')}`
        +`<details class="ui-info" style="margin-top:4px"><summary>ⓘ 說明</summary><div class="ui-info-body">${ls.map(x=>`<div style="margin:3px 0"><b>${esc(x.name)}</b>：${esc(x.status||'')}；預計 ${esc(x.eta||'—')}</div>`).join('')}`
        +`<div class="note" style="margin-top:4px">更新 ${esc(String(d.updated_at||'').slice(5,16).replace('T',' '))}</div></div></details>`;
    }catch(e){console.warn('[loadNonEtfLines]',e);recordGlobalError('loadNonEtfLines',e);el.textContent='非 ETF 研究線：進度檔讀不到'}
  }

// 先.一三五-1kh-o（2026-11-05，[預設放行]，docs/PROPOSAL_APPJS_SPLIT.md 甲）：「策略 vs 0050」曲線群（交易・策略頁卡片）由 app.js 原封不動搬出（首頁首次載入用不到），
// 由 app.js 的轉接殼以 _lazyCall 載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。

  // ══════ 策略 vs 0050（2026-10-11 先.六十八，取代 2026-09-15「我們 vs 0050」）══════
  // 資料：data/strategy_curves.json（.github/scripts/build_strategy_curves.py 每日產生；選股三榜改用重疊組合法，
  // 舊卡「依序串接複利」把重疊的 5 日報酬串接、誤放大約 5 倍，已刪除）＋本機 /auto/strategy_line（真錢 Bb-90，
  // 帳本只在本機）。每條線從自己的起始日歸一為 100，灰線為同期 0050；指標與「金礦判讀」都由 Python 端同一支
  // metrics() 算好，這裡只畫——判讀文字是固定規則（<60 日「尚不足以判斷」），前端不自行產生任何推論文字。
  // 先.七十三（2026-10-11）：「全部疊加」排第一且為預設；其後 自動投資、模擬 A～F（先.九十一-1 加 F）、選股榜單。內部 id 不變。
  let SC_DATA=null,SC_LIVE=null,SC_LIVE_ERR='',SC_TAB='all',SC_BOARD='value';
  const SC_TABS=[['all','全部疊加'],['live','自動投資'],['paper_1','模擬 A'],['paper_3','模擬 B'],['paper_4','模擬 C'],
    ['paper_1b','模擬 D'],['paper_2','模擬 E'],['paper_5','模擬 F'],['paper_7','模擬 G'],['boards','選股榜單']];
  const SC_BOARDS=[['value','估值'],['momentum','動能'],['future','未來']];
  // 每條線固定顏色（疊圖與單線圖一致）；0050 固定灰色
  const SC_COLOR_BY={live_bb90:'#2f81f7',paper_1:'#d4a017',paper_3:'#3fb950',paper_4:'#db61a2',paper_1b:'#f0883e',paper_2:'#a371f7',paper_5:'#79c0ff',paper_7:'#ff9bce',
    board_value:'#56d4dd',board_momentum:'#e5534b',board_future:'#b5d334'};
  const SC_BENCH_COLOR='#8b8b8b';
  const scColor=id=>SC_COLOR_BY[id]||'#9e9e9e';
  let SC_PLOT=null;  // 目前畫面上那張圖的資料（按住圖顯示當日數值用）
  // 先.一〇四-4：「跟 0050 比」讀檔失敗要講原因（不能永遠停在載入中）；15 秒逾時
  let SC_ERR='';
  async function loadStrategyCurves(){
    SC_ERR='';
    const ac=typeof AbortController!=='undefined'?new AbortController():null;
    const to=ac?setTimeout(()=>ac.abort(),15000):null;
    try{
      const r=await fetch('data/strategy_curves.json?t='+Math.floor(Date.now()/60000),ac?{signal:ac.signal}:undefined);
      if(!r.ok)throw new Error('HTTP '+r.status);
      SC_DATA=await r.json();
    }catch(e){
      console.warn('[loadStrategyCurves]',e);recordGlobalError('loadStrategyCurves',e);SC_DATA=null;
      SC_ERR=(e&&e.name==='AbortError')?'等了 15 秒還沒下載完（網路慢或斷線）'
        :(navigator.onLine===false||_isOfflineErr(e))?'目前離線，讀不到資料檔'
        :/HTTP 404/.test(String(e&&e.message))?'資料檔還沒產生（雲端排程尚未跑過）'
        :/HTTP/.test(String(e&&e.message))?('伺服器回應 '+String(e.message).replace('HTTP ',''))
        :('資料檔格式讀不出來（'+String(e&&e.message||e).slice(0,40)+'）');
    }finally{if(to)clearTimeout(to)}
    SC_LIVE=null;SC_LIVE_ERR='';
    if(!LIVE.configured||!LIVE.url){SC_LIVE_ERR='連上電腦才看得到';return SC_DATA}
    try{
      const r=await liveFetch('/auto/strategy_line',15000);
      if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器可能是舊版，需重啟）':''));
      SC_LIVE=await r.json();
    }catch(e){
      // 本機伺服器離線／手機不在家用網路是常態，不是程式錯誤：只記 console、卡上誠實顯示原因，
      // 刻意不呼叫 recordGlobalError（否則每次出門都會在診斷橫幅堆一條假錯誤）。
      console.warn('[loadStrategyCurves live]',e);SC_LIVE_ERR=_isOfflineErr(e)?liveOfflineText():('讀不到本機伺服器（'+(e&&e.message||e)+'）');
    }
    return SC_DATA;
  }
  async function retryStrategyCurves(){
    try{
      const b=document.getElementById('sc-body');if(b)b.innerHTML='<div class="note" style="color:var(--ink-3)">載入中…</div>';
      await Promise.allSettled([loadStrategyCurves(),loadStrategyHistory()]);renderStrategyCurves();
    }catch(e){console.warn('[retryStrategyCurves]',e);recordGlobalError('retryStrategyCurves',e)}
  }
  window.retryStrategyCurves=retryStrategyCurves;
  function scLines(){
    const ls=(SC_DATA&&SC_DATA.lines||[]).slice();
    const i=ls.findIndex(l=>l.id==='live_bb90');
    if(SC_LIVE&&SC_LIVE.id==='live_bb90'){if(i>=0)ls[i]=SC_LIVE;else ls.unshift(SC_LIVE)}
    else if(i>=0&&SC_LIVE_ERR)ls[i]=Object.assign({},ls[i],{note:SC_LIVE_ERR});
    return ls;
  }
  function scById(id){return scLines().find(l=>l.id===id)||null}
  // 先.七十五：剛建倉的線只有一天（起點 100）也算有資料——疊圖畫成一個點，下一個交易日收盤後開始連成線
  const scHasData=l=>!!(l&&l.started&&l.dates&&l.dates.length>=1);
  function scTabHasData(k){
    if(k==='all')return true;
    if(k==='boards')return SC_BOARDS.some(([b])=>scHasData(scById('board_'+b)));
    return scHasData(scById(k==='live'?'live_bb90':k));
  }
  // 「X 月 X 日開始」；自動投資沒有預定日（第一批成交日才算起點）
  function scStartText(l){
    const d=l&&l.start_date;
    if(d&&/^\d{4}-\d{2}-\d{2}/.test(d))return `${+d.slice(5,7)} 月 ${+d.slice(8,10)} 日開始`;
    return l&&l.id==='live_bb90'?'第一批成交後開始':'開始日未定';
  }
  const scShortDate=l=>(l&&l.start_date&&/^\d{4}-\d{2}-\d{2}/.test(l.start_date))?`${+l.start_date.slice(5,7)}/${+l.start_date.slice(8,10)}`:(l&&l.id==='live_bb90'?'第一批成交後':'未定');
  // 多條線畫在同一條日期軸上（聯集日期）；灰線＝最早起始那條的同期 0050（起點 100）。
  // 先.八十-8（2026-10-12）：其餘各線不再一律從 100 起，而是從自己的起始日接在「當天 0050 的值」上
  // （nav×當日 0050 值÷100），線與灰線的距離＝同期跟 0050 的差。按住圖仍顯示各線自己的累積報酬。
  // 只畫有資料的線（先.七十三-2：未開始的不畫空線）。
  let SC_ALIGN={};  // 先.八十-8：疊圖各線的對齊係數（起始日 0050 值÷100），冒煙 #107 驗證用
  function scSvg(lines){
    const W=320,H=150,pad=6;
    const started=lines.filter(scHasData);
    SC_PLOT=null;
    if(!started.length)return '';
    const dates=[...new Set(started.flatMap(l=>l.dates))].sort();
    const xi=Object.fromEntries(dates.map((d,i)=>[d,i]));
    const bl=started.slice().sort((a,b)=>a.dates[0]<b.dates[0]?-1:1)[0];
    const bm=Object.fromEntries(bl.dates.map((d,i)=>[d,bl.bench[i]]));
    const benchAt=d=>{if(bm[d]!=null)return bm[d];let v=null;for(const x of bl.dates){if(x<=d)v=bm[x];else break}return v};
    const kOf=l=>{const v=benchAt(l.dates[0]);return (v!=null&&isFinite(v))?v/100:1};
    const aligned=Object.fromEntries(started.map(l=>[l.id,l.nav.map(v=>v*kOf(l))]));
    SC_ALIGN=Object.fromEntries(started.map(l=>[l.id,kOf(l)]));
    const vals=[100,...started.flatMap(l=>aligned[l.id]),...bl.bench];
    const mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||1;
    const X=d=>pad+(dates.length>1?xi[d]/(dates.length-1):0)*(W-2*pad),Y=v=>pad+(1-(v-mn)/rg)*(H-2*pad);
    const pl=(ds,vs)=>ds.map((d,i)=>`${X(d).toFixed(1)},${Y(vs[i]).toFixed(1)}`).join(' ');
    const lines_=started.map(l=>l.dates.length>1
      ?`<polyline data-line="${l.id}" points="${pl(l.dates,aligned[l.id])}" fill="none" stroke="${scColor(l.id)}" stroke-width="2.2"/>`
      :`<circle data-line="${l.id}" cx="${X(l.dates[0]).toFixed(1)}" cy="${Y(aligned[l.id][0]).toFixed(1)}" r="3.5" fill="${scColor(l.id)}"/>`).join('');
    const toMap=(ds,vs)=>Object.fromEntries(ds.map((d,i)=>[d,vs[i]]));
    SC_PLOT={dates,pad,W,series:[{label:'0050',color:SC_BENCH_COLOR,map:toMap(bl.dates,bl.bench)}]
      .concat(started.map(l=>({label:l.label,color:scColor(l.id),map:toMap(l.dates,l.nav)})))};
    return `<div class="sc-plot" style="position:relative;touch-action:pan-y">
      <svg id="sc-svg" width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <line x1="${pad}" y1="${Y(100).toFixed(1)}" x2="${W-pad}" y2="${Y(100).toFixed(1)}" stroke="var(--hairline)" stroke-width="1" stroke-dasharray="3,2"/>
      <polyline data-line="bench_0050" points="${pl(bl.dates,bl.bench)}" fill="none" stroke="${SC_BENCH_COLOR}" stroke-width="2" opacity=".8"/>
      ${lines_}<line id="sc-guide" x1="0" y1="0" x2="0" y2="${H}" stroke="var(--ink-3)" stroke-width="1" visibility="hidden"/></svg>
      <div id="sc-tip" hidden style="position:absolute;top:4px;pointer-events:none;background:var(--surface,#1c1b19);border:1px solid var(--hairline);border-radius:8px;padding:5px 8px;font-size:11px;line-height:1.55;white-space:nowrap;z-index:2"></div>
    </div>`;
  }
  // 先.七十三-3：手指按住圖（或滑鼠移到圖上）顯示該日各線數值；放開就收起
  function scBindTip(){
    const wrap=document.querySelector('#sc-body .sc-plot'),svg=document.getElementById('sc-svg'),tip=document.getElementById('sc-tip'),guide=document.getElementById('sc-guide');
    if(!wrap||!svg||!tip||!SC_PLOT)return;
    let down=false;
    const show=ev=>{
      try{
        const P=SC_PLOT,r=svg.getBoundingClientRect();
        const fx=Math.min(1,Math.max(0,((ev.clientX-r.left)/r.width*P.W-P.pad)/(P.W-2*P.pad)));
        const i=Math.round(fx*(P.dates.length-1)),d=P.dates[i];
        const gx=P.pad+(P.dates.length>1?i/(P.dates.length-1):0)*(P.W-2*P.pad);
        guide.setAttribute('x1',gx);guide.setAttribute('x2',gx);guide.setAttribute('visibility','visible');
        const rows=P.series.filter(s=>s.map[d]!=null).map(s=>{const v=s.map[d]-100;return `<div><span style="color:${s.color}">●</span> ${_uiEsc(s.label)} ${v>=0?'+':''}${v.toFixed(1)}%</div>`});
        tip.innerHTML=`<div style="color:var(--ink-3)">${d.slice(5).replace('-','/')}</div>`+rows.join('');
        tip.hidden=false;
        const left=ev.clientX-r.left;tip.style.left=(left>r.width/2?Math.max(0,left-tip.offsetWidth-10):left+10)+'px';
      }catch(e){console.warn('[scTip]',e);recordGlobalError('scTip',e)}
    };
    const hide=()=>{tip.hidden=true;guide.setAttribute('visibility','hidden')};
    svg.addEventListener('pointerdown',ev=>{down=true;show(ev)});
    svg.addEventListener('pointermove',ev=>{if(down||ev.pointerType==='mouse')show(ev)});
    ['pointerup','pointercancel','pointerleave'].forEach(t=>svg.addEventListener(t,()=>{down=false;hide()}));
  }
  const _scPp=v=>v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(1)} 點`;
  // 先.九十四-5f：「跟 0050 差多少」是相對比較、不是漲跌，用中性色＋「領先／落後」文字，漲跌色只留給真實漲跌
  const _scVs=v=>{if(v==null||!isFinite(Number(v)))return '—';const n=Number(v),a=Math.abs(n).toFixed(1);return a==='0.0'?'持平 0.0 點':`${n>0?'領先':'落後'} ${a} 點`};
  const _scGap=v=>v==null?'—':(v>0?'+':v<0?'−':'')+Math.abs(Number(v)).toFixed(1);
  const _scPct=v=>v==null?'—':`${Number(v).toFixed(2)}%`;
  const SC_STATUS_COLOR={'真錢':'var(--accent)','模擬中':'var(--ink-2)','紙上追蹤中':'var(--ink-2)','回測通過':'var(--good)','回測未通過':'var(--critical)','未回測':'var(--warn)'};
  function scStatusTag(s){return `<span class="sc-status" style="font-size:10px;padding:1px 6px;border-radius:8px;border:1px solid ${SC_STATUS_COLOR[s]||'var(--hairline)'};color:${SC_STATUS_COLOR[s]||'var(--ink-2)'}">${s||'—'}</span>`}
  function scMetricsHtml(l){
    const m=l.metrics||{};
    // 先.七十二-A4：指標改白話——賺賠％／跟 0050 差多少／最大跌幅；樣本 <60 交易日不顯示年化（先.六十八-3 規則不變）
    return `<div class="note sc-goal" style="margin:0 0 4px">設計目標：<b style="color:var(--ink-2)">${l.goal||'未標示'}</b>　${scStatusTag(l.status)}</div>
    <div class="bot-stats sc-metrics" style="margin:6px 0">
      <div class="s"><span>賺賠％</span><b class="${(m.cum_pct||0)>=0?'pos':'neg'}">${m.cum_pct==null?'—':(m.cum_pct>=0?'+':'')+Number(m.cum_pct).toFixed(1)+'%'}</b></div>
      <div class="s"><span>跟 0050 差多少</span><b class="sc-gap" style="color:var(--ink)">${_scVs(m.cum_gap_pp)}</b></div>
      <div class="s"><span>最大跌幅</span><b>${_scPct(m.mdd_pct)}</b></div>
    </div>
    <div class="note" style="margin-bottom:4px">${m.days||0} 個交易日；同期 0050 ${_scPct(m.bench_cum_pct)}${m.days>=60&&m.ann_gap_pp!=null?'；每年約差 '+_scPp(m.ann_gap_pp):''}</div>
    <div class="note sc-verdict" style="font-weight:600;color:var(--ink-2)">判讀：${m.days>=60?m.verdict:`尚不足以判斷（才 ${m.days||0} 天，要滿 60 天）`}</div>`;
  }
  // 先.七十三-2：還沒開始的線只顯示一行，不畫空圖
  function scNotYetHtml(l){
    return `<div class="note sc-notyet" style="margin:10px 0 2px;color:var(--ink-3)">${_uiEsc(scStartText(l))}，現在還沒有資料</div>`+
      (l&&l.why?`<div class="note sc-notyet-why" style="margin:0 0 10px;color:var(--ink-4)">原因：${_uiEsc(l.why)}</div>`:'');
  }
  // 先.八十一-5：曲線檔 candidacy（例：模擬 B／C 閘門殺測失敗）顯示在該線最上方；data-ui-cite＝照裁示原文保留試驗編號
  const scCandHtml=l=>l&&l.candidacy?`<div class="note sc-cand" data-ui-cite data-ui-keep style="margin:2px 0 6px;font-weight:600;color:var(--critical,#e5534b)">⛔ ${_uiEsc(l.candidacy)}</div>`:'';
  // 先.八十一-16：建倉日事後倒填的線（模擬 B／C／D）照實標明
  const scInceptionHtml=l=>l&&l.inception_note?`<div class="note sc-inception" data-ui-keep style="margin:2px 0 6px;color:var(--warn)">⚠ ${_uiEsc(l.inception_note)}</div>`:'';
  // 先.九十一-1：還沒開始的線也標設計註記（模擬 F：學界已知現象、只是研究）；已開始的線註記已併入 note
  const scDesignHtml=l=>l&&l.design_note&&!scHasData(l)?`<div class="note sc-design" data-ui-keep style="margin:2px 0 6px;color:var(--ink-3)">ⓘ ${_uiEsc(l.design_note)}</div>`:'';
  // 先.九十六-2 ②（2026-10-14 總司令裁示）：樣本不足 60 個交易日時收合，標「累積中（已 N 天／需 60 天）」，點開才看數字與圖
  const SC_MIN_DAYS=60;
  function scCollapseIfShort(l,html,prefix){
    const d=Number((l&&l.metrics&&l.metrics.days)||0);
    if(d>=SC_MIN_DAYS)return html;
    return `<details class="sc-accum"><summary class="note" style="cursor:pointer;margin:6px 0;color:var(--ink-2)">${prefix||''}累積中（已 ${d} 天／需 ${SC_MIN_DAYS} 天）<span style="color:var(--ink-3)">　點開看目前數字</span></summary>${html}</details>`;
  }
  function scLineBlock(l){
    return scCandHtml(l)+scInceptionHtml(l)+scDesignHtml(l)+_scLineBlockInner(l);
  }
  function _scLineBlockInner(l){
    if(!l)return '<div class="note sc-notyet" style="color:var(--ink-3)">現在還沒有資料</div>';
    if(!scHasData(l))return `<div class="note sc-goal" style="margin:6px 0 2px">設計目標：<b style="color:var(--ink-2)">${l.goal||'未標示'}</b></div>`+scNotYetHtml(l)+scHistBlockHtml(l);
    // 先.七十五：剛建倉只有一天時不畫只有一個點的大空圖，改一行說明（歷史段圖裡會畫出起點）
    if(l.dates.length<2)return scCollapseIfShort(l,scMetricsHtml(l)+`<div class="note sc-oneday" style="margin-top:8px;color:var(--ink-3)">${+l.start_date.slice(5,7)}/${+l.start_date.slice(8,10)} 建倉，起點 100；下一個交易日收盤後開始畫線</div>`+scHistBlockHtml(l));
    const full=scMetricsHtml(l)+`<div style="margin-top:8px">${scSvg([l])}</div>`+scHistBlockHtml(l)+`
      <div class="note" style="margin-top:4px;font-size:10px">${l.start_date} 起算為 100；<span style="color:${SC_BENCH_COLOR}">━</span> 灰線＝同期 0050；按住圖看每天數字</div>
      <div class="note" style="margin-top:4px;font-size:10px;color:var(--ink-3)">${l.note||''}</div>`;
    return scCollapseIfShort(l,full);
  }
  // 先.七十三-3：疊圖圖例——0050 灰色排第一，其後每條有資料的線：顏色＋名稱＋目前跟 0050 差幾點
  function scLegendHtml(started){
    const item=(color,label,val)=>`<span class="sc-legend-item" style="display:inline-flex;align-items:center;gap:4px;margin:0 10px 4px 0;white-space:nowrap"><span style="display:inline-block;width:12px;height:3px;border-radius:2px;background:${color}"></span>${_uiEsc(label)}${val!=null?` <b style="font-weight:600">${val}</b>`:''}</span>`;
    return `<div class="sc-legend" style="display:flex;flex-wrap:wrap;font-size:11px;margin-top:6px">`+
      item(SC_BENCH_COLOR,'0050',null)+started.map(l=>item(scColor(l.id),l.label,_scGap(l.metrics&&l.metrics.cum_gap_pp))).join('')+`</div>`;
  }
  // ══════ 先.七十六（2026-10-11）：歷史段——回測（虛線框，只有摘要）／樣本外（點線）／紙上（實線），0050 全程灰線 ══════
  // 資料：data/strategy_history.json（build_strategy_history.py 只讀既有結果檔）。回測結果檔沒有逐月序列，
  // 所以回測段只畫一個虛線框標年化與最大跌幅，不畫曲線（不拿年化去畫一條假的直線）。
  // 樣本外從 2024-12-31＝100 起逐月累積；紙上段接在樣本外終點後面（同一條時間軸、兩段不重疊）。
  let SC_HIST=null,SC_RANGE='3y';
  const SC_RANGES=[['1y','1 年'],['3y','3 年'],['all','全部']];
  async function loadStrategyHistory(){
    try{
      const r=await fetch('data/strategy_history.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      SC_HIST=await r.json();
    }catch(e){console.warn('[loadStrategyHistory]',e);recordGlobalError('loadStrategyHistory',e);SC_HIST=null}
    return SC_HIST;
  }
  const _scMs=d=>Date.parse(d+'T00:00:00Z');
  function _scOosPoints(monthly,base,startD){
    const ks=Object.keys(monthly||{}).sort();if(!ks.length)return [];
    base=base||100;
    const pts=[{d:startD||'2024-12-31',v:base}];let v=base;
    for(const k of ks){v*=1+Number(monthly[k]);const [y,m]=k.split('-').map(Number);const last=new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);pts.push({d:last,v})}
    return pts;
  }
  // 回傳 {segments:[{kind,id,color,pts}], box:{from,to,text}|null, firstDate,lastDate}
  function scHistModel(l){
    const H=SC_HIST&&SC_HIST.lines&&SC_HIST.lines[l.id];if(!H)return null;
    const B=(SC_HIST.bench_0050)||{};
    const segs=[];
    // 先.七十七-5：回測段月序列（年化與原結果檔一致才有 monthly）→ 虛線；樣本外、紙上依序接在前一段終點後面
    const bt0=H.backtest&&H.backtest.monthly&&_scOosPoints(H.backtest.monthly,100,'2003-06-30');
    const bb0=B.backtest&&B.backtest.monthly&&_scOosPoints(B.backtest.monthly,100,'2003-06-30');
    if(bt0&&bt0.length)segs.push({kind:'backtest',color:scColor(l.id),pts:bt0});
    if(bt0&&bt0.length&&bb0&&bb0.length)segs.push({kind:'backtest',color:SC_BENCH_COLOR,pts:bb0,bench:true});
    const oos=H.oos&&_scOosPoints(H.oos.monthly,bt0&&bt0.length?bt0[bt0.length-1].v:100),
          boos=B.oos&&_scOosPoints(B.oos.monthly,bt0&&bt0.length&&bb0&&bb0.length?bb0[bb0.length-1].v:100);
    if(oos&&oos.length)segs.push({kind:'oos',color:scColor(l.id),pts:oos});
    if(oos&&oos.length&&boos&&boos.length)segs.push({kind:'oos',color:SC_BENCH_COLOR,pts:boos,bench:true});
    if(scHasData(l)){
      const base=oos&&oos.length?oos[oos.length-1].v:100,bbase=boos&&boos.length?boos[boos.length-1].v:100;
      segs.push({kind:'paper',color:scColor(l.id),pts:l.dates.map((d,i)=>({d,v:base*l.nav[i]/100}))});
      segs.push({kind:'paper',color:SC_BENCH_COLOR,bench:true,pts:l.dates.map((d,i)=>({d,v:bbase*l.bench[i]/100}))});
    }
    const bt=H.backtest&&H.backtest.cagr!=null?H.backtest:null;
    const all=segs.flatMap(s=>s.pts.map(p=>p.d));
    return {segs,bt,btCurve:!!(bt0&&bt0.length),lastDate:all.length?all.sort().slice(-1)[0]:'2026-10-08'};
  }
  function scHistSvg(model){
    const W=320,H=160,pad=8;
    const last=_scMs(model.lastDate);
    const from=SC_RANGE==='1y'?last-365*864e5:SC_RANGE==='3y'?last-3*365*864e5:_scMs('2003-07-01');
    const vis=model.segs.map(s=>({...s,pts:s.pts.filter(p=>_scMs(p.d)>=from)})).filter(s=>s.pts.length);
    const vals=vis.flatMap(s=>s.pts.map(p=>p.v));
    if(!vals.length&&!(model.bt&&from<_scMs('2025-01-01')))return '';
    // 「全部」橫跨 20 年、數值差十倍以上，改用對數刻度，近年的線才看得出起伏
    const lg=SC_RANGE==='all',T=v=>lg?Math.log(Math.max(v,1e-6)):v;
    const firstVis=vis.length?Math.min(...vis.map(s=>T(s.pts[0].v))):T(100);
    const tv=vals.map(T),mn=Math.min(firstVis,...tv),mx=Math.max(firstVis,...tv),rg=(mx-mn)||1;
    const X=ms=>pad+(ms-from)/((last-from)||1)*(W-2*pad),Y=v=>pad+14+(1-(T(v)-mn)/rg)*(H-2*pad-14);
    const dash={backtest:'5,4',oos:'1.5,3',paper:''};
    const lines=vis.map(s=>s.pts.length>1
      ?`<polyline data-seg="${s.kind}${s.bench?'-0050':''}" points="${s.pts.map(p=>X(_scMs(p.d)).toFixed(1)+','+Y(p.v).toFixed(1)).join(' ')}" fill="none" stroke="${s.color}" stroke-width="${s.bench?1.8:2.2}" stroke-dasharray="${dash[s.kind]}" opacity="${s.bench?.85:1}"/>`
      :`<circle data-seg="${s.kind}${s.bench?'-0050':''}" cx="${X(_scMs(s.pts[0].d)).toFixed(1)}" cy="${Y(s.pts[0].v).toFixed(1)}" r="3" fill="${s.color}"/>`).join('');
    let box='';
    if(model.bt&&!model.btCurve&&from<_scMs('2025-01-01')){
      const x0=X(Math.max(from,_scMs('2003-07-01'))),x1=X(_scMs('2024-12-31'));
      // 框太窄（例如 3 年範圍只露出 2023-10～2024-12）時框內只寫「回測」，數字看上方指標列
      if(x1-x0>12)box=`<rect data-seg="backtest" x="${x0.toFixed(1)}" y="${pad+14}" width="${(x1-x0).toFixed(1)}" height="${H-2*pad-14}" fill="none" stroke="var(--ink-3)" stroke-dasharray="5,4" rx="6"/>`+
        `<text x="${((x0+x1)/2).toFixed(1)}" y="${(H/2+4).toFixed(1)}" text-anchor="middle" fill="var(--ink-3)" font-size="9">${x1-x0>170?`回測 年化 ${(model.bt.cagr*100).toFixed(1)}%｜最大跌幅 ${(model.bt.mdd*100).toFixed(1)}%`:'回測'}</text>`;
    }
    const yr=new Date(from).getUTCFullYear(),ticks=[];
    for(let y=yr+1;_scMs(y+'-01-01')<=last;y+=(SC_RANGE==='all'?4:1))ticks.push(`<text x="${X(_scMs(y+'-01-01')).toFixed(1)}" y="${pad+6}" text-anchor="middle" fill="var(--ink-4)" font-size="8">${y}</text>`);
    return `<svg class="sc-hist" width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      ${lg?'':`<line x1="${pad}" y1="${Y(100).toFixed(1)}" x2="${W-pad}" y2="${Y(100).toFixed(1)}" stroke="var(--hairline)" stroke-width="1" stroke-dasharray="3,2"/>`}${ticks.join('')}${box}${lines}</svg>`;
  }
  // 先.七十六-3：指標列分段——回測年化與最大跌幅／樣本外累計差距／紙上累計差距（<60 交易日：尚不足以判斷）
  // 先.八十一-6：回測最大跌幅 ≤ −45% 加註「接近天條一」（天條一：MDD 不得超過 −50%）
  function scHistMetricsHtml(l){
    const H=SC_HIST&&SC_HIST.lines&&SC_HIST.lines[l.id];if(!H)return '';
    const B=(SC_HIST.bench_0050||{}).oos;
    const cells=[];
    if(H.backtest&&H.backtest.cagr!=null)cells.push(`<div class="s" data-seg="backtest"><span>回測</span><b>年化 ${(H.backtest.cagr*100).toFixed(1)}%</b><span style="font-size:10px">最大跌幅 ${(H.backtest.mdd*100).toFixed(1)}%${H.backtest.mdd<=-0.45?'<b class="sc-survival-near" style="color:var(--warn)">（接近天條一）</b>':''}</span></div>`);
    // 先.八十-8：樣本外格同時寫「策略 +X%／0050 +Y%」，再附差幾點
    if(H.oos&&H.oos.cum_return!=null&&B&&B.cum_return!=null){const g=(H.oos.cum_return-B.cum_return)*100,sp=v=>(v>=0?'+':'')+(v*100).toFixed(1)+'%';cells.push(`<div class="s" data-seg="oos"><span>樣本外</span><b class="sc-oos-pair">策略 ${sp(H.oos.cum_return)}／0050 ${sp(B.cum_return)}</b><span style="font-size:10px;color:var(--ink-2)" class="sc-gap">${_scVs(g)}</span></div>`)}
    const m=l.metrics||{};
    cells.push(`<div class="s" data-seg="paper"><span>紙上</span><b>${scHasData(l)&&m.days>=60?_scPp(m.cum_gap_pp):'尚不足以判斷'}</b><span style="font-size:10px">${scHasData(l)?(m.days||0)+' 個交易日':'還沒開始'}</span></div>`);
    return `<div class="bot-stats sc-hist-metrics" style="margin:6px 0">${cells.join('')}</div>`;
  }
  // 先.七十七-5：回測段可重現性。年化對得上才畫曲線；最大跌幅月資料必然比日資料淺，數字一律以原結果檔為準
  function scReproNoteHtml(l){
    const bt=SC_HIST&&SC_HIST.lines&&SC_HIST.lines[l.id]&&SC_HIST.lines[l.id].backtest,r=bt&&bt.repro;
    if(!r||r.status==='OK')return '';
    const head=r.status==='NO_SERIES'?'回測段沒有逐月資料，只標數字':r.status==='MONTHLY_APPROX'?'月頻近似：曲線用月資料畫，最大跌幅以上方數字為準':r.draw_curve?'回測曲線用月資料畫，最大跌幅以上方數字為準':'回測月資料與原結果對不上，不畫曲線';
    return `<div class="note sc-repro" data-repro="${_uiEsc(r.status)}" style="margin-top:4px;font-size:10.5px;color:var(--ink-3)">${head}${r.why?`<details data-ui-detail style="display:inline"><summary style="display:inline;cursor:pointer;color:var(--ink-4)"> ⓘ</summary><div style="font-size:10px">${_uiEsc(uiPlain(r.why))}</div></details>`:''}</div>`;
  }
  function scHistBlockHtml(l){
    const model=scHistModel(l);if(!model)return '';
    const svg=scHistSvg(model);
    const chip=(on,label,k)=>`<span class="press sc-range" data-range="${k}" style="padding:2px 8px;border-radius:12px;font-size:10.5px;border:1px solid ${on?'var(--accent)':'var(--hairline)'};color:${on?'var(--accent)':'var(--ink-3)'};cursor:pointer" onclick="SC_RANGE='${k}';renderStrategyCurves()">${label}</span>`;
    const lab=(dash,text,seg)=>`<span class="sc-seg-label" data-seg="${seg}" style="display:inline-flex;align-items:center;gap:4px;margin:0 10px 3px 0;white-space:nowrap"><svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3" stroke="var(--ink-2)" stroke-width="2" stroke-dasharray="${dash}"/></svg>${text}</span>`;
    const L=(SC_HIST.meta&&SC_HIST.meta.labels)||{};
    return `<div class="sc-hist-block" style="margin-top:10px">
      <div style="display:flex;gap:6px;justify-content:flex-end;margin-bottom:4px">${SC_RANGES.map(([k,lb])=>chip(k===SC_RANGE,lb,k)).join('')}</div>
      ${scHistMetricsHtml(l)}${svg}${scReproNoteHtml(l)}
      <div class="sc-seg-labels" style="display:flex;flex-wrap:wrap;font-size:10.5px;color:var(--ink-3);margin-top:4px">${lab('5,4',L.backtest||'回測＝用來挑策略的資料','backtest')}${lab('1.5,3',L.oos||'樣本外＝只考過一次','oos')}${lab('',L.paper||'紙上＝今天起才算數','paper')}</div>
    </div>`;
  }
  function renderStrategyCurves(){
    const tabsEl=document.getElementById('sc-tabs'),bodyEl=document.getElementById('sc-body');
    if(!tabsEl||!bodyEl)return;
    if(!SC_DATA||!SC_DATA.lines){
      bodyEl.innerHTML=`<div class="note" style="color:var(--ink-3)">載入失敗：${_uiEsc(SC_ERR||'資料檔裡沒有策略曲線')} <span class="press" style="text-decoration:underline;cursor:pointer" onclick="retryStrategyCurves()">重試</span></div>`;
      tabsEl.innerHTML='';return}
    const chip=(on,label,js,attr,dim)=>`<span class="press sc-tab" ${attr} style="padding:3px 9px;border-radius:14px;font-size:11px;white-space:nowrap;border:1px solid ${on?'var(--accent)':'var(--hairline)'};color:${on?'var(--accent)':'var(--ink-2)'};cursor:pointer;opacity:${dim?'.45':'1'}" onclick="${js}">${label}</span>`;
    tabsEl.innerHTML=SC_TABS.map(([k,lb])=>{const has=scTabHasData(k);return chip(k===SC_TAB,lb,`SC_TAB='${k}';renderStrategyCurves()`,`data-tab="${k}" data-has-data="${has?1:0}"`,!has)}).join('');
    // 先.八十一-16：計算口徑一行（還原價、0050 含息、現金計息），每個分頁都顯示
    let html=SC_DATA.meta&&SC_DATA.meta.method_note?`<div class="note sc-method" data-ui-keep style="margin:0 0 6px;font-size:10.5px;color:var(--ink-3)">${_uiEsc(SC_DATA.meta.method_note)}</div>`:'';
    if(SC_TAB==='boards'){
      html+=`<div style="display:flex;gap:6px;margin-bottom:6px">${SC_BOARDS.map(([k,lb])=>{const has=scHasData(scById('board_'+k));return chip(k===SC_BOARD,lb,`SC_BOARD='${k}';renderStrategyCurves()`,`data-board="${k}"`,!has)}).join('')}</div>`;
      html+=scLineBlock(scById('board_'+SC_BOARD));
      html+=`<div class="note" style="margin-top:6px;font-size:10px;color:var(--warn)">${(SC_DATA.meta&&SC_DATA.meta.correction)||''}</div>`;
    }else if(SC_TAB==='all'){
      const all=scLines(),started=all.filter(scHasData),soon=all.filter(l=>!scHasData(l));
      // 先.九十六-2 ②：疊加圖以「最長的一條」天數判斷，不足 60 個交易日整張收合
      const maxDays=started.reduce((m,l)=>Math.max(m,Number((l.metrics&&l.metrics.days)||0)),0);
      html+=started.length?scCollapseIfShort({metrics:{days:maxDays}},`<div style="margin-top:4px">${scSvg(started)}</div>`+scLegendHtml(started),'最長一條 '):scNotYetHtml(null);
      // 「即將加入」是資料清單不是說明文字，不用 .note（不會被收成「ⓘ 說明」）
      if(soon.length)html+=`<div class="sc-soon" style="margin-top:4px;font-size:11.5px;line-height:1.6;color:var(--ink-3)">即將加入：${soon.map(l=>`${_uiEsc(l.label.replace(/\s*(三檔分散|供給緊縮|景氣閘門|加速|穩健|賣波動)$/,''))}（${scShortDate(l)}）`).join('、')}</div>`;
      html+=`<div class="note" style="font-size:10px;color:var(--ink-3)">各線從自己的起始日接在當天 0050 的位置；按住圖看各線自己的報酬</div>`;
    }else{
      html+=scLineBlock(scById(SC_TAB==='live'?'live_bb90':SC_TAB));
    }
    const meta=SC_DATA.meta||{};
    html+=`<div class="note" style="margin-top:6px;font-size:10px;color:var(--ink-3)">${meta.price_asof?'資料到 '+String(meta.price_asof).slice(5).replace('-','/')+'（最後交易日）':''}</div>`;
    bodyEl.innerHTML=html;
    scBindTip();
  }
