"""先.三十一-一：Web Push（VAPID）自測。全部在暫存目錄，不碰本機 .env、不送任何真推播。"""
import base64, json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
import web_push as W

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def SUB(i=1):
    return {"endpoint": f"https://push.example/{i}", "keys": {"p256dh": "p" * 87, "auth": "a" * 22}}


d = Path(tempfile.mkdtemp())
env = d / ".env"
env.write_text("SOME_OTHER=1", encoding="utf-8")  # 沒有結尾換行
pub = W.gen_keys(env)
txt = env.read_text(encoding="utf-8")
check("金鑰：附加到 .env、不動既有內容", txt.startswith("SOME_OTHER=1\n") and "ALPHA_VAPID_PRIVATE_KEY=" in txt)
check("金鑰：公鑰為 65 bytes 未壓縮點", len(base64.urlsafe_b64decode(pub + "=" * (-len(pub) % 4))) == 65)
check("金鑰：已存在就沿用不覆蓋", W.gen_keys(env) == pub and env.read_text(encoding="utf-8").count("ALPHA_VAPID_PRIVATE_KEY=") == 1)

base = d / "auto"
r = W.send("t", "b", base=base, env_path=d / "none.env", sender=lambda *a: 201)
check("送出：沒有金鑰→ok=0、NO_VAPID_KEY、不拋例外", r["ok"] == 0 and "NO_VAPID_KEY" in r["errors"][0])
r = W.send("t", "b", base=base, env_path=env, sender=lambda *a: 201)
check("送出：沒有訂閱→ok=0、NO_SUBSCRIPTION", r["ok"] == 0 and "NO_SUBSCRIPTION" in r["errors"][0])

check("訂閱：拒絕非 https endpoint", not W.valid_subscription({"endpoint": "http://x", "keys": {"p256dh": "a", "auth": "b"}}))
check("訂閱：拒絕缺 keys", not W.valid_subscription({"endpoint": "https://x"}))
W.add_sub(base, SUB(1), "iOS")
check("訂閱：同 endpoint 覆蓋不重複", W.add_sub(base, SUB(1), "iOS") == 1)
for i in range(2, 15):
    W.add_sub(base, SUB(i))
check("訂閱：最多保留 MAX_SUBS 筆", len(W.load_subs(base)) == W.MAX_SUBS)
W.remove_sub(base, SUB(14)["endpoint"])
check("訂閱：退訂", len(W.load_subs(base)) == W.MAX_SUBS - 1)

seen = []
r = W.send("否決窗", "0050 買 3000 股", kind="veto", base=base, env_path=env,
           sender=lambda s, p, v, t, u: (seen.append(json.loads(p)), 201)[1])
check("送出：全部成功→ok=訂閱數", r["ok"] == W.MAX_SUBS - 1 and r["failed"] == 0)
check("送出：payload 帶 title／body／tag", seen and seen[0]["title"] == "否決窗" and seen[0]["tag"] == "veto")

codes = iter([410, 404, 500] + [201] * 20)
r = W.send("t", "b", base=base, env_path=env, sender=lambda *a: next(codes))
check("送出：410／404 自動移除失效訂閱", len(W.load_subs(base)) == W.MAX_SUBS - 3 and r["failed"] == 3)


def boom(*a):
    raise ConnectionError("down")


r = W.send("t", "b", base=base, env_path=env, sender=boom)
check("送出：網路錯誤→ok=0、不拋例外、不刪訂閱", r["ok"] == 0 and len(W.load_subs(base)) == W.MAX_SUBS - 3)
log = (base / W.LOG_NAME).read_text(encoding="utf-8")
check("紀錄：push_log 不含推播內容（股數金額）", "0050 買 3000 股" not in log and '"kind": "veto"' in log)

# 真加密：pywebpush 以 aes128gcm 加密，用瀏覽器端私鑰解回來應一致
try:
    import http_ece
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from pywebpush import WebPusher
    ck = ec.generate_private_key(ec.SECP256R1())
    cpub = ck.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    sub = {"endpoint": "https://push.example/x", "keys": {"p256dh": W._b64u(cpub), "auth": W._b64u(auth)}}
    msg = json.dumps({"title": "否決窗開始", "body": "測試"}, ensure_ascii=False).encode("utf-8")
    enc = WebPusher(sub).encode(msg, content_encoding="aes128gcm")
    out = http_ece.decrypt(enc["body"], private_key=ck, auth_secret=auth, version="aes128gcm")
    check("加密：aes128gcm 加密後瀏覽器端金鑰可解回原文", out == msg)
except Exception as e:
    check(f"加密：aes128gcm 往返（{type(e).__name__}: {e}）", False)

# VAPID 簽章：用 .env 私鑰簽出的 JWT，公鑰與 .env 公鑰一致
try:
    from py_vapid import Vapid
    v = W.load_vapid(env)
    vv = Vapid.from_string(v["private"])
    hdr = vv.sign({"sub": v["subject"], "aud": "https://web.push.apple.com"})
    from cryptography.hazmat.primitives import serialization as S
    p2 = W._b64u(vv.public_key.public_bytes(S.Encoding.X962, S.PublicFormat.UncompressedPoint))
    check("VAPID：私鑰可簽章且對應公鑰一致", bool(hdr.get("Authorization")) and p2 == v["public"])
except Exception as e:
    check(f"VAPID：簽章（{type(e).__name__}）", False)

print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
