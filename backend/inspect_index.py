import sys, os
sys.path.append(os.path.abspath('.'))
from services.vector_db import load_vector_store

RAW_DIR = os.path.join('data', 'raw_pdfs')
files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.pdf')]
print('raw_pdfs_count', len(files))

db = load_vector_store()
if not db:
    print('NO_DB')
    sys.exit(0)

store = getattr(db, 'docstore', None)
if store is None:
    print('NO_DOCSTORE')
    sys.exit(0)

items = getattr(store, '_dict', None)
if items is None:
    print('DOCSTORE_NO_DICT')
    sys.exit(0)

counts = {}
for k, v in items.items():
    meta = None
    if v is None:
        continue
    if hasattr(v, 'metadata'):
        meta = v.metadata
    elif isinstance(v, dict):
        meta = v.get('metadata', {})
    else:
        meta = getattr(v, '_metadata', {})
    sf = (meta.get('source_file') or '').strip()
    if sf:
        counts[sf] = counts.get(sf, 0) + 1

print('indexed_files_count', len(counts))
for fname, c in counts.items():
    print(f'{fname}: {c}')

missing = [f for f in files if f not in counts]
print('missing_files:', missing)

# Print files present in policies.json but not in docstore
try:
    import json
    with open(os.path.join('data', 'policies.json'), 'r', encoding='utf-8') as fh:
        policies = json.load(fh)
    policy_files = [p['file'] for p in policies]
    missing_policy = [f for f in policy_files if f not in counts]
    print('policy_files_missing_in_index:', missing_policy)
except Exception as e:
    print('policies.json read error', e)
