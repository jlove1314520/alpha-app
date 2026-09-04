# -*- coding: utf-8 -*-
"""HTTPS方案A第一階段（2026-09-04總司令裁示）：產生自簽根CA＋伺服器葉憑證，讓
alpha_live_server.py之後能走HTTPS（解決PWA https頁面抓http本機伺服器的混合內容封鎖）。

**只在本機執行一次性產生（或憑證快過期時重跑），不是每次啟動都跑**——私鑰跟憑證都
寫進`secrets/`（已在.gitignore，永不進git，這個repo是public的）。

規格（總司令原話逐條對應）：
- 根CA：RSA 4096、SHA-256、10年、CN=Alpha Local CA、CA:TRUE（critical basic constraints）、
  keyUsage=keyCertSign+cRLSign（critical）。
- 伺服器葉憑證：RSA 2048、由CA簽、有效期825天（iOS對leaf cert的硬性上限，Apple自2019年
  起任何超過825天的伺服器憑證會被Safari/WebKit直接拒絕，這裡踩在上限內）、
  SAN=IP:192.168.3.241 + IP:127.0.0.1 + DNS:localhost、EKU=serverAuth（critical）。
- 私鑰放secrets/絕不進repo；CA公開憑證另存DER格式`secrets/alpha-ca.crt`（給/ca.crt端點
  下載用，手機端安裝這個檔案當根憑證後才會信任伺服器葉憑證）。

輸出檔案（全部在secrets/，已gitignore）：
  alpha-ca-key.pem      CA私鑰（唯一真正敏感的檔案，外洩=可以偽造任何憑證讓手機信任）
  alpha-ca.pem           CA憑證，PEM格式（人類可讀/openssl慣用）
  alpha-ca.crt           CA憑證，DER格式（給手機安裝用，iOS/Android對.crt副檔名+DER
                          內容的辨識度最高，Content-Type: application/x-x509-ca-cert）
  alpha-server-key.pem   伺服器葉私鑰
  alpha-server-cert.pem  伺服器葉憑證（PEM，uvicorn --ssl-certfile吃這個）
  alpha-server-fullchain.pem  葉憑證+CA憑證串接（部分TLS client驗證鏈需要完整鏈，
                          保險起見一併輸出，uvicorn若用這個檔案也能work）

若secrets/裡已經有一組還在有效期內的憑證，預設不覆蓋（避免每次跑腳本就讓手機端已安裝的
CA信任關係失效、要重裝）——加`--force`才強制重新產生一整組新的CA+葉憑證。
"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CA_KEY_PATH = SECRETS_DIR / "alpha-ca-key.pem"
CA_PEM_PATH = SECRETS_DIR / "alpha-ca.pem"
CA_DER_PATH = SECRETS_DIR / "alpha-ca.crt"
SERVER_KEY_PATH = SECRETS_DIR / "alpha-server-key.pem"
SERVER_CERT_PATH = SECRETS_DIR / "alpha-server-cert.pem"
SERVER_FULLCHAIN_PATH = SECRETS_DIR / "alpha-server-fullchain.pem"

CA_VALID_DAYS = 365 * 10  # 10年
LEAF_VALID_DAYS = 825  # iOS/Safari對伺服器葉憑證的硬性上限，不能超過
SERVER_IPS = ["192.168.3.241", "127.0.0.1"]
SERVER_DNS = ["localhost"]


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def build_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Alpha Local CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Alpha (local dev)"),
    ])
    now = _now()
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # 自簽：issuer=subject
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))  # 容忍時鐘些微超前
        .not_valid_after(now + datetime.timedelta(days=CA_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    cert = builder.sign(key, hashes.SHA256())
    return key, cert


def build_server_leaf(ca_key: rsa.RSAPrivateKey, ca_cert: x509.Certificate) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "alpha-live-server.local")])
    now = _now()
    san = x509.SubjectAlternativeName(
        [x509.IPAddress(__import__("ipaddress").ip_address(ip)) for ip in SERVER_IPS]
        + [x509.DNSName(d) for d in SERVER_DNS]
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=LEAF_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=True,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=True)
        .add_extension(san, critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
    )
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def existing_leaf_still_valid() -> bool:
    if not SERVER_CERT_PATH.exists():
        return False
    try:
        cert = x509.load_pem_x509_certificate(SERVER_CERT_PATH.read_bytes())
    except Exception:
        return False
    remaining = cert.not_valid_after_utc - _now()
    return remaining > datetime.timedelta(days=30)  # 快過期（<30天）就當作需要重新產生


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="即使已有有效憑證也強制重新產生一整組新的CA+葉憑證")
    args = ap.parse_args()

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.force and existing_leaf_still_valid():
        cert = x509.load_pem_x509_certificate(SERVER_CERT_PATH.read_bytes())
        print(f"secrets/裡已有有效憑證（到期 {cert.not_valid_after_utc.isoformat()}），不重新產生。"
              f"要強制重來請加 --force。")
        return

    print("產生根CA（RSA 4096, SHA-256, 10年）...")
    ca_key, ca_cert = build_ca()
    _write_key(CA_KEY_PATH, ca_key)
    CA_PEM_PATH.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    CA_DER_PATH.write_bytes(ca_cert.public_bytes(serialization.Encoding.DER))
    print(f"  {CA_KEY_PATH}")
    print(f"  {CA_PEM_PATH}")
    print(f"  {CA_DER_PATH}（DER格式，/ca.crt端點回傳這個）")

    print("產生伺服器葉憑證（RSA 2048, 由CA簽, 825天）...")
    server_key, server_cert = build_server_leaf(ca_key, ca_cert)
    _write_key(SERVER_KEY_PATH, server_key)
    SERVER_CERT_PATH.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    SERVER_FULLCHAIN_PATH.write_bytes(
        server_cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    print(f"  {SERVER_KEY_PATH}")
    print(f"  {SERVER_CERT_PATH}")
    print(f"  {SERVER_FULLCHAIN_PATH}")

    sans = ", ".join(f"IP:{ip}" for ip in SERVER_IPS) + ", " + ", ".join(f"DNS:{d}" for d in SERVER_DNS)
    print()
    print("=== 摘要 ===")
    print(f"CA：CN={ca_cert.subject.rfc4514_string()}，有效期 {ca_cert.not_valid_before_utc.date()} ~ {ca_cert.not_valid_after_utc.date()}")
    print(f"伺服器葉憑證：CN={server_cert.subject.rfc4514_string()}")
    print(f"  SAN：{sans}")
    print(f"  有效期：{server_cert.not_valid_before_utc.date()} ~ {server_cert.not_valid_after_utc.date()}"
          f"（{(server_cert.not_valid_after_utc - server_cert.not_valid_before_utc).days}天）")
    print(f"  簽發者：{server_cert.issuer.rfc4514_string()}")


if __name__ == "__main__":
    main()
