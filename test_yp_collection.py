"""
YP 平台商家数据采集测试
先测试能否成功获取 YP 商家数据
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.yp_api.merchant_collector import YPMerchantCollector


def test_yp_collection():
    """测试 YP 商家数据采集"""

    print("=" * 60)
    print("YP 平台商家数据采集测试")
    print("=" * 60)
    print()

    # 初始化采集器
    collector = YPMerchantCollector(
        api_base="https://yeahpromos.com",
        api_endpoint="/index/getadvert/getadvert",
        rate_limit=10,  # 每分钟请求限制
        timeout=30,  # 请求超时时间(秒)
        retry_times=3  # 重试次数
    )

    try:
        print("[1/2] 开始采集商家数据...")
        print()

        # 获取商家数据
        merchants = collector.get_all_merchants(
            start_page=1,
            max_pages=1  # 先只测试第一页
        )

        print()
        print(f"✅ 成功采集 {len(merchants)} 个商家")
        print()

        if merchants:
            print("[2/2] 显示前 3 个商家信息:")
            print()

            for i, merchant in enumerate(merchants[:3], 1):
                print(f"商家 {i}:")
                print(f"  ID: {merchant.merchant_id}")
                print(f"  名称: {merchant.merchant_name}")
                print(f"  佣金率: {merchant.commission_rate}")
                print(f"  追踪链接: {merchant.tracking_link[:60]}...")
                print()

            # 保存数据到文件
            output_dir = project_root / "output"
            output_dir.mkdir(exist_ok=True)

            output_file = output_dir / f"merchants_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in merchants], f, indent=2, ensure_ascii=False)

            print(f"✅ 数据已保存到: {output_file}")
            print()
        else:
            print("⚠️  未采集到商家数据")
            print("可能原因:")
            print("  1. YP API 需要登录认证")
            print("  2. API 端点不正确")
            print("  3. 网络连接问题")
            print()

        return len(merchants) > 0

    except Exception as e:
        print(f"❌ 采集失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        collector.close()


if __name__ == "__main__":
    success = test_yp_collection()

    print("=" * 60)
    if success:
        print("✅ 测试通过！可以继续下一步")
    else:
        print("❌ 测试失败，请检查错误信息")
    print("=" * 60)
