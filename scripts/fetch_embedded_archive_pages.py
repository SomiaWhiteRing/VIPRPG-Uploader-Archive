"""Fetch a small checkpointed batch of the proven public embedded-DAT archive pages."""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gzip
import json
import os
from pathlib import Path
import time

import requests

from audit_thread_uploads import parse_archive_responses


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--limit', type=int, default=4)
parser.add_argument('--queue', type=Path, default=Path('local/thread-audit/recovery/public-dat/embedded-root-source-queue.json'))
args = parser.parse_args()
work = Path('local/thread-audit/recovery/public-dat')
queue_path = args.queue
queue = json.loads(queue_path.read_text(encoding='utf-8'))
if queue.get('strategy_deferred_reason'):
    print(json.dumps({'status': 'deferred_for_strategy', 'reason': queue['strategy_deferred_reason']}))
    raise SystemExit(0)
parent_mapping_path = queue.get('parent_mapping_path')
parents = json.loads(Path(parent_mapping_path).read_text(encoding='utf-8'))['mappings'] if parent_mapping_path else None
now = datetime.now(timezone.utc)
if queue.get('next_request_after_utc') and now < datetime.fromisoformat(queue['next_request_after_utc']):
    print(json.dumps({'status': 'deferred_backoff', 'retry_after': queue['next_request_after_utc']}))
    raise SystemExit(0)
shared_backoff_path = work / 'embedded-http-backoff.json'
if shared_backoff_path.exists():
    shared = json.loads(shared_backoff_path.read_text(encoding='utf-8'))
    if now < datetime.fromisoformat(shared['next_request_after_utc']):
        print(json.dumps({'status': 'deferred_shared_archive_backoff', 'retry_after': shared['next_request_after_utc']}))
        raise SystemExit(0)
manifest_path = work / 'embedded-posts-manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
stamp = now.strftime('%Y%m%dT%H%M%SZ')
batch_manifest = work / ('embedded-batch-' + stamp + '.json')
log_path = work / ('embedded-fetch-' + stamp + '.json')
batch = []
events = []
print(json.dumps({'pid': os.getpid(), 'batch_manifest': str(batch_manifest)}), flush=True)
for source in queue['sources']:
    if len(events) >= args.limit:
        break
    if source['status'] not in ('pending', 'request_error'):
        continue
    if source.get('retry_after_utc') and datetime.now(timezone.utc) < datetime.fromisoformat(source['retry_after_utc']):
        continue
    event = {'timestamp': source['timestamp'], 'url': source['source_url'],
             'checked_at': datetime.now(timezone.utc).isoformat()}
    cache = Path(source['cache'])
    try:
        response = requests.get(source['source_url'],
                                headers={'User-Agent': 'VIPRPG-Thread-Archive/1.0 (personal archival research)'},
                                timeout=25)
        event.update(http_status=response.status_code, resolved_url=response.url, bytes=len(response.content))
        if not response.ok:
            error_cache = cache.with_name(cache.stem + '-' + stamp + '-http-error.gz')
            with gzip.open(error_cache, 'wb') as out:
                out.write(response.content)
            event['error_cache'] = str(error_cache)
        response.raise_for_status()
        with gzip.open(cache, 'wb') as out:
            out.write(response.content)
        groups, structure = parse_archive_responses(response.content, parents)
        event.update(structure=structure, mapped_threads=len(groups), cache=str(cache))
        source.update(http_status=response.status_code, resolved_url=response.url, fetched_at=event['checked_at'])
        if not groups and not structure.get('unmapped_comment_rows'):
            if structure['variables'] and not structure['mapped_games'] and not structure['numbered_dat_rows']:
                source.update(status='parsed_empty_page', diagnostic='Explicit empty numbered-DAT JSON and game table in this HTML; not evidence that the thread has no other archived body')
                event['status'] = 'parsed_empty_page'
            else:
                source.update(status='format_review', diagnostic='HTTP200 retained but no mapped numbered DAT records; review structure before absence claims')
                event['status'] = 'format_review'
        else:
            entry = {'cache': str(cache), 'source_url': response.url}
            if parent_mapping_path:
                entry['parent_mapping_path'] = parent_mapping_path
            if not any(x['cache'] == entry['cache'] for x in manifest):
                manifest.append(entry)
            batch.append(entry)
            source['status'] = 'fetched_pending_merge'
            event['status'] = 'fetched_pending_merge'
    except requests.RequestException as error:
        retry = datetime.now(timezone.utc) + timedelta(minutes=20)
        retry_after = error.response.headers.get('Retry-After', '') if error.response is not None else ''
        if retry_after.isdigit():
            retry = max(retry, datetime.now(timezone.utc) + timedelta(seconds=int(retry_after)))
        elif retry_after:
            try:
                retry = max(retry, parsedate_to_datetime(retry_after).astimezone(timezone.utc))
            except (ValueError, TypeError):
                event['unparsed_retry_after'] = retry_after
        source.update(status='request_error', error=str(error), retry_after_utc=retry.isoformat())
        queue['next_request_after_utc'] = retry.isoformat()
        if error.response is None or error.response.status_code in (429, 500, 502, 503, 504):
            shared_backoff_path.write_text(json.dumps({
                'next_request_after_utc': retry.isoformat(), 'source_url': source['source_url'],
                'reason': str(error), 'fetch_ledger': str(log_path),
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        event.update(status='request_error_not_absence', error=str(error), retry_after_utc=retry.isoformat())
    except (ValueError, UnicodeError) as error:
        source.update(status='parse_review', error=str(error))
        event.update(status='parse_review_not_absence', error=str(error), cache=str(cache))
    events.append(event)
    source['last_fetch_event'] = str(log_path)
    queue.update(updated_at=datetime.now(timezone.utc).isoformat(),
                 completed=sum(s['status'] == 'fetched_and_merged' for s in queue['sources']),
                 pending=sum(s['status'] in ('pending', 'request_error') for s in queue['sources']))
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    batch_manifest.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    log_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(event, ensure_ascii=False), flush=True)
    if event['status'] not in ('fetched_pending_merge', 'parsed_empty_page'):
        break
    time.sleep(4)
print(json.dumps({'batch_manifest': str(batch_manifest), 'fetched_sources': len(batch),
                  'fetch_ledger': str(log_path), 'status': events[-1]['status'] if events else 'no_due_sources'}, ensure_ascii=False))
