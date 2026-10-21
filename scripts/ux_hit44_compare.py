# -*- coding: utf-8 -*-
"""先.一二五-2：逐像素比對 ux_hit44_125.mjs 產生的 *_off.png／*_on.png（同一次載入、只差熱區兩條 CSS 規則）。
用法：python scripts/ux_hit44_compare.py research/ux_shots_122/hit44
每組報差異像素數、範圍與最大色階差；最大色階差 ≤ TOL（圓角／陰影反鋸齒的 1～3 階，肉眼看不出）算外觀相同，
超過就 exit 1。"""
import sys
from pathlib import Path

from PIL import Image, ImageChops

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOL = 12  # 實測最大 9 階＝圓角邊緣反鋸齒（research/ux_shots_122 下 off/on 放大比對確認）
d = Path(sys.argv[1] if len(sys.argv) > 1 else "research/ux_shots_122/hit44")
pairs = sorted(d.glob("*_off.png"))
diff_n = same_n = aa_n = 0
for off in pairs:
    on = off.with_name(off.name.replace("_off.png", "_on.png"))
    if not on.exists():
        print(f"缺 {on.name}")
        diff_n += 1
        continue
    a, b = Image.open(off).convert("RGB"), Image.open(on).convert("RGB")
    if a.size != b.size:
        print(f"尺寸不同 {off.name} {a.size} vs {b.size}")
        diff_n += 1
        continue
    dd = ImageChops.difference(a, b)
    bbox = dd.getbbox()
    if not bbox:
        same_n += 1
        continue
    px = list(dd.get_flattened_data()) if hasattr(dd, "get_flattened_data") else list(dd.getdata())
    n = sum(1 for p in px if p != (0, 0, 0))
    mx = max(max(p) for p in px)
    kind = "反鋸齒差" if mx <= TOL else "外觀不同"
    print(f"{kind} {off.name.replace('_off.png', '')}：{n} 像素，範圍 {bbox}，最大色階差 {mx}")
    if mx <= TOL:
        aa_n += 1
    else:
        diff_n += 1
print(f"比對 {len(pairs)} 組：完全相同 {same_n}、只有反鋸齒差（≤{TOL} 階）{aa_n}、外觀不同 {diff_n}")
sys.exit(1 if diff_n or not pairs else 0)
