"""Merge verified public DAT caches; preserve each original and the previous thread evidence."""
import argparse
from datetime import datetime, timezone
import gzip
import html
import json
from pathlib import Path
import re
import shutil

from audit_thread_uploads import parse_posts


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ledger', type=Path, default=Path('local/thread-audit/recovery/public-dat/viprpg-dat-fetches.json'))
args = parser.parse_args()
root = Path('local/thread-audit')
work = root / 'recovery/public-dat'
results = []
for record in json.loads(args.ledger.read_text(encoding='utf-8')):
    if not record.get('cache') or record.get('error'):
        continue
    raw_path = Path(record['cache'])
    raw = gzip.open(raw_path, 'rb').read()
    lines = raw.splitlines()
    if not lines or not all(line.count(b'<>') >= 4 for line in lines):
        results.append({'id': record['id'], 'status': 'not_dat', 'cache': str(raw_path)})
        continue
    key = 'news4vip-' + record['id']
    meta_path = root / 'threads' / (key + '.json')
    thread = json.loads(meta_path.read_text(encoding='utf-8'))
    posts, encoding = parse_posts(raw)
    assert record['id'] in record['original'], 'DAT source/thread ID mismatch'
    assert html.unescape(posts[0]['dat_title']).strip() == thread['title'].strip(), 'DAT title mismatch'
    assert len(posts) == len(lines) and [p['number'] for p in posts] == list(range(1, len(lines) + 1))
    date_match = re.search(r'(\d{4})/(\d{2})/(\d{2})', posts[0]['dateid'])
    assert date_match, 'Missing first-post date'
    start = datetime.fromtimestamp(int(record['id']), timezone.utc)
    assert abs((datetime(*map(int, date_match.groups()), tzinfo=timezone.utc) - start).total_seconds()) < 86400
    source_url = record.get('resolved_url') or record['url']
    posts_path = root / 'threads' / (key + '.posts.json.gz')
    previous = json.load(gzip.open(posts_path, 'rt', encoding='utf-8')) if posts_path.exists() else []
    merged = {p['number']: {**p, 'source_url': p.get('source_url') or thread['source_url']} for p in previous}
    added = {p['number'] for p in posts} - merged.keys()
    if not added:
        results.append({'id': record['id'], 'status': 'already_merged', 'posts': len(posts), 'added_floors': 0})
        continue
    backup = work / 'previous-thread-data'
    backup.mkdir(exist_ok=True)
    for suffix in ['.json', '.html.gz', '.posts.json.gz']:
        path = root / 'threads' / (key + suffix)
        if path.exists() and not (backup / path.name).exists():
            shutil.copyfile(path, backup / path.name)
    for post in posts:
        if post['number'] in added:
            merged[post['number']] = {**post, 'source_url': source_url}
    maximum = max(merged)
    thread.update(post_count=len(merged), max_post=maximum, encoding=encoding, source_url=source_url,
                  raw_source_path=str(raw_path), source_format='dat', fetched_at=datetime.now(timezone.utc).isoformat())
    thread['coverage'] = ('partial' if len(merged) != maximum or (thread['expected'] and maximum < thread['expected'])
                          else 'count_matches' if thread['expected'] else 'expected_unknown')
    thread['attempts'].append({'url': source_url, 'status': 200, 'posts': len(posts), 'operation': 'public_dat_cache_merge'})
    with gzip.open(posts_path, 'wt', encoding='utf-8') as out:
        json.dump(sorted(merged.values(), key=lambda p: p['number']), out, ensure_ascii=False, separators=(',', ':'))
    meta_path.write_text(json.dumps(thread, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    results.append({'id': record['id'], 'title': thread['title'], 'status': thread['coverage'],
                    'posts': len(posts), 'added_floors': len(added), 'saved_after': len(merged),
                    'expected': thread['expected'], 'source_url': source_url, 'cache': str(raw_path)})
output = args.ledger.with_name(args.ledger.stem + '-merged.json')
output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results, ensure_ascii=False))
