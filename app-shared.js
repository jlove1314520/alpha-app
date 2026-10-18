// 常備.開發-20 丙案（2026-10-11 先.六十五）：多個分頁共用（市場／選股／個股／交易之間）專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('shared') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // ── 2026-10-08（先.五十一-3）處置／注意股旗標：data/disposal_flags.json（每日 18:30
  // scripts/build_disposal_flags.py，Shioaji punish/notice＋TPEx 交叉補）。載不到就當作
  // 「沒有旗標」，不擋任何畫面；失敗記進診斷 log。
  let DISPOSAL_FLAGS=null,DISPOSAL_FLAGS_AT=0;
  async function ensureDisposalFlags(){
    if(DISPOSAL_FLAGS&&Date.now()-DISPOSAL_FLAGS_AT<30*60e3)return DISPOSAL_FLAGS;
    try{
      const r=await fetch('data/disposal_flags.json?t='+Math.floor(Date.now()/1800000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      DISPOSAL_FLAGS=await r.json();DISPOSAL_FLAGS_AT=Date.now();
    }catch(e){
      console.warn('[ensureDisposalFlags]',e);recordGlobalError('ensureDisposalFlags',e);
      if(!DISPOSAL_FLAGS)DISPOSAL_FLAGS={disposal:{},notice:{}};
    }
    return DISPOSAL_FLAGS;
  }
  function _twTodayIso(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
  // 回 {kind:'disposal'|'disposal_upcoming'|'notice', ...}；沒有旗標回 null。
  // 處置：今天落在起訖期間內＝處置中；公告了但還沒開始＝即將處置。迄日已過不算。
  // 注意：公布日在 5 個日曆天內才算（注意股是逐日公布，舊的不再有意義）。
  function disposalFlagOf(code,todayIso){
    try{
      const f=DISPOSAL_FLAGS;if(!f||!code)return null;
      const t=todayIso||_twTodayIso();
      const d=(f.disposal||{})[code];
      if(d&&d.end&&d.end>=t)return {...d,kind:(d.start&&d.start>t)?'disposal_upcoming':'disposal'};
      const n=(f.notice||{})[code];
      if(n&&n.announced&&(Date.parse(t)-Date.parse(n.announced))/864e5<=5)return {...n,kind:'notice'};
      return null;
    }catch(e){console.warn('[disposalFlagOf]',e);recordGlobalError('disposalFlagOf',e);return null}
  }
  const FM_TTL=3*60*1000; // localStorage 快取有效期：3 分鐘，過期後才重新打 FinMind
  const _d=n=>new Date(Date.now()-n*864e5).toISOString().slice(0,10);
  // 2026-09-15（P0產品.四）骨架屏共用函式：n行、每行寬度輪流取樣，取代純文字「載入中…」。
  const SKEL_WIDTHS=['w80','w60','w40','w30'];
  function skeletonHtml(n){
    n=n||3;
    let out='';
    for(let i=0;i<n;i++)out+=`<div class="skel-line ${SKEL_WIDTHS[i%SKEL_WIDTHS.length]}"></div>`;
    return out;
  }
  // 自選股/選股榜這類「一列一列」的清單專用骨架，形狀比純文字更接近載入完成後的樣子。
  function skeletonRowsHtml(n){
    n=n||3;
    let out='';
    for(let i=0;i<n;i++)out+=`<div style="padding:10px 0;border-bottom:1px solid var(--hairline)"><div class="skel-line w40"></div><div class="skel-line w80" style="height:9px"></div></div>`;
    return out;
  }
  function fmCacheRead(k){
    if(_cache[k])return _cache[k];
    try{
      const raw=localStorage.getItem('fmc_'+k);if(!raw)return null;
      const o=JSON.parse(raw);if(Date.now()-o.t>FM_TTL)return null;
      _cache[k]=o.d;return o.d;
    }catch(e){console.warn('[fmCacheRead]',e);recordGlobalError('fmCacheRead',e);return null}
  }
  function fmCacheWrite(k,d){
    _cache[k]=d;
    try{localStorage.setItem('fmc_'+k,JSON.stringify({t:Date.now(),d}))}catch(e){console.warn('[fmCacheWrite]',e);recordGlobalError('fmCacheWrite',e)} // 存滿了就算了，不影響功能
  }
  async function fm(ds,id,start){
    const k=ds+id+start;
    const cached=fmCacheRead(k);if(cached){FM_LAST_FAILED=false;return cached}
    try{
      const r=await fetch(`${FM}?dataset=${ds}&data_id=${id}&start_date=${start}`);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const j=await r.json();
      const d=(j&&Array.isArray(j.data))?j.data:[];
      fmCacheWrite(k,d);
      FM_LAST_FAILED=false;FM_LAST_ERR='';
      return d;
    }catch(e){
      // 2026-08-27：這裡刻意不call recordGlobalError()——fm()是高頻呼叫的資料層
      // 函式，FinMind額度用盡時可能短時間內失敗幾十次，全部灌進診斷橫幅的錯誤log
      // 會淹沒真正的程式邏輯bug。這類失敗已經有專門的UI機制處理（FM_LAST_FAILED+
      // fmEmptyMsg()讓每個面板顯示「連線失敗」），不需要疊加一份錯誤log。
      console.warn('[Alpha] FinMind 抓取失敗（不回退舊資料，誠實回報查無資料）：',ds,id,e);
      FM_LAST_FAILED=true;FM_LAST_ERR=fmErrReason(e);
      return [];
    }
  }
  // 先.八十一-10：fmErrReason 移到 app.js（核心，首頁搜尋補查也要用），這裡直接呼叫全域那支
  function fmEmptyMsg(fallback){return FM_LAST_FAILED?((FM_LAST_ERR||'FinMind 連線失敗')+'，請稍後再試'):fallback}
  // 2026-08-27新增（B4：類股卡點擊→成分股清單）：data/company_info.json
  // （見 research/build_company_info.py，讀FinMind TaiwanStockInfo全市場快取）
  // 供代號→名稱/產業分類查詢；data/quotes_all_tw.json（見
  // .github/scripts/update_price_history.py，從price_history.json算出的輕量
  // 快照)供全市場（不只自選股）最新收盤/漲跌%/成交值查詢，避免載入32MB+的
  // 完整price_history.json。
  let COMPANY_INFO_CACHE=null;
  async function loadCompanyInfo(){
    if(!COMPANY_INFO_CACHE){
      try{const r=await fetch('data/company_info.json?t='+Date.now());if(r.ok)COMPANY_INFO_CACHE=await r.json()}catch(e){console.warn('[loadCompanyInfo]',e);recordGlobalError('loadCompanyInfo',e);COMPANY_INFO_CACHE={companies:{}}}
    }
    return (COMPANY_INFO_CACHE&&COMPANY_INFO_CACHE.companies)||{};
  }
  // 先.六十-C9：非每日排程的資料檔，在 App 上標「資料日 YYYY-MM-DD（N 天前）＋更新方式」，不讓舊快照看起來像當天資料
  function _dataDateLabel(iso,how){
    const t=new Date(iso);if(isNaN(t))return '—';
    const days=Math.floor((Date.now()-t.getTime())/86400000);
    return '資料日 '+fmtTzMMDDHHMM(t,'Asia/Taipei').slice(0,5).replace(/^(\d+)\/(\d+)$/,'$1/$2')+'（'+(days<=0?'今天':days+' 天前')+'）'+(how?'；'+how:'');
  }

  // 2026-09-15（週六.三／稽核二.五）零基線柱狀圖：正值柱從共用基線往上長、負值柱
  // 從同一條基線往下長，取代舊版「單一bar在盒子裡置中」（那樣正負值都各自往兩邊
  // 對稱長，視覺上沒有共用基線，容易誤讀漲跌幅度）。.up-zone/.dn-zone各佔一半高度，
  // 兩者交界（.dn-zone的border-top）就是基線，同一列的每一欄交界y座標理論上相同。
  // 先.一〇四-7：第 4 參數 valTxt（選填）＝在這根柱子旁標數值（法人買賣超只標最新一根）
  function divBarHTML(label,v,mx,valTxt){
    const h=Math.max(15,Math.abs(v)/mx*100).toFixed(0);
    // 數值絕對定位、放在沒有柱子的那一半（正值放基線下方、負值放基線上方），不佔版面、不推動零基線（smoke #49）
    const tag=valTxt?`<b class="db-val ${v>=0?'pos-v':'neg-v'}" style="color:${v>=0?'var(--up)':'var(--down)'}">${valTxt}</b>`:'';
    const up=v>=0?`<i class="u" style="height:${h}%"></i>`:'';
    const dn=v<0?`<i class="dn" style="height:${h}%"></i>`:'';
    return `<div class="db${valTxt?' has-val':''}">${tag}<div class="bar-zone"><div class="up-zone">${up}</div><div class="dn-zone">${dn}</div></div><em style="font-size:9px;color:var(--ink-3)">${label}</em></div>`;
  }

  // 2026-08-25 新增：大盤（全市場）融資維持率。這個數字沒辦法在瀏覽器端直接算——
  // 需要「每一檔股票融資餘額(張)×現價」逐檔加總才是真正的擔保品市值，TWSE openapi
  // 雖然免費但不支援瀏覽器CORS，所以改成 alpha-data 這邊用 Python 每天算好、寫成一個
  // 小 JSON 檔（data/margin_maintenance.json，跟這個網站同網域，沒有 CORS 問題），
  // 這裡單純 fetch 那個檔案顯示，不是打 FinMind／TWSE。見
  // alpha-data/compute_margin_maintenance.py 的完整說明。
  function marginLevel(pct){
    if(pct==null)return null;
    if(pct<130)return{l:'斷頭區',c:'var(--critical)'};
    if(pct<150)return{l:'危險',c:'var(--serious)'};
    if(pct<160)return{l:'注意',c:'var(--warn)'};
    return{l:'正常',c:'var(--good)'};
  }
  const MKT_LABEL={TW:'台股',US:'美股',FUT:'期貨'};
  // 先.一〇四-17：選股頁的「期貨」目前是空頁，先隱藏（等總司令決策 3）；市場頁、交易頁照舊三個
  const MKT_HIDDEN={picks:['FUT']};
  function renderMktToggle(page){
    const el=document.getElementById(page+'-toggle');if(!el)return;
    const hide=MKT_HIDDEN[page]||[];
    if(hide.includes(MKT_STATE[page]))MKT_STATE[page]='TW';
    el.innerHTML=['TW','US','FUT'].filter(m=>!hide.includes(m)).map(m=>
      `<span class="press mtg-opt${MKT_STATE[page]===m?' on':''}" onclick="setMarketToggle('${page}','${m}')">${MKT_LABEL[m]}</span>`
    ).join('');
  }
  function setMarketToggle(page,mkt){
    MKT_STATE[page]=mkt;
    renderMktToggle(page);
    if(page==='market')onMarketToggleChange();
    if(page==='picks')onPicksToggleChange();
    if(page==='trade')onTradeToggleChange();
  }
  function onMarketToggleChange(){
    const mkt=MKT_STATE.market;
    document.getElementById('market-tw-panel').style.display=mkt==='TW'?'':'none';
    document.getElementById('market-us-panel').style.display=mkt==='US'?'':'none';
    document.getElementById('market-fut-panel').style.display=mkt==='FUT'?'':'none';
    if(mkt==='US')loadMarketUS();
    if(mkt==='FUT')loadMarketFUT();
  }
  function autoLedgerRowHtml(x){
    const esc=_autoEsc;
    const q=x.filled_qty&&x.filled_qty!==x.qty?(x.filled_qty+'／'+x.qty):String(x.qty||0);
    const why=x.reason_codes&&x.reason_codes.length?'（'+esc(_autoCodesTxt(x.reason_codes))+'）':'';
    return '<div data-mkt="TW" style="display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--hairline);font-size:12.5px">'+
      '<span>'+esc(String(x.date||'').slice(5).replace('-','/'))+' <b>'+esc(x.symbol||'—')+'</b> '+esc(_autoStatusTxt(x.status))+why+'</span>'+
      '<span class="num" style="text-align:right;white-space:nowrap">'+esc(q)+' 股'+(x.avg_price!=null?' @'+esc(x.avg_price):'')+' <span class="note">'+esc(x.batch||'')+'</span></span></div>';
  }
  const TRADE_UNIT_NOTE={TW:'單位：張數（台股現股/當沖以張為單位）',US:'單位：股數（美股以股為單位，無「張」概念）',FUT:'單位：口數；另顯示保證金水位與轉倉提醒'};
  const AUTO_STATUS_LABEL={FILLED:'成交',PARTIAL:'部分成交',SUBMITTED:'已送出',OPEN:'掛單中',CANCELLED:'已取消',REJECT:'拒單',SKIP:'略過'};
  const _autoStatusTxt=s=>AUTO_STATUS_LABEL[s]||String(s||'—');
  function onTradeToggleChange(){
    const mkt=MKT_STATE.trade;
    setTxt('trade-unit-note',TRADE_UNIT_NOTE[mkt]);
    document.querySelectorAll('#scr-trade [data-mkt]').forEach(el=>{
      el.style.display=el.dataset.mkt===mkt?'':'none';
    });
  }

  // ══════ 選股頁（research/score.py 產生的 scores.json，非即時，需本機/排程重新產生）══════
  // ══════ 選股頁 + 個股研究報告頁（scoring-v2，2026-08-24 改版）══════
  // scores.json 格式改版依據 docs/Alpha_評分引擎_10分制設計小抄.md 第五節：
  // json.stocks（不是舊版的 json.scores）、每檔 code/name/industry/rank/total_score(0~10)/
  // coverage/summary/factors{score,percentile,raw,reason}。舊版 composite/_meta/stock_id
  // 欄位已經不存在，這裡整段跟著改，不是選擇性相容兩種格式。
  let PICKS_CACHE=null;
  // 2026-08-27新增（策略層面決定：拆成三個獨立榜單，不要用單一分數通吃）：
  // 價值成長榜/題材動能榜/未來性濾網完全獨立的資料/因子集合，各自分開存放
  // cache，切換榜單不需要重新fetch（除非強制重新整理）。
  let PICKS_MOMENTUM_CACHE=null;
  let PICKS_FUTURE_CACHE=null;
  const FACTOR_LABELS={
    low_vol:'低波動', earnings_growth:'財報成長', revenue_momentum:'營收動能', growth_quality:'成長性/未來性',
    chips:'籌碼', technical:'技術型態', valuation_adj:'估值(成長調整)',
    analyst:'機構觀點', catalyst:'題材/事件',
  };
  const FACTOR_ORDER=['low_vol','earnings_growth','revenue_momentum','growth_quality','chips','technical','valuation_adj','analyst','catalyst'];
  // 題材動能榜的因子集合，跟上面價值成長榜完全獨立（見
  // research/generate_scores_momentum.py檔頭說明：因子/權重各自版本控管）。
  const MOMENTUM_FACTOR_LABELS={
    relative_strength:'相對強度/價格動能', volume_breakout:'量能倍數',
    new_high_breakout:'創新高', volume_price_coordination:'量價配合度',
    chip_concentration:'籌碼集中', group_breadth:'族群齊漲度',
    sector_capital_flow:'產業成交額增加',
  };
  const MOMENTUM_FACTOR_ORDER=['relative_strength','volume_breakout','new_high_breakout','volume_price_coordination','chip_concentration','group_breadth','sector_capital_flow'];
  // 未來性濾網(a)類因子集合（見research/generate_scores_future.py檔頭說明）。
  const FUTURE_FACTOR_LABELS={
    institutional_buying_streak:'法人連續買超天數', institutional_ownership_pct:'買超佔股本比',
    institutional_buying_concentration:'買超集中度', gross_margin_level_stability:'毛利率水準與穩定度',
    capacity_utilization_proxy:'產能利用率代理',
  };
  const FUTURE_FACTOR_ORDER=['institutional_buying_streak','institutional_ownership_pct','institutional_buying_concentration','gross_margin_level_stability','capacity_utilization_proxy'];
  // 2026-08-27新增：三榜共用的設定表，取代原本value/momentum兩路分開寫的
  // ternary——board id → {資料檔名, cache getter/setter, 產生腳本說明,
  // 因子標籤/順序}，往後再加第四個榜單只要在這裡加一筆設定。
  const BOARD_CONFIG={
    value:{file:'scores.json',listFile:'scores_list.json',byCodeKey:'scores',cacheGet:()=>PICKS_CACHE,cacheSet:v=>PICKS_CACHE=v,label:'generate_scores_v2.py',factorLabels:FACTOR_LABELS,factorOrder:FACTOR_ORDER,title:'價值成長榜'},
    momentum:{file:'scores_momentum.json',listFile:'scores_momentum_list.json',byCodeKey:'scores_momentum',cacheGet:()=>PICKS_MOMENTUM_CACHE,cacheSet:v=>PICKS_MOMENTUM_CACHE=v,label:'generate_scores_momentum.py',factorLabels:MOMENTUM_FACTOR_LABELS,factorOrder:MOMENTUM_FACTOR_ORDER,title:'題材動能榜'},
    future:{file:'scores_future.json',listFile:'scores_future_list.json',byCodeKey:'scores_future',cacheGet:()=>PICKS_FUTURE_CACHE,cacheSet:v=>PICKS_FUTURE_CACHE=v,label:'generate_scores_future.py',factorLabels:FUTURE_FACTOR_LABELS,factorOrder:FUTURE_FACTOR_ORDER,title:'未來性濾網'},
  };
  // 2026-08-24 改版：分數文字用金/白/暗三階（不再用紅黃綠號誌色，跟金色主題
  // 衝突），讀條一律金色漸層（資料完整度低才用調暗的扁平金色，見 barFill()）。
  function scoreColor(v){
    if(v>=8)return 'var(--gold)';
    if(v>=5)return 'var(--ink)';
    return 'var(--ink-3)';
  }
  function fmtLiquidity(v){
    if(v==null)return '—';
    if(Math.abs(v)>=1e8)return (v/1e8).toFixed(2)+'億';
    if(Math.abs(v)>=1e4)return (v/1e4).toFixed(0)+'萬';
    return v.toFixed(0);
  }
  function onPicksToggleChange(){
    const mkt=MKT_STATE.picks;
    const scr=document.getElementById('scr-picks');if(scr)scr.classList.toggle('mkt-nontw',mkt!=='TW');  // 先.八十一-12
    document.getElementById('picks-list-card').style.display=mkt==='TW'?'':'none';
    document.getElementById('picks-chips').classList.toggle('off-mkt',mkt!=='TW');  // 先.八十-4：切 class，不設 style.display
    document.getElementById('picks-us-panel').style.display=mkt==='US'?'':'none';
    document.getElementById('picks-fut-panel').style.display=mkt==='FUT'?'':'none';
    if(mkt==='FUT')loadFutTrialsCount().catch(e=>{console.warn('[loadFutTrialsCount]',e);recordGlobalError('loadFutTrialsCount',e)});
    if(mkt==='US')loadUsScoresV0().catch(e=>{console.warn('[loadUsScoresV0]',e);recordGlobalError('loadUsScoresV0',e)});
    document.getElementById('us-screen-panel').style.display=mkt==='US'?'':'none';
    if(mkt==='US')loadUsScreener().catch(e=>{console.warn('[loadUsScreener]',e);recordGlobalError('loadUsScreener',e)});
  }
  // 先.一〇三-13（2026-10-16）：期貨軌已測假說數原本寫死「22」，改讀 data/strategies.json 的 fut_track.trials_summary
  //（generate_strategies_json.py 從 TRIALS_LEDGER.md 動態算出）。讀不到就維持「—」，不猜數字。
  async function loadFutTrialsCount(){
    const el=document.getElementById('fut-trials-n');if(!el||el.dataset.loaded)return;
    const r=await fetch('data/strategies.json?t='+Math.floor(Date.now()/60000));
    if(!r.ok)throw new Error('strategies.json HTTP '+r.status);
    const d=await r.json();
    const list=Array.isArray(d)?d:(d.strategies||[]);
    const f=list.find(x=>x&&x.id==='fut_track');
    const n=f&&f.trials_summary&&f.trials_summary['已測試假說數'];
    if(typeof n==='number'){el.textContent=n;el.dataset.loaded='1';
      const u=f.last_updated?String(f.last_updated).slice(5,10).replace('-','/'):'';if(u)el.title='截至 '+u}
  }
  // 2026-10-11 常備.開發-17：美股評分 v0（價值/成長/品質三分項）。失敗只影響本面板。
  let US_SCORES_V0=null;
  const US_PILLAR_KEYS=['value','growth','quality'];
  function _usEsc(t){return String(t==null?'':t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function _usPct(v){return v==null?'—':(v*100).toFixed(1)+'%'}
  function usPillarDetail(k,p){
    const r=p.raw||{};
    if(k==='value')return `本益比 ${r.pe==null?'—':r.pe} · PEG ${r.peg==null?'—':r.peg} · PBR 缺`;
    if(k==='growth')return `EPS年增 ${_usPct(r.eps_yoy)} · 營收年增 ${_usPct(r.revenue_yoy)} · 毛利率 ${r.gross_margin_yoy_pp==null?'—':(r.gross_margin_yoy_pp>0?'+':'')+r.gross_margin_yoy_pp+'pp'} · 營益率 ${r.op_margin_yoy_pp==null?'—':(r.op_margin_yoy_pp>0?'+':'')+r.op_margin_yoy_pp+'pp'}`;
    return `毛利率 ${_usPct(r.gross_margin)} · 營益率 ${_usPct(r.operating_margin)} · FCF利潤率 ${_usPct(r.fcf_margin)} · 負債比 ${_usPct(r.debt_ratio)}`;
  }
  function usScoreRowHtml(s,labels){
    const pills=US_PILLAR_KEYS.map(k=>{const p=s.pillars&&s.pillars[k];return `<span style="margin-right:8px">${_usEsc(labels[k]||k)} <b class="num">${p?p.score.toFixed(1):'—'}</b></span>`}).join('');
    const detail=US_PILLAR_KEYS.map(k=>{const p=s.pillars&&s.pillars[k];return `<div class="sub">${_usEsc(labels[k]||k)}：${p?_usEsc(usPillarDetail(k,p)):'缺資料'}</div>`}).join('');
    const warn=(s.warnings&&s.warnings.length)?`<div class="sub" style="color:var(--note-gold)">${_usEsc(s.warnings.join('；'))}</div>`:'';
    return `<details class="us-score-row" style="padding:7px 0;border-bottom:1px solid var(--hairline)"><summary style="display:flex;justify-content:space-between;gap:8px;cursor:pointer;list-style:none"><span><b>${s.rank==null?'':'#'+s.rank+' '}${_usEsc(s.code)}</b> <span class="sub">${_usEsc(s.name||s.exchange||'')}</span><div class="sub">${pills}</div></span><span style="text-align:right"><b class="num" style="font-size:16px">${s.total_score==null?'—':s.total_score.toFixed(1)}</b><div class="sub">完整度 ${Math.round((s.coverage||0)*100)}%</div></span></summary><div style="padding:4px 0 2px">${detail}<div class="sub">財報期末 ${_usEsc(s.period_end||'—')}（申報 ${_usEsc(s.filed||'—')}）</div>${warn}<div class="sub"><span class="press" style="color:var(--accent,#d8b070)" onclick="openStock('${_usEsc(s.code)}')">開個股頁 ›</span></div></div></details>`;
  }
  async function loadUsScoresV0(){
    const metaEl=document.getElementById('picks-us-meta'),listEl=document.getElementById('picks-us-list');
    if(!metaEl||!listEl)return;
    try{
      if(!US_SCORES_V0){const r=await fetch('data/us_scores_v0.json?t='+Date.now());if(!r.ok)throw new Error('HTTP '+r.status);US_SCORES_V0=await r.json()}
      const m=US_SCORES_V0.meta||{},rows=US_SCORES_V0.stocks||[];
      const labels={};US_PILLAR_KEYS.forEach(k=>labels[k]=(m.pillars&&m.pillars[k]&&m.pillars[k].label)||k);
      const ranked=rows.filter(s=>s.rank!=null).slice(0,30);
      const pc=m.pillar_coverage||{};
      metaEl.innerHTML=`評分時間 ${_usEsc((m.generated_at||'').slice(0,16).replace('T',' '))} ｜ 財報 ${_usEsc((m.financials_generated_at||'').slice(0,10))} ｜ 股價 ${_usEsc((m.price_source&&m.price_source.as_of)||'—')}<br>樣本 ${rows.length} 檔、排名 ${m.ranked_count||0} 檔（完整度≥50%）；分項涵蓋：${US_PILLAR_KEYS.map(k=>_usEsc(labels[k])+' '+(pc[k]||0)).join('、')}。三分項等權；價值＝本益比/PEG（數值越低代表本益比越低，PBR 缺）、成長＝EPS/營收年增＋毛利率/營益率年變化（年度）、品質＝v0 自訂（毛利率/營益率/FCF利潤率/低負債）。宇宙為 SEC 當下名冊前段＋自選股，非全市場。`;
      listEl.innerHTML=ranked.length?ranked.map(s=>usScoreRowHtml(s,labels)).join(''):'<div class="note">目前沒有完整度≥50%的美股可排名。</div>';
    }catch(e){
      console.warn('[loadUsScoresV0]',e);recordGlobalError('loadUsScoresV0',e);
      metaEl.textContent='美股評分 v0 載入失敗（'+(e&&e.message||e)+'）';listEl.innerHTML='';
    }
  }
  // 2026-10-13 先.八十一-33：美股描述性篩選（成交額／漲跌幅／市值門檻），前端依門檻過濾 data/us_screener.json。
  // 不排名、不是選股訊號；依日均成交額由大到小列前 50 檔。失敗只影響本面板。
  let US_SCREENER=null;
  function _usScrNum(id){const v=(document.getElementById(id)||{}).value;return v===''||v==null||isNaN(+v)?null:+v}
  function usScreenFilter(rows,f){
    return rows.filter(r=>{
      if(r.close==null)return false;
      if(f.dv!=null&&!(r.avg_dollar_volume_20d!=null&&r.avg_dollar_volume_20d>=f.dv*1e6))return false;
      if(f.chmin!=null&&!(r.change_pct!=null&&r.change_pct>=f.chmin))return false;
      if(f.chmax!=null&&!(r.change_pct!=null&&r.change_pct<=f.chmax))return false;
      if(f.cap!=null&&!(r.market_cap_est!=null&&r.market_cap_est>=f.cap*1e9))return false;
      return true;
    }).sort((a,b)=>(b.avg_dollar_volume_20d||0)-(a.avg_dollar_volume_20d||0));
  }
  function _usBig(v,unit){if(v==null)return '—';return unit==='B'?(v/1e9).toFixed(v>=1e11?0:1)+'B':(v/1e6).toFixed(0)+'M'}
  function renderUsScreener(){
    const metaEl=document.getElementById('us-scr-meta'),listEl=document.getElementById('us-scr-list');
    if(!metaEl||!listEl||!US_SCREENER)return;
    const m=US_SCREENER.meta||{},rows=US_SCREENER.stocks||[];
    const f={dv:_usScrNum('us-scr-dv'),chmin:_usScrNum('us-scr-chmin'),chmax:_usScrNum('us-scr-chmax'),cap:_usScrNum('us-scr-cap')};
    const hit=usScreenFilter(rows,f);
    metaEl.innerHTML=`資料日 ${_usEsc(m.as_of||'—')}（美東收盤）｜ 符合 <b class="num" id="us-scr-count">${hit.length}</b> / ${m.priced_count||0} 檔，依日均成交額排序、列前 50 檔<br>只把資料依門檻篩出，沒有排名、沒有回測、不是選股訊號。樣本：${_usEsc(m.universe_note||'')} 市值有值 ${m.market_cap_count||0} 檔。<details style="margin-top:3px"><summary class="sub" style="cursor:pointer">資料品質說明</summary>${(m.data_quality||[]).map(t=>'<div class="sub">・'+_usEsc(t)+'</div>').join('')}</details>`;
    listEl.innerHTML=hit.length?hit.slice(0,50).map(r=>{
      const ch=r.change_pct,col=ch==null?'':(ch>0?'color:var(--up,#e0524a)':ch<0?'color:var(--down,#3aa676)':'');
      const fl=(r.flags&&r.flags.length)?`<div class="sub" style="color:var(--note-gold)">${_usEsc(r.flags.join('；'))}</div>`:'';
      return `<div class="us-scr-row press" style="display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid var(--hairline)" onclick="openStock('${_usEsc(r.code)}')"><span><b>${_usEsc(r.code)}</b> <span class="sub">${_usEsc(r.name||'')}</span><div class="sub">日均成交額 ${_usBig(r.avg_dollar_volume_20d)} ・ 市值 ${_usBig(r.market_cap_est,'B')}</div>${fl}</span><span style="text-align:right"><b class="num">${r.close==null?'—':r.close}</b><div class="sub num" style="${col}">${ch==null?'—':(ch>0?'+':'')+ch.toFixed(2)+'%'}</div></span></div>`;
    }).join(''):'<div class="note">沒有符合門檻的股票，放寬條件再試。</div>';
  }
  async function loadUsScreener(){
    const metaEl=document.getElementById('us-scr-meta'),listEl=document.getElementById('us-scr-list');
    if(!metaEl||!listEl)return;
    try{
      if(!US_SCREENER){const r=await fetch('data/us_screener.json?t='+Date.now());if(!r.ok)throw new Error('HTTP '+r.status);US_SCREENER=await r.json()}
      ['us-scr-dv','us-scr-chmin','us-scr-chmax','us-scr-cap'].forEach(id=>{const el=document.getElementById(id);if(el&&!el._bound){el._bound=1;el.addEventListener('input',()=>{try{renderUsScreener()}catch(e){console.warn('[renderUsScreener]',e);recordGlobalError('renderUsScreener',e)}})}});
      renderUsScreener();
    }catch(e){
      console.warn('[loadUsScreener]',e);recordGlobalError('loadUsScreener',e);
      metaEl.textContent='美股篩選資料載入失敗（'+(e&&e.message||e)+'）';listEl.innerHTML='';
    }
  }
  // 2026-09-05（新一.6）每個因子「為什麼這檔沒有」的真實原因。八因子現在全部有資料源
  // （見 research/live_factors.py），缺的都是「這一檔在那個官方資料檔裡沒有資料」。
  const FACTOR_MISSING_REASON={
    earnings_growth:'這檔沒有官方季度財報（目前只涵蓋上市一般業；上櫃與金融/證券/保險等特殊業別未涵蓋（需要「最新一季 vs 去年同季」才能算年增）。',
    revenue_momentum:'這檔沒有月營收資料（公開的每月營收公告還沒涵蓋到這檔）。',
    growth_quality:'這檔的月營收年增資料不足 6 個月（月營收歷史是「一次性種子快照＋每日累積」，新納入的股票要等累積）。',
    chips:'這檔沒有三大法人／融資融券資料。',
    technical:'這檔的價量歷史不足（至少要 6 個交易日）。',
    valuation_adj:'這檔沒有本益比／股價淨值比資料。',
    analyst:'這檔沒有三大法人買賣紀錄可推算機構行為（本因子是法人實際買賣行為，不是分析師目標價——台股沒有免費的目標價／評等資料源）。',
    catalyst:'這檔近期沒有事件紀錄。',
  };
  // ══════ 2026-09-15（P0產品.二）選股理由：因子貢獻＋百分位＋同產業比較 ══════
  // 三個進入點（個股頁總覽分頁選股理由卡／選股榜每列展開／個股研究報告頁既有因子清單）
  // 共用同一套計算與渲染，避免三份各自維護、彼此不一致。「同產業比較」純粹用目前
  // 已經載入瀏覽器的同一份 scores.json 在前端算百分位排名，不加任何新資料源/新後端
  // 端點（零外部資料）。
  // 樣本太小的產業（<5檔可比）不給百分位——2、3檔互比的「百分位」看起來精確但其實
  // 沒有統計意義，寧可不顯示也不要給一個假精確的數字。
  function industryPercentileFor(allRows,industry,factorKey,score){
    if(!industry||!allRows||!allRows.length)return null;
    const vals=allRows.filter(r=>r.industry===industry&&r.factors&&r.factors[factorKey]&&typeof r.factors[factorKey].score==='number').map(r=>r.factors[factorKey].score);
    if(vals.length<5)return null;
    const n=vals.length;
    const countLE=vals.filter(v=>v<=score).length;
    return {pct:countLE/n,n};
  }
  // percentile 0.99 → 全市場前 1%，跟既有 reason 文字（research/generate_scores_live.py
  // 產生的「居全市場前 X%」）用同一套換算，避免同一頁出現兩種不同口徑的百分位說法。
  // 先.八十一-13：前段超過 50% 改說「最差 N%」（p=0.01 原本顯示「前99%」，看起來像很好，其實是倒數 1%）
  function pctLabel(p){const front=Math.max(1,Math.round((1-p)*100));return front>50?'最差'+Math.max(1,Math.round(p*100))+'%':'前'+front+'%'}
  function factorContribRowHtml(key,row,labels,weights,allRows){
    const weightPct=Math.round((weights[key]||0)*100);
    const refOnly=weights.low_vol===1&&!(weights[key]>0);  // 方案B：非計分成分，明細仍顯示
    const wTxt=refOnly?'僅供參考 · 不計分':'權重 '+weightPct+'%';
    const f=row.factors&&row.factors[key];
    if(!f){
      // 這輪缺資料的類別（價值成長榜的analyst/catalyst，見score_v2.py說明；
      // 題材動能榜/未來性濾網的任何因子也可能因為個股資料不足而缺）：誠實
      // 列出來，不要悄悄省略——讓使用者看得出「總分不是滿權重算出來的」。
      // 2026-09-05（新一.6）：原本除了 analyst 之外，價值成長榜每個缺漏因子都套同一句
      // 「需要新聞/供應鏈連動分析，下一輪實作」——但財報成長/估值/技術型態根本不需要新聞，
      // 它們缺是因為這檔在對應的官方資料檔裡沒有資料。改成逐因子講真正的資料依賴。
      const reasonTxt=FACTOR_MISSING_REASON[key]
        ||'這檔股票目前這項因子資料不足（例如上市時間太短、價量/法人歷史不夠），不是永久缺資料源。';
      return `<div class="factor-row">
        <div class="fr-top"><span class="fr-name" style="color:var(--ink-3)">${labels[key]} <span style="font-size:9.5px;color:var(--ink-4)">${wTxt}</span></span>
          <span style="font-size:9px;color:var(--note-gold);background:rgba(216,176,112,.08);padding:2px 6px;border-radius:5px">尚無資料 · 不計入</span></div>
        <div class="fr-reason" style="color:var(--ink-4)">${reasonTxt}</div>
      </div>`;
    }
    // 貢獻方向：以5分（滿分10）為中性基準，>5拉高總分、<5拉低總分，用置中的雙向長條
    // 呈現（金色往右=拉高，灰色往左=拉低），跟單純0~10絕對分數的長條圖分開表達「貢獻」。
    const dirUp=f.score>=5;
    const mag=Math.min(50,Math.abs(f.score-5)/5*50);
    const dirTag=refOnly?'<span style="color:var(--ink-4)">· 不計分</span>':f.score>5.2?'<span style="color:var(--gold);font-weight:600">▲ 拉高總分</span>'
      :f.score<4.8?'<span style="color:var(--ink-3)">▼ 拉低總分</span>'
      :'<span style="color:var(--ink-4)">· 中性</span>';
    const pctBadge=typeof f.percentile==='number'
      ?`<span style="font-size:9px;color:var(--ink-2);background:rgba(var(--fg-rgb),.06);padding:2px 6px;border-radius:5px">全市場${pctLabel(f.percentile)}</span>`:'';
    // 先.八十一-9：個股頁讀 by_code 小檔時沒有同產業整批列，用 build_by_code.py 先算好的 row._industry_pct（同一套算法）
    const ip=row._industry_pct?(row._industry_pct[key]||null):industryPercentileFor(allRows,row.industry,key,f.score);
    const indBadge=ip?`<span style="font-size:9px;color:var(--ink-2);background:rgba(var(--fg-rgb),.06);padding:2px 6px;border-radius:5px">同產業(${ip.n}檔)${pctLabel(ip.pct)}</span>`:'';
    return `<div class="factor-row">
      <div class="fr-top"><span class="fr-name">${labels[key]} <span style="font-size:9.5px;color:var(--ink-4)">${wTxt}</span></span><span class="fr-score" style="color:${scoreColor(f.score)}">${f.score.toFixed(1)}</span></div>
      <div style="position:relative;height:8px;border-radius:999px;background:var(--surface-3);margin-top:6px;overflow:hidden">
        <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(var(--fg-rgb),.15)"></div>
        <div class="bar-fill" style="position:absolute;top:0;bottom:0;${dirUp?`left:50%;width:${mag}%`:`right:50%;width:${mag}%`};background:${dirUp?'var(--gold-grad)':'rgba(138,133,123,.55)'};border-radius:999px"></div>
      </div>
      <div style="margin-top:5px;display:flex;flex-wrap:wrap;align-items:center;gap:4px">${dirTag}${pctBadge}${indBadge}</div>
      <div class="fr-reason">${uiPlain(f.reason||'').replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>')}</div>
    </div>`;
  }
  // 先.一〇三-13：因子說明裡的 **粗體**（generate_scores_live.py 法人行為那句）原本原樣印出星號，改轉成 <b>
  // 規則式一句話摘要：取百分位最高的1~2個因子＋（若明顯偏弱）百分位最低的因子，
  // 例如「毛利率 78 百分位、動能 91 百分位，但估值偏貴」這種格式（總司令原話範例）。
  // 跟 scores.json 既有的 row.summary（伺服器端只挑單一最突出因子）分開，這裡是
  // 前端另外算的、專門給「選股理由」卡用的版本，不動 research/ 產生腳本。
  function buildReasonSummary(row,boardCfg){
    const order=boardCfg.factorOrder,labels=boardCfg.factorLabels;
    const _c=boardCfg.cacheGet();
    if(_c&&_c.weights&&_c.weights.low_vol===1&&row.summary)return row.summary;  // 方案B：只有低波動計分，直接用伺服器端摘要
    const avail=order.map(k=>({key:k,f:row.factors&&row.factors[k]})).filter(x=>x.f&&typeof x.f.percentile==='number');
    if(!avail.length)return row.summary||'這檔目前所有因子皆無資料，無法拆解分數。';
    const sorted=[...avail].sort((a,b)=>b.f.percentile-a.f.percentile);
    const pct=p=>Math.round(p*100);
    const top=sorted.slice(0,Math.min(2,sorted.length));
    const topTxt=top.map(x=>`${labels[x.key]} ${pct(x.f.percentile)}百分位`).join('、');
    const worst=sorted[sorted.length-1];
    const worstIsTop=top.some(x=>x.key===worst.key);
    if(!worstIsTop&&pct(worst.f.percentile)<50)return `${topTxt}，但${labels[worst.key]}偏弱（${pct(worst.f.percentile)}百分位）。`;
    return `${topTxt}，各因子表現相對均衡。`;
  }

  // 2026-09-15（P0產品.三）把「篩近N日事件」與「事件列表HTML」抽成共用函式——
  // 個股研究報告頁（renderReportEvents）跟個股頁新分頁（renderStockEventsTab）
  // 都要顯示同一份 data/events.json，抽出來才不會兩份各自維護、慢慢長歪。
  function recentEventsFor(d,code,days){
    const cutoff=(()=>{const t=new Date(Date.now()-days*864e5);const z=_zonedParts(t,'Asia/Taipei');
      return `${z.y}-${String(z.m).padStart(2,'0')}-${String(z.d).padStart(2,'0')}`})();
    return (d.events||[]).filter(e=>e.code===code&&String(e.date)>=cutoff)
      .sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  }
  // 先.一一〇-9（2026-10-18 總司令裁示）：每個區塊顯示重要度（importance 0～10，權重表 v0 見 .github/scripts/news_importance.py）
  // 最高的 5 則，其餘收進「看全部 N 則」；不用固定門檻收合。同分新到舊。舊資料沒有 importance（還沒重產的快取、
  // 搜尋精簡版還原的整份事件）就只照時間排——是降級不是錯誤。
  const IMP_TOP_N=5;
  function byImportance(list,timeKey){
    return [...list].sort((a,b)=>((b.importance??-1)-(a.importance??-1))||(String(timeKey(b)).localeCompare(String(timeKey(a)))));
  }
  function topWithRestHtml(list,rowFn,n=IMP_TOP_N){
    const head=list.slice(0,n),rest=list.slice(n);
    return head.map(rowFn).join('')
      +(rest.length?`<details class="imp-rest" style="margin-top:4px"><summary class="note" style="cursor:pointer;margin:4px 0">看全部 ${list.length} 則</summary><div style="display:flex;flex-direction:column;gap:9px">${rest.map(rowFn).join('')}</div></details>`:'');
  }
  function eventsTopHtml(mine){return topWithRestHtml(byImportance(mine,e=>e.date),e=>eventsRowsHtml([e],1))}
  function eventsRowsHtml(mine,limit){
    return mine.slice(0,limit).map(e=>{
      const c=EVENT_TYPE_COLOR[e.type]||'var(--ink-3)';
      const t=(e.title||'').replace(/</g,'&lt;');
      return `<div style="display:flex;gap:9px;align-items:flex-start">
        <span class="num" style="font-size:10px;color:var(--ink-4);min-width:38px;padding-top:2px">${String(e.date).slice(5)}</span>
        <span style="font-size:9.5px;font-weight:700;color:${c};border:1px solid ${c};border-radius:5px;padding:1px 5px;flex-shrink:0;margin-top:1px">${e.type}</span>
        <span style="flex:1;font-size:12px;color:var(--ink-2);line-height:1.5">${e.url?`<a href="${e.url}" target="_blank" rel="noopener" style="color:inherit">${t}</a>`:t}${mopsIrLinkHtml(e,false)}</span>
      </div>`;
    }).join('');
  }
  // ── 2026-09-08（金流一.3）產業金流 ────────────────────────────────────────
  // data/sector_flow.json 由 scripts/build_sector_flow.py 產生（零額外請求）。
  // 可用視窗寫在 meta.windows_usable，缺的寫在 meta.windows_missing_days——
  // 前端**只顯示 meta 說可用的視窗**，不自己補零也不用短視窗冒充長視窗。
  let SECTOR_FLOW=null,SECTOR_FLOW_AT=0,FLOW_WIN=5,FLOW_OPEN=null;
  async function ensureSectorFlow(){
    if(SECTOR_FLOW&&Date.now()-SECTOR_FLOW_AT<10*60*1000)return SECTOR_FLOW;
    try{
      const r=await fetch('data/sector_flow.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      SECTOR_FLOW=await r.json();SECTOR_FLOW_AT=Date.now();
    }catch(e){
      console.warn('[ensureSectorFlow]',e);recordGlobalError('ensureSectorFlow',e);
      if(!SECTOR_FLOW)SECTOR_FLOW=null;
    }
    return SECTOR_FLOW;
  }
