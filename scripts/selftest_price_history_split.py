# -*- coding: utf-8 -*-
"""先.八十二-1（2026-10-13）：price_history 拆檔前後讀出結果完全相同的比對自測。
① 拆檔資料夾讀回＝原單檔（json 序列化逐位元組相同，含代號順序與 meta）
② 每個分桶檔 <20MB  ③ 指定代號只讀部分分桶，結果＝全讀後取子集
④ 拆檔→再存→再讀仍相同（寫入冪等）  ⑤ 舊單檔路徑（自測暫存檔）照舊讀寫單檔
用法：python scripts/selftest_price_history_split.py [單檔來源]
  沒給來源時：repo 已拆檔就用拆檔資料夾當來源（先合成單檔再比對），否則用 data/price_history.json。
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import price_history_store as S  # noqa: E402

QUICK = "--quick" in sys.argv  # 先.八十一-58：冒煙用快速版（300 檔子集來回＋實際分桶大小）；完整 2,960 檔比對在拆檔時已做過
args = [a for a in sys.argv[1:] if a != "--quick"]
src = Path(args[0]) if args else S.CANONICAL
if QUICK:
    head = json.loads((S.split_dir(src) / "_meta.json").read_text(encoding="utf-8")) if not src.exists() else None
    order = (head or {}).get("code_order") or list((S.load(src).get("prices") or {}).keys())
    pick = order[::max(1, len(order) // 300)][:300] + ["2330", "0050", "00646", "00697B"]
    orig = S.load(src, codes=pick)
else:
    orig = S.load(src)  # 單檔存在讀單檔，否則讀拆檔
ser = lambda d: json.dumps(d, ensure_ascii=False, sort_keys=False)
tmp = Path(tempfile.mkdtemp())
res = []
try:
    one = tmp / "single" / "price_history.json"
    one.parent.mkdir()
    one.write_text(json.dumps(orig, ensure_ascii=False, indent=2), encoding="utf-8")
    logical = tmp / "split" / "price_history.json"
    logical.parent.mkdir()
    sizes = S.save(json.loads(one.read_text(encoding="utf-8")), logical, split=True)
    back = S.load(logical)
    res.append((f"①拆檔讀回＝原單檔（{len(orig.get('prices', {}))} 檔）", ser(back) == ser(orig)))
    if QUICK and not src.exists():  # 快速版：大小看 repo 裡實際的分桶檔
        sizes = {f.name: f.stat().st_size for f in S.split_dir(src).glob("*.json")}
    big = {k: v for k, v in sizes.items() if v >= 20 * 1024 * 1024}
    mx = max(sizes.items(), key=lambda kv: kv[1])
    res.append((f"②每檔 <20MB（最大 {mx[0]} {mx[1] / 1048576:.1f}MB，合計 {sum(sizes.values()) / 1048576:.1f}MB；原單檔 {one.stat().st_size / 1048576:.1f}MB）", not big))
    codes = ["2330", "0050", "00646", "00697B", "9999999"]
    part = S.load(logical, codes=codes)
    want = {c: orig["prices"][c] for c in orig["prices"] if c in codes}
    res.append(("③指定代號只讀部分分桶＝子集", part["prices"] == want and list(part["prices"]) == list(want)
                and part.get("meta") == orig.get("meta")))
    S.save(back, logical, split=True)
    res.append(("④再存再讀仍相同", ser(S.load(logical)) == ser(orig)))
    t2 = tmp / "t2.json"
    S.save({"meta": {"x": 1}, "prices": {"1101": [{"date": "2026-01-02", "close": 1.0}]}}, t2)
    res.append(("⑤非正式路徑照舊寫單檔、讀得回", t2.exists() and not (tmp / "t2").exists()
                and S.load(t2)["prices"]["1101"][0]["close"] == 1.0))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
