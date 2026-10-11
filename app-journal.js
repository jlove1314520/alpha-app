// 常備.開發-20 丙案（2026-10-11 先.六十五）：日誌頁專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('journal') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // 日誌頁篩選：全部/台/美/期（用 filter chips，不是三選切換——日誌是回顧型清單，
  // 使用者可能同時想看混合結果，跟市場/選股/交易那種「當下只在一個市場」不同）。
  let JOURNAL_FILTER='ALL';
  const JOURNAL_CHIP_LABEL={ALL:'全部',TW:'台',US:'美',FUT:'期'};
  function renderJournalChips(){
    const el=document.getElementById('journal-chips');
    el.innerHTML=['ALL','TW','US','FUT'].map(k=>
      `<span class="press" style="flex-shrink:0;white-space:nowrap;font-size:12px;font-weight:${JOURNAL_FILTER===k?600:400};color:${JOURNAL_FILTER===k?'#1a1005':'var(--ink-2)'};background:${JOURNAL_FILTER===k?'var(--gold-grad)':'rgba(255,255,255,.05)'};border:1px solid ${JOURNAL_FILTER===k?'transparent':'rgba(255,255,255,.08)'};padding:6px 13px;border-radius:999px;cursor:pointer" onclick="setJournalFilter('${k}')">${JOURNAL_CHIP_LABEL[k]}</span>`
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
  async function loadJournalLedger(){
    const pe=document.getElementById('journal-pnl'),te=document.getElementById('journal-trades');
    if(!pe||!te)return;
    if(!LIVE.configured||!LIVE.url){pe.textContent='連上電腦才看得到';te.innerHTML='<div class="note" style="padding:14px 2px">連上電腦才看得到</div>';setTxt('journal-perf','尚未連線本機伺服器，真錢績效對照只在本機計算。');setTxt('journal-review','尚未連線本機伺服器，盤後復盤只在本機產生。');return}
    try{
      const d=await loadAutoLedger();
      JOURNAL_LEDGER_CACHE=d;_safeAsync('loadWeeklyBrief',loadWeeklyBrief);
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
    const pc=v=>(v>0?'+':'')+v+'%',cls=v=>v>=0?'pos':'neg',diff=Math.round((pf.nav_pct-pf.bench_pct)*100)/100;
    el.innerHTML=journalPerfSvg(pf.points)+
      '<div style="display:flex;gap:14px;font-size:12px;margin-top:4px"><span><span style="color:var(--accent)">━</span> Bb-90 自動交易 <b class="'+cls(pf.nav_pct)+'">'+pc(pf.nav_pct)+'</b></span>'+
      '<span><span style="color:var(--ink-3)">━</span> 同期 0050 全持有 <b class="'+cls(pf.bench_pct)+'">'+pc(pf.bench_pct)+'</b></span></div>'+
      '<div style="margin-top:4px;font-size:12px">差距：<b class="'+cls(diff)+'">'+(diff>0?'+':'')+diff+' 個百分點</b>（'+esc(pf.start)+' 起至 '+esc(pf.as_of)+'，'+pf.points.length+' 個交易日）</div>'+
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
