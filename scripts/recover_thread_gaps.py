"""Look up unavailable threads in Wayback and retain per-source recovery evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import http.client
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse

from audit_thread_uploads import fetch, parse_posts


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path('local/thread-audit'))
parser.add_argument('--workers', type=int, default=1)
parser.add_argument('--retry-failed', action='store_true')
parser.add_argument('--replay-cached', action='store_true')
parser.add_argument('--thread-id', action='append', help='Restrict recovery to newly discovered thread IDs; repeat for multiple threads')
parser.add_argument('--mirror', choices=['original', 'logsoku', 'unkar'], default='original')
args = parser.parse_args()
root = args.root
work = root / 'recovery'
work.mkdir(exist_ok=True)
stopped = threading.Event()
replay_stopped = threading.Event()
threads = []
for path in (root / 'threads').glob('*.json'):
    meta = json.loads(path.read_text(encoding='utf-8'))
    if (not meta['post_count'] or meta['coverage'] == 'partial') and (not args.thread_id or meta['id'] in args.thread_id):
        threads.append(meta)


def recover(thread):
    key = f"{thread['board']}-{thread['id']}"
    destination = work / (key + '-' + args.mirror + '.json')
    previous = None
    if destination.exists():
        previous = json.loads(destination.read_text(encoding='utf-8'))
        if args.replay_cached and previous.get('snapshots'):
            pass
        elif not args.retry_failed or previous['status'] != 'index_request_failed':
            return previous
    if args.replay_cached and not (previous and previous.get('snapshots')):
        return {'id': thread['id'], 'status': 'no_cached_snapshots'}
    if stopped.is_set():
        return {'id': thread['id'], 'status': 'deferred_rate_limit'}
    original = next((u for u in thread.get('fallback_urls', []) if '.5ch.net/' in u), thread['url'].replace('.io/', '.net/'))
    if args.mirror == 'logsoku':
        original = f"http://www.logsoku.com/r/2ch.net/{thread['board']}/{thread['id']}"
    elif args.mirror == 'unkar':
        original = f"http://unkar.org/r/{thread['board']}/{thread['id']}"
    original = original.rstrip('/')
    query = 'https://web.archive.org/cdx/search/cdx?' + urllib.parse.urlencode({
        'url': original + '*', 'output': 'json', 'filter': 'statuscode:200',
        'fl': 'timestamp,original,statuscode,length', 'collapse': 'digest',
    })
    result = {'id': thread['id'], 'board': thread['board'], 'title': thread['title'],
              'original': original, 'query_url': query, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'snapshots': [], 'fetches': []}
    if args.replay_cached:
        result = previous
    else:
        try:
            raw, resolved = fetch(query)
            rows = json.loads(raw)
            result['snapshots'] = [dict(zip(rows[0], row)) for row in rows[1:]] if rows else []
            result['status'] = 'snapshots_found' if result['snapshots'] else 'no_capture_returned'
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
            result.update(status='index_request_failed', error=str(error), http_status=getattr(error, 'code', None))
            if getattr(error, 'code', None) == 429:
                stopped.set()
                result['retry_after'] = error.headers.get('Retry-After')
    merged = {}
    if thread['post_count']:
        with gzip.open(root / 'threads' / (key + '.posts.json.gz'), 'rt', encoding='utf-8') as source:
            merged = {p['number']: p for p in json.load(source)}
    best_raw, best_url, encoding = None, None, None
    candidates = sorted(result['snapshots'], key=lambda s: (int(s.get('length') or 0), s['timestamp']), reverse=True)
    for snapshot in candidates:
        if replay_stopped.is_set():
            result['replay_deferred_rate_limit'] = True
            break
        url = f"https://web.archive.org/web/{snapshot['timestamp']}/{snapshot['original']}"
        if any(f.get('url') == url and f.get('status') == 200 and f.get('post_count', 0) > 0 for f in result['fetches']):
            continue
        entry = {'url': url}
        try:
            cache_path = work / (key + '-' + args.mirror + '-' + snapshot['timestamp'] + '.html.gz')
            if cache_path.exists():
                with gzip.open(cache_path, 'rb') as source:
                    raw = source.read()
                if raw.startswith(b'\x1f\x8b'):
                    raw = gzip.decompress(raw)
                resolved = url
            else:
                raw, resolved = fetch(url)
            posts, enc = parse_posts(raw)
            entry.update(status=200, resolved=resolved, post_count=len(posts))
            with gzip.open(cache_path, 'wb') as out:
                out.write(raw)
            if posts:
                for post in posts:
                    post['source_url'] = resolved
                    merged[post['number']] = post
                best_raw, best_url, encoding = raw, resolved, enc
                expected = thread['expected']
                maximum = max(merged)
                if min(merged) == 1 and len(merged) == maximum and (not expected or maximum >= expected):
                    result['fetches'].append(entry)
                    break
        except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
            entry.update(status=getattr(error, 'code', None), error=str(error))
            if getattr(error, 'code', None) == 429:
                replay_stopped.set()
                entry['retry_after'] = error.headers.get('Retry-After')
        result['fetches'].append(entry)
        time.sleep(0.5)
    if best_raw:
        maximum = max(merged)
        thread.update(post_count=len(merged), max_post=maximum, source_url=best_url, encoding=encoding,
                      fetched_at=datetime.now(timezone.utc).isoformat())
        thread['coverage'] = ('partial' if len(merged) != maximum or (thread['expected'] and maximum < thread['expected'])
                              else 'count_matches' if thread['expected'] else 'expected_unknown')
        thread['attempts'].extend(result['fetches'])
        with gzip.open(root / 'threads' / (key + '.html.gz'), 'wb') as out:
            out.write(best_raw)
        with gzip.open(root / 'threads' / (key + '.posts.json.gz'), 'wt', encoding='utf-8') as out:
            json.dump(sorted(merged.values(), key=lambda p: p['number']), out, ensure_ascii=False, separators=(',', ':'))
        (root / 'threads' / (key + '.json')).write_text(json.dumps(thread, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result.update(status='recovered', post_count=len(merged), coverage=thread['coverage'])
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    time.sleep(1)
    return result


from collections import Counter
counts = Counter()
results = []
with ThreadPoolExecutor(max_workers=args.workers) as pool:
    futures = [pool.submit(recover, thread) for thread in threads]
    for i, future in enumerate(as_completed(futures), 1):
        result = future.result()
        results.append(result)
        counts[result['status']] += 1
        if i % 25 == 0 or i == len(threads) or result['status'] == 'recovered':
            print(json.dumps({'checked': i, 'total': len(threads), 'mirror': args.mirror, 'states': dict(counts)}, ensure_ascii=False), flush=True)
(work / ('lookup-' + args.mirror + '.json')).write_text(json.dumps({'counts': dict(counts), 'threads': results}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
