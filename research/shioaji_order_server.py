# -*- coding: utf-8 -*-
"""Shioaji（永豐證券）paper下單本機伺服器（2026-09-01新增，逐字比照
`research/ibkr_order_server.py`的架構，使用者原話：「AI只擬計畫，送單
永遠使用者親按」，這支補的是台股那一半，跟IBKR美股那半分工不重疊）。

**⚠ 今晚（2026-09-01深夜，台股夜間休市）只驗證到login+activate_ca這一步，
沒有呼叫過`/submit_order`，沒有送過任何測試單。真正的下單測試留到台股
開盤（08:30後）且使用者親自在旁邊確認才做——這是使用者的明確裁示，不是
忘記測，之後接手的人看到這支檔案時，不要誤以為完整下單流程已經測過。**

**架構決策**：跟`ibkr_order_server.py`同一個理由——App是純前端PWA，
沒辦法主動觸發本機程式，開一個只監聽`127.0.0.1`的輕量FastAPI伺服器補
這個缺口，App用瀏覽器`fetch()`打`http://127.0.0.1:8794/...`。

**安全防護（比照ibkr_order_server.py四層，但Shioaji的paper驗證機制
本質不同，見下方「⚠ Shioaji沒有IBKR那種可查詢的模擬帳戶旗標」誠實揭露，
這是本檔案跟ibkr_order_server.py最大的架構差異）**：
1. 共享密鑰(token)驗證：跟ibkr_order_server.py同一套，`/submit_order`
   要帶正確的`X-Alpha-Local-Token`標頭，token獨立產生（不共用IBKR那支
   的token檔案），第一次啟動時印在終端機。
2. **`simulation=True`寫死在程式碼常數裡，不接受任何請求參數覆蓋**——
   `/submit_order`的請求body完全沒有「要不要模擬」這個欄位可以傳，這是
   刻意的設計，不是漏做。
3. **帳戶ID白名單交叉比對**（`EXPECTED_SIM_ACCOUNT_ID`）：每次下單前
   查`api.list_accounts()`，除了確認simulation模式登入成功，還要求
   回傳的`account_id`要等於這裡寫死的已知模擬帳戶ID（2026-09-01實測
   登入這個模擬環境拿到的帳戶是`0727956`）——不符合就直接中止不下單。
   **這是額外的防呆，不是唯一防線**：真正的安全邊界是simulation模式
   登入的伺服器端點本身就是跟正式環境完全分開的基礎設施，不是靠這串
   字串比對，字串比對只是「萬一哪天帳戶設定被改掉、多開了一個非預期的
   帳戶」這種情境下的第二層警報。
4. 只有`/submit_order`會真的下單，其他都是唯讀查詢；下單前後都寫log。

**⚠ Shioaji沒有IBKR那種可查詢的模擬帳戶旗標，誠實揭露這個架構差異**：
IBKR的paper帳戶ID有公開的"DU"字首慣例可以程式碼判斷；2026-09-01實際
用`api.login()`回傳的`Account`物件（`model_dump()`不存在，改用
`vars()`/`.__dict__`檢查過完整欄位：`account_type`/`person_id`/
`broker_id`/`account_id`/`signed`/`username`）**沒有任何一個欄位標示
「這是模擬環境」**，`sj.Shioaji`物件本身也沒有可查詢的`simulation`
屬性——**Shioaji區分模擬/正式環境的機制是連線時走完全不同的伺服器
基礎設施（`simulation=True`參數決定連去哪組伺服器），不是帳戶物件上的
一個可讀欄位**。這代表這裡的「安全鐵律」實際上是：(a)程式碼寫死
`simulation=True`且不開放request覆蓋、(b)額外的帳戶ID白名單比對當
第二層警報，**不是**像IBKR那樣有獨立於連線設定之外的帳戶屬性可以驗證。
如果之後查到Shioaji其實有更可靠的模擬環境驗證方式，要更新這裡的做法，
不是自滿於現狀。

**Log命名跟ibkr_order_server.py共用同一份`data/paper_order_log.json`**
（不是分開開`paper_order_log_tw.json`）——這份檔案的用途本來就是「所有
券商的下單意圖/結果統一日誌」，用`broker`欄位區分是哪一家（"ibkr"/
"shioaji"），比分成兩個檔案更適合以後做「今天總共下了幾張單」這種跨
券商彙總，不需要同時讀兩個檔案再合併。

**台股單位提醒（API欄位命名說明，避免使用者搞混）**：`quantity`欄位
單位是「張」（1張=1000股），不是像美股那樣以「股」為單位——這是台股
市場慣例，`Order`建構時的`quantity`參數本身就是以張為單位，不需要
額外換算，但呼叫端（之後的App UI）要清楚標示單位是「張」。

**訂單狀態判斷（沿用ibkr_order_server.py修好的教訓，但改用Shioaji
自己的狀態機制，不是照抄IBKR的字串比對）**：Shioaji的`OrderStatus`
列舉值是`PendingSubmit`/`PreSubmitted`/`Submitted`/`Filled`/
`PartFilled`/`Cancelled`/`Failed`/`Inactive`（跟IBKR的列舉值不同，
2026-09-01用`dir(sj.OrderStatus)`查證過）。**目前沒有實測證據顯示
Shioaji也有IBKR那種「非終止性Cancelled中途訊息」的問題**（今晚沒有
送過任何測試單，見上方警語），但保守起見沿用同一個等待邏輯：只有
`Filled`才提早結束等待迴圈，`Cancelled`/`Failed`/`Inactive`等看起來
像終止狀態的也一律等滿完整時間預算才下結論，不做「看到某個狀態字串
就假設已經結束」的提早判斷——等到真的送過測試單、觀察過Shioaji的真實
行為之後，才能確認這個保守假設是否也像IBKR一樣是必要的，或者其實
Shioaji的狀態機制真的乾淨、可以簡化。

**啟動方式**：`python research/shioaji_order_server.py`（前景執行，
使用者要用的時候自己啟動，用完關掉）。
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
PAPER_ORDER_LOG_PATH = REPO_ROOT / "data" / "paper_order_log.json"  # 跟ibkr_order_server.py共用，見模組docstring「Log命名」
TOKEN_PATH = Path(__file__).parent / ".shioaji_order_token"  # gitignored，見.gitignore
TW_TZ = timezone(timedelta(hours=8))

SIMULATION_MODE = True  # 寫死，不接受request覆蓋，見模組docstring安全防護第2點
EXPECTED_SIM_ACCOUNT_ID = "0727956"  # 2026-09-01實測登入模擬環境拿到的帳戶ID，見安全防護第3點
SERVER_PORT = 8794
ORDER_FILL_WAIT_SEC = 10


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


def _load_or_create_token() -> str:
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    return token


LOCAL_TOKEN = _load_or_create_token()

app = FastAPI(title="Alpha Shioaji Paper Order Server (本機限定)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jlove1314520.github.io", "http://localhost:8792", "http://127.0.0.1:8792"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _connect():
    """每個請求各自開一條新session，用完即登出——跟ibkr_order_server.py
    同一個理由：下單頻率低，這個開銷可以接受，避免長駐連線的狀態污染。"""
    import shioaji as sj

    env = _load_env(ENV_PATH)
    required = ["SINOPAC_API_KEY", "SINOPAC_SECRET_KEY"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise RuntimeError(f".env缺少必要欄位：{missing}")

    api = sj.Shioaji(simulation=SIMULATION_MODE)
    accounts = api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
    return api, accounts, env


def _verify_paper_account(accounts) -> str:
    """回傳帳戶ID字串；不符合白名單就丟例外。見模組docstring「安全防護」
    第3點——這是額外警報，不是唯一防線，真正的安全邊界是simulation=True
    連去的伺服器基礎設施本身就跟正式環境分開。"""
    if not accounts:
        raise RuntimeError("查不到任何帳戶，無法確認是否為模擬環境，安全起見拒絕")
    account_id = accounts[0].account_id
    if account_id != EXPECTED_SIM_ACCOUNT_ID:
        raise RuntimeError(
            f"帳戶ID（{account_id}）不符合已知的模擬環境帳戶白名單"
            f"（{EXPECTED_SIM_ACCOUNT_ID}），鐵律只能操作已驗證過的模擬帳戶，拒絕執行"
        )
    return account_id


def _check_token(x_alpha_local_token: str | None) -> None:
    if x_alpha_local_token != LOCAL_TOKEN:
        raise HTTPException(status_code=401, detail="token不正確或缺少X-Alpha-Local-Token標頭")


def _sanitize_nan(obj):
    """見ibkr_order_server.py同名函式——NaN不是合法JSON語法，寫檔前統一轉None。"""
    if isinstance(obj, float) and obj != obj:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(v) for v in obj]
    return obj


def _append_paper_trade(entry: dict) -> None:
    data = []
    if PAPER_ORDER_LOG_PATH.exists():
        try:
            data = json.loads(PAPER_ORDER_LOG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = []
    entry = {**entry, "broker": "shioaji"}
    data.append(_sanitize_nan(entry))
    PAPER_ORDER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_ORDER_LOG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class OrderRequest(BaseModel):
    symbol: str
    action: str  # "Buy" or "Sell"（Shioaji的Action enum用字，跟ibkr_order_server.py的"BUY"/"SELL"大小寫不同，刻意保留各自SDK原生用字，呼叫端要注意這個差異）
    quantity: int  # 單位：張（1張=1000股），見模組docstring「台股單位提醒」
    order_type: str = "MKT"  # "MKT" or "LMT"
    limit_price: float | None = None


@app.get("/health")
def health():
    try:
        api, accounts, _ = _connect()
        try:
            account_id = _verify_paper_account(accounts)
            return {"ok": True, "connected": True, "account_type": "simulation", "account_id": account_id}
        finally:
            api.logout()
    except Exception as e:
        return {"ok": False, "connected": False, "error": str(e)}


@app.post("/submit_order")
def submit_order(req: OrderRequest, x_alpha_local_token: str | None = Header(default=None)):
    _check_token(x_alpha_local_token)

    if req.action not in ("Buy", "Sell"):
        raise HTTPException(status_code=400, detail="action必須是Buy或Sell（注意大小寫，Shioaji原生用字）")
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity（張數）必須是正整數")
    if req.order_type == "LMT" and req.limit_price is None:
        raise HTTPException(status_code=400, detail="LMT單必須帶limit_price")

    attempt_id = secrets.token_hex(8)
    _append_paper_trade({
        "attempt_id": attempt_id,
        "phase": "intent",
        "at": datetime.now(TW_TZ).isoformat(),
        "symbol": req.symbol, "action": req.action, "quantity": req.quantity,
        "order_type": req.order_type, "limit_price": req.limit_price,
        "note": "模擬交易，非投資建議",
    })

    try:
        api, accounts, env = _connect()
    except Exception as e:
        _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                              "status": "CONNECT_FAILED", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"連線失敗：{e}")

    try:
        import shioaji as sj

        try:
            _verify_paper_account(accounts)
        except RuntimeError as e:
            _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                                  "status": "REJECTED_NOT_SIMULATION", "error": str(e)})
            raise HTTPException(status_code=403, detail=str(e))

        try:
            contract = api.Contracts.Stocks[req.symbol]
        except Exception:
            _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                                  "status": "CONTRACT_NOT_FOUND"})
            raise HTTPException(status_code=400, detail=f"合約無法解析：{req.symbol}")

        order = api.Order(
            price=req.limit_price if req.order_type == "LMT" else 0,
            quantity=req.quantity,
            action=req.action,
            price_type=sj.StockPriceType.LMT if req.order_type == "LMT" else sj.StockPriceType.MKT,
            order_type=sj.OrderType.ROD,
            account=accounts[0],
        )
        trade = api.place_order(contract, order)

        # 見模組docstring「訂單狀態判斷」：保守起見只有Filled才提早結束等待，
        # 沿用ibkr_order_server.py修好的教訓，即使目前沒有Shioaji本身的
        # 實測證據顯示有類似的非終止性中途狀態問題。
        for _ in range(ORDER_FILL_WAIT_SEC):
            api.update_status(accounts[0])
            if trade.status.status == sj.OrderStatus.Filled:
                break
            import time
            time.sleep(1)

        result = {
            "attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
            "status": str(trade.status.status),
            "order_id": trade.order.id,
            "seqno": getattr(trade.order, "seqno", None),
            "deals": [{"price": d.price, "quantity": d.quantity, "ts": str(d.ts)} for d in (trade.status.deals or [])],
        }
        _append_paper_trade(result)
        return result
    finally:
        try:
            api.logout()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    print(f"本機下單伺服器啟動於 http://127.0.0.1:{SERVER_PORT}（只監聽本機，其他裝置連不到）", flush=True)
    print(f"App設定頁要填的Token：{LOCAL_TOKEN}", flush=True)
    print("今晚只驗證到login，沒有實際送過測試單——真正下單測試留到台股開盤且使用者親自確認才做。", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)
