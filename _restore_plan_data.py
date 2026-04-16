"""
解析截断的 JSON，只提取到完整的部分写入数据库
"""
import mysql.connector, json, re, sys

def parse_partial_json_campaigns(raw_text):
    """从截断的JSON中尽可能提取campaigns数组"""
    # 找到 campaigns 数组开始
    camp_start = raw_text.find('"campaigns"')
    if camp_start < 0:
        return []
    
    # 找到 [ 位置
    bracket_start = raw_text.find('[', camp_start)
    if bracket_start < 0:
        return []
    
    # 逐步提取完整的 campaign 对象
    campaigns = []
    pos = bracket_start + 1
    depth = 0
    current_camp_start = -1
    
    for i in range(pos, len(raw_text)):
        ch = raw_text[i]
        if ch == '{':
            if depth == 0:
                current_camp_start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and current_camp_start >= 0:
                # 尝试解析这个 campaign 对象
                camp_str = raw_text[current_camp_start:i+1]
                try:
                    camp = json.loads(camp_str)
                    campaigns.append(camp)
                    print(f"  Parsed campaign: {camp.get('campaign_name', '?')} with {len(camp.get('ad_groups',[]))} groups")
                except json.JSONDecodeError as e:
                    # 尝试修复
                    try:
                        fixed = re.sub(r',\s*([}\]])', r'\1', camp_str)
                        camp = json.loads(fixed)
                        campaigns.append(camp)
                        print(f"  Fixed campaign: {camp.get('campaign_name', '?')}")
                    except:
                        print(f"  Skip malformed campaign at pos {current_camp_start}")
                current_camp_start = -1
        elif ch == ']' and depth == 0:
            break
    
    return campaigns

# 读取日志文件
log_file = 'logs/ai_raw_20260404_035935.txt'
print(f"Using: {log_file}")

with open(log_file, 'r', encoding='utf-8') as f:
    raw = f.read()

# 提取产品分析
prod_match = re.search(r'"product_analysis"\s*:\s*\{([^}]+)\}', raw, re.DOTALL)
product_analysis = {}
if prod_match:
    try:
        product_analysis = json.loads('{' + prod_match.group(1) + '}')
    except:
        pass

# 提取 profitability
prof_match = re.search(r'"profitability"\s*:\s*\{([^}]+)\}', raw, re.DOTALL)
profitability = {}
if prof_match:
    try:
        profitability = json.loads('{' + prof_match.group(1) + '}')
    except:
        pass

asin = 'B0FX34NS5K'
print(f"ASIN: {asin}")

campaigns = parse_partial_json_campaigns(raw)
print(f"\nTotal campaigns parsed: {len(campaigns)}")

if not campaigns:
    print("No campaigns found!")
    sys.exit(1)

# 写入数据库
conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

cur.execute("SELECT merchant_id, merchant_name FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
plan_row = cur.fetchone()
merchant_id = str(plan_row['merchant_id'] if plan_row else '0')
merchant_name = plan_row['merchant_name'] if plan_row else 'Unknown'

cur.execute("SELECT tracking_url FROM yp_us_products WHERE asin=%s AND tracking_url IS NOT NULL LIMIT 1", (asin,))
row = cur.fetchone()
tracking_url = (row['tracking_url'] if row else None) or f"https://www.amazon.com/dp/{asin}"

# 清理旧数据
cur.execute("SELECT id FROM ads_campaigns WHERE asin=%s", (asin,))
old_camps = cur.fetchall()
for oc in old_camps:
    old_cid = oc['id']
    cur.execute("SELECT id FROM ads_ad_groups WHERE campaign_id=%s", (old_cid,))
    old_groups = cur.fetchall()
    for og in old_groups:
        cur.execute("DELETE FROM ads_ads WHERE ad_group_id=%s", (og['id'],))
    cur.execute("DELETE FROM ads_ad_groups WHERE campaign_id=%s", (old_cid,))
cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))
print(f"Deleted old data")

target_cpa_str = profitability.get('safe_target_cpa', '1.37') or '1.37'
target_cpa_val = float(re.sub(r'[^0-9.]', '', target_cpa_str) or '1.37')

actual_camp_count = 0
actual_group_count = 0
actual_ad_count = 0

for camp_idx, camp in enumerate(campaigns):
    camp_name = camp.get('campaign_name') or f'Campaign {camp_idx+1}'
    budget_pct = camp.get('budget_percentage') or 0
    camp_neg_kws = camp.get('campaign_negative_keywords', [])
    camp_target_cpa_str = camp.get('target_cpa', str(target_cpa_val)) or '0'
    camp_target_cpa = float(re.sub(r'[^0-9.]', '', camp_target_cpa_str) or target_cpa_val)

    cur.execute("""
        INSERT INTO ads_campaigns (
            asin, merchant_id, merchant_name, campaign_name,
            journey_stage, budget_pct, product_price, commission_pct, target_cpa,
            negative_keywords, status, created_at, updated_at
        ) VALUES (%s,%s,%s,%s,'awareness',%s,%s,%s,%s,%s,'draft',NOW(),NOW())
    """, (
        asin, merchant_id, merchant_name, camp_name,
        budget_pct, 12.99, 15.0, camp_target_cpa,
        json.dumps(camp_neg_kws),
    ))
    camp_db_id = cur.lastrowid
    actual_camp_count += 1
    print(f"Campaign {actual_camp_count}: {camp_name}")

    for grp in camp.get('ad_groups', []):
        grp_name = grp.get('ad_group_name') or 'Ad Group'
        kws = grp.get('keywords', [])
        kw_list = []
        for kw in kws:
            mt = kw.get('match_type', '[B]')
            ktype = 'exact' if mt == '[E]' else ('phrase' if mt == '[P]' else 'broad')
            kw_list.append({'kw': kw.get('keyword',''), 'type': ktype})

        cur.execute("""
            INSERT INTO ads_ad_groups (
                campaign_id, asin, ad_group_name,
                keywords, keyword_count, status, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,'draft',NOW(),NOW())
        """, (camp_db_id, asin, grp_name, json.dumps(kw_list), len(kw_list)))
        grp_db_id = cur.lastrowid
        actual_group_count += 1

        headlines_raw = grp.get('headlines', [])
        descriptions_raw = grp.get('descriptions', [])

        headlines_db = [{'text': (h.get('text','') if isinstance(h,dict) else str(h)), 'chars': len(h.get('text','') if isinstance(h,dict) else str(h))} for h in headlines_raw]
        descriptions_db = [{'text': (d.get('text','') if isinstance(d,dict) else str(d)), 'chars': len(d.get('text','') if isinstance(d,dict) else str(d))} for d in descriptions_raw]

        all_chars_valid = all(h['chars'] <= 30 for h in headlines_db) and all(d['chars'] <= 90 for d in descriptions_db)

        cur.execute("""
            INSERT INTO ads_ads (
                ad_group_id, campaign_id, asin, variant,
                headlines, descriptions, sitelinks, callouts,
                structured_snippet, final_url, display_url,
                headline_count, description_count,
                all_chars_valid, status, created_at, updated_at
            ) VALUES (%s,%s,%s,'A',%s,%s,'[]','[]','{}',%s,'amazon.com',%s,%s,%s,'draft',NOW(),NOW())
        """, (
            grp_db_id, camp_db_id, asin,
            json.dumps(headlines_db, ensure_ascii=False),
            json.dumps(descriptions_db, ensure_ascii=False),
            tracking_url,
            len(headlines_db), len(descriptions_db),
            1 if all_chars_valid else 0,
        ))
        actual_ad_count += 1
        print(f"  Group: {grp_name} | {len(kw_list)} kws, {len(headlines_db)} hls, {len(descriptions_db)} descs, valid={all_chars_valid}")

cur.execute("UPDATE ads_plans SET campaign_count=%s, ad_group_count=%s, ad_count=%s WHERE asin=%s",
            (actual_camp_count, actual_group_count, actual_ad_count, asin))

conn.commit()
conn.close()
print(f"\nDone! {actual_camp_count} campaigns, {actual_group_count} groups, {actual_ad_count} ads")
