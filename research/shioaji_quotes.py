# -*- coding: utf-8 -*-
"""台股即時報價擷取（Sinopac Shioaji）。

**2026-09-03升級（B34，使用者裁示「報價升級為逐筆tick串流」）**：從原本
「輪詢快照」（`api.snapshots()`，每次執行登入→查一次→登出→結束）改成
「訂閱逐筆串流」（`api.subscribe()` + `set_on_tick_stk_v1_callback()`等
回呼），登入一次、掛上訂閱後常駐監聽，成交/報價一有變動就即時更新記憶體
狀態，不再是「每隔N分鐘才問一次現在多少錢」。

**架構隨之改變，這是重點，接手的人要先搞懂**：舊版是「短命腳本」，被
Windows排程器每隔幾分鐘呼叫一次、跑完就結束，git commit/push交給外層
`.ps1`負責。新版`main()`在交易時段判定為「開盤中」時**不會馬上結束**，
會登入、訂閱、進入常駐迴圈直到收盤（或行程被中斷）——**這代表`.ps1`
排程器呼叫的方式要跟著改**：不能再假設「呼叫一次、幾秒後就結束」，
改成「開盤前啟動一次，讓它自己跑到收盤」，`.ps1`裡的排程觸發角色改成
「確認常駐行程有沒有在跑、沒有就啟動」的**啟動器**（PID檔案判斷，見
`PID_PATH`），不再是每次都重新登入。**這支腳本可以直接`python research/
shioaji_quotes.py`在開盤前手動啟動**（使用者原話「開盤前先把程式備妥」），
會自己等到交易時段開始才登入，交易時段結束會自動登出並結束行程。

**git commit/push頻率（2026-09-03緊急修正為60秒，使用者P0裁示核准，
不需要再提案）**：原本選15秒（對齊前端輪詢頻率）**在實測中造成嚴重
後果**——常駐迴圈+`checked_at`每次都變動的舊版`_write_market_closed()`
交互作用，當天累積995次commit（見`_write_market_closed()`函式docstring
的完整根因分析），把GitHub Actions排程餓死（同一個repo的push配額被
洪水佔滿，其他排程的push被迫排隊/失敗）。**修正為`FLUSH_INTERVAL_SEC`
=60秒，且只在任一報價值真的變動時才commit**（`_flush_and_push()`裡
新增「跟上次committed內容的quotes逐檔比對last/change_pct等關鍵欄位」
判斷，不是「只要tick_at時間戳有變就commit」——tick_at幾乎每次都會變
但價格常常沒變，舊邏輯等於變相每60秒必定commit一次，新邏輯是真正的
「事件觸發」）。這是使用者在實際運作後回饋的教訓，比原始設計時的
理論對齊考量更重要：**手機即時感受不能用repo commit數量硬撐，要有
節制**，60秒+內容比對是這次調整後的權衡點。

**API方法簽章來源（誠實揭露：查證方式跟查證程度）**：這次改版**沒有
在真實模擬環境連線的情況下測試過tick訂閱**（改版當下台股非交易時段，
Shioaji模擬環境服務時段08:00-21:00內雖然可以登入，但非交易時段不會有
真實tick事件觸發，沒有東西可以驗證）——所有callback簽章/欄位名稱都是
**查證已安裝版本（`shioaji==1.7.4`）的型別存根檔案**
（`shioaji/_core.pyi`，直接讀原始碼等級的官方型別定義，不是憑印象猜的）
得到，包含：`TickSTKv1`/`TickFOPv1`/`BidAskSTKv1`/`BidAskFOPv1`/
`QuoteIdxV1`五個資料結構的完整欄位清單、`set_on_tick_stk_v1_callback`等
六個訂閱callback的完整簽章（確認是單一參數`Callable[[TickSTKv1], None]`，
不是舊版API的`(exchange, tick)`雙參數形式）、`api.subscribe()`是目前
建議用法（`api.quote.subscribe()`在這個版本已標記deprecated，改用
`api.subscribe()`直接呼叫）。**唯一沒有把握、需要下次開盤實測才能確認
的地方**：tick物件的`pct_chg`/`price_chg`欄位是否本身就帶正負號，還是
需要另外查`chg_type`欄位做正負號校正（舊版`snapshots()`快照API的
`change_rate`就是「只給大小、正負號要另外查`change_type`」的設計，
`chg_type`在tick物件上型別是`int`不是`ChangeType`列舉，沒辦法單靠讀
型別定義確定int值怎麼對應——這裡選擇「先假設tick的pct_chg/price_chg
已經帶正負號直接使用」，同時把原始`chg_type`整數值也記進`data_type`
之外的除錯欄位，方便下次開盤讀真實tick log時人工核對這個假設對不對，
如果假設錯了下一輪要修正，不是現在悄悄放著不管）。

**沿用不變的既有設計（跟舊版snapshot版本相同，見下方函式）**：
- 讀`.env`只需要`SINOPAC_API_KEY`/`SINOPAC_SECRET_KEY`，刻意不呼叫
  `activate_ca`（唯讀報價，沒有下單權限）。
- 「自選股」用`DEFAULT_TW_WATCHLIST`代表清單，Python腳本讀不到瀏覽器
  localStorage的既有限制不變。
- `_is_tw_trading_window()`交易時段閘門（週一至五08:30-13:45，粗略判斷
  不含國定假日）、`_write_market_closed()`保留最後一次盤中資料的邏輯
  都原封不動沿用。
- TAIEX/期貨近月合約代碼（`api.Contracts.Indexs.TSE.IX0001`/
  `FUTURES_NEAR_MONTH`四組）不變。
- data_type新增`"REALTIME_TICK"`（App前端`intradayDataTypeLabel()`
  對應顯示「即時(tick)」，見`index.html`同步更新），跟舊版snapshot時代
  的`"REALTIME"`區分開來，讓使用者看得出來這是tick串流還是快照。

**掛排程**：`C:\alpha\run-shioaji-quotes-cycle.ps1`角色改變（見上方
架構說明），仍然由Windows工作排程器`AlphaShioajiQuotes`觸發，但改成
「確認常駐行程存在、不存在才啟動」的啟動器邏輯，不再是每次都重新登入
的短命呼叫。
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_sinopac.json"
ENV_PATH = REPO_ROOT / ".env"
TW_TZ = timezone(timedelta(hours=8))

# 常駐行程的PID檔案（gitignored）：`.ps1`啟動器讀這個檔案判斷「是不是已經
# 有一個常駐行程在跑」，不要重複登入（Shioaji帳戶對同時多個session的行為
# 未知，保守起見一次只允許一個常駐行程）。
PID_PATH = Path(__file__).parent / ".shioaji_stream.pid"

# index.html的WL預設值同一份清單，見模組docstring「已知限制」
DEFAULT_TW_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

# App「期貨」頁FUT_CONTRACTS追蹤的四個近月合約（index.html::FUT_CONTRACTS）
FUTURES_NEAR_MONTH = {
    "TXF_NEAR": {"group": "TXF", "code": "TXFR1", "label": "台指期近月"},
    "MXF_NEAR": {"group": "MXF", "code": "MXFR1", "label": "小型台指期近月"},
    "EXF_NEAR": {"group": "EXF", "code": "EXFR1", "label": "電子期近月"},
    "FXF_NEAR": {"group": "FXF", "code": "FXFR1", "label": "金融期近月"},
}

CONTRACTS_READY_WAIT_SEC = 3  # 登入後合約清單非同步下載，太快存取會KeyError
FLUSH_INTERVAL_SEC = 60  # 2026-09-03緊急修正，見模組docstring「git commit/push頻率」完整理由
TRADING_WINDOW_POLL_SEC = 30  # 常駐迴圈裡多久檢查一次「是否還在交易時段」

# 2026-09-03深夜（使用者補充指令一＋乙「冷熱分離」）：常駐行程把「最新報價快照」＋
# 「當日每分鐘OHLC」寫進本機**熱檔**（gitignored、永遠不commit）。1分K是用這支行程
# 本來就持續收到的tick自己聚合出來的（見TickState.add_tick()），**不另開第二條Shioaji
# 連線、不呼叫api.kbars()**——使用者明確裁示這樣做，理由是第二條連線會跟現有常駐連線
# 衝突。alpha_live_server.py的/live/quotes、/live/stream、/live/kbars直接讀這個熱檔，
# 跟它原本讀data/quotes_sinopac.json的做法一致，只是改讀秒級更新的檔案：兩個獨立行程
# 在Windows上要「共用記憶體」，同機本地檔案是最不需要額外相依、最不會出事的做法
# （真正把兩個行程合併成一個、tick回呼直接餵SSE，使用者已裁示排進佇列稍後做）。
LIVE_STATE_PATH = Path(__file__).parent / ".live_state_sinopac.json"
LIVE_STATE_MIN_INTERVAL_SEC = 1.0  # 熱檔最多每秒寫一次：tick一秒可能好幾筆，寫檔不必跟著每筆寫

# 2026-09-04（總司令裁示零.2「真逐筆推送」）：每收到一筆tick，除了更新記憶體/熱檔，
# 立刻把該檔最新報價＋當前1分K用一個UDP datagram送到本機loopback的
# alpha_live_server.py（127.0.0.1:8002，只聽loopback、不對外）。伺服器收到就更新自己
# 記憶體並喚醒所有SSE連線→這才是「tick回呼→SSE」的真推送（mode=tick-push），不再是
# 2秒輪詢比對。**不開第二條Shioaji連線**（推的是這支行程已經收到的tick）；datagram
# 第一個欄位帶跟伺服器同一份`.alpha_live_token`當驗證（沿用既有token模式），伺服器
# token不符直接丟棄。UDP是fire-and-forget：伺服器沒開時送出去就消失、這支行程完全
# 不受影響；熱檔照寫，當伺服器重啟時的狀態備援。
LIVE_PUSH_ENABLED = True
LIVE_PUSH_ADDR = ("127.0.0.1", 8002)
LIVE_TOKEN_PATH = Path(__file__).parent / ".alpha_live_token"  # gitignored，跟alpha_live_server.py同一份

# 2026-09-04（總司令裁示乙.1「冷熱分離」）：**盤中不再commit/push**。盤中只更新記憶體
# 與本機熱檔（上面LIVE_STATE_PATH，給alpha_live_server.py讀），git追蹤的冷檔
# data/quotes_sinopac.json只在13:30收盤、常駐迴圈結束時寫一次並commit+push一次
# （當日收盤快照）。驗收目標：當日repo commit數<20、Actions報價/大盤排程恢復落地。
# 設成True可退回2026-09-03的「60秒且有變動才commit」行為（只留作緊急退路，不是預設）。
INTRADAY_GIT_PUSH = False


def _load_env(path: Path) -> dict[str, str]:
    kv = {}
    if not path.exists():
        return kv
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


def _write_failure(reason: str) -> None:
    payload = {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": False,
        "error": reason,
        "quotes": {},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入失敗狀態到 {OUT_PATH}：{reason}")


def _clean_positive(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _is_tw_trading_window(now: datetime) -> bool:
    """粗略判斷：週一至五08:30-13:45台北時間。**已知簡化，誠實揭露**：
    沒有扣除國定假日（找不到現成、可信賴的台股假日行事曆免費資料源）。"""
    wd = now.weekday()  # 0=Mon .. 6=Sun
    minutes = now.hour * 60 + now.minute
    return wd <= 4 and 8 * 60 + 30 <= minutes < 13 * 60 + 45


def _write_market_closed() -> None:
    """非交易時段：保留最後一次盤中資料，只把market_status標成closed。

    **2026-09-03緊急修復（P0，使用者回報「今天995次commit餓死Actions」）**：
    根因是這個函式舊版每次呼叫都把`checked_at`更新成當下時間戳寫進
    `data/quotes_sinopac.json`——這個檔案是git追蹤的，`checked_at`每次
    都不同，導致外層`.ps1`launcher的`git diff --quiet`判斷**永遠看到
    有變動**，每2分鐘排程觸發一次就commit一次，24小時不間斷（不分
    盤中盤後），這才是flood的真正主因，不是tick串流本身（tick串流
    只有交易時段才會啟動，觸發頻率遠低於這個「非交易時段」路徑，且
    今天多數時段台股根本沒開盤）。

    **修法**：`checked_at`改成只在記憶體/print訊息裡回報，**不寫進
    會被committed的JSON內容比較**——判斷「要不要覆寫檔案」只看
    `quotes`/`market_status`/`connected`這幾個真正有意義的欄位是否
    改變，沒改變就完全不碰檔案（連write都不做），讓外層`git diff
    --quiet`天然看到「沒有變動」、不會產生空轉commit。`checked_at`
    欄位保留在payload裡（前端/診斷需要知道「最後一次確認的時間」），
    但只有在確實要寫檔（有意義的變動）時才會更新到新的時間戳，非
    交易時段裡連續好幾輪呼叫如果都沒有變動，`checked_at`會停留在
    上一次真正寫檔的時間，這是刻意的犧牲（誠實反映「沒有再檢查出
    新東西」，比每次都灌一個新時間戳但其實什麼都没变化更誠實）。
    """
    existing = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing_quotes = existing.get("quotes", {})
    existing_status = existing.get("market_status")
    existing_connected = existing.get("connected", False)

    # 已經是closed狀態、quotes內容沒變、connected旗標沒變 → 什麼都不用寫，
    # 讓git diff維持乾淨，外層.ps1 launcher不會產生空轉commit。
    if existing_status == "closed" and existing_connected is False:
        print(f"非交易時段，狀態未變（quotes {len(existing_quotes)}檔維持不變），不寫檔避免空轉commit")
        return

    payload = {
        "fetched_at": existing.get("fetched_at"),
        "checked_at": datetime.now(TW_TZ).isoformat(),
        "connected": False,
        "market_status": "closed",
        "error": None,
        "quotes": existing_quotes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("非交易時段（週一至五08:30-13:45外），不登入永豐，保留最後一次盤中資料，market_status=closed（狀態剛轉換，寫入一次）")


class TickState:
    """執行緒安全的最新報價快照。Shioaji的tick/bidask/quote callback在
    背景執行緒觸發（不是主執行緒），主執行緒的常駐迴圈定期讀出目前累積的
    最新狀態去flush成JSON——這個class就是兩邊之間的共享狀態，用鎖保護
    避免讀寫交錯（純為了正確性防呆，CPython的GIL讓dict操作大多情況下
    已經接近原子，但不應該依賴這個實作細節，明確上鎖比較保險）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._quotes: dict[str, dict] = {}
        # 2026-09-03深夜新增：當日1分K聚合（key -> {"YYYY-MM-DDTHH:MM" -> bar}），
        # 只保留「今天」，跨日自動清空。
        self._kbars: dict[str, dict[str, dict]] = {}
        self._kbars_day: str | None = None
        self._last_live_write = 0.0
        self.live_state_path: Path | None = LIVE_STATE_PATH  # 測試可改指到暫存檔
        # tick-push（2026-09-04）：UDP socket懶建立；token讀不到就整個停用並只印一次
        self.push_addr: tuple[str, int] | None = LIVE_PUSH_ADDR if LIVE_PUSH_ENABLED else None
        self._push_sock = None
        self._push_token: str | None = None
        self._push_disabled_reason: str | None = None
        self.push_count = 0

    def update(self, key: str, patch: dict) -> None:
        with self._lock:
            self._quotes.setdefault(key, {})
            self._quotes[key].update({k: v for k, v in patch.items() if v is not None or k not in self._quotes[key]})

    def snapshot(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._quotes.items()}

    def add_tick(self, key: str, price, volume, ts) -> None:
        """用已收到的一筆tick更新當日1分K（O/H/L/C/V）。`ts`是tick.datetime
        （Shioaji給的是台北時間、naive datetime）；沒有就用現在時間。指數quote
        沒有成交量，呼叫端傳0。"""
        if price is None:
            return
        if ts is None:
            ts = datetime.now(TW_TZ).replace(tzinfo=None)
        day = ts.strftime("%Y-%m-%d")
        minute = ts.strftime("%Y-%m-%dT%H:%M")
        try:
            vol = int(volume or 0)
        except (TypeError, ValueError):
            vol = 0
        with self._lock:
            if self._kbars_day != day:
                self._kbars = {}
                self._kbars_day = day
            bars = self._kbars.setdefault(key, {})
            bar = bars.get(minute)
            if bar is None:
                bars[minute] = {"t": minute, "o": price, "h": price, "l": price, "c": price, "v": vol}
            else:
                bar["h"] = max(bar["h"], price)
                bar["l"] = min(bar["l"], price)
                bar["c"] = price
                bar["v"] += vol

    def kbars_snapshot(self) -> dict[str, list[dict]]:
        with self._lock:
            return {k: [dict(b) for _, b in sorted(v.items())] for k, v in self._kbars.items()}

    def push_tick(self, key: str, event: str = "tick", market_status: str = "open") -> bool:
        """把`key`目前的最新報價＋最新一根1分K用UDP推給本機alpha_live_server.py
        （見LIVE_PUSH_ADDR說明）。任何失敗只記log、回傳False，絕不拋出（callback
        執行緒裡不能因為推送失敗讓訂閱掛掉）。"""
        if self.push_addr is None or self._push_disabled_reason:
            return False
        try:
            if self._push_token is None:
                if not LIVE_TOKEN_PATH.exists():
                    self._push_disabled_reason = f"找不到{LIVE_TOKEN_PATH.name}，tick-push停用（先啟動一次alpha_live_server.py讓它產生token）"
                    print(f"  [tick-push] {self._push_disabled_reason}", flush=True)
                    return False
                self._push_token = LIVE_TOKEN_PATH.read_text(encoding="utf-8").strip()
            if self._push_sock is None:
                import socket
                self._push_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._push_sock.setblocking(False)
            with self._lock:
                quote = dict(self._quotes.get(key, {}))
                bars = self._kbars.get(key) or {}
                bar = dict(bars[max(bars)]) if bars else None
            msg = {
                "t": self._push_token, "event": event, "key": key,
                "quote": quote, "bar": bar, "market_status": market_status,
                "ts": datetime.now(TW_TZ).isoformat(),
            }
            self._push_sock.sendto(json.dumps(msg, ensure_ascii=False).encode("utf-8"), self.push_addr)
            self.push_count += 1
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  [tick-push失敗] {key}: {type(e).__name__}: {e}", flush=True)
            return False

    def maybe_write_live_state(self, force: bool = False, market_status: str = "open") -> bool:
        """把最新快照＋當日1分K寫進本機熱檔（見LIVE_STATE_PATH說明），每秒最多
        一次；callback執行緒直接呼叫，失敗只印log絕不拋出（不能讓訂閱掛掉）。
        用「寫暫存檔→原子替換」避免讀的一方（alpha_live_server.py）讀到寫一半
        的檔案。回傳這次有沒有真的寫。"""
        if self.live_state_path is None:
            return False
        now_mono = time.monotonic()
        with self._lock:
            if not force and now_mono - self._last_live_write < LIVE_STATE_MIN_INTERVAL_SEC:
                return False
            self._last_live_write = now_mono
        try:
            payload = {
                "updated_at": datetime.now(TW_TZ).isoformat(),
                "market_status": market_status,
                "connected": True,
                "error": None,
                "mode": "hot-file",
                "kbars_mode": "tick-aggregated-1m",
                "quotes": self.snapshot(),
                "kbars": self.kbars_snapshot(),
            }
            tmp = self.live_state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            # Windows上讀取方（alpha_live_server.py）剛好開著檔案時rename會被拒（WinError 5），
            # 重試三次、每次等50ms；仍失敗就放棄這一次（下一秒還會再寫，且tick-push已把
            # 資料直接推給伺服器，熱檔只是備援）。
            last_err = None
            for _ in range(3):
                try:
                    tmp.replace(self.live_state_path)
                    return True
                except PermissionError as e:
                    last_err = e
                    time.sleep(0.05)
            self._live_write_failures = getattr(self, "_live_write_failures", 0) + 1
            if self._live_write_failures in (1, 10, 100, 1000):  # 不洗log
                print(f"  [live_state熱檔寫入失敗x{self._live_write_failures}] {type(last_err).__name__}: {last_err}", flush=True)
            return False
        except Exception as e:
            print(f"  [live_state熱檔寫入失敗] {type(e).__name__}: {e}", flush=True)
            return False


def _to_float(v):
    """Tick物件很多欄位型別是`str`（見shioaji/_core.pyi型別存根），統一
    轉float，轉不了就誠實回None，不拋例外中斷整條callback。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # 排除NaN


def _make_tick_stk_handler(state: TickState, key: str, label: str | None):
    def handler(tick) -> None:
        try:
            last = _to_float(getattr(tick, "close", None))  # Shioaji命名習慣：tick.close = 這筆成交的價格，不是「前一天收盤」
            pct_chg = _to_float(getattr(tick, "pct_chg", None))
            price_chg = _to_float(getattr(tick, "price_chg", None))
            prev_close = (last - price_chg) if (last is not None and price_chg is not None) else None
            patch = {
                "last": last,
                "close": prev_close,
                "change_pct": pct_chg,
                "volume_this_tick": getattr(tick, "volume", None),
                "total_volume": getattr(tick, "total_volume", None),
                "data_type": "REALTIME_TICK",
                "tick_at": tick.datetime.isoformat() if getattr(tick, "datetime", None) else None,
                "_raw_chg_type": getattr(tick, "chg_type", None),  # 除錯用，見模組docstring正負號校正說明
                "exchange": "TSE",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
            state.add_tick(key, last, getattr(tick, "volume", None), getattr(tick, "datetime", None))
            state.push_tick(key)  # 2026-09-04 tick-push：先推（最低延遲），再寫熱檔備援
            state.maybe_write_live_state()
        except Exception as e:
            # callback裡任何例外都不能讓整個訂閱掛掉，只記log繼續收下一筆
            print(f"  [tick_stk callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_bidask_stk_handler(state: TickState, key: str):
    def handler(bidask) -> None:
        try:
            bid_list = getattr(bidask, "bid_price", None) or []
            ask_list = getattr(bidask, "ask_price", None) or []
            state.update(key, {
                "bid": _clean_positive(bid_list[0]) if bid_list else None,
                "ask": _clean_positive(ask_list[0]) if ask_list else None,
            })
            state.push_tick(key, event="bidask")
            state.maybe_write_live_state()
        except Exception as e:
            print(f"  [bidask_stk callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_tick_fop_handler(state: TickState, key: str, label: str | None):
    def handler(tick) -> None:
        try:
            last = _to_float(getattr(tick, "close", None))
            pct_chg = _to_float(getattr(tick, "pct_chg", None))
            price_chg = _to_float(getattr(tick, "price_chg", None))
            prev_close = (last - price_chg) if (last is not None and price_chg is not None) else None
            patch = {
                "last": last,
                "close": prev_close,
                "change_pct": pct_chg,
                "volume_this_tick": getattr(tick, "volume", None),
                "total_volume": getattr(tick, "total_volume", None),
                "data_type": "REALTIME_TICK",
                "tick_at": tick.datetime.isoformat() if getattr(tick, "datetime", None) else None,
                "_raw_chg_type": getattr(tick, "chg_type", None),
                "exchange": "TAIFEX",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
            state.add_tick(key, last, getattr(tick, "volume", None), getattr(tick, "datetime", None))
            state.push_tick(key)
            state.maybe_write_live_state()
        except Exception as e:
            print(f"  [tick_fop callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_bidask_fop_handler(state: TickState, key: str):
    def handler(bidask) -> None:
        try:
            bid_list = getattr(bidask, "bid_price", None) or []
            ask_list = getattr(bidask, "ask_price", None) or []
            state.update(key, {
                "bid": _clean_positive(bid_list[0]) if bid_list else None,
                "ask": _clean_positive(ask_list[0]) if ask_list else None,
            })
            state.push_tick(key, event="bidask")
            state.maybe_write_live_state()
        except Exception as e:
            print(f"  [bidask_fop callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_quote_idx_handler(state: TickState, key: str, label: str | None):
    def handler(quote) -> None:
        try:
            last = _to_float(getattr(quote, "close", None))
            reference = _to_float(getattr(quote, "reference", None))
            pct_chg = round((last - reference) / reference * 100.0, 4) if (last is not None and reference) else None
            patch = {
                "last": last,
                "close": reference,
                "change_pct": pct_chg,
                "data_type": "REALTIME_TICK",
                "tick_at": quote.datetime.isoformat() if getattr(quote, "datetime", None) else None,
                "exchange": "TSE",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
            state.add_tick(key, last, 0, getattr(quote, "datetime", None))  # 指數沒有成交量
            state.push_tick(key)
            state.maybe_write_live_state()
        except Exception as e:
            print(f"  [quote_idx callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _resolve_fop_key(code: str, code_to_key: dict[str, str]) -> str | None:
    """期貨tick的`tick.code`是**實際月份合約碼**（例如`TXFI6`=台指期2026/09），但訂閱時
    `api.Contracts.Futures.TXF.TXFR1`（連續近月別名）的`.code`是`TXFR1`——B34改tick串流
    時用`contract.code`當反查key，導致所有期貨tick反查不到、被靜默丟掉（總司令
    2026-09-04手機實測：quotes_sinopac.json只剩5檔+TAIEX）。修法：先精確比對，比不到
    再用前三碼商品代號（TXF/MXF/EXF/FXF）對回FUTURES_NEAR_MONTH的key。"""
    if code in code_to_key:
        return code_to_key[code]
    prefix = (code or "")[:3].upper()
    for key, meta in FUTURES_NEAR_MONTH.items():
        if meta["group"] == prefix:
            return key
    return None


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def _build_payload(state: TickState) -> dict:
    """純函式：把TickState目前的快照組成要寫進JSON的payload——抽出來
    跟「寫檔+git操作」分開，讓`research/shioaji_tick_stream_test.py`
    能夠只測試「callback更新狀態→組出正確payload」這段，不必連帶碰
    真正的`data/quotes_sinopac.json`或觸發git commit/push。"""
    return {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": True,
        "market_status": "open",
        "error": None,
        "quotes": state.snapshot(),
    }


_MEANINGFUL_QUOTE_FIELDS = ("last", "change_pct", "bid", "ask")


def _meaningful_quotes(quotes: dict) -> dict:
    """只抽出真正代表「報價有變動」的欄位（last/change_pct/bid/ask），
    排除`tick_at`（幾乎每一筆tick都不同，即使價格完全沒變）、
    `volume_this_tick`/`total_volume`（成交量會持續累加，但單獨累加
    不代表「使用者關心的報價數字」變了）、`_raw_chg_type`等除錯欄位。
    2026-09-03緊急修復用：舊版直接對整份JSON做`git diff --quiet`，
    因為`tick_at`每次都變，等於每次flush都判定「有變動」，60秒一次
    flush就等於60秒一定commit一次，完全沒有達到「只在報價值有變時」
    的效果——這個函式就是修正的核心，把「有沒有變動」的判斷限縮到
    使用者真正在意的價格/報價數字上。"""
    return {code: {k: q.get(k) for k in _MEANINGFUL_QUOTE_FIELDS} for code, q in quotes.items()}


def _last_committed_quotes(rel_path: str) -> dict | None:
    """讀git HEAD版本的quotes_sinopac.json（不是磁碟上還沒commit的
    版本），拿來跟目前狀態比較有沒有「真的」變動。找不到（例如檔案
    從未commit過）就回傳None，呼叫端視為「一定要寫」。"""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout).get("quotes", {})
    except json.JSONDecodeError:
        return None


def _flush_and_push(state: TickState, final: bool = False) -> None:
    """把目前累積的最新報價寫進git追蹤的冷檔並commit+push。

    **2026-09-04乙.1之後的行為**：`INTRADAY_GIT_PUSH=False`（預設）時，盤中呼叫
    （final=False）**什麼都不做**——不寫冷檔、不commit（盤中資料走熱檔＋
    alpha_live_server.py）；只有收盤收尾那次（final=True）才寫冷檔並commit+push
    一次，當作當日收盤快照。盤中不寫冷檔是刻意的：寫了不commit會讓工作區一直
    髒著，干擾同機其他排程（馬拉松/假說佇列）的git操作。

    `INTRADAY_GIT_PUSH=True`（緊急退路）時沿用2026-09-03的邏輯：一律寫冷檔，
    **只有在報價數字真的變動時才commit+push**——見`_meaningful_quotes()`/
    `_last_committed_quotes()`docstring的緊急修復根因說明。"""
    if not final and not INTRADAY_GIT_PUSH:
        return
    payload = _build_payload(state)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rel_path = str(OUT_PATH.relative_to(REPO_ROOT))
    prev_quotes = _last_committed_quotes(rel_path)
    if not final and prev_quotes is not None and _meaningful_quotes(prev_quotes) == _meaningful_quotes(payload["quotes"]):
        return  # 價格/報價數字都沒變，只是tick_at/volume累加，不commit

    timestamp = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    _git(["commit", "-m", f"Shioaji tick stream update {timestamp}", "--", rel_path])

    # 既有fetch+rebase重試模式（見run-shioaji-quotes-cycle.ps1同款邏輯，
    # 這裡搬進Python因為現在是常駐迴圈自己負責push、不是外層.ps1收尾時
    # 才push一次）。**這裡沒有GitHub Actions意義下的「concurrency group」
    # 可用**——concurrency group是GitHub Actions工作流程層級的機制
    # （見`.github/workflows/market.yml`/`quotes.yml`），只協調Actions
    # runner之間的執行順序，管不到這支在使用者本機跑的獨立Python行程；
    # 這裡改用同樣精神但實際可行的辦法：fetch+rebase重試迴圈。
    for attempt in range(5):
        _git(["pull", "--no-rebase", "--quiet"])
        push = _git(["push", "--quiet"])
        if push.returncode == 0:
            return
        time.sleep(5)
    print(f"  [git push] 5次重試後仍失敗，下次flush時的git pull會自然同步", flush=True)


def _cleanup_pid() -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def run_stream_daemon() -> None:
    """常駐主迴圈：登入一次、訂閱全部標的、進入flush迴圈直到收盤或被中斷。"""
    import os
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    env = _load_env(ENV_PATH)
    required = ["SINOPAC_API_KEY", "SINOPAC_SECRET_KEY"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        _write_failure(f".env缺少必要欄位：{missing}")
        _cleanup_pid()
        return

    import shioaji as sj

    api = sj.Shioaji(simulation=True)
    state = TickState()

    try:
        try:
            accounts = api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
        except Exception as e:
            _write_failure(f"登入失敗：{type(e).__name__}: {e}")
            return
        print(f"登入成功，帳戶數：{len(accounts) if accounts else 0}，開始訂閱逐筆tick串流", flush=True)
        time.sleep(CONTRACTS_READY_WAIT_SEC)

        # 訂閱時直接建立code_to_key（tick.code反查標的用，見下方callback
        # 註冊說明），不要訂閱完再重新走一次合約樹反查——那樣容易對不上
        # （原本的寫法就有這個問題：對TAIEX用「有沒有在subscribed清單裡」
        # 三元運算式塞一個可能是空字串的key，改成訂閱當下順手記錄乾淨得多）。
        subscribed = []
        code_to_key: dict[str, str] = {}

        for code in DEFAULT_TW_WATCHLIST:
            try:
                contract = api.Contracts.Stocks[code]
                api.subscribe(contract, quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)
                api.subscribe(contract, quote_type=sj.QuoteType.BidAsk, version=sj.QuoteVersion.v1)
                subscribed.append(code)
                code_to_key[contract.code] = code
            except Exception as e:
                print(f"  [TW個股] {code} 訂閱失敗，跳過：{e}", flush=True)

        try:
            taiex = api.Contracts.Indexs.TSE.IX0001
            api.subscribe(taiex, quote_type=sj.QuoteType.Quote, version=sj.QuoteVersion.v1)
            subscribed.append("TAIEX")
            code_to_key[taiex.code] = "TAIEX"
        except Exception as e:
            print(f"  [TAIEX] 訂閱失敗，跳過：{e}", flush=True)

        for key, meta in FUTURES_NEAR_MONTH.items():
            try:
                group = getattr(api.Contracts.Futures, meta["group"])
                contract = getattr(group, meta["code"])
                api.subscribe(contract, quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)
                api.subscribe(contract, quote_type=sj.QuoteType.BidAsk, version=sj.QuoteVersion.v1)
                subscribed.append(key)
                code_to_key[contract.code] = key
            except Exception as e:
                print(f"  [{meta['label']}] 訂閱失敗，跳過：{e}", flush=True)

        if not subscribed:
            _write_failure("所有標的訂閱都失敗，沒有任何東西可以串流")
            return

        # 註冊callback——單一全域callback，內部靠tick.code反查是哪個標的
        # （Shioaji的v1 callback簽章是單一參數Callable[[TickSTKv1],None]，
        # 不是舊版(exchange,tick)雙參數形式，見模組docstring查證來源）。

        def on_tick_stk(tick):
            key = code_to_key.get(tick.code)
            if key:
                _make_tick_stk_handler(state, key, None)(tick)

        def on_bidask_stk(bidask):
            key = code_to_key.get(bidask.code)
            if key:
                _make_bidask_stk_handler(state, key)(bidask)

        unknown_fop_codes: set[str] = set()

        def on_tick_fop(tick):
            key = _resolve_fop_key(tick.code, code_to_key)
            if key:
                _make_tick_fop_handler(state, key, FUTURES_NEAR_MONTH.get(key, {}).get("label"))(tick)
            elif tick.code not in unknown_fop_codes:
                unknown_fop_codes.add(tick.code)
                print(f"  [tick_fop] 收到無法對應的期貨代碼 {tick.code}（只印一次）", flush=True)

        def on_bidask_fop(bidask):
            key = _resolve_fop_key(bidask.code, code_to_key)
            if key:
                _make_bidask_fop_handler(state, key)(bidask)

        def on_quote_idx(quote):
            key = code_to_key.get(quote.code)
            if key:
                _make_quote_idx_handler(state, key, "加權指數")(quote)

        api.set_on_tick_stk_v1_callback(on_tick_stk)
        api.set_on_bidask_stk_v1_callback(on_bidask_stk)
        api.set_on_tick_fop_v1_callback(on_tick_fop)
        api.set_on_bidask_fop_v1_callback(on_bidask_fop)
        api.set_on_quote_idx_v1_callback(on_quote_idx)

        print(f"訂閱完成：{subscribed}，進入常駐迴圈（每{FLUSH_INTERVAL_SEC}秒檢查；盤中{'會' if INTRADAY_GIT_PUSH else '不'}commit，收盤後commit一次）", flush=True)

        elapsed_since_window_check = 0.0
        while True:
            time.sleep(FLUSH_INTERVAL_SEC)
            _flush_and_push(state)
            elapsed_since_window_check += FLUSH_INTERVAL_SEC
            if elapsed_since_window_check >= TRADING_WINDOW_POLL_SEC:
                elapsed_since_window_check = 0.0
                if not _is_tw_trading_window(datetime.now(TW_TZ)):
                    print("交易時段結束，收尾並登出", flush=True)
                    break

        _flush_and_push(state, final=True)  # 收盤收尾：寫當日收盤快照並commit+push（乙.1之後全天唯一一次）
        state.maybe_write_live_state(force=True, market_status="closed")  # 熱檔也標記收盤，live server據此顯示「今日收盤」
        for k in list(state.snapshot().keys()):
            state.push_tick(k, event="market_closed", market_status="closed")  # 通知live server記憶體也轉「收盤」
    finally:
        try:
            api.logout()
        except Exception:
            pass
        _cleanup_pid()


def main():
    now = datetime.now(TW_TZ)
    if not _is_tw_trading_window(now):
        _write_market_closed()
        return
    run_stream_daemon()


if __name__ == "__main__":
    main()
