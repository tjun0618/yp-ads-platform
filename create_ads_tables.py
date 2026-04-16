"""
Google Ads 三层数据库表结构创建脚本
=====================================
Campaign（广告系列）→ Ad Group（广告组）→ Ad（广告）

运行: python -X utf8 create_ads_tables.py
"""
import mysql.connector

DB = dict(host='localhost', port=3306, user='root', password='admin',
          database='affiliate_marketing', charset='utf8mb4')

DDL = [

# ─────────────────────────────────────────────
# 1. 广告系列（Campaign）
# ─────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS ads_campaigns (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    -- 关联信息
    asin            VARCHAR(20)  NOT NULL COMMENT '商品 ASIN',
    merchant_id     VARCHAR(50)  NOT NULL,
    merchant_name   VARCHAR(255),
    -- 广告系列基本信息
    campaign_name   VARCHAR(255) NOT NULL COMMENT 'Campaign 名称（英文）',
    journey_stage   VARCHAR(50)  NOT NULL COMMENT 'Brand/Problem-Awareness/Solution-Evaluation/Feature-Exploration/Purchase-Decision/Competitor',
    budget_pct      TINYINT UNSIGNED COMMENT '建议预算占比(%)',
    daily_budget_usd DECIMAL(8,2) COMMENT '建议每日预算($)',
    -- 商品盈利分析
    product_price   DECIMAL(10,2),
    commission_pct  DECIMAL(5,2) COMMENT '佣金率(%)',
    commission_usd  DECIMAL(10,2) COMMENT '单次佣金($)',
    target_cpa      DECIMAL(8,2) COMMENT '目标CPA = 价格×佣金×0.7',
    -- 否定关键词（账户级）
    negative_keywords JSON COMMENT '账户级否定关键词列表',
    -- 出价策略
    bid_strategy    VARCHAR(100) COMMENT 'Manual CPC / Max Conversions / Target CPA',
    -- 状态追踪
    status          ENUM('draft','active','paused','archived') DEFAULT 'draft',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_asin        (asin),
    INDEX idx_merchant    (merchant_id),
    INDEX idx_status      (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Google Ads 广告系列（Campaign 层）'
""",

# ─────────────────────────────────────────────
# 2. 广告组（Ad Group）
# ─────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS ads_ad_groups (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    campaign_id     INT UNSIGNED NOT NULL,
    -- 广告组信息
    ad_group_name   VARCHAR(255) NOT NULL,
    theme           VARCHAR(100) COMMENT '关键词主题描述',
    user_intent     VARCHAR(255) COMMENT '用户意图描述',
    -- 关键词（JSON 数组，每条含 match_type 和 keyword）
    keywords        JSON COMMENT '[{"type":"E","kw":"..."},{"type":"P","kw":"..."},{"type":"B","kw":"..."}]',
    negative_keywords JSON COMMENT '广告组级否定关键词',
    -- 关键词统计
    keyword_count   TINYINT UNSIGNED DEFAULT 0,
    -- 出价建议
    cpc_bid_usd     DECIMAL(6,2) COMMENT '建议CPC出价($)',
    -- 状态
    status          ENUM('draft','active','paused','archived') DEFAULT 'draft',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 外键 + 索引
    FOREIGN KEY (campaign_id) REFERENCES ads_campaigns(id) ON DELETE CASCADE,
    INDEX idx_campaign (campaign_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Google Ads 广告组（Ad Group 层）'
""",

# ─────────────────────────────────────────────
# 3. 广告（Ad）
# ─────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS ads_ads (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ad_group_id     INT UNSIGNED NOT NULL,
    campaign_id     INT UNSIGNED NOT NULL,
    asin            VARCHAR(20),
    -- 广告标识
    variant         CHAR(1) DEFAULT 'A' COMMENT 'A=功能主导 / B=情感主导（A/B测试）',
    -- 响应式搜索广告（RSA）字段
    headlines       JSON NOT NULL COMMENT '15个标题 [{text,chars,type}]',
    descriptions    JSON NOT NULL COMMENT '5个描述 [{text,chars,type}]',
    -- 广告扩展
    sitelinks       JSON COMMENT '[{text,desc1,desc2}] 4-8条',
    callouts        JSON COMMENT '["Free Prime Shipping","30-Day Returns",...] 4-8条',
    structured_snippet JSON COMMENT '{header:"Features",values:[...]}',
    -- 投放链接
    final_url       TEXT COMMENT 'YP 投放链接（tracking_url）',
    display_url     VARCHAR(255) COMMENT '显示路径，如 amazon.com/[品牌]/[产品]',
    -- 质量检查
    headline_count  TINYINT UNSIGNED,
    description_count TINYINT UNSIGNED,
    all_chars_valid TINYINT(1) DEFAULT 0 COMMENT '1=全部字符合规',
    quality_notes   TEXT COMMENT '质检备注',
    -- 出价策略
    bidding_phases  JSON COMMENT '[{phase,weeks,strategy,cpc_range},{...}]',
    -- A/B 测试
    ab_winner       TINYINT(1) COMMENT '1=胜出，0=淘汰，NULL=未决',
    -- 状态
    status          ENUM('draft','active','paused','archived') DEFAULT 'draft',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 外键 + 索引
    FOREIGN KEY (ad_group_id) REFERENCES ads_ad_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES ads_campaigns(id) ON DELETE CASCADE,
    INDEX idx_ad_group  (ad_group_id),
    INDEX idx_campaign  (campaign_id),
    INDEX idx_asin      (asin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Google Ads 广告（Ad 层，RSA 响应式搜索广告）'
""",

# ─────────────────────────────────────────────
# 4. 广告方案汇总（每个 ASIN 的完整方案）
# ─────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS ads_plans (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    asin            VARCHAR(20) NOT NULL UNIQUE,
    merchant_id     VARCHAR(50),
    merchant_name   VARCHAR(255),
    product_name    VARCHAR(500),
    product_price   DECIMAL(10,2),
    commission_pct  DECIMAL(5,2),
    target_cpa      DECIMAL(8,2),
    -- 方案统计
    campaign_count  TINYINT UNSIGNED DEFAULT 0,
    ad_group_count  TINYINT UNSIGNED DEFAULT 0,
    ad_count        TINYINT UNSIGNED DEFAULT 0,
    -- 关键词来源
    brand_keywords_used JSON COMMENT '实际使用的品牌关键词',
    -- 方案状态
    plan_status     ENUM('pending','generating','completed','failed') DEFAULT 'pending',
    has_amazon_data TINYINT(1) DEFAULT 0 COMMENT '1=有亚马逊详情数据',
    -- 时间
    generated_at    TIMESTAMP NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_asin      (asin),
    INDEX idx_merchant  (merchant_id),
    INDEX idx_status    (plan_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Google Ads 广告方案汇总（每个 ASIN 一条）'
"""
]


def create_tables():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    for ddl in DDL:
        # 提取表名（去掉括号及后续内容）
        raw = [line.strip() for line in ddl.strip().split('\n')
               if 'CREATE TABLE IF NOT EXISTS' in line][0]
        table_name = raw.replace('CREATE TABLE IF NOT EXISTS ', '').split('(')[0].strip()
        cur.execute(ddl)
        conn.commit()
        # 查行数
        cur.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        cnt = cur.fetchone()[0]
        print(f"OK {table_name}: {cnt} rows")
    cur.close()
    conn.close()
    print("\nAll ads tables created!")


if __name__ == '__main__':
    create_tables()
