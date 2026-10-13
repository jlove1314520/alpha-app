# -*- coding: utf-8 -*-
"""融資維持率（CM 估）每日自動與籌碼K 校準（2026-10-13 總司令【先.八十二】11）。不爬籌碼K。

每天一次（本機排程 AlphaMarginCkCheck，平日 19:30，雲端 17:13／18:41 兩班之後）：
  ① 讀總司令每週貼的籌碼K讀數（research/data/margin_reconcile/external_cm.json，本機、不進 repo；用 scripts/ck_reading.py 登錄）
  ② 取最新一筆「日期 ≥ METHOD_SINCE、且雲端 data/margin_maintenance.json 同日有完整紀錄」的讀數，
     把本站同日原值套目前校準（data/margin_ratio_calibration.json，build_margin_calibration.ck_value）＝App 顯示的數字，與籌碼K比。
     METHOD_SINCE＝2026-10-07：那天起雲端每日紀錄改成分子分母同一天（先.四十三-三），更早的每日紀錄方法不同，
     那些日子的差距由 research/reconcile_cm_external.py 用同日重建處理，不在這裡比。
  ③ 誤差 >2pp（同一筆讀數只處理一次）→ 推播，並自動重估係數：跑 reconcile_cm_external.py（TWSE MI_MARGN，間隔 ≥4 秒、有快取）
     → build_margin_calibration.py，只提交 data/margin_ratio_calibration.json（取鎖帶 token、衝突作廢本機）。
  ④ 最新讀數超過 8 天 → 每 7 天最多推播一次「請貼本週籌碼K讀數」。
狀態與逐日紀錄寫 research/data/margin_reconcile/ck_check_state.json／ck_check_log.jsonl（.gitignore，外部數值不進 repo）。
自身失敗只記 log（十二節）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ck_reading  # noqa: E402

TW = timezone(timedelta(hours=8))
LOCAL = ROOT / "research" / "data" / "margin_reconcile"
STATE = LOCAL / "ck_check_state.json"
LOG = LOCAL / "ck_check_log.jsonl"
CAL = ROOT / "data" / "margin_ratio_calibration.json"
METHOD_SINCE = "2026-10-07"
THRESH_PP = 2.0
STALE_DAYS = 8
REMIND_EVERY_DAYS = 7


def _log(row: dict) -> None:
    row = {"ts": datetime.now(TW).isoformat(timespec="seconds"), **row}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    try:
        LOCAL.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def cloud_margin() -> list:
    """雲端最新版（origin/main）；拿不到就用本機工作區那份。"""
    try:
        import local_git_commit as G
        G._g("fetch", "-q", "origin", "main", timeout=120)
        r = G._g("show", "origin/main:data/margin_maintenance.json", timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 讀雲端維持率失敗，改用本機檔：{type(e).__name__}")
    return _read(ROOT / "data" / "margin_maintenance.json", []) or []


def default_push(title: str, body: str) -> dict:
    import web_push
    return web_push.send(title, body, kind="margin_ck")


def default_reestimate() -> str:
    env = dict(__import__("os").environ, PYTHONIOENCODING="utf-8")
    for args in (["research/reconcile_cm_external.py"], ["research/build_margin_calibration.py"]):
        r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=3600)
        if r.returncode != 0:
            return f"{args[0]} 失敗 exit={r.returncode}"
    import local_git_commit as G
    return G.commit_paths(["data/margin_ratio_calibration.json"], "融資維持率：籌碼K 誤差超過 2pp，自動重估校準係數（先.八十二-11）",
                          drop_on_conflict=True)


def main(today: date | None = None, push=None, reestimate=None, margin=None) -> dict:
    today = today or datetime.now(TW).date()
    push, reestimate = push or default_push, reestimate or default_reestimate
    import build_margin_calibration as M
    state = _read(STATE, {}) or {}
    pts = ck_reading.load().get("points") or []
    res: dict = {"n_readings": len(pts)}
    latest = pts[-1][0] if pts else None
    if latest is None or (today - date.fromisoformat(latest)).days > STALE_DAYS:
        last_rm = state.get("last_reminder")
        if not last_rm or (today - date.fromisoformat(last_rm)).days >= REMIND_EVERY_DAYS:
            r = push("請貼本週籌碼K讀數", f"融資維持率校準：最新讀數 {latest or '沒有'}，已超過 {STALE_DAYS} 天。"
                                      "請把籌碼K顯示的「融資餘額（億）」與「維持率」貼給 CC 存檔。")
            if r.get("ok"):
                state["last_reminder"] = today.isoformat()
            res["reminder"] = r.get("ok", 0)
    mm = margin if margin is not None else cloud_margin()
    by = {r.get("date"): r for r in mm if isinstance(r, dict)}
    cal = _read(CAL, {}) or {}
    cand = [p for p in pts if p[0] >= METHOD_SINCE and p[0] in by and by[p[0]].get("ratio_pct")
            and not by[p[0]].get("data_incomplete")]
    if not cand:
        res["decision"] = "no_comparable_reading"
    else:
        day, _bal, ext = cand[-1]
        shown = M.ck_value(by[day]["ratio_pct"], cal)
        err = round(shown - ext, 2) if shown is not None else None
        res.update(date=day, err_pp=err)
        key = f"{day}:{ext}"
        if err is None:
            res["decision"] = "no_calibration"
        elif abs(err) <= THRESH_PP:
            res["decision"] = "within_2pp"
        elif key in (state.get("handled") or {}):
            res["decision"] = "already_handled"
        else:
            r = push("融資維持率與籌碼K差距超過 2pp",
                     f"{day[5:]}：籌碼K {ext}%，本站估 {shown}%（差 {err:+.1f}pp）。已自動重估校準係數，結果下次開 App 生效。")
            res["pushed"] = r.get("ok", 0)
            res["reestimate"] = reestimate()
            state.setdefault("handled", {})[key] = datetime.now(TW).isoformat(timespec="seconds")
            res["decision"] = "over_2pp_reestimated"
    try:
        LOCAL.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    _log(res)
    return res


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        _log({"decision": "error", "err": f"{type(e).__name__}: {e}"[:200]})
    sys.exit(0)
