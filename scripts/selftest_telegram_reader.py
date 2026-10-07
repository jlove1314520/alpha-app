"""先.四十六：Telegram 只讀擷取自測（假用戶端，不連網、不需要 api_id）。"""
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import telegram_reader as T  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


TW = timezone(timedelta(hours=8))
NOW = datetime(2026, 10, 8, 8, 15, tzinfo=TW)
TARGET = "永豐測試群組"


class FakeClient:
    """模擬 TelegramClient：記錄每一次被呼叫的方法；寫入類方法若真的被呼叫到就是失敗。"""

    def __init__(self, msgs, chat_id=777):
        self.msgs = msgs; self.chat_id = chat_id; self.calls = []; self.downloads = 0

    async def connect(self): self.calls.append("connect")
    async def disconnect(self): self.calls.append("disconnect")
    async def is_user_authorized(self): return True

    async def get_entity(self, t):
        self.calls.append(("get_entity", t))
        return NS(id=self.chat_id, title="X")

    def iter_messages(self, ent, min_id=0, offset_date=None, reverse=False, **kw):
        self.calls.append(("iter_messages", min_id, offset_date))
        sel = [m for m in self.msgs if m.id > (min_id or 0) and (offset_date is None or m.date >= offset_date)]

        async def gen():
            for m in sorted(sel, key=lambda x: x.id):
                yield m
        return gen()

    async def download_media(self, *a, **k):
        self.downloads += 1

    def __getattr__(self, name):
        async def _w(*a, **k):
            self.calls.append(("WRITE", name))
        return _w


def msg(i, days_ago, text="", media=None, post=False, from_channel=None, reply=None, sender_name="王小明"):
    return NS(id=i, date=NOW - timedelta(days=days_ago), message=text, media=media, post=post, post_author=None,
              from_id=NS(channel_id=from_channel) if from_channel else NS(user_id=123),
              reply_to=NS(reply_to_msg_id=reply) if reply else None, sender=NS(first_name=sender_name, phone="0912345678"))


# 1 寫入類方法全被擋
ro = T.ReadOnlyClient(FakeClient([]), TARGET)
blocked = []
for name in ("send_message", "send_file", "edit_message", "delete_messages", "forward_messages", "send_read_acknowledge",
             "delete_dialog", "download_media", "download_file", "iter_participants", "get_messages", "kick_participant"):
    try:
        getattr(ro, name); blocked.append(False)
    except T.ReadOnlyViolation:
        blocked.append(True)
try:
    ro(object()); raw_blocked = False
except T.ReadOnlyViolation:
    raw_blocked = True
try:
    ro.x = 1; set_blocked = False
except T.ReadOnlyViolation:
    set_blocked = True
check("寫入類方法（send／edit／delete／forward／mark_read／leave／下載等 12 項）全部被擋", all(blocked))
check("原始 TL 請求（__call__，可用來 join／leave）被擋、包裝不可被改", raw_blocked and set_blocked)

# 2 目標以外群組拒讀
fc = FakeClient([])
ro = T.ReadOnlyClient(fc, TARGET)
try:
    asyncio.run(ro.get_entity("別的群組")); other_ok = False
except T.ReadOnlyViolation:
    other_ok = True
check("目標以外群組：get_entity 拒絕且未呼叫底層", other_ok and not any(isinstance(c, tuple) and c[0] == "get_entity" for c in fc.calls))
try:
    ro.iter_messages(NS(id=999)); it_ok = False
except T.ReadOnlyViolation:
    it_ok = True
check("目標以外群組：iter_messages 拒絕（未核對目標前也拒）", it_ok)

# 3 媒體不下載、只存允許欄位、發言者只存官方／一般
out = Path(tempfile.mkdtemp())
msgs = [msg(1, 100, "太舊不回補"), msg(2, 30, "正式環境權限開通了嗎", reply=None),
        msg(3, 10, "附圖", media=NS(photo=True)), msg(4, 1, "CA 憑證 activate_ca 失敗", post=True),
        msg(5, 0.5, "零股下單錯誤碼 88", from_channel=777, reply=4)]
fc = FakeClient(msgs)
env = {"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "h", "TELEGRAM_TARGET_CHAT": TARGET}
r = asyncio.run(T.run_once(env, out_dir=out, client=fc, now=NOW))
rows = [json.loads(l) for f in sorted(out.glob("20*.jsonl")) for l in f.read_text(encoding="utf-8").splitlines()]
check("首次回補 90 天：抓到 4 則、排除 100 天前那則", r["state"] == "OK" and sorted(x["id"] for x in rows) == [2, 3, 4, 5])
check("媒體不下載（download 次數 0、只記 has_media）", fc.downloads == 0 and any(x["has_media"] for x in rows))
check("只存允許欄位（不含姓名／帳號／電話）", all(set(x) == {"id", "date", "reply_to", "role", "text", "has_media"} for x in rows)
      and "王小明" not in json.dumps(rows, ensure_ascii=False) and "0912345678" not in json.dumps(rows))
check("發言者只標官方／一般（群組名義與頻道貼文標官方）", {x["id"]: x["role"] for x in rows} == {2: "一般", 3: "一般", 4: "官方", 5: "官方"})
check("回覆對象編號有存", [x for x in rows if x["id"] == 5][0]["reply_to"] == 4)
check("全程沒有呼叫任何寫入方法", not any(isinstance(c, tuple) and c[0] == "WRITE" for c in fc.calls))

# 4 增量不重抓
fc2 = FakeClient(msgs + [msg(6, 0.1, "斷線重連問題")])
r2 = asyncio.run(T.run_once(env, out_dir=out, client=fc2, now=NOW + timedelta(hours=12)))
rows2 = [json.loads(l) for f in sorted(out.glob("20*.jsonl")) for l in f.read_text(encoding="utf-8").splitlines()]
check("增量：第二次只抓新的 1 則、總數不重複", r2.get("new") == 1 and sorted(x["id"] for x in rows2) == [2, 3, 4, 5, 6])
check("增量：第二次以 min_id=上次最後編號查詢", any(isinstance(c, tuple) and c[0] == "iter_messages" and c[1] == 5 for c in fc2.calls))

# 5 摘要、未設定、連續失敗才推播
dg = list(out.glob("digest_*.md"))
txt = "\n".join(p.read_text(encoding="utf-8") for p in dg)
check("每日摘要依關鍵字分類並附訊息編號", "## CA 憑證" in txt and "#4" in txt and "## 零股" in txt and "#5" in txt)
r3 = asyncio.run(T.run_once({}, out_dir=Path(tempfile.mkdtemp()), client=FakeClient([]), now=NOW))
check("未設定 api_id／群組：NOT_CONFIGURED、不算失敗", r3["state"] == "NOT_CONFIGURED")
pushed = []
T._push_failure = lambda n: pushed.append(n)


class Boom(FakeClient):
    async def connect(self): raise ConnectionError("x")


o2 = Path(tempfile.mkdtemp())
res = [asyncio.run(T.run_once(env, out_dir=o2, client=Boom([]), now=NOW))["state"] for _ in range(4)]
check("失敗只記警告：連續第 3 次才推播一次（第 1、2、4 次不推）", res == ["ERROR"] * 4 and pushed == [3])

# 6 登入檔與輸出路徑都在 repo 外
check("登入檔路徑不在 repo 內", ROOT.resolve() not in Path(str(T.SESSION_BASE) + ".session").resolve().parents)
check("擷取輸出與摘要路徑不在 repo 內", ROOT.resolve() not in T.EXPORT_DIR.resolve().parents)
gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
check(".gitignore 含 *.session", "*.session" in gi.splitlines())

print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
