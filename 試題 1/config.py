import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# 載入 .env 檔案中的環境變數
load_dotenv()

# 資料庫連線參數設定 (帳密與先前專案相同，資料庫改為 cathay_exam)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    # 預設值改成通用的假資料或提示字串
    "user": os.getenv("DB_USER", "root"), 
    "password": os.getenv("DB_PASSWORD", "default_password"),
    "database": os.getenv("DB_NAME", "cathay_exam"),
    "charset": "utf8mb4"
}

def get_db_engine():
    """
    建立並回傳 SQLAlchemy 連線引擎，
    供後續 Pandas (爬蟲) 與 API 讀寫資料庫使用。
    """
    db_url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
    )
    
    # echo=False 代表不印出底層執行的 SQL 語法，若想除錯可改為 True
    engine = create_engine(db_url, echo=False)
    return engine