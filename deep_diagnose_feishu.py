# -*- coding: utf-8 -*-
"""
深度诊断飞书 Offers 表数据质量
检查维度：
1. 价格货币问题（是否混入了非USD商品）
2. 投放链接有效性（格式检查、域名检查）
3. 同一ASIN重复记录
4. 商品归属问题（商品名与商户名是否匹配）
5. 价格=0 或异常值的比例
"""

import requests
import json
import time
from collections import Counter, defaultdict

# 飞书配置
APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

def get_token():
    resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                         json={'app_id': APP_ID, 'app_secret': APP_SECRET})
    return resp.json()['tenant_access_token']

import requests.adapters
session = requests.Session()
retry_strategy = requests.adapters.Retry(
    total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

def get_token():
    for attempt in range(3):
        try:
            resp = session.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                                json={'app_id': APP_ID, 'app_secret': APP_SECRET}, timeout=30)
            return resp.json()['tenant_access_token']
        except Exception as e:
            print(f"  token获取失败(尝试{attempt+1}/3): {e}")
            time.sleep(2)
    raise Exception("无法获取飞书token")

token = get_token()
headers = {'Authorization': 'Bearer ' + token}

print("=" * 80)
print("飞书 Offers 表深度数据质量诊断")
print("=" * 80)

# 1. 读取所有记录
print("\n[1] 读取全部记录...")
all_records = []
page_token = None
total_from_api = 0

while True:
    params = {'page_size': 500, 'automatic_fields': False}
    if page_token:
        params['page_token'] = page_token
    for attempt in range(3):
        try:
            resp = session.get(
                f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
                headers=headers, params=params, timeout=60)
            data = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                print(f"  请求失败(尝试{attempt+1}/3): {e}, 重试...")
                time.sleep(3)
                token = get_token()
                headers = {'Authorization': 'Bearer ' + token}
            else:
                raise
    items = data.get('data', {}).get('items', [])
    total_from_api = data.get('data', {}).get('total', 0)
    all_records.extend(items)
    page_token = data.get('data', {}).get('page_token')
    if not page_token or not items:
        break
    # 刷新 token
    if len(all_records) % 3000 == 0:
        token = get_token()
        headers = {'Authorization': 'Bearer ' + token}

print(f"  API 总记录数: {total_from_api}")
print(f"  实际读取: {len(all_records)}")

# 2. 字段统计
print("\n[2] 各字段填充率统计...")
field_stats = defaultdict(lambda: {'filled': 0, 'empty': 0, 'zero': 0})
field_names = set()

for rec in all_records:
    fields = rec.get('fields', {})
    for k, v in fields.items():
        field_names.add(k)
        if v is None or v == '' or v == [] or v == 0:
            field_stats[k]['empty'] += 1
        else:
            field_stats[k]['filled'] += 1
            # 检查数字 0
            try:
                if float(v) == 0:
                    field_stats[k]['zero'] += 1
            except (ValueError, TypeError):
                pass

print(f"  字段总数: {len(field_names)}")
for k in sorted(field_names):
    s = field_stats[k]
    total = s['filled'] + s['empty']
    fill_rate = s['filled'] / total * 100 if total > 0 else 0
    zero_info = f", 其中=0: {s['zero']}" if s['zero'] > 0 else ""
    print(f"  {k}: 填充{s['filled']}/{total} ({fill_rate:.1f}%){zero_info}")

# 3. 价格分析
print("\n[3] 价格分析...")
prices = []
price_zero = 0
price_negative = 0
price_very_low = 0  # < 1
price_very_high = 0  # > 1000

for rec in all_records:
    fields = rec.get('fields', {})
    price_raw = fields.get('价格', None)
    if price_raw is None:
        continue
    try:
        price = float(price_raw)
        if price == 0:
            price_zero += 1
        elif price < 0:
            price_negative += 1
        elif price < 1:
            price_very_low += 1
        elif price > 1000:
            price_very_high += 1
        prices.append(price)
    except (ValueError, TypeError):
        pass

if prices:
    prices.sort()
    print(f"  有效价格数: {len(prices)}")
    print(f"  价格=0: {price_zero}")
    print(f"  价格<0: {price_negative}")
    print(f"  价格<1: {price_very_low}")
    print(f"  价格>1000: {price_very_high}")
    print(f"  最低: ${min(prices):.2f}")
    print(f"  最高: ${max(prices):.2f}")
    print(f"  中位数: ${prices[len(prices)//2]:.2f}")
    print(f"  平均: ${sum(prices)/len(prices):.2f}")
    
    # 价格区间分布
    bins = [0, 5, 10, 20, 50, 100, 200, 500, 1000, float('inf')]
    bin_labels = ['$0', '$1-5', '$5-10', '$10-20', '$20-50', '$50-100', '$100-200', '$200-500', '$500-1000', '$1000+']
    bin_counts = [0] * len(bin_labels)
    for p in prices:
        for i in range(len(bins)-1):
            if bins[i] <= p < bins[i+1]:
                bin_counts[i] += 1
                break
    
    print("\n  价格区间分布:")
    for label, count in zip(bin_labels, bin_counts):
        pct = count / len(prices) * 100
        bar = '#' * int(pct)
        print(f"    {label:>10}: {count:>5} ({pct:5.1f}%) {bar}")

# 4. 投放链接分析
print("\n[4] 投放链接分析...")
has_url = 0
no_url = 0
url_domains = Counter()
url_patterns = Counter()  # 检查链接格式

for rec in all_records:
    fields = rec.get('fields', {})
    url = fields.get('Tracking URL', None)
    if url is None:
        no_url += 1
    elif isinstance(url, str) and url.strip():
        has_url += 1
        # 解析域名
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            url_domains[domain] += 1
            # 检查路径模式
            path = parsed.path
            if 'openurlproduct' in path:
                url_patterns['openurlproduct (标准商品链接)'] += 1
            elif 'openurl' in path:
                url_patterns['openurl (通用链接)'] += 1
            else:
                url_patterns['其他路径'] += 1
        except:
            url_patterns['无法解析'] += 1
    elif isinstance(url, list):
        if url and url[0] and str(url[0]).strip():
            has_url += 1
            url_str = str(url[0])
            from urllib.parse import urlparse
            try:
                parsed = urlparse(url_str)
                url_domains[parsed.netloc] += 1
            except:
                pass
        else:
            no_url += 1
    else:
        no_url += 1

print(f"  有投放链接: {has_url} ({has_url/len(all_records)*100:.1f}%)")
print(f"  无投放链接: {no_url} ({no_url/len(all_records)*100:.1f}%)")

if url_domains:
    print("\n  链接域名分布:")
    for domain, count in url_domains.most_common():
        print(f"    {domain}: {count}")

if url_patterns:
    print("\n  链接格式分布:")
    for pattern, count in url_patterns.most_common():
        print(f"    {pattern}: {count}")

# 5. 同一ASIN重复记录
print("\n[5] 同一 ASIN 重复记录分析...")
asin_records = defaultdict(list)
for rec in all_records:
    fields = rec.get('fields', {})
    asin_raw = fields.get('ASIN', None)
    if asin_raw is None:
        continue
    if isinstance(asin_raw, list):
        asin = (asin_raw[0] if asin_raw else '') or ''
    else:
        asin = str(asin_raw)
    asin = asin.strip()
    if asin:
        asin_records[asin].append(rec)

unique_asins = len(asin_records)
dup_asins = {asin: recs for asin, recs in asin_records.items() if len(recs) > 1}
print(f"  唯一 ASIN 数: {unique_asins}")
print(f"  有重复记录的 ASIN: {len(dup_asins)}")

if dup_asins:
    # 按重复次数排序
    sorted_dups = sorted(dup_asins.items(), key=lambda x: -len(x[1]))
    print(f"\n  重复次数 TOP 10:")
    for asin, recs in sorted_dups[:10]:
        # 收集这些重复记录的关键差异
        merchants = set()
        prices_set = set()
        urls = set()
        for r in recs:
            f = r.get('fields', {})
            m = f.get('商户名称', '')
            if isinstance(m, list):
                m = m[0] if m else ''
            merchants.add(str(m)[:30] if m else '空')
            p = f.get('价格', '')
            if isinstance(p, list):
                p = p[0] if p else ''
            prices_set.add(str(p) if p else '空')
            u = f.get('Tracking URL', '')
            if isinstance(u, list):
                u = u[0] if u else ''
            urls.add('有' if u and str(u).strip() else '无')
        
        print(f"    {asin}: {len(recs)}条 | 商户: {merchants} | 价格: {prices_set} | 链接: {urls}")

# 6. 推广状态分布
print("\n[6] 推广状态分布...")
status_count = Counter()
for rec in all_records:
    fields = rec.get('fields', {})
    status = fields.get('推广状态', None)
    if status is None:
        status_count['空(未标注)'] += 1
    elif isinstance(status, list):
        s = status[0] if status else '空(空数组)'
        status_count[str(s)] += 1
    elif isinstance(status, str):
        status_count[status] += 1
    else:
        status_count[str(status)] += 1

for s, c in status_count.most_common():
    print(f"  {s}: {c} ({c/len(all_records)*100:.1f}%)")

# 7. 商品名与商户名匹配检查（抽样）
print("\n[7] 商品名 vs 商户名匹配检查（抽样100条有链接记录）...")
mismatch_count = 0
match_count = 0
checked = 0

for rec in all_records:
    if checked >= 100:
        break
    fields = rec.get('fields', {})
    url = fields.get('Tracking URL', '')
    if isinstance(url, list):
        url = url[0] if url else ''
    if not url or not str(url).strip():
        continue
    
    merchant = fields.get('商户名称', '')
    if isinstance(merchant, list):
        merchant = merchant[0] if merchant else ''
    merchant = str(merchant).strip().upper()
    
    name = fields.get('商品名称', '')
    if isinstance(name, list):
        name = name[0] if name else ''
    name = str(name).strip()
    
    if not merchant or not name:
        continue
    
    checked += 1
    # 简单匹配：商品名中是否包含商户名的关键部分
    # 去掉常见后缀
    merchant_words = merchant.replace('US', '').replace('INC', '').replace('LLC', '').replace('LTD', '').strip()
    merchant_parts = [w for w in merchant_words.split() if len(w) > 2]
    
    found = False
    name_upper = name.upper()
    for part in merchant_parts:
        if part in name_upper:
            found = True
            break
    
    if found:
        match_count += 1
    else:
        mismatch_count += 1
        if mismatch_count <= 5:
            print(f"    不匹配: ASIN={fields.get('ASIN','')} | 商户={merchant} | 商品名={name[:60]}")

print(f"\n  检查了 {checked} 条有链接记录")
print(f"  匹配: {match_count} ({match_count/checked*100:.1f}%)" if checked > 0 else "  无数据")
print(f"  不匹配: {mismatch_count} ({mismatch_count/checked*100:.1f}%)" if checked > 0 else "")

# 8. 采集来源分析
print("\n[8] 采集时间分布...")
times = Counter()
for rec in all_records:
    fields = rec.get('fields', {})
    ct = fields.get('采集时间', '')
    if isinstance(ct, list):
        ct = ct[0] if ct else ''
    ct = str(ct).strip()
    if ct:
        # 只取日期部分
        date_part = ct[:10] if len(ct) >= 10 else ct
        times[date_part] += 1

for date, count in sorted(times.items()):
    print(f"  {date}: {count} 条")

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)
