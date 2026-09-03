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
   推送**——每`SSE_POLL_INTERVAL_SEC`秒重新讀一次上述兩份JSON檔案、
   內容有變動才送一個SSE事件出去。**這不是使用者原始規格要的「本機
   tick→雲端SSE」那種真正逐筆延遲**，因為`shioaji_quotes.py`目前的
   `TickState`只存在於它自己那個行程的記憶體裡，這支獨立的FastAPI
   行程沒有辦法直接讀到那個記憶體——**要做到真正逐筆，需要讓
   `shioaji_quotes.py`的常駐迴圈跟這支伺服器合併成同一個Python行程**
   （例如`shioaji_quotes.py`啟動時用背景執行緒/asyncio一併把這支
   FastAPI app跑起來，直接共用`TickState`物件，不用再透過檔案中介），
   這是下一輪要做的整合工作，這裡先诚实交付「輪詢間隔內能看到更新」
   的堪用版本，不謊稱是逐筆。
3. `/live/kbars?code=`：**目前是佔位/未完成**——真正的1分K需要呼叫
   `api.kbars()`（Shioaji）或`reqHistoricalData()`（IBKR），這兩者都
   需要一個已登入/已連線的API session，這支獨立伺服器目前沒有自己
   建立連線（刻意避免第二個Shioaji session跟`shioaji_quotes.py`衝突，
   Shioaji帳戶對同時多重連線的行為未經測試過，貿然開第二條連線有風險）
   ——這個端點目前回傳明確的501「尚未實作」錯誤，不是假裝有資料。

**安全設計（逐字比照`ibkr_order_server.py`四層防護精神）**：
1. 共享密鑰token驗證，跟下單伺服器分開存放（`.alpha_live_token`，
   gitignored），第一次啟動印在終端機。
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

REPO_ROOT = Path(__file__).resolve().parent.parent
QUOTES_SINOPAC_PATH = REPO_ROOT / "data" / "quotes_sinopac.json"
QUOTES_IBKR_PATH = REPO_ROOT / "data" / "quotes_ibkr.json"
TOKEN_PATH = Path(__file__).parent / ".alpha_live_token"  # gitignored，見.gitignore

SERVER_PORT = 8001
SSE_POLL_INTERVAL_SEC = 2  # 見模組docstring第2點「誠實範圍」，這是輪詢間隔不是tick延遲


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


def _combined_snapshot() -> dict:
    sinopac = _read_json_safe(QUOTES_SINOPAC_PATH)
    ibkr = _read_json_safe(QUOTES_IBKR_PATH)
    return {
        "sinopac": sinopac,
        "ibkr": ibkr,
    }


@app.get("/live/quotes")
def live_quotes(x_alpha_local_token: str | None = Header(default=None)):
    """回傳目前的報價快照（Shioaji台股+IBKR美股各自最新一份），直接讀
    本機JSON檔案，跟App現在git-based冷資料讀的是同一組欄位結構，前端
    切換冷/熱資料源時不用改解析邏輯。"""
    _check_token(x_alpha_local_token)
    return _combined_snapshot()


@app.get("/live/kbars")
def live_kbars(code: str, x_alpha_local_token: str | None = Header(default=None)):
    """當日1分K——**尚未實作**，見模組docstring第3點誠實範圍說明。"""
    _check_token(x_alpha_local_token)
    raise HTTPException(
        status_code=501,
        detail=(
            f"/live/kbars 尚未實作（code={code}）：需要獨立的Shioaji/IBKR連線"
            "呼叫api.kbars()/reqHistoricalData()，這輪只交付/live/quotes"
            "跟/live/stream，kbars留給下一輪整合。"
        ),
    )


async def _sse_event_generator():
    """輪詢版SSE——見模組docstring第2點「誠實範圍」，不是真正逐筆tick
    推送，是「每SSE_POLL_INTERVAL_SEC秒比對一次檔案內容，有變動才送」。
    """
    last_sent: str | None = None
    while True:
        snapshot = _combined_snapshot()
        payload = json.dumps(snapshot, ensure_ascii=False)
        if payload != last_sent:
            last_sent = payload
            yield f"data: {payload}\n\n"
        await asyncio.sleep(SSE_POLL_INTERVAL_SEC)


@app.get("/live/stream")
async def live_stream(x_alpha_local_token: str | None = Header(default=None)):
    _check_token(x_alpha_local_token)
    return StreamingResponse(_sse_event_generator(), media_type="text/event-stream")


@app.get("/health")
def health():
    """唯一不需要token的端點——只回報「伺服器活著」，不含任何報價/
    帳戶資訊，跟ibkr_order_server.py的/health端點同一個設計精神
    （純粹的存活探測，不算資訊洩漏）。"""
    return {
        "ok": True,
        "sinopac_file_exists": QUOTES_SINOPAC_PATH.exists(),
        "ibkr_file_exists": QUOTES_IBKR_PATH.exists(),
    }


if __name__ == "__main__":
    print(f"本機即時報價伺服器啟動於 http://0.0.0.0:{SERVER_PORT}", flush=True)
    print(f"本機驗證token（貼進App設定頁或Cloudflare Access後的前端設定）：{LOCAL_TOKEN}", flush=True)
    print("**這是唯讀伺服器，完全沒有任何下單/改單能力，程式碼裡也沒有import任何下單相關模組**", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
