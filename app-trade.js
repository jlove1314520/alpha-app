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
      `<span>${esc(o.symbol)} ${o.lot==='IntradayOdd'?'零股':'整股'} ${n(o.qty)} 股</span><span>限價 ${n(o.limit_price)}　${n(o.amount)} 元 ${o.cap_ok?'✓':'⚠ 超過單筆上限'}</span></div>`).join('');
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
      if(b.dataset.sub==='picks')loadPicksReportCard();
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
  function _paperCommonRows(j,weightsHtml){
    const ret=j.total_return_pct;
    const nx=_paperNextRebalance(j.as_of_date);
    return _paperRow('NAV',j.nav!=null?Math.round(j.nav).toLocaleString():'—')
      +_paperRow('累積報酬',ret!=null?(ret>=0?'+':'')+Number(ret).toFixed(2)+'%':'—',(ret||0)>=0?'pos':'neg')
      +_paperRow('目前權重',weightsHtml)
      +_paperRow('下次再平衡',nx?_paperEsc(nx)+'<span class="note" style="margin:0 0 0 3px">預計</span>':'—')
      +'<div class="note" style="margin-top:6px;font-size:11px">截至 '+_paperEsc(j.as_of_date||'—')+' · 已記'+(j.history_months||0)+'筆</div>';
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
      return _paperCardHtml('模擬 A 穩健','0050 70% · 定存 30%',_paperCommonRows(j,w));
    }catch(e){
      console.warn('[_renderPaper7030]',e);recordGlobalError('_renderPaper7030',e);
      return _paperCardHtml('模擬 A 穩健','0050＋定存','<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
    }
  }
  async function _renderPaper1b(){
    try{
      const j=await _fetchPaperJson('data/paper_1b.json');
      if(!j.started)return _paperCardHtml('紙.一b Bb-90','0050 45% · 00646 45% · 00697B 10%','<div style="margin-top:10px;font-size:14px;font-weight:700;color:var(--warn)">2026-11-02 啟動</div><div class="note" style="margin-top:4px;font-size:11px">啟動前不顯示任何數字</div>');
      const wp=j.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml('紙.一b Bb-90','0050 / 00646 / 00697B',_paperCommonRows(j,w||'—'));
    }catch(e){
      console.warn('[_renderPaper1b]',e);recordGlobalError('_renderPaper1b',e);
      return _paperCardHtml('紙.一b Bb-90','0050 / 00646 / 00697B','<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
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
    const title='紙.三 S3-C6 危機閘門',sub='00631L/00647L 各25%·0050/00646 各15%·00697B 20%（閘門關時2倍腿改現金）';
    try{
      const j=await _fetchPaperJson('data/paper_3.json');
      const err=j.last_error?'<div class="note" style="margin-top:6px;font-size:11px;color:var(--down,#e5534b)">最近一次未記帳：'+_paperEsc(j.last_error.reason||j.last_error.status)+'</div>':'';
      // 先.四十八 二：樣本外警示（#428，數字已以結果檔程式核對）
      const oos='<div class="note" style="margin-top:6px;font-size:11px;color:var(--warn)">⚠ 樣本外（2025-01～2026-09，#428）：閘門 21 個持有月中 13 個月關閉，累積 +41.9%，落後 Bb-90 34.3pp、落後 0050 96.6pp。21 個月檢定力低，好壞都不構成證明。紙.三期間若閘門關閉占比 >50% 且落後 Bb-90 >10pp，進槓桿階段 1 須總司令另行裁示。</div>';
      if(!j.started)return _paperCardHtml(title,sub,_paperRow('閘門目前',_paperGateHtml(j.gate_now,null))+'<div style="margin-top:8px;font-size:14px;font-weight:700;color:var(--warn)">2026-10 月底建倉</div><div class="note" style="margin-top:4px;font-size:11px">建倉前不顯示淨值</div>'+err+oos);
      const sg=v=>v==null?'—':(v>=0?'+':'')+Number(v).toFixed(2)+'%';
      const wp=j.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k==='CASH'?'現金':k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml(title,sub,
        _paperRow('閘門目前',_paperGateHtml(j.gate_now,j.pending_switch))
        +_paperCommonRows(j,w||'—')
        +_paperRow('對照 Bb-90（同日起算）',sg(j.bench_bb90_return_pct))
        +_paperRow('對照 0050 全持有',sg(j.bench_0050_return_pct))+err+oos);
    }catch(e){
      console.warn('[_renderPaper3]',e);recordGlobalError('_renderPaper3',e);
      return _paperCardHtml(title,sub,'<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>');
    }
  }
  // 2026-10-10（先.五十九-A1／A2）：紙.四 R1（0050＋信用利差閘門×00631L），R1-C 為主、R1-A 並列。
  // 只讀 data/paper_4.json（兩本帳）與 data/paper_3.json（對照紙.三累積報酬）；揭露文字固定顯示。
  const PAPER4_DISCLOSURE='回測 2003–2024 年化 15.1%／MDD −36.2%；同一閘門在 2025–26 樣本外 21 個月中有 13 個月關閉並大幅落後 0050；無樣本外驗證，僅紙上追蹤';
  async function _renderPaper4(){
    const title='紙.四 R1 信用利差閘門',sub='主：R1-C 0050 50%＋00631L 50%｜並列：R1-A 70%／30%（閘門關時 00631L 改現金）';
    const disc='<div class="note" id="paper4-disclosure" style="margin-top:6px;font-size:11px;color:var(--warn)">⚠ '+_paperEsc(PAPER4_DISCLOSURE)+'。槓桿真錢提案最早 2027-04（紙.四 滿 6 個月）且須符合安全方案其餘前提。</div>';
    try{
      const [j,p3]=await Promise.all([_fetchPaperJson('data/paper_4.json'),_fetchPaperJson('data/paper_3.json').catch(e=>{console.warn('[_renderPaper4] paper_3',e);return {started:false}})]);
      const err=j.last_error?'<div class="note" style="margin-top:6px;font-size:11px;color:var(--down,#e5534b)">最近一次未記帳：'+_paperEsc(j.last_error.reason||j.last_error.status)+'</div>':'';
      if(!j.started||!j.books)return _paperCardHtml(title,sub,_paperRow('閘門目前',_paperGateHtml(j.gate_now,null))+'<div style="margin-top:8px;font-size:14px;font-weight:700;color:var(--warn)">2026-10 月底建倉（與紙.三 同日）</div><div class="note" style="margin-top:4px;font-size:11px">建倉前不顯示淨值</div>'+err+disc);
      const sg=v=>v==null?'—':(v>=0?'+':'')+Number(v).toFixed(2)+'%';
      const pri=j.books[j.primary||'R1-C']||Object.values(j.books)[0];
      const a=j.books['R1-A'];
      const wp=pri.weights_post||{};
      const w=Object.keys(wp).map(k=>_paperEsc(k==='CASH'?'現金':k)+' '+(wp[k]*100).toFixed(0)+'%').join('<br>');
      return _paperCardHtml(title,sub,
        _paperRow('閘門目前',_paperGateHtml(j.gate_now,pri.pending_switch))
        +_paperCommonRows(Object.assign({},pri,{history_months:pri.rows}),w||'—')
        +(a?_paperRow('並列 R1-A（70/30）',sg(a.total_return_pct)):'')
        +_paperRow('對照 0050 全持有',sg(pri.bench_0050_return_pct))
        +_paperRow('對照 Bb-90（同日起算）',sg(pri.bench_bb90_return_pct))
        +_paperRow('對照 紙.三 S3-C6',p3&&p3.started?sg(p3.total_return_pct):'—')+err+disc);
    }catch(e){
      console.warn('[_renderPaper4]',e);recordGlobalError('_renderPaper4',e);
      return _paperCardHtml(title,sub,'<div class="note" style="margin-top:8px">載入失敗：'+_paperEsc(e.message)+'</div>'+disc);
    }
  }
  async function loadPaper7030(){
    const el=document.getElementById('paper-7030-card');if(!el)return;
    try{
      const [a,b,c,d]=await Promise.all([_renderPaper7030(),_renderPaper1b(),_renderPaper3(),_renderPaper4()]);
      el.innerHTML='<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:10px">'+a+b+'<div style="grid-column:1 / -1">'+c+'</div><div style="grid-column:1 / -1" id="paper4-card">'+d+'</div></div>'
        +'<div class="note" style="margin:-4px 0 10px;text-align:center;color:var(--warn)">⚠ 紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。</div>';
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
          <div class="note">只有通過馬拉松完整驗證（含 holdout 解鎖）的策略才會上架這裡。研究進度見 research/MARATHON_STATE.md；上架規格見 research/PAPER_TRADING_ARCHITECTURE.md。</div>
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
      if(!card){toast('策略監控台查無此策略的報告段落');return}
      const det=card.querySelector('[id^="sm-detail-"]');if(det)det.style.display='';
      card.scrollIntoView({behavior:'smooth',block:'start'});
    }catch(e){console.warn('[openStrategyReport]',e);recordGlobalError('openStrategyReport',e)}
  }
  function toggleStrategyDetail(id){
    const el=document.getElementById(id);if(!el)return;
    el.style.display=el.style.display==='none'?'':'none';
  }
  async function loadStrategyMonitor(){
    const el=document.getElementById('strategy-monitor-list');if(!el)return;
    try{
      const r=await fetch('data/strategies.json?t='+Date.now());
      if(!r.ok){el.innerHTML='<div class="note">查無資料（data/strategies.json尚未產生）</div>';return}
      const json=await r.json();
      const list=json.strategies||[];
      if(!list.length){el.innerHTML='<div class="note">查無策略資料</div>';return}
      el.innerHTML=list.map((s,i)=>strategyMonitorCardHtml(s,i)).join('');
    }catch(e){
      console.warn('[loadStrategyMonitor]',e);recordGlobalError('loadStrategyMonitor',e);
      el.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
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
      if(snap.board!==board)continue;
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
        const snapshotCount=snapshots.filter(s=>s.board===board).length;
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
