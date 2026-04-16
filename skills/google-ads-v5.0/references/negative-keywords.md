# 否定关键词动态生成器 v2.0

> 版本: v2.0 | 2026-03-29
> 用途: 根据产品品类动态生成否定关键词，抛弃通用模板

---

## 一、核心原则

```
否定关键词的目标: 屏蔽无效流量，不是越多越好
每个否定词都必须能回答: "搜这个词的人会买我的产品吗？"
如果答案是"可能" → 不加否定
如果答案是"绝对不会" → 加否定
```

---

## 二、三层否定关键词架构

### 第一层：账户级否定词（全Campaign共用）

按产品品类动态选择，**不使用固定列表**:

#### A. 通用无效流量词（所有产品适用）

```
# 非购买意图
-free
-diy
-homemade
-"do it yourself"
-"make your own"
-used
-"second hand"
-rental
-wholesale
-bulk
-manufacturer
-supplier

# 售后/支持类（所有产品适用）
-setup
-installation
-manual
-instructions
-"how to"           ⚠️ 注意: 痛点驱动型产品(如清洁剂)不加这个词
-tutorial
-guide              ⚠️ 注意: 同上
-troubleshooting
-repair
-fix                ⚠️ 注意: 同上
-broken
-"not working"
-problem            ⚠️ 注意: 功能型产品不加这个词
-issue
-error
-warranty
-service
-support
-help
-"replacement parts"
-"spare parts"

# 退货/投诉类（所有产品适用）
-return
-refund
-exchange
-complaint
-contact
-"phone number"
-"customer service"

# 账号/平台类（所有产品适用）
-login
-"sign in"
-"sign up"
-account
-password
-website
-app                ⚠️ 注意: 如果产品本身是app(如喂食器有app控制)，不加
-"near me"
```

#### B. 品类专属否定词（按产品类型选择）

```
【首饰/珠宝类】（jewelry case, jewelry box, organizer）
追加否定:
-watch box, -watch case, -watch organizer
-ring display, -ring holder, -ring box
-earring stand, -earring display
-necklace stand, -necklace hanger
-bracelet display
-jewelry armoire, -jewelry cabinet, -jewelry drawer
-makeup bag, -makeup case, -cosmetic bag
-coin purse
-diamond, -gold, -silver, -platinum    ← 如果产品不含这些材质
-wooden, -leather                      ← 如果产品不是这些材质
-engraved, -custom                     ← 如果产品不支持定制

【宠物用品类】
追加否定:
-cat food, -dog food, -pet food         ← 如果不是食品
-pet insurance
-vet clinic, -veterinarian
-pet adoption, -adopt a dog
-pet grooming, -grooming service
-dog training, -dog trainer
-pet boarding, -kennel

【电子产品类】
追加否定:
-case, -cover, -screen protector        ← 如果产品本身不是配件
-repair, -fix screen, -broken screen
-refurbished, -used
-data recovery
-software, -driver, -firmware

【健康/保健品类】
追加否定:
-recipe, -cooking, -homemade
-side effects                           ← ⚠️ 这个对保健品反而是有用的流量，考虑不加
-dosage, -how much to take
-prescription, -doctor
-recall
-ingredients                            ← ⚠️ 有时是搜索成分的潜在买家，不加

【礼品类通用】
追加否定:
-for men, -for him, -for dad, -for boyfriend, -husband, -son  ← 如果产品仅面向女性
-for kids, -for children, -for baby
-corporate gift, -business gift           ← 如果不是B2B产品
-gift card, -gift certificate
-wrapping paper, -gift box (空盒)         ← 如果用户在搜索包装材料
```

#### C. 删除不适用的通用否定词

```
以下否定词不应出现在特定品类中:

对礼品型产品:
  ❌ 不要加 -setup, -installation, -manual → 礼品不需要安装说明
  ❌ 不要加 -review → 礼品搜索者会看review做决策，这是有价值的流量
  ❌ 不要加 -problem, -issue → 礼品没有"问题"

对功能型产品（清洁剂等）:
  ❌ 不要加 -"how to" → 用户搜"how to remove pet stain"正是目标流量
  ❌ 不要加 -guide → 用户搜"guide to pet stain removal"是潜在买家
  ❌ 不要加 -fix → 用户搜"fix dog pee smell"正是目标流量

对电子/智能产品:
  ❌ 不要加 -app → 如果产品有app功能，用户搜"app controlled feeder"是目标
  ❌ 不要加 -setup → 用户搜"setup automatic feeder"可能是目标流量
```

---

### 第二层：广告系列级否定词

```
规则: 按广告系列的意图方向添加否定词

品牌Campaign:
  -cheap, -budget, -affordable     ← 防止价格敏感用户稀释品牌词质量
  -alternative, -vs, -compare      ← 品牌词不需要对比

品类/功能Campaign:
  (不加额外否定词，让流量自然进来)
  或仅加: -nayno                    ← 防止品牌词流量混入（如果品牌已单独建Campaign）

礼品场景Campaign:
  -cheap, -free, -diy              ← 礼品组要保证一定品质
  -for men, -for boys              ← 如果产品面向女性
  -corporate, -business             ← 如果不是企业礼品
  -under $5                        ← 如果产品$9，$5以下的价格词不相关

购买决策Campaign:
  -review, -vs, -compare, -alternative ← 购买阶段不需要对比词
  -used, -second hand, -rental
```

### 第三层：广告组级否定词

```
规则: 按广告组的具体主题进一步过滤

示例（旅行首饰盒产品）:

组: Travel-Jewelry-Case-Core
  -large, -big, -huge, -oversized     ← 我们卖的是compact
  -wooden, -leather, -acrylic          ← 材质不符
  -for men                             ← 受众不符

组: Graduation-Gifts
  -for men, -for dad, -for boyfriend   ← 受众不符
  -over $50, -luxury, -premium         ← 价格定位不符
  -under $5                            ← 与产品价格不符

组: Brand-Exact
  -review, -vs, -compare               ← 不需要对比
  -cheap, -discount                    ← 品牌词需要保护品牌形象

组: Buy-Now
  -review, -vs, -compare, -alternative
  -used, -second hand, -rental
```

---

## 三、否定关键词自检

```
□ 每个否定词都能回答"搜这个词的人不会买这个产品"
□ 没有误杀高价值流量（如礼品组不加-review）
□ 没有品类不相关的否定词（如首饰盒不加-ingredients）
□ 三层架构完整（账户级 + 系列级 + 组级）
□ 否定词格式正确（以-开头，多词组用引号包裹）
```
