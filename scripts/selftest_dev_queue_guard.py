# -*- coding: utf-8 -*-
"""先.六十二 自測：DevQueue 守門員（scripts/dev_queue_runner.py 的 NEEDS_USER／IRREVERSIBLE 判斷）。

不改任何真實檔案（守門員預檢用暫存佇列檔），不呼叫 claude、不 commit。檢查：
①總司令指定三句不得觸發：「不接付費模型」「刪除舊清單的本機 localStorage 鍵」「Gateway 需登入時只顯示 CTA」
②總司令指定兩句仍須觸發：「請總司令登入」「採購資料」
③〔來源：…〕〔現況：…〕描述性分句不看；做法句照看
④真正的不可逆（刪除資料庫、解鎖 holdout）仍會被擋
⑤守門員自身出錯 → 降級回整句比對（寧可多擋），不拋例外
⑥guard_precheck 只印清單、不改佇列檔任何一個字
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dev_queue_runner as D  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def blocked(text):
    h = D.guard_hits(text)
    return bool(h["needs_user"] or h["irreversible"])


# ① 不得觸發（放在標題與做法句兩種位置都測）
for s in ("不接付費模型", "刪除舊清單的本機 localStorage 鍵", "Gateway 需登入時只顯示 CTA"):
    check(f"標題「{s}」不觸發", not blocked(f"**常備.開發-X {s}**"))
    check(f"做法句「{s}」不觸發", not blocked(f"**常備.開發-X 某功能**〔做法：{s}；心跳：本行〕"))
# ② 仍須觸發
for s, kind in (("請總司令登入", "needs_user"), ("採購資料", "needs_user")):
    check(f"「{s}」仍觸發（{kind}）", D.guard_hits(f"**某項 {s}**")[kind])
    check(f"做法句「{s}」仍觸發", blocked(f"**某項**〔做法：{s}〕"))
# ③ 描述性分句不看、做法句照看
check("〔來源：付費資料商〕不觸發", not blocked("**某項 整理資料**〔來源：付費資料商的公開報告〕"))
check("〔現況：需登入 IBKR〕不觸發", not blocked("**某項 報價排程**〔現況：每週需人工登入一次〕"))
check("同一括號內的做法句仍會觸發", blocked("**某項**〔現況：無；做法：請總司令核准預算〕"))
check("否定詞超過 8 字之後的命中仍觸發", blocked("**某項 不做這件事，但之後要再請總司令登入**"))
# ④ 真正的不可逆
check("刪除資料庫仍擋", D.guard_hits("**某項 刪除 alpha.db 的舊資料表**")["irreversible"])
check("解鎖 holdout 仍擋", D.guard_hits("**某項 解鎖 holdout 再測一次**")["irreversible"])
# ⑤ 守門員自身出錯 → 降級回整句比對
orig = D.guard_scope
D.guard_scope = lambda _c: (_ for _ in ()).throw(RuntimeError("故意弄壞"))
try:
    h = D.guard_hits("**某項（不接付費模型）**")
    check("guard_scope 崩潰 → 不拋例外、退回整句比對（多擋）", h["needs_user"] == ["付費"])
finally:
    D.guard_scope = orig
# ⑥ guard_precheck 不改檔
with tempfile.TemporaryDirectory() as td:
    q = Path(td) / "PENDING_QUEUE.md"
    body = "# 測試\n- [ ] **A 請總司令登入**\n- [ ] **B 不接付費模型**\n- [x] **C 採購資料**\n"
    q.write_text(body, encoding="utf-8")
    orig_q = D.QUEUE
    D.QUEUE = q
    try:
        found = D.guard_precheck()
    finally:
        D.QUEUE = orig_q
    check("guard_precheck 只列出 A（B 被否定詞排除、C 已完成不看）", [f[0][:3] for f in found] == ["**A"])
    check("guard_precheck 不改佇列檔", q.read_text(encoding="utf-8") == body)
# 實際佇列：常備.開發-2／-8／-9 不會被擋
real = [ln for ln in (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8").splitlines() if "常備.開發-" in ln and ln.startswith("- [")]
for n in ("2", "8", "9"):
    ln = next((x for x in real if f"常備.開發-{n} " in x), "")
    check(f"實際佇列 常備.開發-{n} 不會被守門員擋", ln and not blocked(ln[6:]))

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
