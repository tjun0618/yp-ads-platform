"""
亚马逊商品数据爬虫
使用 Playwright 从亚马逊商品页面提取产品信息
"""

import asyncio
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from loguru import logger
from fake_useragent import UserAgent
import json


@dataclass
class Product:
    """商品数据模型"""
    asin: str
    product_name: str
    price: Optional[float]
    currency: str
    rating: Optional[float]
    review_count: Optional[int]
    description: str
    product_url: str
    product_image: Optional[str]
    category: Optional[str]
    brand: Optional[str]
    in_stock: bool

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "asin": self.asin,
            "product_name": self.product_name,
            "price": self.price,
            "currency": self.currency,
            "rating": self.rating,
            "review_count": self.review_count,
            "description": self.description,
            "product_url": self.product_url,
            "product_image": self.product_image,
            "category": self.category,
            "brand": self.brand,
            "in_stock": self.in_stock
        }


class AmazonCrawler:
    """亚马逊商品爬虫"""

    def __init__(self,
                 headless: bool = False,
                 timeout: int = 60000,
                 request_delay: float = 2.0,
                 max_concurrent: int = 5):
        """
        初始化爬虫

        Args:
            headless: 是否使用无头浏览器
            timeout: 页面加载超时(毫秒)
            request_delay: 请求间隔(秒)
            max_concurrent: 最大并发数
        """
        self.headless = headless
        self.timeout = timeout
        self.request_delay = request_delay
        self.max_concurrent = max_concurrent
        self.ua = UserAgent()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()

        # 启动浏览器
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )

        # 创建上下文
        self.context = await self.browser.new_context(
            user_agent=self.ua.random,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York'
        )

        # 添加反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        logger.info("Browser started")

    async def stop(self):
        """停止浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser stopped")

    async def scrape_product(self, url: str) -> Optional[Product]:
        """
        爬取单个商品页面

        Args:
            url: 亚马逊商品 URL

        Returns:
            商品数据
        """
        try:
            page = await self.context.new_page()
            await page.set_default_timeout(self.timeout)

            # 访问页面
            logger.info(f"Scraping product: {url}")
            await page.goto(url, wait_until="networkidle")

            # 等待主内容加载
            await page.wait_for_selector('#productTitle', timeout=30000)

            # 提取商品信息
            product_data = await self._extract_product_data(page, url)

            await page.close()

            if product_data:
                logger.info(f"Successfully scraped: {product_data.product_name}")

                # 请求延迟
                await asyncio.sleep(self.request_delay)

                return product_data
            else:
                logger.warning(f"Failed to extract data from: {url}")
                return None

        except Exception as e:
            logger.error(f"Error scraping product {url}: {e}")
            return None

    async def _extract_product_data(self, page: Page, url: str) -> Optional[Product]:
        """
        从页面提取商品数据

        Args:
            page: Playwright 页面对象
            url: 页面 URL

        Returns:
            商品数据
        """
        try:
            # ASIN
            asin = await self._extract_asin(page, url)

            # 商品名称
            product_name = await self._extract_text(page, '#productTitle', '')

            # 价格
            price, currency = await self._extract_price(page)

            # 评分
            rating = await self._extract_rating(page)

            # 评论数
            review_count = await self._extract_review_count(page)

            # 描述
            description = await self._extract_description(page)

            # 商品图片
            product_image = await self._extract_image(page)

            # 类别
            category = await self._extract_category(page)

            # 品牌
            brand = await self._extract_brand(page)

            # 是否有库存
            in_stock = await self._extract_stock_status(page)

            return Product(
                asin=asin,
                product_name=product_name,
                price=price,
                currency=currency,
                rating=rating,
                review_count=review_count,
                description=description,
                product_url=url,
                product_image=product_image,
                category=category,
                brand=brand,
                in_stock=in_stock
            )

        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None

    async def _extract_text(self, page: Page, selector: str, default: str = "") -> str:
        """提取文本内容"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip()
            return default
        except:
            return default

    async def _extract_asin(self, page: Page, url: str) -> str:
        """提取 ASIN"""
        try:
            # 尝试从 URL 中提取
            import re
            dp_match = re.search(r'/dp/([A-Z0-9]{10})', url)
            if dp_match:
                return dp_match.group(1)

            # 尝试从页面元素中提取
            asin = await self._extract_text(page, '#ASIN', '')
            if asin:
                return asin

            return "UNKNOWN"

        except:
            return "UNKNOWN"

    async def _extract_price(self, page: Page) -> tuple[Optional[float], str]:
        """提取价格"""
        try:
            # 尝试多个价格选择器
            selectors = [
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                '#price_inside_buybox',
                '.a-price .a-offscreen',
                '[data-a-color="price"]'
            ]

            price_text = None
            for selector in selectors:
                price_text = await self._extract_text(page, selector)
                if price_text:
                    break

            if not price_text:
                return None, "USD"

            # 解析价格
            price_text = price_text.replace('$', '').replace(',', '').strip()

            # 处理价格范围（如 "$10.99 - $19.99"）
            if '-' in price_text:
                prices = price_text.split('-')
                price = float(prices[0].strip())
            else:
                price = float(price_text)

            return price, "USD"

        except:
            return None, "USD"

    async def _extract_rating(self, page: Page) -> Optional[float]:
        """提取评分"""
        try:
            rating_text = await self._extract_text(page, '#acrPopover .a-icon-alt', '0')

            # 解析评分文本 "4.5 out of 5 stars"
            import re
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                return float(match.group(1))

            return None

        except:
            return None

    async def _extract_review_count(self, page: Page) -> Optional[int]:
        """提取评论数"""
        try:
            review_text = await self._extract_text(page, '#acrCustomerReviewText', '0')

            # 解析评论数 "12,345 ratings"
            import re
            match = re.search(r'([\d,]+)', review_text)
            if match:
                return int(match.group(1).replace(',', ''))

            return None

        except:
            return None

    async def _extract_description(self, page: Page) -> str:
        """提取商品描述"""
        try:
            # 尝试多个描述选择器
            selectors = [
                '#productDescription',
                '#feature-bullets ul',
                '#centerCol .a-list-item'
            ]

            description = ""
            for selector in selectors:
                desc = await self._extract_text(page, selector)
                if desc:
                    description = desc
                    break

            # 限制描述长度
            if len(description) > 1000:
                description = description[:1000] + "..."

            return description

        except:
            return ""

    async def _extract_image(self, page: Page) -> Optional[str]:
        """提取商品图片"""
        try:
            # 查找主图片
            img = await page.query_selector('#landingImage, #imgBlkFront, .a-dynamic-image')
            if img:
                src = await img.get_attribute('src')
                return src

            return None

        except:
            return None

    async def _extract_category(self, page: Page) -> Optional[str]:
        """提取类别"""
        try:
            category = await self._extract_text(page, '#wayfinding-breadcrumbs_container', '')
            return category

        except:
            return None

    async def _extract_brand(self, page: Page) -> Optional[str]:
        """提取品牌"""
        try:
            brand = await self._extract_text(page, '#bylineInfo', '')
            # 清理品牌文本 "by Nike"
            brand = brand.replace('by ', '').replace('Brand: ', '').strip()
            return brand

        except:
            return None

    async def _extract_stock_status(self, page: Page) -> bool:
        """提取库存状态"""
        try:
            # 检查是否有"Add to Cart"按钮
            add_to_cart = await page.query_selector('#add-to-cart-button, #buybox-see-all')
            if add_to_cart:
                return True

            # 检查是否有"Out of Stock"提示
            out_of_stock = await page.query_selector('#availability span:has-text("Out of Stock")')
            if out_of_stock:
                return False

            return True

        except:
            return True

    async def scrape_multiple(self, urls: List[str]) -> List[Product]:
        """
        批量爬取商品

        Args:
            urls: 商品 URL 列表

        Returns:
            商品数据列表
        """
        logger.info(f"Starting to scrape {len(urls)} products...")

        products = []

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def scrape_with_semaphore(url: str) -> Optional[Product]:
            async with semaphore:
                return await self.scrape_product(url)

        # 并发爬取
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        # 过滤 None 结果
        products = [p for p in results if p is not None]

        logger.info(f"Successfully scraped {len(products)}/{len(urls)} products")
        return products


async def run_crawler(urls: List[str],
                      headless: bool = False,
                      max_concurrent: int = 5) -> List[Product]:
    """
    运行爬虫的便捷函数

    Args:
        urls: 商品 URL 列表
        headless: 是否使用无头浏览器
        max_concurrent: 最大并发数

    Returns:
        商品数据列表
    """
    crawler = AmazonCrawler(
        headless=headless,
        max_concurrent=max_concurrent
    )

    await crawler.start()

    try:
        products = await crawler.scrape_multiple(urls)
        return products
    finally:
        await crawler.stop()


if __name__ == "__main__":
    # 测试代码
    async def test():
        test_url = "https://www.amazon.com/dp/B08XXXXX01"  # 替换为真实 URL

        crawler = AmazonCrawler(headless=False)
        await crawler.start()

        product = await crawler.scrape_product(test_url)

        if product:
            print(json.dumps(product.to_dict(), indent=2, ensure_ascii=False))

        await crawler.stop()

    asyncio.run(test())
