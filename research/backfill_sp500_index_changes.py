"""`HYPOTHESIS_QUEUE.md` #51-US 資料回補（2026-09-09）。

跟`backfill_material_news.py`同一種「可重複呼叫、有界批次、快取檔案
本身就是完成紀錄」設計，適用於`sp500_index_changes_client.py`
（`press.spglobal.com`分類列表`s=2429`，一次一頁50篇，逐頁掃描直到
遇到真正的空頁為止；每頁裡標題符合`is_index_change_title()`的文章
再逐篇解析）。

範圍：offset 0 起、每頁50篇，實測首頁分頁連結給出`o=3680`為最後一頁
（約3,680篇同類新聞稿，74頁），本腳本以「連續遇到空頁」為停止條件
（不寫死74這個數字，避免之後新聞稿增加就漏掃），另加一個遠高於已知
範圍的`MAX_OFFSET`安全網防止端點行為異常時無限迴圈。

用法：`python backfill_sp500_index_changes.py --batch-size 30`
（batch-size 以「頁」為單位計數重度限速對象；已快取的頁與文章不佔
批次額度、不觸發HTTP。）
"""
from __future__ import annotations

import argparse
import time

from sp500_index_changes_client import (
    DATA_DIR,
    DEFAULT_PAGE_SIZE,
    _article_slug,
    fetch_and_parse_article,
    fetch_listing_page,
    is_index_change_title,
)

MAX_OFFSET = 20000  # 安全網：已知範圍約3,680篇/74頁，遠高於此不應發生
SLEEP_BETWEEN_CALLS = 1.5  # press.spglobal.com無公開速率上限文件，沿用保守節流精神


def _listing_cached(offset: int, page_size: int) -> bool:
    return (DATA_DIR / f"LISTING_o{offset:05d}_l{page_size:03d}.parquet").exists()


def backfill(batch_size: int = 30, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    offset = 0
    pages_attempted = 0
    pages_new = 0
    articles_new = 0
    articles_matched_total = 0
    consecutive_empty = 0

    while offset <= MAX_OFFSET:
        was_cached = _listing_cached(offset, page_size)
        page_df = fetch_listing_page(offset, page_size=page_size)
        if not was_cached:
            pages_attempted += 1
            pages_new += 1
            time.sleep(SLEEP_BETWEEN_CALLS)

        if page_df.empty:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print(f"連續2頁（offset={offset - page_size}, {offset}）皆空，判定已到列表末端，停止")
                break
        else:
            consecutive_empty = 0
            matched = page_df[page_df["title"].apply(is_index_change_title)]
            articles_matched_total += len(matched)
            for _, row in matched.iterrows():
                art_path_cached = (DATA_DIR / f"ARTICLE_{_article_slug(row['link'])}.parquet").exists()
                fetch_and_parse_article(row["link"], title=row["title"], article_date=row.get("date", ""))
                if not art_path_cached:
                    articles_new += 1
                    time.sleep(SLEEP_BETWEEN_CALLS)

        if pages_attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 個新頁面，停止（offset目前={offset}）")
            break

        offset += page_size

    total_listing = len(list(DATA_DIR.glob("LISTING_*.parquet")))
    total_articles = len(list(DATA_DIR.glob("ARTICLE_*.parquet")))
    print(f"\n本批次結束：新抓 {pages_new} 個列表頁，符合關鍵字 {articles_matched_total} 篇，"
          f"新抓文章 {articles_new} 篇")
    print(f"累積已快取：列表頁 {total_listing}、文章 {total_articles}")
    return {
        "pages_new": pages_new,
        "articles_matched_total": articles_matched_total,
        "articles_new": articles_new,
        "total_listing_cached": total_listing,
        "total_articles_cached": total_articles,
        "stopped_at_offset": offset,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    args = parser.parse_args()
    backfill(batch_size=args.batch_size, page_size=args.page_size)
