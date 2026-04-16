"""
YP to Feishu - 主程序
从 YP 平台获取商家数据，爬取亚马逊商品，同步到飞书文档
"""

import asyncio
import yaml
import sys
import os
from pathlib import Path
from typing import List, Dict
from loguru import logger
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.yp_api.merchant_collector import YPMerchantCollector, Merchant
from src.yp_api.link_parser import YPLinkParser
from src.amazon.crawler import AmazonCrawler, Product, run_crawler
from src.data.processor import DataProcessor
from src.feishu.client import FeishuClient, FeishuConfig


class YPToFeishuApp:
    """主应用程序"""

    def __init__(self, config_path: str = "config/config.yaml",
                 feishu_config_path: str = "config/feishu_config.yaml"):
        """
        初始化应用

        Args:
            config_path: 主配置文件路径
            feishu_config_path: 飞书配置文件路径
        """
        self.config = self._load_config(config_path)
        self.feishu_config = self._load_feishu_config(feishu_config_path)

        # 初始化组件
        self.yp_collector = YPMerchantCollector(
            api_base=self.config["yp"]["api_base"],
            api_endpoint=self.config["yp"]["merchant_api"],
            rate_limit=self.config["yp"]["rate_limit"],
            timeout=self.config["yp"]["timeout"],
            retry_times=self.config["yp"]["retry_times"]
        )

        self.link_parser = YPLinkParser()

        self.crawler = None  # 延迟初始化

        self.data_processor = DataProcessor()

        self.feishu_client = FeishuClient(self.feishu_config)

        # 工作目录
        self.output_dir = project_root / "output"
        self.output_dir.mkdir(exist_ok=True)

    def _load_config(self, config_path: str) -> Dict:
        """加载主配置文件"""
        config_file = project_root / config_path
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_feishu_config(self, config_path: str) -> FeishuConfig:
        """加载飞书配置"""
        config_file = project_root / config_path
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        feishu_config = config.get("feishu", {})

        return FeishuConfig(
            app_id=feishu_config.get("app_id", ""),
            app_secret=feishu_config.get("app_secret", "")
        )

    def _setup_logging(self):
        """设置日志"""
        log_file = project_root / self.config["logging"]["file"]
        log_file.parent.mkdir(exist_ok=True)

        logger.add(
            log_file,
            rotation=self.config["logging"]["rotation"],
            retention=self.config["logging"]["retention"],
            level=self.config["logging"]["level"]
        )

        logger.add(sys.stderr, level="INFO")

    async def collect_merchants(self) -> List[Merchant]:
        """
        阶段 1：从 YP 采集商家数据

        Returns:
            商家列表
        """
        logger.info("=" * 60)
        logger.info("Phase 1: Collecting merchants from YP platform...")
        logger.info("=" * 60)

        try:
            merchants = self.yp_collector.get_all_merchants()

            # 保存原始数据
            output_file = self.output_dir / f"merchants_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            merchant_dicts = [m.to_dict() for m in merchants]
            self.data_processor.export_to_json(merchant_dicts, output_file)

            logger.info(f"✅ Phase 1 completed: {len(merchants)} merchants collected")
            logger.info(f"   Raw data saved to: {output_file}")

            return merchants

        except Exception as e:
            logger.error(f"❌ Phase 1 failed: {e}")
            raise

    def parse_tracking_links(self, merchants: List[Merchant]) -> List[Dict]:
        """
        阶段 2：解析追踪链接

        Args:
            merchants: 商家列表

        Returns:
            解析后的链接列表
        """
        logger.info("=" * 60)
        logger.info("Phase 2: Parsing tracking links...")
        logger.info("=" * 60)

        try:
            # 提取所有追踪链接
            tracking_links = [m.tracking_link for m in merchants]

            # 批量解析
            parsed_results = self.link_parser.parse_multiple_links(tracking_links)

            # 合并商家信息和链接信息
            for merchant, result in zip(merchants, parsed_results):
                result["merchant_id"] = merchant.merchant_id
                result["merchant_name"] = merchant.merchant_name
                result["commission_rate"] = merchant.commission_rate

            # 过滤有效链接
            valid_links = [r for r in parsed_results if r.get("amazon_url")]

            # 保存解析结果
            output_file = self.output_dir / f"links_parsed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.data_processor.export_to_json(valid_links, output_file)

            logger.info(f"✅ Phase 2 completed: {len(valid_links)} valid links")
            logger.info(f"   Parsed data saved to: {output_file}")

            return valid_links

        except Exception as e:
            logger.error(f"❌ Phase 2 failed: {e}")
            raise

    async def scrape_products(self, parsed_links: List[Dict]) -> List[Product]:
        """
        阶段 3：爬取亚马逊商品数据

        Args:
            parsed_links: 解析后的链接列表

        Returns:
            商品列表
        """
        logger.info("=" * 60)
        logger.info("Phase 3: Scraping Amazon products...")
        logger.info("=" * 60)

        try:
            # 初始化爬虫
            self.crawler = AmazonCrawler(
                headless=self.config["amazon"]["headless"],
                timeout=self.config["amazon"]["timeout"],
                request_delay=self.config["amazon"]["request_delay"],
                max_concurrent=self.config["amazon"]["max_concurrent"]
            )

            await self.crawler.start()

            try:
                # 提取亚马逊 URL
                amazon_urls = [link["amazon_url"] for link in parsed_links if link.get("amazon_url")]

                # 批量爬取
                products = await self.crawler.scrape_multiple(amazon_urls)

                # 保存爬取结果
                output_file = self.output_dir / f"products_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                product_dicts = []
                for product, link in zip(products, parsed_links):
                    product_dict = product.to_dict()
                    product_dict["merchant_id"] = link.get("merchant_id")
                    product_dicts.append(product_dict)

                self.data_processor.export_to_json(product_dicts, output_file)

                logger.info(f"✅ Phase 3 completed: {len(products)} products scraped")
                logger.info(f"   Product data saved to: {output_file}")

                return products

            finally:
                await self.crawler.stop()

        except Exception as e:
            logger.error(f"❌ Phase 3 failed: {e}")
            raise

    def process_and_sync_to_feishu(self,
                                   merchants: List[Merchant],
                                   parsed_links: List[Dict],
                                   products: List[Product]) -> bool:
        """
        阶段 4：处理数据并同步到飞书

        Args:
            merchants: 商家列表
            parsed_links: 解析后的链接列表
            products: 商品列表

        Returns:
            是否成功
        """
        logger.info("=" * 60)
        logger.info("Phase 4: Processing data and syncing to Feishu...")
        logger.info("=" * 60)

        try:
            # 处理商家数据
            merchant_dicts = [m.to_dict() for m in merchants]
            processed_merchants = self.data_processor.process_merchant_data(merchant_dicts)

            # 处理商品数据（添加商家 ID）
            product_dicts = []
            for product, link in zip(products, parsed_links):
                product_dict = product.to_dict()
                product_dict["merchant_id"] = link.get("merchant_id")
                product_dicts.append(product_dict)

            # 生成数据集
            dataset = self.data_processor.generate_dataset(processed_merchants, product_dicts)

            # 去重
            dataset = self.data_processor.deduplicate_products(dataset)

            # 排序（按评分降序）
            dataset = self.data_processor.sort_products(dataset, sort_by="rating", descending=True)

            # 保存处理后的数据
            output_file = self.output_dir / f"dataset_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.data_processor.export_to_json(dataset, output_file)

            logger.info(f"📊 Dataset statistics:")
            stats = self.data_processor.get_statistics(dataset)
            for key, value in stats.items():
                logger.info(f"   {key}: {value}")

            # 同步到飞书
            logger.info("📤 Syncing to Feishu...")

            # 创建飞书表格
            spreadsheet_title = self.feishu_config.get("document", {}).get(
                "title", "YP平台商家商品数据"
            )

            spreadsheet_token = self.feishu_client.create_spreadsheet(
                title=spreadsheet_title,
                folder_token=self.feishu_config.get("document", {}).get("folder_token")
            )

            if not spreadsheet_token:
                logger.error("❌ Failed to create Feishu spreadsheet")
                return False

            # 添加工作表
            sheet_id = self.feishu_client.add_sheet(
                spreadsheet_token=spreadsheet_token,
                title="商品数据"
            )

            if not sheet_id:
                logger.error("❌ Failed to add sheet")
                return False

            # 写入数据
            success = self.feishu_client.write_product_data(
                spreadsheet_token=spreadsheet_token,
                sheet_id=sheet_id,
                products=dataset
            )

            if success:
                logger.info(f"✅ Phase 4 completed: {len(dataset)} products synced to Feishu")
                logger.info(f"   Spreadsheet URL: https://example.com (需要替换为实际URL)")
                return True
            else:
                logger.error("❌ Failed to write data to Feishu")
                return False

        except Exception as e:
            logger.error(f"❌ Phase 4 failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def run(self):
        """运行完整流程"""
        logger.info("🚀 Starting YP to Feishu data pipeline...")
        logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # 阶段 1：采集商家数据
            merchants = self.collect_merchants()

            # 阶段 2：解析链接
            parsed_links = self.parse_tracking_links(merchants)

            if not parsed_links:
                logger.error("❌ No valid tracking links found")
                return

            # 阶段 3：爬取商品数据
            products = await self.scrape_products(parsed_links)

            if not products:
                logger.error("❌ No products scraped")
                return

            # 阶段 4：处理数据并同步到飞书
            success = self.process_and_sync_to_feishu(merchants, parsed_links, products)

            if success:
                logger.info("=" * 60)
                logger.info("✅ All phases completed successfully!")
                logger.info("=" * 60)
                logger.info(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                logger.error("❌ Pipeline failed at phase 4")

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        finally:
            # 清理资源
            self.yp_collector.close()
            self.feishu_client.close()


async def main():
    """主函数"""
    # 初始化应用
    app = YPToFeishuApp()

    # 设置日志
    app._setup_logging()

    # 运行流程
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
