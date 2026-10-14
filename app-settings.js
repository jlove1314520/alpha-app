// 常備.開發-20 丙案（2026-10-11 先.六十五）：設定頁專屬程式，由 app.js 原封不動搬出（只含頂層宣告，未改寫函式本體）。
// 由 app.js 的 loadAppModule('settings') 在點到該頁時才載入；與 app.js 共用同一個全域範圍（一般 <script>，非 ES module）。
  // 2026-09-02新增（使用者原話：「設定頁那行diag灰字讀數收進隱藏debug開關，
  // 平常不顯示」）：這行技術性讀數是給開發者/協作者截圖回報用的，一般使用者
  // 平常看不懂也用不到，預設隱藏；連續點「App版本」5下（3秒內）切換顯示，
  // 狀態存localStorage，跨次開啟App記得住。
  let _debugTapCount=0,_debugTapTimer=null;
  function tapVersionForDebug(){
    _debugTapCount++;
    clearTimeout(_debugTapTimer);
    _debugTapTimer=setTimeout(()=>{_debugTapCount=0},3000);
    if(_debugTapCount>=5){
      _debugTapCount=0;
      const next=!isDebugDiagOn();
      try{localStorage.setItem('alpha_debug_diag',next?'1':'0')}catch(e){console.warn('[tapVersionForDebug]',e)}
      toast(next?'已開啟診斷讀數（設定頁底部）':'已關閉診斷讀數');
      updateViewportDiag();
    }
  }

  // ══════ 設定頁：券商備註存 localStorage；風控硬限制唯讀（/auto/status limits）；推播類別偏好在本機伺服器（/push/prefs）══════
  // 先.六十-A5：舊的 alpha_rc／alpha_notif 本機鍵已無作用（引擎不讀、也沒有推播），不再讀寫。
  function renderRiskLimits(l){
    if(!l)return;
    const nf0=v=>Number(v).toLocaleString('zh-TW');
    if(Array.isArray(l.whitelist))setTxt('rl-whitelist',l.whitelist.join('、'));
    setTxt('rl-cap',l.per_order_cap_twd?('NT$ '+nf0(l.per_order_cap_twd)):'未設定（引擎會全部拒單）');
    if(l.max_price_dev_pct!=null)setTxt('rl-dev','≤ ±'+l.max_price_dev_pct+'%');
    if(l.max_data_age_days!=null)setTxt('rl-age','≤ '+l.max_data_age_days+' 天');
    if(l.veto_minutes!=null)setTxt('rl-veto',l.veto_minutes+' 分鐘');
    setTxt('risk-limits-note','以上為本機引擎目前實際值（讀取自本機伺服器）。任一不符即拒單並推播。這些值只能由你本人修改本機設定檔，App 不能改。');
  }
  async function loadRiskLimits(){
    if(!LIVE.configured||!LIVE.url)return;
    try{
      const r=await liveFetch('/auto/status',6000);
      if(!r.ok)throw new Error('HTTP '+r.status);
      renderRiskLimits((await r.json()).limits);
    }catch(e){console.warn('[loadRiskLimits]',e);recordGlobalError('loadRiskLimits',e);setTxt('risk-limits-note',_isOfflineErr(e)?liveOfflineText():'讀取引擎實際值失敗（本機伺服器是舊版或回應錯誤），目前顯示程式內建預設值。')}
  }
  function _renderNotif(p){
    ['reject','complete','missed'].forEach(k=>{const el=document.getElementById('notif-'+k);if(el)el.classList.toggle('on',!!(p&&p[k]))});
  }
  async function loadNotif(){
    const note=document.getElementById('notif-note');
    if(!LIVE.configured||!LIVE.url){if(note)note.textContent='需連線本機伺服器才能讀取／修改（設定存在本機伺服器，所有已訂閱裝置共用）。';return}
    try{
      const r=await liveFetch('/push/prefs',6000);
      if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器是舊版，需重啟）':''));
      _renderNotif((await r.json()).prefs);
      if(note)note.textContent='設定存在本機伺服器，所有已訂閱裝置共用。關閉的類別不會推播（仍會寫進本機紀錄與紅色橫幅）。';
    }catch(e){console.warn('[loadNotif]',e);recordGlobalError('loadNotif',e);if(note)note.textContent='讀取推播偏好失敗：'+(e&&e.message||e)}
  }
  async function toggleNotif(el,key){
    const note=document.getElementById('notif-note');
    try{
      if(!LIVE.configured||!LIVE.url)throw new Error('連上電腦才看得到');
      const want=!el.classList.contains('on');
      const r=await fetch(LIVE.url+'/push/prefs',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),body:JSON.stringify({[key]:want}),credentials:'include'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      _renderNotif((await r.json()).prefs);
    }catch(e){console.warn('[toggleNotif]',e);recordGlobalError('toggleNotif',e);if(note)note.textContent='修改失敗：'+(e&&e.message||e)}
  }

  // 常備.開發-18：到價與事件推播。只支援台股（本機盤中即時報價只有 Shioaji 台股）；美股自選股列在說明裡、不假裝支援。
  // 規則整份 POST 給本機伺服器（research/price_alerts.py 驗證），App 不自己判斷觸發。
  const ALERT_TW_RE=/^\d{4,6}[A-Z]?$/;
  let ALERT_RULES={};
  function alertGoLive(){
    const el=document.getElementById('live-discovery');const card=el&&el.closest('.card');
    if(card)uiScrollIntoView(card);
  }
  function renderAlerts(d){
    const body=document.getElementById('alert-body'),cta=document.getElementById('alert-cta'),note=document.getElementById('alert-note');
    if(!body)return;
    if(!d){if(cta)cta.style.display='';body.innerHTML='';return}
    if(cta)cta.style.display='none';
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const tw=WL.filter(c=>ALERT_TW_RE.test(c)),us=WL.filter(c=>!ALERT_TW_RE.test(c));
    ALERT_RULES=d.rules||{};
    const fired=d.fired||{};
    const KIND={pct:'漲跌幅',above:'漲到價',below:'跌到價',event:'事件前一日'};
    const inp='style="width:62px;background:var(--surface);border:1px solid var(--hairline);border-radius:6px;padding:4px 6px;color:var(--ink);font-family:inherit;font-size:12px"';
    const v=x=>x==null?'':esc(x);
    let h='';
    if(!tw.length)h+='<div class="note">自選股裡沒有台股，無可設定的標的。</div>';
    tw.forEach(c=>{
      const r=ALERT_RULES[c]||{};const f=fired[c];
      h+='<div class="alert-row" data-code="'+esc(c)+'" style="padding:8px 0;border-bottom:1px solid var(--hairline)">'
        +'<div style="display:flex;justify-content:space-between;font-size:13px"><b>'+esc(c)+'</b>'
        +(f?'<span style="font-size:11px;color:var(--ink-3)">今日已推（'+esc(KIND[f.kind]||f.kind)+'）</span>':'')+'</div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:6px;font-size:11.5px;color:var(--ink-2)">'
        +'<label>漲跌幅 ±<input type="number" step="0.1" min="0" data-k="pct" value="'+v(r.pct)+'" '+inp+'>%</label>'
        +'<label>漲到 <input type="number" step="0.01" min="0" data-k="above" value="'+v(r.above)+'" '+inp+'></label>'
        +'<label>跌到 <input type="number" step="0.01" min="0" data-k="below" value="'+v(r.below)+'" '+inp+'></label>'
        +'<label><input type="checkbox" data-k="event"'+(r.event?' checked':'')+'> 事件前一日</label>'
        +'</div></div>';
    });
    if(tw.length)h+='<button class="btn" style="width:100%;margin-top:10px" onclick="saveAlertsClick()">儲存提醒設定</button>';
    body.innerHTML=h;
    if(note){
      const parts=['每檔每日最多一則；只在台股盤中（週一～週五 09:00–13:30）每分鐘檢查。'];  // 先.八十-5：「非投資建議」只在頁尾一處
      if(us.length)parts.push('美股（'+us.join('、')+'）暫不支援：本機盤中即時報價只有台股。');
      parts.push(d.live_quotes?'本機即時報價：有。':'本機即時報價：目前沒有（盤後或常駐行程未啟動），盤中只會發事件類提醒。');
      if(d.last_check)parts.push('上次檢查 '+String(d.last_check).slice(11,16)+'。');
      note.textContent=parts.join(' ');
    }
  }
  async function loadAlerts(){
    const note=document.getElementById('alert-note');
    if(!LIVE.configured||!LIVE.url){renderAlerts(null);return}
    try{
      const r=await liveFetch('/alerts/rules',6000);
      if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器是舊版，需重啟）':''));
      renderAlerts(await r.json());
    }catch(e){console.warn('[loadAlerts]',e);recordGlobalError('loadAlerts',e);renderAlerts(null);if(note)note.textContent='讀取提醒設定失敗：'+(e&&e.message||e)}
  }
  function collectAlertRules(){
    const rules={};
    document.querySelectorAll('#alert-body .alert-row').forEach(row=>{
      const c=row.dataset.code,r={pct:null,above:null,below:null,event:false};
      row.querySelectorAll('input').forEach(i=>{
        if(i.dataset.k==='event')r.event=i.checked;
        else if(i.value.trim()!=='')r[i.dataset.k]=Number(i.value);
      });
      if(r.pct||r.above||r.below||r.event)rules[c]=r;
    });
    return rules;
  }
  function saveAlertsClick(){_safeAsync('saveAlerts',saveAlerts)}
  async function saveAlerts(){
    const note=document.getElementById('alert-note');
    try{
      if(!LIVE.configured||!LIVE.url)throw new Error('連上電腦才看得到');
      const r=await fetch(LIVE.url+'/alerts/rules',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),body:JSON.stringify({rules:collectAlertRules()}),credentials:'include'});
      if(!r.ok){let m='HTTP '+r.status;try{const j=await r.json();if(j&&j.detail)m=j.detail}catch(e2){console.warn('[saveAlerts:detail]',e2)}throw new Error(m)}
      toast('已儲存提醒設定');
      await loadAlerts();
    }catch(e){console.warn('[saveAlerts]',e);recordGlobalError('saveAlerts',e);if(note)note.textContent='儲存失敗：'+(e&&e.message||e)}
  }

  function readBroker(){try{const s=localStorage.getItem('alpha_broker');return s?JSON.parse(s):{tw:'',us:''}}catch(e){console.warn('[readBroker]',e);recordGlobalError('readBroker',e);return{tw:'',us:''}}}
  function loadBroker(){
    const b=readBroker();
    const tw=document.getElementById('set-broker-tw'),us=document.getElementById('set-broker-us');
    if(tw)tw.value=b.tw||'';if(us)us.value=b.us||'';
  }
  function saveBroker(){
    const tw=document.getElementById('set-broker-tw').value.trim();
    const us=document.getElementById('set-broker-us').value.trim();
    localStorage.setItem('alpha_broker',JSON.stringify({tw,us}));
  }

  function hydrateSettings(){
    _safeAsync('loadRiskLimits',loadRiskLimits);_safeAsync('loadNotif',loadNotif);_safeAsync('loadAlerts',loadAlerts);loadBroker();
    _safeAsync('loadInstallPush',loadInstallPush);  // 常備.開發-34
    setTxt('set-wl-count',WL.length);
    try{renderWLSettings()}catch(e){console.warn('[renderWLSettings]',e);recordGlobalError('renderWLSettings',e)}  // 常備.開發-31
    const cacheCount=Object.keys(localStorage).filter(k=>k.startsWith('fmc_')).length;
    setTxt('set-cache-count',cacheCount+' 筆快取');
    renderColorSchemeToggle();
    _safeSync('renderThemeToggle',renderThemeToggle);  // 先.九十五-4
    loadAboutVersions();
    _safeAsync('loadDataFreshness',loadDataFreshness);  // 2026-09-03 P0三-三.2，獨立包起來，失敗不影響設定頁其他區塊
    _safeAsync('loadDataAudit',()=>loadDataAudit(false));  // 2026-09-06 稽核.一，同樣獨立
    _safeAsync('loadSmokeCloud',loadSmokeCloud);  // 常備.開發-27 雲端夜間冒煙，同樣獨立
    _safeAsync('loadWarrantBackup',loadWarrantBackup);  // 先.九十五-2 權證快照備份，同樣獨立
    _safeAsync('loadSchemaGuard',loadSchemaGuard);  // 常備.開發-28 資料檔 schema 守門，同樣獨立
    _safeAsync('loadAdjAnomalies',loadAdjAnomalies);  // 先.六十一
    _safeAsync('loadCoverage',()=>loadCoverage(false));    // 2026-09-15 稽核二.二，同樣獨立
    _safeAsync('loadSecurity',()=>loadSecurity(false));    // 2026-09-06 連線三.5
    _safeAsync('loadDependencyStatus',loadDependencyStatus);  // 先.八十一-26，同樣獨立
    _safeAsync('loadSignalStatus',()=>loadSignalStatus(false));  // 2026-09-15 開發佇列源頭一.4
    _safeSync('renderLiveStatus',renderLiveStatus);  // 2026-09-03深夜 乙.4
    _safeAsync('loadTrials',loadTrials);  // 常備.開發-33 研究透明度，獨立包起來（常備.開發-29 順手修：原本被併進上一行註解裡，從未執行）
    _safeAsync('loadErrSummary',()=>loadErrSummary(false));  // 常備.開發-29 App 錯誤回報，同樣獨立
    _safeAsync('loadSinopacNotices',loadSinopacNotices);  // 常備.開發-30 永豐 API 公告卡，同樣獨立
  }
  // 常備.開發-30：永豐 API 公告（本機 /sinopac/notices，token 必檢；只有截斷的關鍵句）
  async function loadSinopacNotices(){
    if(!LIVE.configured||!LIVE.url){setTxt('sjnote-status','需連線本機伺服器才看得到');return}
    try{
      const r=await liveFetch('/sinopac/notices',6000);
      if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器是舊版，需重啟）':''));
      const d=await r.json();
      const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      const items=Array.isArray(d.items)?d.items:[];
      setTxt('sjnote-status',!d.available?(d.reason||'沒有資料'):(items.length?'最近 '+items.length+' 則（摘要最新：'+(d.latest_digest||'--')+'）':'近 '+(d.scanned_days||0)+' 天沒有維護／版本／停機相關訊息'));
      const box=document.getElementById('sjnote-list');
      if(box)box.innerHTML=items.map(x=>`<div class="f" style="align-items:flex-start"><span style="white-space:nowrap">${esc(String(x.date).slice(5))} ${esc(x.time)}</span><b style="font-weight:400;text-align:right">${esc(x.sentence)}<span style="color:var(--ink-3)">　${esc(x.category)}·${esc(x.role)}</span></b></div>`).join('');
      setTxt('sjnote-tm',new Date().toTimeString().slice(0,5));
    }catch(e){console.warn('[loadSinopacNotices]',e);recordGlobalError('loadSinopacNotices',e);setTxt('sjnote-status','讀取失敗：'+(e&&e.message||e))}
  }
  // 常備.開發-29：近 7 日 App 錯誤數（本機 /errors/summary，token 必檢；只有筆數與函式名稱）
  async function loadErrSummary(flush){
    setTxt('errsum-pending',_errQRead().length);
    if(!LIVE.configured||!LIVE.url){setTxt('errsum-total','需連線本機伺服器才看得到（錯誤先存在這支手機，連上後自動送出）');return}
    try{
      if(flush)await flushErrorReports();
      const r=await liveFetch('/errors/summary',6000);
      if(!r.ok)throw new Error('HTTP '+r.status+(r.status===404?'（伺服器是舊版，需重啟）':''));
      const d=await r.json();
      const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      setTxt('errsum-total','近 7 日共 '+(d.total_7d||0)+' 筆'+((d.total_7d||0)===0?'，沒有錯誤':''));
      const days=Array.isArray(d.days)?d.days:[];
      const box=document.getElementById('errsum-days');
      if(box)box.innerHTML=days.slice().reverse().map(x=>{
        const top=Object.entries(x.labels||{}).slice(0,3).map(([k,v])=>esc(k)+'×'+v).join('、');
        return `<div class="f"><span>${esc(String(x.date).slice(5))}</span><b>${x.count} 筆${top?'<span style="font-weight:400;color:var(--ink-3)">　'+top+'</span>':''}</b></div>`;
      }).join('');
      setTxt('errsum-tm',String(d.generated_at||'').slice(11,16)||'--:--');
      setTxt('errsum-pending',_errQRead().length);
    }catch(e){console.warn('[loadErrSummary]',e);recordGlobalError('loadErrSummary',e);setTxt('errsum-total','讀取失敗：'+(e&&e.message||e))}
  }
  // 常備.開發-33：試驗帳本檢視（讀 data/trials_index.json，唯讀）
  let _trialsData=null;
  async function loadTrials(){
    try{
      const r=await fetch('data/trials_index.json',{cache:'no-cache'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      _trialsData=await r.json();
      setTxt('trials-meta','共 '+_trialsData.count+' 筆｜更新 '+String(_trialsData.generated_at||'').slice(0,10));
      renderTrials();
    }catch(e){console.warn('[loadTrials]',e);recordGlobalError('loadTrials',e);setTxt('trials-meta','試驗帳本暫時讀不到')}
  }
  function renderTrials(){
    const box=document.getElementById('trials-list');if(!box||!_trialsData)return;
    const q=((document.getElementById('trials-filter')||{}).value||'').trim().toLowerCase();
    const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const rows=_trialsData.rows.filter(r=>!q||(r.name+r.verdict+r.track+r.date).toLowerCase().includes(q)).slice(0,150);
    box.innerHTML=rows.length?rows.map(r=>'<div style="border-bottom:1px solid rgba(var(--fg-rgb),.06);padding:4px 0"><b>#'+r.id+'</b>'+(r.dup_id?'<span style="color:var(--ink-3)">（帳本共用編號）</span>':'')+' '+esc(r.date)+' · '+esc(r.track)+'<br>'+esc(r.name)+' <span style="color:var(--ink-3)">→ '+esc(r.verdict)+'</span></div>').join(''):'<div class="note">沒有符合的紀錄</div>';
  }
  window.renderTrials=renderTrials;

  // 2026-09-06（CF.4）伺服器網址正規化。網域上線後總司令會在手機上打字輸入
  // 「live.example.com」這種形式，很容易少打 https://、多打結尾斜線、或不小心
  // 把 /health 一起貼進來。這裡統一整理成 `https://主機[:port]` 的乾淨形式：
  //   - 沒有 scheme 的補 https://（唯一例外是 192.168./10./127. 開頭的私有 IP，
  //     那是區網直連的舊用法，補 http:// 才不會壞掉）
  //   - 去掉結尾斜線與任何路徑（liveFetch 會自己接 /live/quotes 這類路徑）
  // 回傳 {url, note}：note 是給使用者看的「我幫你改成這樣」說明，沒改就是空字串。
  function normalizeLiveUrl(raw){
    let v=(raw||'').trim();
    if(!v)return {url:'',note:''};
    const before=v;
    if(!/^https?:\/\//i.test(v)){
      const priv=/^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.|127\.)/.test(v);
      v=(priv?'http://':'https://')+v;
    }
    try{
      const u=new URL(v);
      v=u.protocol+'//'+u.host;   // host 已含 port，路徑/查詢字串一律丟掉
    }catch(e){
      console.warn('[normalizeLiveUrl]',e);
      return {url:before.replace(/\/+$/,''),note:''};
    }
    return {url:v,note:(v===before?'':'已將網址整理為 '+v)};
  }
  function saveLiveConfig(){
    const u=document.getElementById('set-live-url'),t=document.getElementById('set-live-token');
    let changed=false;
    try{
      if(u){
        const n=normalizeLiveUrl(u.value);
        changed=(localStorage.getItem('alpha_live_url')||'')!==n.url;
        u.value=n.url;
        localStorage.setItem('alpha_live_url',n.url);
        // 2026-09-08（自動連線一.5）填了手動值就記旗標、以手動值優先；
        // 清空則解除，回到自動發現。使用者要看得出自己覆寫了什麼。
        if(n.url)localStorage.setItem('alpha_live_url_manual','1');
        else{localStorage.removeItem('alpha_live_url_manual');_safeAsync('rediscover',()=>discoverLiveEndpoint(true).then(()=>{loadLiveConfig();renderLiveStatus()}))}
        if(n.note)toast(n.note);
      }
      if(t)localStorage.setItem('alpha_live_token',t.value.trim());
      const ci=document.getElementById('set-cf-access-id'),cs=document.getElementById('set-cf-access-secret');
      if(ci)localStorage.setItem('alpha_cf_access_id',ci.value.trim());
      if(cs)localStorage.setItem('alpha_cf_access_secret',cs.value.trim());
    }catch(e){console.warn('[saveLiveConfig]',e);recordGlobalError('saveLiveConfig',e)}
    loadLiveConfig();renderLiveStatus();restartLiveStream();
    // 換了網址就自動測一次連線，不用再自己按「測試連線」——切網域當下最想知道的
    // 就是「這樣改對不對」，讓使用者少一個步驟也少一次誤判成「壞了」。
    if(changed&&LIVE.configured)_safeAsync('testLiveConnection:auto',testLiveConnection);
  }
  function btSave(){
    try{
      const g=id=>{const el=document.getElementById(id);return el?el.value:''};
      localStorage.setItem('alpha_bt_path',JSON.stringify({nw:g('bt-nw'),pmt:g('bt-pmt'),birth:g('bt-birth'),age:g('bt-age')}));
      localStorage.setItem('alpha_settings_synced_at','');pushSettingsSoon();
    }catch(e){console.warn('[btSave]',e);recordGlobalError('btSave',e)}
    renderBtPath();
  }
  // ── 先.三十五：推播按鈕（先.三十一-一 只加了按鈕、沒有函式，屬假完成，這裡補上） ──
  // iOS 規定 Notification.requestPermission() 必須在使用者點擊的同一個同步流程裡呼叫，
  // 所以 pushEnable() 本身不是 async，權限請求前只做同步檢查、不得有任何 await。
  function _pushNote(msg){const el=document.getElementById('push-note');if(el)el.textContent='推播：'+msg}
  function _pushFail(step,msg,e){
    _pushNote('第'+step+'步失敗：'+msg);
    console.warn('[push] step '+step,msg,e||'');
    try{recordGlobalError('push step '+step,e||new Error(msg))}catch(err){console.warn('[push] recordGlobalError 失敗',err)}
  }
  function _pushStandalone(){
    try{return navigator.standalone===true||(window.matchMedia&&window.matchMedia('(display-mode: standalone)').matches)}catch(e){return false}
  }
  function _b64urlToBytes(s){
    const pad='='.repeat((4-s.length%4)%4);
    const raw=atob((s+pad).replace(/-/g,'+').replace(/_/g,'/'));
    const out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out;
  }
  async function _pushHttpErr(r){
    if(r.status===401)return 'HTTP 401：token 不正確（請到設定頁重新貼上本機 token）';
    let d='';try{const j=await r.json();d=j&&j.detail?('：'+j.detail):''}catch(e){d=''}
    return 'HTTP '+r.status+d+(r.status===404?'（伺服器可能是舊版，需重啟）':'');
  }
  function pushEnable(){
    // 第0步：同步環境檢查（不可 await）
    if(!('serviceWorker' in navigator)){_pushFail(0,'這個瀏覽器不支援 Service Worker（iPhone 需 iOS 16.4 以上，並用 Safari 加到主畫面）');return}
    if(!('PushManager' in window)||typeof Notification==='undefined'){
      _pushFail(0,_pushStandalone()?'這個系統版本不支援網頁推播（iOS 需 16.4 以上）':'請從主畫面的 Alpha 圖示開啟 App 再按（Safari 分頁裡不能開推播；iOS 需 16.4 以上）');return}
    if(!_pushStandalone()){_pushFail(0,'請從主畫面的 Alpha 圖示開啟 App 再按（目前是在瀏覽器分頁裡）');return}
    if(!LIVE.configured||!LIVE.url){_pushFail(0,'連上電腦才能用（到設定頁連線）');return}
    let permP;
    try{permP=Notification.requestPermission()}catch(e){_pushFail(1,'無法要求通知權限（'+(e&&e.message||e)+'）',e);return}
    _pushNote('第1步：要求通知權限中…');
    Promise.resolve(permP).then(perm=>_pushEnableRest(perm)).catch(e=>_pushFail(1,'要求通知權限失敗（'+(e&&e.message||e)+'）',e));
  }
  async function _pushEnableRest(perm){
    if(perm!=='granted'){_pushFail(1,perm==='denied'?'通知權限被拒，請到 iPhone 設定→通知→Alpha 開啟後再按一次':'尚未允許通知（'+perm+'），請再按一次並選「允許」');return}
    let reg,key,sub;
    try{_pushNote('第2步：等待 Service Worker…');reg=await navigator.serviceWorker.ready}
    catch(e){_pushFail(2,'Service Worker 未就緒（'+(e&&e.message||e)+'），請把 App 完全關掉再開',e);return}
    try{
      _pushNote('第3步：向本機伺服器取公鑰…');
      const r=await liveFetch('/push/vapid_public_key',8000);
      if(!r.ok){_pushFail(3,'取公鑰失敗：'+await _pushHttpErr(r));return}
      const j=await r.json();key=j&&j.public_key;
      if(!key){_pushFail(3,'伺服器沒有回傳公鑰（本機 .env 可能缺 VAPID 金鑰）');return}
    }catch(e){_pushFail(3,'連不到本機伺服器（本機離線或網址錯：'+(e&&e.name==='AbortError'?'逾時':(e&&e.message||e))+'）',e);return}
    try{
      _pushNote('第4步：向 Apple／瀏覽器推播服務訂閱…');
      const appKey=_b64urlToBytes(key);
      sub=await reg.pushManager.getSubscription();
      if(sub&&sub.options&&sub.options.applicationServerKey){
        const cur=new Uint8Array(sub.options.applicationServerKey);
        if(cur.length!==appKey.length||cur.some((v,i)=>v!==appKey[i])){await sub.unsubscribe();sub=null}
      }
      if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:appKey});
    }catch(e){_pushFail(4,'訂閱失敗（'+(e&&e.name||'')+' '+(e&&e.message||e)+'）',e);return}
    try{
      _pushNote('第5步：把訂閱交給本機伺服器…');
      const r=await fetch(LIVE.url+'/push/subscribe',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),body:JSON.stringify({subscription:sub.toJSON(),label:'iPhone'}),credentials:'include'});
      if(!r.ok){_pushFail(5,'登記訂閱失敗：'+await _pushHttpErr(r));return}
      const j=await r.json();
      _pushNote('已訂閱，共 '+(j.subscriptions!=null?j.subscriptions:'?')+' 支裝置。可按「測試推播」確認收得到。');
      _safeAsync('loadInstallPush',loadInstallPush);  // 常備.開發-34：訂閱成功後刷新狀態卡
    }catch(e){_pushFail(5,'連不到本機伺服器（'+(e&&e.message||e)+'）',e)}
  }
  // 常備.開發-34（2026-10-11）：iOS 安裝與推播狀態卡。只「讀」狀態：開啟方式、iOS 版本、通知權限、
  // 本裝置訂閱、電腦端登記數；不呼叫 requestPermission／subscribe（那必須由使用者按「開啟推播」）。
  // 每一項各自 try/catch，任一項讀不到只標「讀取失敗」，不影響其他項與設定頁其他面板。
  function _iosVersion(){
    try{
      const ua=navigator.userAgent||'';
      const m=ua.match(/OS (\d+)[_.](\d+)/);
      const isIOS=/iPhone|iPad|iPod/.test(ua)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
      if(!isIOS)return null;
      return m?{major:+m[1],minor:+m[2]}:{major:null,minor:null};
    }catch(e){console.warn('[installPush:ios]',e);return null}
  }
  async function loadInstallPush(){
    const body=document.getElementById('install-push-body'),guide=document.getElementById('install-push-guide');
    if(!body)return;
    const OK='#1aa876',BAD='#e6383f',WARN='#d08a00';
    const rows=[];const row=(label,txt,color)=>rows.push('<div class="f" style="display:flex;justify-content:space-between;gap:8px;padding:2px 0"><span>'+label+'</span><b style="color:'+color+';text-align:right">'+txt+'</b></div>');
    const ios=_iosVersion();
    const standalone=_pushStandalone();
    // 1. 開啟方式
    row('開啟方式',standalone?'主畫面 App':'瀏覽器分頁',standalone?OK:(ios?BAD:WARN));
    // 2. 系統版本（iOS 16.4 起才支援網頁推播）
    let iosTooOld=false;
    if(ios){
      if(ios.major==null)row('系統','iPhone／iPad（讀不到版本）',WARN);
      else{iosTooOld=ios.major<16||(ios.major===16&&ios.minor<4);row('系統','iOS '+ios.major+'.'+ios.minor+(iosTooOld?'（需 16.4 以上）':''),iosTooOld?BAD:OK)}
    }else row('系統','非 iPhone／iPad',OK);
    // 3. 瀏覽器支援
    let supported=false;
    try{supported=('serviceWorker' in navigator)&&('PushManager' in window)&&typeof Notification!=='undefined'}catch(e){console.warn('[installPush:support]',e)}
    row('推播功能',supported?'支援':(ios&&!standalone?'分頁裡不提供（需從主畫面開）':'不支援'),supported?OK:BAD);
    // 4. 通知權限
    let perm='unknown';
    try{if(typeof Notification!=='undefined')perm=Notification.permission}catch(e){console.warn('[installPush:perm]',e)}
    const permTxt={granted:'已允許',denied:ios?'已拒絕（到 iPhone 設定→通知→Alpha 開啟）':'已拒絕（到瀏覽器的網站設定允許通知）','default':'尚未詢問'}[perm]||'讀不到';
    row('通知權限',permTxt,perm==='granted'?OK:(perm==='denied'?BAD:WARN));
    // 5. 本裝置訂閱（瀏覽器端）
    let sub=null,subErr=null;
    if(supported){
      try{
        const reg=await Promise.race([navigator.serviceWorker.getRegistration(),new Promise(r=>setTimeout(()=>r(undefined),3000))]);
        if(reg&&reg.pushManager)sub=await reg.pushManager.getSubscription();
        else subErr='Service Worker 尚未註冊';
      }catch(e){subErr=(e&&e.message)||String(e);console.warn('[installPush:sub]',e);recordGlobalError('loadInstallPush:sub',e)}
    }else subErr='此環境不支援';
    // 6. 電腦端：公鑰是否一致＋登記數（唯讀端點）
    let srvTxt='連上電腦才看得到',srvColor=WARN,keyMatch=null;
    if(typeof LIVE!=='undefined'&&LIVE.configured&&LIVE.url){
      try{
        const r=await liveFetch('/push/vapid_public_key',6000);
        if(!r.ok){srvTxt='讀取失敗（HTTP '+r.status+'）';srvColor=BAD}
        else{
          const j=await r.json();
          const n=j.subscriptions;
          srvTxt=(n!=null?n:'?')+' 支裝置已登記';srvColor=n?OK:WARN;
          if(sub&&j.public_key&&sub.options&&sub.options.applicationServerKey){
            const a=new Uint8Array(sub.options.applicationServerKey),b=_b64urlToBytes(j.public_key);
            keyMatch=a.length===b.length&&a.every((v,i)=>v===b[i]);
          }
        }
      }catch(e){srvTxt='連不到本機伺服器';srvColor=BAD;console.warn('[installPush:server]',e);recordGlobalError('loadInstallPush:server',e)}
    }
    if(sub){
      if(keyMatch===false)row('本裝置訂閱','有，但金鑰與電腦不符（請按「開啟推播」重新訂閱）',BAD);
      else row('本裝置訂閱','有效'+(keyMatch?'（金鑰與電腦一致）':''),OK);
    }else row('本裝置訂閱',subErr?('無（'+subErr+'）'):'尚未訂閱',supported?WARN:BAD);
    row('電腦端',srvTxt,srvColor);
    // 總結一句
    let verdict;
    if(sub&&perm==='granted'&&keyMatch!==false&&srvColor===OK)verdict='<b style="color:'+OK+'">推播就緒</b>：可按「自動投資」卡的「測試推播」確認手機收得到（電腦端登記數含所有裝置，不保證包含這一支）。';
    else if(ios&&!standalone)verdict='<b style="color:'+BAD+'">尚未從主畫面開啟</b>：iPhone 只有「加到主畫面」後從圖示開啟才能收推播，見下方說明。';
    else if(iosTooOld)verdict='<b style="color:'+BAD+'">系統版本太舊</b>：請先把 iPhone 更新到 iOS 16.4 以上。';
    else if(perm==='denied')verdict='<b style="color:'+BAD+'">通知被拒</b>：'+(ios?'到 iPhone「設定 → 通知 → Alpha」':'到瀏覽器的網站設定')+'開啟允許通知，再回來按「開啟推播」。';
    else verdict='<b style="color:'+WARN+'">尚未完成</b>：到「自動投資」卡按「開啟推播」，跟著畫面一步步允許。';
    body.innerHTML=rows.join('')+'<div style="margin-top:6px">'+verdict+'</div>';
    if(guide){
      if(ios&&!standalone){
        guide.style.display='';guide.open=true;
        guide.innerHTML='<summary style="cursor:pointer"><b>怎麼加到主畫面</b></summary>'
          +'<div>以下依 Apple 官方說明整理，未在你的手機上親自看過，<b>按鈕位置以你看到的為準</b>：</div>'
          +'<ol style="margin:4px 0 0 18px;padding:0">'
          +'<li>用 <b>Safari</b> 開本頁（其他瀏覽器的選單可能沒有這個選項）。</li>'
          +'<li>點「分享」按鈕（方框加向上箭頭；新版 iOS 可能要先點網址列旁的「⋯」才看得到）。</li>'
          +'<li>往下找「加入主畫面」，點下去，再按右上角「加入」。</li>'
          +'<li>回到 iPhone 主畫面，點新出現的 <b>Alpha</b> 圖示開啟（不要再從 Safari 開）。</li>'
          +'<li>在 App 裡到「設定」頁，按「自動投資」卡的「開啟推播」，跳出詢問時選「允許」。</li>'
          +'</ol>'
          +'<div style="margin-top:4px">主畫面的 App 跟 Safari 分頁是兩個獨立環境，本機連線網址與 token 要在主畫面 App 裡再設定一次。</div>';
      }else{guide.style.display='none';guide.innerHTML=''}
    }
  }
  window.loadInstallPush=loadInstallPush;
  async function pushTest(){
    try{
      if(!LIVE.configured||!LIVE.url){_pushFail(0,'連上電腦才看得到');return}
      _pushNote('送出測試推播中…');
      const r=await fetch(LIVE.url+'/push/test',{method:'POST',headers:liveHeaders(),credentials:'include'});
      if(!r.ok){_pushFail(1,'測試推播請求失敗：'+await _pushHttpErr(r));return}
      const j=await r.json();
      if(!j.subscriptions){_pushNote('目前沒有任何已訂閱裝置，請先按「開啟本裝置推播」');return}
      const errs=(j.errors||[]).map(x=>String(x).startsWith('DEPENDENCY:')?'電腦缺推播套件（請 CC 在本機安裝 pywebpush）':x);
      _pushNote('送達 '+(j.delivered||0)+' 支、失敗 '+(j.failed||0)+' 支（共 '+j.subscriptions+' 支訂閱）'+(errs.length?'；錯誤：'+errs.join('；'):'')+(j.delivered?'。請看手機是否收到。':''));
    }catch(e){_pushFail(1,'連不到本機伺服器（'+(e&&e.message||e)+'）',e)}
  }
  // 先.三十九：「全部取消」只取消目前這一批（不開緊急停止，之後批次照常）
  async function autoCancelPending(){
    const pe=document.getElementById('auto-pending');
    try{
      if(!LIVE.configured||!LIVE.url)throw new Error('連上電腦才看得到');
      const r=await fetch(LIVE.url+'/auto/cancel_pending',{method:'POST',headers:liveHeaders(),credentials:'include'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const j=await r.json();
      if(pe)pe.textContent=j.cancelled?((j.drill?'演練（假券商）':'')+'本批已取消（之後批次照常）'):('沒有可取消的待執行訂單：'+(j.reason||''));
      if(j.cancelled){window._autoExecAfter=null;const cb=document.getElementById('auto-cancel-all');if(cb)cb.style.display='none'}
    }catch(e){
      console.warn('[autoCancelPending]',e);recordGlobalError('autoCancelPending',e);
      if(pe)pe.textContent='取消失敗（'+(e&&e.message||e)+'）——如需立即擋下，請打開下方「緊急停止」';
    }
  }
  async function autoSetStop(stop,why){
    try{
      if(!LIVE.configured||!LIVE.url)throw new Error('連上電腦才看得到');
      const r=await fetch(LIVE.url+'/auto/stop',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},liveHeaders()),body:JSON.stringify({stop:!!stop}),credentials:'include'});
      if(!r.ok)throw new Error('HTTP '+r.status);
    }catch(e){console.warn('[autoSetStop]',why,e);recordGlobalError('autoSetStop',e);alert('操作失敗：'+(e&&e.message||e))}
    await loadAutoTrading();
  }
  // ── 2026-09-06（連線一.2）測試連線分兩段、錯誤分三類 ───────────────────────
  // 原本只打 /live/quotes，失敗一律顯示瀏覽器丟回來的原始訊息（iOS Safari 就是那句
  // 沒有資訊量的「Load failed」）。總司令看到那句完全無法判斷是伺服器沒開、token 打錯、
  // 還是憑證沒信任——三種的處理方式完全不同。
  // 改成先打 /health（不需 token），再打 /live/quotes（需 token），這樣就能分開：
  //   /health 就連不上 → 伺服器沒在跑，或憑證/網路問題（用網址是不是 https 再細分）
  //   /health 通、/live/quotes 401 → token 錯，伺服器是好的
  //   兩個都通 → 成功
  async function testLiveConnection(){
    loadLiveConfig();
    if(!LIVE.configured){toast('請先填伺服器網址與token');return}
    // 2026-09-08（連線四.1）舊區網位址直接短路，不要讓使用者等 6 秒逾時。
    // 逾時訊息老實但沒用——它說「連不上」，卻不說「這個網址已經廢了、該換成什麼」。
    // 總司令在 4G 下就是卡在這裡：看到「連線逾時」自然去懷疑手機網路，
    // 但問題根本不在網路。能在送出請求前就判斷出來的事，不該讓使用者等。
    const _legacy=legacyLiveUrlReason(LIVE.url);
    if(_legacy){
      LIVE.lastError=(_legacy==='private'?'舊版區網位址':'網址帶了 :8001（舊版區網用法）')
        +'，伺服器已改走 Tailscale。請改填 ts.net 網址（不需加 port）。'
        +'區網直連已停用，此位址在任何網路下都連不到——不是網路問題。';
      toast('舊版區網位址，請改填 ts.net 網址（不需加 port）');
      renderLiveStatus();   // 這會一併畫出設定頁的引導方塊與「清除舊網址」按鈕
      return;
    }
    let health=null;
    try{
      const ac=new AbortController();const t=setTimeout(()=>ac.abort(),6000);
      const r=await fetch(LIVE.url+'/health',{cache:'no-store',credentials:'include',signal:ac.signal});
      clearTimeout(t);
      if(r.ok){
        health=await r.json();
        // 2026-09-06（連線三.2）/health 改成分層回應：沒帶 token 只回 {ok, ts}，
        // 帶了正確 token 才回 build/uptime/stale_process 等診斷欄位。
        // 所以第二段不用另外猜——**再打一次 /health、這次帶 token**，
        // 拿不拿得到 build 就是 token 對不對的答案，比看 401 更直接。
        try{
          const r2=await liveFetch('/health',6000);
          if(r2.ok){const d2=await r2.json();if(d2&&d2.build)health=d2;}
        }catch(e){console.warn('[testLiveConnection:health-token]',e)}
        // 2026-09-06（連線一.3 防再犯）伺服器自己會判斷「行程比原始碼舊」。
        // 總司令這次遇到的就是這個：伺服器檔案已經加了 allow_credentials=True，
        // 但 PC 上的行程是前一天啟動的，預檢缺那個標頭，瀏覽器判 CORS 失敗，
        // App 只顯示一句沒有資訊量的 Load failed，完全看不出是「沒重啟」。
        if(!health.build){
          // 拿得到 {ok} 但拿不到細節 ⇒ 伺服器活著、token 不對
          LIVE.lastError='token不正確';
          toast('② 伺服器活著，但 token 不正確（拿不到需要驗證的診斷資訊），請重貼一次');
          renderLiveStatus();return;
        }
        if(health.stale_process){
          LIVE.lastError='伺服器是舊版，需重啟';
          toast('⚠ 伺服器是舊版（程式碼已更新但行程沒重啟，build '+(health.build||'?')+'）。請重啟 alpha_live_server.py，或等排程 1 分鐘內自動拉起。');
          renderLiveStatus();return;
        }
      }
      else{LIVE.lastError='伺服器有回應但 /health 回 HTTP '+r.status;toast(LIVE.lastError);renderLiveStatus();return}
    }catch(e){
      const isHttps=/^https:/i.test(LIVE.url||'');
      const timeout=e.name==='AbortError';
      // 2026-09-08（連線五.2）錯誤訊息一律附上**實際使用的完整網址**（token 不顯示）。
      // 踩到的事：Cowork 給的測試網址裡有 `tail4c7XXXX` 佔位符，總司令照字面貼上，
      // 錯誤訊息卻只說「連線逾時」——訊息本身沒錯，但使用者無從發現是自己貼錯了。
      // 把用的網址原樣印出來，貼錯一眼就看得到。
      LIVE.lastError=(timeout?'連線逾時':'連不上伺服器')+'（'+(LIVE.url||'未設定')+'）';
      toast((timeout
        ? '① 連線逾時：伺服器可能沒在跑，或網址有誤'
        : (isHttps
            ? '① 連不上：伺服器沒在跑，或這台手機還沒信任自簽憑證（設定→一般→關於→憑證信任設定）'
            : '① 連不上：伺服器沒在跑，或網址/port 不對'))
        +'\n實際使用的網址：'+(LIVE.url||'未設定')
        +'\n請逐字核對，尤其結尾與有無多帶 :8001');
      renderLiveStatus();return;
    }
    try{
      const r=await liveFetch('/live/quotes',6000);
      if(r.status===401){
        LIVE.lastError='token不正確';
        toast('② token 不正確（伺服器活著），請重貼一次');
      }else if(!r.ok){
        LIVE.lastError='HTTP '+r.status;toast('伺服器回應 HTTP '+r.status);
      }else{
        const d=await r.json();LIVE.lastError=null;
        toast('③ 連線成功：伺服器 build '+(health.build||'?')+'、已開機 '+Math.round((health.uptime_sec||0)/60)+' 分鐘、'
          +(health.shioaji_connected?'即時 tick 進來中':'目前無 tick（收盤時段正常）')
          +'、台股來源 '+((d.sinopac&&d.sinopac.source_mode)||'無'));
        restartLiveStream();
      }
    }catch(e){
      LIVE.lastError=(e.name==='AbortError'?'逾時':(e.message||String(e)))+'（'+(LIVE.url||'')+'）';
      toast('/health 通但 /live/quotes 失敗（'+(e.name==='AbortError'?'逾時':(e.message||String(e)))+'）'
        +'——多半是憑證或 CORS，不是伺服器沒開\n實際使用的網址：'+(LIVE.url||'未設定'));
    }
    renderLiveStatus();
  }

  // ── 2026-09-03（P0三-三.2）設定頁「資料新鮮度」：每個資料檔最後更新時間＋是否
  // 逾期（逾期標紅）。判定規則跟 generate_status_json.py::build_schedule_health()
  // 同一套：盤中資料不得超過30分鐘沒更新（開盤前30分鐘寬限，要求上一交易日收盤
  // 資料）；每日排程在排程時刻後寬限3小時內必須落地；盤後/假日至少要有最近一個
  // 交易日的收盤資料。小檔直接抓時間戳；三個超大檔（fundamentals 8MB/stock_detail
  // 12MB/price_history 48MB）不在手機上整份抓，改讀STATUS.json的schedule_health並
  // 註明「依STATUS.json」。顏色刻意用固定色碼，不用--up/--down（那組會隨漲跌顏色
  // 偏好切換，紅綠語意會反過來）。已知簡化（誠實揭露）：不扣國定假日。
  const FRESHNESS_INTRADAY_GAP_MIN=30;
  const FRESHNESS_ITEMS=[
    {label:'台股逐筆tick（本機Shioaji）',file:'data/quotes_sinopac.json',kind:'intraday',tz:'Asia/Taipei',open:[9,0],close:[13,30],local:true},
    {label:'台股盤中報價（GitHub Actions）',file:'data/quotes_tw.json',kind:'intraday',tz:'Asia/Taipei',open:[9,0],close:[13,30]},
    {label:'美股即時報價（本機IBKR）',file:'data/quotes_ibkr.json',kind:'intraday',tz:'America/New_York',open:[9,30],close:[16,0],local:true},
    {label:'美股盤中報價（GitHub Actions）',file:'data/quotes_us.json',kind:'intraday',tz:'America/New_York',open:[9,30],close:[16,0]},
    {label:'台股大盤/類股/三大法人',file:'data/market_tw.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3},
    {label:'美股四大指數',file:'data/market_us.json',kind:'daily',tz:'UTC',mkt:'us',grace:3},
    {label:'美股類股SIC對映',file:'data/us_sic.json',kind:'daily',tz:'UTC',mkt:'us',grace:3},
    {label:'台股ADR溢價',file:'data/adr_premium.json',kind:'intraday',tz:'America/New_York',open:[9,30],close:[16,0]},
    {label:'匯率 USD/TWD',file:'data/fx.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3},
    {label:'大盤融資維持率',file:'data/margin_maintenance.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3},
    {label:'前瞻選股台帳',file:'data/picks_ledger.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3},
    {label:'策略前向紙上績效',file:'data/strategy_performance.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3},
    // 先.六十-C9（2026-10-10）：這三個大檔原本經 STATUS.json 間接判斷（viaStatus），但 STATUS.json 頂層從 09-15 起沒人更新，
    // 判斷跟著失真。改成只串流讀檔案開頭幾 KB 抓它自己的 generated_at（三檔的 meta.generated_at 都在前 1KB 內），讀到就中止下載。
    {label:'個股基本面 PER/月營收',file:'data/fundamentals.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3,head:true},
    {label:'個股財報/法人/融資',file:'data/stock_detail.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3,head:true},
    {label:'個股價量歷史',file:'data/price_history/_meta.json',kind:'daily',tz:'UTC',mkt:'tw',grace:3,head:true},
  ];
  // 先.九十七-R8：每日項目的排程時刻（UTC）改讀 STATUS.json workflows[market.yml].crons（generate_status_json.py 從 market.yml
  // 實際 cron 換算，與後端 _market_run_hms()／橫幅 marketScheduleLabel() 同一規則：台股取台北 14:00 後當日最早一班，美股取台北隔日／09:00 前那班）。
  // 讀不到才退回舊值 06:10／21:30 UTC（只降級不中斷，十二節）；寬限小時數不變。
  const FRESH_FALLBACK_RUN={tw:[6,10],us:[21,30]};
  function _freshnessMarketRuns(stDoc){
    const out={tw:FRESH_FALLBACK_RUN.tw,us:FRESH_FALLBACK_RUN.us,src:'讀不到 market.yml cron，退回舊寫死時刻'};
    try{
      const w=stDoc&&Array.isArray(stDoc.workflows)?stDoc.workflows.find(x=>x&&/market\.yml$/.test(x.file||'')):null;
      const cr=w&&Array.isArray(w.crons)?w.crons.filter(c=>c&&/^\d{2}:\d{2}$/.test(c.utc||'')&&/^\d{2}:\d{2}$/.test(c.taipei||'')):[];
      const hm=c=>c.utc.split(':').map(Number);
      const tw=cr.filter(c=>!c.next_day_taipei&&c.taipei>='14:00').sort((a,b)=>a.taipei<b.taipei?-1:1);
      const us=cr.filter(c=>c.next_day_taipei||c.taipei<'09:00');
      if(tw.length)out.tw=hm(tw[0]);
      if(us.length)out.us=hm(us[0]);
      if(tw.length&&us.length)out.src='market.yml cron';
    }catch(e){console.warn('[_freshnessMarketRuns]',e);recordGlobalError('_freshnessMarketRuns',e);}
    return out;
  }
  // 只讀檔案開頭 maxBytes（Range＋串流，伺服器不支援 Range 也會在讀夠後中止），回傳第一個 "generated_at" 的時間
  async function _headGeneratedAt(url,maxBytes){
    maxBytes=maxBytes||16384;
    const ac=new AbortController();
    const r=await fetch(url+'?t='+Date.now(),{headers:{Range:'bytes=0-'+(maxBytes-1)},cache:'no-store',signal:ac.signal});
    if(!r.ok&&r.status!==206)throw new Error('HTTP '+r.status);
    let txt='';
    if(r.body&&r.body.getReader){
      const rd=r.body.getReader(),dec=new TextDecoder();let n=0;
      try{while(n<maxBytes){const {done,value}=await rd.read();if(done)break;n+=value.length;txt+=dec.decode(value,{stream:true});if(/"generated_at"\s*:\s*"[^"]+"/.test(txt))break}}
      finally{try{ac.abort()}catch(e){console.warn('[_headGeneratedAt] abort',e)}}
    }else{txt=(await r.text()).slice(0,maxBytes)}
    const m=txt.match(/"generated_at"\s*:\s*"([^"]+)"/);
    if(!m)return null;const t=new Date(m[1]);return isNaN(t)?null:t;
  }
  const FRESH_OK_COLOR='#1aa876',FRESH_BAD_COLOR='#e6383f';
  // 「最近一個週一至週五、且距now至少minAgeMs」的tz當地hh:mm時刻。往前推日時直接減
  // 86400000ms，跨日光節約切換那一天會差1小時（只影響邊界，已知簡化）。
  function _lastWeekdayInstant(now,tz,h,mi,minAgeMs){
    const z=_zonedParts(now,tz);
    const offsetMs=Date.UTC(z.y,z.m-1,z.d,z.h,z.mi)-Math.floor(now.getTime()/60000)*60000;
    let cand=new Date(Date.UTC(z.y,z.m-1,z.d,h,mi)-offsetMs);
    for(let i=0;i<10;i++){
      const cz=_zonedParts(cand,tz);
      if(cz.wd>=1&&cz.wd<=5&&(now-cand)>=(minAgeMs||0))return cand;
      cand=new Date(cand.getTime()-86400000);
    }
    return cand;
  }
  function _inSession(now,tz,open,close){
    const z=_zonedParts(now,tz);if(z.wd===0||z.wd===6)return false;
    const m=z.h*60+z.mi;return m>=open[0]*60+open[1]&&m<close[0]*60+close[1];
  }
  function _freshnessJudge(item,ts,now){
    let due,rule;
    if(item.kind==='intraday'){
      const gap=FRESHNESS_INTRADAY_GAP_MIN*60000;
      if(_inSession(now,item.tz,item.open,item.close)){
        const sOpen=_lastWeekdayInstant(now,item.tz,item.open[0],item.open[1],0);
        if(now-sOpen<gap){due=new Date(_lastWeekdayInstant(now,item.tz,item.close[0],item.close[1],0).getTime()-gap);rule='開盤前30分鐘寬限，需有上一交易日收盤資料';}
        else{due=new Date(now.getTime()-gap);rule='盤中不得超過30分鐘未更新';}
      }else{due=new Date(_lastWeekdayInstant(now,item.tz,item.close[0],item.close[1],0).getTime()-gap);rule='盤後/假日需有最近一個交易日收盤資料';}
    }else{
      due=_lastWeekdayInstant(now,item.tz,item.run[0],item.run[1],item.grace*3600000);
      rule='每個平日排程後'+item.grace+'小時內須落地'+(item.runSrc?'（排程時刻：'+item.runSrc+'）':'');
    }
    const status=!ts?'missing':(ts>=due?'ok':'overdue');
    return {status,due,rule};
  }
  function _extractFreshnessTs(d){
    if(!d)return null;
    let v=null;
    if(Array.isArray(d)){const last=d[d.length-1]||{};v=last.generated_at||(last.date?last.date+'T23:59:59+08:00':null);}
    else{const m=d.meta||{};v=d.fetched_at||d.generated_at||m.generated_at||m.last_snapshot_at;}
    if(!v)return null;const t=new Date(v);return isNaN(t)?null:t;
  }
  // 2026-09-06（P0 稽核.一）讀 data/audit_report.json 並呈現。
  // 這一區刻意「查不到就說查不到」：報告檔不存在代表稽核根本沒跑，那本身就是問題，
  // 不能顯示成一片綠色的「一切正常」。
  const AUDIT_CHECK_LABELS={
    a_price_source:'現價來源一致',
    a2_not_in_official:'榜單個股仍在官方名冊',
    a3_stale_price:'榜單個股價格未過期',
    b_entry_plan:'進場價在現價±30%內',
    c_range:'現價落在20日高低點內',
    d_market_cap:'市值＝現價×股數',
    e_pe:'本益比＝現價/近四季EPS',
    e_quarters_gap:'季報序列連續',
    e_quarters_stale:'季報夠新',
    f_null_as_number:'空值不得顯示成數字',
    g_comma_parsing:'千分位逗號解析',
  };
  let AUDIT_CACHE=null;
  // 先.六十一：還原價單日|報酬|>11% 異常警告摘要（research/adjust.py 偵測、generate_status_json.py 彙整，只降級為警告）
  async function loadAdjAnomalies(){
    const el=document.getElementById('adj-anomaly-note');if(!el)return;
    try{
      const r=await fetch('data/adjustment_anomalies.json?t='+Date.now(),{cache:'no-store'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      el.textContent='還原價異常警告（單日漲跌超過 11%，只警告、不影響排程）：'+(d.n_warnings!=null?Number(d.n_warnings).toLocaleString('zh-TW'):'?')+' 筆'+(d.generated_at?'；彙整時間 '+fmtTzMMDDHHMM(new Date(d.generated_at),'Asia/Taipei'):'');
    }catch(e){console.warn('[loadAdjAnomalies]',e);recordGlobalError('loadAdjAnomalies',e);el.textContent='還原價異常警告：讀取 data/adjustment_anomalies.json 失敗（'+(e&&e.message||e)+'）'}
  }
  async function loadDataAudit(force){
    const sum=document.getElementById('audit-summary'),list=document.getElementById('audit-list');
    if(!sum||!list)return;
    try{
      if(force||!AUDIT_CACHE){
        const r=await fetch('data/audit_report.json?t='+Date.now());
        if(!r.ok)throw new Error('HTTP '+r.status);
        AUDIT_CACHE=await r.json();
      }
      const d=AUDIT_CACHE;
      const pass=d.gate_pass===true;
      const rate=(d.violation_rate!=null)?(d.violation_rate*100).toFixed(2)+'%':'—';
      const gap=(d.completeness_gap_rate!=null)?(d.completeness_gap_rate*100).toFixed(1)+'%':'—';
      const nChecked=Object.values(d.by_check||{}).reduce((t,v)=>t+((v&&v.checked)||0),0);
      if(!(d.universe>0)||nChecked===0){sum.innerHTML='<b style="color:var(--warn)">未檢查</b>（稽核報告裡沒有任何一項實際檢查到資料，不能當作正常）';list.innerHTML='';return}
      sum.innerHTML=`<b style="color:${pass?'var(--up)':'var(--warn)'}">${pass?'✓ 通過':'✗ 未通過'}</b>`
        +` ｜ 稽核 ${nf(d.universe)} 檔 ｜ 一致性違規率 <b class="num">${rate}</b>（門檻 1%，${nf(d.stocks_with_violation||0)} 檔）`
        +` ｜ 資料完整度缺口 <b class="num">${gap}</b>（${nf(d.completeness_gap_stocks||0)} 檔，季報斷層/過期）`;
      const by=d.by_check||{};
      const rows=Object.keys(by).sort().map(k=>{
        const v=by[k]||{};
        const bad=(v.violations||0)>0,none=!bad&&!(v.checked>0);  // 先.八十-10：檢查 0 筆＝未檢查，不能顯示成正常
        return `<div class="f" data-audit-check="${k}" data-audit-state="${bad?'bad':(none?'unchecked':'ok')}"><span>${AUDIT_CHECK_LABELS[k]||k}</span>`
          +`<b class="num" style="color:${bad||none?'var(--warn)':'var(--ink-2)'}">${bad?nf(v.violations)+' 筆違規':(none?'未檢查':'0')}`
          +`<span style="color:var(--ink-4);font-weight:400"> / 檢查 ${nf(v.checked||0)}${v.unverifiable?'、無法查核 '+nf(v.unverifiable):''}</span></b></div>`;
      }).join('');
      const top=(d.top_20||[]).slice(0,20).map(v=>
        `<div style="font-size:11px;color:var(--ink-3);padding:3px 0;border-top:1px solid var(--hairline)">`
        +`${v.code&&v.code!=='-'?'<b class="num">'+v.code+'</b> '+(v.name||''):(v.name||'')} · `
        +`${AUDIT_CHECK_LABELS[v.check]||v.check}：我們 ${v.ours} ／ 官方 ${v.official}`
        +`${v.diff_pct!=null?'（差 '+v.diff_pct+'%）':''}</div>`).join('');
      list.innerHTML=`<div class="facts">${rows}</div>`
        +(top?`<details style="margin-top:8px"><summary style="font-size:11.5px;color:var(--ink-3);cursor:pointer">最嚴重的 ${Math.min(20,(d.top_20||[]).length)} 筆</summary>${top}</details>`:'');
      const tm=document.getElementById('audit-tm');
      if(tm&&d.generated_at)tm.textContent=fmtTzMMDDHHMM(new Date(d.generated_at),'Asia/Taipei');
    }catch(e){
      console.warn('[loadDataAudit]',e);recordGlobalError('loadDataAudit',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到稽核報告</b>（'+e.message+'）。代表 scripts/data_audit.py 尚未產生 data/audit_report.json，或排程沒有落地——這本身就是需要處理的狀況，不是「沒問題」。';
      list.innerHTML='';
    }
  }
  // 常備.開發-27：雲端夜間冒煙（data/smoke_cloud.json，.github/workflows/smoke_cloud.yml 每晚產出）。
  // 超過 36 小時沒更新也標警示——排程沒跑跟冒煙失敗一樣需要處理，不能顯示成「沒問題」。
  // 先.九十五-2：權證快照最後備份時間（data/warrant_backup_status.json，本機排程 AlphaWarrantSnapshot 寫）。
  // 備份超過 8 天、或最後快照超過 4 天就標警告（排程可能沒跑／電腦沒開）。404＝排程還沒產生第一份。
  async function loadWarrantBackup(){
    const sum=document.getElementById('warrant-backup-summary'),tm=document.getElementById('warrant-backup-tm');
    if(!sum)return;
    try{
      const r=await fetch('data/warrant_backup_status.json?t='+Date.now());
      if(r.status===404){sum.textContent='尚未產生第一份備份狀態';return}
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const days=t=>t?(Date.now()-new Date(t).getTime())/86400000:null;
      const bAge=days(d.last_backup_at),sAge=days(d.last_snapshot_date?d.last_snapshot_date+'T17:30:00+08:00':null);
      const warn=[];
      if(bAge==null)warn.push('還沒有備份過');else if(bAge>8)warn.push('已 '+Math.floor(bAge)+' 天沒備份');
      if(sAge==null)warn.push('還沒有快照');else if(sAge>4)warn.push('最後快照是 '+Math.floor(sAge)+' 天前，排程可能沒跑或電腦沒開');
      sum.innerHTML=`快照 <b>${nf(d.snapshot_days||0)}</b> 天（最後 ${d.last_snapshot_date||'—'}，共 ${d.snapshot_mb!=null?d.snapshot_mb:'—'} MB）｜已備份 <b>${nf(d.backed_up_days||0)}</b> 天`
        +(warn.length?` ｜ <b style="color:var(--warn)">${warn.join('；')}</b>`:' ｜ <b>✓ 正常</b>');  // 不用漲跌色（台股慣例 --up 是紅色，會誤讀）
      if(tm)tm.textContent=d.last_backup_at?fmtTzMMDDHHMM(new Date(d.last_backup_at),'Asia/Taipei'):'尚未備份';
    }catch(e){
      console.warn('[loadWarrantBackup]',e);recordGlobalError('loadWarrantBackup',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到備份狀態</b>（'+(e&&e.message||e)+'）';
    }
  }
  async function loadSmokeCloud(){
    const sum=document.getElementById('smoke-cloud-summary'),list=document.getElementById('smoke-cloud-list');
    if(!sum||!list)return;
    try{
      const r=await fetch('data/smoke_cloud.json?t='+Date.now());
      if(r.status===404){sum.textContent='尚未產生第一份結果（每晚台北 02:30 自動跑）';list.innerHTML='';return}
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json();
      const ageH=d.generated_at?(Date.now()-new Date(d.generated_at).getTime())/3600000:null;
      const stale=ageH==null||ageH>36;
      const ok=d.all_passed===true;
      const head=d.crashed?'<b style="color:var(--warn)">✗ 測試本身崩潰</b>'
        :`<b style="color:${ok?'var(--up)':'var(--warn)'}">${ok?'✓ 全部通過':'✗ '+nf(d.failed||0)+' 項失敗'}</b> ｜ ${nf(d.passed||0)}/${nf(d.total||0)} 通過`;
      sum.innerHTML=head+(stale?` ｜ <b style="color:var(--warn)">已 ${ageH==null?'?':Math.round(ageH)} 小時沒更新，排程可能沒跑</b>`:'');
      const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      const rows=(d.failures||[]).slice(0,20).map(f=>
        `<div style="font-size:11px;color:var(--ink-3);padding:3px 0;border-top:1px solid var(--hairline)"><b>${esc(f.name)}</b>${f.detail?'：'+esc(f.detail):''}</div>`).join('');
      list.innerHTML=(d.crashed&&d.crash_error?`<div style="font-size:11px;color:var(--ink-3)">${esc(String(d.crash_error).split('\n')[0])}</div>`:'')
        +(rows?`<details style="margin-top:4px"${ok?'':' open'}><summary style="font-size:11.5px;color:var(--ink-3);cursor:pointer">失敗項目</summary>${rows}</details>`:'');
      const tm=document.getElementById('smoke-cloud-tm');
      if(tm&&d.generated_at)tm.textContent=fmtTzMMDDHHMM(new Date(d.generated_at),'Asia/Taipei');
    }catch(e){
      console.warn('[loadSmokeCloud]',e);recordGlobalError('loadSmokeCloud',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到雲端冒煙結果</b>（'+(e&&e.message||e)+'）';list.innerHTML='';
    }
  }
  // 常備.開發-28：資料檔 schema 守門（data/schema_guard/<workflow>.json，各排程 commit 前由 scripts/data_schema_guard.py 寫）。
  // 每條排程各一份報告（避免多條排程搶寫同一檔造成 rebase 衝突）；404＝該排程尚未跑過新版，不算錯。
  const SCHEMA_GUARD_LABELS={market:'盤後市場',quotes:'盤中報價',news_events:'新聞事件',audit:'夜間稽核',
    us_financials:'美股財報',smoke_cloud:'雲端冒煙',local_schedule_watchdog:'本機排程看門狗'};
  async function loadSchemaGuard(){
    const sum=document.getElementById('schema-guard-summary'),list=document.getElementById('schema-guard-list');
    if(!sum||!list)return;
    try{
      const names=Object.keys(SCHEMA_GUARD_LABELS);
      const res=await Promise.allSettled(names.map(async n=>{
        const r=await fetch('data/schema_guard/'+n+'.json?t='+Date.now());
        if(r.status===404)return null;
        if(!r.ok)throw new Error('HTTP '+r.status);
        return r.json();
      }));
      const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      let seen=0,latest=null;const rejected=[],guardErr=[],readErr=[];
      res.forEach((x,i)=>{
        const lab=SCHEMA_GUARD_LABELS[names[i]];
        if(x.status==='rejected'){readErr.push(lab);console.warn('[loadSchemaGuard]',names[i],x.reason);return}
        const d=x.value;if(!d)return;seen++;
        if(d.generated_at&&(!latest||d.generated_at>latest))latest=d.generated_at;
        if(d.guard_error)guardErr.push(lab);
        (d.rejected||[]).forEach(r=>rejected.push({lab,...r}));
      });
      if(readErr.length)recordGlobalError('loadSchemaGuard',new Error('讀不到：'+readErr.join('、')));
      if(!seen&&!readErr.length){sum.textContent='尚未產生第一份結果（下一次排程 commit 時自動產生）';list.innerHTML='';return}
      sum.innerHTML=(rejected.length?`<b style="color:var(--warn)">✗ ${nf(rejected.length)} 個資料檔被攔下（畫面顯示的是上一版）</b>`
        :'<b style="color:var(--up)">✓ 最近一次全部通過</b>')+` ｜ ${nf(seen)}/${nf(names.length)} 條排程有回報`
        +(guardErr.length?` ｜ <b style="color:var(--warn)">守門員自身出錯（未擋發布）：${esc(guardErr.join('、'))}</b>`:'')
        +(readErr.length?` ｜ <b style="color:var(--warn)">讀不到：${esc(readErr.join('、'))}</b>`:'');
      list.innerHTML=rejected.length?'<div class="facts">'+rejected.slice(0,20).map(r=>
        `<div style="font-size:11px;color:var(--ink-3);padding:3px 0;border-top:1px solid var(--hairline)"><b>${esc(r.lab)}｜${esc(r.file)}</b>：${esc((r.errors||[]).slice(0,3).join('；'))}</div>`).join('')+'</div>':'';
      const tm=document.getElementById('schema-guard-tm');
      if(tm&&latest)tm.textContent=fmtTzMMDDHHMM(new Date(latest),'Asia/Taipei');
    }catch(e){
      console.warn('[loadSchemaGuard]',e);recordGlobalError('loadSchemaGuard',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到 schema 守門結果</b>（'+(e&&e.message||e)+'）';list.innerHTML='';
    }
  }
  // 2026-09-15（稽核二.二）讀 data/coverage.json：八因子×全市場覆蓋率儀表板。
  // 資料來自 research/build_coverage_dashboard.py，重用 generate_scores_live.py
  // 同一套原始資料，不是另外重新設計。
  let COVERAGE_CACHE=null;
  async function loadCoverage(force){
    const sum=document.getElementById('coverage-summary'),list=document.getElementById('coverage-list');
    if(!sum||!list)return;
    try{
      if(force||!COVERAGE_CACHE){
        const r=await fetch('data/coverage.json?t='+Date.now());
        if(!r.ok)throw new Error('HTTP '+r.status);
        COVERAGE_CACHE=await r.json();
      }
      const d=COVERAGE_CACHE,factors=d.factors||{};
      const keys=Object.keys(factors);
      const avgCov=keys.length?keys.reduce((s,k)=>s+(factors[k].coverage_pct||0),0)/keys.length:null;
      sum.innerHTML=`全市場 <b class="num">${nf(d.meta&&d.meta.universe_size)}</b> 檔 ｜ 八因子平均覆蓋率 `
        +`<b class="num">${avgCov!=null?(avgCov*100).toFixed(1)+'%':'—'}</b>`;
      const rows=keys.map(k=>{
        const v=factors[k]||{};
        const pct=(v.coverage_pct!=null)?(v.coverage_pct*100).toFixed(1)+'%':'—';
        const low=(v.coverage_pct!=null)&&v.coverage_pct<0.6;
        const reasons=Object.entries(v.missing_reason_breakdown||{}).map(([r,c])=>r+' '+nf(c)+'檔').join('、');
        return `<div class="f"><span>${v.label||k}</span><b class="num" style="color:${low?'var(--warn)':'var(--ink-2)'}">${pct}</b></div>`
          +(v.missing_count?`<div style="font-size:10.5px;color:var(--ink-4);margin:-2px 0 4px">缺 ${nf(v.missing_count)} 檔：${reasons}</div>`:'');
      }).join('');
      list.innerHTML=`<div class="facts">${rows}</div>`;
      const tm=document.getElementById('coverage-tm');
      if(tm&&d.meta&&d.meta.generated_at)tm.textContent=_dataDateLabel(d.meta.generated_at,'market.yml 每日排程重產（常備.開發-35）');
    }catch(e){
      console.warn('[loadCoverage]',e);recordGlobalError('loadCoverage',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到覆蓋率儀表板</b>（'+e.message+'）。代表 research/build_coverage_dashboard.py 尚未產生 data/coverage.json，或排程沒有落地。';
      list.innerHTML='';
    }
  }
  // 2026-09-06（連線三.5）讀 /security。沒設定即時伺服器時誠實說「讀不到」，
  // 不要顯示成一片綠色的「安全無虞」——那比沒有更危險。
  let SECURITY_CACHE=null;
  // 先.八十一-26：相依套件每週檢查結果（靜態檔，不需連上電腦）。檢查日超過 8 天標黃（每週一次的排程可能沒跑）。
  async function loadDependencyStatus(){
    const sum=document.getElementById('dep-summary'),list=document.getElementById('dep-list');
    if(!sum||!list)return;
    try{
      const r=await fetch('data/dependency_status.json?t='+Math.floor(Date.now()/600000));
      if(!r.ok)throw new Error('HTTP '+r.status);
      const d=await r.json(),pk=Array.isArray(d.packages)?d.packages:[];
      const esc=t=>String(t==null?'':t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
      const ts=Date.parse(d.generated_at),ageD=isNaN(ts)?null:(Date.now()-ts)/86400000;
      const behind=pk.filter(p=>p.behind),errs=pk.filter(p=>p.error);
      sum.innerHTML=`${behind.length?`<b style="color:var(--warn)">${behind.length} 個套件有新版</b>`:'<b style="color:var(--up)">✓ 都是最新版</b>'}／共 ${pk.length} 個`
        +`｜檢查日 <b class="num" style="color:${ageD!=null&&ageD>8?'var(--warn)':'var(--ink-2)'}">${isNaN(ts)?'—':fmtTzMMDDHHMM(new Date(ts),'Asia/Taipei')}</b>${ageD!=null&&ageD>8?'（超過 8 天沒檢查，每週排程可能沒跑）':''}`
        +(errs.length?`｜${errs.length} 個查詢失敗`:'');
      list.innerHTML='<div class="facts">'+pk.map(p=>`<div class="f"><span>${esc(p.package)}</span><b class="num" style="color:${p.behind?'var(--warn)':'var(--ink-2)'}">${esc(p.pinned)}${p.behind?' → '+esc(p.latest):''}${p.error?'（查詢失敗）':''}</b></div>`).join('')+'</div>';
    }catch(e){
      console.warn('[loadDependencyStatus]',e);recordGlobalError('loadDependencyStatus',e);
      sum.textContent='讀不到相依套件檢查結果（'+String(e&&e.message||e)+'）';list.innerHTML='';
    }
  }
  async function loadSecurity(force){
    const sum=document.getElementById('sec-summary'),list=document.getElementById('sec-list');
    if(!sum||!list)return;
    if(!LIVE.configured){
      sum.innerHTML='<span style="color:var(--ink-3)">未設定即時伺服器，無法讀取安全統計</span>';
      list.innerHTML='';return;
    }
    try{
      if(force||!SECURITY_CACHE){
        const r=await liveFetch('/security',8000);
        if(!r.ok)throw new Error('HTTP '+r.status);
        SECURITY_CACHE=await r.json();
      }
      const d=SECURITY_CACHE,L=d.limits||{};
      const warn=(d.auth_failed_401||0)>50||(d.banned_ips_now||0)>0;
      sum.innerHTML=`<b style="color:${warn?'var(--warn)':'var(--up)'}">${warn?'⚠ 有異常活動':'✓ 未見異常'}</b>`
        +` ｜ 過去 24 小時外部請求 <b class="num">${nf(d.external_requests||0)}</b> 次／`
        +`<b class="num">${nf(d.external_sources||0)}</b> 個來源網段`;
      list.innerHTML='<div class="facts">'
        +`<div class="f"><span>驗證失敗（401）</span><b class="num" style="color:${(d.auth_failed_401||0)?'var(--warn)':'var(--ink-2)'}">${nf(d.auth_failed_401||0)}</b></div>`
        +`<div class="f"><span>被限速擋下（429）</span><b class="num" style="color:${(d.rate_limited_429||0)?'var(--warn)':'var(--ink-2)'}">${nf(d.rate_limited_429||0)}</b></div>`
        +`<div class="f"><span>目前封鎖中 IP</span><b class="num" style="color:${(d.banned_ips_now||0)?'var(--warn)':'var(--ink-2)'}">${nf(d.banned_ips_now||0)}</b></div>`
        +`<div class="f"><span>串流連線數</span><b class="num">${nf(d.sse_active||0)} / ${nf(L.sse_max||0)}</b></div>`
        +`<div class="f"><span>每分鐘請求上限</span><b class="num">${nf(L.per_ip_per_min||0)}</b></div>`
        +'</div>'
        +((d.recent_blocked||[]).length
          ? `<details style="margin-top:8px"><summary style="font-size:11.5px;color:var(--ink-3);cursor:pointer">最近被擋的 ${d.recent_blocked.length} 筆</summary>`
            +d.recent_blocked.map(e=>`<div style="font-size:10.5px;color:var(--ink-3);padding:3px 0;border-top:1px solid var(--hairline)">${String(e.at).slice(11,19)} · ${e.kind} · ${e.source} · ${e.path}</div>`).join('')
            +'</details>'
          : '<div class="note" style="margin-top:6px">過去 24 小時沒有任何請求被擋下。</div>');
      const tm=document.getElementById('sec-tm');
      if(tm&&d.generated_at)tm.textContent=fmtTzMMDDHHMM(new Date(d.generated_at),'Asia/Taipei');
    }catch(e){
      console.warn('[loadSecurity]',e);
      sum.innerHTML='<span style="color:var(--warn)">讀不到安全統計（'+(e.message||e)+'）</span>';
      list.innerHTML='';
    }
  }
  // 2026-09-15（開發佇列源頭一.4）讀 data/signal_status.json 並呈現三態徽章。
  // 該檔是 research/build_signal_status.py 人工彙整 TRIALS_LEDGER.md/
  // STRATEGY_GRAVEYARD.md 的結果快照，不是本頁即時運算——讀不到就誠實說讀不到，
  // 不要顯示成空白（那會讓人以為「還沒有任何結果」而不是「檔案抓取失敗」）。
  let SIGNAL_STATUS_CACHE=null;
  function _signalTriState(status){
    const s=String(status||'').toUpperCase();
    if(s.indexOf('FAIL')>=0)return'實測無效';
    if(s==='PASS'||s.indexOf('通過')>=0)return'已驗證';
    return'未驗證';  // NOT_STARTED / IN_PROGRESS / EXPERIMENTAL / 已測 / MIXED 等一律歸未驗證，寧可保守不誇大
  }
  function _signalTriColor(tri){
    return tri==='已驗證'?'var(--up)':(tri==='實測無效'?'var(--warn)':'var(--ink-3)');
  }
  async function loadSignalStatus(force){
    const sum=document.getElementById('signal-status-summary'),list=document.getElementById('signal-status-list');
    if(!sum||!list)return;
    try{
      if(force||!SIGNAL_STATUS_CACHE){
        const r=await fetch('data/signal_status.json?t='+Date.now());
        if(!r.ok)throw new Error('HTTP '+r.status);
        SIGNAL_STATUS_CACHE=await r.json();
      }
      const d=SIGNAL_STATUS_CACHE;
      const dirs=Array.isArray(d.directions)?d.directions:[];
      const exts=Array.isArray(d.external_strategies)?d.external_strategies:[];
      const all=dirs.map(x=>({name:x.name,tri:_signalTriState(x.status),detail:x.summary||x.note||''}))
        .concat(exts.map(x=>({name:x.name,tri:_signalTriState(x.status),detail:x.source||''})));
      const counts={'已驗證':0,'未驗證':0,'實測無效':0};
      all.forEach(x=>{counts[x.tri]=(counts[x.tri]||0)+1});
      sum.innerHTML=`研究方向 <b class="num">${nf(dirs.length)}</b> 條＋外部策略 <b class="num">${nf(exts.length)}</b> 條 ｜ `
        +`<b style="color:var(--up)">已驗證 ${counts['已驗證']}</b>／`
        +`<b style="color:var(--ink-3)">未驗證 ${counts['未驗證']}</b>／`
        +`<b style="color:var(--warn)">實測無效 ${counts['實測無效']}</b>`;
      const rows=all.map(x=>`<div style="display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-top:1px solid var(--hairline)">`
        +`<span style="flex-shrink:0;background:${_signalTriColor(x.tri)};color:#1a1005;font-size:9.5px;padding:2px 7px;border-radius:10px;font-weight:700;white-space:nowrap">${x.tri}</span>`
        +`<div style="flex:1;min-width:0"><div style="font-size:11.5px;color:var(--ink-2)">${x.name||''}</div>`
        +(x.detail?`<div style="font-size:10px;color:var(--ink-4);margin-top:2px">${x.detail}</div>`:'')
        +'</div></div>').join('');
      list.innerHTML=`<details><summary style="font-size:11.5px;color:var(--ink-3);cursor:pointer">展開全部 ${all.length} 條</summary>${rows}</details>`;
      const tm=document.getElementById('signal-status-tm');
      // 常備.開發-35：資料日＝最新一筆結案日（data_as_of，人工彙整內容本身的日期）；
      // generated_at 只是 market.yml 每日排程重產時間，分開標示，不讓「今天重產」被誤讀成「今天有新結果」。
      if(tm){
        const asOf=d.data_as_of?String(d.data_as_of).slice(0,10):null;
        const gen=d.generated_at?new Date(d.generated_at):null;
        const genTxt=gen&&!isNaN(gen)?'；每日排程重產 '+fmtTzMMDDHHMM(gen,'Asia/Taipei'):'';
        tm.textContent=asOf?('資料日 '+asOf+'（最新一筆結案）'+genTxt+'；內容為人工彙整，有新結案才變動')
          :(d.generated_at?_dataDateLabel(d.generated_at,'人工彙整快照，有新結案才重產'):'--:--');
      }
    }catch(e){
      console.warn('[loadSignalStatus]',e);recordGlobalError('loadSignalStatus',e);
      sum.innerHTML='<b style="color:var(--warn)">✗ 讀不到訊號成績單</b>（'+e.message+'）。代表 research/build_signal_status.py 尚未產生 data/signal_status.json，或排程沒有落地——這本身就是需要處理的狀況，不是「沒有結果」。';
      list.innerHTML='';
    }
  }
  async function loadDataFreshness(){
    const list=document.getElementById('data-freshness-list');if(!list)return;
    const now=new Date();
    let statusDoc=null;
    try{const r=await fetch('data/STATUS.json?t='+Date.now());if(r.ok)statusDoc=await r.json();}
    catch(e){console.warn('[loadDataFreshness:STATUS]',e);recordGlobalError('loadDataFreshness:STATUS',e);}
    // 各檔獨立抓、獨立判定，用allSettled：一個檔壞了只有那一列顯示「讀取失敗」，其他列照常。
    const mktRuns=_freshnessMarketRuns(statusDoc);
    const settled=await Promise.allSettled(FRESHNESS_ITEMS.map(async item0=>{
      const item=item0.mkt?Object.assign({},item0,{run:mktRuns[item0.mkt],runSrc:mktRuns.src}):item0;
      let ts=null,via='';
      if(item.head){
        ts=await _headGeneratedAt(item.file);
        via='讀檔案自身 generated_at（只讀開頭，不整份下載）';
      }else if(item.viaStatus){
        const checks=statusDoc&&statusDoc.schedule_health&&Array.isArray(statusDoc.schedule_health.checks)?statusDoc.schedule_health.checks:[];
        const c=checks.find(x=>x.file===item.file);
        if(c&&c.last_data_at){ts=new Date(c.last_data_at);if(isNaN(ts))ts=null;}
        via=statusDoc&&statusDoc.updated_at?'依STATUS.json（'+fmtTzMMDDHHMM(new Date(statusDoc.updated_at),'Asia/Taipei')+'產生，大檔不在手機上整份抓）':'STATUS.json讀取失敗';
      }else{
        const r=await fetch(item.file+'?t='+Date.now());
        if(!r.ok)throw new Error('HTTP '+r.status);
        ts=_extractFreshnessTs(await r.json());
      }
      return Object.assign({item,ts,via},_freshnessJudge(item,ts,now));
    }));
    const rows=settled.map((s,i)=>{
      const item=FRESHNESS_ITEMS[i];
      if(s.status==='rejected'){
        console.warn('[loadDataFreshness:'+item.file+']',s.reason);recordGlobalError('loadDataFreshness:'+item.file,s.reason);
        return {item,ts:null,via:'',status:'missing',due:null,rule:'讀取失敗：'+((s.reason&&s.reason.message)||s.reason)};
      }
      return s.value;
    });
    const fmt=d=>d?fmtTzMMDDHHMM(d,'Asia/Taipei'):'—';
    list.innerHTML=rows.map(r=>{
      const bad=r.status!=='ok';
      const badge=bad?`<span style="color:${FRESH_BAD_COLOR};font-weight:700">${r.status==='missing'?'無資料':'逾期'}</span>`:`<span style="color:${FRESH_OK_COLOR};font-weight:600">正常</span>`;
      const sub=(bad&&r.due?('應≥'+fmt(r.due)+'，'):'')+r.rule+(r.via?'；'+r.via:'');
      return `<div class="fresh-row" data-file="${r.item.file}" data-status="${r.status}" style="display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid rgba(128,128,128,.15)">`
        +`<div style="min-width:0"><div style="font-size:12px;font-weight:600;color:${bad?FRESH_BAD_COLOR:'var(--ink)'}">${r.item.label}${r.item.local?' <span style="font-size:10px;opacity:.7">本機</span>':''}</div>`
        +`<div style="font-size:10px;opacity:.75;color:${bad?FRESH_BAD_COLOR:'inherit'}">${sub}</div></div>`
        +`<div style="text-align:right;white-space:nowrap;font-size:12px">${badge}<div style="font-size:10px;opacity:.8;color:${bad?FRESH_BAD_COLOR:'inherit'}">${fmt(r.ts)}</div></div></div>`;
    }).join('');
    const badRows=rows.filter(r=>r.status!=='ok');
    const sum=document.getElementById('data-freshness-summary');
    if(sum)sum.innerHTML=badRows.length?`<b style="color:${FRESH_BAD_COLOR}">${badRows.length} 項逾期/無資料</b>：${badRows.map(r=>r.item.label).join('、')}`:`<b style="color:${FRESH_OK_COLOR}">全部正常</b>`;
    setTxt('data-freshness-tm',fmtTzMMDDHHMM(now,'Asia/Taipei'));
    // 2026-09-26（警.一②）：本機排程停擺告警，資料來自
    // scripts/check_local_schedule_heartbeat.py（雲端每30分鐘寫入STATUS.json）。
    const hbNote=document.getElementById('local-schedule-heartbeat-note');
    if(hbNote){
      try{
        const hb=statusDoc&&statusDoc.local_schedule_heartbeat;
        if(!hb){
          hbNote.innerHTML='本機排程心跳：讀不到（STATUS.json尚無此欄位，或讀取失敗）';
        }else{
          // 2026-09-27（乾.三主體第八點）：判定來源改成三軌
          // (DevQueue/Marathon/Hypothesis-queue)任一有新鮮心跳即存活，
          // 資料結構搬進hb.tracks；舊版hb.devqueue是備援相容寫法，避免
          // 雲端排程還沒跑過新版腳本時這裡直接壞掉。
          const tracks=hb.tracks||{devqueue:hb.devqueue};
          let freshest=null;
          for(const name in tracks){
            const t=tracks[name];if(!t)continue;
            if(t.minutes_since!=null&&(freshest==null||t.minutes_since<freshest.minutes_since)){
              freshest={name,minutes_since:t.minutes_since,last_commit_at:t.last_commit_at};
            }
          }
          const mins=freshest&&freshest.minutes_since;
          const at=freshest&&freshest.last_commit_at?fmtTzMMDDHHMM(new Date(freshest.last_commit_at),'Asia/Taipei'):'—';
          const trackLabel=freshest?freshest.name:'—';
          const stalledTracks=hb.track_stalled||[];
          const stalledNote=stalledTracks.length?`；個別軌道停擺：${stalledTracks.join('、')}`:'';
          if(hb.stalled){
            hbNote.innerHTML=`本機排程心跳：<b style="color:${FRESH_BAD_COLOR}">疑似停擺</b>（三軌皆無新心跳，最新為${trackLabel} ${at}，距今約${mins==null?'—':mins.toFixed(0)}分鐘，門檻${hb.stall_threshold_minutes}分鐘）`;
          }else{
            hbNote.innerHTML=`本機排程心跳：<b style="color:${FRESH_OK_COLOR}">正常</b>（${trackLabel}最近一次commit ${at}，距今約${mins==null?'—':mins.toFixed(0)}分鐘${stalledNote}）`;
          }
        }
      }catch(e){
        console.warn('[loadDataFreshness:heartbeat]',e);recordGlobalError('loadDataFreshness:heartbeat',e);
        hbNote.innerHTML='本機排程心跳：顯示失敗（'+e.message+'）';
      }
    }
    // 2026-10-05（先.十四-一）：橫幅更新沿用這裡已經抓好的 STATUS.json，不重抓一次。
    renderClaudeAuthBanner(statusDoc);
  }
  function renderColorSchemeToggle(){
    const cur=localStorage.getItem('alpha_color_scheme')||'TW';
    const el=document.getElementById('color-scheme-toggle');if(!el)return;
    el.innerHTML=['TW','INTL'].map(k=>
      `<span class="press mtg-opt${cur===k?' on':''}" onclick="setColorScheme('${k}')">${k==='TW'?'台股':'國際'}</span>`
    ).join('');
  }
  // 先.九十五-4：外觀三選一。實際套用在 index.html <head> 的 alphaApplyTheme（第一次繪製前就要跑，所以不放這裡）。
  const THEME_OPTS=[['system','跟隨系統'],['light','淺色'],['dark','深色']];
  function renderThemeToggle(){
    const el=document.getElementById('theme-toggle');if(!el)return;
    const cur=typeof alphaThemePref==='function'?alphaThemePref():'system';
    el.innerHTML=THEME_OPTS.map(([k,l])=>`<span class="press mtg-opt${cur===k?' on':''}" onclick="setThemePref('${k}')">${l}</span>`).join('');
  }
  function setThemePref(k){
    try{localStorage.setItem('alpha_theme',k)}catch(e){console.warn('[setThemePref] 存偏好失敗',e);recordGlobalError('setThemePref',e)}
    const now=typeof alphaApplyTheme==='function'?alphaApplyTheme():'dark';
    renderThemeToggle();
    toast('外觀：'+(THEME_OPTS.find(o=>o[0]===k)||['',''])[1]+(k==='system'?'（目前'+(now==='light'?'淺色':'深色')+'）':''));
  }
  function setColorScheme(key){applyColorScheme(key);renderColorSchemeToggle();toast('已切換：'+COLOR_SCHEMES[key].label)}
