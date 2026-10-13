"""常備.開發-28（2026-10-11）：App 會讀的 data/ JSON 檔 schema 驗證＋寫入（發布）前守門。

為什麼放在「git add 之前」而不是逐支寫入程式裡：
  App 讀的 JSON 有 60 多個、寫入者分散在 40 多支腳本，逐支改寫入邏輯既容易漏、也會動到
  「踩過很多坑才調對」的抓取程式（根目錄 CLAUDE.md：不要順手重構）。App 只看得到「被 commit
  ＋push 到 GitHub Pages 的版本」，所以把關點放在每條排程 commit 前一步，結構上一次涵蓋所有寫入者：
  驗證不過的檔 → 還原成 HEAD 的上一版（＝失敗不覆蓋）→ 寫告警報告＋GitHub ::error:: 註記。

schema 內容（每檔）：頂層型別、必要欄位與型別、時間戳欄位（必須存在且可解析成日期時間）、
少數「空了就代表壞掉」的欄位非空檢查。另外一律用嚴格 JSON 解析——Python 寫得出 NaN／Infinity，
但瀏覽器 JSON.parse 會直接拋錯，整個面板就掛了。

[自行裁量] 時間戳欄位名沿用各檔現有名稱（generated_at／fetched_at／updated_at／meta.generated_at…），
不強制統一改名成 generated_at——改名會讓 App 端所有讀取點一起壞，違反「改A壞B」原則。

CLAUDE.md 十二節：守門員自己壞掉只能降級成警告，絕不讓排程非零退出——本檔所有入口都 fail open
（例外 → 視為通過、印 WARN、exit 0）。只有 `check --strict`（給自測／人工用）才會回非零碼。

用法：
  python scripts/data_schema_guard.py check [--strict] [檔案...]      # 驗證（預設全部已登記檔）
  python scripts/data_schema_guard.py guard --report data/schema_guard/market.json [--push] [--files 檔案...]
      # 排程 commit 前呼叫：只看相對 HEAD 有變動（或 --files 指定）的已登記檔；
      # 不過者還原 HEAD 版本（未追蹤的新檔則搬到暫存目錄，不進 commit）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:  # 十二節：cp950 主控台印不出特殊字元時不得崩潰
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent

# ---- schema 登記表 ------------------------------------------------------------
# 型別寫法："str" "int" "num"(int/float，不含 bool) "bool" "dict" "list" "null"，可用 | 組合。
# ts：時間戳欄位路徑（點號表示巢狀），None＝此檔沒有時間戳（靜態設定檔）。ts_nullable：允許 null。
# nonempty：這些欄位（dict/list）為空就判壞——只登記「空了 App 一定整塊壞掉」的大型資料檔。

def _S(type_="dict", ts="generated_at", req=None, nonempty=(), ts_nullable=False, item_req=None):
    return {"type": type_, "ts": ts, "req": dict(req or {}), "nonempty": tuple(nonempty),
            "ts_nullable": ts_nullable, "item_req": dict(item_req or {})}

_META = {"meta": "dict"}
_FETCHED = "fetched_at"
_MG = "meta.generated_at"

SCHEMAS: dict[str, dict] = {
    # 首頁／系統
    "data/STATUS.json": _S(ts="updated_at", req={"data_files": "list", "workflows": "list"}),
    "data/adjustment_anomalies.json": _S(req={"n_warnings": "int", "warnings": "list"}),
    "data/audit_report.json": _S(req={"violation_rate": "num|null", "universe": "int"}),
    "data/auto_heartbeat.json": _S(ts="updated_at", req={"events": "list"}),
    "data/daily_brief.json": _S(req={"premarket": "dict", "weekly": "dict"}),
    "data/weekly_report.json": _S(req={"summary": "list"}),
    "data/smoke_cloud.json": _S(req={"all_passed": "bool", "total": "int", "failures": "list"}),
    "data/live_endpoints.json": _S(ts="meta.updated_at", req={**_META, "endpoints": "list"}),
    "data/ui_glossary.json": _S(ts=None, req={"terms": "list"}),
    "data/coverage.json": _S(ts=_MG, req={**_META, "factors": "dict"}),
    "data/trials_index.json": _S(req={"rows": "list"}),
    # 市場
    "data/market_tw.json": _S(ts=_FETCHED, req={"errors": "list", "taiex": "dict|null", "sectors": "list"}),
    "data/market_us.json": _S(ts=_FETCHED, req={"indices": "dict"}),
    "data/fx.json": _S(ts=_FETCHED, req={"usd_twd": "dict|null"}),
    "data/margin_maintenance.json": _S(type_="list", ts=None, nonempty=("$",),
                                       item_req={"date": "str", "ratio_pct": "num|null"}),
    "data/margin_ratio_calibration.json": _S(req={"segments": "list"}),
    "data/sector_flow.json": _S(ts=_MG, req={**_META, "sectors": "dict", "stocks": "dict"}),
    "data/institutional_history.json": _S(ts=_MG, req={**_META, "dates": "list", "series": "dict"}),
    "data/adr_premium.json": _S(ts="computed_at", req={"rows": "dict"}),
    "data/cftc_cot.json": _S(ts=_FETCHED, req={"contracts": "dict"}),
    "data/bls_macro.json": _S(ts=_FETCHED, req={"series": "dict"}),
    "data/customs_trade.json": _S(ts=_FETCHED, req={"errors": "list"}),
    "data/industrial_production.json": _S(ts=_FETCHED, req={"errors": "list"}),
    "data/short_lending_available.json": _S(ts=_FETCHED, req={"twse": "dict", "otc": "dict"}),
    "data/securities_lending_sell.json": _S(ts=_FETCHED, req={"twse": "dict", "tpex": "dict"}),
    "data/foreign_holding.json": _S(ts=_FETCHED, req={"stocks": "dict"}),
    "data/disposal_flags.json": _S(ts=_MG, req={**_META, "disposal": "dict", "notice": "dict"}),
    "data/earnings_calendar.json": _S(ts=_MG, req={**_META, "earnings": "dict"}),
    # 報價
    "data/quotes_tw.json": _S(ts=_FETCHED, req={"quotes": "dict"}),
    "data/quotes_us.json": _S(ts=_FETCHED, req={"quotes": "dict"}),
    "data/quotes_all_tw.json": _S(ts=_FETCHED, req={"quotes": "dict"}, nonempty=("quotes",)),
    "data/quotes_ibkr.json": _S(ts=_FETCHED, req={"connected": "bool", "quotes": "dict"}),
    "data/quotes_sinopac.json": _S(ts=_FETCHED, req={"connected": "bool", "quotes": "dict"}),
    "data/sparklines.json": _S(ts=_MG, req={**_META, "sparklines": "dict"}),
    "data/whitelist_price_status.json": _S(req={"codes": "dict"}),
    # 個股
    "data/company_info.json": _S(ts=_MG, req={**_META, "companies": "dict"}, nonempty=("companies",)),
    "data/fundamentals.json": _S(ts=_MG, req={**_META, "fundamentals": "dict"}, nonempty=("fundamentals",)),
    "data/stock_detail.json": _S(ts=_MG, req={**_META, "stocks": "dict"}, nonempty=("stocks",)),
    "data/stock_detail_eps.json": _S(ts=_MG, req={**_META, "stocks": "dict"}),
    "data/holders.json": _S(ts=_MG, req={**_META, "stocks": "dict"}),
    "data/cash_flow.json": _S(req={"stocks": "dict"}),
    # 先.八十二-1：price_history 改拆檔（scripts/price_history_store.py）；舊單檔不再登記，
    # 否則單檔被刪會被當成「讀檔失敗」而從 HEAD 還原回 72MB 大檔。
    "data/price_history/_meta.json": _S(ts=_MG, req={**_META, "code_order": "list"}, nonempty=("code_order",)),
    **{f"data/price_history/b{_b}.json": _S(ts=None, req={"prices": "dict"}) for _b in list("0123456789") + ["x"]},
    "data/listed_universe.json": _S(ts=_MG, req={**_META, "active": "list", "last_seen": "dict"},
                                    nonempty=("active",)),
    "data/events.json": _S(ts=_FETCHED, req={"events": "list"}),
    "data/news.json": _S(ts=_FETCHED, req={"news": "list"}),
    # 選股／策略
    "scores.json": _S(ts=_MG, req={**_META, "stocks": "list"}, nonempty=("stocks",)),
    "scores_momentum.json": _S(ts=_MG, req={**_META, "stocks": "list"}, nonempty=("stocks",)),
    "scores_future.json": _S(ts=_MG, req={**_META, "stocks": "list"}, nonempty=("stocks",)),
    "data/picks_ledger.json": _S(ts=_MG, req={**_META, "snapshots": "list"}),
    "data/signal_status.json": _S(req={"directions": "list"}),
    "data/strategies.json": _S(req={"strategies": "list"}),
    "data/strategy_curves.json": _S(ts=_MG, req={**_META, "lines": "list"}),
    "data/strategy_history.json": _S(ts=_MG, req={**_META, "lines": "dict"}),
    "data/strategy_monthly_returns.json": _S(req={"months": "list", "returns": "dict"}),
    "data/strategy_performance.json": _S(req={"strategies": "dict"}),
    "data/supply_watchlist.json": _S(ts="meta.as_of", req={**_META, "rows": "list"}),
    "data/paper_7030.json": _S(req={"started": "bool"}),
    "data/paper_1b.json": _S(req={"started": "bool"}),
    "data/paper_3.json": _S(req={"started": "bool"}),
    "data/paper_4.json": _S(req={"started": "bool"}),
    "data/paper_tracking_watch.json": _S(req={"items": "list"}),
    "data/paper_trades.json": _S(ts_nullable=True, req={"strategies": "list"}),
    # 美股
    "data/us_sic.json": _S(ts=_FETCHED, req={"tickers": "dict"}),
    "data/us_events.json": _S(ts=_FETCHED, req={"tickers": "dict"}),
    "data/us_insider_trading.json": _S(ts=_FETCHED, req={"tickers": "dict"}),
    "data/us_13f_holdings.json": _S(ts=_FETCHED, req={"filers": "dict"}),
    "data/us_financials.json": _S(req={"financials": "dict"}),
    "data/us_scores_v0.json": _S(ts=_MG, req={**_META, "stocks": "list"}),
    "data/us_analyst_reco.json": _S(req={"tickers": "dict"}),
}

# ---- 驗證 ---------------------------------------------------------------------

_PY = {"str": (str,), "int": (int,), "num": (int, float), "bool": (bool,),
       "dict": (dict,), "list": (list,), "null": (type(None),)}


def _type_ok(v, spec: str) -> bool:
    for t in spec.split("|"):
        if t in ("int", "num") and isinstance(v, bool):
            continue
        if isinstance(v, _PY[t]):
            return True
    return False


def _tname(v) -> str:
    return "null" if v is None else type(v).__name__


def _get(obj, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _ts_ok(s) -> bool:
    if not isinstance(s, str) or not s.strip():
        return False
    try:
        datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _reject_constant(name):
    raise ValueError(f"含 {name}（瀏覽器 JSON.parse 不接受）")


def strict_loads(text: str):
    return json.loads(text, parse_constant=_reject_constant)


def validate_obj(rel: str, obj) -> list[str]:
    sc = SCHEMAS.get(rel)
    if sc is None:
        return []
    errs: list[str] = []
    if not _type_ok(obj, sc["type"]):
        return [f"頂層型別應為 {sc['type']}，實際 {_tname(obj)}"]
    if sc["type"] == "list":
        if "$" in sc["nonempty"] and not obj:
            errs.append("清單為空")
        for i, row in enumerate(obj):
            if not isinstance(row, dict):
                errs.append(f"[{i}] 應為 dict，實際 {_tname(row)}")
                break
            for k, t in sc["item_req"].items():
                if k not in row:
                    errs.append(f"[{i}] 缺必要欄位 {k}")
                elif not _type_ok(row[k], t):
                    errs.append(f"[{i}].{k} 型別應為 {t}，實際 {_tname(row[k])}")
            if len(errs) >= 5:
                break
        return errs
    for k, t in sc["req"].items():
        if k not in obj:
            errs.append(f"缺必要欄位 {k}")
        elif not _type_ok(obj[k], t):
            errs.append(f"{k} 型別應為 {t}，實際 {_tname(obj[k])}")
    if sc["ts"]:
        found, v = _get(obj, sc["ts"])
        if not found:
            errs.append(f"缺時間戳欄位 {sc['ts']}")
        elif v is None and sc["ts_nullable"]:
            pass
        elif not _ts_ok(v):
            errs.append(f"時間戳 {sc['ts']} 無法解析：{str(v)[:40]!r}")
    for k in sc["nonempty"]:
        if k in obj and isinstance(obj[k], (dict, list)) and not obj[k]:
            errs.append(f"{k} 為空（此檔空了 App 會整塊無資料，視為寫壞）")
    return errs


def validate_file(path: Path, rel: str | None = None) -> list[str]:
    rel = rel or path.resolve().relative_to(REPO).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"讀檔失敗：{type(e).__name__}: {e}"]
    if text.startswith("﻿"):
        return ["檔頭有 BOM（瀏覽器 r.json() 會解析失敗）"]
    try:
        obj = strict_loads(text)
    except Exception as e:
        return [f"不是合法 JSON：{type(e).__name__}: {str(e)[:160]}"]
    return validate_obj(rel, obj)


# ---- git 輔助 -----------------------------------------------------------------

def _git(*args, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _changed_registered() -> list[str]:
    """相對 HEAD 有變動（含未追蹤）的已登記檔。"""
    out = _git("status", "--porcelain", "--untracked-files=all", "--", *SCHEMAS.keys()).stdout
    rels = []
    for line in out.splitlines():
        p = line[3:].strip().strip('"')
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        if p in SCHEMAS:
            rels.append(p)
    return sorted(set(rels))


def _tracked_in_head(rel: str) -> bool:
    return _git("cat-file", "-e", f"HEAD:{rel}").returncode == 0


def _reject(rel: str) -> str:
    """不覆蓋：已追蹤檔還原成 HEAD 版本；未追蹤新檔搬到暫存目錄（不進 commit）。回傳處置說明。"""
    path = REPO / rel
    if _tracked_in_head(rel):
        r = _git("checkout", "HEAD", "--", rel)
        if r.returncode == 0:
            return "已還原成上一版（HEAD），本次不發布"
        return f"還原失敗：{r.stderr.strip()[:200]}"
    dest_dir = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "schema_guard_rejected"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / rel.replace("/", "__")
    shutil.move(str(path), str(dest))
    return f"新檔未通過，已移出 repo 至 {dest}"


# ---- 報告 ---------------------------------------------------------------------

def _write_report(report_path: Path, result: dict) -> None:
    """只有「結果內容」變了才重寫，避免每次排程都產生一個只有時間戳不同的 commit。"""
    try:
        old = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        old = None
    key = lambda d: json.dumps({k: d.get(k) for k in ("rejected", "guard_error", "checked")},
                               ensure_ascii=False, sort_keys=True) if isinstance(d, dict) else None
    if old is not None and key(old) == key(result):
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, report_path)


def _push_alert(result: dict) -> None:
    """本機排程用（--push）：有檔被攔下就送一則 Web Push；推播失敗只印警告（十二節）。
    雲端 workflow 沒有推播憑證，告警走 ::error:: 註記＋data/schema_guard/*.json（設定頁顯示）。"""
    try:
        sys.path.insert(0, str(REPO / "research"))
        import web_push
        files = "、".join(r["file"].rsplit("/", 1)[-1] for r in result["rejected"])
        web_push.notify("Alpha 資料檔驗證失敗（未發布）", f"{result['label']}：{files} 不符 schema，已保留上一版。"[:220],
                        kind="schema_guard")
    except Exception as e:
        print(f"[schema_guard] WARN 推播失敗（{type(e).__name__}），不影響流程")


def guard(files: list[str] | None, report: str | None, label: str, push: bool = False) -> dict:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    result = {"generated_at": now, "label": label, "checked": [], "rejected": [], "guard_error": None,
              "note": "常備.開發-28：排程 commit 前驗證 App 會讀的 JSON；不過者還原上一版、不發布。"
                      "generated_at 是「結果最後一次改變」的時間，不是每次執行時間。"}
    try:
        if files:
            rels = []
            for f in files:
                p = Path(f)
                p = p if p.is_absolute() else (REPO / p)
                rel = p.resolve().relative_to(REPO).as_posix()
                if rel in SCHEMAS and p.exists():
                    rels.append(rel)
        else:
            rels = _changed_registered()
        result["checked"] = sorted(rels)
        for rel in rels:
            errs = validate_file(REPO / rel, rel)
            if not errs:
                continue
            action = _reject(rel)
            result["rejected"].append({"file": rel, "errors": errs[:8], "action": action})
            msg = f"{rel} schema 驗證失敗：{'；'.join(errs[:3])} → {action}"
            print(f"::error title=資料檔 schema 驗證失敗::{msg}")
            print(f"[schema_guard] ✗ {msg}", file=sys.stderr)
        print(f"[schema_guard] {label}：檢查 {len(rels)} 檔，攔下 {len(result['rejected'])} 檔")
    except Exception as e:  # 十二節：守門員自己壞掉 → fail open
        result["guard_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        print(f"::warning title=schema 守門員自身失敗（fail open，不擋發布）::{result['guard_error']}")
    if push and result["rejected"]:
        _push_alert(result)
    if report:
        try:
            _write_report(REPO / report, result)
        except Exception as e:
            print(f"[schema_guard] WARN 寫報告失敗（不中止）：{type(e).__name__}: {e}")
    return result


def check(files: list[str], strict: bool) -> int:
    targets = files or [r for r in SCHEMAS if (REPO / r).exists()]
    bad = 0
    for f in targets:
        p = Path(f)
        p = p if p.is_absolute() else (REPO / p)
        rel = p.resolve().relative_to(REPO).as_posix()
        if rel not in SCHEMAS:
            print(f"－ {rel}：未登記 schema（略過）")
            continue
        if not p.exists():
            print(f"－ {rel}：檔案不存在（略過）")
            continue
        errs = validate_file(p, rel)
        if errs:
            bad += 1
            print(f"✗ {rel}：{'；'.join(errs[:5])}")
        else:
            print(f"✓ {rel}")
    print(f"合計 {len(targets)} 檔，{bad} 檔不通過")
    return 1 if (strict and bad) else 0


def main(argv: list[str]) -> int:
    try:
        if not argv or argv[0] not in ("check", "guard"):
            print(__doc__)
            return 0
        cmd, rest = argv[0], argv[1:]
        strict = "--strict" in rest
        report = None
        label = os.environ.get("GITHUB_WORKFLOW") or "local"
        files: list[str] = []
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--report" and i + 1 < len(rest):
                report = rest[i + 1]; i += 2; continue
            if a == "--label" and i + 1 < len(rest):
                label = rest[i + 1]; i += 2; continue
            if a in ("--strict", "--files", "--push"):
                i += 1; continue
            files.append(a); i += 1
        if cmd == "check":
            return check(files, strict)
        guard(files or None, report, label, push="--push" in rest)
        return 0
    except Exception as e:  # 十二節：任何未預期例外都 fail open
        print(f"::warning title=schema 守門員自身失敗（fail open）::{type(e).__name__}: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
