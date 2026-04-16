"""
YP 追踪链接解析器
解析 YP 追踪链接，提取亚马逊商品 URL
"""

import re
from typing import Optional, List
from urllib.parse import urlparse, parse_qs, urlunparse
from loguru import logger


class YPLinkParser:
    """YP 追踪链接解析器"""

    def __init__(self):
        # YP 域名
        self.yp_domains = [
            "yeahpromos.com",
            "www.yeahpromos.com"
        ]

        # 亚马逊域名
        self.amazon_domains = [
            "amazon.com",
            "www.amazon.com",
            "smile.amazon.com"
        ]

    def parse_tracking_link(self, tracking_link: str) -> Optional[str]:
        """
        解析 YP 追踪链接，提取最终的亚马逊 URL

        Args:
            tracking_link: YP 追踪链接

        Returns:
            亚马逊商品 URL 或 None
        """
        if not tracking_link:
            logger.warning("Empty tracking link")
            return None

        try:
            # 检查是否是 YP 域名
            parsed = urlparse(tracking_link)
            if parsed.netloc not in self.yp_domains:
                logger.warning(f"Not a YP tracking link: {parsed.netloc}")
                return None

            # 解析查询参数
            query_params = parse_qs(parsed.query)

            # 常见的参数名称
            amazon_url = None
            for param_name in ["url", "target", "link", "dest", "redirect"]:
                if param_name in query_params:
                    amazon_url = query_params[param_name][0]
                    break

            if not amazon_url:
                logger.warning(f"No target URL found in tracking link: {tracking_link}")
                return None

            # 验证是否是亚马逊 URL
            if not self._is_amazon_url(amazon_url):
                logger.warning(f"Not an Amazon URL: {amazon_url}")
                return None

            # 清理和规范化 URL
            amazon_url = self._normalize_url(amazon_url)

            logger.info(f"Extracted Amazon URL: {amazon_url}")
            return amazon_url

        except Exception as e:
            logger.error(f"Error parsing tracking link: {e}")
            return None

    def _is_amazon_url(self, url: str) -> bool:
        """
        检查是否是亚马逊 URL

        Args:
            url: URL

        Returns:
            是否是亚马逊 URL
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc in self.amazon_domains
        except:
            return False

    def _normalize_url(self, url: str) -> str:
        """
        规范化 URL（移除追踪参数等）

        Args:
            url: 原始 URL

        Returns:
            规范化的 URL
        """
        try:
            parsed = urlparse(url)

            # 要移除的查询参数（追踪参数）
            tracking_params = [
                "ref_", "tag", "linkCode", "ascsubtag",
                "creativeASIN", "camp", "creative", "linkID"
            ]

            # 解析查询参数
            query_params = parse_qs(parsed.query, keep_blank_values=True)

            # 移除追踪参数
            for param in tracking_params:
                if param in query_params or any(p.startswith(param) for p in query_params):
                    # 移除该参数
                    query_params = {
                        k: v for k, v in query_params.items()
                        if not k.startswith(param)
                    }

            # 重建 URL
            new_query = "&".join(f"{k}={v[0]}" for k, v in query_params.items())
            new_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ""  # 移除 fragment
            ))

            return new_url

        except Exception as e:
            logger.error(f"Error normalizing URL: {e}")
            return url

    def extract_asin(self, url: str) -> Optional[str]:
        """
        从亚马逊 URL 中提取 ASIN

        Args:
            url: 亚马逊 URL

        Returns:
            ASIN 或 None
        """
        if not url:
            return None

        asin = None

        try:
            # 方法 1: 从 /dp/ASIN 中提取
            dp_match = re.search(r'/dp/([A-Z0-9]{10})', url)
            if dp_match:
                asin = dp_match.group(1)
                return asin

            # 方法 2: 从 /gp/product/ASIN 中提取
            gp_match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
            if gp_match:
                asin = gp_match.group(1)
                return asin

            # 方法 3: 从查询参数中提取
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if "ASIN" in query_params:
                asin = query_params["ASIN"][0]
                return asin

            # 方法 4: 从 path 中提取（针对短链接）
            path_match = re.search(r'/([A-Z0-9]{10})(?:/?|$)', url)
            if path_match:
                asin = path_match.group(1)
                return asin

            logger.warning(f"Could not extract ASIN from URL: {url}")
            return None

        except Exception as e:
            logger.error(f"Error extracting ASIN: {e}")
            return None

    def is_product_page(self, url: str) -> bool:
        """
        判断是否是商品页面（而非店铺页面）

        Args:
            url: 亚马逊 URL

        Returns:
            是否是商品页面
        """
        if not url:
            return False

        try:
            # 检查路径
            if "/dp/" in url or "/gp/product/" in url:
                return True

            # 检查查询参数
            if "ASIN" in url:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking if product page: {e}")
            return False

    def parse_multiple_links(self, tracking_links: List[str]) -> List[dict]:
        """
        批量解析追踪链接

        Args:
            tracking_links: 追踪链接列表

        Returns:
            解析结果列表
        """
        results = []

        for link in tracking_links:
            result = {
                "original_link": link,
                "amazon_url": None,
                "asin": None,
                "is_product": False,
                "error": None
            }

            try:
                # 解析追踪链接
                amazon_url = self.parse_tracking_link(link)
                if amazon_url:
                    result["amazon_url"] = amazon_url

                    # 提取 ASIN
                    asin = self.extract_asin(amazon_url)
                    if asin:
                        result["asin"] = asin
                        result["is_product"] = self.is_product_page(amazon_url)

                else:
                    result["error"] = "Failed to parse tracking link"

            except Exception as e:
                result["error"] = str(e)

            results.append(result)

        logger.info(f"Parsed {len(results)} tracking links")
        return results
