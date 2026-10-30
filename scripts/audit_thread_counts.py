"""Compare directory, chronology and retained page counts; reparse cached responses."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import shutil

from bs4 import BeautifulSoup

from audit_thread_uploads import parse_posts, parse_archive_responses, text, write_csv


root = Path('local/thread-audit')
destination = root / 'count-audit'
destination.mkdir(exist_ok=True)
coverage = json.loads((root / 'coverage.json').read_text(encoding='utf-8'))
threads = {(t['board'], t['id']): json.loads((root / 'threads' / f"{t['board']}-{t['id']}.json").read_text(encoding='utf-8'))
           for t in coverage}
for name in ['coverage.json', 'summary.json']:
    backup = destination / ('before-' + name)
    if not backup.exists():
        shutil.copyfile(root / name, backup)
initial = {(t['board'], t['id']): t for t in json.loads((destination / 'before-coverage.json').read_text(encoding='utf-8'))}

chrono = {}
soup = BeautifulSoup((root / 'chrono.html').read_bytes().decode('cp932', 'replace'), 'html.parser')
for row in soup.find_all('tr'):
    cells = row.find_all('td', recursive=False)
    if len(cells) < 6:
        continue
    for anchor in cells[4].find_all('a', href=True):
        match = re.search(r'/test/read.cgi/([^/]+)/(\d+)', anchor['href'])
        if not match:
            continue
        count = cells[5].get_text(strip=True)
        chrono[(match[1], match[2])] = {
            'count': int(count) if count.isdigit() else None,
            'notes': ' '.join(cell.get_text(' ', strip=True) for cell in cells[8:] if cell.get_text(strip=True)),
        }


def page_counts(source):
    soup = BeautifulSoup(source, 'html.parser')
    found = []
    for node in soup.select('.metastats, .pagestats, .reslist, #thread-menu'):
        label = node.get_text(' ', strip=True)
        for pattern in [r'(\d+)\s*コメント', r'(?:\(|\[)\s*(\d+)\s*res\s*(?:\)|\])', r'全\s*(\d+)\s*レス']:
            for match in re.finditer(pattern, label, re.I):
                entry = {'value': int(match[1]), 'label': match[0], 'location': node.get('id') or ' '.join(node.get('class', []))}
                if entry not in found:
                    found.append(entry)
    for match in re.finditer(r'<font\b[^>]*>\s*総レス数\s*<b[^>]*>\s*(\d+)\s*</b>', source, re.I):
        found.append({'value': int(match[1]), 'label': text(match[0]), 'location': 'total_response_footer'})
    if soup.select('table.article[id^="kiji_"]'):
        for node in soup.select('div.title'):
            match = re.search(r'\((\d+)\)\s*$', node.get_text(' ', strip=True))
            if match:
                entry = {'value': int(match[1]), 'label': match[0], 'location': 'desktop2ch_thread_title'}
                if entry not in found:
                    found.append(entry)
    return found


pages = []
public_dat_html = root / 'recovery/public-dat/viprpg-dat-html-crosschecks.json'
if public_dat_html.exists():
    for record in json.loads(public_dat_html.read_text(encoding='utf-8')):
        if record.get('status') == 200:
            pages.append({'key': ('news4vip', record['id']), 'path': Path(record['cache']),
                          'url': record['resolved_url'], 'kind': 'public_dat_html_crosscheck'})
for key, t in threads.items():
    if t['coverage'] == 'partial' or t.get('source_format') == 'dat':
        source_path = Path(t['raw_source_path']) if t.get('raw_source_path') else root / 'threads' / f'{key[0]}-{key[1]}.html.gz'
        pages.append({'key': key, 'path': source_path, 'url': t['source_url'], 'kind': 'selected_thread_source'})
for ledger_path in (root / 'recovery').glob('news4vip-*-original.json'):
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    fetched = {}
    for item in ledger.get('fetches', []):
        match = re.search(r'/web/(\d+)', item['url'])
        if match and item.get('status') == 200:
            fetched[match[1]] = item.get('resolved', item['url'])
    for timestamp, url in fetched.items():
        path = root / 'recovery' / f"news4vip-{ledger['id']}-original-{timestamp}.html.gz"
        if path.exists():
            pages.append({'key': ('news4vip', ledger['id']), 'path': path, 'url': url, 'kind': 'archived_response'})
for meta_path in (root / 'recovery/mirror-probes').glob('*.json'):
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    path = meta_path.with_suffix('.html.gz')
    if path.exists():
        pages.append({'key': ('news4vip', meta['thread_id']), 'path': path,
                      'url': meta.get('resolved_url', meta['requested_url']), 'kind': 'mirror_probe'})

audit = []
prior_summary = destination / 'summary.json'
repairs = json.loads(prior_summary.read_text(encoding='utf-8')).get('repairs', []) if prior_summary.exists() else []
cache_posts = {}
seen = set()
embedded_pages = {}
for item in pages:
    path = item['path']
    page_key = (path, item['key'])
    if page_key in seen:
        continue
    seen.add(page_key)
    with gzip.open(path, 'rb') as source:
        raw = source.read()
    if raw.startswith(b'\x1f\x8b'):
        raw = gzip.decompress(raw)
    is_embedded = threads.get(item['key'], {}).get('source_format') in ('embedded_numbered_dat', 'embedded_comment_json') and item['kind'] == 'selected_thread_source'
    if is_embedded:
        if path not in embedded_pages:
            mapping_path = threads[item['key']].get('parent_mapping_path')
            parents = json.loads(Path(mapping_path).read_text(encoding='utf-8'))['mappings'] if mapping_path else None
            embedded_pages[path] = parse_archive_responses(raw, parents)
        grouped, embedded_structure = embedded_pages[path]
        posts, encoding = grouped.get(item['key'][1], []), embedded_structure['encoding']
    else:
        posts, encoding = parse_posts(raw)
    source = raw.decode(encoding, 'replace')
    declared = page_counts(source)
    title_match = re.search(r'<title>(.*?)</title>', source, re.I | re.S)
    title = text(title_match[1]) if title_match else ''
    body_nodes = len(re.findall(r'<dd\b', source, re.I))
    container_ids = re.findall(r'\bdata-id="(\d+)"', source, re.I)
    read2ch_ids = re.findall(r'<div\b[^>]*\bid="r(\d+)"[^>]*>', source, re.I)
    desktop_ids = re.findall(r'<table\b[^>]*\bid="kiji_(\d+)"[^>]*>', source, re.I)
    source_rejections = ([record for record in embedded_structure.get('rejected_source_records', [])
                          if record['thread_id'] == item['key'][1]] if is_embedded else [])
    if is_embedded:
        structure_count = embedded_structure.get('raw_thread_floor_counts', embedded_structure['thread_floor_counts']).get(item['key'][1], 0)
        structure_kind = ('embedded comment JSON mapped by original game/thread evidence'
                          if embedded_structure.get('source_format') == 'embedded_comment_json'
                          else 'embedded JSON numbered DAT records mapped by game/thread links')
        declared = []
    elif raw.splitlines() and all(line.count(b'<>') >= 4 for line in raw.splitlines()):
        structure_count, structure_kind = len(raw.splitlines()), 'DAT line records (including deleted placeholders)'
        title = posts[0]['dat_title']
    elif container_ids:
        structure_count, structure_kind = len(set(container_ids)), 'data-id containers'
    elif read2ch_ids:
        structure_count, structure_kind = len(set(read2ch_ids)), 'READ2CH r-number containers'
    elif desktop_ids:
        structure_count, structure_kind = len(set(desktop_ids)), 'desktop2ch kiji-number tables'
    elif re.search(r'<td\b[^>]*class="msg"', source, re.I):
        structure_count, structure_kind = len(re.findall(r'<td\b[^>]*class="msg"', source, re.I)), 'VIPRPG DAT2HTML message cells'
    else:
        structure_count, structure_kind = body_nodes, 'dd tags (may include non-post metadata)'
    numbers = {p['number'] for p in posts}
    empty_bodies = sum(not p['text'].strip() for p in posts)
    deleted_bodies = sum(p['text'].strip() in ('あぼーん', 'うふ～ん', 'うふ〜ん') for p in posts)
    positive = [c['value'] for c in declared if c['value'] > 0]
    if posts and empty_bodies == len(posts):
        status = 'post_headers_but_no_body_text'
    elif posts and empty_bodies + deleted_bodies == len(posts):
        status = 'only_deleted_body_placeholders'
    elif posts and source_rejections:
        status = 'source_records_rejected_or_truncated'
    elif posts:
        status = ('page_count_exceeds_extracted' if positive and max(positive) > len(numbers) else
                  'page_count_matches_extracted' if positive and max(positive) == len(numbers) else 'posts_present')
    elif 'unkarは閉鎖しました' in source:
        status = 'closure_notice_no_posts'
    elif 'datが存在しません' in source:
        status = 'missing_dat_error_no_posts'
    elif positive:
        status = 'positive_page_count_but_zero_parsed'
    elif any(c['value'] == 0 for c in declared):
        status = 'explicit_zero_page_count'
    else:
        status = 'no_posts_and_no_thread_counter'
    thread = threads.get(item['key'])
    audit.append({'board': item['key'][0], 'id': item['key'][1], 'page_kind': item['kind'],
                  'directory_count': thread['expected'] if thread else None,
                  'chronology_count': chrono.get(item['key'], {}).get('count'),
                  'page_title': title, 'page_counts': declared, 'parsed_posts': len(posts),
                  'nonempty_bodies': len(posts) - empty_bodies, 'empty_bodies': empty_bodies,
                  'deleted_placeholder_bodies': deleted_bodies,
                  'source_record_rejections': len(source_rejections),
                  'rejected_source_floors': sorted({record['number'] for record in source_rejections if record['number'] is not None}),
                  'min_floor': min(numbers) if numbers else None, 'max_floor': max(numbers) if numbers else None,
                  'structure_count': structure_count, 'structure_kind': structure_kind, 'result': status,
                  'url': item['url'], 'cache_path': str(path.resolve())})
    if not posts or not thread or item['kind'] == 'mirror_probe' or is_embedded:
        continue
    key = item['key']
    if key not in cache_posts:
        old_path = root / 'threads' / f'{key[0]}-{key[1]}.posts.json.gz'
        if old_path.exists():
            with gzip.open(old_path, 'rt', encoding='utf-8') as source_file:
                existing = json.load(source_file)
            for post in existing:
                post.setdefault('source_url', thread['source_url'])
            cache_posts[key] = {p['number']: p for p in existing}
        else:
            cache_posts[key] = {}
    merged = cache_posts[key]
    added = numbers - merged.keys()
    if not added:
        continue
    for post in posts:
        if post['number'] in added:
            merged[post['number']] = {**post, 'source_url': item['url']}
    name = f'{key[0]}-{key[1]}'
    backup_dir = destination / 'previous-thread-data'
    backup_dir.mkdir(exist_ok=True)
    for suffix in ['.json', '.html.gz', '.posts.json.gz']:
        old_path = root / 'threads' / (name + suffix)
        if old_path.exists() and not (backup_dir / (name + suffix)).exists():
            shutil.copyfile(old_path, backup_dir / (name + suffix))
    maximum = max(merged)
    thread.update(post_count=len(merged), max_post=maximum, encoding=encoding, source_url=item['url'],
                  fetched_at=datetime.now(timezone.utc).isoformat())
    thread['coverage'] = ('partial' if len(merged) != maximum or (thread['expected'] and maximum < thread['expected'])
                          else 'count_matches' if thread['expected'] else 'expected_unknown')
    thread['attempts'].append({'url': item['url'], 'status': 200, 'posts': len(posts), 'operation': 'count_audit_cache_reparse'})
    with gzip.open(root / 'threads' / (name + '.html.gz'), 'wb') as out:
        out.write(raw)
    with gzip.open(root / 'threads' / (name + '.posts.json.gz'), 'wt', encoding='utf-8') as out:
        json.dump(sorted(merged.values(), key=lambda p: p['number']), out, ensure_ascii=False, separators=(',', ':'))
    (root / 'threads' / (name + '.json')).write_text(json.dumps(thread, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    repairs.append({'id': key[1], 'title': thread['title'], 'added_floors': len(added), 'page_counts': declared,
                    'saved_after': len(merged), 'directory_count': thread['expected'], 'coverage': thread['coverage'], 'source': item['url']})

per_thread = []
pages_by_thread = defaultdict(list)
for item in audit:
    pages_by_thread[(item['board'], item['id'])].append(item)
for key, before in initial.items():
    if before['coverage'] not in ('partial', 'unavailable'):
        continue
    current = threads[key]
    per_thread.append({'board': key[0], 'id': key[1], 'title': current['title'], 'directory_count': current['expected'],
                       'chronology_count': chrono.get(key, {}).get('count'), 'saved_before': before['post_count'],
                       'saved_after': current['post_count'], 'coverage_after': current['coverage'],
                       'cached_page_results': dict(Counter(p['result'] for p in pages_by_thread[key])),
                       'chronology_notes': chrono.get(key, {}).get('notes', '')})
summary = {'audited_missing_threads': len(per_thread),
           'directory_positive_counts': sum(bool(t['directory_count'] and t['directory_count'] > 0) for t in per_thread),
           'directory_zero_counts': sum(t['directory_count'] == 0 for t in per_thread),
           'directory_unknown_counts': sum(t['directory_count'] is None for t in per_thread),
           'cached_pages_audited': len(audit), 'page_results': dict(Counter(p['result'] for p in audit)), 'repairs': repairs}
write_csv(destination / 'pages.csv', audit, list(audit[0]))
write_csv(destination / 'threads.csv', per_thread, list(per_thread[0]))
(destination / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
