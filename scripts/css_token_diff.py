# 2026-10-14 先.九十四-5i：比對 css_token_shots.mjs 的 before／after 截圖（逐像素）與 computed style 摘要。
# 門檻：每張截圖差異像素 < 0.5%；computed style 序列另外列出不一致筆數（應為 0）。
# 用法：python scripts/css_token_diff.py
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent / "research" / "ux_shots" / "css_tokens"
LIMIT = 0.005
bad = 0
for b in sorted((ROOT / "before").glob("*.png")):
    a = ROOT / "after" / b.name
    if not a.exists():
        print(f"缺少 after：{b.name}"); bad += 1; continue
    ib, ia = Image.open(b).convert("RGB"), Image.open(a).convert("RGB")
    if ib.size != ia.size:
        print(f"FAIL {b.name}：尺寸不同 {ib.size} vs {ia.size}"); bad += 1; continue
    diff = ImageChops.difference(ib, ia).convert("L")
    n = sum(1 for v in diff.getdata() if v)
    ratio = n / (ib.size[0] * ib.size[1])
    sa_p = a.parent / (a.stem + ".styles.json")
    sb_p = b.parent / (b.stem + ".styles.json")
    sb = json.loads(sb_p.read_text(encoding="utf-8")) if sb_p.exists() else []
    sa = json.loads(sa_p.read_text(encoding="utf-8")) if sa_p.exists() else []
    smis = sum(1 for x, y in zip(sb, sa) if x != y) + abs(len(sb) - len(sa))
    ok = ratio < LIMIT
    bad += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {b.name}：差異像素 {n}／{ib.size[0]*ib.size[1]}＝{ratio*100:.3f}%；computed style 不一致 {smis}／{len(sb)} 個元素")
print("=== 全部 < 0.5% ===" if not bad else f"=== {bad} 張超標 ===")
sys.exit(1 if bad else 0)
