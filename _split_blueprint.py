"""
_split_blueprint.py v2 - 简洁切割，只做 @app.route -> @bp.route 替换
不做内容删除，重复定义后续手动处理
"""

import re

SRC = r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\ads_manager.py"
OUT = r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu"

with open(SRC, "r", encoding="utf-8") as f:
    lines = f.readlines()

total = len(lines)
print(f"Source: {total} lines")

# 行号从1开始，切片用0-based index
slices = {
    "routes_products": (298, 2859),    # 行 299 ~ 2859
    "routes_merchants": (2859, 4190),   # 行 2860 ~ 4190
    "routes_collect": (4190, 5889),     # 行 4191 ~ 5889
    "routes_analytics": (5889, 8862),   # 行 5890 ~ 8862
}

headers = {
    "routes_products": '''\
# routes_products.py - 商品列表、广告方案、广告生成API
# 从 ads_manager.py 行 299-2859 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, datetime
from pathlib import Path
from flask import (Blueprint, render_template_string, jsonify, request,
                   redirect, url_for, send_file, Response, current_app)
from urllib.parse import quote
from config import DB, BASE_DIR, SCRAPER_SCRIPT, OUTPUT_DIR, STOP_FILE, PROGRESS_FILE
from db import get_db, _db, _cached_count, _count_cache
from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK

bp = Blueprint("products", __name__)

''',

    "routes_merchants": '''\
# routes_merchants.py - Amazon采集、商户管理、商户商品
# 从 ads_manager.py 行 2860-4190 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, subprocess, datetime
from pathlib import Path
from flask import (Blueprint, render_template_string, jsonify, request,
                   redirect, url_for, send_file, Response, current_app)
from urllib.parse import quote
from config import (DB, BASE_DIR, SCRAPER_SCRIPT, OUTPUT_DIR, STOP_FILE,
                    PROGRESS_FILE, YP_COLLECT_SCRIPT, YP_STOP_FILE, PYTHON_EXE,
                    YP_SITE_ID, YP_API_TOKEN, YP_OFFER_BY_ADVERT_URL)
from db import get_db, _db, _cached_count, _count_cache
from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK, _SCRAPE_TOPNAV

bp = Blueprint("merchants", __name__)

# 全局状态变量 - Amazon采集
scrape_process = None
scrape_running = False
scrape_thread = None

''',

    "routes_collect": '''\
# routes_collect.py - YP采集、作战室、下载方案
# 从 ads_manager.py 行 4191-5889 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, subprocess, datetime
from pathlib import Path
from flask import (Blueprint, render_template_string, jsonify, request,
                   redirect, url_for, send_file, Response, current_app)
from urllib.parse import quote
from config import (DB, BASE_DIR, SCRAPER_SCRIPT, OUTPUT_DIR, STOP_FILE,
                    PROGRESS_FILE, YP_COLLECT_SCRIPT, YP_STOP_FILE, PYTHON_EXE,
                    YP_SITE_ID, YP_API_TOKEN, YP_OFFER_BY_ADVERT_URL)
from db import get_db, _db, _cached_count, _count_cache, _parse_report_column, _clean_numeric_value
from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK, _SCRAPE_TOPNAV

bp = Blueprint("collect", __name__)

''',

    "routes_analytics": '''\
# routes_analytics.py - 投放优化、质量评分、竞品分析、YP同步
# 从 ads_manager.py 行 5890-8862 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, subprocess, datetime, time
from pathlib import Path
from flask import (Blueprint, render_template_string, jsonify, request,
                   redirect, url_for, send_file, Response, current_app)
from urllib.parse import quote
from config import (DB, BASE_DIR, OUTPUT_DIR,
                    YP_SYNC_SCRIPT, YP_SYNC_STATE, YP_SYNC_LOG)
from db import get_db, _db, _cached_count, _count_cache, _parse_report_column, _clean_numeric_value
from templates_shared import BASE_CSS, NAV_HTML

bp = Blueprint("analytics", __name__)

# 全局状态
optimized_uploads = {}
_yp_sync_proc = None

''',
}

# 需要完全删除的重复定义（行号范围，0-based）
# 这些变量已在 header 或其他模块中定义，需要从切割的代码块中移除
skip_ranges = {
    "routes_products": [],  # 暂时不删
    "routes_merchants": [],  # 暂时不删
    "routes_collect": [],    # 暂时不删
    "routes_analytics": [],  # 暂时不删
}

for name, (start, end) in slices.items():
    header = headers[name]
    chunk = lines[start:end]
    
    # 只做 @app.route -> @bp.route 替换
    processed = []
    for line in chunk:
        line = line.replace("@app.route(", "@bp.route(")
        processed.append(line)
    
    filepath = f"{OUT}\\{name}.py"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header)
        f.writelines(processed)
    
    print(f"  {name}.py: {len(processed)} lines written")

print("\nDone!")
