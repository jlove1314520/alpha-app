"""自測：產業金流地圖聚合 `scripts/build_sector_flow.py`（先.一三五-1db）。

`D`／`OUT`／`ROOT` 換成暫存目錄：零外部請求、不讀也不動真實 data/ 與 PENDING_QUEUE.md。
市場頁「產業金流」卡唯一來源，這裡確認：
- 5／20 日外資／投信／自營／合計加總與手算一致；合計＝外資＋投信＋自營（即自營＝三大法人−外資−投信）；
- 估算金額＝張×1000×收盤；覆蓋不足的零星日期剔除；ETF 不進產業；不在名冊的代號不輸出；
- 外資缺值日記 missing_days、不當 0；法人 20 日加權均價；
- 逆勢買超：加權跌>1%、產業跌>0.5%、≥前 20 日日均 1.5 倍或 ≥3 億，邊界與大盤日期不符不判；
- 四份輸入任一讀不到／損壞／是空的 → 不覆寫既有 sector_flow.json、不拋未處理例外；
- 倒數區塊只改標記之間，標記外的位元組（含 CRLF 行尾）原封不動；沒有標記或佇列檔不存在不出錯。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("build_sector_flow", ROOT / "scripts" / "build_sector_flow.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
B.PHS._read.__defaults__ = (1,)  # 損壞情境不要重試 5 次空等

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def close(a, b, tol=0.01):
    return a is not None and abs(a - b) <= tol


def run(d: Path):
    B.D = d
    B.OUT = d / "sector_flow.json"
    B.ROOT = d
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


N = 25
DATES = [f"202610{i + 1:02d}" for i in range(N)]
ISO = [f"{x[:4]}-{x[4:6]}-{x[6:]}" for x in DATES]
SPARSE = "20260930"  # 只有 1 檔的零星殘留日 → 要被剔除


def flat(prior, last):
    """前 24 天 prior、最後一天 last，各為 [外資, 投信, 自營]。"""
    return {d: (list(last) if i == N - 1 else list(prior)) for i, d in enumerate(DATES)}


def px(last_ratio, base=100.0):
    return [{"date": ISO[i], "close": base * (last_ratio if i == N - 1 else 1.0)} for i in range(N)]


SER = {
    # 半導體 4 檔，最後一天全部 −1%
    "2330": flat([10, 5, -3], [30, 5, -3]),     # 前 24 天合計 12、末日 32 → 32×99/(12×100)=2.64 倍 → 個股條件成立
    "2303": flat([-5, 0, 0], [-5, 0, 0]),       # 賣超 → 不成立
    "2454": flat([1000, 1000, 1000], [4000, 0, 0]),  # 日均 3 億、末日 3.96 億：1.32 倍未達、但 ≥3 億 → 成立
    "3711": flat([1, 1, 1], [4, 0, 0]),         # 1.32 倍、金額小 → 不成立
    # 航運 3 檔，最後一天 +1%（產業漲 → 即使個股大買也不判）
    "2603": flat([1, 1, 1], [10000, 0, 0]),
    "2609": flat([1, 0, 0], [1, 0, 0]),
    "2615": flat([1, 0, 0], [1, 0, 0]),
    # 上櫃：最後 2 天外資缺值
    "5483": {d: ([None, 2, 1] if i >= N - 2 else [3, 2, 1]) for i, d in enumerate(DATES)},
    # ETF 與已下市
    "0050": flat([100, 0, 0], [100, 0, 0]),
    "9999": flat([1, 1, 1], [1, 1, 1]),
}
SER["2330"][SPARSE] = [999, 999, 999]

PRICES = {c: px(0.99) for c in ("2330", "2303", "2454", "3711")}
PRICES.update({c: px(1.01) for c in ("2603", "2609", "2615")})
PRICES["5483"] = px(1.0, 50.0)
PRICES["0050"] = px(1.0, 150.0)
PRICES["9999"] = px(1.0)

IND = {"2330": "半導體業", "2303": "半導體業", "2454": "半導體業", "3711": "半導體業",
       "2603": "航運業", "2609": "航運業", "2615": "航運業", "5483": "其他業", "0050": "ETF", "9999": "半導體業"}

CD_BLOCK_OLD = "<!-- FLOW_COUNTDOWN_BEGIN -->\n- [!] 舊倒數\n<!-- FLOW_COUNTDOWN_END -->"


def write_inputs(d: Path, taiex_date=ISO[-1], taiex_chg=-1.5, skip=(), corrupt=(), empty=()):
    docs = {
        "institutional_history.json": {"dates": [SPARSE] + DATES, "series": SER},
        "company_info.json": {"companies": {c: {"name": f"名{c}", "industry": v} for c, v in IND.items()}},
        "listed_universe.json": {"active": [c for c in IND if c != "9999"]},
        "price_history.json": {"meta": {}, "prices": PRICES},
        "market_tw.json": {"taiex": {"data_date": taiex_date, "change_pct": taiex_chg}},
    }
    blank = {"institutional_history.json": {"dates": [], "series": {}}, "company_info.json": {"companies": {}},
             "listed_universe.json": {"active": []}, "price_history.json": {"meta": {}, "prices": {}}}
    for name, doc in docs.items():
        if name in skip:
            continue
        p = d / name
        if name in corrupt:
            p.write_text('{"x": [', encoding="utf-8")
        else:
            p.write_text(json.dumps(blank[name] if name in empty else doc, ensure_ascii=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：正常聚合")
    d1 = base / "main"
    d1.mkdir()
    write_inputs(d1)
    q1 = "# 佇列\n前文 A\n" + CD_BLOCK_OLD + "\n後文 B\n"
    (d1 / "PENDING_QUEUE.md").write_bytes(q1.encode("utf-8"))
    rc, err = run(d1)
    check("main 回 0、無例外", rc == 0 and err is None, (rc, err))
    doc = json.loads((d1 / "sector_flow.json").read_text(encoding="utf-8"))
    m, S, SEC = doc["meta"], doc["stocks"], doc["sectors"]
    check("零星殘留日剔除：25 個交易日、剔除 1 天", m["trading_days_available"] == 25 and m["dates_dropped_low_coverage"] == 1, m)
    check("可用視窗 [1,5,20]、60 日還差 35 天", m["windows_usable"] == [1, 5, 20] and m["windows_missing_days"] == {"60": 35}, m)
    s = S["2330"]
    n5, n20 = s["net_5d"], s["net_20d"]
    check("2330 5 日外資＝4×10+30＝70", n5["foreign_lots"] == 70, n5)
    check("2330 5 日投信 25、自營 −15", n5["trust_lots"] == 25 and n5["dealer_lots"] == -15, n5)
    check("2330 5 日合計＝80（沒算進剔除日的 999）", n5["total_lots"] == 80, n5)
    check("2330 20 日合計＝19×12+32＝260", n20["total_lots"] == 260, n20)
    check("估算金額＝張×1000×最新收盤 99", n5["est_amount"] == 80 * 1000 * 99 and n20["est_amount"] == 260 * 99000, (n5, n20))
    bad = [c for c, e in S.items() for w in (1, 5, 20)
           if e[f"net_{w}d"].get("missing_days") is None
           and abs(e[f"net_{w}d"]["total_lots"] - e[f"net_{w}d"]["foreign_lots"] - e[f"net_{w}d"]["trust_lots"]
                   - e[f"net_{w}d"]["dealer_lots"]) > 1e-6]
    check("自營＝合計−外資−投信（所有完整視窗）", not bad, bad)
    check("已下市 9999 不輸出", "9999" not in S)
    check("ETF 不進產業：排除 1 檔、sectors 無 ETF", m["non_industry_excluded"] == 1 and "ETF" not in SEC, (m["non_industry_excluded"], list(SEC)))
    semi = SEC.get("半導體業") or {}
    exp5 = 80 + (-25) + (4 * 3000 + 4000) + (4 * 3 + 4)
    check("半導體 5 日合計張數手算一致", semi.get("net_5d_lots") == exp5, (semi.get("net_5d_lots"), exp5))
    check("半導體成分 4 檔（9999 不算）", semi.get("constituents") == 4, semi.get("constituents"))
    exp_amt = sum(S[c]["net_5d"]["est_amount"] for c in ("2330", "2303", "2454", "3711"))
    check("半導體 5 日估算金額＝成分股加總", semi.get("net_5d_est_amount") == exp_amt)
    check("半導體當日等權漲跌 −1%（4 檔）", semi.get("day_return_pct") == -1.0 and semi.get("day_return_n") == 4, semi.get("day_return_pct"))
    check("航運當日 +1%", (SEC.get("航運業") or {}).get("day_return_pct") == 1.0)
    check("其他業只 1 檔 → 不算產業漲跌", "day_return_pct" not in (SEC.get("其他業") or {}))
    check("流入榜依估算金額排序：2454 第一", (semi.get("top_inflow") or [{}])[0].get("code") == "2454", semi.get("top_inflow"))
    k = S["5483"]
    check("5483 外資缺值 2 天：5 日 missing_days＝2", k["net_5d"].get("missing_days") == 2, k["net_5d"])
    check("5483 5 日合計只加完整的 3 天＝18", k["net_5d"]["total_lots"] == 18, k["net_5d"])
    check("5483 foreign_missing_days＝2、外資連續天數 0", k.get("foreign_missing_days") == 2 and k["streak_days"]["foreign"] == 0, k)
    check("5483 外資投信同向因缺值不判", k["foreign_trust_aligned"] is False)
    ap = s.get("inst_avg_price_20d") or {}
    exp_ap = (19 * 12 * 100 + 32 * 99) / 260
    check("2330 法人 20 日加權均價手算一致", close(ap.get("price"), exp_ap) and ap.get("buy_days") == 20, (ap, exp_ap))
    check("2330 現價對均價", close(ap.get("vs_close_pct"), (99 / exp_ap - 1) * 100), ap)
    check("2303 全賣超 → 無均價", "inst_avg_price_20d" not in S["2303"])
    check("2330 逆勢買超（2.64 倍）", S["2330"].get("contrarian_buy") is True, S["2330"].get("contrarian_detail"))
    check("2454 逆勢買超（1.32 倍但 ≥3 億）", S["2454"].get("contrarian_buy") is True)
    check("3711 未達 1.5 倍、未達 3 億 → 否", S["3711"].get("contrarian_buy") is False)
    check("2303 賣超 → 否", S["2303"].get("contrarian_buy") is False)
    check("2603 大買但產業上漲 → 否", S["2603"].get("contrarian_buy") is False)
    check("ETF 0050 不判逆勢", "contrarian_buy" not in S["0050"])
    check("contrarian_count＝2、無 _contra 殘留", m["contrarian_count"] == 2 and not any("_contra" in e for e in S.values()), m["contrarian_count"])
    q_after = (d1 / "PENDING_QUEUE.md").read_bytes().decode("utf-8")
    check("倒數區塊已改寫（35 個交易日）", "60 日視窗還需 35 個交易日" in q_after and "舊倒數" not in q_after)
    check("倒數區塊外文字不動", q_after.startswith("# 佇列\n前文 A\n<!-- FLOW_COUNTDOWN_BEGIN -->")
          and q_after.endswith("<!-- FLOW_COUNTDOWN_END -->\n後文 B\n"))

    print("情境二：大盤條件")
    for label, kw in (("加權只跌 0.9% → 全不亮", {"taiex_chg": -0.9}),
                      ("加權正好 −1.0%（未超過）→ 全不亮", {"taiex_chg": -1.0})):
        dd = base / f"tx{abs(kw['taiex_chg'])}"
        dd.mkdir()
        write_inputs(dd, **kw)
        run(dd)
        o = json.loads((dd / "sector_flow.json").read_text(encoding="utf-8"))
        check(label, o["meta"]["contrarian_count"] == 0 and o["stocks"]["2330"].get("contrarian_buy") is False)
    dd = base / "txdate"
    dd.mkdir()
    write_inputs(dd, taiex_date=ISO[-2])
    run(dd)
    o = json.loads((dd / "sector_flow.json").read_text(encoding="utf-8"))
    check("加權資料日≠法人最新日 → 不判、寫 note",
          o["meta"]["contrarian_taiex_change_pct"] is None and o["meta"]["contrarian_note"]
          and not any("contrarian_buy" in e for e in o["stocks"].values()))

    print("情境三：輸入讀不到／損壞／是空的 → 不覆寫既有輸出")
    GOOD = '{"meta":{"date":"20261024"},"sectors":{"舊":{}},"stocks":{}}'
    INPUTS = ("institutional_history.json", "company_info.json", "listed_universe.json", "price_history.json")
    for name in INPUTS:
        for mode in ("skip", "corrupt", "empty"):
            dd = base / f"{name}_{mode}"
            dd.mkdir()
            write_inputs(dd, **{mode: (name,)})
            (dd / "sector_flow.json").write_text(GOOD, encoding="utf-8")
            (dd / "PENDING_QUEUE.md").write_bytes(q1.encode("utf-8"))
            rc, err = run(dd)
            kept = (dd / "sector_flow.json").read_text(encoding="utf-8") == GOOD
            q_kept = (dd / "PENDING_QUEUE.md").read_bytes() == q1.encode("utf-8")
            check(f"{name} {mode}：無例外、非 0、不覆寫、佇列不動",
                  err is None and rc not in (0, None) and kept and q_kept, (rc, err, kept, q_kept))

    print("情境四：倒數區塊行尾與邊界")
    crlf = ("# 佇列\r\n前文\r\n" + CD_BLOCK_OLD.replace("\n", "\r\n") + "\r\n後文\r\n").encode("utf-8")
    dd = base / "crlf"
    dd.mkdir()
    (dd / "PENDING_QUEUE.md").write_bytes(crlf)
    B.ROOT = dd
    B._update_queue_countdown(25, DATES, {"60": 35}, [1, 5, 20])
    after = (dd / "PENDING_QUEUE.md").read_bytes()
    bi = crlf.index(b"<!-- FLOW_COUNTDOWN_BEGIN -->")
    ei = crlf.index(b"<!-- FLOW_COUNTDOWN_END -->")
    check("CRLF 檔：BEGIN 以前位元組不變", after[:bi] == crlf[:bi])
    check("CRLF 檔：END 以後位元組不變（含 \\r\\n）", after.endswith(crlf[ei:]))
    check("CRLF 檔：區塊內不留裸 \\n（行尾跟檔案一致）",
          b"\n" not in after[bi:after.index(b"<!-- FLOW_COUNTDOWN_END -->")].replace(b"\r\n", b""))
    nomark = "# 佇列\n沒有標記\n".encode("utf-8")
    (dd / "PENDING_QUEUE.md").write_bytes(nomark)
    B._update_queue_countdown(25, DATES, {"60": 35}, [1, 5, 20])
    check("沒有標記 → 原封不動", (dd / "PENDING_QUEUE.md").read_bytes() == nomark)
    (dd / "PENDING_QUEUE.md").unlink()
    try:
        B._update_queue_countdown(25, DATES, {"60": 35}, [1, 5, 20])
        check("佇列檔不存在 → 不拋例外、不新建", not (dd / "PENDING_QUEUE.md").exists())
    except Exception as e:  # noqa: BLE001
        check("佇列檔不存在 → 不拋例外", False, e)
    (dd / "PENDING_QUEUE.md").write_bytes(nomark.replace("沒有標記".encode("utf-8"), CD_BLOCK_OLD.encode("utf-8")))
    B._update_queue_countdown(60, ["20260801"] + DATES, {}, [1, 5, 20, 60])
    t = (dd / "PENDING_QUEUE.md").read_bytes().decode("utf-8")
    check("視窗全足 → 改寫成「可以動工」", "視窗已足夠，可以動工" in t and "舊倒數" not in t)

print(f"\n{ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
