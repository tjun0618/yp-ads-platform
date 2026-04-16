import json
from pathlib import Path
s = json.loads(Path('output/download_state.json').read_text('utf-8'))
completed = set(s.get('completed_mids', []))
failed = set(s.get('failed_mids', []))
products = s.get('products', [])
print('completed_mids:', len(completed))
print('failed_mids:', len(failed))
print('total products:', len(products))
print('last_updated:', s.get('last_updated'))
