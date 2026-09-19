# -*- coding: utf-8 -*-
"""應跑班次計算（2026-09-16 總司令裁示【班次數門檻】，取代「間隔×3倍」）。

**為什麼要這支**：market.yml 停擺 31 小時（09-15 17:00／18:30、09-16 05:30
三個班次全部沒有產出），但舊判準是「預期間隔(1440分)×3倍=3天」，31小時遠
遠不到3天，整條線靜默停擺一天半都不會亮燈。總司令裁示：**不加新架構，
改判準**——把「間隔×倍數」換成「連續N個應跑班次無新產出」，market.yml
明確給了班次表（工作日17:00/18:30/隔日05:30共三班），quotes.yml／
news_events.yml各自用自己的cron換算應跑班次，一律N=2就亮燈。

**「應跑班次」用既有交易日曆與假日表判定**：週末不算（cron本身已經只排
Mon-Fri，但這裡額外用weekday()判斷是避免未來cron改動時的隱性假設），
國定假日不算——避免誤報（同一套判準太緊時，一個假日夾在兩個班次中間
就會被誤數成「連續2個沒跑」）。

**維護提醒（手動同步，沒有建置流程可以共用一份）**：`TW_HOLIDAYS_2026`
是從 `index.html` 第 2239 行左右的 `TW_HOLIDAYS_2026` 手動抄過來的複本，
只寫死 2026 年，跨年前要更新；改一邊要記得改另一邊。沒更新時的行為是
把該假日當成交易日——結果只是那天可能多算一個「應跑」，不會反過來把
真的停擺藏起來，這個方向的失敗比較安全（沿用 index.html 同一套設計理由）。

用法：
    from expected_shift_calendar import count_missed_shifts
    n, labels = count_missed_shifts("market_yml", last_output_dt, now_dt)
    # n >= 2 就是「連續2個應跑班次沒有新產出」

回放測試（驗證這次31小時停擺會在第2班亮燈）：
    python scripts/expected_shift_calendar.py --replay-2026-09-outage
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有
# ⚠/✓/✗(U+26A0/2713/2717)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

TZ = timezone(timedelta(hours=8))
UTC = timezone.utc

# 手動同步自 index.html::TW_HOLIDAYS_2026（見檔頭維護提醒）。
TW_HOLIDAYS_2026 = {
    "2026-01-01", "2026-02-13", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-19", "2026-02-20", "2026-02-27", "2026-02-28", "2026-04-03",
    "2026-04-06", "2026-05-01", "2026-06-19", "2026-09-25", "2026-10-09",
    "2026-10-26", "2026-12-25",
}


def is_tw_trading_day(d: date) -> bool:
    """週末（weekday()>=5）或列在 TW_HOLIDAYS_2026 的日期，都不是交易日。"""
    if d.weekday() >= 5:  # 5=週六 6=週日
        return False
    return d.isoformat() not in TW_HOLIDAYS_2026


def _tp(d: date, hour: int, minute: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)


def market_yml_expected_shifts(since: datetime, until: datetime) -> list[datetime]:
    """market.yml 三班：交易日 17:00／18:30／隔日 05:30（Asia/Taipei）。

    三班是不是「應跑」，都由同一個交易日旗標（那一天是否為台股交易日）
    決定——包含「隔日05:30」這班：它對應的是 cron `30 21 * * 1-5` 在那個
    UTC 交易日weekday觸發、換算到台北時間落到下一個日曆日，跟這個交易日
    是不是隔天也是交易日無關（cron 本身就不看隔天）。
    """
    out: list[datetime] = []
    if since is None or until is None or since >= until:
        return out
    d = since.date() - timedelta(days=1)  # 往前多抓一天，避免邊界漏算
    end_d = until.date() + timedelta(days=1)
    while d <= end_d:
        if is_tw_trading_day(d):
            for hh, mm, day_offset in ((17, 0, 0), (18, 30, 0), (5, 30, 1)):
                ts = _tp(d + timedelta(days=day_offset), hh, mm)
                if since < ts <= until:
                    out.append(ts)
        d += timedelta(days=1)
    return sorted(out)


def audit_yml_expected_shifts(since: datetime, until: datetime) -> list[datetime]:
    """audit.yml 一班：交易日 23:20（Asia/Taipei），對照 cron `20 15 * * 1-5`。

    2026-09-17（總司令裁示【停擺】查核追加）：AlphaDataAudit 原本沒被納入
    2026-09-16那次班次數轉換（原裁示只點名market.yml/quotes.yml/
    news_events.yml），仍停留在「間隔1440分×3=3天」判準，導致這次
    data_audit.py 因 TWSE_COMPANY ImportError 連續兩個交易日（09-16/09-17）
    跑不出任何結果時，舊判準要等到第3天才會亮燈——這正是總司令這次抓到
    的落差。補上這個 profile，跟其他三支workflow用同一套機制、同一個
    模組，不是另外發明一套。
    """
    out: list[datetime] = []
    if since is None or until is None or since >= until:
        return out
    d = since.date() - timedelta(days=1)
    end_d = until.date() + timedelta(days=1)
    while d <= end_d:
        if is_tw_trading_day(d):
            ts = _tp(d, 23, 20)
            if since < ts <= until:
                out.append(ts)
        d += timedelta(days=1)
    return sorted(out)


_ALL_10MIN = {0, 10, 20, 30, 40, 50}


def _quotes_yml_expected_minutes(weekday: int, hour: int) -> set[int]:
    """回傳這個 UTC (weekday, hour) 命中哪些10分鐘刻度，直接對照
    `.github/workflows/quotes.yml` 的三段 cron（原始寫的是 UTC，這裡不做
    時區換算，比對完再轉回台北時間，避免換算出錯）。
    weekday 用 python `datetime.weekday()`（0=週一...6=週日）。
    """
    minutes: set[int] = set()
    if weekday in (0, 1, 2, 3, 4):  # cron dow 1-5＝週一~五
        if hour in (1, 2, 3, 4):
            minutes |= _ALL_10MIN
        if hour == 5:
            minutes |= {0, 10, 20, 30}
        if 8 <= hour <= 23:
            minutes |= _ALL_10MIN
    if weekday in (1, 2, 3, 4, 5):  # cron dow 2-6＝週二~六
        if hour in (0, 1):
            minutes |= _ALL_10MIN
    return minutes


def quotes_yml_expected_shifts(since: datetime, until: datetime) -> list[datetime]:
    """quotes.yml：每10分鐘一班，落在三段cron窗口內才算應跑（窗外的空檔，
    包含台股盤中結束到美股開盤前約2小時的已知空窗，本來就不會被算進來，
    不需要另外用 window_hours 排除）。"""
    out: list[datetime] = []
    if since is None or until is None or since >= until:
        return out
    since_utc = since.astimezone(UTC)
    until_utc = until.astimezone(UTC)
    cur = since_utc.replace(second=0, microsecond=0)
    cur -= timedelta(minutes=cur.minute % 10)
    while cur <= until_utc:
        if cur > since_utc and cur.minute in _quotes_yml_expected_minutes(cur.weekday(), cur.hour):
            out.append(cur.astimezone(TZ))
        cur += timedelta(minutes=10)
    return out


def news_events_yml_expected_shifts(since: datetime, until: datetime) -> list[datetime]:
    """news_events.yml：cron `*/30 * * * *`，全天候每30分鐘一班，不分平日/
    假日/時段——沒有任何calendar gating需要做。"""
    out: list[datetime] = []
    if since is None or until is None or since >= until:
        return out
    since_utc = since.astimezone(UTC)
    until_utc = until.astimezone(UTC)
    cur = since_utc.replace(second=0, microsecond=0)
    cur -= timedelta(minutes=cur.minute % 30)
    while cur <= until_utc:
        if cur > since_utc:
            out.append(cur.astimezone(TZ))
        cur += timedelta(minutes=30)
    return out


EXPECTED_SHIFT_FUNCS = {
    "market_yml": market_yml_expected_shifts,
    "quotes_yml": quotes_yml_expected_shifts,
    "news_events_yml": news_events_yml_expected_shifts,
    "audit_yml": audit_yml_expected_shifts,
}


def count_missed_shifts(shift_source: str, last_output: datetime | None,
                         now: datetime) -> tuple[int, list[str]]:
    """回傳 (last_output 到 now 之間，理應要跑但目前沒有新產出的班次數,
    這些班次時間字串列表)。shift_source 不認得或 last_output 是 None（讀不到
    上次產出時間）都回 (0, [])——沒有基準點就不能算「錯過幾班」，交給呼叫端
    的既有 unknown/missing 分支處理，不在這裡假裝算得出來。"""
    fn = EXPECTED_SHIFT_FUNCS.get(shift_source)
    if fn is None or last_output is None:
        return 0, []
    shifts = fn(last_output, now)
    return len(shifts), [s.strftime("%Y-%m-%d %H:%M") for s in shifts]


def _replay_2026_09_outage() -> int:
    """回放2026-09-16總司令裁示【驗收】描述的31小時停擺，驗證新判準會在
    「第2個班次」就亮燈（不是要等到31小時後才發現）。

    時間軸依裁示原文：最後一次成功產出約在 2026-09-15 05:30 台北（對應
    09-14這個交易日的第3班，cron `30 21 * * 1-5` 在09-14 UTC 21:30觸發）；
    之後 09-15 17:00／18:30、09-16 05:30 三個班次全部沒有產出。
    """
    last_output = _tp(date(2026, 9, 15), 5, 30)
    checkpoints = [
        ("09-15 17:00（第1班錯過）", _tp(date(2026, 9, 15), 17, 0), 1),
        ("09-15 18:30（第2班錯過，裁示要求這裡就要亮燈）", _tp(date(2026, 9, 15), 18, 30), 2),
        ("09-16 05:30（第3班錯過，即總司令發現時的31小時停擺點）", _tp(date(2026, 9, 16), 5, 30), 3),
    ]
    print("=" * 70)
    print("  回放測試：market.yml 31小時停擺（09-15 05:30 之後）")
    print("=" * 70)
    ok = True
    for label, now, expect_n in checkpoints:
        n, shift_labels = count_missed_shifts("market_yml", last_output, now)
        alarm = n >= 2
        status = "✓ 亮燈" if alarm else "－ 未亮燈"
        print(f"  {label}：錯過班次數={n}（應為{expect_n}）　{status}")
        for s in shift_labels:
            print(f"      └ {s}")
        if n != expect_n:
            ok = False
            print(f"      ⚠ 錯過班次數與預期不符（預期{expect_n}，實際{n}）")
    print()
    if ok:
        print("  ✓ 驗證通過：09-15 18:30（第2班）錯過數達到2，會亮燈——"
              "比舊判準（間隔1440分×3=3天）快非常多（3天≈4320分 vs 現在1.5小時內就亮）。")
        return 0
    print("  ✗ 驗證未通過，見上方 ⚠ 標記")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay-2026-09-outage", action="store_true",
                     help="回放09-15/09-16 market.yml 31小時停擺，驗證第2班亮燈")
    a = ap.parse_args()
    if a.replay_2026_09_outage:
        return _replay_2026_09_outage()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
