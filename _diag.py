with open('ads_manager.py','r',encoding='utf-8') as f:
    lines = f.readlines()

# Find routes and index def
for i,l in enumerate(lines):
    stripped = l.strip()
    if "route('/')" in stripped or 'route("/")' in stripped or 'def index' in stripped or 'def product_list' in stripped:
        print(f'Line {i+1}: {l.rstrip()}')
