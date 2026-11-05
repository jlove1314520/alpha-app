# -*- coding: utf-8 -*-
"""從 git 歷史重建融資個股「依官方資料日」逐股表（先.一三五-1jt-a 甲，2026-11-05 [預設放行]）。零外部請求。

背景：`data/margin_by_stock_history.json` 的 series 以「執行日鍵」存，同鍵晚班會覆寫前一班；
上櫃 10/05、10/13、10/19、10/29、上市 10/27（＋可選上櫃 9/24）的逐股數字只剩 git 歷史（1jt／1jx／1jy）。
本程式逐版讀 git 歷史（加上目前工作目錄的檔），把每一版每個執行日鍵的上市／上櫃逐股快照收成「快照節點」，
再依下列順序給每個節點定官方資料日：
  ① 錨點：該版本有 `data_dates[鍵][邊]` → 直接採用（10/29 起的版本才有）。
  ② 鏈結：節點 B 的「前日融資餘額」與節點 A 的「今日融資餘額」≥80% 相同（共同代號 ≥50）→ B＝A 的下一個交易日
     （交易日曆＝平日扣掉 `trading_calendar.json` 的 closed＋unscheduled_closed）。
  ③ 慣例（只用在①②都推不到的節點）：首見於執行日鍵 K、且首見時間早於台北 K 日 18:00 → 前一交易日。
衝突（同一節點推出兩個日期、或兩個節點推到同一日但數值不同）一律不寫、列在報告。
寫入 `by_data_date[side][YYYYMMDD][code]`（同一資料日同一檔先到先存、不覆寫既有）與 `by_data_date_src`（git:版本 hash）。
series／data_dates／tpex_codes 不動。

用法：python scripts/rebuild_margin_by_data_date.py [--dry-run]
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
REL = "data/margin_by_stock_history.json"
CAL = ROOT / "data" / "trading_calendar.json"
TW = timezone(timedelta(hours=8))
SAME_RATIO = 0.999
CHAIN_RATIO = 0.8
MIN_CODES = 50


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")


def closed_days() -> set[str]:
    c = json.loads(CAL.read_text(encoding="utf-8"))
    out = set()
    for y in (c.get("tw") or {}).values():
        for k in ("closed", "unscheduled_closed"):
            out |= set(y.get(k) or [])
    return out


CLOSED: set[str] = set()


def is_td(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in CLOSED


def step_td(d8: str, n: int) -> str:
    d = datetime.strptime(d8, "%Y%m%d").date()
    while True:
        d += timedelta(days=n)
        if is_td(d):
            return d.strftime("%Y%m%d")


def ratio_same(a: dict, b: dict, ia: int, ib: int) -> tuple[float, int]:
    common = [c for c in a if c in b]
    if len(common) < MIN_CODES:
        return 0.0, len(common)
    return sum(1 for c in common if a[c][ia] == b[c][ib]) / len(common), len(common)


def full_same(a: dict, b: dict) -> bool:
    common = [c for c in a if c in b]
    return len(common) >= MIN_CODES and sum(1 for c in common if a[c] == b[c]) / len(common) >= SAME_RATIO


def main() -> int:
    dry = "--dry-run" in sys.argv
    global CLOSED
    CLOSED = closed_days()
    log = git("log", "--reverse", "--format=%H %ct", "--", REL).split()
    versions = [(log[i][:11], int(log[i + 1])) for i in range(0, len(log), 2)]
    docs = []
    for h, ct in versions:
        try:
            docs.append((h, ct, json.loads(git("show", f"{h[:11]}:{REL}"))))
        except Exception as e:  # noqa: BLE001
            print(f"! 讀不到版本 {h}：{e}（略過）")
    cur_path = ROOT / REL
    cur = json.loads(cur_path.read_text(encoding="utf-8"))
    docs.append(("worktree", int(datetime.now(TW).timestamp()), cur))
    tpex_codes = set(cur.get("tpex_codes") or [])
    for _, _, dc in docs:
        tpex_codes |= set(dc.get("tpex_codes") or [])
    print(f"版本 {len(docs)} 個（含工作目錄），上櫃代號 {len(tpex_codes)} 個")

    report = {"conflicts": [], "nodes": {}}
    result = {}
    for side in ("twse", "tpex"):
        nodes = []  # {vals, first:(hash,ct,key), anchors:set}
        sig_cache = {}
        for h, ct, dc in docs:
            ser = dc.get("series") or {}
            keys = sorted({k for b in ser.values() if isinstance(b, dict) for k in b})
            ddmap = dc.get("data_dates") or {}
            for k in keys:
                snap = {}
                for code, b in ser.items():
                    if not isinstance(b, dict) or ((code in tpex_codes) != (side == "tpex")):
                        continue
                    v = b.get(k)
                    if isinstance(v, list) and len(v) == 3:
                        snap[code] = tuple(v)
                if len(snap) < MIN_CODES:
                    continue
                sig = hash(frozenset(snap.items()))
                idx = sig_cache.get(sig)
                if idx is None:
                    idx = next((i for i, n in enumerate(nodes) if full_same(n["vals"], snap)), None)
                    if idx is None:
                        nodes.append({"vals": dict(snap), "first": (h, ct, k), "anchors": set()})
                        idx = len(nodes) - 1
                    else:
                        for c, v in snap.items():
                            nodes[idx]["vals"].setdefault(c, v)
                    sig_cache[sig] = idx
                a = (ddmap.get(k) or {}).get(side)
                if a:
                    nodes[idx]["anchors"].add(a)
        # ② 鏈結邊
        nxt = {i: [] for i in range(len(nodes))}
        prv = {i: [] for i in range(len(nodes))}
        for i, A in enumerate(nodes):
            for j, B in enumerate(nodes):
                if i == j:
                    continue
                r, n = ratio_same(A["vals"], B["vals"], 0, 1)
                if r >= CHAIN_RATIO:
                    nxt[i].append(j)
                    prv[j].append(i)
        dates: dict[int, set] = {i: set(n["anchors"]) for i, n in enumerate(nodes)}
        how = {i: ("錨點" if n["anchors"] else None) for i, n in enumerate(nodes)}

        def propagate():
            q = deque(i for i in dates if dates[i])
            seen = set()
            while q:
                i = q.popleft()
                if i in seen or len(dates[i]) != 1:
                    continue
                seen.add(i)
                d0 = next(iter(dates[i]))
                for j in nxt[i]:
                    cand = step_td(d0, 1)
                    if cand not in dates[j]:
                        dates[j].add(cand)
                        how[j] = how[j] or "鏈結"
                        q.append(j)
                for j in prv[i]:
                    cand = step_td(d0, -1)
                    if cand not in dates[j]:
                        dates[j].add(cand)
                        how[j] = how[j] or "鏈結"
                        q.append(j)
        propagate()
        # ③ 慣例（只給①②都推不到的節點）
        for i, n in enumerate(nodes):
            if dates[i]:
                continue
            h, ct, k = n["first"]
            t = datetime.fromtimestamp(ct, TW)
            if t.strftime("%Y%m%d") == k and t.hour < 18:
                dates[i].add(step_td(k, -1))
                how[i] = "慣例"
        propagate()
        # 收結果
        by_day: dict[str, list[int]] = {}
        for i in range(len(nodes)):
            if len(dates[i]) == 1:
                by_day.setdefault(next(iter(dates[i])), []).append(i)
            elif len(dates[i]) > 1:
                report["conflicts"].append(f"{side} 節點首見 {nodes[i]['first'][0]}/{nodes[i]['first'][2]} 推出多個日期 {sorted(dates[i])}")
        out_side, src_side = {}, {}
        for d8, idxs in sorted(by_day.items()):
            if len(idxs) > 1:
                report["conflicts"].append(f"{side} {d8} 有 {len(idxs)} 個不同快照（首見 "
                                           f"{[nodes[i]['first'][0] for i in idxs]}），不寫")
                continue
            n = nodes[idxs[0]]
            out_side[d8] = {c: list(v) for c, v in n["vals"].items()}
            src_side[d8] = f"git:{n['first'][0]}"
            report["nodes"].setdefault(side, []).append(
                f"{d8} {len(n['vals'])} 檔 首見 {n['first'][0]}（鍵 {n['first'][2]}）{how[idxs[0]]}")
        unk = [nodes[i]["first"] for i in range(len(nodes)) if not dates[i]]
        if unk:
            report["conflicts"].append(f"{side} {len(unk)} 個節點推不出日期：{[(h, k) for h, _, k in unk]}")
        result[side] = (out_side, src_side)

    for side in ("twse", "tpex"):
        print(f"\n== {side} ==")
        for line in report["nodes"].get(side, []):
            print("  " + line)
        days = sorted(result[side][0])
        if days:
            d, miss = days[0], []
            while d < days[-1]:
                d = step_td(d, 1)
                if d not in result[side][0]:
                    miss.append(d)
            print(f"  區間 {days[0]}～{days[-1]} 共 {len(days)} 天；缺交易日 {miss or '無'}")
    print("\n衝突／推不出：" + ("無" if not report["conflicts"] else ""))
    for c in report["conflicts"]:
        print("  ! " + c)

    # 對照現行 series：現行有 data_dates 的鍵，數值必須與重建表一致（自我檢查）
    bad = 0
    for k, sides in (cur.get("data_dates") or {}).items():
        for side, d8 in (sides or {}).items():
            if not d8 or d8 not in result[side][0]:
                continue
            tab = result[side][0][d8]
            codes = [c for c, b in cur["series"].items() if k in b and c in tab]
            diff = sum(1 for c in codes if cur["series"][c][k] != tab[c])
            if codes and diff / len(codes) > 0.02:
                bad += 1
                print(f"  ! 自我檢查：現行鍵 {k} {side}（資料日 {d8}）與重建表 {diff}/{len(codes)} 檔不同")
    print(f"自我檢查（現行 data_dates 鍵 vs 重建表）：{'通過' if not bad else f'{bad} 處不一致'}")
    if bad or dry:
        print("（dry-run 或自我檢查不過：不寫檔）")
        return 1 if bad else 0

    bdd = cur.get("by_data_date") or {}
    bsrc = cur.get("by_data_date_src") or {}
    added = 0
    for side, (tab, src) in result.items():
        s_days = bdd.setdefault(side, {})
        for d8, rows in tab.items():
            day = s_days.setdefault(d8, {})
            # 歷史較早：重建值先放，現行（live）已存的代號不覆寫；兩邊都有的以既有為準（先到先存）
            for c, v in rows.items():
                if c not in day:
                    day[c] = v
                    added += 1
            bsrc.setdefault(side, {}).setdefault(d8, src[d8])
    cur["by_data_date"] = {s: dict(sorted(v.items())) for s, v in sorted(bdd.items())}
    cur["by_data_date_src"] = {s: dict(sorted(v.items())) for s, v in sorted(bsrc.items())}
    cur_path.write_text(json.dumps(cur, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已寫入 {REL}：by_data_date 新增 {added} 筆；檔案 {cur_path.stat().st_size / 1e6:.2f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
