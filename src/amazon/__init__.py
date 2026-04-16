"""
亚马逊爬虫模块
"""

from .crawler import AmazonCrawler, Product, run_crawler

__all__ = ['AmazonCrawler', 'Product', 'run_crawler']
