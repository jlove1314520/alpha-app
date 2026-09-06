# 即時伺服器對外公開後的防線（連線二／連線三，2026-09-06）

服務現在經 Tailscale Funnel 公開在網際網路上。這份文件說明目前有哪些防線、
怎麼查看狀態、以及 token 什麼時候該換。

原則是總司令定的三句話：**縮小面積、限總量、看得見**。不加 WAF、不加 VPN。

---

## 一、縮小面積

| 措施 | 現況 |
|---|---|
| uvicorn 綁定 | `127.0.0.1`（Funnel 由**本機的 tailscaled** 轉入，不需要對區網開） |
| 區網直連 | **不通**（`http://192.168.3.241:8001` 連不到，這是預期行為） |
| 互動文件 | `/docs`、`/redoc`、`/openapi.json` 全部 404 |
| 免 token 端點 | 三個：`/health`（只回 `{ok, ts}`）、`/ca.crt`、`/whoami`（只回呼叫端自己的網段與 UA 摘要） |
| `/health` 細節 | `build`、`uptime_sec`、`shioaji_connected`、`stale_process` 等**要帶 token 才回** |

**為什麼 `/health` 要分層**：公開之後，連 build sha 都算情報——它讓人知道跑的是哪一版
程式碼，可以拿去對已知漏洞；uptime 洩漏重啟節奏；`shioaji_connected` 洩漏交易作息。
掃描器不需要知道這些。分層之後兩件事都成立：任何人都能確認「伺服器活著」，
只有自己人看得到細節。

**關於 `X-Forwarded-For` 的信任前提**：伺服器只綁 loopback，所以連線來源必定是本機的
tailscaled，XFF 也只可能由它填，外部無法直接連進來偽造。這個前提由程式自己守著：
只要出現非 loopback 的連線來源就會在 log 記一次
`[security] ⚠ 非 loopback 連線來源 …`，不會安靜地繼續信任 XFF。

> 實作細節（踩過才知道）：uvicorn 預設 `proxy_headers=True`，會自動拿 XFF 覆寫
> `request.client`，結果就是**永遠看不到真正的連線來源**，上面那道警告一次都不會響。
> 已改成 `proxy_headers=False`，XFF 由程式自己讀，兩件事才分得開。

---

## 二、限總量

| 限制 | 值 | 超過時 |
|---|---|---|
| 每 IP 每分鐘總請求（含 200） | 120 | 429 ＋ log |
| 每 IP 每分鐘驗證失敗 | 20 | 封鎖 10 分鐘 ＋ log |
| SSE 同時連線 | 10 | 429 |
| uvicorn 同時連線 | 50 | 排隊 |
| uvicorn 閒置連線壽命 | 15 秒 | 關閉 |

**正常使用離上限有多遠**（實測）：一次冷啟動加切三個分頁，約 30 秒內打 18 次。
上限是每分鐘 120，用掉大約 15%。

**已知的邊界**：自選股每一檔在載入時會各打一次 `/live/kbars`。自選股超過約 100 檔時，
一次冷啟動就可能逼近每分鐘 120 的上限。伺服器端對 kbars 有 60 秒快取，所以重複載入
不會再打 Shioaji，但**請求數仍然會計入限額**。真的養到那麼多檔時，要嘛改成批次端點，
要嘛把上限往上調——不要靠運氣。

---

## 三、看得見

帶 token 打 `GET /security`，或直接看 App 設定頁的「安全」小卡：

- 過去 24 小時的外部請求數與來源網段數
- 驗證失敗（401）次數
- 被限速擋下（429）次數
- 目前封鎖中的 IP 數
- 串流連線數 / 上限
- 最近 10 筆被擋下的路徑

**來源 IP 只顯示到 /24 網段**：看得出是不是同一批來源就夠判斷了，留完整位址對排查
沒有多大幫助，卻讓這份摘要本身變成敏感資料。

> 開放第一天的實際觀察：Funnel 開通不到一分鐘，就出現兩個不同的外部 IP 在掃描，
> 其中一個在打 `/xmlrpc.php?rsd`（典型的 WordPress 漏洞掃描）。這不是有人針對我們，
> 是網際網路的常態背景噪音——但它證明了「先做硬規則再開公開」的順序是必要的。

---

## 四、token 什麼時候該換

**換法**：
```
python research/rotate_live_token.py          # 換新並印出
python research/rotate_live_token.py --show   # 只看目前的，不換
```

換完舊 token 立即失效，腳本會自動終止伺服器行程，排程會在 1 分鐘內用新 token
重新啟動。手機要到 App 設定頁重貼新 token 才連得上。

**該換的時機**：
- 手機遺失或被別人拿走（token 存在手機的 localStorage 裡）
- token 貼進截圖、訊息、或任何公開的地方
- 給過別人看，或曾經在別人的裝置上登入過
- `/security` 的 401 次數異常升高（代表有人在猜）
- 定期輪替：建議每季一次

**換完要確認**：手機按「測試連線」看到「③ 連線成功」才算完成；
其他有貼過舊 token 的裝置也要一起換，否則會一直 401，反而觸發封鎖。

---

## 五、相依套件的更新節奏

`research/requirements-live.txt` 鎖住版本。
`scripts/check_security_updates.py` 每週一 08:00 由排程 `AlphaDepCheck` 執行，
查 PyPI 官方 API 比對有沒有新版，**只回報不自動升級**，結果寫進
`data/dependency_status.json`。

不自動升級的理由：這是常駐對外服務，自動升級等於在沒人看著的時候換掉地基。
要升級就照 `CLAUDE.md`「七之二、常駐服務發布紀律」四步驗過：
重啟 → 比對 build sha → OPTIONS 預檢 → `stale_process=false`。

---

## 六、備援

Cloudflare Tunnel 那一套完整保留（`docs/cloudflare_tunnel_setup.md`、
`cloudflared/config.example.yml`）。Funnel 的頻寬或穩定性哪天不夠用，
照那份買網域切過去即可，記得把啟動器的 `ALPHA_LIVE_SERVER_HTTPS` 改回 `"1"`。
