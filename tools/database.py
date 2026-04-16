# -*- coding: utf-8 -*-
"""
tools/database.py
=================
数据库工具

功能:
- db_query: 执行 SELECT 查询
- db_write: 执行 INSERT/UPDATE/UPSERT
- 连接池管理
- 事务支持
"""

import logging
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager
import threading

try:
    import pymysql
    from pymysql.cursors import DictCursor
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

from .base_tool import (
    BaseTool, ToolConfig, ToolResult, ToolError, 
    ValidationError, ExecutionError
)


logger = logging.getLogger(__name__)


# 默认数据库配置
DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4"
}


class ConnectionPool:
    """
    简单的连接池
    
    线程安全的数据库连接池
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_config: Dict[str, Any] = None, pool_size: int = 5):
        if self._initialized:
            return
        
        self.db_config = db_config or DEFAULT_DB_CONFIG
        self.pool_size = pool_size
        self._pool: List = []
        self._pool_lock = threading.Lock()
        self._initialized = True
    
    def get_connection(self):
        """获取连接"""
        if not PYMYSQL_AVAILABLE:
            raise ImportError("pymysql is required for database operations")
        
        with self._pool_lock:
            if self._pool:
                return self._pool.pop()
        
        return self._create_connection()
    
    def return_connection(self, conn):
        """归还连接"""
        with self._pool_lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                conn.close()
    
    def _create_connection(self):
        """创建新连接"""
        return pymysql.connect(
            host=self.db_config.get("host", "localhost"),
            user=self.db_config.get("user", "root"),
            password=self.db_config.get("password", ""),
            database=self.db_config.get("database", ""),
            charset=self.db_config.get("charset", "utf8mb4"),
            cursorclass=DictCursor,
            autocommit=True
        )
    
    @contextmanager
    def connection(self):
        """连接上下文管理器"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)


# 全局连接池
_db_pool: Optional[ConnectionPool] = None


def get_db_pool(db_config: Dict[str, Any] = None) -> ConnectionPool:
    """获取数据库连接池"""
    global _db_pool
    if _db_pool is None:
        _db_pool = ConnectionPool(db_config)
    return _db_pool


def init_db_pool(db_config: Dict[str, Any]):
    """初始化数据库连接池"""
    global _db_pool
    _db_pool = ConnectionPool(db_config)


class DBQueryTool(BaseTool):
    """
    数据库查询工具
    
    执行 SELECT 查询并返回结果
    """
    
    def __init__(self, config: ToolConfig = None, db_config: Dict[str, Any] = None):
        if config is None:
            config = ToolConfig(
                id="db_query",
                name="数据库查询",
                type="database",
                description="执行 SQL 查询，返回结果数组",
                parameters={
                    "sql": {
                        "type": "string",
                        "description": "SQL 查询语句 (仅支持 SELECT)",
                        "required": True
                    }
                },
                returns={
                    "type": "array",
                    "description": "查询结果数组，每行为一个字典"
                },
                timeout=30,
                safe=True,
                error_handling="raise"
            )
        
        super().__init__(config)
        self.db_config = db_config or DEFAULT_DB_CONFIG
        self._pool = get_db_pool(self.db_config)
    
    def execute(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行查询
        
        Args:
            params: {"sql": "SELECT * FROM table"}
        
        Returns:
            查询结果列表
        """
        sql = params.get("sql", "").strip()
        
        # 安全检查：只允许 SELECT
        if not sql.upper().startswith("SELECT"):
            raise ValidationError(
                self.config.id,
                "Only SELECT statements are allowed for db_query"
            )
        
        # 禁止危险操作
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
        for keyword in dangerous_keywords:
            if keyword in sql.upper():
                raise ValidationError(
                    self.config.id,
                    f"Dangerous keyword '{keyword}' is not allowed"
                )
        
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return list(results) if results else []
        
        except pymysql.Error as e:
            raise ExecutionError(
                self.config.id,
                f"Database query failed: {e}",
                e
            )


class DBWriteTool(BaseTool):
    """
    数据库写入工具
    
    执行 INSERT/UPDATE/UPSERT 操作
    """
    
    def __init__(self, config: ToolConfig = None, db_config: Dict[str, Any] = None):
        if config is None:
            config = ToolConfig(
                id="db_write",
                name="数据库写入",
                type="database",
                description="写入数据到数据库表",
                parameters={
                    "table": {
                        "type": "string",
                        "description": "目标表名",
                        "required": True
                    },
                    "data": {
                        "type": "object",
                        "description": "要写入的数据 (键值对)",
                        "required": True
                    },
                    "mode": {
                        "type": "string",
                        "description": "写入模式",
                        "enum": ["insert", "update", "upsert"],
                        "default": "insert"
                    },
                    "where": {
                        "type": "string",
                        "description": "UPDATE 模式的 WHERE 条件"
                    }
                },
                returns={
                    "type": "object",
                    "description": "写入结果，包含 affected_rows, insert_id"
                },
                timeout=30,
                safe=False,
                error_handling="raise"
            )
        
        super().__init__(config)
        self.db_config = db_config or DEFAULT_DB_CONFIG
        self._pool = get_db_pool(self.db_config)
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行写入
        
        Args:
            params: {
                "table": "table_name",
                "data": {"field1": "value1", ...},
                "mode": "insert" | "update" | "upsert",
                "where": "id = 1"  # for update mode
            }
        
        Returns:
            {"affected_rows": 1, "insert_id": 123}
        """
        table = params.get("table")
        data = params.get("data", {})
        mode = params.get("mode", "insert")
        where = params.get("where")
        
        if not table:
            raise ValidationError(self.config.id, "Table name is required")
        
        if not data:
            raise ValidationError(self.config.id, "Data is required")
        
        if mode == "update" and not where:
            raise ValidationError(
                self.config.id,
                "WHERE clause is required for UPDATE mode"
            )
        
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    if mode == "insert":
                        sql, values = self._build_insert(table, data)
                    elif mode == "update":
                        sql, values = self._build_update(table, data, where)
                    elif mode == "upsert":
                        sql, values = self._build_upsert(table, data)
                    else:
                        raise ValidationError(
                            self.config.id,
                            f"Unknown mode: {mode}"
                        )
                    
                    affected_rows = cursor.execute(sql, values)
                    conn.commit()
                    
                    return {
                        "affected_rows": affected_rows,
                        "insert_id": cursor.lastrowid,
                        "mode": mode
                    }
        
        except pymysql.Error as e:
            raise ExecutionError(
                self.config.id,
                f"Database write failed: {e}",
                e
            )
    
    def _build_insert(self, table: str, data: Dict[str, Any]) -> tuple:
        """构建 INSERT 语句"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return sql, list(data.values())
    
    def _build_update(self, table: str, data: Dict[str, Any], where: str) -> tuple:
        """构建 UPDATE 语句"""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        return sql, list(data.values())
    
    def _build_upsert(self, table: str, data: Dict[str, Any]) -> tuple:
        """构建 INSERT ... ON DUPLICATE KEY UPDATE 语句"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        update_clause = ", ".join([f"{k} = VALUES({k})" for k in data.keys()])
        
        sql = f"""
            INSERT INTO {table} ({columns}) 
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        return sql, list(data.values())


# 便捷函数
def db_query(sql: str) -> List[Dict[str, Any]]:
    """
    快捷查询函数
    
    Args:
        sql: SELECT 语句
    
    Returns:
        查询结果列表
    """
    tool = DBQueryTool()
    result = tool.run({"sql": sql})
    if not result.success:
        raise result.error if result.error else ExecutionError("db_query", "Unknown error")
    return result.data


def db_insert(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    快捷插入函数
    
    Args:
        table: 表名
        data: 数据字典
    
    Returns:
        操作结果
    """
    tool = DBWriteTool()
    result = tool.run({"table": table, "data": data, "mode": "insert"})
    if not result.success:
        raise result.error if result.error else ExecutionError("db_insert", "Unknown error")
    return result.data


def db_update(table: str, data: Dict[str, Any], where: str) -> Dict[str, Any]:
    """
    快捷更新函数
    
    Args:
        table: 表名
        data: 数据字典
        where: WHERE 条件
    
    Returns:
        操作结果
    """
    tool = DBWriteTool()
    result = tool.run({"table": table, "data": data, "mode": "update", "where": where})
    if not result.success:
        raise result.error if result.error else ExecutionError("db_update", "Unknown error")
    return result.data


def db_upsert(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    快捷 Upsert 函数
    
    Args:
        table: 表名
        data: 数据字典
    
    Returns:
        操作结果
    """
    tool = DBWriteTool()
    result = tool.run({"table": table, "data": data, "mode": "upsert"})
    if not result.success:
        raise result.error if result.error else ExecutionError("db_upsert", "Unknown error")
    return result.data
