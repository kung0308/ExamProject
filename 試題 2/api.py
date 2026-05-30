import os
import logging
from fastapi import FastAPI, Query, HTTPException
from sqlalchemy import text
import uvicorn

# 自動將工作目錄切換至本腳本所在的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# ================= 1. Log 監控設定 =================
# 設定 Logging 格式，並同時輸出到終端機與 api_execution.log 檔案中
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("api_execution.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 引入資料庫連線模組 (請確保 config.py 已複製到本資料夾)
from config import get_db_engine

# 初始化 FastAPI 應用程式
app = FastAPI(
    title="戶政司門牌查詢系統 API",
    description="國泰數據架構工程師上機測驗 - 試題 2（FastAPI 實作）\n包含 Log 紀錄與異常告警觸發機制。",
    version="1.0.0"
)

@app.get("/api/address", summary="依縣市與鄉鎮市區查詢門牌初編紀錄", tags=["門牌資料查詢"])
def get_address_records(
    city: str = Query("台北市", description="欲查詢的縣市名稱（例如：台北市）"),
    district: str = Query(..., description="欲查詢的鄉鎮市區（例如：大安區）")
):
    """
    ### 接口說明：
    輸入 `city` (縣市) 與 `district` (鄉鎮市區)，系統將會從 MySQL 資料庫中撈取相對應的門牌初編結構化資料。
    
    ### 安全機制：
    本 API 採用 **參數化查詢 (Parameterized Query)**，100% 防止 SQL 注入 (SQL Injection) 攻擊。
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            # 撰寫嚴謹的 SQL 語法 
            sql_query = text("""
                SELECT city, district, village, neighborhood, address, compile_date, compile_type 
                FROM address_records 
                WHERE city = :city AND district = :district
            """)
            
            # 執行查詢，將 API 收到的參數綁定進去
            result = conn.execute(sql_query, {"city": city, "district": district})
            
            # 將 SQLAlchemy 的查詢結果轉換為 Python 的字典 (Dict) 格式，以便轉為 JSON
            records = [dict(row._mapping) for row in result]
            
            # ================= 2. 異常與監控 Log 寫入 =================
            if len(records) == 0:
                # 觸發 Grafana 警報的關鍵字："查無資料"
                logging.warning(f"⚠️ [API 查詢異常] 條件 '{city} {district}' 查無資料，可能尚未爬取或名稱錯誤。")
            else:
                logging.info(f"✅ [API 查詢成功] 條件 '{city} {district}' 共回傳 {len(records)} 筆資料。")
            
            # 回傳標準化 JSON 格式
            return {
                "status": "success",
                "total_count": len(records),
                "query_conditions": {
                    "city": city,
                    "district": district
                },
                "data": records
            }
            
    except Exception as e:
        # 發生資料庫或程式嚴重錯誤時，記錄 ERROR Log
        logging.error(f"❌ [API 系統錯誤] 資料庫查詢失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"資料庫查詢失敗: {str(e)}")

# 啟動伺服器
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 API 服務啟動成功！")
    print("👉 請打開瀏覽器進入測試網頁: http://127.0.0.1:8000/docs")
    print("="*60 + "\n")
    
    # 啟動本地伺服器
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)