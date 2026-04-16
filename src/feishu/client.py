"""
飞书 API 客户端
用于与飞书文档 API 交互
"""

import requests
import time
import json
from typing import Optional, Dict, List
from loguru import logger
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    base_url: str = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书客户端"""

    def __init__(self, config: FeishuConfig):
        """
        初始化客户端

        Args:
            config: 飞书配置
        """
        self.config = config
        self.access_token = None
        self.token_expires_at = 0
        self.session = requests.Session()

    def _get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token

        Returns:
            access token
        """
        # 检查 token 是否过期
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"{self.config.base_url}/auth/v3/tenant_access_token/internal"

        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret
        }

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"Failed to get token: {data.get('msg')}")

            self.access_token = data["tenant_access_token"]
            # 设置过期时间（提前5分钟）
            self.token_expires_at = time.time() + data["expire"] - 300

            logger.info("Successfully got tenant access token")
            return self.access_token

        except Exception as e:
            logger.error(f"Error getting tenant access token: {e}")
            raise

    def _make_request(self, method: str, endpoint: str,
                      data: Optional[Dict] = None,
                      params: Optional[Dict] = None,
                      retry: int = 3) -> Optional[Dict]:
        """
        发起 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            data: 请求体
            params: 查询参数
            retry: 重试次数

        Returns:
            响应数据
        """
        url = f"{self.config.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }

        for attempt in range(retry):
            try:
                logger.debug(f"Request: {method} {url}")

                if method == "GET":
                    response = self.session.get(url, headers=headers, params=params, timeout=30)
                else:
                    response = self.session.post(url, headers=headers, json=data, timeout=30)

                response.raise_for_status()

                result = response.json()

                if result.get("code") == 0:
                    return result.get("data")
                else:
                    logger.warning(f"API error: {result.get('msg')}")
                    return None

            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error: {e.response.status_code}")

                if e.response.status_code == 429:
                    # 限流，等待后重试
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time} seconds")
                    time.sleep(wait_time)

                if attempt == retry - 1:
                    raise

            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt == retry - 1:
                    raise

        return None

    def create_document(self, title: str, folder_token: Optional[str] = None) -> Optional[str]:
        """
        创建飞书文档

        Args:
            title: 文档标题
            folder_token: 文件夹 token（可选）

        Returns:
            文档 token
        """
        endpoint = "/docx/v1/documents"

        data = {
            "title": title
        }

        if folder_token:
            data["parent_node"] = folder_token

        result = self._make_request("POST", endpoint, data=data)

        if result:
            document_id = result.get("document", {}).get("document_id")
            logger.info(f"Created document: {document_id}")
            return document_id

        return None

    def create_spreadsheet(self, title: str, folder_token: Optional[str] = None) -> Optional[str]:
        """
        创建飞书表格

        Args:
            title: 表格标题
            folder_token: 文件夹 token（可选）

        Returns:
            表格 token
        """
        endpoint = "/sheets/v3/spreadsheets"

        data = {
            "title": title
        }

        if folder_token:
            data["folder_token"] = folder_token

        result = self._make_request("POST", endpoint, data=data)

        if result:
            spreadsheet_token = result.get("spreadsheet", {}).get("spreadsheet_token")
            logger.info(f"Created spreadsheet: {spreadsheet_token}")
            return spreadsheet_token

        return None

    def add_sheet(self, spreadsheet_token: str, title: str) -> Optional[str]:
        """
        添加工作表

        Args:
            spreadsheet_token: 表格 token
            title: 工作表标题

        Returns:
            工作表 ID
        """
        endpoint = "/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/batchAdd"

        data = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": title
                        }
                    }
                }
            ]
        }

        result = self._make_request("POST", endpoint, data=data)

        if result:
            sheet_id = result.get("updates", {}).get("addSheets", [{}])[0].get("properties", {}).get("sheet_id")
            logger.info(f"Added sheet: {sheet_id}")
            return str(sheet_id)

        return None

    def add_rows(self, spreadsheet_token: str, sheet_id: str, rows: List[List]) -> bool:
        """
        批量添加行数据

        Args:
            spreadsheet_token: 表格 token
            sheet_id: 工作表 ID
            rows: 行数据（每行是一个列表）

        Returns:
            是否成功
        """
        endpoint = "/sheets/v2/spreadsheets/{spreadsheet_token}/append"

        data = {
            "valueRange": {
                "sheetId": sheet_id,
                "values": rows
            }
        }

        result = self._make_request("POST", endpoint, data=data)

        if result:
            update_count = result.get("updates", {}).get("updatedRows", 0)
            logger.info(f"Added {update_count} rows")
            return True

        return False

    def write_product_data(self, spreadsheet_token: str,
                           sheet_id: str,
                           products: List[Dict]) -> bool:
        """
        写入商品数据到飞书表格

        Args:
            spreadsheet_token: 表格 token
            sheet_id: 工作表 ID
            products: 商品数据列表

        Returns:
            是否成功
        """
        # 定义表头
        headers = [
            "商家名称",
            "商品ASIN",
            "商品名称",
            "价格",
            "货币",
            "佣金率",
            "评分",
            "评论数",
            "品牌",
            "类别",
            "商品描述",
            "追踪链接",
            "采集时间"
        ]

        # 构建数据行
        rows = [headers]

        for product in products:
            row = [
                product.get("merchant_name", ""),
                product.get("asin", ""),
                product.get("product_name", ""),
                str(product.get("price", "")),
                product.get("currency", ""),
                product.get("commission_rate", ""),
                str(product.get("rating", "")),
                str(product.get("review_count", "")),
                product.get("brand", ""),
                product.get("category", ""),
                product.get("description", ""),
                product.get("tracking_link", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            rows.append(row)

        # 分批写入（每批最多 500 行）
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            success = self.add_rows(spreadsheet_token, sheet_id, batch)

            if not success:
                logger.error(f"Failed to add batch {i}-{i+len(batch)}")
                return False

            # 避免限流
            time.sleep(0.5)

        logger.info(f"Successfully wrote {len(products)} products to Feishu")
        return True

    def get_spreadsheet_info(self, spreadsheet_token: str) -> Optional[Dict]:
        """
        获取表格信息

        Args:
            spreadsheet_token: 表格 token

        Returns:
            表格信息
        """
        endpoint = f"/sheets/v3/spreadsheets/{spreadsheet_token}/metainfo"

        result = self._make_request("GET", endpoint)

        if result:
            return result

        return None

    def close(self):
        """关闭会话"""
        self.session.close()
