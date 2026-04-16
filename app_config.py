"""
YP Affiliate 管理台 - 配置模块
路径常量、数据库配置、全局状态
"""

import sys
import os
import threading
from pathlib import Path

# ─── 路径常量 ───────────────────────────────────────────────────────────────
BASE_DIR = Path(os.path.abspath(__file__)).parent
STOP_FILE = BASE_DIR / ".scrape_stop"
PROGRESS_FILE = BASE_DIR / ".scrape_progress"
SCRAPER_SCRIPT = BASE_DIR / "scrape_amazon_details.py"
OUTPUT_DIR = BASE_DIR / "output"
YP_COLLECT_SCRIPT = BASE_DIR / "download_only.py"
YP_STOP_FILE = BASE_DIR / ".yp_collect_stop"
PYTHON_EXE = sys.executable

# YP 同步
YP_SYNC_SCRIPT = BASE_DIR / "yp_sync_merchants.py"
YP_SYNC_STATE = BASE_DIR / "output" / "yp_sync_state.json"
YP_SYNC_LOG = BASE_DIR / "logs" / "yp_sync_merchants.log"

# ─── YP API 配置 ────────────────────────────────────────────────────────────
YP_SITE_ID = "12002"
YP_API_TOKEN = "7951dc7484fa9f9d"
YP_OFFER_BY_ADVERT_URL = "https://www.yeahpromos.com/index/apioffer/getofferbyadvert"

# ─── 数据库配置 ─────────────────────────────────────────────────────────────
DB = dict(
    host="localhost",
    port=3306,
    user="root",
    password="admin",
    database="affiliate_marketing",
    charset="utf8mb4",
)

# ─── 全局状态 ───────────────────────────────────────────────────────────────
# 正在生成中的 ASIN 集合（防止重复提交）
_generating = set()
_gen_lock = threading.Lock()

# YP 同步子进程引用
_yp_sync_proc = None
