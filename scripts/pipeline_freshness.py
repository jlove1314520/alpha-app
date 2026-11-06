# -*- coding: utf-8 -*-
"""本機管線新鮮度判定（2026-09-10 停擺四）。

**為什麼要有這支**：`alpha.db` 從 2026-08-21 起沒有再進過任何一筆資料，
整整 20 天沒人發現。事後檢討，缺的不是某一個修正，是**一張清單**——
我們從來沒有「本機有哪些管線、每一條最後一次真正產出是什麼時候」的完整表。

這支只做一件事：讀 `data/seed/pipeline_registry.json`，逐條算出「最後產出時間」
與「是否停擺」。它是**共用函式庫**，兩個地方都呼叫它：

  * `scripts/pipeline_inventory.py`         —— 印給人看的清點表
  * `scripts/check_external_connectivity.py` —— 每 5 分鐘的自動告警

兩邊讀同一份登錄檔、走同一套判定，才不會出現「表上有、自檢沒監控」的漏洞
（總司令 2026-09-10 指示停擺四.3）。

**mtime 與資料層時間戳的差別是這支的核心**：
mtime 只證明「檔案被寫過」，不證明「內容是新的」。
`alpha.db` 每天都被連線寫入所以 mtime 天天更新，但 `daily_price` 的
`max(date)` 停在 8/21——這正是靜默停擺的典型形狀。
所以凡是檔案內部帶有日期／時間戳的，一律看資料層的值。
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from expected_shift_calendar import count_missed_shifts

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "seed" / "pipeline_registry.json"
TZ = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 班次數門檻（2026-09-16 總司令裁示【班次數】）
#
# 背景：「間隔×3倍」對每天固定跑幾班的雲端管線（market.yml 三班次）會把
# 「連續錯過2個應跑班次」跟「假日/週末」混在一起容忍到72小時——2026-09-15
# 那次31小時停擺，用這套公式要撐到72小時才會亮紅燈，比總司令自己肉眼發現
# 更慢。裁示是「不加新架構，改判準」：不是重寫一套排程系統，只是把「以時間
# 長度為單位」的門檻換成「以應跑班次數為單位」，且班次要不要跑用交易日曆
# （週末＋國定假日）判定，避免把「本來就不該跑」的假日算成停擺。
#
# 應跑班次的精確計算（逐一對照各 workflow 實際 cron）交給
# scripts/expected_shift_calendar.py（count_missed_shifts()），這裡不重複
# 一份簡化版——兩份平行維護遲早分岔，本檔只負責讀 shift_profile 設定、呼叫
# 那支、把結果併進既有的 rows/stalled 輸出格式。
#
# 沒有設定 shift_profile 的管線（本機常駐/連續型任務，如 IBKR/Shioaji 報價、
# alpha.db）維持原本「間隔×stall_factor」判定不變——那些任務不是「一天固定
# 幾班」的形狀，班次計數對它們沒有意義，勉強套用才是真的在加架構。


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _resolve(rel: str) -> Path:
    """登錄檔裡的路徑可以是 repo 相對路徑，也可以是絕對路徑（alpha.db 在 repo 外）。"""
    p = Path(rel)
    return p if p.is_absolute() else ROOT / rel


def _parse_ts(v) -> datetime | None:
    """把各種寫法的時間戳轉成帶時區的 datetime。

    容忍三種格式：ISO 帶時區、ISO 不帶時區（當成台北時間）、
    以及 `20260821` 這種純日期字串（TAIFEX 那張表用的）。
    無法解析就回 None，讓呼叫端標成 unknown——**不要猜**。
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.isdigit() and len(s) == 8:
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


_LOG_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2})?")


def _dig(doc, path: str):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _filter_lines(spec: dict, text: str) -> str:
    """先.一三五-1kh-p：選填 line_filter（正規式，必須符合）／line_exclude（正規式，不得符合）。
    兩個都沒寫就原樣回傳（既有條目行為不變）。正規式寫錯只降級成警告、照原文處理（十二節）。"""
    inc, exc = spec.get("line_filter"), spec.get("line_exclude")
    if not inc and not exc:
        return text
    try:
        ri = re.compile(inc) if inc else None
        rx = re.compile(exc) if exc else None
        return "\n".join(ln for ln in text.splitlines()
                         if (ri is None or ri.search(ln)) and (rx is None or not rx.search(ln)))
    except re.error as e:
        print(f"::warning::{spec.get('task')} line_filter 正規式錯誤，照原文處理：{e}")
        return text


def _last_output(spec: dict, f: Path) -> tuple[datetime | None, str]:
    """回傳 (最後產出時間, 這個時間是怎麼來的)。"""
    kind = spec.get("freshness", "mtime")
    if kind == "mtime":
        return datetime.fromtimestamp(f.stat().st_mtime, TZ), "檔案修改時間"
    if kind == "json_field":
        doc = json.loads(f.read_text(encoding="utf-8"))
        field = spec["field"]
        return _parse_ts(_dig(doc, field)), f"JSON 欄位 {field}"
    if kind == "log_last_timestamp":
        # 先.一〇三-7：cycle log 改讀 log 內最後一個時間戳。mtime 會被 git checkout／pull 改寫，
        # 日誌一字未增也會看起來是新的；只讀檔尾 64KB，找不到時間戳才退回 mtime 並註明。
        with f.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            tail = fh.read().decode("utf-8", errors="replace")
        # 先.一三五-1kh-p：多支排程共用一份日誌時，用選填 line_filter／line_exclude 只取屬於這一支的行
        tail = _filter_lines(spec, tail)
        hits = _LOG_TS_RE.findall(tail)
        best = None
        for d, t, tz in hits:
            dt = _parse_ts(f"{d}T{t}{tz}")
            if dt and (best is None or dt > best):
                best = dt
        if best:
            return best, "log 內最後時間戳"
        return datetime.fromtimestamp(f.stat().st_mtime, TZ), "log 內找不到時間戳，退回檔案修改時間"
    if kind == "dir_latest_json_field":
        # 先.一〇九-29：每日一檔的目錄（例 data/pe_snapshot/<資料日>.json），取檔名排序最後一個 *.json 讀欄位。
        # 例外交給 evaluate() 的單條 try，只標 unknown、不影響其他條。
        files = sorted(f.glob(spec.get("glob", "*.json")))
        if not files:
            return None, "目錄內沒有符合的檔案"
        doc = json.loads(files[-1].read_text(encoding="utf-8"))
        field = spec["field"]
        return _parse_ts(_dig(doc, field)), f"目錄最新檔 {files[-1].name} 的 {field}"
    if kind == "jsonl_last_field":
        lines = [ln for ln in _filter_lines(spec, f.read_text(encoding="utf-8")).splitlines() if ln.strip()]
        if not lines:
            return None, "JSONL 為空（或沒有符合 line_filter 的列）"
        field = spec["field"]
        return _parse_ts(_dig(json.loads(lines[-1]), field)), f"JSONL 末筆 {field}"
    if kind == "sqlite_max_date":
        # 唯讀開啟：這支是監測器，絕不能碰到被監測的資料庫
        con = sqlite3.connect(f"file:{f.as_posix()}?mode=ro", uri=True)
        try:
            best, detail = None, []
            for t in spec.get("tables", []):
                row = con.execute(
                    f'select max("{t["column"]}") from "{t["table"]}"').fetchone()
                dt = _parse_ts(row[0] if row else None)
                detail.append(f'{t["table"]}={row[0] if row else None}')
                # 取**最新**的那一張表：只要有一張還在進資料，就不算整條管線死了
                if dt and (best is None or dt > best):
                    best = dt
            return best, "各表 max(date)：" + "、".join(detail)
        finally:
            con.close()
    return None, f"未知的 freshness 類型 {kind}"


_LOG_DAY_RE = re.compile(r"^\[(\d{2})-(\d{2}) \d{2}:\d{2}\]")


def _fallback_ratio(spec: dict, f: Path, now: datetime) -> tuple[str, str, dict]:
    """先.一三五-1kh-e2（收件匣 039 已定案 1kh-e 甲）：雲端停擺被本機備援遮住的判斷。

    `data/quotes_tw.json`／`data/news.json` 的時間戳雲端與本機備援都會刷新，看產出檔永遠是新的；
    改看本機備援自己的紀錄：每天「雲端落後→本機補抓」占全部判斷的比例。雲端全停時，備援補一次就把
    檔案刷新，下一輪看到「雲端新鮮」而跳過，所以比例約 50%（不是 100%）；雲端正常時接近 0%。
    門檻（ratio_threshold）因此取兩者之間，最近 consecutive_days 個「有足夠樣本的日子」都 ≥ 門檻才判停擺。

    登錄檔欄位：format＝"jsonl"（field_ts／field_decision／fetched_values／skip_values）或
    "log"（fetched_regex／skip_regex，日期取行首 [MM-DD HH:MM]）；min_samples_per_day、
    consecutive_days、ratio_threshold、max_age_days。回傳 (status, reason, extra)。
    讀檔／解析失敗由 evaluate() 的單條 try 接住只標 unknown（十二節：寧可漏抓，不可癱瘓）。
    """
    fmt = spec.get("format", "jsonl")
    per_day: dict = {}
    text = f.read_text(encoding="utf-8", errors="replace")
    if fmt == "jsonl":
        fts, fdec = spec.get("field_ts", "ts"), spec.get("field_decision", "decision")
        fetched_v = set(spec.get("fetched_values", ["fetched"]))
        skip_v = set(spec.get("skip_values", ["skip_cloud_fresh"]))
        for ln in text.splitlines():
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except ValueError:
                continue  # 單行壞掉跳過，不讓一筆髒資料炸掉整條
            dt = _parse_ts(d.get(fts))
            dec = d.get(fdec)
            if dt is None or dec not in fetched_v | skip_v:
                continue
            c = per_day.setdefault(dt.astimezone(TZ).date(), [0, 0])
            c[0 if dec in fetched_v else 1] += 1
    elif fmt == "log":
        rf, rs = re.compile(spec["fetched_regex"]), re.compile(spec["skip_regex"])
        for ln in text.splitlines():
            m = _LOG_DAY_RE.match(ln)
            if not m:
                continue
            hit_f, hit_s = bool(rf.search(ln)), bool(rs.search(ln))
            if not (hit_f or hit_s):
                continue
            mo, dd = int(m.group(1)), int(m.group(2))
            yr = now.year - 1 if mo > now.month else now.year  # 日誌沒寫年；跨年時月份大於今天的算去年
            try:
                day = datetime(yr, mo, dd).date()
            except ValueError:
                continue
            c = per_day.setdefault(day, [0, 0])
            c[0 if hit_f else 1] += 1
    else:
        return "unknown", f"未知的 format {fmt}", {}
    min_n = int(spec.get("min_samples_per_day", 6))
    need = int(spec.get("consecutive_days", 2))
    thr = float(spec.get("ratio_threshold", 0.4))
    days = sorted(d for d, (a, b) in per_day.items() if a + b >= min_n)[-need:]
    detail = {d.isoformat(): {"fetched": per_day[d][0], "skip": per_day[d][1],
                              "ratio": round(per_day[d][0] / sum(per_day[d]), 3)} for d in days}
    extra = {"fallback_days": detail, "ratio_threshold": thr}
    if len(days) < need:
        return "skipped", f"本機備援紀錄裡樣本足夠（≥{min_n} 次／日）的日子不到 {need} 天，不判定", extra
    max_age = int(spec.get("max_age_days", 5))
    if (now.date() - days[-1]).days > max_age:
        return "skipped", f"本機備援紀錄最近有樣本的日子是 {days[-1]}，超過 {max_age} 天，不判定（備援本身可能沒在跑）", extra
    if all(detail[d.isoformat()]["ratio"] >= thr for d in days):
        txt = "、".join(f'{k} {v["fetched"]}/{v["fetched"] + v["skip"]}' for k, v in detail.items())
        return "stalled", f"雲端停擺被本機備援遮住：最近 {need} 天本機補抓比例都 ≥ {thr:.0%}（{txt}）", extra
    return "ok", "雲端大多準時（本機補抓比例未連續偏高）", extra


def _tw_closed(d) -> bool:
    """台股休市日（週末＋data/trading_calendar.json closed／unscheduled_closed）。讀不到日曆 → False（照常判定）。"""
    if d.weekday() >= 5:
        return True
    try:
        cal = json.loads((_resolve("data/trading_calendar.json")).read_text(encoding="utf-8"))
        y = (cal.get("tw") or {}).get(str(d.year)) or {}
        return d.isoformat() in (set(y.get("closed") or []) | set(y.get("unscheduled_closed") or []))
    except Exception:  # noqa: BLE001 -- 監測器自身失敗只降級（十二節）
        return False


def evaluate(now: datetime | None = None) -> tuple[list[dict], list[str]]:
    """逐條算出狀態，回傳 (每條的結果, 停擺告警文字)。

    每一條各自 try：這支是監測器，**監測器死掉比被監測的東西死掉更糟**，
    單條出錯只標成 unknown，不影響其他條。
    """
    reg = load_registry()
    now = now or datetime.now(TZ)
    factor = reg.get("stall_factor", 3)
    rows: list[dict] = []
    stalled: list[str] = []

    for spec in reg.get("pipelines", []):
        row = {
            "task": spec["task"],
            "purpose": spec.get("purpose", ""),
            "artifact": spec["artifact"],
            "expected_interval_min": spec["interval_min"],
            "freshness": spec.get("freshness", "mtime"),
        }
        try:
            # 2026-10-23 DevQueue 20261023-123102：經核准停用的排程（例：先.一二七-A 停用 AlphaMarathon／
            # AlphaHypothesisQueue）在登錄檔標 "retired": "停用日期＋依據"，不再判停擺；條目保留供稽核。
            # 沿用 skipped 狀態，下游（fault ledger、STATUS）不必另外認新狀態。
            retired = spec.get("retired")
            if retired:
                row.update(status="skipped", reason=f"已停用：{retired}")
                rows.append(row)
                continue
            # 2026-11-01 DevQueue 20261101-130102（先.一三五-1ha）：只在台股交易日跑的管線（登錄檔標
            # "tw_trading_days_only": true），休市日沒產出是正常的。日曆讀不到時照常判定（_tw_closed 回 False）。
            if spec.get("tw_trading_days_only") and _tw_closed(now.date()):
                row.update(status="skipped", reason="台股休市日，沒產出是正常的")
                rows.append(row)
                continue
            win = spec.get("window_hours")
            if win and not (win[0] <= now.hour < win[1]):
                row.update(status="skipped",
                           reason=f"觀察窗 {win[0]}:00-{win[1]}:00 之外，沒產出是正常的")
                rows.append(row)
                continue
            f = _resolve(spec["artifact"])
            if not f.exists() and spec.get("check") == "fallback_ratio":
                # 備援紀錄只在本機有（不進公開 repo）；雲端 runner 讀不到是正常的，不判停擺（十二節）
                row.update(status="skipped", reason="本機備援紀錄不存在（雲端 runner 或備援未啟用），不判定")
                rows.append(row)
                continue
            if not f.exists():
                row.update(status="missing", reason="產出檔不存在")
                stalled.append(f'{spec["task"]}：產出檔 {spec["artifact"]} 不存在')
                rows.append(row)
                continue
            if spec.get("check") == "fallback_ratio":
                st, why, extra = _fallback_ratio(spec, f, now)
                # 2026-11-06 先.一三五-1kh-e5［預設放行］建議乙：登錄檔標 "known_issue"（已知原因＋依據）的，
                # 判到停擺只記不告警——狀態改 "known"（不在 fault ledger 的 FAULT_STATUSES、不進 stalled 清單），
                # 原因照實寫進 reason。比例回落（ok）時照常顯示 ok；要恢復告警，刪掉該欄即可。
                known = spec.get("known_issue")
                if st == "stalled" and known:
                    st, why = "known", f"已知、只記不告警（{known}）：{why}"
                row.update(status=st, reason=why, source="本機備援補抓比例", **extra)
                if st == "stalled":
                    stalled.append(f'{spec["task"]}：{why}')
                rows.append(row)
                continue
            last, how = _last_output(spec, f)
            row["source"] = how
            if last is None:
                row.update(status="unknown", reason=f"讀不到時間戳（{how}）")
                rows.append(row)
                continue
            age = (now - last).total_seconds() / 60.0
            profile_name = spec.get("shift_profile")
            if profile_name:
                missed, shift_labels = count_missed_shifts(profile_name, last, now)
                threshold = spec.get("missed_shift_threshold", 2)
                row.update(
                    last_output=last.isoformat(), age_min=round(age, 1),
                    shift_profile=profile_name, missed_shifts=missed,
                    missed_shift_threshold=threshold,
                    latest_due_shift=shift_labels[-1] if shift_labels else None,
                    status="stalled" if missed >= threshold else "ok",
                )
                if missed >= threshold:
                    stalled.append(
                        f'{spec["task"]}：{spec["artifact"]} 已連續錯過 {missed} 個應跑班次'
                        f'（門檻 {threshold} 班，最近應跑 '
                        f'{shift_labels[-1] if shift_labels else "?"}；{how}）')
                rows.append(row)
                continue
            limit = spec["interval_min"] * factor
            # 2026-11-01 DevQueue 20261101-130102：有觀察窗的管線，末筆在今天開窗之前（前一個窗口的最後一筆）時，
            # 從開窗時刻起算——舊版拿前一晚末筆算年齡，每天開窗第一次檢查（13:02）必判停擺，
            # AlphaTwsePublishProbe 的 fault_history 因此累積 28 次假警報。開窗後超過門檻仍沒產出才算停擺。
            judged_age = age
            if win:
                window_open = now.replace(hour=win[0], minute=0, second=0, microsecond=0)
                if last < window_open:
                    judged_age = (now - window_open).total_seconds() / 60.0
                    row["age_from_window_open_min"] = round(judged_age, 1)
            row.update(last_output=last.isoformat(), age_min=round(age, 1),
                       stall_limit_min=limit,
                       status="stalled" if judged_age > limit else "ok")
            if judged_age > limit:
                stalled.append(
                    f'{spec["task"]}：{spec["artifact"]} 已 {age:.0f} 分鐘沒有新產出'
                    f'（預期每 {spec["interval_min"]} 分鐘，門檻 {limit} 分鐘；{how}）')
        except Exception as e:  # noqa: BLE001
            row.update(status="unknown", reason=f"{type(e).__name__}: {e}")
        rows.append(row)
    return rows, stalled
