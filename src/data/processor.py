"""
数据处理器
整合 YP 商家数据和亚马逊商品数据
"""

import json
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime
import hashlib


class DataProcessor:
    """数据处理器"""

    def __init__(self):
        self.merchant_cache = {}
        self.product_cache = set()

    def process_merchant_data(self, merchants: List[Dict]) -> List[Dict]:
        """
        处理商家数据

        Args:
            merchants: 原始商家数据列表

        Returns:
            处理后的商家数据列表
        """
        logger.info(f"Processing {len(merchants)} merchants...")

        processed = []

        for merchant in merchants:
            try:
                # 清理和标准化数据
                cleaned = {
                    "merchant_id": str(merchant.get("merchant_id", "")),
                    "merchant_name": merchant.get("merchant_name", "").strip(),
                    "commission_rate": merchant.get("commission_rate", "").strip(),
                    "tracking_link": merchant.get("tracking_link", "").strip(),
                    "description": merchant.get("description", "").strip(),
                    "category": merchant.get("category", "").strip()
                }

                # 验证必要字段
                if not cleaned["merchant_name"] or not cleaned["tracking_link"]:
                    logger.warning(f"Skipping invalid merchant: {merchant}")
                    continue

                # 缓存商家数据
                self.merchant_cache[cleaned["merchant_id"]] = cleaned

                processed.append(cleaned)

            except Exception as e:
                logger.error(f"Error processing merchant: {e}")
                continue

        logger.info(f"Processed {len(processed)} valid merchants")
        return processed

    def merge_product_data(self,
                          merchant: Dict,
                          product: Dict) -> Dict:
        """
        合并商家和商品数据

        Args:
            merchant: 商家数据
            product: 商品数据

        Returns:
            合并后的数据
        """
        merged = {
            # 商家信息
            "merchant_id": merchant.get("merchant_id", ""),
            "merchant_name": merchant.get("merchant_name", ""),
            "commission_rate": merchant.get("commission_rate", ""),

            # 商品信息
            "asin": product.get("asin", ""),
            "product_name": product.get("product_name", ""),
            "price": product.get("price"),
            "currency": product.get("currency", "USD"),
            "rating": product.get("rating"),
            "review_count": product.get("review_count"),
            "description": product.get("description", ""),
            "product_url": product.get("product_url", ""),
            "product_image": product.get("product_image", ""),
            "category": product.get("category", ""),
            "brand": product.get("brand", ""),
            "in_stock": product.get("in_stock", True),

            # 追踪链接
            "tracking_link": merchant.get("tracking_link", ""),

            # 元数据
            "collected_at": datetime.now().isoformat(),
            "data_hash": self._generate_hash(product)
        }

        return merged

    def generate_dataset(self,
                        merchants: List[Dict],
                        products: List[Dict]) -> List[Dict]:
        """
        生成完整数据集

        Args:
            merchants: 商家数据列表
            products: 商品数据列表（每个商品应包含 merchant_id）

        Returns:
            完整数据集
        """
        logger.info("Generating dataset...")

        dataset = []
        merchant_map = {m["merchant_id"]: m for m in merchants}

        for product in products:
            try:
                merchant_id = product.get("merchant_id")

                if not merchant_id:
                    logger.warning(f"Product missing merchant_id: {product.get('asin')}")
                    continue

                merchant = merchant_map.get(merchant_id)

                if not merchant:
                    logger.warning(f"Merchant not found: {merchant_id}")
                    continue

                # 合并数据
                merged = self.merge_product_data(merchant, product)
                dataset.append(merged)

            except Exception as e:
                logger.error(f"Error merging data: {e}")
                continue

        logger.info(f"Generated dataset with {len(dataset)} records")
        return dataset

    def deduplicate_products(self, products: List[Dict]) -> List[Dict]:
        """
        去重商品数据

        Args:
            products: 商品数据列表

        Returns:
            去重后的商品数据列表
        """
        logger.info(f"Deduplicating {len(products)} products...")

        seen_hashes = set()
        deduplicated = []

        for product in products:
            try:
                product_hash = self._generate_hash(product)

                if product_hash not in seen_hashes:
                    seen_hashes.add(product_hash)
                    deduplicated.append(product)
                else:
                    logger.debug(f"Duplicate product found: {product.get('asin')}")

            except Exception as e:
                logger.error(f"Error deduplicating: {e}")
                continue

        logger.info(f"Removed {len(products) - len(deduplicated)} duplicates")
        return deduplicated

    def filter_products(self,
                        products: List[Dict],
                        min_price: Optional[float] = None,
                        max_price: Optional[float] = None,
                        min_rating: Optional[float] = None,
                        in_stock_only: bool = True) -> List[Dict]:
        """
        过滤商品数据

        Args:
            products: 商品数据列表
            min_price: 最低价格
            max_price: 最高价格
            min_rating: 最低评分
            in_stock_only: 仅保留有库存商品

        Returns:
            过滤后的商品数据列表
        """
        logger.info(f"Filtering {len(products)} products...")

        filtered = []

        for product in products:
            try:
                # 检查价格范围
                price = product.get("price")
                if price is not None:
                    if min_price and price < min_price:
                        continue
                    if max_price and price > max_price:
                        continue

                # 检查评分
                rating = product.get("rating")
                if min_rating and rating is not None:
                    if rating < min_rating:
                        continue

                # 检查库存
                if in_stock_only:
                    if not product.get("in_stock", True):
                        continue

                filtered.append(product)

            except Exception as e:
                logger.error(f"Error filtering: {e}")
                continue

        logger.info(f"Filtered to {len(filtered)} products")
        return filtered

    def sort_products(self,
                     products: List[Dict],
                     sort_by: str = "rating",
                     descending: bool = True) -> List[Dict]:
        """
        排序商品数据

        Args:
            products: 商品数据列表
            sort_by: 排序字段 (rating, price, review_count)
            descending: 是否降序

        Returns:
            排序后的商品数据列表
        """
        logger.info(f"Sorting {len(products)} products by {sort_by}...")

        try:
            reverse = descending

            if sort_by == "rating":
                sorted_products = sorted(
                    products,
                    key=lambda x: x.get("rating", 0) or 0,
                    reverse=reverse
                )
            elif sort_by == "price":
                sorted_products = sorted(
                    products,
                    key=lambda x: x.get("price", 0) or 0,
                    reverse=reverse
                )
            elif sort_by == "review_count":
                sorted_products = sorted(
                    products,
                    key=lambda x: x.get("review_count", 0) or 0,
                    reverse=reverse
                )
            elif sort_by == "commission":
                # 需要解析佣金率
                sorted_products = sorted(
                    products,
                    key=lambda x: self._parse_commission(x.get("commission_rate", "0%")),
                    reverse=reverse
                )
            else:
                logger.warning(f"Unknown sort field: {sort_by}")
                sorted_products = products

            return sorted_products

        except Exception as e:
            logger.error(f"Error sorting: {e}")
            return products

    def _generate_hash(self, data: Dict) -> str:
        """
        生成数据哈希（用于去重）

        Args:
            data: 数据字典

        Returns:
            哈希值
        """
        # 使用关键字段生成哈希
        key_fields = [
            data.get("asin", ""),
            data.get("product_name", ""),
            data.get("merchant_id", "")
        ]

        hash_str = "|".join(key_fields)
        return hashlib.md5(hash_str.encode()).hexdigest()

    def _parse_commission(self, commission_str: str) -> float:
        """
        解析佣金率字符串

        Args:
            commission_str: 佣金率字符串（如 "8.5%"）

        Returns:
            佣金率数值
        """
        try:
            # 移除百分号
            commission_str = commission_str.replace("%", "").strip()

            # 转换为浮点数
            return float(commission_str)

        except:
            return 0.0

    def export_to_json(self, data: List[Dict], filepath: str) -> bool:
        """
        导出数据到 JSON 文件

        Args:
            data: 数据列表
            filepath: 文件路径

        Returns:
            是否成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(data)} records to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False

    def get_statistics(self, products: List[Dict]) -> Dict:
        """
        获取数据统计信息

        Args:
            products: 商品数据列表

        Returns:
            统计信息字典
        """
        stats = {
            "total_products": len(products),
            "total_merchants": len(set(p.get("merchant_id") for p in products)),
            "products_with_price": sum(1 for p in products if p.get("price") is not None),
            "products_with_rating": sum(1 for p in products if p.get("rating") is not None),
            "in_stock_count": sum(1 for p in products if p.get("in_stock", False)),
            "avg_price": 0,
            "avg_rating": 0,
            "price_range": None,
            "rating_range": None
        }

        # 计算平均价格
        prices = [p["price"] for p in products if p.get("price") is not None]
        if prices:
            stats["avg_price"] = sum(prices) / len(prices)
            stats["price_range"] = [min(prices), max(prices)]

        # 计算平均评分
        ratings = [p["rating"] for p in products if p.get("rating") is not None]
        if ratings:
            stats["avg_rating"] = sum(ratings) / len(ratings)
            stats["rating_range"] = [min(ratings), max(ratings)]

        return stats
