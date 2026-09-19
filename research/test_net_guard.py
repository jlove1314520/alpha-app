"""驗收腳本（合規.二）：故意打黑名單網域，實證(1)被net_guard擋下
(2)**沒有任何真實網路連線被建立**——不是只靠讀程式碼推論會擋下，是用
`socket.create_connection`monkeypatch成「一被呼叫就讓測試失敗」來實測，
確保就算net_guard本身有漏洞，這支測試也抓得到「其實還是發出了請求」。
"""
from __future__ import annotations

import socket

import requests

import net_guard


def _forbid_real_connections(*_args, **_kwargs):
    raise AssertionError(
        "偵測到真實網路連線嘗試——net_guard應該要在建立連線前就攔截，"
        "這代表防呆本身有漏洞，不是測試設計問題。"
    )


def test_blocked_domains_raise_before_any_network_call() -> None:
    net_guard.install()
    original_create_connection = socket.create_connection
    socket.create_connection = _forbid_real_connections
    try:
        for url in (
            "https://mopsov.twse.com.tw/mops/web/ajax_t51sb10",
            "https://doc.twse.com.tw/some/report.pdf",
            "https://ic.tpex.org.tw/some/page",
            "https://bsr.twse.com.tw/bshtm/",
        ):
            try:
                requests.get(url, timeout=5)
            except net_guard.BlockedDomainError:
                pass
            else:
                raise AssertionError(f"{url} 應該被net_guard擋下卻沒有")
    finally:
        socket.create_connection = original_create_connection
        net_guard.uninstall()
    print("test_net_guard: 4個黑名單網域全部在建立連線前被攔截"
          "（用socket.create_connection monkeypatch實測，非只靠程式碼推論）。")


def test_non_blocked_domain_not_affected_by_guard_logic() -> None:
    """只驗證`is_blocked()`本身的判斷邏輯不誤判白名單網域，不實際發出
    請求（避免測試依賴外部網路可用性）。"""
    net_guard.install()
    try:
        assert not net_guard.is_blocked("https://www.twse.com.tw/rwd/zh/fund/T86")
        assert not net_guard.is_blocked("https://openapi.twse.com.tw/v1/x")
        assert not net_guard.is_blocked("https://notmopsov.twse.com.tw/x")
    finally:
        net_guard.uninstall()
    print("test_net_guard: 白名單網域與前綴巧合網域的判斷邏輯正確。")


if __name__ == "__main__":
    test_blocked_domains_raise_before_any_network_call()
    test_non_blocked_domain_not_affected_by_guard_logic()
