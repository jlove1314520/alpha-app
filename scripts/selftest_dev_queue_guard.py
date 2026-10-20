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
# ⑦ 先.六十七-5 approval_precheck：已裁示解凍／核准卻仍 [!] → 警告；解除條件寫法、引文、[ ] 都不算；不改檔
with tempfile.TemporaryDirectory() as td:
    q = Path(td) / "PENDING_QUEUE.md"
    body = ("# 測試\n- [!] **A 兩榜回測**〔先.六十五 總司令裁示解凍：登記為重新驗證〕\n"
            "- [!] **B 建排程**〔先寫提案，總司令核准後再建〕\n- [!] **C 待總司令核准預算**\n"
            "- [ ] **D 已解**〔總司令已核准〕\n```\n- [!] **E 引文** 總司令已核准\n```\n"
            "- [!] **F 某項**〔2026-10-11 總司令已同意改採丙案〕\n")
    q.write_text(body, encoding="utf-8")
    orig_q = D.QUEUE
    D.QUEUE = q
    try:
        found = D.approval_precheck()
    finally:
        D.QUEUE = orig_q
    check(f"approval_precheck 只列出 A、F（{[f[0][:3] for f in found]}）", [f[0][:3] for f in found] == ["A 兩", "F 某"])
    check("approval_precheck 不改佇列檔", q.read_text(encoding="utf-8") == body)
D.QUEUE, _oq = Path("不存在的佇列.md"), D.QUEUE
try:
    check("approval_precheck 讀不到佇列 → 不拋例外、回空", D.approval_precheck() == [])
finally:
    D.QUEUE = _oq
# 實際佇列：常備.開發-2／-8／-9 不會被擋
real = [ln for ln in (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8").splitlines() if "常備.開發-" in ln and ln.startswith("- [")]
for n in ("2", "8", "9"):
    ln = next((x for x in real if f"常備.開發-{n} " in x), "")
    check(f"實際佇列 常備.開發-{n} 不會被守門員擋", ln and not blocked(ln[6:]))

# 先.一二二-13：碰撞偵測對 PENDING_QUEUE.md 純檔尾新增不讓路、改寫既有行仍讓路（用暫存 git repo 產生真的 diff）
import subprocess  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    def _git(*a):
        return subprocess.run(["git", "-C", td, *a], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    _git("init", "-q")
    _git("config", "user.email", "selftest@example.invalid")
    _git("config", "user.name", "selftest")
    qf = tdp / "PENDING_QUEUE.md"
    qf.write_text("- [ ] A\n- [ ] B\n- [ ] C\n", encoding="utf-8")
    _git("add", "PENDING_QUEUE.md")
    _git("commit", "-q", "-m", "init")
    _oroot = D.ROOT
    D.ROOT = tdp
    try:
        qf.write_text("- [ ] A\n- [ ] B\n- [ ] C\n\n- [ ] D 新增條目\n", encoding="utf-8")
        check("PENDING_QUEUE.md 只在檔尾新增條目 → 視為純新增（不讓路）", D._append_only_change("PENDING_QUEUE.md") is True)
        qf.write_text("- [x] A 已完成\n- [ ] B\n- [ ] C\n- [ ] D\n", encoding="utf-8")
        check("PENDING_QUEUE.md 改寫既有行＋檔尾新增 → 不算純新增（照舊讓路）", D._append_only_change("PENDING_QUEUE.md") is False)
        qf.write_text("- [ ] A\n- [ ] 插在中間\n- [ ] B\n- [ ] C\n", encoding="utf-8")
        check("PENDING_QUEUE.md 在中間插入 → 不算純新增（照舊讓路）", D._append_only_change("PENDING_QUEUE.md") is False)
        check("判斷不存在的檔案 → 不拋例外、回 False", D._append_only_change("不存在.md") is False)
    finally:
        D.ROOT = _oroot

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
