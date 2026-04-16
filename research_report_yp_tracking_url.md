# YP (YeahPromos) 投放链接生成机制调研报告

## 核心结论

你在 YP 平台点击 Copy 生成的投放链接 **不是通过 API 直接返回的**，而是需要完成一个先决条件：**先申请加入商户计划，审核通过后才能获得追踪令牌（track token），再与产品 ID 拼接生成投放链接。**

---

## 1. 投放链接的组成结构

你的示例链接：
```
https://yeahpromos.com/index/index/openurlproduct?track=440ddc5f761c3546&pid=477789
```

拆解如下：

| 参数 | 值 | 含义 |
|------|-----|------|
| `track` | `440ddc5f761c3546` | 商户级追踪令牌 (Merchant Tracking Token)，由 YP 平台分配，用于标识是哪个商户的追踪链接 |
| `pid` | `477789` | 产品 ID (Product ID)，对应 YP 平台内部的产品标识 |

YP 平台存在两种投放链接接口：

- `openurlproduct`：产品级深度链接（推荐），格式：`?track={token}&pid={product_id}`
- `openurl`：通用 Offer 级链接，格式：`?track={token}&url={offer_id}/`

---

## 2. 为什么 API 返回的 tracking_url 为空？

我们实际调用了 YP 的 Offer API 和 Merchant API，发现：

**Offer API 返回的数据：**
```json
{
  "product_id": 1350843,
  "asin": "B0GH5JDMK3",
  "tracking_url": "",     // 空字符串！
  "product_status": "Online"
}
```

**Merchant API 返回的数据：**
```json
{
  "mid": 111334,
  "merchant_name": "Farfetch US",
  "tracking_url": null,   // null！
  "track": null,          // 关键字段！
  "is_deeplink": "1",     // 支持深度链接
  "status": "UNAPPLIED"   // 未申请！
}
```

原因很明确：**`track` 字段只有在申请商户计划并被批准后才会被赋值。** 你的 Physician's Choice 品牌（MID: 362247）应该是已经在 YP 网页端申请通过了，所以 UI 上能复制到 `track=440ddc5f761c3546`。

---

## 3. 获取投放链接的完整流程

### 第一步：申请商户计划

在 YP 平台网页端找到目标商户（如 Physician's Choice），点击申请。审核通过后，商户状态从 `UNAPPLIED` 变为 `APPLIED/APPROVED`，`track` 字段会被赋值。

### 第二步：获取 track token

申请通过后，Merchant API 的 `track` 字段将不再是 null，而是一个类似 `440ddc5f761c3546` 的十六进制字符串。

### 第三步：获取 product_id

通过 Offer API 搜索目标商品，获取 `product_id`（对应链接中的 `pid` 参数）。

### 第四步：拼接投放链接

```
https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={product_id}
```

---

## 4. 链接的跳转链路（实际追踪机制）

根据 urlquery.net 的实际扫描，YP 投放链接的完整跳转链路为：

```
1. yeahpromos.com/index/index/openurlproduct?track=xxx&pid=xxx
   ↓ (YP 服务器重定向)
2. track.webgains.com/...  (二级联盟 WebGains 追踪)
   ↓
3. 最终目标页面 (亚马逊商品页)
   带有归因参数: ?wgu=xxx&wgexpiry=xxx&utm_campaign=xxx&cname=xxx
```

YP 平台本身是一个三级联盟（Sub-Affiliate Network），底层通过 **WebGains** 二级联盟进行实际追踪和佣金结算。你拿到的 `track` token 在 YP 服务器端会被转换为 WebGains 的追踪参数。

---

## 5. 关键注意事项

**关于 `pid` 与 `product_id` 的映射**：
你示例中的 `pid=477789` 与 API 返回的 `product_id`（1350843 级别）数值不同，可能存在内部映射。建议在网页端找到 Physician's Choice 的产品后，检查 Copy 链接中的 `pid` 值，与 API 中的 `product_id` 做对比，确认对应关系。

**风险提示**：
根据第三方评测（大数跨境），YP 被标记为三级联盟，存在佣金空间小、拒付率高的问题。有用户反馈 500 美元业绩仅被认可 13.72 美元。建议关注结算数据，如有异常及时与 YP 客服沟通。

---

## 6. 总结

| 问题 | 答案 |
|------|------|
| 投放链接从哪来？ | 需要先申请商户 → 审核通过获得 track token → 与 product_id 拼接 |
| API 能直接获取吗？ | 不能。API 返回的 tracking_url 为空，track 在未申请时为 null |
| track 是什么？ | 商户级追踪令牌，申请通过后 YP 平台自动分配 |
| pid 是什么？ | 产品 ID，对应 API 中的 product_id（可能有内部映射） |
| 链接怎么生成？ | `https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}` |
