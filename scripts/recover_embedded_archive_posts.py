"""Restore numbered original posts embedded in old VIPRPG archive pages as JSON."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import re
import shutil
import unicodedata

from audit_thread_uploads import parse_archive_responses


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest', type=Path, required=True, help='JSON list of cache/source_url objects')
parser.add_argument('--queue', type=Path, default=Path('local/thread-audit/recovery/public-dat/embedded-root-source-queue.json'))
args = parser.parse_args()
root = Path('local/thread-audit')
work = root / 'recovery/public-dat'
now = datetime.now(timezone.utc)
results = []
for entry in json.loads(args.manifest.read_text(encoding='utf-8')):
    cache = Path(entry['cache'])
    parent_mapping_path = entry.get('parent_mapping_path')
    parents = json.loads(Path(parent_mapping_path).read_text(encoding='utf-8'))['mappings'] if parent_mapping_path else None
    with gzip.open(cache, 'rb') as source:
        groups, structure = parse_archive_responses(source.read(), parents)
    result = {'cache': str(cache), 'source_url': entry['source_url'], 'structure': structure, 'threads': []}
    for thread_id, posts in groups.items():
        key = 'news4vip-' + thread_id
        meta_path = root / 'threads' / (key + '.json')
        if not meta_path.exists():
            result['threads'].append({'id': thread_id, 'status': 'outside_directory', 'records': len(posts)})
            continue
        thread = json.loads(meta_path.read_text(encoding='utf-8'))
        if thread['coverage'] not in ('partial', 'unavailable', 'not_fetched'):
            result['threads'].append({'id': thread_id, 'status': 'already_complete', 'records': len(posts)})
            continue
        posts_path = root / 'threads' / (key + '.posts.json.gz')
        previous = json.load(gzip.open(posts_path, 'rt', encoding='utf-8')) if posts_path.exists() else []
        merged = {p['number']: {**p, 'source_url': p.get('source_url') or thread['source_url']} for p in previous}
        start = datetime.fromtimestamp(int(thread_id), timezone.utc)
        local_start = start.astimezone(timezone(timedelta(hours=9)))
        end = None
        end_day = re.fullmatch(r'(\d{1,2})/(\d{1,2})', thread.get('end') or '')
        if end_day:
            year = local_start.year + ((int(end_day[1]), int(end_day[2])) < (local_start.month, local_start.day))
            end = datetime(year, int(end_day[1]), int(end_day[2]), tzinfo=local_start.tzinfo) + timedelta(days=1)
        additions = []
        quality_repairs = []
        rejected = []
        for post in posts:
            previous_post = merged.get(post['number'])
            if previous_post is not None:
                if not previous_post.get('source_replacement_character_count'):
                    continue
                if any('\ufffd' in post[field] for field in ('name', 'mail', 'dateid', 'body_html')):
                    continue
                if post['dateid'] != previous_post['dateid'] or post['mail'] != previous_post['mail']:
                    continue
                if unicodedata.normalize('NFKC', post['name']) != unicodedata.normalize('NFKC', previous_post['name']):
                    continue
                damaged, clean = [re.sub(r'\s+', '', unicodedata.normalize('NFKC', p['text']))
                                  for p in (previous_post, post)]
                if not re.fullmatch(re.escape(damaged).replace('\ufffd', '.+?'), clean):
                    continue
            stamp = re.search(r'(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}:\d{2})', post['dateid'])
            when = datetime.strptime(stamp[1] + ' ' + stamp[2], '%Y/%m/%d %H:%M:%S').replace(tzinfo=local_start.tzinfo)
            if when < local_start - timedelta(seconds=60) or (end and when >= end):
                rejected.append({'number': post['number'], 'dateid': post['dateid'], 'reason': 'outside_directory_thread_dates'})
                continue
            restored = {**post, 'source_url': entry['source_url'], 'source_post_url': entry['source_url']}
            if previous_post is not None:
                restored['previous_source_variants'] = previous_post.get('previous_source_variants', []) + [
                    {k: v for k, v in previous_post.items() if k != 'previous_source_variants'}]
                quality_repairs.append(restored)
            else:
                additions.append(restored)
        if not additions and not quality_repairs:
            result['threads'].append({'id': thread_id, 'status': 'no_new_floors', 'records': len(posts), 'rejected': rejected})
            continue
        backup = work / 'embedded-previous-thread-data'
        backup.mkdir(exist_ok=True)
        for suffix in ['.json', '.posts.json.gz', '.html.gz']:
            old = root / 'threads' / (key + suffix)
            if old.exists() and not (backup / old.name).exists():
                shutil.copyfile(old, backup / old.name)
        for post in additions + quality_repairs:
            merged[post['number']] = post
        maximum = max(merged)
        thread.update(post_count=len(merged), max_post=maximum, source_url=entry['source_url'],
                      source_format=structure.get('source_format', 'embedded_numbered_dat'), raw_source_path=str(cache),
                      encoding=structure['encoding'],
                      fetched_at=now.isoformat())
        thread['coverage'] = ('partial' if len(merged) != maximum or (thread['expected'] and maximum < thread['expected'])
                              else 'count_matches' if thread['expected'] else 'expected_unknown')
        thread['attempts'].append({'url': entry['source_url'], 'status': 200, 'posts': len(posts),
                                   'added_floors': len(additions), 'repaired_source_loss_floors': len(quality_repairs),
                                   'operation': 'embedded_numbered_dat_cache_merge'})
        if parent_mapping_path:
            thread['parent_mapping_path'] = parent_mapping_path
            for post in additions + quality_repairs:
                post['parent_mapping_path'] = parent_mapping_path
        with gzip.open(posts_path, 'wt', encoding='utf-8') as out:
            json.dump(sorted(merged.values(), key=lambda p: p['number']), out, ensure_ascii=False, separators=(',', ':'))
        meta_path.write_text(json.dumps(thread, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result['threads'].append({'id': thread_id, 'title': thread['title'], 'status': thread['coverage'],
                                  'records': len(posts), 'added_floors': len(additions),
                                  'floor_numbers': sorted(p['number'] for p in additions),
                                  'repaired_source_loss_floors': sorted(p['number'] for p in quality_repairs),
                                  'saved_after': len(merged), 'expected': thread['expected'], 'rejected': rejected})
    results.append(result)
output = work / ('embedded-posts-recovery-' + now.strftime('%Y%m%dT%H%M%SZ') + '.json')
output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
queue_path = args.queue
if queue_path.exists():
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    processed = {r['cache']: r for r in results}
    for source in queue['sources']:
        if source['cache'] not in processed:
            continue
        added = sum(t.get('added_floors', 0) for t in processed[source['cache']]['threads'])
        repaired = sum(len(t.get('repaired_source_loss_floors', [])) for t in processed[source['cache']]['threads'])
        if source['status'] == 'fetched_and_merged' and not added and not repaired:
            continue
        structure = processed[source['cache']]['structure']
        status = ('partial_parent_mapping' if structure.get('unmapped_comment_rows')
                  else 'partial_source_records' if structure.get('rejected_source_records') else 'fetched_and_merged')
        source.update(status=status, merged_at=now.isoformat(),
                      merge_ledger=output.relative_to(root).as_posix(), last_merge_added_floors=added,
                      last_source_loss_repairs=repaired)
        source['unmapped_tkool_dat_ids'] = processed[source['cache']]['structure'].get('unmapped_tkool_dat_ids', {})
        source['rejected_source_records'] = structure.get('rejected_source_records', [])
    queue.update(updated_at=now.isoformat(),
                 completed=sum(s['status'] == 'fetched_and_merged' for s in queue['sources']),
                 pending=sum(s['status'] in ('pending', 'request_error') for s in queue['sources']))
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'ledger': str(output), 'added_floors': sum(t.get('added_floors', 0) for r in results for t in r['threads']),
                  'repaired_source_loss_floors': sum(len(t.get('repaired_source_loss_floors', [])) for r in results for t in r['threads']),
                  'sources': results}, ensure_ascii=False))
