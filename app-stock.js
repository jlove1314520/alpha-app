// 常備.開發-20 丙案（2026-10-11 先.六十五）：個股頁專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('stock') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  function updateStockSimTag(code){
    const el=document.getElementById('sh-sim');if(!el)return;
    const t=(code&&!isUS(code))?simTradeText(code):'';
    el.textContent=t;el.hidden=!t;
  }
  // 個股頁頭部：把漲跌停徽章掛在名稱旁，價格格上色。個股頁的元素結構跟自選股列
  // 不同（名稱在 .stock-head .l 裡），所以另外寫一支，不硬套同一段字串樣板。
  function applyLimitBadge(code,price,prevClose,liveQuote){
    const head=document.querySelector('#scr-stock .stock-head');if(!head)return;
    const old=head.querySelector('.limit-badge');if(old)old.remove();
    const r=head.querySelector('.r');if(r)r.classList.remove('at-limit','lu','ld');
    const lim=limitPrices(code,prevClose,liveQuote);
    const st=limitState(price,lim);
    if(!st)return;
    const nameEl=head.querySelector('.l b');
    if(nameEl)nameEl.insertAdjacentHTML('afterend',limitBadge(st));
    if(r)r.classList.add('at-limit',st==='up'?'lu':'ld');
  }
  function disposalTagHtml(code){
    const f=disposalFlagOf(code);if(!f)return '';
    const md=s=>s?s.slice(5).replace('-','/'):'?';
    const esc=t=>String(t||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const tip=esc(uiPlain(f.reason||''));
    if(f.kind==='notice')return `<span class="disp-tag notice" title="${tip}">注意股 ${md(f.announced)}公布</span>`;
    const lbl=f.kind==='disposal'?'處置股':'即將處置';
    return `<span class="disp-tag" title="${tip}">${lbl} ${md(f.start)}–${md(f.end)}${f.interval?' · 每'+esc(f.interval.replace(/分鐘$/,''))+'分鐘撮合':''}</span>`;
  }
  async function updateStockDisposalTag(code){
    const el=document.getElementById('sh-flag');if(!el)return;
    el.innerHTML='';
    if(!code||isUS(code))return;
    await ensureDisposalFlags();
    if(currentCode!==code)return;
    el.innerHTML=disposalTagHtml(code);
  }
  function skeletonBlockHtml(height){return `<div class="skel-block" style="height:${height||160}px"></div>`}
  // 2026-08-27 架構修正：三大法人chip改讀stock_detail.json，數值已經是「張」
  // （fetch_market_tw.py抓T86時已經/1000過），不是原始股數，所以是直接round，
  // 不像舊版FinMind路徑的setChip()/zhang()還要再/1000一次。
  function setChipLots(id,v){const el=document.getElementById(id);if(!el)return;
    el.textContent=(v==null||isNaN(v)?'—':(v>=0?'+':'−')+Math.round(Math.abs(v)).toLocaleString()+' 張');
    el.className=v>=0?'pos':'neg'}
  function trendChart(cl,fmtLabel){
    if(cl.length<2)return '<div class="note">近月資料不足</div>';
    const mn=Math.min(...cl),mx=Math.max(...cl),rg=(mx-mn)||1;
    const up=cl[cl.length-1]>=cl[0];const col=`var(--${up?'up':'down'})`;
    const x=i=>(i/(cl.length-1)*320).toFixed(1);
    const y=c=>(96-(c-mn)/rg*80).toFixed(1);
    const pts=cl.map((c,i)=>`${x(i)},${y(c)}`).join(' ');
    const lastX=x(cl.length-1),lastY=y(cl[cl.length-1]);
    return `<svg viewBox="0 0 320 110" style="width:100%">
      <line x1="0" y1="96" x2="320" y2="96" stroke="#383835" stroke-width="1"/>
      <line x1="0" y1="56" x2="320" y2="56" stroke="#2c2c2a" stroke-width="1"/>
      <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/>
      <circle cx="${lastX}" cy="${lastY}" r="3.5" fill="${col}"/>
      <text x="${Math.min(318,Math.max(2,+lastX))}" y="${Math.max(12,+lastY-8)}" text-anchor="${+lastX>280?'end':'middle'}" font-size="10" fill="var(--ink-2)">${fmtLabel(cl[cl.length-1])}</text>
    </svg>`;
  }
  // 2026-08-27 新增：個股頁財報/三大法人/融資融券改讀 data/stock_detail.json
  // （見 .github/scripts/update_stock_financials.py + fetch_market_tw.py +
  // update_margin_maintenance.py 三支排程腳本合力寫入），不再對FinMind打
  // FinancialStatements/BalanceSheet/InstitutionalInvestorsBuySell/
  // MarginPurchaseShortSale。只涵蓋TWSE「上市公司」（t187ap06_L_ci「一般業」
  // 分類），上櫃股票/金融股目前查不到會自然回傳{}，呼叫端顯示「—」不崩潰。
  // 常備.開發-20（2026-10-11）：整份 stock_detail.json 約 14MB，改成每檔一個檔案
  // data/stock_detail/{代號}.json（scripts/split_stock_detail.py 從整份檔切出，內容相同），
  // 開哪一檔才抓哪一檔。404＝該代號不在涵蓋範圍，跟以前「整份檔裡查不到」一樣回傳{}。
  // 同一檔的並行呼叫共用同一個 Promise，不重複下載。
  const STOCK_DETAIL_BY_CODE={};
  function loadStockDetail(code){
    code=String(code||'');
    if(!/^[0-9A-Za-z]{2,10}$/.test(code))return Promise.resolve({});
    if(!STOCK_DETAIL_BY_CODE[code]){
      STOCK_DETAIL_BY_CODE[code]=fetch('data/stock_detail/'+code+'.json?t='+Date.now())
        .then(r=>r.ok?r.json():{})
        .then(d=>(d&&typeof d==='object')?d:{})
        .catch(e=>{console.warn('[loadStockDetail]',code,e);recordGlobalError('loadStockDetail',e);delete STOCK_DETAIL_BY_CODE[code];return {}});
    }
    return STOCK_DETAIL_BY_CODE[code];
  }
  // 2026-09-02新增（B29：美股個股頁財報UI）；2026-10-11 常備.開發-16 改為
  // SEC XBRL companyfacts 每週排程（.github/scripts/fetch_us_financials_sec.py、
  // .github/workflows/us_financials.yml），涵蓋 NYSE/Nasdaq 名冊前段約 250 檔，
  // 欄位為年度值（非逐季）＋最近一期負債比——查不到的代號一律顯示「暫無」，
  // 不得假裝有資料。
  let US_FINANCIALS_CACHE=null;
  async function loadUsFinancials(code){
    if(!US_FINANCIALS_CACHE){
      try{const r=await fetch('data/us_financials.json?t='+Date.now());if(r.ok)US_FINANCIALS_CACHE=await r.json()}catch(e){console.warn('[loadUsFinancials]',e);recordGlobalError('loadUsFinancials',e);US_FINANCIALS_CACHE={financials:{}}}
    }
    return (US_FINANCIALS_CACHE&&US_FINANCIALS_CACHE.financials&&US_FINANCIALS_CACHE.financials[code])||null;
  }
  async function loadFinancialsUS(code){
    const f=await loadUsFinancials(code);
    if(currentCode!==code)return; // 使用者已切到別檔股票，這份資料作廢
    setTxt('eps-bars-title','年度利潤率（美股，非逐季）');
    setTxt('fin-roe-lbl','營收年增（年度）');
    setTxt('fin-fcf-lbl','FCF 利潤率（年度）');
    if(!f){
      document.getElementById('eps-bars').innerHTML='<div class="note">美股暫無此代號的 SEC 年報資料（每週排程涵蓋 NYSE/Nasdaq 名冊前段約 250 檔）</div>';
      ['fin-gross','fin-op','fin-roe','fin-fcf'].forEach(id=>setTxt(id,'—'));
      setTxt('fin-note','美股暫無此代號的財報資料');
      return;
    }
    const _pct=v=>v!=null?(v*100).toFixed(1)+'%':'—';
    const _cur=f.currency&&f.currency!=='USD'?f.currency+' ':'';
    const _eps=f.eps!=null?`EPS${f.eps_kind==='basic'?'(基本)':'(稀釋)'} ${_cur}${f.eps}`:'EPS —';
    document.getElementById('eps-bars').innerHTML=`<div class="note">${_eps} · 負債比 ${_pct(f.debt_ratio)}${f.balance_period_end?'（'+f.balance_period_end+'）':''} · 毛利率 ${_pct(f.gross_margin)} · 營益率 ${_pct(f.operating_margin)} · 期間 ${f.period_end}（較前期 ${f.prior_period_end||'—'}）</div>`;
    setTxt('fin-gross',f.gross_margin!=null?(f.gross_margin*100).toFixed(1)+'%':'—');
    setTxt('fin-op',f.operating_margin!=null?(f.operating_margin*100).toFixed(1)+'%':'—');
    if(f.revenue_yoy!=null){const re=document.getElementById('fin-roe');re.textContent=(f.revenue_yoy>=0?'+':'')+(f.revenue_yoy*100).toFixed(1)+'%';re.className=f.revenue_yoy>=0?'pos':'neg'}
    else setTxt('fin-roe','—');
    setTxt('fin-fcf',f.fcf_margin!=null?(f.fcf_margin*100).toFixed(1)+'%':'—');
    const warn=(f.missing_fields&&f.missing_fields.length)?` · 缺漏欄位：${f.missing_fields.join('/')}`:'';
    const usAt=US_FINANCIALS_CACHE&&US_FINANCIALS_CACHE.generated_at?String(US_FINANCIALS_CACHE.generated_at).slice(0,10):'不明';
    const fw=(f.warnings&&f.warnings.length)?` · ${f.warnings.join('；')}`:'';
    setTxt('fin-note',`來源：SEC XBRL 年報（每週排程更新；更新日 ${usAt}；申報日 ${f.filed||'—'}）· 期末 ${f.period_end}${warn}${fw}`);
  }

  // 2026-08-27 架構修正：改讀 data/stock_detail.json（見 fetch_market_tw.py 從
  // 排程已經在打的T86回應多榨出來的逐股三大法人買賣超，累積近5日history），不再
  // 對FinMind打TaiwanStockInstitutionalInvestorsBuySell。只涵蓋跟financials同一份
  // 「上市公司」名單，查不到回傳null（沿用舊行為，呼叫端已經會處理null）。
  function _t86Date(d){return d&&d.length===8?`${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`:d}
  async function instNet(code){
    const detail=await loadStockDetail(code);
    const inst=detail.institutional;
    if(!inst)return null;
    const series=(inst.history||[]).map(h=>({date:_t86Date(h.date),v:h.foreign_lots}));
    return{date:_t86Date(inst.date),foreign:inst.foreign_lots,trust:inst.trust_lots,dealer:inst.dealer_lots,total:inst.foreign_lots+inst.trust_lots+(inst.dealer_lots||0),series,history:inst.history||[]};
  }
  // 2026-09-04（籌碼分頁免費層第一單位）：三大法人逐日／累計表＋外資估算成本。
  // 資料只用stock_detail.json既有的institutional.history（market.yml每日累積，剛開始
  // 只有幾天，會逐日變長）；估算成本=近N日「外資淨買超日」的淨買張數×當日收盤加權
  // 平均（不知道真正逐筆成交價，只能概估），畫面明確標「估算、非精確成本」，且
  // 有走勢圖時把這條價位畫上去（lightweight-charts的priceLine）。
  // 2026-09-08（金流一.3）個股籌碼徽章，資料來自 data/sector_flow.json。
  // **只顯示算得出來的**：streak_days 與 foreign_trust_aligned 現在就有；
  // abnormal（60日z）、逆勢買超、法人20日均價需要更長視窗，沒有就整個不畫，
  // 不用短視窗冒充——一個看起來像那麼回事的假徽章比沒有徽章傷害大得多。
  async function renderChipBadges(code){
    const host=document.getElementById('chip-badges');if(!host)return;
    host.innerHTML='';
    const d=await ensureSectorFlow();
    const e=d&&d.stocks&&d.stocks[code];
    if(!e)return;
    const m=d.meta||{},badges=[];
    const pill=(txt,col)=>`<span style="display:inline-block;font-size:10px;font-weight:700;color:${col};border:1px solid ${col};border-radius:6px;padding:2px 7px;margin:0 5px 5px 0">${txt}</span>`;
    const sd=e.streak_days||{};
    const st=sd.total;
    if(st&&Math.abs(st)>=2)
      badges.push(pill(`三大法人連${st>0?'買':'賣'} ${Math.abs(st)} 日`,st>0?'var(--up)':'var(--down)'));
    if(sd.foreign&&Math.abs(sd.foreign)>=2)
      badges.push(pill(`外資連${sd.foreign>0?'買':'賣'} ${Math.abs(sd.foreign)} 日`,sd.foreign>0?'var(--up)':'var(--down)'));
    if(sd.trust&&Math.abs(sd.trust)>=2)
      badges.push(pill(`投信連${sd.trust>0?'買':'賣'} ${Math.abs(sd.trust)} 日`,sd.trust>0?'var(--up)':'var(--down)'));
    const w0=(m.windows_usable||[])[0];
    if(e.foreign_trust_aligned&&w0!=null){
      const f=(e['net_'+w0+'d']||{}).foreign_lots||0;
      badges.push(pill(f>0?'土洋同買':'土洋同賣',f>0?'var(--up)':'var(--down)'));
    }
    if(e.abnormal&&e.z_today!=null)
      badges.push(pill(`異常大${e.z_today>0?'買':'賣'}（z=${e.z_today}）`,'var(--gold)'));
    if(!badges.length){
      host.innerHTML='<div class="note">近期無連續買賣（≥2 日）或土洋同買訊號。</div>';
      return;
    }
    const miss=m.windows_missing_days||{};
    const missTxt=Object.keys(miss).length
      ?`　異常大買（60 日 z 分數）、逆勢買超、法人 20 日均價需更長視窗，`
        +`${Object.entries(miss).map(([w,n])=>`${w} 日還需 ${n} 個交易日`).join('、')}，`
        +`累積足夠前不顯示。`:'';
    host.innerHTML=badges.join('')
      +`<div class="note" style="margin-top:2px">法人行為（描述性資訊，非預測訊號）。`
      +`資料日 ${m.date||'—'}。${missTxt}</div>`;
  }
  function renderChipTrend(code,inst,px){
    const tbl=document.getElementById('chip-trend-table'),note=document.getElementById('chip-trend-note'),cost=document.getElementById('chip-cost-note');
    if(!tbl)return;
    const hist=(inst&&inst.history||[]).filter(h=>h&&h.date).slice().sort((a,b)=>a.date<b.date?-1:1);
    if(!hist.length){tbl.innerHTML='<div class="note">查無逐日法人資料（僅涵蓋TWSE上市／TPEx上櫃股票，且排程剛開始累積）</div>';if(note)note.textContent='';if(cost)cost.textContent='外資估算成本：—（無逐日資料）';return}
    let cum=0;const fmt=v=>v==null?'—':`<span class="${v>=0?'pos':'neg'}">${v>=0?'+':''}${nf(Math.round(v))}</span>`;
    const rows=hist.map(h=>{const f=h.foreign_lots||0,t=h.trust_lots||0,d=h.dealer_lots||0,tot=f+t+d;cum+=tot;
      return `<tr><td style="color:var(--ink-3)">${_t86Date(h.date).slice(5)}</td><td>${fmt(f)}</td><td>${fmt(t)}</td><td>${fmt(d)}</td><td>${fmt(tot)}</td><td>${fmt(cum)}</td></tr>`}).join('');
    tbl.innerHTML=`<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11px;text-align:right"><thead><tr style="color:var(--ink-3)"><th style="text-align:left">日期</th><th>外資</th><th>投信</th><th>自營</th><th>合計</th><th>累計</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    if(note)note.textContent=`自 ${_t86Date(hist[0].date)} 起累積 ${hist.length} 個交易日（TWSE T86／TPEx 每日排程累積，天數會逐日增加）· 三大法人累計 ${cum>=0?'+':''}${nf(Math.round(cum))} 張`;
    // 外資估算成本
    const closeByDate={};(px||[]).forEach(r=>{if(r&&r.date&&r.close!=null)closeByDate[r.date]=r.close});
    let lots=0,amt=0,used=0;
    hist.forEach(h=>{const f=h.foreign_lots||0;const c=closeByDate[_t86Date(h.date)];if(f>0&&c!=null){lots+=f;amt+=f*c;used++}});
    if(cost){
      if(lots>0){const est=amt/lots;cost.innerHTML=`外資估算成本：<b>${nf(est)}</b>（估算、非精確成本：以近 ${hist.length} 日中 ${used} 個外資淨買超日的淨買張數×當日收盤加權概算，不是逐筆成交成本；資料天數愈少愈不可靠）`;
        try{if(STOCK_CHART.series&&STOCK_CHART.code===code){if(STOCK_CHART.costLine){try{STOCK_CHART.series.removePriceLine(STOCK_CHART.costLine)}catch(e){}}STOCK_CHART.costLine=STOCK_CHART.series.createPriceLine({price:est,color:'#d4a84b',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'外資估算成本'})}}catch(e){console.warn('[renderChipTrend:priceLine]',e)}
      }else{cost.textContent='外資估算成本：—（近期沒有外資淨買超日，或無對應收盤價）'}
    }
  }

  // 2026-08-25 新增：個股融資融券（籌碼分頁）。融資餘額變化/融券餘額/資券比/券資比是
  // 準確資料；「估算融資維持率」是自己算的，公式：融資餘額(張)×現價÷
  // 估計融資金額，估計融資金額用「近20日均價×融資成數60%」概估原始成本（不知道真正
  // 每筆融資的實際進場價，只能用近期均價概估），畫面上明確標「估算值」，跟上面幾個
  // 準確資料分開，符合使用者要求「準確資料權重要高於估算值」。
  // 2026-08-27 架構修正：改讀 data/stock_detail.json（見
  // update_margin_maintenance.py 從排程已經在打的MI_MARGN多榨出來的逐股融資融券），
  // 不再對FinMind打TaiwanStockMarginPurchaseShortSale。
  async function loadMarginChip(code,px){
    const detail=await loadStockDetail(code);
    const mg=detail.margin;
    if(!mg||mg.margin_balance_today==null){
      ['mg-balance','mg-balance-chg','mg-short','mg-ratio'].forEach(id=>setTxt(id,'—'));
      setTxt('mg-short-ratio','券資比：—');setTxt('mg-note',fmEmptyMsg('查無融資融券資料'));
      setTxt('mg-maint','估算融資維持率：—');
      return;
    }
    const marginBal=mg.margin_balance_today,marginPrev=mg.margin_balance_prev??marginBal;
    const shortBal=mg.short_balance_today||0;
    const chg=marginBal-marginPrev;
    setTxt('mg-balance',nf(marginBal)+' 張');
    const ce=document.getElementById('mg-balance-chg');ce.textContent=(chg>=0?'+':'')+nf(chg)+' 張';ce.className=chg>=0?'pos':'neg';
    setTxt('mg-short',nf(shortBal)+' 張');
    setTxt('mg-ratio',shortBal>0?(marginBal/shortBal).toFixed(1)+' 倍':'—（融券餘額為0）');
    setTxt('mg-short-ratio',`券資比：${marginBal>0?(shortBal/marginBal*100).toFixed(2)+'%':'—'}`);
    setTxt('mg-note','來源：TWSE MI_MARGN（GitHub Actions 排程）');
    if(px&&px.length&&marginBal>0){
      const last20=px.slice(-20).map(x=>x.close);
      const avg20=last20.reduce((a,b)=>a+b,0)/last20.length;
      const curPx=px[px.length-1].close;
      const estMaintenance=avg20>0?(curPx/avg20)/0.6*100:null;
      const me=document.getElementById('mg-maint');
      if(estMaintenance!=null){
        const lv=marginLevel(estMaintenance);
        me.innerHTML=`估算融資維持率：<b style="color:${lv?lv.c:'inherit'}">${estMaintenance.toFixed(1)}%</b>（估算值，非券商實際維持率——以近20日均價概估原始融資成本、假設融資成數60%，非個股真實逐筆成本）`;
      }else{me.textContent='估算融資維持率：—'}
    }else{setTxt('mg-maint','估算融資維持率：—（融資餘額為0或無足夠股價資料）')}
  }

  // 2026-09-15（源頭二.3第1名）外資持股比率，TWSE官方MI_QFIIS，
  // .github/scripts/fetch_foreign_holding.py每日排程產生 data/foreign_holding.json。
  // 跟loadStockDetail同一種「內存快取+fetch失敗不外溢」寫法。
  let FOREIGN_HOLDING_CACHE=null;
  async function loadForeignHoldingCache(){
    if(FOREIGN_HOLDING_CACHE)return FOREIGN_HOLDING_CACHE;
    try{const r=await fetch('data/foreign_holding.json?t='+Date.now());if(r.ok)FOREIGN_HOLDING_CACHE=await r.json()}
    catch(e){console.warn('[loadForeignHoldingCache]',e);recordGlobalError('loadForeignHoldingCache',e)}
    return FOREIGN_HOLDING_CACHE||{stocks:{}};
  }
  async function loadForeignHoldingChip(code){
    try{
      const d=await loadForeignHoldingCache();
      const e=d.stocks&&d.stocks[code];
      if(!e||e.foreign_holding_ratio==null){
        setTxt('fh-ratio','—');setTxt('fh-can-invest','—');
        setTxt('fh-note',fmEmptyMsg('查無外資持股資料'));
        return;
      }
      setTxt('fh-ratio',e.foreign_holding_ratio+'%');
      setTxt('fh-can-invest',e.foreign_can_invest_ratio!=null?e.foreign_can_invest_ratio+'%':'—');
      setTxt('fh-note',`資料日 ${e.date} · 來源：TWSE MI_QFIIS（GitHub Actions 排程）`);
    }catch(e){
      console.warn('[loadForeignHoldingChip]',e);recordGlobalError('loadForeignHoldingChip',e);
      setTxt('fh-note','載入失敗');
    }
  }

  // 2026-09-15（源頭二.3第5名）可借券賣出股數，TWSE官方SBL/TWT96U，僅適用台股。
  // 注意：只有「可借額度」，不是借券費率、不是已借部位（見fetch腳本docstring）。
  let SHORT_LENDING_CACHE=null;
  async function loadShortLendingChip(code){
    try{
      if(!SHORT_LENDING_CACHE){
        try{const r=await fetch('data/short_lending_available.json?t='+Date.now());if(r.ok)SHORT_LENDING_CACHE=await r.json()}
        catch(e){console.warn('[loadShortLendingChip:fetch]',e);recordGlobalError('loadShortLendingChip:fetch',e)}
      }
      const d=SHORT_LENDING_CACHE;
      const twseVol=d&&d.twse&&d.twse[code];
      const vol=twseVol!=null?twseVol:(d&&d.otc&&d.otc[code]);
      if(vol==null){
        setTxt('sbl-available',fmEmptyMsg('查無資料'));
        setTxt('sbl-note','來源：TWSE SBL/TWT96U（GitHub Actions 排程）');
        return;
      }
      setTxt('sbl-available',nf(vol)+' 股');
      setTxt('sbl-note',`僅可借額度，非借券費率、非已借部位 · 來源：TWSE SBL/TWT96U（GitHub Actions 排程）`);
    }catch(e){
      console.warn('[loadShortLendingChip]',e);recordGlobalError('loadShortLendingChip',e);
      setTxt('sbl-note','載入失敗');
    }
  }

  // 2026-09-15（源頭一.3）千張大戶（集保opendata.tdcc.com.tw），僅適用台股，每週五20:00更新。
  let TDCC_HOLDERS_CACHE=null;
  async function loadTdccHoldersChip(code){
    try{
      if(!TDCC_HOLDERS_CACHE){
        try{const r=await fetch('data/holders.json?t='+Date.now());if(r.ok)TDCC_HOLDERS_CACHE=await r.json()}
        catch(e){console.warn('[loadTdccHoldersChip:fetch]',e);recordGlobalError('loadTdccHoldersChip:fetch',e)}
      }
      const rec=TDCC_HOLDERS_CACHE&&TDCC_HOLDERS_CACHE.stocks&&TDCC_HOLDERS_CACHE.stocks[code];
      if(!rec){
        setTxt('tdcc-big-ratio',fmEmptyMsg('查無資料'));
        setTxt('tdcc-small-ratio','—');setTxt('tdcc-week-chg','—');setTxt('tdcc-streak','—');
        setTxt('tdcc-note','來源：集保結算所（每週五 20:00 排程）');
        return;
      }
      setTxt('tdcc-big-ratio',rec.big_holder_ratio!=null?rec.big_holder_ratio.toFixed(2)+'%':'—');
      setTxt('tdcc-small-ratio',rec.small_holder_ratio!=null?rec.small_holder_ratio.toFixed(2)+'%':'—');
      setTxt('tdcc-week-chg',rec.week_change_pct!=null?((rec.week_change_pct>=0?'+':'')+rec.week_change_pct.toFixed(2)+'%'):'僅一週資料，無週變化');
      setTxt('tdcc-streak',rec.streak_weeks!=null?rec.streak_weeks+' 週':'—');
      setTxt('tdcc-note',`資料日 ${rec.date||'—'} · 來源：集保結算所（每週五 20:00 排程）`);
    }catch(e){
      console.warn('[loadTdccHoldersChip]',e);recordGlobalError('loadTdccHoldersChip',e);
      setTxt('tdcc-note','載入失敗');
    }
  }

  // 2026-09-15（源頭一.3）借券賣出當日成交量，TWSE官方TWT93U＋TPEx官方tpex_short_sell。
  // 注意：跟loadShortLendingChip（可借額度）是不同的資料，這裡是「今天實際借出去賣了多少」。
  let SBL_SELL_CACHE=null;
  async function loadSblSellChip(code){
    try{
      if(!SBL_SELL_CACHE){
        try{const r=await fetch('data/securities_lending_sell.json?t='+Date.now());if(r.ok)SBL_SELL_CACHE=await r.json()}
        catch(e){console.warn('[loadSblSellChip:fetch]',e);recordGlobalError('loadSblSellChip:fetch',e)}
      }
      const d=SBL_SELL_CACHE;
      const tw=d&&d.twse&&d.twse[code];
      const otc=d&&d.tpex&&d.tpex[code];
      if(!tw&&!otc){
        setTxt('sbl-sell-volume',fmEmptyMsg('查無資料'));
        setTxt('sbl-sell-return','—');
        setTxt('sbl-sell-note','來源：TWSE TWT93U／TPEx tpex_short_sell（GitHub Actions 排程）');
        return;
      }
      if(tw){
        setTxt('sbl-sell-volume',nf(tw.sbl_sell)+' 股');
        setTxt('sbl-sell-return',nf(tw.sbl_return)+' 股');
        setTxt('sbl-sell-note',`資料日 ${d.twse_date||'—'} · 上市（TWSE TWT93U）· 多數股票非0視為正常`);
      }else{
        setTxt('sbl-sell-volume',nf(otc.sbl_sell_volume)+' 股');
        setTxt('sbl-sell-return',fmEmptyMsg('TPEx端點無此欄位'));
        setTxt('sbl-sell-note',`資料日 ${d.tpex_date||'—'} · 上櫃（TPEx tpex_short_sell）`);
      }
    }catch(e){
      console.warn('[loadSblSellChip]',e);recordGlobalError('loadSblSellChip',e);
      setTxt('sbl-sell-note','載入失敗');
    }
  }

  // 2026-09-15（源頭二.3第2名）內部人交易，SEC EDGAR官方Form 4，
  // .github/scripts/fetch_us_insider_trading.py每日排程產生 data/us_insider_trading.json。
  // 僅適用美股（台股走loadForeignHoldingChip那張卡，兩者互斥顯示）。
  let INSIDER_TRADING_CACHE=null;
  async function loadInsiderTradingCache(){
    if(INSIDER_TRADING_CACHE)return INSIDER_TRADING_CACHE;
    try{const r=await fetch('data/us_insider_trading.json?t='+Date.now());if(r.ok)INSIDER_TRADING_CACHE=await r.json()}
    catch(e){console.warn('[loadInsiderTradingCache]',e);recordGlobalError('loadInsiderTradingCache',e)}
    return INSIDER_TRADING_CACHE||{tickers:{}};
  }
  function setInsiderTradingNA(msg){
    setTxt('insider-note',msg);
    document.getElementById('insider-table').innerHTML='<div class="note">'+msg+'</div>';
  }
  async function loadInsiderTradingChip(code){
    try{
      const d=await loadInsiderTradingCache();
      const e=d.tickers&&d.tickers[code];
      const txns=e&&e.transactions;
      if(!txns||!txns.length){
        setInsiderTradingNA(fmEmptyMsg('查無內部人交易資料'));
        return;
      }
      const rows=txns.slice(0,5).map(t=>{
        const shares=t.shares!=null?nf(t.shares):'—';
        const price=t.price!=null?'$'+nf(t.price):'—';
        const cls=t.code==='P'?'pos':(t.code==='S'?'neg':'');
        return `<div class="f"><span>${t.transaction_date||'—'} ${t.reporting_owner||''}${t.title?'（'+t.title+'）':''}</span><b class="${cls}">${t.code_label||t.code||'—'} ${shares}股 @ ${price}</b></div>`;
      }).join('');
      document.getElementById('insider-table').innerHTML=`<div class="facts">${rows}</div>`;
      setTxt('insider-note',`近${txns.length}筆申報（買${e.buy_count||0}/賣${e.sell_count||0}）· 來源：SEC EDGAR Form 4（GitHub Actions 排程）`);
    }catch(e){
      console.warn('[loadInsiderTradingChip]',e);recordGlobalError('loadInsiderTradingChip',e);
      setInsiderTradingNA('載入失敗');
    }
  }

  // 2026-09-15（源頭二.3第6名）機構持倉，SEC EDGAR官方Form 13F，僅追蹤波克夏
  // 海瑟威一家申報人（未做CUSIP對映/全市場13F整合），僅適用美股。
  let US_13F_CACHE=null;
  function setUs13fNA(msg){
    setTxt('f13-note',msg);
    document.getElementById('f13-rows').innerHTML='<div class="note">'+msg+'</div>';
  }
  async function loadUs13fChip(code){
    try{
      if(!US_13F_CACHE){
        try{const r=await fetch('data/us_13f_holdings.json?t='+Date.now());if(r.ok)US_13F_CACHE=await r.json()}
        catch(e){console.warn('[loadUs13fChip:fetch]',e);recordGlobalError('loadUs13fChip:fetch',e)}
      }
      const filer=US_13F_CACHE&&US_13F_CACHE.filers&&US_13F_CACHE.filers.berkshire_hathaway;
      if(!filer){setUs13fNA(fmEmptyMsg('查無13F資料'));return}
      const h=filer.holdings&&filer.holdings[code];
      if(!h){
        setUs13fNA(`波克夏海瑟威最新13F（申報日${filer.filed_at||'—'}）未列此檔部位`);
        return;
      }
      document.getElementById('f13-rows').innerHTML=`<div class="f"><span>波克夏海瑟威</span><b>${nf(h.shares)}股（申報市值約US$${nf(Math.round(h.value_usd/1e6))}M）</b></div>`;
      setTxt('f13-note',`申報日 ${filer.filed_at||'—'} · 來源：SEC EDGAR Form 13F-HR（GitHub Actions 排程，僅追蹤波克夏一家申報人）`);
    }catch(e){
      console.warn('[loadUs13fChip]',e);recordGlobalError('loadUs13fChip',e);
      setUs13fNA('載入失敗');
    }
  }

  // 2026-09-15（PENDING_QUEUE「三」美股半邊）重大訊息，SEC EDGAR官方Form 8-K，
  // .github/scripts/fetch_us_8k.py每日排程產生 data/us_events.json，僅適用美股。
  let US_8K_CACHE=null;
  function setUs8kNA(msg){
    setTxt('us8k-note',msg);
    document.getElementById('us8k-table').innerHTML='<div class="note">'+msg+'</div>';
  }
  async function loadUs8kChip(code){
    try{
      if(!US_8K_CACHE){
        try{const r=await fetch('data/us_events.json?t='+Date.now());if(r.ok)US_8K_CACHE=await r.json()}
        catch(e){console.warn('[loadUs8kChip:fetch]',e);recordGlobalError('loadUs8kChip:fetch',e)}
      }
      const d=US_8K_CACHE||{};
      const e=d.tickers&&d.tickers[code];
      const filings=e&&e.filings;
      if(!filings||!filings.length){
        setUs8kNA(fmEmptyMsg('查無8-K申報資料（近'+(d.keep_days||180)+'天）'));
        return;
      }
      const rows=filings.slice(0,5).map(f=>{
        const items=(f.items&&f.items.length)?f.items.join('；'):'（無Item條號說明）';
        return `<div class="f" style="align-items:flex-start"><span>${f.filed_at||'—'}${f.filing_type&&f.filing_type!=='8-K'?'（'+f.filing_type+'）':''}</span><b style="text-align:right;max-width:70%"><a href="${f.url}" target="_blank" rel="noopener">${items}</a></b></div>`;
      }).join('');
      document.getElementById('us8k-table').innerHTML=`<div class="facts">${rows}</div>`;
      setTxt('us8k-note',`近${filings.length}筆申報 · 來源：SEC EDGAR Form 8-K（GitHub Actions 排程，只存索引不存全文）`);
    }catch(e){
      console.warn('[loadUs8kChip]',e);recordGlobalError('loadUs8kChip',e);
      setUs8kNA('載入失敗');
    }
  }

  // 2026-08-27 架構修正：EPS/毛利率/營益率/ROE改讀 data/stock_detail.json（見
  // update_stock_financials.py，TWSE官方t187ap06_L_ci綜合損益表+t187ap07_L_ci
  // 資產負債表，累積式寫回），不再對FinMind打FinancialStatements/BalanceSheet。
  // **FCF維持FinMind、非本輪範圍**：TWSE官方開放資料沒有現金流量表對應端點
  // （已查證swagger完整清單確認），這是永久性限制，不是漏遷移——查不到就誠實
  // 顯示「TWSE無此資料源」而不是留著FinMind呼叫假裝有替代來源。
  let CASH_FLOW_CACHE=null;
  async function loadCashFlow(){
    if(!CASH_FLOW_CACHE){const r=await fetch('data/cash_flow.json?t='+Date.now());if(!r.ok)throw new Error('HTTP '+r.status);CASH_FLOW_CACHE=await r.json()}
    return CASH_FLOW_CACHE;
  }
  async function loadFinancials(code){
    const detail=await loadStockDetail(code);
    if(currentCode!==code)return; // 使用者已切到別檔股票，這份資料作廢
    const fin=(detail.financials&&detail.financials.quarters)||[];
    if(fin.length){
      const vals=fin.map(q=>q.eps).filter(v=>v!=null);
      const mx=Math.max(...vals.map(Math.abs))||1;
      document.getElementById('eps-bars').innerHTML=fin.filter(q=>q.eps!=null).map((q,i,arr)=>{const isl=i===arr.length-1;
        return `<div class="b"><span class="v">${q.eps.toFixed(1)}</span><i style="height:${Math.max(8,Math.abs(q.eps)/mx*100).toFixed(0)}%${isl?';background:var(--accent-deep);outline:2px solid var(--accent);outline-offset:-2px':''}"></i><em>${q.year}Q${q.quarter}</em></div>`}).join('')
        ||'<div class="note">查無財報 EPS</div>';
    }else{document.getElementById('eps-bars').innerHTML='<div class="note">查無財報 EPS</div>'}
    const last=fin.length?fin[fin.length-1]:null;
    setTxt('fin-gross',last&&last.gross_margin_pct!=null?last.gross_margin_pct.toFixed(1)+'%':'—');
    setTxt('fin-op',last&&last.op_margin_pct!=null?last.op_margin_pct.toFixed(1)+'%':'—');
    const roe=detail.financials&&detail.financials.roe_ttm_pct;
    if(roe!=null){const re=document.getElementById('fin-roe');re.textContent=(roe>=0?'+':'')+roe.toFixed(1)+'%';re.className=roe>=0?'pos':'neg'}
    else{setTxt('fin-roe','—')}
    // 常備.開發-7（2026-10-11）：FCF 改讀 data/cash_flow.json（FinMind 現金流量表本機快取→每季手動產生，TTM），
    // 官方 openapi 無現金流量表端點；查不到時說明原因，不留「—」讓人猜。
    let fcfNote='FCF：';
    try{
      const cf=await loadCashFlow(),x=cf&&cf.stocks&&cf.stocks[code];
      if(currentCode!==code)return;
      if(x&&x.fcf_ttm!=null){
        const e=document.getElementById('fin-fcf');e.textContent=(x.fcf_ttm/1e8).toFixed(1)+' 億';e.className=x.fcf_ttm>=0?'pos':'neg';
        setTxt('fin-fcf-lbl','自由現金流（近四季）');
        fcfNote+=`近四季至 ${x.as_of}，營業現金流 ${(x.cfo_ttm/1e8).toFixed(1)} 億＋資本支出 ${(x.capex_ttm/1e8).toFixed(1)} 億；來源 FinMind 現金流量表（非官方，每季更新）`;
      }else{
        setTxt('fin-fcf','—');
        fcfNote+=cf?'此代號不在 FinMind 現金流量表快取（金融業格式不同或快取缺檔），TWSE／TPEx 官方無現金流量表開放資料':'現金流量表檔讀取失敗';
      }
    }catch(e){console.warn('[loadFinancials:fcf]',e);recordGlobalError('loadFinancials:fcf',e);setTxt('fin-fcf','—');fcfNote+='讀取失敗'}
    // 常備.開發-4（2026-10-11）：上市金融業＋上櫃財報。來源標記讀 financials.source；
    // 官方只給最新一季「累計數」，單季序列有 2025Q1~2026Q1 斷層的公司，另外顯示最新累計（latest_cum）。
    const F=detail.financials||{},lc=F.latest_cum,src=F.source||(last?'t187ap06_L_ci':'');
    const srcTxt=src?((/_O_|mopsfin/.test(src)?'TPEx官方 ':'TWSE官方 ')+src+'（'+(F.industry_format||'上市一般業')+'）'):'';
    const lcNewer=lc&&(!last||lc.year*4+lc.quarter>last.year*4+last.quarter);
    if(lcNewer&&!last){
      setTxt('fin-gross',lc.gross_cum!=null&&lc.revenue_cum?(lc.gross_cum/lc.revenue_cum*100).toFixed(1)+'%（累計）':'—');
      setTxt('fin-op',lc.op_cum!=null&&lc.revenue_cum?(lc.op_cum/lc.revenue_cum*100).toFixed(1)+'%（累計）':'—');
    }
    const lcTxt=lcNewer?` · 最新官方累計 ${lc.year} 前${lc.quarter}季：${lc.revenue_cum!=null?'營收 '+(lc.revenue_cum/1e8).toFixed(1)+' 億、':''}EPS ${lc.eps_cum!=null?lc.eps_cum.toFixed(2):'—'}（累計數，非單季）${last?`；單季序列停在 ${last.year}Q${last.quarter}，下一季起以累計差分補上`:''}`:'';
    if(last||lc)setTxt('fin-note',`來源：${srcTxt}${last?` · 單季 ${last.year}Q${last.quarter}`:''}${lcTxt}；${fcfNote}`);
    else setTxt('fin-note','查無財報資料（TWSE／TPEx 官方開放資料皆無此代號，可能為興櫃、ETF 或新上市）');
  }
  async function loadRevenueChart(code,rev){
    const amtEl=document.getElementById('rev-chart-amt'),yoyEl=document.getElementById('rev-chart-yoy'),lblEl=document.getElementById('rev-chart-labels');
    if(!amtEl)return;
    if(!rev.length){amtEl.innerHTML='<div class="note">查無月營收</div>';yoyEl.innerHTML='';lblEl.innerHTML='';setTxt('kn-yoy','—');REV_ROWS=[];return}
    const px=await fm('TaiwanStockPrice',code,_d(430));
    if(currentCode!==code)return;
    const priceAt=(y,m)=>{
      const inMonth=px.filter(p=>{const d=p.date.split('-');return +d[0]===y&&+d[1]===m});
      return inMonth.length?inMonth[inMonth.length-1].close:null;
    };
    const bars=rev.slice(-8);
    REV_ROWS=bars.map(r=>{
      let py=r.revenue_year,pm=r.revenue_month-1;if(pm===0){pm=12;py--}
      const prev=rev.find(x=>x.revenue_year===py&&x.revenue_month===pm);
      const mom=prev&&prev.revenue?(r.revenue-prev.revenue)/prev.revenue*100:null;
      const yr=rev.find(x=>x.revenue_year===r.revenue_year-1&&x.revenue_month===r.revenue_month);
      const yoy=r.yoyPre!=null?r.yoyPre:(yr&&yr.revenue?(r.revenue-yr.revenue)/yr.revenue*100:null);
      return {...r,mom,yoy,price:priceAt(r.revenue_year,r.revenue_month)};
    });
    const amtVals=REV_ROWS.map(r=>r.revenue/1e8);const amtMax=Math.max(...amtVals)||1;
    amtEl.innerHTML=REV_ROWS.map((r,i)=>`<div class="rc-bar" data-i="${i}"><i style="height:${Math.max(6,r.revenue/1e8/amtMax*100).toFixed(0)}%"></i></div>`).join('');
    const yoyVals=REV_ROWS.map(r=>r.yoy).filter(v=>v!=null);
    const yoyAbsMax=Math.max(...yoyVals.map(Math.abs),1)||1;
    yoyEl.innerHTML='<div class="rc-zero"></div>'+REV_ROWS.map((r,i)=>{
      if(r.yoy==null)return `<div class="rc-bar" data-i="${i}"></div>`;
      const h=Math.min(50,Math.abs(r.yoy)/yoyAbsMax*50);
      return `<div class="rc-bar" data-i="${i}"><i class="${r.yoy>=0?'up':'dn'}" style="height:${h.toFixed(0)}%"></i></div>`;
    }).join('');
    lblEl.innerHTML=REV_ROWS.map(r=>`<span>${r.revenue_month}月</span>`).join('');
    const rl=REV_ROWS[REV_ROWS.length-1];
    const ye=document.getElementById('kn-yoy');ye.textContent=rl.yoy!=null?(rl.yoy>=0?'+':'')+rl.yoy.toFixed(1)+'%':'—';ye.className=rl.yoy>=0?'pos':'neg';
    document.getElementById('rev-note').innerHTML=`${rl.revenue_year}/${rl.revenue_month} 月營收 ${nf(Math.round(rl.revenue/1e8))} 億${rl.yoy!=null?` · YoY <b class="${rl.yoy>=0?'pos':'neg'}">${rl.yoy>=0?'+':''}${rl.yoy.toFixed(1)}%</b>`:''} · research快照`;
  }

  // 2026-09-15（P0產品.二）個股頁「選股理由」卡：獨立於選股頁的hydratePicks流程，
  // 讓使用者從自選股/搜尋直接進個股頁也看得到（不必先去逛過選股頁才會有cache）。
  // 只讀scores.json（價值成長榜，六因子這輪擴充成八因子的既有資料），不打任何新端點。
  async function ensureValueScores(){
    if(PICKS_CACHE)return PICKS_CACHE;
    try{
      const res=await fetch('scores.json?_='+Date.now());
      if(!res.ok)throw new Error('HTTP '+res.status);
      PICKS_CACHE=await res.json();
    }catch(e){console.warn('[ensureValueScores]',e);recordGlobalError('ensureValueScores',e)}
    return PICKS_CACHE;
  }
  async function renderStockReasonCard(code){
    const host=document.getElementById('stock-reason-card');if(!host)return;
    if(isUS(code)){host.innerHTML='<div class="note">美股暫無選股理由（因子評分目前僅涵蓋台股，見 scores.json meta.market:"TW"）</div>';return}
    host.innerHTML=skeletonHtml(4);  // 2026-09-15 P0產品.四：骨架屏
    const cache=await ensureValueScores();
    if(currentCode!==code)return;  // await期間已切到別檔，作廢（同renderReport的世代守衛精神，避免A檔理由畫到B檔頁面）
    if(!cache){host.innerHTML='<div class="note">尚未產生 scores.json，或載入失敗。此清單由 research/generate_scores_v2.py 在本機/排程產生後 commit 進 repo，不是即時計算。</div>';return}
    const row=(cache.stocks||[]).find(r=>r.code===code);
    if(!row){host.innerHTML='<div class="note">這檔不在選股評分樣本內（可能資料完整度不足或流動性不足未進榜，樣本涵蓋 '+(cache.stocks||[]).length+' 檔，非全市場逐檔掃描）。</div>';return}
    const boardCfg=BOARD_CONFIG.value;
    const weights=cache.weights||{};
    const allRows=cache.stocks||[];
    host.innerHTML=`<div class="note" style="margin-bottom:6px">${buildReasonSummary(row,boardCfg)}</div>`
      +boardCfg.factorOrder.map(k=>factorContribRowHtml(k,row,boardCfg.factorLabels,weights,allRows)).join('');
  }

  async function openStock(code){
    if(typeof code!=='string')code=currentCode;
    currentCode=code;
    const us=isUS(code);
    go('stock');
    document.querySelectorAll('#stock-tabs button').forEach((x,i)=>x.classList.toggle('on',i===0));
    // 先.七十二-B7：總覽＝ov＋tech＋ai 三個既有子頁（只動個股頁的子頁，不再誤清交易頁的子頁狀態）
    const ovSubs=((document.querySelector('#stock-tabs button')||{}).dataset||{}).subs||'ov';
    document.querySelectorAll('#scr-stock .subscreen').forEach(s=>s.classList.toggle('active',ovSubs.split(',').includes(s.id.replace(/^sub-/,''))));
    if(ovSubs.split(',').includes('tech'))setTimeout(()=>_safeAsync('renderTechChartTab',()=>renderTechChartTab(code)),0);
    try{renderBuyCta(code)}catch(e){console.warn('[renderBuyCta]',e);recordGlobalError('renderBuyCta',e)}
    setTxt('sh-name',nameOf(code));setTxt('sh-sub',code+(us?' · 美股':' · 台股'));setTxt('sh-price','…');setTxt('sh-chg','載入中');updateStockSimTag(code);_safeAsync('updateStockDisposalTag',()=>updateStockDisposalTag(code));
    ['kn-per','kn-yield','kn-yoy','kn-pbr','chip-foreign','chip-trust','chip-dealer','chip-total'].forEach(id=>setTxt(id,'…'));
    document.getElementById('rev-chart-amt').innerHTML=skeletonBlockHtml(120);
    document.getElementById('rev-chart-yoy').innerHTML='';document.getElementById('rev-chart-labels').innerHTML='';
    document.getElementById('trend-chart').innerHTML=skeletonBlockHtml(220);  // 2026-09-15 P0產品.四：骨架屏取代純文字「載入中」，形狀貼近圖表區塊
    document.getElementById('stock-reason-card').innerHTML=skeletonHtml(4);  // 2026-09-15 P0產品.二/四，避免殘留上一檔的選股理由
    if(us){
      const [px]=await Promise.all([fm('USStockPrice',code,_d(35)),ensureIbkrQuotes()]);
      if(currentCode!==code)return;  // 2026-09-06：await 期間已切到別檔，作廢
      // 2026-09-03新增（P0全App現價掃描）：個股頁頭部價格原本完全略過
      // IBKR即時/收盤報價，一律顯示FinMind日線最後一筆——現在改成跟
      // 首頁自選股/市場頁同一套「先試intradayQuote()、查不到才退回FinMind」
      // 規則，個股頁看到的現價才會跟其他分頁一致。
      const iq=intradayQuote(code,true);
      if(iq&&iq.price!=null){
        const cls=(iq.change||0)>=0?'pos':'neg';
        const pe=document.getElementById('sh-price');pe.textContent='$'+nf(iq.price);pe.className=cls;
        const ce=document.getElementById('sh-chg');ce.textContent=`${(iq.change||0)>=0?'+':''}${(+(iq.change||0)).toFixed(2)}（${(iq.change_pct||0)>=0?'+':''}${(iq.change_pct||0).toFixed(2)}%）`;ce.className=cls;
        if(px.length)renderStockChart(code,px,true);
        setTxt('trend-note',`來源：IBKR${intradayTagText(iq)}`);  // 2026-09-08 實測.七
      }else if(px.length){const last=px[px.length-1];const prev=px.length>1?px[px.length-2].Close:last.Close;
        const chg=last.Close-prev;const pct=prev?chg/prev*100:0;const cls=chg>=0?'pos':'neg';
        const pe=document.getElementById('sh-price');pe.textContent='$'+nf(last.Close);pe.className=cls;
        const ce=document.getElementById('sh-chg');ce.textContent=`${chg>=0?'+':''}${(+chg).toFixed(2)}（${pct>=0?'+':''}${pct.toFixed(2)}%）`;ce.className=cls;
        renderStockChart(code,px,true);
        setTxt('trend-note',`來源：FinMind USStockPrice · 近 ${px.length} 個交易日收盤（日線收盤，非當下報價）`);
      }else{setTxt('sh-price','—');setTxt('sh-chg',fmEmptyMsg('查無此代號'));document.getElementById('trend-chart').innerHTML='<div class="note">'+fmEmptyMsg('查無資料')+'</div>'}
      ['kn-per','kn-pbr','kn-yield','kn-yoy','kn-turnover','kn-vol-mult'].forEach(id=>setTxt(id,'—'));
      setTxt('kn-liquidity-flag','');
      REV_ROWS=[];
      document.getElementById('rev-chart-amt').innerHTML='<div class="note">美股尚未支援月營收（FinMind 此指標僅提供台股）</div>';
      document.getElementById('rev-note').textContent='美股暫無此資料';
      ['chip-foreign','chip-trust','chip-dealer','chip-total'].forEach(id=>setTxt(id,'—'));
      setTxt('chip-note','美股暫無三大法人資料（僅適用台股）');
      document.getElementById('chip-bars').innerHTML='<div class="note">美股暫無此資料</div>';
      _safeSync('renderChipTrend',()=>renderChipTrend(code,null,[]));
      _safeAsync('renderChipBadges',()=>renderChipBadges(code));  // 2026-09-08 金流一.3
      ['mg-balance','mg-balance-chg','mg-short','mg-ratio'].forEach(id=>setTxt(id,'—'));
      setTxt('mg-short-ratio','券資比：—');setTxt('mg-note','美股暫無融資融券資料（僅適用台股）');setTxt('mg-maint','估算融資維持率：—');
      document.getElementById('eps-bars').innerHTML=skeletonHtml(3);  // 2026-09-15 P0產品.四：骨架屏
      setTxt('fh-ratio','—');setTxt('fh-can-invest','—');
      setTxt('fh-note','美股無此資料（僅適用台股，外資持股比率為TWSE官方統計）');
      setTxt('sbl-available','—');
      setTxt('sbl-note','美股無此資料（僅適用台股，可借券賣出股數為TWSE官方統計）');
      setTxt('tdcc-big-ratio','—');setTxt('tdcc-small-ratio','—');setTxt('tdcc-week-chg','—');setTxt('tdcc-streak','—');
      setTxt('tdcc-note','美股無此資料（僅適用台股，千張大戶為集保結算所官方統計）');
      setTxt('sbl-sell-volume','—');setTxt('sbl-sell-return','—');
      setTxt('sbl-sell-note','美股無此資料（僅適用台股，借券賣出成交量為TWSE/TPEx官方統計）');
      _safeAsync('loadInsiderTradingChip',()=>loadInsiderTradingChip(code));
      _safeAsync('loadUs13fChip',()=>loadUs13fChip(code));
      _safeAsync('loadUs8kChip',()=>loadUs8kChip(code));
      loadFinancialsUS(code);
      _safeAsync('renderStockReasonCard',()=>renderStockReasonCard(code));  // 2026-09-15 P0產品.二
      _safeAsync('renderStockBrief',()=>renderStockBrief(code));  // 常備.開發-13
      _safeAsync('renderAnalystRadar',()=>renderAnalystRadar(code));  // 常備.開發-15
      _safeAsync('renderRevenueRead',()=>renderRevenueRead(code));  // 常備.開發-14
      return;
    }
    setTxt('eps-bars-title','季度獲利（EPS · 元）');
    setTxt('fin-roe-lbl','ROE（近四季）');
    setTxt('fin-fcf-lbl','自由現金流（最新季）');
    document.getElementById('eps-bars').innerHTML=skeletonHtml(3);  // 2026-09-15 P0產品.四：骨架屏
    // 2026-08-27 架構修正：PER/PBR/殖利率、月營收改讀 data/fundamentals.json
    // （見 build_fundamentals_json.py），不再對 FinMind 打 TaiwanStockPER／
    // TaiwanStockMonthRevenue——這兩個資料集目前沒有排程自動更新（TWSE官方開放
    // 資料只有最新快照、無歷史區間查詢，見該腳本docstring揭露），是研究端既有
    // 快取整理出的快照。價格走勢/融資/三大法人這幾塊這輪還沒有替換掉FinMind，
    // 維持原樣（會誠實顯示連線失敗，不是假資料）。
    // 2026-09-06（實測.一）個股頁也走同一條回退鏈：先把後面幾層要用的檔案備妥，
    // FinMind 抓不到（額度用盡/冷門股）時才有東西可退。
    // 常備.開發-20（先.六十七）：只抓這一檔的小檔（data/quote_lite），不再為一檔下載整份 sparklines／quotes_all_tw
    await Promise.allSettled([ensureQuoteLite([code]),ensureListedUniverse()]);
    if(currentCode!==code)return;
    const [px,fund,inst]=await Promise.all([
      fm('TaiwanStockPrice',code,_d(35)),loadFundamentals(code),instNet(code),ensureSinopacQuotes()]);
    if(currentCode!==code)return;  // 2026-09-06：await 期間已切到別檔，作廢（見 canonicalPrice 註解）
    const per=fund.ratios?[fund.ratios]:[];
    const rev=fund.month_revenue?fund.month_revenue.map(r=>({revenue_year:r.year,revenue_month:r.month,revenue:r.revenue,yoyPre:r.yoy!=null?r.yoy*100:null})):[];
    loadFinancials(code);
    // 2026-09-03新增（P0全App現價掃描）：個股頁頭部價格原本完全略過Shioaji
    // 即時/收盤報價，一律顯示FinMind日線最後一筆——現在改成跟首頁自選股/
    // 市場頁同一套「先試intradayQuote()、查不到才退回FinMind」規則（沒在
    // Shioaji既有5檔預設清單裡的股票會自然查不到，正常退回FinMind，不是bug）。
    const iq=intradayQuote(code,false);
    if(iq&&iq.price!=null){
      const cls=(iq.change||0)>=0?'pos':'neg';
      const pe=document.getElementById('sh-price');pe.textContent=nf(iq.price);pe.className=cls;
      _safeSync('applyLimitBadge',()=>applyLimitBadge(code,iq.price,iq.prev_close,iq));
      const ce=document.getElementById('sh-chg');ce.textContent=`${(iq.change||0)>=0?'+':''}${(+(iq.change||0)).toFixed(1)}（${(iq.change_pct||0)>=0?'+':''}${(iq.change_pct||0).toFixed(2)}%）`;ce.className=cls;
      if(px.length)renderStockChart(code,px,false);
      setTxt('trend-note',`來源：Shioaji${intradayTagText(iq)}`);  // 2026-09-08 實測.七
    }else if(px.length){const last=px[px.length-1];const prev=px.length>1?px[px.length-2].close:last.close-last.spread;
      const chg=last.spread!=null?last.spread:last.close-prev;const pct=prev?chg/prev*100:0;const cls=chg>=0?'pos':'neg';
      const pe=document.getElementById('sh-price');pe.textContent=nf(last.close);pe.className=cls;
      const ce=document.getElementById('sh-chg');ce.textContent=`${chg>=0?'+':''}${(+chg).toFixed(1)}（${pct>=0?'+':''}${pct.toFixed(2)}%）`;ce.className=cls;
      renderStockChart(code,px,false);
      // 2026-09-06（實測.三）沒有即時源時也要判漲跌停，用日線的前一筆收盤當前收
      _safeSync('applyLimitBadge:daily',()=>applyLimitBadge(code,last.close,prev,null));
      setTxt('trend-note',`來源：FinMind TaiwanStockPrice · 近 ${px.length} 個交易日收盤（日線收盤，非當下報價，原始未還原股價）`);
    }else{
      // 2026-09-06（實測.一）FinMind 沒有（冷門股或額度用盡）時退回統一回退鏈的後兩層：
      // quotes_all_tw（全市場收盤）→ sparklines（歷史最後收盤）。原本這裡直接寫死
      // 「查無此代號」，但那些股票其實我們手上就有價格，只是沒去拿。
      const fb=resolveQuote(code,false);
      if(fb&&fb.price!=null){
        const chg=fb.change??0,pct=fb.change_pct??0,cls=chg>=0?'pos':'neg';
        const pe=document.getElementById('sh-price');
        // 2026-09-17（稽核.四.1修正版(a)）：fb.is_stale=true代表as_of落後大盤當日
        // 最大日期，不得標「現價」——價格數字本身直接帶真實日期，漲跌%不顯示
        // （那是拿舊日期算出來的，顯示出來會誤導成「今天的漲跌」）。
        pe.textContent=fb.is_stale?`${fb.asof?String(fb.asof).slice(5).replace('-','/'):'?'}收盤 ${nf(fb.price)}`:nf(fb.price);
        pe.className=cls;
        const ce=document.getElementById('sh-chg');
        ce.textContent=fb.is_stale?'':`${chg>=0?'+':''}${(+chg).toFixed(1)}（${pct>=0?'+':''}${pct.toFixed(2)}%）`;
        ce.className=cls;
        _safeSync('applyLimitBadge:fallback',()=>applyLimitBadge(code,fb.price,fb.prev_close,null));
        const sp=fb.sparkline||sparkFor(code);
        if(sp&&sp.length>=2)renderStockChart(code,sp.map(c=>({close:c})),false);
        setTxt('trend-note',`來源：${QUOTE_TIER_LABEL[fb.tier]||fb.tier}${fb.asof?'（'+fb.asof+'）':''}${fb.is_stale?'　⚠ 落後大盤當日最新日期，非現價':''}　FinMind 本次無資料`);
      }else{
        setTxt('sh-price','—');setTxt('sh-chg',noQuoteLabel(code,false));
        document.getElementById('trend-chart').innerHTML='<div class="note">'+noQuoteLabel(code,false)+'</div>';
      }
    }
    loadMarginChip(code,px);
    _safeAsync('renderStockReasonCard',()=>renderStockReasonCard(code));  // 2026-09-15 P0產品.二
      _safeAsync('renderStockBrief',()=>renderStockBrief(code));  // 常備.開發-13
      _safeAsync('renderAnalystRadar',()=>renderAnalystRadar(code));  // 常備.開發-15
    _safeAsync('renderRevenueRead',()=>renderRevenueRead(code));  // 常備.開發-14
    _safeAsync('loadForeignHoldingChip',()=>loadForeignHoldingChip(code));  // 2026-09-15 源頭二.3第1名
    setInsiderTradingNA('台股無此資料（僅適用美股，內部人交易為SEC Form 4申報）');  // 2026-09-15 源頭二.3第2名
    setUs13fNA('台股無此資料（僅適用美股，機構持倉為SEC Form 13F申報）');  // 2026-09-15 源頭二.3第6名
    setUs8kNA('台股無此資料（僅適用美股，重大訊息請看「題材判斷」卡的MOPS重大訊息）');  // 2026-09-15 PENDING_QUEUE「三」美股半邊
    _safeAsync('loadShortLendingChip',()=>loadShortLendingChip(code));  // 2026-09-15 源頭二.3第5名
    _safeAsync('loadTdccHoldersChip',()=>loadTdccHoldersChip(code));  // 2026-09-15 源頭一.3
    _safeAsync('loadSblSellChip',()=>loadSblSellChip(code));  // 2026-09-15 源頭一.3
    if(px.length){
      // 量能突破倍數：相對自身20日均量的動能訊號（可以＜1，只是「比平常冷」，不等於「不流動」）。
      // 流動性門檻是完全獨立的另一件事：不管跟自己比是熱是冷，成交值絕對數字太低（單日<3000萬）
      // 就是真的量能不足，這種股票不管技術面多漂亮都拉不動——兩個訊號分開判斷，不能混用同一個
      // 相對倍數當作流動性門檻（那樣的話，像台積電這種天量常態股，只要今天比自己前20日均量
      // 略低，就會被誤判成「量能不足」，但它其實還是全市場數一數二流動的股票）。
      const LIQUIDITY_FLOOR=30000000; // NT$3000萬/日，絕對門檻，不是相對值
      const moneys=px.map(x=>x.Trading_money||0);
      const todayMoney=moneys[moneys.length-1];
      const avg20=moneys.slice(-20).reduce((a,b)=>a+b,0)/Math.min(20,moneys.length);
      const mult=avg20>0?todayMoney/avg20:null;
      setTxt('kn-turnover',nf(Math.round(todayMoney/1e4))+' 萬');
      const me=document.getElementById('kn-vol-mult');
      if(mult!=null){me.textContent=mult.toFixed(2)+' 倍';me.className=mult>=1.3?'pos':(mult<0.7?'neg':'')}
      const flagEl=document.getElementById('kn-liquidity-flag');
      flagEl.textContent=todayMoney<LIQUIDITY_FLOOR?'⚠ 量能不足，漲不動（今日成交值低於3000萬元流動性門檻）':'';
    }else{setTxt('kn-turnover','—');setTxt('kn-vol-mult','—');setTxt('kn-liquidity-flag','')}
    const p=per.length?per[per.length-1]:{};
    setTxt('kn-per',p.per??'—');setTxt('kn-pbr',p.pbr??'—');setTxt('kn-yield',p.dividend_yield!=null?p.dividend_yield+'%':'—');
    loadRevenueChart(code,rev);
    if(inst){
      setChipLots('chip-foreign',inst.foreign);setChipLots('chip-trust',inst.trust);setChipLots('chip-dealer',inst.dealer);setChipLots('chip-total',inst.total);
      setTxt('chip-note',`最新 ${inst.date} · TWSE T86（GitHub Actions 排程）`);
      const mx=Math.max(...inst.series.map(s=>Math.abs(s.v)))||1;
      document.getElementById('chip-bars').innerHTML=inst.series.map(s=>divBarHTML(s.date.slice(5),s.v,mx)).join('');
      _safeSync('renderChipTrend',()=>renderChipTrend(code,inst,px));
      _safeAsync('renderChipBadges',()=>renderChipBadges(code));  // 2026-09-08 金流一.3
    }else{['chip-foreign','chip-trust','chip-dealer','chip-total'].forEach(id=>setTxt(id,'—'));
      _safeSync('renderChipTrend',()=>renderChipTrend(code,null,px));
      document.getElementById('chip-bars').innerHTML='<div class="note">查無法人資料（僅涵蓋TWSE上市「一般業」，上櫃/金融股暫無）</div>';
      setTxt('chip-note','查無資料（僅涵蓋TWSE上市「一般業」，上櫃/金融股暫無）');
    }
  }

  // ── 個股子頁 ──
  document.querySelectorAll('#stock-tabs button').forEach(b=>{
    b.addEventListener('click',()=>{
      document.querySelectorAll('#stock-tabs button').forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
      // 先.七十二-B7：一個分頁可顯示多個既有子頁（data-subs）
      const subs=(b.dataset.subs||b.dataset.sub).split(',');
      document.querySelectorAll('#scr-stock .subscreen').forEach(s=>s.classList.toggle('active',subs.includes(s.id.replace(/^sub-/,''))));
      // 2026-09-15（P0產品.三）事件/技術型態兩個分頁改成點到才載入：事件分頁隱藏時
      // 容器是display:none，技術型態分頁的lightweight-charts在寬度0的容器建圖表會
      // 尺寸算錯，兩者都不適合跟其他分頁一樣在openStock()就直接畫。
      if(subs.includes('events'))_safeAsync('renderStockEventsTab',()=>renderStockEventsTab(currentCode));
      if(subs.includes('tech'))_safeAsync('renderTechChartTab',()=>renderTechChartTab(currentCode));
    });
  });

  // ── 個股頁底部列（先.六十-A1，2026-10-10）──
  // 台股：唯讀說明（真錢只由本機 Bb-90 引擎執行，App 不提供手動下單）；
  // 美股：既有 IBKR 模擬（Paper）帳戶下單卡（research/ibkr_order_server.py）。
  function renderBuyCta(code){
    const us=isUS(code);
    const tw=document.getElementById('buy-cta-tw');if(tw)tw.style.display=us?'none':'';
    ['buy-cta-us-sell','buy-cta-us-buy'].forEach(id=>{const b=document.getElementById(id);if(b)b.style.display=us?'':'none'});
  }
  async function checkIbkrHealthAndAccount(){
    const he=document.getElementById('ibkr-health');
    he.textContent='檢查中…';he.className='';
    try{
      const r=await fetch(IBKR_ORDER_SERVER+'/health');
      const j=await r.json();
      if(j.ok){IBKR_STATE.connected=true;he.textContent='已連線 · Paper帳戶 '+j.account_id;he.className='pos'}
      else{IBKR_STATE.connected=false;he.textContent='連線失敗：'+(j.error||'未知錯誤');he.className='neg'}
    }catch(e){
      IBKR_STATE.connected=false;
      he.textContent='連不到本機下單伺服器（未啟動？）— 請先在本機另開終端機執行 python research/ibkr_order_server.py';
      he.className='neg';
      console.warn('[checkIbkrHealthAndAccount:health]',e);
    }
    try{
      const r=await fetch(IBKR_ORDER_SERVER+'/account_summary?symbol='+encodeURIComponent(currentCode));
      if(r.ok){
        const j=await r.json();
        setTxt('ibkr-position',(j.position_qty||0)+' 股');
        const bp=j.summary&&j.summary.BuyingPower;
        setTxt('ibkr-buying-power',bp!=null?'$'+nf(Math.round(+bp)):'—');
      }else{setTxt('ibkr-position','—');setTxt('ibkr-buying-power','—')}
    }catch(e){
      setTxt('ibkr-position','—');setTxt('ibkr-buying-power','—');
      console.warn('[checkIbkrHealthAndAccount:account_summary]',e);
    }
  }
  function openIbkrSheet(side){
    setTxt('ibkr-symbol',currentCode);
    setIbkrSide(side==='sell'?'SELL':'BUY');
    setIbkrOrderType('MKT');
    document.getElementById('ibkr-qty').value=1;
    document.getElementById('ibkr-limit-price').value='';
    document.getElementById('ibkr-token').value=readIbkrToken();
    document.getElementById('ibkr-result').textContent='';
    document.getElementById('ibkr-mask').classList.add('open');
    document.getElementById('ibkr-sheet').classList.add('open');
    checkIbkrHealthAndAccount().catch(e=>{console.warn('[openIbkrSheet]',e);recordGlobalError('openIbkrSheet',e)});
  }

  // ══════ 2026-09-03深夜（乙.5）個股頁走勢圖：TradingView lightweight-charts ══════
  // 日線=既有FinMind資料（沿用）；1分K=本機/live/kbars（shioaji_quotes.py用tick聚合，非api.kbars），
  // 串流每個事件帶kbars_last→series.update()。函式庫載不到（離線/CDN故障）→退回既有SVG折線。
  const STOCK_CHART={chart:null,series:null,mode:'daily',userPickedMode:false,code:null,us:false,daily:[],intraday:[],dailyNote:'',rawRows:[]};
  function _cssVar(n,fb){try{return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||fb}catch(e){return fb}}
  function lwcAvailable(){return typeof window.LightweightCharts!=='undefined'&&typeof window.LightweightCharts.createChart==='function'&&!!window.LightweightCharts.CandlestickSeries}
  // 常備.開發-20（2026-10-11）：函式庫（gzip 約 64KB）原本寫在 <head> 首頁一開就下載，
  // 改成第一次要畫K線時才載入；載入完成前先畫既有SVG折線，載好後由呼叫端重畫一次。
  // 載入失敗（離線/CDN故障）就維持SVG折線，跟以前「函式庫載不到」的退回行為相同。
  const LWC_SRC='https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.js';
  let LWC_LOADING=null;
  function ensureLwc(){
    if(lwcAvailable())return Promise.resolve(true);
    if(!LWC_LOADING){
      LWC_LOADING=new Promise(res=>{
        const sc=document.createElement('script');sc.src=LWC_SRC;sc.async=true;
        sc.onload=()=>res(lwcAvailable());
        sc.onerror=e=>{console.warn('[ensureLwc] 圖表函式庫載入失敗，維持SVG折線',e);res(false)};
        document.head.appendChild(sc);
      }).then(ok=>{if(!ok)LWC_LOADING=null;return ok});
    }
    return LWC_LOADING;
  }
  function _destroyStockChart(){if(STOCK_CHART.chart){try{STOCK_CHART.chart.remove()}catch(e){console.warn('[destroyStockChart]',e)}}STOCK_CHART.chart=null;STOCK_CHART.series=null;STOCK_CHART.costLine=null}
  // lightweight-charts的時間軸一律以UTC顯示，這裡把台北時間加8小時偏移，讓刻度顯示台北時間（常見做法）。
  function _minuteBarToLwc(b){return {time:Math.floor(new Date(b.t+':00+08:00').getTime()/1000)+8*3600,open:b.o,high:b.h,low:b.l,close:b.c}}
  function renderStockChart(code,rows,us){
    const el=document.getElementById('trend-chart');if(!el)return;
    if(STOCK_CHART.code!==code){STOCK_CHART.userPickedMode=false;STOCK_CHART.mode='daily'}
    STOCK_CHART.code=code;STOCK_CHART.us=us;
    STOCK_CHART.rawRows=rows||[];  // 2026-09-15 P0產品.三：保留原始列（含成交量），技術型態分頁疊加成交量長條要用，不用再多打一次fm()
    STOCK_CHART.daily=(rows||[]).map(r=>us?{time:r.date,open:r.Open,high:r.High,low:r.Low,close:r.Close}:{time:r.date,open:r.open,high:r.max,low:r.min,close:r.close})
      .filter(x=>x.time&&x.close!=null&&x.open!=null&&x.high!=null&&x.low!=null);
    // 2026-09-06（實測.二.2）判定改成「查得到當日1分K」而不是「串流有推過這一檔」。
    // 總司令要求當日曲線當預設、20日日線降為第二個切換選項；未訂閱的代號現在也
    // 查得到 api.kbars()，只看 kbarsLast 會讓它們永遠停在日線。
    const hasIntraday=!us&&((LIVE_KB[code]&&LIVE_KB[code].closes&&LIVE_KB[code].closes.length>=2)||(LIVE.connected&&!!LIVE.kbarsLast[code]));
    if(hasIntraday&&!STOCK_CHART.userPickedMode)STOCK_CHART.mode='intraday';
    if(!hasIntraday)STOCK_CHART.mode='daily';
    renderTrendModeToggle(hasIntraday);
    setTimeout(()=>{const n=document.getElementById('trend-note');if(n&&n.textContent&&!/^1分K/.test(n.textContent))STOCK_CHART.dailyNote=n.textContent},0); // 記住日線來源說明，切回日線時還原（loadIntradayBars是非同步的，這個timeout(0)一定跑在它覆寫之前）
    if(!lwcAvailable()){
      _destroyStockChart();el.style.height='';
      const closes=STOCK_CHART.daily.map(x=>x.close);
      const lwcP=ensureLwc();
      el.innerHTML=trendChart(closes,v=>(us?'$':'')+nf(v))+'<div class="note" style="font-size:10px">圖表函式庫（lightweight-charts）'+(LWC_LOADING?'載入中':'未載入')+'，顯示簡易折線</div>';
      lwcP.then(ok=>{if(ok&&STOCK_CHART.code===code&&document.getElementById('trend-chart')===el)renderStockChart(code,rows,us)})
        .catch(e=>{console.warn('[renderStockChart:ensureLwc]',e);recordGlobalError('renderStockChart:ensureLwc',e)});
      return;
    }
    _destroyStockChart();el.innerHTML='';el.style.height='220px';
    const LWC=window.LightweightCharts;
    const chart=LWC.createChart(el,{width:el.clientWidth||320,height:220,
      layout:{background:{type:'solid',color:'transparent'},textColor:_cssVar('--ink-3','#9aa0a6')},
      grid:{vertLines:{color:'rgba(128,128,128,.12)'},horzLines:{color:'rgba(128,128,128,.12)'}},
      rightPriceScale:{borderVisible:false},
      timeScale:{borderVisible:false,timeVisible:STOCK_CHART.mode==='intraday',secondsVisible:false},
      handleScroll:{vertTouchDrag:false}});
    const up=_cssVar('--up','#ff5257'),down=_cssVar('--down','#24c98a');
    const series=chart.addSeries(LWC.CandlestickSeries,{upColor:up,downColor:down,borderVisible:false,wickUpColor:up,wickDownColor:down});
    STOCK_CHART.chart=chart;STOCK_CHART.series=series;
    // 2026-09-06（實測.三.2）盤中 K 線畫兩條漲跌停虛線。
    // 這是 K 線圖上最有用的一條參考線：看得到今天離鎖住還有多遠，比只看一個數字直觀。
    // 只在算得出來時畫（TSE/OTC 4 位數普通股或有合約值），ETF 與興櫃不畫，
    // 理由見 limitPrices() 的說明——寧可不畫也不要畫一條錯的線。
    _safeSync('renderStockChart:limitLines',()=>{
      const prev=(STOCK_CHART.daily.length>1)?STOCK_CHART.daily[STOCK_CHART.daily.length-2].close:null;
      const lim=limitPrices(code,prev,intradayQuote(code,us));
      if(!lim)return;
      const style=(LWC.LineStyle&&LWC.LineStyle.Dashed!=null)?LWC.LineStyle.Dashed:2;
      series.createPriceLine({price:lim.up,color:getComputedStyle(document.documentElement).getPropertyValue('--up').trim()||'#e6383f',
        lineWidth:1,lineStyle:style,axisLabelVisible:true,title:'漲停 '+lim.up});
      series.createPriceLine({price:lim.down,color:getComputedStyle(document.documentElement).getPropertyValue('--down').trim()||'#1aa34a',
        lineWidth:1,lineStyle:style,axisLabelVisible:true,title:'跌停 '+lim.down});
    });
    if(STOCK_CHART.mode==='intraday'){loadIntradayBars(code)}
    else{series.setData(STOCK_CHART.daily);chart.timeScale().fitContent()}
  }
  async function loadIntradayBars(code){
    try{
      const r=await liveFetch('/live/kbars?code='+encodeURIComponent(code),5000);
      // 常備.開發-10（2026-10-11）：美股伺服器刻意回 501（IBKR 連線衝突未確認，伺服器不改），App 改顯示誠實說明，不當成錯誤
      if(r.status===501){const e=new Error('美股 1 分 K 尚未提供（IBKR 連線衝突未確認），請看日線');e.honest501=true;throw e}
      if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||('HTTP '+r.status))}
      const d=await r.json();
      STOCK_CHART.intraday=(d.bars||[]).map(_minuteBarToLwc);
      if(STOCK_CHART.series&&STOCK_CHART.code===code&&STOCK_CHART.mode==='intraday'){
        STOCK_CHART.chart.applyOptions({timeScale:{timeVisible:true}});
        STOCK_CHART.series.setData(STOCK_CHART.intraday);STOCK_CHART.chart.timeScale().fitContent();
      }
      setTxt('trend-note',`1分K：本機 Shioaji tick 聚合（${d.mode}，${(d.bars||[]).length} 根，${d.hot_file_status==='hot-file'?'即時更新中':'非即時：常駐行程未在跑或已收盤'}）`);
    }catch(e){
      if(!e.honest501){console.warn('[loadIntradayBars]',e);recordGlobalError('loadIntradayBars',e)}  // 501 是已知的設計狀態，不記成錯誤
      STOCK_CHART.mode='daily';STOCK_CHART.userPickedMode=false;
      if(STOCK_CHART.series){STOCK_CHART.chart.applyOptions({timeScale:{timeVisible:false}});STOCK_CHART.series.setData(STOCK_CHART.daily);STOCK_CHART.chart.timeScale().fitContent()}
      renderTrendModeToggle(false);
      setTxt('trend-note',e.honest501?e.message:'1分K取得失敗（'+(e.message||e)+'），改顯示日線');
    }
  }
  function renderTrendModeToggle(hasIntraday){
    const el=document.getElementById('trend-mode-toggle');if(!el)return;
    if(!hasIntraday){el.innerHTML='';return}
    el.innerHTML=[['daily','日線'],['intraday','1分K(即時)']].map(([k,l])=>`<span class="press mtg-opt${STOCK_CHART.mode===k?' on':''}" onclick="setTrendMode('${k}')">${l}</span>`).join('');
  }
  function setTrendMode(k){
    STOCK_CHART.mode=k;STOCK_CHART.userPickedMode=true;
    if(k==='intraday'){loadIntradayBars(STOCK_CHART.code)}
    else if(STOCK_CHART.series){STOCK_CHART.chart.applyOptions({timeScale:{timeVisible:false}});STOCK_CHART.series.setData(STOCK_CHART.daily);STOCK_CHART.chart.timeScale().fitContent();setTxt('trend-note',STOCK_CHART.dailyNote||'')}
    renderTrendModeToggle(true);
  }
  // ══════ 2026-09-15（P0產品.三）技術型態分頁：MA/成交量開關疊加 ══════
  // 刻意不做型態辨識（頭肩頂/三角收斂等，留待P2）——這裡只是「把既有價量資料換一種
  // 描述方式呈現」，不新增資料源，也不暗示任何買賣訊號。價量資料沿用「總覽」分頁
  // renderStockChart()已經抓好的STOCK_CHART.rawRows/daily，不再多打一次fm()。
  const TECH_MA_PERIODS=[5,10,20,60];
  const TECH_MA_COLOR={5:'#e9c98f',10:'#7aa2f7',20:'#bb9af7',60:'#9ece6a'};
  let TECH_TOGGLES={ma5:true,ma10:true,ma20:false,ma60:false,vol:true};
  const TECH_CHART={chart:null,candleSeries:null,volSeries:null,maSeries:{},code:null,closes:[],dates:[],volumes:[]};
  function destroyTechChart(){
    if(TECH_CHART.chart){try{TECH_CHART.chart.remove()}catch(e){console.warn('[destroyTechChart]',e)}}
    TECH_CHART.chart=null;TECH_CHART.candleSeries=null;TECH_CHART.volSeries=null;TECH_CHART.maSeries={};TECH_CHART.code=null;
  }
  // 簡單移動平均，period-1筆之前沒有值（不外插、不用較短窗口湊數，缺就是缺）。
  function smaSeries(closes,dates,period){
    const out=[];
    for(let i=period-1;i<closes.length;i++){
      let sum=0;for(let j=i-period+1;j<=i;j++)sum+=closes[j];
      out.push({time:dates[i],value:sum/period});
    }
    return out;
  }
  function renderTechChips(){
    const el=document.getElementById('tech-toggle-chips');if(!el)return;
    const mk=(key,label)=>chip(label,!!TECH_TOGGLES[key],`toggleTechIndicator('${key}')`);
    el.innerHTML=[mk('ma5','MA5'),mk('ma10','MA10'),mk('ma20','MA20'),mk('ma60','MA60'),mk('vol','成交量')].join('');
  }
  function toggleTechIndicator(key){
    TECH_TOGGLES[key]=!TECH_TOGGLES[key];
    renderTechChips();
    _safeSync('applyTechIndicators',applyTechIndicators);
  }
  function applyTechIndicators(){
    if(!TECH_CHART.chart)return;
    const LWC=window.LightweightCharts;
    TECH_MA_PERIODS.forEach(p=>{
      const key='ma'+p;
      const want=TECH_TOGGLES[key];
      if(want&&!TECH_CHART.maSeries[key]){
        TECH_CHART.maSeries[key]=TECH_CHART.chart.addSeries(LWC.LineSeries,{color:TECH_MA_COLOR[p],lineWidth:1.5,priceLineVisible:false,lastValueVisible:false});
        TECH_CHART.maSeries[key].setData(smaSeries(TECH_CHART.closes,TECH_CHART.dates,p));
      }else if(!want&&TECH_CHART.maSeries[key]){
        try{TECH_CHART.chart.removeSeries(TECH_CHART.maSeries[key])}catch(e){console.warn('[applyTechIndicators:removeMA]',e)}
        delete TECH_CHART.maSeries[key];
      }
    });
    if(TECH_TOGGLES.vol&&!TECH_CHART.volSeries){
      TECH_CHART.volSeries=TECH_CHART.chart.addSeries(LWC.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'tech-vol'});
      TECH_CHART.chart.priceScale('tech-vol').applyOptions({scaleMargins:{top:0.82,bottom:0}});
      TECH_CHART.volSeries.setData(TECH_CHART.volumes);
    }else if(!TECH_TOGGLES.vol&&TECH_CHART.volSeries){
      try{TECH_CHART.chart.removeSeries(TECH_CHART.volSeries)}catch(e){console.warn('[applyTechIndicators:removeVol]',e)}
      TECH_CHART.volSeries=null;
    }
  }
  async function renderTechChartTab(code){
    const el=document.getElementById('tech-chart');if(!el)return;
    renderTechChips();
    if(TECH_CHART.chart&&TECH_CHART.code===code)return;  // 同一檔已經畫過，切回這個分頁不用重建
    const us=isUS(code);
    const rows=(STOCK_CHART.code===code?STOCK_CHART.rawRows:[])||[];
    const daily=rows.map(r=>us
      ?{time:r.date,open:r.Open,high:r.High,low:r.Low,close:r.Close,volume:r.Volume}
      :{time:r.date,open:r.open,high:r.max,low:r.min,close:r.close,volume:r.Trading_Volume})
      .filter(x=>x.time&&x.close!=null&&x.open!=null&&x.high!=null&&x.low!=null);
    if(!daily.length){
      destroyTechChart();
      el.innerHTML='<div class="note">查無足夠的日線價量資料可畫技術指標（需先在「總覽」分頁載入過這一檔的走勢圖）。</div>';
      return;
    }
    try{await ensureLwc()}catch(e){console.warn('[renderTechChartTab:ensureLwc]',e)}  // 常備.開發-20：函式庫改為用到才載入
    if(!lwcAvailable()){
      destroyTechChart();
      el.innerHTML='<div class="note">圖表函式庫（lightweight-charts）未載入，暫無法顯示K線疊加均線/成交量。</div>';
      return;
    }
    destroyTechChart();el.innerHTML='';el.style.height='300px';
    const LWC=window.LightweightCharts;
    const chart=LWC.createChart(el,{width:el.clientWidth||320,height:300,
      layout:{background:{type:'solid',color:'transparent'},textColor:_cssVar('--ink-3','#9aa0a6')},
      grid:{vertLines:{color:'rgba(128,128,128,.12)'},horzLines:{color:'rgba(128,128,128,.12)'}},
      rightPriceScale:{borderVisible:false},timeScale:{borderVisible:false},handleScroll:{vertTouchDrag:false}});
    const up=_cssVar('--up','#ff5257'),down=_cssVar('--down','#24c98a');
    const candle=chart.addSeries(LWC.CandlestickSeries,{upColor:up,downColor:down,borderVisible:false,wickUpColor:up,wickDownColor:down});
    candle.setData(daily.map(x=>({time:x.time,open:x.open,high:x.high,low:x.low,close:x.close})));
    TECH_CHART.chart=chart;TECH_CHART.candleSeries=candle;TECH_CHART.code=code;
    TECH_CHART.closes=daily.map(x=>x.close);TECH_CHART.dates=daily.map(x=>x.time);
    TECH_CHART.volumes=daily.map(x=>({time:x.time,value:x.volume||0,color:x.close>=x.open?up:down}));
    applyTechIndicators();
    chart.timeScale().fitContent();
  }
  function liveUpdateStockPage(){
    const code=currentCode;if(!code||CURRENT_TAB!=='stock')return;
    const us=isUS(code);
    const iq=intradayQuote(code,us);
    if(iq&&iq.price!=null){
      const cls=(iq.change||0)>=0?'pos':'neg';
      const pe=document.getElementById('sh-price');if(pe){pe.textContent=(us?'$':'')+nf(iq.price);pe.className=cls}
      const ce=document.getElementById('sh-chg');if(ce){ce.textContent=`${(iq.change||0)>=0?'+':''}${(+(iq.change||0)).toFixed(us?2:1)}（${(iq.change_pct||0)>=0?'+':''}${(iq.change_pct||0).toFixed(2)}%）`;ce.className=cls}
    }
    updateStockSimTag(code);
    const bar=LIVE.kbarsLast[code];
    if(!bar||STOCK_CHART.code!==code)return;
    const tg=document.getElementById('trend-mode-toggle');
    if(tg&&!tg.innerHTML)renderTrendModeToggle(true); // 開頁時還沒有1分K、現在有了→補上切換鈕
    if(STOCK_CHART.series&&STOCK_CHART.mode==='intraday'){
      try{STOCK_CHART.series.update(_minuteBarToLwc(bar))}catch(e){console.warn('[liveUpdateStockPage:update]',e)}
    }
  }
  window.addEventListener('resize',()=>{if(STOCK_CHART.chart){const el=document.getElementById('trend-chart');if(el&&el.clientWidth)STOCK_CHART.chart.applyOptions({width:el.clientWidth})}});
  // ── 2026-10-11（常備.開發-13）個股簡報（規則版）──────────────────────────────
  // 五條要點，每條只是把既有檔案的數字翻成白話：①營收年增（fundamentals.json）
  // ②法人連買賣天數（institutional_history.json，查不到退回 stock_detail.json 的近 5 日）
  // ③融資增減（stock_detail.json margin）④處置／注意（disposal_flags.json）
  // ⑤近期事件（events.json）。沒有資料的條目照實寫「查無」與查了哪個檔，不留白、不推論。
  // 這裡刻意不下任何「偏多／偏空」結論——那是判斷，規則版不做。
  let INST_HIST_CACHE=null;
  async function ensureInstHistory(){
    if(INST_HIST_CACHE)return INST_HIST_CACHE;
    try{
      const r=await fetch('data/institutional_history.json?t='+Math.floor(Date.now()/1800000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      INST_HIST_CACHE=await r.json();
    }catch(e){console.warn('[ensureInstHistory]',e);recordGlobalError('ensureInstHistory',e);INST_HIST_CACHE={dates:[],series:{}}}
    return INST_HIST_CACHE;
  }
  // rows：由舊到新；從最新一日往回數，同方向（買超>0／賣超<0）連續幾天，遇到 0 或反向就停。
  function _instStreak(rows,pick){
    let dir=null,days=0;
    for(let i=rows.length-1;i>=0;i--){
      const v=pick(rows[i]);
      const s=v>0?'買':v<0?'賣':null;
      if(!s)break;
      if(dir===null)dir=s;else if(s!==dir)break;
      days++;
    }
    return {dir,days};
  }
  function buildStockBriefPoints(code,{fund,detail,hist,flag,events,todayIso}){
    const pts=[];
    const pct=x=>(x>=0?'+':'')+x.toFixed(1)+'%';
    // ① 營收年增
    try{
      const mr=(fund&&fund.month_revenue)||[];
      const last=mr[mr.length-1];
      if(!last)pts.push({k:'營收',t:'查無月營收（data/fundamentals.json 沒有這檔）'});
      else{
        let yoy=last.yoy;
        if(yoy==null){const alt=(fund.revenue_history_scoring||[]).find(r=>r.year===last.year&&r.month===last.month);if(alt&&alt.yoy!=null)yoy=alt.yoy}
        const amt=last.revenue!=null?`${(last.revenue/1e8).toFixed(last.revenue>=1e10?0:1)} 億元`:'金額缺';
        pts.push({k:'營收',t:`${last.year} 年 ${last.month} 月營收 ${amt}，`+(yoy!=null?`年增 ${pct(yoy*100)}`:'年增率官方未提供')});
      }
    }catch(e){console.warn('[brief:rev]',e);recordGlobalError('brief:rev',e);pts.push({k:'營收',t:'計算失敗（已記入診斷 log）'})}
    // ② 法人連買賣
    try{
      let rows=[],src='';
      const ser=hist&&hist.series&&hist.series[code];
      if(ser&&Object.keys(ser).length){
        rows=Object.keys(ser).sort().map(d=>({date:d,f:+ser[d][0]||0,t:+ser[d][1]||0,d:+ser[d][2]||0}));src='近 '+rows.length+' 個交易日';
      }else{
        const h=(detail&&detail.institutional&&detail.institutional.history)||[];
        rows=h.map(x=>({date:x.date,f:+x.foreign_lots||0,t:+x.trust_lots||0,d:+x.dealer_lots||0}));src='近 '+rows.length+' 個交易日，僅 stock_detail 短歷史';
      }
      if(!rows.length)pts.push({k:'法人',t:'查無三大法人紀錄（institutional_history.json／stock_detail.json 都沒有這檔）'});
      else{
        const tot=_instStreak(rows,r=>r.f+r.t+r.d),fo=_instStreak(rows,r=>r.f),tr=_instStreak(rows,r=>r.t);
        const ds=String(rows[rows.length-1].date);const md=ds.length===8?ds.slice(4,6)+'/'+ds.slice(6):ds;
        const fmt=(n,s)=>s.dir?`${n}連${s.dir} ${s.days} 日`:`${n}最新一日持平`;
        pts.push({k:'法人',t:`截至 ${md}：${fmt('三大法人合計',tot)}；${fmt('外資',fo)}；${fmt('投信',tr)}（資料涵蓋${src}）`});
      }
    }catch(e){console.warn('[brief:inst]',e);recordGlobalError('brief:inst',e);pts.push({k:'法人',t:'計算失敗（已記入診斷 log）'})}
    // ③ 融資變化
    try{
      const m=detail&&detail.margin;
      if(!m||m.margin_balance_today==null)pts.push({k:'融資',t:'查無融資餘額（data/stock_detail.json 沒有這檔，上櫃或未涵蓋）'});
      else if(m.margin_balance_prev==null)pts.push({k:'融資',t:`融資餘額 ${nf(m.margin_balance_today)} 張，前一日資料缺，無法算增減`});
      else{
        const dlt=m.margin_balance_today-m.margin_balance_prev;
        const p=m.margin_balance_prev?dlt/m.margin_balance_prev*100:null;
        pts.push({k:'融資',t:`融資餘額 ${nf(m.margin_balance_today)} 張，較前一日${dlt>0?'增加':dlt<0?'減少':'持平'}${dlt?' '+nf(Math.abs(dlt))+' 張':''}${p!=null&&dlt?'（'+pct(p)+'）':''}`});
      }
    }catch(e){console.warn('[brief:margin]',e);recordGlobalError('brief:margin',e);pts.push({k:'融資',t:'計算失敗（已記入診斷 log）'})}
    // ④ 處置／注意（判定沿用 disposalFlagOf，跟個股頁紅標同一套規則）
    try{
      if(!flag)pts.push({k:'處置',t:'目前不是處置股，近 5 日也未列注意股（data/disposal_flags.json）'});
      else if(flag.kind==='notice')pts.push({k:'處置',t:`注意股：${flag.announced||'?'} 公布，原因：${flag.reason||'未提供'}`});
      else pts.push({k:'處置',t:`${flag.kind==='disposal'?'處置中':'即將處置'}：${flag.start||'?'}～${flag.end||'?'}${flag.interval?'，每 '+flag.interval+'撮合一次':''}`});
    }catch(e){console.warn('[brief:disposal]',e);recordGlobalError('brief:disposal',e);pts.push({k:'處置',t:'計算失敗（已記入診斷 log）'})}
    // ⑤ 近期事件（過去 30 日最新兩筆＋未來 30 日最近一筆）
    try{
      const t=Date.parse(todayIso);
      const mine=(events||[]).filter(e=>e&&e.code===code&&e.date);
      const past=mine.filter(e=>{const d=(t-Date.parse(e.date))/864e5;return d>=0&&d<=30}).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,2);
      const fut=mine.filter(e=>{const d=(Date.parse(e.date)-t)/864e5;return d>0&&d<=30}).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,1);
      if(!past.length&&!fut.length)pts.push({k:'事件',t:'近 30 日與未來 30 日查無事件（data/events.json：重大訊息／月營收／除權息）'});
      else pts.push({k:'事件',t:[...past.map(e=>`${e.date.slice(5)} ${e.title}`),...fut.map(e=>`即將 ${e.date.slice(5)} ${e.title}`)].join('；')});
    }catch(e){console.warn('[brief:events]',e);recordGlobalError('brief:events',e);pts.push({k:'事件',t:'計算失敗（已記入診斷 log）'})}
    return pts;
  }
  async function renderStockBrief(code){
    const el=document.getElementById('ai-brief-body');if(!el)return;
    if(isUS(code)){el.innerHTML='<div class="note">美股暫不提供規則簡報（五個來源檔都是台股官方資料）。</div>';return}
    el.innerHTML='<div class="note">載入中…</div>';
    const [fund,detail,hist,,ev]=await Promise.allSettled([loadFundamentals(code),loadStockDetail(code),ensureInstHistory(),ensureDisposalFlags(),ensureEvents()]);
    if(currentCode!==code)return;
    const v=r=>r.status==='fulfilled'?r.value:null;
    const todayIso=_twTodayIso();
    const pts=buildStockBriefPoints(code,{fund:v(fund)||{},detail:v(detail)||{},hist:v(hist),flag:disposalFlagOf(code,todayIso),events:(v(ev)||{}).events||[],todayIso});
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    el.innerHTML='<ol style="margin:4px 0 0 18px;padding:0;line-height:1.7">'+pts.map(p=>`<li><b>${esc(p.k)}</b>　${esc(p.t)}</li>`).join('')+'</ol>'
      +'<div class="note" style="margin-top:8px">規則摘要，非 AI 判斷、非投資建議：只把 fundamentals／stock_detail／institutional_history／disposal_flags／events 五份檔案的數字轉成文字，不推論漲跌。</div>';
  }
  // ── 2026-10-11（常備.開發-15）目標價與評等（公開來源）────────────────────────────
  // 只顯示 data/us_analyst_reco.json 裡 Finnhub 免費層的「評等家數分佈」，不自行計分、不推論漲跌。
  let US_RECO_CACHE=null;
  const ANALYST_TW_NOTE='台股目前沒有合法的免費來源：證交所／櫃買 OpenAPI 與 FinMind 都沒有券商目標價或評等資料，券商研究報告屬付費商品（待採購），依資料取得鐵律不爬新聞或付費報告。查證紀錄：docs/FIRST_HAND_SOURCES.md。';
  function buildAnalystRadarHtml(code,data){
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    if(!isUS(code))return `<div class="note">${esc(ANALYST_TW_NOTE)}</div>`;
    const tail='<div class="note" style="margin-top:8px">目標價：Finnhub 目標價端點為付費方案，待採購，目前不顯示。評等為多家券商家數彙整，非投資建議。</div>';
    const rows=data&&data.tickers&&data.tickers[code];
    if(!rows||!rows.length){
      const cov=(data&&data.coverage)||[];
      const why=!data?'評等檔（data/us_analyst_reco.json）尚未產生或讀取失敗'
        :cov.includes(code)?'Finnhub 這檔沒有回傳評等資料':`目前只涵蓋 ${cov.join('、')||'—'}，這檔不在清單內`;
      return `<div class="note">查無評等：${esc(why)}。</div>`+tail;
    }
    const L=rows[0],K=[['strongBuy','強力買進'],['buy','買進'],['hold','持有'],['sell','賣出'],['strongSell','強力賣出']];
    const n=x=>Number(x)||0,tot=K.reduce((a,[k])=>a+n(L[k]),0);
    if(!tot)return `<div class="note">查無評等：${esc(L.period)} 期家數皆為 0。</div>`+tail;
    const bars=K.map(([k,lb])=>`<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:64px;font-size:12px">${lb}</span><div style="flex:1;height:8px;background:var(--hairline);border-radius:4px;overflow:hidden"><div style="width:${(n(L[k])/tot*100).toFixed(1)}%;height:100%;background:var(--ink-2)"></div></div><span style="width:28px;text-align:right;font-size:12px">${n(L[k])}</span></div>`).join('');
    let trend='';
    const P=rows[1];
    if(P){const pos=r=>n(r.strongBuy)+n(r.buy),pt=K.reduce((a,[k])=>a+n(P[k]),0);
      if(pt){const d=pos(L)/tot*100-pos(P)/pt*100;trend=`買進類占比 ${(pos(L)/tot*100).toFixed(0)}%，較 ${esc(P.period)} 期${Math.abs(d)<0.5?'持平':(d>0?'上升 ':'下降 ')+Math.abs(d).toFixed(0)+' 個百分點'}。`}}
    return `<div class="note" style="margin-bottom:4px">${esc(L.period)} 期，共 ${tot} 家券商評等（來源：Finnhub 免費層，抓取時間 ${esc((data.generated_at||'').slice(0,10))}）</div>${bars}`
      +(trend?`<div class="note" style="margin-top:6px">${trend}</div>`:'')+tail;
  }
  async function renderAnalystRadar(code){
    const el=document.getElementById('analyst-radar-body');if(!el)return;
    if(!isUS(code)){el.innerHTML=buildAnalystRadarHtml(code,null);return}
    el.innerHTML='<div class="note">載入中…</div>';
    if(!US_RECO_CACHE){
      try{const r=await fetch('data/us_analyst_reco.json?t='+Date.now());if(r.ok)US_RECO_CACHE=await r.json()}
      catch(e){console.warn('[renderAnalystRadar]',e);recordGlobalError('renderAnalystRadar',e)}
    }
    if(currentCode!==code)return;
    el.innerHTML=buildAnalystRadarHtml(code,US_RECO_CACHE);
  }
  // ── 2026-10-11（常備.開發-14）營收解讀（規則版）────────────────────────────────
  // 三段文字：①月增（最新月 vs 上一月）②年增（官方 yoy，缺時用去年同月金額自算）
  // ③累計年增（今年 1 月～最新月合計 vs 去年同期合計；去年某月缺金額時用「今年該月÷(1+官方年增)」回推，
  // 仍缺就照實寫缺哪幾個月、不硬算）。資料只來自 fundamentals.json 的 month_revenue＋revenue_history_scoring。
  function buildRevenueReadPoints(fund){
    const pts=[];
    const pct=x=>(x>=0?'+':'')+x.toFixed(1)+'%';
    const amt=v=>(v/1e8).toFixed(v>=1e10?0:1)+' 億元';
    const M={};
    [...((fund&&fund.revenue_history_scoring)||[]),...((fund&&fund.month_revenue)||[])].forEach(r=>{
      if(!r||r.year==null||r.month==null)return;
      const k=r.year*100+r.month,o=M[k]||{};
      M[k]={year:r.year,month:r.month,revenue:r.revenue!=null?r.revenue:o.revenue,yoy:r.yoy!=null?r.yoy:o.yoy};
    });
    const keys=Object.keys(M).map(Number).filter(k=>M[k].revenue!=null).sort((a,b)=>a-b);
    if(!keys.length)return [{k:'月增',t:'查無月營收（data/fundamentals.json 沒有這檔）'},{k:'年增',t:'查無月營收，無法計算'},{k:'累計年增',t:'查無月營收，無法計算'}];
    const L=M[keys[keys.length-1]],ym=`${L.year} 年 ${L.month} 月`;
    const prevKey=L.month===1?(L.year-1)*100+12:L.year*100+L.month-1;
    const lastYr=(y,m)=>{const r=M[(y-1)*100+m];if(r&&r.revenue!=null)return r.revenue;const c=M[y*100+m];return c&&c.revenue!=null&&c.yoy!=null&&c.yoy>-1?c.revenue/(1+c.yoy):null};
    try{
      const p=M[prevKey];
      if(!p||!p.revenue)pts.push({k:'月增',t:`${ym}營收 ${amt(L.revenue)}；上一月營收缺，無法算月增`});
      else{const v=(L.revenue-p.revenue)/p.revenue*100;pts.push({k:'月增',t:`${ym}營收 ${amt(L.revenue)}，較上月 ${amt(p.revenue)}${v>0?'增加':v<0?'減少':'持平'} ${pct(v)}`})}
    }catch(e){console.warn('[revRead:mom]',e);recordGlobalError('revRead:mom',e);pts.push({k:'月增',t:'計算失敗（已記入診斷 log）'})}
    try{
      let yoy=L.yoy!=null?L.yoy*100:null,src='官方年增率';
      if(yoy==null){const ly=M[(L.year-1)*100+L.month];if(ly&&ly.revenue){yoy=(L.revenue-ly.revenue)/ly.revenue*100;src='以去年同月金額自算'}}
      pts.push({k:'年增',t:yoy!=null?`${ym}較去年同月${yoy>0?'成長':yoy<0?'衰退':'持平'} ${pct(yoy)}（${src}）`:`${ym}年增率官方未提供，去年同月金額也缺，無法計算`});
    }catch(e){console.warn('[revRead:yoy]',e);recordGlobalError('revRead:yoy',e);pts.push({k:'年增',t:'計算失敗（已記入診斷 log）'})}
    try{
      let cur=0,prv=0;const miss=[];
      for(let m=1;m<=L.month;m++){
        const c=M[L.year*100+m];const ly=lastYr(L.year,m);
        if(!c||c.revenue==null||ly==null){miss.push(m);continue}
        cur+=c.revenue;prv+=ly;
      }
      if(miss.length)pts.push({k:'累計年增',t:`${L.year} 年 1～${L.month} 月累計年增無法計算：缺 ${miss.join('、')} 月的今年或去年同月金額（快照只保留部分月份）`});
      else{const v=(cur-prv)/prv*100;pts.push({k:'累計年增',t:`${L.year} 年 1～${L.month} 月累計營收 ${amt(cur)}，較去年同期 ${amt(prv)}${v>0?'成長':v<0?'衰退':'持平'} ${pct(v)}`})}
    }catch(e){console.warn('[revRead:ytd]',e);recordGlobalError('revRead:ytd',e);pts.push({k:'累計年增',t:'計算失敗（已記入診斷 log）'})}
    return pts;
  }
  async function renderRevenueRead(code){
    const el=document.getElementById('ai-rev-body');if(!el)return;
    if(isUS(code)){el.innerHTML='<div class="note">美股暫不提供營收解讀（月營收為台股官方申報資料）。</div>';return}
    el.innerHTML='<div class="note">載入中…</div>';
    const fund=await loadFundamentals(code);
    if(currentCode!==code)return;
    const pts=buildRevenueReadPoints(fund||{});
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    el.innerHTML='<ol style="margin:4px 0 0 18px;padding:0;line-height:1.7">'+pts.map(p=>`<li><b>${esc(p.k)}</b>　${esc(p.t)}</li>`).join('')+'</ol>'
      +'<div class="note" style="margin-top:8px">規則摘要，非 AI 判斷、非投資建議：只用 data/fundamentals.json 的月營收數字計算，不推論漲跌。</div>';
  }
  // 常備.開發-5（2026-10-11）：美股事件時間軸＝下一次財報日（data/earnings_calendar.json，yfinance 推估）
  // ＋近 90 天 SEC Form 8-K（data/us_events.json，fetch_us_8k.py 排程，只存索引）。無資料時說明原因。
  const US_6K_ISSUERS=['TSM','UMC','ASX','CHT'];  // 外國私人發行人申報 6-K 不申報 8-K（見 fetch_us_8k.py 檔頭）
  async function renderUsEventsTab(code,host){
    host.innerHTML=skeletonRowsHtml(3);
    try{
      if(!US_8K_CACHE){const r=await fetch('data/us_events.json?t='+Date.now());if(r.ok)US_8K_CACHE=await r.json()}
      const cal=await loadEarningsCalendar();
      if(currentCode!==code)return;
      const d=US_8K_CACHE||{},t=d.tickers&&d.tickers[code],ec=cal[code];
      const cutoff=new Date(Date.now()-90*86400000).toISOString().slice(0,10),today=new Date().toISOString().slice(0,10);
      const rows=[];
      if(ec&&ec.next_earnings_date&&ec.next_earnings_date>=today){
        const sess={pre:'盤前',post:'盤後'}[ec.estimated_session]||'';
        rows.push({date:ec.next_earnings_date,type:'財報日',title:'下一次財報公布（預估'+(sess?'，通常'+sess:'')+(ec.eps_estimate!=null?'；EPS 預估 '+Number(ec.eps_estimate).toFixed(2):'')+'）'});
      }
      ((t&&t.filings)||[]).filter(f=>String(f.filed_at||'')>=cutoff).forEach(f=>rows.push({date:f.filed_at,type:f.filing_type||'8-K',title:(f.items&&f.items.length?f.items.join('；'):'（無 Item 條號說明）'),url:f.url}));
      const why=[];
      if(!t)why.push(US_6K_ISSUERS.includes(code)?'外國私人發行人改申報 Form 6-K，不適用 8-K（6-K 尚未接入）':'此代號不在 8-K 追蹤清單（data/us_sic.json）內，未抓取');
      else if(!rows.some(r=>r.type!=='財報日'))why.push(US_6K_ISSUERS.includes(code)?'外國私人發行人改申報 Form 6-K，近 90 天無 8-K 屬正常':'近 90 天無 8-K 申報');
      if(!ec)why.push('財報日：此代號不在財報行事曆追蹤清單（fetch_earnings_calendar.py）');
      else if(!rows.some(r=>r.type==='財報日'))why.push('財報日：行事曆尚無下一次日期');
      const foot='<div class="note" style="margin-top:8px">來源：SEC EDGAR Form 8-K（只存索引，點標題看原文）'+(d.fetched_at?'，'+fmtTzMMDDHHMM(new Date(d.fetched_at),'Asia/Taipei'):'')+'；財報日為 yfinance 推估，公司可能改期。非投資建議。'+(why.length?'<br>'+why.map(_autoEsc).join('；'):'')+'</div>';
      host.innerHTML=(rows.length?'<div style="display:flex;flex-direction:column;gap:9px">'+eventsRowsHtml(rows,15)+'</div>':'<div class="note">近 90 天無可顯示的美股事件</div>')+foot;
    }catch(e){console.warn('[renderUsEventsTab]',e);recordGlobalError('renderUsEventsTab',e);host.innerHTML='<div class="note">美股事件載入失敗（'+_autoEsc(e&&e.message||e)+'）</div>'}
  }
  // 個股頁「事件」分頁（P0產品.三框架）：跟上面研究報告頁的事件卡是同一份資料，
  // 差別是這裡不需要scores.json的row（總覽/搜尋進來的股票未必在評分樣本內），
  // 而且空狀態要用總司令裁示的「尚未 X｜原因｜下一步」一行格式。
  async function renderStockEventsTab(code){
    const host=document.getElementById('stock-events-list');if(!host)return;
    if(isUS(code)){await renderUsEventsTab(code,host);return}
    host.innerHTML=skeletonRowsHtml(3);  // 2026-09-15 P0產品.四：骨架屏
    const d=await ensureEvents();
    if(currentCode!==code)return;  // await期間已切到別檔，作廢
    const mine=recentEventsFor(d,code,30);
    if(!mine.length){
      host.innerHTML='<div class="note">尚未偵測到近30日事件｜已查MOPS上市/上櫃重大訊息、TWSE月營收公布、除權息三類官方資料，此代號近30日無相符紀錄｜可等下一輪排程（每30分鐘更新）或近期營收公布日後再回來查看'
        +(d.fetched_at?`（資料時間 ${fmtTzMMDDHHMM(new Date(d.fetched_at),'Asia/Taipei')}）`:'')+'</div>';
      return;
    }
    host.innerHTML='<div style="display:flex;flex-direction:column;gap:9px">'+eventsRowsHtml(mine,20)+'</div>'
      +`<div class="note" style="margin-top:8px">近 30 日共 ${mine.length} 筆${mine.length>20?'，只顯示最近 20 筆':''}。資料來源：MOPS 重大訊息／TWSE 月營收／除權息，只存索引不存全文，點標題看原文。</div>`;
  }
