# -*- coding: utf-8 -*-
"""Alpha 秒級即時架構 Phase 1「冷熱分離」——本機唯讀即時資料伺服器
（2026-09-03新增，使用者裁示乙.2，逐字規格：GET /live/quotes、GET
/live/stream(SSE)、GET /live/kbars?code=，沿用`ibkr_order_server.py`的
token/白名單模式，只開讀取端點、不開任何下單端點）。

**這輪的誠實範圍（使用者原話「先不用綁定完成也可以先開始寫」，這裡先
交出老實可用的第一版，不是假裝已經完全做完）**：

1. `/live/quotes`：**已完整可用**——直接讀`data/quotes_sinopac.json`/
   `data/quotes_ibkr.json`兩份本機檔案回傳目前快照，這兩份檔案本來就是
   `shioaji_quotes.py`/`ibkr_quotes.py`常駐行程即時維護的（見那兩支
   腳本模組docstring），這支伺服器只是把它們包裝成一個統一的HTTP端點，
   不用再另外連一次Shioaji/IBKR。
2. `/live/stream`（SSE）：**目前是「輪詢再包裝」，不是真正的逐筆tick
   推送**——每`SSE_POLL_INTERVAL_SEC`秒重新讀一次熱檔/JSON檔案、
   內容有變動才送一個SSE事件出去。**每個事件的payload都帶
   `mode:"poll-diff-2s"`欄位、/health也回報`stream_mode`**（使用者
   2026-09-03深夜補充指令二：要在回應/文件裡明確標出來，不要讓接手的人
   誤以為是真推送；改成tick回呼直接推送已登記BACKLOG稍後做）。**這不是使用者原始規格要的「本機
   tick→雲端SSE」那種真正逐筆延遲**，因為`shioaji_quotes.py`目前的
   `TickState`只存在於它自己那個行程的記憶體裡，這支獨立的FastAPI
   行程沒有辦法直接讀到那個記憶體——**要做到真正逐筆，需要讓
   `shioaji_quotes.py`的常駐迴圈跟這支伺服器合併成同一個Python行程**
   （例如`shioaji_quotes.py`啟動時用背景執行緒/asyncio一併把這支
   FastAPI app跑起來，直接共用`TickState`物件，不用再透過檔案中介），
   這是下一輪要做的整合工作，這裡先诚实交付「輪詢間隔內能看到更新」
   的堪用版本，不謊稱是逐筆。
3. `/live/kbars?code=`：**台股已可用（2026-09-03深夜，使用者補充指令一）**
   ——**不是**呼叫`api.kbars()`，是讀`shioaji_quotes.py`常駐行程用已收到
   的tick自己聚合的「當日每分鐘OHLC」（寫在本機熱檔`.live_state_sinopac.
   json`，見該腳本`TickState.add_tick()`），不另開第二條Shioaji連線。
   回應帶`mode:"tick-aggregated-1m"`誠實標示來源。**美股（IBKR）1分K
   仍回501**：`ibkr_quotes.py`目前是短命輪詢腳本、沒有常駐tick可聚合，
   要做需先確認`reqHistoricalData()`會不會跟現有連線衝突，使用者裁示
   「不確定就先回報、不要硬做」，這裡照辦。

**熱檔/冷檔切換（2026-09-03深夜）**：`shioaji_quotes.py`常駐行程盤中每秒
最多寫一次熱檔（gitignored），這支伺服器的三個端點**優先讀熱檔**、熱檔
不存在或超過`HOT_STATE_MAX_AGE_SEC`沒更新（常駐行程沒在跑/收盤後）就
退回讀git追蹤的`data/quotes_sinopac.json`冷檔，回應裡用`source_mode`
（`hot-file`/`cold-git-file`）標明這次是哪一種，前端據此顯示「即時」或
「離線，顯示最後收盤」。

**安全設計（逐字比照`ibkr_order_server.py`四層防護精神）**：
1. 共享密鑰token驗證，跟下單伺服器分開存放（`.alpha_live_token`，
   gitignored），第一次啟動印在終端機。**三個/live端點一律要求
   `X-Alpha-Local-Token`，即使流量已經過Cloudflare Access／Private
   Network＋WARP裝置驗證也不跳過**（使用者2026-09-03深夜補充指令三：
   多一層防護不嫌多，風險評估以最嚴標準做）——程式碼裡沒有任何「來源
   是私有網段就免token」的分支，之後也不准加。只有`/health`不需要token
   （純存活探測，不含任何報價內容）。
2. **只有讀取端點，程式碼裡完全沒有任何下單/改單/連線帳戶設定的
   import或呼叫**——這是「只開讀取端點」鐵律的程式碼層級保證，不是
   靠口頭承諾。
3. CORS白名單限定GitHub Pages正式網址+本機開發網址，跟下單伺服器
   同一份清單。
4. **監聽`0.0.0.0`而非`127.0.0.1`（跟`ibkr_order_server.py`/
   `shioaji_order_server.py`刻意只聽127.0.0.1不同，這是唯一的例外，
   原因見下方「監聽介面決策」**）。

**監聽介面決策（使用者明確要求回報，這裡是我的決定+理由）**：**選
`0.0.0.0`（監聽全部網路介面），不是`127.0.0.1`**。原因：這支伺服器
設計上要透過Cloudflare Tunnel的Private Network路由讓外部（手機/其他
裝置）連進來——cloudflared在本機把封包送到的目的地是這台機器的**區網
IP**（例如`192.168.3.241`，見這輪`ipconfig`實測結果），不是
`127.0.0.1`（`127.0.0.1`只有這台機器自己能連到，連本機同一部機器上的
cloudflared行程雖然理論上可以連127.0.0.1，但Private Network路由設計
上是把目的地位址設成區網IP整個網段，若伺服器只聽127.0.0.1，區網IP
那個網路介面完全收不到連線，會直接連不上）。**已知取捨（誠實揭露，
不是沒想過）**：`0.0.0.0`代表同一個區網（同一個Wi-Fi）上的其他裝置
理論上也能打到這個port——這裡用token驗證擋著（沒有正確token一律401），
且**內容僅止於報價快照，不含任何帳戶/部位/下單能力**，風險程度遠低於
`ibkr_order_server.py`/`shioaji_order_server.py`那種真的能觸發下單的
伺服器（那兩支維持只聽127.0.0.1不變，這裡的例外只套用在這支唯讀
報價伺服器身上）。

**啟動方式**：`python research/alpha_live_server.py`（前景執行，跟
`shioaji_quotes.py`/`ibkr_quotes.py`分開跑，不搶Shioaji/IBKR連線）。
"""
from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import os
from datetime import datetime, timedelta, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
QUOTES_SINOPAC_PATH = REPO_ROOT / "data" / "quotes_sinopac.json"
QUOTES_IBKR_PATH = REPO_ROOT / "data" / "quotes_ibkr.json"
TOKEN_PATH = Path(__file__).parent / ".alpha_live_token"  # gitignored，見.gitignore
# 熱檔（shioaji_quotes.py常駐行程每秒最多寫一次，gitignored）。環境變數可覆寫，
# 給測試指到暫存檔用，避免測試把假資料寫進正式熱檔。
LIVE_STATE_PATH = Path(os.environ.get("ALPHA_LIVE_STATE_PATH") or (Path(__file__).parent / ".live_state_sinopac.json"))
HOT_STATE_MAX_AGE_SEC = 120  # 熱檔超過這麼久沒更新就視為「常駐行程沒在跑」，退回冷檔

SERVER_PORT = 8001
SSE_POLL_INTERVAL_SEC = 2  # 見模組docstring第2點「誠實範圍」，這是輪詢間隔不是tick延遲
SSE_MODE = "poll-diff-2s"  # 使用者補充指令二：每個事件都帶這個欄位，誠實標示不是真逐筆推送
SSE_KEEPALIVE_SEC = 15  # 沒有變動時定期送註解行，避免隧道/代理把閒置連線切掉
KBARS_MODE = "tick-aggregated-1m"
TW_TZ = timezone(timedelta(hours=8))


def _load_or_create_token() -> str:
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    return token


LOCAL_TOKEN = _load_or_create_token()

app = FastAPI(title="Alpha Live Quote Server（本機唯讀即時報價，Phase 1冷熱分離）")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jlove1314520.github.io", "http://localhost:8792", "http://127.0.0.1:8792"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _check_token(x_alpha_local_token: str | None) -> None:
    if x_alpha_local_token != LOCAL_TOKEN:
        raise HTTPException(status_code=401, detail="token不正確或缺少X-Alpha-Local-Token標頭")


def _read_json_safe(path: Path) -> dict | None:
    """讀不到/壞掉就回傳None，不拋例外中斷整個請求——沿用這個repo一貫
    的「查不到就誠實回報，不塞假資料」原則。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _hot_state() -> tuple[dict | None, str]:
    """回傳(熱檔內容, 狀態)。狀態：hot-file（新鮮可用）/hot-file-stale（存在但
    超過HOT_STATE_MAX_AGE_SEC沒更新，常駐行程沒在跑或已收盤）/hot-file-missing。"""
    doc = _read_json_safe(LIVE_STATE_PATH)
    if not doc or not isinstance(doc, dict):
        return None, "hot-file-missing"
    try:
        ts = datetime.fromisoformat(str(doc.get("updated_at")))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TW_TZ)
        age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return doc, "hot-file-stale"
    return doc, ("hot-file" if age <= HOT_STATE_MAX_AGE_SEC else "hot-file-stale")


def _combined_snapshot() -> dict:
    """三個端點共用的快照：台股優先用熱檔（秒級），熱檔不新鮮就退回git冷檔；
    美股目前只有冷檔（ibkr_quotes.py沒有常駐行程）。每一段都帶source_mode。"""
    hot, hot_status = _hot_state()
    cold = _read_json_safe(QUOTES_SINOPAC_PATH)
    if hot is not None and hot_status == "hot-file":
        sinopac = {
            "fetched_at": hot.get("updated_at"),
            "connected": True,
            "market_status": hot.get("market_status", "open"),
            "error": None,
            "quotes": hot.get("quotes") or {},
            "source_mode": "hot-file",
        }
    else:
        sinopac = dict(cold) if isinstance(cold, dict) else None
        if sinopac is not None:
            sinopac["source_mode"] = "cold-git-file"
            sinopac["hot_file_status"] = hot_status
    ibkr = _read_json_safe(QUOTES_IBKR_PATH)
    if isinstance(ibkr, dict):
        ibkr = dict(ibkr)
        ibkr["source_mode"] = "cold-git-file"
    kbars_last = {}
    if hot is not None:
        for key, bars in (hot.get("kbars") or {}).items():
            if bars:
                kbars_last[key] = bars[-1]
    return {
        "sinopac": sinopac,
        "ibkr": ibkr,
        "kbars_last": kbars_last,   # 每檔最新一根1分K，前端逐筆series.update()用，不必另外打/live/kbars
        "kbars_mode": KBARS_MODE,
        "hot_file_status": hot_status,
    }


@app.get("/live/quotes")
def live_quotes(x_alpha_local_token: str | None = Header(default=None)):
    """回傳目前的報價快照（Shioaji台股+IBKR美股各自最新一份），直接讀
    本機JSON檔案，跟App現在git-based冷資料讀的是同一組欄位結構，前端
    切換冷/熱資料源時不用改解析邏輯。"""
    _check_token(x_alpha_local_token)
    return _combined_snapshot()


def _looks_like_us_symbol(code: str) -> bool:
    return bool(code) and not code.isdigit() and code.upper() == code


@app.get("/live/kbars")
def live_kbars(code: str, x_alpha_local_token: str | None = Header(default=None)):
    """當日1分K（台股）：讀shioaji_quotes.py常駐行程用tick聚合、寫在熱檔的
    bars，回應帶mode="tick-aggregated-1m"。**token一律必檢，不因私有網路跳過。**
    美股仍501（理由見模組docstring第3點）。"""
    _check_token(x_alpha_local_token)
    code = (code or "").strip()
    if _looks_like_us_symbol(code):
        raise HTTPException(
            status_code=501,
            detail=(
                f"美股（{code}）1分K尚未實作：ibkr_quotes.py目前是短命輪詢腳本、沒有常駐tick可聚合；"
                "要做需先確認IBKR reqHistoricalData()會不會跟現有連線衝突，使用者裁示不確定就先回報不硬做。"
            ),
        )
    hot, status = _hot_state()
    if hot is None:
        raise HTTPException(
            status_code=404,
            detail="本機熱檔不存在：shioaji_quotes.py常駐行程今天還沒跑過（或這台機器不是跑排程的那台），沒有可聚合的tick。",
        )
    bars = (hot.get("kbars") or {}).get(code) or []
    if not bars:
        raise HTTPException(
            status_code=404,
            detail=f"{code} 今天沒有聚合到任何tick：不在常駐行程訂閱清單（目前有 {sorted((hot.get('kbars') or {}).keys())}）或今天尚未開盤。",
        )
    return {
        "code": code,
        "mode": KBARS_MODE,
        "source": "shioaji_quotes.py常駐行程用已收到的tick聚合（非api.kbars()，未另開連線）",
        "generated_at": hot.get("updated_at"),
        "market_status": hot.get("market_status"),
        "hot_file_status": status,   # hot-file=常駐行程正在更新；hot-file-stale=收盤後/行程未跑，bars是最後狀態
        "bars": bars,
    }


async def _sse_event_generator():
    """輪詢版SSE——見模組docstring第2點「誠實範圍」，不是真正逐筆tick
    推送，是「每SSE_POLL_INTERVAL_SEC秒比對一次熱檔/檔案內容，有變動才送」。
    每個事件payload都帶`mode:"poll-diff-2s"`；沒有變動時每SSE_KEEPALIVE_SEC
    秒送一行SSE註解（`: keepalive`）當心跳，避免隧道把閒置連線切掉。
    """
    last_sent: str | None = None
    idle = 0.0
    yield "retry: 3000\n\n"
    while True:
        snapshot = _combined_snapshot()
        body = json.dumps(snapshot, ensure_ascii=False)
        if body != last_sent:
            last_sent = body
            idle = 0.0
            event = dict(snapshot)
            event["mode"] = SSE_MODE
            event["sent_at"] = datetime.now(TW_TZ).isoformat()
            yield f"event: snapshot\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        else:
            idle += SSE_POLL_INTERVAL_SEC
            if idle >= SSE_KEEPALIVE_SEC:
                idle = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(SSE_POLL_INTERVAL_SEC)


@app.get("/live/stream")
async def live_stream(x_alpha_local_token: str | None = Header(default=None)):
    """SSE串流（mode=poll-diff-2s，見_sse_event_generator）。**token一律必檢，
    不因私有網路跳過。**瀏覽器原生EventSource無法帶自訂標頭，前端要用
    fetch()讀串流（index.html::startLiveStream()），這是刻意為了保住token
    驗證，不是疏忽。"""
    _check_token(x_alpha_local_token)
    return StreamingResponse(
        _sse_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    """唯一不需要token的端點——只回報「伺服器活著」，不含任何報價/
    帳戶資訊，跟ibkr_order_server.py的/health端點同一個設計精神
    （純粹的存活探測，不算資訊洩漏）。"""
    _, hot_status = _hot_state()
    return {
        "ok": True,
        "sinopac_file_exists": QUOTES_SINOPAC_PATH.exists(),
        "ibkr_file_exists": QUOTES_IBKR_PATH.exists(),
        "hot_file_status": hot_status,          # hot-file / hot-file-stale / hot-file-missing
        "stream_mode": SSE_MODE,                # 誠實標示：/live/stream是2秒輪詢比對，不是真逐筆推送
        "kbars_mode": KBARS_MODE,               # /live/kbars是tick聚合，不是api.kbars()
        "token_required_on_live_endpoints": True,  # 三個/live端點一律要token，不因私有網路跳過
        "us_kbars": "not_implemented",
    }


if __name__ == "__main__":
    print(f"本機即時報價伺服器啟動於 http://0.0.0.0:{SERVER_PORT}", flush=True)
    print(f"本機驗證token（貼進App設定頁「即時伺服器」卡片）：{LOCAL_TOKEN}", flush=True)
    print(f"熱檔路徑：{LIVE_STATE_PATH}（由shioaji_quotes.py常駐行程盤中每秒寫入；stream_mode={SSE_MODE}, kbars_mode={KBARS_MODE}）", flush=True)
    print("**這是唯讀伺服器，完全沒有任何下單/改單能力，程式碼裡也沒有import任何下單相關模組**", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
