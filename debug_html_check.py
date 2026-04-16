import urllib.request
r = urllib.request.urlopen('http://localhost:5055/merchant_products?merchant_id=362400')
html = r.read().decode('utf-8')

# 找fetch调用
ft = html.find('fetch(url).then')
with open('debug_html_output.txt', 'w', encoding='utf-8') as f:
    f.write(f"fetch chain ({ft}):\n")
    f.write(html[ft:ft+500] + '\n\n' if ft>=0 else 'NOT FOUND\n\n')
    
    rp = html.find('function renderPager')
    f.write(f"renderPager found: {rp>=0}\n")
    
    sc = html.rfind('</script>')
    f.write(f"last </script> at: {sc}, total len: {len(html)}\n\n")
    
    mid_i = html.find("const mid")
    f.write(f"mid var: {html[mid_i:mid_i+100] if mid_i>=0 else 'NOT FOUND'}\n\n")
    
    # 找所有JS错误点：检查 {{ }} 是否还存在于HTML中
    brace_idx = html.find('{{method')
    f.write(f"{{{{method found at: {brace_idx}\n\n")
    
    # 打印整个script区域
    sc_start = html.rfind('<script>')
    f.write(f"Last script block (sc_start={sc_start}):\n")
    f.write(html[sc_start:sc_start+3000])
    f.write('\n\n...\n')
    
    # 找第一个<script>
    sc1 = html.find('<script>')
    f.write(f"First script block (sc1={sc1}):\n")
    f.write(html[sc1:sc1+1000])

print("Written to debug_html_output.txt")
