"""
YP Affiliate 管理台 - 数据库模块
连接池、缓存、工具函数
"""

import time as _time
import mysql.connector
import mysql.connector.pooling as _pool
from app_config import DB


# ─── 单连接（适合写操作）────────────────────────────────────────────────────
def get_db():
    """获取新的数据库连接（设置 sql_mode）"""
    conn = mysql.connector.connect(**DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
        )
        cur.close()
    except Exception:
        pass
    return conn


# ─── 连接池（采集页面用，高并发友好）────────────────────────────────────────
# _db_pool = _pool.MySQLConnectionPool(pool_name="scrape_pool", pool_size=10, pool_reset_session=True, **DB)


def _db():
    """从连接池取连接（供采集相关路由使用）

    注意：由于连接池容易出现耗尽问题，暂时改为直接创建新连接
    """
    return mysql.connector.connect(**DB)


# ─── COUNT 缓存（60s TTL，避免频繁全表扫描）──────────────────────────────────
_count_cache: dict = {}
_COUNT_TTL = 60


def _cached_count(key, sql, params=()):
    """带缓存的 COUNT 查询"""
    now = _time.time()
    if key in _count_cache:
        val, exp = _count_cache[key]
        if now < exp:
            return val
    conn = _db()
    cur = conn.cursor()
    cur.execute(sql, params)
    val = cur.fetchone()[0]
    conn.close()
    _count_cache[key] = (val, now + _COUNT_TTL)
    return val


# ─── 检查物化缓存表是否已就绪 ─────────────────────────────────────────────
_cache_table_ok = False


def check_cache_table():
    """检查 yp_us_products 是否存在"""
    global _cache_table_ok
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM yp_us_products LIMIT 1")
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        _cache_table_ok = True
        print(
            f"[cache] yp_us_products ready, count={cnt}",
            flush=True,
        )
    except Exception as e:
        _cache_table_ok = False
        print(f"[cache] yp_us_products not ready: {e}", flush=True)


# ─── Google Ads 报告解析工具 ─────────────────────────────────────────────
def _parse_report_column(header):
    """模糊匹配 Google Ads 导出文件的列名，返回标准列名"""
    h = header.strip().lower()
    mapping = {
        "search term": "search_term",
        "search_term": "search_term",
        "搜索词": "search_term",
        "query": "search_term",
        "impr.": "impressions",
        "impressions": "impressions",
        "曝光量": "impressions",
        "clicks": "clicks",
        "点击量": "clicks",
        "ctr": "ctr",
        "点击率": "ctr",
        "avg. cpc": "cpc",
        "cost / click": "cpc",
        "平均每次点击费用": "cpc",
        "cost": "cost",
        "费用": "cost",
        "conversions": "conversions",
        "转化次数": "conversions",
        "conv.": "conversions",
        "conv. rate": "conv_rate",
        "转化率": "conv_rate",
        "conv. value": "conv_value",
        "转化价值": "conv_value",
        "quality score": "quality_score",
        "质量得分": "quality_score",
        "qs": "quality_score",
        "campaign": "campaign_name",
        "广告系列": "campaign_name",
        "ad group": "ad_group_name",
        "广告组": "ad_group_name",
        "match type": "match_type",
        "匹配类型": "match_type",
    }
    return mapping.get(h, None)


def _clean_numeric_value(value, field_type="float"):
    """清洗数值字段（去除 $、%、逗号等）"""
    if value is None or value == "":
        return None
    s = str(value).strip().replace("$", "").replace(",", "").replace("%", "")
    try:
        if field_type == "float":
            return float(s)
        elif field_type == "int":
            return int(s)
    except ValueError:
        return None
