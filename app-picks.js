// 常備.開發-20 丙案（2026-10-11 先.六十五）：選股頁（含研究報告子頁）專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('picks') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // ── 2026-09-06（P0 稽核.一）全 App 唯一的「現價」真值來源 ──────────────────
  // 背景：總司令實測「光聖 6442 現價 1755、建議進場價 32」。根因是 renderReport()
  // 在 await 之後沒有世代檢查，上一檔（6808，收盤 32.0）晚回來的 FinMind 結果
  // 蓋進了 6442 的分批進場計畫（6808 的 last=32.0／low20=31.25／low60=31.25 與
  // 畫面上三個數字逐一吻合，見 PROGRESS.md 的證據鏈）。
  // 世代守衛（防線一）修掉那條競態；這支函式是防線二：任何頁面要顯示「由某個
  // 資料源算出來的價格」時，先跟真值比一次，差超過 30% 就不准顯示數字，改顯示
  // 誠實的錯誤訊息並記進診斷 log——不管未來是哪一支抓取器出錯，都不會再讓一個
  // 明顯荒謬的價格安靜地出現在畫面上。
  // 順序依總司令裁示：即時（Shioaji/IBKR）→ quotes_tw/us → quotes_all_tw 收盤
  // → sparklines 最後一點。全部查不到就回 null（回 null 代表「無法查核」，
  // 呼叫端要放行，不能因為查不到真值就把正常資料擋掉）。
  // 2026-09-06（實測.一）改為委派 resolveQuote()。原本這裡自己抄了一份一模一樣的
  // 回退順序，兩份規則遲早會走鐘——真值查核與畫面顯示必須是同一條鏈，否則稽核會
  // 說「一致」而使用者看到的是另一個數字。
  function canonicalPrice(code){
    try{
      const q=resolveQuote(code,isUS(code));
      if(q&&q.price!=null&&isFinite(q.price))
        return {price:+q.price,src:QUOTE_TIER_LABEL[q.tier]||q.tier,tier:q.tier};
    }catch(e){console.warn('[canonicalPrice]',e);recordGlobalError('canonicalPrice',e)}
    return null;
  }
  const PRICE_SANITY_TOLERANCE=0.30;  // 總司令裁示：±30%
  // 回傳 null=通過（或無法查核），回傳字串=不通過，字串就是要顯示給使用者看的原因。
  function priceSanityFailure(code,price,label){
    if(price==null||!isFinite(price))return null;
    const c=canonicalPrice(code);
    if(!c||!c.price)return null;                       // 查不到真值→無法查核，放行
    const diff=Math.abs(price/c.price-1);
    if(diff<=PRICE_SANITY_TOLERANCE)return null;
    const msg=`${label} 算出的 ${nf(price.toFixed(2))} 與現價 ${nf(c.price.toFixed(2))}（${c.src}）差 ${(diff*100).toFixed(0)}%，超過 ${(PRICE_SANITY_TOLERANCE*100)}% 容許值，判定為資料不一致，暫不顯示。`;
    recordGlobalError('priceSanity:'+code,new Error(msg));
    return msg;
  }
  function isDisposalNow(code,todayIso){const f=disposalFlagOf(code,todayIso);return !!f&&f.kind==='disposal'}
  // 2026-09-06（P0 稽核.一）缺值安全的數字格式化。
  // 起因：光聖 6442 的 valuation_adj.raw.peg 是 null，報告頁直接寫 peg.toFixed(2)，
  // 整個 renderReport() 在中途拋 TypeError 死掉——名稱已經換成「光聖 6442」但
  // 下面的分批進場計畫還停在上一檔（昇貿 6808，收盤 32）的數字，看起來就像
  // 「光聖現價 1755、建議進場價 32」。同一段還有 (null*100).toFixed(1) 會安靜地
  // 印出「0.0%」，那是把「沒有資料」顯示成「成長 0%」，屬於假資料，一併根治。
  // 規則：任何可能為 null 的數值一律走這兩支，缺值就是「—」，不是 0、不是崩潰。
  // 先.八十-10：加千分位（法人張數等大數字）
  const fmtN=(v,d=2,suffix='')=>(v==null||typeof v!=='number'||!isFinite(v))?'—':v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})+suffix;
  const fmtPct=(v,d=1)=>(v==null||typeof v!=='number'||!isFinite(v))?'—':(v*100).toFixed(d)+'%';
  // 2026-09-08（健檢.三）撞到評分引擎上限的年增率不得當真值顯示。
  // REVENUE_YOY_CAP=2.0（+200%）是引擎的裁切值，不是公司真的成長兩倍——
  // 多半是低基期或併購造成的。顯示成乾淨的「200.0%」等於把裁切值當事實報給使用者。
  // 改成「≥200%」並標灰加註，讓人一眼看出這是上限不是實測值。
  function fmtPctCapped(v,cap,d=1){
    if(v==null||typeof v!=='number'||!isFinite(v))return '—';
    if(cap!=null&&v>=cap)
      return `<span style="color:var(--ink-3)">≥${(cap*100).toFixed(0)}%<span style="font-size:9.5px">（特殊基期，資料存疑）</span></span>`;
    return (v*100).toFixed(d)+'%';
  }
  // 估值區間卡要同產業所有股票的近四季 EPS：讀精簡檔 data/stock_detail_eps.json
  // （每檔只留 financials.quarters 最後四筆 {year,quarter,eps}，epsTtmFromDetail 本來就只用這四筆）。
  let STOCK_DETAIL_EPS_CACHE=null;
  async function loadStockDetailEps(){
    if(!STOCK_DETAIL_EPS_CACHE){
      try{const r=await fetch('data/stock_detail_eps.json?t='+Date.now());if(r.ok)STOCK_DETAIL_EPS_CACHE=await r.json()}catch(e){console.warn('[loadStockDetailEps]',e);recordGlobalError('loadStockDetailEps',e)}
      if(!STOCK_DETAIL_EPS_CACHE)STOCK_DETAIL_EPS_CACHE={stocks:{}};
    }
    return STOCK_DETAIL_EPS_CACHE.stocks||{};
  }

  // 這批 8 大類是舊版「主流題材」資金流向 chips 用的 FinMind 產業指數代碼
  // （Trading_money 逐產業合計成交值），跟上面「類股表現」熱力圖（現在改讀
  // market_tw.json 的 TWSE 官方28類）是兩條獨立的路——這裡目前還是走 FinMind，
  // 額度用盡時 fm() 已經會誠實回傳空陣列/連線失敗訊息，不是顯示假資料，暫不在
  // 這輪 P0-1 範圍內一併重寫（見 P0-1 驗收範圍：大盤指數/美股指數/類股/三大法人/
  // 自選股報價，不含這個「主流題材」次要功能）。
  const HEAT_CATS=[
    {id:'Semiconductor',label:'半導體'},{id:'Electronic',label:'電子'},
    {id:'CommunicationsInternet',label:'通信網路'},{id:'Optoelectronic',label:'光電'},
    {id:'FinancialInsurance',label:'金融保險'},{id:'ElectricMachinery',label:'電機'},
    {id:'ShippingTransportation',label:'航運'},{id:'Tourism',label:'觀光'},
  ];
  const HEAT_TO_SCORE_INDUSTRY={
    Semiconductor:'半導體業', Electronic:'電子工業', CommunicationsInternet:'通信網路業',
    Optoelectronic:'光電業', FinancialInsurance:'金融保險', ElectricMachinery:'電機機械',
    ShippingTransportation:'航運業', Tourism:'觀光事業',
  };
  async function fetchIndustryFlow(cat){
    const px=await fm('TaiwanStockPrice',cat.id,_d(30));
    if(px.length<6)return{...cat,inflow:null};
    const moneys=px.map(x=>x.Trading_money||0);
    const last=px[px.length-1];
    const avg5=moneys.slice(-5).reduce((a,b)=>a+b,0)/5;
    const avg20=moneys.slice(-20).reduce((a,b)=>a+b,0)/Math.min(20,moneys.length);
    const inflow=avg20>0?(avg5/avg20-1)*100:null;
    // 連續流入天數（從最新一天往回數，當日成交值 > 全樣本20日均值 就算一天）+ 這段期間累計漲幅，
    // 用來判斷「已經漲一段、資金卡位很久」的擁擠度，不是嚴謹的統計檢定，只是即時提示用的粗略估法。
    let streak=0;
    for(let i=px.length-1;i>=0&&moneys[i]>avg20;i--)streak++;
    const streakStartPx=px[Math.max(0,px.length-1-streak)].close;
    const cumGain=streakStartPx?((last.close-streakStartPx)/streakStartPx*100):0;
    const crowded=streak>=3&&cumGain>=8;
    const pct=last.spread!=null?last.spread/(last.close-last.spread)*100:0;
    return{...cat,inflow,pct,streak,cumGain,crowded,date:last.date};
  }
  let MAINSTREAM_CACHE=null;
  function renderMainstreamChips(){
    const el=document.getElementById('mainstream-chips');if(!el||!MAINSTREAM_CACHE)return;
    if(!MAINSTREAM_CACHE.length){
      // 2026-08-28修正（UX走查發現）：原本用「或」把「真的沒有產業符合條件」跟
      // 「連線失敗」兩種語意完全不同的狀態糊成一句話，使用者看了不知道該不該按
      // 重新整理。FM_LAST_FAILED本來就已經能明確分辨是哪一種，這裡改成兩句
      // 各自獨立、不含糊的訊息。
      el.innerHTML='<div class="note">'+(FM_LAST_FAILED&&/FinMind/.test(MAINSTREAM_SRC)?'repo 檔與 FinMind 都讀不到：'+fmEmptyMsg(''):'目前沒有產業呈現5日/20日資金淨流入')+'</div>';
      return;
    }
    const srcEl=document.getElementById('mainstream-src');if(srcEl)srcEl.textContent=MAINSTREAM_SRC;
    el.innerHTML=MAINSTREAM_CACHE.map(r=>{
      const scoreInd=r.scoreInd||HEAT_TO_SCORE_INDUSTRY[r.id];
      const active=PICKS_INDUSTRY===scoreInd;
      return `<span class="press" style="flex-shrink:0;font-size:12px;font-weight:${active?600:400};color:${active?'#1a1005':'var(--ink-2)'};background:${active?'var(--gold-grad)':'rgba(255,255,255,.05)'};border:1px solid ${active?'transparent':'rgba(255,255,255,.08)'};padding:6px 13px;border-radius:999px;cursor:pointer;white-space:nowrap" onclick="filterPicksByIndustry('${scoreInd}')">${r.label} <span style="color:${active?'#1a1005':'var(--up)'}">+${r.inflow.toFixed(1)}%</span>${r.crowded?' ⚠ 已擁擠':''}</span>`;
    }).join('');
  }
  // 先.八十一-10：主流題材主來源改為 repo 的 data/industry_flow.json（scripts/build_industry_flow.py：price_history
  // 成交值依產業加總，同一條「近5日÷近20日均成交值」公式，涵蓋全部產業、名稱與選股榜一致）；讀不到才退回
  // 上面 8 個 FinMind 產業指數。MAINSTREAM_SRC 記來源與資料日，畫在 chips 下方。
  let MAINSTREAM_SRC='';
  async function loadMainstreamIndustries(){
    const el=document.getElementById('mainstream-chips');if(!el)return;
    el.innerHTML='<div class="skel-block" style="height:26px;width:70px;border-radius:14px;flex:0 0 auto"></div><div class="skel-block" style="height:26px;width:70px;border-radius:14px;flex:0 0 auto"></div><div class="skel-block" style="height:26px;width:70px;border-radius:14px;flex:0 0 auto"></div>';  // 2026-09-15 P0產品.四：骨架屏
    let repoErr='';
    try{
      const r=await fetch('data/industry_flow.json?t='+Math.floor(Date.now()/600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const rows=(d&&d.industries)||[];
      if(!rows.length)throw new Error('檔案沒有任何產業');
      MAINSTREAM_CACHE=rows.filter(x=>x.inflow_pct!=null&&x.inflow_pct>0).slice(0,5)
        .map(x=>({id:x.industry,label:x.industry,scoreInd:x.industry,inflow:x.inflow_pct,pct:x.pct,streak:x.streak,cumGain:x.cum_gain_pct,crowded:x.crowded,date:x.date}));
      MAINSTREAM_SRC=`來源：repo 每日收盤成交值依產業加總（資料日 ${(d.meta&&d.meta.data_date)||'—'}）`;
      renderMainstreamChips();
      return;
    }catch(e){repoErr=String(e&&e.message||e);console.warn('[loadMainstreamIndustries:repo]',e);recordGlobalError('loadMainstreamIndustries:repo',e)}
    const results=await Promise.all(HEAT_CATS.map(fetchIndustryFlow));
    MAINSTREAM_CACHE=results.filter(r=>r.inflow!=null&&r.inflow>0).sort((a,b)=>b.inflow-a.inflow).slice(0,5);
    MAINSTREAM_SRC=`來源：FinMind 產業指數（repo industry_flow.json 讀取失敗：${repoErr}）`;
    renderMainstreamChips();
  }
  // 選股榜每列展開/收合（不離開排行榜頁），跟點整列導去完整報告頁分開——點展開箭頭
  // 才切換這個detail區塊，點列的其他地方仍導去showReport()看完整版（含分批進場計畫）。
  function togglePickDetail(id){
    const el=document.getElementById(id);if(!el)return;
    el.style.display=el.style.display==='none'?'':'none';
    // 先.八十一-9：清單是精簡檔（因子沒有說明文字），第一次展開才讀這一檔的完整列
    if(el.style.display===''&&el.dataset.lite){
      const board=el.dataset.board,code=el.dataset.code;delete el.dataset.lite;
      _safeAsync('pickDetailFull',async()=>{
        const full=await fullPickRow(board,code);
        if(!full){el.innerHTML='<div class="note">因子明細載入失敗，請稍後再試或點列看完整報告</div>';return}
        const cfg=BOARD_CONFIG[board],c=cfg.cacheGet();
        el.innerHTML=pickDetailInner(full,cfg,(c&&c.stocks)||[]);
      });
    }
  }
  // 先.八十一-9：選股頁清單改讀 scores*_list.json（因子只有分數與百分位）。展開／報告要完整列時讀
  // data/by_code/<代號>.json 裡這一榜的列；讀不到才退回下載整份 scores*.json（並以完整檔取代精簡清單）。
  async function fullPickRow(board,code){
    const cfg=BOARD_CONFIG[board];
    const c=cfg.cacheGet();
    const hit=c&&!c._lite&&(c.stocks||[]).find(r=>r.code===code);
    if(hit)return hit;
    const d=await byCode(code);
    const row=d&&d[cfg.byCodeKey];
    if(row&&row.code===code){const x=Object.assign({},row);delete x._industry_pct;return x}
    try{
      const res=await fetch(cfg.file+'?_='+Date.now());
      if(!res.ok)throw new Error('HTTP '+res.status);
      const full=await res.json();cfg.cacheSet(full);
      return (full.stocks||[]).find(r=>r.code===code)||null;
    }catch(e){console.warn('[fullPickRow]',e);recordGlobalError('fullPickRow',e);return null}
  }
  function pickDetailInner(r,boardCfg,allRows){
    const weights=(boardCfg.cacheGet()&&boardCfg.cacheGet().weights)||{};
    return `<div class="note" style="margin:8px 0 4px">${buildReasonSummary(r,boardCfg)}</div>
        ${boardCfg.factorOrder.map(k=>factorContribRowHtml(k,r,boardCfg.factorLabels,weights,allRows||[])).join('')}`;
  }
  let PICKS_BOARD='value'; // 'value' | 'momentum' | 'future'
  let REPORT_CACHE=null;
  // 2026-09-06（P0 稽核.一）報告頁世代序號：跟首頁 HYDRATE_HOME_SEQ 同一套做法。
  // renderReport() 內有 await，快速連點兩檔時舊那次的 await 會晚回來並蓋掉新那檔的
  // 畫面（就是「光聖 6442 顯示 6808 的 32」的根因）。每次進入 renderReport 就把序號
  // 加一，await 之後只要序號變了就整批作廢，不准再碰 DOM。
  let REPORT_SEQ=0;
  let REPORT_CACHE_BOARD='value'; // 記錄目前顯示的報告屬於哪個榜單，factorRowHtml()要看這個決定用哪套FACTOR_LABELS
  let ENTRY_PLAN_CACHE=null;
  function barFill(coverage){
    return (coverage!=null&&coverage<0.5)?'rgba(216,176,112,.5)':'var(--gold-grad)';
  }
  let SUPPLY_VIEW=false;
  const PICKS_TOP_N=30; // 排行榜預設只顯示前 30 名，樣本其餘檔數靠搜尋查（見 generate_scores_v2.py 說明）
  let PICKS_INDUSTRY=null; // null = 全部產業
  // 2026-08-27新增（策略層面決定）：三榜共用同一個載入/渲染函式，只是檔名跟
  // 存放的cache變數不同——PICKS_BOARD決定要抓哪個檔案、存進哪個cache，設定
  // 都集中在上面的BOARD_CONFIG。
  function _picksBoardConfig(){
    return BOARD_CONFIG[PICKS_BOARD];
  }
  async function hydratePicks(forceReload){
    renderMktToggle('picks');onPicksToggleChange();
    renderPicksBoardToggle();
    applySupplyMode();
    if(SUPPLY_VIEW){_safeAsync('hydrateSupply',()=>hydrateSupply(forceReload));return}
    _safeAsync('loadMainstreamIndustries',loadMainstreamIndustries);
    const cfg=_picksBoardConfig();
    await ensureDisposalFlags().catch(e=>{console.warn('[ensureDisposalFlags]',e);recordGlobalError('ensureDisposalFlags',e)});  // 先.五十一-3：排除處置股前先載旗標
    if(cfg.cacheGet()&&!forceReload){renderPicks(cfg.cacheGet());stampUpdated('picks');return}
    const listEl=document.getElementById('picks-list');
    listEl.innerHTML=skeletonRowsHtml(6);  // 2026-09-15 P0產品.四：骨架屏取代純文字「載入中」
    try{
      // 先.八十一-9：先讀精簡清單（gzip 約為完整檔的一成多），讀不到才讀完整檔
      let res=await fetch(cfg.listFile+'?_='+Date.now()).catch(e=>{console.warn('[loadPicks:list]',e);return null});
      if(!res||!res.ok)res=await fetch(cfg.file+'?_='+Date.now());
      if(!res.ok)throw new Error('HTTP '+res.status);
      const json=await res.json();
      cfg.cacheSet(json);
      renderPicks(json);
      stampUpdated('picks');
    }catch(e){
      console.warn('[loadPicks]',e);recordGlobalError('loadPicks',e);
      listEl.innerHTML=`<div class="note">尚未產生 ${cfg.file}，或載入失敗（${e.message}）。此清單由 research/${cfg.label} 在本機/排程產生後 commit 進repo，不是即時報價。</div>`;
      document.getElementById('picks-asof-line').textContent='—';
    }
  }
  // 切換價值成長榜/題材動能榜——兩榜完全獨立的因子/權重（見
  // research/score_live_momentum.py檔頭說明），切換時保留各自的cache，
  // 不用每次都重新fetch。

  // ══════ 2026-10-01（先.八-三）供給吃緊觀察清單：只顯示 I1–I4 原始變化值與桶內百分位，無綜合分數／排名／績效 ══════
  let SUPPLY_CACHE=null,SUPPLY_FILTER='',SUPPLY_SORT='I1',SUPPLY_DESC=true,SUPPLY_SHOWN=100;
  const SUPPLY_IND_LABEL={I1:'預收增加',I2:'存貨周轉',I3:'毛利率',I4:'資本支出'};
  function applySupplyMode(){
    const sc=document.getElementById('scr-picks');if(sc)sc.classList.toggle('supply-mode',!!SUPPLY_VIEW);
    const card=document.getElementById('picks-supply-card');if(card)card.style.display=SUPPLY_VIEW?'':'none';
  }
  function switchSupplyView(){
    if(SUPPLY_VIEW)return;
    SUPPLY_VIEW=true;
    renderPicksBoardToggle();applySupplyMode();
    _safeAsync('hydrateSupply',()=>hydrateSupply(false));
  }
  async function hydrateSupply(forceReload){
    const listEl=document.getElementById('supply-list');if(!listEl)return;
    if(SUPPLY_CACHE&&!forceReload){renderSupply();return}
    listEl.innerHTML=skeletonRowsHtml(6);
    try{
      const res=await fetch('data/supply_watchlist.json?_='+Math.floor(Date.now()/3600000));
      if(!res.ok)throw new Error('HTTP '+res.status);
      SUPPLY_CACHE=await res.json();
      renderSupply();
    }catch(e){
      console.warn('[hydrateSupply]',e);recordGlobalError('hydrateSupply',e);
      listEl.innerHTML='<div class="note">尚未產生 data/supply_watchlist.json，或載入失敗（'+String(e.message).replace(/[&<>]/g,'')+'）。此清單由排程每日產生後 commit 進 repo。</div>';
      const m=document.getElementById('supply-meta-line');if(m)m.textContent='—';
    }
  }
  function onSupplyFilter(v){SUPPLY_FILTER=v;SUPPLY_SHOWN=100;_safeSync('renderSupply',renderSupply)}
  function onSupplySort(k){
    if(SUPPLY_SORT===k)SUPPLY_DESC=!SUPPLY_DESC;else{SUPPLY_SORT=k;SUPPLY_DESC=true}
    SUPPLY_SHOWN=100;_safeSync('renderSupply',renderSupply);
  }
  function supplyMoreTap(){SUPPLY_SHOWN+=100;_safeSync('renderSupply',renderSupply)}
  function supplyFmt(k,v){
    if(v==null||!isFinite(v))return '—';
    if(k==='I2')return (v>0?'+':'')+v.toFixed(2)+'次';
    const pp=v*100;return (pp>0?'+':'')+pp.toFixed(2)+'pp';
  }
  function renderSupply(){
    const d=SUPPLY_CACHE;if(!d)return;
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const m=d.meta||{};
    const covPct=m.coverage_period!=null?(m.coverage_period*100).toFixed(1)+'%':'—';
    const lowCov=m.coverage_period!=null&&m.coverage_period<0.8;
    // 先.八十一-14：as_of 是「內容最後一次有變動」的日期，不是最後檢查日——本機排程每晚 23:00 重算，內容沒變不改寫。
    // 基準季在下一季法定期限過後才會換，畫面寫明，避免看起來像排程停了。
    const _nextDl={Q1:'8/14（第二季）',Q2:'11/14（第三季）',Q3:'隔年 3/31（年報）',Q4:'5/15（第一季）'}[String(m.period||'').slice(-2)]||'';
    const _unchangedTxt=`<br><span style="color:var(--ink-3)">內容自 ${esc(m.as_of)} 起沒有變動：每晚 23:00 本機排程重算，基準季仍是 ${esc(m.period)}${_nextDl?'，下一季財報法定期限 '+_nextDl+' 過後才會換季':''}。</span>`;
    document.getElementById('supply-meta-line').innerHTML=
      `基準季 <b>${esc(m.period)}</b>（法定公告期限 ${esc(m.period_deadline)} 已過）· 資料日 ${esc(m.as_of)}<br>名冊 ${m.n_universe} 檔，已入庫該季財報 ${m.n_with_period} 檔（${covPct}），可計百分位 ${m.n_scored} 檔`
      +(lowCov?`<br><span style="color:#c9a35a">資料準備中（已涵蓋 ${m.n_with_period}／${m.n_universe.toLocaleString('en-US')} 檔）：財報入庫覆蓋率未達 80%，暫不顯示桶內百分位，下列僅列已入庫股票的原始變化值</span>`:'')+_unchangedTxt;
    const rows=d.rows||[];
    const inds=[...new Set(rows.map(r=>r.i))].sort();
    const sel=document.getElementById('supply-industry');
    if(sel&&sel.options.length!==inds.length+1){
      sel.innerHTML='<option value="">全部產業</option>'+inds.map(i=>`<option value="${esc(i)}">${esc(i)}</option>`).join('');
    }
    if(sel)sel.value=SUPPLY_FILTER;
    document.getElementById('supply-sort-chips').innerHTML=['I1','I2','I3','I4'].map(k=>{
      const on=SUPPLY_SORT===k;
      return chip(`${k} ${SUPPLY_IND_LABEL[k]}${on?(SUPPLY_DESC?' ↓':' ↑'):''}`,on,`onSupplySort('${k}')`);
    }).join('');
    const idx={I1:0,I2:1,I3:2,I4:3}[SUPPLY_SORT];
    let list=SUPPLY_FILTER?rows.filter(r=>r.i===SUPPLY_FILTER):rows.slice();
    list.sort((a,b)=>{
      const x=a.v[idx],y=b.v[idx];
      const xn=(x==null),yn=(y==null);
      if(xn&&yn)return a.c<b.c?-1:1;
      if(xn)return 1;if(yn)return -1;
      return SUPPLY_DESC?(y-x):(x-y);
    });
    const listEl=document.getElementById('supply-list');
    if(!list.length){listEl.innerHTML='<div class="note">目前沒有已入庫該季財報的股票符合條件。</div>';document.getElementById('supply-more').innerHTML='';return}
    const cell=(k,r,j)=>{
      const p=r.p[j];
      const pTxt=lowCov?'':`<div class="num" style="font-size:10.5px;color:var(--ink-3)">${p==null?'—':'桶內 '+Math.round(p*100)+'%'}</div>`;
      return `<div style="flex:1;min-width:0"><div style="font-size:10px;color:var(--ink-3)">${k}</div><div class="num" style="font-size:12.5px">${supplyFmt(k,r.v[j])}</div>${pTxt}</div>`;
    };
    listEl.innerHTML=list.slice(0,SUPPLY_SHOWN).map(r=>
      `<div style="padding:9px 0;border-bottom:1px solid var(--hairline)"><div style="display:flex;justify-content:space-between;gap:8px"><b style="font-size:13.5px">${esc(r.n)} ${esc(r.c)}</b><span class="note" style="margin:0">${esc(r.i)}${r.b!==r.i?'（桶：'+esc(r.b)+'）':''}${(r.sc||lowCov)?'':' · 指標不足3項，無百分位'}</span></div>`
      +`<div style="display:flex;gap:6px;margin-top:4px">${['I1','I2','I3','I4'].map((k,j)=>cell(k,r,j)).join('')}</div></div>`).join('');
    document.getElementById('supply-more').innerHTML=list.length>SUPPLY_SHOWN?chip(`再顯示 100 檔（共 ${list.length}）`,false,'supplyMoreTap()'):`<span class="note">共 ${list.length} 檔</span>`;
    const ind=m.indicators||{};
    document.getElementById('supply-defs').innerHTML=['I1','I2','I3','I4'].map(k=>`${k}：${esc(ind[k]||'')}`).join('<br>')
      +'<br>百分位：'+(lowCov?'（覆蓋率達 80% 後才顯示）':'')+esc(m.percentile_def||'')+'<br>限制：'+(m.limits||[]).map(esc).join('；');
  }
  function switchPicksBoard(board){
    const wasSupply=SUPPLY_VIEW;
    if(PICKS_BOARD===board&&!wasSupply)return;
    SUPPLY_VIEW=false;applySupplyMode();
    PICKS_BOARD=board;
    PICKS_INDUSTRY=null; // 換榜單時清掉產業篩選，避免舊榜單選的產業在新榜單裡對不上
    renderPicksBoardToggle();
    hydratePicks(false);
  }
  function renderPicksBoardToggle(){
    const el=document.getElementById('picks-board-toggle');if(!el)return;
    const mk=(id)=>`<span class="mtg-opt press${(!SUPPLY_VIEW&&PICKS_BOARD===id)?' on':''}" style="flex:1;text-align:center" onclick="switchPicksBoard('${id}')">${BOARD_CONFIG[id].title}</span>`;
    el.innerHTML=Object.keys(BOARD_CONFIG).map(mk).join('')
      +`<span class="mtg-opt press${SUPPLY_VIEW?' on':''}" style="flex:1;text-align:center" onclick="switchSupplyView()">供給觀察</span>`;
  }
  // 沒有公司名稱（null/缺欄位）時退回只顯示代號，不要顯示 "null"/"undefined" 這種假名稱。
  function pickLabel(r){
    return r.name?`${r.name} ${r.code}`:r.code;
  }
  // 2026-08-25 修正：25+個產業全部塞進一列橫向捲動 chips，CJK文字沒設white-space:nowrap
  // 時瀏覽器會在任兩個中文字之間換行，chip被撐成兩行、跟下一列內容重疊（iPhone 16實機
  // 截圖回報過）。修法：(1) 每個chip補white-space:nowrap，文字不會再被逼著換行；
  // (2) 橫向列只放常用前8個（依樣本中檔數由多到少排序，不是字母序，常用的優先露出），
  // 其餘用「更多」開下面的全選單（sheet，flex-wrap讓多個chip自然換行，不受單列高度限制）。
  const PICKS_CHIPS_VISIBLE=8;
  let PICKS_ALL_INDUSTRIES=[];
  function renderPicksChips(allRows){
    const counts={};
    allRows.forEach(r=>{if(r.industry)counts[r.industry]=(counts[r.industry]||0)+1});
    const industries=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]);
    PICKS_ALL_INDUSTRIES=industries;
    const chipsEl=document.getElementById('picks-chips');
    const visible=industries.slice(0,PICKS_CHIPS_VISIBLE);
    // 如果目前選的產業篩選不在常用前8名內（從全選單挑的），也要讓它顯示在橫向列上，
    // 不然使用者選了之後會看不到自己選的是哪個、以為篩選失效。
    if(PICKS_INDUSTRY&&!visible.includes(PICKS_INDUSTRY))visible.push(PICKS_INDUSTRY);
    chipsEl.innerHTML=chip('全部',PICKS_INDUSTRY===null,'filterPicksByIndustry(null)')
      +visible.map(ind=>chip(`${ind}(${counts[ind]})`,PICKS_INDUSTRY===ind,`filterPicksByIndustry('${ind}')`)).join('')
      +(industries.length>PICKS_CHIPS_VISIBLE?chip('更多 ⋯',false,'openIndustrySheet()'):'');
  }
  function openIndustrySheet(){
    const el=document.getElementById('industry-sheet-list');
    el.innerHTML=chip('全部',PICKS_INDUSTRY===null,"filterPicksByIndustry(null);closeIndustrySheet()")
      +PICKS_ALL_INDUSTRIES.map(ind=>chip(ind,PICKS_INDUSTRY===ind,`filterPicksByIndustry('${ind}');closeIndustrySheet()`)).join('');
    document.getElementById('industry-mask').classList.add('open');
    document.getElementById('industry-sheet').classList.add('open');
  }
  function currentPicksCache(){
    return BOARD_CONFIG[PICKS_BOARD].cacheGet();
  }
  function filterPicksByIndustry(ind){
    PICKS_INDUSTRY=PICKS_INDUSTRY===ind?null:ind; // 再點一次同一個 chip 取消篩選
    const cache=currentPicksCache();
    if(cache)renderPicks(cache);
    renderMainstreamChips();
  }
  function boardCfg0(){return BOARD_CONFIG[PICKS_BOARD]}
  function pickRowHtml(r,allRows){
    // 2026-08-27修正（P1-新，使用者裁示「選股改為全市場+資料完整度，不要用
    // 門檻排除」）：coverage不再是伺服器端排除條件，這裡改成「視覺弱化」——
    // 低完整度的卡片降低整體不透明度+加註「資料稀疏」，但仍然完整顯示，
    // 不隱藏、不排除。流動性門檻維持不變（不進數字排名，rank會是null）。
    const _pcache=boardCfg0().cacheGet();
    const planB=!!(_pcache&&_pcache.meta&&_pcache.meta.score_scheme==='B'&&PICKS_BOARD==='value');
    const lowCov=!planB&&r.coverage<0.5;  // 方案B：總分只看低波動，資料完整度不影響總分，不再變淡/標資料稀疏
    const lowLiq=(r.flags||[]).includes('流動性不足');
    const topPick=r.rank===1;
    const boardCfg=BOARD_CONFIG[PICKS_BOARD];
    const labelsForBoard=boardCfg.factorLabels;
    const missingLabels=(r.missing_factors||[]).map(k=>labelsForBoard[k]||k);
    // 2026-09-15（P0產品.二）選股榜每列可展開：點展開箭頭才切換下面這塊因子拆解，
    // 不影響點列其他地方導去showReport()看完整報告（含分批進場計畫）的既有行為。
    const detailId='pick-detail-'+PICKS_BOARD+'-'+r.code;
    return `
    <div class="row press rise" style="flex-direction:column;align-items:stretch;gap:8px;cursor:pointer;background:var(--card-grad);border:1px solid ${topPick?'rgba(216,176,112,.3)':'var(--hairline)'};border-radius:16px;padding:14px;margin-bottom:10px;opacity:${lowCov?0.62:1}" onclick="showReport('${r.code}')">
      <div style="display:flex;align-items:center;gap:12px">
        <div class="num" style="width:24px;text-align:center;font-size:15px;font-weight:700;color:${topPick?'var(--gold)':'var(--ink-3)'}">${r.rank??'—'}</div>
        <div class="nm" style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap"><b style="font-size:15.5px">${pickLabel(r)}</b>${r.industry?`<span style="font-size:9.5px;color:var(--ink-2);background:rgba(255,255,255,.06);padding:2px 6px;border-radius:5px">${r.industry}</span>`:''}</div>
          <div style="font-size:11px;color:var(--ink-3);margin-top:4px">${r.summary||''}${lowCov?'<br><span style="color:#c9a35a">⚠ 資料稀疏，分數僅供參考'+(missingLabels.length?'（缺'+missingLabels.join('、')+'）':'')+'</span>':''}${lowLiq?'<br><span style="color:#c9524a">⚠ 流動性不足 · 不進數字排名</span>':''}</div>
          <div style="font-size:10px;color:var(--ink-4);margin-top:2px">近20日均成交值 ${fmtLiquidity(r.liquidity_20d)}元 · 資料完整度 ${Math.round(r.coverage*100)}%</div>
        </div>
        <div style="text-align:right;flex-shrink:0"><div class="num" style="font-size:20px;font-weight:700;color:${scoreColor(r.total_score)}">${r.total_score.toFixed(1)}</div><div style="font-size:9px;color:var(--ink-4)">/ 10</div></div>
        <button type="button" class="press" style="flex-shrink:0;background:none;border:none;color:var(--ink-3);font-size:16px;padding:2px 6px;line-height:1" onclick="event.stopPropagation();togglePickDetail('${detailId}')" aria-label="展開選股理由">⌄</button>
      </div>
      <div class="meter" style="height:5px;margin-top:0"><i style="width:${(r.total_score*10).toFixed(0)}%;background:${barFill(r.coverage)}"></i></div>
      <div id="${detailId}" style="display:none" onclick="event.stopPropagation()"${r._lite?` data-lite="1" data-board="${PICKS_BOARD}" data-code="${r.code}"`:''}>
        ${r._lite?`<div class="note" style="margin:8px 0 4px">${buildReasonSummary(r,boardCfg)}</div>`+skeletonHtml(3):pickDetailInner(r,boardCfg,allRows)}
      </div>
    </div>`;
  }
  function renderPicks(json){
    const meta=json.meta||{};
    const covTxt=meta.universe_size?`（涵蓋 ${(json.stocks||[]).length}/${meta.universe_size} 檔全市場宇宙）`:'';
    document.getElementById('picks-asof-line').textContent='資料基準日 '+(meta.data_asof||'—')+' · 樣本 '+(json.stocks||[]).length+' 檔'+covTxt;
    const weightNoteEl=document.getElementById('picks-weight-note');
    if(weightNoteEl){
      const noteByEngine={
        'scoring-momentum-v1':'題材動能榜：因子聚焦股價領先財報的動能訊號，財報只當地雷排除用，估值不扣分 ｜ 相對強度已改用還原權息收盤價，除息事件涵蓋率隨每日累積逐步提高，剛上線這幾週可能還沒回溯到少數個股的最新事件 ｜ ⚠ 創新高/量價配合度因子的門檻參數（1.3倍/2.5倍/0.6/0.7等）為經驗值，尚未經統計驗證 ｜ 非投資建議',
        'scoring-future-v1':'未來性濾網：因子聚焦法人籌碼行為+毛利率品質+產能利用率代理（(a)類，現在就能算的部分）｜ 非投資建議',
      };
      weightNoteEl.textContent=noteByEngine[meta.engine_version]
        ||(meta.score_scheme==='B'
          ?'價值成長榜（計分方案B）：總分只用低波動（近60日日報酬標準差，越低越高分）；其餘成分明細僅供參考、不計分 ｜ 非投資建議'
          :'價值成長榜（計分方案A・恢復，2026-09-30生效）：八項成分依凍結權重加權；權重凍結於2024-12-31前之研究期。尚未回測驗證，財報成長成分重驗未過（#287/#403），僅供參考 ｜ 非投資建議');
    }
    // 2026-09-30（價值成長榜恢復）三榜共用：scores*.json 的 meta.backtest_status 一律顯示成標籤；meta.backtest_note（若有）接在標籤後；方案B（已撤銷）的揭露全文仍相容。
    _safeSync('renderPicksBacktestTag',()=>{
      const el=document.getElementById('picks-backtest-note');
      const covEl=document.getElementById('picks-coverage-note');
      const planB=meta.score_scheme==='B';
      if(el){
        if(meta.backtest_status){
          const esc=t=>String(t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
          el.innerHTML=`<span style="display:inline-block;font-size:10.5px;font-weight:600;color:#c9524a;border:1px solid rgba(201,82,74,.5);border-radius:6px;padding:1px 7px">${esc(meta.backtest_status)}</span>`
            +(meta.backtest_note?` <span style="color:var(--ink-3)">${esc(meta.backtest_note)}</span>`:'')
            +(planB&&meta.score_scheme_disclosure?` <span style="color:var(--ink-3)">${esc(meta.score_scheme_disclosure)}</span>`:'');
          el.style.display='';
        }else{el.style.display='none'}
      }
      if(covEl)covEl.style.display=planB?'none':'';
    });
    const allRows=json.stocks||[];
    renderPicksChips(allRows);
    const listEl=document.getElementById('picks-list');
    if(!allRows.length){listEl.innerHTML='<div class="note">無資料</div>';return}
    // rank 為 null 的股票是流動性不足、已被排除於排行榜之外（仍留在 allRows 供搜尋），
    // 這裡的排行榜清單只顯示有 rank 的。
    // 2026-10-08（先.五十一-3）AI 選股候選排除處置期間內個股（分盤撮合＋預收款券，實際難以進出）。
    // 旗標檔沒載到時 isDisposalNow 一律回 false＝不排除，只在清單上方說明。
    const ranked0=allRows.filter(r=>r.rank!=null);
    const base=PICKS_INDUSTRY?ranked0.filter(r=>r.industry===PICKS_INDUSTRY):ranked0;
    const excluded=base.filter(r=>isDisposalNow(r.code));
    const filtered=(excluded.length?base.filter(r=>!isDisposalNow(r.code)):base).slice(0,PICKS_TOP_N);
    const topEx=base.slice(0,PICKS_TOP_N).filter(r=>isDisposalNow(r.code));
    const dispNote=excluded.length
      ?`<div class="note" id="picks-disposal-note" style="color:#c9524a;margin-bottom:6px">已排除處置股 ${excluded.length} 檔${topEx.length?`（原本在前 ${PICKS_TOP_N} 名：${topEx.map(r=>r.code+(r.name?' '+r.name:'')).join('、')}）`:''}（資料：${(DISPOSAL_FLAGS&&DISPOSAL_FLAGS.meta&&DISPOSAL_FLAGS.meta.generated_at||'').slice(0,16).replace('T',' ')||'—'}）</div>`
      :(DISPOSAL_FLAGS&&DISPOSAL_FLAGS.meta?'':'<div class="note" id="picks-disposal-note" style="margin-bottom:6px">處置股旗標未載入，本清單未排除處置股</div>');
    listEl.innerHTML=dispNote+filtered.map(r=>pickRowHtml(r,allRows)).join('');
  }
  // 搜尋任一檔（樣本內即使不在排行榜前段也查得到，樣本外誠實顯示查無資料——見
  // generate_scores_v2.py 的說明：目前架構沒有後端可以現算一支新股票的橫斷面百分位）。
  function onPicksSearchInput(q){
    const resEl=document.getElementById('picks-search-result');
    const listCard=document.getElementById('picks-list-card');
    const chipsEl=document.getElementById('picks-chips');
    q=q.trim();
    if(!q){resEl.innerHTML='';listCard.style.display='';chipsEl.classList.remove('off-search');return}
    listCard.style.display='none';chipsEl.classList.add('off-search');  // 先.八十-4：切 class，不設 style.display
    const rows=(currentPicksCache()&&currentPicksCache().stocks)||[];
    const ql=q.toLowerCase();
    const hits=rows.filter(r=>r.code.toLowerCase().includes(ql)||(r.name&&r.name.includes(q)));
    if(!hits.length){
      resEl.innerHTML=`<div class="note" style="padding:14px 2px">查無「${q}」的評分資料——可能不在這輪抽樣樣本內，或資料完整度不足（&lt;50%）沒有計算。樣本涵蓋 ${rows.length} 檔，非全市場逐檔掃描。</div>`;
      return;
    }
    resEl.innerHTML=`<div class="card" style="margin-top:2px"><h3>搜尋結果</h3>${hits.map(r=>pickRowHtml(r,rows)).join('')}</div>`;
  }

  // ── 個股研究報告頁 ──
  function showReport(code){
    const cache=currentPicksCache();
    const row=(cache&&cache.stocks||[]).find(r=>r.code===code);
    if(!row){toast('查無這檔的評分資料');return}
    const board=PICKS_BOARD;
    const open=r=>{REPORT_CACHE=r;REPORT_CACHE_BOARD=board;ENTRY_PLAN_CACHE=null;go('report')};
    if(!row._lite){open(row);return}
    // 先.八十一-9：清單是精簡列（沒有 raw／說明文字），報告頁要完整列，先讀這一檔的完整列再進報告
    _safeAsync('showReport:full',async()=>{
      const full=await fullPickRow(board,code);
      if(!full){toast('這檔的完整評分明細載入失敗，請稍後再試');return}
      open(full);
    });
  }
  let EXTREME_MOVE_ACTIVE=false;
  function factorRowHtml(key){
    const boardCfg=BOARD_CONFIG[REPORT_CACHE_BOARD];
    const cache=boardCfg.cacheGet();
    const weights=(cache&&cache.weights)||{};
    const allRows=(cache&&cache.stocks)||[];
    return factorContribRowHtml(key,REPORT_CACHE,boardCfg.factorLabels,weights,allRows);
  }
  // ── 2026-09-05（新一.7）極端走勢防呆 ────────────────────────────────
  // 60日漲幅 >80%、或營收年增觸到評分引擎的 ±200% 硬上限，代表這檔已經走完一大段、或成長率是
  // 低基期／併購這類特殊事件造成的。這種情況下「分批買入計畫」那種看起來像操作建議的東西不該
  // 出現，改在頂端明講風險。判斷只用 scores.json 已經算好的欄位（technical.gain_60d、
  // growth_quality/revenue_momentum 的年增率），不打任何新的資料源。
  const EXTREME_60D_GAIN=0.8;
  const REVENUE_YOY_CAP=2.0;
  function extremeMoveFlags(row){
    const out=[];const f=(row&&row.factors)||{};
    const g=f.technical&&f.technical.raw&&f.technical.raw.gain_60d;
    if(g!=null&&g>EXTREME_60D_GAIN)out.push(`近60個交易日已上漲 ${(g*100).toFixed(0)}%`);
    const yoy=f.growth_quality&&f.growth_quality.raw&&f.growth_quality.raw.rev_growth_12m_yoy;
    if(yoy!=null&&yoy>=REVENUE_YOY_CAP)out.push(`近12個月營收年增平均 ${(yoy*100).toFixed(0)}%（觸及評分上限，多為低基期或併購造成，不代表可延續）`);
    const rm=f.revenue_momentum&&f.revenue_momentum.raw&&f.revenue_momentum.raw.rev_yoy;
    if(rm!=null&&rm>=REVENUE_YOY_CAP)out.push(`最新月營收年增 ${(rm*100).toFixed(0)}%（同屬特殊基期）`);
    return out;
  }
  function renderExtremeMoveWarning(row){
    const host=document.getElementById('report-extreme-warning');if(!host)return;
    const flags=extremeMoveFlags(row);
    EXTREME_MOVE_ACTIVE=flags.length>0;
    if(!EXTREME_MOVE_ACTIVE){host.style.display='none';host.innerHTML='';return}
    host.style.display='';
    // 2026-09-06（實測.四）總司令裁示取消「極端走勢就不顯示分批進場」：
    // 階梯照顯示，把判斷權留給使用者，這裡只負責把風險講得夠醒目。
    host.innerHTML=`⚠ 追高風險提醒：${flags.join('；')}。下方進場階梯照常顯示，但請自行判斷是否值得追。`;
  }
  async function renderReport(){
    const row=REPORT_CACHE;
    if(!row)return;
    const runId=++REPORT_SEQ;
    // ── 2026-09-06（P0 稽核.一）進場先清空「上一檔留下來的內容」──────────────
    // 這是「光聖 6442 顯示 32」那一類錯誤的第三層防線。前兩層（世代守衛、價格
    // 恆等式）只擋得住「錯的東西被寫進來」；這一層擋的是「對的東西沒寫進來，
    // 舊的東西就留在原地」——只要 renderReport 中途因為任何原因中斷（例如當時
    // 的 peg=null 讓 toFixed 拋錯），畫面上就會同時出現新股票的名字和舊股票的
    // 數字，而且完全沒有任何錯誤提示。清空之後最壞情況是顯示「載入中…」，
    // 不會是另一檔股票的價格。
    ['report-factors','report-industry-tech','report-entry-plan','report-events','report-valuation-band'].forEach(id=>{
      const el=document.getElementById(id);if(el)el.innerHTML=skeletonHtml(4);  // 2026-09-15 P0產品.四：骨架屏
    });
    const opEl=document.getElementById('report-order-plan');if(opEl)opEl.innerHTML='';
    ENTRY_PLAN_CACHE=null;
    document.getElementById('report-asof').textContent=`資料時間：${row.data_asof}（盤後/延遲資料） ｜ ⚠️ 非投資建議`;
    document.getElementById('report-name').textContent=pickLabel(row);
    document.getElementById('report-industry').textContent=row.industry||'—';
    document.getElementById('report-total-score').textContent=row.total_score.toFixed(1);
    document.getElementById('report-total-score').style.color=scoreColor(row.total_score);
    const covPct=Math.round(row.coverage*100);
    document.getElementById('report-coverage').textContent=`資料完整度 ${covPct}%${row.score_scheme==='B'?'（明細因子資料完整度；方案B總分只用低波動，不受影響）':row.coverage<0.7?'（部分因子本次缺資料，總分依「重新分配權重」規則計算，僅供參考）':''}`;
    document.getElementById('report-summary').textContent=row.summary||'';
    _safeSync('renderExtremeMoveWarning',()=>renderExtremeMoveWarning(row));  // 2026-09-05 新一.7
    _safeAsync('renderReportEvents',()=>renderReportEvents(row));  // 2026-09-08 建置一.1
    _safeAsync('renderValuationBand',()=>renderValuationBand(row));  // 2026-09-10 建置一.2
    // 環形讀條：滿圈周長 251.2（r=40），offset 從滿圈（0分）動畫到對應總分的角度
    const ring=document.getElementById('report-ring');
    ring.style.strokeDashoffset='251.2';
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      ring.style.strokeDashoffset=(251.2*(1-row.total_score/10)).toFixed(1);
    }));
    updateReportWatchBtn(row.code);

    _safeSync('renderReport:factors',()=>{
      const orderForBoard=BOARD_CONFIG[REPORT_CACHE_BOARD].factorOrder;
      const factorsHtml=orderForBoard.map(factorRowHtml).join('');
      document.getElementById('report-factors').innerHTML=factorsHtml||'<div class="note">無評分資料</div>';
    });

    // 產業分析/財報數據/技術型態：直接引用已算好的 raw 數據，不編造敘述
    // 2026-09-06：整段包進 _safeSync（CLAUDE.md 錯誤隔離原則）。原本沒有包，
    // 一個欄位是 null 就讓整個 renderReport 停在這裡，後面的分批進場計畫完全
    // 不會被重畫，上一檔的價格就留在畫面上——這正是總司令看到的那個畫面。
    _safeSync('renderReport:facts',()=>{
    const f=row.factors||{};
    let itHtml='<div class="facts">';
    itHtml+=`<div class="f"><span>所屬產業</span><b>${row.industry||'—'}</b></div>`;
    // 2026-09-06：每一行都「有值才顯示」，缺值直接不列出這一行（不列 > 列「—」>
    // 列「0.0%」）。原本只檢查因子物件存在、沒檢查欄位本身，pe/peg 為 null 會崩潰，
    // eps_yoy/rev_yoy 為 null 會印成 0.0%。
    const fact=(label,v,fmt)=>{if(v==null||typeof v!=='number'||!isFinite(v))return;itHtml+=`<div class="f"><span>${label}</span><b>${fmt(v)}</b></div>`};
    if(f.earnings_growth)fact('EPS 年增',f.earnings_growth.raw.eps_yoy,v=>fmtPct(v));
    if(f.revenue_momentum)fact('月營收年增',f.revenue_momentum.raw.rev_yoy,v=>fmtPctCapped(v,REVENUE_YOY_CAP));
    if(f.growth_quality)fact('近12月營收年增',f.growth_quality.raw.rev_growth_12m_yoy,v=>fmtPctCapped(v,REVENUE_YOY_CAP));
    if(f.valuation_adj)fact('本益比 PE',f.valuation_adj.raw.pe,v=>fmtN(v,1));
    if(f.valuation_adj)fact('PEG',f.valuation_adj.raw.peg,v=>fmtN(v,2));
    // 2026-08-27修正（真bug）：scores.json現在有兩條產生管線——研究端
    // score_v2.py的chips原始值是「近20日均成交值的百分比」
    // (inst_net_pct_of_20d_trading_value)，JSON-only上線路徑generate_scores_live.py
    // 沒有per股票成交值資料，只能給「累積張數」(inst_net_lots_available_days)，
    // 兩者單位不同，不能互相假裝是同一個東西——這裡改成兩個key都檢查，各自用
    // 正確的單位顯示，缺兩者都沒有時完全不顯示這行（不是對undefined硬呼叫
    // .toFixed()崩潰，這是原本的bug，導致點一下選股排行列就會拋
    // unhandledrejection，冒煙測試check#6新增的最終錯誤檢查才抓到）。
    if(f.chips&&f.chips.raw.inst_net_pct_of_20d_trading_value!=null)fact('三大法人近20日買超',f.chips.raw.inst_net_pct_of_20d_trading_value,v=>fmtPct(v));
    else if(f.chips)fact('三大法人買賣超（累積張數）',f.chips.raw.inst_net_lots_available_days,v=>fmtN(v,0,' 張'));
    if(f.technical)fact('技術型態指標',f.technical.raw.ma60_breakout_x_volume_index,v=>fmtN(v,3));
    itHtml+='</div>';
    document.getElementById('report-industry-tech').innerHTML=itHtml;
    });

    document.getElementById('report-strategy').textContent='目前為「AI 綜合評分排行」清單性質，不是自動交易策略；下方按鈕只依分批進場計畫產生試算，不代表任何策略訊號。台股由 Shioaji 自動執行 Bb-90（真錢，附否決窗）；美股未串接下單（只交易白名單 ETF，與本頁個股無關）。';

    // 分批進場計畫：機械式資金分配規則（現價/-4%/-8%），不是估值預測，不是投資建議
    const planEl=document.getElementById('report-entry-plan');
    // 2026-09-05（新一.7）：極端走勢時完全不顯示分批買入計畫——這種價位下給出「現價/-4%/-8%」
    // 三檔進場價，看起來就像在建議承接，但實際上追高風險已經顯著升高。頂端的警示列會說明原因。
    const cta0=document.querySelector('#scr-report .buy-cta');if(cta0)cta0.style.display='';
    planEl.innerHTML=skeletonHtml(3);  // 2026-09-15 P0產品.四：骨架屏
    try{
      const usCode=isUS(row.code);
      // 常備.開發-20（先.六十七）：首頁不再整份載入 sparklines／quotes_all_tw，防線二的真值要自己備妥這一檔的小檔
      // 先.八十一-10：台股改讀 repo（by_code 近 60 日價）為主、FinMind 補充；美股照舊
      const [pxS]=await Promise.allSettled([usCode?fm('USStockPrice',row.code,_d(70)):twPxRepoFirst(row.code,_d(70)),ensureQuoteLite([row.code])]);
      if(pxS.status==='rejected')throw pxS.reason;
      const px=pxS.value;
      // 防線一：await 期間使用者已經切到別檔，這批結果作廢（不作廢就會把這一檔的
      // 價格寫進另一檔的頁面——光聖 6442 顯示 6808 的 32 就是這樣來的）。
      if(runId!==REPORT_SEQ)return;
      if(!px.length){planEl.innerHTML='<div class="note">'+fmEmptyMsg('查無報價資料')+'，無法計算分批進場價位。</div>';return}
      const closes=px.map(x=>usCode?x.Close:x.close).filter(x=>x!=null);
      const highs=px.map(x=>usCode?x.High:x.max).filter(x=>x!=null);
      const lows=px.map(x=>usCode?x.Low:x.min).filter(x=>x!=null);
      const last=closes[closes.length-1];
      const low20=Math.min(...closes.slice(-20));
      const low60=Math.min(...closes.slice(-60));
      // 防線二：跟全 App 唯一真值比對，差超過 ±30% 就不顯示任何數字。
      const sane=priceSanityFailure(row.code,last,'分批進場計畫');
      if(sane){
        planEl.innerHTML='<div class="note" style="color:var(--warn)">⚠ '+sane+'</div>';
        const ctaBad=document.querySelector('#scr-report .buy-cta');if(ctaBad)ctaBad.style.display='none';
        return;
      }
      // 2026-09-06（實測.四）改成**技術層級階梯**，不再用固定 −4%／−8%。
      // 固定百分比的問題是它跟這一檔的實際結構完全無關：−4% 對一檔日波動 1% 的
      // 金融股是很深的回檔，對一檔日波動 5% 的小型股只是雜訊。改成用這一檔自己的
      // 均線、前波低點與 ATR 當價位，每一階都標明依據，使用者看得懂為什麼是這個價。
      const ma=n=>{const a=closes.slice(-n);return a.length<n?null:a.reduce((x,y)=>x+y,0)/a.length};
      // ATR14：用真實區間（含跳空），沒有高低價時退回收盤差的絕對值
      const atr=(()=>{
        const n=14;
        if(highs.length>=n+1&&lows.length>=n+1){
          const trs=[];
          for(let i=closes.length-n;i<closes.length;i++){
            if(i<1)continue;
            const h=highs[i],l=lows[i],pc=closes[i-1];
            if(h==null||l==null||pc==null)continue;
            trs.push(Math.max(h-l,Math.abs(h-pc),Math.abs(l-pc)));
          }
          if(trs.length)return trs.reduce((x,y)=>x+y,0)/trs.length;
        }
        const diffs=[];
        for(let i=Math.max(1,closes.length-n);i<closes.length;i++)diffs.push(Math.abs(closes[i]-closes[i-1]));
        return diffs.length?diffs.reduce((x,y)=>x+y,0)/diffs.length:null;
      })();
      const swingLow=lows.length>=20?Math.min(...lows.slice(-20)):low20;
      const swingHigh=highs.length>=20?Math.max(...highs.slice(-20)):Math.max(...closes.slice(-20));

      // 候選層級。只留「不高於現價」的（進場階梯是等回檔，不是追價），
      // 現價那一階永遠保留當第一階。
      const cand=[
        {label:'現價進場',price:last,basis:'目前成交價'},
        {label:'5 日均線',price:ma(5),basis:'近 5 日收盤平均'},
        {label:'10 日均線',price:ma(10),basis:'近 10 日收盤平均'},
        {label:'20 日均線（月線）',price:ma(20),basis:'近 20 日收盤平均'},
        {label:'前波低點',price:swingLow,basis:'近 20 日最低價'},
        {label:'1×ATR 回撤',price:atr!=null?last-atr:null,basis:atr!=null?`ATR14 ${nf(atr.toFixed(2))}`:''},
        {label:'2×ATR 回撤',price:atr!=null?last-2*atr:null,basis:atr!=null?`ATR14 ${nf(atr.toFixed(2))} 的兩倍`:''},
      ].filter(x=>x.price!=null&&isFinite(x.price)&&x.price>0&&x.price<=last*1.0001);

      // 依價位由高到低排；價位太接近的（差 <0.5%）只留一個，避免出現三階幾乎同價
      cand.sort((a,b)=>b.price-a.price);
      const levels=[];
      for(const c of cand){
        if(levels.length&&Math.abs(levels[levels.length-1].price-c.price)/last<0.005){
          levels[levels.length-1].label+=`／${c.label}`;
          continue;
        }
        levels.push(c);
      }
      const picked=levels.slice(0,4);
      // 資金配置：第一階最重，越往下越輕（等回檔的機率遞減）。四階以內都給得出來。
      const WEIGHTS={1:[100],2:[60,40],3:[40,35,25],4:[35,30,20,15]};
      const w=WEIGHTS[picked.length]||[];
      // 2026-09-06（實測.四）價位取到合法檔位。ATR 算出來的是 1638.21 這種數字，
      // 台股 1000 元以上的最小跳動單位是 5 元，1638.21 根本掛不進去。往下取整
      // （買單取整到下一個合法價位，對買方只會更好），美股沒有這個問題所以跳過。
      const toTick=v=>{if(usCode)return v;const t=twseTick(v);return +(Math.floor(+(v/t).toFixed(6))*t).toFixed(2)};
      const tranches=picked.map((c,i)=>{const px2=toTick(c.price);
        return {label:c.label,price:px2,pct:w[i],basis:c.basis,off:((px2/last-1)*100)};});
      ENTRY_PLAN_CACHE={code:row.code,name:row.name,tranches};
      planEl.innerHTML=
        (EXTREME_MOVE_ACTIVE?`<div class="note" style="margin-bottom:10px;color:var(--warn);border:1px solid rgba(250,178,25,.35);border-radius:9px;padding:8px 10px"><b>⚠ 追高風險高</b>：${extremeMoveFlags(row).join('；')}。階梯照常顯示，判斷權在你。</div>`:'')+
        `<div class="note" style="margin-bottom:12px">⚠️ 技術層級分批規則（價位取自這一檔自己的均線／前波低點／ATR，非估值預測、非投資建議，僅為進場資金分配參考）。近期支撐參考：20 日低點 ${nf(low20.toFixed(2))}、60 日低點 ${nf(low60.toFixed(2))}、近 20 日最高 ${nf(swingHigh.toFixed(2))}。</div>`+
        `<div style="display:flex;flex-direction:column;gap:10px">`+
        tranches.map((t,i)=>`<div style="display:flex;align-items:center;gap:12px">
          <span class="num" style="width:22px;height:22px;border-radius:50%;background:rgba(216,176,112,.15);color:var(--gold);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">${i+1}</span>
          <span style="flex:1;font-size:12.5px;color:var(--ink-2)">${t.label}<br><span style="font-size:9.5px;color:var(--ink-4)">${t.basis}${t.off<-0.05?`　距現價 ${t.off.toFixed(1)}%`:''}</span></span>
          <span class="num" style="font-size:13px;font-weight:600">${nf(t.price.toFixed(2))}</span>
          <span class="num" style="font-size:10px;color:var(--ink-4);width:34px;text-align:right">${t.pct}%</span>
        </div>`).join('')+`</div>`;
    }catch(e){
      console.warn('[renderReport:tranches]',e);recordGlobalError('renderReport:tranches',e);
      planEl.innerHTML='<div class="note">分批進場價位計算失敗（'+e.message+'）。</div>';
    }
  }
  function updateReportWatchBtn(code){
    const btn=document.getElementById('report-watch-btn');if(!btn)return;
    const inWL=WL.includes(code);
    btn.querySelector('svg').innerHTML=inWL
      ?'<path d="M20 6L9 17l-5-5"/>'
      :'<path d="M12 4v16M4 12h16"/>';
    btn.style.borderColor=inWL?'rgba(216,176,112,.4)':'rgba(255,255,255,.08)';
  }
  function toggleReportWatch(){
    const row=REPORT_CACHE;if(!row)return;
    if(WL.includes(row.code)){WL=WL.filter(x=>x!==row.code);toast('已從觀察清單移除')}
    else{WL.push(row.code);toast('已加入觀察清單')}
    localStorage.setItem('alpha_wl',JSON.stringify(WL));pushWatchlistSoon();pushSettingsSoon();
    updateReportWatchBtn(row.code);
  }
  function generateOrderPlan(){
    if(!ENTRY_PLAN_CACHE){toast('分批進場計畫尚未載入完成');return}
    const {tranches}=ENTRY_PLAN_CACHE;
    document.getElementById('report-order-plan').innerHTML=`<div class="gate" style="margin-top:10px">
      <div style="font-weight:700;margin-bottom:8px">📋 下單計畫（僅顯示，不會送出）</div>
      ${tranches.map((t,i)=>`<div class="g">批次 ${i+1}：${nf(t.price.toFixed(2))} 元 · 資金配置 ${t.pct}% · 張數請自行決定</div>`).join('')}
      <div class="g" style="color:var(--warn);margin-top:8px">⚠️ 本計畫非投資建議、不構成買賣訊號；只顯示、不會實際下單。台股由 Shioaji 自動執行 Bb-90（真錢，附否決窗）；美股未串接下單，只交易白名單 ETF，與本計畫無關。</div>
    </div>`;
    toast('已產生下單計畫（僅顯示，未送出）');
  }
  // 近 30 日事件流。無事件時要**講清楚查了什麼**，不能只寫「無資料」——
  // 「沒查」跟「查了沒有」對使用者是完全不同的資訊。
  // ── 2026-09-10（建置一.2）估值區間（非目標價）─────────────────────────────
  // 總司令裁示：目標價卡改為「同產業本益比 25/50/75 百分位 × 近四季 EPS」，
  // 附產業樣本數與資料日期；EPS ≤0 或樣本 <8 檔顯示「同產業樣本不足無法估算」
  // 並列出樣本數。
  //
  // 這張卡刻意「不是目標價」：它只回答一個機械式問題——「如果這檔的本益比移動到
  // 同產業的 25/50/75 百分位，用它近四季 EPS 換算出來的股價是多少」。沒有預測、
  // 沒有機構評等（台股沒有免費的分析師目標價資料源，這點在因子說明裡已寫過）。
  //
  // 資料來源與回退鏈（CLAUDE.md 七、資料原則：主來源→備援→由已有欄位推導）：
  //   本益比（每一檔）   主：data/fundamentals.json ratios.per（TWSE 每日本益比
  //                         BWIBBU，官方定義即為「近四季 EPS」基準）
  //                     備援：收盤價 ÷ 近四季 EPS（stock_detail 季報加總）
  //   近四季 EPS（本檔） 主：data/stock_detail.json 連續四季 eps 加總
  //                         （TWSE t187ap06_L_ci 綜合損益表-一般業）
  //                     備援：收盤價 ÷ 官方本益比 回推（同樣是官方欄位的推導）
  // 每個輸出都帶 source 標記並直接寫在畫面上，不做靜默降級。
  const VALUATION_MIN_SAMPLE=8;      // 樣本 <8 檔一律不估（總司令裁示）
  const VALUATION_EPS_MAX_LAG_Q=4;   // 近四季 EPS 的最新一季落後超過 4 季就視為過期
  // ETF/ETN/受益證券/存託憑證沒有「同產業本益比」可言，直接不適用
  const VALUATION_EXCLUDED_INDUSTRY=/ETF|ETN|受益證券|存託憑證|所有證券|指數投資證券/;

  function _qIndex(y,q){return y*4+q}
  function _currentQIndex(nowMs){
    const z=_zonedParts(new Date(nowMs==null?Date.now():nowMs),'Asia/Taipei');
    return z.y*4+Math.floor((z.m-1)/3)+1;
  }
  // 近四季 EPS：**必須是連續四季，而且不能過期**。
  // 這兩個檢查不是防禦性程式碼潔癖，是實測踩出來的：data/stock_detail.json 的季報
  // 歷史是 2026-08-27 一次性回補到 2024Q4，之後每日排程只補「當下最新那一季」，
  // 中間 2025Q1~2026Q1 是空的。直接取陣列最後四筆的話：
  //   2317 鴻海 會得到 2024Q2+2024Q3+2024Q4+2026Q2 = 17.26（橫跨兩年的假 TTM）
  //   2603 長榮 會得到 67.88，用它換算出的中位數價 870 元 vs 現價 229 元
  //   6223 旺矽 會得到 2024 整年的舊值（落後 6 季）
  // 這種數字看起來完全正常，卻會生出離譜的估值區間。寧可顯示「資料不足」。
  function epsTtmFromDetail(detail,nowMs){
    const qs=((detail&&detail.financials)||{}).quarters||[];
    if(qs.length<4)return null;
    const last4=qs.slice(-4);
    if(last4.some(x=>x.eps==null||!isFinite(x.eps)))return null;
    const idx=last4.map(x=>_qIndex(x.year,x.quarter));
    for(let i=1;i<4;i++)if(idx[i]!==idx[0]+i)return null;                // 不連續 → 不用
    if(idx[3]<_currentQIndex(nowMs)-VALUATION_EPS_MAX_LAG_Q)return null; // 過期 → 不用
    return {eps:last4.reduce((s,x)=>s+x.eps,0),
            label:last4[0].year+'Q'+last4[0].quarter+'~'+last4[3].year+'Q'+last4[3].quarter};
  }
  // 單一代號的本益比（含回退鏈），拿不到就回 null，不猜、不填 0
  function peValueFor(code,funds,detailStocks,quotes,nowMs){
    const r=((funds[code]||{}).ratios)||{};
    if(r.per!=null&&isFinite(r.per)&&r.per>0)return{pe:r.per,src:'twse',date:r.date||null};
    const t=epsTtmFromDetail(detailStocks[code],nowMs);
    const px=(quotes[code]||{}).close;
    if(t&&t.eps>0&&px!=null&&px>0)return{pe:px/t.eps,src:'derived',date:(quotes[code]||{}).date||null};
    return null;
  }
  // 線性內插百分位（等同 numpy.percentile 預設的 linear 法），輸入須已排序
  function percentileLinear(sortedVals,p){
    const n=sortedVals.length;
    if(!n)return null;
    if(n===1)return sortedVals[0];
    const i=(n-1)*p,lo=Math.floor(i),hi=Math.min(lo+1,n-1),f=i-lo;
    return sortedVals[lo]*(1-f)+sortedVals[hi]*f;
  }
  function _vbNum(v,d){return v==null||!isFinite(v)?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})}

  async function renderValuationBand(row){
    const host=document.getElementById('report-valuation-band');if(!host)return;
    const code=row.code;
    const disclaimer='<div class="note" style="margin-top:8px">這不是目標價、也不是投資建議：'
      +'台股沒有免費的分析師目標價／評等資料源，本卡只做機械換算——同產業本益比百分位 × 本檔近四季 EPS，'
      +'不含任何對未來獲利的預測。本益比偏低本身也可能反映風險或衰退。</div>';
    if(!/^\d{4,6}[A-Z]?$/.test(String(code))){
      host.innerHTML='<div class="note" data-ui-keep><b>只涵蓋台股</b></div><div class="note">估值區間目前只涵蓋台股（同產業本益比來自證交所每日本益比）。此代號非台股，無同產業本益比樣本可比。</div>';
      return;
    }
    const [,companies,quotes]=await Promise.all([loadFundamentals(code),loadCompanyInfo(),loadQuotesAllTw()]);
    const detailStocks=await loadStockDetailEps();
    const funds=(FUNDAMENTALS_CACHE&&FUNDAMENTALS_CACHE.fundamentals)||{};
    const industry=(companies[code]&&companies[code].industry)||row.industry||null;
    if(!industry){
      host.innerHTML='<div class="note" data-ui-keep><b>查不到這檔的產業分類</b></div><div class="note">查不到這檔的產業分類（data/company_info.json 無此代號），無法取同產業本益比樣本，因此不估算估值區間。</div>'+disclaimer;
      return;
    }
    if(VALUATION_EXCLUDED_INDUSTRY.test(industry)){
      host.innerHTML='<div class="note" data-ui-keep><b>本益比法不適用</b></div><div class="note">「'+industry+'」屬 ETF／受益證券／存託憑證類，沒有同產業本益比可比，本益比法不適用，因此不估算。</div>'+disclaimer;
      return;
    }
    // 同產業樣本
    const peers=Object.keys(companies).filter(c=>companies[c]&&companies[c].industry===industry);
    const vals=[];const srcCnt={twse:0,derived:0};const perDates=[];
    for(const c of peers){
      const v=peValueFor(c,funds,detailStocks,quotes,null);
      if(!v)continue;
      vals.push(v.pe);srcCnt[v.src]++;if(v.date)perDates.push(v.date);
    }
    vals.sort((a,b)=>a-b);
    const n=vals.length;
    const perDate=perDates.length?perDates.sort()[perDates.length-1]:null;
    // 本檔近四季 EPS（主：季報加總；備援：現價 ÷ 官方本益比 回推）
    const own=peValueFor(code,funds,detailStocks,quotes,null);
    const px=(quotes[code]&&quotes[code].close)!=null?quotes[code].close:null;
    const t=epsTtmFromDetail(detailStocks[code],null);
    let eps=null,epsSrc='',epsNote='';
    if(t){eps=t.eps;epsSrc='證交所季報加總';epsNote=t.label}
    else if(own&&own.src==='twse'&&px!=null&&px>0&&own.pe>0){
      eps=px/own.pe;epsSrc='由 TWSE 每日本益比與收盤價回推';epsNote='本益比 '+_vbNum(own.pe,2)+'、收盤 '+_vbNum(px,2);
    }
    const sampleLine='同產業「'+industry+'」有效樣本 <b>'+n+'</b> 檔'
      +(n?'（證交所每日本益比 '+srcCnt.twse+' 檔＋收盤價÷近四季EPS 推導 '+srcCnt.derived+' 檔）':'')
      +(perDate?'，本益比資料日 '+perDate:'')
      +'。同產業成分共 '+peers.length+' 檔，其餘因本益比為負或缺值而未納入。';
    // 不足以估算的三種情況：樣本不足、EPS 拿不到、EPS ≤ 0
    if(n<VALUATION_MIN_SAMPLE||eps==null||eps<=0){
      let why;
      if(eps==null)why='拿不到本檔近四季 EPS（季報四季不連續或已過期，且無官方本益比可回推）';
      else if(eps<=0)why='本檔近四季 EPS 為 '+_vbNum(eps,2)+' 元（≤0），本益比法不適用';
      else why='同產業有效樣本只有 '+n+' 檔，未達 '+VALUATION_MIN_SAMPLE+' 檔門檻';
      // 先.七十二-A2：結論短句常駐顯示，原因與樣本說明另一行（過長會收成「ⓘ 說明」）
      host.innerHTML='<div class="note" data-ui-keep><b>同產業樣本不足無法估算</b></div><div class="note">'+why+'。<br>'+sampleLine+'</div>'+disclaimer;
      return;
    }
    const p25=percentileLinear(vals,0.25),p50=percentileLinear(vals,0.5),p75=percentileLinear(vals,0.75);
    // 本檔目前落在同業第幾百分位（嚴格小於的比例）
    let rankPct=null;
    if(own&&own.pe>0&&n>1){let below=0;for(const v of vals)if(v<own.pe)below++;rankPct=Math.round(below/n*100)}
    const cells=[['25% 分位',p25],['中位數',p50],['75% 分位',p75]].map(function(a){
      const lbl=a[0],pe=a[1];
      return '<div style="flex:1;text-align:center;padding:8px 4px;border:1px solid var(--line);border-radius:10px">'
        +'<div style="font-size:10px;color:var(--ink-4)">'+lbl+'</div>'
        +'<div class="num" style="font-size:17px;font-weight:700;color:var(--ink-1);margin-top:2px">'+_vbNum(pe*eps,1)+'</div>'
        +'<div style="font-size:9.5px;color:var(--ink-4)">本益比 '+_vbNum(pe,1)+'</div></div>';
    }).join('');
    host.innerHTML='<div style="display:flex;gap:7px;margin-bottom:8px">'+cells+'</div>'
      +'<div class="note">現價 <b class="num">'+(px!=null?_vbNum(px,2):'—')+'</b>'
      +(own?'，本檔本益比 <b class="num">'+_vbNum(own.pe,2)+'</b>（'+(own.src==='twse'?'證交所每日本益比':'收盤價÷近四季EPS 推導')+'）'
            +(rankPct!=null?'，位於同業第 '+rankPct+' 百分位':''):'，本檔查無本益比')
      +'。<br>近四季 EPS <b class="num">'+_vbNum(eps,2)+'</b> 元（'+epsSrc+(epsNote?'，'+epsNote:'')+'）。<br>'+sampleLine+'</div>'
      // 先.七十二-A2：長說明會收成「ⓘ 說明」，產業樣本數另放一行短字常駐顯示
      +'<div class="note" data-ui-keep style="margin-top:4px">同產業樣本 <b>'+n+'</b> 檔</div>'
      +disclaimer;
  }
  async function renderReportEvents(row){
    const host=document.getElementById('report-events');if(!host)return;
    const d=await ensureEvents();
    const code=row.code;
    const mine=recentEventsFor(d,code,30);

    // 上方三個數字：月營收年增、法人連續天數——都取自已經算好的因子 raw，不重算
    const f=row.factors||{};
    const facts=[];
    const revYoy=f.revenue_momentum&&f.revenue_momentum.raw?f.revenue_momentum.raw.rev_yoy:null;
    if(revYoy!=null&&isFinite(revYoy))facts.push(['最新月營收年增',fmtPctCapped(revYoy,REVENUE_YOY_CAP)]);
    const an=f.analyst&&f.analyst.raw?f.analyst.raw:null;
    if(an){
      if(an.foreign_streak_days!=null)facts.push(['外資連續買賣',`${an.foreign_streak_days>0?'買超':'賣超'} ${Math.abs(an.foreign_streak_days)} 日`]);
      if(an.trust_streak_days!=null)facts.push(['投信連續買賣',`${an.trust_streak_days>0?'買超':'賣超'} ${Math.abs(an.trust_streak_days)} 日`]);
    }
    const factsHtml=facts.length
      ?'<div class="facts" style="margin-bottom:10px">'+facts.map(([k,v])=>`<div class="f"><span>${k}</span><b class="num">${v}</b></div>`).join('')+'</div>':'';

    if(!mine.length){
      host.innerHTML=factsHtml
        +'<div class="note">近 30 日無重大訊息／月營收／法說／除權息事件（已查 MOPS 上市與上櫃重大訊息、TWSE 月營收、除權息四類）。'
        +(d.fetched_at?`資料時間 ${fmtTzMMDDHHMM(new Date(d.fetched_at),'Asia/Taipei')}。`:'')
        +'</div>';
      return;
    }
    host.innerHTML=factsHtml
      +'<div style="display:flex;flex-direction:column;gap:9px">'+eventsRowsHtml(mine,12)+'</div>'
      +`<div class="note" style="margin-top:8px">近 30 日共 ${mine.length} 筆${mine.length>12?'，只顯示最近 12 筆':''}。資料來源：MOPS 重大訊息／TWSE 月營收／除權息，只存索引不存全文，點標題看原文。</div>`;
  }
