# AI 原生系统配置规范 v1.0

## 配置文件结构

```
config/
├── settings.yaml        # 全局设置
├── agents.yaml          # Agent 定义
├── skills.yaml          # 技能注册
├── tools.yaml           # 工具定义
└── prompts/             # 提示词模板
    ├── system/
    └── user/
```

---

## 一、全局设置 (settings.yaml)

```yaml
# 系统配置
system:
  name: "YP AI System"
  version: "1.0.0"
  debug: true

# LLM 配置
llm:
  default_provider: qianfan
  default_model: ernie-4.0-8k
  
  providers:
    qianfan:
      api_key: ${QIANFAN_AK}
      secret_key: ${QIANFAN_SK}
      models:
        - ernie-4.0-8k
        - ernie-3.5-8k
        - ernie-speed-8k

# 数据库配置
database:
  host: localhost
  port: 3306
  user: root
  password: admin
  database: affiliate_marketing

# 记忆系统配置
memory:
  short_term:
    type: redis
    host: localhost
    port: 6379
    ttl: 3600
  long_term:
    type: none  # none / chromadb / milvus
```

---

## 二、Agent 定义 (agents.yaml)

```yaml
agents:
  orchestrator:
    name: "系统调度员"
    description: "理解用户意图，调度子Agent完成任务"
    model: ernie-4.0-8k
    role: |
      你是 YP Affiliate 系统的主调度员。
      你的职责是理解用户意图，将任务分解，并调度合适的子Agent执行。
    
    capabilities:
      - intent_recognition
      - task_decomposition
      - agent_scheduling
    
    sub_agents:
      - ad_creator
      - scraper
      - analyst
    
    tools:
      - db_query

  ad_creator:
    name: "广告创作专家"
    description: "基于Google Ads技能，为产品生成完整广告方案"
    model: ernie-4.0-8k
    role: |
      你是一位专业的 Google Ads 广告策划专家。
      你拥有10年+ 美国市场 Google Ads 联盟营销投放经验。
    
    skills:
      - google-ads-v5.0
    
    tools:
      - db_query
      - db_write
      - file_write
    
    workflow:
      - step: 1
        name: "获取产品信息"
        tool: db_query
      - step: 2
        name: "执行技能生成广告"
        skill: google-ads-v5.0
      - step: 3
        name: "保存广告方案"
        tool: db_write

  scraper:
    name: "数据采集员"
    description: "采集Amazon、YP、SEMrush等平台数据"
    model: ernie-3.5-8k
    skills:
      - amazon-scraping
      - yp-scraping
    tools:
      - browser_navigate
      - browser_extract
      - db_write

  analyst:
    name: "数据分析师"
    description: "分析广告效果、商品数据，生成洞察报告"
    model: ernie-4.0-8k
    skills:
      - data-analysis
    tools:
      - db_query
      - file_write
```

---

## 三、技能注册 (skills.yaml)

```yaml
skills:
  google-ads-v5.0:
    name: "Google Ads 创作技能 v5.0"
    path: skills/google-ads-v5.0/SKILL.md
    description: "基于用户旅程的专业级 Google Ads 广告创建技能"
    version: "5.0"
    
    references:
      - product-category-analyzer.md
      - keyword-engine.md
      - negative-keywords.md
      - copy-generator.md
      - qa-checker.md
    
    input_schema:
      type: object
      required: [asin, product_name, price]
      properties:
        asin: { type: string }
        product_name: { type: string }
        price: { type: number }
        commission: { type: string }
        rating: { type: number }
        brand_keywords: { type: array }
    
    output_schema:
      type: object
      properties:
        product_analysis: { type: object }
        campaigns: { type: array }
        account_negative_keywords: { type: array }
    
    qa_checks:
      - price_consistency
      - ad_group_duplicates
      - keyword_authenticity
      - template_residue

  amazon-scraping:
    name: "Amazon 商品采集技能"
    path: skills/amazon-scraping/SKILL.md
    description: "采集 Amazon 商品详情数据"
    tools_required:
      - browser_navigate
      - browser_extract
      - db_write

  data-analysis:
    name: "数据分析技能"
    path: skills/data-analysis/SKILL.md
    description: "分析广告效果、商品数据"
    analysis_types:
      - ad_performance
      - product_performance
```

---

## 四、工具定义 (tools.yaml)

```yaml
tools:
  db_query:
    name: "数据库查询"
    type: database
    description: "执行 SQL 查询，返回结果"
    parameters:
      sql:
        type: string
        required: true
    returns: array
    timeout: 30
    safe: true

  db_write:
    name: "数据库写入"
    type: database
    description: "写入数据到数据库"
    parameters:
      table: { type: string, required: true }
      data: { type: object, required: true }
      mode: { type: string, default: insert }
    returns: object
    timeout: 30
    safe: false

  browser_navigate:
    name: "打开网页"
    type: browser
    description: "使用浏览器打开指定 URL"
    parameters:
      url: { type: string, required: true }
      wait_until: { type: string, default: domcontentloaded }
    timeout: 60

  browser_extract:
    name: "提取数据"
    type: browser
    description: "从页面提取数据"
    parameters:
      selectors: { type: object, required: true }
    returns: object
    timeout: 10

  http_request:
    name: "HTTP 请求"
    type: http
    description: "发送 HTTP 请求"
    parameters:
      method: { type: string, default: GET }
      url: { type: string, required: true }
      headers: { type: object }
      body: { type: object }
    returns: object
    timeout: 30

  file_write:
    name: "写入文件"
    type: file
    description: "写入内容到文件"
    parameters:
      path: { type: string, required: true }
      content: { type: string, required: true }
    returns: boolean

  notify:
    name: "发送通知"
    type: notification
    description: "发送通知消息"
    parameters:
      channel: { type: string, required: true }
      message: { type: string, required: true }
    timeout: 10
```

---

## 五、配置加载器实现

```python
# config/loader.py
import os
import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._cache = {}
    
    def load_settings(self) -> Dict[str, Any]:
        return self._load_yaml("settings.yaml")
    
    def load_agents(self) -> Dict[str, Any]:
        return self._load_yaml("agents.yaml")["agents"]
    
    def load_agent(self, agent_id: str) -> Dict[str, Any]:
        return self.load_agents().get(agent_id)
    
    def load_skills(self) -> Dict[str, Any]:
        return self._load_yaml("skills.yaml")["skills"]
    
    def load_skill_content(self, skill_id: str) -> str:
        skill_config = self.load_skill(skill_id)
        if not skill_config:
            raise ValueError(f"Skill not found: {skill_id}")
        
        skill_path = Path(skill_config["path"])
        if not skill_path.is_absolute():
            skill_path = self.config_dir.parent / skill_path
        
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 加载参考文件
        refs = skill_config.get("references", [])
        if refs:
            refs_dir = skill_path.parent / "references"
            for ref in refs:
                ref_path = refs_dir / ref
                if ref_path.exists():
                    with open(ref_path, 'r', encoding='utf-8') as f:
                        content += f"\n\n---\n\n## {ref}\n\n{f.read()}"
        
        return content
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        if filename in self._cache:
            return self._cache[filename]
        
        filepath = self.config_dir / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        data = self._replace_env_vars(data)
        self._cache[filename] = data
        return data
    
    def _replace_env_vars(self, obj: Any) -> Any:
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        return obj

# 全局实例
config = ConfigLoader()
```

---

## 六、下一步

1. 创建 `config/` 目录和配置文件
2. 实现 `ConfigLoader` 类
3. 创建 `Agent` 基类（从配置创建）
4. 迁移广告生成功能到新架构
