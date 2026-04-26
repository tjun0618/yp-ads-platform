"""
YP平台报表采集脚本

采集两张报表：
1. 商户佣金报表（dim=advert_id）- 按商户维度
2. 商品报表（dim=CampaignId）- 按商品维度

使用方法：
    python yp_report_collector.py --type merchant  # 采集商户报表
    python yp_report_collector.py --type product   # 采集商品报表
    python yp_report_collector.py --type all       # 采集所有报表
"""

import argparse
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import pymysql

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4",
}

# YP平台配置
YP_BASE_URL = "https://yeahpromos.com"
YP_LOGIN_URL = f"{YP_BASE_URL}/index/login/login"
YP_MERCHANT_REPORT_URL = f"{YP_BASE_URL}/index/offer/report_performance"
YP_PRODUCT_REPORT_URL = f"{YP_BASE_URL}/index/offer/report_performance"

# 默认 site_id
DEFAULT_SITE_ID = "12002"


def get_db():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def create_tables():
    """创建报表数据表"""
    conn = get_db()
    cur = conn.cursor()

    # 商户佣金报表表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS yp_merchant_report (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            merchant_name VARCHAR(255),
            report_date DATE NOT NULL,
            clicks INT DEFAULT 0,
            detail_views INT DEFAULT 0,
            add_to_carts INT DEFAULT 0,
            purchases INT DEFAULT 0,
            amount DECIMAL(10,2) DEFAULT 0,
            commission DECIMAL(10,2) DEFAULT 0,
            site_id VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_merchant_date (merchant_id, report_date, site_id),
            INDEX idx_report_date (report_date),
            INDEX idx_merchant_id (merchant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 商品报表表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS yp_product_report (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            merchant_name VARCHAR(255),
            product_id VARCHAR(20),
            asin VARCHAR(20) NOT NULL,
            report_date DATE NOT NULL,
            clicks INT DEFAULT 0,
            detail_views INT DEFAULT 0,
            add_to_carts INT DEFAULT 0,
            purchases INT DEFAULT 0,
            amount DECIMAL(10,2) DEFAULT 0,
            commission DECIMAL(10,2) DEFAULT 0,
            site_id VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_asin_date (asin, report_date, site_id),
            INDEX idx_report_date (report_date),
            INDEX idx_merchant_id (merchant_id),
            INDEX idx_product_id (product_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[OK] 数据表创建完成")


def parse_amount(amount_str):
    """解析金额字符串，如 '$159.96' -> 159.96"""
    if not amount_str:
        return 0.0
    match = re.search(r"[\d,]+\.?\d*", amount_str.replace(",", ""))
    return float(match.group()) if match else 0.0


class YPReportCollector:
    """YP平台报表采集器"""

    def __init__(self, headless=False, persistent=True):
        self.headless = headless
        self.persistent = persistent
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    def start(self):
        """启动浏览器"""
        self.playwright = sync_playwright().start()

        if self.persistent:
            # 使用持久化配置文件保存登录状态
            user_data_dir = "C:/Users/wuhj/.playwright-yp-profile"
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir, headless=self.headless
            )
        else:
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context()

        self.page = self.context.new_page()
        print("[OK] 浏览器启动完成")

    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("[OK] 浏览器已关闭")

    def login(self, username="Tong jun", password="@Tj840618"):
        """登录YP平台"""
        print(f"[INFO] 正在检查登录状态...")
        self.page.goto(YP_BASE_URL + "/index/amounts/index")
        self.page.wait_for_load_state("networkidle")
        
        # 检查是否已登录
        if "login" not in self.page.url:
            print("[OK] 已登录")
            return True
        
        # 跳转到登录页
        print("[INFO] 需要登录，正在跳转到登录页...")
        self.page.goto(YP_LOGIN_URL)
        self.page.wait_for_load_state("networkidle")
            
        # 填写用户名密码（使用正确的选择器）
        try:
            # 用户名输入框
            uname_input = self.page.query_selector('input[placeholder*="User"], input[name="uname"], #uname')
            if uname_input:
                uname_input.fill(username)
            
            # 密码输入框
            pwd_input = self.page.query_selector('input[type="password"], input[name="pwd"], #pwd')
            if pwd_input:
                pwd_input.fill(password)
        except Exception as e:
            print(f"[WARN] 自动填充失败: {e}")
        
        # 检查是否有验证码
        captcha_input = self.page.query_selector('input[placeholder*="Verify"], input[name="captcha"]')
        if captcha_input:
            # 需要手动输入验证码
            print("[WARN] 需要手动输入验证码")
            print("[INFO] 请在浏览器中完成登录，然后按回车继续...")
            input()
            
            # 等待登录成功
            self.page.wait_for_url("**/amounts/index**", timeout=60000)
            print("[OK] 登录成功")
            return True
        else:
            # 尝试点击登录按钮
            login_btn = self.page.query_selector('button:has-text("Go"), button[type="submit"]')
            if login_btn:
                login_btn.click()
                self.page.wait_for_load_state("networkidle")
                
                # 检查是否登录成功
                if "login" not in self.page.url:
                    print("[OK] 登录成功")
                    return True
                    
        print("[WARN] 自动登录失败，请手动登录后按回车继续...")
        input()
        return True

        # 填写用户名密码（使用正确的选择器）
        try:
            # 用户名输入框
            uname_input = self.page.query_selector(
                'input[placeholder*="User"], input[name="uname"], #uname'
            )
            if uname_input:
                uname_input.fill(username)

            # 密码输入框
            pwd_input = self.page.query_selector(
                'input[type="password"], input[name="pwd"], #pwd'
            )
            if pwd_input:
                pwd_input.fill(password)
        except Exception as e:
            print(f"[WARN] 自动填充失败: {e}")

        # 检查是否有验证码
        captcha_input = self.page.query_selector(
            'input[placeholder*="Verify"], input[name="captcha"]'
        )
        if captcha_input:
            # 需要手动输入验证码
            print("[WARN] 需要手动输入验证码")
            print("[INFO] 请在浏览器中完成登录，然后按回车继续...")
            input()

            # 等待登录成功
            self.page.wait_for_url("**/amounts/index**", timeout=60000)
            print("[OK] 登录成功")
            return True
        else:
            # 尝试点击登录按钮
            login_btn = self.page.query_selector(
                'button:has-text("Go"), button[type="submit"]'
            )
            if login_btn:
                login_btn.click()
                self.page.wait_for_load_state("networkidle")

                # 检查是否登录成功
                if "login" not in self.page.url:
                    print("[OK] 登录成功")
                    return True

        print("[WARN] 自动登录失败，请手动登录后按回车继续...")
        input()
        return True

    def collect_merchant_report(self, start_date, end_date, site_id=DEFAULT_SITE_ID):
        """采集商户佣金报表"""
        print(f"[INFO] 采集商户报表: {start_date} ~ {end_date}")

        url = f"{YP_MERCHANT_REPORT_URL}?start_date={start_date}&end_date={end_date}&site_id={site_id}&dim=advert_id"
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

        # 提取表格数据
        data = self.page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return [];
                
                const rows = table.querySelectorAll('tr');
                const result = [];
                
                rows.forEach((row, i) => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 8) {
                        result.push({
                            merchant_id: cells[0]?.textContent?.trim() || '',
                            merchant_name: cells[1]?.textContent?.trim() || '',
                            clicks: parseInt(cells[2]?.textContent?.trim()) || 0,
                            detail_views: parseInt(cells[3]?.textContent?.trim()) || 0,
                            add_to_carts: parseInt(cells[4]?.textContent?.trim()) || 0,
                            purchases: parseInt(cells[5]?.textContent?.trim()) || 0,
                            amount: cells[6]?.textContent?.trim() || '$0.00',
                            commission: cells[7]?.textContent?.trim() || '$0.00'
                        });
                    }
                });
                
                return result;
            }
        """)

        print(f"[OK] 采集到 {len(data)} 条商户数据")
        return data

    def collect_product_report(self, start_date, end_date, site_id=DEFAULT_SITE_ID):
        """采集商品报表"""
        print(f"[INFO] 采集商品报表: {start_date} ~ {end_date}")

        url = f"{YP_PRODUCT_REPORT_URL}?start_date={start_date}&end_date={end_date}&site_id={site_id}&dim=CampaignId"
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

        # 提取表格数据
        data = self.page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return [];
                
                const rows = table.querySelectorAll('tr');
                const result = [];
                
                rows.forEach((row, i) => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 10) {
                        result.push({
                            merchant_id: cells[0]?.textContent?.trim() || '',
                            merchant_name: cells[1]?.textContent?.trim() || '',
                            product_id: cells[2]?.textContent?.trim() || '',
                            asin: cells[3]?.textContent?.trim() || '',
                            clicks: parseInt(cells[4]?.textContent?.trim()) || 0,
                            detail_views: parseInt(cells[5]?.textContent?.trim()) || 0,
                            add_to_carts: parseInt(cells[6]?.textContent?.trim()) || 0,
                            purchases: parseInt(cells[7]?.textContent?.trim()) || 0,
                            amount: cells[8]?.textContent?.trim() || '$0.00',
                            commission: cells[9]?.textContent?.trim() || '$0.00'
                        });
                    }
                });
                
                return result;
            }
        """)

        print(f"[OK] 采集到 {len(data)} 条商品数据")
        return data

    def save_merchant_report(self, data, report_date, site_id):
        """保存商户报表数据"""
        if not data:
            return 0

        conn = get_db()
        cur = conn.cursor()

        saved = 0
        for row in data:
            if not row["merchant_id"]:
                continue

            try:
                cur.execute(
                    """
                    INSERT INTO yp_merchant_report 
                    (merchant_id, merchant_name, report_date, clicks, detail_views, 
                     add_to_carts, purchases, amount, commission, site_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        merchant_name = VALUES(merchant_name),
                        clicks = VALUES(clicks),
                        detail_views = VALUES(detail_views),
                        add_to_carts = VALUES(add_to_carts),
                        purchases = VALUES(purchases),
                        amount = VALUES(amount),
                        commission = VALUES(commission)
                """,
                    (
                        row["merchant_id"],
                        row["merchant_name"],
                        report_date,
                        row["clicks"],
                        row["detail_views"],
                        row["add_to_carts"],
                        row["purchases"],
                        parse_amount(row["amount"]),
                        parse_amount(row["commission"]),
                        site_id,
                    ),
                )
                saved += 1
            except Exception as e:
                print(f"[ERROR] 保存商户 {row['merchant_id']} 失败: {e}")

        conn.commit()
        cur.close()
        conn.close()

        print(f"[OK] 保存 {saved} 条商户报表数据")
        return saved

    def save_product_report(self, data, report_date, site_id):
        """保存商品报表数据"""
        if not data:
            return 0

        conn = get_db()
        cur = conn.cursor()

        saved = 0
        for row in data:
            if not row["asin"]:
                continue

            try:
                cur.execute(
                    """
                    INSERT INTO yp_product_report 
                    (merchant_id, merchant_name, product_id, asin, report_date, 
                     clicks, detail_views, add_to_carts, purchases, amount, commission, site_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        merchant_name = VALUES(merchant_name),
                        product_id = VALUES(product_id),
                        clicks = VALUES(clicks),
                        detail_views = VALUES(detail_views),
                        add_to_carts = VALUES(add_to_carts),
                        purchases = VALUES(purchases),
                        amount = VALUES(amount),
                        commission = VALUES(commission)
                """,
                    (
                        row["merchant_id"],
                        row["merchant_name"],
                        row["product_id"],
                        row["asin"],
                        report_date,
                        row["clicks"],
                        row["detail_views"],
                        row["add_to_carts"],
                        row["purchases"],
                        parse_amount(row["amount"]),
                        parse_amount(row["commission"]),
                        site_id,
                    ),
                )
                saved += 1
            except Exception as e:
                print(f"[ERROR] 保存商品 {row['asin']} 失败: {e}")

        conn.commit()
        cur.close()
        conn.close()

        print(f"[OK] 保存 {saved} 条商品报表数据")
        return saved


def main():
    parser = argparse.ArgumentParser(description="YP平台报表采集")
    parser.add_argument(
        "--type",
        choices=["merchant", "product", "all"],
        default="all",
        help="报表类型: merchant(商户), product(商品), all(全部)",
    )
    parser.add_argument("--start-date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--site-id", default=DEFAULT_SITE_ID, help="站点ID")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--create-tables", action="store_true", help="创建数据表")

    args = parser.parse_args()

    # 默认日期范围：本月
    if not args.start_date:
        args.start_date = datetime.now().strftime("%Y-%m-01")
    if not args.end_date:
        args.end_date = datetime.now().strftime("%Y-%m-%d")

    # 报表日期使用结束日期
    report_date = args.end_date

    # 创建数据表
    if args.create_tables:
        create_tables()
        return

    # 采集报表
    collector = YPReportCollector(headless=args.headless)

    try:
        collector.start()
        collector.login()

        if args.type in ["merchant", "all"]:
            data = collector.collect_merchant_report(
                args.start_date, args.end_date, args.site_id
            )
            collector.save_merchant_report(data, report_date, args.site_id)

        if args.type in ["product", "all"]:
            data = collector.collect_product_report(
                args.start_date, args.end_date, args.site_id
            )
            collector.save_product_report(data, report_date, args.site_id)

    finally:
        collector.close()

    print("\n[DONE] 采集完成")


if __name__ == "__main__":
    main()
