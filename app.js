// 常備.開發-20（2026-10-11）：由 index.html 的主 <script> 原封不動搬出（內容未改）。
// index.html 以一般（非 defer／非 async）<script src> 在 <body> 末端同一位置載入，執行時機與搬出前相同。
// 常備.開發-20 丙案（2026-10-11）：分頁專屬程式已拆到 app-market／picks／stock／trade／journal／settings（＋app-shared）.js，點到該頁才載入，見下方 loadAppModule。
  // 2026-08-27新增：全域錯誤收集，「修一樣壞一樣」的根治措施之一——任何漏接的
  // 錯誤最終都會被window.onerror/unhandledrejection攔到，不會完全消失在
  // console裡沒人看到。只留最近20筆，避免無限累積吃記憶體。
  let GLOBAL_ERRORS=[];

  // 先.九十六-R4（2026-10-14）：減少動態。app.css 的全域 prefers-reduced-motion 規則只管 CSS 動畫／轉場，
  // 管不到 JS 明確指定的 scrollIntoView 的平滑捲動選項，也不該在使用者要求減少動態時還加閃爍 class。
  // JS 端要捲動一律走 uiScrollIntoView()，要加動畫 class 前先問 uiReducedMotion()。
  function uiReducedMotion(){
    try{return !!(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)}
    catch(e){console.warn('[uiReducedMotion] 讀不到系統設定，視為未要求減少動態',e);return false}
  }
  function uiScrollIntoView(el,opt){
    if(!el)return;
    el.scrollIntoView(Object.assign({block:'start'},opt||{},{behavior:uiReducedMotion()?'auto':'smooth'}));
  }

  // ══════ 先.七十二-A1／A3（2026-10-11）：白話轉換表（前台唯一一份；對照 data/ui_glossary.json）══════
  // 資料檔裡帶來的文字（評分理由、錯誤訊息、伺服器回傳的原因）在顯示前一律經過 uiPlain()，把內部代號換成白話、
  // 拿掉端點名與檔案路徑。新增內部代號時同步改這裡與 data/ui_glossary.json。
  const UI_PLAIN_MAP=[
    [/來源\s*TWSE\s*官方財報\s*t187ap\S*/g,'來源：證交所財報'],
    [/\bt187ap\w*(\/\w+)*/g,''],[/\bmopsfin_\w+/g,''],[/\bBWIBBU_ALL\b/g,''],[/\btpex_\w+/g,''],
    [/\bT86\b/g,'法人統計'],[/\bMI_MARGN\b/g,'融資統計'],[/\bMI_QFIIS\b/g,'外資持股'],[/\bTWT\d+U\b/g,''],
    [/\bTWSE\b/g,'證交所'],[/\bTPEx\b/g,'櫃買中心'],[/\bTAIFEX\b/g,'期交所'],
    [/FinMind/gi,'公開資料'],[/Shioaji/gi,'永豐'],
    [/紙\.一b(\s*Bb-?90)?/g,'模擬 D'],[/紙上\s*4\s*R1-A/g,'模擬 C（並列版）'],[/紙上\s*4(\s*R1-C)?/g,'模擬 C'],[/紙上\s*3(\s*S3-C6)?/g,'模擬 B'],[/\bR1-A\b/g,'模擬 C（並列版）'],[/紙\.一(\s*70\/30)?/g,'模擬 A'],[/紙\.二/g,'模擬 E'],[/紙\.三(\s*S3-C6)?/g,'模擬 B'],[/紙\.四(\s*R1-C)?/g,'模擬 C'],
    [/真錢\s*Bb-?90/g,'自動投資'],[/Bb-?90/g,'自動投資'],
    [/\bS3-C6\b/g,'模擬 B'],[/\bR1-C\b/g,'模擬 C'],
    [/\bLIVE_WITH_VETO\b/g,'真錢（可取消）'],[/\bLIVE\b/g,'真錢'],[/\bSIMULATION\b/g,'模擬'],
    [/\bMDD\b/g,'最大跌幅'],[/唯讀/g,'只能看'],[/否決窗/g,'取消時間'],
    // 先.八十-6（2026-10-12）補：這次全檢漏抓的詞
    [/([+\-−]?\d+(?:\.\d+)?)\s*pp\b/g,'$1 個百分點'],[/\bpp\b/g,'個百分點'],[/同產業桶內|同桶內|桶內/g,'同產業中'],
    // 先.八十一-13：「全市場前 99%」反直覺（其實是倒數 1%），前段超過 50% 一律改說「最差 N%」
    [/(全市場|同產業中|同產業\(\d+檔\))\s*前\s*(\d+)\s*%/g,(m,a,x)=>(+x>50?`${a}最差 ${Math.max(1,100-(+x))}%`:m)],
    [/yfinance/gi,'Yahoo 財經'],[/\bNAV\b/g,'淨值'],[/BAA10Y/g,'信用利差'],[/Cloudflare\s*Access/g,'存取閘道'],
    [/\bXBRL\b/g,'結構化財報'],[/\bMI_INDEX\b/g,'大盤統計'],[/\bSTOCK_DAY\b/g,'日成交'],[/\bopenapi\b/gi,'開放資料'],[/SBL\//g,''],
    [/GitHub Actions\s*排程/g,'每日排程'],
    // 先.八十一-44：本日新增的資料來源說明含工程術語 repo／price_history，改白話（先具體、後通用）
    // 先.八十一-45：錯誤訊息／空狀態裡殘留的工程術語（commit、GitHub Actions、程式檔名）
    [/\s*commit\s*進\s*(?:repo|本站)/g,'存進本站'],[/最近一次\s*commit/g,'最近一次更新'],[/排程\s*commit\s*時/g,'排程更新時'],
    [/[（(]\s*GitHub Actions\s*[）)]/g,'（雲端排程）'],[/GitHub Actions/g,'雲端排程'],[/\bActions\s*排程/g,'雲端排程'],[/\bActions\s*最後一筆/g,'雲端排程最後一筆'],
    [/(?:(?:research|scripts)\/)?[\w./-]*?\b[\w-]+\.py\b/g,'程式'],
    [/repo\s*price_history/g,'本站每日收盤檔'],[/\brepo\s+[\w.-]+\.json\b/g,'本站資料檔'],[/\brepo\s*排程/g,'本站每日排程'],
    [/\brepo\s*檔/g,'本站資料檔'],[/\brepo\s*名單/g,'本站名單'],[/\brepo\b/g,'本站'],
    [/[（(]\s*#\d{3}(?:\s*[／/、,，]\s*#\d{3})*\s*[）)]/g,''],[/[，,、]?\s*#\d{3}\b/g,''],
    [/data\/[\w./-]+\.json/g,'資料檔'],[/research\/[\w./-]+\.py/g,'程式'],
    [/（\s*[／/、，]*\s*）/g,''],[/\(\s*\)/g,'']
  ];
  function uiPlain(s){
    try{let t=String(s==null?'':s);for(const [re,to] of UI_PLAIN_MAP)t=t.replace(re,to);return t.replace(/\s{2,}/g,' ').trim()}
    catch(e){console.warn('[uiPlain]',e);return String(s==null?'':s)}
  }

  // 先.六十九-1（2026-10-11）：同網域資料檔（data/*.json、scores*.json）60 秒記憶體快取。
  // 實測同一次開啟首頁 quotes_tw、margin_maintenance 各被不同面板抓了 2 次；這裡把同一路徑（忽略 ?t= 這類
  // 查詢字串）60 秒內的 GET 併成一次網路請求，各呼叫端拿到各自的 clone()。仍是網路優先：60 秒一到就重抓；
  // 指定 cache:'no-store'／'reload' 的呼叫（例如檢查新版、測試）照舊直通網路；失敗的回應不留。
  // 包裝本身出錯時直接退回原生 fetch（只 console.warn：這時 recordGlobalError 可能還沒定義，而且退回原生
  // fetch 後功能完全正常，不是使用者需要看到的錯誤）。
  (function(){
    const nativeFetch=window.fetch.bind(window),MEM=new Map(),TTL=60*1000;
    window.fetch=function(input,init){
      try{
        const req=typeof input==='string'||input instanceof URL?null:input;
        const method=String((init&&init.method)||(req&&req.method)||'GET').toUpperCase();
        const cacheMode=(init&&init.cache)||(req&&req.cache)||'';
        const u=new URL(req?req.url:String(input),location.href);
        // window.__ALPHA_FETCH_MEMCACHE_OFF：只給冒煙主頁面用（它會在同一頁內換假資料再重抓）；正式使用者不會有這個值
        if(!window.__ALPHA_FETCH_MEMCACHE_OFF&&method==='GET'&&cacheMode!=='no-store'&&cacheMode!=='reload'&&u.origin===location.origin&&
           /\.json$/.test(u.pathname)&&(/\/data\//.test(u.pathname)||/\/scores[^/]*\.json$/.test(u.pathname))){
          const key=u.pathname,hit=MEM.get(key);
          if(hit&&Date.now()-hit.at<TTL)return hit.p.then(r=>r.clone());
          const p=nativeFetch(input,init).then(r=>{if(!r.ok)MEM.delete(key);
            // 先.八十一-8：SW 先回上次存的資料時會帶 x-alpha-from-cache；記下來讓畫面標「上次資料」
            try{if(r.headers.get('x-alpha-from-cache')==='1'){const at=r.headers.get('x-alpha-cached-at')||'';
              const S=window.__ALPHA_STALE||(window.__ALPHA_STALE={n:0,at:''});S.n++;if(at&&(!S.at||at<S.at))S.at=at;
              window.dispatchEvent(new Event('alpha-stale-data'))}}catch(e2){console.warn('[fetchMemCache:stale]',e2)}
            return r});
          p.catch(()=>MEM.delete(key));
          MEM.set(key,{at:Date.now(),p});
          setTimeout(()=>{const h=MEM.get(key);if(h&&h.p===p)MEM.delete(key)},TTL+1000);
          return p.then(r=>r.clone());
        }
      }catch(e){console.warn('[fetchMemCache] 包裝失敗，改用原生 fetch',e)}
      return nativeFetch(input,init);
    };
    // 先.八十一-8：SW 背景抓到新版資料 → 清掉那條路徑的 60 秒記憶體快取，1.2 秒後把目前分頁重畫一次（多個檔案一起更新只重畫一次）
    window.__alphaMemDrop=k=>MEM.delete(k);
  })();
  let _uiDataRefreshT=null;
  try{
    if('serviceWorker' in navigator)navigator.serviceWorker.addEventListener('message',ev=>{
      try{
        const d=ev.data||{};if(d.type!=='DATA_UPDATED')return;
        window.__alphaMemDrop&&window.__alphaMemDrop(d.path);
        clearTimeout(_uiDataRefreshT);
        _uiDataRefreshT=setTimeout(()=>{window.__ALPHA_STALE=null;window.dispatchEvent(new Event('alpha-stale-data'));if(typeof uiRefreshCurrent==='function')uiRefreshCurrent()},1200);
      }catch(e){console.warn('[sw DATA_UPDATED]',e)}
    });
    // addEventListener 不會自動開始收訊息（要設 onmessage 或呼叫 startMessages），否則 DATA_UPDATED 會一直排隊收不到
    if('serviceWorker' in navigator&&navigator.serviceWorker.startMessages)navigator.serviceWorker.startMessages();
  }catch(e){console.warn('[sw message:setup]',e)}

  // ══════ 常備.開發-20 丙案（2026-10-11 先.六十五）：分頁程式延遲載入 ══════
  // app.js 只留首頁＋導覽＋共用；其餘分頁程式拆到 app-<頁>.js，點到該頁才載入（不引入建置步驟，
  // 檔案內容是由原 app.js 依頂層宣告原封不動搬出，未改寫任何函式本體）。
  // 機制：下面每個「轉接殼」函式與分頁檔裡的真函式同名；第一次被呼叫時先載入該分頁檔（真函式
  // 會覆蓋同名的全域函式），再轉呼叫真函式。載入失敗只讓那一次呼叫 reject（由呼叫端的
  // _safeAsync／_safeSync 記進錯誤 log），不影響其他面板。
  // 維護規則：app.js（或別的分頁檔）要呼叫某分頁檔裡的函式，必須在下方轉接殼清單加一行同名轉接殼；
  // 分頁檔裡不得宣告與 app.js 同名的 let／const（會讓整個分頁檔語法錯誤載入失敗）。冒煙 #53／#85 會擋明顯漏接。
  const LAZY_MOD_DEPS={market:['shared'],picks:['shared'],stock:['shared'],trade:['shared'],journal:['shared'],settings:['shared']};
  const LAZY_MOD_PROMISES={};
  function loadAppModule(mod){
    if(LAZY_MOD_PROMISES[mod])return LAZY_MOD_PROMISES[mod];
    const p=Promise.all((LAZY_MOD_DEPS[mod]||[]).map(loadAppModule)).then(()=>new Promise((res,rej)=>{
      const s=document.createElement('script');
      s.src='app-'+mod+'.js?v='+encodeURIComponent(APP_VERSION);
      s.onload=()=>res();
      s.onerror=()=>rej(new Error('分頁程式 app-'+mod+'.js 載入失敗（離線或網路中斷？）'));
      document.head.appendChild(s);
    }));
    LAZY_MOD_PROMISES[mod]=p;
    p.catch(e=>{delete LAZY_MOD_PROMISES[mod];console.warn('[loadAppModule:'+mod+']',e);recordGlobalError('loadAppModule:'+mod,e)});  // 失敗清掉，下次可重試
    return p;
  }
  // 常備.開發-20（先.六十七）：首頁不再抓完整股票名稱清單（見 loadStockInfo 註解），改在第一次切到其他分頁時抓；
  // 最多等 2.5 秒就先畫（逾時或失敗不擋分頁，名稱清單載好後下一次重繪就會補上）。
  function _namesForPage(){
    if(infoLoaded)return Promise.resolve();
    const p=Promise.resolve().then(()=>loadStockInfo()).catch(e=>{console.warn('[_namesForPage]',e);recordGlobalError('_namesForPage',e)});
    return Promise.race([p,new Promise(r=>setTimeout(r,2500))]);
  }
  // 先.八十一-9：個股頁／選股頁不需要整份名稱清單（個股名稱由 quote_lite／by_code 小檔補、選股列自帶名稱），
  // 不再為這兩頁下載約 490KB 的 FinMind TaiwanStockInfo；搜尋與其他分頁照舊。
  const _NO_NAMES_MODS={stock:1,picks:1};
  function _lazyCall(mod,name,args){
    return Promise.all([loadAppModule(mod),_NO_NAMES_MODS[mod]?null:_namesForPage()]).then(()=>{
      const f=window[name];
      if(typeof f!=='function'||f._lazyStub)throw new Error('分頁程式 app-'+mod+'.js 已載入但找不到 '+name);
      return f.apply(window,args);
    });
  }
  function openSectorList(...a){return _lazyCall('market','openSectorList',a)}
  function loadMarketIndex(...a){return _lazyCall('market','loadMarketIndex',a)}
  function loadHeatmap(...a){return _lazyCall('market','loadHeatmap',a)}
  function loadChipsMarketDetail(...a){return _lazyCall('market','loadChipsMarketDetail',a)}
  function renderJournalChips(...a){return _lazyCall('journal','renderJournalChips',a)}
  function loadWeeklyBrief(...a){return _lazyCall('journal','loadWeeklyBrief',a)}
  function loadJournalLedger(...a){return _lazyCall('journal','loadJournalLedger',a)}
  function loadSysWeekly(...a){return _lazyCall('journal','loadSysWeekly',a)}
  function loadResearchScorecard(...a){return _lazyCall('journal','loadResearchScorecard',a)}
  function onTradeInit(...a){return _lazyCall('trade','onTradeInit',a)}
  function loadMarketUS(...a){return _lazyCall('market','loadMarketUS',a)}
  function loadMarketFUT(...a){return _lazyCall('market','loadMarketFUT',a)}
  function loadScanners(...a){return _lazyCall('market','loadScanners',a)}
  function hydrateMarket(...a){return _lazyCall('market','hydrateMarket',a)}
  function openStock(...a){return _lazyCall('stock','openStock',a)}
  function openStrategyReport(...a){return _lazyCall('trade','openStrategyReport',a)}
  function hydratePicks(...a){return _lazyCall('picks','hydratePicks',a)}
  function renderReport(...a){return _lazyCall('picks','renderReport',a)}
  function hydrateSettings(...a){return _lazyCall('settings','hydrateSettings',a)}
  function liveUpdateStockPage(...a){return _lazyCall('stock','liveUpdateStockPage',a)}
  [openSectorList,loadMarketIndex,loadHeatmap,loadChipsMarketDetail,renderJournalChips,loadWeeklyBrief,loadJournalLedger,loadSysWeekly,loadResearchScorecard,onTradeInit,loadMarketUS,loadMarketFUT,loadScanners,hydrateMarket,openStock,openStrategyReport,hydratePicks,renderReport,hydrateSettings,liveUpdateStockPage].forEach(f=>{f._lazyStub=true});
  // 先.八十-2（2026-10-12）：電腦離線統一狀態。本機伺服器連不上（Failed to fetch／Load failed／逾時中止）是常態，
  // 不是程式錯誤：不進錯誤 log、不顯示英文原始訊息，相關卡片只留一行「電腦離線（最後連線 MM/DD HH:MM）」。
  // 最後連線時間＝liveFetch／串流最後一次拿到回應的時間（存本機 localStorage，只是時間戳）。
  const LIVE_LASTOK_KEY='alpha_live_last_ok';
  function _isOfflineErr(e){
    if(!e)return false;
    if(e.offline)return true;
    const t=String((e.name||'')+' '+(e.message||e));
    return /Failed to fetch|Load failed|NetworkError|network connection was lost|AbortError|signal is aborted|The user aborted|電腦離線/i.test(t);
  }
  function _liveMarkOk(){try{localStorage.setItem(LIVE_LASTOK_KEY,new Date().toISOString())}catch(e){console.warn('[liveMarkOk]',e)}}
  function liveOfflineText(){
    let at=null;try{at=localStorage.getItem(LIVE_LASTOK_KEY)}catch(e){console.warn('[liveOfflineText]',e)}
    const d=at?new Date(at):null;
    if(!d||isNaN(d))return '電腦離線（還沒連上過）';
    const p=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(d);
    const g=k=>(p.find(x=>x.type===k)||{}).value||'';
    return '電腦離線（最後連線 '+g('month')+'/'+g('day')+' '+g('hour')+':'+g('minute')+'）';
  }
  function _offlineErr(cause){const x=new Error('電腦離線');x.offline=true;x.cause=cause;return x}
  function recordGlobalError(label,err){
    if(_isOfflineErr(err)){console.info('[離線，不計程式錯誤]',label);return}
    const msg=(err&&err.message)?err.message:String(err);
    GLOBAL_ERRORS.push({label,msg,time:fmtTzHHMM(new Date(),'Asia/Taipei')});
    if(GLOBAL_ERRORS.length>20)GLOBAL_ERRORS.shift();
    try{_errReportEnqueue(label,msg)}catch(e2){console.warn('[recordGlobalError] 錯誤回報排隊失敗',e2)}
    renderErrorLog();
  }
  // 常備.開發-29（2026-10-11）：App 錯誤回報。每筆錯誤先去識別化、排進 localStorage（上限 100 筆，離線也不遺失），
  // 每 60 秒／切到背景時 POST 到本機伺服器 /errors（token 必檢，伺服器端會再去識別化一次並做每日彙總）。
  // 只送 label／msg／ts／ver，不送網址、UA、自選股。送出失敗刻意不呼叫 recordGlobalError——
  // 否則「回報失敗」本身又會排進回報佇列，離線時無限自我餵食；只 console.warn，佇列留著下次再送。
  const ERR_Q_KEY='alpha_err_report_q',ERR_Q_MAX=100;
  function _errScrub(t,n){
    return String(t==null?'':t).replace(/https?:\/\/\S+/gi,'<url>').replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g,'<email>')
      .replace(/\b[A-Za-z0-9_\-]{24,}\b/g,'<token>').replace(/\d{7,}/g,'<num>').replace(/\s+/g,' ').trim().slice(0,n);
  }
  function _errQRead(){try{const q=JSON.parse(localStorage.getItem(ERR_Q_KEY)||'[]');return Array.isArray(q)?q:[]}catch(e){console.warn('[errQRead]',e);return[]}}
  function _errQWrite(q){try{localStorage.setItem(ERR_Q_KEY,JSON.stringify(q.slice(-ERR_Q_MAX)))}catch(e){console.warn('[errQWrite]',e)}}
  function _errReportEnqueue(label,msg){
    const q=_errQRead();q.push({label:_errScrub(label,80),msg:_errScrub(msg,200),ts:new Date().toISOString()});_errQWrite(q);
  }
  let _errFlushing=false;
  async function flushErrorReports(){
    if(_errFlushing||typeof LIVE==='undefined'||!LIVE.configured||!LIVE.url||!LIVE.token)return;
    const q=_errQRead();if(!q.length)return;
    _errFlushing=true;
    const batch=q.slice(0,50);
    try{
      const ver=((document.getElementById('about-app-ver')||{}).textContent||'').trim();
      const r=await fetch(LIVE.url+'/errors',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),
        body:JSON.stringify({errors:batch,ver}),credentials:'include',cache:'no-store'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      _errQWrite(_errQRead().slice(batch.length));  // 只移除已送出的那批，送出期間新進的保留
    }catch(e){console.warn('[flushErrorReports] 送出失敗，下次再送（刻意不記 recordGlobalError，見上方註解）',e)}
    finally{_errFlushing=false}
  }
  setInterval(()=>{flushErrorReports().catch(e=>console.warn('[flushErrorReports]',e))},60*1000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flushErrorReports().catch(e=>console.warn('[flushErrorReports]',e))});
  // 2026-09-06（實測.五）一行摘要：幾筆、幾種、最近一筆是什麼。
  // 同一個錯誤常常連續發生好幾十次（例如某個渲染每次進頁面都拋），只講「有錯誤」
  // 沒有資訊量，講「12 筆、2 種、最近：renderReport 讀取 null 的 toFixed」才有。
  function errorLogSummary(){
    if(!GLOBAL_ERRORS.length)return '';
    const kinds=new Set(GLOBAL_ERRORS.map(x=>x.label+'|'+x.msg));
    const last=GLOBAL_ERRORS[GLOBAL_ERRORS.length-1];
    const msg=last.msg.length>52?last.msg.slice(0,52)+'…':last.msg;
    return `⚠ 偵測到程式錯誤 ${GLOBAL_ERRORS.length} 筆／${kinds.size} 種　最近：${last.label} — ${msg}`;
  }
  // 複製給 Cowork 用的完整內容。除了錯誤本身，把版本、時間、裝置、螢幕、連線狀態
  // 一起帶上——沒有這些，收到的人第一句一定是「你的版本是哪個」。
  function errorLogDetailText(){
    const ver=(document.getElementById('about-app-ver')||{}).textContent||'?';
    const lines=[
      'Alpha 錯誤詳情',
      '時間：'+new Date().toISOString(),
      'App 版本：'+ver,
      '網址：'+location.href,
      'UA：'+navigator.userAgent,
      '螢幕：'+window.innerWidth+'x'+window.innerHeight+' dpr='+(window.devicePixelRatio||1),
      '即時源：'+(LIVE.connected?('連線中 '+(LIVE.sourceMode||'')):(LIVE.configured?('已設定但離線'+(LIVE.lastError?'：'+LIVE.lastError:'')):'未設定')),
      '自選股：'+WL.length+' 檔',
      '',
      '錯誤 '+GLOBAL_ERRORS.length+' 筆（新到舊）：',
    ];
    GLOBAL_ERRORS.slice().reverse().forEach((x,i)=>lines.push(`${i+1}. [${x.time}] ${x.label}: ${x.msg}`));
    return lines.join('\n');
  }
  async function copyErrorLog(){
    const text=errorLogDetailText();
    try{
      await navigator.clipboard.writeText(text);
      toast('錯誤詳情已複製，可以直接貼給 Cowork');
    }catch(e){
      // iOS Safari 在非使用者手勢或非安全來源下會拒絕 clipboard API。
      // 退回「選取整段文字」，使用者長按就能複製，不是把失敗吞掉。
      console.warn('[copyErrorLog]',e);
      const listEl=document.getElementById('error-log-list');
      if(listEl){
        const r=document.createRange();r.selectNodeContents(listEl);
        const sel=window.getSelection();sel.removeAllRanges();sel.addRange(r);
        toast('這個瀏覽器擋了自動複製，已為你選取，長按選「複製」');
      }else{toast('複製失敗：'+(e.message||e))}
    }
  }
  function renderErrorLog(){
    const el=document.getElementById('error-log'),listEl=document.getElementById('error-log-list');
    const sumEl=document.getElementById('error-log-summary');
    if(!el||!listEl)return;
    if(!GLOBAL_ERRORS.length){el.style.display='none';return}
    el.style.display='';
    if(sumEl)sumEl.textContent=errorLogSummary();
    listEl.textContent=errorLogDetailText();
    const btn=document.getElementById('error-log-copy');
    if(btn&&!btn._wired){btn._wired=true;btn.onclick=(ev)=>{ev.preventDefault();ev.stopPropagation();_safeAsync('copyErrorLog',copyErrorLog)}}
  }
  window.addEventListener('error',e=>{recordGlobalError('window.onerror',e.error||e.message||e)});
  window.addEventListener('unhandledrejection',e=>{recordGlobalError('unhandledrejection',e.reason)});

  // ── 導覽 ──
  const scrs = {home:'scr-home',market:'scr-market','chips-market':'scr-chips-market',picks:'scr-picks',report:'scr-report',trade:'scr-trade',journal:'scr-journal',stock:'scr-stock',settings:'scr-settings'};
  // 2026-08-27新增（使用者定位的「改A壞B」根因之一）：任一分頁的載入/渲染函式
  // 失敗，不能連累其他分頁或導覽本身——sync函式包try/catch，async函式的promise
  // 要接.catch()（try/catch接不住async函式await之後才發生的rejection）。錯誤
  // 一律記進 recordGlobalError()，讓診斷橫幅看得到，不是單純console.warn完就消失。
  // 2026-09-06（實測.五）_safeSync 補上 async 保護。
  // 根因證據：用修正前的版本重現總司令的操作（連開 12 檔選股報告頁），
  // GLOBAL_ERRORS 出現 8 筆 `unhandledrejection: Cannot read properties of null
  // (reading 'toFixed')`——那正是 6442 的 peg=null。它之所以逃出 _safeSync，是因為
  // `go()` 用 `_safeSync('renderReport', renderReport)` 呼叫一個 **async** 函式：
  // async 函式的錯誤是 rejected promise，不是同步 throw，try/catch 接不到，於是
  // 冒到 window 的 unhandledrejection，變成使用者看到的那條橫幅。
  // 這裡改成「回傳值是 thenable 就順手 .catch()」，同一個標籤同時保護兩種函式，
  // 呼叫端不用再去記哪一個是 async（記錯就是下一次同樣的橫幅）。
  function _safeSync(label,fn){
    try{
      const r=fn();
      if(r&&typeof r.then==='function')r.catch(e=>{console.warn('['+label+']',e);recordGlobalError(label,e)});
      return r;
    }catch(e){console.warn('['+label+']',e);recordGlobalError(label,e)}
  }
  function _safeAsync(label,fn){Promise.resolve().then(fn).catch(e=>{console.warn('['+label+']',e);recordGlobalError(label,e)})}
  let CURRENT_TAB='home'; // 2026-08-28新增，供pull-to-refresh判斷目前在哪一頁該重整什麼
  // 先.八十一-8：背景更新後重畫目前分頁（同 go() 的載入動作，但不捲回頂端、不切分頁）
  function uiRefreshCurrent(){
    const name=CURRENT_TAB;
    if(name==='home')_safeAsync('hydrateHome',hydrateHome);
    else if(name==='market')_safeAsync('hydrateMarket',hydrateMarket);
    else if(name==='picks')_safeAsync('hydratePicks',hydratePicks);
    else if(name==='trade')_safeSync('onTradeInit',onTradeInit);
    else if(name==='settings')_safeSync('hydrateSettings',hydrateSettings);
  }
  // 「上次資料」提示：任何資料是 SW 先回的舊存檔時，首頁狀態列下方顯示一行（含存檔時間）；背景更新完成後自動收起
  function uiRenderStaleLine(){
    try{
      const strip=document.getElementById('home-status-strip');if(!strip)return;
      let el=document.getElementById('data-stale-line');
      if(!el){el=document.createElement('div');el.id='data-stale-line';el.className='note';el.setAttribute('data-ui-keep','');el.style.cssText='margin:4px 2px 0;font-size:11px;color:var(--ink-3)';strip.insertAdjacentElement('afterend',el)}
      const S=window.__ALPHA_STALE;
      if(!S||!S.n){el.hidden=true;return}
      const t=S.at?new Date(S.at):null;
      el.hidden=false;
      el.textContent='先顯示上次存的資料'+(t&&!isNaN(t)?'（'+fmtTzMMDDHHMM(t,'Asia/Taipei')+' 存）':'')+'，背景更新中；各卡片日期以卡上標示為準';
    }catch(e){console.warn('[uiRenderStaleLine]',e)}
  }
  window.addEventListener('alpha-stale-data',()=>uiRenderStaleLine());
  function go(name){
    CURRENT_TAB=name;
    document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
    document.getElementById(scrs[name]).classList.add('active');
    document.querySelectorAll('#nav button[data-scr]').forEach(b=>b.classList.toggle('on', b.dataset.scr===name));
    document.getElementById('main').scrollTo(0,0);
    if(name==='home')_safeAsync('hydrateHome',hydrateHome);
    if(name==='market')_safeAsync('hydrateMarket',hydrateMarket);
    if(name==='chips-market')_safeAsync('loadChipsMarketDetail',loadChipsMarketDetail);
    if(name==='picks')_safeAsync('hydratePicks',hydratePicks);
    if(name==='trade')_safeSync('onTradeInit',onTradeInit);
    if(name==='journal'){_safeSync('renderJournalChips',renderJournalChips);_safeAsync('loadWeeklyBrief',loadWeeklyBrief);_safeAsync('loadSysWeekly',loadSysWeekly);_safeAsync('loadJournalLedger',loadJournalLedger);_safeAsync('loadResearchScorecard',loadResearchScorecard)}
    if(name==='report')_safeSync('renderReport',renderReport);
    if(name==='settings')_safeSync('hydrateSettings',hydrateSettings);
  }
  document.querySelectorAll('#nav button[data-scr]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.scr)));

  // ══════ 右上角台美股即時時鐘（2026-08-24 新增）══════
  // 用 Intl.DateTimeFormat 的 timeZone 選項取得指定時區的當地時間，
  // 美東時間的夏令/冬令切換由瀏覽器內建時區資料庫自動處理，不用自己算 DST 規則。
  function zonedNow(tz){
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:tz,hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',weekday:'short'}).formatToParts(new Date());
    const m={};parts.forEach(p=>m[p.type]=p.value);
    const wd={Sun:0,Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6}[m.weekday];
    const h=+m.hour,mi=+m.minute,s=+m.second;
    return {h,mi,s,wd,hhmmss:`${m.hour}:${m.minute}:${m.second}`};
  }
  // 2026-08-28修正（P0-a，第6次時鐘問題，使用者裝置實測回報「會動但數值
  // 錯」）：根因不是setInterval沒註冊到（那是前5次「完全停擺」的bug，已經
  // 修好），這次是好幾個「顯示某個時間戳」的地方（市場資料時間/最後更新/
  // 錯誤log時間）用了Date.prototype.getHours()/getMinutes()/getMonth()/
  // getDate()或toLocaleTimeString()/toLocaleString()都沒指定timeZone
  // 參數——這些method不指定timeZone時，一律用「執行環境（使用者瀏覽器/
  // 裝置系統）」當下的本地時區去換算，不是強制轉換成台北或紐約時間。如果
  // 使用者手機系統時區不是Asia/Taipei（出國、系統時區被覆寫等情況），
  // 畫面顯示的時間就會偏移，但setInterval本身仍正常在跑（時鐘「看起來
  // 有在動」，只是換算出來的數值不對）。修法：全部改用跟zonedNow()同一套
  // Intl.DateTimeFormat+明確timeZone機制，不使用Date物件的本地時區
  // getter，也不手寫+8/-12/-13這種固定時差常數（會忽略夏令時間，紐約
  // 一年裡有大半時間是UTC-4不是UTC-5）。
  function fmtTzHHMM(dateInput,tz){
    const d=(dateInput instanceof Date)?dateInput:new Date(dateInput);
    if(isNaN(d.getTime()))return '--:--';
    return new Intl.DateTimeFormat('en-US',{timeZone:tz,hour12:false,hour:'2-digit',minute:'2-digit'}).format(d);
  }
  function fmtTzMMDDHHMM(dateInput,tz){
    const d=(dateInput instanceof Date)?dateInput:new Date(dateInput);
    if(isNaN(d.getTime()))return '--/-- --:--';
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:tz,hour12:false,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).formatToParts(d);
    const m={};parts.forEach(p=>m[p.type]=p.value);
    return `${m.month}/${m.day} ${m.hour}:${m.minute}`;
  }
  function fmtTzMD(dateInput,tz){
    const d=(dateInput instanceof Date)?dateInput:new Date(dateInput);
    if(isNaN(d.getTime()))return '--/--';
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:tz,month:'2-digit',day:'2-digit'}).formatToParts(d);
    const m={};parts.forEach(p=>m[p.type]=p.value);
    return `${+m.month}/${+m.day}`;
  }
  // 2026-08-25 新增：盤中近即時報價（GitHub Actions 排程抓，見 .github/workflows/quotes.yml）。
  // FinMind 免費版只有盤後日線，畫面顯示「盤中」卻只能給前一日收盤價會誤導使用者。
  let INTRADAY_TW=null,INTRADAY_US=null,INTRADAY_IBKR=null,INTRADAY_SINOPAC=null;
  // 先.九十五-R1②：即時檔抓取是不是因為「連不上網路」失敗（頂端市場時鐘據此寫「離線」而不是「無資料」）
  const INTRADAY_NET_OFF={tw:false,us:false};
  function intradayAgeMin(data){
    if(!data||!data.fetched_at)return null;
    return (Date.now()-new Date(data.fetched_at).getTime())/60000;
  }
  // 2026-09-03新增（P0根因修復）：判斷一個ISO時間戳是否落在指定時區的
  // 「今天」——用來讓收盤後的sinopacQuote()/ibkrQuote()知道「這筆資料雖然
  // 已經超過20分鐘沒更新，但確實是今天收盤時記錄的，不是隔夜留下的舊值」，
  // 用en-CA locale（輸出YYYY-MM-DD）方便直接字串比較，不用手動組日期。
  // 2026-10-08 先.五十一：Shioaji 的 tick_at／sim_at 是不帶時區的台北時間字串，new Date() 會照裝置時區解析，
  // 這裡直接比日期字串；帶時區的字串退回 _isSameLocalDate。
  function _isTaipeiToday(iso){
    if(!iso)return false;const t=String(iso);
    if(/[zZ]|[+-]\d\d:?\d\d$/.test(t))return _isSameLocalDate(t,'Asia/Taipei');
    return t.slice(0,10)===new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  }
  function _isSameLocalDate(iso,tz){
    if(!iso)return false;
    const d=new Date(iso);
    if(isNaN(d.getTime()))return false;
    const fmt=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'});
    return fmt.format(d)===fmt.format(new Date());
  }
  // 2026-09-03新增：判斷「這份INTRADAY_*資料現在應不應該當作盤中即時
  // 串流看待」——**優先信任後端自己回報的`market_status`欄位**（
  // shioaji_quotes.py會誠實寫"open"/"closed"，這是最準確的第一手signal，
  // 完全對應使用者P0裁示原文「當報價檔market_status為closed...」）；只有
  // 在這個欄位不存在時（目前ibkr_quotes.py還沒有這個欄位，見PENDING_QUEUE
  // P0三-一.3待查）才退回用前端算的交易時段當估計值，不是無條件都用前端
  // 時鐘猜。
  function _shouldTreatAsLive(data,fallbackInWindow){
    if(data&&typeof data.market_status==='string')return data.market_status==='open';
    return fallbackInWindow;
  }
  // 統一判斷「這份INTRADAY_*資料現在能不能拿來當現價顯示」，取代原本
  // 市場頁大盤指數/期貨卡各自重複一份幾乎一樣的connected&&age<=STALE_MIN
  // 檢查——每一處都有同一個bug（收盤後20分鐘閘門把今天的收盤價誤判成
  // 過期，退回顯示別的資料源的prev_close/EOD，見sinopacQuote()/
  // ibkrQuote()同一輪P0修復的完整根因說明）。盤中沿用原本的新鮮度閘門
  // （偵測即時流是否卡住失效）；收盤後只要資料確實是今天的就一律接受，
  // 標記isTodayClose讓呼叫端知道要顯示「今日收盤」而不是「即時」。
  function _intradaySourceFresh(data,tz,fallbackInWindow){
    if(!data)return {fresh:false,isTodayClose:false};
    if(_shouldTreatAsLive(data,fallbackInWindow)){
      const age=intradayAgeMin(data);
      return {fresh:!!data.connected&&age!=null&&age<=INTRADAY_STALE_MIN,isTodayClose:false};
    }
    const dataIsToday=_isSameLocalDate(data.fetched_at,tz);
    return {fresh:dataIsToday,isTodayClose:dataIsToday};
  }
  // 2026-09-01新增，同日改版：IBKR本機Gateway報價（research/ibkr_quotes.py，
  // 本機排程觸發，不經過GitHub Actions——見該檔案docstring「掛排程」）。
  // **只接美股**（台股維持現有TWSE來源，IBKR對台股只有延遲、沒有增益，
  // 改版原因見ibkr_quotes.py docstring開頭）：DEFAULT_US_WATCHLIST那5檔
  // 美股+四大美股指數。實測這個paper帳戶對這些美股標的也是DELAYED不是
  // REALTIME（IBKR帳戶市場數據訂閱層級限制，誠實顯示標籤，不假裝即時）。
  // 只覆蓋這9個標的（IBKR腳本的既知限制，見ibkr_quotes.py docstring
  // 「已知限制」：沒辦法讀瀏覽器localStorage的真實自選股清單），其餘股票
  // 照舊完全不受影響。
  // 2026-09-03修正（P0根因，使用者實測回報：收盤後今天的收盤tick被20分鐘
  // 閘門誤丟成過期，畫面退回EOD/prev_close，看起來像整個管線沒更新——真正
  // 根因不是接錯欄位，是這個閘門不分盤中/盤後一律套用）：**20分鐘新鮮度
  // 閘門只在「現在應該是盤中」時生效**，用來偵測「即時串流卡住/掛掉」；
  // 一旦已經過了收盤時間，只要這筆資料的`fetched_at`確實是「今天」記錄的
  // （不是隔夜/更早留下的），就一律接受當作「今日收盤」顯示，不管距離
  // 現在已經過了幾小時——這才是使用者想看到的「收盤後這支股票收在多少」，
  // 不是被閘門擋掉退回另一條資料源的prev_close/EOD值。回傳物件新增
  // `isTodayClose`旗標，供`intradayTag()`判斷要顯示「今日收盤」而非
  // 「即時(tick)」或「延遲N分」。
  function ibkrQuote(code){
    if(!INTRADAY_IBKR)return null;
    const age=intradayAgeMin(INTRADAY_IBKR);
    const live=_shouldTreatAsLive(INTRADAY_IBKR,isUsTradingWindowNow());
    const dataIsToday=_isSameLocalDate(INTRADAY_IBKR.fetched_at,'America/New_York');
    if(live){
      if(!INTRADAY_IBKR.connected)return null;
      if(age==null||age>INTRADAY_STALE_MIN)return null;
    }else if(!dataIsToday){
      return null; // 真的是隔夜留下的舊資料，誠實退回EOD，不是bug
    }
    const q=INTRADAY_IBKR.quotes&&INTRADAY_IBKR.quotes[code];
    if(!q||q.last==null)return null;
    return {
      price:q.last, prev_close:q.close,
      change:(q.close!=null?q.last-q.close:null), change_pct:q.change_pct,
      ageMin:age, source:'ibkr', dataType:q.data_type,
      isTodayClose:!live&&dataIsToday,
    };
  }
  // 2026-09-01新增：Shioaji本機報價（research/shioaji_quotes.py），跟
  // ibkrQuote()同一套邏輯，鏡射過來只是資料源換成台股券商。分工鐵律：
  // 台股一律走這裡，美股一律走ibkrQuote()，兩者不重疊（見shioaji_quotes.py
  // /ibkr_quotes.py各自docstring）。
  function sinopacQuote(code){
    if(!INTRADAY_SINOPAC)return null;
    const age=intradayAgeMin(INTRADAY_SINOPAC);
    const live=_shouldTreatAsLive(INTRADAY_SINOPAC,isTwTradingWindowNow());
    const dataIsToday=_isSameLocalDate(INTRADAY_SINOPAC.fetched_at,'Asia/Taipei');
    if(live){
      if(!INTRADAY_SINOPAC.connected)return null;
      if(age==null||age>INTRADAY_STALE_MIN)return null;
    }else if(!dataIsToday){
      return null; // 真的是隔夜留下的舊資料，誠實退回EOD，不是bug
    }
    const q=INTRADAY_SINOPAC.quotes&&INTRADAY_SINOPAC.quotes[code];
    if(!q||q.last==null)return null;
    return {
      price:q.last, prev_close:q.close,
      change:(q.close!=null?q.last-q.close:null), change_pct:q.change_pct,
      ageMin:age, source:'sinopac', dataType:q.data_type,
      isTodayClose:!live&&dataIsToday,
    };
  }
  // 2026-10-08 先.五十一-1：試撮價（shioaji_quotes.py 把 tick.simtrade 寫進 sim_price／sim_at，
  // 不動 last）。只在 08:30–09:00、13:25–13:30（台北）且 sim_at 是今天時回傳「試撮 xxx」，其餘回空字串。
  function simTradeText(code){
    try{
      const q=INTRADAY_SINOPAC&&INTRADAY_SINOPAC.quotes&&INTRADAY_SINOPAC.quotes[code];
      if(!q||q.sim_price==null||!q.sim_at)return '';
      const z=zonedNow('Asia/Taipei');const m=z.h*60+z.mi;
      const inWin=z.wd>=1&&z.wd<=5&&((m>=8*60+30&&m<9*60)||(m>=13*60+25&&m<13*60+30));
      if(!inWin||!_isTaipeiToday(q.sim_at))return '';
      return '試撮 '+nf(q.sim_price);
    }catch(e){console.warn('[simTradeText]',e);recordGlobalError('simTradeText',e);return ''}
  }
  // ── 2026-09-06（實測.三）漲跌停 ────────────────────────────────────────────
  // 兩個來源，優先用官方值：
  //  1. Shioaji 合約的 limit_up / limit_down（由 live server 的 /live/quotes 帶進來）
  //  2. 沒有即時源時用「前收 × 1.1 / 0.9，依 TWSE 檔位規則取整」
  //
  // **回退公式的適用範圍是實測釘死的，不是假設**：拿 Shioaji 合約快取（2026-09-04、
  // 3154 檔）逐檔對過，結論是
  //   - TSE + OTC 的 4 位數普通股 1976 檔：公式與官方值 **100% 吻合、0 檔不符**
  //   - 興櫃（OES）363 檔全部不符——興櫃漲跌幅是 ±20% 不是 ±10%
  //   - ETF/ETN（00 開頭）用不同的檔位表，且其中 98 檔（元大寶滬深這類境外連結）
  //     根本沒有漲跌幅限制（limit_up 是 9999.95）
  // 所以公式只用在「在官方在市名冊內的 4 位數非 00 開頭代號」，其他一律不亮燈，
  // 寧可不顯示也不要標一個錯的漲停價。
  const TWSE_TICKS=[[10,0.01],[50,0.05],[100,0.1],[500,0.5],[1000,1],[Infinity,5]];
  function twseTick(p){for(const [hi,t] of TWSE_TICKS)if(p<hi)return t;return 5}
  function limitPrices(code,prevClose,liveQuote){
    if(liveQuote&&liveQuote.limit_up!=null&&liveQuote.limit_down!=null)
      return {up:+liveQuote.limit_up,down:+liveQuote.limit_down,src:'合約'};
    if(prevClose==null||!isFinite(prevClose)||prevClose<=0)return null;
    if(isUS(code))return null;                       // 美股沒有漲跌幅限制
    if(!/^\d{4}$/.test(code)||code.startsWith('00'))return null;  // ETF/ETN 檔位表不同
    if(!isListedNow(code))return null;               // 不在上市櫃名冊（興櫃 ±20%、已下市）
    const ru=prevClose*1.1,rd=prevClose*0.9;
    const tu=twseTick(ru),td=twseTick(rd);
    return {up:+(Math.floor(+(ru/tu).toFixed(6))*tu).toFixed(2),
            down:+(Math.ceil(+(rd/td).toFixed(6))*td).toFixed(2),src:'前收推算'};
  }
  // 回傳 'up' / 'down' / null。用 0.001 的容差比對，避免浮點數讓「剛好漲停」比不出來。
  function limitState(price,lim){
    if(!lim||price==null||!isFinite(price))return null;
    if(Math.abs(price-lim.up)<0.001)return 'up';
    if(Math.abs(price-lim.down)<0.001)return 'down';
    return null;
  }
  function limitBadge(state){
    if(!state)return '';
    const isUp=state==='up';
    return `<span class="limit-badge ${isUp?'lu':'ld'}">${isUp?'漲停':'跌停'}</span>`;
  }
  async function loadIntradayQuotes(){
    // 2026-09-03深夜（乙.4）：即時串流連線中時，quotes_tw/us這兩份Actions冷檔（10分鐘才變一次、
    // 台股那份859KB）60秒內不重抓——串流每幾秒觸發一次重繪，每次都重抓會把手機流量吃光。
    const liveSkip=LIVE.connected;
    if(!(liveSkip&&Date.now()-INTRADAY_TW_AT<60000)){
      try{const r=await fetch('data/quotes_tw.json?t='+Date.now());INTRADAY_NET_OFF.tw=false;if(r.ok){INTRADAY_TW=await r.json();INTRADAY_TW_AT=Date.now()}}catch(e){INTRADAY_NET_OFF.tw=_isOfflineErr(e);console.warn('[loadIntradayQuotes:tw]',e);recordGlobalError('loadIntradayQuotes:tw',e)}
    }
    if(!(liveSkip&&Date.now()-INTRADAY_US_AT<60000)){
      try{const r=await fetch('data/quotes_us.json?t='+Date.now());INTRADAY_NET_OFF.us=false;if(r.ok){INTRADAY_US=await r.json();INTRADAY_US_AT=Date.now()}}catch(e){INTRADAY_NET_OFF.us=_isOfflineErr(e);console.warn('[loadIntradayQuotes:us]',e);recordGlobalError('loadIntradayQuotes:us',e)}
    }
    await ensureIbkrQuotes();
    await ensureSinopacQuotes();
    try{updateClocks()}catch(e){console.warn('[loadIntradayQuotes:updateClocks]',e);recordGlobalError('loadIntradayQuotes:updateClocks',e)}
  }
  // 2026-09-01新增：quotes_ibkr.json/quotes_sinopac.json由本機
  // research/ibkr_quotes.py／research/shioaji_quotes.py排程產生，不一定
  // 存在（使用者沒開Gateway/沒開排程、或這台裝置本身不是跑排程的那台
  // 機器），查不到就是null，intradayQuote()/loadUsIndexes()/
  // loadMarketIndex()/loadHomeIndex()會自動退回既有FinMind/Yahoo/TWSE
  // 資料源，這裡刻意不記recordGlobalError——檔案不存在是完全正常的情況，
  // 不是錯誤。獨立成函式讓多個載入函式都能各自確保資料已載入，不假設
  // 呼叫順序（沒有做快取，跟這支App其他報價載入函式的既有慣例一致，
  // 每次都重抓）。
  async function ensureIbkrQuotes(){
    if(LIVE.connected&&Date.now()-LIVE.ibkrAt<20000)return; // 2026-09-03深夜：串流剛送來的資料比git冷檔新，不要蓋掉
    try{const r=await fetch('data/quotes_ibkr.json?t='+Date.now());INTRADAY_IBKR=r.ok?await r.json():null}catch(e){console.warn('[ensureIbkrQuotes]',e);INTRADAY_IBKR=null}
  }
  async function ensureSinopacQuotes(){
    if(LIVE.connected&&Date.now()-LIVE.sinopacAt<20000)return; // 同上
    try{const r=await fetch('data/quotes_sinopac.json?t='+Date.now());INTRADAY_SINOPAC=r.ok?await r.json():null}catch(e){console.warn('[ensureSinopacQuotes]',e);INTRADAY_SINOPAC=null}
  }
  // 資料超過20分鐘沒更新就不當作「盤中即時」使用了（寧可退回FinMind日線，也不要
  // 顯示過期到失去意義的「盤中」報價卻讓人以為是新的）。
  const INTRADAY_STALE_MIN=20;
  // 2026-09-03深夜（乙.4）本機即時伺服器連線狀態（函式定義在設定頁區塊startLiveStream()等）。
  const LIVE={url:null,token:null,cfId:null,cfSecret:null,configured:false,connected:false,lastEventAt:null,kbarsLast:{},abort:null,retryMs:3000,lastError:null,sinopacAt:0,ibkrAt:0,sourceMode:null,streamMode:null};
  // 2026-09-06（實測.一）官方在市名冊。由 scripts/build_listed_universe.py 每日彙整
  // TWSE/TPEx 的四個官方端點產生。用途只有一個：分辨「這一檔真的不在市」與
  // 「這一檔在市、只是我們沒接好」。總司令實測新增自選股顯示「無報價」，資料其實
  // 三個檔案裡都有，就是後者。
  let LISTED_UNIVERSE=null;
  // 2026-10-09（先.五十六-A1）：官方停止交易清單（TPEx tpex_cmode／TWSE TWTAWU），來自 listed_universe.json 的 suspended
  let LISTED_SUSPENDED={},LISTED_SUSPECTED={};
  function suspendedInfo(code){return (LISTED_SUSPENDED&&LISTED_SUSPENDED[code]&&LISTED_SUSPENDED[code].trading_status==='SUSPENDED_OFFICIAL')?LISTED_SUSPENDED[code]:null}
  // 先.八十一-57：官方終止上市（近 365 天）、疑似停止交易（仍在名冊但連續 ≥5 個交易日不在官方收盤快照、無公告）
  function delistedInfo(code){return (LISTED_SUSPENDED&&LISTED_SUSPENDED[code]&&LISTED_SUSPENDED[code].trading_status==='DELISTED_OFFICIAL')?LISTED_SUSPENDED[code]:null}
  function suspectedInfo(code){return (LISTED_SUSPECTED&&LISTED_SUSPECTED[code])||null}
  // 沒有報價時要顯示的文字：官方停止交易者顯示「停止交易（官方）」，取代「無報價」
  function noQuoteLabel(code,us){
    const s=!us&&suspendedInfo(code);
    if(s)return '停止交易（官方'+(s.since?'，'+s.since+' 起':(s.as_of?'，資料日 '+s.as_of:''))+'）';
    const dl=!us&&delistedInfo(code);
    if(dl)return '終止上市（官方'+(dl.since?'，'+dl.since:'')+'）';
    const sp=!us&&suspectedInfo(code);
    if(sp)return '疑似停止交易（'+(sp.last_quoted?String(sp.last_quoted).slice(5).replace('-','/')+' 後':'')+'官方收盤表找不到，無公告）';
    return '無報價（'+noQuoteReason(code,us)+'）';
  }
  async function ensureListedUniverse(){
    if(LISTED_UNIVERSE)return LISTED_UNIVERSE;
    try{
      const r=await fetch('data/listed_universe.json?t='+Math.floor(Date.now()/3600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      LISTED_UNIVERSE=new Set(d.active||[]);
      LISTED_SUSPENDED=(d.suspended&&typeof d.suspended==='object')?d.suspended:{};
      LISTED_SUSPECTED=(d.suspected_halt&&typeof d.suspected_halt==='object')?d.suspected_halt:{};
    }catch(e){
      console.warn('[ensureListedUniverse]',e);recordGlobalError('ensureListedUniverse',e);
      if(!LISTED_UNIVERSE)LISTED_UNIVERSE=new Set();
    }
    return LISTED_UNIVERSE;
  }
  // 名冊沒載到（size 0）時一律回 true＝「當作在市」，不能因為名冊沒讀到就把
  // 每一檔股票都標成已下市。
  function isListedNow(code){return !LISTED_UNIVERSE||LISTED_UNIVERSE.size===0||LISTED_UNIVERSE.has(code)}
  let INTRADAY_TW_AT=0,INTRADAY_US_AT=0;
  // 2026-08-26 新增（P2）：「無報價」要說明原因，不能只丟一個沒有解釋的空狀態——
  // 依可取得的訊號盡量誠實分類成「休市」／「資料源失敗」／「未涵蓋」三種之一。
  // ── 2026-09-06（實測.一）全 App 唯一的報價回退鏈 ────────────────────────────
  // 總司令實測：新增一檔自選股後顯示「無報價」，但那一檔在 quotes_all_tw.json 與
  // sparklines.json 裡都有價格。根因是各處各自只查 quotes_tw.json（Actions 只抓
  // 前 210 檔），查不到就直接放棄，沒有往後面兩層退。
  //
  // 四層，依總司令指定的順序，每一層都標明自己是哪一層：
  //   1. live      即時（Shioaji tick / IBKR），受 20 分鐘新鮮度限制
  //   2. quotes    quotes_tw.json / quotes_us.json（約 210 檔，不管新不新鮮都收）
  //   3. all       quotes_all_tw.json（全市場 2,837 檔盤後收盤）
  //   4. history   sparklines.json 最後一點
  //
  // 第 4 層說明：總司令指定的是「price_history 最後收盤」。price_history.json 是
  // 好幾 MB 的全歷史檔，在手機上整份抓不划算；sparklines.json（286KB）就是由
  // build_sparklines.py 從 price_history 切出來的近 20 日收盤，**最後一點就是
  // price_history 的最後收盤**，是同一個數字的輕量版本，所以用它。
  function resolveQuote(code,us){
    const iq=intradayQuote(code,us);
    if(iq&&iq.price!=null)return Object.assign({},iq,{tier:'live'});

    const cold=(us?INTRADAY_US:INTRADAY_TW);
    const raw=cold&&cold.quotes?cold.quotes[code]:null;
    // 先.八十一-24：stale:true＝MIS 這檔沒有成交也沒有委買賣，fetch_quotes_tw.py 用「昨收」頂上（漲跌固定 0）。
    // 2026-10-13 上午 GitHub 排程整段沒跑，07:50 開盤前那份全是這種列，首頁自選股整排顯示「+0.00%」像是今天平盤。
    // 這種列不是報價，跳過，交給下一層（全市場盤後收盤，帶真實日期與當日漲跌）。
    if(raw&&raw.price!=null&&raw.stale!==true){
      return {price:raw.price,change:raw.change??null,change_pct:raw.change_pct??null,
              prev_close:raw.prev_close??null,sparkline:raw.sparkline,
              source:'quotes_file',tier:'quotes',
              asof:cold&&cold.fetched_at?cold.fetched_at:null};
    }

    if(!us){
      const a=QUOTES_ALL_TW_CACHE&&QUOTES_ALL_TW_CACHE.quotes?QUOTES_ALL_TW_CACHE.quotes[code]:null;
      if(a&&a.close!=null){
        // 2026-09-17（稽核.四.1修正版(a)）：a.is_stale=true代表這筆的as_of落後大盤
        // 當日最大日期（例如TWSE payload還沒更新），change_pct是這檔自己前後兩個
        // 交易日的真實漲跌沒有錯，但拿「舊日期的漲跌」當「今天的漲跌」顯示會誤導，
        // 這裡直接回null，交給呼叫端（hydrateHome等）決定要不要顯示日期標籤。
        const isStale=a.is_stale===true;
        const pct=(!isStale&&typeof a.change_pct==='number'&&isFinite(a.change_pct)&&a.change_pct!==-100)?a.change_pct:null;
        // 前收優先用 sparklines 的倒數第二點（那是真實收盤價），只有查不到時才用
        // change_pct 反推。反推會有誤差：change_pct 只存到小數第二位，反推出來的
        // 前收可能差一點點，而漲跌停價是拿前收乘 1.1 再取整的，差一點就可能整檔
        // 判錯（例如 511 反推成 511.02，漲停就從 562 變成 563）。
        const sp0=sparkFor(code);
        const prevExact=(sp0&&sp0.length>=2)?sp0[sp0.length-2]:null;
        const prev=(prevExact!=null&&isFinite(prevExact))?prevExact:(pct!=null?a.close/(1+pct/100):null);
        return {price:a.close,change:prev!=null?a.close-prev:null,change_pct:pct,
                prev_close:prev,source:'quotes_all_tw',tier:'all',asof:a.date||a.as_of||null,
                is_stale:isStale,stale_days:a.stale_days||null};
      }
    }

    const sp=sparkFor(code);
    if(sp&&sp.length){
      const last=sp[sp.length-1],prev=sp.length>1?sp[sp.length-2]:null;
      if(last!=null&&isFinite(last)){
        // 2026-09-15：asof 改用 SPARKLINES_ASOF（見 ensureSparklines()），不再是
        // 寫死的 null——這一層是四層回退鏈的最後一層，理論上最容易過期，卻是
        // 唯一從來不標日期的一層，跟財報過期的處理原則不一致（財報過期至少
        // 標「XXXXQn」，這裡過去完全沒有任何標示）。
        // 2026-09-17（稽核.四.1修正版(a)）：個別代號如果在SPARKLINES_STALE_DATES
        // 裡有紀錄，代表它最後一筆的實際日期比SPARKLINES_ASOF還舊（大盤當日
        // 最大日期），asof要用那個真實日期，change_pct（舊日期算出來的漲跌）
        // 不顯示，交給is_stale標記讓呼叫端決定畫法。
        const staleAsof=SPARKLINES_STALE_DATES[code];
        const isStale=!!staleAsof;
        return {price:last,change:isStale?null:(prev!=null?last-prev:null),
                change_pct:isStale?null:(prev?((last-prev)/prev*100):null),prev_close:prev,
                sparkline:sp,source:'sparklines',tier:'history',asof:staleAsof||SPARKLINES_ASOF,
                is_stale:isStale};
      }
    }
    return null;
  }
  // 每一層在 UI 上怎麼講。層級越後面越舊，要讓使用者一眼分得出來，不能都講成「即時」。
  const QUOTE_TIER_LABEL={
    live:'即時',
    quotes:'排程報價（約10分鐘）',
    all:'全市場盤後收盤',
    history:'歷史最後收盤',
  };
  // 走到這裡代表四層全部沒有。依總司令裁示：只有「已下市/暫停交易」才算真的無報價，
  // 其他情況都要說出是哪一環沒接上，不能含糊帶過。
  function noQuoteReason(code,us){
    if(!us&&!isListedNow(code))return '已下市或暫停交易';
    if(!us&&LISTED_UNIVERSE&&LISTED_UNIVERSE.size>0&&LISTED_UNIVERSE.has(code))
      return '在官方名冊內但四層來源都沒有這一檔的價格，請回報';
    const src=us?INTRADAY_US:INTRADAY_TW;
    if(src&&src.quotes&&src.quotes[code]){
      const age=intradayAgeMin(src);
      if(age!=null&&age>INTRADAY_STALE_MIN)return '休市或排程尚未更新';
      return '資料源失敗';
    }
    if(FM_LAST_FAILED)return '資料源失敗';
    return us?'美股報價檔未涵蓋此檔':'未涵蓋此檔';
  }
  function intradayQuote(code,us){
    // 2026-09-01分工鐵律：台股一律走Shioaji（REALTIME，永豐自家經紀商
    // 報價，見shioaji_quotes.py），美股一律走IBKR（REALTIME/DELAYED視
    // 帳戶市場數據訂閱而定，見ibkr_quotes.py），兩者不重疊，各自查不到
    // 才退回現有FinMind/quotes_tw/quotes_us來源。
    if(!us){
      const sinopac=sinopacQuote(code);
      if(sinopac)return sinopac;
    }else{
      const ibkr=ibkrQuote(code);
      if(ibkr)return ibkr;
    }
    const src=us?INTRADAY_US:INTRADAY_TW;
    if(!src||!src.quotes)return null;
    const q=src.quotes[code];if(!q)return null;
    const age=intradayAgeMin(src);
    if(age==null||age>INTRADAY_STALE_MIN)return null;
    return{...q,ageMin:age,source:'finmind'};
  }
  // 2026-08-26 修正（P1-2）：原本不管有沒有資料都顯示「現在時鐘時間」，導致「美股
  // 資料延遲 11:23」這種文字即使完全沒抓到資料也會出現、且旁邊的時間看起來像是
  // 「資料的時間」但其實只是當下時鐘——使用者實測回報過這個誤導。改成三態誠實規則：
  // 完全沒資料→「無資料」；盤中且資料新鮮→「延遲N分」；休市→「已收盤(M/D)」，
  // 時間戳一律顯示資料本身的實際時間（fetched_at 或最後一筆報價日期），不是現在幾點。
  // 2026-08-28 P0-a 根治（第6次時鐘問題的真因）：前面幾輪修正把.tm改成
  // 顯示fmtTzHHMM(d,tz)算出來的「資料時間」（data.fetched_at），不是
  // 「現在時鐘時間」——這個欄位視覺上緊貼在時鐘pill裡，使用者會當成時鐘看，
  // 但它其實只在每次抓到新報價時才變動，抓價間隔內完全不動，看起來就像
  // 「時鐘停了/算錯」。改回.tm=zonedNow(tz).hhmmss.slice(0,5)，一律顯示
  // 該市場「現在時間」，每秒隨setInterval(updateClocks,1000)更新；資料
  // 新鮮度改用label文字（「延遲N分」/「已收盤(M/D)」）表達，不再疊在時間欄位上。
  function mktPill(elId,tz,openMin,closeMin,intradayGetter){
    const el=document.getElementById(elId);if(!el)return;
    const dotEl=el.querySelector('.dot'),bEl=el.querySelector('b'),tmEl=el.querySelector('.tm');
    if(!dotEl||!bEl||!tmEl)return;
    const z=zonedNow(tz);
    const mins=z.h*60+z.mi;
    const open=z.wd>=1&&z.wd<=5&&mins>=openMin&&mins<closeMin;
    const data=intradayGetter?intradayGetter():null;
    const age=intradayAgeMin(data);
    let label,dot;
    // 先.九十五-R1②：斷網時沒抓到即時檔寫「離線」，不寫「無資料」（下面卡片可能正顯示上次存的資料，兩處說法要一致）
    if(age==null){label=(navigator.onLine===false||INTRADAY_NET_OFF[elId==='mkt-us'?'us':'tw'])?'離線':'無資料';dot='var(--ink-3)';}
    else{const d=new Date(data.fetched_at);
      if(open&&age<=INTRADAY_STALE_MIN){label='延遲'+Math.max(1,Math.round(age))+'分';dot='var(--good)'}
      else if(open){label='資料延遲';dot='var(--warn)'}
      else{label='已收盤('+fmtTzMD(d,tz)+')';dot='var(--ink-3)'}}
    dotEl.style.background=dot;
    bEl.textContent=label;
    // 2026-08-28 P0-a 根治：.tm=該市場現在時間(每秒更新的時鐘)，非 fetched_at。
    tmEl.textContent=z.hhmmss.slice(0,5);
  }
  // 2026-08-27新增（P2-新，盤前盤後）：美股時鐘從「開盤/休市」兩態擴為
  // 盤前/盤中/盤後/休市四態——跟 fetch_quotes_us.py::us_market_session()
  // 同一套邊界(04:00-09:30盤前/09:30-16:00盤中/16:00-20:00盤後/其餘休市)，
  // 用 zonedNow() 算的美東當地時間分鐘數判斷，不是寫死UTC常數，日光節約
  // 由 Intl.DateTimeFormat 自動處理（跟既有 mktPill() 同一個機制）。
  function usMarketSession(z){
    if(z.wd<1||z.wd>5)return 'closed';
    const m=z.h*60+z.mi;
    if(m>=4*60&&m<9*60+30)return 'pre';
    if(m>=9*60+30&&m<16*60)return 'regular';
    if(m>=16*60&&m<20*60)return 'post';
    return 'closed';
  }
  // 2026-08-28 P0-a 根治：同mktPill()，.tm改回顯示美東現在時間(每秒更新)，
  // 不再顯示data.fetched_at資料時間——那才是前6輪時鐘問題看起來「算錯」的真因。
  function mktPillUS(){
    const el=document.getElementById('mkt-us');if(!el)return;
    const dotEl=el.querySelector('.dot'),bEl=el.querySelector('b'),tmEl=el.querySelector('.tm');
    if(!dotEl||!bEl||!tmEl)return;
    const z=zonedNow('America/New_York');
    const session=usMarketSession(z);
    const data=INTRADAY_US;
    const age=intradayAgeMin(data);
    let label,dot;
    if(session==='pre'||session==='post'){label=session==='pre'?'盤前':'盤後';dot='var(--warn)';}
    else if(session==='closed'){
      if(age==null){label=(navigator.onLine===false||INTRADAY_NET_OFF.us)?'離線':'無資料';dot='var(--ink-3)'}
      else{label='已收盤('+fmtTzMD(new Date(data.fetched_at),'America/New_York')+')';dot='var(--ink-3)'}}
    else{
      if(age==null){label=(navigator.onLine===false||INTRADAY_NET_OFF.us)?'離線':'無資料';dot='var(--ink-3)'}
      else if(age<=INTRADAY_STALE_MIN){label='延遲'+Math.max(1,Math.round(age))+'分';dot='var(--good)'}
      else{label='資料延遲';dot='var(--warn)'}}
    dotEl.style.background=dot;
    bEl.textContent=label;
    // 2026-08-28 P0-a 根治：.tm=美東現在時間(每秒更新)，非 fetched_at。
    tmEl.textContent=z.hhmmss.slice(0,5);
  }
  // ── 2026-09-06（健檢.一）交易日曆 ───────────────────────────────────────────
  // 問題：診斷橫幅原本用「rolling 24 小時」判斷資料過舊，所以每逢週末與國定假日
  // 都會亂叫「大盤/類股/三大法人 資料過舊」——但那些資料本來就只在交易日產生，
  // 週日看到的星期五收盤資料是**完全正常**的，不是故障。誤報比不報更糟：叫久了
  // 使用者就不看橫幅，真的壞掉時也不會注意。
  //
  // 改成跟「最近一個應有交易日的收盤時間」比：資料日期只要不早於那一天，就不算過舊。
  //
  // 假日表資料來源：
  //   台股 2026 年休市日 — 臺灣證券交易所「113 年度～115 年度交易日曆表」公告
  //     （https://www.twse.com.tw/zh/holidaySchedule/holidaySchedule）
  //   美股 2026 年休市日 — NYSE 官方 Holidays & Trading Hours
  //     （https://www.nyse.com/markets/hours-calendars）
  // 只寫死 2026 年（總司令指示「寫死一份 2026 年的即可」）。跨年前要更新，
  // 沒更新時的行為是「把該假日當成交易日」——結果只是那天可能誤報一次，
  // 不會反過來把真的過舊藏起來，這個方向的失敗比較安全。
  const TW_HOLIDAYS_2026=new Set([
    '2026-01-01','2026-02-12','2026-02-13','2026-02-16','2026-02-17','2026-02-18','2026-02-19','2026-02-20',
    '2026-02-27','2026-02-28','2026-04-03','2026-04-06','2026-05-01','2026-06-19',
    '2026-09-25','2026-09-28','2026-10-09','2026-10-26','2026-12-25',
  ]);
  const US_HOLIDAYS_2026=new Set([
    '2026-01-01','2026-01-19','2026-02-16','2026-04-03','2026-05-25','2026-06-19',
    '2026-07-03','2026-09-07','2026-11-26','2026-12-25',
  ]);
  // 先.八十一-13（2026-10-13）：多年度假日表，App 內一律用 TW_HOLIDAYS／US_HOLIDAYS。內建＝上方 2026 兩份（selftest 比對用，
  // 名稱與格式勿改）＋NYSE 官方頁已公布的 2027；台股 2027 官方尚未公布（TWSE 通常年底公告）。開 App 時再讀
  // data/trading_calendar.json（.github/scripts/fetch_trading_calendar.py，台股問 TWSE 官方日曆端點、美股抄 NYSE 官方頁），
  // 讀到就併入；尚未公布的年份照舊只排除週末（失敗方向較安全，見上方說明）。
  // 這段刻意放在時鐘（updateClocks）首次執行之前：原本假日表宣告在時鐘之後，第一次 updateClocks() 讀到
  // 尚未宣告的 const（暫時死區）而拋錯，首頁狀態列第一秒畫不出來（先.八十一-13 雜項）。
  const US_HOLIDAYS_2027=['2027-01-01','2027-01-18','2027-02-15','2027-03-26','2027-05-31','2027-06-18','2027-07-05','2027-09-06','2027-11-25','2027-12-24'];
  const TW_HOLIDAYS=new Set(TW_HOLIDAYS_2026),US_HOLIDAYS=new Set([...US_HOLIDAYS_2026,...US_HOLIDAYS_2027]);
  let TRADING_CAL=null;
  fetch('data/trading_calendar.json?t='+Math.floor(Date.now()/3600000))
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
    .then(d=>{
      for(const [mkt,set] of [['tw',TW_HOLIDAYS],['us',US_HOLIDAYS]])
        for(const y of Object.values((d&&d[mkt])||{}))[...((y&&y.closed)||[]),...((y&&y.unscheduled_closed)||[])].forEach(x=>set.add(x));  // 先.八十一-48：含臨時停市
      TRADING_CAL=d;
    })
    .catch(e=>{console.warn('[tradingCalendar]',e);recordGlobalError('tradingCalendar',e)});
  function updateClocks(){
    try{renderHomeStatusSummary()}catch(e){console.warn('[updateClocks:summary]',e)}  // 2026-09-04 P0產品.一
    mktPill('mkt-tw','Asia/Taipei',9*60,13*60+30,()=>INTRADAY_TW);
    mktPillUS();
  }
  // 2026-08-27修正（使用者定位的根因）：原本是「updateClocks();setInterval(...)」
  // 同一行、先執行後註冊——如果第一次同步執行updateClocks()時拋錯，setInterval
  // 永遠不會被註冊到（拋錯會中止當前script區塊剩下的同步程式碼），時鐘從此
  // 永久停擺，且後面所有初始化呼叫（loadIntradayQuotes等）也不會執行到。
  // 改成：先註冊interval（用try/catch包住每次執行，不會因為一次失敗就整個
  // 停掉），再包在try/catch裡執行一次首次呼叫，兩者都不會讓拋錯往外傳播。
  setInterval(()=>{try{updateClocks()}catch(e){console.warn('[clock]',e);recordGlobalError('clock',e)}},1000);
  try{updateClocks()}catch(e){console.warn('[clock]',e);recordGlobalError('clock',e)}
  // loadIntradayQuotes是async function：一般try/catch包不住之後才發生的promise
  // rejection（async函式一呼叫就立刻回傳pending promise，try/catch的範圍只涵蓋
  // 同步丟出的那段），要用.catch()才能真正接住，不然還是會變成unhandledrejection。
  const _safeLoadIntradayQuotes=()=>loadIntradayQuotes().catch(e=>{console.warn('[loadIntradayQuotes]',e);recordGlobalError('loadIntradayQuotes',e)});
  setInterval(_safeLoadIntradayQuotes,2*60*1000);
  _safeLoadIntradayQuotes();

  // ══════ 盤中近即時輪詢（2026-09-02新增，PENDING_QUEUE「數字盤中自動跳動」）══════
  // 跟上面既有的2分鐘_safeLoadIntradayQuotes()是兩件事：那支只更新
  // INTRADAY_TW/US/IBKR/SINOPAC快取+時鐘label，不會讓自選股/大盤數字真的
  // 動起來（沒有重繪畫面）。這裡額外每15秒觸發一次，且只在三個條件同時
  // 成立才會真的打網路+重繪：①台股或美股至少一個在其交易時段②使用者正在
  // 看「今日」或「市場」分頁③App分頁在前景可見——三者缺一律跳過，不背景
  // 空轉浪費資源，也不誤導使用者以為所有分頁都在即時跳動。**這不是逐筆
  // 串流**，只是定時重新fetch既有的quotes_*.json靜態檔（後端排程本身多久
  // 更新一次是另一回事，這裡純粹是前端多久重新讀一次），畫面上明確標示
  // 「近即時輪詢」而非「即時」，避免使用者誤解成逐筆tick。
  const FAST_POLL_INTERVAL_MS=15000;
  let PREV_QUOTE_PRICES={}; // code/指數label -> 上一次輪詢看到的價格，判斷要不要閃爍用，非權威資料
  function _ymd(z){return `${z.y}-${String(z.m).padStart(2,'0')}-${String(z.d).padStart(2,'0')}`}
  function isTradingDay(dateObj,tz,holidays){
    const z=_zonedParts(dateObj,tz);
    if(z.wd===0||z.wd===6)return false;            // 週末
    return !holidays.has(_ymd(z));
  }
  // 2026-09-15（sparklines凍結事件，總司令裁示）：算「dateStr這天」到「今天」之間
  // 經過了幾個交易日（週末/假日不算），給resolveQuote()的history層（sparklines
  // 最後一道回退）判斷是不是已經過期太久，過期太久要把日期直接寫進價格文字，
  // 不能讓使用者以為是當前價。dateStr格式YYYY-MM-DD，抓不到就回傳null（呼叫端
  // 視為「不確定新舊，保守當作可能過期」還是「不過期」由呼叫端自己決定，這裡
  // 只負責算數字）。
  function tradingDaysSince(dateStr,tz,holidays){
    if(!dateStr||dateStr.length<10)return null;
    const y=+dateStr.slice(0,4),m=+dateStr.slice(5,7),d=+dateStr.slice(8,10);
    if(!y||!m||!d)return null;
    const start=new Date(Date.UTC(y,m-1,d,4,0,0));  // 台北中午前後，避免UTC轉換跨到前一天
    const now=new Date();
    let n=0;
    for(let cursor=new Date(start.getTime()+864e5);cursor<=now;cursor=new Date(cursor.getTime()+864e5)){
      if(isTradingDay(cursor,tz,holidays))n++;
    }
    return n;
  }
  // 回傳「最近一個應該已經收盤的交易日」的 Date（該日當地收盤時間）。
  // 今天是交易日但還沒收盤時，要往前找到前一個交易日——否則盤中會誤判成過舊。
  // nowMs 可以外部注入，讓「模擬成週日／模擬成交易日盤後」這種驗收不需要去動
  // 全域的 Date（動全域 Date 會連帶影響時鐘、SSE、快取判斷，測出來的東西就不準了）。
  function lastExpectedSessionEnd(tz,holidays,closeH,closeMi,nowMs){
    const now=(nowMs!=null)?new Date(nowMs):new Date();
    for(let back=0;back<12;back++){                // 最多往前找 12 天（含連假）
      const d=new Date(now.getTime()-back*864e5);
      if(!isTradingDay(d,tz,holidays))continue;
      const z=_zonedParts(d,tz);
      // 用該日的當地收盤時刻組出一個絕對時間：拿當天任一時刻的 offset 回推
      const guess=new Date(d);
      const cur=_zonedParts(guess,tz);
      const deltaMin=(closeH*60+closeMi)-(cur.h*60+cur.mi);
      const end=new Date(guess.getTime()+deltaMin*60000);
      if(end<=now)return end;
    }
    return null;
  }
  // 資料時間戳夠不夠新：只要不早於「最近一個應有交易日收盤」再扣掉寬限，就算新鮮。
  // graceMin 是給排程留的緩衝（收盤後不會立刻產出）。
  function isFreshForCalendar(fetchedAtMs,tz,holidays,closeH,closeMi,graceMin,nowMs){
    if(fetchedAtMs==null||!isFinite(fetchedAtMs))return false;
    const end=lastExpectedSessionEnd(tz,holidays,closeH,closeMi,nowMs);
    if(end==null)return true;                      // 算不出來就不擋（不製造誤報）
    return fetchedAtMs>=end.getTime()-(graceMin||0)*60000;
  }
  function isTwTradingWindowNow(){
    // 沿用research/shioaji_quotes.py::_is_tw_trading_window()同一組時窗
    // （週一至五08:30–13:45台北時間，涵蓋現貨盤前~盤後緩衝），不是自己另外
    // 發明一套邊界，跟後端資料源禮儀的既有慣例一致。
    const z=zonedNow('Asia/Taipei');
    const mins=z.h*60+z.mi;
    return z.wd>=1&&z.wd<=5&&mins>=8*60+30&&mins<13*60+45;
  }
  function isUsTradingWindowNow(){
    // 沿用既有usMarketSession()（盤前/盤中/盤後/休市四態），非'closed'都算
    // 「在交易時段」——跟.github/workflows/quotes.yml涵蓋盤前盤後的既有範圍
    // 一致（quotes_us.json本來就會在這整段時間持續更新）。
    return usMarketSession(zonedNow('America/New_York'))!=='closed';
  }
  function pollStatusText(twActive,usActive){
    // 2026-09-04（四修.四）：SSE連線中時，畫面上的數字是由即時串流推動的，不是15秒輪詢——
    // 文案要跟著實際模式走，不能同一頁又寫「近即時輪詢」又寫「即時連線中」。
    if(LIVE.connected){
      const mode=LIVE.streamMode==='tick-push'?'逐筆推送 tick-push':(LIVE.streamMode||'SSE');
      return `● 即時串流連線中（${mode}${LIVE.sourceMode==='tick-push-memory'?'':'，來源'+(LIVE.sourceMode||'')}），數字隨 tick 更新，已停用15秒輪詢`;
    }
    if(!twActive&&!usActive)return '已收盤，暫停自動更新';
    const which=twActive&&usActive?'台美股皆':(twActive?'台股':'美股');
    return `🔄 ${which}在交易時段，約每15秒自動更新（近即時輪詢，非逐筆tick）`;
  }
  // 每個tick都會更新這兩個誠實揭露文字（不管待會要不要真的去fetch），讓
  // 使用者一眼看到目前是不是在自動更新中，跟下面「要不要真的打網路」分開判斷。
  function updatePollNote(){
    const twActive=isTwTradingWindowNow(),usActive=isUsTradingWindowNow();
    const txt=pollStatusText(twActive,usActive);
    const h=document.getElementById('home-poll-note');if(h)h.textContent=txt;
    const m=document.getElementById('market-poll-note');if(m)m.textContent=txt;
    return {twActive,usActive};
  }
  // 數字變動時的視覺回饋：比對這次渲染後畫面上的data-flash-value跟上次輪詢
  // 記住的值，不同才加flash-up/flash-down（見CSS約52行新增的flash-up-kf/
  // flash-down-kf keyframes，跟.rise/.grow是不同用途的動畫，不能共用）。
  // 動畫結束後用animationend自動移除class，不用setTimeout猜時間。
  function flashPriceEls(scopeSelector){
    const scope=document.querySelector(scopeSelector);if(!scope)return;
    scope.querySelectorAll('[data-flash-code]').forEach(el=>{
      const code=el.dataset.flashCode;
      const cur=parseFloat(el.dataset.flashValue);
      if(isNaN(cur))return;
      const prev=PREV_QUOTE_PRICES[code];
      if(prev!=null&&prev!==cur&&!uiReducedMotion()){ // 先.九十六-R4：減少動態時不閃
        el.classList.remove('flash-up','flash-down');
        void el.offsetWidth; // 強制reflow，讓同方向的連續變動也能重新觸發動畫
        el.classList.add(cur>prev?'flash-up':'flash-down');
        el.addEventListener('animationend',()=>el.classList.remove('flash-up','flash-down'),{once:true});
      }
      PREV_QUOTE_PRICES[code]=cur;
    });
  }
  async function fastPollTick(){
    const {twActive,usActive}=updatePollNote();
    if(LIVE.connected)return; // 2026-09-03深夜（乙.4）：即時串流接管更新（scheduleLiveRerender），輪詢冷檔沒有意義
    if(!twActive&&!usActive)return; // 兩個市場都收盤，不輪詢
    if(CURRENT_TAB!=='home'&&CURRENT_TAB!=='market')return; // 使用者沒在看這兩頁，不輪詢
    if(document.visibilityState!=='visible')return; // App在背景/螢幕鎖定，不輪詢
    try{
      // 沿用既有載入函式重新fetch對應JSON，不重新發明抓資料邏輯。
      await loadIntradayQuotes();
    }catch(e){console.warn('[fastPollTick:load]',e);recordGlobalError('fastPollTick:load',e);return}
    try{
      if(CURRENT_TAB==='home'){
        await hydrateHome();
        flashPriceEls('#wl-list');
        flashPriceEls('#home-idx-rows');
      }else if(CURRENT_TAB==='market'){
        if(MKT_STATE.market==='TW'){await loadMarketIndex();flashPriceEls('#idx-rows')}
        else if(MKT_STATE.market==='US'){await loadMarketUS();flashPriceEls('#us-idx-rows')}
        else if(MKT_STATE.market==='FUT'){await loadMarketFUT()}
      }
    }catch(e){console.warn('[fastPollTick:render]',e);recordGlobalError('fastPollTick:render',e)}
  }
  setInterval(()=>{fastPollTick().catch(e=>{console.warn('[fastPollTick]',e);recordGlobalError('fastPollTick',e)})},FAST_POLL_INTERVAL_MS);
  try{updatePollNote()}catch(e){console.warn('[updatePollNote]',e);recordGlobalError('updatePollNote',e)}

  // 2026-08-28新增：設定頁底部縮放/貼底問題診斷讀數（純唯讀，不影響其他
  // 版面邏輯）。獨立的setInterval+resize監聽，自成一體try/catch，跟上面
  // 時鐘的錯誤隔離同一個精神——這裡拋錯只會讓這行診斷文字不更新，不會
  // 拖累其他任何功能。
  let _safeAreaProbeEl=null;
  function _safeAreaBottomPx(){
    if(!_safeAreaProbeEl){
      _safeAreaProbeEl=document.createElement('div');
      _safeAreaProbeEl.style.cssText='height:env(safe-area-inset-bottom);position:fixed;visibility:hidden;top:0;left:0;width:0';
      document.body.appendChild(_safeAreaProbeEl);
    }
    return _safeAreaProbeEl.offsetHeight;
  }
  function isDebugDiagOn(){
    try{return localStorage.getItem('alpha_debug_diag')==='1'}catch(e){return false}
  }
  function updateViewportDiag(){
    const el=document.getElementById('viewport-diag');if(!el)return;
    if(!isDebugDiagOn()){el.style.display='none';el.textContent='';return}
    el.style.display='';
    const standalone=(navigator.standalone===true)||(window.matchMedia&&matchMedia('(display-mode: standalone)').matches);
    const innerH=window.innerHeight;
    const visualVP=window.visualViewport?Math.round(window.visualViewport.height):'n/a';
    const safeBottom=_safeAreaBottomPx();
    const navEl=document.getElementById('nav');
    const navGap=navEl?(window.innerHeight-navEl.getBoundingClientRect().bottom):'n/a';
    // 2026-08-28新增（驗證black-translucent→black修正用，之後可移除）：
    // screenH（實體螢幕高）/clientH（documentElement.clientHeight）方便
    // 一眼看出innerH有沒有等於實體螢幕高，不用另外開DevTools量。
    const screenH=screen.height;
    const clientH=document.documentElement.clientHeight;
    // 2026-08-28新增（驗證100lvh修正用）：#app實際渲染高度，理論上改完
    // 應該要接近screenH（實體螢幕高），不再卡在少算狀態列高度的innerH。
    const appEl=document.getElementById('app');
    const appH=appEl?Math.round(appEl.getBoundingClientRect().height):'n/a';
    el.textContent=`standalone=${standalone} · innerH=${innerH} · visualVP=${visualVP} · safeBottom=${safeBottom} · navGap=${navGap} · screenH=${screenH} · clientH=${clientH} · appH=${appH}`;
  }
  setInterval(()=>{try{updateViewportDiag()}catch(e){console.warn('[viewportDiag]',e);recordGlobalError('viewportDiag',e)}},1000);
  window.addEventListener('resize',()=>{try{updateViewportDiag()}catch(e){console.warn('[viewportDiag:resize]',e);recordGlobalError('viewportDiag:resize',e)}});
  if(window.visualViewport)window.visualViewport.addEventListener('resize',()=>{try{updateViewportDiag()}catch(e){console.warn('[viewportDiag:vvresize]',e);recordGlobalError('viewportDiag:vvresize',e)}});
  try{updateViewportDiag()}catch(e){console.warn('[viewportDiag]',e);recordGlobalError('viewportDiag',e)}

  // ══════ 真實資料層（FinMind，瀏覽器直抓，免後端）══════
  const FM="https://api.finmindtrade.com/api/v4/data";
  // 常備.開發-8（2026-10-11）：多自選清單。alpha_wl 仍是「目前清單」（既有程式全部照舊讀寫 WL），
  // alpha_wl_lists＝{active, lists:{名稱:[代號]}} 存全部清單；切換時才把 WL 寫回 lists。舊格式第一次載入自動搬進「我的自選」。
  const WL_DEFAULT_NAME='我的自選';
  function wlListsRead(){
    let o=null;try{o=JSON.parse(localStorage.getItem('alpha_wl_lists'))}catch(e){console.warn('[wlListsRead]',e);recordGlobalError('wlListsRead',e)}
    if(!o||typeof o!=='object'||!o.lists||typeof o.lists!=='object'||!Object.keys(o.lists).length){
      o={active:WL_DEFAULT_NAME,lists:{[WL_DEFAULT_NAME]:Array.isArray(WL)?WL.slice():[]}};
    }
    if(!o.lists[o.active])o.active=Object.keys(o.lists)[0];
    o.lists[o.active]=Array.isArray(WL)?WL.slice():o.lists[o.active];  // 目前清單以 WL 為準
    return o;
  }
  function wlListsWrite(o){localStorage.setItem('alpha_wl_lists',JSON.stringify(o))}
  function _wlActivate(o,name){
    o.active=name;wlListsWrite(o);WL=o.lists[name].slice();localStorage.setItem('alpha_wl',JSON.stringify(WL));
    pushWatchlistSoon();pushSettingsSoon();renderWLTabs();hydrateHome();
  }
  function wlSwitch(name){const o=wlListsRead();if(!o.lists[name]||o.active===name)return false;wlListsWrite(o);_wlActivate(o,name);return true}
  function wlCreate(name){
    name=String(name||'').trim().slice(0,20);const o=wlListsRead();
    if(!name||o.lists[name]){toast(name?'已有同名清單':'清單名稱不可空白');return false}
    o.lists[name]=[];_wlActivate(o,name);return true;
  }
  function wlRemove(name){
    const o=wlListsRead();if(!o.lists[name])return false;
    if(Object.keys(o.lists).length<=1){toast('至少要保留一個清單');return false}
    delete o.lists[name];_wlActivate(o,o.active===name?Object.keys(o.lists)[0]:o.active);return true;
  }
  function wlCreatePrompt(){const n=prompt('新清單名稱（最多 20 字）');if(n!=null)wlCreate(n)}
  function wlRemovePrompt(){const o=wlListsRead();if(confirm('下架清單「'+o.active+'」？清單內代號一併移除（其他清單不受影響）'))wlRemove(o.active)}
  function renderWLTabs(){
    const el=document.getElementById('wl-tabs');if(!el)return;
    const o=wlListsRead(),esc=t=>String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const chip=(on)=>'font-size:11.5px;padding:3px 10px;border-radius:12px;white-space:nowrap;cursor:pointer;border:1px solid var(--hairline);'+(on?'background:var(--accent);color:#fff;border-color:var(--accent)':'');
    el.innerHTML=Object.keys(o.lists).map(n=>`<span class="press wl-tab" data-name="${esc(n)}" style="${chip(n===o.active)}">${esc(n)}（${o.lists[n].length}）</span>`).join('')
      +`<span class="press" style="${chip(false)}" onclick="wlCreatePrompt()">＋</span>`
      +(Object.keys(o.lists).length>1?`<span class="press" style="${chip(false)}" onclick="wlRemovePrompt()">下架</span>`:'');
    el.querySelectorAll('.wl-tab').forEach(t=>t.addEventListener('click',()=>wlSwitch(t.dataset.name)));
  }
  // 常備.開發-31（2026-10-11）：自選股匯入匯出（CSV／JSON，含多清單）。
  // JSON＝{format:'alpha-watchlists',version:1,exported_at,active,lists:{名稱:[代號]}}；CSV＝「清單,代號」兩欄。
  // 匯入一律「合併」：同名清單取聯集、新名稱新建，不刪除任何既有清單或代號；也接受純代號陣列／單欄 CSV（併入「匯入清單」）。
  const WL_IO_MAX_LISTS=50,WL_IO_MAX_CODES=300,WL_IO_FALLBACK='匯入清單';
  function _wlNormCode(c){
    c=String(c==null?'':c).trim().replace(/^["']|["']$/g,'').trim();
    if(!/^[0-9A-Za-z][0-9A-Za-z.\-]{0,9}$/.test(c))return null;
    return /^[A-Za-z]/.test(c)?c.toUpperCase():c;
  }
  function _wlNormName(n){n=String(n==null?'':n).replace(/[\r\n\t]/g,' ').trim().slice(0,20);return n||WL_IO_FALLBACK}
  function _wlCsvCell(s){s=String(s);return /[",\r\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s}
  function _wlCsvSplit(line){
    const out=[];let cur='',q=false;
    for(let i=0;i<line.length;i++){const ch=line[i];
      if(q){if(ch==='"'){if(line[i+1]==='"'){cur+='"';i++}else q=false}else cur+=ch}
      else if(ch==='"')q=true;else if(ch===','||ch===';'||ch==='\t'){out.push(cur);cur=''}else cur+=ch}
    out.push(cur);return out.map(x=>x.trim());
  }
  // 純解析，不碰 localStorage：回傳 {lists:{名稱:[代號]}, skipped:[無效值]}；格式整個認不得時丟例外
  function wlParseImport(text,filename){
    text=String(text||'').replace(/^﻿/,'');
    const lists={},skipped=[];
    const add=(name,code)=>{const c=_wlNormCode(code);if(!c){if(String(code||'').trim())skipped.push(String(code).trim().slice(0,20));return}
      name=_wlNormName(name);if(!lists[name]){if(Object.keys(lists).length>=WL_IO_MAX_LISTS)return;lists[name]=[]}
      if(!lists[name].includes(c)&&lists[name].length<WL_IO_MAX_CODES)lists[name].push(c)};
    const t=text.trim();
    if(/\.json$/i.test(filename||'')||t.startsWith('{')||t.startsWith('[')){
      const d=JSON.parse(t);
      if(Array.isArray(d))d.forEach(c=>add(WL_IO_FALLBACK,c));
      else if(d&&typeof d==='object'&&d.lists&&typeof d.lists==='object')Object.keys(d.lists).forEach(n=>{const a=d.lists[n];if(Array.isArray(a))a.forEach(c=>add(n,c))});
      else if(d&&Array.isArray(d.watchlist))d.watchlist.forEach(c=>add(WL_IO_FALLBACK,c));
      else throw new Error('JSON 格式認不得（需要 lists 物件或代號陣列）');
    }else{
      const rows=t.split(/\r?\n/).map(l=>l.trim()).filter(Boolean).map(_wlCsvSplit);
      if(!rows.length)throw new Error('檔案是空的');
      let ci=-1,li=-1;const h=rows[0].map(x=>x.toLowerCase());
      ci=h.findIndex(x=>['code','代號','symbol','ticker','stock_id'].includes(x));
      li=h.findIndex(x=>['list','清單','group','name_of_list'].includes(x));
      const hasHeader=ci>=0;
      if(!hasHeader){const two=rows[0].length>=2&&_wlNormCode(rows[0][1]);ci=two?1:0;li=two?0:-1}  // 無表頭：第二欄像代號才當「清單,代號」，否則視為「代號,名稱…」
      rows.slice(hasHeader?1:0).forEach(r=>add(li>=0?r[li]:WL_IO_FALLBACK,r[ci]));
    }
    if(!Object.keys(lists).length)throw new Error('檔案裡沒有任何有效代號'+(skipped.length?'（略過 '+skipped.length+' 個無效值）':''));
    return {lists,skipped};
  }
  // 純合併：把 imp.lists 併進 o（同名聯集、新名新建），回傳 {added,newLists}
  function wlMergeImport(o,impLists){
    let added=0;const newLists=[];
    Object.keys(impLists).forEach(n=>{
      if(!o.lists[n]){if(Object.keys(o.lists).length>=WL_IO_MAX_LISTS)return;o.lists[n]=[];newLists.push(n)}
      impLists[n].forEach(c=>{if(!o.lists[n].includes(c)&&o.lists[n].length<WL_IO_MAX_CODES){o.lists[n].push(c);added++}});
    });
    return {added,newLists};
  }
  function wlExportText(fmt){
    const o=wlListsRead();
    if(fmt==='csv'){const rows=['list,code'];Object.keys(o.lists).forEach(n=>o.lists[n].forEach(c=>rows.push(_wlCsvCell(n)+','+_wlCsvCell(c))));return '﻿'+rows.join('\r\n')+'\r\n'}
    return JSON.stringify({format:'alpha-watchlists',version:1,exported_at:new Date().toISOString(),active:o.active,lists:o.lists},null,2);
  }
  function wlExport(fmt){
    try{
      const txt=wlExportText(fmt),ext=fmt==='csv'?'csv':'json';
      const blob=new Blob([txt],{type:fmt==='csv'?'text/csv;charset=utf-8':'application/json'});
      const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='alpha-watchlists-'+new Date().toISOString().slice(0,10)+'.'+ext;
      document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1500);
      const o=wlListsRead();toast('已匯出 '+Object.keys(o.lists).length+' 個清單（'+ext.toUpperCase()+'）');
    }catch(e){console.warn('[wlExport]',e);recordGlobalError('wlExport',e);toast('匯出失敗：'+(e&&e.message||e))}
  }
  function wlImportPick(){
    try{
      const inp=document.createElement('input');inp.type='file';inp.accept='.json,.csv,.txt,application/json,text/csv,text/plain';
      inp.onchange=()=>{const f=inp.files&&inp.files[0];if(!f)return;
        if(f.size>512*1024){toast('檔案太大（上限 512KB）');return}
        f.text().then(txt=>wlImportText(txt,f.name)).catch(e=>{console.warn('[wlImport:read]',e);recordGlobalError('wlImport:read',e);toast('讀檔失敗：'+(e&&e.message||e))})};
      inp.click();
    }catch(e){console.warn('[wlImportPick]',e);recordGlobalError('wlImportPick',e);toast('無法開啟檔案選擇')}
  }
  function wlImportText(txt,filename){
    let p;try{p=wlParseImport(txt,filename)}catch(e){console.warn('[wlImport:parse]',e);toast('匯入失敗：'+(e&&e.message||e));return false}
    const names=Object.keys(p.lists),total=names.reduce((s,n)=>s+p.lists[n].length,0);
    if(!confirm('匯入 '+names.length+' 個清單、共 '+total+' 個代號（'+names.slice(0,5).join('、')+(names.length>5?'…':'')+'）？\n同名清單會合併（只增不減），不會刪除你現有的任何清單或代號。'+(p.skipped.length?'\n略過無效值 '+p.skipped.length+' 個。':'')))return false;
    try{
      const o=wlListsRead(),r=wlMergeImport(o,p.lists);
      _wlActivate(o,o.active);  // 寫回 lists、同步 WL（目前清單若被併入也會即時更新）＋推送多裝置同步
      renderWLSettings();
      toast('已匯入：新增 '+r.added+' 個代號'+(r.newLists.length?'、新建 '+r.newLists.length+' 個清單':''));
      return true;
    }catch(e){console.warn('[wlImport:merge]',e);recordGlobalError('wlImport:merge',e);toast('匯入失敗：'+(e&&e.message||e));return false}
  }
  function renderWLSettings(){
    const el=document.getElementById('set-wl-lists');if(!el)return;
    const o=wlListsRead(),n=Object.keys(o.lists);
    el.textContent=n.length+' 個清單、共 '+n.reduce((t,k)=>t+o.lists[k].length,0)+' 檔';  // 文案規則：說明 ≤40 字，清單明細看首頁分頁籤
  }
  let WL=(()=>{try{return JSON.parse(localStorage.getItem('alpha_wl'))||["2330","2454","2317","1513","3231"]}catch(e){console.warn('[WL]',e);recordGlobalError('WL',e);return ["2330","2454","2317","1513","3231"]}})();
  try{wlListsWrite(wlListsRead())}catch(e){console.warn('[wl migrate]',e);recordGlobalError('wl migrate',e)}  // 常備.開發-8：舊單一清單自動搬進「我的自選」
  let currentCode="2330";
  const _cache={};
  const nf=n=>n==null||isNaN(n)?'—':Number(n).toLocaleString();
  function setTxt(id,t){const el=document.getElementById(id);if(el)el.textContent=t}
  const isUS=code=>/^[A-Za-z]/.test(code);
  // 常備.開發-20（先.六十七）：FinMind 名稱清單失敗時，首頁先用 data/quote_lite/{代號}.json 的名稱（見 ensureQuoteLite），
  // 整份 company_info.json 延後到搜尋／其他頁真的要用時才抓。
  const LITE_NAME={};
  // 先.九十五-R1①：自選股等熱門代號的名稱同步存本機（alpha_name_saved，最多 300 筆），斷網重開時名稱不會退成代號。
  // 只是名稱對照（公開資訊），不是報價；有網路時一律以 FinMind／小檔的新名稱為準並覆寫。
  const NAME_SAVED_KEY='alpha_name_saved';
  const NAME_SAVED=(()=>{try{return JSON.parse(localStorage.getItem(NAME_SAVED_KEY))||{}}catch(e){console.warn('[NAME_SAVED]',e);return {}}})();
  let _nameSaveT=null;
  function _nameRemember(code,n){
    if(!code||!n||n===code||NAME_SAVED[code]===n)return;
    NAME_SAVED[code]=n;
    const ks=Object.keys(NAME_SAVED);if(ks.length>300)ks.slice(0,ks.length-300).forEach(k=>delete NAME_SAVED[k]);
    if(_nameSaveT)return;
    _nameSaveT=setTimeout(()=>{_nameSaveT=null;try{localStorage.setItem(NAME_SAVED_KEY,JSON.stringify(NAME_SAVED))}catch(e){console.warn('[nameRemember]',e)}},500);
  }
  const nameOf=code=>{const n=STOCKNAME[code]||STOCKNAME_US[code]||LITE_NAME[code];if(n){_nameRemember(code,n);return n}return NAME_SAVED[code]||code};
  // 2026-08-24 新增：手動「重新整理」按鈕用——清掉全部 FinMind 快取（記憶體＋localStorage），
  // 讓接下來的 hydrateXxx() 重新真的打一次 API，不要停在 3 分鐘內的舊快取。
  function fmClearCache(){
    Object.keys(_cache).forEach(k=>delete _cache[k]);
    try{Object.keys(localStorage).filter(k=>k.startsWith('fmc_')).forEach(k=>localStorage.removeItem(k))}catch(e){console.warn('[fmClearCache]',e);recordGlobalError('fmClearCache',e)}
  }
  // 2026-08-24 新增：畫面上「最後更新：HH:MM」的共用函式，標的是「瀏覽器這次實際刷新畫面的時間」，
  // 不是資料本身的交易日（那個各卡片自己的 date 欄位已經有顯示）。
  function stampUpdated(scr){
    const el=document.getElementById(scr+'-updated-tm');if(!el)return;
    // 2026-08-28修正（P0-a，第6次時鐘問題的真正根因）：原本用
    // t.getHours()/getMinutes()依賴裝置本地時區，這支函式從2026-08-24
    // 就存在、是「最後更新」欄位真正的驅動來源（hydrateHome()/
    // hydrateMarket()資料重新整理完成時都會呼叫），比昨晚新增的
    // refreshTap()疊加寫入還早、更根本。改用fmtTzHHMM()明確指定
    // Asia/Taipei。
    el.textContent=fmtTzHHMM(new Date(),'Asia/Taipei');
  }
  // 2026-08-25 修正：資料卡在舊日期不更新的另一半根因（另一半在 sw.js）——這裡原本
  // fetch 失敗時會「改用舊快取」（fmCacheStale，沒有任何新鮮度限制，可能是好幾天前
  // 存的），畫面看起來正常但其實是舊資料，使用者無從分辨。改成：失敗就是失敗，不
  // 回退舊資料，回傳空陣列讓呼叫端顯示「查無資料」的同時，設 FM_LAST_FAILED=true，
  // 讓呼叫端可以用 fmEmptyMsg() 分辨「這次是連線失敗」還是「這檔本來就沒資料」。
  let FM_LAST_FAILED=false;
  // 先.八十一-10：FinMind 失敗時記下白話原因（額度用盡／網路／逾時…），fmEmptyMsg 一併顯示，不只顯示「—」。
  let FM_LAST_ERR='';
  // 先.八十一-10：把 FinMind 失敗翻成白話原因（先.八十一-19 移到核心 app.js：首頁搜尋補查也要用，app-shared.js 未必已載入）
  function fmErrReason(e){
    const m=String((e&&e.message)||e||'');
    if(/HTTP 402/.test(m))return 'FinMind 免費額度用盡（HTTP 402），約一小時後恢復';
    if(/HTTP 429/.test(m))return 'FinMind 請求太頻繁（HTTP 429）';
    if(/HTTP 5\d\d/.test(m))return 'FinMind 伺服器錯誤（'+m+'）';
    if(/HTTP \d+/.test(m))return 'FinMind 回應錯誤（'+m+'）';
    if(e&&e.name==='AbortError')return 'FinMind 逾時沒有回應';
    if(e&&e.name==='TypeError')return 'FinMind 連不上（網路中斷或被擋）';
    return 'FinMind 失敗（'+(m||'原因不明')+'）';
  }
  // 2026-08-25 修正：原本線的顏色是看「這段sparkline最後一天vs第一天」（多日趨勢），
  // 跟旁邊直接顯示的「今日漲跌%」徽章是兩個不同的比較基準，兩者顏色常常對不上
  // （例如過去9天總體是漲的、但今天是跌的，線會畫成漲色、徽章卻是跌色），使用者
  // 實機截圖就是這個情況。改成外部明確傳入「今日漲跌」的布林值，跟徽章保證一致。
  function spark(cl,up){if(cl.length<2)return '';const mn=Math.min(...cl),mx=Math.max(...cl),rg=(mx-mn)||1;
    const pts=cl.map((c,i)=>`${(i/(cl.length-1)*64).toFixed(1)},${(24-(c-mn)/rg*20+1).toFixed(1)}`).join(' ');
    return `<svg class="spark" width="64" height="26" viewBox="0 0 64 26" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="var(--${up?'up':'down'})" stroke-width="2"/></svg>`}

  // ══════ 策略 vs 0050（2026-10-11 先.六十八，取代 2026-09-15「我們 vs 0050」）══════
  // 資料：data/strategy_curves.json（.github/scripts/build_strategy_curves.py 每日產生；選股三榜改用重疊組合法，
  // 舊卡「依序串接複利」把重疊的 5 日報酬串接、誤放大約 5 倍，已刪除）＋本機 /auto/strategy_line（真錢 Bb-90，
  // 帳本只在本機）。每條線從自己的起始日歸一為 100，灰線為同期 0050；指標與「金礦判讀」都由 Python 端同一支
  // metrics() 算好，這裡只畫——判讀文字是固定規則（<60 日「尚不足以判斷」），前端不自行產生任何推論文字。
  // 先.七十三（2026-10-11）：「全部疊加」排第一且為預設；其後 自動投資、模擬 A～F（先.九十一-1 加 F）、選股榜單。內部 id 不變。
  let SC_DATA=null,SC_LIVE=null,SC_LIVE_ERR='',SC_TAB='all',SC_BOARD='value';
  const SC_TABS=[['all','全部疊加'],['live','自動投資'],['paper_1','模擬 A'],['paper_3','模擬 B'],['paper_4','模擬 C'],
    ['paper_1b','模擬 D'],['paper_2','模擬 E'],['paper_5','模擬 F'],['boards','選股榜單']];
  const SC_BOARDS=[['value','估值'],['momentum','動能'],['future','未來']];
  // 每條線固定顏色（疊圖與單線圖一致）；0050 固定灰色
  const SC_COLOR_BY={live_bb90:'#2f81f7',paper_1:'#d4a017',paper_3:'#3fb950',paper_4:'#db61a2',paper_1b:'#f0883e',paper_2:'#a371f7',paper_5:'#79c0ff',
    board_value:'#56d4dd',board_momentum:'#e5534b',board_future:'#b5d334'};
  const SC_BENCH_COLOR='#8b8b8b';
  const scColor=id=>SC_COLOR_BY[id]||'#9e9e9e';
  let SC_PLOT=null;  // 目前畫面上那張圖的資料（按住圖顯示當日數值用）
  async function loadStrategyCurves(){
    try{
      const r=await fetch('data/strategy_curves.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      SC_DATA=await r.json();
    }catch(e){console.warn('[loadStrategyCurves]',e);recordGlobalError('loadStrategyCurves',e);SC_DATA=null}
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
    if(!SC_DATA||!SC_DATA.lines){bodyEl.innerHTML='<div class="note" style="color:var(--ink-3)">策略曲線資料尚未產生</div>';tabsEl.innerHTML='';return}
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
  // ── 2026-09-04（四修.三）走勢線二選一：連上即時且該檔有當日1分K→畫「今日走勢」（隨盤中變動）；
  // 否則退回既有近20日日線並標「20日」。標籤永遠顯示，使用者一眼分得出是今日還是20日。
  const LIVE_KB={};  // code -> {at, closes:[...], lastT}
  // ── 2026-09-05（總司令「零」）全市場走勢線：data/sparklines.json（每檔近20收盤，約286KB）
  // 由 build_sparklines.py 從 price_history.json 切出（零額外網路請求）。取代舊的「逐檔打
  // TWSE STOCK_DAY」：舊法只有清單內的上市股有線、上櫃股完全沒有、一次抓不完還會被限流打斷。
  // 現在任何頁面、任何新加入的自選股，只要在全市場歷史裡就立刻有線。
  let SPARKLINES=null,SPARKLINES_AT=0,SPARKLINES_ASOF=null,SPARKLINES_STALE_DATES={};
  // 常備.開發-20（2026-10-11）：首頁 loadHomeIndex 與 hydrateHome 同時呼叫，原本會下載兩次
  // （gzip 約 112KB×2）；改成進行中的呼叫共用同一個 Promise。
  let SPARKLINES_INFLIGHT=null;
  // 常備.開發-20（先.六十七）：SPARKLINES 可能只裝了首頁小檔（ensureQuoteLite）合併進來的幾檔，
  // 所以「整份已載入」另用旗標判斷，不能只看 SPARKLINES 有沒有值。
  let SPARKLINES_FULL=false;
  function ensureSparklines(){
    if(SPARKLINES_FULL&&SPARKLINES&&Date.now()-SPARKLINES_AT<10*60*1000)return Promise.resolve(SPARKLINES);
    if(!SPARKLINES_INFLIGHT)SPARKLINES_INFLIGHT=_ensureSparklinesImpl().finally(()=>{SPARKLINES_INFLIGHT=null});
    return SPARKLINES_INFLIGHT;
  }
  async function _ensureSparklinesImpl(){
    try{
      const r=await fetch('data/sparklines.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      // 2026-09-15（總司令裁示，sparklines凍結事件）：這份檔案整批共用同一個
      // data_asof（build_sparklines.py每次整批重切，不是逐檔各自的時間戳），
      // 之前只取.sparklines丟掉.meta，害resolveQuote()第四層(history)永遠回傳
      // asof:null——sparklines.json卡在09-05不更新那十天，使用者看到的舊價格
      // 完全沒有任何日期標示，跟看到當天的價格長得一模一樣。現在存下來，
      // resolveQuote()才能誠實標出「這個數字是哪天的」。
      // 2026-09-17（稽核.四.1修正版(a)）：新增stale_dates——build_sparklines.py
      // 不再整批排除落後大盤最大日期的股票，改逐檔記在這裡（code→實際最後一天
      // 日期），沒出現代表跟data_asof同一天。
      SPARKLINES=d.sparklines||{};SPARKLINES_ASOF=(d.meta&&d.meta.data_asof)||null;
      SPARKLINES_STALE_DATES=d.stale_dates||{};SPARKLINES_AT=Date.now();SPARKLINES_FULL=true;
    }catch(e){console.warn('[ensureSparklines]',e);recordGlobalError('ensureSparklines',e);if(!SPARKLINES)SPARKLINES={}}
    return SPARKLINES;
  }
  function sparkFor(code){return (SPARKLINES&&SPARKLINES[code])||null}
  // ── 常備.開發-20（2026-10-11 先.六十七）首頁小檔 data/quote_lite/{代號}.json ──────────
  // 首頁自選股列與加權指數膠囊只需要十幾檔的走勢線＋全市場收盤＋名稱，不再為此下載整份
  // sparklines.json（gzip 約 112KB）、quotes_all_tw.json（約 51KB）、company_info.json（約 73KB）。
  // 小檔由 scripts/split_quote_lite.py 從那三份檔原樣切出（同一步驟產生，日期一致），
  // 合併進 SPARKLINES／QUOTES_ALL_TW_CACHE／LITE_NAME，resolveQuote() 四層回退鏈完全不用改。
  // 退路：小檔整批抓不到（非 404 的錯誤，或要的代號全部 404＝小檔目錄不存在）→ 改抓整份檔，行為同改版前。
  // 某一檔單檔與分片都沒有＝三份來源都沒有這一檔，整份檔裡也不會有，照原本「無報價」處理。
  const QUOTE_LITE_INDEX=new Set(['TAIEX','TPEx']);  // 英文字母開頭但屬台股指數、在 sparklines 裡有線的代號
  const QUOTE_LITE_AT={};  // code -> 抓取時間（10 分鐘內不重抓，與 ensureSparklines 一致）
  async function ensureQuoteLite(codes){
    const want=[...new Set((codes||[]).filter(c=>c&&(!isUS(c)||QUOTE_LITE_INDEX.has(c))))]
      .filter(c=>!(QUOTE_LITE_AT[c]&&Date.now()-QUOTE_LITE_AT[c]<10*60*1000));
    if(!want.length)return;
    if(SPARKLINES_FULL&&QUOTES_ALL_TW_FULL&&Date.now()-SPARKLINES_AT<10*60*1000)return;
    // 先.六十九-3：兩層。熱門代號（自選股／Bb-90 白名單／指數／近 30 日進榜）有單檔；其餘合併在
    // data/quote_lite/p/{前兩碼}.json（00 開頭用前三碼）。單檔 404 → 改抓所屬分片（同一次呼叫內同一分片只抓一次）。
    const tb=Math.floor(Date.now()/60000),shardP={};
    const shardOf=c=>{const k=/^00/.test(c)?c.slice(0,3):c.slice(0,2);
      return shardP[k]||(shardP[k]=fetch('data/quote_lite/p/'+encodeURIComponent(k)+'.json?t='+tb).then(r=>{if(r.status===404)return {};if(!r.ok)throw new Error('分片 '+k+' HTTP '+r.status);return r.json()}))};
    const res=await Promise.allSettled(want.map(c=>fetch('data/quote_lite/'+encodeURIComponent(c)+'.json?t='+tb)
      .then(r=>{if(r.status===404)return shardOf(c).then(sh=>sh&&sh[c]?{code:c,d:sh[c]}:{code:c,miss:true});if(!r.ok)throw new Error(c+' HTTP '+r.status);return r.json().then(d=>({code:c,d}))})));
    let hardFail=0,miss=0,offFail=0;
    const saved=_qlSavedRead();
    for(let i=0;i<res.length;i++){
      const x=res[i];
      if(x.status==='rejected'){
        // 先.九十五-R1①③：斷網抓不到 → 用上次存在本機的小檔頂上（只有自選股與指數有存），不算程式錯誤
        const off=_isOfflineErr(x.reason)||navigator.onLine===false;
        if(off)offFail++;else console.warn('[ensureQuoteLite]',x.reason);
        hardFail++;
        const c=want[i];
        if(off&&saved[c]){try{_qlApply(c,saved[c])}catch(e){console.warn('[ensureQuoteLite:saved]',c,e)}}
        continue}
      const {code,d}=x.value;QUOTE_LITE_AT[code]=Date.now();
      if(x.value.miss){miss++;continue}
      try{
        if(WL.includes(code)||QUOTE_LITE_INDEX.has(code))saved[code]=d;
        _qlApply(code,d);
      }catch(e){hardFail++;console.warn('[ensureQuoteLite:merge]',code,e)}
    }
    _qlSavedWrite(saved);
    if(hardFail||(miss&&miss===want.length)){
      const why=hardFail?`${hardFail} 檔抓取失敗`:`要的 ${want.length} 檔全部 404（小檔目錄可能不存在）`;
      if(hardFail&&offFail===hardFail){console.info('[ensureQuoteLite] 離線：'+why+'，已用本機存檔頂上（不計程式錯誤）');return}
      console.warn('[ensureQuoteLite] 小檔不可用，改抓整份 sparklines／quotes_all_tw：'+why);
      recordGlobalError('ensureQuoteLite',new Error(why+'，已改抓整份檔'));
      await Promise.allSettled([ensureSparklines(),loadQuotesAllTw()]);
    }
  }
  // 先.九十五-R1①：自選股／指數的小檔（走勢線、收盤、名稱、資料日）另存本機 alpha_quote_lite_saved，斷網時頂上；
  // 小檔本身帶 asof／sd 資料日，卡片照常標日期，不會冒充即時。
  const QL_SAVED_KEY='alpha_quote_lite_saved';
  function _qlSavedRead(){try{return JSON.parse(localStorage.getItem(QL_SAVED_KEY))||{}}catch(e){console.warn('[qlSavedRead]',e);return {}}}
  function _qlSavedWrite(o){
    try{const keep={};for(const k of Object.keys(o))if(WL.includes(k)||QUOTE_LITE_INDEX.has(k))keep[k]=o[k];localStorage.setItem(QL_SAVED_KEY,JSON.stringify(keep))}
    catch(e){console.warn('[qlSavedWrite]',e)}
  }
  function _qlApply(code,d){
    if(!SPARKLINES_FULL){
      SPARKLINES=SPARKLINES||{};
      if(Array.isArray(d.s))SPARKLINES[code]=d.s;
      if(d.sd)SPARKLINES_STALE_DATES[code]=d.sd;else delete SPARKLINES_STALE_DATES[code];
      if(d.asof)SPARKLINES_ASOF=d.asof;
    }
    if(!QUOTES_ALL_TW_FULL){
      QUOTES_ALL_TW_CACHE=QUOTES_ALL_TW_CACHE||{quotes:{}};
      if(d.a)QUOTES_ALL_TW_CACHE.quotes[code]=d.a;
    }
    if(d.n)LITE_NAME[code]=d.n;
  }
  // ── 2026-09-06（實測.二）當日 1 分K ────────────────────────────────────────
  // 兩點改動：
  //  1. 不再要求 SSE 已連線。`/live/kbars` 現在對未訂閱的代號會在常駐行程的同一條
  //     Shioaji 連線上呼叫 api.kbars() 查詢（伺服器端快取 60 秒），只要 live server
  //     連得上就查得到，不必等那一檔先被訂閱、也不必等串流建立。
  //  2. 兩種 bar 形狀都收：tick 聚合來的是 {t, c}，api.kbars() 查來的是
  //     {ts, close, volume}。只認一種的話換了來源就整條線消失。
  function _barClose(b){return b==null?null:(b.c!=null?b.c:(b.close!=null?b.close:null))}
  function _barTime(b){return b==null?null:(b.t!=null?b.t:(b.ts!=null?b.ts:null))}
  async function getLiveCloses(code){
    if(!LIVE.configured)return null;
    const c=LIVE_KB[code];
    if(c&&Date.now()-c.at<60000)return c.closes;
    try{
      const r=await liveFetch('/live/kbars?code='+encodeURIComponent(code),9000);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const bars=d.bars||[];
      LIVE_KB[code]={at:Date.now(),
                     closes:bars.map(_barClose).filter(x=>x!=null),
                     lastT:bars.length?_barTime(bars[bars.length-1]):null,
                     tradeDate:d.trade_date||null,
                     mode:d.mode||null};
      return LIVE_KB[code].closes;
    }
    catch(e){
      // 查不到是常態（live server 沒開、或那一檔今天真的沒成交），走勢線退回 20 日
      // 日線即可，不記進診斷橫幅——那會被伺服器沒開的日子灌爆。
      console.warn('[getLiveCloses]',code,e.message||e);
      LIVE_KB[code]={at:Date.now(),closes:[],lastT:null,tradeDate:null,mode:null};
      return [];
    }
  }
  // 串流每個事件帶kbars_last：把最新一根K併進快取（同一分鐘就取代最後一點、新的一分鐘就append），
  // 不必每次重新打/live/kbars。
  function mergeLiveKbarsLast(){
    const kl=LIVE.kbarsLast||{};
    Object.keys(kl).forEach(code=>{const c=LIVE_KB[code];if(!c)return;const b=kl[code];if(!b||b.c==null)return;
      const bc=_barClose(b),bt=_barTime(b);
      if(bc==null)return;
      if(c.lastT===bt){if(c.closes.length)c.closes[c.closes.length-1]=bc}else{c.closes.push(bc);c.lastT=bt}});
  }
  function sparkWithTag(closes,up,tag){const s=spark(closes,up);if(!s)return '<span class="sparkwrap"></span>';return `<span class="sparkwrap">${s}<em>${tag}</em></span>`}
  // 2026-09-06（實測.二.2）當日曲線專用：**以前收為基線**，不是 min-max 拉滿。
  // 差別很實際：min-max 會把「今天只動了 0.3%」畫成一條劇烈起伏的線，看起來像
  // 大漲大跌；以前收當基準線之後，線離基準多遠就是真的漲跌多少，而且線在基準
  // 之上是紅、之下是綠，跟旁邊的漲跌幅顏色一定一致。
  function sparkBaseline(closes,prevClose){
    if(!closes||closes.length<2)return '';
    const W=64,H=26,PAD=3;
    const vals=closes.filter(v=>v!=null&&isFinite(v));
    if(vals.length<2)return '';
    const base=(prevClose!=null&&isFinite(prevClose))?prevClose:vals[0];
    // 讓基線一定落在畫面內，且上下對稱——否則基線貼著邊，看不出「離基準多遠」
    const span=Math.max(Math.abs(Math.max(...vals)-base),Math.abs(Math.min(...vals)-base))||(base*0.001)||1;
    const y=v=>{const t=(v-base)/(span*2)+0.5;return (H-PAD-t*(H-PAD*2)).toFixed(1)};
    const pts=vals.map((v,i)=>`${(i/(vals.length-1)*W).toFixed(1)},${y(v)}`).join(' ');
    const last=vals[vals.length-1];
    const up=last>=base;
    const baseY=y(base);
    return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`
      +`<line x1="0" y1="${baseY}" x2="${W}" y2="${baseY}" stroke="var(--ink-4)" stroke-width="1" stroke-dasharray="2 2" opacity=".55"/>`
      +`<polyline points="${pts}" fill="none" stroke="var(--${up?'up':'down'})" stroke-width="2" stroke-linejoin="round"/>`
      +`</svg>`;
  }
  // 當日曲線的標籤：今天就寫「今日」，隔日開盤前顯示的是前一交易日，就直接標日期。
  function intradayTagText(code){
    const c=LIVE_KB[code];
    const d=c&&c.tradeDate?String(c.tradeDate):null;
    if(!d)return '今日';
    const today=(()=>{const z=_zonedParts(new Date(),'Asia/Taipei');return `${z.y}-${String(z.m).padStart(2,'0')}-${String(z.d).padStart(2,'0')}`})();
    return d===today?'今日':d.slice(5);
  }
  const SPARK_PLACEHOLDER='<span class="sparkwrap"></span>';  // 沒線也留同寬空位，每列一樣高、欄位不位移
  // 回傳{html,mode}：mode='today'(即時1分K)/'20d'/''(無)
  function rowSparkline(code,fallback20d,up,prevClose){
    // 2026-09-06（實測.二.2）當日 1 分K 優先，且以前收為基線。
    // 不再要求 LIVE.connected——只要 /live/kbars 查得到（含未訂閱代號走 api.kbars()）
    // 就畫當日曲線；查不到才退回 20 日日線並照舊標「20日」。
    const kb=LIVE_KB[code];
    if(kb&&kb.closes&&kb.closes.length>=2){
      const html=sparkBaseline(kb.closes,prevClose);
      if(html)return {html:`<span class="sparkwrap">${html}<em>${intradayTagText(code)}</em></span>`,mode:'today'};
    }
    // 2026-09-05：優先用全市場 sparklines.json（涵蓋上市＋上櫃約2827檔）；
    // fallback20d 是 quotes_tw.json 裡的舊欄位，留著當它還在時的備援，之後會整個消失。
    const marketWide=sparkFor(code);
    const closes=(marketWide&&marketWide.length>=2)?marketWide:((fallback20d&&fallback20d.length>=2)?fallback20d:null);
    if(closes)return {html:sparkWithTag(closes,up,'20日'),mode:'20d'};
    return {html:SPARK_PLACEHOLDER,mode:''};
  }

  // 2026-09-02新增（使用者裁示「誠實標示：每個報價旁加badge『即時/延遲~15分/
  // 盤後』，美股IBKR paper一律標延遲，不得偽裝即時」）：統一的資料新鮮度badge
  // 文字對照表，供所有顯示報價來源的地方共用，避免各處各寫一套、字眼不一致。
  // 沿用IBKR/Shioaji既有回報的data_type字串（見ibkr_quotes.py/shioaji_quotes.py
  // 的MARKET_DATA_TYPE_LABEL），不自己發明新分類。
  function intradayDataTypeLabel(dt){
    // 2026-09-03新增：Shioaji從輪詢快照(REALTIME)升級成逐筆tick訂閱(B34)，
    // 新的data_type值刻意跟舊的分開標示，讓使用者看得出來這是真的逐筆
    // 進來的還是舊版的定期快照（見research/shioaji_quotes.py模組docstring）。
    if(dt==='REALTIME_TICK')return '即時(tick)';
    if(dt==='REALTIME')return '即時';
    if(dt==='DELAYED')return '延遲~15分';
    if(dt==='YAHOO_DELAYED')return 'Yahoo延遲~15分';
    if(dt==='FROZEN'||dt==='DELAYED_FROZEN')return '盤後';
    return dt||'未知';
  }
  // 有近即時報價（20分鐘內）就優先用它顯示，並標「盤中 延遲約N分」；沒有就照舊用FinMind
  // 日線，不會因為加了這個功能反而讓沒有近即時資料的股票顯示變差。
  // 2026-09-08（實測.七）**回傳結構化物件 {text,color}，不再回傳 HTML 字串。**
  // 這是總司令實測抓到的 bug：原本回傳 `<span ...>` HTML，但兩個呼叫點
  // （3748 美股 IBKR、3803 台股 Shioaji）用 setTxt() → el.textContent，
  // HTML 被當成純文字整串印在畫面上，**個股頁的資料新鮮度提示長期是壞的**。
  // 根本原因是同一個函式同時服務 HTML 與 textContent 兩種情境，
  // 光修呼叫端只是把地雷往後推——**改成回傳資料而非標記，這類錯配就不可能再發生**。
  // 需要樣式的呼叫端自己組 span（見 intradayTagHtml()）。
  function intradayTag(iq,us){
    if(!iq)return null;
    if(iq.source==='ibkr'||iq.source==='sinopac'){
      const label=iq.source==='ibkr'?'IBKR':'Shioaji';
      // 2026-09-03新增：收盤後但資料確實是今天的（見ibkrQuote()/sinopacQuote()
      // 的isTodayClose判斷），標「今日收盤」+資料時間戳，不再顯示「約N分前」
      // 這種暗示「盤中即時」的措辭（收盤後過了幾小時，講「N分前」會誤導）。
      if(iq.isTodayClose){
        const tz=iq.source==='ibkr'?'America/New_York':'Asia/Taipei';
        const src=iq.source==='ibkr'?INTRADAY_IBKR:INTRADAY_SINOPAC;
        const ts=src&&src.fetched_at?fmtTzHHMM(new Date(src.fetched_at),tz):'';
        return {text:`· ${label} 今日收盤${ts?' '+ts:''}`,color:'var(--ink-3)'};
      }
      const mins=Math.max(1,Math.round(iq.ageMin));
      return {text:`· ${label} ${intradayDataTypeLabel(iq.dataType)} 約${mins}分前`,color:'var(--warn)'};
    }
    const mins=Math.max(1,Math.round(iq.ageMin));
    // 2026-09-04 P0緊急回歸修正：13:30後不得出現「盤中」——依該市場現在的session顯示
    const open=us===true?isUsTradingWindowNow():(us===false?isTwTradingWindowNow():(isTwTradingWindowNow()||isUsTradingWindowNow()));
    if(!open)return {text:`· 已收盤 · Actions 最後一筆 約${mins}分前`,color:'var(--ink-3)'};
    return {text:`· 盤中 延遲約${mins}分(GitHub Actions)`,color:'var(--warn)'};
  }
  // 2026-09-08（實測.七）需要樣式的地方用這支，需要純文字的直接取 .text
  function intradayTagHtml(iq,us){
    const t=intradayTag(iq,us);
    if(!t)return '';
    return `<span style="color:${t.color};margin-left:4px">${t.text}</span>`;
  }
  function intradayTagText(iq,us){
    const t=intradayTag(iq,us);
    return t?t.text:'';
  }
  const WL_DETAIL_OPEN=new Set();
  function toggleWlDetail(code){const d=document.querySelector(`[data-wl-detail="${code}"]`);if(!d)return;const open=d.hidden;d.hidden=!open;if(open)WL_DETAIL_OPEN.add(code);else WL_DETAIL_OPEN.delete(code)}
  let HYDRATE_HOME_SEQ=0;
  // 先.八十一-7（常備.開發-20 第三招）：首頁下方卡片捲到才載。#home-lazy-sentinel 真的進入畫面時才執行（不預留邊界：實測哨兵在首屏下緣 23px，預留 300px 等於沒有延後）；
  // 同一個名稱只排一次，已執行過就直接再跑（例如重新整理首頁）。不支援 IntersectionObserver 的瀏覽器直接執行。
  // uiLoadLazyAll()：立刻把排隊中的全部執行（冒煙測試開頁後呼叫一次，讓既有檢查照常看得到資料）。
  const UI_LAZY={q:new Map(),seen:false,obs:null,armed:false};
  function uiLazyHome(name,fn){
    if(UI_LAZY.seen||typeof IntersectionObserver==='undefined'){_safeAsync(name,fn);return}
    UI_LAZY.q.set(name,fn);
    if(UI_LAZY.armed)return;
    UI_LAZY.armed=true;
    const s=document.getElementById('home-lazy-sentinel');
    if(!s){uiLoadLazyAll();return}
    // 頁面剛開時卡片還沒長出來，哨兵會短暫出現在畫面裡、之後才被推到下方——所以不在開頁當下判斷：
    // ①捲動時（capture：首頁可能在內層容器捲動）只要哨兵頂端已在畫面下緣之上（捲到或捲過）就載入——直接跳過哨兵也算
    // ②版面穩定（2 秒）後哨兵本來就在畫面裡（例如很高的桌機視窗）就直接載入
    let tick=false;
    const onScroll=()=>{if(tick||UI_LAZY.seen)return;tick=true;requestAnimationFrame(()=>{tick=false;
      try{if(!UI_LAZY.seen&&s.getBoundingClientRect().top<innerHeight){document.removeEventListener('scroll',onScroll,true);uiLoadLazyAll()}}catch(e){console.warn('[uiLazyHome:scroll]',e)}})};
    document.addEventListener('scroll',onScroll,{passive:true,capture:true});
    setTimeout(()=>{try{if(!UI_LAZY.seen&&s.getBoundingClientRect().top<innerHeight)uiLoadLazyAll()}catch(e){console.warn('[uiLazyHome:settle]',e)}},2000);
  }
  function uiLoadLazyAll(){
    UI_LAZY.seen=true;
    if(UI_LAZY.obs){UI_LAZY.obs.disconnect();UI_LAZY.obs=null}
    const q=[...UI_LAZY.q];UI_LAZY.q.clear();
    q.forEach(([n,f])=>_safeAsync(n,f));
  }
  window.uiLoadLazyAll=uiLoadLazyAll;
  async function hydrateHome(){
    _safeSync('renderWLTabs',renderWLTabs);  // 常備.開發-8
    const el=document.getElementById('wl-list');if(!el)return;
    // 2026-09-04 P0產品.一修正：初次載入與即時重繪可能同時執行，兩個迴圈會把列塞進同一個容器
    // 造成自選股重複出現。改成每次執行拿一個序號、列先組進fragment，最後只有「最新那次」才整批替換。
    const runId=++HYDRATE_HOME_SEQ;
    const frag=document.createDocumentFragment();
    // 常備.開發-20（先.六十七）：自選股小檔（走勢線＋全市場收盤＋名稱）與名稱清單同時抓
    const liteP=ensureQuoteLite(WL).catch(e=>{console.warn('[hydrateHome:ensureQuoteLite]',e);recordGlobalError('hydrateHome:ensureQuoteLite',e)});
    try{await loadStockInfo({lite:true})}catch(e){console.warn('[hydrateHome:loadStockInfo]',e);recordGlobalError('hydrateHome:loadStockInfo',e)}
    await liteP;
    if(runId!==HYDRATE_HOME_SEQ)return;
    _safeAsync('loadHomeIndex',loadHomeIndex);
    _safeAsync('loadTodayEvents',loadTodayEvents);
    _safeAsync('loadHomeBrief',loadHomeBrief);  // 常備.開發-2 盤前日報（規則摘要）
    uiLazyHome('loadMyHoldingsEvents',loadMyHoldingsEvents);  // 2026-09-15 開發佇列自走；先.八十一-7 捲到才載
    _safeAsync('loadAutoTrading',loadAutoTrading);
    // 先.八十一-7：破億試算在設定頁，設定頁 hydrateSettings 自己會呼叫 renderBtPath，首頁不再提早抓 strategy_history
    _safeAsync('loadHomeExecCard',loadHomeExecCard);  // 常備.開發-11 真錢執行總覽卡（唯讀）
    _safeAsync('loadHomeBrokerCard',loadHomeBrokerCard);  // 2026-09-15 開發佇列自走，週六.五：總資產卡吃/live/positions+/live/balance真數字
    uiLazyHome('loadStrategyCurves',async()=>{await Promise.allSettled([loadStrategyCurves(),loadStrategyHistory()]);renderStrategyCurves()});  // 先.六十八；先.八十一-7 捲到才載
    await loadIntradayQuotes();
    if(!WL.length){el.innerHTML='<div class="note" style="padding:14px 2px">尚無自選股，點右上「管理」搜尋加入</div>';return}
    // 2026-09-06（實測.一）三份檔案一起備妥再畫：sparklines（走勢線＋回退鏈最後一層）、
    // quotes_all_tw（全市場 2,837 檔收盤，回退鏈第三層）、listed_universe（分辨真的
    // 下市還是我們沒接好）。用 allSettled，任一份失敗只是少一層，不能讓整個首頁不畫。
    // 常備.開發-20（先.六十七）：sparklines／quotes_all_tw 改由上面 ensureQuoteLite 只抓自選股各自的小檔（已在名稱前備妥）
    await Promise.allSettled([ensureQuoteLite(WL),ensureListedUniverse()]);
    // 2026-09-06（實測.二）改成 LIVE.configured：當日曲線現在不需要 SSE 已連線，
    // /live/kbars 對未訂閱代號會走 api.kbars() 查詢，只要 live server 連得上就有線。
    if(LIVE.configured){mergeLiveKbarsLast();await Promise.allSettled(WL.filter(c=>!isUS(c)).map(getLiveCloses))}  // 2026-09-04四修.三
    if(runId!==HYDRATE_HOME_SEQ)return;
    let showedExtendedHours=false; // 2026-08-27新增：只要有任一列顯示了盤前/盤後價，就顯示風險揭露
    const earningsCal=await loadEarningsCalendar(); // 2026-08-27新增（P2-新，財報行事曆）
    if(runId!==HYDRATE_HOME_SEQ)return;
    for(const code of WL){
      const nm=nameOf(code);const us=isUS(code);
      const wrap=document.createElement('div');wrap.className='swipe-wrap';
      wrap.innerHTML=`<button class="swipe-del" data-code="${code}"><span>✕</span>刪除</button><div class="swipe-row"><div class="nm"><b>${nm}</b><span>${code} · 載入中…</span></div></div>`;
      frag.appendChild(wrap);
      const rowEl=wrap.querySelector('.swipe-row');
      attachSwipe(rowEl,code);
      wrap.querySelector('.swipe-del').onclick=()=>confirmDelete(code);
      // 2026-08-27 架構修正：sparkline改讀 data/quotes_tw.json/quotes_us.json
      // 本身附帶的近20日收盤序列（見 fetch_quotes_tw.py::fetch_sparkline_20d /
      // fetch_quotes_us.py 的yfinance批次），不再對FinMind打
      // TaiwanStockPrice/USStockPrice——這是STATUS.json列的最後一個P0缺口。
      // rawQ跟iq分開：iq在資料過舊(>20分鐘)時會是null（避免拿舊價格假裝即時），
      // 但sparkline是日線、不需要這麼嚴格的新鮮度，所以sparkline/備援價格改用
      // rawQ（不管新不新鮮都給，跟原本FinMind退回邏輯精神一致）。
      // 2026-09-06（實測.一）改吃統一的四層回退鏈。原本只查 quotes_tw.json（Actions
      // 只抓前 210 檔），新增的自選股只要不在那份清單裡就直接顯示「無報價」，
      // 但那些股票在 quotes_all_tw.json（2,837 檔）與 sparklines.json 裡都有價格。
      const q=resolveQuote(code,us);
      const iq=(q&&q.tier==='live')?q:null;
      const rawQ=q;
      if(!q){rowEl.innerHTML=`<div class="nm"><b>${nm}</b><span>${code}${us?' · 美股':''} · ${noQuoteLabel(code,us)}</span></div>${SPARK_PLACEHOLDER}<div class="px"><b>—</b></div>`;continue}
      const price=q.price;
      const chg=q.change??0;
      const pct=q.change_pct??0;
      const cls=chg>=0?'u':'d';
      // 2026-09-15（sparklines凍結事件，總司令裁示「過期可以用，但不准假裝是當前的」）：
      // 四層回退鏈走到最後一層(history/sparklines)時，若資料已經超過3個交易日沒更新，
      // 價格數字本身要直接標日期，不能只靠可展開的小字說明——那個說明預設收合，
      // 使用者不點開根本看不到。跟財報過期同一套原則（見live_factors.py新鮮度檢查）。
      // 2026-09-17（稽核.四.1修正版(a)）：加上q.is_stale——這是資料層（quotes_all_tw/
      // sparklines）自己標的「落後大盤當日最大日期」旗標，即使只差1天也算（不是
      // 上面那個3個交易日的寬鬆門檻），總司令原話「不准把落後一天的收盤當現價顯示」，
      // 兩個條件任一成立就視為過期，不得只用「即時/現價」字樣呈現。
      const histStaleDays=(q.tier==='history')?tradingDaysSince(q.asof,'Asia/Taipei',TW_HOLIDAYS):null;
      // 先.八十一-24：台股盤中（交易時段內）若只拿得到「前一交易日以前」的收盤（全市場盤後檔／歷史層），同樣標日期、
      // 不顯示漲跌%——那是昨天的漲跌，不是今天的（10/13 上午排程沒跑時就是這個情況）。
      const _twToday=(()=>{const z=_zonedParts(new Date(),'Asia/Taipei');return _ymd(z)})();
      const oldCloseInSession=!us&&q.tier!=='live'&&q.tier!=='quotes'&&isTwTradingWindowNow()&&!!q.asof&&String(q.asof).slice(0,10)<_twToday;
      const priceIsStale=(histStaleDays!=null&&histStaleDays>3)||q.is_stale===true||oldCloseInSession;
      const priceLabel=priceIsStale
        ?`${q.asof?String(q.asof).slice(5).replace('-','/'):'?'}收盤 ${us?'$':''}${nf(price)}`
        :`${us?'$':''}${nf(price)}`;
      // 總司令原話：「漲跌% 若是拿舊日期算出來的，一律不顯示（不是顯示0，是不顯示）」。
      const pctTagHtml=priceIsStale?'':`<span class="chg-tag ${cls}">${chg>=0?'+':''}${pct.toFixed(2)}%</span>`;
      // 2026-09-04 P0產品.一：來源/新鮮度文字收進可展開的說明，列上只留一顆彩色小點
      // 每一層講自己的話：不能把「三天前的歷史收盤」講成「已收盤（Actions排程最後一筆）」
      const srcText=iq?`${intradayTagHtml(iq,us)||'· 近即時（Actions排程）'}`
        :('· '+(QUOTE_TIER_LABEL[q.tier]||'盤後')+(q.asof?('（'+String(q.asof).slice(5)+'）'):''));
      const mktOpenNow=us?isUsTradingWindowNow():isTwTradingWindowNow();
      const dotCls=!mktOpenNow?'gr':((iq&&(iq.source==='sinopac'||iq.source==='ibkr')&&!iq.isTodayClose&&/REALTIME/.test(iq.data_type||''))?'g':(iq&&!iq.isTodayClose?'y':'gr'));
      const meta=`${code}${us?' · 美股':''}<span class="sdot ${dotCls} wl-src-dot" data-wl-dot="${code}" title="點一下看資料來源" onclick="event.stopPropagation();toggleWlDetail('${code}')"></span>`;
      const sp=rowSparkline(code,rawQ&&rawQ.sparkline,chg>=0,q.prev_close).html;  // 2026-09-06實測.二：當日曲線（前收基線）→ 退回20日
      // 2026-09-06（實測.三）漲跌停：優先用合約值，沒有即時源時用前收推算
      const lim=limitPrices(code,q.prev_close,iq);
      const limSt=limitState(price,lim);
      // 2026-08-27新增（P2-新，盤前盤後）：美股才有extended_hours（見
      // fetch_quotes_us.py），只在盤前/盤後時段、且該時段真的有資料時才顯示，
      // 跟正規盤收盤價分開一行、明確標示「盤前」/「盤後」，不會被誤會成正規盤價。
      let extHtml='';
      if(us&&rawQ&&rawQ.extended_hours){
        const eh=rawQ.extended_hours;
        const seg=eh.market_state==='PRE'?eh.pre:(eh.market_state==='POST'?eh.post:null);
        const segLabel=eh.market_state==='PRE'?'盤前':'盤後';
        if(seg&&seg.price!=null){
          const segCls=(seg.change??0)>=0?'u':'d';
          const segPct=seg.change_pct!=null?seg.change_pct:0;
          extHtml=`<div class="note" style="margin-top:2px">${segLabel} <b class="num ${segCls}">$${nf(seg.price)}</b> <span class="chg-tag ${segCls}">${segPct>=0?'+':''}${segPct.toFixed(2)}%</span></div>`;
          showedExtendedHours=true;
        }
      }
      // 2026-08-27新增（P2-新，財報行事曆）：只在21天內有下一次財報時才顯示，
      // 太遠的日期對「接下來要注意什麼」沒有實際參考價值，只會讓每一列都塞滿
      // 用不到的資訊。
      let earningsHtml='';
      if(us&&earningsCal[code]&&earningsCal[code].next_earnings_date){
        const days=(new Date(earningsCal[code].next_earnings_date)-new Date())/86400000;
        if(days>=0&&days<=21){
          const d=new Date(earningsCal[code].next_earnings_date);
          const sessionTxt=earningsCal[code].estimated_session==='pre'?'盤前'
            :(earningsCal[code].estimated_session==='post'?'盤後':'時段未知');
          // 2026-08-28修正（P0-a）：原本getMonth()/getDate()依賴裝置本地
          // 時區——next_earnings_date是純日期字串會被解析成UTC午夜，西半球
          // 時區的裝置用本地時區取值會少算一天。改用fmtTzMD()明確指定
          // America/New_York（美股財報情境，跟資料語意一致）。
          earningsHtml=`<div class="note" style="margin-top:2px;color:var(--ink-3)">📅 財報：${fmtTzMD(d,'America/New_York')}（${sessionTxt}，估計）</div>`;
        }
      }
      // data-flash-code/data-flash-value：給盤中快速輪詢(fastPollTick())用來判斷
      // 「這次重繪後的價格」跟「上次輪詢看到的價格」是否不同，不同才閃爍，見
      // flashPriceEls()。這裡只是標記資料，平常渲染不受影響。
      rowEl.innerHTML=`<div class="nm"><b>${nm}</b><span>${meta}</span>${limitBadge(limSt)}</div>${sp}<div class="px${limSt?' at-limit '+(limSt==='up'?'lu':'ld'):''}"><b data-flash-code="${code}" data-flash-value="${price}"${priceIsStale?' style="font-size:.85em"':''}>${priceLabel}</b>${pctTagHtml}${(!us&&simTradeText(code))?`<div class="note" style="color:var(--ink-3)">${simTradeText(code)}</div>`:''}</div>`;
      if(extHtml)rowEl.insertAdjacentHTML('beforeend',extHtml);
      if(earningsHtml)rowEl.insertAdjacentHTML('beforeend',earningsHtml);
      // 2026-09-04 P0產品.一：可展開的來源說明（預設收合；smoke test仍能在DOM裡讀到「今日收盤」「即時(tick)」等字樣）
      const det=document.createElement('div');det.className='wl-detail';det.dataset.wlDetail=code;det.hidden=!WL_DETAIL_OPEN.has(code);
      det.innerHTML=`${srcText.replace(/^·\s*/,'')}`;
      wrap.appendChild(det);
    }
    if(runId!==HYDRATE_HOME_SEQ)return;  // 期間又有一次更新開跑，這批結果作廢，讓最新那次接手
    el.replaceChildren(frag);
    const extNote=document.getElementById('wl-extended-hours-note');
    if(extNote)extNote.style.display=showedExtendedHours?'':'none';
    stampUpdated('home');
    updateDiagBanner();
  }

  // ══════ 市場頁（大盤指數 / 類股 / 三大法人 / 期貨籌碼）══════
  // 2026-08-25 新增：統一的「資料時間」格式，跟「最後更新」（瀏覽器實際刷新畫面的時間）
  // 是不同概念——這個是資料本身屬於哪個交易日，明確標「FinMind 盤後」提醒不是即時報價。
  function fmtDataTime(dateStr){
    return dateStr?`資料時間 ${dateStr.replaceAll('-','/')}（盤後）`:'';
  }
  function setDataTime(elId,dateStr){const el=document.getElementById(elId);if(el)el.textContent=fmtDataTime(dateStr)}
  // 2026-08-26 架構修正（P0-1）：大盤指數/類股/三大法人/台指期/美股指數全部改成讀
  // GitHub Actions 排程產生的 data/market_tw.json / data/market_us.json，不再直接
  // 呼叫 FinMind——FinMind 免費層已 402 額度用盡，client-side 直打全部會失敗
  // （見 research/ 第79輪記錄）。跟 quotes_tw.json/quotes_us.json 同一套「排程抓→
  // commit→App只讀檔」模式，見 .github/workflows/market.yml。
  // 2026-08-27 新增：個股月營收/財報比率(PER/PBR/殖利率)改讀 data/fundamentals.json
  // （見 research/build_fundamentals_json.py），跟 market_tw.json 一樣是本機檔案、
  // 不呼叫 FinMind。這份檔案是手動快照非排程自動更新（該腳本docstring已揭露原因），
  // 只查得到「產生當下研究端剛好有快取」的股票，查不到時回傳空物件，呼叫端會
  // 自然顯示「—」而不是崩潰。
  // 先.八十一-9（2026-10-13）：個股頁每檔一個小檔 data/by_code/<代號>.json（scripts/build_by_code.py，
  // 從 fundamentals／holders／institutional_history／events／sector_flow… 等整份檔切出這一檔）＋共用
  // data/by_code/_meta.json（各檔的 meta 等共用欄位）。byCodeSection(code,name) 回傳「跟整份檔同結構、
  // 只含這一檔」的物件；小檔讀不到（網路錯誤）回 null，呼叫端退回整份檔。404＝這檔在所有來源都沒資料，
  // 回傳只有共用欄位的空殼（等同整份檔裡查不到這檔）。子集不寫進整份檔的全域快取（其他頁要全市場）。
  let BY_CODE_META_P=null,BY_CODE_META_AT=0;const BY_CODE_P=new Map();
  function _byCodeMeta(){
    if(!BY_CODE_META_P||Date.now()-BY_CODE_META_AT>10*60*1000){
      BY_CODE_META_AT=Date.now();
      BY_CODE_META_P=fetch('data/by_code/_meta.json?t='+Math.floor(Date.now()/60000))
        .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
        .catch(e=>{BY_CODE_META_P=null;console.warn('[byCode:meta]',e);recordGlobalError('byCode:meta',e);return null});
    }
    return BY_CODE_META_P;
  }
  function byCode(code){
    code=String(code||'').toUpperCase();
    if(!/^[0-9A-Z]{4,6}$/.test(code))return Promise.resolve(null);
    const hit=BY_CODE_P.get(code);
    if(hit&&Date.now()-hit.at<10*60*1000)return hit.p;
    const p=fetch('data/by_code/'+code+'.json?t='+Math.floor(Date.now()/60000))
      .then(r=>{if(r.status===404)return {code};if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
      .catch(e=>{BY_CODE_P.delete(code);console.warn('[byCode]',code,e);recordGlobalError('byCode',e);return null});
    BY_CODE_P.set(code,{p,at:Date.now()});
    if(BY_CODE_P.size>40)BY_CODE_P.delete(BY_CODE_P.keys().next().value);
    return p;
  }
  // 先.八十一-28：排程自測（scripts/selftest_by_code.py）發現小檔與整份檔不一致時，_meta.consistency.mismatch>0，
  // 這時一律不用小檔、退回整份檔，並在診斷 log 記一次（只記一次，不洗版）。
  let BY_CODE_BAD_LOGGED=false;
  function _byCodeOk(m){
    const c=m&&m.consistency;
    if(c&&c.mismatch>0){
      if(!BY_CODE_BAD_LOGGED){BY_CODE_BAD_LOGGED=true;const e=new Error(`個股小檔與整份檔不一致 ${c.mismatch} 處（${c.checked_at||''}），已改讀整份檔`);console.warn('[byCode:inconsistent]',e,c.examples);recordGlobalError('byCode:inconsistent',e)}
      return false;
    }
    return true;
  }
  async function byCodeSection(code,name){
    const [m,d]=await Promise.all([_byCodeMeta(),byCode(code)]);
    if(!_byCodeOk(m))return null;
    const sec=m&&m.sections&&m.sections[name];
    if(!sec||!d)return null;
    const part=d[name]||{},out=Object.assign({},sec.common||{});
    for(const [k,h] of Object.entries(sec.shape||{})){if(h==='dict')out[k]=part[k]||{};else if(h==='list')out[k]=part[k]||[]}
    out._byCode=code;
    return out;
  }
  // 先.八十一-10：台股個股日線主來源改為 repo（by_code 小檔的近 60 日價，取自 price_history.json，每日三班排程），
  // 小檔沒有價格（新上市、ETF 未收錄等）才打 FinMind 補。回傳 FinMind TaiwanStockPrice 同形狀的列，
  // 陣列上掛 _src（'repo'｜'finmind'）供畫面標來源。
  async function twPxRepoFirst(code,fmStart){
    const d=await byCode(code);
    const rows=(d&&Array.isArray(d.price))?d.price:[];
    if(rows.length>=2){
      const out=rows.map((r,i)=>{
        const [date,open,high,low,close,volume,turnover]=r;
        const pc=i?rows[i-1][4]:null;
        return {date,open,max:high,min:low,close,Trading_Volume:volume,Trading_money:turnover,spread:(pc!=null&&close!=null)?+(close-pc).toFixed(4):null};
      });
      out._src='repo';
      return out;
    }
    const px=await fm('TaiwanStockPrice',code,fmStart||_d(35));
    px._src='finmind';
    return px;
  }
  // 整份檔已在記憶體就用整份；否則先讀這一檔的小檔，小檔讀不到才下載整份。
  async function stockScoped(code,name,full,loadFull){
    if(full)return full;
    const s=code?await byCodeSection(code,name):null;
    return s||loadFull();
  }
  let FUNDAMENTALS_CACHE=null;
  async function loadFundamentals(code){
    if(!FUNDAMENTALS_CACHE&&code){
      const s=await byCodeSection(code,'fundamentals');
      if(s&&!FUNDAMENTALS_CACHE)return (s.fundamentals&&s.fundamentals[code])||{};
    }
    if(!FUNDAMENTALS_CACHE){
      try{const r=await fetch('data/fundamentals.json?t='+Date.now());if(r.ok)FUNDAMENTALS_CACHE=await r.json()}catch(e){console.warn('[loadFundamentals]',e);recordGlobalError('loadFundamentals',e);FUNDAMENTALS_CACHE={fundamentals:{}}}
    }
    return (FUNDAMENTALS_CACHE&&FUNDAMENTALS_CACHE.fundamentals&&FUNDAMENTALS_CACHE.fundamentals[code])||{};
  }
  let QUOTES_ALL_TW_CACHE=null;
  // 常備.開發-20（先.六十七）：QUOTES_ALL_TW_CACHE 可能只裝了首頁小檔合併的幾檔，整份是否已載入另用旗標判斷。
  let QUOTES_ALL_TW_FULL=false,QUOTES_ALL_TW_P=null;
  async function loadQuotesAllTw(){
    if(!QUOTES_ALL_TW_FULL){
      // 同改版前：只試一次，失敗不重抓；同時呼叫共用同一個下載
      if(!QUOTES_ALL_TW_P)QUOTES_ALL_TW_P=(async()=>{
        try{const r=await fetch('data/quotes_all_tw.json?t='+Date.now());if(!r.ok)throw new Error('HTTP '+r.status);QUOTES_ALL_TW_CACHE=await r.json()}
        catch(e){console.warn('[loadQuotesAllTw]',e);recordGlobalError('loadQuotesAllTw',e);QUOTES_ALL_TW_CACHE=QUOTES_ALL_TW_CACHE||{quotes:{}}}
        QUOTES_ALL_TW_FULL=true;
      })();
      await QUOTES_ALL_TW_P;
    }
    return (QUOTES_ALL_TW_CACHE&&QUOTES_ALL_TW_CACHE.quotes)||{};
  }
  // 2026-08-27新增（P2-新，財報行事曆）：data/earnings_calendar.json
  // （見 .github/scripts/fetch_earnings_calendar.py，yfinance get_calendar()，
  // 只涵蓋美股追蹤標的）。
  let EARNINGS_CALENDAR_CACHE=null;
  async function loadEarningsCalendar(){
    if(!EARNINGS_CALENDAR_CACHE){
      try{const r=await fetch('data/earnings_calendar.json?t='+Date.now());if(r.ok)EARNINGS_CALENDAR_CACHE=await r.json()}catch(e){console.warn('[loadEarningsCalendar]',e);recordGlobalError('loadEarningsCalendar',e);EARNINGS_CALENDAR_CACHE={earnings:{}}}
    }
    return (EARNINGS_CALENDAR_CACHE&&EARNINGS_CALENDAR_CACHE.earnings)||{};
  }
  // 2026-09-02新增（使用者原話：「今日事件接earnings_calendar」）：首頁
  // 「今日事件」卡片，接上data/earnings_calendar.json，列出21天內即將公布
  // 財報的股票（跟個股頁盤前/盤後那段既有邏輯同一個門檻，方便對照）。
  // **誠實揭露範圍**：這份行事曆目前只涵蓋`.github/scripts/
  // fetch_earnings_calendar.py`追蹤清單裡的美股（yfinance來源），不是「今日
  // 所有市場事件」，也不含台股（台股月營收/財報公告日期目前沒有現成的
  // 行事曆資料源），卡片文案要講清楚範圍，不能讓使用者誤以為涵蓋全市場。
  async function loadTodayEvents(){
    const el=document.getElementById('today-events');if(!el)return;
    try{
      const cal=await loadEarningsCalendar();
      const now=Date.now();
      const rows=Object.entries(cal)
        .map(([code,info])=>{
          if(!info||!info.next_earnings_date)return null;
          const days=(new Date(info.next_earnings_date)-now)/86400000;
          if(!(days>=0&&days<=21))return null;
          return {code,days,...info};
        })
        .filter(Boolean)
        .sort((a,b)=>a.days-b.days);
      const card=document.getElementById('home-events-card');
      if(!rows.length){el.innerHTML='<div class="note">近21天內（美股，`fetch_earnings_calendar.py`追蹤清單）查無即將公布的財報，或資料尚未更新</div>';if(card)card.hidden=true;return}
      if(card)card.hidden=false;  // 2026-09-04 P0產品.一：只在有事件時顯示
      const sessionLabel={pre:'盤前',post:'盤後'};
      el.innerHTML=rows.map(r=>{
        const d=new Date(r.next_earnings_date);
        const dateTxt=`${d.getUTCMonth()+1}/${d.getUTCDate()}`;
        const sess=sessionLabel[r.estimated_session]||'';
        return `<div class="row" style="cursor:default"><div class="nm"><b>${nameOf(r.code)||r.code}</b><span>${r.code} · 美股財報</span></div><div class="px"><b>${dateTxt}</b><span>${sess}</span></div></div>`;
      }).join('')+'<div class="note" style="margin-top:6px">僅涵蓋追蹤清單內的美股財報日期（yfinance），非全市場事件，不含台股</div>';
    }catch(e){
      console.warn('[loadTodayEvents]',e);recordGlobalError('loadTodayEvents',e);
      el.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
    }
  }
  // 2026-09-15（開發佇列自走，承接自競品一）「我的持股事件」卡：codes＝自選股(WL)
  // ∪ 紙上持倉（data/strategy_performance.json各策略目前holdings，交易頁「策略
  // 監控台」用的同一份mark-to-market資料），事件來源沿用ensureEvents()（跟個股頁
  // 「近期事件與題材」卡同一份data/events.json、同一個快取，不重打）＋news.json裡
  // 已命中股票代號的新聞，兩者合併依時間排一條流，點一列跳個股頁。
  let NEWS_CACHE=null,NEWS_AT=0;
  async function ensureNews(){
    if(NEWS_CACHE&&Date.now()-NEWS_AT<10*60*1000)return NEWS_CACHE;
    try{
      const r=await fetch('data/news.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      NEWS_CACHE=await r.json();NEWS_AT=Date.now();
    }catch(e){
      console.warn('[ensureNews]',e);recordGlobalError('ensureNews',e);
      if(!NEWS_CACHE)NEWS_CACHE={news:[]};
    }
    return NEWS_CACHE;
  }
  // 先.八十一-11：名稱＋代號（名稱依序取名稱清單／quote_lite 小檔／事件本身帶的公司名；都沒有才只顯示代號）
  function _holdName(code,evName){
    const n=nameOf(code);
    const nm=(n&&n!==code)?n:((evName&&evName[code])||'');
    return nm?`${String(nm).replace(/</g,'&lt;')} ${code}`:code;
  }
  async function loadMyHoldingsEvents(){
    const card=document.getElementById('home-my-events-card'),el=document.getElementById('my-holdings-events');
    if(!el)return;
    try{
      // 先.八十一-11：範圍＝自選股＋真錢持股（本機 /auto/ledger 去識別化帳本裡有成交的代號），不含研究策略／模擬持股。
      // 真錢持股要連上電腦才讀得到；讀不到時只列自選股，並在說明寫明原因。
      const codes=new Set(WL),realCodes=new Set();
      let realNote='';
      if(LIVE.configured&&LIVE.url){
        try{
          const lg=await loadAutoLedger();
          ((lg&&lg.rows)||[]).forEach(r=>{if((r.filled_qty||0)>0&&/^[0-9A-Z]{4,6}$/.test(String(r.symbol||'')))realCodes.add(r.symbol)});
        }catch(e){
          if(_isOfflineErr(e))realNote='電腦離線，真錢持股暫未列入';
          else{console.warn('[loadMyHoldingsEvents:ledger]',e);recordGlobalError('loadMyHoldingsEvents:ledger',e);realNote='讀取真錢帳本失敗，真錢持股暫未列入'}
        }
      }else realNote='未連上電腦，真錢持股暫未列入';
      realCodes.forEach(c=>codes.add(c));
      if(!codes.size){card.hidden=true;return}
      const [evDoc,newsDoc]=await Promise.all([loadEventsForCodes([...codes]),ensureNews(),ensureQuoteLite([...codes]).catch(e=>{console.warn('[loadMyHoldingsEvents:names]',e)})]);
      const items=[],evName={};
      (evDoc.events||[]).forEach(e=>{
        if(!codes.has(e.code))return;
        if(e.name)evName[e.code]=e.name;
        const ts=Date.parse(e.date);
        if(!isNaN(ts))items.push({ts,dateTxt:String(e.date).slice(5),code:e.code,title:e.title,kind:e.type||'事件',url:e.url});
      });
      (newsDoc.news||[]).forEach(n=>{
        const ts=Date.parse(n.published);
        if(isNaN(ts))return;
        (n.codes||[]).forEach(c=>{
          if(!codes.has(c))return;
          items.push({ts,dateTxt:new Date(ts).toISOString().slice(5,10),code:c,title:n.title,kind:'新聞',url:n.url});
        });
      });
      items.sort((a,b)=>b.ts-a.ts);
      const top=items.slice(0,20);
      if(!top.length){card.hidden=true;return}
      card.hidden=false;
      el.innerHTML=top.map(it=>{
        const c=EVENT_TYPE_COLOR[it.kind]||'var(--ink-3)';
        const t=(it.title||'').replace(/</g,'&lt;');
        return `<div style="display:flex;gap:9px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--hairline);cursor:pointer" onclick="openStock('${it.code}')">
          <span class="num" style="font-size:10px;color:var(--ink-4);min-width:32px;padding-top:2px">${it.dateTxt}</span>
          <span style="font-size:9.5px;font-weight:700;color:${c};border:1px solid ${c};border-radius:5px;padding:1px 5px;flex-shrink:0;margin-top:1px">${it.kind}</span>
          <span style="flex:1;font-size:12px;color:var(--ink-2);line-height:1.5"><b style="color:var(--ink)">${_holdName(it.code,evName)}</b>${realCodes.has(it.code)?' <span style="font-size:9.5px;color:var(--gold)">真錢持股</span>':''}・${t}${it.kind==='法說會'?mopsIrLinkHtml({type:it.kind,code:it.code},true):''}</span>
        </div>`;
      }).join('')
        +`<div class="note" data-ui-explain style="margin-top:8px">自選股 ${WL.length} 檔＋真錢持股 ${realCodes.size} 檔（不含研究策略／模擬持股）${realNote?'（'+realNote+'）':''}，共 ${items.length} 則事件新聞${items.length>20?'，只顯示最近20筆':''}。來源：data/events.json（MOPS重大訊息／TWSE月營收／除權息）＋data/news.json（僅已命中股票代號者，覆蓋率有限）。點一列跳個股頁。</div>`;
    }catch(e){
      console.warn('[loadMyHoldingsEvents]',e);recordGlobalError('loadMyHoldingsEvents',e);
      el.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
      if(card)card.hidden=true;
    }
  }
  let SECTOR_LIST_CACHE=null;
  function closeSectorSheet(){
    document.getElementById('sector-mask').classList.remove('open');
    document.getElementById('sector-sheet').classList.remove('open');
  }
  // 先.九十四-5g（2026-10-14）：方法論說明頁。分數算法說明對照 research/score_v2.py::_pct_score（去極值1%/99%→百分位→×10）
  // 與三支 generate_scores_*.py 的加權（缺資料的因子不算 0 分，只用有資料的因子按權重比例算；coverage＝有資料的權重合計）。
  // 日期、回測狀態、權重一律讀當下資料檔（scores_*_list.json 的 meta、research/weights_frozen*.json、data/STATUS.json），不寫死數字。
  // 失敗只影響本視窗（各段各自 try/catch），不外溢。
  const METHOD_BOARDS={
    value:{title:'價值成長榜',list:'scores_list.json',weights:'research/weights_frozen.json',
      inputs:['data/fundamentals.json','data/stock_detail.json','data/price_history.json','data/company_info.json'],
      plain:'想找「財報在成長、價格不算太貴、籌碼與走勢不差」的公司。估值是跟同產業比（同產業不足 8 檔就跟全市場比）。'},
    momentum:{title:'題材動能榜',list:'scores_momentum_list.json',weights:'research/weights_frozen_momentum.json',
      inputs:['data/fundamentals.json','data/stock_detail.json','data/price_history.json','data/company_info.json','data/quotes_all_tw.json','data/market_tw.json'],
      plain:'想找「股價與成交量正在轉強、資金往那個族群流」的公司。財報只用來排除地雷，不加分；完全不看本益比，題材股本來就貴。'},
    future:{title:'未來性濾網',list:'scores_future_list.json',weights:'research/weights_frozen_future.json',
      inputs:['data/stock_detail.json','data/company_info.json','data/price_history.json'],
      plain:'想找「法人持續買進、毛利率高又穩」的公司。目前只做得到「現在就能算」的部分，事件資料與 AI 質性判讀尚未實作。'},
  };
  // 美股但書原文（alpha-app/CLAUDE.md 七、資料原則「美股結論一律附存活者偏誤但書」現行文字，2026-10-14 先.九十四-4 口徑）。
  const US_SURVIVORSHIP_CAVEAT='存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。';
  const METHOD_INPUT_NAMES={'data/fundamentals.json':'本益比、殖利率、月營收','data/stock_detail.json':'財報、三大法人、融資融券',
    'data/price_history.json':'每日收盤價','data/company_info.json':'公司名稱與產業別','data/quotes_all_tw.json':'今日收盤快照','data/market_tw.json':'大盤與類股'};
  const METHOD_META_CACHE={};
  let METHOD_STATUS_CACHE=null,METHOD_BOARD='value',METHOD_GEN=0;
  function _mEsc(t){return String(t==null?'':t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function _mTime(iso){if(!iso)return '—';const d=new Date(iso);if(isNaN(d))return _mEsc(iso);const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}/${p(d.getMonth()+1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`}
  function _mMoney(v){if(v==null||!isFinite(v))return '—';if(Math.abs(v)>=1e8)return (v/1e8).toFixed(2)+'億';if(Math.abs(v)>=1e4)return (v/1e4).toFixed(0)+'萬';return String(v)}
  async function _methodJson(url){const r=await fetch(url);if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
  function closeMethodSheet(){
    document.getElementById('method-mask').classList.remove('open');
    document.getElementById('method-sheet').classList.remove('open');
  }
  function openMethodSheet(board){
    try{
      // 先.九十五-R4：'us'＝從美股選股開啟，只顯示美股段（但書置頂），台股三榜切換與內容隱藏。
      const us=board==='us';
      const usEl=document.getElementById('method-us-body'),tg=document.getElementById('method-board-toggle'),bb=document.getElementById('method-board-body');
      if(usEl)usEl.style.display=us?'':'none';
      if(tg)tg.style.display=us?'none':'inline-flex';
      if(bb)bb.style.display=us?'none':'';
      if(us){
        document.getElementById('method-mask').classList.add('open');
        document.getElementById('method-sheet').classList.add('open');
        const sh=document.getElementById('method-sheet');if(sh)sh.scrollTop=0;
        renderMethodUs();renderMethodCommon();
        return;
      }
      if(!METHOD_BOARDS[board])board=METHOD_BOARD;
      METHOD_BOARD=board;
      document.getElementById('method-mask').classList.add('open');
      document.getElementById('method-sheet').classList.add('open');
      document.querySelectorAll('#method-board-toggle .mtg-opt').forEach(b=>b.classList.toggle('on',b.dataset.board===board));
      renderMethodCommon();
      renderMethodBoard(board).catch(e=>{console.warn('[renderMethodBoard]',e);recordGlobalError('renderMethodBoard',e)});
    }catch(e){console.warn('[openMethodSheet]',e);recordGlobalError('openMethodSheet',e)}
  }
  function methodGoResearch(){
    closeMethodSheet();go('journal');
    setTimeout(()=>{const c=document.getElementById('journal-research-card');if(c)c.scrollIntoView({block:'start'})},200);
  }
  async function renderMethodBoard(board){
    const el=document.getElementById('method-board-body');if(!el)return;
    const gen=++METHOD_GEN,cfg=METHOD_BOARDS[board];
    el.innerHTML='載入中…';
    let meta=METHOD_META_CACHE[board],wf=null,status=METHOD_STATUS_CACHE,labels={};
    const errs=[];
    const jobs=[
      meta?null:_methodJson(cfg.list).then(j=>{meta=METHOD_META_CACHE[board]=j.meta||{}}).catch(e=>{errs.push('榜單檔 '+cfg.list+'：'+e.message)}),
      _methodJson(cfg.weights).then(j=>{wf=j}).catch(e=>{errs.push('權重檔：'+e.message)}),
      status?null:_methodJson('data/STATUS.json').then(j=>{status=METHOD_STATUS_CACHE=j}).catch(e=>{errs.push('STATUS.json：'+e.message)}),
      loadAppModule('shared').then(()=>{const bc=typeof BOARD_CONFIG!=='undefined'&&BOARD_CONFIG[board];if(bc)labels=bc.factorLabels||{}}).catch(e=>{errs.push('因子中文名：'+e.message)}),
    ].filter(Boolean);
    await Promise.allSettled(jobs);
    if(gen!==METHOD_GEN)return;  // 使用者已切到別的榜
    if(errs.length){console.warn('[renderMethodBoard] 部分資料載入失敗',errs);recordGlobalError('renderMethodBoard',new Error(errs.join('；')))}
    const m=meta||{};
    const btag=m.backtest_status?`<span style="display:inline-block;font-size:10.5px;font-weight:600;color:var(--caution);border:1px solid rgba(201,82,74,.5);border-radius:6px;padding:1px 7px">${_mEsc(m.backtest_status)}</span>`+(m.backtest_note?` ${_mEsc(m.backtest_note)}`:''):'（讀不到回測狀態）';
    let wHtml='<div>讀不到權重檔，無法列出權重。</div>';
    if(wf&&wf.weights){
      const ws=Object.entries(wf.weights).filter(([,w])=>w>0).sort((a,b)=>b[1]-a[1]);
      wHtml=ws.map(([k,w])=>`<div style="display:flex;justify-content:space-between;border-bottom:1px solid var(--hairline);padding:3px 0"><span>${_mEsc(labels[k]||k)}</span><b class="num">${Math.round(w*100)}%</b></div>`).join('');
      const hashOk=m.weights_hash&&wf.weights_sha256?m.weights_hash===wf.weights_sha256:null;
      wHtml+=`<div style="margin-top:4px">${wf.dev_period?`權重凍結於 ${_mEsc(wf.frozen_at)}，只用 ${_mEsc(wf.dev_period.val_end)} 以前的研究期決定，之後不再依結果調整。`:`這組權重是初始設計值（${_mEsc(wf.frozen_at)} 定下），<b>不是</b>回測找出來的最佳值。`}`
        +(hashOk===true?' 已核對：今天榜單用的就是這組權重。':hashOk===false?' <span style="color:var(--caution)">⚠ 今天榜單記錄的權重版本與此檔不一致，以榜單為準。</span>':'')+'</div>';
      // 價值成長榜 meta.disclaimer 載明 analyst／catalyst 全市場沒有資料源，權重實際全數重新分配（讀當下 meta，文字改了就不顯示）。
      if(board==='value'&&/analyst\/catalyst兩項全市場沒有資料源/.test(m.disclaimer||''))wHtml+=`<div>其中「${_mEsc(labels.analyst||'analyst')}」「${_mEsc(labels.catalyst||'catalyst')}」目前全市場都沒有資料，實際上這兩項的權重都分給了其他項目。</div>`;
    }
    const files=((status&&status.data_files)||[]);
    // 前台不顯示原始來源字串（含內部端點代號），只顯示白話名稱＋產生時間；完整來源在設定頁「進階 → 資料來源」。
    const inHtml=cfg.inputs.map(pth=>{
      const f=files.find(x=>x.path===pth);
      return `<div style="display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--hairline);padding:4px 0"><span>${_mEsc(METHOD_INPUT_NAMES[pth]||pth)}</span>`
        +(f?`<span class="num" style="text-align:right">${_mTime(f.generated_at)}${f.status&&f.status!=='ok'?` <span style="color:var(--caution)">異常</span>`:''}</span>`
          :'<span style="text-align:right">未列入清單，看資料基準日</span>')+'</div>';
    }).join('');
    const floor=m.liquidity_floor_20d_value;
    el.innerHTML=`
      <div style="font-size:14px;font-weight:700;color:var(--ink);margin-bottom:4px">${_mEsc(cfg.title)}</div>
      <div>${_mEsc(cfg.plain)}</div>
      <div style="margin-top:6px">回測狀態：${btag}</div>
      <div style="font-weight:700;color:var(--ink-2);margin-top:12px">分數怎麼算（0～10 分）</div>
      <div>① 每個因子（例如營收成長、法人買超）先在全市場合格股票裡比名次，最極端的前後 1% 先壓平，再換成百分位：贏過幾成的股票，大約就是幾分（贏過 80% ≈ 8 分）。</div>
      <div>② 各因子的分數按下面的權重加權平均，得到總分。</div>
      <div>③ 某個因子沒有資料，<b>不當成 0 分</b>：總分只用有資料的因子、按權重比例算；「資料完整度」＝有資料的因子權重合計。完整度低的分數比較不可靠。</div>
      <div>④ 近 20 日平均成交值${floor?'低於 '+_mEsc(_mMoney(floor))+'元':'不足'}的股票照樣算分，但<b>不進數字排名</b>；處置期間的股票從清單排除。</div>
      <div style="margin-top:4px">所以分數是「跟今天其他股票比的相對位置」，不是漲跌預測；高分不等於該買。</div>
      <div style="font-weight:700;color:var(--ink-2);margin-top:12px">因子權重</div>
      ${wHtml}
      <div style="font-weight:700;color:var(--ink-2);margin-top:12px">資料日期</div>
      <div>資料基準日：<b class="num">${_mEsc(m.data_asof||'—')}</b>　榜單產生：<span class="num">${_mTime(m.generated_at)}</span>　合格股票 ${_mEsc(m.universe_size??'—')} 檔</div>
      <div>都是盤後資料，不是即時報價。</div>
      <div style="font-weight:700;color:var(--ink-2);margin-top:12px">用到哪些資料、何時更新</div>
      ${inHtml}
      <div style="margin-top:4px">原始資料來自證交所、櫃買中心、期交所的官方公開資料；公司產業別是一次性整理、不常變動。</div>
      ${errs.length?`<div style="color:var(--note-gold);margin-top:6px">部分資料讀取失敗：${_mEsc(errs.join('；'))}</div>`:''}`;
  }
  function renderMethodUs(){
    const el=document.getElementById('method-us-body');if(!el||el.dataset.done)return;
    try{
      el.innerHTML=`
        <div id="method-us-caveat" style="color:var(--caution);font-weight:700;border:1px solid rgba(201,82,74,.5);border-radius:8px;padding:8px 10px;margin-bottom:10px">⚠ ${_mEsc(US_SURVIVORSHIP_CAVEAT)}</div>
        <div style="font-size:14px;font-weight:700;color:var(--ink);margin-bottom:4px">美股評分 v0</div>
        <div>用 SEC 申報的年度財報（XBRL）加上 yfinance 每日收盤價，把美股排序。只是資料排序，<b>還沒回測過</b>。</div>
        <div>名冊是 SEC 當下的申報人清單，不是當年的名冊，已下市公司多數拿不到價格，所以這份排序不能拿來回測、也不能當成歷史上會贏的證據。</div>
        <div style="margin-top:4px">美股篩選（成交額／漲跌幅／市值門檻）只篩資料、不排名，也不是選股訊號。</div>`;
      el.dataset.done='1';
    }catch(e){console.warn('[renderMethodUs]',e);recordGlobalError('renderMethodUs',e)}
  }
  function renderMethodCommon(){
    const el=document.getElementById('method-common-body');if(!el||el.dataset.done)return;
    try{
      el.innerHTML=`
        <div style="font-weight:700;color:var(--ink-2)">回測與已知偏誤</div>
        <div>· 台股三個榜的回測狀態寫在上方紅框標籤；「回測未通過」代表照分數挑股票，在歷史上贏不過 0050，分數只能當資料整理參考。</div>
        <div>· 台股榜每天會先排除已不在上市櫃名冊、或股價落後全市場 30 天以上的代號（已下市、長期停止交易）。</div>
        <div>· 美股：<b>${_mEsc(US_SURVIVORSHIP_CAVEAT)}</b> 美股評分 v0 用的是 SEC 當下名冊，不是當年的名冊，不能拿來回測。</div>
        <div>· 回測用的是過去的資料，不代表未來。</div>
        <div style="font-weight:700;color:var(--ink-2);margin-top:12px">研究做得怎麼樣</div>
        <div>試過多少想法、哪些失敗、有沒有贏過 0050，都記在「研究成績單」。</div>
        <button class="btn ghost" style="width:100%;margin-top:8px" onclick="methodGoResearch()">研究成績單</button>
        <div style="margin-top:10px;color:var(--ink-3)">所有分數只是資料整理與排序，非投資建議，不代表買賣訊號。</div>`;
      el.dataset.done='1';
    }catch(e){console.warn('[renderMethodCommon]',e);recordGlobalError('renderMethodCommon',e)}
  }
  let MARKET_TW_CACHE=null,MARKET_US_CACHE=null;
  // 2026-08-27 新增（P1-1）：統一的頁面頂端診斷橫幅，取代「六個面板各喊一次連線
  // 失敗」——集中檢查各個資料檔案的新鮮度，一次列出哪些過期/缺失、原因分類、
  // 下次排程時間。個別面板本身維持簡潔的空狀態（不重複顯示落落長的錯誤訊息）。
  // 2026-09-08（排程一.3）台股來源是否「還沒發布」而非「我們抓不到」。
  // 判準：現在是交易日、已收盤、但還在證交所的發布空窗內。
  // 空窗上界先取收盤後 4 小時（13:30→17:30）——這是**保守的暫定值**，
  // `scripts/probe_twse_publish_time.py` 正在連續三個交易日實測真正的發布時刻，
  // 量到之後改成實測值並同步調整 market.yml 的排程時間。
  // 在量到之前**寧可說「尚未發布」也不要說「過舊」**：
  // 前者最壞是晚一點才顯示正確狀態，後者是每天誣賴自己故障。
  function isTwSourceNotYetPublished(){
    try{
      const z=_zonedParts(new Date(),'Asia/Taipei');
      if(z.wd<1||z.wd>5)return false;                 // 假日本來就沒有
      const mins=z.h*60+z.mi;
      return mins>=13*60+30&&mins<17*60+30;           // 收盤後 4 小時內
    }catch(e){console.warn('[isTwSourceNotYetPublished]',e);return false}
  }
  // 2026-09-04（四修.四）：自選股報價「資料過舊」的判定抽成純函式，並納入即時源——
  // 台股只要Shioaji即時源新鮮（SSE連線中的記憶體推送、或20分鐘內的熱檔/冷檔），就不算過舊，
  // 即使Actions的quotes_tw.json沒落地；美股同理看IBKR源。這樣「資料過舊」跟「即時連線中」
  // 不會同頁矛盾。抽成函式也是為了讓smoke test能用twOpen=true直接驗，不受測試時段影響。
  function diagQuoteProblems(twOpen,usOpen){
    const problems=[];
    const twLive=_intradaySourceFresh(INTRADAY_SINOPAC,'Asia/Taipei',true).fresh&&(LIVE.connected||intradayAgeMin(INTRADAY_SINOPAC)<=INTRADAY_STALE_MIN);
    const twQAge=intradayAgeMin(INTRADAY_TW);
    if(twOpen&&!twLive&&(twQAge==null||twQAge>INTRADAY_STALE_MIN))problems.push({name:'自選股台股報價',reason:(twQAge==null?'無資料':'資料過舊')+'（Actions quotes_tw 與 Shioaji 即時源皆無新鮮資料）',schedule:'盤中每10分鐘（09:00–13:30）；即時源需本機 live server 連線'});
    const usLive=_intradaySourceFresh(INTRADAY_IBKR,'America/New_York',true).fresh&&(LIVE.connected||intradayAgeMin(INTRADAY_IBKR)<=INTRADAY_STALE_MIN);
    const usQAge=intradayAgeMin(INTRADAY_US);
    if(usOpen&&!usLive&&(usQAge==null||usQAge>INTRADAY_STALE_MIN))problems.push({name:'自選股美股報價',reason:usQAge==null?'無資料':'資料過舊',schedule:'盤中每10分鐘'});
    return problems;
  }
  // 先.九十五-R2：橫幅「下次排程」時間改讀 STATUS.json 的 workflows[market.yml].crons（generate_status_json.py 從
  // .github/workflows/market.yml 實際 cron 換算台北時間，單一來源）；STATUS 還沒有這欄（舊版）時不寫時間，不寫死舊時刻。
  function marketScheduleLabel(stDoc,kind){
    try{
      const w=stDoc&&Array.isArray(stDoc.workflows)?stDoc.workflows.find(x=>x&&/market\.yml$/.test(x.file||'')):null;
      const cr=w&&Array.isArray(w.crons)?w.crons:[];
      if(kind==='us'){const t=cr.filter(c=>c.next_day_taipei||c.taipei<'09:00').map(c=>c.taipei);
        return t.length?'美股收盤後 '+t.join('、')+'（台北隔日）':'美股收盤後（market.yml 排程）'}
      const t=cr.filter(c=>!c.next_day_taipei&&c.taipei>='14:00').map(c=>c.taipei);
      return t.length?'台股收盤後 '+t[0]+(t.length>1?'（補救 '+t.slice(1).join('、')+'）':''):'台股收盤後（market.yml 排程）';
    }catch(e){console.warn('[marketScheduleLabel]',e);return kind==='us'?'美股收盤後（market.yml 排程）':'台股收盤後（market.yml 排程）'}
  }
  async function updateDiagBanner(){
    const el=document.getElementById('diag-banner');if(!el)return;
    // 2026-08-28修正（P0併入，Cowork定位）：MARKET_TW_CACHE/MARKET_US_CACHE
    // 只有loadMarketDataFiles()會填，而它之前只被市場頁的hydrate呼叫——首頁
    // hydrateHome()一開始就呼叫這裡，快取還是null，害這個橫幅誤報「美股四大
    // 指數/大盤指數無資料」，其實market_us.json/market_tw.json都是新鮮的。
    // 比照下面既有的`await loadFundamentals('')`同一模式，檢查新鮮度前先確保
    // 快取已載入。
    await loadMarketDataFiles();
    const nowTW=zonedNow('Asia/Taipei'),nowUS=zonedNow('America/New_York');
    const twOpen=nowTW.wd>=1&&nowTW.wd<=5&&(nowTW.h*60+nowTW.mi)>=540&&(nowTW.h*60+nowTW.mi)<810;
    const usOpen=nowUS.wd>=1&&nowUS.wd<=5&&(nowUS.h*60+nowUS.mi)>=570&&(nowUS.h*60+nowUS.mi)<960;
    const problems=diagQuoteProblems(twOpen,usOpen);
    const stDoc=await ensureStatusDoc();
    const twSched=marketScheduleLabel(stDoc,'tw'),usSched=marketScheduleLabel(stDoc,'us');
    // 先.九十五-R1 順帶：斷網時沒抓到檔，說「離線」而不是「尚未排程抓取或抓取失敗」
    const netOff=navigator.onLine===false||INTRADAY_NET_OFF.tw;
    const noDataTxt=netOff?'離線，連不上資料檔':'無資料（尚未排程抓取或抓取失敗）';
    // 大盤/類股/三大法人、美股指數：這兩個一天只排程1-2次，用24小時當過期門檻。
    const twMAge=marketDataAgeMin(MARKET_TW_CACHE);
    // 2026-09-06（健檢.一）改用交易日曆判斷，不再用 rolling 24 小時。
    // 台股 13:30 收盤，排程通常在收盤後陸續產出，給 4 小時寬限。
    const twFresh=isFreshForCalendar(
      MARKET_TW_CACHE&&MARKET_TW_CACHE.fetched_at?new Date(MARKET_TW_CACHE.fetched_at).getTime():null,
      'Asia/Taipei',TW_HOLIDAYS,13,30,4*60);
    // 2026-09-08（排程一.3）**「來源尚未發布」與「我們抓不到」是兩件事。**
    // 實測 2026-09-08 15:05 打 TWSE T86 與 MI_MARGN 都回
    // `stat='很抱歉，沒有符合條件的資料'`、total=0——**證交所根本還沒發布**，
    // 而我們的排程訂在 14:10，永遠早於發布時間。
    // 舊文案一律講「資料過舊」，等於把「證交所還沒發布」講成我方故障，
    // 使用者看到的是「這個 App 壞了」。**已發布卻抓不到才叫過舊。**
    const twSrcNotYet=isTwSourceNotYetPublished();
    if(twMAge==null||!twFresh)problems.push({
      name:'大盤指數/類股/三大法人',
      reason:twSrcNotYet
        ?'證交所今日資料尚未發布（實測收盤後 95 分鐘仍未提供，發布時間量測中）'
        :(twMAge==null?noDataTxt:'資料過舊（比最近一個交易日的收盤還舊）'),
      schedule:twSrcNotYet?'待證交所發布後自動抓取':twSched});
    const usMAge=marketDataAgeMin(MARKET_US_CACHE);
    // 美股 16:00 ET 收盤，同樣給 4 小時寬限
    const usFresh=isFreshForCalendar(
      MARKET_US_CACHE&&MARKET_US_CACHE.fetched_at?new Date(MARKET_US_CACHE.fetched_at).getTime():null,
      'America/New_York',US_HOLIDAYS,16,0,4*60);
    if(usMAge==null||!usFresh)problems.push({name:'美股四大指數',reason:usMAge==null?noDataTxt:'資料過舊（比最近一個交易日的收盤還舊）',schedule:usSched});
    // 2026-08-27 新增：個股基本面快照（月營收/PER/PBR）改排程累積更新後，超過3天沒更新
    // 就代表 update_fundamentals_daily.py 那步連續失敗，提醒使用者可能看到過期的基本面數字。
    // 常備.開發-20（2026-10-11）：原本為了讀一個時間戳下載整份 fundamentals.json（gzip 約 536KB）。
    // 改讀 STATUS.json 的 data_files（generate_status_json.py 從同一份檔的 meta.generated_at 抄出，
    // 同一個 market.yml 排程產生）；STATUS 查不到這一列才退回舊做法讀整份檔。
    let fundGenAt=null;
    const stRow=stDoc&&Array.isArray(stDoc.data_files)?stDoc.data_files.find(x=>x&&x.path==='data/fundamentals.json'):null;
    if(stRow&&stRow.generated_at)fundGenAt=stRow.generated_at;
    else{await loadFundamentals('');fundGenAt=FUNDAMENTALS_CACHE&&FUNDAMENTALS_CACHE.meta&&FUNDAMENTALS_CACHE.meta.generated_at}
    const fundAgeMin=fundGenAt?(Date.now()-new Date(fundGenAt).getTime())/60000:null;
    if(fundAgeMin==null||fundAgeMin>3*24*60)problems.push({name:'個股基本面（月營收/PER/PBR）',reason:fundAgeMin==null?'無資料或缺少更新時間戳':'資料可能過期（超過3天未更新）',schedule:twSched});
    // 2026-08-27 新增：大盤融資維持率改排程累積更新後，超過3天沒新的一天就代表
    // update_margin_maintenance.py 連續失敗（常見原因：TWSE信用交易統計www.twse.
    // com.tw/rwd端點當天尚未發布、2026-09-15起分母已改TWSE官方端點，不再是FinMind
    // 額度問題），提醒使用者畫面上那個數字可能不是最新的，不要誤以為永遠有效。
    let marginHistory=[];
    try{const r=await fetch('data/margin_maintenance.json?t='+Date.now());if(r.ok)marginHistory=await r.json()}catch(e){console.warn('[updateDiagBanner:margin]',e);recordGlobalError('updateDiagBanner:margin',e)}
    const marginLast=Array.isArray(marginHistory)&&marginHistory.length?marginHistory[marginHistory.length-1]:null;
    const marginAgeMin=marginLast&&marginLast.date?(Date.now()-new Date(marginLast.date+'T00:00:00+08:00').getTime())/60000:null;
    if(marginAgeMin==null||marginAgeMin>3*24*60)problems.push({name:'大盤融資維持率',reason:marginAgeMin==null?'無資料':'資料過期（超過3天未更新）',schedule:twSched});
    else if(marginLast&&marginLast.data_incomplete)problems.push({name:'大盤融資維持率',reason:'今日資料不完整（分母/全市場融資金額取得失敗）',schedule:twSched});
    if(!problems.length){el.style.display='none';return}
    el.style.display='';
    el.innerHTML='⚠ 部分資料異常：'+problems.map(p=>`<b>${p.name}</b>（${p.reason}，下次排程 ${p.schedule}）`).join('；');
  }
  async function loadMarketDataFiles(force){
    if(force||!MARKET_TW_CACHE){
      try{const r=await fetch('data/market_tw.json?t='+Date.now());if(r.ok)MARKET_TW_CACHE=await r.json()}catch(e){console.warn('[loadMarketDataFiles:tw]',e);recordGlobalError('loadMarketDataFiles:tw',e)}
    }
    if(force||!MARKET_US_CACHE){
      try{const r=await fetch('data/market_us.json?t='+Date.now());if(r.ok)MARKET_US_CACHE=await r.json()}catch(e){console.warn('[loadMarketDataFiles:us]',e);recordGlobalError('loadMarketDataFiles:us',e)}
    }
  }
  function marketDataAgeMin(data){
    if(!data||!data.fetched_at)return null;
    return (Date.now()-new Date(data.fetched_at).getTime())/60000;
  }
  function fmtMarketDataTime(data){
    if(!data||!data.fetched_at)return '查無資料（尚未排程抓取或本次抓取失敗）';
    const age=marketDataAgeMin(data);
    const d=new Date(data.fetched_at);
    // 2026-08-28修正（P0-a）：原本toLocaleString('zh-TW',...)沒指定
    // timeZone，依賴裝置本地時區——這是台股大盤/三大法人資料時間戳，
    // 改用fmtTzMMDDHHMM()明確指定Asia/Taipei。
    return `資料 ${fmtTzMMDDHHMM(d,'Asia/Taipei')}`;
  }
  function idxRowHtml(label,srcLabel,item,changePctOverride){
    if(!item||item.close==null)return `<div class="row idx-row" style="cursor:default"><div class="nm"><b>${label}</b><span>${srcLabel}</span></div>${SPARK_PLACEHOLDER}<div class="px"><b>—</b><span>查無資料</span></div></div>`;
    const pct=changePctOverride!=null?changePctOverride:item.change_pct;
    const cls=(pct==null)?'':(pct>=0?'pos':'neg');
    const pctTxt=pct==null?'—':`${pct>=0?'+':''}${pct.toFixed(2)}%`;
    // 2026-08-27：近20日收盤序列跟著market_tw.json/market_us.json一起排程抓（見
    // fetch_market_tw.py/fetch_market_us.py），不用另外呼叫FinMind畫這條走勢線。
    const up=(pct==null&&item.sparkline&&item.sparkline.length>=2)?item.sparkline[item.sparkline.length-1]>=item.sparkline[0]:(pct==null?true:pct>=0);
    const sp=rowSparkline(item.liveKey||'',item.sparkline,up).html;  // 2026-09-04四修.三：item.liveKey有當日1分K時畫「今日」，否則20日
    // data-flash-code用label（可能含中文/空白，用encodeURIComponent避免破壞屬性值）：
    // 給盤中快速輪詢(fastPollTick())的flashPriceEls()判斷這個指數的價格是否較上次
    // 輪詢變動，見hydrateHome()裡自選股列同樣的用法。
    return `<div class="row idx-row" style="cursor:default"><div class="nm"><b>${label}</b><span>${srcLabel}</span></div>${sp}<div class="px"><b data-flash-code="${encodeURIComponent(label)}" data-flash-value="${item.close}">${nf(item.close)}</b><span class="${cls}">${pctTxt}</span></div></div>`;
  }
  // 2026-09-04 P0產品.一：首頁大盤速覽膠囊（跟idxRowHtml同一份資料，不同排版）
  function idxCapsuleHtml(label,srcLabel,item){
    if(!item||item.close==null)return `<div class="idx-cap"><div class="cn">${label}</div><div class="cv" style="color:var(--ink-3)">—</div><div class="cp" style="color:var(--ink-3)">查無資料</div></div>`;
    const pct=item.change_pct;const cls=pct==null?'':(pct>=0?'pos':'neg');
    const up=(pct==null&&item.sparkline&&item.sparkline.length>=2)?item.sparkline[item.sparkline.length-1]>=item.sparkline[0]:(pct==null?true:pct>=0);
    const spk=rowSparkline(item.liveKey||'',item.sparkline,up);
    const live=LIVE.connected&&LIVE_KB[item.liveKey||'']&&LIVE_KB[item.liveKey||''].closes.length>=2?LIVE_KB[item.liveKey||''].closes:null;
    const capSvg=spark(live||item.sparkline||[],up);
    const isLive=/Shioaji 即時|IBKR (即時|延遲)|Yahoo 延遲/.test(srcLabel||'');
    return `<div class="idx-cap" title="${(srcLabel||'').replace(/"/g,'')}"><div class="cn"><span class="sdot ${isLive?'g':'gr'}" style="width:6px;height:6px;margin-right:4px"></span>${label}</div><div class="cv ${cls}" data-flash-code="${encodeURIComponent(label)}" data-flash-value="${item.close}">${nf(item.close)}</div><div class="cp ${cls}">${pct==null?'—':`${pct>=0?'+':''}${pct.toFixed(2)}%`}${spk.mode?`<span style="font-size:9px;color:var(--ink-3);font-weight:400;margin-left:4px">${spk.mode==='today'?'今日':'20日'}</span>`:''}</div>${capSvg}</div>`;
  }
  async function loadUsIndexes(){
    await loadMarketDataFiles();
    await ensureIbkrQuotes();
    const idx=(MARKET_US_CACHE&&MARKET_US_CACHE.indices)||{};
    const order=[['^DJI','道瓊工業指數'],['^GSPC','S&P 500'],['^IXIC','NASDAQ'],['^SOX','費城半導體指數']];
    const {fresh:ibkrFresh,isTodayClose}=_intradaySourceFresh(INTRADAY_IBKR,'America/New_York',isUsTradingWindowNow());
    return order.map(([id,label])=>{
      const ibkrQ=ibkrFresh?INTRADAY_IBKR.quotes[id]:null;
      if(ibkrQ&&ibkrQ.last!=null){
        // IBKR沒有近20日走勢序列，sparkline借用既有Yahoo資料源的（不影響
        // 主數字/漲跌%的即時性，走勢線本來就不需要跟主數字同一個資料源）。
        const item={close:ibkrQ.last,change_pct:ibkrQ.change_pct,sparkline:idx[id]&&idx[id].sparkline};
        // 2026-09-02新增：ibkr_quotes.py對IBKR無訂閱的指數（道瓊/費半）現在會
        // 自己改抓Yahoo寫進同一份quotes_ibkr.json，data_type多一種"YAHOO_
        // DELAYED"，來源標籤要老實反映「這其實是Yahoo不是IBKR」，不能沿用
        // 「IBKR xxx」這個前綴誤導使用者。2026-09-03新增：收盤後但資料確實
        // 是今天的（isTodayClose），標「今日收盤」不再講「延遲N分」這種
        // 暗示盤中即時的措辭。
        // 2026-09-04修正：收盤後YAHOO_DELAYED的資料也要標Yahoo，不能因為走了
        // isTodayClose分支就變成「IBKR 今日收盤」（smoke check 19在美股盤後時段
        // 跑才踩到的既有誠實標示bug）。
        const isYahoo=ibkrQ.data_type==='YAHOO_DELAYED';
        const srcLabel=isTodayClose
          ?(isYahoo?'Yahoo 今日收盤':'IBKR 今日收盤')
          :(isYahoo?'Yahoo 延遲~15分':`IBKR ${intradayDataTypeLabel(ibkrQ.data_type)}`);
        return {html:idxRowHtml(label,srcLabel,item),date:INTRADAY_IBKR.fetched_at,label,srcLabel,item};
      }
      // 2026-09-08（健檢.五.4 總司令裁示）本機IBKR逾期時不得靜默回退。
      // 舊寫法只標「Yahoo Finance（每日收盤快照）」——那句話本身沒說謊，
      // 但使用者看不出「本機即時來源其實掛了」，會以為美股本來就只有收盤快照。
      // 靜默降級比顯示錯誤更危險：錯誤會被修，靜默降級會被當成正常狀態放著，
      // 這次就是這樣拖了六天（09/02～09/08 排程根本不存在都沒人發現）。
      const _ibkrStale=INTRADAY_IBKR&&!ibkrFresh;
      const _fbLabel=_ibkrStale
        ?'本機IBKR逾期→Yahoo每日收盤快照'
        :'Yahoo Finance（每日收盤快照）';
      return {html:idxRowHtml(label,_fbLabel,idx[id]),date:idx[id]&&idx[id].as_of,label,srcLabel:_fbLabel,item:idx[id]};
    });
  }
  // market_tw.json這批盤後資料的「收盤日」標籤：今天→今日收盤（MM-DD）；昨天→昨日收盤（MM-DD）；
  // 更早（例如週一看到週五的）→前次收盤（MM-DD）。永遠帶日期。
  function twCloseDateLabel(twCache){
    let d=null;
    // 先.八十一-1：優先用加權指數自己的資料日（data_date），落後時尾巴附「大盤資料停在 MM/DD」（stale_note 由排程寫入）
    const dd=twCache&&(twCache.data_date||(twCache.taiex&&twCache.taiex.data_date));
    const stale=twCache&&twCache.stale_note?`｜⚠ ${twCache.stale_note}`:'';
    if(dd&&/^\d{4}-\d{2}-\d{2}$/.test(dd))d=new Date(`${dd}T14:00:00+08:00`);
    const raw=twCache&&((twCache.tpex&&twCache.tpex.date)||(twCache.taiex&&twCache.taiex.date));
    if(!d&&raw&&/^\d{8}$/.test(raw))d=new Date(`${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}T14:00:00+08:00`);
    else if(twCache&&twCache.fetched_at)d=new Date(twCache.fetched_at);
    if(!d||isNaN(d))return '收盤（日期不明）'+stale;
    const z=_zonedParts(d,'Asia/Taipei'),n=_zonedParts(new Date(),'Asia/Taipei');
    const md=String(z.m).padStart(2,'0')+'-'+String(z.d).padStart(2,'0');
    const dayDiff=Math.round((Date.UTC(n.y,n.m-1,n.d)-Date.UTC(z.y,z.m-1,z.d))/86400000);
    return (dayDiff<=0?'今日收盤':(dayDiff===1?'昨日收盤':'前次收盤'))+`（${md}）`+stale;
  }
  function taiexRowSource(twCache){
    const {fresh,isTodayClose}=_intradaySourceFresh(INTRADAY_SINOPAC,'Asia/Taipei',isTwTradingWindowNow());
    const q=fresh?INTRADAY_SINOPAC.quotes&&INTRADAY_SINOPAC.quotes.TAIEX:null;
    if(q&&q.last!=null){
      const srcLabel=isTodayClose?'Shioaji 今日收盤':'Shioaji 即時';
      return {srcLabel,item:{close:q.last,change_pct:q.change_pct,sparkline:twCache.taiex&&twCache.taiex.sparkline,liveKey:'TAIEX'}};
    }
    return {srcLabel:'證交所',item:twCache.taiex};
  }
  // 2026-09-01新增，同日補齊四檔：期貨近月優先用Shioaji即時報價（App
  // 「期貨」頁FUT_CONTRACTS的id → shioaji_quotes.py寫進quotes_sinopac.json
  // 的key，兩邊各自獨立命名，這裡做對應），查不到/過期才退回現有TAIFEX
  // CSV來源（market_tw.json::futures）。
  const FUT_ID_TO_SINOPAC_KEY={TX:'TXF_NEAR',MTX:'MXF_NEAR',TE:'EXF_NEAR',TF:'FXF_NEAR'};
  function shioajiFutRowSource(appFutId,fallbackFut){
    const {fresh,isTodayClose}=_intradaySourceFresh(INTRADAY_SINOPAC,'Asia/Taipei',isTwTradingWindowNow());
    const key=FUT_ID_TO_SINOPAC_KEY[appFutId];
    const q=(fresh&&key)?INTRADAY_SINOPAC.quotes&&INTRADAY_SINOPAC.quotes[key]:null;
    if(q&&q.last!=null){
      const srcLabel=isTodayClose?'Shioaji 今日收盤 · 近月合約':'Shioaji 即時 · 近月合約';
      return {fut:{last:q.last,change_pct:q.change_pct},srcLabel};
    }
    return {fut:fallbackFut,srcLabel:null};
  }
  async function loadHomeIndex(){
    const el=document.getElementById('home-idx-rows');if(!el)return;
    await loadMarketDataFiles();
    await ensureSinopacQuotes();
    const tw=MARKET_TW_CACHE||{},usIdx=await loadUsIndexes();
    await ensureQuoteLite(['TAIEX']);  // 常備.開發-20：加權指數膠囊走勢線只抓 TAIEX 小檔，不下載整份 sparklines.json
    if(LIVE.configured){mergeLiveKbarsLast();await Promise.allSettled(['TAIEX','TXF_NEAR'].map(getLiveCloses))}  // 2026-09-06實測.二
    const taiexSrc=taiexRowSource(tw),txfSrc=shioajiFutRowSource('TX',tw.tx_futures);
    // 2026-09-04 P0產品.一：首頁改橫向膠囊帶（名稱、點數、%、迷你走勢），一屏約三顆
    const capsules=[idxCapsuleHtml('加權指數',taiexSrc.srcLabel,taiexSrc.item)];
    // 先.八十-8：台指期膠囊補近月日線走勢（data/market_tw.json tx_futures.sparkline，近月連續、未做轉倉調整）；連上即時則照舊畫當日 1 分K
    if(txfSrc.fut&&txfSrc.fut.last!=null)capsules.push(idxCapsuleHtml('台指期近月',txfSrc.srcLabel||'TAIFEX',{close:txfSrc.fut.last,change_pct:txfSrc.fut.change_pct,liveKey:'TXF_NEAR',sparkline:((tw.tx_futures||{}).sparkline||[]).filter(v=>v!=null)}));
    usIdx.forEach(r=>{if(r.item)capsules.push(idxCapsuleHtml(r.label,r.srcLabel,r.item))});
    el.innerHTML=capsules.join('')||'<div class="note">查無資料</div>';
    if(capsules.length&&window.__ALPHA_DATA_MS==null)window.__ALPHA_DATA_MS=performance.now();  // 先.八十一-8：第一次有資料數字出現的時間（量測用）
    // 2026-09-04（四修.四）：加權/台指期走Shioaji即時時，時間戳寫即時時間；否則明標收盤日
    const liveTw=(taiexSrc.srcLabel||'').startsWith('Shioaji')||!!txfSrc.srcLabel;
    document.getElementById('home-idx-datatime').textContent=liveTw
      ?`台股 Shioaji 即時（${INTRADAY_SINOPAC&&INTRADAY_SINOPAC.fetched_at?fmtTzHHMM(new Date(INTRADAY_SINOPAC.fetched_at),'Asia/Taipei'):'—'}）· 美股指數為每日收盤快照`
      :`${twCloseDateLabel(tw)}｜${fmtMarketDataTime(tw)}`;
    _safeSync('estAmountNote',()=>{const t=estAmountText();if(t)document.getElementById('home-idx-datatime').textContent+=' · '+t});
  }
  // 2026-10-08 先.五十一-5：IX0001 預估成交金額（shioaji_quotes.py 寫進 TAIEX quote 的 estimate_amount_sum）。
  // 只顯示「今天」的值；單位假設新台幣元（待實盤核對），超出 100 億～5 兆的數量級一律不顯示並記警告，
  // 不讓單位錯置的數字安靜出現在首頁。
  function estAmountText(){
    const q=INTRADAY_SINOPAC&&INTRADAY_SINOPAC.quotes&&INTRADAY_SINOPAC.quotes.TAIEX;
    if(!q||q.estimate_amount_sum==null)return '';
    if(!_isTaipeiToday(q.tick_at||INTRADAY_SINOPAC.fetched_at))return '';
    const v=+q.estimate_amount_sum;
    if(!(v>=1e10&&v<=5e12)){console.warn('[estAmountText] 預估成交金額數量級異常，不顯示',v);return ''}
    return '今日預估成交金額 '+(v/1e8).toLocaleString('zh-TW',{maximumFractionDigits:0})+' 億';
  }

  // 2026-08-24 新增：台股/美股/期貨三選切換，市場/選股/交易三頁共用同一套邏輯。
  // MKT_STATE 記每頁目前選哪個市場（不共用同一個值——選股頁選美股，市場頁不會跟著跳）。
  const MKT_STATE={market:'TW',picks:'TW',trade:'TW'};
  // 先.六十-A4：真錢帳本（本機伺服器 /auto/ledger，token 必檢；只回去識別化欄位）
  // 常備.開發-2（2026-10-11）：盤前日報／盤勢摘要／週覆盤共用 data/daily_brief.json（固定規則產生，非 AI 判斷）
  let DAILY_BRIEF_CACHE=null,JOURNAL_LEDGER_CACHE=null;
  async function loadDailyBrief(){
    if(DAILY_BRIEF_CACHE)return DAILY_BRIEF_CACHE;
    const r=await fetch('data/daily_brief.json?t='+Date.now());
    if(!r.ok)throw new Error('HTTP '+r.status);
    return DAILY_BRIEF_CACHE=await r.json();
  }
  const _briefLines=ls=>(ls||[]).map(l=>'<div style="padding:2px 0">· '+_autoEsc(uiPlain(l))+'</div>').join('');
  const _briefFoot=d=>'<div style="margin-top:6px;font-size:10px;color:var(--ink-4)">'+_autoEsc(String(d.disclaimer||'規則摘要，非 AI 判斷').replace(/、?非投資建議/g,''))+(d.data_asof?'；資料日 '+_autoEsc(d.data_asof)+'（最後交易日）':'')+'</div>';
  function _briefWatchLine(d){
    const ev=d.premarket&&d.premarket.events||{},nw=d.premarket&&d.premarket.news||{};
    const m=ev.material_by_code||{},n=nw.by_code||{};
    const hit=WL.map(c=>({c,m:m[c]||0,n:n[c]||0})).filter(x=>x.m||x.n);
    if(!hit.length)return '自選股 '+WL.length+' 檔：'+(ev.material_date?ev.material_date+' ':'')+'無重大訊息、新聞索引無點名';
    return '自選股：'+hit.map(x=>(nameOf(x.c)||x.c)+'（'+[x.m?'重訊 '+x.m:'',x.n?'新聞 '+x.n:''].filter(Boolean).join('、')+'）').join('、');
  }
  async function loadHomeBrief(){
    const card=document.getElementById('home-ai-card'),el=document.getElementById('home-ai-body');
    if(!card||!el)return;
    try{
      const d=await loadDailyBrief();
      el.innerHTML=_briefLines((d.premarket&&d.premarket.lines||[]).concat([_briefWatchLine(d)]))+_briefFoot(d);
      card.hidden=false;
    }catch(e){console.warn('[loadHomeBrief]',e);recordGlobalError('loadHomeBrief',e);card.hidden=true}
  }
  async function loadAutoLedger(){
    if(!LIVE.configured||!LIVE.url)return null;
    const r=await liveFetch('/auto/ledger',15000);
    if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器可能是舊版，需重啟）':''));
    return await r.json();
  }
  // <auto-period-selftest>（常備.開發-11：scripts/selftest_home_exec_card.mjs 依這組標記抽出本段純函式驗三態，勿刪標記；段內不得碰 DOM／網路）
  // 先.六十-A2／A4：交易頁機器人卡與日誌頁共用的顯示對照
  const AUTO_MODE_LABEL={SIMULATION:'模擬',LIVE_WITH_VETO:'真錢（附否決窗）',LIVE:'真錢（無否決窗）'};
  const AUTO_REASON_LABEL={first_tranche:'首批',month_end:'月底再平衡',retry_after_error:'重跑上一期',open_batch:'續跑進行中批次',sim_drill:'模擬演練'};
  const AUTO_CODE_LABEL={INSUFFICIENT_CASH:'現金不足',CAP:'超過單次上限',LIMIT_DEV:'限價偏離前收',LIMIT:'缺限價',STALE:'資料過期',WHITELIST:'非白名單',RECONCILE:'對帳未過',STOP_FLAG:'緊急停止',PRICE_MISSING:'缺前收價',ACTION:'僅允許買進',CASH_ONLY:'僅限現股',LOT:'數量不合'};
  const _autoCodesTxt=cs=>(cs||[]).map(c=>AUTO_CODE_LABEL[c]||c).join('、');
  // 先.七十九-5：真錢改為「流程驗證單」——T1 結算後引擎開 STOP 並在 status 寫 strategy_frozen，前台一律顯示「已暫停：等紙上策略打贏 0050」。
  // 只有 STOP 開著且有 strategy_frozen 才算「暫停」；單純 STOP（緊急停止）維持原本的緊急停止文字。
  function autoFreezeText(d){
    const fz=d&&d.status&&d.status.strategy_frozen;
    if(!(d&&d.stopped&&fz))return '';
    return '已暫停：'+(fz.reason||'等紙上策略打贏 0050');
  }
  // 流程驗證單尚未結束（還沒暫停）時的一行說明；沒有 flow_verification_plan 就回空字串
  function autoFlowPlanText(d){
    const fp=d&&d.status&&d.status.flow_verification_plan;
    if(!fp||autoFreezeText(d))return '';
    return fp.note||'流程驗證單：只跑第 1 期，結算後自動暫停';
  }
  function autoNextText(d){
    const fz=autoFreezeText(d);
    if(fz)return fz;
    const n=d&&d.next_run;
    const tr=d&&d.next_tranche!=null?('第 '+d.next_tranche+(d.tranche_total?'／'+d.tranche_total:'')+' 期 · '):'';
    if(!n)return tr+'（讀不到交易日曆）';
    return tr+String(n.date).slice(5).replace('-','/')+' '+n.time+'（'+(AUTO_REASON_LABEL[n.reason]||n.reason)+'）';
  }
  // 常備.開發-11：本期執行摘要（純函式）。st＝/auto/status 回應、lg＝/auto/ledger 回應（任一可為 null）。
  // 本期＝帳本最近一個批次（排除撤單測試）；送出＝非拒單／略過的委託；成交比例＝已成交股數÷送出股數。
  // state：none（無紀錄）／blocked（整批被擋、沒送出）／pending（已送出未成交）／partial（部分成交）／full（全部成交）
  function autoPeriodBatchLabel(b){
    const m=/^(\d{4})(\d{2})-(T(\d+)|M)$/.exec(String(b||''));
    if(!m)return String(b||'—');
    return m[1]+'/'+m[2]+' '+(m[3]==='M'?'月底再平衡':'第 '+m[4]+' 期');
  }
  function autoPeriodReasons(st,codes){
    const out=[],s=(st&&st.status)||{},err=String(s.last_error||'');
    if(autoFreezeText(st))out.push(autoFreezeText(st)+'（流程驗證單完成後停止第 2 期以後的批次）');
    else if(st&&st.stopped)out.push('緊急停止開關開著，引擎一律拒單（到設定頁關閉後才會恢復）');
    if(err.startsWith('INSUFFICIENT_CASH:'))out.push('交割戶錢不夠（尚未入金或餘額不足）：'+err.slice('INSUFFICIENT_CASH:'.length));
    else if(err)out.push('最近一次執行出錯：'+err);
    const cs=(codes||[]).filter(c=>!(c==='INSUFFICIENT_CASH'&&err.startsWith('INSUFFICIENT_CASH:')));
    if(cs.length)out.push('被擋原因：'+_autoCodesTxt(cs));
    return out;
  }
  function autoPeriodSummary(st,lg){
    const rows=((lg&&lg.rows)||[]).filter(r=>r&&r.batch&&r.batch!=='撤單測試');
    const b=rows.length?rows.reduce((x,r)=>String(r.date||'')>String(x.date||'')?r:x).batch:null;
    const sub=b?rows.filter(r=>r.batch===b):[];
    const sent=sub.filter(r=>r.status!=='REJECT'&&r.status!=='SKIP');
    const qty=sent.reduce((t,r)=>t+(Number(r.qty)||0),0),fq=sent.reduce((t,r)=>t+(Number(r.filled_qty)||0),0);
    const state=!b?'none':!sent.length?'blocked':(qty>0&&fq>=qty?'full':(fq>0?'partial':'pending'));
    const la=st&&st.live_account;
    const dev=la&&!la.empty&&!la.error&&Array.isArray(la.holdings)?la.holdings.map(h=>({symbol:h.symbol,pct:h.pct,target:h.target_pct,dev:h.dev_pp})):[];
    const codes=[...new Set(sub.flatMap(r=>r.reason_codes||[]))].sort();
    return {state,batch:b,period:b?autoPeriodBatchLabel(b):null,
      send_date:sub.length?sub.map(r=>String(r.date||'')).sort().pop():null,
      n_orders:sub.length,n_sent:sent.length,qty,filled_qty:fq,fill_pct:qty?Math.round(fq/qty*1000)/10:null,
      deviation:dev,deviation_note:dev.length?'':(la&&la.error?'無法計算權重：'+la.error:'尚無成交，沒有實際權重可比'),
      next:st?autoNextText(st):null,reasons:autoPeriodReasons(st,codes)};
  }
  // 常備.開發-32：Bb-90 分批進度圖（純函式）。T1～T{tranche_total} 依引擎 state 的 next_tranche 判定（＜n 已完成、＝n 進行中或下一期、＞n 之後）；
  // 進行中＝帳本已有該期批次，或下一次觸發原因是續跑／重跑；之後各期日期為推估（引擎每月只動一次：T1 首個交易日、其後每月最後一個交易日）。
  // 月底模式（M）在 T 期跑完後每月一次，顯示已做幾次。緊急停止／流程驗證暫停時，進行中／下一期標「已暫停」。
  function autoTrancheTimeline(st,lg){
    const tt=Math.max(1,Math.min(24,Number(st&&st.tranche_total)||4));
    const n=Math.max(1,Number(st&&st.next_tranche)||1);
    const nr=st&&st.next_run,busy=!!(nr&&(nr.reason==='open_batch'||nr.reason==='retry_after_error'));
    const pause=autoFreezeText(st)||(st&&st.stopped?'緊急停止中':'');
    const by={},mYm=new Set();
    ((lg&&lg.rows)||[]).forEach(r=>{
      const m=/^(\d{4})(\d{2})-(T\d+|M)$/.exec(String(r&&r.batch||''));if(!m)return;
      if(m[3]==='M')mYm.add(m[1]+m[2]);
      const d=String(r.date||'');if(!by[m[3]]||d>by[m[3]])by[m[3]]=d;
    });
    const fmt=d=>String(d).replace(/-/g,'/');
    const ymAdd=(iso,k)=>{const y=Number(String(iso).slice(0,4)),mo=Number(String(iso).slice(5,7))-1+k;return (y+Math.floor(mo/12))+'/'+String(mo%12+1).padStart(2,'0')};
    const steps=[];
    for(let k=1;k<=tt;k++){
      const L='T'+k,d=by[L]||null;
      const state=k<n?'done':k>n?'later':(d||busy?'active':'next');
      let when;
      if(d)when=(state==='done'?'':'送單 ')+fmt(d);
      else if(state==='done')when='已完成';
      else if(nr&&nr.date)when=k===n?'預計 '+fmt(nr.date):'預計 '+ymAdd(nr.date,k-n)+' 月底';
      else when='日期待定';
      steps.push({key:L,label:'第 '+k+' 期',state,when,paused:!!pause&&(state==='active'||state==='next')});
    }
    let ms='later',mw='第 '+tt+' 期後每月月底';
    if(n>tt){ms=busy?'active':'next';mw=nr&&nr.date?'預計 '+fmt(nr.date):'日期待定'}
    if(mYm.size)mw='已做 '+mYm.size+' 次 · '+mw;
    steps.push({key:'M',label:'月底再平衡',state:ms,when:mw,paused:!!pause&&(ms==='active'||ms==='next')});
    return {steps,tranche_total:tt,next_tranche:n,pause};
  }
  // </auto-period-selftest>
  // 常備.開發-11：首頁真錢執行總覽卡（唯讀；兩個端點各自隔離，一個失敗另一個照畫）
  function renderHomeExec(st,lg,errs){
    const el=document.getElementById('home-exec-body');if(!el)return;
    const esc=_autoEsc,v=autoPeriodSummary(st,lg),L=[];
    const STATE_TXT={none:'本期尚無送單紀錄',blocked:'本期整批被擋，沒有送出委託',pending:'已送出，尚未成交',partial:'部分成交',full:'全部成交'};
    if(st)L.push('模式：'+esc((st.drill?'演練 · ':'')+(AUTO_MODE_LABEL[st.mode]||st.mode||'—')));
    if(v.batch){
      L.push('本期：<b>'+esc(v.period)+'</b>　送單日 '+esc(String(v.send_date||'—').replace(/-/g,'/'))+'　<b>'+esc(STATE_TXT[v.state])+'</b>');
      L.push('送出 '+v.n_sent+' 筆（本期紀錄共 '+v.n_orders+' 筆）　成交比例 '+(v.fill_pct==null?'—':v.fill_pct+'%')+(v.qty?'（'+v.filled_qty.toLocaleString('zh-TW')+'／'+v.qty.toLocaleString('zh-TW')+' 股）':''));
    }else L.push('<b>'+STATE_TXT.none+'</b>'+(lg?'（帳本是空的，首批尚未執行）':''));
    if(v.deviation.length)L.push('權重（實際／目標，偏離）：'+v.deviation.map(d=>esc(d.symbol)+' '+d.pct+'%／'+d.target+'%（'+(d.dev>0?'+':'')+d.dev+'pp）').join('、'));
    else if(st)L.push('權重：'+esc(v.deviation_note));
    if(st)L.push('下一期：'+esc(v.next));
    v.reasons.forEach(r=>L.push('<span style="color:var(--warn)">⚠ '+esc(r)+'</span>'));
    (errs||[]).forEach(e=>L.push('<span style="color:var(--ink-4)">'+esc(e)+'</span>'));
    el.innerHTML=L.map(x=>'<div style="padding:2px 0">'+x+'</div>').join('')+(st?renderTrancheTimeline(st,lg):'')+'<div style="margin-top:6px;font-size:10px;color:var(--ink-4)">只能看，不能下單</div>';
  }
  // 常備.開發-32：分批進度圖（橫向時間軸；失敗只降級成一行說明，不影響上面的本期摘要）
  function renderTrancheTimeline(st,lg){
    try{
      const esc=_autoEsc,t=autoTrancheTimeline(st,lg);
      const TAG={done:'已完成',active:'進行中',next:'下一期',later:'之後'};
      const DOT={done:'background:var(--good);border-color:var(--good);color:#fff',active:'background:var(--accent);border-color:var(--accent);color:#fff',
        next:'background:var(--surface);border-color:var(--accent);color:var(--accent)',later:'background:var(--surface);border-color:var(--hairline);color:var(--ink-4)'};
      const cells=t.steps.map(s=>{
        const tag=s.paused?'已暫停':TAG[s.state];
        return '<div class="tranche-step" data-state="'+s.state+'" style="flex:1;min-width:58px;text-align:center;position:relative;z-index:1">'
          +'<div style="width:20px;height:20px;margin:0 auto;border-radius:50%;border:2px solid;box-sizing:border-box;font-size:11px;line-height:16px;font-weight:700;'+DOT[s.state]+'">'+(s.state==='done'?'✓':s.key==='M'?'M':esc(s.key.slice(1)))+'</div>'
          +'<div style="font-size:11px;margin-top:3px;color:var(--ink-2)">'+esc(s.label)+'</div>'
          +'<div style="font-size:10px;font-weight:600;color:'+(s.paused?'var(--warn)':s.state==='later'?'var(--ink-4)':s.state==='done'?'var(--good)':'var(--accent)')+'">'+esc(tag)+'</div>'
          +'<div style="font-size:10px;color:var(--ink-4)">'+esc(s.when)+'</div></div>';
      }).join('');
      return '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--hairline)">'
        +'<div style="font-size:11px;color:var(--ink-3);margin-bottom:6px">分批進度（共 '+t.tranche_total+' 期，之後每月月底再平衡）</div>'
        +'<div id="home-tranche-timeline" style="position:relative;display:flex;gap:4px;overflow-x:auto">'
        +'<div style="position:absolute;left:29px;right:29px;top:10px;height:2px;background:var(--hairline);z-index:0"></div>'
        +cells+'</div>'
        +(t.pause?'<div style="font-size:10px;color:var(--warn);margin-top:4px">⚠ '+esc(t.pause)+'：時間軸只顯示排程位置，引擎目前不會送單</div>':'')
        +'<div style="font-size:10px;color:var(--ink-4);margin-top:2px">「之後」各期日期為推估，以引擎實際觸發為準</div></div>';
    }catch(e){console.warn('[renderTrancheTimeline]',e);recordGlobalError('renderTrancheTimeline',e);return '<div class="note" style="margin-top:6px">分批進度圖暫時畫不出來</div>'}
  }
  // 先.七十二-B6：設定頁「常用／進階」兩層（CSS 依 #scr-settings.ui-adv 決定顯示哪一層；卡片與載入函式不變）
  function uiSettingsLayer(layer){
    try{
      const scr=document.getElementById('scr-settings');if(!scr)return;
      scr.classList.toggle('ui-adv',layer==='adv');
      document.querySelectorAll('#settings-layer-toggle button').forEach(b=>b.classList.toggle('on',b.dataset.layer===layer));
      window.scrollTo(0,0);
    }catch(e){console.warn('[uiSettingsLayer]',e);recordGlobalError('uiSettingsLayer',e)}
  }
  // 先.七十二-B5：電腦沒設定連線時，「我的資產」與「自動投資這一期」兩張卡收起，只留一行 #home-offline-line
  // 先.八十-2：text＝已設定但連不上時的一行（電腦離線（最後連線…））；不給就是「連上電腦才看得到」
  function uiHomeOffline(off,text){
    try{
      const line=document.getElementById('home-offline-line');if(line){line.hidden=!off;if(off)line.textContent=text?(text+' →'):'我的資產、自動投資：連上電腦才看得到 →'}
      ['home-money-card','home-exec-card'].forEach(id=>{const c=document.getElementById(id);if(c)c.hidden=!!off});
    }catch(e){console.warn('[uiHomeOffline]',e);recordGlobalError('uiHomeOffline',e)}
  }
  async function loadHomeExecCard(){
    const el=document.getElementById('home-exec-body');if(!el)return;
    if(!LIVE.configured||!LIVE.url){el.textContent='連上電腦才看得到';uiHomeOffline(true);return}
    uiHomeOffline(false);
    const [a,b]=await Promise.allSettled([
      (async()=>{const r=await liveFetch('/auto/status',6000);if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})(),
      loadAutoLedger()]);
    const errs=[];
    if(a.status==='rejected'){console.warn('[loadHomeExecCard status]',a.reason);recordGlobalError('loadHomeExecCard status',a.reason);errs.push('讀不到 /auto/status（本機伺服器離線或舊版）')}
    if(b.status==='rejected'){console.warn('[loadHomeExecCard ledger]',b.reason);recordGlobalError('loadHomeExecCard ledger',b.reason);errs.push('讀不到 /auto/ledger（本機伺服器離線或舊版）')}
    if(a.status==='rejected'&&b.status==='rejected'){
      if(_isOfflineErr(a.reason)&&_isOfflineErr(b.reason)){el.textContent=liveOfflineText();uiHomeOffline(true,liveOfflineText());return}
      el.textContent='讀取真錢執行紀錄失敗（本機伺服器是舊版或回應錯誤）';return}
    renderHomeExec(a.status==='fulfilled'?a.value:null,b.status==='fulfilled'?b.value:null,errs);
  }

  // ── 左滑刪除 ──
  function attachSwipe(row,code){
    let x0=null,dx=0,moved=false;
    const base=()=>row.dataset.open?-76:0;
    const set=v=>row.style.transform=`translateX(${v}px)`;
    const start=x=>{x0=x;moved=false;row.style.transition='none'};
    const move=x=>{if(x0==null)return;dx=Math.max(-92,Math.min(0,base()+(x-x0)));if(Math.abs(x-x0)>6)moved=true;set(dx)};
    const end=()=>{if(x0==null)return;x0=null;row.style.transition='transform .22s';const op=dx<-40;row.dataset.open=op?'1':'';set(op?-76:0);
      if(op)document.querySelectorAll('.swipe-row').forEach(r=>{if(r!==row&&r.dataset.open){r.dataset.open='';r.style.transition='transform .22s';r.style.transform='translateX(0)'}})};
    row.addEventListener('touchstart',e=>start(e.touches[0].clientX),{passive:true});
    row.addEventListener('touchmove',e=>move(e.touches[0].clientX),{passive:true});
    row.addEventListener('touchend',end);
    row.addEventListener('mousedown',e=>{start(e.clientX);const mm=ev=>move(ev.clientX);const mu=()=>{end();document.removeEventListener('mousemove',mm);document.removeEventListener('mouseup',mu)};document.addEventListener('mousemove',mm);document.addEventListener('mouseup',mu)});
    row.addEventListener('click',()=>{if(moved)return;if(row.dataset.open){row.dataset.open='';row.style.transition='transform .22s';set(0);return}_safeAsync('openStock',()=>openStock(code))});
  }

  // ── 刪除確認視窗 ──
  let cfAction=null;
  function confirmDelete(code){
    const nm=nameOf(code);
    document.getElementById('cf-msg').innerHTML=`確定要從自選股移除<br><b style="font-size:16px">${nm}（${code}）</b>嗎？`;
    cfAction=()=>{WL=WL.filter(x=>x!==code);localStorage.setItem('alpha_wl',JSON.stringify(WL));pushWatchlistSoon();pushSettingsSoon();hydrateHome()};
    document.getElementById('confirm').classList.add('open');
    document.getElementById('cmask').classList.add('open');
  }
  function cfYes(){if(cfAction)cfAction();cfAction=null;cfNo()}
  function cfNo(){document.getElementById('confirm').classList.remove('open');document.getElementById('cmask').classList.remove('open')}

  // ── 搜尋股票（台股 + 美股）──
  let STOCKNAME={},STOCKLIST=[],STOCKNAME_US={},STOCKLIST_US=[],infoLoading=false,infoLoaded=false;
  // 2026-09-04：改成「共用同一個進行中的promise」——之前第二個呼叫者遇到infoLoading=true會直接
  // return，hydrateHome() await完根本沒等到名稱載好，自選股列就渲染成只有代號。
  let INFO_PROMISE=null;
  // 常備.開發-20（先.六十七）：opts.lite＝首頁用，只讀 localStorage 快取、不發任何網路請求——
  // 實測 FinMind TaiwanStockInfo 名稱清單本身就約 490KB（加 USStockInfo 約 58KB），失敗時的退路
  // company_info.json 約 73KB，都比首頁其餘資料加起來還大。首頁自選股台股名稱改由 ensureQuoteLite
  // 小檔補（nameOf 退到 LITE_NAME），美股沒有本地名稱來源，快取沒有時暫顯示代號。
  // 完整清單在打開搜尋（openSearch）或第一次切到其他分頁（_lazyCall）時才抓。
  // 本次工作階段 FinMind 已失敗過就 10 分鐘內不重打（避免每次切頁再等一次 12 秒逾時），直接走退路。
  let FINMIND_INFO_FAILED_AT=0;
  // 先.八十一-19：名稱清單來源（'repo'＝data/stock_names.json；'finmind'＝FinMind 完整名單）與 FinMind 補查狀態
  let INFO_SRC='',FM_NAMES_SUPP=null,FM_NAMES_SUPP_DONE=null;
  // repo 名單查不到時才向 FinMind 補查一次（整個工作階段只補一次），合併進清單後重跑搜尋；失敗寫明原因。
  function finmindNamesSupplement(){
    if(FM_NAMES_SUPP)return FM_NAMES_SUPP;
    const _fmInfo=(ds)=>{const ac=new AbortController();const timer=setTimeout(()=>ac.abort(),12000);
      return fetch(`${FM}?dataset=${ds}`,{signal:ac.signal}).then(r=>r.ok?r.json():Promise.reject(new Error('HTTP '+r.status))).finally(()=>clearTimeout(timer))};
    FM_NAMES_SUPP=Promise.allSettled([_fmInfo('TaiwanStockInfo'),_fmInfo('USStockInfo')]).then(([sTW,sUS])=>{
      let added=0;const errs=[];
      if(sTW.status==='fulfilled'){
        for(const s of ((sTW.value&&sTW.value.data)||[])){const id=s.stock_id;if(!id||STOCKNAME[id])continue;
          if(id.length<4||id.length>6||(id.length===6&&/^\d+$/.test(id)))continue;
          STOCKNAME[id]=s.stock_name;STOCKLIST.push({id,name:s.stock_name||'',ind:s.industry_category||'',mkt:'TW'});added++}
      }else errs.push('台股：'+fmErrReason(sTW.reason));
      if(sUS.status==='fulfilled'){
        for(const s of ((sUS.value&&sUS.value.data)||[])){const id=s.stock_id;if(!id||STOCKNAME_US[id])continue;
          const nm=(s.stock_name||'').replace(/\s*Common Stock\s*$/i,'');STOCKNAME_US[id]=nm;STOCKLIST_US.push({id,name:nm,ind:s.Subsector||'',mkt:'US'});added++}
      }else errs.push('美股：'+fmErrReason(sUS.reason));
      if(errs.length)console.warn('[finmindNamesSupplement]',errs.join('；'));
      FM_NAMES_SUPP_DONE={added,errs};
      return FM_NAMES_SUPP_DONE;
    });
    return FM_NAMES_SUPP;
  }
  function loadStockInfo(opts){
    const lite=!!(opts&&opts.lite);
    if(infoLoaded)return Promise.resolve();
    // 進行中的是 lite 呼叫、這次要完整清單：等它結束，沒載到再自己走一次（含 company_info 退路）
    if(INFO_PROMISE)return lite?INFO_PROMISE:INFO_PROMISE.then(()=>infoLoaded?undefined:loadStockInfo());
    INFO_PROMISE=_loadStockInfoImpl(lite).finally(()=>{INFO_PROMISE=null});
    return INFO_PROMISE;
  }
  async function _loadStockInfoImpl(lite){
    if(infoLoaded)return;infoLoading=true;
    let finmindErr=null;
    const skipFinmind=FINMIND_INFO_FAILED_AT&&Date.now()-FINMIND_INFO_FAILED_AT<10*60*1000;
    try{
      const c=localStorage.getItem('alpha_info'),cu=localStorage.getItem('alpha_info_us');
      // 2026-10-11（常備.開發-19 順修）：空清單快取視同沒有快取——FinMind 額度用盡時舊版會把空清單寫進快取，
      // 之後每次開 App 都讀到空清單、永遠不走 company_info.json 退路，搜尋查不到任何股票。
      if(c&&cu&&((JSON.parse(c).list)||[]).length){const o=JSON.parse(c),ou=JSON.parse(cu);STOCKNAME=o.map;STOCKLIST=o.list;STOCKNAME_US=ou.map;STOCKLIST_US=ou.list;infoLoaded=true;infoLoading=false;return}
    }catch(e){console.warn('[loadStockInfo:cacheRead]',e);recordGlobalError('loadStockInfo:cacheRead',e)}
    if(lite){infoLoading=false;return}  // 首頁：沒有快取就不抓，見 loadStockInfo 註解
    // 先.八十一-19：名稱清單改 repo 為主——data/stock_names.json（scripts/build_stock_names.py：台股取 company_info、
    // 美股取 SEC 名冊公司名），gzip 約 33KB，取代 FinMind TaiwanStockInfo＋USStockInfo（約 550KB）。
    // 不寫進 alpha_info 快取（那份快取不會過期，repo 名單每天會變）。查不到的代號由 doSearch 觸發 FinMind 補查。
    try{
      const r=await fetch('data/stock_names.json?t='+Math.floor(Date.now()/3600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const tw=(d&&d.tw)||[],us=(d&&d.us)||[];
      if(!tw.length)throw new Error('stock_names.json 台股清單為空');
      STOCKNAME={};STOCKLIST=[];STOCKNAME_US={};STOCKLIST_US=[];
      for(const [id,name,ind] of tw){STOCKNAME[id]=name;STOCKLIST.push({id,name:name||'',ind:ind||'',mkt:'TW'})}
      for(const [id,name,ind] of us){STOCKNAME_US[id]=name;STOCKLIST_US.push({id,name:name||'',ind:ind||'',mkt:'US'})}
      infoLoaded=true;INFO_SRC='repo';infoLoading=false;
      return;
    }catch(e){console.warn('[loadStockInfo:repo]',e);recordGlobalError('loadStockInfo:repo',e)}
    if(skipFinmind)finmindErr=new Error('FinMind 名稱清單本次工作階段已失敗，10 分鐘內不重打');
    else try{
      // 2026-09-08 兩個真缺陷一起修（實測抓到，不是預防性重構）：
      // (1) **原本沒有逾時中止**。實測 FinMind 的 USStockInfo 端點掛住超過 45 秒
      //     不回應（同一時間 TaiwanStockInfo 正常、curl 打同一個端點 0.49 秒就回），
      //     這個 fetch 就一直懸著。後果不只是搜尋清單載不出來——連冒煙測試的
      //     `waitUntil:'networkidle'` 都永遠等不到，整套測試無法執行。
      // (2) **原本用 Promise.all**，違反 CLAUDE.md 明文規定
      //     「多個獨立子任務平行執行時用 Promise.allSettled」。台股與美股清單是
      //     兩件互相獨立的事，美股掛掉不該讓台股也拿不到。
      const _fmInfo=(ds)=>{
        const ac=new AbortController();
        const timer=setTimeout(()=>ac.abort(),12000);
        return fetch(`${FM}?dataset=${ds}`,{signal:ac.signal})
          .then(r=>r.ok?r.json():Promise.reject(new Error('HTTP '+r.status)))
          .finally(()=>clearTimeout(timer));
      };
      const [sTW,sUS]=await Promise.allSettled([_fmInfo('TaiwanStockInfo'),_fmInfo('USStockInfo')]);
      if(sTW.status==='rejected')console.warn('[loadStockInfo:TW]',sTW.reason);
      if(sUS.status==='rejected')console.warn('[loadStockInfo:US]',sUS.reason);
      const jTW=sTW.status==='fulfilled'?sTW.value:null;
      const jUS=sUS.status==='fulfilled'?sUS.value:null;
      const dTW=(jTW&&jTW.data)||[],dUS=(jUS&&jUS.data)||[];
      const seen={};STOCKLIST=[];STOCKNAME={};
      for(const s of dTW){const id=s.stock_id;if(!id||seen[id])continue;
        if(id.length<4||id.length>6)continue;if(id.length===6&&/^\d+$/.test(id))continue; // 濾掉權證
        seen[id]=1;STOCKNAME[id]=s.stock_name;STOCKLIST.push({id,name:s.stock_name||'',ind:s.industry_category||'',mkt:'TW'})}
      const seenUS={};STOCKNAME_US={};
      for(const s of dUS){const id=s.stock_id;if(!id)continue;
        const nm=(s.stock_name||'').replace(/\s*Common Stock\s*$/i,'');
        STOCKNAME_US[id]=nm;seenUS[id]={id,name:nm,ind:s.Subsector||'',mkt:'US'}}
      STOCKLIST_US=Object.values(seenUS);
      // 2026-10-11（常備.開發-19 順修）：台股清單空（FinMind 402 額度用盡／逾時）不得標成已載入，
      // 否則下面 company_info.json 退路不會執行、空清單還會被寫進快取。
      if(!STOCKLIST.length)throw new Error('FinMind TaiwanStockInfo 清單為空（'+(sTW.status==='rejected'?String(sTW.reason&&sTW.reason.message||sTW.reason):'回應無 data')+'）');
      infoLoaded=true;
      try{
        localStorage.setItem('alpha_info',JSON.stringify({map:STOCKNAME,list:STOCKLIST}));
        localStorage.setItem('alpha_info_us',JSON.stringify({map:STOCKNAME_US,list:STOCKLIST_US}));
      }catch(e){console.warn('[loadStockInfo:cacheWrite]',e);recordGlobalError('loadStockInfo:cacheWrite',e)}
    }catch(e){console.warn('[loadStockInfo:fetch]',e);finmindErr=e;FINMIND_INFO_FAILED_AT=Date.now()}
    // 2026-09-04：FinMind打不到（額度/IP封鎖/離線）時，退回repo內data/company_info.json補台股名稱與搜尋清單
    // （零外部資料，3137檔），不讓自選股列變成只有代號。美股名稱沒有本地備援，維持代號。
    // 錯誤記錄政策：退路成功→FinMind失敗只留console.warn（功能沒壞，不該亮診斷紅字）；
    // 退路也失敗→兩個都記進recordGlobalError（這才是真的壞）。
    if(!infoLoaded){
      try{
        const r=await fetch('data/company_info.json?t='+Date.now());
        if(!r.ok)throw new Error('HTTP '+r.status);
        const d=await r.json();const comps=(d&&d.companies)||{};STOCKNAME=STOCKNAME||{};STOCKLIST=STOCKLIST||[];
        for(const [id,c] of Object.entries(comps)){if(!c||!c.name)continue;if(!STOCKNAME[id]){STOCKNAME[id]=c.name;STOCKLIST.push({id,name:c.name,ind:c.industry||'',mkt:'TW'})}}
        if(Object.keys(STOCKNAME).length){infoLoaded=true;console.warn('[loadStockInfo] FinMind不可用，改用data/company_info.json補台股名稱',Object.keys(comps).length)}
        else throw new Error('company_info.json沒有任何公司名稱');
      }catch(e2){
        console.warn('[loadStockInfo:companyInfoFallback]',e2);recordGlobalError('loadStockInfo:companyInfoFallback',e2);
        if(finmindErr)recordGlobalError('loadStockInfo:fetch',finmindErr);
      }
    }
    infoLoading=false;
  }
  // 2026-10-11（常備.開發-19）全域搜尋：同一個搜尋框同時查①股票代號／名稱（原有，點列加入自選）
  // ②新聞標題（data/news.json）③事件（data/events.json：標題／類型／公司名，含除權息、重大訊息、月營收）
  // ④策略名稱（data/strategies.json），結果分四組顯示。新聞／事件沿用既有 ensureNews()／ensureEvents()
  // 快取，不額外打外部 API；三份檔案各自 allSettled 載入，任一失敗只讓該組顯示「載入失敗」，不影響
  // 股票組。輸入公司名（如「台積電」）時，名稱對到的台股代號（≤5 檔）也會帶出該代號的新聞與事件。
  let GS_STRATS=null,GS_STATE={news:'idle',events:'idle',strategies:'idle'};
  async function ensureStrategiesForSearch(){
    if(GS_STRATS)return GS_STRATS;
    const r=await fetch('data/strategies.json?t='+Math.floor(Date.now()/60000));
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();GS_STRATS=(d&&d.strategies)||[];return GS_STRATS;
  }
  function loadGlobalSearchSources(){
    const jobs=[['news',ensureNews],['events',ensureEvents],['strategies',ensureStrategiesForSearch]];
    jobs.forEach(([k])=>{if(GS_STATE[k]!=='ok')GS_STATE[k]='loading'});
    return Promise.allSettled(jobs.map(([k,fn])=>Promise.resolve().then(fn).then(
      ()=>{GS_STATE[k]='ok'},
      e=>{GS_STATE[k]='err';console.warn('[globalSearch:'+k+']',e);recordGlobalError('globalSearch:'+k,e)})))
      .then(()=>{try{if(document.getElementById('search-sheet').classList.contains('open'))doSearch()}catch(e){console.warn('[globalSearch:rerender]',e);recordGlobalError('globalSearch:rerender',e)}});
  }
  async function openSearch(){
    document.getElementById('search-mask').classList.add('open');
    document.getElementById('search-sheet').classList.add('open');
    document.getElementById('search-input').value='';
    document.getElementById('search-results').innerHTML='<div class="note" style="padding:16px">載入股票清單…</div>';
    const src=loadGlobalSearchSources();
    await loadStockInfo();
    doSearch();
    setTimeout(()=>document.getElementById('search-input').focus(),200);
    return src;
  }
  function closeSearch(){document.getElementById('search-mask').classList.remove('open');document.getElementById('search-sheet').classList.remove('open')}
  function _gsEsc(t){return String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
  function _gsHead(title,n,more){return `<div class="gs-head" style="font-size:11px;font-weight:700;color:var(--ink-3);padding:12px 4px 4px;border-bottom:1px solid var(--hairline)">${title}　${n} 筆${more?`<span style="font-weight:400">（只顯示前 ${more} 筆）</span>`:''}</div>`}
  function _gsStateNote(k,label){
    const st=GS_STATE[k];
    if(st==='loading'||st==='idle')return `<div class="gs-head" style="font-size:11px;font-weight:700;color:var(--ink-3);padding:12px 4px 4px">${label}</div><div class="note" style="padding:8px 4px">${label}載入中…</div>`;
    if(st==='err')return `<div class="gs-head" style="font-size:11px;font-weight:700;color:var(--ink-3);padding:12px 4px 4px">${label}</div><div class="note" style="padding:8px 4px">${label}載入失敗（詳見診斷錯誤 log）</div>`;
    return null;
  }
  function doSearch(){
    const q=document.getElementById('search-input').value.trim();
    const box=document.getElementById('search-results');
    if(!q){box.innerHTML='<div class="note" style="padding:16px">輸入關鍵字開始搜尋：股票代號或公司名（美股用代號如 AAPL）、新聞標題、事件（例：除息、重大訊息）、策略名稱</div>';return}
    const qU=q.toUpperCase();
    const out=[];
    // ① 股票
    const resTW=STOCKLIST.filter(s=>s.id.startsWith(q)||s.name.includes(q));
    const resUS=STOCKLIST_US.filter(s=>s.id.startsWith(qU)||s.name.toUpperCase().includes(qU));
    const nStock=resTW.length+resUS.length;
    const res=[...resTW,...resUS].slice(0,30);
    // 先.八十一-19：repo 名單查不到才向 FinMind 補查（整個工作階段一次），補完重跑；補查失敗寫明原因
    let noHit='查無股票';
    if(!nStock&&INFO_SRC==='repo'){
      if(!FM_NAMES_SUPP){noHit='repo 名單查無，正在向 FinMind 完整名單補查…';finmindNamesSupplement().then(()=>{if(document.getElementById('search-input').value.trim()===q)doSearch()})}
      else noHit='查無股票（repo 名單與 FinMind 補查都沒有）';
      if(FM_NAMES_SUPP&&FM_NAMES_SUPP_DONE&&FM_NAMES_SUPP_DONE.errs.length)noHit=`查無股票（repo 名單沒有；FinMind 補查失敗：${_gsEsc(FM_NAMES_SUPP_DONE.errs.join('；'))}）`;
    }
    out.push(`<div class="gs-group" data-group="stocks">`+_gsHead('股票',nStock,nStock>30?30:0)
      +(res.length?res.map(s=>`<div class="sr" onclick="pickStock('${s.id}')"><div><b>${_gsEsc(s.name)}</b> <span class="sub">${s.id} · ${s.mkt==='US'?'美股':'台股'}</span><div class="sub">${_gsEsc(s.ind)}</div></div><span class="act">${WL.includes(s.id)?'✓ 已加入':'＋ 加入'}</span></div>`).join('')
        :`<div class="note gs-nohit" style="padding:8px 4px">${noHit}</div>`)+`</div>`);
    // 名稱／代號對到的台股（只在 ≤5 檔時用，避免輸入「2」這種短字串把整個市場的新聞事件都帶出來）
    const codeSet=new Set(resTW.length&&resTW.length<=5?resTW.map(s=>s.id):[]);
    // ② 新聞（新到舊）
    let html=_gsStateNote('news','新聞');
    if(!html){
      const pool=(NEWS_CACHE&&NEWS_CACHE.news)||[];
      const all=pool.filter(n=>(n.title||'').toUpperCase().includes(qU)||(n.codes||[]).some(c=>codeSet.has(c)));
      all.sort((a,b)=>(Date.parse(b.published)||0)-(Date.parse(a.published)||0));
      html=_gsHead('新聞',all.length,all.length>10?10:0)+(all.length?all.slice(0,10).map(n=>{
        const ts=Date.parse(n.published);const d=isNaN(ts)?'':new Date(ts+8*3600e3).toISOString().slice(5,10);
        return `<div class="sr" data-url="${_gsEsc(n.url)}" onclick="gsOpenUrl(this.dataset.url)"><div><b style="font-size:13px">${_gsEsc(n.title)}</b><div class="sub">${d} · ${_gsEsc(n.source||'')}${(n.codes||[]).length?' · '+_gsEsc(n.codes.join('、')):''}</div></div><span class="act">原文 ↗</span></div>`}).join('')
        :`<div class="note" style="padding:8px 4px">查無新聞（新聞索引只保留近期 ${pool.length} 篇標題）</div>`);
    }
    out.push(`<div class="gs-group" data-group="news">${html}</div>`);
    // ③ 事件（未來的排前面、由近到遠，之後才是過去的由新到舊）
    html=_gsStateNote('events','事件');
    if(!html){
      const all=((EVENTS_CACHE&&EVENTS_CACHE.events)||[]).filter(e=>(e.title||'').toUpperCase().includes(qU)||(e.type||'').includes(q)||(e.name&&e.name.includes(q))||codeSet.has(e.code));
      const today=new Date(Date.now()+8*3600e3).toISOString().slice(0,10);
      all.sort((a,b)=>{const fa=(a.date||'')>=today,fb=(b.date||'')>=today;if(fa!==fb)return fa?-1:1;return fa?String(a.date).localeCompare(String(b.date)):String(b.date).localeCompare(String(a.date))});
      html=_gsHead('事件',all.length,all.length>10?10:0)+(all.length?all.slice(0,10).map(e=>{
        const nm=e.name||nameOf(e.code)||'';
        return `<div class="sr" data-code="${_gsEsc(e.code||'')}" data-url="${_gsEsc(e.url||'')}" onclick="gsOpenEvent(this.dataset.code,this.dataset.url)"><div><b style="font-size:13px">${e.code?_gsEsc(e.code)+' '+_gsEsc(nm)+'・':''}${_gsEsc(e.title)}</b><div class="sub">${_gsEsc(e.date||'')} · ${_gsEsc(e.type||'事件')} · ${_gsEsc(e.source||'')}</div></div><span class="act">${e.code?'個股 →':'原文 ↗'}</span></div>`}).join('')
        :`<div class="note" style="padding:8px 4px">查無事件</div>`);
    }
    out.push(`<div class="gs-group" data-group="events">${html}</div>`);
    // ④ 策略
    html=_gsStateNote('strategies','策略');
    if(!html){
      const all=(GS_STRATS||[]).filter(s=>[s.name,s.id,s.type,s.status].some(v=>v&&String(v).toUpperCase().includes(qU)));
      html=_gsHead('策略',all.length,0)+(all.length?all.map(s=>`<div class="sr" data-sid="${_gsEsc(String(s.id||'').replace(/[^\w.-]/g,''))}" onclick="gsOpenStrategy(this.dataset.sid)"><div><b style="font-size:13px">${_gsEsc(s.name||s.id)}</b><div class="sub">${_gsEsc(s.type||'')} · ${_gsEsc(s.status||'')}</div></div><span class="act">報告 →</span></div>`).join('')
        :`<div class="note" style="padding:8px 4px">查無策略</div>`);
    }
    out.push(`<div class="gs-group" data-group="strategies">${html}</div>`);
    box.innerHTML=out.join('')+'<div class="note" style="padding:10px 4px">新聞／事件只存標題與連結索引（data/news.json、data/events.json）：點新聞開原文、點事件跳個股頁、點股票加入自選、點策略看報告。非投資建議。</div>';
  }
  function gsOpenUrl(u){try{if(u&&/^https?:\/\//.test(u))window.open(u,'_blank','noopener')}catch(e){console.warn('[gsOpenUrl]',e);recordGlobalError('gsOpenUrl',e)}}
  function gsOpenEvent(code,url){if(code){closeSearch();openStock(code)}else gsOpenUrl(url)}
  function gsOpenStrategy(id){closeSearch();try{go('trade')}catch(e){console.warn('[gsOpenStrategy:go]',e);recordGlobalError('gsOpenStrategy:go',e)}openStrategyReport(id)}
  function pickStock(code){
    if(!WL.includes(code)){WL.push(code);localStorage.setItem('alpha_wl',JSON.stringify(WL));pushWatchlistSoon();pushSettingsSoon();toast('已加入 '+nameOf(code))}
    else{toast('已在自選股中')}
    doSearch();hydrateHome();
  }

  // 2026-08-25 新增：月營收雙圖（上金額/下YoY雙向）+ 觸控玻璃小卡。REV_ROWS 是目前這檔股票
  // 圖上顯示的 8 個月資料，給 setupRevChartTouch() 的手指拖曳事件用來查目前指到哪一根柱。
  let REV_ROWS=[];

  function renderRevTip(r,clientX,clientY){
    const tip=document.getElementById('rev-tip');if(!tip||!r)return;
    const fmt=v=>v==null?'—':(v>=0?'+':'')+v.toFixed(1)+'%';
    tip.innerHTML=`<b class="hd">${r.revenue_year}/${String(r.revenue_month).padStart(2,'0')}</b>
      <div class="row"><span>股價</span><b>${r.price!=null?nf(r.price):'—'}</b></div>
      <div class="row"><span>營收</span><b>${nf(Math.round(r.revenue/1e8))} 億</b></div>
      <div class="row"><span>月增率 MoM</span><b class="${r.mom>=0?'pos':'neg'}">${fmt(r.mom)}</b></div>
      <div class="row"><span>年增率 YoY</span><b class="${r.yoy>=0?'pos':'neg'}">${fmt(r.yoy)}</b></div>`;
    const app=document.getElementById('app'),rect=app.getBoundingClientRect();
    const tipW=190,tipH=124;
    let x=clientX+14,y=clientY-tipH-14;
    if(x+tipW>rect.right)x=clientX-tipW-14;
    if(x<rect.left)x=rect.left+4;
    if(y<rect.top)y=clientY+18;
    if(y+tipH>rect.bottom)y=rect.bottom-tipH-4;
    tip.style.left=x+'px';tip.style.top=y+'px';
    tip.classList.add('show');
  }
  function hideRevTip(){const t=document.getElementById('rev-tip');if(t)t.classList.remove('show')}
  function setupRevChartTouch(){
    const wrap=document.getElementById('rev-chart-wrap');if(!wrap)return;
    let active=false;
    const pick=clientX=>{
      const n=REV_ROWS.length;if(!n)return null;
      const rect=wrap.getBoundingClientRect();
      let idx=Math.floor((clientX-rect.left)/rect.width*n);
      return REV_ROWS[Math.max(0,Math.min(n-1,idx))];
    };
    const onMove=e=>{
      if(!active)return;
      const t=e.touches?e.touches[0]:e;
      const r=pick(t.clientX);if(r)renderRevTip(r,t.clientX,t.clientY);
      if(e.cancelable)e.preventDefault();
    };
    const onStart=e=>{
      active=true;
      const t=e.touches?e.touches[0]:e;
      const r=pick(t.clientX);if(r)renderRevTip(r,t.clientX,t.clientY);
    };
    const onEnd=()=>{active=false;hideRevTip()};
    wrap.addEventListener('touchstart',onStart,{passive:true});
    wrap.addEventListener('touchmove',onMove,{passive:false});
    wrap.addEventListener('touchend',onEnd);
    wrap.addEventListener('touchcancel',onEnd);
    wrap.addEventListener('mousedown',onStart);
    wrap.addEventListener('mousemove',onMove);
    window.addEventListener('mouseup',onEnd);
  }
  function editWL(){openSearch()}
  // 2026-09-27新增（紙.一）、2026-10-06擴充（先.二十七-二）：紙.一(0050/定存70/30)與
  // 紙.一b(0050 45%/00646 45%/00697B 10%，即Bb-90台灣可執行版)並列的前進式紙上追蹤卡片。
  // 資料只讀data/paper_7030.json與data/paper_1b.json，不寫死任何數字。兩張卡各自
  // 獨立fetch與try/catch：一邊失敗只影響那一邊，不連帶中斷另一邊或其他分頁。
  // 下次再平衡日期為前端依「as_of_date所屬月份的最後一個平日」估算，標「預計」
  // （實際以交易日曆為準，遇連假會提前）。
  function _paperEsc(t){return String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
  // 先.二十七-三：紙.一首次月底記帳／紙.一b啟動逾期未寫入→紅色橫幅（沿用先.十四的做法：
  // 首頁一載入就評估，不等使用者點進分頁）。資料來自market.yml「紙上追蹤看守」步驟寫出的
  // data/paper_tracking_watch.json。抓檔失敗＝視為沒有告警（fail open，CLAUDE.md十二）；
  // 但看守檔本身超過96小時沒更新要另外告警（監控的監控，CLAUDE.md十一）。
  function renderPaperTrackingBanner(doc){
    try{
      const el=document.getElementById('paper-tracking-banner');if(!el)return;
      if(!doc){el.style.display='none';el.innerHTML='';return;}
      const gen=doc.generated_at?Date.parse(doc.generated_at):NaN;
      const ageH=isNaN(gen)?null:(Date.now()-gen)/3600000;
      const lines=[];
      if(doc.status==='ERROR'){
        (doc.items||[]).forEach(i=>lines.push('⚠️ '+_paperEsc(i.msg)));
      }
      if(ageH!=null&&ageH>96)lines.push('⚠️ 紙上追蹤看守檔已超過96小時未更新（看守員可能停擺）');
      uiRedBanner(el,lines.map(x=>x.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&').replace(/&quot;/g,'"')));  // 先.七十二-A3 兩段式
    }catch(e){console.warn('[renderPaperTrackingBanner]',e);recordGlobalError('renderPaperTrackingBanner',e);}
  }
  async function loadPaperTrackingBanner(){
    let doc=null;
    try{const r=await fetch('data/paper_tracking_watch.json?t='+Date.now());if(r.ok)doc=await r.json();}
    catch(e){console.warn('[loadPaperTrackingBanner]',e);}
    renderPaperTrackingBanner(doc);
  }

  // ── IBKR Paper 下單卡片（2026-09-02新增，真的會打本機research/ibkr_order_server.py） ──
  const IBKR_ORDER_SERVER='http://127.0.0.1:8793';
  let IBKR_STATE={side:'BUY',orderType:'MKT',connected:false};
  function readIbkrToken(){try{return localStorage.getItem('alpha_ibkr_token')||''}catch(e){console.warn('[readIbkrToken]',e);return''}}
  function saveIbkrToken(){try{localStorage.setItem('alpha_ibkr_token',document.getElementById('ibkr-token').value.trim())}catch(e){console.warn('[saveIbkrToken]',e);recordGlobalError('saveIbkrToken',e)}}
  // .btn.ghost在CSS裡定義在.btn.buy/.btn.sell之後，同specificity會蓋掉背景色，
  // 不能靠疊加class做「選中態」高亮，改用行內style直接控制，避免cascade順序陷阱。
  function _segStyle(el,on,onBg,onFg){
    el.style.background=on?onBg:'';el.style.color=on?onFg:'';
  }
  function setIbkrSide(side){
    IBKR_STATE.side=side;
    _segStyle(document.getElementById('ibkr-side-buy'),side==='BUY','var(--up-deep)','#fff');
    _segStyle(document.getElementById('ibkr-side-sell'),side==='SELL','var(--down-deep)','#fff');
    document.getElementById('ibkr-submit-btn').className='btn '+(side==='BUY'?'buy':'sell');
    document.getElementById('ibkr-submit-btn').textContent=(side==='BUY'?'送出模擬買進':'送出模擬賣出')+'委託（IBKR Paper）';
  }
  function setIbkrOrderType(t){
    IBKR_STATE.orderType=t;
    _segStyle(document.getElementById('ibkr-type-mkt'),t==='MKT','var(--accent)','#fff');
    _segStyle(document.getElementById('ibkr-type-lmt'),t==='LMT','var(--accent)','#fff');
    document.getElementById('ibkr-limit-row').style.display=t==='LMT'?'flex':'none';
  }
  function updateIbkrPreview(){/* 目前僅數量輸入即時性檢查用，實際部位/資金要打API才有真數字，見checkIbkrHealthAndAccount() */}
  function closeIbkrSheet(){
    document.getElementById('ibkr-mask').classList.remove('open');
    document.getElementById('ibkr-sheet').classList.remove('open');
  }
  async function submitIbkrOrderUI(){
    const resEl=document.getElementById('ibkr-result');
    const token=readIbkrToken();
    const qty=parseInt(document.getElementById('ibkr-qty').value,10);
    const limitPrice=document.getElementById('ibkr-limit-price').value;
    if(!token){resEl.textContent='請先貼上本機驗證token（伺服器終端機啟動時會印出）';resEl.className='note neg';return}
    if(!qty||qty<=0){resEl.textContent='數量必須是正整數';resEl.className='note neg';return}
    if(IBKR_STATE.orderType==='LMT'&&!limitPrice){resEl.textContent='限價單必須輸入限價';resEl.className='note neg';return}
    if(!IBKR_STATE.connected){resEl.textContent='目前連不上本機下單伺服器，無法送單（見上方「連線狀態」）';resEl.className='note neg';return}
    const btn=document.getElementById('ibkr-submit-btn');
    btn.disabled=true;btn.style.opacity='.5';
    resEl.textContent='送出中…';resEl.className='note';
    try{
      const body={symbol:currentCode,action:IBKR_STATE.side,quantity:qty,order_type:IBKR_STATE.orderType};
      if(IBKR_STATE.orderType==='LMT')body.limit_price=parseFloat(limitPrice);
      const r=await fetch(IBKR_ORDER_SERVER+'/submit_order',{
        method:'POST',
        headers:{'Content-Type':'application/json','X-Alpha-Local-Token':token},
        body:JSON.stringify(body),
      });
      const j=await r.json();
      if(!r.ok){resEl.textContent='被拒絕：'+(j.detail||JSON.stringify(j));resEl.className='note neg'}
      else{
        resEl.textContent=`狀態：${j.status} · 成交 ${j.filled}/${qty} 股 · 均價 ${j.avg_fill_price||'—'} · 委託編號 ${j.order_id}`;
        resEl.className='note pos';
        toast('✓ IBKR Paper 委託已送出，狀態：'+j.status);
      }
    }catch(e){
      resEl.textContent=_isOfflineErr(e)?('送出失敗：'+liveOfflineText()):('送出失敗（伺服器回應錯誤）：'+(e.message||e));
      resEl.className='note neg';
      console.warn('[submitIbkrOrderUI]',e);recordGlobalError('submitIbkrOrderUI',e);
    }finally{
      btn.disabled=false;btn.style.opacity='1';
    }
  }

  // ── 機器人開關 ──
  function flipBot(el,name){
    el.classList.toggle('on');
    const on=el.classList.contains('on');
    el.closest('.card').classList.toggle('paused',!on);
    toast(on?('▶ 策略 '+name+' 已恢復運行'):('⏸ 策略 '+name+' 已暫停，持倉不受影響'));
  }

  // ── Toast ──
  let tmr;
  // 2026-08-28新增（使用者回報「所有重新整理按鈕都按不動」）：實測發現按鈕
  // 本身的onclick都有正確觸發fetch（見smoke_test.mjs check 8），真正的問題是
  // 「沒有任何視覺回饋」——home-updated-tm/market-updated-tm這兩個「最後更新」
  // 時間戳欄位存在於HTML卻從來沒有任何JS寫入過（死欄位，永遠卡在--:--），
  // 使用者看不到任何變化，感覺上就是「按了沒反應」。這個共用helper讓每個
  // 重新整理按鈕點下去：文字先變「更新中…」＋暫時不可再點－>執行實際重整
  // 邏輯->成功就更新對應的時間戳欄位＋toast確認->無論成功失敗都還原按鈕文字。
  async function refreshTap(el,tsElId,fn){
    if(!el){await fn();return}
    const orig=el.textContent;
    el.textContent='更新中…';el.style.pointerEvents='none';
    try{
      await fn();
      // 2026-08-28修正（P0-a）：原本toLocaleTimeString('zh-TW',...)沒指定
      // timeZone，依賴裝置本地時區，改用fmtTzHHMM()明確指定Asia/Taipei。
      if(tsElId){const tsEl=document.getElementById(tsElId);if(tsEl)tsEl.textContent=fmtTzHHMM(new Date(),'Asia/Taipei')}
      toast('已更新');
    }catch(e){
      console.warn('[refreshTap]',e);recordGlobalError('refreshTap',e);
      toast('更新失敗，請重試');
    }finally{
      el.textContent=orig;el.style.pointerEvents='';
    }
  }
  // 2026-08-28新增：下拉重新整理（pull-to-refresh）。只有#main捲到最頂端
  // （scrollTop===0）時才開始追蹤下拉距離，避免跟頁面內本身的上下捲動互相
  // 干擾；每個分頁對應到自己的重整動作，跟按鈕(refreshTap)共用同一套邏輯。
  const PTR_TAB_ACTIONS={
    home:()=>{fmClearCache();return hydrateHome()},
    market:()=>{fmClearCache();return hydrateMarket()},
    picks:()=>{fmClearCache();return hydratePicks(true)},
  };
  const PTR_THRESHOLD=64;
  function setupPullToRefresh(){
    const mainEl=document.getElementById('main'),indEl=document.getElementById('ptr-indicator');
    if(!mainEl||!indEl)return;
    let startY=null,pulling=false,triggered=false;
    mainEl.addEventListener('touchstart',e=>{
      if(mainEl.scrollTop>0){startY=null;return}
      startY=e.touches[0].clientY;pulling=true;triggered=false;
    },{passive:true});
    mainEl.addEventListener('touchmove',e=>{
      if(!pulling||startY===null)return;
      const dy=e.touches[0].clientY-startY;
      if(dy<=0){indEl.style.transform='translate(-50%,-100%)';return}
      const dist=Math.min(dy*0.5,PTR_THRESHOLD*1.4);
      indEl.style.transform=`translate(-50%, ${dist-40}px)`;
      indEl.textContent=dist>=PTR_THRESHOLD?'↑ 放開重新整理':'↓ 下拉重新整理';
      triggered=dist>=PTR_THRESHOLD;
    },{passive:true});
    mainEl.addEventListener('touchend',async()=>{
      if(!pulling)return;
      pulling=false;
      if(triggered){
        const action=PTR_TAB_ACTIONS[CURRENT_TAB];
        indEl.textContent='更新中…';indEl.style.transform='translate(-50%, 24px)';
        if(action){
          try{await action();toast('已更新')}
          catch(e){console.warn('[pullToRefresh]',e);recordGlobalError('pullToRefresh',e);toast('更新失敗，請重試')}
        }else{
          toast('此頁無需下拉更新');
        }
      }
      indEl.style.transform='translate(-50%,-100%)';
      startY=null;triggered=false;
    });
  }
  function toast(msg){
    const t=document.getElementById('toast');
    t.textContent=msg; t.classList.add('show');
    clearTimeout(tmr); tmr=setTimeout(()=>t.classList.remove('show'),2400);
  }
  function chip(label,active,onclick){
    return `<span class="press" style="flex-shrink:0;white-space:nowrap;font-size:12px;font-weight:${active?600:400};color:${active?'#1a1005':'var(--ink-2)'};background:${active?'var(--gold-grad)':'rgba(var(--fg-rgb),.05)'};border:1px solid ${active?'transparent':'rgba(var(--fg-rgb),.08)'};padding:6px 13px;border-radius:999px;cursor:pointer" onclick="${onclick}">${label}</span>`;
  }
  function closeIndustrySheet(){
    document.getElementById('industry-mask').classList.remove('open');
    document.getElementById('industry-sheet').classList.remove('open');
  }

  // ══════ 2026-09-03深夜（乙.4）本機即時伺服器：偵測→SSE接管→連不上退回冷資料 ══════
  // 伺服器=research/alpha_live_server.py（三端點一律要X-Alpha-Local-Token）。瀏覽器原生
  // EventSource不能帶自訂標頭，所以這裡用fetch()讀text/event-stream自己切事件——刻意
  // 為了保住token驗證（使用者補充指令三），不是不會用EventSource。
  // ── 2026-09-04 P0產品.一：首頁細狀態列（可展開）。摘要一行＋一顆小點，展開才看得到
  // 最後更新／即時連線／輪詢文案／匯率。小點：綠=即時連線且資料新鮮、黃=已設定但離線或資料延遲、灰=盤後/未設定。
  function toggleHomeStatus(){const st=document.getElementById('home-status-strip'),d=document.getElementById('home-status-detail');if(!st||!d)return;const open=d.hidden;d.hidden=!open;st.classList.toggle('open',open)}
  function renderHomeStatusSummary(){
    const el=document.getElementById('home-status-summary'),dot=document.getElementById('home-status-dot');if(!el||!dot)return;
    const zTw=zonedNow('Asia/Taipei');const twOpen=zTw.wd>=1&&zTw.wd<=5&&(zTw.h*60+zTw.mi)>=540&&(zTw.h*60+zTw.mi)<810;
    const usSess=usMarketSession(zonedNow('America/New_York'));
    // 2026-09-15（週六.六／稽核二.五）週末/國定假日跟「交易日已收盤」是兩種不同狀態，
    // 不該共用「已收盤」這個字——已收盤暗示「今天有開、現在收了」，週末/假日根本沒開盤。
    // 沿用既有交易日曆isTradingDay()/TW_HOLIDAYS_2026（健檢.一同一份），不新增假日表。
    const twTradingDay=isTradingDay(new Date(),'Asia/Taipei',TW_HOLIDAYS);
    const twTxt='台股'+(twOpen?'盤中':(twTradingDay?'已收盤':'休市')),usTxt='美股'+({pre:'盤前',regular:'盤中',post:'盤後',closed:'休市'}[usSess]||'休市');
    let liveTxt,cls;
    if(LIVE.connected){liveTxt=LIVE.streamMode==='tick-push'?'即時逐筆':'即時連線';cls='g'}
    else if(LIVE.configured){liveTxt='離線（最後收盤 '+lastCloseLabel()+'）';cls='y'}
    else{liveTxt='未設即時源';cls='gr'}
    if(!twOpen&&usSess==='closed'&&cls==='g')cls='gr';  // 全部收盤時即使連著也是灰（沒有在動的東西）
    const upd=document.getElementById('home-updated-tm');const updTxt=upd&&upd.textContent&&upd.textContent!=='--:--'?' · 更新 '+upd.textContent:'';
    const txt=`${twTxt} · ${usTxt} · ${liveTxt}${updTxt}`;
    if(el.textContent!==txt)el.textContent=txt;
    dot.className='sdot '+cls;
  }
  // ── 2026-09-08（自動連線一）端點自動發現 ───────────────────────────────
  // **總司令裁示：不該讓使用者每次手填伺服器網址。**
  // 原本「網址不寫進公開 repo」的理由不成立——Tailscale 官方文件載明所有 TLS
  // 憑證都記錄在憑證透明度（CT）公開帳本、含裝置完整網域名稱，且實測 Funnel
  // 開通不到一分鐘即遭外部掃描。**網址早已公開，隱藏它零安全效益**，
  // 卻造成每台裝置都要手動設定、架構一變更全部裝置斷線。
  //
  // token 不在這裡面，也永遠不會進 repo——端點本身仍然要求 token 才給資料，
  // /health 與 /whoami 是刻意設計的免 token 診斷端點。
  let LIVE_ENDPOINTS=null,DISCOVERY={running:false,at:0,tookMs:null,picked:null,tried:[]};
  const LIVE_FAIL_STREAK={n:0};
  async function fetchEndpointList(){
    if(LIVE_ENDPOINTS)return LIVE_ENDPOINTS;
    try{
      const r=await fetch('data/live_endpoints.json?t='+Math.floor(Date.now()/60000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      LIVE_ENDPOINTS=(d.endpoints||[])
        .filter(e=>e&&e.enabled&&e.url)
        .sort((a,b)=>(a.priority||99)-(b.priority||99));
    }catch(e){
      console.warn('[fetchEndpointList]',e);recordGlobalError('fetchEndpointList',e);
      LIVE_ENDPOINTS=[];
    }
    return LIVE_ENDPOINTS;
  }
  // 並行打所有候選的 /health（免 token、2 秒逾時），第一個回 {ok:true} 的勝出。
  // 並行不是為了快看——是因為候選端點彼此獨立，序列試會讓「第一個掛掉」
  // 白白拖慢所有人 2 秒。
  async function discoverLiveEndpoint(force){
    if(DISCOVERY.running)return null;
    // 手動覆寫優先：使用者自己填了就尊重他，不要偷偷換掉（裁示一.5）
    if(!force&&localStorage.getItem('alpha_live_url_manual')==='1')return null;
    DISCOVERY.running=true;
    const t0=Date.now();DISCOVERY.tried=[];
    try{
      const list=await fetchEndpointList();
      if(!list.length){DISCOVERY.picked=null;return null}
      const probe=(ep)=>new Promise(resolve=>{
        const ac=new AbortController();
        const timer=setTimeout(()=>{ac.abort()},2000);
        fetch(ep.url+'/health',{cache:'no-store',signal:ac.signal})
          .then(r=>r.ok?r.json():null)
          .then(j=>resolve(j&&j.ok===true?ep:null))
          .catch(()=>resolve(null))
          .finally(()=>clearTimeout(timer));
      });
      const results=await Promise.all(list.map(ep=>probe(ep).then(ok=>{
        DISCOVERY.tried.push({url:ep.url,label:ep.label,ok:!!ok});
        return ok;
      })));
      // 依 priority 順序取第一個成功的（list 已排序，results 同序）
      const hit=results.find(Boolean)||null;
      DISCOVERY.tookMs=Date.now()-t0;
      DISCOVERY.at=Date.now();
      DISCOVERY.picked=hit?{url:hit.url,label:hit.label}:null;
      if(hit){
        localStorage.setItem('alpha_live_url',hit.url);
        localStorage.setItem('alpha_live_url_label',hit.label||'');
        LIVE_FAIL_STREAK.n=0;
      }
      return hit;
    }catch(e){
      console.warn('[discoverLiveEndpoint]',e);recordGlobalError('discoverLiveEndpoint',e);
      return null;
    }finally{DISCOVERY.running=false}
  }
  // 執行中自我修復：連續失敗 3 次就重跑一次發現（裁示一.3）
  async function liveSelfHeal(reason){
    LIVE_FAIL_STREAK.n++;
    if(LIVE_FAIL_STREAK.n<3)return;
    LIVE_FAIL_STREAK.n=0;
    const before=LIVE.url;
    const hit=await discoverLiveEndpoint();
    if(hit&&hit.url!==before){
      loadLiveConfig();
      toast('已自動切換至 '+(hit.label||hit.url));
      restartLiveStream();
    }
    console.warn('[liveSelfHeal]',reason,'→',hit?hit.url:'仍無可用端點');
  }
  function loadLiveConfig(){
    try{
      LIVE.url=((localStorage.getItem('alpha_live_url')||'').trim().replace(/\/+$/,''))||null;
      LIVE.token=(localStorage.getItem('alpha_live_token')||'').trim()||null;
      LIVE.cfId=(localStorage.getItem('alpha_cf_access_id')||'').trim()||null;
      LIVE.cfSecret=(localStorage.getItem('alpha_cf_access_secret')||'').trim()||null;
    }
    catch(e){console.warn('[loadLiveConfig]',e);LIVE.url=null;LIVE.token=null;LIVE.cfId=null;LIVE.cfSecret=null}
    LIVE.configured=!!(LIVE.url&&LIVE.token);
  }
  // 2026-09-08（連線四.1）舊區網位址偵測。判定條件照總司令指定：
  // 私有網段（10./172.16-31./192.168.）或帶 :8001。
  // 為什麼「:8001 也算」：即使有人填了 ts.net 卻手動加上 :8001，
  // Funnel 對外只走 443，帶 port 一樣連不到——那也是同一個舊用法的殘留。
  function legacyLiveUrlReason(url){
    if(!url)return null;
    let host='',port='';
    try{const u=new URL(/^https?:\/\//i.test(url)?url:'https://'+url);host=u.hostname;port=u.port}
    catch(e){return null}
    if(/^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)/.test(host))return 'private';
    if(port==='8001')return 'port8001';
    return null;
  }
  // 2026-09-08（連線五.1）把實際生效的網址完整顯示出來，可換行不截斷。
  function renderLiveUrlFull(){
    const box=document.getElementById('live-url-full');if(!box)return;
    if(!LIVE.url){box.style.display='none';box.innerHTML='';return;}
    box.style.display='';
    box.innerHTML='<div style="display:flex;gap:8px;align-items:flex-start">'
      +'<span style="color:var(--ink-4);flex-shrink:0">目前生效</span>'
      +'<span class="num" id="live-url-full-text" style="flex:1;word-break:break-all;color:var(--ink-2);line-height:1.5">'
      +String(LIVE.url).replace(/</g,'&lt;')+'</span>'
      +'<button class="press" onclick="copyLiveUrl()" style="flex-shrink:0;font-size:11px;padding:3px 9px;border-radius:6px;border:1px solid var(--hairline);background:transparent;color:var(--accent);cursor:pointer">複製</button>'
      +'</div>';
  }
  async function copyLiveUrl(){
    try{
      await navigator.clipboard.writeText(LIVE.url||'');
      toast('已複製完整網址');
    }catch(e){
      // clipboard API 在非安全內容或權限被擋時會失敗——退回選取文字，
      // 讓使用者自己長按複製，而不是靜默什麼都沒發生。
      console.warn('[copyLiveUrl]',e);
      try{
        const el=document.getElementById('live-url-full-text');
        if(el){const r=document.createRange();r.selectNodeContents(el);
          const sel=getSelection();sel.removeAllRanges();sel.addRange(r);}
        toast('無法自動複製，已為你選取網址，請長按複製');
      }catch(e2){console.warn('[copyLiveUrl:fallback]',e2);toast('複製失敗，請手動選取')}
    }
  }
  // 2026-09-08（自動連線一.2）把發現過程顯示出來——耗時與選中端點。
  function renderDiscovery(){
    const box=document.getElementById('live-discovery');if(!box)return;
    const manual=localStorage.getItem('alpha_live_url_manual')==='1';
    if(manual){
      box.innerHTML='<span style="color:var(--warn)">使用手動端點，已停用自動發現。</span>'
        +'（清空下方「進階」裡的網址欄即可恢復自動）';
      return;
    }
    if(DISCOVERY.running){box.textContent='正在自動尋找可用的伺服器…';return}
    if(!DISCOVERY.at){box.textContent='尚未執行自動發現。';return}
    const tried=DISCOVERY.tried.map(t=>(t.ok?'✓ ':'✗ ')+t.label).join('　');
    if(DISCOVERY.picked){
      box.innerHTML='<b style="color:var(--up)">已自動連上：'+DISCOVERY.picked.label+'</b>'
        +'（耗時 '+DISCOVERY.tookMs+' ms）<br>'
        +'<span style="color:var(--ink-4)">候選：'+tried+'</span><br>'
        +'<span style="color:var(--ink-4)">你不需要手動填網址。日後端點變更由 data/live_endpoints.json 統一更新，裝置端不用動。</span>';
    }else{
      box.innerHTML='<b style="color:var(--status-bad)">所有候選端點都連不上</b>（耗時 '+DISCOVERY.tookMs+' ms）<br>'
        +'<span style="color:var(--ink-4)">候選：'+(tried||'清單為空')+'</span><br>'
        +'<span style="color:var(--ink-4)">請確認家中 PC 的即時伺服器有在跑。</span>';
    }
  }
  // 2026-09-08（自動連線二.4）IBKR 權杖每週日 01:00 ET 失效，到期前 24 小時起提醒。
  function renderIbkrTokenWarn(){
    const box=document.getElementById('ibkr-token-warn');if(!box)return;
    try{
      const z=_zonedParts(new Date(),'America/New_York');
      // 下一個「週日 01:00 ET」距離現在幾小時。wd: 0=週日
      const nowMin=z.wd*24*60+z.h*60+z.mi;
      const targetMin=0*24*60+1*60;            // 週日 01:00
      let diffMin=targetMin-nowMin;
      if(diffMin<=0)diffMin+=7*24*60;          // 已過就算下一週
      const hrs=diffMin/60;
      // 剛過期的判定：週日 01:00 之後、且 Gateway 這邊沒有新鮮資料
      const stale=INTRADAY_IBKR&&!INTRADAY_IBKR.connected;
      if(hrs>24&&!stale){box.innerHTML='';box.style.display='none';return}
      box.style.display='';
      const msg=stale
        ? '<b>IBKR 權杖可能已到期</b>——伺服器回報未連上 Gateway。請到 PC 上重新登入 IB Gateway。'
        : 'IBKR 權杖將於約 '+Math.round(hrs)+' 小時後（美東週日 01:00）到期，屆時需在 PC 上手動重登一次 Gateway。';
      box.innerHTML='<div style="border:1px solid var(--gold);border-radius:8px;padding:8px 10px;background:rgba(212,168,75,.08);font-size:11.5px;color:var(--ink-2);line-height:1.6">⚠ '
        +msg+'<br><span style="color:var(--ink-4)">這是 IBKR 官方的每週安全機制，沒有合規的自動化解法。</span></div>';
    }catch(e){console.warn('[renderIbkrTokenWarn]',e);recordGlobalError('renderIbkrTokenWarn',e)}
  }
  function renderLegacyLiveWarn(){
    const box=document.getElementById('live-url-legacy-warn');if(!box)return;
    const reason=legacyLiveUrlReason(LIVE.url);
    if(!reason){box.style.display='none';box.innerHTML='';return;}
    const what=reason==='private'
      ?'此為<b>舊版區網位址</b>'
      :'此網址帶了 <span class="num">:8001</span>，那是<b>舊版區網用法</b>';
    box.style.display='';
    box.innerHTML='<div style="border:1px solid var(--gold);border-radius:8px;padding:9px 10px;background:rgba(212,168,75,.08)">'
      +'<div style="font-size:12px;color:var(--ink-2);line-height:1.6">'
      +'⚠ '+what+'，伺服器已改走 <b>Tailscale</b>，'
      +'請改填 <span class="num">ts.net</span> 網址（<b>不需加 port</b>）。'
      +'<br><span style="color:var(--ink-4)">這個位址在任何網路下都連不到，'
      +'所以測試連線只會一直逾時——不是網路問題，是網址過期了。</span></div>'
      +'<button class="press" onclick="clearLegacyLiveUrl()" style="margin-top:8px;font-size:11.5px;padding:5px 12px;border-radius:7px;border:1px solid var(--gold);background:transparent;color:var(--gold);cursor:pointer">清除舊網址</button>'
      +'</div>';
  }
  function clearLegacyLiveUrl(){
    try{
      localStorage.removeItem('alpha_live_url');
      const u=document.getElementById('set-live-url');if(u)u.value='';
      toast('已清除舊網址，請填入 ts.net 網址');
    }catch(e){console.warn('[clearLegacyLiveUrl]',e);recordGlobalError('clearLegacyLiveUrl',e)}
    loadLiveConfig();renderLiveStatus();
  }
  function liveHeaders(){
    const h={'X-Alpha-Local-Token':LIVE.token||''};
    // 兩個都有才送。只填一個是設定沒填完，送半組只會換來一個難查的 403，
    // 不如當成沒設定、讓「測試連線」照既有路徑誠實回報連不上。
    if(LIVE.cfId&&LIVE.cfSecret){h['CF-Access-Client-Id']=LIVE.cfId;h['CF-Access-Client-Secret']=LIVE.cfSecret}
    return h;
  }
  // 2026-09-06（CF.2/CF.3）credentials:'include'：Cloudflare Access 通過驗證後會在
  // live.<domain> 種 CF_Authorization cookie，但 App 是從 github.io 打過去的跨來源
  // 請求，預設不會帶 cookie，Access 會把請求導去登入頁，前端只看得到一個沒有 CORS
  // 標頭的失敗。伺服器端已對應回 Access-Control-Allow-Credentials: true 且用精確
  // 來源（帶 credentials 時瀏覽器禁止 Allow-Origin: *）。
  // 區網直連（http://192.168.x.x:8001）沒有 cookie 也不受影響，這個選項是安全的。
  async function liveFetch(path,timeoutMs){
    const ac=new AbortController();const t=setTimeout(()=>ac.abort(),timeoutMs||4000);
    try{
      const r=await fetch(LIVE.url+path,{headers:liveHeaders(),cache:'no-store',credentials:'include',signal:ac.signal});
      _liveMarkOk();LIVE.offline=false;return r;
    }catch(e){if(_isOfflineErr(e)){LIVE.offline=true;throw _offlineErr(e)}throw e}
    finally{clearTimeout(t)}
  }
  // ── 2026-09-15（開發佇列自走，週六.五）首頁總資產卡 ──────────────────────────
  // 券商唯讀資料經live server：/live/positions（Shioaji list_positions+IBKR部位）、
  // /live/balance（Shioaji account_balance+IBKR帳戶摘要），見
  // research/alpha_live_server.py。三種畫面狀態：
  //   1. 沒設定即時伺服器 → 維持原本「串接券商帳戶→」CTA（既有行為不動）。
  //   2. 有設定但兩個broker都查無資料（非交易時段/常駐行程沒在跑/Gateway沒開）
  //      → CTA文案換成過渡說明，不能繼續講「尚未串接」（其實已經串了，只是
  //      暫時查不到），也不能假裝有數字。
  //   3. 至少一個broker有真數字 → 顯示總資產卡，換算成NTD用data-ntd交給既有
  //      renderCcyAmounts()（見「幣別切換」那節）畫成NT$/US$。
  // Shioaji的account_balance()只回現金餘額（acc_balance），不含持股市值，這裡
  // 用positions的quantity×last_price自己加總——這是概算（沒有計入手續費/稅），
  // 卡片文字與note已誠實標「概算，非交易確認」。IBKR用NetLiquidation（IBKR官方
  // 算好的帳戶淨值，含現金+持股市值，比自己重算可靠），USD需要FX_RATE才能併入
  // NTD總額，匯率沒有時該部分誠實跳過並在detail說明，不用舊匯率硬湊。
  // 先.二十九：自動交易狀態／否決窗／緊急停止（只經 /auto/*，不具下單能力）
  // 先.三十-四：破億路徑（輸入只存本機設定，不進 repo）
  // 先.八十-7（2026-10-12）：破億推算用的年化不再寫死 10.19%，改讀 data/strategy_history.json 的自動投資（Bb-90）回測年化。
  let BT_RATE=null,BT_RATE_LOADING=null;const BT_GOAL=1e8;
  function btEnsureRate(){
    if(BT_RATE!=null)return Promise.resolve(BT_RATE);
    if(!BT_RATE_LOADING)BT_RATE_LOADING=(SC_HIST?Promise.resolve():loadStrategyHistory()).then(()=>{
      const c=SC_HIST&&SC_HIST.lines&&SC_HIST.lines.live_bb90&&SC_HIST.lines.live_bb90.backtest&&SC_HIST.lines.live_bb90.backtest.cagr;
      BT_RATE=(typeof c==='number'&&isFinite(c))?c:null;return BT_RATE;
    }).catch(e=>{console.warn('[btEnsureRate]',e);recordGlobalError('btEnsureRate',e);return null}).finally(()=>{BT_RATE_LOADING=null});
    return BT_RATE_LOADING;
  }
  function btRead(){try{const s=localStorage.getItem('alpha_bt_path');return s?JSON.parse(s):{}}catch(e){console.warn('[btRead]',e);recordGlobalError('btRead',e);return{}}}
  function btCalc(o){
    const goal=o.goal||BT_GOAL,pmt=o.pmt||0;
    const n=(o.target-o.now)/(365.25*86400000);
    if(!(n>0)||!(o.nw>=0))return null;
    const fvAt=(r)=>{const g=Math.pow(1+r,n),m=Math.pow(1+r,1/12)-1;return o.nw*g+pmt*(Math.abs(m)>1e-12?(g-1)/m:12*n)};
    const g=Math.pow(1+o.rate,n),m=Math.pow(1+o.rate,1/12)-1,af=(g-1)/m;
    const fvNo=o.nw*g,fvWith=fvNo+pmt*af;
    const reqNo=o.nw>0?Math.pow(goal/o.nw,1/n)-1:null;
    let reqWith=null;
    if(fvAt(-0.5)<goal){let lo=-0.5,hi=2;if(fvAt(hi)>=goal){for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(fvAt(mid)<goal)lo=mid;else hi=mid}reqWith=(lo+hi)/2}}
    return{n,fvNo,fvWith,reqNo,reqWith,needPmt:Math.max(0,(goal-fvNo)/af)};
  }
  function btFmt(v){if(v==null||!isFinite(v))return'—';return v>=1e8?'NT$ '+(v/1e8).toFixed(2)+' 億':'NT$ '+Math.round(v/1e4).toLocaleString()+' 萬'}
  function btPct(v){return v==null||!isFinite(v)?'—':(v*100).toFixed(2)+'%'}
  function renderBtPath(){
    const out=document.getElementById('bt-out');if(!out)return;
    const s=btRead();
    const set=(id,v)=>{const el=document.getElementById(id);if(el&&document.activeElement!==el&&v!=null)el.value=v};
    set('bt-nw',s.nw);set('bt-pmt',s.pmt);set('bt-birth',s.birth);set('bt-age',s.age==null?40:s.age);
    const nw=Number(s.nw),pmt=Number(s.pmt||0),age=Number(s.age==null||s.age===''?40:s.age);
    if(s.nw===''||s.nw==null||!(nw>=0)||!s.birth){out.textContent='請填入淨資產與出生日期';renderBtProb(null);return}
    const b=new Date(s.birth+'T00:00:00');if(isNaN(b)){out.textContent='出生日期格式不正確';renderBtProb(null);return}
    const target=new Date(b.getFullYear()+age,b.getMonth(),b.getDate());
    if(BT_RATE==null){
      const t0=target.getFullYear()+'-'+String(target.getMonth()+1).padStart(2,'0')+'-'+String(target.getDate()).padStart(2,'0');
      out.innerHTML='目標日期：'+t0+'<br>回測年化讀取中…';
      btEnsureRate().then(r=>{if(r!=null)renderBtPath();else out.innerHTML='目標日期：'+t0+'<br>讀不到回測年化（data/strategy_history.json），暫不推算'});
      renderBtProb({});return;
    }
    const c=btCalc({nw,pmt,target:target.getTime(),now:Date.now(),rate:BT_RATE});
    if(!c){out.textContent='目標日期已過或輸入不合理，請調整目標年齡';renderBtProb(null);return}
    try{renderBtProb({nw,pmt,nmon:Math.round(c.n*12)})}catch(e){console.warn('[renderBtProb]',e);recordGlobalError('renderBtProb',e)}
    const d=target.getFullYear()+'-'+String(target.getMonth()+1).padStart(2,'0')+'-'+String(target.getDate()).padStart(2,'0');
    out.innerHTML=['目標日期：'+d+'（剩 '+c.n.toFixed(1)+' 年）',
      '需要年化報酬（不再投入）：'+btPct(c.reqNo),
      '需要年化報酬（含每月投入）：'+btPct(c.reqWith),
      '以 '+btPct(BT_RATE)+'（回測，非保證）推算到目標日：不投入 '+btFmt(c.fvNo)+'；含每月投入 '+btFmt(c.fvWith),
      '要達 1 億，每月需投入：'+btFmt(c.needPmt)].join('<br>');
  }
  // 先.五十九-B5：達標機率。只抓公開檔 data/strategy_monthly_returns.json（回測月報酬，不含個資），
  // 在瀏覽器內用本機四欄參數以 12 個月區塊自助法抽樣 5,000 次；參數不送出、不寫入任何公開檔。
  const BT_PROB={B:5000,block:12,seed:20261010,data:null,loading:null,timer:null};
  function btRng(seed){let a=seed>>>0;return function(){a=(a+0x6D2B79F5)>>>0;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return((t^(t>>>14))>>>0)/4294967296}}
  // 純函式（冒煙用）：R＝{策略:[月報酬...]}，所有策略共用同一組區塊（配對比較，同 R2 做法）
  function btProbCalc(R,o){
    const names=Object.keys(R),T=R[names[0]].length,blk=o.block||12,B=o.B||5000,nmon=o.nmon,goal=o.goal||BT_GOAL;
    if(!(nmon>0)||!(T>blk))return null;
    const rnd=btRng(o.seed==null?20261010:o.seed),nb=Math.ceil(nmon/blk),fin=names.map(()=>new Float64Array(B));
    const st=new Int32Array(nb);
    for(let b=0;b<B;b++){
      for(let k=0;k<nb;k++)st[k]=Math.floor(rnd()*(T-blk+1));
      for(let j=0;j<names.length;j++){
        const r=R[names[j]];let w=o.nw,t=0;
        for(let k=0;k<nb&&t<nmon;k++)for(let i=0;i<blk&&t<nmon;i++,t++)w=w*(1+r[st[k]+i])+(o.pmt||0);
        fin[j][b]=w;
      }
    }
    const q=(a,p)=>{const x=Array.from(a).sort((m,n)=>m-n),h=(x.length-1)*p,l=Math.floor(h);return x[l]+(x[Math.min(l+1,x.length-1)]-x[l])*(h-l)};
    const out={};
    names.forEach((k,j)=>{let c=0;for(let b=0;b<B;b++)if(fin[j][b]>=goal)c++;out[k]={p:c/B,p5:q(fin[j],.05),p50:q(fin[j],.5),p95:q(fin[j],.95)}});
    return out;
  }
  async function btProbData(){
    if(BT_PROB.data)return BT_PROB.data;
    if(!BT_PROB.loading)BT_PROB.loading=fetch('data/strategy_monthly_returns.json?t='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}).then(d=>{BT_PROB.data=d;return d}).finally(()=>{BT_PROB.loading=null});
    return BT_PROB.loading;
  }
  // 先.八十-7（2026-10-12）：下架「勝 0050／破億」等樣本內重抽機率（用 2003–2024 回測月報酬自己重抽自己，必然偏樂觀）。
  // 前台不再顯示任何機率數字；btProbCalc 保留給研究與冒煙 #59 驗算，不出現在畫面上。
  const BT_PROB_OFF='樣本內重抽，偏樂觀，不能當依據';
  function renderBtProb(params){
    const el=document.getElementById('bt-prob');if(!el)return;
    if(params){el.innerHTML='<b>假設情境達標比例</b>：已下架——'+BT_PROB_OFF+'。';return}
    el.innerHTML='假設情境達標比例：請先填入淨資產與出生日期。已下架數字：'+BT_PROB_OFF+'。';return;
    const bias='<a href="https://github.com/jlove1314520/alpha-app/blob/main/research/WIN_PROBABILITY_2026-10.md" target="_blank" rel="noopener">偏誤說明（WIN_PROBABILITY_2026-10）</a>';
    if(!params){el.innerHTML='假設情境達標比例：請先填入淨資產與出生日期（每月投入、目標年齡可留預設），填好後在你的瀏覽器內計算，不會送出。';return}
    clearTimeout(BT_PROB.timer);
    el.textContent='假設情境達標比例計算中…';
    BT_PROB.timer=setTimeout(()=>{
      btProbData().then(d=>{
        const res=btProbCalc(d.returns,{nw:params.nw,pmt:params.pmt,nmon:params.nmon,goal:BT_GOAL,B:BT_PROB.B,block:BT_PROB.block,seed:BT_PROB.seed});
        if(!res){el.textContent='假設情境達標比例：期間太短或資料不足，無法計算';return}
        const lab={'0050':'0050 全持有','Bb-90':'Bb-90','S3-C6':'S3-C6（紙.三）','R1-A':'R1-A（紙.四 並列）','R1-C':'R1-C（紙.四 主）'};
        const rows=(d.strategies||Object.keys(res)).filter(k=>res[k]).map(k=>'<tr><td>'+_autoEsc(lab[k]||k)+'</td><td style="text-align:right"><b>'+(res[k].p*100).toFixed(1)+'%</b></td><td style="text-align:right">'+btFmt(res[k].p5)+'</td><td style="text-align:right">'+btFmt(res[k].p50)+'</td><td style="text-align:right">'+btFmt(res[k].p95)+'</td></tr>').join('');
        el.innerHTML='<b>假設情境：歷史重抽樣中 '+params.nmon+' 個月後 ≥ 1 億的比例</b>'
          +'<table style="width:100%;font-size:11px;margin:4px 0"><tr><th style="text-align:left">策略</th><th style="text-align:right">比例</th><th style="text-align:right">期末 5%</th><th style="text-align:right">中位</th><th style="text-align:right">95%</th></tr>'+rows+'</table>'
          +'<div style="color:var(--warn)">⚠ '+_autoEsc(d.label||'回測，非保證')+'：用 '+_autoEsc((d.months||[])[0]||'')+'～'+_autoEsc((d.months||[]).slice(-1)[0]||'')+' 回測月報酬，12 個月區塊自助法抽樣 '+BT_PROB.B.toLocaleString()+' 次（固定種子）；R1 無樣本外驗證。參數只在你的瀏覽器內計算。'+bias+'</div>';
      }).catch(e=>{console.warn('[renderBtProb]',e);recordGlobalError('renderBtProb',e);el.textContent='假設情境達標比例：讀取回測月報酬失敗（'+e.message+'）'});
    },50);
  }
  // 先.三十一-二：橫幅由三個來源合成——本機狀態/緊急停止、本機離線、Pages 上的去識別化排程心跳
  const AUTO_BAN={local:'',offline:'',hb:'',px:''};
  // ══════ 先.七十二-A3（2026-10-11）：紅色橫幅一律「狀況＋下一步」兩段式，細節點開才顯示 ══════
  // 所有紅色橫幅（自動投資異常／本機排程心跳／白名單價格缺漏／本機 Claude 登入／模擬追蹤看守）都走 uiRedBanner()；
  // 原始訊息（含 report_error 寫出的錯誤）先比對 UI_BANNER_RULES 轉成白話兩段，比不到就用 uiPlain() 轉白話後截短。
  // 原始全文放在收合的「細節」裡（不刪，方便回報問題）。
  const UI_BANNER_RULES=[
    // 先.七十三-4：入金不足——第一行只寫白話結論（含下次排程是星期幾），金額等數字一律收進「看細節」
    {re:/餘額查詢失敗/,sit:()=>'查不到帳戶餘額，'+_uiNextWhen()+'先不下單',next:'下次排程自動重試',go:'settings'},
    {re:/資金不足|現金不足|餘額不足|INSUFFICIENT_CASH|未入金|入金/,sit:()=>'還沒入金，'+_uiNextWhen()+'不會下單',next:'入金後自動重跑',go:'settings'},
    {re:/緊急停止|STOP\.flag|STOP_FLAG/,sit:'已按緊急停止，暫不下單',next:'到設定頁解除',go:'settings'},
    {re:/心跳|排程未執行|電腦可能關機|漏跑/,sit:'電腦沒在跑，自動投資暫停',next:'打開電腦就會恢復',go:'settings'},
    {re:/價格缺漏|價格補不到|whitelist_price|白名單.*價格/,sit:'缺 ETF 價格，先不下單',next:'資料補齊後自動重跑',go:'settings'},
    {re:/對帳|RECONCILE/,sit:'帳戶對不起來，先不下單',next:'確認後自動重跑',go:'settings'},
    {re:/登入過期|AUTH_EXPIRED|需要重新登入/,sit:'電腦上的助理要重新登入',next:'在電腦上重新登入',go:'settings'},
    {re:/額度已用盡|QUOTA_EXCEEDED/,sit:'電腦上的助理額度用完',next:'額度恢復後自動續跑',go:'settings'},
    {re:/沒有實際執行|STALLED/,sit:'電腦上的自動工作停了',next:'打開電腦檢查',go:'settings'},
    {re:/拒單|REJECT/i,sit:'這一批被拒單',next:'看拒單原因',go:'settings'},
    {re:/看守檔.*未更新|看守員可能停擺/,sit:'模擬追蹤的檢查停了',next:'等下次排程補上',go:'settings'},
    {re:/月底.*未寫入|未寫入|逾期未/,sit:'模擬追蹤漏記一期',next:'等下次排程補記',go:'settings'},
  ];
  // 下次自動投資排程是星期幾（/auto/status 的 next_run.date；讀不到就說「這一期」）
  let AUTO_NEXT_RUN_DATE='';
  function _uiNextWhen(){
    const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(AUTO_NEXT_RUN_DATE||'');
    if(!m)return '這一期';
    return '週'+'日一二三四五六'[new Date(Date.UTC(+m[1],+m[2]-1,+m[3])).getUTCDay()];
  }
  function uiBannerParts(raw){
    const t=String(raw||'');
    for(const r of UI_BANNER_RULES)if(r.re.test(t))return {sit:typeof r.sit==='function'?r.sit():r.sit,next:r.next,go:r.go};
    const p=uiPlain(t).replace(/^[⚠️\s]+/,'');
    return {sit:[...p].length>18?[...p].slice(0,18).join('')+'…':p,next:'看細節',go:null};
  }
  function _uiEsc(t){return String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
  function uiRedBanner(el,msgs){
    if(!el)return;
    const list=(msgs||[]).filter(Boolean);
    if(!list.length){el.style.display='none';el.innerHTML='';return}
    const first=uiBannerParts(list[0]);
    const more=list.length>1?`（另有 ${list.length-1} 項）`:'';
    el.style.display='block';
    el.innerHTML=`<div class="ui-ban-sit" data-ui-keep>${_uiEsc(first.sit)}${more}</div>`+
      `<div class="ui-ban-next"><span class="press" style="text-decoration:underline;cursor:pointer" onclick="${first.go?`go('${first.go}')`:`this.closest('[id]').querySelector('details').open=true`}">${_uiEsc(first.next)} ›</span></div>`+
      `<details class="ui-ban-detail" data-ui-detail><summary style="cursor:pointer;font-weight:400;font-size:11px;opacity:.8">看細節</summary>`+
      `<div style="font-weight:400;font-size:11px;margin-top:4px">${list.map(m=>_uiEsc(uiPlain(m))).join('<br>')}</div>`+
      `<div style="display:none" data-ui-raw>${list.map(_uiEsc).join('<br>')}</div></details>`;
  }
  function renderAutoBanner(){
    uiRedBanner(document.getElementById('auto-banner'),[AUTO_BAN.offline,AUTO_BAN.hb,AUTO_BAN.px,AUTO_BAN.local]);
  }
  // 規則：台股交易日，台北 09:50 後當日沒有 run 心跳，或 13:50 後沒有 settle 心跳→紅色橫幅。
  // 讀不到心跳檔（網路錯誤、404）時不亂報，只 console.warn（無法判斷≠未執行）。
  function evalAutoHeartbeat(doc,now){
    const z=_zonedParts(now||new Date(),'Asia/Taipei');
    if(!isTradingDay(now||new Date(),'Asia/Taipei',TW_HOLIDAYS))return '';
    const today=_ymd(z),mins=z.h*60+z.mi;
    const ev=(doc&&Array.isArray(doc.events))?doc.events:[];
    const has=t=>ev.some(e=>e&&e.task===t&&typeof e.ts==='string'&&e.ts.slice(0,10)===today);
    // 先.三十九：排程安裝時間晚於當日應執行時間→那一項不報警（安裝當天的誤報）
    const inst=doc&&typeof doc.installed_at==='string'?doc.installed_at:'';
    const instMins=inst.slice(0,10)===today?(+inst.slice(11,13))*60+(+inst.slice(14,16)):(inst.slice(0,10)>today?1e9:-1);
    if(instMins>13*60+50)return '';
    if(mins>=13*60+50&&!has('settle'))return '自動交易排程未執行（電腦可能關機或離線）：今日盤後結算沒有心跳';
    if(mins>=9*60+50&&!has('run')&&!(instMins>9*60+50))return '自動交易排程未執行（電腦可能關機或離線）：今日盤前任務沒有心跳';
    return '';
  }
  // 先.八十一-13：選用資料檔（排程還沒產生過就不存在，例如 whitelist_price_status／us_analyst_reco 首次上線前）
  // 404 過一次就記在本次工作階段，一小時內不再請求，避免每次切頁都打出 404。
  function dataMissingSkip(f){try{const t=+sessionStorage.getItem('alpha_miss:'+f);return !!t&&Date.now()-t<3600000}catch(e){console.warn('[dataMissingSkip]',e);return false}}
  function dataMissingMark(f){try{sessionStorage.setItem('alpha_miss:'+f,String(Date.now()))}catch(e){console.warn('[dataMissingMark]',e)}}
  // 先.五十八-A2：白名單三檔（0050／00646／00697B）價格補不到時，雲端每日更新會寫 data/whitelist_price_status.json，這裡顯示紅條（不得靜默）
  async function loadWhitelistPriceStatus(){
    try{
      if(dataMissingSkip('whitelist_price_status')){AUTO_BAN.px='';return}
      const r=await fetch('data/whitelist_price_status.json?t='+Date.now(),{cache:'no-store'});
      if(r.status===404){dataMissingMark('whitelist_price_status');AUTO_BAN.px='';return}
      if(!r.ok){console.warn('[loadWhitelistPriceStatus] HTTP',r.status);AUTO_BAN.px='';return}
      const d=await r.json();
      AUTO_BAN.px=(d&&d.all_ok===false)?String(d.warning||'白名單 ETF 價格缺漏（詳見 data/whitelist_price_status.json）'):'';
    }catch(e){console.warn('[loadWhitelistPriceStatus]',e);recordGlobalError('loadWhitelistPriceStatus',e);AUTO_BAN.px=''}
    renderAutoBanner();
  }
  async function loadAutoHeartbeat(){
    try{
      const r=await fetch('data/auto_heartbeat.json?t='+Date.now(),{cache:'no-store'});
      if(!r.ok){console.warn('[loadAutoHeartbeat] HTTP',r.status);AUTO_BAN.hb='';return}
      AUTO_BAN.hb=evalAutoHeartbeat(await r.json());
    }catch(e){console.warn('[loadAutoHeartbeat]',e);recordGlobalError('loadAutoHeartbeat',e);AUTO_BAN.hb=''}
    renderAutoBanner();
  }
  const _autoEsc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  // 常備.開發-25（2026-10-11）：設定頁「為什麼沒下單」——preflight 各項紅綠燈＋白話原因（原本只列 PASS/FAIL 技術字）。
  // 白話對照只是說明文字，判定一律照引擎寫的 result，App 不自行改判。detail 照原文附在下方小字。
  const PF_PLAIN={
    env:['電腦上的永豐金鑰檔齊全','電腦上的永豐金鑰檔缺東西，程式登不進券商'],
    live_login:['能登入永豐正式環境（只查詢）','登不進永豐正式環境，無法查帳也無法下單'],
    signed:['證券帳戶已完成 API 簽署','證券帳戶還沒完成 API 簽署，券商不收程式委託'],
    ca:['電子憑證可用，且距到期超過 30 天','電子憑證不能用或快到期，沒有憑證送不出委託'],
    q_balance:['查得到交割戶餘額','查不到交割戶餘額，無法確認錢夠不夠'],
    q_settlements:['查得到未交割款','查不到未交割款，無法確認可用的錢'],
    q_positions:['查得到持股','查不到持股，下單前無法對帳'],
    cash_ready:['交割戶的錢夠買下一批','交割戶的錢不夠下一批（或還沒入金），這批不會送單'],
    push:['手機已開推播','沒有手機開推播，否決窗通知送不到，這批不會送單'],
    push_deps:['電腦的推播套件正常','電腦缺推播套件，通知送不出去'],
    conn_budget:['券商連線數還有餘裕','券商連線數已滿，新登入會被拒'],
    tasks:['電腦的自動排程都開著','有自動排程沒註冊或被停用，時間到不會自己跑'],
    calendar:['今年的開休市日曆已備好','缺今年的開休市日曆，程式不知道哪天開盤'],
    prices:['三檔的前收盤價夠新','前收盤價太舊，限價算不準，一律拒單'],
    exdiv:['除息資料夠新','除息資料太舊或不完整，可能在除息日下錯價'],
    config:['本機設定的資金／上限／期數合理','本機設定的資金／上限／期數有問題，會被擋單'],
    monthly_ok:['每月投入不大於總資金','每月投入大於總資金，第 5 個月起會被擋單（只提醒）'],
    drill_a:['模擬演練（下單到結算）做過且成功','模擬演練還沒完整跑過'],
    drill_b:['模擬演練（取消整批）做過且成功','取消演練還沒做完或結果不對'],
    drill_cfg:['演練用的暫時設定已清掉','還留著演練用的設定，要先清掉'],
    mode:['目前模式','目前模式']
  };
  // 純函式：把 preflight 轉成 {lights:[{dot,color,label,plain,detail,result}],blockers:[白話],stale:bool}
  function preflightLights(pf,nowMs){
    const dotOf={PASS:['●','#2da44e'],FAIL:['●','#e5534b'],WARN:['●','#d4a72c'],INFO:['○','var(--ink-3,#888)']};  // 固定色：不用 --up/--down（台股慣例漲紅跌綠會讓 PASS 變紅）
    const lights=pf.items.map(i=>{
      const p=PF_PLAIN[i.id],r=String(i.result||'');
      const [dot,color]=dotOf[r]||['●','var(--ink-3,#888)'];
      const plain=p?(r==='FAIL'||r==='WARN'?p[1]:p[0]):String(i.name||i.id||'');
      return {dot,color,result:r,label:String(i.name||''),plain,detail:String(i.detail||'')};
    });
    const t=Date.parse(pf.ran_at||'');
    return {lights,blockers:lights.filter(l=>l.result==='FAIL').map(l=>l.plain),stale:isFinite(t)&&(nowMs-t)>36*3600e3};
  }
  function renderAutoPreflight(pf){
    const el=document.getElementById('auto-preflight');if(!el)return;
    if(!pf||!Array.isArray(pf.items)){el.textContent='電腦還沒做上線前自檢，說不出原因。在電腦執行 python research/auto_rebalance_bb90.py --preflight（只查詢、不送單）後重新整理。';return}
    const v=preflightLights(pf,Date.now());
    const box=(bg,fg,html)=>'<div style="margin:4px 0 6px;padding:6px 8px;border-radius:8px;background:'+bg+';color:'+fg+'">'+html+'</div>';
    // 先.四十四-五：全部 PASS（含 CA）才顯示「可切換真錢模式」；否則寫明原因
    const head=pf.go_live_ready===true
      ?box('rgba(45,164,78,.15)','#2da44e','<b>可切換真錢模式</b>：上線前自檢全部通過。切換方式見 docs/AUTO_TRADING_SETUP.md 第九節（由你本人修改本機設定檔）。')
      :box('rgba(229,83,75,.12)','#e5534b','<b>沒下單的原因</b>'+(v.blockers.length?'（'+v.blockers.length+' 項紅燈）：'+v.blockers.map(_autoEsc).join('；')
        :(Array.isArray(pf.go_live_blockers)&&pf.go_live_blockers.length?'：'+pf.go_live_blockers.map(_autoEsc).join('；'):'：自檢結果未含完整判定，請重跑 --preflight')));
    const stale=v.stale?box('rgba(212,167,44,.15)','#d4a72c','這份自檢是 '+_autoEsc(String(pf.ran_at).slice(0,16).replace('T',' '))+' 做的，已超過 36 小時，紅綠燈可能不是現在的狀況；重跑 --preflight 可更新。'):'';
    el.innerHTML=head+stale+'<div style="margin-bottom:4px">自檢時間：'+_autoEsc(String(pf.ran_at||'').slice(0,16).replace('T',' '))+'　綠燈 '+_autoEsc(pf.pass)+'／紅燈 '+_autoEsc(pf.fail)+'（共 '+v.lights.length+' 項）</div>'+
      v.lights.map(l=>'<div style="margin:3px 0;display:flex;gap:6px;align-items:flex-start"><span style="color:'+l.color+';font-size:14px;line-height:1.2" aria-label="'+_autoEsc(l.result)+'">'+l.dot+'</span><span><b>'+_autoEsc(l.plain)+'</b>'+(l.result==='INFO'?'：'+_autoEsc(l.detail):'<br><span style="color:var(--ink-4);font-size:11px">'+_autoEsc(l.label)+'｜'+_autoEsc(l.detail)+'</span>')+'</span></div>').join('');
  }
  function renderLiveAccount(a){
    const el=document.getElementById('live-account-body');if(!el)return;
    if(!a){el.textContent='伺服器未回傳帳戶資料（可能是舊版，需重啟）';return}
    if(a.error){el.textContent='無法計算：'+a.error;return}
    if(a.empty){el.textContent='尚無真錢自動交易紀錄（第 1 批尚未執行）。';return}
    const n=v=>v==null?'—':Number(v).toLocaleString('zh-TW');
    const sg=v=>v==null?'—':(v>0?'+':'')+n(v);
    const rows=(a.holdings||[]).map(h=>'<tr><td>'+_autoEsc(h.symbol)+'</td><td style="text-align:right">'+n(h.shares)+'</td><td style="text-align:right">'+_autoEsc(h.pct)+'%</td><td style="text-align:right">'+_autoEsc(h.target_pct)+'%</td><td style="text-align:right">'+(h.dev_pp==null?'—':(h.dev_pp>0?'+':'')+_autoEsc(h.dev_pp)+'pp')+'</td></tr>').join('');
    el.innerHTML='<div>自 '+_autoEsc(a.since)+' 起（市值基準日 '+_autoEsc(a.as_of)+'）</div>'+
      '<table style="width:100%;font-size:12px;margin:6px 0"><tr><th style="text-align:left">標的</th><th style="text-align:right">股數</th><th style="text-align:right">占比</th><th style="text-align:right">目標</th><th style="text-align:right">偏離</th></tr>'+rows+'</table>'+
      '<div>累計投入：'+n(a.invested)+' 元　總市值：'+n(a.market_value)+' 元</div>'+
      '<div>自動交易損益：'+sg(a.pnl)+' 元　對照（同金額同日買 0050）：'+sg(a.bench_0050_pnl)+' 元</div>'+
      (a.has_preexisting?'<div style="color:var(--ink-4)">帳戶另有自動交易以外的持股，占比含這部分、損益不含。</div>':'')+
      (a.bench_missing_fills?'<div style="color:var(--ink-4)">有 '+_autoEsc(a.bench_missing_fills)+' 筆成交日找不到 0050 收盤，對照組未計入。</div>':'');
  }
  async function loadAutoTrading(){
    const note=document.getElementById('auto-status-note');
    if(!note)return;
    _safeAsync('loadAutoHeartbeat',loadAutoHeartbeat);
    _safeAsync('loadWhitelistPriceStatus',loadWhitelistPriceStatus);
    try{
      if(!LIVE.configured||!LIVE.url){note.textContent='連上電腦才看得到';AUTO_BAN.offline='';AUTO_BAN.local='';renderAutoBanner();return}
      const r=await liveFetch('/auto/status',5000);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      AUTO_BAN.offline='';
      AUTO_NEXT_RUN_DATE=String((d.next_run&&d.next_run.date)||'');
      const st=d.status||{};
      const bits=[(d.drill?'【演練（假券商）】':'')+'模式：'+(d.mode||'SIMULATION')];
      if(st.updated_at)bits.push('更新：'+st.updated_at);
      if(st.last_error)bits.push('最近錯誤：'+st.last_error);
      if(st.next_tranche!=null)bits.push('下一期：'+st.next_tranche);
      if(st.live_permission)bits.push(st.live_permission.effective?('正式環境權限：已生效（'+(st.live_permission.since||'')+' 起）'):('正式環境權限：尚未生效（最後檢查 '+(st.live_permission.checked_at||'?')+'）'));
      if(Array.isArray(st.drift_alert)&&st.drift_alert.length&&st.deviation)bits.push('偏離目標超過5個百分點（只提醒，不自動賣出）：'+st.drift_alert.map(c=>c+' '+(st.deviation[c]&&st.deviation[c].dev_pp>0?'+':'')+(st.deviation[c]?st.deviation[c].dev_pp:'?')+'pp').join('、'));
      note.textContent=bits.join('　');
      const tg=document.getElementById('auto-stop-toggle');if(tg)tg.checked=!!d.stopped;
      const pe=document.getElementById('auto-pending'),cb=document.getElementById('auto-cancel-all');
      const p=d.pending;let active=false;
      if(p&&Array.isArray(p.orders)&&p.orders.length&&!p.done&&!p.cancelled){
        active=true;
        window._autoExecAfter=p.execute_after||null;
        pe.textContent=(d.drill?'演練（假券商）':'')+'將於 '+String(p.execute_after||'?').slice(11,16)+' 自動送出，無需操作（剩 '+autoCountdownText()+'）：'+p.orders.map(o=>(o.symbol||'')+' '+(o.action==='Sell'?'賣':'買')+' '+(o.qty||'')+'股 @'+(o.limit_price||'')).join('；');
      }else{window._autoExecAfter=null;pe.textContent=p&&p.cancelled?'本批已取消（之後批次照常）':'目前沒有待執行訂單'}
      if(cb)cb.style.display=active?'':'none';
      try{renderAutoPreflight(st.preflight)}catch(e){console.warn('[renderAutoPreflight]',e);recordGlobalError('renderAutoPreflight',e)}
      try{renderLiveAccount(d.live_account)}catch(e){console.warn('[renderLiveAccount]',e);recordGlobalError('renderLiveAccount',e)}
      const red=st.banner==='red'||!!st.last_error;
      // 先.五十五-B6：交割戶餘額查詢為 0 的現金不足，改寫成可行動的說明
      // 先.五十四-6 更正 2：現金不足直接顯示引擎寫好的說明文字（可用餘額、本批所需、入金後次一交易日 09:05 自動重跑）
      const cashMsg=String(st.last_error||'').startsWith('INSUFFICIENT_CASH:')?String(st.last_error).slice('INSUFFICIENT_CASH:'.length):'';
      AUTO_BAN.local=red?(cashMsg||('自動交易異常：'+(st.last_error||'請檢查'))):(autoFreezeText(d)?('自動投資'+autoFreezeText(d)):(d.stopped?'自動交易已緊急停止（一律拒單）':''));
      renderAutoBanner();
    }catch(e){console.warn('[loadAutoTrading]',e);recordGlobalError('loadAutoTrading',e);note.textContent=_isOfflineErr(e)?liveOfflineText():'讀取自動交易狀態失敗（伺服器未更新）';AUTO_BAN.offline=_isOfflineErr(e)?liveOfflineText():'讀不到本機自動交易狀態（伺服器未更新）';renderAutoBanner()}
  }
  // 先.三十九：否決窗倒數（每秒更新文字裡的「剩 X 分 Y 秒」）
  function autoCountdownText(){
    const t=window._autoExecAfter?Date.parse(window._autoExecAfter):NaN;
    if(!isFinite(t))return '?';
    const s=Math.max(0,Math.round((t-Date.now())/1000));
    return s<=0?'0 秒（即將送出）':(Math.floor(s/60)+' 分 '+(s%60)+' 秒');
  }
  if(!window._autoCdTimer)window._autoCdTimer=setInterval(()=>{
    try{
      const pe=document.getElementById('auto-pending');
      if(pe&&window._autoExecAfter)pe.textContent=pe.textContent.replace(/剩 [^）]*）/,'剩 '+autoCountdownText()+'）');
    }catch(e){console.warn('[autoCountdown]',e);recordGlobalError('autoCountdown',e)}
  },1000);
  // 常備.開發-3（2026-10-11）：持倉損益卡。posR＝/live/positions 回應；msg＝無資料時要顯示的說明。
  // Shioaji 預設 Unit.Common：quantity 單位「張」、price＝成本均價、last_price＝現價、pnl＝券商算的未實現損益（已含預估費用）。
  // 現價缺時退回 resolveQuote（即時→quotes→全市場→sparklines 最後收盤＝price_history 最後收盤的輕量版）。
  function renderHomePositions(posR,msg){
    const el=document.getElementById('home-pos-body');if(!el)return;
    const esc=_autoEsc;
    const sp=posR&&posR.sinopac;
    if(!sp||!sp.available){el.textContent=msg||('永豐持倉暫時無法取得（'+((sp&&sp.reason)||'常駐行程未啟動或非交易時段')+'）');return}
    const ps=(sp.positions||[]).filter(p=>Number(p.quantity)>0);
    if(!ps.length){el.textContent='永豐目前沒有整股持倉（以「張」為單位查詢，零股部位不在此列）';return}
    let tCost=0,tVal=0,tPnl=0;
    const rows=ps.map(p=>{
      const code=String(p.code||''),lots=Number(p.quantity)||0,sh=lots*1000,cost=Number(p.price)||0;
      let lp=Number(p.last_price)||0,src='券商';
      if(!lp){const q=resolveQuote(code,false);if(q&&q.price!=null){lp=Number(q.price);src=q.tier==='history'?'收盤':'報價'}}
      const bp=p.pnl==null||p.pnl===''?NaN:Number(p.pnl);
      const val=lp?sh*lp:null,pnl=src==='券商'&&Number.isFinite(bp)?bp:(val!=null&&cost?val-sh*cost:null);
      tCost+=sh*cost;if(val!=null)tVal+=val;if(pnl!=null)tPnl+=pnl;
      const pct=pnl!=null&&cost?pnl/(sh*cost)*100:null;
      const cls=pnl==null?'':(pnl>=0?'pos':'neg');
      return '<div style="display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--hairline);font-size:12.5px">'+
        '<span><b>'+esc(nameOf(code))+'</b> <span class="note">'+esc(code)+' · '+lots+' 張 · 成本 '+(cost?cost.toFixed(2):'—')+'</span></span>'+
        '<span class="num" style="text-align:right;white-space:nowrap">市值 '+(val!=null?Math.round(val).toLocaleString('zh-TW'):'—')+(src!=='券商'?'<span class="note">（'+src+'）</span>':'')+
        '<br><b class="'+cls+'">'+(pnl==null?'—':(pnl>0?'+':'')+Math.round(pnl).toLocaleString('zh-TW'))+(pct!=null?'（'+(pct>0?'+':'')+pct.toFixed(2)+'%）':'')+'</b></span></div>';
    });
    el.innerHTML=rows.join('')+'<div style="margin-top:6px">合計成本 '+Math.round(tCost).toLocaleString('zh-TW')+'　市值 '+Math.round(tVal).toLocaleString('zh-TW')+'　未實現 <b class="'+(tPnl>=0?'pos':'neg')+'">'+(tPnl>0?'+':'')+Math.round(tPnl).toLocaleString('zh-TW')+'</b></div>'+
      '<div style="margin-top:4px;font-size:10px;color:var(--ink-4)">來源：本機 /live/positions（永豐唯讀查詢，'+esc(String(posR.generated_at||'').slice(11,16))+'）；單位張＝1000股，零股不在此列；未實現損益優先用券商回傳值（含預估費用），否則以市值−成本概算；非投資建議</div>';
  }
  async function loadHomeBrokerCard(){
    const cta=document.getElementById('home-broker-cta');
    const card=document.getElementById('home-asset-card');
    if(!cta||!card)return;
    const CTA_DEFAULT_HTML='連上電腦才看得到 →';
    if(!LIVE.configured||!LIVE.url){cta.innerHTML=CTA_DEFAULT_HTML;cta.style.display='';card.hidden=true;_safeSync('renderHomePositions',()=>renderHomePositions(null,'連上電腦才看得到'));uiHomeOffline(true);return}
    uiHomeOffline(false);cta.style.display='none';
    let posR=null,balR=null;
    try{
      const [rp,rb]=await Promise.all([liveFetch('/live/positions',9000),liveFetch('/live/balance',9000)]);
      if(rp&&rp.ok)posR=await rp.json();
      if(rb&&rb.ok)balR=await rb.json();
    }catch(e){console.warn('[loadHomeBrokerCard]',e);recordGlobalError('loadHomeBrokerCard',e);
      if(_isOfflineErr(e)){card.hidden=true;cta.style.display='none';uiHomeOffline(true,liveOfflineText());return}}
    // 常備.開發-20（先.六十七）：持倉不一定在自選股裡，現價退路要的小檔先備妥
    try{const pc=((posR&&posR.sinopac&&posR.sinopac.positions)||[]).map(p=>String(p.code||''));if(pc.length)await ensureQuoteLite(pc)}catch(e){console.warn('[loadHomeBrokerCard:ensureQuoteLite]',e);recordGlobalError('loadHomeBrokerCard:ensureQuoteLite',e)}
    _safeSync('renderHomePositions',()=>renderHomePositions(posR));
    const sinoBal=balR&&balR.sinopac&&balR.sinopac.available?balR.sinopac.balance:null;
    const sinoPos=posR&&posR.sinopac&&posR.sinopac.available?(posR.sinopac.positions||[]):null;
    const ibkrBal=balR&&balR.ibkr&&balR.ibkr.connected?balR.ibkr.balance:null;
    if(!sinoBal&&!ibkrBal){
      // 已設定即時伺服器，但這次兩邊都查無帳戶資料——跟「完全沒串接」是不同狀態，
      // 文案要誠實反映，不能沿用原本「串接券商帳戶→」（使用者其實已經填過設定）。
      cta.style.display='';card.hidden=true;
      cta.innerHTML='帳戶資料暫時拿不到 →';
      return;
    }
    let totalNtd=0;const lines=[];
    if(sinoBal){
      const cash=Number(sinoBal.acc_balance)||0;
      let posVal=0,posN=0;
      if(sinoPos&&sinoPos.length){
        for(const p of sinoPos){
          // 常備.開發-3 修正：Shioaji list_positions 預設 Unit.Common，quantity 單位是「張」，市值要 ×1000 股
          const qty=Number(p.quantity)||0,lp=Number(p.last_price)||0;
          if(qty&&lp){posVal+=qty*1000*lp;posN++}
        }
      }
      totalNtd+=cash+posVal;
      lines.push(`永豐（模擬）現金 <b class="num" data-ntd="${cash}"></b>`);
      if(posN)lines.push(`永豐（模擬）持股市值(估) <b class="num" data-ntd="${posVal}"></b>（${posN}檔）`);
    }else{
      lines.push('永豐（模擬）：暫無資料（'+((balR&&balR.sinopac&&balR.sinopac.reason)||'常駐行程未啟動')+'）');
    }
    if(ibkrBal){
      const netLiqRaw=ibkrBal.NetLiquidation;
      if(netLiqRaw&&netLiqRaw.value!=null){
        const usd=Number(netLiqRaw.value)||0;
        if(FX_RATE){
          const ntd=usd*FX_RATE;
          totalNtd+=ntd;
          lines.push(`IBKR（paper）淨值 US$${usd.toLocaleString(undefined,{maximumFractionDigits:2})} <b class="num" data-ntd="${ntd}"></b>`);
        }else{
          lines.push(`IBKR（paper）淨值 US$${usd.toLocaleString(undefined,{maximumFractionDigits:2})}（匯率未更新，未併入總額）`);
        }
      }else{
        lines.push('IBKR（paper）：已連線但查無淨值欄位');
      }
    }else{
      lines.push('IBKR（paper）：暫無資料（'+((balR&&balR.ibkr&&balR.ibkr.error)||'Gateway未連線')+'）');
    }
    document.getElementById('home-asset-total').dataset.ntd=String(totalNtd);
    document.getElementById('home-asset-detail').innerHTML=lines.join('<br>');
    cta.style.display='none';card.hidden=false;
    renderCcyAmounts();
  }
  // ── 2026-09-06（實測.一.3）把自選股清單推給常駐行程 ────────────────────────
  // Shioaji 的訂閱清單原本寫死在 shioaji_quotes.py（5 檔），Python 讀不到瀏覽器的
  // localStorage，所以使用者自己加的股票永遠拿不到 tick。改成每次自選股變動就把
  // 清單 POST 給 live server，它寫進共用檔案，常駐行程幾秒內完成增刪訂閱。
  // 沒設定即時伺服器、或伺服器沒開時，這裡靜靜跳過——那是完全正常的狀態
  // （回退鏈的第 2～4 層照樣有價格），不該跳錯誤給使用者看。
  let PUSH_WATCHLIST_TIMER=null;
  function pushWatchlistSoon(){
    // 連續加好幾檔時只推最後一次，不要每按一下就打一次伺服器
    if(PUSH_WATCHLIST_TIMER)clearTimeout(PUSH_WATCHLIST_TIMER);
    PUSH_WATCHLIST_TIMER=setTimeout(()=>{_safeAsync('pushWatchlist',pushWatchlist)},800);
  }
  async function pushWatchlist(){
    if(!LIVE.configured||!LIVE.url)return;
    const codes=WL.filter(c=>!isUS(c));
    try{
      const ac=new AbortController();const t=setTimeout(()=>ac.abort(),5000);
      const r=await fetch(LIVE.url+'/subscribe',{
        method:'POST',
        headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),
        body:JSON.stringify({codes}),
        cache:'no-store',credentials:'include',signal:ac.signal});
      clearTimeout(t);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      if(d.truncated&&d.truncated.length)toast('自選股超過即時訂閱上限，未訂閱：'+d.truncated.slice(0,3).join('、')+(d.truncated.length>3?' 等':''));
    }catch(e){
      // 伺服器沒開是常態，不記進診斷橫幅（會淹掉真正的程式錯誤）；
      // 只在主控台留一行，需要時查得到。
      console.warn('[pushWatchlist] 推送自選股清單失敗（不影響顯示，回退鏈仍有價格）：',e.message||e);
    }
  }
  // ── 2026-09-15（CF.6／稽核.四）多裝置設定同步 ───────────────────────────────
  // 總司令原話：「live server 新增 /settings 端點(token 驗證)，儲存自選股、
  // 幣別、風控參數；App 啟動時拉取、變更時推送，讓任何裝置設定一致」。
  // 衝突解法：比較 updated_at，新的贏——單使用者少裝置場景不需要欄位級合併。
  // 沒設定即時伺服器、或伺服器沒開時，這裡靜靜跳過（跟 pushWatchlist 同款
  // 「伺服器沒開是常態」處理），不影響 localStorage-only 的既有行為。
  let SETTINGS_PUSH_TIMER=null,SETTINGS_PULLED_ONCE=false;
  function _collectLocalSettings(){
    return {watchlist:WL,watchlists:wlListsRead(),currency:CCY,breakthrough_path:btRead()};  // 先.六十-A5：risk_control 已移除（引擎不讀）
  }
  function _applyServerSettings(s){
    if(!s||typeof s!=='object')return;
    if(Array.isArray(s.watchlist)){WL=s.watchlist;localStorage.setItem('alpha_wl',JSON.stringify(WL))}
    if(s.watchlists&&typeof s.watchlists==='object'&&s.watchlists.lists&&typeof s.watchlists.lists==='object'){
      const o=s.watchlists;if(!o.lists[o.active])o.active=Object.keys(o.lists)[0];
      if(o.active&&Array.isArray(s.watchlist))o.lists[o.active]=s.watchlist.slice();
      if(o.active){wlListsWrite(o);try{renderWLTabs()}catch(e){console.warn('[applyServerSettings:wl]',e);recordGlobalError('applyWL',e)}}
    }
    if(typeof s.currency==='string'){CCY=s.currency;localStorage.setItem('alpha_ccy',CCY)}
    if(s.breakthrough_path&&typeof s.breakthrough_path==='object'){localStorage.setItem('alpha_bt_path',JSON.stringify(s.breakthrough_path));try{renderBtPath()}catch(e){console.warn('[applyServerSettings:bt]',e);recordGlobalError('applyBt',e)}}
  }
  async function pullSettingsOnce(){
    if(SETTINGS_PULLED_ONCE)return;  // 每個App session只在啟動時拉一次
    if(!LIVE.configured||!LIVE.url)return;
    SETTINGS_PULLED_ONCE=true;
    try{
      const r=await liveFetch('/settings',5000);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      if(!d.exists)return;  // 伺服器還沒存過任何裝置的設定，本機值就是唯一版本，不覆蓋
      const localAt=localStorage.getItem('alpha_settings_synced_at');
      if(!localAt||new Date(d.updated_at)>new Date(localAt)){
        _applyServerSettings(d.settings);
        localStorage.setItem('alpha_settings_synced_at',d.updated_at);
        if(CURRENT_TAB==='home')_safeAsync('hydrateHome:afterSettingsSync',hydrateHome);
        toast('已從其他裝置同步設定');
      }
    }catch(e){
      console.warn('[pullSettingsOnce] 拉取跨裝置設定失敗（不影響顯示，沿用本機值）：',e.message||e);
    }
  }
  function pushSettingsSoon(){
    if(SETTINGS_PUSH_TIMER)clearTimeout(SETTINGS_PUSH_TIMER);
    SETTINGS_PUSH_TIMER=setTimeout(()=>{_safeAsync('pushSettings',pushSettings)},800);
  }
  async function pushSettings(){
    if(!LIVE.configured||!LIVE.url)return;
    try{
      const ac=new AbortController();const t=setTimeout(()=>ac.abort(),5000);
      const r=await fetch(LIVE.url+'/settings',{
        method:'POST',
        headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),
        body:JSON.stringify(_collectLocalSettings()),
        cache:'no-store',credentials:'include',signal:ac.signal});
      clearTimeout(t);
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      if(d.updated_at)localStorage.setItem('alpha_settings_synced_at',d.updated_at);
    }catch(e){
      console.warn('[pushSettings] 推送設定失敗（不影響顯示，本機值仍有效）：',e.message||e);
    }
  }
  function lastCloseLabel(){
    // 使用者指定字眼「離線，顯示最後收盤 MM-DD」：用台北日期、MM-DD兩位數格式
    const d=INTRADAY_SINOPAC&&INTRADAY_SINOPAC.fetched_at?new Date(INTRADAY_SINOPAC.fetched_at):null;
    if(!d||isNaN(d))return '—';
    const z=_zonedParts(d,'Asia/Taipei');return String(z.m).padStart(2,'0')+'-'+String(z.d).padStart(2,'0');
  }
  function renderLiveStatus(){
    let txt,color;
    if(!LIVE.configured){txt='離線（未設定即時伺服器），顯示最後收盤 '+lastCloseLabel();color='var(--ink-3)'}
    // 2026-10-08 先.五十一-2：Shioaji 行情連線中斷（event_code 1）到重連補完 1 分K 之前
    else if(LIVE.connected&&LIVE.feedGap){
      const gs=LIVE.feedGap.gap_start?String(LIVE.feedGap.gap_start).slice(11,16):'';
      txt='⚠ 行情中斷，補資料中'+(gs?'（自 '+gs+'）':'');color='var(--warn)';
    }
    else if(LIVE.connected){txt='● 即時連線中（本機伺服器・'+(LIVE.sourceMode==='tick-push-memory'?'逐筆推送':(LIVE.sourceMode==='hot-file'?'熱檔秒級':'冷檔'))+(LIVE.streamMode?'・'+LIVE.streamMode:'')+'）';color='var(--status-ok)'}
    // 2026-09-08（自動連線二.1）重連過程不得靜默：正在重試就明講第幾次。
    else if(LIVE.retryCount>0){
      txt='重新連線中（第 '+LIVE.retryCount+' 次）'
        +(DISCOVERY.picked?'・'+DISCOVERY.picked.label:'')
        +'，暫時顯示最後收盤 '+lastCloseLabel();
      color='var(--warn)';
    }
    else{txt=(!LIVE.lastError||_isOfflineErr({message:LIVE.lastError})?liveOfflineText():'離線（連不上即時伺服器：'+LIVE.lastError+'）')+'，顯示最後收盤 '+lastCloseLabel();color='var(--status-bad)'}
    const el=document.getElementById('home-live-status');if(el){el.textContent=txt;el.style.color=color}
    const note=document.getElementById('live-status-note');if(note){note.textContent=txt;note.style.color=color}
    try{updatePollNote()}catch(e){console.warn('[renderLiveStatus:updatePollNote]',e)}  // 2026-09-04四修.四：輪詢文案跟著連線狀態走
    try{renderHomeStatusSummary()}catch(e){console.warn('[renderLiveStatus:summary]',e)}
    if(LIVE.connected!==renderLiveStatus._lastConnected){renderLiveStatus._lastConnected=LIVE.connected;_safeAsync('updateDiagBanner',updateDiagBanner)}  // 連線狀態一變就重算橫幅，不讓「資料過舊」殘留
    const u=document.getElementById('set-live-url'),t=document.getElementById('set-live-token');
    if(u&&document.activeElement!==u)u.value=LIVE.url||'';
    if(t&&document.activeElement!==t)t.value=LIVE.token||'';
    // 2026-09-06（CF.3）Access 服務權杖兩欄同樣回填，規則一致：正在打字的欄位不覆蓋
    const ci=document.getElementById('set-cf-access-id'),cs=document.getElementById('set-cf-access-secret');
    if(ci&&document.activeElement!==ci)ci.value=LIVE.cfId||'';
    if(cs&&document.activeElement!==cs)cs.value=LIVE.cfSecret||'';
    _safeSync('renderLegacyLiveWarn',renderLegacyLiveWarn);  // 2026-09-08 連線四.1
    _safeSync('renderLiveUrlFull',renderLiveUrlFull);        // 2026-09-08 連線五.1
    _safeSync('renderDiscovery',renderDiscovery);            // 2026-09-08 自動連線一.2
    _safeSync('renderIbkrTokenWarn',renderIbkrTokenWarn);    // 2026-09-08 自動連線二.4
  }
  function applyLiveSnapshot(ev){
    if(ev.sinopac&&ev.sinopac.quotes){INTRADAY_SINOPAC=ev.sinopac;LIVE.sinopacAt=Date.now();LIVE.sourceMode=ev.sinopac.source_mode||null}
    if(ev.ibkr&&ev.ibkr.quotes){INTRADAY_IBKR=ev.ibkr;LIVE.ibkrAt=Date.now()}
    LIVE.kbarsLast=ev.kbars_last||{};LIVE.lastEventAt=Date.now();LIVE.streamMode=ev.mode||null;
    LIVE.feedGap=(ev.feed_gap&&ev.feed_gap.in_gap)?ev.feed_gap:null;  // 2026-10-08 先.五十一-2
  }
  async function rerenderAfterLive(){
    try{
      if(CURRENT_TAB==='home'){await hydrateHome();flashPriceEls('#wl-list');flashPriceEls('#home-idx-rows')}
      else if(CURRENT_TAB==='market'){
        if(MKT_STATE.market==='TW'){await loadMarketIndex();flashPriceEls('#idx-rows');await loadHeatmap();_safeAsync('loadScanners',loadScanners)}
        else if(MKT_STATE.market==='US'){await loadMarketUS();flashPriceEls('#us-idx-rows')}
        else if(MKT_STATE.market==='FUT'){await loadMarketFUT()}
      }else if(CURRENT_TAB==='stock'){liveUpdateStockPage()}
      renderLiveStatus();
    }catch(e){console.warn('[rerenderAfterLive]',e);recordGlobalError('rerenderAfterLive',e)}
  }
  let _liveRerenderTimer=null,_liveLastRerender=0;
  function scheduleLiveRerender(){
    if(_liveRerenderTimer)return;
    const wait=Math.max(0,3000-(Date.now()-_liveLastRerender)); // 首頁/市場頁重繪最多每3秒一次；個股頁1分K更新很輕，同一節奏即可
    _liveRerenderTimer=setTimeout(()=>{_liveRerenderTimer=null;_liveLastRerender=Date.now();rerenderAfterLive()},wait);
  }
  async function startLiveStream(){
    loadLiveConfig();renderLiveStatus();
    if(!LIVE.configured||LIVE.abort)return;
    const ac=new AbortController();LIVE.abort=ac;
    try{
      const r=await fetch(LIVE.url+'/live/stream',{headers:liveHeaders(),cache:'no-store',credentials:'include',signal:ac.signal});
      if(!r.ok){LIVE.lastError=r.status===401?'token不正確':'HTTP '+r.status;throw new Error(LIVE.lastError)}
      LIVE.connected=true;LIVE.lastError=null;LIVE.retryMs=3000;_liveMarkOk();renderLiveStatus();
      _safeAsync('pushWatchlist:onconnect',pushWatchlist);  // 2026-09-06：連上就對齊一次訂閱清單
      const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
      while(true){
        const {value,done}=await reader.read();if(done)break;
        buf+=dec.decode(value,{stream:true});
        let idx;
        while((idx=buf.indexOf('\n\n'))>=0){
          const chunk=buf.slice(0,idx);buf=buf.slice(idx+2);
          const dataLines=chunk.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim());
          if(!dataLines.length)continue; // retry:/": keepalive"註解行，沒有資料
          try{applyLiveSnapshot(JSON.parse(dataLines.join('\n')));scheduleLiveRerender()}catch(e){console.warn('[live:parse]',e)}
        }
      }
      LIVE.lastError='串流結束';
    }catch(e){
      if(!ac.signal.aborted)LIVE.lastError=LIVE.lastError||(e.name==='TypeError'?'無回應或被拒絕':(e.message||String(e)));
    }finally{
      LIVE.connected=false;
      if(LIVE.abort===ac)LIVE.abort=null;
      renderLiveStatus();
      if(!ac.signal.aborted){
        // 2026-09-08（自動連線二.1）重連過程不得靜默——把第幾次寫進狀態列。
        // 使用者看到「重新連線中（第 3 次）」跟看到一片空白，
        // 對「系統有沒有在做事」的判斷完全不同。
        LIVE.retryCount=(LIVE.retryCount||0)+1;
        const wait=LIVE.retryMs;LIVE.retryMs=Math.min(30000,LIVE.retryMs*2); // 指數退避，最多30秒
        renderLiveStatus();
        // 連續失敗達門檻就重跑端點發現（自動連線一.3）
        _safeAsync('liveSelfHeal',()=>liveSelfHeal('SSE 斷線第 '+LIVE.retryCount+' 次'));
        setTimeout(()=>{startLiveStream().catch(e=>{console.warn('[live:reconnect]',e)})},wait);
      }else{LIVE.retryCount=0}
    }
  }
  function restartLiveStream(){
    const old=LIVE.abort;LIVE.abort=null;if(old){try{old.abort()}catch(e){}}
    LIVE.retryMs=3000;
    setTimeout(()=>{startLiveStream().catch(e=>{console.warn('[live:start]',e);recordGlobalError('startLiveStream',e)})},200);
  }
  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='visible'&&LIVE.configured&&!LIVE.connected&&!LIVE.abort)restartLiveStream();
  });
  // 2026-09-08（自動連線二.2）網路恢復時立刻重試一次，不等退避計時。
  // 退避到 30 秒時，使用者可能已經接回網路卻還要乾等半分鐘——
  // 那半分鐘裡畫面看起來就是「還是壞的」，是最容易被誤判成沒修好的時候。
  window.addEventListener('online',()=>{
    if(!LIVE.configured)return;
    LIVE.retryMs=1000;   // 重置退避，網路剛回來值得立刻試
    if(!LIVE.connected){
      toast('偵測到網路恢復，立即重新連線');
      restartLiveStream();
    }
  });
  function _zonedParts(d,tz){
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:tz,hourCycle:'h23',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',weekday:'short'}).formatToParts(d);
    const o={};parts.forEach(x=>o[x.type]=x.value);
    const wd={Sun:0,Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6}[o.weekday];
    return {y:+o.year,m:+o.month,d:+o.day,h:(+o.hour)%24,mi:+o.minute,wd};
  }
  // ── 2026-09-08（建置一.1）事件資料 ─────────────────────────────────────────
  // data/events.json 由 .github/scripts/fetch_news_events.py 產生，只存索引不存全文：
  // 標題、連結、時間、標的、類型。全文有著作權疑慮，而且我們要的是「這檔最近發生
  // 什麼事」——點進去看原文才是正確的閱讀路徑。
  let EVENTS_CACHE=null,EVENTS_AT=0;
  // 常備.開發-20（2026-10-11）：首頁持股事件卡只需要自選股＋持倉十幾檔，改抓
  // data/events_by_code/{代號}.json（scripts/split_events_by_code.py 由整份 events.json 切出，
  // 內容相同），不再為此下載整份 events.json（gzip 約 347KB）。404＝該代號目前沒有事件。
  // 整份檔已經在記憶體（例如先開過搜尋）就直接用整份，不重複下載。
  // 先.八十一-11：data/events_by_code/_index.json＝目前有事件的代號清單（split_events_by_code.py 同班產生），
  // 只對清單內代號發請求，沒事件的代號不再打出 404。索引讀不到回 null，呼叫端照舊逐檔請求（404 視為沒事件）。
  let EVENTS_INDEX_P=null,EVENTS_INDEX_AT=0;
  function eventsIndex(){
    if(!EVENTS_INDEX_P||Date.now()-EVENTS_INDEX_AT>10*60*1000){
      EVENTS_INDEX_AT=Date.now();
      EVENTS_INDEX_P=fetch('data/events_by_code/_index.json?t='+Math.floor(Date.now()/60000))
        .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
        .then(d=>new Set((d&&d.codes)||[]))
        .catch(e=>{EVENTS_INDEX_P=null;console.warn('[eventsIndex]',e);recordGlobalError('eventsIndex',e);return null});
    }
    return EVENTS_INDEX_P;
  }
  async function loadEventsForCodes(codes){
    if(EVENTS_CACHE&&Date.now()-EVENTS_AT<10*60*1000)return EVENTS_CACHE;
    const t=Math.floor(Date.now()/60000);
    const idx=await eventsIndex();
    const res=await Promise.allSettled(codes.filter(c=>/^[0-9A-Za-z]{2,10}$/.test(String(c))&&(!idx||idx.has(String(c)))).map(c=>
      fetch('data/events_by_code/'+c+'.json?t='+t).then(r=>r.ok?r.json():{events:[]})));
    const events=[];
    res.forEach(x=>{
      if(x.status==='fulfilled'){if(x.value&&Array.isArray(x.value.events))events.push(...x.value.events)}
      else{console.warn('[loadEventsForCodes]',x.reason);recordGlobalError('loadEventsForCodes',x.reason)}
    });
    return {events};
  }
  // 先.八十一-30：整份事件改讀精簡版 data/events_search.json（split_events_by_code.py 同班產生，gzip 約 156KB，
  // 整份 events.json 約 382KB），還原成與 events.json 完全相同的物件（同欄位、同順序、同頂層欄位）；
  // 精簡版讀不到或格式不對才讀整份檔。
  function _expandEventsSearch(d){
    if(!d||!Array.isArray(d.rows)||!Array.isArray(d.u)||!Array.isArray(d.t)||!Array.isArray(d.s))throw new Error('events_search.json 格式不符');
    const names=d.names||{};
    // 列格式見 split_events_by_code.py _srow：第 7 欄名稱（0＝用預設），第 8 欄是其他欄位（例如 yoy_pct），照原順序接在 url 後面
    const events=d.rows.map(r=>{const [code,date,ti,title,ui,si]=r;const o={code};if(d.has_name!==false)o.name=(r.length>6&&r[6]!==0)?r[6]:names[code];o.date=date;o.type=d.t[ti];o.title=title;o.source=d.s[si];o.url=d.u[ui];if(r.length>7&&r[7])Object.assign(o,r[7]);return o});
    return Object.assign({},d.top||{},{events});
  }
  // 先.八十一-56：精簡版與整份事件檔要同一班產生。只讀整份檔開頭幾 KB 取它的 fetched_at（頂層第一個欄位）來比；
  // 讀不到（離線、伺服器不支援）回 null＝不比（不擋精簡版）。
  async function _eventsFullFetchedAt(){
    try{
      const ac=new AbortController();
      const r=await fetch('data/events.json?t='+Math.floor(Date.now()/60000),{headers:{Range:'bytes=0-4095'},signal:ac.signal});
      if(!r.ok&&r.status!==206)return null;
      let txt='';
      if(r.body&&r.body.getReader){const rd=r.body.getReader(),dec=new TextDecoder();let n=0;
        try{while(n<8192){const {done,value}=await rd.read();if(done)break;n+=value.length;txt+=dec.decode(value,{stream:true});if(/"fetched_at"\s*:\s*"[^"]+"/.test(txt))break}}
        finally{try{ac.abort()}catch(e){console.warn('[_eventsFullFetchedAt] abort',e)}}}
      else txt=(await r.text()).slice(0,8192);
      const m=txt.match(/"fetched_at"\s*:\s*"([^"]+)"/);return m?m[1]:null;
    }catch(e){console.warn('[_eventsFullFetchedAt]',e);return null}
  }
  async function ensureEvents(){
    if(EVENTS_CACHE&&Date.now()-EVENTS_AT<10*60*1000)return EVENTS_CACHE;
    try{
      let d=null;
      try{
        const rs=await fetch('data/events_search.json?t='+Math.floor(Date.now()/60000));
        if(!rs.ok)throw new Error('HTTP '+rs.status);
        d=_expandEventsSearch(await rs.json());
        const full=await _eventsFullFetchedAt();
        if(full&&d.fetched_at&&full!==d.fetched_at)throw new Error('精簡版（'+d.fetched_at+'）與整份事件檔（'+full+'）不同班');
        d._source='search';
      }catch(e1){
        console.warn('[ensureEvents:search→full]',e1);
        const r=await fetch('data/events.json?t='+Math.floor(Date.now()/60000));
        if(!r.ok)throw new Error('HTTP '+r.status);
        d=await r.json();
        d._source='full';d._fallback_reason=String(e1&&e1.message||e1);  // 標示：這次是退回整份檔
      }
      EVENTS_CACHE=d;EVENTS_AT=Date.now();
    }catch(e){
      console.warn('[ensureEvents]',e);recordGlobalError('ensureEvents',e);
      if(!EVENTS_CACHE)EVENTS_CACHE={events:[]};
    }
    return EVENTS_CACHE;
  }
  const EVENT_TYPE_COLOR={
    '月營收':'var(--gold)','除權息':'#7aa2f7','法說會':'var(--up)','併購':'#e0af68',
    '增減資':'#bb9af7','重大訂單':'var(--up)','人事':'var(--ink-3)','財務':'#7dcfff',
    '訴訟':'var(--down)','處分資產':'#9ece6a','停復牌':'var(--down)','其他':'var(--ink-3)',
    '財報日':'var(--gold)','8-K':'#7dcfff','8-K/A':'#7dcfff',  // 常備.開發-5 美股
  };
  // 常備.開發-22（2026-10-11）：法說會事件附 MOPS「法人說明會簡報內容」官方公開查詢頁連結
  // （公開資訊觀測站舊版站 mopsov.twse.com.tw 的單一公司查詢，GET 直接開即可看到該公司
  // 近期法說會日期、擇要訊息與中英文簡報 PDF 連結；上市與上櫃皆適用）。
  // 只放連結：App 不抓、不下載、不轉存簡報內容。新版 mops.twse.com.tw 為單頁應用，
  // 無法用網址直接帶公司代號，故用舊版站的查詢網址。
  function mopsIrUrl(code){
    code=String(code||'').trim();
    if(!/^[0-9A-Z]{4,6}$/.test(code))return '';
    return 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1?encodeURIComponent=1&step=1&firstin=1&off=1&queryName=co_id&inpuType=co_id&TYPEK=all&co_id='+encodeURIComponent(code);
  }
  function mopsIrLinkHtml(e,stop){
    if(!e||e.type!=='法說會')return '';
    const u=mopsIrUrl(e.code);if(!u)return '';
    return ` <a class="mops-ir-link" href="${u}" target="_blank" rel="noopener"${stop?' onclick="event.stopPropagation()"':''} style="font-size:10.5px;color:var(--gold);white-space:nowrap">MOPS簡報↗</a>`;
  }
  // 2026-10-05（先.十四-一）：本機 claude -p launcher 登入過期／額度用盡／連續3小時
  // 無實際執行的紅色橫幅。
  // **2026-10-05（先.十四-一續）為什麼要抽成獨立函式並在啟動時呼叫**：第一版寫在
  // loadDataFreshness() 裡面，而那支只有 hydrateSettings()（＝使用者點進「設定」頁）
  // 才會跑——等於這個「本機 Claude 掛了」的告警，必須使用者自己想到去翻設定頁才看得到，
  // 跟裁示要求的「App 首頁讀到即顯示紅色橫幅」不符，也剛好重演 10/3 事故的同一種形狀
  // （告警機制存在、但沒有人會在那個位置看它）。現在首頁一載入就評估一次。
  // 獨立try/catch，失敗只影響這個橫幅，不影響其他面板（CLAUDE.md「App穩定性與錯誤隔離原則」）。
  function renderClaudeAuthBanner(statusDoc){
    try{
      const banner=document.getElementById('claude-auth-banner');
      if(!banner)return;
      const ca=statusDoc&&statusDoc.local_schedule_heartbeat&&statusDoc.local_schedule_heartbeat.claude_auth;
      const st=ca&&ca.overall_status;
      // 先.七十二-A3：兩段式；原始字樣（含「需要重新登入」「額度已用盡」「沒有實際執行」）保留在收合細節
      if(st==='AUTH_EXPIRED')uiRedBanner(banner,['⚠️ 本機 Claude 需要重新登入（偵測到登入過期）：'+(ca.detail||'')]);
      else if(st==='QUOTA_EXCEEDED')uiRedBanner(banner,['⚠️ 本機 Claude 額度已用盡：'+(ca.detail||'')]);
      else if(st==='STALLED_3H')uiRedBanner(banner,['⚠️ 本機自走系統超過門檻時間（開發線 3 小時／研究線每週一輪，7 天）沒有實際執行：'+(ca.detail||'')]);
      else uiRedBanner(banner,[]);
    }catch(e){
      console.warn('[renderClaudeAuthBanner]',e);recordGlobalError('renderClaudeAuthBanner',e);
    }
  }
  // 啟動時自己抓一次 STATUS.json（設定頁沒被點開也要看得到橫幅）。抓檔失敗
  // 一律當成「沒有告警」處理，不得讓它變成另一個單點故障（CLAUDE.md 十二節 fail open）。
  async function loadClaudeAuthBanner(){
    renderClaudeAuthBanner(await ensureStatusDoc());
  }
  // 常備.開發-20（2026-10-11）：啟動時 Claude 授權橫幅與診斷橫幅都要 STATUS.json，共用一次下載
  // （60 秒內重用）。失敗回 null，呼叫端照舊當成「沒有資料」處理（十二節 fail open）。
  let STATUS_DOC_P=null,STATUS_DOC_AT=0;
  function ensureStatusDoc(){
    if(STATUS_DOC_P&&Date.now()-STATUS_DOC_AT<60*1000)return STATUS_DOC_P;
    STATUS_DOC_AT=Date.now();
    STATUS_DOC_P=fetch('data/STATUS.json?t='+Date.now()).then(r=>r.ok?r.json():null)
      .catch(e=>{console.warn('[ensureStatusDoc]',e);return null});
    return STATUS_DOC_P;
  }
  // 2026-08-25 新增，2026-08-28擴充：設定頁+首頁底部顯示 App 版本／Service
  // Worker 版本／SW 狀態，方便確認手機是不是真的更新到最新版（用手機開 App
  // 時肉眼比對這裡的版本號即可）。**這個常數由 .git/hooks/pre-commit 在每次
  // commit時自動改寫成當下時間戳**（見該hook腳本說明），不用手動記得改——
  // 這是使用者2026-08-28明確要求「每次commit自動更新」的做法：沒有建置流程
  // 可以注入版本號，改用git hook在commit前用sed改這一行。
  const APP_VERSION='2026-10-15.0057';
  async function loadAboutVersions(){
    setTxt('about-app-ver',APP_VERSION);
    setTxt('home-footer-version','Alpha v'+APP_VERSION);
    if(!('serviceWorker' in navigator)){setTxt('about-sw-ver','瀏覽器不支援');setTxt('about-sw-status','—');return}
    try{
      const swText=await fetch('sw.js?_='+Date.now(),{cache:'no-store'}).then(r=>r.text());
      const m=swText.match(/CACHE\s*=\s*'([^']+)'/);
      setTxt('about-sw-ver',m?m[1]:'讀不到');
    }catch(e){console.warn('[loadAboutVersions]',e);recordGlobalError('loadAboutVersions',e);setTxt('about-sw-ver','讀取失敗')}
    const reg=await navigator.serviceWorker.getRegistration().catch(()=>null);
    if(!reg){setTxt('about-sw-status','尚未註冊');return}
    setTxt('about-sw-status',reg.active?'已啟用':(reg.installing?'安裝中':(reg.waiting?'等待啟用':'未知')));
  }
  async function forceUpdateApp(){
    try{
      if('serviceWorker' in navigator){
        const regs=await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map(r=>r.unregister()));
      }
      if('caches' in window){
        const keys=await caches.keys();
        await Promise.all(keys.map(k=>caches.delete(k)));
      }
      toast('已清除快取，重新整理中…');
      setTimeout(()=>location.reload(true),400);
    }catch(e){
      console.warn('[forceUpdate]',e);recordGlobalError('forceUpdate',e);
      toast('強制更新失敗：'+e.message);
    }
  }

  // 2026-10-08（先.五十二-5）：偵測新版。抓 sw.js 讀出快取版本（pre-commit 與 APP_VERSION 同步改寫），
  // 比目前頁面的 APP_VERSION 新就在頂端顯示「有新版，點此更新」；點擊沿用 forceUpdateApp（清快取＋重載）。
  // 網路失敗（離線）是正常情況，只 console.warn 不記錄錯誤 log（刻意排除，避免離線時錯誤 log 一直長）。
  async function checkNewVersion(){
    let txt;
    try{txt=await fetch('sw.js?_='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.text():'')}
    catch(e){console.warn('[checkNewVersion] 網路失敗（不記錄）',e);return}
    try{
      const m=(txt||'').match(/CACHE\s*=\s*'alpha-v([^']+)'/);
      const swVer=m?m[1]:null;
      const el=document.getElementById('new-version-banner');
      if(el)el.style.display=(swVer&&swVer>APP_VERSION)?'block':'none';
      window._latestSwVersion=swVer;
    }catch(e){console.warn('[checkNewVersion]',e);recordGlobalError('checkNewVersion',e)}
  }
  // 先.六十九-1：外殼改快取優先後，新版由背景安裝的 SW「等待中」帶著。點提示條＝叫等待中的 SW 接手並重載
  // （整批換版）；沒有等待中的 SW（例如新版還沒裝完）才退回原本的清快取＋重載。
  let SW_APPLY_CLICKED=false;
  async function applyNewVersion(){
    try{
      const el=document.getElementById('new-version-banner');if(el)el.textContent='更新中…';
      const reg='serviceWorker' in navigator?await navigator.serviceWorker.getRegistration().catch(()=>null):null;
      if(reg&&reg.waiting){
        SW_APPLY_CLICKED=true;reg.waiting.postMessage({type:'SKIP_WAITING'});
        setTimeout(()=>{if(SW_APPLY_CLICKED)forceUpdateApp()},5000);  // 5 秒沒換上就退回清快取
        return;
      }
      await forceUpdateApp();
    }catch(e){console.warn('[applyNewVersion]',e);recordGlobalError('applyNewVersion',e)}
  }
  function watchSwUpdate(reg){
    const show=()=>{const el=document.getElementById('new-version-banner');if(el&&navigator.serviceWorker.controller)el.style.display='block'};
    if(reg.waiting)show();
    reg.addEventListener('updatefound',()=>{
      const w=reg.installing;if(!w)return;
      w.addEventListener('statechange',()=>{if(w.state==='installed')show()});
    });
  }

  // ── 漲跌顏色偏好（2026-08-24 新增）：預設台股慣例紅漲綠跌，可切成國際慣例綠漲紅跌。
  // 透過覆寫 --up/--down 系列 CSS 變數即時套用到整站（因為既有元件都是吃這組變數，
  // 不用一一改元件），存 localStorage，下次開 App 記得上次選擇。
  const COLOR_SCHEMES={
    TW:{up:'#ff5257',upDeep:'#e6383f',down:'#24c98a',downDeep:'#1aa876',label:'台股慣例（紅漲綠跌）'},
    INTL:{up:'#24c98a',upDeep:'#1aa876',down:'#ff5257',downDeep:'#e6383f',label:'國際慣例（綠漲紅跌）'},
  };
  // 先.九十六-R2（2026-10-14）修 bug：原本把上面的深色值直接寫進 <html> inline style，
  // inline 優先於 :root[data-theme="light"]，淺色模式的 --up／--down 永遠被蓋成深色亮色（綠字對比 1.7:1）。
  // 改成只設 data-updown 屬性，實際顏色由 app.css 依深淺色各給一組；COLOR_SCHEMES 的色碼只剩說明用途。
  function applyColorScheme(key){
    const k=COLOR_SCHEMES[key]?key:'TW';
    const html=document.documentElement;
    ['--up','--up-deep','--down','--down-deep'].forEach(p=>html.style.removeProperty(p));
    if(k==='INTL')html.setAttribute('data-updown','intl');else html.removeAttribute('data-updown');
    localStorage.setItem('alpha_color_scheme',k);
  }

  // ── 幣別切換（2026-08-25 新增）：今日頁總資產/已實現損益、交易頁持倉損益支援 NT$/US$。
  // 2026-08-27 架構修正：匯率改讀 data/fx.json（GitHub Actions 排程用 yfinance
  // TWD=X 抓，見 .github/scripts/fetch_fx.py），不再對 FinMind 打
  // TaiwanExchangeRate——那是 STATUS.json 列出的 P0 項目（額度耗盡就讓幣值切換
  // 失效）。抓不到就不換算、不准用寫死的舊匯率頂替（見 CLAUDE.md 已知地雷），
  // 畫面誠實顯示「匯率未更新」。
  let CCY=localStorage.getItem('alpha_ccy')||'TWD';
  let FX_RATE=null,FX_DATE=null;
  const CCY_TOGGLE_IDS=['home-ccy-toggle','trade-ccy-toggle','settings-ccy-toggle'];
  const FX_NOTE_IDS=['home-fx-note','trade-fx-note','settings-fx-note'];
  let FX_CACHE=null;
  async function fetchFx(){
    try{const r=await fetch('data/fx.json?t='+Date.now());if(r.ok)FX_CACHE=await r.json()}catch(e){console.warn('[fetchFx]',e);recordGlobalError('fetchFx',e);FX_CACHE=null}
    const usd=FX_CACHE&&FX_CACHE.usd_twd;
    if(!usd||usd.rate==null){FX_RATE=null;FX_DATE=null;renderFxNote();return}
    FX_RATE=usd.rate;FX_DATE=usd.date;
    renderFxNote();
  }
  function renderFxNote(){
    const txt=FX_RATE?`匯率 ${FX_RATE.toFixed(2)}（${FX_DATE.replaceAll('-','/')}）`:'匯率未更新';
    FX_NOTE_IDS.forEach(id=>setTxt(id,txt));
  }
  function fmtCcyAmount(ntd,signed){
    const useUsd=CCY==='USD'&&FX_RATE;
    const amt=useUsd?ntd/FX_RATE:ntd;
    const sym=useUsd?'US$':'NT$';
    const absTxt=Math.abs(amt).toLocaleString(undefined,{maximumFractionDigits:CCY==='USD'?2:0});
    return signed?(amt>=0?'+ ':'− ')+sym+' '+absTxt:sym+' '+absTxt;
  }
  function renderCcyAmounts(){
    document.querySelectorAll('[data-ntd]').forEach(el=>{
      const ntd=Number(el.dataset.ntd);
      el.textContent=fmtCcyAmount(ntd,el.dataset.ccySigned==='1');
    });
  }
  function renderCcyToggles(){
    CCY_TOGGLE_IDS.forEach(id=>{
      const el=document.getElementById(id);if(!el)return;
      el.innerHTML=['TWD','USD'].map(k=>{
        const disabled=k==='USD'&&!FX_RATE;
        return `<span class="press mtg-opt${CCY===k?' on':''}" style="${disabled?'opacity:.4':''}" onclick="setCcy('${k}')">${k==='TWD'?'NT$':'US$'}</span>`;
      }).join('');
    });
  }
  function setCcy(key){
    if(key==='USD'&&!FX_RATE){toast('匯率未更新，暫時無法切換至美元');return}
    CCY=key;localStorage.setItem('alpha_ccy',key);pushSettingsSoon();
    renderCcyToggles();renderCcyAmounts();
  }

  // ── 啟動：載入真實自選股報價 + 註冊 PWA ──
  // 2026-08-27新增：每一步都獨立包起來，任何一步失敗（例如applyColorScheme
  // 存取到不存在的DOM元素）都不能讓後面的hydrateHome()等初始化整批中斷不執行
  // ——這正是使用者定位的「改A壞B」根因：一段同步程式碼中途拋錯，同一個
  // <script>區塊後面的敘述就不會再執行了。
  _safeSync('applyColorScheme',()=>applyColorScheme(localStorage.getItem('alpha_color_scheme')||'TW'));
  _safeSync('renderCcyToggles',renderCcyToggles);
  _safeSync('renderCcyAmounts',renderCcyAmounts);
  _safeSync('renderFxNote',renderFxNote);
  _safeAsync('fetchFx',()=>fetchFx().then(()=>{renderCcyToggles();renderCcyAmounts()}));
  _safeSync('setupRevChartTouch',setupRevChartTouch);
  _safeSync('setupPullToRefresh',setupPullToRefresh);
  _safeAsync('hydrateHome',hydrateHome);
  // 2026-08-28新增：版本號要在頁面一載入就顯示在首頁底部（不是只有進了設定頁
  // 才觸發loadAboutVersions()那次），使用者才能不用點進設定就一眼確認手機是
  // 不是新版。
  _safeAsync('loadAboutVersions',loadAboutVersions);
  // 2026-10-08（先.五十二-5）：新版提示——載入時、每 30 分鐘、切回畫面時各檢查一次
  // 先.八十一-7（第二招）：第一次開（還沒有 SW 接管）頁面本身就是最新版，不必再抓一次 sw.js 比版本——那次跟 register() 重複
  _safeAsync('checkNewVersion',()=>('serviceWorker' in navigator&&navigator.serviceWorker.controller)?checkNewVersion():Promise.resolve());
  try{
    setInterval(()=>{checkNewVersion().catch(e=>{console.warn('[checkNewVersion:interval]',e);recordGlobalError('checkNewVersion:interval',e)})},30*60*1000);
    setInterval(()=>{if('serviceWorker' in navigator)navigator.serviceWorker.getRegistration().then(r=>r&&r.update()).catch(e=>console.warn('[serviceWorker.update:interval] 離線時正常，不記錄',e))},30*60*1000);
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')checkNewVersion().catch(e=>{console.warn('[checkNewVersion:visible]',e);recordGlobalError('checkNewVersion:visible',e)})});
  }catch(e){console.warn('[checkNewVersion:setup]',e);recordGlobalError('checkNewVersion:setup',e)}
  // 2026-10-05（先.十四-一）：本機 Claude 登入過期／額度／停擺的紅色橫幅要在首頁
  // 一載入就評估，不是等使用者點進設定頁（見 renderClaudeAuthBanner 的註解）。
  _safeAsync('loadClaudeAuthBanner',loadClaudeAuthBanner);
  _safeAsync('loadPaperTrackingBanner',loadPaperTrackingBanner);
  // 2026-09-03深夜（乙.4）：讀即時伺服器設定並嘗試連線；沒設定/連不上就維持冷資料路徑並標「離線」。
  _safeSync('loadLiveConfig',loadLiveConfig);
  _safeSync('renderLiveStatus',renderLiveStatus);
  // 2026-09-08（自動連線一.2）啟動時自動發現端點，使用者永不手填。
  // 順序很重要：先發現、再連線——先連線的話第一次一定用到舊的或空的網址，
  // 使用者會看到一次沒必要的「連不上」再自己好起來，那種閃爍比慢一點更糟。
  // 發現本身有 2 秒逾時且並行，最壞情況只多等 2 秒。
  _safeAsync('discoverLiveEndpoint',()=>discoverLiveEndpoint()
    .then(()=>{loadLiveConfig();renderLiveStatus();return startLiveStream()})
    .then(()=>pullSettingsOnce()));  // 2026-09-15（CF.6／稽核.四）連上即時伺服器後拉一次跨裝置設定
  if('serviceWorker' in navigator){
    navigator.serviceWorker.register('sw.js').then(reg=>{
      // 先.九十六-R1 走查順手修：SW 被瀏覽器／測試環境封鎖時 register() 會回 undefined，不是程式錯誤，跳過即可
      if(!reg){console.warn('[serviceWorker] register 回傳空值（SW 被封鎖或不支援），略過更新監看');return}
      watchSwUpdate(reg);
      // 先.八十一-7（第二招：合併重複抓取）：register() 本身就會檢查 sw.js 有沒有新版，啟動時不再多叫一次 reg.update()（量測顯示 sw.js 被抓兩次）
    }).catch(e=>{console.warn('[serviceWorker]',e);recordGlobalError('serviceWorker',e)});
    // 只有使用者點了「有新版」才因換版重載；第一次安裝時的 clients.claim() 也會觸發 controllerchange，不能重載
    navigator.serviceWorker.addEventListener('controllerchange',()=>{if(SW_APPLY_CLICKED){SW_APPLY_CLICKED=false;location.reload()}});
  }
// 先.七十二-A2（2026-10-11）：說明文字（.note）超過 40 字自動收成「ⓘ 說明」點開。
// 進階頁（[data-ui-advanced]）、已收過的、頁尾免責、或標了 data-ui-keep 的狀態行不收。內容原封不動搬進 <details>，
// 讀 textContent 的既有程式不受影響；之後被重繪（innerHTML／textContent 改寫）時由 MutationObserver 再收一次。
// 先.八十-5（2026-10-12）更正：
//  ① 只收「說明」類：頁面原始標記裡、沒有 id 的 .note（有 id 的多半是程式填的狀態／卡片主內容）；⚠ 附註也算，按鈕寫「⚠ 注意」；
//    啟動時標 data-ui-explain，之後只處理有這個標記的元素。程式動態產生的說明要收，就在 HTML 字串裡自己加 data-ui-explain。
//  ② 時鐘每秒改字不得觸發重掃：觀察器只看「變動落在 data-ui-explain 元素裡、或新增節點本身帶 data-ui-explain」的那幾筆，
//    其餘（時鐘、報價、列表重繪）直接略過，不再整頁 querySelectorAll。
// 先.八十-6（2026-10-12）：前台內部代號守門。各面板組字串的地方很多（innerHTML／textContent／setTxt），逐一包 uiPlain
// 容易漏；這裡在顯示層統一處理：#app 內的文字節點（[data-ui-advanced]、[data-ui-raw]、script/style 除外）只要命中
// UI_PLAIN_MAP 任一規則就改寫。先用一條合併 regex 快速判斷，沒命中就不動（時鐘每秒改字只多一次短字串比對）。
// 改寫後的文字不再命中，不會自我觸發迴圈。
const UI_TERM_TEST=new RegExp(UI_PLAIN_MAP.map(([re])=>re.source).join('|'));
function uiPlainRaw(t){let s=String(t);for(const [re,to] of UI_PLAIN_MAP)s=s.replace(re,to);return s}
function uiTermFixNode(n){
  try{
    if(!n||n.nodeType!==3)return;
    const v=n.nodeValue;if(!v||!UI_TERM_TEST.test(v))return;
    const el=n.parentElement;if(!el||/^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA)$/.test(el.tagName)||el.closest('[data-ui-advanced],[data-ui-raw],[data-ui-cite]'))return;
    const nv=uiPlainRaw(v);if(nv!==v)n.nodeValue=nv;
  }catch(e){console.warn('[uiTermFixNode]',e)}
}
function uiTermFixTree(root){
  try{
    if(!root)return;if(root.nodeType===3)return uiTermFixNode(root);
    const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);for(let n=w.nextNode();n;n=w.nextNode())uiTermFixNode(n);
  }catch(e){console.warn('[uiTermFixTree]',e)}
}
try{
  uiTermFixTree(document.getElementById('app'));
  new MutationObserver(ms=>{for(const m of ms){
    if(m.type==='characterData')uiTermFixNode(m.target);
    else m.addedNodes&&m.addedNodes.forEach(uiTermFixTree);
  }}).observe(document.getElementById('app'),{childList:true,subtree:true,characterData:true});
}catch(e){console.warn('[uiTermGuard:init]',e);recordGlobalError('uiTermGuard:init',e)}
const UI_NOTE_MAX=40;
function uiCompactNote(n){
  try{
    if(!n||!n.hasAttribute('data-ui-explain')||n.hasAttribute('data-ui-keep')||n.closest('[data-ui-advanced],[data-ui-footer-disclaimer]'))return;
    if(n.firstElementChild&&n.firstElementChild.matches('details[data-ui-detail]')&&n.childNodes.length===1)return;
    const t=(n.textContent||'').replace(/\s+/g,' ').trim();
    if([...t].length<=UI_NOTE_MAX)return;
    const d=document.createElement('details');d.setAttribute('data-ui-detail','');d.className='ui-info';
    const sm=document.createElement('summary');sm.textContent=/^⚠/.test(t)?'⚠ 注意':'ⓘ 說明';d.appendChild(sm);
    const body=document.createElement('div');body.className='ui-info-body';
    while(n.firstChild)body.appendChild(n.firstChild);
    d.appendChild(body);n.appendChild(d);
  }catch(e){console.warn('[uiCompactNote]',e);recordGlobalError('uiCompactNote',e)}
}
function uiMarkExplainNotes(root){
  (root||document).querySelectorAll('#app .note:not([id]):not([data-ui-keep])').forEach(n=>{
    if(n.closest('[data-ui-advanced],[data-ui-detail],[data-ui-footer-disclaimer]'))return;
    n.setAttribute('data-ui-explain','');
  });
}
function uiCompactAll(root){(root||document).querySelectorAll('#app .note[data-ui-explain]').forEach(uiCompactNote)}
window.__uiCompactScans=0;  // 冒煙 #105 用：觀察器實際處理（掃描）次數
let _uiCompactQ=new Set(),_uiCompactPending=false;
function _uiCompactFlush(){_uiCompactPending=false;const q=[..._uiCompactQ];_uiCompactQ.clear();if(!q.length)return;window.__uiCompactScans++;q.forEach(uiCompactNote)}
try{
  uiMarkExplainNotes();
  new MutationObserver(ms=>{
    for(const m of ms){
      const t=m.target&&m.target.nodeType===1?m.target:m.target&&m.target.parentElement;
      const host=t&&t.closest?t.closest('[data-ui-explain]'):null;
      if(host)_uiCompactQ.add(host);
      m.addedNodes&&m.addedNodes.forEach(a=>{if(a.nodeType!==1)return;if(a.matches('[data-ui-explain]'))_uiCompactQ.add(a);a.querySelectorAll&&a.querySelectorAll('[data-ui-explain]').forEach(x=>_uiCompactQ.add(x))});
    }
    if(_uiCompactQ.size&&!_uiCompactPending){_uiCompactPending=true;setTimeout(_uiCompactFlush,120)}
  }).observe(document.getElementById('app'),{childList:true,subtree:true,characterData:true});
  uiCompactAll();
}catch(e){console.warn('[uiCompact:init]',e);recordGlobalError('uiCompact:init',e)}
// 先.六十九-1：核心程式執行完畢（導覽、各面板載入函式都已註冊）＝可互動時間點；scripts/measure_second_open.mjs 讀這個值。
window.__ALPHA_BOOT_MS=performance.now();
