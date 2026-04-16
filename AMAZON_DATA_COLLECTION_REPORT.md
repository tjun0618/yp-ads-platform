# 亚马逊商品数据采集报告

**采集日期**: 2026-03-22
**采集状态**: ✅ 完成

---

## 📊 采集概况

### 总体统计
- **爬取商家数**: 8个
- **搜索产品数**: 40个
- **爬取详情数**: 32个
- **数据格式**: JSON + CSV
- **采集时长**: 约3-4分钟

### 采集的商家列表

| # | 商家名称 | 产品数 | 详情数 |
|---|---------|-------|-------|
| 1 | OlliePets_US | 5 | 4 |
| 2 | Sik Silk PL | 5 | 4 |
| 3 | Lepro | 5 | 4 |
| 4 | iHerb | 5 | 4 |
| 5 | DOVOH | 5 | 4 |
| 6 | Hoka US | 5 | 4 |
| 7 | VANTRUE | 5 | 4 |
| 8 | SUNUV | 5 | 4 |

---

## 📁 数据文件

### 搜索结果文件

1. **amazon_search_results_improved.json**
   - 路径: `output/amazon_search_results_improved.json`
   - 格式: JSON
   - 记录数: 40条
   - 包含字段:
     - `asin`: 亚马逊产品ID
     - `title`: 产品标题
     - `price`: 价格
     - `rating`: 评分
     - `reviews`: 评论数
     - `image_url`: 产品图片
     - `merchant_name`: 商家名称
     - `product_url`: 产品链接
     - `collected_at`: 采集时间

2. **amazon_search_results_improved.csv**
   - 路径: `output/amazon_search_results_improved.csv`
   - 格式: CSV
   - 记录数: 40条
   - 用途: 数据分析和导入到其他工具

### 产品详情文件

1. **amazon_product_details_improved.json**
   - 路径: `output/amazon_product_details_improved.json`
   - 格式: JSON
   - 记录数: 32条
   - 包含字段:
     - `asin`: 亚马逊产品ID
     - `title`: 产品标题
     - `price`: 价格
     - `rating`: 评分
     - `review_count`: 评论数
     - `description`: 产品描述
     - `features`: 产品特性（列表）
     - `images`: 产品图片（列表）
     - `brand`: 品牌
     - `product_url`: 产品链接
     - `collected_at`: 采集时间

2. **amazon_product_details_improved.csv**
   - 路径: `output/amazon_product_details_improved.csv`
   - 格式: CSV
   - 记录数: 32条
   - 注意: 列表字段（features, images）用 ` | ` 分隔

---

## 🎯 采集的产品类别

### 宠物用品
- OlliePets_US
  - 狗玩具（章鱼玩具、绳结玩具）
  - 狗碗（不锈钢、防滑）
  - 猫屋（多猫、可折叠）

### 服装配饰
- Sik Silk PL
  - 丝绸枕套
  - 丝绸内衣
  - 睡衣套装

### 照明设备
- Lepro
  - RGB落地灯
  - 智能台灯
  - 氛围灯
  - 极简台灯

### 健康补充剂
- iHerb
  - NMN补充剂
  - 维生素
  - 蛋白粉
  - 营养补充剂

### 测量工具
- DOVOH
  - 激光水平仪
  - 三脚架
  - 垂直激光仪
  - 外部激光水平仪

### 运动鞋
- Hoka US
  - 跑步鞋
  - 健身鞋
  - 徒步鞋

### 汽车配件
- VANTRUE
  - 行车记录仪
  - 气吹清洁器
  - 汽车配件

### 美甲设备
- SUNUV
  - 美甲灯
  - LED美甲干燥器
  - 电源适配器

---

## 📈 数据质量分析

### 采集成功的产品示例

#### 1. OlliePets_US - 狗玩具
- **ASIN**: B0FWLT3KPM
- **标题**: Ollie The Octopus Dog Toy Tough 4 Inch Handmade Eco Cotton Rope Dog Toy
- **价格**: $117.35
- **评分**: 4.0/5
- **评论数**: 29
- **品牌**: Visit the Chowabunga Store

#### 2. DOVOH - 激光水平仪
- **ASIN**: B09DG38RSH
- **标题**: DOVOH 4x360° Laser Level 360 Self Leveling, 16 Lines Green Laser
- **价格**: $77.99
- **评分**: 4.6/5
- **品牌**: DOVOH
- **特性**: 360°激光, 自调平, 16线绿色激光

#### 3. Hoka US - 跑步鞋
- **ASIN**: B0D5FNKVWN
- **品牌**: HOKA
- **评分**: 4.5+/5
- **类别**: 运动鞋

---

## 🔧 技术实现

### 使用的工具和库
- **Python**: 主要编程语言
- **requests**: HTTP请求库
- **BeautifulSoup4**: HTML解析库
- **csv**: CSV文件处理
- **json**: JSON文件处理

### 采集策略
1. **搜索阶段**: 通过商家名称在亚马逊搜索产品
2. **筛选阶段**: 每个商家提取前5个产品
3. **详情爬取**: 爬取前4个产品的详细信息
4. **数据保存**: 同时保存JSON和CSV格式

### 反爬虫措施
1. **延迟控制**: 请求间隔3-4秒
2. **User-Agent**: 模拟浏览器请求
3. **限制数量**: 控制爬取速度和数量
4. **错误处理**: 添加异常处理机制

---

## 💡 使用建议

### 1. 数据分析
- 使用Excel或Google Sheets打开CSV文件进行分析
- 使用Python pandas库进行数据处理
- 使用Tableau或Power BI进行可视化

### 2. 广告投放
- 根据产品评分筛选高质量产品
- 根据价格定位目标市场
- 根据评论数评估产品热度

### 3. 扩展采集
如需采集更多商家或产品，可修改脚本参数：
```python
max_search_merchants = 20  # 增加商家数量
max_products_per_merchant = 10  # 增加每个商家的产品数
max_detail_scrapes = 10  # 增加详情爬取数量
```

---

## ⚠️ 注意事项

### 1. 采集限制
- 为了避免被亚马逊封禁，当前限制了爬取数量
- 实际使用时建议使用代理IP池
- 可以增加延迟时间降低风险

### 2. 数据准确性
- 价格可能会变动，建议定期更新
- 部分产品可能缺货或下架
- 评分和评论数会随时间变化

### 3. 法律合规
- 遵守亚马逊的服务条款
- 不要用于商业竞争或恶意目的
- 尊重网站robots.txt规定

---

## 📞 技术支持

如有问题或需要扩展功能，可以：
1. 查看脚本代码中的注释
2. 联系开发团队
3. 参考Amazon MWS API文档

---

## 📝 更新日志

### v1.0 (2026-03-22)
- ✅ 初始版本发布
- ✅ 实现8个商家的数据采集
- ✅ 支持40个产品搜索
- ✅ 支持32个产品详情爬取
- ✅ 导出JSON和CSV格式
- ✅ 使用BeautifulSoup进行HTML解析

---

**报告生成时间**: 2026-03-22 13:20
**数据文件位置**: `output/` 目录
**脚本位置**: `scrape_amazon_products_improved.py`
