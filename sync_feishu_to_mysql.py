"""
飞书 Merchants & Categories → MySQL 同步脚本
- 创建 yp_merchants 和 yp_categories 表（不存在时）
- 从飞书拉取全量数据，ON DUPLICATE KEY UPDATE 保证幂等
- 可反复运行，不会重复插入

用法:
    python sync_feishu_to_mysql.py            # 同步商户 + 类别
    python sync_feishu_to_mysql.py merchants  # 只同步商户
    python sync_feishu_to_mysql.py categories # 只同步类别
"""

import sys
import time
import logging
import requests
from datetime import datetime

# ─── 飞书配置 ────────────────────────────────────────────────────
FEISHU_APP_ID     = 'cli_a935343a74f89cd4'
FEISHU_APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
FEISHU_APP_TOKEN  = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_MERCHANTS   = 'tblR2JhVsdTugueo'   # 10,020 条
TABLE_CATEGORIES  = 'tblgOVVvOccSVLgU'   # 148 条

# ─── MySQL 配置 ─────────────────────────────────────────────────
MYSQL_HOST  = 'localhost'
MYSQL_PORT  = 3306
MYSQL_USER  = 'root'
MYSQL_PASS  = 'admin'
MYSQL_DB    = 'affiliate_marketing'
BATCH_SIZE  = 500
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  飞书工具
# ══════════════════════════════════════════════

def get_feishu_token():
    r = requests.post(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET},
        timeout=15
    )
    r.raise_for_status()
    return r.json()['tenant_access_token']


def fetch_all_records(feishu_token: str, table_id: str) -> list:
    """分页拉取飞书表格全量数据，返回 fields 列表"""
    headers   = {'Authorization': f'Bearer {feishu_token}'}
    base_url  = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records'
    records   = []
    page_token = None

    while True:
        params = {'page_size': 500}
        if page_token:
            params['page_token'] = page_token

        resp = requests.get(base_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get('data', {})

        items = data.get('items', [])
        for item in items:
            records.append(item.get('fields', {}))

        if data.get('has_more') and data.get('page_token'):
            page_token = data['page_token']
            time.sleep(0.2)   # 稍作限速
        else:
            break

    return records


# ══════════════════════════════════════════════
#  MySQL 工具
# ══════════════════════════════════════════════

def get_mysql_conn():
    import mysql.connector
    return mysql.connector.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, charset='utf8mb4',
        autocommit=False
    )


def ensure_tables(conn):
    """建表（若不存在）"""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS yp_merchants (
            id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            merchant_id     INT UNSIGNED  NOT NULL         COMMENT '商户ID（YP mid）',
            merchant_name   VARCHAR(255)  NOT NULL         COMMENT '商户名称',
            avg_payout      DECIMAL(12,2) DEFAULT NULL     COMMENT '平均佣金率/金额',
            cookie_days     SMALLINT      DEFAULT NULL     COMMENT 'Cookie 有效天数',
            website         TEXT          DEFAULT NULL     COMMENT '官网 URL',
            country         VARCHAR(100)  DEFAULT NULL     COMMENT '国家',
            transaction_type VARCHAR(50)  DEFAULT NULL     COMMENT '交易类型 (CPS/CPA…)',
            status          VARCHAR(30)   DEFAULT NULL     COMMENT '申请状态 (APPROVED/PENDING/UNAPPLIED)',
            online_status   VARCHAR(20)   DEFAULT NULL     COMMENT '在线状态 (onLine/offLine)',
            deep_link       VARCHAR(10)   DEFAULT NULL     COMMENT '是否支持深链 (Yes/No)',
            logo            TEXT          DEFAULT NULL     COMMENT 'Logo URL',
            collected_at    VARCHAR(50)   DEFAULT NULL     COMMENT '飞书采集时间',
            synced_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_merchant_id (merchant_id),
            INDEX idx_merchant_name (merchant_name(100)),
            INDEX idx_status        (status),
            INDEX idx_online_status (online_status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='YP平台商户信息（来源：飞书 Merchants 表）'
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS yp_categories (
            id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            category_id   INT UNSIGNED NOT NULL          COMMENT '类别ID',
            category_name VARCHAR(200) NOT NULL          COMMENT '类别名称',
            collected_at  VARCHAR(50)  DEFAULT NULL      COMMENT '飞书采集时间',
            synced_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_category_id (category_id),
            INDEX idx_category_name (category_name(100))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='YP平台商品类别（来源：飞书 Categories 表）'
    """)

    conn.commit()
    cur.close()
    log.info('✅ 表 yp_merchants 和 yp_categories 已就绪')


# ══════════════════════════════════════════════
#  同步商户
# ══════════════════════════════════════════════

def _parse_number(val):
    """解析飞书数字字段（可能是 float 或 dict）"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, dict):
        return val.get('value') or val.get('number')
    try:
        return float(str(val).strip())
    except Exception:
        return None


def _parse_text(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip() or None
    if isinstance(val, list):
        # 飞书多行文本返回 [{"text": "..."}]
        parts = []
        for item in val:
            if isinstance(item, dict):
                parts.append(item.get('text', ''))
            else:
                parts.append(str(item))
        return ''.join(parts).strip() or None
    return str(val).strip() or None


def _parse_select(val):
    """飞书单选字段"""
    if isinstance(val, dict):
        return val.get('text') or val.get('value')
    return _parse_text(val)


def _parse_date(val):
    """飞书日期字段（毫秒时间戳 → ISO 字符串）"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            import datetime as dt
            return dt.datetime.fromtimestamp(val / 1000, tz=dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(val)
    return str(val)


def sync_merchants(conn, feishu_token: str):
    log.info('── 同步商户 ─────────────────────────────')
    log.info('从飞书拉取 Merchants 数据...')
    records = fetch_all_records(feishu_token, TABLE_MERCHANTS)
    log.info(f'拉取到 {len(records):,} 条商户记录')

    SQL = """
        INSERT INTO yp_merchants
            (merchant_id, merchant_name, avg_payout, cookie_days, website,
             country, transaction_type, status, online_status, deep_link,
             logo, collected_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            merchant_name    = VALUES(merchant_name),
            avg_payout       = VALUES(avg_payout),
            cookie_days      = VALUES(cookie_days),
            website          = VALUES(website),
            country          = VALUES(country),
            transaction_type = VALUES(transaction_type),
            status           = VALUES(status),
            online_status    = VALUES(online_status),
            deep_link        = VALUES(deep_link),
            logo             = VALUES(logo),
            collected_at     = VALUES(collected_at)
    """

    cur = conn.cursor()
    batch   = []
    written = 0
    skipped = 0

    for rec in records:
        mid = _parse_number(rec.get('Merchant ID'))
        if not mid:
            skipped += 1
            continue

        avg_payout   = _parse_number(rec.get('Avg Payout (%)'))
        cookie_days  = _parse_number(rec.get('Cookie Days'))
        if cookie_days is not None:
            cookie_days = int(cookie_days)

        batch.append((
            int(mid),
            _parse_text(rec.get('Merchant Name')) or '',
            round(float(avg_payout), 2) if avg_payout is not None else None,
            cookie_days,
            _parse_text(rec.get('Website')),
            _parse_text(rec.get('Country')),
            _parse_select(rec.get('Transaction Type')),
            _parse_select(rec.get('Status')),
            _parse_select(rec.get('Online Status')),
            _parse_select(rec.get('Deep Link')),
            _parse_text(rec.get('Logo')),
            _parse_date(rec.get('Collected At')),
        ))

        if len(batch) >= BATCH_SIZE:
            cur.executemany(SQL, batch)
            conn.commit()
            written += len(batch)
            batch = []
            log.info(f'  商户写入进度: {written:,}/{len(records):,}')

    if batch:
        cur.executemany(SQL, batch)
        conn.commit()
        written += len(batch)

    cur.close()
    log.info(f'✅ 商户同步完成：写入 {written:,} 条，跳过 {skipped} 条无效记录')
    return written


# ══════════════════════════════════════════════
#  同步类别
# ══════════════════════════════════════════════

def sync_categories(conn, feishu_token: str):
    log.info('── 同步类别 ─────────────────────────────')
    log.info('从飞书拉取 Categories 数据...')
    records = fetch_all_records(feishu_token, TABLE_CATEGORIES)
    log.info(f'拉取到 {len(records):,} 条类别记录')

    SQL = """
        INSERT INTO yp_categories (category_id, category_name, collected_at)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            category_name = VALUES(category_name),
            collected_at  = VALUES(collected_at)
    """

    cur = conn.cursor()
    batch   = []
    written = 0
    skipped = 0

    for rec in records:
        cid = _parse_number(rec.get('Category ID'))
        if not cid:
            skipped += 1
            continue

        batch.append((
            int(cid),
            _parse_text(rec.get('Category Name')) or '',
            _parse_date(rec.get('Collected At')),
        ))

    if batch:
        cur.executemany(SQL, batch)
        conn.commit()
        written = len(batch)

    cur.close()
    log.info(f'✅ 类别同步完成：写入 {written:,} 条，跳过 {skipped} 条无效记录')
    return written


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

def main():
    args = [a.lower() for a in sys.argv[1:]]
    do_merchants  = not args or 'merchants'  in args or 'all' in args
    do_categories = not args or 'categories' in args or 'all' in args

    log.info('=' * 55)
    log.info('飞书 → MySQL 商户/类别同步')
    log.info('=' * 55)

    t0 = time.time()

    # 获取飞书 Token
    feishu_token = get_feishu_token()
    log.info('✅ 飞书 Token 获取成功')

    # 连接 MySQL
    conn = get_mysql_conn()
    log.info('✅ MySQL 连接成功')

    # 建表
    ensure_tables(conn)

    # 同步
    if do_merchants:
        sync_merchants(conn, feishu_token)

    if do_categories:
        sync_categories(conn, feishu_token)

    conn.close()
    elapsed = time.time() - t0
    log.info('=' * 55)
    log.info(f'全部完成，耗时 {elapsed:.1f} 秒')
    log.info('=' * 55)


if __name__ == '__main__':
    main()
