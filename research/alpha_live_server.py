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
2. `/live/stream`（SSE）：**2026-09-04零.2起是真逐筆推送（`mode:"tick-push"`）**
   ——`shioaji_quotes.py`每收到一筆tick就用loopback UDP（127.0.0.1:8002，
   只聽本機、token必檢）推給這支伺服器，伺服器更新記憶體`LiveMem`並用
   asyncio.Condition喚醒所有SSE連線，中間沒有輪詢（250ms內多筆合併）。
   沒有新鮮tick（收盤後／常駐行程沒跑）時自動退回舊的「每2秒比對熱檔/
   冷檔」模式並標`mode:"poll-diff-2s"`，/health的`stream_mode`回報當下
   實際模式。**這不是使用者原始規格要的「本機
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
import hashlib
import json
import secrets
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

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
# 2026-09-04（總司令裁示HTTPS方案A）：自簽CA＋伺服器葉憑證，解決PWA（https頁面）抓這支
# http本機伺服器的「混合內容」封鎖。憑證由research/gen_local_ca.py產生，全部放secrets/
# （已gitignore，私鑰絕不進repo；這個repo是public的）。
SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CA_CRT_PATH = SECRETS_DIR / "alpha-ca.crt"        # DER格式，/ca.crt端點回傳這個給手機安裝
SSL_KEYFILE = SECRETS_DIR / "alpha-server-key.pem"
SSL_CERTFILE = SECRETS_DIR / "alpha-server-cert.pem"
# **第二階段（先寫好不切換）**：預設仍是HTTP（保持現有手機/PWA連線不中斷），總司令確認
# 手機已安裝secrets/alpha-ca.crt（透過/ca.crt下載）之後，設這個環境變數才會改監聽HTTPS：
#   ALPHA_LIVE_SERVER_HTTPS=1 python research/alpha_live_server.py
# 不做成「憑證檔案存在就自動切」，因為手機裝好CA之前貿然切HTTPS會讓所有裝置連不上，
# 這個決定必須是總司令明確一個動作（設環境變數/未來排程腳本旗標），不是憑感覺自動判斷。
ENABLE_HTTPS = os.environ.get("ALPHA_LIVE_SERVER_HTTPS") == "1"
SSE_POLL_INTERVAL_SEC = 2  # 退回輪詢模式時的比對間隔（記憶體沒有新鮮tick時才用）
SSE_MODE_POLL = "poll-diff-2s"   # 退回模式：每2秒比對熱檔/冷檔，有變才送
SSE_MODE_PUSH = "tick-push"      # 2026-09-04零.2：shioaji_quotes.py每筆tick經UDP推進來→立刻喚醒SSE
SSE_MODE = SSE_MODE_POLL  # 相容既有引用；實際每個事件的mode由當下是否有新鮮tick決定
SSE_PUSH_COALESCE_SEC = 0.25  # tick爆量時把250ms內的多筆合併成一個事件（延遲≤250ms，仍是推送不是輪詢）
# tick ingress：只聽loopback，不對外；datagram第一個欄位必須帶同一份.alpha_live_token
TICK_INGRESS_HOST = "127.0.0.1"
TICK_INGRESS_PORT = int(os.environ.get("ALPHA_TICK_INGRESS_PORT") or 8002)
MEM_FRESH_SEC = 120  # 記憶體最後一筆tick超過這麼久就不算「即時」，退回熱檔/冷檔
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
# 2026-09-06（連線一.2）行程啟動時間，給 /health 的 uptime 用。
# 總司令要 /health 回 {ok, uptime, shioaji_connected, last_tick_at}——uptime 是判斷
# 「剛剛被自動重啟過」的關鍵：如果每次看 uptime 都只有幾十秒，代表它一直在崩潰重啟，
# 那跟「一直沒在跑」是完全不同的故障，不能只看 ok。
SERVER_STARTED_AT = time.time()


def _git_head_sha(repo_root: Path) -> str | None:
    """讀 .git 取目前 HEAD 的短 sha。刻意不呼叫 git 指令：這支是常駐服務，
    不該為了一行版本號去 spawn 子行程（也不保證 PATH 上有 git）。"""
    try:
        head = (repo_root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            p1 = repo_root / ".git" / ref
            if p1.exists():
                return p1.read_text(encoding="utf-8").strip()[:7]
            # packed-refs 的情況
            packed = repo_root / ".git" / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return line.split(" ", 1)[0][:7]
            return None
        return head[:7]
    except OSError:
        return None


_REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SHA = _git_head_sha(_REPO_ROOT)
# 2026-09-06（連線一.3 防再犯）行程載入這支檔案時，檔案本身的修改時間。
# 這是「行程是不是舊版」最直接的判斷：檔案改過但行程沒重啟，Python 不會自己重載，
# 記憶體裡跑的就是舊程式。總司令這次遇到的正是這個——伺服器檔案已經加了
# allow_credentials=True，但行程是前一天啟動的，預檢就是缺那個標頭，
# 瀏覽器判 CORS 失敗，App 只看得到一句沒有資訊量的 Load failed。
# 判斷「行程跑的是不是舊程式」用**內容雜湊**，不用 mtime。
# 兩次實測踩到的坑都記在這裡：
#   第一版寫成 import 時算一次的常數 → 檔案之後被改也偵測不到，機制完全失效。
#   第二版改成每次請求讀 mtime → 排程的自動 commit（marathon/hypothesis_queue 會
#     git pull --rebase）會更新檔案 mtime，即使內容一個字都沒變也會誤報「舊版」。
# 內容雜湊兩個問題都沒有：內容一樣就是一樣，跟檔案時間、git 操作都無關。
# 限制誠實揭露：只涵蓋這支檔案本身，它 import 的模組改了不會被偵測到。
def _source_hash() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    except OSError:
        return ""


def _source_mtime() -> float:
    try:
        return os.path.getmtime(__file__)
    except OSError:
        return 0.0


SOURCE_HASH_AT_START = _source_hash()

# ── CORS 白名單 ────────────────────────────────────────────────────────────
# 2026-09-06（Cloudflare 網域上線準備 CF.2）：改成「精確來源 + 允許憑證」。
# 為什麼一定要精確來源：一旦回應帶 `Access-Control-Allow-Credentials: true`，
# 瀏覽器就**禁止** `Access-Control-Allow-Origin: *`，整個跨來源請求會被擋掉。
# 這裡本來就是逐一列舉來源（沒有用 *），加上 allow_credentials 後仍然合規。
#
# 為什麼需要 credentials：Cloudflare Access 擋在 tunnel 前面，通過驗證後會種一個
# `CF_Authorization` cookie 在 live.<domain> 這個網域上。App 從 github.io 打過去
# 是跨來源請求，預設不會帶 cookie，Access 會回 302 導到登入頁，前端只會看到
# 一個沒有 CORS 標頭的失敗。前端加 `credentials: 'include'`、伺服器回
# `Allow-Credentials: true`，兩邊都做才成立。
#
# 網域還沒買，所以用環境變數擴充：網域到手後設
#   set ALPHA_LIVE_ALLOW_ORIGINS=https://app.example.com
# 就會加進白名單，不用改程式碼重新部署。
_DEFAULT_ALLOW_ORIGINS = [
    "https://jlove1314520.github.io",   # GitHub Pages 上的正式 App
    "http://localhost:8792",            # 本機開發與冒煙測試
    "http://127.0.0.1:8792",
]
_extra_origins = [
    o.strip().rstrip("/")
    for o in (os.environ.get("ALPHA_LIVE_ALLOW_ORIGINS") or "").split(",")
    if o.strip()
]
ALLOW_ORIGINS = _DEFAULT_ALLOW_ORIGINS + _extra_origins

# 明確列出允許的請求標頭，不用 "*"。Starlette 對 "*" 的做法是把 preflight 要求的
# 標頭原樣鏡射回去（不會真的回一個 "*"），所以舊寫法其實也不會壞；但 Cloudflare
# Access 的 CORS 設定要求填出具體標頭名稱，兩邊寫成同一份清單比較不會對不起來，
# 日後有人改動也看得出來這裡跟 Access 設定是綁在一起的。
# 走 Cloudflare Access 服務權杖時，瀏覽器會多送 CF-Access-Client-Id/Secret 兩個標頭。
# 因為 Access 那邊要開「Bypass options requests to origin」（否則預檢一定 403，
# 見 docs/cloudflare_tunnel_setup.md），預檢會直接打到這支伺服器，所以這份清單
# 必須含這兩個名字，不然會被我們自己的 CORSMiddleware 擋成 400。
ALLOW_HEADERS = ["X-Alpha-Local-Token", "Content-Type", "Accept", "Cache-Control",
                 "CF-Access-Client-Id", "CF-Access-Client-Secret"]

app = FastAPI(title="Alpha Live Quote Server（本機唯讀即時報價，Phase 1冷熱分離）")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_methods=["GET", "POST"],  # POST 只有 /subscribe 用（推自選股清單），沒有任何下單能力
    # FastAPI/Starlette的CORSMiddleware會在OPTIONS preflight直接攔截回應，不會走到任何
    # route handler（也就不會經過_check_token()），所以preflight本來就不驗token，這裡是
    # 框架既有行為，不需要額外程式碼。
    allow_headers=ALLOW_HEADERS,
    allow_credentials=True,
)


@app.middleware("http")
async def _json_utf8_charset(request, call_next):
    """2026-09-04：三個端點的JSON回應（含401/404/501錯誤）一律明標
    `Content-Type: application/json; charset=utf-8`。FastAPI預設只給
    `application/json`，手機瀏覽器直接開網址時會把中文錯誤訊息顯示成亂碼
    （JSON規範上是UTF-8，但瀏覽器「直接顯示」時不一定照規範猜）。SSE的
    text/event-stream不動。"""
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct:
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


class LiveMem:
    """伺服器行程內的即時狀態（2026-09-04零.2）：由tick ingress（UDP）逐筆更新，
    SSE連線用asyncio.Condition等待version變動——這就是「tick回呼→SSE」的共用記憶體，
    只是跨行程的那一段用loopback UDP銜接（shioaji_quotes.py不開第二條連線）。"""

    def __init__(self) -> None:
        self.quotes: dict[str, dict] = {}
        self.kbars: dict[str, dict[str, dict]] = {}
        self.market_status: str = "open"
        self.last_tick_at: datetime | None = None
        self.updated_at: str | None = None
        self.version = 0
        self.ticks_received = 0
        # 2026-09-06（實測.二.補）常駐行程在每次 kbars_reply 帶回來的當日用量，
        # 讓 /health 看得到還剩多少額度（官方盤中上限 270 次/日）。
        self.kbars_calls_today: int | None = None
        self.kbars_daily_budget: int | None = None
        self.rejected = 0
        self.cond: asyncio.Condition | None = None

    def fresh(self) -> bool:
        return self.last_tick_at is not None and (datetime.now(timezone.utc) - self.last_tick_at).total_seconds() <= MEM_FRESH_SEC

    def seed_from_hot_file(self) -> None:
        """啟動時用熱檔把當日已累積的1分K/最新報價先載進來（不標新鮮），伺服器重啟
        不會把今天的K線弄丟。"""
        doc = _read_json_safe(LIVE_STATE_PATH)
        if not isinstance(doc, dict):
            return
        self.quotes = dict(doc.get("quotes") or {})
        for key, bars in (doc.get("kbars") or {}).items():
            self.kbars[key] = {b["t"]: dict(b) for b in bars if isinstance(b, dict) and "t" in b}
        self.market_status = doc.get("market_status", "open")
        self.updated_at = doc.get("updated_at")

    def apply(self, msg: dict) -> bool:
        if msg.get("t") != LOCAL_TOKEN:
            self.rejected += 1
            return False
        key = msg.get("key")
        if not key:
            return False
        q = msg.get("quote")
        if isinstance(q, dict) and q:
            self.quotes[key] = q
        bar = msg.get("bar")
        if isinstance(bar, dict) and bar.get("t"):
            day = str(bar["t"])[:10]
            bars = self.kbars.setdefault(key, {})
            for t in [t for t in bars if t[:10] != day]:  # 跨日清掉前一天
                bars.pop(t, None)
            bars[bar["t"]] = bar
        self.market_status = msg.get("market_status") or self.market_status
        self.last_tick_at = datetime.now(timezone.utc)
        self.updated_at = msg.get("ts") or datetime.now(TW_TZ).isoformat()
        self.ticks_received += 1
        self.version += 1
        return True

    def kbars_list(self, key: str) -> list[dict]:
        return [dict(b) for _, b in sorted((self.kbars.get(key) or {}).items())]


MEM = LiveMem()


class _TickIngress(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr) -> None:
        try:
            msg = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            MEM.rejected += 1
            return
        # 2026-09-06（實測.二.1）kbars 查詢的回覆不是 tick，不進 MEM，直接喚醒等待中的請求
        if msg.get("event") == "kbars_reply":
            if msg.get("t") != LOCAL_TOKEN:
                MEM.rejected += 1
                return
            if msg.get("kbars_calls_today") is not None:
                MEM.kbars_calls_today = msg.get("kbars_calls_today")
                MEM.kbars_daily_budget = msg.get("kbars_daily_budget")
            fut = _kbars_pending.pop(str(msg.get("req_id")), None)
            if fut is not None and not fut.done():
                fut.set_result(msg)
            return
        if MEM.apply(msg) and MEM.cond is not None:
            asyncio.get_event_loop().create_task(_notify_all())


async def _notify_all() -> None:
    async with MEM.cond:
        MEM.cond.notify_all()


@app.on_event("startup")
async def _start_tick_ingress() -> None:
    MEM.cond = asyncio.Condition()
    MEM.seed_from_hot_file()
    loop = asyncio.get_event_loop()
    try:
        await loop.create_datagram_endpoint(_TickIngress, local_addr=(TICK_INGRESS_HOST, TICK_INGRESS_PORT))
        print(f"tick ingress 監聽 udp://{TICK_INGRESS_HOST}:{TICK_INGRESS_PORT}（只聽loopback，token必檢）", flush=True)
    except OSError as e:
        print(f"tick ingress 無法監聽 {TICK_INGRESS_HOST}:{TICK_INGRESS_PORT}：{e}；/live/stream將退回{SSE_MODE_POLL}", flush=True)


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
    if MEM.fresh():
        sinopac = {
            "fetched_at": MEM.updated_at,
            "connected": True,
            "market_status": MEM.market_status,
            "error": None,
            "quotes": {k: dict(v) for k, v in _strip_index_keys(MEM.quotes).items()},
            "source_mode": "tick-push-memory",
        }
    elif hot is not None and hot_status == "hot-file":
        sinopac = {
            "fetched_at": hot.get("updated_at"),
            "connected": True,
            "market_status": hot.get("market_status", "open"),
            "error": None,
            "quotes": _strip_index_keys(hot.get("quotes") or {}),
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
    if MEM.kbars:
        for key, bars in MEM.kbars.items():
            if bars:
                kbars_last[key] = dict(bars[max(bars)])
    elif hot is not None:
        for key, bars in (hot.get("kbars") or {}).items():
            if bars:
                kbars_last[key] = bars[-1]
    return {
        "sinopac": sinopac,
        "ibkr": ibkr,
        "kbars_last": kbars_last,   # 每檔最新一根1分K，前端逐筆series.update()用，不必另外打/live/kbars
        "kbars_mode": KBARS_MODE,
        "hot_file_status": hot_status,
        "mem_fresh": MEM.fresh(),
    }


@app.get("/live/quotes")
def live_quotes(x_alpha_local_token: str | None = Header(default=None)):
    """回傳目前的報價快照（Shioaji台股+IBKR美股各自最新一份），直接讀
    本機JSON檔案，跟App現在git-based冷資料讀的是同一組欄位結構，前端
    切換冷/熱資料源時不用改解析邏輯。"""
    _check_token(x_alpha_local_token)
    return _combined_snapshot()


def _is_index_key(key: str) -> bool:
    """櫃買指數（TPEX）與37類股指數（IDX_IX00xx）由/live/indices提供，不進stream快照。"""
    return key == "TPEX" or str(key).startswith("IDX_")


def _strip_index_keys(quotes: dict) -> dict:
    return {k: v for k, v in (quotes or {}).items() if not _is_index_key(k)}


@app.get("/live/indices")
def live_indices(x_alpha_local_token: str | None = Header(default=None)):
    """櫃買指數＋37類股指數（2026-09-04四修.二）：來源優先記憶體（tick-push），其次熱檔；
    都沒有就回available=false讓前端退回market_tw.json並標日期。**token一律必檢。**"""
    _check_token(x_alpha_local_token)
    if MEM.fresh():
        quotes, src, gen, ms = MEM.quotes, "tick-push-memory", MEM.updated_at, MEM.market_status
    else:
        hot, status = _hot_state()
        if hot is not None and status == "hot-file":
            quotes, src, gen, ms = (hot.get("quotes") or {}), "hot-file", hot.get("updated_at"), hot.get("market_status", "open")
        else:
            return {"available": False, "reason": "常駐行程沒有新鮮的指數報價（非交易時段或shioaji_quotes.py未在跑）", "hot_file_status": status}
    tpex = quotes.get("TPEX")
    sectors = []
    for key, q in quotes.items():
        if key.startswith("IDX_") and isinstance(q, dict):
            sectors.append({"key": key, "code": key[4:], "name": q.get("label") or key, "last": q.get("last"),
                            "close": q.get("close"), "change_pct": q.get("change_pct"), "tick_at": q.get("tick_at")})
    sectors.sort(key=lambda r: r["code"])
    return {
        "available": bool(tpex or sectors), "source_mode": src, "market_status": ms, "generated_at": gen,
        "tpex": tpex, "sectors": sectors, "count": len(sectors),
        "note": "Shioaji Indexs.OTC/TSE Quote訂閱（見shioaji_quotes.py::INDEX_SUBSCRIPTIONS）；change_pct由last與reference自算",
    }


def _looks_like_us_symbol(code: str) -> bool:
    """只有「純英文字母1~5碼」才當美股代號（AAPL/MSFT）。TAIEX/TPEX/TXF_NEAR/IDX_IX0010這些
    是台股指數/期貨key，不是美股（2026-09-04四修.三修正：之前把TAIEX/TXF_NEAR誤判成美股回501，
    大盤速覽的當日1分K永遠拿不到）。"""
    return bool(code) and code.isalpha() and code.isascii() and code.upper() == code and 1 <= len(code) <= 5 and code not in ("TAIEX", "TPEX")


@app.get("/live/kbars")
async def live_kbars(code: str, x_alpha_local_token: str | None = Header(default=None)):
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
    mem_bars = MEM.kbars_list(code)
    backfill_note = None
    if mem_bars:
        reason = _needs_kbars_backfill(mem_bars)
        today = datetime.now(TW_TZ).date().isoformat()
        if reason and _kbars_backfilled.get(code) != today:
            _kbars_backfilled[code] = today   # 先記再查：查失敗也不重試，避免反覆打 API
            queried = await _kbars_via_daemon(code)
            if queried and queried.get("bars"):
                before = len(mem_bars)
                mem_bars = _merge_bars(mem_bars, queried["bars"])
                backfill_note = (f"偵測到{reason}，已補查 api.kbars() 合併"
                                 f"（{before} → {len(mem_bars)} 根，同一分鐘以 tick 聚合為準）")
                print(f"  [kbars補齊] {code} {backfill_note}", flush=True)
            else:
                backfill_note = f"偵測到{reason}，但補查沒有拿到資料（額度用盡或常駐行程沒回應）"
                print(f"  [kbars補齊] {code} {backfill_note}", flush=True)
    if mem_bars:
        return {
            "code": code, "mode": KBARS_MODE,
            "source": "alpha_live_server記憶體（shioaji_quotes.py每筆tick經UDP推入，非api.kbars()）",
            "generated_at": MEM.updated_at, "market_status": MEM.market_status,
            "hot_file_status": "tick-push-memory" if MEM.fresh() else status,
            "backfill": backfill_note,
            "bars": mem_bars,
        }
    # 2026-09-06（實測.二.1）沒有 tick 聚合資料時，改向常駐行程即時查 api.kbars()。
    # 這是「未訂閱代號也要有當日曲線」的關鍵路徑：使用者新增的自選股不會馬上有 tick
    # 歷史（訂閱是從那一刻才開始），但 api.kbars() 查得到今天從開盤到現在的完整 1 分K。
    queried = await _kbars_via_daemon(code)
    if queried is not None:
        return queried

    if hot is None:
        raise HTTPException(
            status_code=404,
            detail=("本機熱檔不存在，且向常駐行程查 api.kbars() 也沒有回應："
                    "shioaji_quotes.py 今天還沒跑過（或這台機器不是跑排程的那台）。")
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


def _sse_frame(snapshot: dict, mode: str) -> str:
    event = dict(snapshot)
    event["mode"] = mode
    event["sent_at"] = datetime.now(TW_TZ).isoformat()
    return f"event: snapshot\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _wait_version_change(v: int, timeout: float) -> bool:
    """等記憶體version變動（tick進來）；逾時回False。"""
    try:
        async with MEM.cond:
            await asyncio.wait_for(MEM.cond.wait_for(lambda: MEM.version != v), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def _sse_event_generator():
    """SSE串流，兩種模式、每個事件都明標`mode`：
    - `tick-push`（2026-09-04零.2）：記憶體有新鮮tick（MEM.fresh()）時，等
      asyncio.Condition被tick ingress喚醒就立刻送——shioaji_quotes.py收到tick
      →UDP→這裡→SSE，中間沒有任何輪詢；250ms內的多筆合併成一個事件。
    - `poll-diff-2s`：沒有新鮮tick（收盤後／常駐行程沒跑／ingress沒起來）時，
      退回每2秒比對熱檔/冷檔、有變才送的舊行為。
    沒有變動時每SSE_KEEPALIVE_SEC秒送一行`: keepalive`。"""
    last_sent: str | None = None
    idle = 0.0
    yield "retry: 3000\n\n"
    snapshot = _combined_snapshot()
    last_sent = json.dumps(snapshot, ensure_ascii=False)
    yield _sse_frame(snapshot, SSE_MODE_PUSH if MEM.fresh() else SSE_MODE_POLL)
    while True:
        if MEM.fresh() and MEM.cond is not None:
            v = MEM.version
            changed = await _wait_version_change(v, SSE_KEEPALIVE_SEC)
            if changed:
                await asyncio.sleep(SSE_PUSH_COALESCE_SEC)
                snapshot = _combined_snapshot()
                last_sent = json.dumps(snapshot, ensure_ascii=False)
                idle = 0.0
                yield _sse_frame(snapshot, SSE_MODE_PUSH)
            else:
                yield ": keepalive\n\n"
            continue
        snapshot = _combined_snapshot()
        body = json.dumps(snapshot, ensure_ascii=False)
        if body != last_sent:
            last_sent = body
            idle = 0.0
            yield _sse_frame(snapshot, SSE_MODE_POLL)
        else:
            idle += SSE_POLL_INTERVAL_SEC
            if idle >= SSE_KEEPALIVE_SEC:
                idle = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(SSE_POLL_INTERVAL_SEC)


# ── /subscribe：App 把自選股清單推給常駐行程 ────────────────────────────────
# 2026-09-06（實測.一.3）背景：Shioaji 的訂閱清單原本寫死在 shioaji_quotes.py 的
# DEFAULT_TW_WATCHLIST（5 檔），Python 行程讀不到瀏覽器的 localStorage，所以使用者
# 自己加的自選股永遠拿不到 tick。改成 App 把清單 POST 過來、寫進一個共用檔案，
# 常駐行程每輪讀它做增刪訂閱。
#
# **這個端點不具備任何下單能力**，它只決定「要串流哪些代號的報價」。伺服器整體
# 仍然是唯讀的（沒有 place_order，程式碼裡也沒有 import 下單模組）。
#
# 訂閱上限：Shioaji 官方文件載明 `api.subscribe()` 數量上限為 200 個
# （https://sinotrade.github.io/zh/tutor/limit/）。常駐行程已經固定用掉約 53 個
# （TAIEX 1、類股與櫃買指數 38、期貨 2 檔各 Tick+BidAsk 共 4、預設 5 檔股票各
# Tick+BidAsk 共 10），所以動態清單設 100 檔上限、且**只訂 Tick 不訂 BidAsk**
# （畫面只需要成交價，五檔買賣不需要），合計約 153 個，離上限還有餘裕。
# 超過上限的部分會被截掉，並在回應裡明講截掉了幾檔，不會安靜吃掉。
# ── 2026-09-06（實測.二.1）向常駐行程查 kbars ───────────────────────────────
# /live/kbars 原本只能回「已訂閱代號的 tick 聚合」，沒訂閱的一律 404。總司令要求
# 走勢線改成當日盤中曲線，而且**不准開第二條 Shioaji 連線**——能查 api.kbars() 的
# 只有 shioaji_quotes.py 那條常駐連線。所以這裡走 loopback UDP：送一個查詢過去，
# 對方在同一條連線上查完，用既有的 tick-push 通道回 event="kbars_reply"。
# 查不到就誠實回 404 並說明是哪一環沒接上，不塞假資料。
KBARS_REQ_ADDR = ("127.0.0.1", int(os.environ.get("ALPHA_KBARS_REQ_PORT") or 8003))
KBARS_REQ_TIMEOUT_SEC = 8.0
KBARS_CACHE_SEC = 60.0          # 總司令指定：查詢結果快取 60 秒
# ── 2026-09-06（實測.二.補.1）當日曲線必須從開盤起算 ────────────────────────
# tick 聚合只能從「開始訂閱那一刻」算起。常駐行程 09:15 才啟動、或某檔 09:20 才被
# 加進自選股時，聚合出來的曲線會從半路開始，看起來像那檔股票今天到 09:20 才開盤。
# 這裡在回傳前檢查兩件事，任一成立就補查一次 api.kbars() 並合併：
#   (a) 第一根晚於 09:01
#   (b) 中間有超過 3 分鐘的缺口（冷門股本來就可能好幾分鐘沒成交，3 分鐘是總司令
#       指定的門檻；用「缺口」而不是「每分鐘都要有」是因為沒成交就是沒有 K，
#       那是真實情況不是缺漏）
# **每檔每日只補一次**（總司令指定）：官方盤中 kbars 上限 270 次/日，重複補會很快
# 燒光額度，而且補過之後缺口就不會再出現，重複補沒有意義。
KBARS_OPEN_HHMM = "09:01"
KBARS_MAX_GAP_MIN = 3
_kbars_backfilled: dict[str, str] = {}   # code -> 已補過的交易日


def _bar_minute(b: dict) -> str | None:
    """兩種 bar 形狀都取得到分鐘字串（tick 聚合是 t、api.kbars 查詢是 ts）。"""
    v = b.get("t") or b.get("ts")
    if not v:
        return None
    return str(v)[:16]


def _needs_kbars_backfill(bars: list[dict]) -> str | None:
    """需要補就回傳原因字串，不需要回 None。"""
    mins = [m for m in (_bar_minute(b) for b in bars) if m]
    if not mins:
        return "沒有任何 bar"
    first = mins[0][11:16]
    if first > KBARS_OPEN_HHMM:
        return f"第一根是 {first}，晚於 {KBARS_OPEN_HHMM}"
    for a, b in zip(mins, mins[1:]):
        try:
            ta = int(a[11:13]) * 60 + int(a[14:16])
            tb = int(b[11:13]) * 60 + int(b[14:16])
        except ValueError:
            continue
        if tb - ta > KBARS_MAX_GAP_MIN:
            return f"{a[11:16]} 到 {b[11:16]} 有 {tb - ta} 分鐘缺口"
    return None


def _merge_bars(agg: list[dict], queried: list[dict]) -> list[dict]:
    """合併：**同一分鐘以 tick 聚合為準**（總司令指定）。

    tick 是逐筆真值，查詢回來的 K 是交易所彙總；同一分鐘兩者都有時，用手上這份
    逐筆聚合的，查詢那份只用來填沒有的分鐘。
    """
    out: dict[str, dict] = {}
    for b in queried:
        m = _bar_minute(b)
        if m:
            out[m] = {"t": m, "c": b.get("close") if b.get("close") is not None else b.get("c"),
                      "v": b.get("volume") if b.get("volume") is not None else b.get("v"),
                      "src": "api.kbars"}
    for b in agg:
        m = _bar_minute(b)
        if m:
            merged = dict(b)
            merged["t"] = m
            merged["src"] = "tick"
            out[m] = merged
    return [out[k] for k in sorted(out)]
_kbars_pending: dict[str, asyncio.Future] = {}
_kbars_cache: dict[str, tuple[float, dict]] = {}
_kbars_sock = None


def _kbars_request(code: str, req_id: str) -> bool:
    """把查詢送給常駐行程。送不出去回 False（例如行程沒開），由呼叫端誠實回報。"""
    global _kbars_sock
    try:
        if _kbars_sock is None:
            import socket
            _kbars_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _kbars_sock.setblocking(False)
        msg = {"t": LOCAL_TOKEN, "op": "kbars", "code": code, "req_id": req_id}
        _kbars_sock.sendto(json.dumps(msg).encode("utf-8"), KBARS_REQ_ADDR)
        return True
    except OSError as e:
        print(f"  [kbars查詢] 送出失敗 {code}：{type(e).__name__}: {e}", flush=True)
        return False


WATCHLIST_PATH = Path(os.environ.get("ALPHA_LIVE_WATCHLIST_PATH")
                      or (Path(__file__).parent / ".live_watchlist.json"))
MAX_DYNAMIC_SUBSCRIPTIONS = 100


def _is_tw_stock_code(code: str) -> bool:
    """只收台股普通股/ETF代號。擋掉美股代號與亂填的字串，避免常駐行程對著一堆
    查不到的合約反覆丟例外。"""
    return bool(code) and code.isdigit() and (
        len(code) == 4 or (len(code) in (5, 6) and code.startswith("00")))


@app.post("/subscribe")
async def post_subscribe(payload: dict, x_alpha_local_token: str | None = Header(default=None)):
    _check_token(x_alpha_local_token)
    raw = payload.get("codes") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="需要 {\"codes\": [\"2330\", ...]} 這樣的 JSON")

    seen, accepted, rejected = set(), [], []
    for item in raw:
        code = str(item).strip()
        if code in seen:
            continue
        seen.add(code)
        (accepted if _is_tw_stock_code(code) else rejected).append(code)

    truncated = accepted[MAX_DYNAMIC_SUBSCRIPTIONS:]
    accepted = accepted[:MAX_DYNAMIC_SUBSCRIPTIONS]

    doc = {
        "updated_at": datetime.now(TW_TZ).isoformat(),
        "codes": accepted,
        "limit": MAX_DYNAMIC_SUBSCRIPTIONS,
        "rejected": rejected,
        "truncated": truncated,
    }
    try:
        WATCHLIST_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"寫入訂閱清單失敗：{e}") from e

    return {
        "ok": True,
        "accepted": len(accepted),
        "codes": accepted,
        "rejected": rejected,
        "truncated": truncated,
        "limit": MAX_DYNAMIC_SUBSCRIPTIONS,
        "note": ("超過上限的部分沒有訂閱：" + ", ".join(truncated)) if truncated else
                "全部收下，常駐行程會在下一輪（數秒內）完成訂閱",
    }


@app.get("/subscribe")
async def get_subscribe(x_alpha_local_token: str | None = Header(default=None)):
    """目前生效的動態訂閱清單。給 App 與除錯用——看得到伺服器認的是什麼，
    才不用靠猜判斷「到底推上去了沒」。"""
    _check_token(x_alpha_local_token)
    doc = _read_json_safe(WATCHLIST_PATH)
    if not doc:
        return {"codes": [], "updated_at": None, "limit": MAX_DYNAMIC_SUBSCRIPTIONS,
                "note": "尚未收到任何自選股清單，常駐行程目前只訂 DEFAULT_TW_WATCHLIST"}
    return doc


async def _kbars_via_daemon(code: str) -> dict | None:
    """向常駐行程查當日 1 分K。查得到回結果 dict，查不到回 None（讓呼叫端走既有的 404）。

    快取 60 秒（總司令指定）：走勢線是每列都要畫的東西，20 檔自選股同時開頁面就是
    20 個查詢，沒有快取會直接打爆 Shioaji 的流量上限。
    """
    now = time.time()
    hit = _kbars_cache.get(code)
    if hit and now - hit[0] < KBARS_CACHE_SEC:
        return hit[1]

    req_id = secrets.token_hex(8)
    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _kbars_pending[req_id] = fut
    if not _kbars_request(code, req_id):
        _kbars_pending.pop(req_id, None)
        return None
    try:
        msg = await asyncio.wait_for(fut, timeout=KBARS_REQ_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        _kbars_pending.pop(req_id, None)
        print(f"  [kbars查詢] {code} 逾時（{KBARS_REQ_TIMEOUT_SEC}秒）："
              "常駐行程可能沒開或正在忙", flush=True)
        return None
    bars = msg.get("bars") or []
    if not bars:
        # 常駐行程有回覆但沒有資料：把它給的原因印出來。第一版這裡直接 return None，
        # 結果兩邊 log 都是空的，只能靠猜——查不到的原因本身就是最該看見的東西。
        print(f"  [kbars查詢] {code} 無資料：{msg.get('error') or '常駐行程未附原因'}", flush=True)
        return None
    result = {
        "code": code,
        "mode": "api-kbars-1m",
        "source": ("shioaji_quotes.py 在既有常駐連線上呼叫 api.kbars() 查詢"
                   "（未另開連線），live server 快取 60 秒"),
        "trade_date": msg.get("trade_date"),
        "generated_at": msg.get("ts"),
        "market_status": MEM.market_status,
        "bars": bars,
    }
    _kbars_cache[code] = (now, result)
    return result


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


@app.get("/ca.crt")
def get_ca_cert():
    """2026-09-04（HTTPS方案A）：回傳本機自簽CA的公開憑證（DER格式），手機安裝這個之後
    才會信任伺服器葉憑證，才能在HTTPS模式下連線不跳警告。**這個端點刻意不驗token**——
    CA公開憑證本身不是機密（機密是私鑰，私鑰永遠留在這台機器的secrets/裡，這個端點
    完全沒有讀取私鑰的程式碼路徑），任何人下載這份憑證也只能「信任這台機器簽的憑證」，
    不能拿它偽造新憑證或存取任何資料。"""
    if not CA_CRT_PATH.exists():
        raise HTTPException(status_code=404, detail="CA憑證尚未產生：先在本機執行 python research/gen_local_ca.py")
    return Response(content=CA_CRT_PATH.read_bytes(), media_type="application/x-x509-ca-cert",
                     headers={"Content-Disposition": "attachment; filename=alpha-ca.crt"})


@app.get("/health")
def health():
    """唯一不需要token的端點——只回報「伺服器活著」，不含任何報價/
    帳戶資訊，跟ibkr_order_server.py的/health端點同一個設計精神
    （純粹的存活探測，不算資訊洩漏）。"""
    # 2026-09-06（連線一.2）shioaji_connected 的定義寫清楚，避免看的人誤會：
    # 這裡回報的是「有沒有在收到 tick」，不是「Shioaji session 是否登入中」——
    # live server 本來就沒有 Shioaji 連線（那在 shioaji_quotes.py 那個行程裡），
    # 它只看得到有沒有 tick 從 loopback UDP 推進來。收盤時段沒有 tick 是正常的。
    _, hot_status = _hot_state()
    _last_tick = MEM.last_tick_at
    _tick_age = None
    if _last_tick is not None:
        _tick_age = (datetime.now(TW_TZ) - _last_tick).total_seconds()
    return {
        "ok": True,
        "uptime_sec": round(time.time() - SERVER_STARTED_AT, 1),
        "build": BUILD_SHA,
        "started_at": datetime.fromtimestamp(SERVER_STARTED_AT, TW_TZ).isoformat(),
        "source_mtime": datetime.fromtimestamp(_source_mtime(), TW_TZ).isoformat(),
        # 行程啟動時間早於原始碼修改時間 ⇒ 記憶體裡跑的是舊程式，必須重啟。
        # 留 5 秒容差：啟動當下寫檔的競態不算。
        "source_hash": SOURCE_HASH_AT_START,
        "stale_process": bool(SOURCE_HASH_AT_START and _source_hash()
                              and SOURCE_HASH_AT_START != _source_hash()),
        "shioaji_connected": bool(_tick_age is not None and _tick_age < 120),
        "shioaji_connected_note": "定義＝120 秒內有收到 tick。收盤時段沒有 tick 是正常的，"
                                  "不代表 shioaji_quotes.py 沒在跑",
        "last_tick_age_sec": round(_tick_age, 1) if _tick_age is not None else None,
        "sinopac_file_exists": QUOTES_SINOPAC_PATH.exists(),
        "ibkr_file_exists": QUOTES_IBKR_PATH.exists(),
        "hot_file_status": hot_status,          # hot-file / hot-file-stale / hot-file-missing
        "stream_mode": SSE_MODE_PUSH if MEM.fresh() else SSE_MODE_POLL,  # 當下實際模式：有新鮮tick=tick-push，否則退回2秒輪詢比對
        "tick_ingress": f"udp://{TICK_INGRESS_HOST}:{TICK_INGRESS_PORT}",
        "ticks_received": MEM.ticks_received,
        "tick_rejected": MEM.rejected,
        "last_tick_at": MEM.last_tick_at.astimezone(TW_TZ).isoformat(timespec="seconds") if MEM.last_tick_at else None,
        "kbars_mode": KBARS_MODE,               # /live/kbars是tick聚合，不是api.kbars()
        "token_required_on_live_endpoints": True,  # 三個/live端點一律要token，不因私有網路跳過
        "us_kbars": "not_implemented",
        "index_quotes_in_memory": sum(1 for k in MEM.quotes if _is_index_key(k)),  # 2026-09-04四修.二：TPEX+37類股
        "https_enabled": ENABLE_HTTPS,  # 2026-09-04 HTTPS方案A：目前實際監聽模式（見ENABLE_HTTPS說明）
        # 2026-09-06：把 CORS 設定攤在 /health 裡，切網域時可以直接看伺服器認的是哪些來源，
        # 不用去翻程式碼或猜（跨來源失敗的錯誤訊息在瀏覽器端通常很不具體）。
        "cors": {"allow_origins": ALLOW_ORIGINS, "allow_headers": ALLOW_HEADERS,
                 "allow_credentials": True},
        # 2026-09-06（實測.一.3）動態訂閱現況，方便對照「App 推了什麼」與「行程訂了什麼」
        # 2026-09-06（實測.二.補）今日 api.kbars() 用量。官方盤中上限 270 次/日、
        # 10 秒 50 次，超過會暫停服務一分鐘、反覆違規停權，所以要看得到。
        "kbars_usage": {"calls_today": MEM.kbars_calls_today,
                        "daily_budget": MEM.kbars_daily_budget},
        "dynamic_subscriptions": (lambda d: {
            "count": len(d.get("codes") or []) if d else 0,
            "updated_at": (d or {}).get("updated_at"),
            "limit": MAX_DYNAMIC_SUBSCRIPTIONS,
        })(_read_json_safe(WATCHLIST_PATH)),
        "ca_crt_available": CA_CRT_PATH.exists(),
    }


if __name__ == "__main__":
    print(f"[build] git sha={BUILD_SHA}　原始碼修改時間="
          f"{datetime.fromtimestamp(_source_mtime(), TW_TZ).isoformat()}", flush=True)
    print(f"本機即時報價伺服器啟動於 http://0.0.0.0:{SERVER_PORT}", flush=True)
    print(f"本機驗證token（貼進App設定頁「即時伺服器」卡片）：{LOCAL_TOKEN}", flush=True)
    print(f"熱檔路徑：{LIVE_STATE_PATH}（備援）；tick ingress udp://{TICK_INGRESS_HOST}:{TICK_INGRESS_PORT}；stream_mode=有新鮮tick時{SSE_MODE_PUSH}、否則{SSE_MODE_POLL}；kbars_mode={KBARS_MODE}", flush=True)
    print("**這是唯讀伺服器，完全沒有任何下單/改單能力，程式碼裡也沒有import任何下單相關模組**", flush=True)
    ssl_kwargs = {}
    if ENABLE_HTTPS:
        if not (SSL_KEYFILE.exists() and SSL_CERTFILE.exists()):
            print(f"[錯誤] ALPHA_LIVE_SERVER_HTTPS=1但找不到憑證檔案（{SSL_KEYFILE}/{SSL_CERTFILE}）。"
                  f"先跑 python research/gen_local_ca.py 產生，或不要設這個環境變數改用HTTP。", flush=True)
            raise SystemExit(1)
        ssl_kwargs = {"ssl_keyfile": str(SSL_KEYFILE), "ssl_certfile": str(SSL_CERTFILE)}
        print(f"HTTPS模式啟用（自簽憑證，手機需先安裝 secrets/alpha-ca.crt，透過/ca.crt下載）：https://0.0.0.0:{SERVER_PORT}", flush=True)
    else:
        print(f"HTTP模式（預設；設環境變數ALPHA_LIVE_SERVER_HTTPS=1可切HTTPS，見模組docstring）", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, **ssl_kwargs)
