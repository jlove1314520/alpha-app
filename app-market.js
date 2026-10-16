// 常備.開發-20 丙案（2026-10-11 先.六十五）：市場頁（含籌碼市場子頁）專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('market') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // 2026-09-10（建置一.3）美股類股（SEC SIC）／ADR溢價，見 loadMarketUsSector()／
  // loadMarketAdrPremium()。跟上面幾個INTRADAY_*同樣的「全域快取+各自fetch」風格。
  let US_SIC_CACHE=null,ADR_PREMIUM_CACHE=null;
  // 類股指數名稱（market_tw.json的sectors[].name，官方28+類，2026-08-27實測
  // 共37種）→company_info.json的industry分類文字。**這是「依股票產業分類分組」
  // 的近似清單，不是TWSE官方指數審核過的完整成分股名冊**（openStock等既有
  // 功能也沒有這種官方成分股資料源可用），清單畫面會誠實標註這點。部分較舊
  // 的合併類別（水泥窯製/塑膠化工/機電/化學生技醫療）用「聯集」對應到現行
  // 拆分後的細項分類，是盡力而為的對應，不保證跟TWSE歷史指數定義逐字一致。
  const SECTOR_TO_INDUSTRY={
    '水泥窯製類指數':['水泥工業'], '塑膠化工類指數':['塑膠工業','化學工業'],
    '機電類指數':['電機機械','電器電纜'], '水泥類指數':['水泥工業'],
    '食品類指數':['食品工業'], '塑膠類指數':['塑膠工業'],
    '紡織纖維類指數':['紡織纖維'], '電機機械類指數':['電機機械'],
    '電器電纜類指數':['電器電纜'],
    '化學生技醫療類指數':['化學生技醫療','化學工業','生技醫療業'],
    '化學類指數':['化學工業'], '生技醫療類指數':['生技醫療業'],
    '玻璃陶瓷類指數':['玻璃陶瓷'], '造紙類指數':['造紙工業'],
    '鋼鐵類指數':['鋼鐵工業'], '橡膠類指數':['橡膠工業'],
    '汽車類指數':['汽車工業'], '電子工業類指數':['電子工業'],
    '半導體類指數':['半導體業'], '電腦及週邊設備類指數':['電腦及週邊設備業'],
    '光電類指數':['光電業'], '通信網路類指數':['通信網路業'],
    '電子零組件類指數':['電子零組件業'], '電子通路類指數':['電子通路業'],
    '資訊服務類指數':['資訊服務業'], '其他電子類指數':['其他電子業','其他電子類'],
    '建材營造類指數':['建材營造'], '航運類指數':['航運業'],
    '觀光餐旅類指數':['觀光餐旅','觀光事業'],
    '金融保險類指數':['金融保險','金融業'], '貿易百貨類指數':['貿易百貨'],
    '油電燃氣類指數':['油電燃氣業'],
    '綠能環保類指數':['綠能環保','綠能環保類'],
    '數位雲端類指數':['數位雲端','數位雲端類'],
    '運動休閒類指數':['運動休閒','運動休閒類'],
    '居家生活類指數':['居家生活','居家生活類'], '其他類指數':['其他'],
  };
  async function openSectorList(sectorName){
    try{
      const industries=SECTOR_TO_INDUSTRY[sectorName];
      const listEl=document.getElementById('sector-sheet-list');
      const titleEl=document.getElementById('sector-sheet-title');
      if(!listEl||!titleEl)return;
      titleEl.textContent=sectorName.replace('類指數','')+'（成分股，依產業分類）';
      document.getElementById('sector-mask').classList.add('open');
      document.getElementById('sector-sheet').classList.add('open');
      if(!industries){listEl.innerHTML='<div class="note">此類股暫無對應的產業分類資料。</div>';return}
      listEl.innerHTML=skeletonRowsHtml(5);  // 2026-09-15 P0產品.四：骨架屏取代純文字「載入中」
      const [companies,quotes]=await Promise.all([loadCompanyInfo(),loadQuotesAllTw()]);
      const codes=Object.keys(companies).filter(c=>industries.includes(companies[c].industry));
      if(!codes.length){listEl.innerHTML='<div class="note">查無成分股資料。</div>';return}
      let scoreMap={};
      if(PICKS_CACHE&&PICKS_CACHE.stocks)scoreMap=Object.fromEntries(PICKS_CACHE.stocks.map(s=>[s.code,s.total_score]));
      const rows=codes.map(code=>{
        const q=quotes[code]||{};
        return{code,name:companies[code].name||code,change_pct:q.change_pct,turnover:q.turnover,score:scoreMap[code]};
      }).sort((a,b)=>(b.change_pct??-999)-(a.change_pct??-999));
      const ciAt=COMPANY_INFO_CACHE&&COMPANY_INFO_CACHE.meta&&COMPANY_INFO_CACHE.meta.generated_at;
      listEl.innerHTML='<div class="note" style="margin-bottom:8px">依股票產業分類分組，非TWSE官方指數完整成分股清單；共 '+rows.length+' 檔。產業分類'+(ciAt?_dataDateLabel(ciAt,'公司名冊非每日排程'):'資料日不明')+'。</div>'
        +rows.map(r=>{
          const chgCls=r.change_pct==null?'':(r.change_pct>=0?'pos':'neg');
          const chgTxt=r.change_pct==null?'—':(r.change_pct>=0?'+':'')+r.change_pct.toFixed(2)+'%';
          const turnTxt=r.turnover==null?'—':fmtLiquidity(r.turnover)+'元';
          const scoreTxt=r.score==null?'—':r.score.toFixed(1);
          return `<div class="row press" style="cursor:pointer" onclick="closeSectorSheet();openStock('${r.code}')">
            <div class="nm"><b>${r.name}</b><span>${r.code}</span></div>
            <div class="num ${chgCls}" style="min-width:64px;text-align:right">${chgTxt}</div>
            <div class="num" style="min-width:70px;text-align:right;color:var(--ink-3);font-size:11px">${turnTxt}</div>
            <div class="num" style="min-width:34px;text-align:right;color:var(--gold)">${scoreTxt}</div>
          </div>`;
        }).join('');
    }catch(e){
      console.warn('[openSectorList]',e);recordGlobalError('openSectorList',e);
      const listEl=document.getElementById('sector-sheet-list');
      if(listEl)listEl.innerHTML='<div class="note">載入失敗：'+e.message+'</div>';
    }
  }
  // 2026-09-01新增：加權指數優先用Shioaji即時報價(quotes_sinopac.json)，
  // 查不到/過期才退回現有TWSE來源（market_tw.json）——分工鐵律，見
  // intradayQuote()同一段說明。回傳{srcLabel,item}供idxRowHtml()使用，
  // sparkline借用既有TWSE來源的（Shioaji這支腳本沒有近20日走勢序列）。
  // ── 2026-09-04（四修.二）櫃買指數＋37類股即時：live server的/live/indices（5秒快取），
  // 連不上退回market_tw.json並**一律標日期**（總司令原話：絕不能再讓昨天的漲跌幅在今天
  // 盤中不標日期地顯示）。
  const LIVE_IDX={at:0,data:null};
  async function getLiveIndices(){
    if(!LIVE.connected)return null;
    if(LIVE_IDX.data&&Date.now()-LIVE_IDX.at<5000)return LIVE_IDX.data;
    try{const r=await liveFetch('/live/indices',4000);if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json();LIVE_IDX.data=d&&d.available?d:null;LIVE_IDX.at=Date.now();return LIVE_IDX.data}
    catch(e){console.warn('[getLiveIndices]',e);LIVE_IDX.data=null;LIVE_IDX.at=Date.now();return null}
  }
  function tpexRowSource(twCache,liveIdx){
    const q=liveIdx&&liveIdx.tpex;
    if(q&&q.last!=null){
      return {srcLabel:liveIdx.market_status==='closed'?'永豐 今日收盤':'永豐 即時',item:{close:q.last,change_pct:q.change_pct,sparkline:twCache.tpex&&twCache.tpex.sparkline}};
    }
    // 先.一〇四-6：落後與否看櫃買自己的資料日（不再沿用整份檔的 stale_note）
    return {srcLabel:'櫃買 '+twCloseDateLabel(twCache),item:twCache.tpex&&{close:twCache.tpex.close,change_pct:twCache.tpex.change_pct,sparkline:twCache.tpex.sparkline,stale_tag:staleTag(twCache.tpex.date,'tw')}};
  }
  async function loadMarketIndex(){
    const el=document.getElementById('idx-rows');if(!el)return;
    await loadMarketDataFiles();
    await ensureSinopacQuotes();
    const tw=MARKET_TW_CACHE||{};
    if(LIVE.connected){mergeLiveKbarsLast();await Promise.allSettled(['TAIEX'].map(getLiveCloses))}  // 2026-09-04四修.三
    const taiexSrc=taiexRowSource(tw);
    // 2026-09-02修正（圖表診斷任務發現的真bug）：這裡組給idxRowHtml()的物件原本
    // 只挑close/change_pct兩個欄位，漏掉market_tw.json::tpex.sparkline——不是「資料
    // 還沒累積到2點」這種資料不足，而是即使sparkline以後累積到20點，這裡也永遠不會
    // 把它傳進去，櫃買指數那條走勢線注定永久畫不出來。改成把sparkline也一併帶進去。
    const liveIdx=await getLiveIndices();
    const tpexSrc=tpexRowSource(tw,liveIdx);
    if(taiexSrc.item&&!(taiexSrc.srcLabel||'').startsWith('Shioaji'))taiexSrc.item=Object.assign({},taiexSrc.item,{stale_tag:staleTag(taiexSrc.item.data_date||tw.data_date,'tw')});  // 先.一〇四-6
    el.innerHTML=idxRowHtml('加權指數',taiexSrc.srcLabel,taiexSrc.item)+idxRowHtml('櫃買指數',tpexSrc.srcLabel,tpexSrc.item);
    // 2026-09-04四修.二：時間戳跟著實際來源走——即時就寫即時時間，退回盤後就明標收盤日
    if(liveIdx&&liveIdx.tpex)document.getElementById('idx-datatime').textContent=`Shioaji 即時（${liveIdx.generated_at?fmtTzHHMM(new Date(liveIdx.generated_at),'Asia/Taipei'):'—'}）· 走勢線為近20日收盤`;
    else document.getElementById('idx-datatime').textContent=`${twCloseDateLabel(tw)}｜${fmtMarketDataTime(tw)}`;
  }
  function futRowHtml(label,fut,srcLabel){
    if(!fut||fut.last==null)return `<div class="row" style="cursor:default"><div class="nm"><b>${label}</b><span>TAIFEX</span></div><div class="px"><b>—</b><span>查無資料</span></div></div>`;
    // 先.一〇四-6：盤後資料（非即時）資料日落後台股最後交易日 → 整列灰、不上紅綠、標 MM/DD
    const stale=srcLabel?'':staleTag(fut.data_date||fut.date,'tw');
    const cls=stale?'':(fut.change_pct>=0?'pos':'neg');
    const cm=fut.contract_month?`${fut.contract_month.slice(0,4)}/${fut.contract_month.slice(4,6)}`:'';
    const srcHtml=srcLabel||`期交所${cm?` · ${cm} 近月`:''}`;
    const sp=rowSparkline('TXF_NEAR',null,(fut.change_pct||0)>=0).html;  // 2026-09-04四修.三：即時時畫台指期當日1分K
    return `<div class="row${stale?' is-stale':''}" style="cursor:default"><div class="nm"><b>${label}${stale?` <span class="stale-tag">${stale}</span>`:''}</b><span>${srcHtml}</span></div>${sp}<div class="px"><b class="num">${nf(fut.last)}</b><span class="num ${cls}">${fut.change_pct>=0?'+':''}${(fut.change_pct||0).toFixed(2)}%</span></div></div>`;
  }
  function hexMix(c1,c2,t){
    const p=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
    const [r1,g1,b1]=p(c1),[r2,g2,b2]=p(c2);
    const r=Math.round(r1+(r2-r1)*t),g=Math.round(g1+(g2-g1)*t),b=Math.round(b1+(b2-b1)*t);
    return `#${[r,g,b].map(x=>x.toString(16).padStart(2,'0')).join('')}`;
  }
  function heatColor(pct){
    let t=Math.max(-3,Math.min(3,pct))/3;
    // 先.一〇三-13：跟隨設定頁「漲跌顏色」——國際慣例（綠漲紅跌）時把正負對調，原本永遠紅漲綠跌
    if(document.documentElement.getAttribute('data-updown')==='intl')t=-t;
    // 先.九十五-4：淺色模式改用淺底＋淡紅／淡綠（字是深色 --ink），深色模式維持原本的值
    if(document.documentElement.getAttribute('data-theme')==='light')
      return t>=0?hexMix('#ebe6dc','#ef9a96',t):hexMix('#ebe6dc','#8fd0b0',-t);
    return t>=0?hexMix('#383835','#8f2f2f',t):hexMix('#383835','#265244',-t);
  }
  // 外觀切換（設定頁或手機系統切換）或漲跌顏色切換時重畫熱力圖，顏色才會跟著換；自身失敗只警告
  ['alpha-theme-change','alpha-updown-change'].forEach(ev=>window.addEventListener(ev,()=>{
    try{if(document.getElementById('heat-grid')&&typeof loadHeatmap==='function')loadHeatmap().catch(e=>{console.warn('[heat theme]',e);recordGlobalError('heatThemeRedraw',e)})}
    catch(e){console.warn('[heat theme]',e);recordGlobalError('heatThemeRedraw',e)}
  }));
  // 2026-08-26 架構修正：類股表現改讀 market_tw.json 的 sectors（TWSE MI_INDEX
  // 官方28類產業分類，見 fetch_market_tw.py），不再逐類呼叫 FinMind。
  async function loadHeatmap(){
    const el=document.getElementById('heat-grid');if(!el)return;
    await loadMarketDataFiles();
    let sectors=(MARKET_TW_CACHE&&MARKET_TW_CACHE.sectors)||[];
    // 2026-09-04四修.二：連上即時且/live/indices有37類股→用即時漲跌幅（依名稱對應），標「Shioaji 即時」；
    // 否則沿用market_tw.json盤後資料，但一律明標收盤日（不能讓昨天的漲跌幅在今天盤中不標日期地顯示）。
    const liveIdx=await getLiveIndices();
    let heatSrcNote=null;
    if(liveIdx&&Array.isArray(liveIdx.sectors)&&liveIdx.sectors.length){
      const byName={};liveIdx.sectors.forEach(s=>{byName[s.name]=s});
      const merged=sectors.length?sectors.map(r=>{const l=byName[r.name];return l&&l.change_pct!=null?{...r,change_pct:l.change_pct,close:l.last}:{...r,change_pct:null}}):liveIdx.sectors.map(s=>({name:s.name,close:s.last,change_pct:s.change_pct}));
      const hit=merged.filter(r=>r.change_pct!=null).length;
      sectors=merged;
      heatSrcNote=`Shioaji 即時 ${hit}/${merged.length} 類股（${liveIdx.generated_at?fmtTzHHMM(new Date(liveIdx.generated_at),'Asia/Taipei'):'—'}）`+(liveIdx.market_status==='closed'?'（今日收盤）':'');
    }
    if(!sectors.length){el.innerHTML='<div class="note">查無資料</div>';document.getElementById('heat-datatime').textContent=fmtMarketDataTime(MARKET_TW_CACHE);return}
    // 2026-08-27新增（B4）：每張卡加onclick開成分股清單（openSectorList），
    // 用JSON.stringify(r.name)而不是直接內插字串，避免類股名稱萬一含特殊
    // 字元(引號等)break掉onclick屬性——目前37個類股名稱都是安全的中文字，
    // 但這樣寫比較保險，不依賴「資料源永遠不會出現特殊字元」這個假設。
    el.innerHTML=sectors.map(r=>{
      const nameAttr=JSON.stringify(r.name).replace(/"/g,'&quot;');
      return r.change_pct==null
      ?`<div class="tile press" style="background:var(--line-mid);cursor:pointer" onclick='openSectorList(${nameAttr})'><b>${r.name.replace('類指數','')}</b><span>—</span></div>`
      :`<div class="tile press" style="background:${heatColor(r.change_pct)};cursor:pointer" onclick='openSectorList(${nameAttr})'><b>${r.name.replace('類指數','')}</b><span>${r.change_pct>=0?'+':''}${r.change_pct.toFixed(2)}%</span></div>`;
    }).join('');
    document.getElementById('heat-datatime').textContent=heatSrcNote||`${twCloseDateLabel(MARKET_TW_CACHE)}｜${fmtMarketDataTime(MARKET_TW_CACHE)}`;
  }

  // 2026-08-26 架構修正：改讀 market_tw.json 的 institutional_history（TWSE T86
  // 全市場逐日加總，見 fetch_market_tw.py）。**單位是「淨買賣張數」不是金額**——
  // T86 只給股數沒有逐股價格，換算成金額需要每股價格加權，這裡沒有那個資料，
  // 誠實只回報張數，不假裝算出金額（App 原本標「億元」是錯的，這裡一併改正）。
  // 歷史是跨多次排程執行累積出來的，一開始可能只有 1-2 天，會隨時間增加到 5-10 天。
  // 先.一〇四-7：單位可切張／億元（億元讀 *_net_amt，來自先.一〇三-1b 的 BFI82U；還沒有就停用並說明）；
  // 最新一根標數值、數字一律千分位。
  // 先.一〇三-1b-1：合計預設億元（BFI82U 有金額時）；張數收進下方「看細節」，切換鈕保留。
  let INST_UNIT=null;
  function setInstUnit(u){INST_UNIT=u;_safeAsync('loadInstTotal',loadInstTotal)}
  window.setInstUnit=setInstUnit;
  function _instFmt(v,unit){
    if(v==null||!isFinite(v))return '—';
    const sign=v>=0?'+':'−';
    return unit==='amt'?sign+Math.abs(v).toLocaleString('zh-TW',{maximumFractionDigits:1,minimumFractionDigits:1})+' 億'
      :sign+Math.round(Math.abs(v)).toLocaleString('zh-TW')+' 張';
  }
  // 先.一〇三-1b-1：「看細節」——逐日張數（T86 ALLBUT0999）＋最新一日金額分項（BFI82U）。兩者口徑不同，各標來源。
  function _instDetailHTML(history){
    const rows=history.slice().reverse();
    const md=d=>String(d||'').slice(4,6)+'/'+String(d||'').slice(6,8);
    const c=v=>`<td style="text-align:right;color:${v==null?'var(--ink-4)':(v>=0?'var(--up)':'var(--down)')}">${v==null?'—':_instFmt(v,'lots').replace(/ 張$/,'')}</td>`;
    const tb=`<table style="width:100%;font-size:11px;border-collapse:collapse;margin-top:4px"><tr style="color:var(--ink-3)"><td>日期</td><td style="text-align:right">合計</td><td style="text-align:right">外資</td><td style="text-align:right">投信</td><td style="text-align:right">自營商</td></tr>`+
      rows.map(h=>`<tr><td>${md(h.date)}</td>${c(h.total_net_lots)}${c(h.foreign_net_lots)}${c(h.trust_net_lots)}${c(h.dealer_net_lots)}</tr>`).join('')+'</table>';
    const lastH=history[history.length-1],last=lastH&&lastH.total_net_amt!=null?lastH:null;
    const amt=last?`<div style="margin-top:6px">${md(last.date)} 金額：外資 ${_instFmt(last.foreign_net_amt,'amt')}、投信 ${_instFmt(last.trust_net_amt,'amt')}、自營商 ${_instFmt(last.dealer_net_amt,'amt')}（自行買賣 ${_instFmt(last.dealer_self_net_amt,'amt')}、避險 ${_instFmt(last.dealer_hedge_net_amt,'amt')}）</div>`:'';
    return `<details><summary style="cursor:pointer;font-size:11px;color:var(--accent)">看細節</summary>`+
      `<div class="note" style="margin-top:4px">淨買賣張數（上市，不含權證／牛熊證；外資含外資自營商；來源：證交所 T86）</div>${tb}${amt}`+
      (last?'<div class="note" style="margin-top:4px">金額口徑（BFI82U）含權證、外資不含外資自營商（已計入自營商），與張數口徑不同，兩者不能直接相除換算均價。</div>':'')+
      '</details>';
  }
  async function loadInstTotal(){
    const el=document.getElementById('inst-bars');if(!el)return;
    await loadMarketDataFiles();
    const history=(MARKET_TW_CACHE&&MARKET_TW_CACHE.institutional_history)||[];
    if(!history.length){el.innerHTML='<div class="note">查無資料</div>';return}
    const hasAmt=history.some(h=>h.total_net_amt!=null);
    const unit=((INST_UNIT||'amt')==='amt'&&hasAmt)?'amt':'lots';
    const sw=document.getElementById('inst-unit');
    if(sw){
      const chip=(k,lb,dis)=>`<span class="press" ${dis?'aria-disabled="true"':`onclick="setInstUnit('${k}')"`} style="padding:2px 9px;border-radius:12px;font-size:11px;border:1px solid ${unit===k?'var(--accent)':'var(--hairline)'};color:${dis?'var(--ink-4)':(unit===k?'var(--accent)':'var(--ink-3)')};${dis?'cursor:not-allowed':'cursor:pointer'}">${lb}</span>`;
      sw.innerHTML=chip('lots','張',false)+chip('amt','億元',!hasAmt)+(hasAmt?'':'<span class="note" style="margin:0 0 0 6px;font-size:10px">億元：待接官方金額資料</span>');
    }
    const nets=history.map(h=>({date:h.date,net:unit==='amt'?h.total_net_amt:h.total_net_lots})).filter(n=>n.net!=null);
    const mx=Math.max(...nets.map(n=>Math.abs(n.net)))||1;
    el.innerHTML=nets.map((n,i)=>divBarHTML(n.date.slice(4,6)+'/'+n.date.slice(6,8),n.net,mx,i===nets.length-1?_instFmt(n.net,unit).replace(/ (張|億)$/,''):'')).join('');
    // 先.一〇五-5：最新一根的數值標籤若跟相鄰柱子（含柱子所在欄位）重疊，就改放到圖表右上角
    requestAnimationFrame(()=>{try{
      const v=el.querySelector('.db-val');if(!v)return;
      const vr=v.getBoundingClientRect(),cols=[...el.querySelectorAll('.db')];
      const hit=cols.slice(0,-1).some(c=>{const b=c.querySelector('i.u,i.dn');if(!b)return false;const r=b.getBoundingClientRect();
        return vr.left<r.right&&r.left<vr.right&&vr.top<r.bottom&&r.top<vr.bottom});
      const wide=cols.length&&vr.width>cols[cols.length-1].getBoundingClientRect().width+2;
      if(hit||wide){el.classList.add('val-corner');v.classList.add('at-corner')}else{el.classList.remove('val-corner')}
    }catch(e){console.warn('[instBarLabel]',e)}});
    const todayNet=nets[nets.length-1].net;
    const te=document.getElementById('inst-today');
    te.textContent=_instFmt(todayNet,unit);te.style.color=todayNet>=0?'var(--up)':'var(--down)';
    const un=document.getElementById('inst-unit-note');
    if(un)un.textContent=unit==='amt'?'單位：億元（上市，含權證；外資不含外資自營商）；來源：證交所三大法人買賣金額統計（BFI82U）':'單位：張（上市，不含權證）；來源：證交所 T86';
    const dt=document.getElementById('inst-detail');
    if(dt)dt.innerHTML=_instDetailHTML(history);
    document.getElementById('inst-datatime').textContent=fmtMarketDataTime(MARKET_TW_CACHE)+(history.length<5?`（累積中，目前${history.length}天）`:'');
    // 2026-09-02新增：市場頁「籌碼」精簡入口卡（#chips-entry-inst）跟這裡是
    // 同一份資料的兩種呈現，不重新fetch，直接複寫同樣的文字/顏色。
    const ee=document.getElementById('chips-entry-inst');
    if(ee){ee.textContent=te.textContent;ee.style.color=te.style.color}
  }
  // 先.五十三-A2：主數字、三條線、圖表、入口卡一律用對齊籌碼K的 ratio_pct_ck；沒有 ck（校準檔缺失）才退回本站原值
  function marginVal(h){return h&&h.ratio_pct_ck!=null?h.ratio_pct_ck:(h?h.ratio_pct:null)}
  function marginChart(history){
    const pts=history.filter(h=>marginVal(h)!=null);
    if(!pts.length)return '<div class="note">查無可畫的維持率數字</div>';
    const vals=pts.map(h=>marginVal(h));
    const ymin=Math.min(100,Math.floor(Math.min(...vals)/10)*10-10);
    const ymax=Math.max(220,Math.ceil(Math.max(...vals)/10)*10+10);
    const W=320,H=110,pad=4,n=pts.length;
    const y=v=>(H-pad)-(v-ymin)/(ymax-ymin)*(H-2*pad);
    const x=i=>n<=1?W/2:(i/(n-1))*(W-2*pad)+pad;
    const band=(v,color)=>v<ymin||v>ymax?'':`<line x1="0" y1="${y(v).toFixed(1)}" x2="${W}" y2="${y(v).toFixed(1)}" stroke="${color}" stroke-width="1" stroke-dasharray="3,3" opacity=".65"/>`;
    const lineEls=n>=2
      ?`<polyline points="${pts.map((h,i)=>`${x(i).toFixed(1)},${y(marginVal(h)).toFixed(1)}`).join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"/>`
      :`<circle cx="${W/2}" cy="${y(marginVal(pts[0])).toFixed(1)}" r="4" fill="var(--accent)"/>`;
    const lastX=x(n-1).toFixed(1),lastY=y(marginVal(pts[n-1])).toFixed(1);
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%">
      ${band(160,'var(--warn)')}${band(150,'var(--serious)')}${band(130,'var(--critical)')}
      ${lineEls}<circle cx="${lastX}" cy="${lastY}" r="3.5" fill="var(--accent)"/>
    </svg>${n===1?'<div class="note" style="margin-top:2px">目前只有一天資料，趨勢線會隨每日累積增加</div>':''}`;
  }
  // 2026-10-08（先.五十二）：資料日＝分子分母共同的日期（不是抓取日）；舊紀錄沒有分母日期欄位時退回紀錄日。
  function marginDataDay(h){return (h&&(h.margin_money_date||h.finmind_margin_money_date||h.date))||'—'}
  async function _marginJson(url){const r=await fetch(url+'?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
  async function loadMarginMaintenance(){
    const sumEl=document.getElementById('margin-summary'),chartEl=document.getElementById('margin-chart'),noteEl=document.getElementById('margin-note');
    if(!sumEl)return;
    const [hR,cR,bR]=await Promise.allSettled([_marginJson('data/margin_maintenance.json'),_marginJson('data/margin_ratio_calibration.json'),_marginJson('research/data/margin_backfill.json')]);
    if(hR.status==='rejected'){console.warn('[loadMarginMaintenance]',hR.reason);recordGlobalError('loadMarginMaintenance',hR.reason)}
    if(cR.status==='rejected')console.warn('[loadMarginMaintenance:calibration]',cR.reason);
    if(bR.status==='rejected')console.warn('[loadMarginMaintenance:backfill]',bR.reason);
    const history=hR.status==='fulfilled'&&Array.isArray(hR.value)?hR.value:[];
    const calib=cR.status==='fulfilled'?cR.value:null;
    const bf=bR.status==='fulfilled'?bR.value:null;
    if(!history.length){
      sumEl.innerHTML='<div class="note">查無資料（每日計算尚未產生歷史）</div>';
      if(chartEl)chartEl.innerHTML='';
      return;
    }
    const valid=history.filter(h=>!h.data_incomplete&&h.ratio_pct!=null);
    const last=history[history.length-1],prev=valid[valid.length-1];
    // 先.五十三-A2／A3：k、N、最大誤差都從校準檔讀（不寫死）；warn 時只降級成「校準待更新」警告，不隱藏數字
    const k=calib&&typeof calib.k==='number'?calib.k:(calib&&typeof calib.ratio_mean==='number'?calib.ratio_mean:null);
    const calHead=calib&&k!=null
      ?`<div class="note" id="margin-calib" style="margin-top:2px">對齊籌碼K（${calib.mode==='linear'&&typeof calib.alpha==='number'&&typeof calib.beta==='number'
          ?`線性換算＝本站 × ${calib.beta} ${calib.alpha<0?'−':'＋'} ${Math.abs(calib.alpha)}`
          :`係數 ${k}${calib.mode==='segmented'?'，依水位分段校準':''}`}，近 ${calib.n_points!=null?calib.n_points:calib.n_days} 日最大誤差 ${calib.max_err_pp!=null?calib.max_err_pp:'?'} pp）</div>`
        // 先.一〇五-7：誤差警語合併成一行（原本「校準值…誤差最大…」與「校準待更新…」兩行）；校準值留在這一行，仍不隱藏數字（先.五十三-A）
        +(calib.warn?`<div class="note" id="margin-calib-warn" style="color:var(--warn);margin-top:2px">⚠ 校準待更新：誤差 ±${calib.max_err_pp!=null?calib.max_err_pp:'?'} pp，${(()=>{const v=marginVal(history[history.length-1]);return v!=null?v.toFixed(1)+'%':'—'})()} 僅供參考</div>`:'')
      :'<div class="note" style="color:var(--warn)">校準檔讀取失敗，以下為本站算法原值</div>';
    const raw=h=>h&&h.ratio_pct_ck!=null&&h.ratio_pct!=null?`<div class="note" id="margin-raw" style="color:var(--ink-4);margin-top:2px">本站原值 ${h.ratio_pct.toFixed(1)}%</div>`:'';
    const fmt=h=>{const v=marginVal(h);return v!=null?v.toFixed(1)+'%':'—'};
    if(last.data_incomplete){
      sumEl.innerHTML=`<div style="padding:6px 0 10px"><div style="font-size:20px;font-weight:700;color:var(--warn)">資料不完整</div><div class="note">資料日 ${marginDataDay(last)}：${last.incomplete_reason||'分子分母不同天或取得失敗，不相除'}</div>`
        +(prev?`<div class="note" style="margin-top:4px">上一筆有效：資料日 ${marginDataDay(prev)}　${fmt(prev)}</div>${raw(prev)}`:'<div class="note">尚無有效的上一筆</div>')+calHead+`</div>`;
    }else{
      const lv=marginLevel(marginVal(last));
      // 先.一〇四-9：校準誤差超過門檻（warn 或最大誤差 > warn_pp）→ 不給假精確的一位小數，改「約 低–高%」（±最大誤差、取整）、字級降一級
      const _v=marginVal(last),_err=calib&&typeof calib.max_err_pp==='number'?calib.max_err_pp:null;
      const _fuzzy=_v!=null&&_err!=null&&(calib.warn||_err>(calib.warn_pp!=null?calib.warn_pp:0.5));
      const mainTxt=_fuzzy?`約 ${Math.floor(_v-_err)}–${Math.ceil(_v+_err)}%`:fmt(last);
      sumEl.innerHTML=`<div style="padding:6px 0 10px"><div id="margin-main" data-fuzzy="${_fuzzy?1:0}" title="${_fuzzy?'校準值 '+fmt(last)+'，誤差最大 ±'+_err+' pp':''}" style="font-size:${_fuzzy?22:28}px;font-weight:700;color:${lv?lv.c:'var(--ink)'}">${mainTxt}</div>${_fuzzy&&!(calib&&calib.warn)?`<div class="note" id="margin-ck-val" style="margin-top:0">校準值 ${fmt(last)}（誤差最大 ±${_err} pp，數字僅供參考）</div>`:''}<div class="note">${lv?lv.l+' · ':''}資料日 ${marginDataDay(last)}</div>${calHead}${raw(last)}</div>`;
    }
    let chartHtml=marginChart(valid);
    try{
      const bv=bf&&Array.isArray(bf.records)?bf.records.filter(r=>!r.data_incomplete&&marginVal(r)!=null):[];
      if(bv.length){
        const lv_=o=>o&&marginVal(o)!=null?marginVal(o).toFixed(1)+'%':null;
        const lo=lv_(bf.low_2025_04)?`2025-04 股災最低 ${lv_(bf.low_2025_04)}（${bf.low_2025_04.date}）`:'';
        const lo24=lv_(bf.low_2024_08)?`；2024-08 最低 ${lv_(bf.low_2024_08)}（${bf.low_2024_08.date}）`:'';
        // 先.五十五 分段校準後狀態字串帶原因（例：校準未驗證（低於實測最低水位 156.7%））→ 用 startsWith
        const unvN=bv.filter(r=>String(r.ck_status||'').startsWith('校準未驗證')).length,unv=unvN>0;
        chartHtml+=`<div class="note" style="margin-top:8px">歷史回補（對齊籌碼K換算，2024-07～08、2025-03～05，${bv.length} 天）</div>${marginChart(bv)}<div class="note" id="margin-crash-low" style="color:var(--serious)">${lo}${lo24}</div>`
          +(unv?'<div class="note" id="margin-crash-unverified" style="color:var(--warn)">⚠ 股災段換算「校準未驗證」（'+unvN+' 天）：分段係數只用 2026-07～10 的籌碼K讀數校準，實測最低水位約 156.7%，更低的股災水位尚無讀數可驗證</div>':'');
      }
    }catch(e){console.warn('[loadMarginMaintenance:backfill-chart]',e);recordGlobalError('loadMarginMaintenance:backfill-chart',e)}
    if(chartEl)chartEl.innerHTML=chartHtml;
    if(noteEl)noteEl.textContent=`本站算法：上市（TWSE）全部可融資證券（含 ETF）同一天的「逐股融資餘額 × 收盤 × 1000 ÷ 融資金額」（皆 TWSE 官方，累積 ${history.length} 天）。此公式與愛玩股、FinLab 公開的標準公式相同；FinLab 的分母另外加計上櫃。主數字已換算成對齊籌碼K的口徑（本站原值 × 係數 k，k 由總司令提供的籌碼K讀數與同日本站原值重算，差異原因尚未查明），灰字附本站原值；160／150／130 三條線與圖表都用換算後數字。分子分母不同天時一律標「資料不完整」、不相除；日期一律為資料日。`;
    const ee=document.getElementById('chips-entry-margin');
    if(ee){
      if(last.data_incomplete){ee.textContent='資料不完整'+(prev&&marginVal(prev)!=null?'（上一筆 '+marginVal(prev).toFixed(1)+'%）':'');ee.style.color='var(--warn)'}
      else{const lv=marginLevel(marginVal(last));const mm=document.getElementById('margin-main');  // 先.一〇四-9：入口卡跟主數字同一種寫法
        ee.textContent=(mm&&mm.dataset.fuzzy==='1'?'約 ':'')+(marginVal(last)!=null?marginVal(last).toFixed(1)+'%':'—')+(lv?'·'+lv.l:'');ee.style.color=lv?lv.c:'var(--ink)'}
    }
  }

  // 2026-09-02新增：市場籌碼總覽頁（scr-chips-market）進來時重新確保資料
  // 新鮮——loadInstTotal()/loadMarginMaintenance()本來就會在市場頁載入時
  // 跑過一次（用來填精簡入口卡），這裡重跑一次是防呆（例如使用者長時間
  // 停留在市場頁很久才點進籌碼總覽，或未來有深連結直接進這頁的情境），
  // market_tw.json有快取不會重打，margin_maintenance.json本來就很小，
  // 重新抓一次成本可忽略。
  async function loadChipsMarketDetail(){
    await Promise.allSettled([loadInstTotal(),loadMarginMaintenance()]);
  }

  // 先.八十一-10：主來源改為 repo 的 data/futures_institutional.json（.github/scripts/fetch_futures_institutional.py，
  // TAIFEX 官方三大法人-區分各期貨契約，每日三班排程）；讀不到或沒有台指期才退回 FinMind，兩者都失敗寫明原因。
  const setFut=(id,v)=>{const el=document.getElementById(id);if(!el)return;el.textContent=(v>=0?'+':'')+nf(v)+' 口';el.className=v>=0?'pos':'neg'};
  async function loadFutInst(){
    let repoErr='';
    try{
      const r=await fetch('data/futures_institutional.json?t='+Math.floor(Date.now()/600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const h=((d&&d.history)||[]).slice(-1)[0];
      const tx=h&&h.products&&h.products.TX;
      if(!tx)throw new Error('檔案裡沒有台指期（TX）資料');
      const v=k=>(tx[k]&&tx[k].net_oi)||0;
      setFut('fut-foreign',v('foreign'));setFut('fut-trust',v('trust'));setFut('fut-dealer',v('dealer'));setFut('fut-total',v('foreign')+v('trust')+v('dealer'));
      setTxt('fut-note',`最新 ${h.date} · 台指期未平倉淨口數 · 來源：期交所官方（repo 排程）`);
      return;
    }catch(e){repoErr=String(e&&e.message||e);console.warn('[loadFutInst:repo]',e);recordGlobalError('loadFutInst:repo',e)}
    const raw=await fm('TaiwanFuturesInstitutionalInvestors','TX',_d(10));
    if(!raw.length){
      ['fut-foreign','fut-trust','fut-dealer','fut-total'].forEach(id=>setTxt(id,'—'));
      setTxt('fut-note',`無法取得期貨法人部位：repo 檔讀取失敗（${repoErr}）；FinMind 補充${FM_LAST_FAILED?'也失敗（'+(FM_LAST_ERR||'原因不明')+'）':'查無資料'}`);
      return;
    }
    const last=raw[raw.length-1].date;
    let f=0,t=0,d=0;
    raw.filter(r=>r.date===last).forEach(r=>{
      const net=(r.long_open_interest_balance_volume||0)-(r.short_open_interest_balance_volume||0);
      if(r.institutional_investors==='外資')f=net;else if(r.institutional_investors==='投信')t=net;else if(r.institutional_investors==='自營商')d=net;
    });
    setFut('fut-foreign',f);setFut('fut-trust',t);setFut('fut-dealer',d);setFut('fut-total',f+t+d);
    setTxt('fut-note',`最新 ${last} · FinMind 期貨三大法人（TX）（repo 檔讀取失敗：${repoErr}，改用 FinMind 補充）`);
  }
  // 常備.開發-14（2026-10-11）盤勢解讀（規則版）：四行只把既有檔案的數字翻成白話——
  // ①大盤漲跌（market_tw.json taiex）②類股強弱前三（market_tw.json sectors 依漲跌幅排序，最強／最弱各三）
  // ③法人合計（market_tw.json institutional_history 最新一日；有 BFI82U 金額報億元，否則張，同籌碼頁）
  // ④融資維持率水位（margin_maintenance.json，與籌碼頁同一套 marginVal／marginLevel 對齊籌碼K口徑與分級）。
  // 不下「偏多／偏空」結論；查不到的寫「查無」與查了哪個檔。
  function buildMarketReadLines({mkt,margin}){
    const out=[];
    const pct=x=>(x>=0?'+':'')+(+x).toFixed(2)+'%';
    const lots=x=>(x>=0?'買超 ':'賣超 ')+nf(Math.round(Math.abs(x)))+' 張';
    const yi=x=>(x>=0?'買超 ':'賣超 ')+Math.abs(x).toLocaleString('zh-TW',{maximumFractionDigits:1,minimumFractionDigits:1})+' 億元';
    try{
      const t=mkt&&mkt.taiex;
      if(!t||t.close==null||t.change_pct==null)out.push('大盤：查無加權指數收盤（data/market_tw.json）');
      else{const dt=(t.sparkline_dates||[]).slice(-1)[0];out.push(`大盤：加權指數${dt?'（'+dt+' 收盤）':''} ${nf(t.close)}，${t.change_pct>0?'上漲':t.change_pct<0?'下跌':'平盤'} ${pct(t.change_pct)}`)}
    }catch(e){console.warn('[marketRead:taiex]',e);recordGlobalError('marketRead:taiex',e);out.push('大盤：計算失敗（已記入診斷 log）')}
    try{
      const ss=((mkt&&mkt.sectors)||[]).filter(x=>x&&x.name&&typeof x.change_pct==='number');
      if(ss.length<3)out.push('類股：查無足夠類股指數（data/market_tw.json sectors 不足 3 類）');
      else{
        const srt=ss.slice().sort((a,b)=>b.change_pct-a.change_pct);
        const nm=x=>String(x.name).replace(/類指數$/,'');
        const f=a=>a.map(x=>nm(x)+' '+pct(x.change_pct)).join('、');
        out.push(`類股（${ss.length} 類指數）：最強 ${f(srt.slice(0,3))}；最弱 ${f(srt.slice(-3).reverse())}`);
      }
    }catch(e){console.warn('[marketRead:sector]',e);recordGlobalError('marketRead:sector',e);out.push('類股：計算失敗（已記入診斷 log）')}
    try{
      const h=((mkt&&mkt.institutional_history)||[]).slice(-1)[0];
      if(!h||h.total_net_lots==null)out.push('法人：查無三大法人全市場合計（data/market_tw.json institutional_history）');
      else{const d=String(h.date||'');const md=d.length===8?d.slice(4,6)+'/'+d.slice(6):d;
        // 先.一〇三-1b-1：有 BFI82U 金額就報億元（張數在籌碼總覽「看細節」）
        if(h.total_net_amt!=null)out.push(`法人（${md}）：三大法人合計${yi(h.total_net_amt)}（外資${yi(h.foreign_net_amt||0)}、投信${yi(h.trust_net_amt||0)}、自營商${yi(h.dealer_net_amt||0)}）`);
        else out.push(`法人（${md}）：三大法人合計${lots(h.total_net_lots)}（外資${lots(h.foreign_net_lots||0)}、投信${lots(h.trust_net_lots||0)}、自營商${lots(h.dealer_net_lots||0)}）`)}
    }catch(e){console.warn('[marketRead:inst]',e);recordGlobalError('marketRead:inst',e);out.push('法人：計算失敗（已記入診斷 log）')}
    try{
      const hs=Array.isArray(margin)?margin:[];
      const last=hs[hs.length-1];
      const valid=hs.filter(h=>!h.data_incomplete&&marginVal(h)!=null);
      const use=last&&!last.data_incomplete&&marginVal(last)!=null?last:valid[valid.length-1];
      if(!use)out.push('融資維持率：查無有效數字（data/margin_maintenance.json）');
      else{
        const v=marginVal(use),lv=marginLevel(v);
        const prev=valid[valid.indexOf(use)-1];
        const dlt=prev&&marginVal(prev)!=null?v-marginVal(prev):null;
        out.push(`融資維持率：${v.toFixed(1)}%（${lv?lv.l:''}，160／150／130 為注意／危險／斷頭線；資料日 ${marginDataDay(use)}${dlt!=null?'，較前一筆'+(dlt>=0?'+':'')+dlt.toFixed(1)+' 個百分點':''}）`+(use!==last?'；最新一筆資料不完整，改列上一筆有效值':''));
      }
    }catch(e){console.warn('[marketRead:margin]',e);recordGlobalError('marketRead:margin',e);out.push('融資維持率：計算失敗（已記入診斷 log）')}
    return out;
  }
  async function loadMarketBrief(){
    const el=document.getElementById('market-brief-body');if(!el)return;
    const [dR,,mR]=await Promise.allSettled([loadDailyBrief(),loadMarketDataFiles(),_marginJson('data/margin_maintenance.json')]);
    if(mR.status==='rejected'){console.warn('[loadMarketBrief:margin]',mR.reason);recordGlobalError('loadMarketBrief:margin',mR.reason)}
    let html='';
    try{html+='<div style="font-weight:600;margin-bottom:2px">盤勢解讀</div>'+_briefLines(buildMarketReadLines({mkt:MARKET_TW_CACHE,margin:mR.status==='fulfilled'?mR.value:null}))}
    catch(e){console.warn('[loadMarketBrief:read]',e);recordGlobalError('loadMarketBrief:read',e);html+='<div>盤勢解讀計算失敗（'+_autoEsc(e&&e.message||e)+'）</div>'}
    if(dR.status==='fulfilled'){const d=dR.value;html+='<div style="font-weight:600;margin:6px 0 2px">盤前資訊</div>'+_briefLines(d.premarket&&d.premarket.lines,d.premarket&&d.premarket.line_dates,d.premarket&&d.premarket.line_markets)+_briefFoot(d)}
    else{console.warn('[loadMarketBrief]',dR.reason);recordGlobalError('loadMarketBrief',dR.reason);html+='<div>讀取盤前資訊失敗（'+_autoEsc(dR.reason&&dR.reason.message||dR.reason)+'）</div><div style="margin-top:6px;font-size:10px;color:var(--ink-4)">規則摘要，非 AI 判斷、非投資建議</div>'}
    el.innerHTML=html;
  }
  async function loadMarketUS(){
    const el=document.getElementById('us-idx-rows');if(!el)return;
    const usIdx=await loadUsIndexes();
    el.innerHTML=usIdx.map(r=>r.html).join('');
    document.getElementById('us-idx-datatime').textContent=fmtMarketDataTime(MARKET_US_CACHE);
    // 2026-09-10（建置一.3）美股類股/ADR溢價各自獨立try/catch（用allSettled，
    // 不用all）——其中一張卡失敗不能拖垮已經渲染好的美股指數，見CLAUDE.md
    // 「App穩定性與錯誤隔離原則」。
    const subResults=await Promise.allSettled([loadMarketUsSector(),loadMarketAdrPremium(),loadMarketCftcCot(),loadMarketBlsMacro()]);
    const subLabels=['loadMarketUsSector','loadMarketAdrPremium','loadMarketCftcCot','loadMarketBlsMacro'];
    subResults.forEach((r,i)=>{if(r.status==='rejected'){console.warn('['+subLabels[i]+']',r.reason);recordGlobalError(subLabels[i],r.reason)}});
  }
  // 2026-09-15（源頭二.3第8名）美國總經指標（BLS），market-us-panel卡片。
  let BLS_MACRO_CACHE=null;
  async function loadMarketBlsMacro(){
    const el=document.getElementById('bls-macro-rows');if(!el)return;
    if(!BLS_MACRO_CACHE){
      try{const r=await fetch('data/bls_macro.json?t='+Date.now());if(r.ok)BLS_MACRO_CACHE=await r.json()}
      catch(e){console.warn('[loadMarketBlsMacro]',e);recordGlobalError('loadMarketBlsMacro',e)}
    }
    const d=BLS_MACRO_CACHE;
    const rows=[['unemployment_rate','失業率'],['cpi_u','CPI年增率'],['nonfarm_payrolls','非農就業(月增)']];
    if(!d||!d.series){
      el.innerHTML=rows.map(([,label])=>`<div class="f"><span>${label}</span><b style="font-weight:400;font-size:12px;color:var(--ink-3)">查無資料</b></div>`).join('');
      document.getElementById('bls-macro-datatime').textContent='';
      return;
    }
    let latestDate=null;
    el.innerHTML=rows.map(([key,label])=>{
      const s=d.series[key];
      if(!s||s.latest_value==null)return `<div class="f"><span>${label}</span><b style="font-weight:400;font-size:12px;color:var(--ink-3)">查無資料</b></div>`;
      if(!latestDate||s.latest_date>latestDate)latestDate=s.latest_date;
      let valTxt;
      if(key==='unemployment_rate')valTxt=s.latest_value.toFixed(1)+'%'+(s.change_mom!=null?`（${s.change_mom>=0?'+':''}${s.change_mom.toFixed(1)}pp）`:'');
      else if(key==='cpi_u')valTxt=s.yoy_pct!=null?(s.yoy_pct>=0?'+':'')+s.yoy_pct.toFixed(1)+'%':'資料不足無法計算';
      else valTxt=s.change_mom!=null?(s.change_mom>=0?'+':'')+nf(Math.round(s.change_mom))+'千人':'—';
      const cls=key==='unemployment_rate'?(s.change_mom>0?'neg':(s.change_mom<0?'pos':'')):(key==='cpi_u'?(s.yoy_pct>3?'neg':''):(s.change_mom>=0?'pos':'neg'));
      return `<div class="f"><span>${label}</span><b class="${cls}">${valTxt}</b></div>`;
    }).join('');
    document.getElementById('bls-macro-datatime').textContent=latestDate?`資料日 ${latestDate}（BLS官方月頻統計）`:'';
  }
  // 2026-09-15（源頭二.3第3名）CFTC COT投機客淨部位，market-us-panel卡片。
  let CFTC_COT_CACHE=null;
  async function loadMarketCftcCot(){
    const el=document.getElementById('cftc-cot-rows');if(!el)return;
    if(!CFTC_COT_CACHE){
      try{const r=await fetch('data/cftc_cot.json?t='+Date.now());if(r.ok)CFTC_COT_CACHE=await r.json()}
      catch(e){console.warn('[loadMarketCftcCot]',e);recordGlobalError('loadMarketCftcCot',e)}
    }
    const d=CFTC_COT_CACHE;
    const contracts=[['sp500','S&P 500'],['nasdaq100','NASDAQ-100'],['vix','VIX期貨']];
    if(!d||!d.contracts){
      el.innerHTML=contracts.map(([,label])=>`<div class="f"><span>${label}</span><b style="font-weight:400;font-size:12px;color:var(--ink-3)">查無資料</b></div>`).join('');
      document.getElementById('cftc-cot-datatime').textContent='';
      return;
    }
    let latestDate=null;
    el.innerHTML=contracts.map(([key,label])=>{
      const c=d.contracts[key];const hist=c&&c.history;
      if(!hist||!hist.length)return `<div class="f"><span>${label}</span><b style="font-weight:400;font-size:12px;color:var(--ink-3)">查無資料</b></div>`;
      const last=hist[hist.length-1];
      if(!latestDate||last.date>latestDate)latestDate=last.date;
      const prev=hist.length>1?hist[hist.length-2]:null;
      const chg=prev?last.net-prev.net:null;
      const cls=last.net>=0?'pos':'neg';
      const chgTxt=chg==null?'':`（較上週${chg>=0?'+':''}${nf(chg)}）`;
      return `<div class="f"><span>${label}</span><b class="${cls}">${last.net>=0?'+':''}${nf(last.net)}${chgTxt}</b></div>`;
    }).join('');
    document.getElementById('cftc-cot-datatime').textContent=latestDate?`資料日 ${latestDate}（CFTC每週二資料，當週五公布）`:'';
  }
  // ── 2026-09-10（建置一.3）美股類股（SEC SIC對映）／ADR溢價 ──
  async function loadUsSicAdrFiles(force){
    if(force||!US_SIC_CACHE){
      try{const r=await fetch('data/us_sic.json?t='+Date.now());if(r.ok)US_SIC_CACHE=await r.json()}catch(e){console.warn('[loadUsSicAdrFiles:sic]',e);recordGlobalError('loadUsSicAdrFiles:sic',e)}
    }
    if(force||!ADR_PREMIUM_CACHE){
      try{const r=await fetch('data/adr_premium.json?t='+Date.now());if(r.ok)ADR_PREMIUM_CACHE=await r.json()}catch(e){console.warn('[loadUsSicAdrFiles:adr]',e);recordGlobalError('loadUsSicAdrFiles:adr',e)}
    }
  }
  function usSectorRowHtml(ticker,sicInfo,quote){
    // 2026-09-10：優先用SEC EDGAR自己回傳的entity_name（跟SIC同一個CIK來源，
    // 短且乾淨）；STOCKNAME_US（FinMind USStockInfo）少數ADR名稱會夾帶完整
    // 股權說明（例如ASX會變成一長串「American Depositary Shares (each
    // representing Two Common Shares)」），沒有SIC資料時才退回nameOf()。
    const nm=(sicInfo&&sicInfo.entity_name)||nameOf(ticker);
    const label=nm&&nm!==ticker?`${ticker}（${nm}）`:ticker;
    const sector=sicInfo&&sicInfo.sic_description?`${sicInfo.sic_description}（SIC ${sicInfo.sic}）`:'尚無SIC資料（排程抓取中或該檔查無對映）';
    if(!quote||quote.price==null)return `<div class="row" style="cursor:default"><div class="nm"><b>${label}</b><span>${sector}</span></div><div class="px"><b>—</b><span>查無報價</span></div></div>`;
    const pct=quote.change_pct;const cls=pct==null?'':(pct>=0?'pos':'neg');
    const pctTxt=pct==null?'—':`${pct>=0?'+':''}${pct.toFixed(2)}%`;
    return `<div class="row" style="cursor:default"><div class="nm"><b>${label}</b><span>${sector}</span></div><div class="px"><b>$${nf(quote.price)}</b><span class="${cls}">${pctTxt}</span></div></div>`;
  }
  async function loadMarketUsSector(){
    const el=document.getElementById('us-sector-rows');if(!el)return;
    if(!INTRADAY_US)await loadIntradayQuotes();
    await loadUsSicAdrFiles();
    const sicMap=(US_SIC_CACHE&&US_SIC_CACHE.tickers)||{};
    const quotes=(INTRADAY_US&&INTRADAY_US.quotes)||{};
    const tickers=Array.from(new Set([...Object.keys(sicMap),...Object.keys(quotes)]));
    if(!tickers.length){el.innerHTML='<div class="note">尚無資料（SEC SIC 對映與美股報價都還沒抓到）</div>';document.getElementById('us-sector-datatime').textContent='';return}
    // 同產業（SIC說明）排在一起，查無SIC的排最後
    const rows=tickers.map(tk=>({tk,sic:sicMap[tk],q:quotes[tk]}))
      .sort((a,b)=>{
        const sa=(a.sic&&a.sic.sic_description)||'￿',sb=(b.sic&&b.sic.sic_description)||'￿';
        return sa===sb?a.tk.localeCompare(b.tk):sa.localeCompare(sb);
      });
    el.innerHTML=rows.map(r=>usSectorRowHtml(r.tk,r.sic,r.q)).join('');
    const sicTime=US_SIC_CACHE&&US_SIC_CACHE.fetched_at?fmtTzMMDDHHMM(new Date(US_SIC_CACHE.fetched_at),'Asia/Taipei'):'查無資料';
    document.getElementById('us-sector-datatime').textContent=`分類資料 ${sicTime}；股價 ${fmtMarketDataTime(INTRADAY_US)}`;
  }
  function adrRowHtml(ticker,row,errReason){
    const nm=row?nameOf(row.tw_code):'';
    const label=nm?`${ticker}（${nm}${row?row.tw_code:''}）`:ticker;
    if(!row)return `<div class="f"><span>${label}</span><b style="font-weight:400;font-size:12px;color:var(--ink-3)">${errReason||'查無資料'}</b></div>`;
    const cls=row.premium_pct>=0?'pos':'neg';
    const pctTxt=`${row.premium_pct>=0?'+':''}${row.premium_pct.toFixed(2)}%`;
    return `<div class="f"><span>${label}</span><b class="${cls}" title="ADR比率1:${row.ratio}／${row.source}">${pctTxt}</b></div>`;
  }
  async function loadMarketAdrPremium(){
    const el=document.getElementById('adr-rows');if(!el)return;
    await loadUsSicAdrFiles();
    const data=ADR_PREMIUM_CACHE;
    const order=['TSM','UMC','ASX','CHT'];
    if(!data){el.innerHTML=order.map(tk=>adrRowHtml(tk,null,'查無資料（尚未排程抓取或抓取失敗）')).join('');document.getElementById('adr-datatime').textContent='';return}
    const errByTk={};(data.errors||[]).forEach(e=>{if(e&&e.ticker)errByTk[e.ticker]=e.reason});
    el.innerHTML=order.map(tk=>adrRowHtml(tk,data.rows&&data.rows[tk],errByTk[tk])).join('');
    document.getElementById('adr-datatime').textContent=data.computed_at
      ?`計算時間 ${fmtTzMMDDHHMM(new Date(data.computed_at),'Asia/Taipei')}（美股 ADR 現價×匯率÷比率，對台股${(()=>{const d=Object.values(data.rows||{}).map(r=>r.tw_quote_date).filter(Boolean).sort().pop();return d?' '+String(d).slice(5).replace('-','/')+' ':''})()}收盤；ADR比率為固定值）`
      :'查無計算時間';
  }
  const FUT_CONTRACTS=[{id:'TX',label:'台指期近月'},{id:'MTX',label:'小型台指期近月'},{id:'TE',label:'電子期近月'},{id:'TF',label:'金融期近月'}];
  async function loadMarketFUT(){
    const el=document.getElementById('fut-quote-rows');if(!el)return;
    await loadMarketDataFiles();
    await ensureSinopacQuotes();
    const tw=MARKET_TW_CACHE||{};
    const futs=tw.futures||{};
    const sources=FUT_CONTRACTS.map(c=>({...c,src:shioajiFutRowSource(c.id,futs[c.id])}));
    el.innerHTML=sources.map(c=>futRowHtml(c.label,c.src.fut,c.src.srcLabel)).join('');
    // 2026-09-04（四修.四）：四檔都走Shioaji即時時，不再寫「資料時間 07:24（GitHub Actions 排程）」
    // 這種跟畫面上數字對不上的時間；改寫即時時間，TAIFEX盤後資料另標收盤日。
    const liveN=sources.filter(s=>s.src&&s.src.srcLabel).length;
    document.getElementById('fut-quote-datatime').textContent=liveN
      ?`Shioaji 即時 ${liveN}/${sources.length} 檔（${INTRADAY_SINOPAC&&INTRADAY_SINOPAC.fetched_at?fmtTzHHMM(new Date(INTRADAY_SINOPAC.fetched_at),'Asia/Taipei'):'—'}）；TAIFEX 盤後資料 ${twCloseDateLabel(tw)}`
      :`${twCloseDateLabel(tw)}｜${fmtMarketDataTime(tw)}`;
    // 正逆價差：近月台指期收盤－加權指數（現貨）收盤——2026-09-01改用跟畫面上
    // 顯示的同一個資料源（Shioaji優先/退回TAIFEX CSV），避免上面卡片顯示
    // Shioaji的數字、下面價差卻用TAIFEX CSV的數字算出不一致的結果。
    const txSrc=sources.find(c=>c.id==='TX'),taiexSrc=taiexRowSource(tw);
    const tx=txSrc&&txSrc.src.fut,taiex=taiexSrc.item;
    // 先.一〇三-2（2026-10-15）：現貨與期貨的資料日不同就不算價差（例：現貨 10/15 收盤對期貨 10/14 收盤會算出假的逆價差）。
    // Shioaji 即時／今日收盤算「今天」；TAIFEX 盤後用 data_date（沒有就用 date 的 YYYYMMDD）。
    const _todayTw=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Taipei'});
    const _ymd=s=>{s=String(s||'');return /^\d{8}$/.test(s)?`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6)}`:s.slice(0,10)};
    const spotDate=taiex?(taiexSrc.srcLabel!=='證交所'?_todayTw:_ymd(taiex.data_date)):'';
    const futDate=tx?(txSrc.src.srcLabel?_todayTw:_ymd(tx.data_date||tx.date)):'';
    const _md=d=>d?d.slice(5).replace('-','/'):'—';
    if(tx&&tx.last!=null&&taiex&&taiex.close!=null&&spotDate&&futDate&&spotDate!==futDate){
      setTxt('basis-spot',nf(taiex.close));setTxt('basis-fut',nf(tx.last));
      document.getElementById('basis-note').textContent=futDate<spotDate
        ?`期貨資料停在 ${_md(futDate)}，現貨是 ${_md(spotDate)}，日期不同無法計算。`
        :`現貨資料停在 ${_md(spotDate)}，期貨是 ${_md(futDate)}，日期不同無法計算。`;
    }else if(tx&&tx.last!=null&&taiex&&taiex.close!=null){
      setTxt('basis-spot',nf(taiex.close));
      setTxt('basis-fut',nf(tx.last));
      const basis=tx.last-taiex.close;
      const bEl=document.getElementById('basis-note');
      bEl.innerHTML=`${basis>=0?'正價差':'逆價差'} <b class="num ${basis>=0?'pos':'neg'}">${basis>=0?'+':''}${nf(basis.toFixed(0))}</b>（期貨－現貨；正價差通常反映市場偏多氣氛，逆價差反映偏空，僅供參考）`;
    }else{
      setTxt('basis-spot','—');setTxt('basis-fut','—');
      document.getElementById('basis-note').textContent='資料不足，無法計算。';
    }
  }
  // 2026-10-08 先.五十一-4：排行榜卡。資料來自本機即時伺服器 /live/scanners（shioaji_quotes.py 每 60 秒查一次），
  // App 端同樣最多 60 秒打一次；沒連線／非盤中誠實顯示原因，不放假資料。
  const SCANNERS={tab:'change_pct_up',data:null,at:0};
  async function loadScanners(){
    const el=document.getElementById('scanners-list'),note=document.getElementById('scanners-note');if(!el)return;
    try{
      if(!LIVE.connected){SCANNERS.data=null;el.innerHTML='<div class="note">連上電腦才看得到（只在盤中更新）</div>';if(note)note.textContent='';return}
      if(!SCANNERS.data||Date.now()-SCANNERS.at>=60000){
        const r=await liveFetch('/live/scanners',5000);if(!r.ok)throw new Error('HTTP '+r.status);
        SCANNERS.data=await r.json();SCANNERS.at=Date.now();
      }
      renderScanners();
    }catch(e){console.warn('[loadScanners]',e);recordGlobalError('loadScanners',e);el.innerHTML='<div class="note">排行榜讀取失敗：'+(e.message||String(e))+'</div>'}
  }
  function setScannerTab(k){SCANNERS.tab=k;_safeSync('renderScanners',renderScanners)}
  function renderScanners(){
    const el=document.getElementById('scanners-list'),note=document.getElementById('scanners-note');if(!el)return;
    document.querySelectorAll('#scanners-tabs [data-sk]').forEach(b=>b.classList.toggle('on',b.dataset.sk===SCANNERS.tab));
    const d=SCANNERS.data;
    if(!d||!d.available){el.innerHTML='<div class="note">'+((d&&d.reason)||'今日尚無排行榜')+'</div>';if(note)note.textContent='';return}
    const rows=(d.lists&&d.lists[SCANNERS.tab])||[];
    const err=d.errors&&d.errors[SCANNERS.tab];
    if(!rows.length){el.innerHTML='<div class="note">此類別本輪未取得'+(err?'：'+err:'')+'</div>'}
    else el.innerHTML=rows.map((r,i)=>{
      const cls=(r.change_pct||0)>=0?'u':'d';
      const pct=r.change_pct==null?'—':((r.change_pct>=0?'+':'')+r.change_pct.toFixed(2)+'%');
      const ext=SCANNERS.tab==='volume'?(' · '+(r.total_volume!=null?Number(r.total_volume).toLocaleString('zh-TW')+' 張':'—'))
        :(SCANNERS.tab==='amount'?(' · '+(r.total_amount!=null?(Number(r.total_amount)/1e8).toFixed(1)+' 億':'—')):'');
      return `<div class="row" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--hairline)" onclick="openStock('${String(r.code||'').replace(/[^0-9A-Za-z]/g,'')}')"><span>${i+1}. ${r.name||''} <span class="note">${r.code||''}</span></span><span class="num ${cls}">${r.close!=null?nf(r.close):'—'} ${pct}<span class="note">${ext}</span></span></div>`;
    }).join('');
    if(note)note.textContent='更新時間 '+(d.generated_at?fmtTzHHMM(new Date(d.generated_at),'Asia/Taipei'):'—')+(err?'（本輪：'+err+'）':'');
  }
  async function hydrateMarket(){
    renderMktToggle('market');
    // 2026-08-27修正：改用Promise.allSettled——Promise.all只要其中一個
    // sub-panel失敗就整個await立刻拋錯，會讓下面stampUpdated/updateDiagBanner
    // 這些後續程式碼整批不執行，變成「一個面板壞掉、其他面板的收尾也跟著壞」。
    // 2026-09-08（金流一.3）產業金流併入同一批 allSettled——它自己有 try/catch，
    // 掛了只影響自己那張卡，不會拖垮其他面板（錯誤隔離原則）。
    const results=await Promise.allSettled([loadMarketIndex(),loadHeatmap(),loadInstTotal(),loadFutInst(),loadMarginMaintenance(),renderSectorFlow(),loadCustomsTrade(),loadIndustrialProduction(),loadScanners(),loadIrEvents(),loadIndustryHeat()]);
    const labels=['loadMarketIndex','loadHeatmap','loadInstTotal','loadFutInst','loadMarginMaintenance','renderSectorFlow','loadCustomsTrade','loadIndustrialProduction','loadScanners','loadIrEvents','loadIndustryHeat'];
    results.forEach((r,i)=>{if(r.status==='rejected'){console.warn('['+labels[i]+']',r.reason);recordGlobalError(labels[i],r.reason)}});
    _safeAsync('loadMarketBrief',loadMarketBrief);  // 常備.開發-2
    if(MKT_STATE.market==='US')_safeAsync('loadMarketUS',loadMarketUS);
    if(MKT_STATE.market==='FUT')_safeAsync('loadMarketFUT',loadMarketFUT);
    stampUpdated('market');
    updateDiagBanner();
  }
  // 2026-09-15（源頭二.3第9名）全國進出口貿易統計，market-tw-panel卡片。
  let CUSTOMS_TRADE_CACHE=null;
  // 先.八十一-20：近期法說會列表（重大訊息公告，官方）。每列：公告日、公司、標題、MOPS 簡報連結（使用者自己點開，不爬取）。
  let IR_EVENTS_CACHE=null;
  async function loadIrEvents(){
    const el=document.getElementById('ir-events-rows');if(!el)return;
    try{
      if(!IR_EVENTS_CACHE){const r=await fetch('data/ir_events.json?t='+Math.floor(Date.now()/600000));if(!r.ok)throw new Error('HTTP '+r.status);IR_EVENTS_CACHE=await r.json()}
      const d=IR_EVENTS_CACHE,ev=(d.events||[]).slice(0,20);
      const esc=t=>String(t==null?'':t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      el.innerHTML=ev.length?ev.map(e=>`<div class="ir-row" style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--hairline);cursor:pointer" onclick="openStock('${esc(e.code)}')">
          <span class="num" style="font-size:10px;color:var(--ink-4);min-width:34px;padding-top:2px">${esc(String(e.date||'').slice(5).replace('-','/'))}</span>
          <span style="flex:1;font-size:12px;color:var(--ink-2);line-height:1.5"><b style="color:var(--ink)">${esc(e.name||'')} ${esc(e.code)}</b>・${esc(e.title)}${e.call_date?`<span style="color:var(--gold)">（${esc(String(e.call_date).slice(5).replace('-','/'))} 舉行）</span>`:''}${mopsIrLinkHtml({type:'法說會',code:e.code},true)}</span></div>`).join('')
        :'<div class="note">近 60 天沒有法說會公告</div>';
      document.getElementById('ir-events-datatime').textContent=`近 60 天共 ${d.count||0} 則${(d.count||0)>20?'，只顯示最近 20 則':''}；左邊日期是重大訊息公告日；公告有寫舉行日的另標「MM/DD 舉行」。簡報 PDF 請點「MOPS簡報」自行開啟（MOPS 不開放程式抓取）。`;
    }catch(e){
      console.warn('[loadIrEvents]',e);recordGlobalError('loadIrEvents',e);
      el.innerHTML='<div class="note">法說會列表載入失敗（'+String(e&&e.message||e).replace(/[&<>]/g,'')+'）</div>';
    }
  }
  // 研究室.五-3（2026-10-15）：產業營收熱度表，讀 research_radar.json 的 industry_heat，依營收年增中位數排序。
  let INDUSTRY_HEAT_CACHE=null;
  async function loadIndustryHeat(){
    const el=document.getElementById('industry-heat-rows');if(!el)return;
    try{
      if(!INDUSTRY_HEAT_CACHE){const r=await fetch('data/research_radar.json?t='+Math.floor(Date.now()/600000));if(!r.ok)throw new Error('HTTP '+r.status);INDUSTRY_HEAT_CACHE=await r.json()}
      const d=INDUSTRY_HEAT_CACHE,meta=d.meta||{};
      const rows=(d.industry_heat||[]).slice().sort((a,b)=>(b.median_rev3_yoy??-1e9)-(a.median_rev3_yoy??-1e9));
      const esc=t=>String(t==null?'':t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      const pct=v=>v==null||!isFinite(v)?'—':(v>=0?'+':'')+(v*100).toFixed(1)+'%';
      const cls=v=>v==null?'':(v>=0?'pos':'neg');
      const th='style="text-align:right;font-weight:500;color:var(--ink-4);padding:4px 2px"';
      const td='class="num" style="text-align:right;padding:4px 2px"';
      el.innerHTML=rows.length?`<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead><tr><th style="text-align:left;font-weight:500;color:var(--ink-4);padding:4px 2px">產業</th><th ${th}>檔數</th><th ${th}>營收年增中位數</th><th ${th}>營收成長家數比</th><th ${th}>20日漲跌中位數</th></tr></thead>
          <tbody>${rows.map(x=>`<tr style="border-top:1px solid var(--hairline)"><td style="padding:4px 2px;color:var(--ink-2)">${esc(x.industry)}</td><td ${td}>${esc(x.n)}</td><td ${td}><span class="${cls(x.median_rev3_yoy)}">${pct(x.median_rev3_yoy)}</span></td><td ${td}>${x.share_rev_up==null?'—':(x.share_rev_up*100).toFixed(0)+'%'}</td><td ${td}><span class="${cls(x.median_ret20)}">${pct(x.median_ret20)}</span></td></tr>`).join('')}</tbody></table></div>`
        :'<div class="note">目前沒有產業營收熱度資料</div>';
      document.getElementById('industry-heat-datatime').textContent=`資料日 ${esc(meta.asof||'—')}；營收年增＝近 3 個月營收合計比去年同期；成長家數比＝該產業近 3 月營收年增 >0 的家數比例。${meta.disclaimer||'變化排序未經回測，不是買賣訊號；非投資建議。'}`;
    }catch(e){
      console.warn('[loadIndustryHeat]',e);recordGlobalError('loadIndustryHeat',e);
      el.innerHTML='<div class="note">產業營收熱度載入失敗（'+String(e&&e.message||e).replace(/[&<>]/g,'')+'）</div>';
    }
  }
  async function loadCustomsTrade(){
    const el=document.getElementById('customs-trade-rows');if(!el)return;
    if(!CUSTOMS_TRADE_CACHE){
      try{const r=await fetch('data/customs_trade.json?t='+Date.now());if(r.ok)CUSTOMS_TRADE_CACHE=await r.json()}
      catch(e){console.warn('[loadCustomsTrade]',e);recordGlobalError('loadCustomsTrade',e)}
    }
    const d=CUSTOMS_TRADE_CACHE;
    if(!d||!d.latest){
      el.innerHTML='<div class="note">查無資料</div>';
      document.getElementById('customs-trade-datatime').textContent='';
      return;
    }
    const toYi=v=>(v/1e6).toFixed(1)+'億元'; // 原始單位新臺幣千元，除以1,000,000換算成億元
    const yoy=d.yoy;
    const balCls=d.latest.trade_balance>=0?'pos':'neg';
    el.innerHTML=[
      `<div class="f"><span>出口總值</span><b>${toYi(d.latest.export_total)}${yoy&&yoy.export_yoy_pct!=null?`（YoY ${yoy.export_yoy_pct>=0?'+':''}${yoy.export_yoy_pct.toFixed(1)}%）`:''}</b></div>`,
      `<div class="f"><span>進口總值</span><b>${toYi(d.latest.import_total)}${yoy&&yoy.import_yoy_pct!=null?`（YoY ${yoy.import_yoy_pct>=0?'+':''}${yoy.import_yoy_pct.toFixed(1)}%）`:''}</b></div>`,
      `<div class="f"><span>出入超（貿易${d.latest.trade_balance>=0?'順':'逆'}差）</span><b class="${balCls}">${d.latest.trade_balance>=0?'+':''}${toYi(d.latest.trade_balance)}</b></div>`,
    ].join('');
    // 先.八十一-14：抓取每天三班都成功，資料月落後是官方開放資料檔本身更新慢（新聞稿較早、開放資料檔較晚），畫面寫明原因與落後月數
    document.getElementById('customs-trade-datatime').textContent=`資料月 ${d.latest.date}${_monthLagTxt(d.latest.date)}（財政部關務署官方開放資料檔本身最新只到這個月；每日排程照常抓取${d.fetched_at?'，最後抓取 '+fmtTzMMDDHHMM(new Date(d.fetched_at),'Asia/Taipei'):''}）`;
  }
  // 2026-09-15（源頭二.3第10名）工業生產指數，market-tw-panel卡片。
  // 2026-10-11 常備.開發-21：同檔 export_orders 欄位接外銷訂單總金額（data.gov.tw#101580 地區別總計），缺就誠實顯示未取得。
  let IP_INDEX_CACHE=null;
  async function loadIndustrialProduction(){
    const el=document.getElementById('ip-index-rows');if(!el)return;
    if(!IP_INDEX_CACHE){
      try{const r=await fetch('data/industrial_production.json?t='+Date.now());if(r.ok)IP_INDEX_CACHE=await r.json()}
      catch(e){console.warn('[loadIndustrialProduction]',e);recordGlobalError('loadIndustrialProduction',e)}
    }
    const d=IP_INDEX_CACHE;
    if(!d||!d.latest){
      el.innerHTML='<div class="note">查無資料</div>';
      document.getElementById('ip-index-datatime').textContent='';
      return;
    }
    const mom=d.latest.change_mom_pct,yoy=d.yoy_pct;
    const rows=[
      `<div class="f"><span>生產指數（${d.latest.base_period}）</span><b>${d.latest.value.toFixed(2)}</b></div>`,
      `<div class="f"><span>月增(MoM)</span><b class="${mom==null?'':(mom>=0?'pos':'neg')}">${mom!=null?(mom>=0?'+':'')+mom.toFixed(1)+'%':'資料不足'}</b></div>`,
      `<div class="f"><span>年增(YoY)</span><b class="${yoy==null?'':(yoy>=0?'pos':'neg')}">${yoy!=null?(yoy>=0?'+':'')+yoy.toFixed(1)+'%':'資料不足'}</b></div>`,
    ];
    const eo=d.export_orders;
    const pct=v=>v!=null?(v>=0?'+':'')+v.toFixed(1)+'%':'資料不足';
    const cls=v=>v==null?'':(v>=0?'pos':'neg');
    if(eo&&eo.value!=null){
      rows.push(
        `<div class="f"><span>外銷訂單（${eo.date}）</span><b>${(eo.value/100).toFixed(1)}億美元</b></div>`,
        `<div class="f"><span>外銷訂單月增(MoM)</span><b class="${cls(eo.change_mom_pct)}">${pct(eo.change_mom_pct)}</b></div>`,
        `<div class="f"><span>外銷訂單年增(YoY)</span><b class="${cls(eo.yoy_pct)}">${pct(eo.yoy_pct)}</b></div>`,
      );
    }else{
      rows.push(`<div class="f"><span>外銷訂單</span><b>本次未取得</b></div>`);
    }
    el.innerHTML=rows.join('');
    document.getElementById('ip-index-datatime').textContent=`生產指數資料月 ${d.latest.date}${_monthLagTxt(d.latest.date)}${eo&&eo.date?`、外銷訂單資料月 ${eo.date}`:''}（經濟部官方開放資料檔本身最新只到這個月，通常落後 2 個月以上；每日排程照常抓取${d.fetched_at?'，最後抓取 '+fmtTzMMDDHHMM(new Date(d.fetched_at),'Asia/Taipei'):''}）`;
  }
  // 先.八十一-14：「YYYY-MM」距今（台北）幾個月
  function _monthLagTxt(ym){
    const m=/^(\d{4})-(\d{2})/.exec(String(ym||''));if(!m)return '';
    const z=_zonedParts(new Date(),'Asia/Taipei');
    const lag=(z.y-+m[1])*12+(z.m-+m[2]);
    return lag>0?`，距今 ${lag} 個月`:'';
  }
  function fmtFlowAmt(v){
    if(v==null||!isFinite(v))return '—';
    const a=Math.abs(v);
    if(a>=1e8)return (v/1e8).toFixed(1)+'億';
    if(a>=1e4)return (v/1e4).toFixed(0)+'萬';
    return String(Math.round(v));
  }
  function setFlowWin(w){FLOW_WIN=w;FLOW_OPEN=null;_safeAsync('renderSectorFlow',()=>renderSectorFlow())}
  function toggleFlowSector(ind){FLOW_OPEN=(FLOW_OPEN===ind?null:ind);_safeAsync('renderSectorFlow',()=>renderSectorFlow())}
  async function renderSectorFlow(){
    const host=document.getElementById('sector-flow-body');
    const noteEl=document.getElementById('sector-flow-note');
    const tg=document.getElementById('flow-toggle');
    if(!host)return;
    const d=await ensureSectorFlow();
    if(!d||!d.sectors||!Object.keys(d.sectors).length){
      host.innerHTML='<div class="note">尚無產業金流資料（data/sector_flow.json 未產生或為空）。</div>';
      if(tg)tg.innerHTML='';if(noteEl)noteEl.textContent='';
      return;
    }
    const m=d.meta||{},usable=m.windows_usable||[];
    if(!usable.includes(FLOW_WIN))FLOW_WIN=usable[usable.length-1]||usable[0];
    // 切換鈕只列 meta 說可用的視窗——缺的不給按，避免按下去是空的
    if(tg){
      const lab={1:'當日',5:'近5日',20:'近20日',60:'近60日'};
      tg.innerHTML=usable.map(w=>`<span class="press mtg-opt${FLOW_WIN===w?' on':''}" style="flex:1;text-align:center" onclick="setFlowWin(${w})">${lab[w]||w+'日'}</span>`).join('');
    }
    const key='net_'+FLOW_WIN+'d_est_amount';
    const lotKey='net_'+FLOW_WIN+'d_lots';
    const rows=Object.entries(d.sectors)
      .map(([ind,a])=>({ind,amt:a[key]||0,lots:a[lotKey]||0,n:a.constituents,a}))
      .filter(r=>r.amt!==0)
      .sort((x,y)=>y.amt-x.amt);
    const top=rows.slice(0,8),bot=rows.slice(-5).reverse();
    const shown=top.concat(bot.filter(b=>!top.some(t=>t.ind===b.ind)));
    const maxAbs=Math.max(...shown.map(r=>Math.abs(r.amt)),1);
    host.innerHTML=shown.map(r=>{
      const pct=Math.max(2,Math.abs(r.amt)/maxAbs*100);
      const pos=r.amt>0,col=pos?'var(--up)':'var(--down)';
      const open=FLOW_OPEN===r.ind;
      let html=`<div class="press" onclick="toggleFlowSector('${r.ind.replace(/'/g,"\'")}')" style="cursor:pointer;padding:6px 0;border-bottom:1px solid rgba(var(--fg-rgb),.05)">
        <div style="display:flex;align-items:baseline;gap:8px">
          <span style="flex:1;font-size:12px;color:var(--ink-2)">${r.ind}<span style="font-size:9.5px;color:var(--ink-4)"> ${r.n}檔</span></span>
          <b class="num" style="font-size:12.5px;color:${col}">${pos?'+':''}${fmtFlowAmt(r.amt)}</b>
          <span class="num" style="font-size:9.5px;color:var(--ink-4);min-width:62px;text-align:right">${nf(Math.round(r.lots))} 張</span>
          <span style="font-size:10px;color:var(--ink-4)">${open?'▾':'▸'}</span>
        </div>
        <div style="height:3px;background:rgba(var(--fg-rgb),.05);border-radius:2px;margin-top:3px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${col};opacity:.65"></div>
        </div>
      </div>`;
      if(open){
        const mk=(list,label,c)=>!list||!list.length?'':`<div style="margin-top:6px"><div style="font-size:9.5px;color:var(--ink-4);margin-bottom:3px">${label}</div>`
          +list.slice(0,10).map(x=>`<div style="display:flex;gap:8px;font-size:11px;padding:2px 0;align-items:baseline">
              <span class="num" style="color:var(--ink-4);min-width:36px">${x.code}</span>
              <span style="flex:1;color:var(--ink-2)">${x.name||''}</span>
              <span class="num" style="color:${c};min-width:58px;text-align:right">${x.est_amount>0?'+':''}${fmtFlowAmt(x.est_amount)}</span>
              <span class="num" style="color:var(--ink-4);font-size:9.5px;min-width:56px;text-align:right">${nf(Math.round(x.lots||0))} 張</span></div>`).join('')+'</div>';
        html+=`<div style="padding:4px 0 10px 0">
          <div class="note" style="margin:0 0 4px 0">成分股依「近 ${r.a.rank_window_days} 日淨買超<b>估算金額</b>」排序（與上方產業數字同一把尺；張數僅供參考，貴的股票少張數也可能是大金額）</div>
          ${mk(r.a.top_inflow,'買超前 10','var(--up)')}${mk(r.a.top_outflow,'賣超前 10','var(--down)')}</div>`;
      }
      return html;
    }).join('');
    if(noteEl){
      const miss=m.windows_missing_days||{};
      const missTxt=Object.keys(miss).length
        ?`　${Object.entries(miss).map(([w,n])=>`${w} 日視窗還需累積 ${n} 個交易日`).join('、')}（象限散點圖待 20 日視窗長滿後補上）。`:'';
      noteEl.innerHTML=`資料日 ${m.date||'—'}，${m.trading_days_available||0} 個交易日。`
        +`金額為<b>估算</b>（張×1000×當日收盤），非真實成交金額；自營商含避險未拆分。`
        +`已排除 ETF／ETN／存託憑證等 ${m.non_industry_excluded||0} 檔非產業證券。${missTxt}`;
    }
  }
