"""網域層級的爬蟲合規防呆（2026-09-20總司令裁示【緊急·合規】合規.二，
根因修復：把防呆從【腳本層】移到【網域層】）。

**背景**：2026-09-15曾對四支既有MOPS client（`mops_material_news_
client.py`／`mops_buyback_client.py`／`mops_cb_conversion_price_
client.py`／`mops_insider_holdings_client.py`）逐支手動加`PermissionError`
擋下`mopsov.twse.com.tw`。但這個防呆綁在「已知的四支程式」上，2026-09-19
一支全新腳本（`material_disclosure_order_win_count.py`）完全沒繼承到，
直接對同一個被`robots.txt`全站`Disallow: /`的網域發出100次POST請求——
規則寫在`CLAUDE.md`／`docs/DATA_SOURCE_MAP.md`裡，但沒有任何機器在檢查
「新腳本有沒有不小心打到黑名單網域」，這次就是這樣破的。

**這支模組解決的問題**：把黑名單網域的擋法從「每支腳本各自記得寫
PermissionError」改成「呼叫`install()`一次，之後這個Python行程裡任何
`requests`呼叫（不管是哪支腳本、哪個函式）打到黑名單網域都會被攔下，
連請求都不會送出去」。

**已知限制（誠實記錄，不假裝做到了）**：這不是全機器/全域的防呆——
`install()`只影響「有呼叫這支模組的Python行程」，不會自動保護「完全沒
import這支模組的全新腳本」。要做到「新腳本預設受保護、不需要作者記得」
的完整版本，需要在Python的系統級`sitecustomize.py`或使用者級site-packages
掛一個全域monkeypatch，但那樣的改動會影響**這台機器上所有跟`requests`
有關的Python行程**，不限於這個專案（例如使用者未來寫的任何其他小工具，
只要用到`requests`就會被這個黑名單影響），blast radius超出本專案範圍，
所屬於需要總司令確認才能做的機器層級變更，本輪不自行決定。**因此實際
的雙重防線是**：(1) 本模組讓「有記得import」的腳本得到網域層防呆而非
腳本層防呆（同一支`install()`保護所有黑名單網域，不用每個網域各寫一次
PermissionError）；(2) `audit_preflight.py`的靜態掃描（合規.三）在
commit/稽核時抓出「完全沒import net_guard、卻硬寫黑名單網域字串」的
新腳本，兩層合起來才是完整的防呆，不是這支模組單獨就能做到。
"""
from __future__ import annotations

import functools
from urllib.parse import urlsplit

import requests

# 黑名單網域清單，來源：`docs/DATA_SOURCE_MAP.md`裡明確標🔴且理由是
# 「robots.txt全站/大面積Disallow」或「使用條款明文禁止爬蟲」或「查詢
# 介面要求人工圖形驗證碼（程式解驗證碼=禁止）」的網域。**日後
# `docs/DATA_SOURCE_MAP.md`新增同類🔴條目時，這裡要同步補上**。
DOMAIN_BLOCKLIST: frozenset[str] = frozenset({
    # robots.txt「Disallow: /」（除bingbot外全站禁止），2026-09-08查證，
    # 2026-09-15總司令裁示停用四支既有client，2026-09-19又被新腳本繞過
    # （本模組正是為了堵住這個繞過口子而生）。
    "mopsov.twse.com.tw",
    # robots.txt「Disallow: /」（年報/簡報PDF實際主機），2026-09-09查證。
    "doc.twse.com.tw",
    # 使用條款明文「禁止透過…蜘蛛程式、爬蟲程式或擷取程式等方式下載」，
    # 2026-09-08查證，見`docs/TPEX_INDUSTRY_CHAIN_GATE.md`。
    "ic.tpex.org.tw",
    # 查詢介面要求人工輸入圖形驗證碼，總司令2026-09-06原話「分點資料走
    # 合法路線,不繞驗證碼、不爬bsr」，程式解驗證碼＝禁止取得方式。
    "bsr.twse.com.tw",
})


class BlockedDomainError(PermissionError):
    """對黑名單網域發出請求時拋出。是`PermissionError`的子類，跟既有四支
    MOPS client手寫的`PermissionError`同一種語意，呼叫端既有的
    `except PermissionError`邏輯不需要改。"""


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_blocked(url: str) -> bool:
    """網域完全比對（含子網域）：`a.b.mopsov.twse.com.tw`也算命中
    `mopsov.twse.com.tw`，但`notmopsov.twse.com.tw`這種前綴巧合不算
    （用`.`分段比對，不用字串`endswith`裸比對，避免這類假陽性/假陰性）。"""
    host = _host_of(url)
    if not host:
        return False
    parts = host.split(".")
    for blocked in DOMAIN_BLOCKLIST:
        blocked_parts = blocked.split(".")
        if parts[-len(blocked_parts):] == blocked_parts:
            return True
    return False


_installed = False
_original_request = requests.Session.request


def _guarded_request(self, method, url, *args, **kwargs):
    if is_blocked(url):
        raise BlockedDomainError(
            f"net_guard：{_host_of(url)} 在黑名單網域清單裡"
            "（見research/net_guard.py::DOMAIN_BLOCKLIST與"
            "docs/DATA_SOURCE_MAP.md），本次請求已在送出前被攔截，"
            "不會有任何網路流量發出。如需恢復，需先有合規替代方案"
            "或總司令另行核准。"
        )
    return _original_request(self, method, url, *args, **kwargs)


def install() -> None:
    """monkeypatch `requests.Session.request`（`get`/`post`/…最終都會走
    這個方法），對本行程之後所有`requests`呼叫生效，直到`uninstall()`。
    重複呼叫是安全的（不會疊加patch兩次）。"""
    global _installed
    if _installed:
        return
    requests.Session.request = _guarded_request  # type: ignore[method-assign]
    _installed = True


def uninstall() -> None:
    """還原成patch前的原始方法，主要給測試用（驗證patch本身可逆）。"""
    global _installed
    if not _installed:
        return
    requests.Session.request = _original_request  # type: ignore[method-assign]
    _installed = False


def self_test() -> None:
    """驗收腳本：故意打黑名單網域，確認被擋下且沒有送出任何真實請求。"""
    install()
    assert is_blocked("https://mopsov.twse.com.tw/mops/web/ajax_t51sb10")
    assert is_blocked("https://sub.mopsov.twse.com.tw/x")
    assert is_blocked("https://doc.twse.com.tw/some/report.pdf")
    assert is_blocked("https://ic.tpex.org.tw/some/page")
    assert is_blocked("https://bsr.twse.com.tw/bshtm/")
    assert not is_blocked("https://www.twse.com.tw/rwd/zh/fund/T86")
    assert not is_blocked("https://notmopsov.twse.com.tw/x")  # 前綴巧合不算命中

    blocked_hit = False
    try:
        requests.get("https://mopsov.twse.com.tw/mops/web/ajax_t51sb10", timeout=5)
    except BlockedDomainError:
        blocked_hit = True
    assert blocked_hit, "應該要被net_guard擋下，卻沒有拋出BlockedDomainError"

    print("net_guard self_test: 全部通過（黑名單網域被攔截，未送出任何真實請求；"
          "白名單網域與前綴巧合網域不受影響）。")


if __name__ == "__main__":
    self_test()
