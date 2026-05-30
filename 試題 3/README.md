# 試題 3：建置 Log 收集器與 Discord 異常通報 (PLG Stack)

本專案採用輕量、現代化的 **PLG Stack (Promtail + Loki + Grafana)** 作為集中式日誌 (Log) 管理平台，打破傳統架構沉重的資源消耗。系統無縫整合 **【試題 1：網路爬蟲】** 與 **【試題 2：FastAPI】**，透過動態監聽本地日誌檔，結合 **Discord Webhook**。當爬蟲崩潰 (出現 `ERROR`) 或 API 查詢無資料 (出現 `查無資料`) 時，系統將於 **60 秒內** 自動推播精美的告警訊息至開發團隊頻道，建構無人值守的自動化維運環境。

---

## 💡 系統架構與數據流設計

本監控平台採用解耦架構，各組件職責明確，具備極高的水平擴展性：

1. **應用層 (Apps)**：
   * **【試題 1 爬蟲】** 執行時自動輸出日誌至 `試題 1/scraper_execution.log`。
   * **【試題 2 API】** 執行時自動輸出日誌至 `試題 2/api_execution.log`。
2. **傳輸層 (Promtail - Log Agent)**：
   * 以背景守護進程 (Daemon) 形式運行，掛載並即時監聽上述兩份 `.log` 檔案的變化。
   * 當發現新日誌行時，自動打上結構化標籤（如 `job="scraper_logs"` 或 `job="api_logs"`）並推送至 Loki。
3. **儲存層 (Loki - Log Database)**：
   * 由 Grafana 官方開發的「非全文索引」日誌資料庫。
   * 僅針對 Promtail 帶來的標籤 (Labels) 建立索引，日誌主體以壓縮區塊儲存，記憶體佔用極低。
4. **視覺化與告警層 (Grafana - Dashboard & Alerting)**：
   * **Explore 介面**：提供強大的 LogQL 語法，供工程師快速檢索跨服務的歷史日誌。
   * **Alert 引擎**：每 60 秒執行一次聚合計算。當特定關鍵字觸發閾值時，透過 Contact Point 向外發送 Webhook 請求。

```text
+-----------------------+      +------------------+      +--------------+      +-----------------+      +-----------------+
| 試題 1: Scraper Log   | ---> |  Promtail Agent  | ---> |  Loki DB     | ---> | Grafana Alert   | ---> | Discord Channel |
| 試題 2: FastAPI Log   |      |  (Label Tagging) |      | (Log Storage)|      | (LogQL Engine)  |      | (Instant Push)  |
+-----------------------+      +------------------+      +--------------+      +-----------------+      +-----------------+
🛠️ 環境前置要求
在開始部署前，請確保您的開發機已安裝以下基礎設施：

Windows 10 / 11 (建議啟用 WSL2 核心)

Docker Desktop >= v4.20.0

Python 3.11+ 且配置有專案虛擬環境 (.venv)

📦 基礎設施配置檔案參考
為了實現完全復刻，以下為本專案的核心設定檔架構（皆已放置於 試題 3/ 資料夾下）：

1. docker-compose.yml
YAML
version: "3.8"

networks:
  monitor-network:
    driver: bridge

services:
  loki:
    image: grafana/loki:latest
    container_name: loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitor-network

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    volumes:
      # 關鍵：將本機的試題1與試題2日誌目錄掛載進容器中，以便即時監控
      - /var/log:/var/log
      - C:/ExamProject/試題 1:/mnt/logs/scraper:ro
      - C:/ExamProject/試題 2:/mnt/logs/api:ro
      - ./promtail-config.yaml:/etc/promtail/config.yaml
    command: -config.file=/etc/promtail/config.yaml
    networks:
      - monitor-network
    depends_on:
      - loki

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - monitor-network
    depends_on:
      - loki
2. promtail-config.yaml
YAML
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: scraper_service
    static_configs:
      - targets:
          - localhost
        labels:
          job: scraper_logs
          __path__: /mnt/logs/scraper/scraper_execution.log

  - job_name: api_service
    static_configs:
      - targets:
          - localhost
        labels:
          job: api_logs
          __path__: /mnt/logs/api/api_execution.log
🚀 部署與執行步驟
Step 1: 取得 Discord Webhook URL
為了使告警引擎能夠正常通報，必須先配置接收端點：

開啟 Discord，進入您管理的伺服器，或點擊左側 + 建立全新伺服器。

在任意文字頻道（例如 #門牌系統告警）右側點擊 ⚙️ 編輯頻道。

切換至 整合 (Integrations) 頁籤 -> 點擊 建立 Webhook (Webhooks)。

將其命名為 戶政門牌監控中心，並點擊 複製 Webhook 網址 保存至剪貼簿。

Step 2: 使用自動化管理工具啟動平台
專案隨附 manage_monitor.bat 批次檔，免去手動輸入冗長路徑指令。對該檔案點擊兩下執行，並在選單中輸入 1（啟動監控平台）。
該工具會在背景執行 docker compose up -d，同時喚醒 Loki、Promtail 與 Grafana 容器。

Step 3: 登入 Grafana 與綁定 Loki 資料源
開啟瀏覽器進入首頁：👉 http://localhost:3000

在登入介面輸入預設憑證：

Email or username: admin

Password: admin
(首次登入時，系統會詢問是否修改新密碼，建議點擊下方 Skip 跳過以維持測試一致性。)

進入左側選單的 Connections -> Data sources。

點選右上角藍色按鈕 Add data source，並在搜尋框輸入並選擇 Loki。

在 HTTP -> URL 欄位填入 Docker 內網位址：http://loki:3100。

直接滑動至畫面的最下方，點擊 Save & test。

當畫面上方出現綠色打勾提示 Data source connected and labels found. 即代表連線成功。

Step 4: 設定 Discord 通報端點 (Contact Point)
點擊左側選單的 🔔 Alerting -> Contact points。

點擊藍色按鈕 + Add contact point。

Name (名稱) 填入 Discord Alert。

Integration (整合類型) 下拉選單切換至 Discord。

Webhook URL 貼上您在 Step 1 中複製的 Discord 連線網址。

點擊畫面右上角的 Test 按鈕 -> 點選 Send test notification。

確認機制：檢查您的 Discord 頻道是否「叮咚」響起並收到來自 Grafana 的測試字串。

點擊最下方的 Save contact point 儲存。

🚨 異常規則設定 (Alert Rules)
請點選左側選單 🔔 Alerting -> Alert rules，點擊 + New alert rule 依序建立兩條生產級監控規則：

規則一：監控【試題 1】爬蟲異常
Rule name: 爬蟲執行嚴重錯誤告警

Step 1 (Define query):

資料源下拉選單指定 Loki。

LogQL 輸入：count_over_time({job="scraper_logs"} |= "ERROR" [1m])

條件（Condition）配置：選擇當次數 Is above 0 時觸發（代表 1 分鐘內只要出現一次錯誤便通報）。

Step 2 (Evaluation):

Folder: 建立一個名為 System Alerts 的資料夾。

Evaluation group: 建立名為 1m-scan 的群組，間隔（Interval）填入 1m。

Pending period: 填入 0s（重要！移除等待期，確保即時通報）。

Step 3 (Configure notifications):

在 Contact point 中指定剛剛建立的 Discord Alert。

Annotations (摘要資訊):

填寫：⚠️ 戶政司門牌爬蟲發生崩潰或嚴重錯誤，請儘速重啟爬蟲！

規則二：監控【試題 2】API 查詢為空
Rule name: 門牌API回傳空值告警

Step 1 (Define query):

資料源下拉選單指定 Loki。

LogQL 輸入：count_over_time({job="api_logs"} |= "查無資料" [1m])

條件（Condition）配置：選擇當次數 Is above 0 時觸發。

Step 2 & 3 設定: 同規則一，歸類於 System Alerts，並指定 Discord Alert 為 Contact point。

Annotations (摘要資訊):

填寫：⚠️ 門牌 API 查詢回傳空值，條件可能查無此區，或資料庫有漏爬、未同步現象。

儲存規則後，全自動化監控便正式上線。

💡 實戰運維與故障排除 (Troubleshooting)
1. 忘記 Grafana 管理員密碼，如何強制重設？
若先前修改過密碼且遺忘，由於本機 Docker 容器未配置真實 SMTP 郵件伺服器，將無法透過 Email 收取重設連結。請使用隨附的 manage_monitor.bat 工具，輸入選單選項 4（重設 Grafana 密碼）。
該工具會深入 Docker 底層容器執行以下指令：

Bash
docker exec -it grafana grafana-cli admin reset-admin-password admin
指令完成後，Grafana 管理員密碼將被強制覆蓋回初始密碼 admin。請隨後重啟 Grafana 容器並重新登入。

2. 生產環境避坑：Uvicorn 「無限重啟重載」迴圈
在開發 FastAPI 階段，若啟用熱重載功能（reload=True），當 API 觸發異常並將「查無資料」寫入 api_execution.log 時，Uvicorn 檢測到目錄下的檔案發生變更，會誤判為程式碼更新，大喊 1 change detected 並強行重啟服務。此重啟動作又會觸發日誌狀態變更，導致 API 陷入發瘋洗頻的無限重啟迴圈。

解決方案：
在 API 程式碼最下方的進入點，正式環境下必須將熱重載關閉（reload=False）：

Python
if __name__ == "__main__":
    # 正式部署必須將 reload 設為 False，防止 Log 寫入引發無限重啟
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
3. Grafana Explore 介面顯示 「No Logs Found」
若檔案內有日誌，但 Grafana 卻撈不到，通常是因為 Docker 在 Windows 下的檔案掛載通知脫鉤（Docker 容器在啟動時，日誌檔尚未被無中生有建立出來，導致 Promtail 沒有掃描到該檔案控制權）。

解決方案：
對著 manage_monitor.bat 點擊兩下：

輸入 2 徹底關閉並移除容器群組。

輸入 1 重新背景編排啟動。
這將會強制 Promtail 破壞舊有的位置書籤（Positions），並強制從檔案的第 1 行開始重新將日誌搬移灌入 Loki 資料庫中。