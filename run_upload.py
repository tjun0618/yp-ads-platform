import subprocess
import sys

# 运行上传脚本
result = subprocess.run(
    [sys.executable, 'quick_upload_to_feishu.py'],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='ignore',
    cwd='.'
)

print("=== 标准输出 ===")
print(result.stdout)
print("\n=== 标准错误 ===")
print(result.stderr)
print(f"\n=== 退出码: {result.returncode} ===")
