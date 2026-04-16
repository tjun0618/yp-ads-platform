"""Count and compare routes between old and new ads_manager"""
import sys, re
sys.path.insert(0, '.')

# 1. Count routes in NEW app
from ads_manager import app
new_routes = []
for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
    methods = sorted(r.methods - {'HEAD', 'OPTIONS'})
    new_routes.append((r.rule, methods, r.endpoint))

print(f"=== NEW APP: {len(new_routes)} routes ===")
for rule, methods, endpoint in new_routes:
    print(f"  {rule:45s} {','.join(methods):8s} -> {endpoint}")

# 2. Count routes in ORIGINAL backup
with open('ads_manager.py.bak', 'r', encoding='utf-8') as f:
    content = f.read()

old_routes = re.findall(r"@app\.route\(['\"]([^'\"]+)['\"]", content)
print(f"\n=== ORIGINAL FILE: {len(old_routes)} @app.route decorators ===")
for r in sorted(old_routes):
    print(f"  {r}")

# 3. Compare
new_paths = {r[0] for r in new_routes}
old_paths = set(old_routes)
missing = old_paths - new_paths
extra = new_paths - old_paths

print(f"\n=== COMPARISON ===")
print(f"Old: {len(old_paths)}, New: {len(new_paths)}")
if missing:
    print(f"MISSING in new app ({len(missing)}):")
    for m in sorted(missing):
        print(f"  - {m}")
if extra:
    print(f"EXTRA in new app ({len(extra)}):")
    for e in sorted(extra):
        print(f"  + {e}")
if not missing and not extra:
    print("ALL ROUTES MATCH!")
