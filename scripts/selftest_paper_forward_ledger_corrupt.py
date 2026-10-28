# -*- coding: utf-8 -*-
"""自測：前向帳本「寫到一半的壞行」時的行為（先.一三五-1t 重現；先.一三八-6 改為 (b)＋(c) 規則，paper_10～18 共用模組 research/paper_forward_common.py）。

⚠️ 下面「檢查」1、3 是 先.一三五-1t 當時（修規則前）的描述，已過時；現行規則：
  A（最後一行半截、無結尾換行）→ 原檔備份後丟棄該行補跑、摘要 ledger_repairs；
  A2（最後一行壞但有結尾換行）／B（中間行壞）→ 停跑、帳本不動、last_error；
  C（整檔空白）→ 停跑、不重新建倉、last_error。

全部在暫存目錄、合成價格（3 檔虛構代號 × 10 個虛構交易日）與合成帳本上進行，不碰真實帳本／摘要，
**不印任何淨值或報酬**（只檢查例外類型、退出碼、檔案是否被改動、摘要有沒有 last_error 欄）。

三種壞帳本情境：
  A. 最後一行半截（_append 寫到一半被中斷）
  B. 中間一行壞
  C. 整檔空白（只有空白／換行）
檢查：
  1. 現況重現：A／B 的 step() 丟 ValueError（json.loads 失敗，實際是子類 JSONDecodeError）；C 不丟例外、被當成「尚未起跑」重新建倉（只記錄，不改）。
  2. run_main() 失敗時仍 exit 0（十二節），且把 last_error（類型＋訊息前 200 字）、last_error_at 寫進摘要檔；
     forward_sim_watch 會把它判成 ERROR。
  3. 帳本一個位元組都不動（不自動刪除或略過壞行——怎麼修帳本是判定規則，見提案 先.一三五-1t-a）。
  4. 帳本修好後再跑一次成功，摘要重寫、last_error 消失。
  5. 寫摘要本身失敗（摘要路徑是目錄）時只印警告、仍 exit 0。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_forward_common as C  # noqa: E402
import forward_sim_watch as W  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


DAYS = [f"2030-01-{d:02d}" for d in range(2, 12)]
CODES = ["9801", "9802", "9803"]          # 虛構代號
PRICES = {c: [{"date": d, "close": 10.0 + i, "adj_close": 10.0 + i, "turnover": 1e8} for d in DAYS]
          for i, c in enumerate(CODES)}
px = C.Px(PRICES)
active = set(CODES)
td = Path(tempfile.mkdtemp(prefix="paper_fwd_corrupt_"))


def make_spec(name: str) -> C.Spec:
    return C.Spec(key=name, label="合成", note="合成", prereg="-", trial_no=None, start_not_before=DAYS[0],
                  judge_after="2031-01-01", mode="event", top_n=2, hold_days=3,
                  signal=lambda ctx, day, uni: [{"code": c} for c in sorted(uni)][:1],
                  log_path=td / f"{name}_log.jsonl", out_path=td / f"{name}.json")


def build_good(name: str) -> C.Spec:
    sp = make_spec(name)
    C.step(sp, {}, px=C.Px({c: rs[:6] for c, rs in PRICES.items()}), active=active)   # 先跑前 6 天，留 4 天給下一次
    return sp


try:
    base = build_good("base")
    good_bytes = base.log_path.read_bytes()
    good_lines = good_bytes.decode("utf-8").splitlines()
    check(len(good_lines) == 6, f"合成帳本建好 {len(good_lines)} 列（應 6）")

    C.LEDGER_BACKUP_DIR = td / "bak"          # 備份寫進暫存目錄，不碰 research/data
    NL = chr(10)
    cases = {
        "A_last_half": NL.join(good_lines[:-1] + [good_lines[-1][: len(good_lines[-1]) // 2]]),
        "A2_last_bad_with_newline": NL.join(good_lines[:-1] + [good_lines[-1][:20]]) + NL,
        "B_middle_bad": NL.join(good_lines[:2] + [good_lines[2][:15]] + good_lines[3:]) + NL,
        "C_blank": NL + " " + NL + NL,
    }
    for name, text in cases.items():
        sp = make_spec(name)
        sp.log_path.write_text(text, encoding="utf-8", newline="")
        before = sp.log_path.read_bytes()
        if name == "A_last_half":
            # (b) 最後一行半截且無結尾換行 → 備份原檔、丟棄該行、照常補跑
            sp.out_path.write_text(json.dumps({"label": "舊摘要"}), encoding="utf-8")
            rc = C.run_main(lambda sp=sp: C.step(sp, {}, px=px, active=active), "合成", sp.out_path)
            baks = sorted((td / "bak").glob(sp.log_path.name + ".corrupt-*"))
            check(rc == 0 and len(baks) == 1 and baks[0].read_bytes() == before, f"{name}：原檔整份備份（位元組相同）")
            rows = [json.loads(l) for l in sp.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            check([r["date"] for r in rows] == DAYS, f"{name}：丟棄半截行後補跑，帳本 {len(rows)} 列日期連續（應 {len(DAYS)}）")
            check(rows[4] == json.loads(good_lines[4]), f"{name}：半截行之前的有效列原封不動")
            doc = json.loads(sp.out_path.read_text(encoding="utf-8"))
            check("last_error" not in doc and (doc.get("ledger_repairs") or {}).get("backups") == [baks[0].name],
                  f"{name}：摘要寫明 ledger_repairs、沒有 last_error")
            continue
        err = None
        try:
            C.step(sp, {}, px=px, active=active)
        except Exception as e:  # noqa: BLE001
            err = e
        if name == "C_blank":
            check(isinstance(err, RuntimeError), f"{name}：(c) 帳本存在但無有效列 → 停跑（{type(err).__name__}），不重新建倉")
        else:
            check(isinstance(err, ValueError), f"{name}：非最後一行半截 → 照舊停跑（{type(err).__name__}）")
        check(sp.log_path.read_bytes() == before, f"{name}：帳本一個位元組都沒被改")
        check(not list((td / "bak").glob(sp.log_path.name + ".corrupt-*")), f"{name}：沒有產生備份（只有 (b) 會動帳本）")
        # 失敗看得見
        sp.out_path.write_text(json.dumps({"label": "舊摘要", "generated_at": "2030-01-01T00:00:00+08:00"}), encoding="utf-8")
        rc = C.run_main(lambda sp=sp: C.step(sp, {}, px=px, active=active), "合成", sp.out_path)
        doc = json.loads(sp.out_path.read_text(encoding="utf-8"))
        check(rc == 0, f"{name}：run_main 仍 exit 0（十二節）")
        le = doc.get("last_error")
        check(isinstance(le, str) and le.split(":")[0] in ("ValueError", "RuntimeError") and len(le) <= len(le.split(":")[0]) + 2 + 200,
              f"{name}：摘要有 last_error（類型＋訊息前 200 字）")
        check(bool(doc.get("last_error_at")) and doc.get("label") == "舊摘要", f"{name}：有 last_error_at，且保留舊摘要其他欄位")
        row = W.check_one(sp.out_path, W.date(2030, 1, 3), set())
        check(row.get("status") == "ERROR", f"{name}：forward_sim_watch 判 ERROR（實際 {row.get('status')}）")
        check(sp.log_path.read_bytes() == before, f"{name}：run_main 後帳本仍未被改")
        # 修好後再跑成功、last_error 消失
        sp.log_path.write_bytes(good_bytes)
        rc = C.run_main(lambda sp=sp: C.step(sp, {}, px=px, active=active), "合成", sp.out_path)
        doc = json.loads(sp.out_path.read_text(encoding="utf-8"))
        check(rc == 0 and "last_error" not in doc and doc.get("label") == "合成", f"{name}：帳本修好後重跑成功、last_error 消失")

    # 檔案不存在 → 視為尚未起跑（不是 (c)）
    sp = make_spec("E_missing")
    check(C.read_log(sp) == [], "E：帳本檔不存在 → []（尚未起跑，不是 (c)）")

    # 5. 寫摘要本身失敗也不中斷
    sp = make_spec("D_out_is_dir")
    sp.log_path.write_text(cases["B_middle_bad"], encoding="utf-8")
    sp.out_path.mkdir()
    rc = C.run_main(lambda: C.step(sp, {}, px=px, active=active), "合成", sp.out_path)
    check(rc == 0, "D：摘要寫不進去（路徑是目錄）仍 exit 0、只印警告")
finally:
    shutil.rmtree(td, ignore_errors=True)

print(f"\n{'全部通過' if not fails else f'{len(fails)} 項失敗'}")
sys.exit(1 if fails else 0)
