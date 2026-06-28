---
name: kado-discovery-patterns
description: Kado listDir and byFrontmatter query recipes, caching patterns, and error handling. Load when making Kado discovery calls outside of inbox-triage.py. (Write, compose, and upload operations → kado-write-patterns.)
user-invocable: false
---
# Kado Discovery Patterns
# version: 0.1.1

## Listing Files

Write a small script to `tomo-tmp/list_dir.py` then run it:

```python
# tomo-tmp/list_dir.py
import sys, json
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient
client = KadoClient()
files = client.list_dir('100 Inbox/', depth=1)
for f in files:
    print(f"{f['type']:5} {f['path']}")
```

```bash
python3 tomo-tmp/list_dir.py
```

## Querying by Frontmatter

Write a script to `tomo-tmp/query_fm.py` then run it:

```python
# tomo-tmp/query_fm.py
import sys, json
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient
client = KadoClient()
hits = client.search_by_frontmatter('tomo.state=pending-approval', path_prefix='100 Inbox/')
print(json.dumps(hits, indent=2))
```

```bash
python3 tomo-tmp/query_fm.py
```

byFrontmatter is strict equality only. No wildcards, no partial matching.

To query multiple states, make separate calls and merge — write one script, run it:

```python
# tomo-tmp/query_multi.py
import sys, json
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient
client = KadoClient()
pending_approval = client.search_by_frontmatter('tomo.state=pending-approval', path_prefix='100 Inbox/')
pending_accept = client.search_by_frontmatter('tomo.state=pending-accept', path_prefix='100 Inbox/')
captured = client.search_by_frontmatter('tomo.state=captured', path_prefix='100 Inbox/')
all_hits = pending_approval + pending_accept + captured
print(json.dumps(all_hits, indent=2))
```

```bash
python3 tomo-tmp/query_multi.py
```

## Reading Note Content

Write a script to `tomo-tmp/read_note.py` then run it:

```python
# tomo-tmp/read_note.py
import sys
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient
client = KadoClient()
result = client.read_note('100 Inbox/note.md')
print(result['content'][:500])
```

```bash
python3 tomo-tmp/read_note.py
```

## Error Handling

```python
import sys
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient, KadoError, KadoConnectionError

try:
    client = KadoClient()
except KadoConnectionError:
    print("Kado unreachable", file=sys.stderr)
    sys.exit(1)

try:
    result = client.read_note(path)
except KadoError as e:
    print(f"kado-read failed for {path}: {e}", file=sys.stderr)
    # Skip and continue — don't abort the batch
```

## Caching Pattern

When reading multiple docs, cache bodies locally to avoid repeat Kado calls:
```python
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient

client = KadoClient()
cache_dir = Path("tomo-tmp/inbox-cache")
cache_dir.mkdir(parents=True, exist_ok=True)
manifest = {}

for hit in hits:
    result = client.read_note(hit["path"])
    filename = hit["path"].rsplit("/", 1)[-1]
    (cache_dir / filename).write_text(result["content"])
    manifest[filename] = {
        "vault_path": hit["path"],
        "checksum": "sha256:" + hashlib.sha256(result["content"].encode()).hexdigest(),
    }

(cache_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
```
