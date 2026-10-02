"""先.十-五.2／先.十一-一：產業缺貨方向「產業桶對照表」建置腳本（2026-10-02 總司令審定後已凍結；有 FROZEN.json 時拒絕重新產生）。

不讀任何價格、不計算任何報酬。輸出：
  docs/industry_shortage_mapping.csv      桶層級對照（A 中分類／C 貨品別／證交所產業別，各附依據與等級）
  docs/industry_shortage_stock_map.csv    個股→桶（確定性規則，來源為 TaiwanStockInfo 非 PIT 快照）
  docs/industry_shortage_mapping.md       說明＋每桶股票數＋SHA256
對應依據一律是官方分類名稱的字面或官方定義對應，不得依回測結果調整。
等級：A＝官方名稱字面相同或字面包含；B＝官方定義對應（名稱不同但涵蓋範圍可由官方分類定義確認）；
      C＝近似／弱對應（須 Cowork 特別審）。
"""
import csv
import hashlib
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
INFO = ROOT / "research" / "data" / "raw" / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet"

# bucket_id, 名稱, A 中分類(代碼:官方名), C 貨品別, 證交所產業別, 各依據與等級
BUCKETS = [
    dict(id="B01", name="電子零組件（含半導體）",
         a=[("26", "電子零組件製造業")], c=["電子產品"], t=["半導體業", "電子零組件業"],
         basis_a="證交所『電子零組件業』與主計總處『電子零組件製造業』字面相同；『半導體業』屬 TSIC 26 之子類（官方定義）",
         basis_c="C『電子產品』為電子零組件／積體電路為主之貨品別（官方貨品別名稱）",
         basis_t="電子零組件業＝字面對應；半導體業＝官方定義對應",
         ga="A", gc="B", gt="A,B", note=""),
    dict(id="B02", name="電腦通信光電（資通訊硬體）",
         a=[("27", "電腦、電子產品及光學製品製造業")], c=[], t=["電腦及週邊設備業", "通信網路業", "光電業"],
         basis_a="『電腦及週邊設備業』字面含於『電腦、電子產品及光學製品製造業』；通信網路屬 TSIC 27 通信傳播設備；光電業字面對應『光學製品』",
         basis_c="總司令 2026-10-02 審定：移除 S_C（『光學器材』為 C 級，對電腦通信不具代表性），B02 只用 S_A",
         basis_t="電腦及週邊設備業＝字面；通信網路業＝官方定義；光電業＝字面（弱）",
         ga="A,B", gc="-", gt="A,B,C",
         note="僅有 S_A（總司令 2026-10-02 審定移除 S_C；資通類貨品別檔案取不到，光學器材代表性弱）"),
    dict(id="B03", name="電機設備（電力設備與電線電纜）",
         a=[("28", "電力設備及配備製造業")], c=["電機產品"], t=["電器電纜"],
         basis_a="『電器電纜』對應『電力設備及配備製造業』（TSIC 28 含電線及配線器材）",
         basis_c="C『電機產品』字面對應『電力設備』",
         basis_t="電器電纜為證交所產業別，字面含『電』，TSIC 定義對應",
         ga="B", gc="B", gt="B",
         note="證交所『電機機械』同時含電機與機械，依字面歸 B04，不拆分；B03 因此股票數偏少"),
    dict(id="B04", name="機械設備",
         a=[("29", "機械設備製造業")], c=["機械"], t=["電機機械"],
         basis_a="『電機機械』字面含『機械』；主計總處『機械設備製造業』",
         basis_c="C『機械』字面相同",
         basis_t="『電機機械』整類歸此桶（含重電等電機股，屬已知混雜）",
         ga="A", gc="A", gt="A",
         note="電機機械混有重電／電機股，與 B03 部分重疊但不重複計入"),
    dict(id="B05", name="基本金屬（鋼鐵）",
         a=[("24", "基本金屬製造業")], c=["基本金屬"], t=["鋼鐵工業"],
         basis_a="鋼鐵屬基本金屬（TSIC 24 含鋼鐵基本工業）",
         basis_c="C『基本金屬』字面相同",
         basis_t="鋼鐵工業＝官方定義對應；金屬製品製造業（TSIC 25）無對應證交所產業別，未使用",
         ga="B", gc="A", gt="B", note=""),
    dict(id="B06", name="運輸工具（汽車與其他運輸工具）",
         a=[("30", "汽車及其零件製造業"), ("31", "其他運輸工具及其零件製造業")], c=["運輸工具"], t=["汽車工業"],
         basis_a="『汽車工業』字面對應『汽車及其零件製造業』；機車、自行車屬 TSIC 31",
         basis_c="C『運輸工具』字面對應",
         basis_t="汽車工業＝字面；航運業屬運輸服務，非製造業，不納入",
         ga="A", gc="A", gt="A", note=""),
    dict(id="B07", name="塑橡膠製品",
         a=[("21", "橡膠製品製造業"), ("22", "塑膠製品製造業")], c=["塑橡膠製品"], t=["橡膠工業", "塑膠工業"],
         basis_a="『橡膠工業』『塑膠工業』字面對應『橡膠製品』『塑膠製品』",
         basis_c="C『塑橡膠製品』字面含兩者",
         basis_t="字面對應；證交所『塑膠工業』實質含塑膠原料（台塑系），與『塑膠製品』範圍不完全一致，屬已知偏差",
         ga="A", gc="A", gt="A", note=""),
    dict(id="B08", name="化學工業",
         a=[("17", "石油及煤製品製造業"), ("18", "化學材料及肥料製造業"), ("19", "其他化學製品製造業")],
         c=["化學品"], t=["化學工業"],
         basis_a="『化學工業』字面含於 17／18／19 之『化學』與主計總處『化學工業』大類（I3）；不含藥品、橡膠、塑膠（各有專屬桶）",
         basis_c="C『化學品』字面對應",
         basis_t="字面相同",
         ga="A,B", gc="A", gt="A", note=""),
    dict(id="B09", name="紡織成衣",
         a=[("11", "紡織業"), ("12", "成衣及服飾品製造業")], c=["紡織品"], t=["紡織纖維"],
         basis_a="『紡織纖維』字面對應『紡織業』；證交所『紡織纖維』含成衣廠，故併入 12",
         basis_c="C『紡織品』字面對應",
         basis_t="字面對應",
         ga="A,B", gc="A", gt="A", note=""),
    dict(id="B10", name="食品飲料",
         a=[("08", "食品及飼品製造業"), ("09", "飲料製造業")], c=[], t=["食品工業"],
         basis_a="『食品工業』字面對應『食品及飼品製造業』；飲料屬食品相關，證交所無獨立產業別",
         basis_c="無對應貨品別（C 檔無食品類）",
         basis_t="字面對應",
         ga="A", gc="-", gt="A", note="僅有 S_A（無 S_C）"),
    dict(id="B11", name="造紙",
         a=[("15", "紙漿、紙及紙製品製造業")], c=[], t=["造紙工業"],
         basis_a="『造紙工業』字面對應『紙漿、紙及紙製品製造業』",
         basis_c="無對應貨品別",
         basis_t="字面相同",
         ga="A", gc="-", gt="A", note="僅有 S_A；證交所造紙工業僅約 8 檔，易因 <8 檔規則當期不出分數"),
    dict(id="B12", name="非金屬礦物（水泥、玻璃陶瓷）",
         a=[("23", "非金屬礦物製品製造業")], c=[], t=["水泥工業", "玻璃陶瓷"],
         basis_a="水泥、玻璃、陶瓷皆屬 TSIC 23 非金屬礦物製品（官方定義）",
         basis_c="C『礦產品』為礦業產品（非加工製品），不對應；不使用",
         basis_t="水泥工業、玻璃陶瓷＝官方定義對應",
         ga="B", gc="-", gt="B", note="僅有 S_A"),
    dict(id="B13", name="生技醫療（藥品與醫用化學製品）",
         a=[("20", "藥品及醫用化學製品製造業")], c=[], t=["生技醫療業"],
         basis_a="『生技醫療業』對應『藥品及醫用化學製品製造業』（官方定義；醫材亦在 TSIC 其他類，不完全涵蓋）",
         basis_c="無對應貨品別",
         basis_t="官方定義對應",
         ga="B", gc="-", gt="B", note="僅有 S_A；存貨率對藥品的『缺貨』意涵最弱，須 Cowork 審是否保留"),
]

# 非產業標籤：個股若同時有這些與具體產業別，這些一律忽略（傘狀或題材標籤）
UMBRELLA = {"電子工業", "化學生技醫療", "其他", "創新板股票", "創新版股票", "所有證券", "大盤", "Index",
            "存託憑證", "受益證券", "ETF", "上櫃ETF", "上櫃指數股票型基金(ETF)", "ETN", "指數投資證券(ETN)"}


def build_maps():
    t2b = {}
    for b in BUCKETS:
        for t in b["t"]:
            assert t not in t2b, t
            t2b[t] = b["id"]
    return t2b


def stock_map():
    info = pd.read_parquet(INFO)
    info = info[info["type"].isin(["twse", "tpex"])]
    t2b = build_maps()
    rows = []
    for sid, g in info.groupby("stock_id"):
        cats = sorted(set(g["industry_category"]) - UMBRELLA)
        if not cats:
            rows.append((sid, g["stock_name"].iloc[0], g["type"].iloc[0], "|".join(sorted(set(g["industry_category"]))), "", "umbrella_or_nonstock"))
            continue
        targets = {t2b.get(c, "UNMAPPED:" + c) for c in cats}
        if len(targets) > 1:
            rows.append((sid, g["stock_name"].iloc[0], g["type"].iloc[0], "|".join(cats), "", "ambiguous_excluded"))
        else:
            tgt = next(iter(targets))
            if tgt.startswith("UNMAPPED:"):
                rows.append((sid, g["stock_name"].iloc[0], g["type"].iloc[0], "|".join(cats), "", "unmapped_category"))
            else:
                rows.append((sid, g["stock_name"].iloc[0], g["type"].iloc[0], "|".join(cats), tgt, "mapped"))
    return rows


def sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


FROZEN = DOCS / "industry_shortage_mapping_FROZEN.json"


def verify():
    import json
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    ok = True
    for name, want in fz["sha256_lf"].items():
        got = sha(DOCS / name)
        print(("OK  " if got == want else "BAD ") + name, got)
        ok = ok and got == want
    return ok


def main():
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    if FROZEN.exists():
        print("對照表已凍結（%s），不得重新產生；用 --verify 核對 SHA256" % FROZEN.name)
        sys.exit(2)
    DOCS.mkdir(exist_ok=True)
    fb = DOCS / "industry_shortage_mapping.csv"
    with fb.open("w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["bucket_id", "bucket_name", "a_codes", "a_names", "c_commodities", "twse_categories",
                    "basis_a", "grade_a", "basis_c", "grade_c", "basis_twse", "grade_twse", "note"])
        for b in BUCKETS:
            w.writerow([b["id"], b["name"], "|".join(c for c, _ in b["a"]), "|".join(n for _, n in b["a"]),
                        "|".join(b["c"]), "|".join(b["t"]), b["basis_a"], b["ga"], b["basis_c"], b["gc"],
                        b["basis_t"], b["gt"], b["note"]])
    rows = stock_map()
    fs = DOCS / "industry_shortage_stock_map.csv"
    with fs.open("w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stock_id", "stock_name", "market", "specific_categories", "bucket_id", "status"])
        for r in sorted(rows):
            w.writerow(r)
    st = Counter(r[5] for r in rows)
    bc = Counter(r[4] for r in rows if r[5] == "mapped")
    unm = Counter(r[3] for r in rows if r[5] == "unmapped_category")
    amb = [r for r in rows if r[5] == "ambiguous_excluded"]
    amb_c = Counter(r[3] for r in amb)
    # 4 位數字代號的普通股（排除權證／ETF／債券類代號）
    def is_common(sid):
        return sid.isdigit() and len(sid) == 4
    bc4 = Counter(r[4] for r in rows if r[5] == "mapped" and is_common(r[0]))
    lines = []
    lines.append("# 產業缺貨方向：產業桶對照表（草案，未凍結，待 Cowork 審）\n")
    lines.append("狀態：**未凍結。** 依總司令 2026-10-02【先.十】五.2：由 CC 依官方分類名稱字面／官方定義逐桶建立並附依據欄，**凍結前停下等 Cowork 審**。"
                 "未讀任何價格、未計算任何報酬、未呼叫 `register_trial()`。\n")
    lines.append("建置腳本：`research/industry_shortage_mapping.py`（確定性，重跑結果相同）。桶層級表：`docs/industry_shortage_mapping.csv`（含依據與等級欄）；"
                 "個股→桶：`docs/industry_shortage_stock_map.csv`。\n")
    lines.append("等級：A＝官方名稱字面相同或字面包含；B＝官方定義對應；C＝近似／弱對應（須特別審）。\n")
    lines.append("## 桶總表\n")
    lines.append("| 桶 | 名稱 | A（中分類） | C（貨品別） | 證交所產業別 | 股票數（4碼普通股／全部） | 等級 A/C/證 |")
    lines.append("|---|---|---|---|---|---|---|")
    for b in BUCKETS:
        lines.append(f"| {b['id']} | {b['name']} | {'、'.join(n for _, n in b['a'])} | {'、'.join(b['c']) or '—'} | "
                     f"{'、'.join(b['t'])} | {bc4.get(b['id'], 0)}／{bc.get(b['id'], 0)} | {b['ga']}/{b['gc']}/{b['gt']} |")
    lines.append("")
    lines.append("## 個股→桶的確定性規則\n")
    lines.append("1. 資料：`TaiwanStockInfo`（非 PIT 現況快照，type 為 twse／tpex；偏差已於 #406 承認，見草案 §4）。\n"
                 "2. 同一檔股票在 `TaiwanStockInfo` 可有多列（例如 2330 有『半導體業』與『電子工業』）。先剔除傘狀／題材標籤"
                 "（" + "、".join(sorted(UMBRELLA)) + "）。\n"
                 "3. 剔除後若沒有剩餘標籤，標 `umbrella_or_nonstock`（多為 ETF、存託憑證等）。\n"
                 "4. 剩餘標籤各自查對照表；若指向**多個不同桶（或桶與未對應類別並存）**，標 `ambiguous_excluded`，**不分配、不納入**（寧缺勿猜）。\n"
                 "5. 唯一指向一個桶者標 `mapped`；唯一指向未對應類別者標 `unmapped_category`（例如金融、建材營造、航運、觀光、資訊服務、電子通路、其他電子業）。\n"
                 "6. 不使用 `drop_duplicates('stock_id')` 取第一列的做法（該做法使結果取決於列順序；#406 面板沿用該做法，本對照表不沿用）。\n")
    lines.append("## 狀態統計（TaiwanStockInfo 非 PIT 快照，twse＋tpex 全部列）\n")
    lines.append("| 狀態 | 檔數 |")
    lines.append("|---|---|")
    for k in ("mapped", "ambiguous_excluded", "unmapped_category", "umbrella_or_nonstock"):
        lines.append(f"| {k} | {st.get(k, 0)} |")
    lines.append("")
    lines.append("### ambiguous_excluded 明細（類別組合：檔數）\n")
    for k, v in amb_c.most_common():
        lines.append(f"- {k}：{v}")
    lines.append("")
    lines.append("### unmapped_category 明細（類別：檔數）\n")
    for k, v in unm.most_common():
        lines.append(f"- {k}：{v}")
    lines.append("")
    lines.append("## 已知限制（供 Cowork 審）\n")
    lines.append("- 『電機機械』（證交所）混有電機與機械，整類歸 B04；B03 因此只含『電器電纜』，股票數少。\n"
                 "- 『光電業』『通信網路業』在 TSIC 與證交所歸屬不同體系，B02 依總司令 2026-10-02 審定不用 S_C（資通類貨品別檔案取不到，光學器材代表性弱），只用 S_A。\n"
                 "- B02、B10～B13 沒有 S_C，只用 S_A；因此訊號來源在桶間不一致（有的桶是 S_A 與 S_C 平均，有的只有 S_A）。\n"
                 "- 『電子零組件業』『半導體業』合併為 B01，使 B01 成為最大桶；K=3 時 B01 入選會主導持股。\n"
                 "- 桶 <8 檔當期不出分數（草案 §2(b)）；B11 造紙可能常因此缺席。\n"
                 "- 對照表為 A 與 C 兩種分類各自映射到證交所產業別，未使用 TSIC 與證交所之間的官方對照檔（官方沒有）。\n")
    lines.append("## SHA256（存證用；總司令 2026-10-02 審定後凍結，之後不得修改）\n")
    lines.append(f"- `docs/industry_shortage_mapping.csv`：`{sha(fb)}`")
    lines.append(f"- `docs/industry_shortage_stock_map.csv`：`{sha(fs)}`")
    (DOCS / "industry_shortage_mapping.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("status", dict(st))
    print("bucket (4-digit common / all):", {b["id"]: (bc4.get(b["id"], 0), bc.get(b["id"], 0)) for b in BUCKETS})
    print("ambiguous:", len(amb))


if __name__ == "__main__":
    main()
