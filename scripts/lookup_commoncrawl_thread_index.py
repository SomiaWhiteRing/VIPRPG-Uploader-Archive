"""Find missing VIPRPG threads in public Common Crawl CDXJ blocks via HTTP ranges."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re

import requests


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--collection', default='CC-MAIN-2018-51')
parser.add_argument('--prefix', default='com,logsoku)/r/2ch.net/news4vip/13')
parser.add_argument('--label', default='logsoku-news4vip-13')
parser.add_argument('--proxy', default='http://127.0.0.1:7897')
args = parser.parse_args()
if not (re.fullmatch(r'CC-MAIN-\d{4}-\d{2}', args.collection) or args.collection == 'CC-MAIN-2012') or not re.fullmatch(r'[a-z0-9_-]+', args.label):
    raise ValueError('Invalid collection or output label')
root = Path('local/thread-audit')
work = root / 'recovery/commoncrawl' / args.collection
work.mkdir(parents=True, exist_ok=True)
base = f'https://data.commoncrawl.org/cc-index/collections/{args.collection}/indexes/'
session = requests.Session()
session.headers['User-Agent'] = 'VIPRPG-Thread-Archive/1.0 (personal archival research)'
if args.proxy:
    session.proxies = {'http': args.proxy, 'https': args.proxy}


def read_range(name, start, end):
    cache = work / f'{name}-{start}-{end}.bin'
    metadata = cache.with_suffix('.json')
    if cache.exists() and metadata.exists():
        return cache.read_bytes(), json.loads(metadata.read_text(encoding='utf-8'))['total']
    with session.get(base + name, headers={'Range': f'bytes={start}-{end}'}, timeout=25, stream=True) as response:
        response.raise_for_status()
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
        if response.status_code != 206 or not match or (int(match[1]), int(match[2])) != (start, end):
            raise ValueError('Server did not return the requested index range')
        raw = response.content
        if len(raw) != end - start + 1:
            raise ValueError('Incomplete index range')
        cache.write_bytes(raw)
        metadata.write_text(json.dumps({'url': base + name, 'start': start, 'end': end, 'total': int(match[3])}) + '\n', encoding='utf-8')
        return raw, int(match[3])


result = {'collection': args.collection, 'prefix': args.prefix, 'checked_at': datetime.now(timezone.utc).isoformat()}
try:
    _, size = read_range('cluster.idx', 0, 2047)
    prefix = args.prefix.encode('ascii')
    low, high = 0, size
    while high - low > 8192:
        middle = (low + high) // 2
        raw, _ = read_range('cluster.idx', middle, min(middle + 8191, size - 1))
        first = raw.find(b'\n') + 1
        line = raw[first:].split(b'\n', 1)[0]
        if line.split(b' ', 1)[0] < prefix:
            low = middle + first + len(line) + 1
        else:
            high = middle + first
    start = max(0, low - 8192)
    raw, _ = read_range('cluster.idx', start, min(high + 65536, size - 1))
    lines = raw.split(b'\n')
    if start:
        lines = lines[1:]
    if not raw.endswith(b'\n'):
        lines = lines[:-1]
    selected, previous, closed = [], None, False
    for line in lines:
        if not line:
            continue
        key = line.split(b' ', 1)[0]
        if key.startswith(prefix):
            if previous and not selected:
                selected.append(previous)
            selected.append(line)
        elif key > prefix:
            if not selected and previous:
                selected.append(previous)
            closed = True
            break
        else:
            previous = line
    (work / (args.label + '-selected.idx')).write_bytes(b'\n'.join(selected) + b'\n')
    wanted = {t['id'] for p in (root / 'threads').glob('*.json')
              if (t := json.loads(p.read_text(encoding='utf-8')))['coverage'] in ('partial', 'unavailable')}
    hits = []
    prefix_records = 0
    for line in selected:
        fields = line.decode('utf-8').split('\t')
        name, offset, length = fields[1], int(fields[2]), int(fields[3])
        if not re.fullmatch(r'cdx-\d+\.gz', name):
            raise ValueError('Unsupported CDXJ block name')
        compressed, _ = read_range(name, offset, offset + length - 1)
        for record in gzip.decompress(compressed).decode('utf-8').splitlines():
            surt, timestamp, value = record.split(' ', 2)
            if not surt.startswith(args.prefix):
                continue
            prefix_records += 1
            data = json.loads(value)
            url = data.get('url', '')
            match = (re.search(r'/news4vip/(?:dat/|zip/)?(\d+)', url) or
                     re.search(r'viprpg\.org(?::\d+)?/(?:archive/)?(?:dat/|dat2html/html/)(\d+)', url) or
                     re.search(r'viprpg\.org(?::\d+)?/(?:archive/)?dat[^#]*[?&](?:dat|q)=(\d+)', url))
            if match and match[1] in wanted:
                hits.append({'thread_id': match[1], 'timestamp': timestamp, 'surt': surt, **data})
    (work / (args.label + '-hits.json')).write_text(json.dumps(hits, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result.update(status='index_prefix_checked' if closed else 'partial_index_window',
                  prefix_closed=closed, index_blocks=len(selected), prefix_index_records=prefix_records, matching_records=len(hits),
                  matching_threads=len({h['thread_id'] for h in hits}),
                  successful_records=sum(str(h.get('status')) == '200' for h in hits),
                  cluster_search_low=low, cluster_search_high=high)
except (requests.RequestException, OSError, ValueError, EOFError) as error:
    result.update(status='request_or_index_error', error=str(error))
finally:
    session.close()
(work / (args.label + '-lookup.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
