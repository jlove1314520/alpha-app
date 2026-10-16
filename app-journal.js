// 常備.開發-20 丙案（2026-10-11 先.六十五）：日誌頁專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('journal') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // 日誌頁篩選：全部/台/美/期（用 filter chips，不是三選切換——日誌是回顧型清單，
  // 使用者可能同時想看混合結果，跟市場/選股/交易那種「當下只在一個市場」不同）。
  let JOURNAL_FILTER='ALL';
  const JOURNAL_CHIP_LABEL={ALL:'全部',TW:'台',US:'美',FUT:'期'};
  function renderJournalChips(){
    const el=document.getElementById('journal-chips');
    el.innerHTML=['ALL','TW','US','FUT'].map(k=>
      `<span class="press" style="flex-shrink:0;white-space:nowrap;font-size:12px;font-weight:${JOURNAL_FILTER===k?600:400};color:${JOURNAL_FILTER===k?'#1a1005':'var(--ink-2)'};background:${JOURNAL_FILTER===k?'var(--gold-grad)':'rgba(var(--fg-rgb),.05)'};border:1px solid ${JOURNAL_FILTER===k?'transparent':'rgba(var(--fg-rgb),.08)'};padding:6px 13px;border-radius:999px;cursor:pointer" onclick="setJournalFilter('${k}')">${JOURNAL_CHIP_LABEL[k]}</span>`
    ).join('');
    document.querySelectorAll('#journal-trades [data-mkt]').forEach(el=>{
      el.style.display=(JOURNAL_FILTER==='ALL'||el.dataset.mkt===JOURNAL_FILTER)?'':'none';
    });
  }
  function setJournalFilter(k){JOURNAL_FILTER=k;renderJournalChips()}
  async function loadWeeklyBrief(){
    const el=document.getElementById('journal-weekly-body');if(!el)return;
    try{
      const d=await loadDailyBrief();
      const w=d.weekly||{},ls=(w.lines||[]).slice();
      const rows=JOURNAL_LEDGER_CACHE&&JOURNAL_LEDGER_CACHE.rows;
      if(Array.isArray(rows)){
        const wk=rows.filter(x=>String(x.date||'')>=String(w.week_start||'9'));
        const c={};wk.forEach(x=>{const k=_autoStatusTxt(x.status);c[k]=(c[k]||0)+1});
        ls.push('自動投資 '+(w.week_start||'')+' 起委託 '+wk.length+' 筆'+(wk.length?'（'+Object.keys(c).map(k=>k+' '+c[k]).join('、')+'）':''));
      }else ls.push('自動投資：連上電腦才看得到本週委託');
      el.innerHTML=_briefLines(ls)+_briefFoot(d);
    }catch(e){console.warn('[loadWeeklyBrief]',e);recordGlobalError('loadWeeklyBrief',e);el.textContent='讀取週覆盤摘要失敗（'+(e&&e.message||e)+'）'}
  }
  // 常備.開發-26：系統週報（data/weekly_report.json，本機每週日 20:00 產出）。各區塊 level：ok／warn／bad／unknown。
  const _SYSWK_SEC=[['system_health','系統健康'],['freshness','資料新鮮度'],['research','研究進度'],['paper','紙上追蹤'],['live_execution','真錢執行']];
  const _SYSWK_DOT={ok:'#3fb37f',warn:'#d8b070',bad:'#e5534b',unknown:'#888'};
  function sysWeeklyHtml(d){
    const esc=_autoEsc,sm=d.summary||[];
    const rows=_SYSWK_SEC.map(([k,lab],i)=>{
      const s=d[k]||{},lv=s.level||'unknown';
      const txt=s.error?'讀取失敗（'+s.error+'）':(sm.find(x=>String(x).startsWith(lab))||'').replace(lab+'：','');
      return '<div style="padding:3px 0;display:flex;gap:8px;align-items:flex-start"><span style="flex-shrink:0;width:9px;height:9px;border-radius:50%;margin-top:5px;background:'+_SYSWK_DOT[lv]+'"></span><span><b>'+esc(lab)+'</b>　'+esc(uiPlain(txt||'—'))+'</span></div>';
    }).join('');
    const det=[];
    // 先.一〇三-13：多個停擺項目合併成一行（原本一項一行）
    const f=d.freshness||{},stl=(f.stalled||[]).map(x=>x.task+(x.age_min!=null?'（'+Math.round(x.age_min/60)+' 小時沒新產出）':''));
    if(stl.length)det.push('停擺：'+stl.join('、'));
    const lv=d.live_execution||{};if(lv.codes_week)det.push('真錢排程事件：'+Object.keys(lv.codes_week).map(k=>k+' '+lv.codes_week[k]).join('、'));
    ((d.paper||{}).books||[]).forEach(b=>{if(b.total_return_pct!=null)det.push(b.label+'：累計 '+(b.total_return_pct>0?'+':'')+b.total_return_pct+'%（'+(b.as_of||'—')+'）')});
    return '<div class="note" style="margin-bottom:4px">'+esc(d.week_start||'')+' ～ '+esc(d.week_end||'')+'</div>'+rows+
      (det.length?'<div style="margin-top:6px;font-size:11px;color:var(--ink-3)">'+det.map(x=>'· '+esc(uiPlain(x))).join('<br>')+'</div>':'')+_briefFoot(d);
  }
  async function loadSysWeekly(){
    const el=document.getElementById('journal-sysweekly');if(!el)return;
    try{
      const r=await fetch('data/weekly_report.json?t='+Date.now());
      if(r.status===404){el.textContent='尚未產生第一份週報（每週日 20:00 由電腦自動產生）';return}
      if(!r.ok)throw new Error('HTTP '+r.status);
      el.innerHTML=sysWeeklyHtml(await r.json());
    }catch(e){console.warn('[loadSysWeekly]',e);recordGlobalError('loadSysWeekly',e);el.textContent='讀取系統週報失敗（'+(e&&e.message||e)+'）'}
  }
  // 先.八十二-10：真錢持股卡（/auto/ledger 的 holdings）。每次連線成功就存一份在手機（localStorage，只在本機），
  // 電腦離線或讀取失敗時改顯示最後一次同步的內容與時間；從沒同步過就照實說。
  const HOLD_KEY='alpha_live_holdings_v1';
  function holdingsCacheSave(h){try{localStorage.setItem(HOLD_KEY,JSON.stringify({at:new Date().toISOString(),holdings:h}))}catch(e){console.warn('[holdingsCacheSave]',e)}}
  function holdingsCacheLoad(){try{return JSON.parse(localStorage.getItem(HOLD_KEY)||'null')}catch(e){console.warn('[holdingsCacheLoad]',e);return null}}
  function holdingsHtml(h){
    const esc=_autoEsc,n=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2}),md=d=>d?String(d).slice(5).replace('-','/'):'—';
    if(!Array.isArray(h))return '無法計算持股（'+esc((h&&h.error)||'伺服器未回傳')+'）';
    if(!h.length)return '目前沒有自動交易買進的持股';
    return h.map(x=>{
      const up=(x.pnl||0)>=0,st=x.settlement||{};
      const stTxt=st.status==='pending'?'<span style="color:var(--note-gold)">待交割（'+md(st.date)+' 扣款）</span>':'已交割（'+md(st.date)+'）';
      return '<div style="padding:6px 0;border-bottom:1px solid var(--hairline)">'+
        '<div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(x.symbol)+' '+esc(nameOf(x.symbol)!==x.symbol?nameOf(x.symbol):'')+'</b><span>'+n(x.qty)+' 股</span></div>'+
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:12px;margin-top:2px"><span>成本 '+n(x.cost)+' 元（均價 '+n(x.avg_cost)+'）</span><span>市值 '+n(x.value)+' 元</span></div>'+
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:12px;margin-top:2px"><span>損益 <b class="'+(up?'pos':'neg')+'">'+(up?'+':'')+n(x.pnl)+' 元'+(x.pnl_pct!=null?'（'+(x.pnl_pct>0?'+':'')+x.pnl_pct+'%）':'')+'</b></span><span>'+stTxt+'</span></div>'+
        '<div style="font-size:10px;color:var(--ink-4);margin-top:2px">'+md(x.close_date)+' 收盤 '+n(x.close)+' 估值</div></div>';
    }).join('')+'<div style="font-size:10px;color:var(--ink-4);margin-top:6px">只算自動交易買進的股數；未計手續費與稅；交割日依成交日起 T+2 交易日推算。</div>';
  }
  function renderHoldings(h,syncedNote){
    const el=document.getElementById('journal-holdings');if(!el)return;
    const card=document.getElementById('journal-holdings-card');if(card)card.hidden=false;
    el.innerHTML=holdingsHtml(h)+(syncedNote?'<div class="note" data-ui-keep style="margin-top:4px;color:var(--note-gold)">'+_autoEsc(syncedNote)+'</div>':'');
  }
  function renderHoldingsFromCache(why){
    const c=holdingsCacheLoad(),el=document.getElementById('journal-holdings');
    const card=document.getElementById('journal-holdings-card'),ln=document.getElementById('journal-offline-line');
    if(!c||!c.holdings){
      if(el)el.textContent=why+'，尚未同步過持股資料';
      // 先.一〇四：從沒同步過＝這張卡沒有任何資訊，收起並併入離線那一行（首屏卡數，先.七十二-C8）
      if(card)card.hidden=true;
      if(ln){ln.hidden=false;ln.textContent='自動投資帳本、真錢持股：連上電腦才看得到 →'}
      return}
    if(card)card.hidden=false;
    const t=new Date(c.at),md=t.toLocaleDateString('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit'});
    renderHoldings(c.holdings,why+'，顯示 '+md+' '+fmtTzHHMM(t,'Asia/Taipei')+' 最後同步的資料');
  }
  async function loadJournalLedger(){
    const pe=document.getElementById('journal-pnl'),te=document.getElementById('journal-trades');
    if(!pe||!te)return;
    // 先.七十二-B5／C8：離線時三張自動投資卡收起、只留一行
    const off=!LIVE.configured||!LIVE.url;
    try{const ln=document.getElementById('journal-offline-line');if(ln)ln.hidden=!off;document.querySelectorAll('#scr-journal [data-ui-live]').forEach(c=>{c.hidden=off})}catch(e){console.warn('[journal offline]',e);recordGlobalError('journal offline',e)}
    if(off)_safeSync('renderHoldingsFromCache',()=>renderHoldingsFromCache('電腦未連線'));
    if(off){pe.textContent='連上電腦才看得到';te.innerHTML='<div class="note" style="padding:14px 2px">連上電腦才看得到</div>';setTxt('journal-perf','尚未連線本機伺服器，真錢績效對照只在本機計算。');setTxt('journal-review','尚未連線本機伺服器，盤後復盤只在本機產生。');return}
    try{
      const d=await loadAutoLedger();
      JOURNAL_LEDGER_CACHE=d;_safeAsync('loadWeeklyBrief',loadWeeklyBrief);
      _safeSync('renderHoldings',()=>{const h=d&&d.holdings!==undefined?d.holdings:{error:'伺服器是舊版，沒有持股欄位（需重啟）'};if(Array.isArray(h))holdingsCacheSave(h);renderHoldings(h)});
      setTxt('journal-tm',fmtTzHHMM(new Date(),'Asia/Taipei'));
      const rows=d&&d.rows||[];
      te.innerHTML=rows.length?rows.map(autoLedgerRowHtml).join(''):'<div class="note" style="padding:14px 2px">首批尚未執行</div>';
      const p=d&&d.pnl;
      const sg=v=>v==null?'—':(v>0?'+':'')+Number(v).toLocaleString('zh-TW');
      if(!d||!d.first_batch_done)pe.innerHTML='首批尚未執行'+(rows.length?'（目前只有未成交的委託紀錄，見下方）':'');
      else if(!p||p.error)pe.textContent='無法估值：'+(p&&p.error||'伺服器未回傳損益');
      else pe.innerHTML='本週：<b class="'+(p.week>=0?'pos':'neg')+'">'+sg(p.week)+' 元</b>　累計：<b class="'+(p.total>=0?'pos':'neg')+'">'+sg(p.total)+' 元'+(p.total_pct!=null?'（'+(p.total_pct>0?'+':'')+p.total_pct+'%）':'')+'</b><br><span class="note">估值基準日 '+_autoEsc(p.as_of)+'；本週自 '+_autoEsc(p.week_start)+' 起</span>';
      _safeSync('renderJournalPerf',()=>renderJournalPerf(d));
      _safeSync('renderJournalReview',()=>renderJournalReview(d));
      renderJournalChips();
    }catch(e){
      console.warn('[loadJournalLedger]',e);recordGlobalError('loadJournalLedger',e);
      _safeSync('renderHoldingsFromCache',()=>renderHoldingsFromCache('電腦離線或讀取失敗'));
      pe.textContent='讀取真錢帳本失敗（'+(e&&e.message||e)+'）';
      te.innerHTML='<div class="note" style="padding:14px 2px">讀取失敗，請確認本機伺服器在線</div>';
      setTxt('journal-perf','讀取真錢帳本失敗，無法畫績效對照');
      setTxt('journal-review','讀取真錢帳本失敗，無法顯示盤後復盤');
    }
  }
  // 常備.開發-12：真錢績效對照（累計淨值 vs 同期 0050 全持有）。資料由伺服器 auto_ledger_view.perf_series() 算好，這裡只畫。
  function journalPerfSvg(pts){
    const W=320,H=140,pad=4,vals=pts.flatMap(p=>[p.nav,p.bench]).concat([1]);
    const mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||0.01;
    const X=i=>pad+(pts.length>1?i/(pts.length-1):0.5)*(W-2*pad),Y=v=>pad+(1-(v-mn)/rg)*(H-2*pad);
    const line=k=>pts.length>1?pts.map((p,i)=>X(i).toFixed(1)+','+Y(p[k]).toFixed(1)).join(' '):(pad+','+Y(pts[0][k]).toFixed(1)+' '+(W-pad)+','+Y(pts[0][k]).toFixed(1));
    return '<svg width="100%" height="'+H+'" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+
      '<line x1="'+pad+'" y1="'+Y(1).toFixed(1)+'" x2="'+(W-pad)+'" y2="'+Y(1).toFixed(1)+'" stroke="var(--hairline)" stroke-width="1" stroke-dasharray="3,2"/>'+
      '<polyline points="'+line('bench')+'" fill="none" stroke="var(--ink-3)" stroke-width="2"/>'+
      '<polyline points="'+line('nav')+'" fill="none" stroke="var(--accent)" stroke-width="2.5"/></svg>';
  }
  function renderJournalPerf(d){
    const el=document.getElementById('journal-perf');if(!el)return;
    const esc=_autoEsc,pf=d&&d.perf;
    if(!d||!d.first_batch_done||!pf){el.innerHTML='<b>尚無部位</b>（首批成交後自動出現累計淨值與同期 0050 全持有對照）';return}
    if(pf.error||!Array.isArray(pf.points)||!pf.points.length){el.textContent='無法畫績效對照：'+(pf.error||'伺服器未回傳序列');return}
    // 先.一〇八-2：差距是「贏輸」不是「漲跌」，改中性色＋領先／落後（同 app.js _scVs，UX 提案①）
    const pc=v=>(v>0?'+':'')+v+'%',cls=v=>v>=0?'pos':'neg',diff=Math.round((pf.nav_pct-pf.bench_pct)*100)/100;
    el.innerHTML=journalPerfSvg(pf.points)+
      '<div style="display:flex;gap:14px;font-size:12px;margin-top:4px"><span><span style="color:var(--accent)">━</span> Bb-90 自動交易 <b class="'+cls(pf.nav_pct)+'">'+pc(pf.nav_pct)+'</b></span>'+
      '<span><span style="color:var(--ink-3)">━</span> 同期 0050 全持有 <b class="'+cls(pf.bench_pct)+'">'+pc(pf.bench_pct)+'</b></span></div>'+
      '<div style="margin-top:4px;font-size:12px">跟 0050 差多少：<b class="journal-gap" style="color:var(--ink)">'+(Math.abs(diff)<0.005?'持平 0 個百分點':(diff>0?'領先 ':'落後 ')+Math.abs(diff)+' 個百分點')+'</b>（'+esc(pf.start)+' 起至 '+esc(pf.as_of)+'，'+pf.points.length+' 個交易日）</div>'+
      '<div style="margin-top:6px;font-size:10px;color:var(--ink-4)"><b>含手續費、未含稅</b>。'+esc(pf.note||'')+'；累計淨值＝持股市值÷累計投入。唯讀；非投資建議</div>';
  }
  // 常備.開發-23：盤後復盤（/auto/ledger 的 review＝伺服器讀 LIVE/review_YYYYMMDD.json，13:40 結算後自動產出）。這裡只畫。
  const JOURNAL_ODD_LABEL={MATCH:'相符',MISMATCH:'不符',MISSING:'驗證檔未產生',NO_ODD:'當日無零股委託'};
  function renderJournalReview(d){
    const el=document.getElementById('journal-review');if(!el)return;
    const esc=_autoEsc,rv=d&&d.review;
    if(rv===undefined){el.textContent='伺服器未回傳復盤欄位（可能是舊版，需重啟）';return}
    if(!rv){el.innerHTML='<b>尚無復盤</b>（首批送單當天 13:40 結算後自動產生）';return}
    if(rv.error){el.textContent='無法顯示盤後復盤：'+rv.error;return}
    const s=rv.summary||{},pc=v=>v==null?'—':(v>0?'+':'')+v+'%';
    const slipCls=v=>v==null?'':(v>0?'neg':'pos');
    const odd=rv.odd_lot||{},dv=rv.deviation,nx=rv.next_run;
    const rows=(rv.orders||[]).map(o=>'<tr><td>'+esc(o.symbol)+' '+esc(o.lot)+'</td><td style="text-align:right">'+(o.filled_qty||0)+'/'+(o.qty||0)+'</td><td style="text-align:right">'+(o.avg_price!=null?esc(o.avg_price):'—')+'</td><td style="text-align:right">'+(o.ref_price!=null?esc(o.ref_price):'—')+(o.ref_source==='prev_close'?'*':'')+'</td><td style="text-align:right" class="'+slipCls(o.slippage_pct)+'">'+pc(o.slippage_pct)+'</td><td>'+esc(_autoStatusTxt(o.status))+'</td></tr>').join('');
    const rej=(rv.rejects||[]).map(r=>(r.symbol?esc(r.symbol)+'：':'')+esc(_autoCodesTxt(r.codes))).join('；');
    el.innerHTML='<div style="font-size:12px">日期 <b>'+esc(rv.date)+'</b>　批次 '+esc((rv.batches||[]).join('、')||'—')+'</div>'+
      '<div style="margin-top:4px">送單 <b>'+(s.n_orders||0)+'</b> 筆　全數成交 <b>'+(s.n_filled||0)+'</b> 筆　成交率 <b>'+(s.fill_rate_pct!=null?s.fill_rate_pct+'%':'—')+'</b>　加權滑價 <b class="'+slipCls(s.slippage_pct_weighted)+'">'+pc(s.slippage_pct_weighted)+'</b>'+(s.all_final===false?'　<span style="color:var(--warn)">尚有未終結委託</span>':'')+'</div>'+
      (rows?'<table style="width:100%;font-size:11px;margin-top:6px;border-collapse:collapse"><tr style="color:var(--ink-3)"><td>標的</td><td style="text-align:right">成交/委託</td><td style="text-align:right">均價</td><td style="text-align:right">參考價</td><td style="text-align:right">滑價</td><td>狀態</td></tr>'+rows+'</table>':'')+
      (rej?'<div style="margin-top:4px">拒單：'+rej+'</div>':'')+
      '<div style="margin-top:4px">零股驗證：<b>'+esc(JOURNAL_ODD_LABEL[odd.status]||odd.status||'—')+'</b></div>'+
      '<div>偏離目標權重：'+(dv?'最大 <b'+(dv.max_abs_pp>dv.threshold_pp?' style="color:var(--warn)"':'')+'>'+esc(dv.max_abs_pp)+' 個百分點</b>（告警門檻 '+esc(dv.threshold_pp)+'）':'尚未計算')+'</div>'+
      '<div>下期：<b>'+(nx?esc(nx.date)+' '+esc(nx.time||'')+'（'+esc(AUTO_REASON_LABEL[nx.reason]||nx.reason)+'）':'讀不到交易日曆')+'</b></div>'+
      '<div style="margin-top:6px;font-size:10px;color:var(--ink-4)">滑價＝成交均價÷參考價−1（買進，正值＝買貴）；參考價＝永豐平盤參考價，標 * 者為前一交易日收盤後備。產生於 '+esc(String(rv.generated_at||'').slice(0,16).replace('T',' '))+'。唯讀；非投資建議</div>';
  }
  // 先.八十二-9／先.八十三-5（2026-10-13）：研究成績單——試驗帳本＋墓園驗屍（A／B／C）＋樣本外對 0050。
  // 資料檔 data/research_scorecard.json（scripts/build_research_scorecard.py，每日排程只讀既有檔重產）；結論句由資料算出，這裡只畫。
  async function loadResearchScorecard(){
    const el=document.getElementById('journal-research');if(!el)return;
    try{
      const r=await fetch('data/research_scorecard.json?t='+Date.now());
      if(!r.ok)throw new Error('HTTP '+r.status);
      el.innerHTML=researchScorecardHtml(await r.json());el.dataset.loaded='1';
    }catch(e){console.warn('[loadResearchScorecard]',e);recordGlobalError('loadResearchScorecard',e);el.textContent='讀取研究成績單失敗（'+(e&&e.message||e)+'）';el.dataset.loaded='err'}
  }
  function researchScorecardHtml(d){
    const esc=_autoEsc,n=v=>v==null?'—':Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2}),pp=v=>v==null?'—':(v>0?'+':'')+n(v);
    const t=d.trials||{},a=d.autopsy||{},o=d.oos||{},c=a.counts||{},lb=a.labels||{};
    const sec=(h,b)=>'<div style="margin-top:10px"><div style="font-weight:600;font-size:13px">'+h+'</div>'+b+'</div>';
    // 先.一〇四-16：成績單先只給「標題＋3 個數字」，其餘全文收進「展開看全文」
    const _ls=(o.lines||[]).filter(x=>x.days),_mat=_ls.filter(x=>o.min_days==null||x.days>=o.min_days),_win=_mat.filter(x=>x.gap_pp!=null&&x.gap_pp>0);
    const _stat=(v,l)=>'<div style="flex:1;min-width:0;text-align:center;padding:6px 4px;border:1px solid var(--hairline);border-radius:10px"><div class="num" style="font-size:18px;font-weight:700;color:var(--ink)">'+v+'</div><div style="font-size:10.5px;color:var(--ink-3)">'+l+'</div></div>';
    const head='<div style="font-size:14px;font-weight:600;line-height:1.5">'+esc(o.conclusion||'樣本外對照讀取失敗')+'</div>'
      +'<div style="display:flex;gap:6px;margin-top:8px">'+_stat(t.error?'—':n(t.count),'測過的方法')+_stat(a.error?'—':n(a.total),'已判死')
      +_stat(o.error?'—':(_mat.length?(_win.length+'／'+_mat.length):'—'),_mat.length?'樣本外贏 0050':('樣本外未滿 '+n(o.min_days)+' 天'))+'</div>';
    let h="";
    h+=sec('一、測過幾種方法',t.error?'<div class="note">讀取失敗：'+esc(t.error)+'</div>':
      '<div class="note">試驗帳本共 <b>'+n(t.count)+'</b> 筆（就是多重比較用的試驗總數；框架自檢只列出、不計入）。</div>'+
      '<div class="note">'+(t.by_verdict||[]).map(([k,v])=>esc(k)+' '+n(v)).join('、')+'</div>'+
      '<div class="note" style="color:var(--ink-3)">「通過判準」多半只過了單一關卡或屬於配置類（例：#418 股債配置），不等於贏 0050；贏不贏看第三段。</div>');
    const rows=(a.rows||[]);
    h+=sec('二、各自為什麼死（墓園 '+n(a.total)+' 條）',a.error?'<div class="note">讀取失敗：'+esc(a.error)+'</div>':
      ['A','B','C'].map(k=>'<div class="note"><b>'+k+' '+esc(lb[k]||'')+'</b>：'+n(c[k])+' 條</div>').join('')+
      '<div class="note" style="color:var(--ink-3)">其中 '+n(a.borderline)+' 條是邊界判斷。A 類要先修再重新事前登記；B 類補得到資料才開案；C 類不得調參重測。</div>'+
      '<details style="margin-top:6px"><summary class="press" style="font-size:12px;color:var(--accent)">看全部 '+rows.length+' 條死因</summary>'+
      rows.map(x=>'<div style="padding:5px 0;border-bottom:1px solid var(--hairline);font-size:11.5px"><b>'+esc(x.class)+(x.borderline?'（邊界）':'')+'</b> '+esc(x.name)+'<span style="color:var(--ink-4)">（'+esc(x.date)+'）</span><br>'+esc(x.why)+'</div>').join('')+'</details>');
    const ls=(o.lines||[]).filter(x=>x.days);
    h+=sec('三、樣本外對照 0050（上線後的真實走勢）',o.error?'<div class="note">讀取失敗：'+esc(o.error)+'</div>':
      ls.map(x=>'<div style="padding:5px 0;border-bottom:1px solid var(--hairline);font-size:12px"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(x.label)+'</b><span>'+esc(x.judge)+'</span></div>'+
        '<div style="color:var(--ink-3)">'+esc(String(x.start||'').slice(5))+'～'+esc(String(x.as_of||'').slice(5))+'（'+n(x.days)+' 個交易日）：策略 '+pp(x.ret_pct)+'%，同期 0050 '+pp(x.bench_pct)+'%，差 '+pp(x.gap_pp)+' 個百分點；最大回撤 '+n(x.mdd_pct)+'%（0050 '+n(x.bench_mdd_pct)+'%）</div></div>').join('')+
      '<div class="note" style="color:var(--ink-3)">樣本外滿 '+n(o.min_days)+' 個交易日才拿來判斷贏輸；天數不足的領先或落後都只是暫時的。</div>'+
      // 先.九十一-1：還沒開始的線也列出（含設計註記，例：模擬 F 學界已知現象、只是研究）
      (o.lines||[]).filter(x=>!x.days&&(x.design_note||x.candidacy)).map(x=>'<div class="note sc-soon-note" style="font-size:11.5px;color:var(--ink-3)">即將開始：<b>'+esc(x.label)+'</b>（'+esc(String(x.start||'').slice(5).replace('-','/'))+' 起）'+(x.design_note?'；'+esc(x.design_note):'')+(x.candidacy?'；'+esc(x.candidacy):'')+'</div>').join(''));
    // 先.九十一-1／-5-1：四、研究說明（已知現象與不做的路線）
    if((d.notes||[]).length)h+=sec('四、研究說明',(d.notes||[]).map(x=>'<div class="note rs-note" style="padding:4px 0"><b>'+esc(x.title)+'</b><br>'+esc(x.body)+'</div>').join(''));
    h+='<div style="margin-top:8px;font-size:10px;color:var(--ink-4)">資料：試驗帳本、墓園驗屍（研究紀錄）、策略曲線；產生於 '+esc(String((d.meta||{}).generated_at||'').slice(0,16).replace('T',' '))+'；研究紀錄整理。</div>';
    return head+'<details class="rs-full" style="margin-top:8px"><summary class="press" style="font-size:12px;color:var(--accent);cursor:pointer">展開看全文</summary>'+h+'</details>';
  }
