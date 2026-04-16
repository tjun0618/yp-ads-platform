"""
YP 平台商家数据采集器
从 YP Monetization API 获取所有商家信息
"""

import requests
import time
from typing import List, Dict, Optional
from loguru import logger
from dataclasses import dataclass


@dataclass
class Merchant:
    """商家数据模型"""
    merchant_id: str
    merchant_name: str
    commission_rate: str
    tracking_link: str
    description: str
    category: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant_name,
            "commission_rate": self.commission_rate,
            "tracking_link": self.tracking_link,
            "description": self.description,
            "category": self.category
        }


class YPMerchantCollector:
    """YP 商家采集器"""

    def __init__(self, api_base: str, api_endpoint: str,
                 rate_limit: int = 10, timeout: int = 30, retry_times: int = 3):
        """
        初始化采集器

        Args:
            api_base: API 基础 URL
            api_endpoint: API 端点
            rate_limit: 每分钟请求限制
            timeout: 请求超时时间(秒)
            retry_times: 重试次数
        """
        self.api_base = api_base
        self.api_endpoint = api_endpoint
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.retry_times = retry_times
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = 0

    def _respect_rate_limit(self):
        """遵守 API 限流规则"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < (60 / self.rate_limit):
            sleep_time = (60 / self.rate_limit) - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        发起 HTTP 请求（带重试）

        Args:
            url: 请求 URL
            params: 请求参数

        Returns:
            响应 JSON 数据
        """
        for attempt in range(self.retry_times):
            try:
                self._respect_rate_limit()

                logger.info(f"Requesting {url} (attempt {attempt + 1}/{self.retry_times})")

                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )

                self.request_count += 1

                response.raise_for_status()

                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
                if attempt == self.retry_times - 1:
                    raise

            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error: {e.response.status_code} (attempt {attempt + 1})")

                if e.response.status_code == 429:
                    # 限流，等待更长时间
                    wait_time = 60 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time} seconds")
                    time.sleep(wait_time)

                if attempt == self.retry_times - 1:
                    raise

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                if attempt == self.retry_times - 1:
                    raise

        return None

    def get_all_merchants(self, start_page: int = 1,
                          max_pages: Optional[int] = None) -> List[Merchant]:
        """
        获取所有商家信息

        Args:
            start_page: 起始页码
            max_pages: 最大页数（None 表示全部）

        Returns:
            商家列表
        """
        logger.info("Starting merchant collection from YP platform...")

        merchants = []
        page = start_page

        while True:
            if max_pages and page > max_pages:
                logger.info(f"Reached max pages limit: {max_pages}")
                break

            logger.info(f"Fetching page {page}...")

            url = f"{self.api_base}{self.api_endpoint}"
            params = {
                "page": page,
                "limit": 100  # 每页返回数量
            }

            try:
                data = self._make_request(url, params)

                if not data:
                    logger.error(f"Failed to fetch page {page}")
                    break

                # 解析响应数据
                page_merchants = self._parse_merchants(data)

                if not page_merchants:
                    logger.info(f"No more merchants found on page {page}")
                    break

                merchants.extend(page_merchants)
                logger.info(f"Found {len(page_merchants)} merchants on page {page}")

                page += 1

            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break

        logger.info(f"Total merchants collected: {len(merchants)}")
        return merchants

    def _parse_merchants(self, data: Dict) -> List[Merchant]:
        """
        解析商家数据

        Args:
            data: API 响应数据

        Returns:
            商家列表
        """
        merchants = []

        # 根据实际 API 响应结构解析
        # 注意：这里需要根据 YP 平台实际返回的数据结构进行调整

        try:
            # 假设数据结构为 { "data": [ {...}, {...} ] }
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    merchant = Merchant(
                        merchant_id=str(item.get("id", "")),
                        merchant_name=item.get("name", ""),
                        commission_rate=item.get("commission", ""),
                        tracking_link=item.get("link", ""),
                        description=item.get("description", ""),
                        category=item.get("category", "")
                    )
                    merchants.append(merchant)

            # 假设数据结构为 { "list": [ {...}, {...} ] }
            elif "list" in data and isinstance(data["list"], list):
                for item in data["list"]:
                    merchant = Merchant(
                        merchant_id=str(item.get("id", "")),
                        merchant_name=item.get("name", ""),
                        commission_rate=item.get("commission", ""),
                        tracking_link=item.get("link", ""),
                        description=item.get("description", ""),
                        category=item.get("category", "")
                    )
                    merchants.append(merchant)

            # 假设数据直接是列表
            elif isinstance(data, list):
                for item in data:
                    merchant = Merchant(
                        merchant_id=str(item.get("id", "")),
                        merchant_name=item.get("name", ""),
                        commission_rate=item.get("commission", ""),
                        tracking_link=item.get("link", ""),
                        description=item.get("description", ""),
                        category=item.get("category", "")
                    )
                    merchants.append(merchant)

            else:
                logger.warning(f"Unexpected data structure: {list(data.keys())}")

        except Exception as e:
            logger.error(f"Error parsing merchants: {e}")

        return merchants

    def get_merchant_by_id(self, merchant_id: str) -> Optional[Merchant]:
        """
        根据商家 ID 获取商家信息

        Args:
            merchant_id: 商家 ID

        Returns:
            商家信息
        """
        url = f"{self.api_base}{self.api_endpoint}"
        params = {"id": merchant_id}

        try:
            data = self._make_request(url, params)

            if data:
                merchants = self._parse_merchants(data)
                if merchants:
                    return merchants[0]

        except Exception as e:
            logger.error(f"Error fetching merchant {merchant_id}: {e}")

        return None

    def close(self):
        """关闭会话"""
        self.session.close()
        logger.info(f"Total requests made: {self.request_count}")
