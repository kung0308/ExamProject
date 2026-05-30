import os
import time
import logging
import pandas as pd
import re
import io
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy import exc, text

# 引入 DB 連線模組
from config import get_db_engine

# ================= 1. Log 監控設定 =================
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("scraper_execution.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 遮蔽 urllib3 與 selenium 底層連線錯誤 (避免 Ctrl+C 時噴出一堆連線拒絕警告)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

def run_scraper():
    logging.info("啟動爬蟲程式，準備連線戶政司網站...")
    
    # ================= 2. 建立防呆機制 =================
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            logging.info("✅ 確認 MySQL 資料庫連線正常！")
    except Exception as e:
        logging.error(f"❌ 資料庫連線失敗，請檢查 Docker 是否啟動。錯誤: {e}")
        return

    # ================= 3. 初始化瀏覽器 =================
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    all_districts_data = [] 

    try:
        url = "https://www.ris.gov.tw/info-doorplate/app/doorplate/main"
        driver.get(url)
        driver.maximize_window()
        wait = WebDriverWait(driver, 10) 
        
        logging.info("網頁載入中，開始執行初始點擊流程...")
        time.sleep(3) 
        
        tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-type='date']")))
        tab.click()
        
        time.sleep(2) 
        tpe_map = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@title, '臺北') or contains(text(), '臺北') or contains(@id, 'taipei')]")))
        driver.execute_script("arguments[0].click();", tpe_map)
        time.sleep(3) 

        # ================= 4. 動態取得所有「鄉鎮市區」選項 =================
        area_dropdown = wait.until(EC.presence_of_element_located((By.ID, "areaCode")))
        select_area = Select(area_dropdown)
        district_options = [opt.text for opt in select_area.options if "請選擇" not in opt.text]
        logging.info(f"📍 找到需爬取的區域共 {len(district_options)} 個: {district_options}")
        logging.info("💡 提示：若需中途退出，請輸入指令 q，程式將為您保存進度並優雅關閉。")

        # ================= 5. 開始迴圈爬取各區 (加入重試與中斷保護) =================
        try:
            quit_program = False
            for dist_name in district_options:
                logging.info(f"\n{'='*40}\n🚀 開始處理: 【{dist_name}】\n{'='*40}")
                
                # --- 新增：針對單一行政區的「重試迴圈」 ---
                while True:
                    area_dropdown = wait.until(EC.presence_of_element_located((By.ID, "areaCode")))
                    Select(area_dropdown).select_by_visible_text(dist_name)
                    
                    driver.execute_script("document.getElementById('sDate').value = '1140901';")
                    driver.execute_script("document.getElementById('eDate').value = '1141130';")
                    
                    kind_dropdown = driver.find_element(By.ID, "registerKind")
                    Select(kind_dropdown).select_by_visible_text("門牌初編")
                    
                    # --- 互動式指令與資料同步驗證防呆 ---
                    skip_district = False
                    while True:
                        print("\n👉 [人工介入要求]:")
                        print(f"1. 請在瀏覽器確認表單是否已切換為【{dist_name}】")
                        print(f"2. 輸入圖形驗證碼並點擊『查詢』。")
                        print("3. 確認下方跑出『查詢結果表格』或跳出『查無資料』後，再來這裡下指令！")
                        print("--------------------------------------------------")
                        print("  [Enter] 直接按下 : 網頁已更新，開始擷取該區資料")
                        print("  [s]     輸入 s   : 跳過抓取此區 (例如已抓過)，前往下一區")
                        print("  [q]     輸入 q   : 停止爬取並儲存退出 (推薦)")
                        print("--------------------------------------------------")
                        
                        user_cmd = input("請輸入指令 (或按 Ctrl+C 結束): ").strip().lower()
                        
                        if user_cmd == 'q':
                            logging.warning("🛑 使用者選擇提前結束 (輸入 q)！已停止爬取剩餘的區域。")
                            quit_program = True
                            break
                        elif user_cmd == 's':
                            logging.info(f"⏭️ 使用者選擇跳過【{dist_name}】。")
                            skip_district = True
                            break
                        elif user_cmd == '':
                            # 驗證網頁內容是否真的已經換成當前目標區域
                            try:
                                # 試抓當前頁面，如果有表格，檢查第一筆資料
                                dfs = pd.read_html(io.StringIO(driver.page_source))
                                if dfs:
                                    df = max(dfs, key=len)
                                    if len(df) > 0 and len(df.columns) > 1:
                                        first_addr = str(df.iloc[0, 1])  # 假設地址在第二欄
                                        if dist_name not in first_addr and "臺北市" in first_addr:
                                            print(f"\n⚠️ 【資料不同步警告】!")
                                            print(f"網頁目前顯示的第一筆資料為：「{first_addr}」")
                                            print(f"這似乎是上一區的資料，不是我們準備抓的【{dist_name}】！")
                                            print("👉 可能原因：您忘記按『查詢』、驗證碼錯誤，或是網頁還沒讀取完。")
                                            print("請在網頁上重新查詢並確認結果後，再按一次 Enter。")
                                            continue  # 回到 while 等待
                            except Exception:
                                # 若無表格 (可能是查無資料)，放行讓後續邏輯處理
                                pass
                            break # 驗證通過，跳出選單 while 迴圈開始抓取
                        else:
                            print("❌ 錯誤指令，請按 Enter、s 或 q")
                    
                    if quit_program:
                        break # 跳出「重試迴圈」
                    
                    if skip_district:
                        break # 跳出「重試迴圈」，進入下一個 dist_name

                    # --- 判斷是否有資料 ---
                    try:
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "sp_1_result-pager")))
                    except Exception:
                        logging.warning(f"⚠️ 查無表格資料或驗證失敗，跳過此區。")
                        break # 該區處理完畢，跳出「重試迴圈」

                    # --- 資料擷取 ---
                    try:
                        total_pages_str = driver.find_element(By.ID, "sp_1_result-pager").text
                        total_pages = int(total_pages_str)
                        logging.info(f"🔍 共有 {total_pages} 頁，準備分頁抓取...")
                    except Exception:
                        logging.warning(f"無法抓取總頁數，預設只抓取第 1 頁。")
                        total_pages = 1

                    dist_dfs = [] 

                    for current_page in range(1, total_pages + 1):
                        logging.info(f"⏳ 正在擷取第 {current_page} / {total_pages} 頁...")
                        
                        html_source = driver.page_source
                        dfs = pd.read_html(io.StringIO(html_source))
                        
                        if not dfs:
                            break
                            
                        df = max(dfs, key=len)
                        dist_dfs.append(df)
                        
                        if current_page < total_pages:
                            try:
                                next_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "ui-icon-seek-next")))
                                driver.execute_script("arguments[0].click();", next_btn)
                                time.sleep(2) 
                            except Exception as e:
                                break

                    if not dist_dfs:
                        break

                    dist_final_df = pd.concat(dist_dfs, ignore_index=True)
                    dist_final_df.dropna(how='all', inplace=True)

                    dist_final_df = dist_final_df.rename(columns={
                        dist_final_df.columns[1]: 'address',
                        dist_final_df.columns[2]: 'compile_date',
                        dist_final_df.columns[3]: 'compile_type'
                    })

                    # =========================================================
                    # 【終極防呆】：防止寫入錯誤行政區，出錯時退回重試迴圈
                    # =========================================================
                    actual_dist = dist_name 
                    is_mismatch = False
                    try:
                        first_addr = str(dist_final_df['address'].iloc[0])
                        match = re.search(r'臺北市(?P<dist>.*?區)', first_addr)
                        if match:
                            actual_dist = match.group('dist')
                            if actual_dist != dist_name:
                                # 若資料真的抓錯了(防線被突破)，拋棄這批資料，並標記需要重試
                                logging.error(f"❌ [嚴重錯誤] 爬下來的資料實為【{actual_dist}】，而非預期的【{dist_name}】！")
                                logging.error("為避免資料庫出現重複/錯誤標籤，將直接拋棄此次擷取的資料。")
                                logging.error(f"🔄 系統將重新回到【{dist_name}】的等待步驟，請重新查詢！")
                                is_mismatch = True
                    except Exception as e:
                        pass 
                    
                    if is_mismatch:
                        continue # 觸發重試！回到重試迴圈的頂部 (重新綁定表單為 dist_name 並等待輸入)

                    def parse_address(addr, current_dist):
                        district, village, neighborhood, clean_addr = current_dist, None, None, addr
                        if pd.isna(addr):
                            return district, village, neighborhood, clean_addr
                        
                        match = re.search(r'臺北市(?P<dist>.*?區)?(?P<vil>.*?里)?(?P<neigh>\d+鄰)?(?P<real_addr>.*)', str(addr))
                        if match:
                            gd = match.groupdict()
                            district = gd.get('dist') or current_dist
                            village = gd.get('vil')
                            neighborhood = gd.get('neigh')
                            clean_addr = gd.get('real_addr')
                        return district, village, neighborhood, clean_addr

                    parsed_data = dist_final_df['address'].apply(lambda x: parse_address(x, actual_dist))
                    dist_final_df['district'] = [x[0] for x in parsed_data]
                    dist_final_df['village'] = [x[1] for x in parsed_data]
                    dist_final_df['neighborhood'] = [x[2] for x in parsed_data]
                    dist_final_df['address'] = [x[3] for x in parsed_data] 
                    dist_final_df['city'] = '台北市'
                    dist_final_df['compile_type'] = '門牌初編'

                    cols_to_insert = ['city', 'district', 'village', 'neighborhood', 'address', 'compile_date', 'compile_type']
                    dist_final_df = dist_final_df[cols_to_insert]
                    
                    all_districts_data.append(dist_final_df)
                    logging.info(f"✅ 【{actual_dist}】擷取完畢，共 {len(dist_final_df)} 筆有效資料。")

                    temp_df = pd.concat(all_districts_data, ignore_index=True)
                    # 存檔前去重，多一層保護
                    temp_df.drop_duplicates(inplace=True)
                    temp_df.to_csv("temp_backup.csv", index=False, encoding='utf-8-sig')

                    # 順利完成該區，跳出「重試迴圈」，進入下個行政區
                    break 

                if quit_program:
                    break # 跳出外層的行政區 for 迴圈

        except KeyboardInterrupt:
            print("\n")
            logging.warning("🛑 [強制中斷] 偵測到 Ctrl+C！已停止爬取剩餘的區域。")
            logging.info("💡 提示：若使用 Ctrl+C 中斷，Chrome 視窗可能無法自動關閉，建議下次使用指令 'q' 結束。")
        except Exception as e:
            logging.error(f"迴圈執行中發生未預期錯誤: {e}")

        # ================= 6. 彙整所有資料並輸出 (CSV + MySQL) =================
        logging.info("💾 系統準備將目前已抓取到的資料匯出並寫入資料庫...")
        if not all_districts_data:
            logging.warning("所有區域皆無資料或爬取失敗，結束程式。")
            return

        final_master_df = pd.concat(all_districts_data, ignore_index=True)
        # 【全域去重防呆】確保合併後絕對沒有重複資料
        final_master_df.drop_duplicates(subset=['city', 'district', 'village', 'neighborhood', 'address', 'compile_date'], inplace=True)
        
        logging.info(f"\n🎉 爬取流程結束！總計蒐集到 {len(final_master_df)} 筆不重複資料。準備寫入檔案與資料庫...")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"ris_data_TPE_{timestamp}.csv"
        final_master_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 已儲存總表 CSV: {csv_filename}")
        
        if os.path.exists("temp_backup.csv"):
            os.remove("temp_backup.csv")

        try:
            logging.info("準備將資料寫入暫存表 (address_records_temp)...")
            final_master_df.to_sql(name='address_records_temp', con=engine, if_exists='replace', index=False)
            
            with engine.begin() as conn:
                # 移除會刪除舊資料的指令 DELETE FROM address_records;
                
                # 採用 LEFT JOIN 過濾比對，確保只插入資料庫沒有的新資料 (防重複)
                conn.execute(text("""
                    INSERT INTO address_records (city, district, village, neighborhood, address, compile_date, compile_type)
                    SELECT t.city, t.district, t.village, t.neighborhood, t.address, t.compile_date, t.compile_type 
                    FROM address_records_temp t
                    LEFT JOIN address_records r 
                        ON t.address = r.address AND t.compile_date = r.compile_date
                    WHERE r.address IS NULL;
                """))
                
                conn.execute(text("DROP TABLE address_records_temp;"))
                
            logging.info("🏆 [資料庫寫入完成] 交易成功！舊資料已保留，新資料也安全寫入並自動去重。")

        except Exception as db_e:
            logging.error(f"❌ 資料庫更新過程發生錯誤。錯誤細節: {db_e}")
            
    except Exception as e:
        logging.error(f"爬蟲執行發生未預期錯誤: {str(e)}")
    finally:
        try:
            # 加入 try-except 防止 driver 被強制關閉時引發連線錯誤阻礙結束
            driver.quit()
            logging.info("瀏覽器已關閉，任務結束。")
        except Exception:
            logging.info("任務結束 (驅動程式可能已被強制中斷，瀏覽器需手動關閉)。")

if __name__ == "__main__":
    try:
        run_scraper()
    except KeyboardInterrupt:
        pass