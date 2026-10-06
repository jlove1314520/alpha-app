"""先.三十一-一：標準 Web Push（VAPID，方案A）。不註冊任何第三方帳號。

- VAPID 金鑰只放本機 .env（ALPHA_VAPID_PRIVATE_KEY／ALPHA_VAPID_PUBLIC_KEY／ALPHA_VAPID_SUBJECT），
  私鑰只讀進記憶體，不印出、不寫進 log、不 commit。`python research/web_push.py --gen-keys`
  只在 .env 還沒有這組金鑰時產生並附加（不讀出既有內容），只印公鑰。
- 訂閱由 App 經本機 API（X-Alpha-Local-Token）交給 alpha_live_server，存在
  research/data/auto_trading/push_subscriptions.json（.gitignore 已排除 research/data/）。
- send() 永遠不拋例外，回傳 {"ok": 成功送達的訂閱數, "failed": ..., "errors": [...]}；
  要不要 fail closed 由呼叫端決定（否決窗開始＝fail closed，其餘＝只降級警告）。
- push_log.jsonl 只記事件類別與成功／失敗數，不記內容（內容含股數與金額）。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
ENV_PATH = REPO / ".env"
DEFAULT_DIR = REPO / "research" / "data" / "auto_trading"
SUBS_NAME = "push_subscriptions.json"
LOG_NAME = "push_log.jsonl"
TW = timezone(timedelta(hours=8))
# VAPID sub：用 App 公開網址（已公開，非個資）。2026-10-06 實測 Apple 會以 BadJwtToken(403)
# 拒絕 .example 佔位信箱；改用本網址後 Apple 回 BadWebPushToken(400，假 token 的預期結果)，代表 JWT 已被接受。
DEFAULT_SUBJECT = "https://jlove1314520.github.io"
MAX_SUBS = 10


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _read_env(env_path: Path = ENV_PATH) -> dict:
    env = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def load_vapid(env_path: Path = ENV_PATH) -> dict | None:
    env = _read_env(env_path)
    priv, pub = env.get("ALPHA_VAPID_PRIVATE_KEY"), env.get("ALPHA_VAPID_PUBLIC_KEY")
    if not (priv and pub):
        return None
    return {"private": priv, "public": pub, "subject": env.get("ALPHA_VAPID_SUBJECT") or DEFAULT_SUBJECT}


def public_key(env_path: Path = ENV_PATH) -> str | None:
    v = load_vapid(env_path)
    return v["public"] if v else None


def gen_keys(env_path: Path = ENV_PATH) -> str:
    """.env 已有金鑰就沿用（不覆蓋，否則手機上既有訂閱全部失效）；沒有才產生並附加。回傳公鑰。"""
    v = load_vapid(env_path)
    if v:
        return v["public"]
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    priv = _b64u(k.private_numbers().private_value.to_bytes(32, "big"))
    pub = _b64u(k.public_key().public_bytes(serialization.Encoding.X962,
                                            serialization.PublicFormat.UncompressedPoint))
    prefix = ""
    if env_path.exists() and env_path.read_bytes()[-1:] not in (b"\n", b""):
        prefix = "\n"
    with open(env_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"{prefix}# 先.三十一-一 Web Push VAPID 金鑰（只在本機，勿外流；換掉會讓手機訂閱全部失效）\n"
                f"ALPHA_VAPID_PRIVATE_KEY={priv}\nALPHA_VAPID_PUBLIC_KEY={pub}\n"
                f"ALPHA_VAPID_SUBJECT={DEFAULT_SUBJECT}\n")
    return pub


def _subs_path(base: Path) -> Path:
    return Path(base) / SUBS_NAME


def load_subs(base: Path = DEFAULT_DIR) -> list:
    try:
        d = json.loads(_subs_path(base).read_text(encoding="utf-8"))
        return [s for s in d.get("subscriptions", []) if isinstance(s, dict) and s.get("endpoint")]
    except Exception:
        return []


def _save_subs(base: Path, subs: list) -> None:
    p = _subs_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"updated_at": datetime.now(TW).isoformat(timespec="seconds"),
                               "subscriptions": subs}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def valid_subscription(sub) -> bool:
    if not isinstance(sub, dict):
        return False
    ep, keys = sub.get("endpoint"), sub.get("keys")
    return (isinstance(ep, str) and ep.startswith("https://") and len(ep) < 2048 and isinstance(keys, dict)
            and isinstance(keys.get("p256dh"), str) and isinstance(keys.get("auth"), str))


def add_sub(base: Path, sub: dict, label: str = "") -> int:
    """同一 endpoint 視為同一支裝置（覆蓋）；最多保留 MAX_SUBS 筆最新的。回傳目前訂閱數。"""
    if not valid_subscription(sub):
        raise ValueError("訂閱格式不正確（需要 endpoint 與 keys.p256dh／keys.auth）")
    subs = [s for s in load_subs(base) if s.get("endpoint") != sub["endpoint"]]
    subs.append({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]},
                 "label": str(label or "")[:40], "added_at": datetime.now(TW).isoformat(timespec="seconds")})
    subs = subs[-MAX_SUBS:]
    _save_subs(base, subs)
    return len(subs)


def remove_sub(base: Path, endpoint: str) -> int:
    subs = [s for s in load_subs(base) if s.get("endpoint") != endpoint]
    _save_subs(base, subs)
    return len(subs)


def _log(base: Path, kind: str, result: dict) -> None:
    try:
        p = Path(base) / LOG_NAME
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": datetime.now(TW).isoformat(timespec="seconds"), "kind": kind,
                                "ok": result.get("ok", 0), "failed": result.get("failed", 0),
                                "errors": result.get("errors", [])[:5]}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[warn] 寫推播紀錄失敗：{type(e).__name__}", flush=True)


def _pywebpush_sender(sub: dict, payload: str, vapid: dict, ttl: int, urgency: str) -> int:
    """實際送出一則；回傳推播服務的 HTTP 狀態碼。網路錯誤照常拋例外。"""
    from pywebpush import webpush, WebPushException
    try:
        r = webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload,
                    vapid_private_key=vapid["private"], vapid_claims={"sub": vapid["subject"]},
                    ttl=ttl, headers={"Urgency": urgency}, timeout=10)
        return int(getattr(r, "status_code", 201))
    except WebPushException as e:
        resp = getattr(e, "response", None)
        if resp is not None:
            return int(resp.status_code)
        raise


SENDER = _pywebpush_sender  # 自測替換用，正式流程不要動


def send(title: str, body: str, kind: str = "info", base: Path = DEFAULT_DIR, url: str = "./",
         ttl: int = 3600, urgency: str = "high", env_path: Path = ENV_PATH, sender=None) -> dict:
    """送給所有已訂閱裝置。永遠不拋例外。404／410（訂閱已失效）自動移除。"""
    res = {"ok": 0, "failed": 0, "errors": [], "subscriptions": 0}
    try:
        vapid = load_vapid(env_path)
        if not vapid:
            res["errors"].append("NO_VAPID_KEY:本機 .env 沒有 VAPID 金鑰")
            return res
        subs = load_subs(base)
        res["subscriptions"] = len(subs)
        if not subs:
            res["errors"].append("NO_SUBSCRIPTION:沒有任何裝置訂閱推播")
            return res
        payload = json.dumps({"title": title, "body": body, "tag": kind, "url": url,
                              "ts": datetime.now(TW).isoformat(timespec="seconds")}, ensure_ascii=False)
        fn = sender or SENDER
        gone = []
        for s in subs:
            try:
                code = fn(s, payload, vapid, ttl, urgency)
            except Exception as e:
                res["failed"] += 1
                res["errors"].append(f"NETWORK:{type(e).__name__}")
                continue
            if 200 <= code < 300:
                res["ok"] += 1
            else:
                res["failed"] += 1
                res["errors"].append(f"HTTP_{code}")
                if code in (404, 410):
                    gone.append(s["endpoint"])
        if gone:
            _save_subs(base, [s for s in subs if s["endpoint"] not in gone])
    except Exception as e:
        res["errors"].append(f"INTERNAL:{type(e).__name__}")
    finally:
        _log(base, kind, res)
    return res


def notify(title: str, body: str, kind: str = "info", base: Path = DEFAULT_DIR, **kw) -> dict:
    """非關鍵推播（拒單／錯誤／漏跑／完成）：失敗只印一行警告，不影響呼叫端。"""
    r = send(title, body, kind=kind, base=base, **kw)
    if not r.get("ok"):
        print(f"[warn] 推播未送達（{kind}）：{'；'.join(r.get('errors', [])[:3]) or '未知'}", flush=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="Web Push（VAPID）工具")
    ap.add_argument("--gen-keys", action="store_true", help=".env 沒有 VAPID 金鑰時產生並附加；只印公鑰")
    ap.add_argument("--status", action="store_true", help="顯示金鑰是否就緒與訂閱數（不印私鑰與 endpoint）")
    ap.add_argument("--test", action="store_true", help="送一則測試推播給所有訂閱裝置")
    a = ap.parse_args()
    if a.gen_keys:
        print("VAPID 公鑰：", gen_keys())
        return 0
    if a.test:
        r = send("Alpha 測試推播", "收到這則代表否決窗推播可以送到這支裝置。", kind="test")
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else 1
    print(json.dumps({"vapid_ready": bool(load_vapid()), "subscriptions": len(load_subs())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
