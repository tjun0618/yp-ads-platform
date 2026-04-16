import os, threading, time, re
os.chdir(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu')
import ads_manager
t = threading.Thread(target=ads_manager.load_us_merchants)
t.start(); t.join(3)
print('merchants:', len(ads_manager._us_merchant_names))
app = ads_manager.app
app.config['TESTING'] = True
with app.test_client() as c:
    # 默认排序（newest = id DESC）
    t0 = time.time()
    r = c.get('/')
    print(f'GET / (newest) -> {r.status_code}  {time.time()-t0:.2f}s')
    if r.status_code == 200:
        data = r.data.decode('utf-8','replace')
        nums = re.findall('class="stat-num">([^<]+)<', data)
        asins = re.findall('ASIN: <code>([^<]+)</code>', data)
        print(f'stats: {nums}  ASINs: {asins[:3]}')
    else:
        print(data[:400])

    # 佣金排序（慢，仅测试）
    t0 = time.time()
    r2 = c.get('/?sort=commission_desc')
    print(f'GET / (commission_desc) -> {r2.status_code}  {time.time()-t0:.2f}s')
