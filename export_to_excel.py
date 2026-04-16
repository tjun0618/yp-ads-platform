# -*- coding: utf-8 -*-
"""
将 download_state.json 中所有采集到的商品数据导出到 D:/workspace/YP_products.xlsx
支持超过 100 万行时自动分 sheet
"""
import json
import sys
import time
from pathlib import Path
import pandas as pd

STATE_FILE = Path("output/download_state.json")
OUTPUT_FILE = Path(r"D:\workspace\YP_products.xlsx")
MAX_ROWS_PER_SHEET = 900_000  # Excel 单 sheet 上限约 104 万，留余量

# 字段中文映射（列名顺序）
COLUMNS = [
    ("merchant_name",  "商户名称"),
    ("merchant_id",    "商户ID"),
    ("asin",           "ASIN"),
    ("product_name",   "商品名称"),
    ("category",       "类别"),
    ("price",          "价格(USD)"),
    ("commission",     "佣金率"),
    ("tracking_link",  "投放链接"),
    ("scraped_at",     "采集时间"),
]

def main():
    print("=== YP 商品数据 → Excel 导出工具 ===")
    print(f"读取: {STATE_FILE}")

    t0 = time.time()
    print("加载 JSON（文件较大，请稍候）...", flush=True)
    data = json.loads(STATE_FILE.read_text("utf-8"))
    products = data.get("products", [])
    completed = len(data.get("completed_mids", []))
    total = len(products)
    print(f"已完成商户: {completed}  |  总商品数: {total:,}")
    print(f"JSON 加载耗时: {time.time()-t0:.1f}s")

    if total == 0:
        print("没有数据，退出。")
        return

    # 构建 DataFrame
    print("构建 DataFrame...", flush=True)
    t1 = time.time()
    col_keys = [c[0] for c in COLUMNS]
    col_names = [c[1] for c in COLUMNS]
    rows = []
    for p in products:
        rows.append([p.get(k, "") for k in col_keys])
    df = pd.DataFrame(rows, columns=col_names)
    print(f"DataFrame 构建耗时: {time.time()-t1:.1f}s  |  形状: {df.shape}")

    # 写入 Excel（分 sheet）
    print(f"写入 Excel: {OUTPUT_FILE} ...", flush=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    t2 = time.time()

    num_sheets = (total + MAX_ROWS_PER_SHEET - 1) // MAX_ROWS_PER_SHEET
    print(f"共 {num_sheets} 个 Sheet，每 Sheet 最多 {MAX_ROWS_PER_SHEET:,} 行")

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for i in range(num_sheets):
            start = i * MAX_ROWS_PER_SHEET
            end = min(start + MAX_ROWS_PER_SHEET, total)
            sheet_name = f"商品数据" if num_sheets == 1 else f"Sheet{i+1}({start+1}-{end})"
            chunk = df.iloc[start:end]
            chunk.to_excel(writer, sheet_name=sheet_name, index=False)

            # 调整列宽
            ws = writer.sheets[sheet_name]
            col_widths = {
                "商户名称": 30, "商户ID": 12, "ASIN": 12, "商品名称": 60,
                "类别": 20, "价格(USD)": 12, "佣金率": 10,
                "投放链接": 80, "采集时间": 20,
            }
            for col_idx, col_name in enumerate(col_names, 1):
                from openpyxl.utils import get_column_letter
                ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(col_name, 15)

            # 冻结首行
            ws.freeze_panes = "A2"

            print(f"  Sheet '{sheet_name}' 写入完成 ({end-start:,} 行)", flush=True)

    elapsed = time.time() - t0
    size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print()
    print(f"✅ 导出完成！")
    print(f"   文件: {OUTPUT_FILE}")
    print(f"   大小: {size_mb:.1f} MB")
    print(f"   总行数: {total:,}")
    print(f"   耗时: {elapsed:.1f}s")

if __name__ == "__main__":
    main()
