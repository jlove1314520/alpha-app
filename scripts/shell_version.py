"""先.六十九-2（2026-10-11）：App 外殼版本號與發布節奏。由 .git/hooks/pre-commit 呼叫 `hook`，趕工迴圈呼叫 `release`。

外殼檔＝index.html、sw.js、app.js、app-*.js、app.css。版本戳＝app.js 的 APP_VERSION、index.html 的 app.css?v=／app.js?v=、
sw.js 的 CACHE。sw.js 一變，手機背景就會裝新版（先.六十九-1 快取優先＋點提示條才換版），所以「版本號什麼時候動」
＝「手機什麼時候換版」。

規則：
1. 只有外殼「真的」變動才更新版本號：暫存區 diff 扣掉版本戳字樣後還有增刪行才算（只改了版本戳＝不算）。
2. 趕工模式（PENDING_QUEUE 常備.開發 還有 - [ ]）下，DevQueue 的 commit（環境變數 ALPHA_CYCLE_ID 有值）距上次發布
   不滿 60 分鐘 → 這次不動版本號，只記「待發布」；commit 與 push 照常（資料檔完全不受影響）。已安裝的手機繼續用上一版
   完整外殼（快取優先），不會一小時內反覆跳「有新版」。互動視窗（總司令即時對話）的 commit 不延後。
3. `release`：有待發布且（距上次發布 ≥60 分鐘，或已不在趕工）→ 只對暫存區蓋版本戳、單獨 commit（不推送；由下一次既有
   push 帶上去）。暫存區有別人的東西時延後，不混進別人的 commit。
4. 蓋版本戳只改「暫存區」那一份（git show :path → 改字 → hash-object → update-index），工作目錄同步改字但不 git add，
   所以工作目錄裡別人尚未 commit 的修改不會被掃進這次 commit（舊 hook 用 git add app.js／app-*.js 會掃進去）。

狀態檔 research/.shell_release.json（本機、不進版控）：{last_release, pending, pending_since, pending_commits}。
任何失敗只印警告；hook 模式失敗時 exit 2，pre-commit 會退回舊的直接蓋戳行為（十二節：守門員失敗只降級）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ALPHA_SHELL_ROOT") or Path(__file__).resolve().parent.parent)
STATE = ROOT / "research" / ".shell_release.json"
TZ = timezone(timedelta(hours=8))
SHELL_RE = re.compile(r"^(index\.html|sw\.js|app(-[a-z]+)?\.js|app\.css)$")
STAMP_FILES = ("index.html", "app.js", "sw.js")
STAMP_PATTERNS = [
    (re.compile(r"const APP_VERSION='[^']*'"), lambda v: f"const APP_VERSION='{v}'"),
    (re.compile(r"(app\.(?:css|js)\?v=)[0-9.-]+"), lambda v: rf"\g<1>{v}"),
    (re.compile(r"const CACHE = 'alpha-v[^']*'"), lambda v: f"const CACHE = 'alpha-v{v}'"),
]
RELEASE_GAP_SEC = 60 * 60
CRUNCH_LINE = re.compile(r"^- \[ \] \*\*常備\.開發-")


def _git(*args, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], input=input_bytes, capture_output=True, check=True).stdout


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def crunch_active() -> bool:
    if os.environ.get("ALPHA_SHELL_CRUNCH") in ("0", "1"):  # 測試用覆寫
        return os.environ["ALPHA_SHELL_CRUNCH"] == "1"
    try:
        lines = (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    fenced, inside = set(), False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            inside = not inside
            fenced.add(i)
        elif inside:
            fenced.add(i)
    return any(CRUNCH_LINE.match(ln) for i, ln in enumerate(lines) if i not in fenced)


def _unstamp(text: str) -> str:
    for pat, _ in STAMP_PATTERNS:
        text = pat.sub("<STAMP>", text)
    return text


def staged_shell_files() -> list[str]:
    names = _git("diff", "--cached", "--name-only").decode("utf-8", "replace").split()
    return [n for n in names if SHELL_RE.match(n)]


def real_shell_change(files: list[str]) -> bool:
    """扣掉版本戳後，暫存區與 HEAD 的外殼檔內容是否仍不同（新增檔、刪除檔都算真變動）。"""
    for f in files:
        try:
            head = _git("show", f"HEAD:{f}").decode("utf-8", "replace")
        except subprocess.CalledProcessError:
            return True
        try:
            idx = _git("show", f":{f}").decode("utf-8", "replace")
        except subprocess.CalledProcessError:
            return True
        if _unstamp(head.replace("\r\n", "\n")) != _unstamp(idx.replace("\r\n", "\n")):
            return True
    return False


def _stamp_text(text: str, v: str) -> str:
    for pat, rep in STAMP_PATTERNS:
        text = pat.sub(rep(v), text)
    return text


def stamp(v: str) -> list[str]:
    """只改暫存區與工作目錄的版本戳字樣；不 git add 整個檔案。回傳改了暫存區的檔名。"""
    changed = []
    for f in STAMP_FILES:
        try:
            idx = _git("show", f":{f}")
        except subprocess.CalledProcessError:
            continue
        new = _stamp_text(idx.decode("utf-8"), v).encode("utf-8")
        if new != idx:
            sha = _git("hash-object", "-w", "--stdin", input_bytes=new).decode().strip()
            mode = _git("ls-files", "-s", "--", f).decode().split()[0]
            _git("update-index", "--cacheinfo", f"{mode},{sha},{f}")
            changed.append(f)
        wp = ROOT / f
        if wp.exists():
            raw = wp.read_bytes().decode("utf-8")
            w = _stamp_text(raw, v)
            if w != raw:
                wp.write_bytes(w.encode("utf-8"))
    return changed


def _current_version() -> str:
    try:
        m = re.search(r"const CACHE = 'alpha-v([^']*)'", _git("show", ":sw.js").decode("utf-8"))
        return m.group(1) if m else ""
    except subprocess.CalledProcessError:
        return ""


def _now_stamp() -> str:
    """分鐘級時間戳；同一分鐘內已用過（版本號不會變＝手機收不到新版）時加上秒數，字串比較仍比舊版大。"""
    now = datetime.now(TZ)
    v = now.strftime("%Y-%m-%d.%H%M")
    return v if v > _current_version() else now.strftime("%Y-%m-%d.%H%M%S")


def hook() -> int:
    files = staged_shell_files()
    if not files:
        return 0
    if os.environ.get("ALPHA_SHELL_RELEASING") == "1":
        return 0
    if not real_shell_change(files):
        print("[pre-commit] 外殼只有版本戳字樣變動，版本號不更新（先.六十九-2）")
        return 0
    st = _load_state()
    now = time.time()
    if os.environ.get("ALPHA_CYCLE_ID") and crunch_active() and now - float(st.get("last_release") or 0) < RELEASE_GAP_SEC:
        st.update(pending=True, pending_since=st.get("pending_since") or now, pending_commits=int(st.get("pending_commits") or 0) + 1)
        _save_state(st)
        left = int((RELEASE_GAP_SEC - (now - float(st.get("last_release") or 0))) / 60)
        print(f"[pre-commit] 趕工模式：外殼版本號延後發布（距上次發布不滿 60 分鐘，約 {left} 分後由趕工迴圈發布；"
              f"累積 {st['pending_commits']} 個外殼 commit）")
        return 0
    v = _now_stamp()
    stamp(v)
    st.update(last_release=now, last_version=v, pending=False, pending_since=None, pending_commits=0)
    _save_state(st)
    print(f"[pre-commit] App 外殼版本號已自動更新為 {v}")
    return 0


def release(push: bool = False) -> int:
    st = _load_state()
    if not st.get("pending"):
        print("shell_release：沒有待發布的外殼變動")
        return 0
    now = time.time()
    if crunch_active() and now - float(st.get("last_release") or 0) < RELEASE_GAP_SEC:
        print("shell_release：距上次發布不滿 60 分鐘，稍後再發布")
        return 0
    if _git("diff", "--cached", "--name-only").strip():
        print("shell_release：暫存區有其他人的變動，這次不發布（不混進別人的 commit）")
        return 0
    v = _now_stamp()
    changed = stamp(v)
    if not changed:
        st.update(pending=False, pending_commits=0, pending_since=None)
        _save_state(st)
        print("shell_release：版本戳已是最新，清除待發布")
        return 0
    n = int(st.get("pending_commits") or 0)
    env = dict(os.environ, ALPHA_SHELL_RELEASING="1")
    subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m",
                    f"App 外殼發布 {v}（先.六十九-2：趕工期間累積 {n} 個外殼 commit，每小時最多發布一次）"],
                   check=True, env=env)
    st.update(last_release=now, last_version=v, pending=False, pending_since=None, pending_commits=0)
    _save_state(st)
    print(f"shell_release：已發布外殼版本 {v}（累積 {n} 個外殼 commit）")
    if push:
        r = subprocess.run(["git", "-C", str(ROOT), "push", "-q"], capture_output=True, text=True)
        print("shell_release：push " + ("成功" if r.returncode == 0 else "失敗，留給下一次既有 push 帶上去"))
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "hook":
            return hook()
        if cmd == "release":
            return release(push="--push" in sys.argv)
        if cmd == "status":
            print(json.dumps({"state": _load_state(), "crunch_active": crunch_active()}, ensure_ascii=False))
            return 0
    except Exception as e:  # noqa: BLE001 -- 十二節：自身失敗只降級
        print(f"shell_version {cmd} 失敗（{type(e).__name__}: {e}）")
        return 2 if cmd == "hook" else 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
