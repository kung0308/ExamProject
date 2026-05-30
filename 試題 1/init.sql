-- 建立資料庫
CREATE DATABASE IF NOT EXISTS cathay_exam CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 切換至該資料庫
USE cathay_exam;

-- 建立存放門牌資料的表單
CREATE TABLE IF NOT EXISTS address_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city VARCHAR(10) DEFAULT '台北市',
    district VARCHAR(20) NOT NULL,
    village VARCHAR(20),
    neighborhood VARCHAR(10),
    address VARCHAR(255) NOT NULL,
    compile_date VARCHAR(20),
    compile_type VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;