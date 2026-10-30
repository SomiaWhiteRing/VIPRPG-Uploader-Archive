"""Advance one checkpointed Wayback mirror-index batch, respecting retry delays."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import http.client

from audit_thread_uploads import fetch


root = Path('local/thread-audit')
work = root / 'recovery'
checkpoint_path = work / 'resume-index.json'
checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8'))
now = datetime.now(timezone.utc)
due = checkpoint.get('retry_after_utc') if checkpoint.get('status') == 'deferred' else checkpoint.get('next_index_after_utc')
if due and now < datetime.fromisoformat(due):
    print(json.dumps({'status': 'waiting_retry_time', 'retry_after_utc': due}))
    raise SystemExit()

providers = {
    'read2ch': 'read2ch.com/r/news4vip/*',
    'desktop-jp': 'desktop2ch.jp/news4vip/*',
    'desktop-org': 'desktop2ch.org/news4vip/*',
    'desktop-tv': 'desktop2ch.tv/news4vip/*',
    '2chnull': '2chnull.info/r/news4vip/*',
    '2bangai': '2bangai.net/read/*',
    'log2ch': 'log2ch.net/read.php/news4vip/*',
    '2chlog': '2chlog.net/test/read.cgi/news4vip/*',
    '2ch-hork': '2ch.hork.info/res/*',
    'unkar-read': 'unkar.org/read/*',
    'old-logsoku-subdomain': '2ch.logsoku.com/*',
    'dat2ch': '*.dat2ch.net/*',
    'rawdat-2chdays': '*.2chdays.net/*',
    'legacy-log9': '*.log9.info/*',
}
lookup_method = checkpoint.get('lookup_method', 'content-200')
if lookup_method not in ('content-200', 'redirects-revisits'):
    raise ValueError('Unknown lookup method')
if lookup_method == 'redirects-revisits':
    # A zero 200-status result can still have canonical redirects or revisit records.
    providers = {
        'original-2ch': 'hayabusa.2ch.net/test/read.cgi/news4vip/*',
        'original-5ch': 'hayabusa.5ch.net/test/read.cgi/news4vip/*',
        'logsoku-r': 'logsoku.com/r/news4vip/*',
        'logsoku-thread': 'logsoku.com/thread/hayabusa.2ch.net/news4vip/*',
        'unkar-r': 'unkar.org/r/news4vip/*',
        **providers,
    }
    order = ['original-2ch', 'original-5ch', 'read2ch', 'logsoku-r', 'logsoku-thread', 'unkar-r',
             'desktop-tv', 'desktop-jp', 'desktop-org', '2chnull', '2bangai',
             'log2ch', '2chlog', '2ch-hork', 'unkar-read', 'old-logsoku-subdomain', 'dat2ch', 'rawdat-2chdays', 'legacy-log9']
    providers = {key: providers[key] for key in order}
    ledger_path = work / 'batch-lookups-redirects-revisits.json'
    cache_prefix = 'cdx-non200-batch-'
    status_filter = 'statuscode:(?:3[0-9]{2}|-)'
else:
    ledger_path = work / 'batch-lookups-more-mirrors.json'
    cache_prefix = 'cdx-batch-'
    status_filter = 'statuscode:200'
preferred = checkpoint.get('next_stage')
if preferred in providers:
    providers = {preferred: providers[preferred], **{key: value for key, value in providers.items() if key != preferred}}
ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else []
pending_ids = sorted(t['id'] for p in (root / 'threads').glob('*.json')
                     if (t := json.loads(p.read_text(encoding='utf-8')))['board'] == 'news4vip'
                     and t['coverage'] in ('unavailable', 'partial'))
item = next((x for x in ledger if x['label'] == checkpoint.get('stage') and x.get('status') != 200), None)
if item is None:
    for provider, base in providers.items():
        completed = {i for x in ledger if x['label'].rsplit('-', 1)[0] == provider and x.get('status') == 200 for i in x['ids']}
        candidates = [i for i in pending_ids if i not in completed]
        if not candidates:
            continue
        batch = 1 + max((int(x['label'].rsplit('-', 1)[1]) for x in ledger
                         if x['label'].rsplit('-', 1)[0] == provider), default=0)
        ids = candidates[:500]
        params = [
            ('url', base), ('output', 'json'), ('filter', status_filter),
            ('filter', 'original:.*/news4vip/.*'),
            ('filter', 'original:.*(?:' + '|'.join(ids) + ').*'),
            ('fl', 'timestamp,original,statuscode,length')]
        if lookup_method == 'content-200':
            params.append(('collapse', 'digest'))
        query = 'https://web.archive.org/cdx/search/cdx?' + urllib.parse.urlencode(params)
        item = {'label': f'{provider}-{batch}', 'ids': ids, 'query_url': query, 'lookup_method': lookup_method}
        ledger.append(item)
        break
if item is None:
    checkpoint.update(status='planned_mirrors_indexed', checked_at=now.isoformat(), runner='scripts/lookup_thread_mirror_batch.py')
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'planned_mirrors_indexed', 'remaining_threads': len(pending_ids)}))
    raise SystemExit()

checkpoint.update(stage=item['label'], status='querying', checked_at=now.isoformat(), runner='scripts/lookup_thread_mirror_batch.py')
checkpoint.update(lookup_method=lookup_method, lookup_ledger_path=str(ledger_path), lookup_cache_prefix=cache_prefix)
checkpoint.pop('captures', None)
checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
attempt = {'at': now.isoformat()}
try:
    raw, resolved = fetch(item['query_url'])
    rows = json.loads(raw)
    if rows and rows[0] != ['timestamp', 'original', 'statuscode', 'length']:
        raise ValueError('Unexpected CDX fields')
    (work / (cache_prefix + item['label'] + '.json')).write_bytes(raw)
    item.update(status=200, captures=max(0, len(rows) - 1), checked_at=now.isoformat())
    item.pop('error', None)
    for row in rows[1:]:
        snapshot = dict(zip(rows[0], row))
        if lookup_method == 'redirects-revisits':
            snapshot['capture_kind'] = 'redirect_or_revisit'
        match = re.search(r'/news4vip/(?:dat/|zip/)?(\d+)', snapshot['original'])
        if not match or match[1] not in item['ids']:
            continue
        thread_id = match[1]
        path = work / f'news4vip-{thread_id}-original.json'
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
        else:
            record = {'id': thread_id, 'board': 'news4vip', 'title': '', 'original': snapshot['original'],
                      'snapshots': [], 'fetches': [], 'query_url': 'batch:' + item['label']}
        if snapshot not in record['snapshots']:
            record['snapshots'].append(snapshot)
        if record.get('status') != 'recovered':
            record['status'] = 'snapshots_found'
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    attempt.update(status=200, captures=item['captures'])
    checkpoint.update(status='index_complete', captures=item['captures'], checked_at=datetime.now(timezone.utc).isoformat())
    checkpoint.update(last_index_stage=item['label'], last_index_captures=item['captures'])
    # The heartbeat runs every 15 minutes; avoid accumulating the HTTP response time as scheduling drift.
    # Successful queries retain a five-minute minimum gap; errors and 429s still defer at least 15 minutes.
    checkpoint['next_index_after_utc'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    checkpoint.pop('retry_after_utc', None)
    checkpoint.pop('error', None)
except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
    status = getattr(error, 'code', None)
    delay = 15 * 60
    if status == 429 and error.headers.get('Retry-After', '').isdigit():
        delay = max(delay, int(error.headers['Retry-After']))
    item.update(status=status, error=str(error))
    attempt.update(status=status, error=str(error))
    checkpoint.update(status='deferred', error=str(error), http_status=status,
                      retry_after_utc=(datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat())
item.setdefault('attempt_history', []).append(attempt)
ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: checkpoint.get(k) for k in ['stage', 'lookup_method', 'status', 'captures', 'retry_after_utc', 'error']}, ensure_ascii=False))
