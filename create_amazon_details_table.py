# -*- coding: utf-8 -*-
"""
创建 amazon_product_details 表
与 yp_products 通过 asin 关联
"""
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin', database='affiliate_marketing'
)
cur = conn.cursor()

# 创建商品详情表
create_sql = """
CREATE TABLE IF NOT EXISTS amazon_product_details (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    asin            VARCHAR(20)     NOT NULL COMMENT 'ASIN，关联 yp_products.asin',

    -- 基本信息
    title           TEXT            COMMENT '商品标题（英文）',
    brand           VARCHAR(255)    COMMENT '品牌名',
    price           VARCHAR(50)     COMMENT '当前价格，如 $29.99',
    original_price  VARCHAR(50)     COMMENT '原价（如有划线价）',
    rating          VARCHAR(20)     COMMENT '评分，如 4.5 out of 5 stars',
    review_count    VARCHAR(50)     COMMENT '评论数，如 1,234 ratings',
    availability    VARCHAR(255)    COMMENT '库存状态，如 In Stock',

    -- 商品描述
    bullet_points   MEDIUMTEXT      COMMENT '商品要点（bullet points），JSON 数组格式',
    description     MEDIUMTEXT      COMMENT '商品详细描述（A+ 内容或文字描述）',

    -- 商品详情
    product_details MEDIUMTEXT      COMMENT '商品规格/技术参数（JSON 格式）',

    -- 分类
    category_path   TEXT            COMMENT '商品分类路径，如 Electronics > Cameras > ...',

    -- 图片
    main_image_url  TEXT            COMMENT '主图 URL',
    image_urls      MEDIUMTEXT      COMMENT '所有图片 URL（JSON 数组）',

    -- 评论样本（用于 Ads 素材）
    top_reviews     MEDIUMTEXT      COMMENT '前5条精选评论（JSON 数组，含标题/内容/星级）',

    -- 关键字（用于 Ads）
    keywords        TEXT            COMMENT '从标题+bullet提取的关键词（JSON 数组）',

    -- 元数据
    amazon_url      TEXT            COMMENT '完整亚马逊链接',
    page_language   VARCHAR(20)     DEFAULT 'en-US' COMMENT '页面语言',
    scraped_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP COMMENT '抓取时间',
    updated_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 索引
    UNIQUE KEY uq_asin (asin),
    KEY idx_brand (brand),
    KEY idx_scraped_at (scraped_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='亚马逊商品详情，供 Google Ads 投放素材使用';
"""

cur.execute(create_sql)
conn.commit()
print("✅ amazon_product_details 表创建成功（或已存在）")

# 验证
cur.execute("DESCRIBE amazon_product_details")
print("\n字段列表:")
for row in cur.fetchall():
    print(f"  {row[0]:<25} {row[1]:<20} {row[2]}")

conn.close()
