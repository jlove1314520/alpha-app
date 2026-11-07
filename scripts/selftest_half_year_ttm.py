"""先.一三五-1mb 自測：半年報列標 period＝H1／H2，App 與稽核的近四季 EPS 改用「下半年＋今年 Q1＋Q2」。
零外部請求：只讀本機 data/stock_detail.json（記憶體內標記，不寫回）。
檢查：① 2249 標記後 TTM＝4.95＋4.01＋1.33（App 與稽核兩邊）② 一般連續四季（2330）結果與改版前相同
③ 沒有 period 標記時照舊回 null（不靠結構猜）。
先.一三五-1me 追加：④ 仍是半年報、今年只有 Q2（2758 型）→ TTM＝去年 H2＋今年 H1（2758＝1.25＋0.33；1.25＝全年 2.29−上半年 1.04，先.一三五-1ms，證據 prior_year_half）
⑤ 2760／6565／6812／7752／6911 以月營收證明（period_basis=month_revenue）⑥ 月營收對不上（改成單季量級）就不標。"""
import copy, importlib.util, json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("usf", ROOT / ".github/scripts/update_stock_financials.py")
usf = importlib.util.module_from_spec(spec); spec.loader.exec_module(usf)

raw = json.loads((ROOT / "data/stock_detail.json").read_text(encoding="utf-8"))["stocks"]
# 先.一三五-1mk：每日管線已把 period 標記寫進正式檔，「未標記」對照組要先剝掉標記，不能直接拿原檔
for _c in ["2249", "2330", "2758", "6898", "2760", "6565", "6812", "7752", "6911"]:
    for _q in ((raw.get(_c) or {}).get("financials") or {}).get("quarters") or []:
        _q.pop("period", None); _q.pop("period_basis", None)
codes = ["2249", "2330", "2758", "6898", "2760", "6565", "6812", "7752", "6911"]
ME = ["2760", "6565", "6812", "7752", "6911"]
mrev = usf.load_month_revenue_map()
tagged = copy.deepcopy({c: raw[c] for c in codes})
st = usf.tag_half_year_periods(tagged, mrev)
fails = []
def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)

q2249 = tagged["2249"]["financials"]["quarters"]
ok([(q["year"], q["quarter"], q.get("period")) for q in q2249][-4:] ==
   [(2025, 2, "H1"), (2025, 4, "H2"), (2026, 1, None), (2026, 2, None)], "2249 標記 2025Q2=H1、2025Q4=H2、2026Q1/Q2 不標")
ok([q["eps"] for q in q2249] == [q["eps"] for q in raw["2249"]["financials"]["quarters"]], "2249 數值未改")
ok(not any(q.get("period") for q in tagged["2330"]["financials"]["quarters"]), "2330 一般公司不標")
q2758 = tagged["2758"]["financials"]["quarters"][-2:]
ok([(q["year"], q["quarter"], q.get("period"), q.get("period_basis")) for q in q2758] ==
   [(2025, 4, "H2", "q2_q4_pair"), (2026, 2, "H1", "prior_year_half")], "2758 2026Q2 標 H1（prior_year_half，本機無 2026 月營收）")
for c in ME:
    t = tagged[c]["financials"]["quarters"][-2:]
    ok([(q["year"], q["quarter"], q.get("period")) for q in t] == [(2025, 4, "H2"), (2026, 2, "H1")]
       and t[1].get("period_basis") == "month_revenue", f"{c} 2025Q4=H2、2026Q2=H1（2026Q2 以月營收證明）")
q6911 = tagged["6911"]["financials"]["quarters"]
ok([q.get("period") for q in q6911 if q["year"] == 2025] == [None, None, "H2"] and q6911[-2].get("period_basis") == "month_revenue",
   "6911 2025Q1/Q2 單季不標、2025Q4 以月營收證明為 H2")
# 反例：把 7752 的 2026 月營收改成「Q2 營收＝4～6 月單季加總」→ 不得標 H1
neg = copy.deepcopy({"7752": raw["7752"]})
mneg = {"7752": dict(mrev["7752"])}
rv = neg["7752"]["financials"]["quarters"][-1]["revenue"]
for m in range(1, 7):
    mneg["7752"][(2026, m)] = rv / 3
usf.tag_half_year_periods(neg, mneg)
ok(neg["7752"]["financials"]["quarters"][-1].get("period") is None, "反例：月營收顯示是單季時 7752 2026Q2 不標")
neg2 = copy.deepcopy({"7752": raw["7752"]})
usf.tag_half_year_periods(neg2, {})
ok(neg2["7752"]["financials"]["quarters"][-1].get("period_basis") == "prior_year_half", "沒有月營收時退回 prior_year_half")

# App 端：從 app-picks.js 抽出 epsTtmFromDetail 用 node 跑
js = (ROOT / "app-picks.js").read_text(encoding="utf-8")
i = js.index("  function epsTtmFromDetail(")
j = js.index("\n  }\n", i) + 4
fn = js[i:j]
cases = {"2249": tagged["2249"], "6898": tagged["6898"], "2330": tagged["2330"], "2758": tagged["2758"],
         "2249_untagged": raw["2249"], "2758_untagged": raw["2758"]}
cases.update({c: tagged[c] for c in ME})
node_src = ("const VALUATION_EPS_MAX_LAG_Q=4;function _qIndex(y,q){return y*4+q}"
            "function _currentQIndex(){return 2026*4+4}\n" + fn +
            "\nconst C=" + json.dumps(cases) + ";const out={};for(const k in C)out[k]=epsTtmFromDetail(C[k],0);"
            "console.log(JSON.stringify(out));")
res = json.loads(subprocess.run(["node", "-e", node_src], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
print("App:", res)
ok(res["2249"] and abs(res["2249"]["eps"] - (4.95 + 4.01 + 1.33)) < 1e-9 and res["2249"]["label"] == "2025下半年~2026Q2", "App 2249 TTM＝4.95＋4.01＋1.33")
ok(res["6898"] and abs(res["6898"]["eps"] - (2.64 + 1.27 + 1.53)) < 1e-9, "App 6898 TTM＝2.64＋1.27＋1.53")
q2330 = raw["2330"]["financials"]["quarters"][-4:]
ok(res["2330"] and abs(res["2330"]["eps"] - sum(q["eps"] for q in q2330)) < 1e-9, "App 2330 連續四季結果不變")
ok(res["2758"] and abs(res["2758"]["eps"] - (1.25 + 0.33)) < 1e-9 and res["2758"]["label"] == "2025下半年~2026上半年", "App 2758 TTM＝1.25＋0.33")
# 先.一三五-1ms：2025 H2 原存全年累計 2.29，已改成全年−上半年＝2.29−1.04＝1.25（fix_h2_cumulative_eps），期望值跟著改
ok(res["2758_untagged"] is None, "App 2758 沒有 period 標記照舊 null")
ok(abs(res["6911"]["eps"] - (0.39 + 0.43)) < 1e-9, "App 6911 TTM＝0.39＋0.43")
for c in ME:
    q = tagged[c]["financials"]["quarters"]
    ok(res[c] and abs(res[c]["eps"] - (q[-2]["eps"] + q[-1]["eps"])) < 1e-9, f"App {c} TTM＝去年 H2＋今年 H1")
ok(res["2249_untagged"] is None, "App 沒有 period 標記照舊 null")

# 稽核端
sys.path.insert(0, str(ROOT / "scripts"))
import data_audit as da
class A:
    def __init__(s): s.hits = []; s.notes = []
    def note(s, k, **kw): s.notes.append(k)
    def hit(s, k, code, *a): s.hits.append((k, code))
for label, src in (("tagged", tagged), ("untagged", {c: raw[c] for c in codes})):
    a = A()
    ref = {c: {"close": 100.0} for c in codes}
    loc = {"fundamentals": {c: {"ratios": {"per": 12.0}} for c in codes}, "stock_detail": src}
    da.check_e_pe(a, codes, ref, {}, loc)
    gaps = sorted(c for k, c in a.hits if k == "e_quarters_gap")
    print("稽核", label, "e_quarters_gap:", gaps)
    if label == "tagged":
        ok(gaps == [], "稽核標記後 9 檔都不列 e_quarters_gap")
    else:
        ok(gaps == ["2249", "2758", "2760", "6565", "6812", "6898", "6911", "7752"], "稽核未標記時與改版前相同（半年報 8 檔列 gap）")

# 先.一三五-1mk：離線路徑（--offline-merge-backfill）也要標半年報。拿掉標記的副本寫到暫存檔，跑完再比對（不動正式檔）
import tempfile
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td) / "stock_detail.json"
    full = json.loads((ROOT / "data/stock_detail.json").read_text(encoding="utf-8"))
    for c in codes:
        for q in full["stocks"][c]["financials"]["quarters"]:
            q.pop("period", None); q.pop("period_basis", None)
    tmp.write_text(json.dumps(full, ensure_ascii=False), encoding="utf-8")
    orig_out = usf.OUT_PATH
    usf.OUT_PATH = tmp
    try:
        usf.offline_merge_backfill()
    finally:
        usf.OUT_PATH = orig_out
    off = json.loads(tmp.read_text(encoding="utf-8"))
    hy = off["meta"].get("financials_half_year_period") or {}
    ok(hy.get("mode") == "offline" and "2249" in (hy.get("tagged_codes") or []), "離線路徑 meta 有 mode=offline 半年報紀錄")
    ok([(q["year"], q["quarter"], q.get("period")) for q in off["stocks"]["2249"]["financials"]["quarters"]][-4:] ==
       [(q["year"], q["quarter"], q.get("period")) for q in q2249][-4:], "離線路徑 2249 標記與每日路徑相同")
    ok(not any(q.get("period") for q in off["stocks"]["2330"]["financials"]["quarters"]), "離線路徑 2330 不標")

print("自測", "全部通過" if not fails else f"失敗 {len(fails)} 項")
sys.exit(1 if fails else 0)
