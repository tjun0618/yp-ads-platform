"""
创建广告优化模块所需的数据库表
运行: python -X utf8 create_optimization_tables.py
"""
import mysql.connector

DB = dict(host='localhost', port=3306, user='root', password='admin',
          database='affiliate_marketing', charset='utf8mb4')

TABLES = {

    # 上传的搜索词报告（原始数据）
    'ads_search_term_reports': """
    CREATE TABLE IF NOT EXISTS ads_search_term_reports (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        upload_id    VARCHAR(36) NOT NULL COMMENT '同一批上传共享同一UUID',
        upload_name  VARCHAR(255) COMMENT '上传文件名',
        report_type  ENUM('search_term','keyword_performance','campaign') DEFAULT 'search_term',
        asin         VARCHAR(20)  COMMENT '关联的ASIN（手动指定或自动匹配）',
        campaign_name VARCHAR(255),
        ad_group_name VARCHAR(255),
        search_term  VARCHAR(500) NOT NULL,
        match_type   VARCHAR(50),
        impressions  INT DEFAULT 0,
        clicks       INT DEFAULT 0,
        ctr          FLOAT DEFAULT 0,
        cpc          FLOAT DEFAULT 0,
        cost         FLOAT DEFAULT 0,
        conversions  FLOAT DEFAULT 0,
        conv_rate    FLOAT DEFAULT 0,
        conv_value   FLOAT DEFAULT 0,
        roas         FLOAT DEFAULT 0,
        quality_score INT DEFAULT 0 COMMENT 'Google Ads QS 1-10',
        uploaded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_upload(upload_id),
        INDEX idx_asin(asin),
        INDEX idx_search_term(search_term(100))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # AI 生成的优化建议
    'ads_optimization_suggestions': """
    CREATE TABLE IF NOT EXISTS ads_optimization_suggestions (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        upload_id    VARCHAR(36) NOT NULL COMMENT '对应哪次上传',
        asin         VARCHAR(20),
        plan_id      INT COMMENT '关联 ads_plans.id',
        suggestion_type ENUM(
            'add_negative',        -- 建议加否定关键词
            'increase_bid',        -- 建议提升出价
            'expand_match',        -- 建议扩展匹配类型
            'new_ad_group',        -- 建议新建Ad Group
            'rewrite_headline',    -- 建议改写标题
            'rewrite_description', -- 建议改写描述
            'pause_keyword',       -- 建议暂停关键词
            'budget_alert'         -- 预算异常警告
        ) NOT NULL,
        priority     ENUM('high','medium','low') DEFAULT 'medium',
        search_term  VARCHAR(500) COMMENT '触发建议的搜索词',
        current_value VARCHAR(500) COMMENT '当前值（如当前标题文案）',
        suggested_value VARCHAR(1000) COMMENT '建议改为',
        reason       TEXT COMMENT '建议原因',
        data_evidence JSON COMMENT '支撑数据（impressions/clicks等）',
        status       ENUM('pending','applied','dismissed') DEFAULT 'pending',
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_upload(upload_id),
        INDEX idx_asin(asin),
        INDEX idx_type(suggestion_type),
        INDEX idx_status(status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # KPI 目标设置
    'ads_kpi_targets': """
    CREATE TABLE IF NOT EXISTS ads_kpi_targets (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        target_name  VARCHAR(100) NOT NULL,
        asin         VARCHAR(20) COMMENT 'NULL = 全局目标',
        campaign_name VARCHAR(255) COMMENT 'NULL = 全局',
        metric       ENUM('roas','cpa','ctr','cvr','cpc','daily_budget') NOT NULL,
        target_value FLOAT NOT NULL,
        alert_threshold FLOAT COMMENT '报警阈值（偏差%）',
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_target(asin, campaign_name, metric)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # KPI 实际数据（从上传报告中提取）
    'ads_kpi_actuals': """
    CREATE TABLE IF NOT EXISTS ads_kpi_actuals (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        upload_id    VARCHAR(36) NOT NULL,
        asin         VARCHAR(20),
        campaign_name VARCHAR(255),
        metric       VARCHAR(50) NOT NULL,
        actual_value FLOAT NOT NULL,
        period_start DATE,
        period_end   DATE,
        recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_upload(upload_id),
        INDEX idx_asin(asin)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # 上传批次记录
    'ads_report_uploads': """
    CREATE TABLE IF NOT EXISTS ads_report_uploads (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        upload_id    VARCHAR(36) NOT NULL UNIQUE,
        file_name    VARCHAR(255),
        file_size    INT,
        report_type  VARCHAR(50),
        row_count    INT DEFAULT 0,
        asin         VARCHAR(20) COMMENT '手动关联的ASIN',
        status       ENUM('processing','done','failed') DEFAULT 'processing',
        suggestion_count INT DEFAULT 0,
        notes        TEXT,
        uploaded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_upload_id(upload_id),
        INDEX idx_asin(asin)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

def main():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    for tname, sql in TABLES.items():
        try:
            cur.execute(sql)
            conn.commit()
            print(f"[OK] {tname}")
        except Exception as e:
            print(f"[ERR] {tname}: {e}")
    cur.close()
    conn.close()
    print("Done.")

if __name__ == '__main__':
    main()
