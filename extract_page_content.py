"""
获取并保存浏览器页面内容
"""

import subprocess


def run_qqbrowser_command(command: str) -> str:
    """运行 QQBrowserSkill 命令"""
    qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
    
    try:
        full_command = f'& "{qqbrowser_path}" {command}'
        result = subprocess.run(
            ['powershell', '-Command', full_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=60
        )
        return result.stdout
    except Exception as e:
        print(f"错误: {e}")
        return ""


def main():
    print("正在获取浏览器页面内容...")
    
    # 获取页面快照
    output = run_qqbrowser_command('browser_snapshot')
    
    if output:
        # 保存到文件
        with open('page_content.txt', 'w', encoding='utf-8') as f:
            f.write(output)
        
        print(f"页面内容已保存到 page_content.txt")
        print(f"内容长度: {len(output)} 字符")
        print(f"\n前500个字符:")
        print(output[:500])
    else:
        print("获取页面内容失败")


if __name__ == "__main__":
    main()
