# Cloudflare 網域上線手冊（**目前為備援方案，2026-09-06 起主線改用 Tailscale Funnel**）

> **狀態說明（連線二.5）**：2026-09-06 已改用 Tailscale Funnel 對外提供服務——免費、
> 公司手機不必安裝任何憑證、也不必開 WARP，TLS 由 Tailscale 以 Let's Encrypt 憑證終結。
> 這份 Cloudflare 手冊**保留不刪**，作為備援：如果哪天 Funnel 的頻寬上限或穩定性不夠用，
> 照這份買網域走 Cloudflare Tunnel 即可，內容仍然有效（`cloudflared/config.example.yml`
> 也保留著）。切回去時記得把啟動器的 `ALPHA_LIVE_SERVER_HTTPS` 改回 `"1"`。

這份是給總司令今晚照著做的操作說明。伺服器端與 App 端該改的都已經改好並上線，
剩下的是 Cloudflare 後台的設定。

---

## 0. 先講一個會擋住整件事的關鍵發現

**如果 App 繼續留在 `jlove1314520.github.io`，用 Cloudflare Access 的瀏覽器登入
（cookie）驗證，在 iPhone 上會失敗。**

原因是兩層：

1. **Access 的 preflight 一定會 403。** App 送出的請求帶著 `X-Alpha-Local-Token`
   這個自訂標頭，瀏覽器因此會先送一個 `OPTIONS` 預檢請求。而瀏覽器**依設計不會在
   OPTIONS 請求裡帶 cookie**，Access 收到沒有 `CF_Authorization` 的請求就回 403，
   整個跨來源交握直接失敗。這一點 Cloudflare 官方文件明講，不是設定錯誤。
   → 解法：在 Access 應用程式裡打開 **Bypass options requests to origin**。
2. **iOS Safari 會擋跨站 cookie。** `github.io` 與 `你的網域.com` 是兩個不同的
   註冊網域，Safari 的追蹤預防預設封鎖第三方 cookie，所以就算前面那關過了，
   `CF_Authorization` 也送不出去。

所以今晚要**先做一個選擇**，兩條路都可行：

| | A：Access 服務權杖（建議） | B：把 App 也搬到 `app.<domain>` |
|---|---|---|
| 驗證方式 | 兩個 HTTP 標頭，完全不用 cookie | 瀏覽器 SSO cookie |
| iPhone 相容 | 沒有 cookie 問題，一定可用 | 同註冊網域，cookie 變同站，可用 |
| 今晚工作量 | Cloudflare 建一組服務權杖，App 設定頁貼上 | 改 GitHub Pages 自訂網域＋DNS＋等憑證簽發 |
| 風險 | 權杖存在手機 localStorage（與現有 X-Alpha-Local-Token 同等級） | 換網址會讓舊書籤/已安裝的 PWA 失效，要重裝 |
| App 端 | **已經寫好，欄位留空就是不啟用** | 需要另外處理 Pages 網域，本輪未動 |

**建議走 A**，今晚就能通；B 當作之後想整併網址時再做（評估見文末第 5 節）。

---

## 1. cloudflared：Public Hostname 與 ingress

設定草稿在 `cloudflared/config.example.yml`。複製成實際設定檔再改：

```
copy cloudflared\config.example.yml %USERPROFILE%\.cloudflared\config.yml
```

把 `<TUNNEL_UUID>` 與 `<domain>` 換成真值，然後重啟 cloudflared 服務。

核心那段是：

```yaml
ingress:
  - hostname: live.<domain>
    service: https://localhost:8001
    originRequest:
      caPool: C:\alpha\alpha-app\secrets\alpha-ca.pem
      originServerName: localhost
      keepAliveTimeout: 180s
  - service: http_status:404
```

### 為什麼不是 `noTLSVerify: true`，也不另開 HTTP 監聽

總司令給的兩個選項我都評估過，最後選了第三條、也是最好的一條：**讓 cloudflared
信任我們自己的 CA**。

- **另開一個只給 cloudflared 用的 HTTP 監聽**，在這支伺服器上不是小改動。
  `alpha_live_server.py` 同一個行程還綁著 tick ingress 的 UDP socket
  （`127.0.0.1:8002`），再起第二個 uvicorn 行程會在那個 port 上 bind 失敗；要在
  同一行程內同時聽兩個 port 得改寫啟動流程。為了一條 loopback 連線去動啟動流程，
  風險大於收益。
- **`noTLSVerify: true`** 可以動，但它的意思是「這一段不驗任何憑證」。我們已經有
  自己的 CA（`secrets/alpha-ca.pem`），伺服器憑證的 SAN 本來就含 `DNS:localhost`，
  用 `caPool` 指過去就是完整驗證，沒有理由退回不驗。
- **`caPool` 對伺服器零改動**：現在跑的自簽 HTTPS（`0.0.0.0:8001`）原封不動，
  手機在區網直連 `192.168.3.241:8001` 的既有用法也完全不受影響。

如果哪天 caPool 出問題（例如換憑證忘了同步），把那兩行註解掉改成
`noTLSVerify: true` 就能先恢復服務。那是備援，不是預設。

`keepAliveTimeout: 180s` 是給 SSE（`/live/stream`）用的。那是長連線，預設的閒置
逾時會把它砍掉；伺服器每 15 秒送一次 keepalive，180 秒有足夠餘裕。

---

## 2. Access application 的 CORS 設定要怎麼填

在 Zero Trust 後台 → Access → Applications → 你的 `live.<domain>` 應用程式 →
Settings，逐項填：

| 欄位 | 填什麼 | 為什麼 |
|---|---|---|
| Access-Control-Allow-Origins | `https://jlove1314520.github.io` | **必須是精確來源**。只要開了 Allow credentials，瀏覽器就禁止 `*`，填 `*` 會讓整個請求被擋 |
| Access-Control-Allow-Methods | `GET, OPTIONS` | 這支伺服器只有 GET 端點 |
| Access-Control-Allow-Headers | `X-Alpha-Local-Token, Content-Type, Accept, Cache-Control` | 與伺服器 `ALLOW_HEADERS` 同一份清單；走服務權杖時再加 `CF-Access-Client-Id, CF-Access-Client-Secret` |
| Access-Control-Allow-Credentials | **開啟** | 走 cookie 路徑時必要；走服務權杖也建議開著，兩者不衝突 |
| Access-Control-Max-Age | `600` | 預檢結果快取十分鐘，減少來回 |
| **Bypass options requests to origin** | **開啟** | 見第 0 節：不開這個，預檢一定 403，什麼都不會通 |
| SameSite Attribute（Advanced settings） | `None` | 走 cookie 路徑時必要；`Lax`/`Strict` 都不會在跨站請求送出 |

**關於 Bypass OPTIONS 的安全影響（誠實揭露）**：打開之後，未經 Access 驗證的
`OPTIONS` 請求會直接到我們的伺服器。實際風險很低——OPTIONS 不回傳任何資料，
Starlette 只回一段 `OK` 加上 CORS 標頭；所有真正的資料端點仍然要同時通過
Access 與 `X-Alpha-Local-Token` 兩道驗證。

---

## 3. 今晚的步驟（走 A：服務權杖）

1. **買網域**，在 Cloudflare 完成 DNS 託管。
2. **Zero Trust → Networks → Tunnels**，在既有 tunnel 上新增 Public Hostname：
   - Subdomain `live`、Domain 你的網域
   - Service：`HTTPS`、URL `localhost:8001`
   - Additional application settings → TLS：
     - Origin Server Name = `localhost`
     - CA Pool 貼上 `secrets/alpha-ca.pem` 的內容（或改用本機 `config.yml`，
       見第 1 節，兩種擇一即可）
3. **Zero Trust → Access → Service Auth → Service Tokens**，建立一組
   `alpha-live`，**Client Secret 只會顯示一次，先複製起來**。
4. **Access → Applications** 新增 Self-hosted 應用程式：
   - Application domain：`live.<domain>`
   - Policy：Action 選 **Service Auth**，Include → Service Token → 選 `alpha-live`
     （這一步很重要，Action 不選 Service Auth 的話 Access 仍然會跳登入頁）
   - 若也想保留自己用瀏覽器登入的能力，再加第二條 Policy：Action `Allow`、
     Include 你的 Email
   - Settings 依第 2 節逐項填好，**Bypass options requests to origin 記得開**
5. **App 設定頁**（手機上開 Alpha → 設定）：
   - 伺服器網址填 `live.<domain>`（不用打 `https://`，App 會自動補上並整理格式，
     存檔後會自動重測連線）
   - Access Client Id / Access Client Secret 兩欄貼上第 3 步的服務權杖
   - 本機權杖那欄維持原本的 `X-Alpha-Local-Token`
6. 按「測試連線」，應該看到即時連線中。

### 走 B（cookie 登入）時的差異

第 3、4 步改成一般的 Email 政策，App 設定頁的兩個 Access 欄位留空，然後
**必須先在手機瀏覽器直接開一次 `https://live.<domain>/health`**，完成 Access 登入、
讓 `CF_Authorization` cookie 種下去，之後 App 的跨來源請求才帶得出去。
這一步不能省——PWA 內的 `fetch` 沒辦法跟著 Access 的登入轉址走完流程。
另外要記得把 SameSite 設成 `None`，且 iPhone 上很可能仍會被 Safari 的跨站 cookie
封鎖，這也是建議走 A 的原因。

---

## 4. 已經改好的部分（不用再動）

- **伺服器 CORS**（`research/alpha_live_server.py`）
  - `allow_origins` 改為明確清單，並可用環境變數 `ALPHA_LIVE_ALLOW_ORIGINS`
    擴充（逗號分隔），網域到手後不用改程式碼
  - 新增 `allow_credentials=True`
  - `allow_headers` 由 `*` 改為明確清單，與 Access 後台填的那份一致
  - `/health` 現在會回傳目前生效的 CORS 設定，切網域時可以直接看伺服器認哪些來源
- **App**（`index.html`）
  - 伺服器網址欄位支援網域形式，會自動補 `https://`、去掉結尾斜線與多餘路徑
    （私有 IP 例外，補 `http://` 以維持區網直連）
  - 換網址存檔後自動重新測試連線
  - `liveFetch` 與 SSE 都加上 `credentials: 'include'`
  - 設定頁新增 Access Client Id / Secret 兩個選填欄位，留空即完全不啟用

---

## 5. 加分項評估：把 App 也放到 `app.<domain>`（先評估，未執行）

GitHub Pages 支援免費自訂網域與自動 HTTPS，技術上完全可行。

**好處**

- `app.<domain>` 與 `live.<domain>` 屬同一註冊網域，Access cookie 變成同站，
  iOS Safari 的跨站 cookie 封鎖不再是問題
- CORS 從跨站變成同註冊網域的跨子網域，設定更單純
- 網址好記，之後對外展示也體面

**代價與風險**

- 換網址後舊的 `jlove1314520.github.io` 書籤與**已安裝到手機桌面的 PWA 會失效**，
  要重新安裝；localStorage 是綁在來源上的，**自選股與設定會全部不見**
  （這一點在 `/settings` 多裝置同步做完之後就不再是問題，所以順序上建議
  先做 `/settings`，再考慮搬家）
- Service Worker 快取也會跟著換來源重新建立，第一次載入會慢一點
- DNS 與憑證簽發要等，不適合在今晚跟網域切換一起做

**建議**：今晚先不要動。等 `/settings` 多裝置同步上線、設定不再綁在單一瀏覽器
之後再搬，那時候搬家的成本才是可接受的。

---

## 6. 驗收方式

網域切好後，在電腦上依序確認：

```bash
# 1. 沒帶任何憑證 → 應該被 Access 擋下（403 或轉址到登入頁）
curl -i https://live.<domain>/health

# 2. 帶服務權杖 → 應該回 200 與 JSON
curl -i https://live.<domain>/health ^
  -H "CF-Access-Client-Id: <CLIENT_ID>" ^
  -H "CF-Access-Client-Secret: <CLIENT_SECRET>"

# 3. 預檢請求 → 開了 Bypass OPTIONS 之後應該回 200，且帶精確的 Allow-Origin
curl -i -X OPTIONS https://live.<domain>/live/quotes ^
  -H "Origin: https://jlove1314520.github.io" ^
  -H "Access-Control-Request-Method: GET" ^
  -H "Access-Control-Request-Headers: x-alpha-local-token"
```

第 3 步的回應必須同時看到這兩行，缺一個 App 就會連不上：

```
Access-Control-Allow-Origin: https://jlove1314520.github.io
Access-Control-Allow-Credentials: true
```

---

## 參考

- [Cloudflare One：Access 應用程式的 CORS 設定](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/)
- [Cloudflare One：CF_Authorization cookie 與 SameSite 設定](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/)
- [Cloudflare One：服務權杖](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)
