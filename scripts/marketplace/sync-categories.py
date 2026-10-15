"""Generate the browser copy from the canonical domain registry; --check detects drift."""
from pathlib import Path
import argparse
import json

root = Path(__file__).resolve().parents[2]
source = root / 'packages/py/trustlens-core/src/trustlens/core/catalogue/categories.json'
target = root / 'packages/constants/src/marketplace-data.json'
content = json.dumps(json.loads(source.read_text(encoding='utf-8')), ensure_ascii=False, separators=(',', ':')) + '\n'
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
if args.check:
    if not target.exists() or target.read_text(encoding='utf-8') != content:
        raise SystemExit('Category registry drift. Run scripts/marketplace/sync-categories.py')
    print('CATEGORY_REGISTRY=PASS')
else:
    target.write_text(content, encoding='utf-8')
