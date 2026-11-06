"""先.一三五-1mb 自測：半年報列標 period＝H1／H2，App 與稽核的近四季 EPS 改用「下半年＋今年 Q1＋Q2」。
零外部請求：只讀本機 data/stock_detail.json（記憶體內標記，不寫回）。
檢查：① 2249 標記後 TTM＝4.95＋4.01＋1.33（App 與稽核兩邊）② 一般連續四季（2330）結果與改版前相同
③ 半年報但今年沒有 Q1（2758 型）照舊回 null ④ 沒有 period 標記時照舊回 null（不靠結構猜）。"""
import copy, importlib.util, json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("usf", ROOT / ".github/scripts/update_stock_financials.py")
usf = importlib.util.module_from_spec(spec); spec.loader.exec_module(usf)

raw = json.loads((ROOT / "data/stock_detail.json").read_text(encoding="utf-8"))["stocks"]
codes = ["2249", "2330", "2758", "6898"]
tagged = copy.deepcopy({c: raw[c] for c in codes})
st = usf.tag_half_year_periods(tagged)
fails = []
def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)

q2249 = tagged["2249"]["financials"]["quarters"]
ok([(q["year"], q["quarter"], q.get("period")) for q in q2249][-4:] ==
   [(2025, 2, "H1"), (2025, 4, "H2"), (2026, 1, None), (2026, 2, None)], "2249 標記 2025Q2=H1、2025Q4=H2、2026Q1/Q2 不標")
ok([q["eps"] for q in q2249] == [q["eps"] for q in raw["2249"]["financials"]["quarters"]], "2249 數值未改")
ok(not any(q.get("period") for q in tagged["2330"]["financials"]["quarters"]), "2330 一般公司不標")

# App 端：從 app-picks.js 抽出 epsTtmFromDetail 用 node 跑
js = (ROOT / "app-picks.js").read_text(encoding="utf-8")
i = js.index("  function epsTtmFromDetail(")
j = js.index("\n  }\n", i) + 4
fn = js[i:j]
cases = {"2249": tagged["2249"], "6898": tagged["6898"], "2330": tagged["2330"], "2758": tagged["2758"],
         "2249_untagged": raw["2249"]}
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
ok(res["2758"] is None, "App 2758（今年沒有 Q1）照舊 null")
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
        ok(gaps == ["2758"], "稽核標記後只剩 2758 列 e_quarters_gap")
    else:
        ok(gaps == ["2249", "2758", "6898"], "稽核未標記時與改版前相同（2249／2758／6898 列 gap）")

print("自測", "全部通過" if not fails else f"失敗 {len(fails)} 項")
sys.exit(1 if fails else 0)
