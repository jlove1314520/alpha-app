"""先.四十六：永豐 API 官方 Telegram 群組「只讀」擷取（Telethon／總司令個人帳號 MTProto）。

安全設計（總司令裁示，自測 scripts/selftest_telegram_reader.py 逐條證明）：
- 只讀一個群組：排程只認本機 .env 的 TELEGRAM_TARGET_CHAT_ID（數字 ID，設定工具解析後寫入）；其他目標一律拒絕。
- 先.四十六-補：設定模式（--login）可輸入「群組顯示名稱」，用 SetupClient.iter_dialogs 只比對標題找出同名群組
  （不讀任何訊息、不輸出其他聊天的標題，只印「找到 N 個同名群組」），iter_dialogs 只在設定模式開放。
- 程式層禁止寫入：ReadOnlyClient 只開放 get_entity／iter_messages（＋連線生命週期）；
  send／edit／delete／forward／join／leave／mark_read／下載媒體／原始 TL 請求（__call__）一律拋 PermissionError。
- 不下載任何媒體；只存文字、時間、訊息編號、回覆對象編號、發言者「官方／一般」標記，不存他人姓名、帳號、電話。
- 增量：記錄上次讀到的訊息編號，只抓新的；首次回補最近 90 天。
- 輸出、摘要、狀態都在 repo 外（C:\\alpha\\telegram_export\\sinopac_api\\）；登入檔在 C:\\alpha\\secrets\\。
- api_id／api_hash／登入檔不印出、不 commit。失敗只記警告與心跳，連續 3 次失敗才推播，不影響任何交易流程。

用法：
  python research/telegram_reader.py            排程用：增量抓取＋產生當日摘要
  python research/telegram_reader.py --login    一次性：由總司令本人在終端機輸入手機號碼／驗證碼／兩步驟密碼
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_PATH = REPO / ".env"
SECRETS_DIR = Path(r"C:\alpha\secrets")
SESSION_BASE = SECRETS_DIR / "telegram_reader"          # Telethon 會自動加 .session
EXPORT_DIR = Path(r"C:\alpha\telegram_export\sinopac_api")
STATE_NAME = "_state.json"
HB_NAME = "_heartbeat.jsonl"
TW = timezone(timedelta(hours=8))
BACKFILL_DAYS = 90
PUSH_AFTER_FAILURES = 3

DIGEST_CATEGORIES = [
    ("正式環境／權限", r"正式環境|正式權限|production|權限|簽署|開通|permission"),
    ("CA 憑證", r"\bCA\b|憑證|activate_ca|pfx|certificate"),
    ("零股", r"零股|odd ?lot|IntradayOdd|Odd"),
    ("上櫃", r"上櫃|櫃買|OTC|TPEx"),
    ("下單錯誤碼", r"錯誤碼|error ?code|errcode|op_code|op_msg|下單失敗|委託失敗|rejected?"),
    ("斷線重連", r"斷線|重連|reconnect|disconnect|session ?down|連線中斷|timeout|逾時"),
    ("流量限制", r"流量|限制|上限|limit|rate|頻率|停權|暫停服務"),
    ("維護公告", r"維護|停機|maintenance|公告|暫停"),
    ("版本更新", r"版本|更新|release|v\d+\.\d+|升級|upgrade"),
    ("breaking change", r"breaking|不相容|棄用|deprecat|移除|改名"),
]


class ReadOnlyViolation(PermissionError):
    pass


class ReadOnlyClient:
    """只讀包裝：底層 TelegramClient 只透過這裡用，且只開放 get_entity／iter_messages。
    目標以外的群組一律拒讀。其他任何屬性存取（含 send_message、__call__ 原始請求）都拋 ReadOnlyViolation。"""

    _LIFECYCLE = ("connect", "disconnect", "is_user_authorized")

    def __init__(self, client, target: str):
        object.__setattr__(self, "_c", client)
        object.__setattr__(self, "_target", str(target).strip())
        object.__setattr__(self, "_target_id", None)

    def __getattr__(self, name):
        if name in self._LIFECYCLE:
            return getattr(self._c, name)
        raise ReadOnlyViolation(f"只讀擷取不允許呼叫 {name}")

    def __setattr__(self, name, value):
        raise ReadOnlyViolation("只讀包裝不可修改")

    def __call__(self, *a, **k):
        raise ReadOnlyViolation("只讀擷取不允許送出原始 Telegram 請求")

    async def get_entity(self, target):
        if str(target).strip() != self._target:
            raise ReadOnlyViolation("只允許讀取 .env 指定的單一目標群組")
        ent = await self._c.get_entity(target)
        object.__setattr__(self, "_target_id", getattr(ent, "id", None))
        return ent

    def iter_messages(self, entity, **kw):
        if self._target_id is None or getattr(entity, "id", None) != self._target_id:
            raise ReadOnlyViolation("只允許讀取已核對過的目標群組")
        for bad in ("search", "from_user", "filter"):
            kw.pop(bad, None)
        return self._c.iter_messages(entity, **kw)


class SetupClient:
    """設定模式專用（--login）：多開放 iter_dialogs 讓顯示名稱解析成數字 ID；寫入類一律拒絕。
    排程模式絕不使用本類別（排程只用 ReadOnlyClient）。"""

    _ALLOWED = ("connect", "disconnect", "is_user_authorized", "start", "get_entity", "iter_dialogs")

    def __init__(self, client):
        object.__setattr__(self, "_c", client)

    def __getattr__(self, name):
        if name in self._ALLOWED:
            return getattr(self._c, name)
        raise ReadOnlyViolation(f"設定模式也不允許呼叫 {name}")

    def __setattr__(self, name, value):
        raise ReadOnlyViolation("只讀包裝不可修改")

    def __call__(self, *a, **k):
        raise ReadOnlyViolation("不允許送出原始 Telegram 請求")


def _peer_id(ent) -> int:
    from telethon import utils
    return int(utils.get_peer_id(ent))


async def resolve_target(sc, text: str, choose=input, out=print, peer_id=_peer_id) -> int:
    """把設定工具輸入的目標（顯示名稱／@帳號名稱／邀請連結）解析成數字 ID（Telethon marked id）。
    顯示名稱：iter_dialogs 只比對群組與頻道的標題（完全相同），不讀訊息、不輸出任何聊天標題。"""
    t = (text or "").strip()
    if not t:
        raise ValueError("沒有輸入目標群組")
    if t.startswith("@") or "t.me/" in t or t.startswith(("http://", "https://")):
        return peer_id(await sc.get_entity(t))
    hits = []
    async for d in sc.iter_dialogs():
        if (getattr(d, "is_group", False) or getattr(d, "is_channel", False)) and (getattr(d, "title", "") or "").strip() == t:
            hits.append(d)
    out(f"找到 {len(hits)} 個同名群組")
    if not hits:
        raise LookupError("你已加入的群組／頻道裡沒有標題完全相同的（請確認大小寫、空白，或改用邀請連結）")
    if len(hits) == 1:
        return peer_id(hits[0].entity)
    for i, d in enumerate(hits, 1):
        n = getattr(getattr(d, "entity", None), "participants_count", None)
        out(f"  序號 {i}：成員約 {n if n is not None else '（未知）'} 位")
    k = int(str(choose(f"請輸入序號（1～{len(hits)}）：")).strip())
    if not 1 <= k <= len(hits):
        raise ValueError("序號超出範圍")
    return peer_id(hits[k - 1].entity)


def write_env_key(key: str, value: str, path: Path = ENV_PATH) -> None:
    """取代或附加 .env 的單一鍵（保留其他行與換行格式）；不印出任何值。"""
    raw = path.read_bytes().decode("utf-8") if path.exists() else ""   # 不用 read_text：它會把 CRLF 轉成 LF
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = [l for l in raw.splitlines() if not re.match(rf"^\s*{re.escape(key)}\s*=", l)]
    lines.append(f"{key}={value}")
    path.write_text(eol.join(lines) + eol, encoding="utf-8", newline="")


def read_env(path: Path = ENV_PATH) -> dict:
    env = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def is_official(msg, chat_id) -> bool:
    """「官方」＝以群組本身名義發言（匿名管理員／頻道貼文）或帶管理員署名。
    已知限制：只開放 get_entity／iter_messages，讀不到管理員名單，管理員以個人身分發言時會標「一般」。"""
    if getattr(msg, "post", False) or getattr(msg, "post_author", None):
        return True
    fid = getattr(msg, "from_id", None)
    cid = getattr(fid, "channel_id", None) if fid is not None else None
    return cid is not None and chat_id is not None and int(cid) == int(chat_id)


def to_record(msg, chat_id) -> dict:
    """只取允許的欄位；絕不碰媒體內容、不取發言者身分資訊。"""
    d = getattr(msg, "date", None)
    rt = getattr(msg, "reply_to", None)
    return {
        "id": int(msg.id),
        "date": d.astimezone(TW).isoformat(timespec="seconds") if d else None,
        "reply_to": getattr(rt, "reply_to_msg_id", None) if rt is not None else None,
        "role": "官方" if is_official(msg, chat_id) else "一般",
        "text": getattr(msg, "message", None) or "",
        "has_media": bool(getattr(msg, "media", None)),
    }


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def write_records(records: list[dict], out_dir: Path) -> set[str]:
    """依訊息日期（台北）append 到 YYYY-MM-DD.jsonl，回傳寫到的日期集合。"""
    days = set()
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in sorted(records, key=lambda x: x["id"]):
        day = (r["date"] or "")[:10] or "unknown"
        with open(out_dir / f"{day}.jsonl", "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        days.add(day)
    return days


def build_digest(day: str, out_dir: Path) -> Path | None:
    src = out_dir / f"{day}.jsonl"
    if not src.exists():
        return None
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    lines = [f"# 永豐 API 群組每日摘要 {day}", "", f"訊息 {len(rows)} 則（只讀擷取；本檔只在本機，不進 repo）", ""]
    for name, pat in DIGEST_CATEGORIES:
        hit = [r for r in rows if re.search(pat, r.get("text") or "", re.I)]
        if not hit:
            continue
        lines.append(f"## {name}（{len(hit)}）")
        for r in hit:
            t = re.sub(r"\s+", " ", r.get("text") or "")[:160]
            lines.append(f"- #{r['id']} {str(r.get('date'))[11:16]} [{r.get('role')}] {t}")
        lines.append("")
    dst = out_dir / f"digest_{day}.md"
    dst.write_text("\n".join(lines), encoding="utf-8")
    return dst


async def fetch(ro: ReadOnlyClient, target: str, state: dict, now: datetime) -> list[dict]:
    ent = await ro.get_entity(target)
    chat_id = getattr(ent, "id", None)
    if state.get("chat_id") not in (None, chat_id):
        state["last_id"] = 0                 # 目標換了：重新回補，不混用舊編號
    state["chat_id"] = chat_id
    last_id = int(state.get("last_id") or 0)
    recs = []
    if last_id:
        it = ro.iter_messages(ent, min_id=last_id, reverse=True)
    else:
        it = ro.iter_messages(ent, offset_date=now - timedelta(days=BACKFILL_DAYS), reverse=True)
    async for m in it:
        if int(m.id) <= last_id:
            continue
        recs.append(to_record(m, chat_id))
    if recs:
        state["last_id"] = max(r["id"] for r in recs)
    return recs


def _heartbeat(out_dir: Path, code: str, n: int = 0) -> None:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / HB_NAME, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": datetime.now(TW).isoformat(timespec="seconds"), "code": code, "new": n}) + "\n")
    except Exception as e:
        print(f"[warn] 心跳寫入失敗：{type(e).__name__}", flush=True)


def _push_failure(n: int) -> None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import web_push
        web_push.send("Telegram 擷取連續失敗", f"永豐 API 群組只讀擷取已連續失敗 {n} 次（不影響交易流程）。", kind="error")
    except Exception as e:
        print(f"[warn] 推播失敗：{type(e).__name__}（只記警告）", flush=True)


def make_client(env: dict):
    from telethon import TelegramClient
    return TelegramClient(str(SESSION_BASE), int(env["TELEGRAM_API_ID"]), env["TELEGRAM_API_HASH"])


async def run_once(env: dict, out_dir: Path = EXPORT_DIR, client=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(TW)
    state_p = out_dir / STATE_NAME
    state = _load_json(state_p, {})
    target_s = env.get("TELEGRAM_TARGET_CHAT_ID", "").strip()   # 先.四十六-補：排程只認數字 ID
    target = int(target_s) if re.fullmatch(r"-?\d+", target_s) else None
    if not (env.get("TELEGRAM_API_ID") and env.get("TELEGRAM_API_HASH") and target is not None):
        _heartbeat(out_dir, "NOT_CONFIGURED")
        return {"state": "NOT_CONFIGURED"}
    try:
        c = client or make_client(env)
        ro = ReadOnlyClient(c, target)
        await ro.connect()
        try:
            if not await ro.is_user_authorized():
                raise RuntimeError("尚未登入（請執行設定工具完成首次登入）")
            recs = await fetch(ro, target, state, now)
        finally:
            try:
                await ro.disconnect()
            except Exception:
                pass
        days = write_records(recs, out_dir)
        for d in sorted(days | {now.astimezone(TW).date().isoformat()}):
            build_digest(d, out_dir)
        state.update(consecutive_failures=0, last_ok=now.isoformat(timespec="seconds"), last_error=None)
        _write_json(state_p, state)
        _heartbeat(out_dir, "OK", len(recs))
        return {"state": "OK", "new": len(recs)}
    except Exception as e:
        n = int(state.get("consecutive_failures") or 0) + 1
        state.update(consecutive_failures=n, last_error=f"{type(e).__name__}")
        _write_json(state_p, state)
        _heartbeat(out_dir, "ERROR")
        print(f"[warn] Telegram 擷取失敗（第 {n} 次連續）：{type(e).__name__}", flush=True)
        if n == PUSH_AFTER_FAILURES:
            _push_failure(n)
        return {"state": "ERROR", "consecutive_failures": n}


async def login(env: dict) -> int:
    """一次性登入：手機號碼／驗證碼／兩步驟密碼由 Telethon 在終端機向總司令本人詢問，本程式不記錄、不印出。"""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    c = make_client(env)
    sc = SetupClient(c)
    await sc.start()          # 已登入就不會再問手機／驗證碼
    try:
        try:
            tid = await resolve_target(sc, env.get("TELEGRAM_TARGET_CHAT", ""))
        except Exception as e:
            print(f"找不到目標群組（{type(e).__name__}）：{e}", flush=True)
            return 1
        write_env_key("TELEGRAM_TARGET_CHAT_ID", str(tid))
        ro = ReadOnlyClient(c, tid)
        ent = await ro.get_entity(tid)
        print(f"登入成功，目標群組可讀取：{getattr(ent, 'title', '（無標題）')}（ID 已寫入 .env）", flush=True)
        return 0
    except Exception as e:
        print(f"目標群組無法讀取（{type(e).__name__}）：請確認你的帳號已在群組內", flush=True)
        return 1
    finally:
        await c.disconnect()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--jitter-max-sec", type=int, default=0, help="排程用：開始前隨機延遲 0～N 秒")
    a = ap.parse_args()
    env = read_env()
    if a.login:
        return asyncio.run(login(env))
    if a.jitter_max_sec > 0:
        import time
        time.sleep(random.uniform(0, a.jitter_max_sec))
    out = asyncio.run(run_once(env))
    print(json.dumps(out, ensure_ascii=False))
    return 0                                   # 失敗也 exit 0：只記警告，不影響任何其他排程


if __name__ == "__main__":
    sys.exit(main())
