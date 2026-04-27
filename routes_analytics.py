# routes_analytics.py - 投放优化、质量评分、竞品分析、YP同步
# 从 ads_manager.py 行 5890-8862 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, subprocess, datetime
from pathlib import Path
from flask import (
    Blueprint,
    render_template_string,
    jsonify,
    request,
    redirect,
    url_for,
    send_file,
    Response,
    current_app,
)
from urllib.parse import quote
from app_config import (
    DB,
    BASE_DIR,
    OUTPUT_DIR,
    YP_SYNC_SCRIPT,
    YP_SYNC_STATE,
    YP_SYNC_LOG,
)
from db import (
    get_db,
    _db,
    _cached_count,
    _count_cache,
    _parse_report_column,
    _clean_numeric_value,
)
from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _SCRAPE_TOPNAV

bp = Blueprint("analytics", __name__)

# 全局状态
optimized_uploads = {}
_yp_sync_proc = None


@bp.route("/api/optimize/upload", methods=["POST"])
def api_optimize_upload():
    """
    T-002: 上传 Google Ads 报告文件（CSV或Excel）
    接收字段: file（文件）、asin（可选）、report_type
    """
    try:
        if "file" not in request.files:
            return jsonify({"ok": False, "msg": "未上传文件"})

        file = request.files["file"]
        asin = request.form.get("asin", "").strip()
        report_type = request.form.get("report_type", "search_term").strip()

        if not file or file.filename == "":
            return jsonify({"ok": False, "msg": "文件为空"})

        upload_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now()

        rows = []

        # 判断文件类型并解析
        filename = file.filename.lower()
        if filename.endswith(".csv"):
            # CSV 解析
            try:
                content = file.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(content))

                for row_dict in reader:
                    rows.append(row_dict)
            except UnicodeDecodeError:
                # 尝试 GBK 编码
                file.seek(0)
                content = file.read().decode("gbk")
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)

        elif filename.endswith((".xlsx", ".xls")):
            # Excel 解析
            try:
                import openpyxl

                file.seek(0)
                wb = openpyxl.load_workbook(file)
                ws = wb.active

                # 读取表头
                headers = [cell.value for cell in ws[1]]

                # 建立列索引映射
                col_mapping = {}
                for i, h in enumerate(headers):
                    std_col = _parse_report_column(str(h) if h else "")
                    if std_col:
                        col_mapping[i] = std_col

                # 读取数据行
                for row in ws.iter_rows(min_row=2, values_only=True):
                    row_dict = {}
                    for idx, val in enumerate(row):
                        if idx in col_mapping:
                            row_dict[col_mapping[idx]] = val
                    if row_dict:
                        rows.append(row_dict)

            except ImportError:
                return jsonify(
                    {
                        "ok": False,
                        "msg": "Excel解析失败，请安装 openpyxl: pip install openpyxl",
                    }
                )
            except Exception as e:
                return jsonify({"ok": False, "msg": f"Excel解析错误: {e}"})

        else:
            return jsonify({"ok": False, "msg": "仅支持CSV或Excel文件"})

        if not rows:
            return jsonify({"ok": False, "msg": "文件中没有数据"})

        # 批量插入数据库
        conn = get_db()
        cur = conn.cursor()

        insert_sql = """
            INSERT INTO ads_search_term_reports 
            (upload_id, asin, report_type, search_term, impressions, clicks, ctr, cpc, cost,
             conversions, conv_rate, conv_value, quality_score, campaign_name, ad_group_name, match_type,
             upload_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        batch_data = []
        for row in rows:
            try:
                batch_data.append(
                    (
                        upload_id,
                        asin or None,
                        report_type,
                        row.get("search_term"),
                        _clean_numeric_value(row.get("impressions"), "int"),
                        _clean_numeric_value(row.get("clicks"), "int"),
                        _clean_numeric_value(row.get("ctr"), "float"),
                        _clean_numeric_value(row.get("cpc"), "float"),
                        _clean_numeric_value(row.get("cost"), "float"),
                        _clean_numeric_value(row.get("conversions"), "int"),
                        _clean_numeric_value(row.get("conv_rate"), "float"),
                        _clean_numeric_value(row.get("conv_value"), "float"),
                        _clean_numeric_value(row.get("quality_score"), "int"),
                        row.get("campaign_name"),
                        row.get("ad_group_name"),
                        row.get("match_type"),
                        timestamp,
                    )
                )
            except Exception:
                continue

        if batch_data:
            cur.executemany(insert_sql, batch_data)

        # 插入上传记录
        insert_upload_sql = """
            INSERT INTO ads_report_uploads 
            (upload_id, asin, report_type, file_name, row_count, status, upload_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(
            insert_upload_sql,
            (
                upload_id,
                asin or None,
                report_type,
                file.filename,
                len(batch_data),
                "pending",
                timestamp,
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "ok": True,
                "upload_id": upload_id,
                "row_count": len(batch_data),
                "msg": f"成功导入 {len(batch_data)} 条数据",
            }
        )

    except Exception as e:
        return jsonify({"ok": False, "msg": f"上传失败: {str(e)}"})


# ─── 广告优化模块（T-003: 分析引擎）───────────────────────────────────────


@bp.route("/api/optimize/analyze/<upload_id>", methods=["POST"])
def api_optimize_analyze(upload_id):
    """
    T-003: 分析上传的报告数据，生成优化建议
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        # 查询本批次数据
        cur.execute(
            """
            SELECT id, search_term, impressions, clicks, ctr, cpc, cost,
                   conversions, conv_rate, conv_value, quality_score,
                   campaign_name, ad_group_name, match_type
            FROM ads_search_term_reports
            WHERE upload_id = %s
        """,
            (upload_id,),
        )

        rows = cur.fetchall()
        if not rows:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "msg": "未找到该批次数据"})

        # 转换为字典列表
        data = []
        for row in rows:
            data.append(
                {
                    "id": row[0],
                    "search_term": row[1],
                    "impressions": row[2] or 0,
                    "clicks": row[3] or 0,
                    "ctr": row[4] or 0.0,
                    "cpc": row[5] or 0.0,
                    "cost": row[6] or 0.0,
                    "conversions": row[7] or 0,
                    "conv_rate": row[8] or 0.0,
                    "conv_value": row[9] or 0.0,
                    "quality_score": row[10] or 0,
                    "campaign_name": row[11],
                    "ad_group_name": row[12],
                    "match_type": row[13],
                }
            )

        suggestions = []
        total_impr = 0
        total_clicks = 0
        total_cost = 0.0
        total_conv = 0
        total_conv_value = 0.0

        # 分析每一条记录
        for item in data:
            total_impr += item["impressions"]
            total_clicks += item["clicks"]
            total_cost += item["cost"]
            total_conv += item["conversions"]
            total_conv_value += item["conv_value"]

            clicks = item["clicks"]
            conv_rate = item["conv_rate"]
            cost = item["cost"]
            conversions = item["conversions"]
            impressions = item["impressions"]
            quality_score = item["quality_score"]
            match_type = (item["match_type"] or "").lower()

            # 规则1：高点击低转化（否定词建议）
            if clicks >= 5 and conv_rate < 0.02 and cost > 2.0:
                priority = "high" if clicks >= 10 else "medium"
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "add_negative",
                        "priority": priority,
                        "current_value": f"clicks={clicks}, conv_rate={conv_rate:.1%}, cost=${cost:.2f}",
                        "suggested_value": f"否定: {item['search_term']}",
                        "reason": f"该词 {clicks} 次点击，转化率仅 {conv_rate:.1%}，消耗 ${cost:.2f}，建议加入否定关键词",
                    }
                )

            # 规则2：高转化低曝光（提升出价建议）
            if conversions >= 1 and impressions < 100:
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "increase_bid",
                        "priority": "high",
                        "current_value": f"conversions={conversions}, impressions={impressions}",
                        "suggested_value": "提升出价 20-30%",
                        "reason": f"该词已有 {conversions} 次转化但曝光仅 {impressions}，建议提升出价扩大曝光",
                    }
                )

            # 规则3：高转化可扩展匹配
            if conversions >= 2 and match_type in ("exact", "完全匹配"):
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "expand_match",
                        "priority": "medium",
                        "current_value": f"conversions={conversions}, match_type={item['match_type']}",
                        "suggested_value": f'词组匹配: "{item["search_term"]}"',
                        "reason": f"高转化完全匹配词，建议同步添加词组匹配版本扩大覆盖",
                    }
                )

            # 规则4：高价值词建议独立Ad Group
            if conversions >= 3:
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "new_ad_group",
                        "priority": "high",
                        "current_value": f"conversions={conversions}",
                        "suggested_value": f"新建Ad Group: [Exact] {item['search_term']}",
                        "reason": f"该词转化 {conversions} 次，建议单独成组精细化管理",
                    }
                )

            # 规则5：低质量分广告文案优化
            if quality_score > 0 and quality_score <= 5:
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "rewrite_headline",
                        "priority": "high",
                        "current_value": f"quality_score={quality_score}/10",
                        "suggested_value": "优化广告标题和描述，提高相关性",
                        "reason": f"关键词质量得分仅 {quality_score}/10，建议优化广告文案提升相关性",
                    }
                )

            # 规则6：零转化高消耗词暂停建议
            if cost >= 10.0 and conversions == 0 and clicks >= 10:
                suggestions.append(
                    {
                        "upload_id": upload_id,
                        "search_term": item["search_term"],
                        "rule_type": "pause_keyword",
                        "priority": "high",
                        "current_value": f"cost=${cost:.2f}, clicks={clicks}, conversions=0",
                        "suggested_value": "暂停关键词",
                        "reason": f"已消耗 ${cost:.2f}，{clicks} 次点击零转化，建议暂停或加入否定",
                    }
                )

        # 插入优化建议
        if suggestions:
            insert_sugg_sql = """
                INSERT INTO ads_optimization_suggestions
                (upload_id, search_term, rule_type, priority, current_value, suggested_value, reason, created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            now = datetime.datetime.now()
            batch_sugg = []
            for s in suggestions:
                batch_sugg.append(
                    (
                        s["upload_id"],
                        s["search_term"],
                        s["rule_type"],
                        s["priority"],
                        s["current_value"],
                        s["suggested_value"],
                        s["reason"],
                        now,
                        "pending",
                    )
                )
            cur.executemany(insert_sugg_sql, batch_sugg)

        # 计算KPI
        total_ctr = (total_clicks / total_impr * 100) if total_impr > 0 else 0.0
        total_roas = (total_conv_value / total_cost) if total_cost > 0 else 0.0

        # 写入KPI实际值
        kpi_metrics = [
            ("impressions", total_impr),
            ("clicks", total_clicks),
            ("ctr", round(total_ctr, 2)),
            ("cost", round(total_cost, 2)),
            ("conversions", total_conv),
            ("roas", round(total_roas, 2)),
            ("conv_value", round(total_conv_value, 2)),
        ]

        insert_kpi_sql = """
            INSERT INTO ads_kpi_actuals
            (upload_id, metric_name, actual_value, record_time)
            VALUES (%s, %s, %s, %s)
        """
        now = datetime.datetime.now()
        batch_kpi = []
        for metric_name, value in kpi_metrics:
            batch_kpi.append((upload_id, metric_name, value, now))
        cur.executemany(insert_kpi_sql, batch_kpi)

        # 更新上传记录状态
        cur.execute(
            """
            UPDATE ads_report_uploads
            SET status = 'done', suggestion_count = %s, analyze_time = %s
            WHERE upload_id = %s
        """,
            (len(suggestions), now, upload_id),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "ok": True,
                "suggestions": len(suggestions),
                "kpi": {
                    "impressions": total_impr,
                    "clicks": total_clicks,
                    "ctr": round(total_ctr, 2),
                    "cost": round(total_cost, 2),
                    "conversions": total_conv,
                    "roas": round(total_roas, 2),
                    "conv_value": round(total_conv_value, 2),
                },
                "msg": f"分析完成，生成 {len(suggestions)} 条优化建议",
            }
        )

    except Exception as e:
        return jsonify({"ok": False, "msg": f"分析失败: {str(e)}"})


@bp.route("/api/optimize/upload_excel", methods=["POST"])
def api_optimize_upload_excel():
    """上传Excel报告文件并解析"""
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "未上传文件"})

        file = request.files["file"]
        report_type = request.form.get("report_type", "keywords")
        merchant_id = request.form.get("merchant_id", "")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")

        if not file or file.filename == "":
            return jsonify({"success": False, "error": "文件为空"})

        if not merchant_id:
            return jsonify({"success": False, "error": "请选择品牌"})

        # 解析Excel
        rows = []
        filename = file.filename.lower()

        if filename.endswith((".xlsx", ".xls")):
            try:
                import openpyxl

                file.seek(0)
                wb = openpyxl.load_workbook(file)
                ws = wb.active

                # 读取表头
                headers = [
                    str(cell.value).strip() if cell.value else "" for cell in ws[1]
                ]

                # 读取数据行
                for row in ws.iter_rows(min_row=2, values_only=True):
                    row_dict = {}
                    for idx, val in enumerate(row):
                        if idx < len(headers) and headers[idx]:
                            row_dict[headers[idx]] = val
                    if row_dict:
                        rows.append(row_dict)

            except Exception as e:
                return jsonify({"success": False, "error": f"Excel解析错误: {e}"})
        else:
            return jsonify({"success": False, "error": "仅支持Excel文件"})

        if not rows:
            return jsonify({"success": False, "error": "文件中没有数据"})

        # 根据报告类型处理数据
        data = []
        for row in rows:
            if report_type == "keywords":
                # 搜索关键字报告
                data.append(
                    {
                        "keyword": row.get("Keyword")
                        or row.get("关键字")
                        or row.get("Search keyword")
                        or "",
                        "match_type": row.get("Match type")
                        or row.get("匹配类型")
                        or "",
                        "campaign": row.get("Campaign") or row.get("广告系列") or "",
                        "ad_group": row.get("Ad group") or row.get("广告组") or "",
                        "impressions": int(
                            float(row.get("Impr.") or row.get("展示次数") or 0)
                        ),
                        "clicks": int(
                            float(row.get("Clicks") or row.get("点击次数") or 0)
                        ),
                        "ctr": float(
                            str(row.get("CTR") or row.get("点击率") or "0").replace(
                                "%", ""
                            )
                        )
                        / 100,
                        "cpc": float(row.get("Avg. CPC") or row.get("平均CPC") or 0),
                        "cost": float(row.get("Cost") or row.get("花费") or 0),
                        "conversions": int(
                            float(row.get("Conversions") or row.get("转化") or 0)
                        ),
                    }
                )
            elif report_type == "search_terms":
                # 搜索字词报告
                data.append(
                    {
                        "search_term": row.get("Search term")
                        or row.get("搜索词")
                        or row.get("Search query")
                        or "",
                        "keyword": row.get("Keyword") or row.get("关键字") or "",
                        "match_type": row.get("Match type")
                        or row.get("匹配类型")
                        or "",
                        "campaign": row.get("Campaign") or row.get("广告系列") or "",
                        "ad_group": row.get("Ad group") or row.get("广告组") or "",
                        "impressions": int(
                            float(row.get("Impr.") or row.get("展示次数") or 0)
                        ),
                        "clicks": int(
                            float(row.get("Clicks") or row.get("点击次数") or 0)
                        ),
                        "ctr": float(
                            str(row.get("CTR") or row.get("点击率") or "0").replace(
                                "%", ""
                            )
                        )
                        / 100,
                        "cpc": float(row.get("Avg. CPC") or row.get("平均CPC") or 0),
                        "cost": float(row.get("Cost") or row.get("花费") or 0),
                        "conversions": int(
                            float(row.get("Conversions") or row.get("转化") or 0)
                        ),
                    }
                )

        # 调用投放数据API保存
        from routes_products import api_workflow_ads_data

        # 构造请求对象
        class FakeRequest:
            def get_json(self, silent=False):
                return {
                    "report_type": report_type,
                    "report_date": end_date,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data": data,
                }

        # 直接保存到数据库
        conn = get_db()
        cur = conn.cursor()

        saved = 0
        if report_type == "keywords":
            for row in data:
                if not row.get("keyword"):
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO ads_keywords_report
                        (merchant_id, report_date, keyword, match_type, campaign, ad_group,
                         impressions, clicks, ctr, cpc, cost, conversions)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            merchant_id,
                            end_date,
                            row.get("keyword", ""),
                            row.get("match_type", ""),
                            row.get("campaign", ""),
                            row.get("ad_group", ""),
                            row.get("impressions", 0),
                            row.get("clicks", 0),
                            row.get("ctr", 0),
                            row.get("cpc", 0),
                            row.get("cost", 0),
                            row.get("conversions", 0),
                        ),
                    )
                    saved += 1
                except Exception as e:
                    print(f"[ERROR] 保存关键字失败: {e}")
        elif report_type == "search_terms":
            for row in data:
                if not row.get("search_term"):
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO ads_search_terms_report
                        (merchant_id, report_date, search_term, keyword, match_type, campaign, ad_group,
                         impressions, clicks, ctr, cpc, cost, conversions)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            merchant_id,
                            end_date,
                            row.get("search_term", ""),
                            row.get("keyword", ""),
                            row.get("match_type", ""),
                            row.get("campaign", ""),
                            row.get("ad_group", ""),
                            row.get("impressions", 0),
                            row.get("clicks", 0),
                            row.get("ctr", 0),
                            row.get("cpc", 0),
                            row.get("cost", 0),
                            row.get("conversions", 0),
                        ),
                    )
                    saved += 1
                except Exception as e:
                    print(f"[ERROR] 保存搜索词失败: {e}")

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "saved_count": saved, "message": f"已保存 {saved} 条数据"}
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


# ─── 广告优化模块（T-004: 数据查询API）────────────────────────────────────


@bp.route("/api/optimize/uploads", methods=["GET"])
def api_optimize_uploads():
    """返回所有上传记录列表"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT upload_id, asin, report_type, file_name, row_count, 
                   status, suggestion_count, upload_time, analyze_time
            FROM ads_report_uploads
            ORDER BY upload_time DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # 转换 datetime 为字符串
        for row in rows:
            for key, val in row.items():
                if isinstance(val, datetime.datetime):
                    row[key] = val.strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({"ok": True, "data": rows})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"查询失败: {str(e)}"})


@bp.route("/api/optimize/suggestions/<upload_id>", methods=["GET"])
def api_optimize_suggestions(upload_id):
    """返回该批次所有优化建议（按priority排序）"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, search_term, rule_type, priority, current_value, 
                   suggested_value, reason, status, created_at
            FROM ads_optimization_suggestions
            WHERE upload_id = %s
            ORDER BY FIELD(priority, 'high', 'medium', 'low') DESC, created_at DESC
        """,
            (upload_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            for key, val in row.items():
                if isinstance(val, datetime.datetime):
                    row[key] = val.strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({"ok": True, "data": rows})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"查询失败: {str(e)}"})


@bp.route("/api/optimize/kpi", methods=["GET"])
def api_optimize_kpi():
    """返回所有KPI目标 + 最新实际值对比"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 获取KPI目标
        cur.execute("""
            SELECT id, metric_name, target_value, alert_threshold, asin, campaign_name, created_at
            FROM ads_kpi_targets
            ORDER BY created_at DESC
        """)
        targets = cur.fetchall()

        # 获取最新实际值
        cur.execute("""
            SELECT t1.upload_id, t1.metric_name, t1.actual_value, t1.record_time
            FROM ads_kpi_actuals t1
            INNER JOIN (
                SELECT metric_name, MAX(record_time) as max_time
                FROM ads_kpi_actuals
                GROUP BY metric_name
            ) t2 ON t1.metric_name = t2.metric_name AND t1.record_time = t2.max_time
        """)
        actuals = cur.fetchall()

        cur.close()
        conn.close()

        # 构建实际值映射
        actual_map = {}
        for act in actuals:
            actual_map[act["metric_name"]] = act["actual_value"]

        # 合并数据
        result = []
        for tgt in targets:
            metric = tgt["metric_name"]
            actual_val = actual_map.get(metric, None)

            result.append(
                {
                    "target_id": tgt["id"],
                    "metric_name": metric,
                    "target_value": tgt["target_value"],
                    "actual_value": actual_val,
                    "alert_threshold": tgt["alert_threshold"],
                    "asin": tgt["asin"],
                    "campaign_name": tgt["campaign_name"],
                    "is_alert": actual_val is not None
                    and abs(actual_val - tgt["target_value"]) > tgt["alert_threshold"],
                }
            )

        return jsonify({"ok": True, "data": result})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"查询失败: {str(e)}"})


@bp.route("/api/optimize/kpi_target", methods=["POST"])
def api_optimize_kpi_target():
    """保存KPI目标"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "msg": "缺少数据"})

        metric_name = data.get("metric_name", "").strip()
        target_value = data.get("target_value")
        alert_threshold = data.get("alert_threshold", 0)
        asin = data.get("asin", "").strip() or None
        campaign_name = data.get("campaign_name", "").strip() or None

        if not metric_name or target_value is None:
            return jsonify({"ok": False, "msg": "metric_name 和 target_value 为必填项"})

        conn = get_db()
        cur = conn.cursor()

        insert_sql = """
            INSERT INTO ads_kpi_targets
            (metric_name, target_value, alert_threshold, asin, campaign_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(
            insert_sql,
            (
                metric_name,
                float(target_value),
                float(alert_threshold),
                asin,
                campaign_name,
                datetime.datetime.now(),
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"ok": True, "msg": "KPI目标已保存"})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"保存失败: {str(e)}"})


@bp.route("/api/optimize/suggestion_action", methods=["POST"])
def api_optimize_suggestion_action():
    """更新优化建议状态（应用/忽略）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "msg": "缺少数据"})

        suggestion_id = data.get("id")
        status = data.get("status", "").strip()

        if not suggestion_id or not status:
            return jsonify({"ok": False, "msg": "id 和 status 为必填项"})

        if status not in ("applied", "dismissed"):
            return jsonify({"ok": False, "msg": "status 必须为 applied 或 dismissed"})

        conn = get_db()
        cur = conn.cursor()

        update_sql = """
            UPDATE ads_optimization_suggestions
            SET status = %s, updated_at = %s
            WHERE id = %s
        """
        cur.execute(update_sql, (status, datetime.datetime.now(), suggestion_id))

        conn.commit()
        affected = cur.rowcount
        cur.close()
        conn.close()

        if affected == 0:
            return jsonify({"ok": False, "msg": "未找到该建议"})

        return jsonify({"ok": True, "msg": f"建议状态已更新为 {status}"})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"更新失败: {str(e)}"})


# ═══════════════════════════════════════════════════════════════════════════
# T-007~T-010: 广告质量评分（Quality Score）后端
# ═══════════════════════════════════════════════════════════════════════════


def _ensure_quality_score_column():
    """T-007: 确保 ads_ads 和 ads_plans 表中存在 quality_score 字段"""
    try:
        conn = get_db()
        cur = conn.cursor()
        # ads_ads 表加 quality_score
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ads_ads'
              AND COLUMN_NAME = 'quality_score'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute(
                "ALTER TABLE ads_ads ADD COLUMN quality_score FLOAT DEFAULT NULL COMMENT 'QS评分0-100'"
            )
            cur.execute(
                "ALTER TABLE ads_ads ADD COLUMN qs_detail JSON DEFAULT NULL COMMENT 'QS各维度明细'"
            )
            conn.commit()
        # ads_plans 表加 avg_quality_score
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ads_plans'
              AND COLUMN_NAME = 'avg_quality_score'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute(
                "ALTER TABLE ads_plans ADD COLUMN avg_quality_score FLOAT DEFAULT NULL COMMENT '方案平均QS'"
            )
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        app.logger.warning(f"_ensure_quality_score_column: {e}")


def calculate_quality_score(ad_data):
    """T-008: 计算单条广告的 Quality Score（0-100）

    评分维度（共100分）：
    - 标题质量     (30分): 数量/长度/含关键词/含数字/含CTA
    - 描述质量     (25分): 数量/长度/含USP/字符合规
    - 扩展资产     (20分): sitelinks/callouts/structured_snippet
    - 合规性       (15分): 所有字段字符数是否合规
    - 文案多样性   (10分): A/B变体区别度
    """
    import json as _json

    score = 0.0
    detail = {}

    # 解析 JSON 字段
    try:
        headlines = (
            _json.loads(ad_data.get("headlines", "[]"))
            if isinstance(ad_data.get("headlines"), str)
            else (ad_data.get("headlines") or [])
        )
    except Exception:
        headlines = []
    try:
        descriptions = (
            _json.loads(ad_data.get("descriptions", "[]"))
            if isinstance(ad_data.get("descriptions"), str)
            else (ad_data.get("descriptions") or [])
        )
    except Exception:
        descriptions = []
    try:
        sitelinks = (
            _json.loads(ad_data.get("sitelinks", "[]"))
            if isinstance(ad_data.get("sitelinks"), str)
            else (ad_data.get("sitelinks") or [])
        )
    except Exception:
        sitelinks = []
    try:
        callouts = (
            _json.loads(ad_data.get("callouts", "[]"))
            if isinstance(ad_data.get("callouts"), str)
            else (ad_data.get("callouts") or [])
        )
    except Exception:
        callouts = []
    try:
        snippets = (
            _json.loads(ad_data.get("structured_snippet", "{}"))
            if isinstance(ad_data.get("structured_snippet"), str)
            else (ad_data.get("structured_snippet") or {})
        )
    except Exception:
        snippets = {}

    # ── 1. 标题质量 (30分) ──
    hl_texts = []
    for h in headlines:
        if isinstance(h, dict):
            hl_texts.append(h.get("text", ""))
        elif isinstance(h, str):
            hl_texts.append(h)
    hl_count = len(hl_texts)
    hl_score = 0.0
    # 数量分：3条=6，5条=10，8条=14，≥10条=16
    hl_count_map = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15}
    hl_score += hl_count_map.get(min(hl_count, 9), 16) if hl_count < 10 else 16
    # 长度分：平均长度 ≥ 20 加4分
    if hl_texts:
        avg_len = sum(len(t) for t in hl_texts) / len(hl_texts)
        hl_score += min(avg_len / 30.0 * 8.0, 8.0)
    # 合规分：所有标题 ≤ 30 字符
    hl_valid = all(len(t) <= 30 for t in hl_texts) if hl_texts else False
    hl_score += 6.0 if hl_valid else 0.0
    score += min(hl_score, 30.0)
    detail["headline"] = round(min(hl_score, 30.0), 1)

    # ── 2. 描述质量 (25分) ──
    desc_texts = []
    for d in descriptions:
        if isinstance(d, dict):
            desc_texts.append(d.get("text", ""))
        elif isinstance(d, str):
            desc_texts.append(d)
    desc_count = len(desc_texts)
    desc_score = 0.0
    # 数量分
    desc_count_map = {0: 0, 1: 5, 2: 10, 3: 12, 4: 14}
    desc_score += desc_count_map.get(min(desc_count, 4), 14)
    # 长度分：平均 ≥ 70 字符
    if desc_texts:
        avg_dlen = sum(len(t) for t in desc_texts) / len(desc_texts)
        desc_score += min(avg_dlen / 90.0 * 7.0, 7.0)
    # 合规分：所有描述 ≤ 90 字符
    desc_valid = all(len(t) <= 90 for t in desc_texts) if desc_texts else False
    desc_score += 4.0 if desc_valid else 0.0
    score += min(desc_score, 25.0)
    detail["description"] = round(min(desc_score, 25.0), 1)

    # ── 3. 扩展资产 (20分) ──
    asset_score = 0.0
    # Sitelinks：有2条+6分，有4条+10分
    sl_count = len(sitelinks) if isinstance(sitelinks, list) else 0
    asset_score += min(sl_count / 4.0 * 10.0, 10.0)
    # Callouts：有2条+4分，有4条+6分
    co_count = len(callouts) if isinstance(callouts, list) else 0
    asset_score += min(co_count / 4.0 * 6.0, 6.0)
    # Structured Snippet
    if (
        snippets
        and (isinstance(snippets, dict) and snippets.get("values"))
        or isinstance(snippets, list)
    ):
        asset_score += 4.0
    score += min(asset_score, 20.0)
    detail["assets"] = round(min(asset_score, 20.0), 1)

    # ── 4. 合规性 (15分) ──
    compliance_score = 15.0
    # 有违规标题扣分
    bad_hl = [t for t in hl_texts if len(t) > 30]
    bad_desc = [t for t in desc_texts if len(t) > 90]
    compliance_score -= len(bad_hl) * 3.0
    compliance_score -= len(bad_desc) * 4.0
    compliance_score = max(compliance_score, 0.0)
    # all_chars_valid 字段
    if ad_data.get("all_chars_valid"):
        compliance_score = min(compliance_score + 3.0, 15.0)
    score += compliance_score
    detail["compliance"] = round(compliance_score, 1)

    # ── 5. 文案多样性 (10分) ──
    diversity_score = 5.0  # 基础分
    if hl_count >= 10 and desc_count >= 4:
        diversity_score = 10.0
    elif hl_count >= 8 and desc_count >= 3:
        diversity_score = 8.0
    elif hl_count >= 5 and desc_count >= 2:
        diversity_score = 7.0
    score += diversity_score
    detail["diversity"] = round(diversity_score, 1)

    total = round(min(score, 100.0), 1)
    detail["total"] = total
    return total, detail


@bp.route("/api/ads/score/<asin>", methods=["POST"])
def api_ads_score_asin(asin):
    """T-009: 对指定 ASIN 的所有广告计算 QS 评分，更新 ads_ads 表，返回平均分"""
    try:
        _ensure_quality_score_column()
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT a.id, a.variant, a.headlines, a.descriptions,
                   a.sitelinks, a.callouts, a.structured_snippet,
                   a.all_chars_valid
            FROM ads_ads a
            WHERE a.asin = %s
        """,
            (asin,),
        )
        ads = cur.fetchall()
        if not ads:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "msg": f"未找到 ASIN={asin} 的广告"})

        results = []
        import json as _json

        for ad in ads:
            qs, detail = calculate_quality_score(ad)
            cur.execute(
                """
                UPDATE ads_ads SET quality_score=%s, qs_detail=%s, updated_at=NOW()
                WHERE id=%s
            """,
                (qs, _json.dumps(detail), ad["id"]),
            )
            results.append(
                {
                    "ad_id": ad["id"],
                    "variant": ad["variant"],
                    "qs": qs,
                    "detail": detail,
                }
            )

        # 更新 ads_plans 的平均分
        avg_qs = sum(r["qs"] for r in results) / len(results) if results else 0
        cur.execute(
            """
            UPDATE ads_plans SET avg_quality_score=%s, updated_at=NOW()
            WHERE asin=%s
        """,
            (round(avg_qs, 1), asin),
        )

        conn.commit()
        cur.close()
        conn.close()
        return jsonify(
            {"ok": True, "asin": asin, "avg_qs": round(avg_qs, 1), "ads": results}
        )

    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@bp.route("/api/ads/scores", methods=["GET"])
def api_ads_scores_all():
    """T-009: 获取所有 ASIN 的平均 QS 评分列表（用于 /qs_dashboard）"""
    try:
        _ensure_quality_score_column()
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT p.asin, p.product_name, p.avg_quality_score,
                   p.ad_count,
                   COUNT(a.id) AS scored_ads,
                   SUM(CASE WHEN a.quality_score >= 80 THEN 1 ELSE 0 END) AS qs_good,
                   SUM(CASE WHEN a.quality_score >= 60 AND a.quality_score < 80 THEN 1 ELSE 0 END) AS qs_ok,
                   SUM(CASE WHEN a.quality_score < 60 THEN 1 ELSE 0 END) AS qs_bad
            FROM ads_plans p
            LEFT JOIN ads_ads a ON a.asin = p.asin
            WHERE p.plan_status = 'completed'
            GROUP BY p.asin, p.product_name, p.avg_quality_score, p.ad_count
            ORDER BY p.avg_quality_score ASC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # 汇总统计
        total_ads = sum(r["scored_ads"] or 0 for r in rows)
        qs_good_total = sum(r["qs_good"] or 0 for r in rows)
        qs_bad_total = sum(r["qs_bad"] or 0 for r in rows)
        avg_overall = (
            sum((r["avg_quality_score"] or 0) for r in rows) / len(rows) if rows else 0
        )

        return jsonify(
            {
                "ok": True,
                "summary": {
                    "total_asins": len(rows),
                    "total_ads": total_ads,
                    "avg_qs": round(avg_overall, 1),
                    "qs_good": qs_good_total,
                    "qs_bad": qs_bad_total,
                },
                "items": rows,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@bp.route("/api/ads/score_batch", methods=["POST"])
def api_ads_score_batch():
    """T-009: 对所有 completed 方案批量计算 QS，后台更新"""
    try:
        _ensure_quality_score_column()
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT DISTINCT asin FROM ads_plans WHERE plan_status='completed'")
        asins = [r["asin"] for r in cur.fetchall()]
        cur.close()
        conn.close()

        updated = 0
        import json as _json

        for asin in asins:
            conn2 = get_db()
            cur2 = conn2.cursor(dictionary=True)
            cur2.execute(
                """
                SELECT id, variant, headlines, descriptions,
                       sitelinks, callouts, structured_snippet, all_chars_valid
                FROM ads_ads WHERE asin=%s
            """,
                (asin,),
            )
            ads = cur2.fetchall()
            if not ads:
                cur2.close()
                conn2.close()
                continue
            scores = []
            for ad in ads:
                qs, detail = calculate_quality_score(ad)
                cur2.execute(
                    "UPDATE ads_ads SET quality_score=%s, qs_detail=%s, updated_at=NOW() WHERE id=%s",
                    (qs, _json.dumps(detail), ad["id"]),
                )
                scores.append(qs)
            avg_qs = sum(scores) / len(scores) if scores else 0
            cur2.execute(
                "UPDATE ads_plans SET avg_quality_score=%s, updated_at=NOW() WHERE asin=%s",
                (round(avg_qs, 1), asin),
            )
            conn2.commit()
            cur2.close()
            conn2.close()
            updated += 1

        return jsonify({"ok": True, "msg": f"已批量评分 {updated} 个 ASIN"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


# T-010: 在 Flask 启动时自动初始化 quality_score 字段（调用一次）
try:
    with app.app_context():
        _ensure_quality_score_column()
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════════════
# 投放优化模块 - 前端页面
# ═══════════════════════════════════════════════════════════════════════════

OPTIMIZE_HTML = (
    """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投放优化 - YP Affiliate</title>
<style>
"""
    + BASE_CSS
    + """
/* 投放优化专用样式 */
.tab-nav { display: flex; gap: 4px; border-bottom: 1px solid #2a2d36; margin-bottom: 20px; }
.tab-nav button {
  padding: 12px 24px; background: transparent; border: none; color: #888;
  font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent;
  transition: all .15s;
}
.tab-nav button:hover { color: #e0e0e0; }
.tab-nav button.active { color: #ffa726; border-bottom-color: #ffa726; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* 上传区域 */
.upload-zone {
  border: 2px dashed #2a2d36; border-radius: 12px; padding: 40px;
  text-align: center; background: #15181f; transition: all .15s;
  cursor: pointer;
}
.upload-zone:hover { border-color: #ffa726; background: #1a1d24; }
.upload-zone.dragover { border-color: #ffa726; background: #1e2129; }
.upload-icon { font-size: 48px; margin-bottom: 16px; }
.upload-text { color: #adb5bd; font-size: 14px; margin-bottom: 8px; }
.upload-hint { color: #666; font-size: 12px; }
.file-preview {
  display: flex; align-items: center; gap: 12px; padding: 16px;
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 8px;
  margin-top: 16px;
}
.file-icon { font-size: 32px; }
.file-info { flex: 1; }
.file-name { font-weight: 600; color: #fff; }
.file-size { color: #888; font-size: 12px; }

/* 表单样式 */
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; color: #adb5bd; font-size: 13px; }
.form-group input, .form-group select {
  width: 100%; padding: 10px 14px; border: 1px solid #2a2d36;
  border-radius: 8px; background: #15181f; color: #e0e0e0; font-size: 13px;
}
.form-group input:focus, .form-group select:focus { outline: none; border-color: #ffa726; }
.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }

/* 进度条 */
.progress-bar {
  height: 8px; background: #23262f; border-radius: 4px; overflow: hidden;
  margin-top: 12px;
}
.progress-fill {
  height: 100%; background: linear-gradient(90deg, #ffa726, #ff7043);
  border-radius: 4px; transition: width .3s ease;
}
.progress-text { text-align: center; margin-top: 8px; font-size: 12px; color: #888; }

/* 建议卡片 */
.suggestion-card {
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
  padding: 20px; margin-bottom: 16px; position: relative;
  border-left: 4px solid #2a2d36;
}
.suggestion-card.priority-high { border-left-color: #ef5350; }
.suggestion-card.priority-medium { border-left-color: #ffa726; }
.suggestion-card.priority-low { border-left-color: #64b5f6; }
.suggestion-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
}
.suggestion-type {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;
}
.suggestion-type.negative { background: #3d1a1a; color: #ef5350; }
.suggestion-type.bid { background: #1a3d1a; color: #66bb6a; }
.suggestion-type.match { background: #0a2040; color: #64b5f6; }
.suggestion-type.adgroup { background: #2a1a4a; color: #ce93d8; }
.suggestion-type.copy { background: #3d2a0a; color: #ffa726; }
.suggestion-type.pause { background: #23262f; color: #888; }
.suggestion-keyword {
  font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px;
}
.suggestion-reason { color: #adb5bd; font-size: 13px; margin-bottom: 8px; }
.suggestion-action { color: #ffa726; font-size: 13px; font-weight: 500; }
.suggestion-data {
  display: flex; gap: 20px; margin: 12px 0; padding: 12px;
  background: #15181f; border-radius: 8px; font-size: 12px;
}
.suggestion-data span { color: #888; }
.suggestion-data strong { color: #fff; margin-left: 4px; }
.suggestion-actions {
  display: flex; gap: 10px; margin-top: 12px;
}
.suggestion-actions button { flex: 1; }

/* KPI卡片 */
.kpi-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 24px;
}
.kpi-card {
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
  padding: 20px; text-align: center;
}
.kpi-card.status-good { border-color: #2e7d32; }
.kpi-card.status-warning { border-color: #e65100; }
.kpi-card.status-danger { border-color: #c62828; }
.kpi-label { font-size: 12px; color: #888; text-transform: uppercase; margin-bottom: 8px; }
.kpi-value { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.kpi-value.good { color: #66bb6a; }
.kpi-value.warning { color: #ffa726; }
.kpi-value.danger { color: #ef5350; }
.kpi-target { font-size: 12px; color: #666; margin-bottom: 4px; }
.kpi-change { font-size: 12px; }
.kpi-change.up { color: #66bb6a; }
.kpi-change.down { color: #ef5350; }

/* 统计栏 */
.stats-bar {
  display: flex; gap: 24px; padding: 16px 20px;
  background: #15181f; border-radius: 8px; margin-bottom: 20px;
}
.stat-item { text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: #fff; }
.stat-label { font-size: 12px; color: #888; margin-top: 4px; }

/* 加载状态 */
.loading-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 17, 23, 0.8); display: none;
  align-items: center; justify-content: center; z-index: 1000;
}
.loading-overlay.active { display: flex; }
.loading-spinner {
  width: 48px; height: 48px; border: 3px solid #2a2d36;
  border-top-color: #ffa726; border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { margin-top: 16px; color: #adb5bd; text-align: center; }

/* 空状态 */
.empty-state {
  text-align: center; padding: 60px 20px; color: #666;
}
.empty-state-icon { font-size: 64px; margin-bottom: 16px; }
.empty-state-title { font-size: 18px; color: #adb5bd; margin-bottom: 8px; }
.empty-state-desc { font-size: 14px; }
</style>
</head>
<body>
"""
    + NAV_HTML.format(
        p0="",
        p1="",
        p2="",
        p3="",
        p4="",
        p5="",
        p6="active",
        p7="",
        p8="",
        p9="",
        p10="",
        p11="",
    )
    + """
<div class="container">
  <h1 style="font-size: 20px; margin-bottom: 20px;">📈 投放优化</h1>
  
  <div class="tab-nav">
    <button class="active" onclick="switchTab(0)">📤 数据上传</button>
    <button onclick="switchTab(1)">📊 ROI 分析</button>
    <button onclick="switchTab(2)">💡 优化建议</button>
    <button onclick="switchTab(3)">🎯 KPI 目标</button>
  </div>
  
  <!-- Tab 0: 数据上传 -->
  <div class="tab-content active" id="tab-upload">
    <!-- 核心数据上传区 -->
    <div class="card">
      <h2>🔑 核心数据 <span style="font-size:12px;color:#888;font-weight:normal">（每1-2周上传一次）</span></h2>
      <p style="color:#888;font-size:13px;margin-bottom:20px;">
        上传以下4项数据即可生成完整的优化报告。建议固定周期上传，追踪效果趋势。
      </p>
      
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:20px;">
        <!-- 1. 搜索关键字报告 -->
        <div class="upload-card" style="background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="font-size:24px;">📊</span>
            <div>
              <div style="font-weight:600;color:#fff;">搜索关键字报告</div>
              <div style="font-size:12px;color:#888;">Google Ads → 报告 → 搜索关键字</div>
            </div>
          </div>
          <div class="upload-zone-sm" id="zone-keywords" onclick="triggerUpload('keywords')" style="border:2px dashed #2a2d36;border-radius:8px;padding:20px;text-align:center;cursor:pointer;">
            <div style="color:#888;font-size:13px;">点击上传 .xlsx/.csv</div>
          </div>
          <input type="file" id="file-keywords" style="display:none" accept=".xlsx,.xls,.csv" onchange="handleReportUpload('keywords', event)">
          <div id="status-keywords" style="margin-top:10px;font-size:12px;color:#888;"></div>
        </div>
        
        <!-- 2. 搜索字词报告 -->
        <div class="upload-card" style="background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="font-size:24px;">🔍</span>
            <div>
              <div style="font-weight:600;color:#fff;">搜索字词报告</div>
              <div style="font-size:12px;color:#888;">Google Ads → 报告 → 搜索字词</div>
            </div>
          </div>
          <div class="upload-zone-sm" id="zone-search_terms" onclick="triggerUpload('search_terms')" style="border:2px dashed #2a2d36;border-radius:8px;padding:20px;text-align:center;cursor:pointer;">
            <div style="color:#888;font-size:13px;">点击上传 .xlsx/.csv</div>
          </div>
          <input type="file" id="file-search_terms" style="display:none" accept=".xlsx,.xls,.csv" onchange="handleReportUpload('search_terms', event)">
          <div id="status-search_terms" style="margin-top:10px;font-size:12px;color:#888;"></div>
        </div>
        
        <!-- 3. YP品牌报表 -->
        <div class="upload-card" style="background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="font-size:24px;">💰</span>
            <div>
              <div style="font-weight:600;color:#fff;">YP品牌报表</div>
              <div style="font-size:12px;color:#888;">YP后台截图或手动输入</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px;">
            <div>
              <label style="font-size:11px;color:#888;">点击数</label>
              <input type="number" id="yp-clicks" style="width:100%;padding:8px;border-radius:6px;border:1px solid #2a2d36;background:#15181f;color:#fff;" placeholder="0">
            </div>
            <div>
              <label style="font-size:11px;color:#888;">加购数</label>
              <input type="number" id="yp-add_to_carts" style="width:100%;padding:8px;border-radius:6px;border:1px solid #2a2d36;background:#15181f;color:#fff;" placeholder="0">
            </div>
            <div>
              <label style="font-size:11px;color:#888;">购买数</label>
              <input type="number" id="yp-purchases" style="width:100%;padding:8px;border-radius:6px;border:1px solid #2a2d36;background:#15181f;color:#fff;" placeholder="0">
            </div>
            <div>
              <label style="font-size:11px;color:#888;">佣金($)</label>
              <input type="number" id="yp-commission" step="0.01" style="width:100%;padding:8px;border-radius:6px;border:1px solid #2a2d36;background:#15181f;color:#fff;" placeholder="0.00">
            </div>
          </div>
          <button class="btn btn-sm btn-primary" onclick="saveYpReport()">💾 保存YP数据</button>
          <div id="status-yp_report" style="margin-top:10px;font-size:12px;color:#888;"></div>
        </div>
        
        <!-- 4. 花费金额 -->
        <div class="upload-card" style="background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="font-size:24px;">💵</span>
            <div>
              <div style="font-weight:600;color:#fff;">Google Ads花费</div>
              <div style="font-size:12px;color:#888;">实际充值/花费金额</div>
            </div>
          </div>
          <div style="display:flex;gap:10px;align-items:end;">
            <div style="flex:1;">
              <label style="font-size:11px;color:#888;">花费金额 ($)</label>
              <input type="number" id="cost-amount" step="0.01" style="width:100%;padding:8px;border-radius:6px;border:1px solid #2a2d36;background:#15181f;color:#fff;" placeholder="0.00">
            </div>
            <button class="btn btn-sm btn-primary" onclick="saveCostData()">💾 保存</button>
          </div>
          <div id="status-cost" style="margin-top:10px;font-size:12px;color:#888;"></div>
        </div>
      </div>
      
      <!-- 日期范围和品牌选择 -->
      <div class="form-row" style="margin-top:20px;padding-top:20px;border-top:1px solid #2a2d36;">
        <div class="form-group">
          <label>品牌/商户ID</label>
          <select id="merchant-select" onchange="loadMerchantData()">
            <option value="">选择品牌...</option>
          </select>
        </div>
        <div class="form-group">
          <label>开始日期</label>
          <input type="date" id="start-date">
        </div>
        <div class="form-group">
          <label>结束日期</label>
          <input type="date" id="end-date">
        </div>
        <div class="form-group" style="display:flex;align-items:end;">
          <button class="btn btn-success" onclick="calculateROI()" style="width:100%;">📊 计算ROI</button>
        </div>
      </div>
    </div>
    
    <!-- 补充数据上传区 -->
    <div class="card">
      <h2>📋 补充数据 <span style="font-size:12px;color:#888;font-weight:normal">（可选，提升分析精度）</span></h2>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
        <div style="background:#15181f;border-radius:8px;padding:16px;">
          <div style="font-weight:600;margin-bottom:8px;">🖼️ Campaign截图</div>
          <input type="file" id="file-campaign" accept="image/*,.pdf" style="font-size:12px;" onchange="handleImageUpload('campaign', event)">
          <div id="status-campaign" style="font-size:11px;color:#888;margin-top:6px;"></div>
        </div>
        <div style="background:#15181f;border-radius:8px;padding:16px;">
          <div style="font-weight:600;margin-bottom:8px;">📈 广告组CTR</div>
          <input type="file" id="file-ad_group" accept=".xlsx,.xls,.csv" style="font-size:12px;" onchange="handleReportUpload('ad_group', event)">
          <div id="status-ad_group" style="font-size:11px;color:#888;margin-top:6px;"></div>
        </div>
        <div style="background:#15181f;border-radius:8px;padding:16px;">
          <div style="font-weight:600;margin-bottom:8px;">📝 广告文案数据</div>
          <input type="file" id="file-ad_copy" accept=".xlsx,.xls,.csv" style="font-size:12px;" onchange="handleReportUpload('ad_copy', event)">
          <div id="status-ad_copy" style="font-size:11px;color:#888;margin-top:6px;"></div>
        </div>
      </div>
    </div>
    
    <!-- 历史记录 -->
    <div class="card">
      <h2>📅 历史数据记录</h2>
      <table>
        <thead>
          <tr>
            <th>日期范围</th>
            <th>品牌</th>
            <th>Google花费</th>
            <th>YP佣金</th>
            <th>ROI</th>
            <th>关键字数</th>
            <th>搜索词数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="history-table">
          <tr><td colspan="8" style="text-align:center;color:#666;padding:40px;">加载中...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
  
  <!-- Tab 1: ROI分析 -->
  <div class="tab-content" id="tab-roi">
    <div class="card">
      <h2>📊 ROI 分析仪表盘</h2>
      <div id="roi-dashboard">
        <div class="empty-state">
          <div class="empty-state-icon">📊</div>
          <div class="empty-state-title">请先上传数据并计算ROI</div>
          <div class="empty-state-desc">在"数据上传"页面填写完整数据后点击"计算ROI"</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h2>📈 关键字效果分析</h2>
      <div id="keywords-analysis">
        <div class="empty-state">
          <div class="empty-state-icon">🔑</div>
          <div class="empty-state-title">暂无关键字数据</div>
          <div class="empty-state-desc">上传搜索关键字报告后显示分析结果</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h2>🔍 搜索字词分析</h2>
      <div id="search-terms-analysis">
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">暂无搜索字词数据</div>
          <div class="empty-state-desc">上传搜索字词报告后显示分析结果</div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Tab 2: 优化建议 -->
  <div class="tab-content" id="tab-suggestions">
    <div class="card">
      <div class="filters">
        <select id="batch-filter" onchange="loadSuggestions()">
          <option value="">选择上传批次</option>
        </select>
        <select id="type-filter" onchange="loadSuggestions()">
          <option value="">全部建议类型</option>
          <option value="negative">加否定词</option>
          <option value="bid">提升出价</option>
          <option value="match">扩展匹配</option>
          <option value="adgroup">新建AdGroup</option>
          <option value="copy">改文案</option>
          <option value="pause">暂停词</option>
        </select>
        <select id="priority-filter" onchange="loadSuggestions()">
          <option value="">全部优先级</option>
          <option value="high">高</option>
          <option value="medium">中</option>
          <option value="low">低</option>
        </select>
        <button class="btn btn-secondary" onclick="loadSuggestions()">🔄 刷新</button>
      </div>
      
      <div class="stats-bar" id="suggestion-stats">
        <div class="stat-item"><div class="stat-value" id="stat-total">-</div><div class="stat-label">总建议</div></div>
        <div class="stat-item"><div class="stat-value" id="stat-high">-</div><div class="stat-label">高优先级</div></div>
        <div class="stat-item"><div class="stat-value" id="stat-pending">-</div><div class="stat-label">待处理</div></div>
        <div class="stat-item"><div class="stat-value" id="stat-adopted">-</div><div class="stat-label">已采纳</div></div>
      </div>
    </div>
    
    <div id="suggestions-list">
      <div class="empty-state">
        <div class="empty-state-icon">💡</div>
        <div class="empty-state-title">请先选择上传批次</div>
        <div class="empty-state-desc">选择上方下拉菜单中的批次查看优化建议</div>
      </div>
    </div>
  </div>
  
  <!-- Tab 3: KPI 仪表盘 -->
  <div class="tab-content" id="tab-kpi">
    <div class="card">
      <h2>设置 KPI 目标</h2>
      <div class="form-row">
        <div class="form-group">
          <label>指标</label>
          <select id="kpi-metric">
            <option value="roas">ROAS</option>
            <option value="cpa">CPA</option>
            <option value="ctr">CTR</option>
            <option value="cvr">CVR</option>
            <option value="cpc">CPC</option>
          </select>
        </div>
        <div class="form-group">
          <label>目标值</label>
          <input type="number" id="kpi-target" placeholder="如: 3" step="0.1">
        </div>
        <div class="form-group">
          <label>报警阈值 (%)</label>
          <input type="number" id="kpi-threshold" placeholder="如: 20" value="20">
        </div>
        <div class="form-group">
          <label>ASIN/Campaign (可选)</label>
          <input type="text" id="kpi-scope" placeholder="全部">
        </div>
      </div>
      <button class="btn btn-primary" onclick="saveKpiTarget()">💾 保存目标</button>
    </div>
    
    <div class="card">
      <h2>KPI 达成状态</h2>
      <div class="kpi-grid" id="kpi-cards">
        <div class="kpi-card status-good">
          <div class="kpi-label">ROAS</div>
          <div class="kpi-value good">🟢 4.2x</div>
          <div class="kpi-target">目标: 3x</div>
          <div class="kpi-change up">↑ 40% 超标</div>
        </div>
        <div class="kpi-card status-danger">
          <div class="kpi-label">CPA</div>
          <div class="kpi-value danger">🔴 $18</div>
          <div class="kpi-target">目标: $15</div>
          <div class="kpi-change down">↑ 20% 超标</div>
        </div>
        <div class="kpi-card status-warning">
          <div class="kpi-label">CTR</div>
          <div class="kpi-value warning">🟡 3.2%</div>
          <div class="kpi-target">目标: 4%</div>
          <div class="kpi-change down">↓ 20%</div>
        </div>
        <div class="kpi-card status-good">
          <div class="kpi-label">CVR</div>
          <div class="kpi-value good">🟢 2.1%</div>
          <div class="kpi-target">目标: 2%</div>
          <div class="kpi-change">达标</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h2>最近批次数据摘要</h2>
      <table>
        <thead>
          <tr>
            <th>批次时间</th>
            <th>总花费</th>
            <th>总点击</th>
            <th>总转化</th>
            <th>ROAS</th>
            <th>CTR</th>
            <th>CVR</th>
            <th>建议数</th>
          </tr>
        </thead>
        <tbody id="batch-summary">
          <tr><td colspan="8" style="text-align:center;color:#666;padding:40px;">加载中...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- 加载遮罩 -->
<div class="loading-overlay" id="loading-overlay">
  <div>
    <div class="loading-spinner"></div>
    <div class="loading-text" id="loading-text">处理中...</div>
  </div>
</div>

<script>
let currentFile = null;
let currentUploadId = null;
let currentMerchantId = null;

// Tab切换
function switchTab(index) {
  document.querySelectorAll('.tab-nav button').forEach((btn, i) => {
    btn.classList.toggle('active', i === index);
  });
  document.querySelectorAll('.tab-content').forEach((content, i) => {
    content.classList.toggle('active', i === index);
  });
  if (index === 0) loadMerchants();
  if (index === 1) loadRoiDashboard();
  if (index === 2) loadBatchOptions();
  if (index === 3) loadKpiData();
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
  // 设置默认日期范围
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
  document.getElementById('start-date').value = firstDay.toISOString().slice(0, 10);
  document.getElementById('end-date').value = today.toISOString().slice(0, 10);
  
  // 加载商户列表
  loadMerchants();
});

// 加载商户列表
function loadMerchants() {
  fetch('/api/merchants?limit=100')
  .then(r => r.json())
  .then(data => {
    const select = document.getElementById('merchant-select');
    select.innerHTML = '<option value="">选择品牌...</option>';
    if (data.merchants) {
      data.merchants.forEach(m => {
        select.innerHTML += `<option value="${m.merchant_id}">${m.merchant_name || m.merchant_id}</option>`;
      });
    }
  })
  .catch(e => console.error('加载商户失败:', e));
}

// 加载商户数据
function loadMerchantData() {
  const merchantId = document.getElementById('merchant-select').value;
  if (!merchantId) return;
  
  currentMerchantId = merchantId;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;
  
  // 加载已有数据
  fetch(`/api/workflow/ads_data/${merchantId}?start_date=${startDate}&end_date=${endDate}`)
  .then(r => r.json())
  .then(data => {
    if (data.success && data.data) {
      // 更新状态显示
      if (data.data.summary) {
        const s = data.data.summary;
        if (s.google_cost) document.getElementById('cost-amount').value = s.google_cost;
      }
      if (data.data.keywords_stats) {
        const ks = data.data.keywords_stats;
        document.getElementById('status-keywords').innerHTML = 
          `<span style="color:#4caf50;">✓ ${ks.keyword_count || 0} 个关键字，花费 $${ks.total_cost || 0}</span>`;
      }
      if (data.data.search_terms_stats) {
        const ts = data.data.search_terms_stats;
        document.getElementById('status-search_terms').innerHTML = 
          `<span style="color:#4caf50;">✓ ${ts.term_count || 0} 个搜索词</span>`;
      }
    }
  })
  .catch(e => console.error('加载商户数据失败:', e));
}

// 触发文件上传
function triggerUpload(type) {
  document.getElementById('file-' + type).click();
}

// 处理报告上传
function handleReportUpload(type, event) {
  const file = event.target.files[0];
  if (!file) return;
  
  const merchantId = currentMerchantId || document.getElementById('merchant-select').value;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;
  
  if (!merchantId) {
    toast('请先选择品牌', 'error');
    return;
  }
  
  const statusEl = document.getElementById('status-' + type);
  statusEl.innerHTML = '<span style="color:#ffa726;">⏳ 上传中...</span>';
  
  // 读取文件内容
  const reader = new FileReader();
  reader.onload = function(e) {
    let data = [];
    
    // 解析CSV/Excel
    if (file.name.endsWith('.csv')) {
      const lines = e.target.result.split('\\n');
      const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
      for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const values = lines[i].split(',');
        const row = {};
        headers.forEach((h, idx) => {
          row[h] = (values[idx] || '').trim().replace(/"/g, '');
        });
        data.push(row);
      }
    } else {
      // Excel需要后端解析
      statusEl.innerHTML = '<span style="color:#ffa726;">⏳ 解析Excel...</span>';
      uploadExcelFile(type, file, merchantId, startDate, endDate, statusEl);
      return;
    }
    
    // 发送到后端
    submitReportData(type, data, merchantId, startDate, endDate, statusEl);
  };
  reader.readAsText(file);
}

// 上传Excel文件
function uploadExcelFile(type, file, merchantId, startDate, endDate, statusEl) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('report_type', type);
  formData.append('merchant_id', merchantId);
  formData.append('start_date', startDate);
  formData.append('end_date', endDate);
  
  fetch('/api/optimize/upload_excel', {
    method: 'POST',
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      statusEl.innerHTML = `<span style="color:#4caf50;">✓ 已保存 ${data.saved_count || 0} 条数据</span>`;
      toast('上传成功', 'success');
    } else {
      statusEl.innerHTML = `<span style="color:#ef5350;">✗ ${data.error || '上传失败'}</span>`;
    }
  })
  .catch(e => {
    statusEl.innerHTML = `<span style="color:#ef5350;">✗ 上传失败: ${e.message}</span>`;
  });
}

// 提交报告数据
function submitReportData(type, data, merchantId, startDate, endDate, statusEl) {
  fetch(`/api/workflow/ads_data/${merchantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_type: type,
      report_date: endDate,
      start_date: startDate,
      end_date: endDate,
      data: data
    })
  })
  .then(r => r.json())
  .then(result => {
    if (result.success) {
      statusEl.innerHTML = `<span style="color:#4caf50;">✓ ${result.message}</span>`;
      toast('上传成功', 'success');
    } else {
      statusEl.innerHTML = `<span style="color:#ef5350;">✗ ${result.error}</span>`;
    }
  })
  .catch(e => {
    statusEl.innerHTML = `<span style="color:#ef5350;">✗ 上传失败: ${e.message}</span>`;
  });
}

// 保存YP报表数据
function saveYpReport() {
  const merchantId = currentMerchantId || document.getElementById('merchant-select').value;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;
  
  if (!merchantId) {
    toast('请先选择品牌', 'error');
    return;
  }
  
  const ypData = {
    clicks: parseInt(document.getElementById('yp-clicks').value) || 0,
    add_to_carts: parseInt(document.getElementById('yp-add_to_carts').value) || 0,
    purchases: parseInt(document.getElementById('yp-purchases').value) || 0,
    commission: parseFloat(document.getElementById('yp-commission').value) || 0
  };
  
  const statusEl = document.getElementById('status-yp_report');
  statusEl.innerHTML = '<span style="color:#ffa726;">⏳ 保存中...</span>';
  
  fetch(`/api/workflow/ads_data/${merchantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_type: 'yp_report',
      start_date: startDate,
      end_date: endDate,
      yp_data: ypData
    })
  })
  .then(r => r.json())
  .then(result => {
    if (result.success) {
      statusEl.innerHTML = `<span style="color:#4caf50;">✓ YP数据已保存</span>`;
      toast('YP数据保存成功', 'success');
    } else {
      statusEl.innerHTML = `<span style="color:#ef5350;">✗ ${result.error}</span>`;
    }
  })
  .catch(e => {
    statusEl.innerHTML = `<span style="color:#ef5350;">✗ 保存失败</span>`;
  });
}

// 保存花费金额
function saveCostData() {
  const merchantId = currentMerchantId || document.getElementById('merchant-select').value;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;
  const costAmount = parseFloat(document.getElementById('cost-amount').value) || 0;
  
  if (!merchantId) {
    toast('请先选择品牌', 'error');
    return;
  }
  
  const statusEl = document.getElementById('status-cost');
  statusEl.innerHTML = '<span style="color:#ffa726;">⏳ 保存中...</span>';
  
  fetch(`/api/workflow/ads_data/${merchantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_type: 'cost',
      start_date: startDate,
      end_date: endDate,
      cost_amount: costAmount
    })
  })
  .then(r => r.json())
  .then(result => {
    if (result.success) {
      statusEl.innerHTML = `<span style="color:#4caf50;">✓ 花费金额已保存</span>`;
      toast('花费金额保存成功', 'success');
    } else {
      statusEl.innerHTML = `<span style="color:#ef5350;">✗ ${result.error}</span>`;
    }
  })
  .catch(e => {
    statusEl.innerHTML = `<span style="color:#ef5350;">✗ 保存失败</span>`;
  });
}

// 计算ROI
function calculateROI() {
  const merchantId = currentMerchantId || document.getElementById('merchant-select').value;
  const startDate = document.getElementById('start-date').value;
  const endDate = document.getElementById('end-date').value;
  
  if (!merchantId) {
    toast('请先选择品牌', 'error');
    return;
  }
  
  showLoading('计算ROI...');
  
  fetch(`/api/workflow/ads_data/${merchantId}/roi?start_date=${startDate}&end_date=${endDate}`)
  .then(r => r.json())
  .then(result => {
    hideLoading();
    if (result.success) {
      displayRoiResult(result.data);
      switchTab(1);  // 切换到ROI分析Tab
      toast('ROI计算完成', 'success');
    } else {
      toast(result.error || '计算失败', 'error');
    }
  })
  .catch(e => {
    hideLoading();
    toast('计算失败: ' + e.message, 'error');
  });
}

// 显示ROI结果
function displayRoiResult(data) {
  const summary = data.summary || {};
  const roi = summary.roi || 0;
  const roas = summary.roas || 0;
  const googleCost = summary.google_cost || 0;
  const ypCommission = summary.yp_commission || 0;
  
  const roiStatus = roi >= 0 ? 'good' : 'danger';
  const roiIcon = roi >= 0 ? '🟢' : '🔴';
  
  document.getElementById('roi-dashboard').innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card status-${roiStatus}">
        <div class="kpi-label">ROI</div>
        <div class="kpi-value ${roiStatus}">${roiIcon} ${(roi * 100).toFixed(1)}%</div>
        <div class="kpi-target">目标: > 0%</div>
        <div class="kpi-change">${roi >= 0 ? '盈利' : '亏损'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">ROAS</div>
        <div class="kpi-value">${roas.toFixed(2)}x</div>
        <div class="kpi-target">收入/花费</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Google花费</div>
        <div class="kpi-value">$${googleCost.toFixed(2)}</div>
        <div class="kpi-target">广告投入</div>
      </div>
      <div class="kpi-card status-${ypCommission > 0 ? 'good' : ''}">
        <div class="kpi-label">YP佣金</div>
        <div class="kpi-value ${ypCommission > 0 ? 'good' : ''}">$${ypCommission.toFixed(2)}</div>
        <div class="kpi-target">佣金收入</div>
      </div>
    </div>
    
    <div style="margin-top:20px;padding:20px;background:#15181f;border-radius:12px;">
      <h3 style="font-size:14px;margin-bottom:16px;">📊 分析结论</h3>
      <div style="font-size:13px;color:#adb5bd;line-height:1.8;">
        ${generateRoiAnalysis(roi, roas, googleCost, ypCommission, summary)}
      </div>
    </div>
  `;
  
  // 加载关键字分析
  loadKeywordsAnalysis(data.merchant_id || currentMerchantId, data.date_range);
  loadSearchTermsAnalysis(data.merchant_id || currentMerchantId, data.date_range);
}

// 生成ROI分析结论
function generateRoiAnalysis(roi, roas, cost, commission, summary) {
  let analysis = [];
  
  if (roi >= 0.5) {
    analysis.push('✅ <b>盈利状态良好</b>：ROI超过50%，广告投放效果优秀，建议继续投入。');
  } else if (roi >= 0) {
    analysis.push('⚠️ <b>微利状态</b>：ROI为正但较低，建议优化关键词和出价策略。');
  } else if (roi >= -0.3) {
    analysis.push('⚠️ <b>小幅亏损</b>：ROI为负但亏损不大，建议检查高花费低转化关键词。');
  } else {
    analysis.push('🔴 <b>亏损严重</b>：ROI大幅为负，建议暂停投放并重新评估策略。');
  }
  
  if (cost > 0 && commission === 0) {
    analysis.push('⚠️ <b>无佣金数据</b>：已记录花费但无佣金收入，请确认YP报表是否上传。');
  }
  
  if (summary.yp_clicks > 0 && summary.yp_purchases === 0) {
    analysis.push('💡 <b>转化问题</b>：有点击但无购买，检查落地页或产品竞争力。');
  }
  
  return analysis.join('<br>');
}

// 加载关键字分析
function loadKeywordsAnalysis(merchantId, dateRange) {
  if (!merchantId || !dateRange) return;
  
  fetch(`/api/workflow/ads_data/${merchantId}/keywords?start_date=${dateRange.start_date}&end_date=${dateRange.end_date}&limit=20`)
  .then(r => r.json())
  .then(result => {
    if (result.success && result.data && result.data.length > 0) {
      const keywords = result.data;
      let html = `
        <table>
          <thead>
            <tr>
              <th>关键字</th>
              <th>匹配类型</th>
              <th>点击</th>
              <th>花费</th>
              <th>CPC</th>
              <th>CTR</th>
            </tr>
          </thead>
          <tbody>
      `;
      
      keywords.forEach(kw => {
        html += `
          <tr>
            <td><b>${kw.keyword || '-'}</b></td>
            <td>${kw.match_type || '-'}</td>
            <td>${kw.clicks || 0}</td>
            <td>$${(kw.cost || 0).toFixed(2)}</td>
            <td>$${(kw.cpc || 0).toFixed(2)}</td>
            <td>${((kw.ctr || 0) * 100).toFixed(1)}%</td>
          </tr>
        `;
      });
      
      html += '</tbody></table>';
      document.getElementById('keywords-analysis').innerHTML = html;
    }
  })
  .catch(e => console.error('加载关键字分析失败:', e));
}

// 加载搜索字词分析
function loadSearchTermsAnalysis(merchantId, dateRange) {
  if (!merchantId || !dateRange) return;
  
  fetch(`/api/workflow/ads_data/${merchantId}/search_terms?start_date=${dateRange.start_date}&end_date=${dateRange.end_date}&limit=20`)
  .then(r => r.json())
  .then(result => {
    if (result.success && result.data && result.data.length > 0) {
      const terms = result.data;
      let html = `
        <table>
          <thead>
            <tr>
              <th>搜索词</th>
              <th>触发关键字</th>
              <th>点击</th>
              <th>花费</th>
              <th>建议</th>
            </tr>
          </thead>
          <tbody>
      `;
      
      terms.forEach(term => {
        const suggestion = term.clicks > 5 && term.cost > 5 ? 
          '<span style="color:#ffa726;">考虑加否定</span>' : 
          (term.clicks > 0 ? '<span style="color:#66bb6a;">正常</span>' : '-');
        html += `
          <tr>
            <td><b>${term.search_term || '-'}</b></td>
            <td>${term.keyword || '-'}</td>
            <td>${term.clicks || 0}</td>
            <td>$${(term.cost || 0).toFixed(2)}</td>
            <td>${suggestion}</td>
          </tr>
        `;
      });
      
      html += '</tbody></table>';
      document.getElementById('search-terms-analysis').innerHTML = html;
    }
  })
  .catch(e => console.error('加载搜索词分析失败:', e));
}

// 加载ROI仪表盘
function loadRoiDashboard() {
  // 如果有选中的商户，加载其数据
  const merchantId = currentMerchantId || document.getElementById('merchant-select').value;
  if (merchantId) {
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    
    fetch(`/api/workflow/ads_data/${merchantId}/roi?start_date=${startDate}&end_date=${endDate}`)
    .then(r => r.json())
    .then(result => {
      if (result.success && result.data && result.data.summary) {
        displayRoiResult(result.data);
      }
    })
    .catch(e => console.error('加载ROI失败:', e));
  }
}

// 显示/隐藏加载
function showLoading(text) {
  document.getElementById('loading-text').textContent = text || '处理中...';
  document.getElementById('loading-overlay').classList.add('active');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.remove('active');
}

// Toast提示
function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}

// 文件选择处理（保留原有功能）
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  currentFile = file;
  
  const preview = document.getElementById('file-preview');
  preview.innerHTML = `
    <div class="file-preview">
      <span class="file-icon">📄</span>
      <div class="file-info">
        <div class="file-name">${file.name}</div>
        <div class="file-size">${(file.size / 1024).toFixed(1)} KB</div>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="clearFile()">移除</button>
    </div>
  `;
  preview.style.display = 'block';
}

function clearFile() {
  currentFile = null;
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('file-input').value = '';
}

// 拖拽上传
const uploadZone = document.getElementById('upload-zone');
uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('dragover');
});
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    document.getElementById('file-input').files = files;
    handleFileSelect({ target: { files: files } });
  }
});

// 上传文件
function uploadFile() {
  if (!currentFile) {
    toast('请先选择文件', 'error');
    return;
  }
  
  const formData = new FormData();
  formData.append('file', currentFile);
  formData.append('asin', document.getElementById('asin-input').value);
  formData.append('report_type', document.getElementById('report-type').value);
  
  document.getElementById('upload-progress').style.display = 'block';
  document.getElementById('upload-btn').disabled = true;
  
  fetch('/api/optimize/upload', {
    method: 'POST',
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      currentUploadId = data.upload_id;
      toast('上传成功，开始分析...', 'success');
      startAnalysis(currentUploadId);
    } else {
      toast(data.msg || '上传失败', 'error');
      document.getElementById('upload-btn').disabled = false;
    }
  })
  .catch(e => {
    toast(e.message, 'error');
    document.getElementById('upload-btn').disabled = false;
  });
}

// 开始分析
function startAnalysis(uploadId) {
  document.getElementById('progress-text').textContent = '正在分析数据...';
  document.getElementById('progress-fill').style.width = '50%';
  
  fetch('/api/optimize/analyze/' + uploadId, { method: 'POST' })
  .then(r => r.json())
  .then(data => {
    document.getElementById('progress-fill').style.width = '100%';
    if (data.ok) {
      toast('分析完成！找到 ' + (data.suggestion_count || 0) + ' 条建议', 'success');
      setTimeout(() => {
        document.getElementById('upload-progress').style.display = 'none';
        document.getElementById('upload-btn').disabled = false;
        clearFile();
        loadUploadHistory();
        switchTab(1);
      }, 500);
    } else {
      toast(data.msg || '分析失败', 'error');
      document.getElementById('upload-btn').disabled = false;
    }
  })
  .catch(e => {
    toast(e.message, 'error');
    document.getElementById('upload-btn').disabled = false;
  });
}

// 加载上传历史
function loadUploadHistory() {
  fetch('/api/optimize/uploads')
  .then(r => r.json())
  .then(data => {
    const tbody = document.getElementById('upload-history');
    if (!data.uploads || data.uploads.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#666;padding:40px;">暂无上传记录</td></tr>';
      return;
    }
    tbody.innerHTML = data.uploads.map(u => `
      <tr>
        <td>${u.created_at || '-'}</td>
        <td>${u.filename || '-'}</td>
        <td>${u.row_count || '-'}</td>
        <td><span class="badge badge-${u.status === 'analyzed' ? 'green' : u.status === 'pending' ? 'orange' : 'gray'}">${u.status || '-'}</span></td>
        <td>${u.suggestion_count || 0}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="viewSuggestions('${u.id}')">查看建议</button>
        </td>
      </tr>
    `).join('');
  })
  .catch(e => toast(e.message, 'error'));
}

// 加载批次选项
function loadBatchOptions() {
  fetch('/api/optimize/uploads')
  .then(r => r.json())
  .then(data => {
    const select = document.getElementById('batch-filter');
    const currentVal = select.value;
    select.innerHTML = '<option value="">选择上传批次</option>' +
      (data.uploads || []).map(u => `<option value="${u.id}">${u.filename} (${u.created_at})</option>`).join('');
    select.value = currentVal;
  })
  .catch(e => toast(e.message, 'error'));
}

// 查看建议
function viewSuggestions(uploadId) {
  document.getElementById('batch-filter').value = uploadId;
  switchTab(1);
  loadSuggestions();
}

// 加载建议列表
function loadSuggestions() {
  const batchId = document.getElementById('batch-filter').value;
  if (!batchId) {
    document.getElementById('suggestions-list').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">💡</div>
        <div class="empty-state-title">请先选择上传批次</div>
        <div class="empty-state-desc">选择上方下拉菜单中的批次查看优化建议</div>
      </div>
    `;
    return;
  }
  
  const type = document.getElementById('type-filter').value;
  const priority = document.getElementById('priority-filter').value;
  
  showLoading('加载建议中...');
  
  fetch(`/api/optimize/suggestions?upload_id=${batchId}&type=${type}&priority=${priority}`)
  .then(r => r.json())
  .then(data => {
    hideLoading();
    updateSuggestionStats(data.stats || {});
    renderSuggestions(data.suggestions || []);
  })
  .catch(e => {
    hideLoading();
    toast(e.message, 'error');
  });
}

// 更新建议统计
function updateSuggestionStats(stats) {
  document.getElementById('stat-total').textContent = stats.total || 0;
  document.getElementById('stat-high').textContent = stats.high || 0;
  document.getElementById('stat-pending').textContent = stats.pending || 0;
  document.getElementById('stat-adopted').textContent = stats.adopted || 0;
}

// 渲染建议卡片
function renderSuggestions(suggestions) {
  const container = document.getElementById('suggestions-list');
  if (suggestions.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-title">暂无优化建议</div>
        <div class="empty-state-desc">当前批次数据表现良好，无需优化</div>
      </div>
    `;
    return;
  }
  
  container.innerHTML = suggestions.map(s => `
    <div class="suggestion-card priority-${s.priority}">
      <div class="suggestion-header">
        <span class="badge badge-${s.priority === 'high' ? 'red' : s.priority === 'medium' ? 'orange' : 'blue'}">${s.priority.toUpperCase()}</span>
        <span class="suggestion-type ${s.type}">${getSuggestionTypeName(s.type)}</span>
      </div>
      <div class="suggestion-keyword">${s.keyword || s.search_term || '-'}</div>
      <div class="suggestion-reason">${s.reason}</div>
      <div class="suggestion-action">建议: ${s.action}</div>
      <div class="suggestion-data">
        <span>曝光 <strong>${s.impressions || 0}</strong></span>
        <span>点击 <strong>${s.clicks || 0}</strong></span>
        <span>花费 <strong>$${s.cost || 0}</strong></span>
        <span>转化 <strong>${s.conversions || 0}</strong></span>
        <span>转化率 <strong>${s.cvr || 0}%</strong></span>
      </div>
      <div class="suggestion-actions">
        <button class="btn btn-success" onclick="handleSuggestion('${s.id}', 'adopt')" ${s.status !== 'pending' ? 'disabled' : ''}>
          ${s.status === 'adopted' ? '✅ 已采纳' : '采纳'}
        </button>
        <button class="btn btn-secondary" onclick="handleSuggestion('${s.id}', 'ignore')" ${s.status !== 'pending' ? 'disabled' : ''}>
          ${s.status === 'ignored' ? '❌ 已忽略' : '忽略'}
        </button>
      </div>
    </div>
  `).join('');
}

function getSuggestionTypeName(type) {
  const names = {
    negative: '加否定关键词',
    bid: '提升出价',
    match: '扩展匹配',
    adgroup: '新建AdGroup',
    copy: '改文案',
    pause: '暂停词'
  };
  return names[type] || type;
}

// 处理建议
function handleSuggestion(suggestionId, action) {
  showLoading('处理中...');
  fetch('/api/optimize/suggestion_action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suggestion_id: suggestionId, action: action })
  })
  .then(r => r.json())
  .then(data => {
    hideLoading();
    if (data.ok) {
      toast(action === 'adopt' ? '已采纳建议' : '已忽略建议', 'success');
      loadSuggestions();
    } else {
      toast(data.msg || '操作失败', 'error');
    }
  })
  .catch(e => {
    hideLoading();
    toast(e.message, 'error');
  });
}

// 保存KPI目标
function saveKpiTarget() {
  const metric = document.getElementById('kpi-metric').value;
  const target = document.getElementById('kpi-target').value;
  const threshold = document.getElementById('kpi-threshold').value;
  const scope = document.getElementById('kpi-scope').value;
  
  if (!target) {
    toast('请输入目标值', 'error');
    return;
  }
  
  showLoading('保存中...');
  fetch('/api/optimize/kpi_target', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ metric, target, threshold, scope })
  })
  .then(r => r.json())
  .then(data => {
    hideLoading();
    if (data.ok) {
      toast('KPI目标已保存', 'success');
      loadKpiData();
    } else {
      toast(data.msg || '保存失败', 'error');
    }
  })
  .catch(e => {
    hideLoading();
    toast(e.message, 'error');
  });
}

// 加载KPI数据
function loadKpiData() {
  showLoading('加载KPI数据...');
  
  Promise.all([
    fetch('/api/optimize/kpi').then(r => r.json()),
    fetch('/api/optimize/uploads?limit=5').then(r => r.json())
  ])
  .then(([kpiData, uploadData]) => {
    hideLoading();
    renderKpiCards(kpiData.kpis || []);
    renderBatchSummary(uploadData.uploads || []);
  })
  .catch(e => {
    hideLoading();
    toast(e.message, 'error');
  });
}

// 渲染KPI卡片
function renderKpiCards(kpis) {
  if (kpis.length === 0) return;
  
  const container = document.getElementById('kpi-cards');
  container.innerHTML = kpis.map(k => {
    const isGood = k.status === 'good';
    const isWarning = k.status === 'warning';
    const isDanger = k.status === 'danger';
    const statusClass = isGood ? 'good' : isWarning ? 'warning' : 'danger';
    const icon = isGood ? '🟢' : isWarning ? '🟡' : '🔴';
    const cardClass = isGood ? 'status-good' : isWarning ? 'status-warning' : 'status-danger';
    
    return `
      <div class="kpi-card ${cardClass}">
        <div class="kpi-label">${k.metric.toUpperCase()}</div>
        <div class="kpi-value ${statusClass}">${icon} ${k.actual}${k.metric === 'roas' ? 'x' : k.metric === 'ctr' || k.metric === 'cvr' ? '%' : ''}</div>
        <div class="kpi-target">目标: ${k.target}${k.metric === 'roas' ? 'x' : k.metric === 'ctr' || k.metric === 'cvr' ? '%' : ''}</div>
        <div class="kpi-change ${k.change >= 0 ? 'up' : 'down'}">${k.change >= 0 ? '↑' : '↓'} ${Math.abs(k.change)}% ${k.changeDesc || ''}</div>
      </div>
    `;
  }).join('');
}

// 渲染批次摘要
function renderBatchSummary(uploads) {
  const tbody = document.getElementById('batch-summary');
  if (uploads.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#666;padding:40px;">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = uploads.map(u => `
    <tr>
      <td>${u.created_at || '-'}</td>
      <td>$${u.total_cost || 0}</td>
      <td>${u.total_clicks || 0}</td>
      <td>${u.total_conversions || 0}</td>
      <td>${u.roas || 0}x</td>
      <td>${u.ctr || 0}%</td>
      <td>${u.cvr || 0}%</td>
      <td>${u.suggestion_count || 0}</td>
    </tr>
  `).join('');
}

// 页面加载时初始化
window.onload = function() {
  loadUploadHistory();
};
</script>
</body>
</html>
"""
)


@bp.route("/optimize")
def optimize_page():
    return render_template_string(OPTIMIZE_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# 主程序入口
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# T-012: QS 质量评分仪表盘
# ═══════════════════════════════════════════════════════════════════════════

QS_DASHBOARD_HTML = (
    """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>质量评分仪表盘 - YP Affiliate</title>
<style>
"""
    + BASE_CSS
    + """
/* QS仪表盘专用样式 */
.qs-stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px; margin-bottom: 28px;
}
.qs-stat-card {
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
  padding: 24px; text-align: center;
}
.qs-stat-value {
  font-size: 36px; font-weight: 700; margin-bottom: 8px;
}
.qs-stat-value.good { color: #66bb6a; }
.qs-stat-value.warning { color: #ffa726; }
.qs-stat-value.danger { color: #ef5350; }
.qs-stat-label { font-size: 13px; color: #888; }

/* QS徽章 */
.qs-badge-circle {
  display: inline-flex; align-items: center; justify-content: center;
  width: 44px; height: 44px; border-radius: 50%; font-size: 14px; font-weight: 700;
}
.qs-badge-circle.good { background: rgba(46, 125, 50, 0.2); color: #66bb6a; border: 2px solid #2e7d32; }
.qs-badge-circle.warning { background: rgba(255, 167, 38, 0.2); color: #ffa726; border: 2px solid #ffa726; }
.qs-badge-circle.danger { background: rgba(198, 40, 40, 0.2); color: #ef5350; border: 2px solid #c62828; }

/* 商品列表 */
.product-list { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px; overflow: hidden; }
.product-list th { background: #15181f; }
.product-list td { vertical-align: middle; }
.product-name { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.product-row:hover td { background: #1e2129; }

/* 进度条 */
.progress-bar-mini {
  height: 6px; background: #23262f; border-radius: 3px; overflow: hidden; width: 100px;
}
.progress-fill-mini {
  height: 100%; border-radius: 3px; transition: width .3s ease;
}
.progress-fill-mini.good { background: #2e7d32; }
.progress-fill-mini.warning { background: #ffa726; }
.progress-fill-mini.danger { background: #c62828; }

/* 空状态 */
.empty-state { text-align: center; padding: 60px 20px; color: #666; }
.empty-state-icon { font-size: 64px; margin-bottom: 16px; }
</style>
</head>
<body>
"""
    + NAV_HTML.format(
        p0="",
        p1="",
        p2="",
        p3="",
        p4="",
        p5="",
        p6="",
        p7="active",
        p8="",
        p9="",
        p10="",
        p11="",
    )
    + """
<div class="container">
  <h1 style="font-size: 20px; margin-bottom: 24px;">⭐ 质量评分仪表盘</h1>
  
  <!-- 总览卡片 -->
  <div class="qs-stats-grid" id="qs-stats">
    <div class="qs-stat-card">
      <div class="qs-stat-value" id="stat-avg">-</div>
      <div class="qs-stat-label">平均 QS 分数</div>
    </div>
    <div class="qs-stat-card">
      <div class="qs-stat-value good" id="stat-good">-</div>
      <div class="qs-stat-label">QS ≥ 80 的广告</div>
    </div>
    <div class="qs-stat-card">
      <div class="qs-stat-value danger" id="stat-bad">-</div>
      <div class="qs-stat-label">QS < 60 的广告</div>
    </div>
    <div class="qs-stat-card">
      <div class="qs-stat-value" id="stat-total">-</div>
      <div class="qs-stat-label">总广告数</div>
    </div>
  </div>
  
  <!-- 商品列表 -->
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;font-size:15px;">商品 QS 排名（按平均 QS 升序）</h2>
      <button class="btn btn-primary btn-sm" onclick="loadQsData()">🔄 刷新数据</button>
    </div>
    <table class="product-list">
      <thead>
        <tr>
          <th>ASIN</th>
          <th>商品名称</th>
          <th>平均 QS</th>
          <th>广告数量</th>
          <th>QS 分布</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody id="product-tbody">
        <tr><td colspan="6" style="text-align:center;padding:40px;color:#666;">加载中...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}

function getQsClass(score) {
  if (score >= 80) return 'good';
  if (score >= 60) return 'warning';
  return 'danger';
}

function htmlEsc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function loadQsData() {
  try {
    const res = await fetch('/api/qs/dashboard');
    const data = await res.json();
    
    if (!data.ok) {
      toast(data.msg || '加载失败', 'error');
      return;
    }
    
    // 更新统计卡片
    document.getElementById('stat-avg').textContent = data.avg_qs || 0;
    document.getElementById('stat-avg').className = 'qs-stat-value ' + getQsClass(data.avg_qs || 0);
    document.getElementById('stat-good').textContent = data.qs_good_count || 0;
    document.getElementById('stat-bad').textContent = data.qs_bad_count || 0;
    document.getElementById('stat-total').textContent = data.total_ads || 0;
    
    // 更新商品列表（后端返回字段：items / avg_quality_score / qs_good / qs_bad / scored_ads）
    const tbody = document.getElementById('product-tbody');
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="empty-state-icon">📊</div><div>暂无数据</div></td></tr>';
      return;
    }
    
    try {
      tbody.innerHTML = data.items.map(p => {
        const avgQs = p.avg_quality_score || 0;
        const qsClass = getQsClass(avgQs);
        const adCount = p.scored_ads || p.ad_count || 0;
        const goodPct = adCount > 0 ? Math.round((p.qs_good || 0) / adCount * 100) : 0;
        const badPct  = adCount > 0 ? Math.round((p.qs_bad  || 0) / adCount * 100) : 0;
        const avgQsDisplay = avgQs ? Math.round(avgQs) : '-';
        const safeName = htmlEsc(p.product_name);
        const safeAsin = htmlEsc(p.asin);
        
        return `
          <tr class="product-row">
            <td><code>${safeAsin}</code></td>
            <td class="product-name" title="${safeName}">${safeName || '-'}</td>
            <td>
              <span class="qs-badge-circle ${avgQs ? qsClass : 'warning'}">${avgQsDisplay}</span>
            </td>
            <td>${adCount}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;font-size:12px;">
                <span style="color:#66bb6a">${p.qs_good || 0} 优</span>
                <div class="progress-bar-mini">
                  <div class="progress-fill-mini good" style="width:${goodPct}%"></div>
                </div>
                <span style="color:#ef5350">${p.qs_bad || 0} 差</span>
                <div class="progress-bar-mini">
                  <div class="progress-fill-mini danger" style="width:${badPct}%"></div>
                </div>
              </div>
            </td>
            <td>
              <a href="/plans/${safeAsin}" class="btn btn-secondary btn-sm">查看</a>
              <button class="btn btn-primary btn-sm" data-asin="${safeAsin}" onclick="rescoreProduct(this.dataset.asin)">重评</button>
            </td>
          </tr>
        `;
      }).join('');
    } catch(renderErr) {
      console.error('渲染商品列表失败:', renderErr);
      toast('渲染失败: ' + renderErr.message, 'error');
    }
    
  } catch (e) {
    console.error('loadQsData失败:', e);
    toast(e.message, 'error');
  }
}

async function rescoreProduct(asin) {
  try {
    const res = await fetch('/api/ads/score/' + asin, { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      toast('评分完成！平均QS: ' + (data.avg_qs || 0), 'success');
      loadQsData();
    } else {
      toast(data.msg || '评分失败', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

window.onload = loadQsData;
</script>
</body>
</html>
"""
)


@bp.route("/qs_dashboard")
def qs_dashboard_page():
    return render_template_string(QS_DASHBOARD_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# T-013: 竞品文案参考库
# ═══════════════════════════════════════════════════════════════════════════

COMPETITOR_ADS_HTML = (
    """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>竞品文案参考库 - YP Affiliate</title>
<style>
"""
    + BASE_CSS
    + """
/* 竞品文案库专用样式 */
.competitor-layout {
  display: grid; grid-template-columns: 260px 1fr; gap: 20px;
}
.sidebar {
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
  padding: 16px; height: fit-content;
}
.sidebar h3 { font-size: 14px; color: #888; margin-bottom: 12px; text-transform: uppercase; }
.merchant-list { max-height: 400px; overflow-y: auto; }
.merchant-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-radius: 6px; cursor: pointer; transition: background .15s;
}
.merchant-item:hover { background: #23262f; }
.merchant-item.active { background: #1565c033; border-left: 3px solid #1565c0; }
.merchant-checkbox { width: 16px; height: 16px; accent-color: #1565c0; }
.merchant-name { font-size: 13px; color: #e0e0e0; }
.merchant-count { font-size: 11px; color: #888; margin-left: auto; }

/* 搜索栏 */
.search-bar {
  display: flex; gap: 12px; margin-bottom: 20px;
}
.search-input {
  flex: 1; padding: 10px 16px; border: 1px solid #2a2d36;
  border-radius: 8px; background: #15181f; color: #e0e0e0; font-size: 14px;
}
.search-input:focus { outline: none; border-color: #1565c0; }

/* 统计栏 */
.stats-bar-comp {
  display: flex; gap: 24px; padding: 16px 20px;
  background: #1a1d24; border-radius: 8px; margin-bottom: 20px;
}
.stat-comp { text-align: center; }
.stat-comp-value { font-size: 24px; font-weight: 700; color: #fff; }
.stat-comp-label { font-size: 12px; color: #888; margin-top: 4px; }

/* 文案卡片网格 */
.ads-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}
.ad-card {
  background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
  padding: 20px; transition: border-color .15s;
}
.ad-card:hover { border-color: #1565c0; }
.ad-card-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #23262f;
}
.ad-card-source { font-size: 12px; color: #888; }
.ad-card-date { font-size: 11px; color: #666; }
.ad-card-headline {
  font-size: 15px; font-weight: 600; color: #64b5f6; margin-bottom: 10px;
  line-height: 1.4;
}
.ad-card-desc {
  font-size: 13px; color: #adb5bd; line-height: 1.6; margin-bottom: 12px;
}
.ad-card-footer {
  display: flex; gap: 8px;
}
.ad-card-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #23262f; color: #888;
}

/* 复制按钮 */
.copy-btn {
  margin-left: auto; padding: 4px 12px; font-size: 12px;
  background: #23262f; border: 1px solid #2a2d36; color: #adb5bd;
  border-radius: 6px; cursor: pointer; transition: all .15s;
}
.copy-btn:hover { background: #1565c0; color: #fff; border-color: #1565c0; }
.copy-btn.copied { background: #2e7d32; color: #fff; border-color: #2e7d32; }

/* 空状态 */
.empty-state-comp { text-align: center; padding: 60px; color: #666; }
.empty-state-comp-icon { font-size: 64px; margin-bottom: 16px; }
</style>
</head>
<body>
"""
    + NAV_HTML.format(
        p0="",
        p1="",
        p2="",
        p3="",
        p4="",
        p5="",
        p6="",
        p7="",
        p8="active",
        p9="",
        p10="",
        p11="",
    )
    + """
<div class="container">
  <h1 style="font-size: 20px; margin-bottom: 20px;">🔍 竞品文案参考库</h1>
  
  <!-- 统计栏 -->
  <div class="stats-bar-comp" id="stats-bar">
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-total-ads">-</div>
      <div class="stat-comp-label">总文案数</div>
    </div>
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-merchants">-</div>
      <div class="stat-comp-label">商户数</div>
    </div>
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-latest" style="font-size:14px;color:#888;">-</div>
      <div class="stat-comp-label">最新采集时间</div>
    </div>
  </div>
  
  <div class="competitor-layout">
    <!-- 左侧筛选 -->
    <div class="sidebar">
      <h3>🏢 商户筛选</h3>
      <div style="margin-bottom:12px;">
        <button class="btn btn-secondary btn-sm" onclick="selectAllMerchants(true)">全选</button>
        <button class="btn btn-secondary btn-sm" onclick="selectAllMerchants(false)">清空</button>
      </div>
      <div class="merchant-list" id="merchant-list">
        <div style="color:#666;padding:20px;text-align:center;">加载中...</div>
      </div>
    </div>
    
    <!-- 右侧内容 -->
    <div>
      <!-- 搜索栏 -->
      <div class="search-bar">
        <input type="text" class="search-input" id="search-input" placeholder="搜索文案内容..." onkeyup="handleSearch()">
        <button class="btn btn-primary" onclick="loadCompetitorAds()">🔍 搜索</button>
        <button class="btn btn-secondary" onclick="clearSearch()">清空</button>
      </div>
      
      <!-- 文案网格 -->
      <div class="ads-grid" id="ads-grid">
        <div class="empty-state-comp">
          <div class="empty-state-comp-icon">📋</div>
          <div>请选择商户或输入关键词搜索</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let allMerchants = [];
let selectedMerchants = new Set();
let allAds = [];

function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}

function compHtmlEsc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function loadMerchants() {
  try {
    const res = await fetch('/api/competitor/merchants');
    const data = await res.json();
    
    if (!data.ok) {
      console.error('loadMerchants API error:', data.msg);
      document.getElementById('merchant-list').innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">加载失败: ' + compHtmlEsc(data.msg || '未知错误') + '</div>';
      toast(data.msg || '加载商户失败', 'error');
      return;
    }
    
    allMerchants = data.merchants || [];
    renderMerchantList();
    updateStats(data.stats || {});
  } catch (e) {
    console.error('loadMerchants 异常:', e);
    document.getElementById('merchant-list').innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">加载异常: ' + compHtmlEsc(e.message) + '</div>';
    toast(e.message, 'error');
  }
}

function renderMerchantList() {
  const container = document.getElementById('merchant-list');
  if (allMerchants.length === 0) {
    container.innerHTML = '<div style="color:#666;padding:20px;text-align:center;">暂无商户数据</div>';
    return;
  }
  
  try {
    // m.id 统一转字符串，避免数字/字符串 Set 判断失效
    container.innerHTML = allMerchants.map(m => {
      const sid = String(m.id);
      const isActive = selectedMerchants.has(sid);
      const safeName = compHtmlEsc(m.name);
      const safeId = compHtmlEsc(sid);
      return `<div class="merchant-item ${isActive ? 'active' : ''}" data-id="${safeId}" onclick="toggleMerchant(this.dataset.id)">
        <input type="checkbox" class="merchant-checkbox" ${isActive ? 'checked' : ''} onclick="event.stopPropagation()">
        <span class="merchant-name">${safeName}</span>
        <span class="merchant-count">${m.ad_count || 0}</span>
      </div>`;
    }).join('');
  } catch(renderErr) {
    console.error('renderMerchantList 渲染失败:', renderErr);
    container.innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">渲染失败: ' + compHtmlEsc(renderErr.message) + '</div>';
  }
}

function toggleMerchant(id) {
  // id 统一转字符串
  const sid = String(id);
  if (selectedMerchants.has(sid)) {
    selectedMerchants.delete(sid);
  } else {
    selectedMerchants.add(sid);
  }
  renderMerchantList();
  loadCompetitorAds();
}

function selectAllMerchants(select) {
  if (select) {
    allMerchants.forEach(m => selectedMerchants.add(String(m.id)));
  } else {
    selectedMerchants.clear();
  }
  renderMerchantList();
  loadCompetitorAds();
}

function updateStats(stats) {
  document.getElementById('stat-total-ads').textContent = stats.total_ads || 0;
  document.getElementById('stat-merchants').textContent = stats.merchant_count || 0;
  document.getElementById('stat-latest').textContent = stats.latest_scraped || '-';
}

async function loadCompetitorAds() {
  const keyword = document.getElementById('search-input').value.trim();
  const merchantIds = Array.from(selectedMerchants);
  
  try {
    const params = new URLSearchParams();
    if (keyword) params.append('keyword', keyword);
    if (merchantIds.length > 0) params.append('merchants', merchantIds.join(','));
    
    const res = await fetch('/api/competitor/ads?' + params.toString());
    const data = await res.json();
    
    if (!data.ok) {
      toast(data.msg || '加载失败', 'error');
      return;
    }
    
    allAds = data.ads || [];
    renderAdsGrid();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderAdsGrid() {
  const container = document.getElementById('ads-grid');
  if (allAds.length === 0) {
    container.innerHTML = '<div class="empty-state-comp" style="grid-column:1/-1;"><div class="empty-state-comp-icon">🔍</div><div>未找到匹配的文案</div></div>';
    return;
  }
  
  try {
    container.innerHTML = allAds.map(ad => {
      // headlines/descriptions 是 JSON 字符串，需要解析
      let headlines = [];
      let descriptions = [];
      try { headlines = typeof ad.headlines === 'string' ? JSON.parse(ad.headlines) : (ad.headlines || []); } catch(e) {}
      try { descriptions = typeof ad.descriptions === 'string' ? JSON.parse(ad.descriptions) : (ad.descriptions || []); } catch(e) {}
      
      const headlineText = (headlines[0] && headlines[0].text) ? headlines[0].text : (ad.headline || ad.title || '无标题');
      const descText = (descriptions[0] && descriptions[0].text) ? descriptions[0].text : (ad.description || '无描述');
      
      const safeMerchant = compHtmlEsc(ad.merchant_name || '未知商户');
      const safeHeadline = compHtmlEsc(headlineText);
      const safeDesc = compHtmlEsc(descText);
      // 所有标题/描述拼接用于复制，存入 data-* 属性
      const allHeadlines = headlines.map(h => h.text || '').filter(Boolean).join(' | ');
      const allDescs = descriptions.map(d => d.text || '').filter(Boolean).join(' | ');
      const safeCopyH = compHtmlEsc(allHeadlines || headlineText);
      const safeCopyD = compHtmlEsc(allDescs || descText);
      
      return `<div class="ad-card">
        <div class="ad-card-header">
          <span class="ad-card-source">🏢 ${safeMerchant}</span>
          <span class="ad-card-date">${compHtmlEsc(ad.scraped_at || '')}</span>
        </div>
        <div class="ad-card-headline">${safeHeadline}</div>
        <div class="ad-card-desc">${safeDesc}</div>
        <div class="ad-card-footer">
          <span class="ad-card-tag">QS: ${ad.quality_score ? Math.round(ad.quality_score) : '-'}</span>
          <span class="ad-card-tag">${compHtmlEsc(ad.asin || '')}</span>
          <button class="copy-btn" data-headline="${safeCopyH}" data-desc="${safeCopyD}" onclick="copyAd(this)">📋 复制</button>
        </div>
      </div>`;
    }).join('');
  } catch(renderErr) {
    console.error('renderAdsGrid 渲染失败:', renderErr);
    container.innerHTML = '<div class="empty-state-comp" style="grid-column:1/-1;color:#ef5350;">渲染失败: ' + compHtmlEsc(renderErr.message) + '</div>';
  }
}

function escapeHtml(text) {
  return compHtmlEsc(text);
}

async function copyAd(btn) {
  // 通过 data-* 属性安全获取内容（避免引号嵌套）
  const headline = btn.dataset.headline || '';
  const desc = btn.dataset.desc || '';
  // data-* 属性里的内容是 HTML 实体，需要解码回原始字符串
  const tmp = document.createElement('textarea');
  tmp.innerHTML = headline;
  const rawH = tmp.value;
  tmp.innerHTML = desc;
  const rawD = tmp.value;
  const text = rawH + String.fromCharCode(10) + rawD;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = '✅ 已复制';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = '📋 复制';
      btn.classList.remove('copied');
    }, 2000);
  } catch (e) {
    toast('复制失败', 'error');
  }
}

function handleSearch() {
  clearTimeout(window.searchTimeout);
  window.searchTimeout = setTimeout(loadCompetitorAds, 300);
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  loadCompetitorAds();
}

window.onload = function() {
  loadMerchants();
  loadCompetitorAds();
};
</script>
</body>
</html>
"""
)


@bp.route("/competitor_ads")
def competitor_ads_page():
    return render_template_string(COMPETITOR_ADS_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# 补充缺失 API（修复前端 JSON 解析错误：Unexpected token '<'）
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/api/qs/dashboard", methods=["GET"])
def api_qs_dashboard():
    """QS 仪表板数据（转发到 /api/ads/scores，与前端 /qs_dashboard 对接）"""
    try:
        _ensure_quality_score_column()
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT p.asin, p.product_name, p.avg_quality_score,
                   p.ad_count,
                   COUNT(a.id) AS scored_ads,
                   SUM(CASE WHEN a.quality_score >= 80 THEN 1 ELSE 0 END) AS qs_good,
                   SUM(CASE WHEN a.quality_score >= 60 AND a.quality_score < 80 THEN 1 ELSE 0 END) AS qs_ok,
                   SUM(CASE WHEN a.quality_score < 60 THEN 1 ELSE 0 END) AS qs_bad
            FROM ads_plans p
            LEFT JOIN ads_ads a ON a.asin = p.asin
            WHERE p.plan_status = 'completed'
            GROUP BY p.asin, p.product_name, p.avg_quality_score, p.ad_count
            ORDER BY p.avg_quality_score ASC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        total_ads = sum(r["scored_ads"] or 0 for r in rows)
        qs_good_total = sum(r["qs_good"] or 0 for r in rows)
        qs_bad_total = sum(r["qs_bad"] or 0 for r in rows)
        avg_overall = (
            sum((r["avg_quality_score"] or 0) for r in rows) / len(rows) if rows else 0
        )
        return jsonify(
            {
                "ok": True,
                "avg_qs": round(avg_overall, 1),
                "qs_good_count": qs_good_total,
                "qs_bad_count": qs_bad_total,
                "total_ads": total_ads,
                "total_asins": len(rows),
                "items": rows,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


@bp.route("/api/competitor/merchants", methods=["GET"])
def api_competitor_merchants():
    """竞品商户列表（用于 /competitor_ads 侧边栏）"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        # ads_plans.merchant_id 是 YP 平台 ID（字符串），与 yp_merchants.id（自增整数）不一致
        # 直接从 ads_plans 聚合有广告方案的商户信息即可
        cur.execute("""
            SELECT p.merchant_id AS id,
                   p.merchant_name AS name,
                   COUNT(DISTINCT a.id) AS ad_count
            FROM ads_plans p
            JOIN ads_ads a ON a.asin = p.asin
            WHERE p.plan_status = 'completed'
            GROUP BY p.merchant_id, p.merchant_name
            ORDER BY ad_count DESC
        """)
        merchants = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(
            {"ok": True, "merchants": merchants, "stats": {"total": len(merchants)}}
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


@bp.route("/api/competitor/ads", methods=["GET"])
def api_competitor_ads():
    """竞品广告列表（用于 /competitor_ads 主内容区）"""
    try:
        merchant_ids_str = request.args.get("merchants", "")
        search = request.args.get("search", "").strip()
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))
        offset = (page - 1) * size

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # merchant_name 直接取 ads_plans，不 JOIN yp_merchants（两表 id 字段不匹配）
        sql = """
            SELECT a.id, a.asin, a.headlines, a.descriptions, a.quality_score,
                   p.product_name, p.merchant_name AS merchant_name
            FROM ads_ads a
            JOIN ads_plans p ON p.asin = a.asin
            WHERE 1=1
        """
        params = []

        if merchant_ids_str:
            # merchant_id 是字符串类型的 YP 平台 ID
            merchant_ids = [x.strip() for x in merchant_ids_str.split(",") if x.strip()]
            if merchant_ids:
                placeholders = ",".join(["%s"] * len(merchant_ids))
                sql += f" AND p.merchant_id IN ({placeholders})"
                params.extend(merchant_ids)

        if search:
            sql += " AND (JSON_SEARCH(a.headlines, 'one', %s) IS NOT NULL OR JSON_SEARCH(a.descriptions, 'one', %s) IS NOT NULL)"
            params.extend([f"%{search}%", f"%{search}%"])

        count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql}) AS _sub"
        cur.execute(count_sql, params)
        total = cur.fetchone()["cnt"]

        sql += " ORDER BY a.quality_score DESC LIMIT %s OFFSET %s"
        params.extend([size, offset])
        cur.execute(sql, params)
        ads = cur.fetchall()
        # headlines/descriptions 是 JSON 字段，已自动解析为 Python 对象
        cur.close()
        conn.close()

        return jsonify(
            {
                "ok": True,
                "ads": ads,
                "total": total,
                "page": page,
                "size": size,
                "pages": max(1, (total + size - 1) // size),
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# YP 全量商户同步控制
# ═══════════════════════════════════════════════════════════════════════════


def _get_yp_sync_state():
    """读取同步状态"""
    if YP_SYNC_STATE.exists():
        try:
            return json.loads(YP_SYNC_STATE.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def _is_yp_sync_running():
    """检查同步进程是否在运行"""
    global _yp_sync_proc
    if _yp_sync_proc and _yp_sync_proc.poll() is None:
        return True
    # 也检查系统进程
    try:
        import wmi

        for p in wmi.WMI().Win32_Process():
            if (
                "yp_sync_merchants" in (p.CommandLine or "")
                and p.Name == "python3.12.exe"
            ):
                return True
    except:
        pass
    return False


@bp.route("/yp_sync")
def page_yp_sync():
    return YP_SYNC_HTML


@bp.route("/api/yp_sync/status")
def api_yp_sync_status():
    state = _get_yp_sync_state()
    running = _is_yp_sync_running()
    db_count = 0
    db_unique = 0
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM yp_merchants")
        db_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT merchant_id) FROM yp_merchants")
        db_unique = cur.fetchone()[0]
        cur.close()
        conn.close()
    except:
        pass
    # 读日志最后20行
    log_lines = []
    if YP_SYNC_LOG.exists():
        try:
            log_lines = YP_SYNC_LOG.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[-20:]
        except:
            pass
    return jsonify(
        {
            "ok": True,
            "running": running,
            "state": state,
            "db_count": db_count,
            "db_unique": db_unique,
            "log_lines": log_lines,
        }
    )


@bp.route("/api/yp_sync/start", methods=["POST"])
def api_yp_sync_start():
    global _yp_sync_proc
    if _is_yp_sync_running():
        return jsonify({"ok": False, "msg": "同步已在运行中"})
    import subprocess

    _yp_sync_proc = subprocess.Popen(
        [sys.executable, str(YP_SYNC_SCRIPT)],
        cwd=str(BASE_DIR),
        stdout=open(str(YP_SYNC_LOG), "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    return jsonify({"ok": True, "msg": "同步已启动"})


@bp.route("/api/yp_sync/stop", methods=["POST"])
def api_yp_sync_stop():
    # 写入停止标记
    import subprocess

    try:
        # kill 掉正在跑的 python3.12 yp_sync_merchants 进程
        result = subprocess.run(
            'taskkill /F /FI "WINDOWTITLE eq yp_sync*" /T 2>nul',
            shell=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            "wmic process where \"CommandLine like '%%yp_sync_merchants%%' and Name='python3.12.exe'\" call terminate",
            shell=True,
            capture_output=True,
            text=True,
        )
    except:
        pass
    return jsonify({"ok": True, "msg": "已发送停止信号"})


@bp.route("/api/yp_sync/reset", methods=["POST"])
def api_yp_sync_reset():
    if _is_yp_sync_running():
        return jsonify({"ok": False, "msg": "请先停止同步再重置"})
    if YP_SYNC_STATE.exists():
        YP_SYNC_STATE.write_text(
            json.dumps(
                {
                    "page": 0,
                    "total": 0,
                    "total_saved": 0,
                    "started_at": None,
                    "last_run_at": None,
                }
            ),
            encoding="utf-8",
        )
    return jsonify({"ok": True, "msg": "进度已重置"})


@bp.route("/api/yp_sync/collect_mid", methods=["POST"])
def api_yp_sync_collect_mid():
    """按商户ID列表采集商户数据（通过 yp_sync_merchants.py --mid）"""
    import subprocess

    data = request.get_json(silent=True) or {}
    merchant_ids = data.get("merchant_ids", [])
    if not merchant_ids:
        return jsonify({"ok": False, "msg": "请提供 merchant_id"})

    script = str(YP_SYNC_SCRIPT)
    if not os.path.exists(script):
        return jsonify({"ok": False, "msg": f"采集脚本不存在: {script}"})

    log_file = OUTPUT_DIR / "mid_collect_merchant_log.txt"
    try:
        proc = subprocess.Popen(
            [sys.executable, script, "--mid"]
            + [str(m).strip() for m in merchant_ids if str(m).strip()],
            cwd=str(BASE_DIR),
            stdout=open(str(log_file), "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        return jsonify(
            {
                "ok": True,
                "msg": f"已启动商户采集：{', '.join(str(m) for m in merchant_ids)}",
                "pid": proc.pid,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"启动失败: {e}"})


YP_SYNC_HTML = (
    "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'>\n"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
    "<title>YP全量同步 · YP Affiliate 管理台</title>\n"
    + _BASE_STYLE_DARK
    + """
<style>
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px;margin-bottom:24px;}
.stat-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:18px 20px;}
.stat-card .label{font-size:.78rem;color:#888;margin-bottom:6px;text-transform:uppercase;}
.stat-card .value{font-size:1.8rem;font-weight:700;color:#fff;}
.stat-card .value.green{color:#69f0ae;} .stat-card .value.red{color:#f44336;} .stat-card .value.orange{color:#ffb74d;} .stat-card .value.blue{color:#64b5f6;}
.progress-wrap{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:20px 22px;margin-bottom:24px;}
.progress-label{display:flex;justify-content:space-between;font-size:.83rem;color:#888;margin-bottom:8px;}
.progress-bg{background:#2a2d36;border-radius:8px;height:12px;overflow:hidden;}
.progress-fill{height:100%;border-radius:8px;background:linear-gradient(90deg,#1565c0,#42a5f5);transition:width .5s;}
.btn-row{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:24px;}
.btn-dl{padding:12px 28px;border:none;border-radius:9px;font-size:.95rem;font-weight:600;cursor:pointer;}
.btn-dl:disabled{opacity:.4;cursor:not-allowed;}
.btn-dl-start{background:#2e7d32;color:#fff;} .btn-dl-start:hover:not(:disabled){background:#388e3c;}
.btn-dl-stop{background:#c62828;color:#fff;} .btn-dl-stop:hover:not(:disabled){background:#d32f2f;}
.btn-dl-warning{background:#e65100;color:#fff;} .btn-dl-warning:hover:not(:disabled){background:#f57c00;}
.log-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:18px 20px;}
.log-title{font-size:.82rem;color:#888;text-transform:uppercase;margin-bottom:10px;}
.log-box{background:#0f1117;border-radius:8px;padding:14px;font-family:monospace;font-size:.8rem;color:#ccc;line-height:1.6;min-height:80px;max-height:320px;overflow-y:auto;white-space:pre-wrap;}
.note-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:16px 20px;margin-bottom:24px;font-size:.84rem;color:#aaa;line-height:1.7;}
.note-card b{color:#e0e0e0;} .note-card code{background:#23262f;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:.82rem;color:#64b5f6;}
.status-text{font-size:.88rem;margin-left:8px;}
.toast-container{position:fixed;top:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:10px;}
.toast{padding:12px 22px;border-radius:8px;font-size:.88rem;color:#fff;opacity:0;transform:translateX(40px);animation:toastIn .3s forwards;}
.toast-success{background:#2e7d32;}
.toast-error{background:#c62828;}
.toast-info{background:#1565c0;}
@keyframes toastIn{to{opacity:1;transform:translateX(0);}}
</style>
</head>
<body>
"""
    + _SCRAPE_TOPNAV
    + """
<div class="page" style="max-width:900px;">
  <h2 style="font-size:1.5rem;color:#fff;margin-bottom:6px;">🌐 YP 全量商户同步</h2>
  <p style="color:#888;font-size:.88rem;margin-bottom:22px;">从 YP API 分页采集全部商户数据至 MySQL，严格遵守速率限制 (1000条/10分钟)</p>

  <h2 style="font-size:1.3rem;color:#fff;margin-bottom:6px;">🏪 按商户 ID 采集商户数据</h2>
  <p style="color:#888;font-size:.85rem;margin-bottom:18px;">输入 YP 平台的 merchant_id（数字），通过 API 直接采集该商户信息，写入 yp_merchants 表。无需 Chrome。</p>
  <div class="note-card">
    <b>速度极快：</b>直接调用 YP API（advert_id 参数），秒级返回，无需浏览器。<br>
    <b>查找 merchant_id：</b>在「商户管理」页面可查看所有商户及其 ID。<br>
    <b>多次采集安全：</b>使用 INSERT ... ON DUPLICATE KEY UPDATE，重复采集会更新已有记录。
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
    <input type="text" id="midMerchantInput" placeholder="输入 merchant_id，多个用逗号分隔（如 111335,112887）"
      style="flex:1;min-width:280px;padding:10px 16px;background:#0f1117;border:1px solid #2a2d36;border-radius:8px;color:#fff;font-size:.9rem;outline:none;">
    <button class="btn-dl btn-dl-start" id="btnMidMerchantCollect" onclick="collectMerchantByMid()">▶ 开始采集</button>
  </div>
  <div class="log-card">
    <div class="log-title">采集日志</div>
    <div class="log-box" id="midMerchantResultBox" style="min-height:50px;">等待操作...</div>
  </div>
</div>
<div class="page" style="max-width:900px;margin-top:30px;">
  <div class="stat-grid">
    <div class="stat-card"><div class="label">YP 平台商户总数</div><div class="value blue" id="s-total">-</div></div>
    <div class="stat-card"><div class="label">本次已同步</div><div class="value green" id="s-saved">-</div></div>
    <div class="stat-card"><div class="label">数据库记录数</div><div class="value" id="s-db">-</div></div>
    <div class="stat-card"><div class="label">唯一商户数</div><div class="value blue" id="s-unique">-</div></div>
    <div class="stat-card"><div class="label">当前页/总页数</div><div class="value orange" id="s-page">-</div></div>
  </div>

  <div class="progress-wrap">
    <div class="progress-label"><span id="s-percent">同步进度: -</span><span id="s-time">-</span></div>
    <div class="progress-bg"><div class="progress-fill" id="s-bar" style="width:0%"></div></div>
  </div>

  <div class="btn-row">
    <button class="btn-dl btn-dl-start" id="btn-start" onclick="startSync()">▶ 开始同步</button>
    <button class="btn-dl btn-dl-stop" id="btn-stop" onclick="stopSync()" disabled>⏹ 暂停</button>
    <button class="btn-dl btn-dl-warning" id="btn-reset" onclick="resetSync()">🔄 重置进度</button>
    <span class="status-text" id="s-running" style="color:#f44336;">⏹ 已停止</span>
  </div>

  <div class="log-card">
    <div class="log-title">📋 实时日志</div>
    <div class="log-box" id="log-box">等待日志...</div>
  </div>

  <div class="note-card">
    <b>速率限制：</b>每页采集 <code>1000</code> 条，批次间隔 <code>10 分钟</code>（遵守 YP 速率限制）<br>
    <b>断点续传：</b>暂停/停止后再次启动会从上次位置继续<br>
    <b>写入方式：</b>全量 INSERT，保留所有原始记录（不去重）<br>
    <b>自动重置：</b>同步完成后状态自动重置，下次启动为全量检查
  </div>
</div>
<script>
var refreshTimer = null;
var isRunning = false;

function updateUI(data) {
  var s = data.state || {};
  isRunning = data.running;

  document.getElementById('s-total').textContent = (s.total || 0).toLocaleString();
  document.getElementById('s-saved').textContent = (s.total_saved || 0).toLocaleString();
  document.getElementById('s-db').textContent = (data.db_count || 0).toLocaleString();
  document.getElementById('s-unique').textContent = (data.db_unique || 0).toLocaleString();

  var page = s.page || 0;
  var total = s.total || 0;
  var total_pages = Math.ceil(total / 1000);
  document.getElementById('s-page').textContent = page + ' / ' + total_pages;

  var pct = total > 0 ? (page / total_pages * 100).toFixed(1) : 0;
  document.getElementById('s-percent').textContent = '同步进度: ' + pct + '%';
  document.getElementById('s-bar').style.width = pct + '%';

  // 估算剩余时间
  if (isRunning && page > 0) {
    var remaining = (total_pages - page) * 10 / 60;
    document.getElementById('s-time').textContent = '预计剩余: ' + remaining.toFixed(1) + ' 小时';
  } else if (page >= total_pages && total_pages > 0) {
    document.getElementById('s-time').textContent = '✅ 已完成';
  } else {
    document.getElementById('s-time').textContent = '-';
  }

  // 按钮状态
  document.getElementById('btn-start').disabled = isRunning;
  document.getElementById('btn-stop').disabled = !isRunning;
  document.getElementById('btn-reset').disabled = isRunning;

  var statusEl = document.getElementById('s-running');
  if (isRunning) {
    statusEl.innerHTML = '<span class=\"badge badge-running\">同步中...</span>';
    statusEl.style.color = '#4caf50';
  } else {
    statusEl.textContent = '⏹ 已停止';
    statusEl.style.color = '#f44336';
  }

  // 日志
  if (data.log_lines && data.log_lines.length) {
    var box = document.getElementById('log-box');
    box.innerHTML = data.log_lines.map(function(l) {
      return '<div>' + l.replace(/</g,'&lt;') + '</div>';
    }).join('');
    box.scrollTop = box.scrollHeight;
  }
}

function refresh() {
  fetch('/api/yp_sync/status').then(function(r){return r.json()}).then(function(d){
    updateUI(d);
  }).catch(function(){});
}

function startSync() {
  fetch('/api/yp_sync/start', {method:'POST'}).then(function(r){return r.json()}).then(function(d){
    toast(d.msg, d.ok?'success':'error');
    setTimeout(refresh, 1000);
  });
}

function stopSync() {
  if (!confirm('确定要暂停同步吗？进度已保存，稍后可继续。')) return;
  fetch('/api/yp_sync/stop', {method:'POST'}).then(function(r){return r.json()}).then(function(d){
    toast(d.msg, d.ok?'success':'error');
    setTimeout(refresh, 2000);
  });
}

function resetSync() {
  if (!confirm('确定要重置进度吗？下次将从头开始。')) return;
  fetch('/api/yp_sync/reset', {method:'POST'}).then(function(r){return r.json()}).then(function(d){
    toast(d.msg, d.ok?'success':'error');
    setTimeout(refresh, 500);
  });
}

function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.style.opacity='0'; t.style.transform='translateX(40px)'; setTimeout(function(){t.remove();},300); }, 3000);
}

// 启动定时刷新
refresh();
refreshTimer = setInterval(refresh, 5000);

function collectMerchantByMid() {
  var input = document.getElementById('midMerchantInput').value.trim();
  if (!input) { toast('请输入 merchant_id', 'error'); return; }
  var mids = input.split(/[,，\s]+/).filter(function(s) { return s.length > 0; });
  var resultBox = document.getElementById('midMerchantResultBox');
  var btn = document.getElementById('btnMidMerchantCollect');
  btn.disabled = true;
  btn.textContent = '启动中...';
  resultBox.textContent = '正在采集商户数据...';
  fetch('/api/yp_sync/collect_mid', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ merchant_ids: mids })
  }).then(function(r) { return r.json(); }).then(function(d) {
    btn.disabled = false;
    btn.textContent = '\u25b6 开始采集';
    if (d.ok) {
      resultBox.textContent = '[' + new Date().toLocaleTimeString() + '] ' + d.msg + '\\n\\n提示：采集通过 YP API 直接完成，通常几秒内写入数据库。刷新页面可查看最新数据。';
      toast('商户采集已启动', 'success');
      setTimeout(refresh, 3000);
    } else {
      resultBox.textContent = 'ERROR: ' + (d.msg || '未知错误');
      toast(d.msg || '启动失败', 'error');
    }
  }).catch(function(e) {
    btn.disabled = false;
    btn.textContent = '\u25b6 开始采集';
    resultBox.textContent = '请求失败: ' + e.message;
    toast('请求失败', 'error');
  });
}
</script>
<div class="toast-container" id="toast-container"></div>
</body>
</html>
"""
)
