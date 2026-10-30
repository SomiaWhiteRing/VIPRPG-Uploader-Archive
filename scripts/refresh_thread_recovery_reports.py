"""Refresh uploader findings and the recovery ledger from saved thread evidence."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path

from audit_thread_uploads import report, write_csv


root = Path('local/thread-audit')
work = root / 'recovery'
directory = json.loads((root / 'directory.json').read_text(encoding='utf-8'))
report(root, Path('D:/VIPRPG-Rescue/uploaderjp-202611'), Path('src/data/catalog.json'), directory)
coverage = json.loads((root / 'coverage.json').read_text(encoding='utf-8'))
baseline = json.loads((work / 'before-coverage.json').read_text(encoding='utf-8'))
initial = {(t['board'], t['id']) for t in baseline if not t['post_count']}
recovered = [t for t in coverage if (t['board'], t['id']) in initial and t['post_count']]
remaining = []
for thread in coverage:
    if thread['coverage'] not in ('unavailable', 'partial', 'not_fetched'):
        continue
    key = f"{thread['board']}-{thread['id']}"
    numbers = set()
    if thread['post_count']:
        with gzip.open(root / 'threads' / (key + '.posts.json.gz'), 'rt', encoding='utf-8') as source:
            numbers = {p['number'] for p in json.load(source)}
    upper = thread['expected'] or thread['max_post']
    ranges = []
    for number in range(1, upper + 1):
        if number in numbers:
            continue
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1][1] = number
        else:
            ranges.append([number, number])
    path = work / (key + '-original.json')
    evidence = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    remaining.append({'board': thread['board'], 'id': thread['id'], 'title': thread['title'],
                      'status': thread['coverage'], 'expected': thread['expected'], 'saved_posts': thread['post_count'],
                      'saved_max_floor': thread['max_post'],
                      'missing_floors': ','.join(str(a) if a == b else f'{a}-{b}' for a, b in ranges) if upper else 'unknown',
                      'indexed_snapshots': len(evidence.get('snapshots', [])),
                      'source_url': thread['source_url'], 'original_url': thread['url']})
write_csv(work / 'recovered-threads.csv', recovered,
          ['board', 'id', 'title', 'coverage', 'expected', 'post_count', 'max_post', 'source_url'])
write_csv(work / 'remaining-threads.csv', remaining,
          ['board', 'id', 'title', 'status', 'expected', 'saved_posts', 'saved_max_floor', 'missing_floors',
           'indexed_snapshots', 'source_url', 'original_url'])
summary_path = work / 'recovery-summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
summary.update(updated_at=datetime.now(timezone.utc).isoformat(), initial_missing_threads=len(initial),
               new_complete_threads=sum(t['coverage'] not in ('partial', 'unavailable', 'not_fetched') for t in recovered),
               new_partial_threads=sum(t['coverage'] == 'partial' for t in recovered),
               new_floor_records=sum(t['post_count'] for t in recovered), remaining=len(remaining),
               remaining_states=dict(Counter(t['status'] for t in remaining)))
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
