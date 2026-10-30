"""Archive the Neocities thread directory and audit uploader references (read-only baseline)."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import gzip
import html
import http.client
import io
import json
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request


DIRECTORY = 'https://viprpg.neocities.org/contents/kako.csv'
URL_RE = re.compile(r'(?:h?ttps?://)?(?:[a-z0-9_-]+\.)*(?:getuploader\.com|uploader\.jp)/[^\s<>"\'\u3000]*', re.I)


def text(fragment):
    fragment = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', fragment, flags=re.S | re.I)
    fragment = re.sub(r'<br\s*/?>', '\n', fragment, flags=re.I)
    return html.unescape(re.sub(r'<[^>]*>', '', fragment)).strip()


def parse_archive_responses(raw, parent_mappings=None):
    """Read automatic archive post data as JSON without executing scripts."""
    from bs4 import BeautifulSoup

    archived_chunked = bool(re.match(rb'^[0-9a-fA-F]+\r\n', raw))
    if archived_chunked:
        chunks = []
        offset = 0
        while True:
            line_end = raw.find(b'\r\n', offset)
            if line_end < 0:
                raise ValueError('Incomplete archived HTTP chunk header')
            size = int(raw[offset:line_end].split(b';', 1)[0], 16)
            if size == 0:
                break
            start = line_end + 2
            if raw[start + size:start + size + 2] != b'\r\n':
                raise ValueError('Incomplete archived HTTP chunk body')
            chunks.append(raw[start:start + size])
            offset = start + size + 2
        raw = b''.join(chunks)
    soup = BeautifulSoup(raw, 'html.parser')
    source = raw.decode(soup.original_encoding or 'cp932')
    comments_match = re.search(r'\bgon\.comments\s*=\s*', source)
    if comments_match:
        comments, _ = json.JSONDecoder().raw_decode(source[comments_match.end():])
        parents = {key: value['thread_id'] for key, value in (parent_mappings or {}).items()}
        zips_match = re.search(r'\bgon\.tkool_zips\s*=\s*', source)
        zips = json.JSONDecoder().raw_decode(source[zips_match.end():])[0] if zips_match else []
        game_parents = {str(item['id']): item['subdir'] for item in zips}
        for game_id, records in comments.items():
            if game_id not in game_parents:
                continue
            thread_id = game_parents[game_id]
            if not re.fullmatch(r'\d{9,10}', thread_id):
                raise ValueError('Invalid original thread subdir in archive ZIP metadata')
            for record in records:
                key = str(record['tkool_dat_id'])
                if key in parents and parents[key] != thread_id:
                    raise ValueError('Conflicting original thread for archive DAT database ID ' + key)
                parents[key] = thread_id
        groups = defaultdict(dict)
        unmapped = Counter()
        for game_id, records in comments.items():
            for record in records:
                key = str(record['tkool_dat_id'])
                if key not in parents:
                    unmapped[key] += 1
                    continue
                thread_id = parents[key]
                number = record['line']
                if not isinstance(number, int) or number < 1 or not re.match(r'\d{4}/\d{2}/\d{2}', record['date']):
                    raise ValueError('Invalid numbered archive comment record')
                if number in groups[thread_id]:
                    post = groups[thread_id][number]
                    if post['raw_comment_record'] != record:
                        raise ValueError(f'Conflicting archive comment records: {thread_id}/{number}')
                    if game_id not in post['archive_game_ids']:
                        post['archive_game_ids'].append(game_id)
                    continue
                groups[thread_id][number] = {
                    'number': number,
                    'header': f"{number} ：{record['name']} [{record['mail']}]：{record['date']}",
                    'text': text(record['body']),
                    'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', record['body'], re.I)],
                    'name': record['name'], 'mail': record['mail'], 'dateid': record['date'],
                    'body_html': record['body'], 'raw_comment_record': record,
                    'archive_game_ids': [game_id],
                }
                replacement_count = sum(record[field].count('\ufffd') for field in ('name', 'mail', 'date', 'body'))
                if replacement_count:
                    groups[thread_id][number]['source_replacement_character_count'] = replacement_count
        return {key: list(posts.values()) for key, posts in groups.items()}, {
            'source_format': 'embedded_comment_json', 'encoding': soup.original_encoding or 'utf-8',
            'archived_http_chunked': archived_chunked, 'mapped_games': len(comments),
            'numbered_dat_rows': sum(map(len, comments.values())),
            'variables': ['gon.comments'] + (['gon.tkool_zips'] if zips_match else []),
            'thread_floor_counts': {key: len(posts) for key, posts in groups.items()},
            'unmapped_comment_rows': sum(unmapped.values()), 'unmapped_tkool_dat_ids': dict(unmapped),
        }
    game_threads = {}
    for row in soup.select('tr.firstline'):
        game = row.select_one('span.id')
        link = row.select_one('a.title[href]')
        match = re.search(r'dlcount\.cgi\?(\d{9,10}):', link['href']) if link else None
        if game and match:
            game_id = game.get_text(strip=True)
            if game_id in game_threads and game_threads[game_id] != match[1]:
                raise ValueError('Conflicting source thread for archive game ' + game_id)
            game_threads[game_id] = match[1]
    groups = defaultdict(dict)
    decoder = json.JSONDecoder()
    row_count = 0
    raw_floors = defaultdict(set)
    rejected_records = []
    variables = []
    for match in re.finditer(r'\bvar\s+(res|dl_res)\s*=\s*', source):
        data, _ = decoder.raw_decode(source[match.end():])
        variables.append(match[1])
        for game_id, records in data.items():
            if game_id not in game_threads:
                raise ValueError('Numbered DAT records lack a source-thread link: ' + game_id)
            thread_id = game_threads[game_id]
            for record in records:
                fields = record.split('<>', 5)
                row_count += 1
                if fields[0].isdigit() and int(fields[0]) > 0:
                    raw_floors[thread_id].add(int(fields[0]))
                if len(fields) != 6 or not fields[0].isdigit() or not re.match(r'\d{4}/\d{2}/\d{2}', fields[3]):
                    rejected_records.append({'game_id': game_id, 'thread_id': thread_id,
                                             'number': int(fields[0]) if fields[0].isdigit() else None,
                                             'reason': 'invalid numbered DAT field count or date',
                                             'raw_numbered_dat': record})
                    continue
                number, name, mail, dateid, body, title = fields
                number = int(number)
                if number < 1:
                    raise ValueError('Invalid embedded floor number')
                if number in groups[thread_id]:
                    post = groups[thread_id][number]
                    if post['raw_numbered_dat'] != record:
                        raise ValueError(f'Conflicting embedded DAT records: {thread_id}/{number}')
                    if game_id not in post['archive_game_ids']:
                        post['archive_game_ids'].append(game_id)
                    continue
                groups[thread_id][number] = {
                    'number': number, 'header': f'{number} ：{text(name)} [{text(mail)}]：{dateid}',
                    'text': text(body), 'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)],
                    'name': text(name), 'mail': mail, 'dateid': dateid, 'body_html': body,
                    'dat_title': title, 'raw_numbered_dat': record, 'archive_game_ids': [game_id],
                }
    return {key: list(posts.values()) for key, posts in groups.items()}, {
        'encoding': soup.original_encoding or 'cp932',
        'archived_http_chunked': archived_chunked,
        'mapped_games': len(game_threads), 'numbered_dat_rows': row_count, 'variables': variables,
        'thread_floor_counts': {key: len(posts) for key, posts in groups.items()},
        'raw_thread_floor_counts': {key: len(numbers) for key, numbers in raw_floors.items()},
        'rejected_source_records': rejected_records,
    }


def fetch(url):
    agent = 'VIPRPG-Thread-Archive/1.0 (personal archival research)' if url.startswith('https://web.archive.org/') else 'Mozilla/5.0'
    request = urllib.request.Request(url, headers={'User-Agent': agent, 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
        if response.headers.get('Content-Encoding', '').lower() == 'gzip':
            raw = gzip.decompress(raw)
        return raw, response.geturl()


def parse_posts(raw):
    dat_lines = raw.splitlines()
    if dat_lines and all(line.count(b'<>') >= 4 for line in dat_lines):
        posts = []
        for number, line in enumerate(raw.decode('cp932').splitlines(), 1):
            name, mail, dateid, body, title = line.split('<>', 4)
            posts.append({'number': number, 'header': f'{number} ：{text(name)} [{text(mail)}]：{dateid}',
                          'text': text(body), 'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)],
                          'name': text(name), 'mail': mail, 'dateid': dateid, 'body_html': body, 'dat_title': title})
        return posts, 'cp932'
    charset = re.search(rb'<meta\b[^>]*charset\s*=\s*["\']?([\w-]+)', raw[:12000], re.I)
    if not charset:
        charset = re.search(rb'<\?xml\b[^>]*encoding\s*=\s*["\']([\w-]+)', raw[:300], re.I)
    encoding = charset[1].decode('ascii') if charset else 'cp932'
    if encoding.lower() in ('shift_jis', 'shift-jis', 'sjis'):
        encoding = 'cp932'
    source = raw.decode(encoding, 'replace')
    posts = []
    blocks = re.split(r'<div\b(?=[^>]*\bdata-id="\d+")[^>]*>', source, flags=re.I)
    if len(blocks) > 1:
        numbers = re.findall(r'<div\b(?=[^>]*\bdata-id="(\d+)")[^>]*>', source, re.I)
        for number, block in zip(numbers, blocks[1:]):
            content = re.search(r'<(section|div)\b[^>]*class="post-content"[^>]*>(.*?)</\1>', block, re.S | re.I)
            if not content:
                continue
            header = text(block[:content.start()])
            body = content[2]
            posts.append({'number': int(number), 'header': header, 'text': text(body),
                          'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)]})
    elif re.search(r'<div\b[^>]*\bid="r\d+"', source, re.I):
        blocks = re.split(r'<div\b[^>]*\bid="r(\d+)"[^>]*>', source, flags=re.I)
        for number, block in zip(blocks[1::2], blocks[2::2]):
            content = re.search(r'<div\b[^>]*class="comment"[^>]*>(.*?)</div>', block, re.S | re.I)
            if not content:
                continue
            body = content[1]
            posts.append({'number': int(number), 'header': text(block[:content.start()]), 'text': text(body),
                          'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)]})
    elif re.search(r'<table\b[^>]*\bid="kiji_\d+"', source, re.I):
        blocks = re.split(r'<table\b[^>]*\bid="kiji_(\d+)"[^>]*>', source, flags=re.I)
        for number, block in zip(blocks[1::2], blocks[2::2]):
            content = re.search(r'<div\b[^>]*class="resc\s+honbun(?:\s+[^"<>]*)?"[^>]*>(.*?)</div>', block, re.S | re.I)
            if not content:
                continue
            body = content[1]
            posts.append({'number': int(number), 'header': text(block[:content.start()]), 'text': text(body),
                          'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)]})
    elif re.search(r'<td\b[^>]*class="msg"', source, re.I):
        blocks = re.split(r'<p>\s*<a\s+name="(\d+)"[^>]*>', source, flags=re.I)
        for number, block in zip(blocks[1::2], blocks[2::2]):
            content = re.search(r'<td\b[^>]*class="msg"[^>]*>(.*?)</td>', block, re.S | re.I)
            if not content:
                continue
            body = content[1]
            posts.append({'number': int(number), 'header': text(block[:content.start()]), 'text': text(body),
                          'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)]})
    else:
        for block in re.split(r'<dt\b[^>]*>', source, flags=re.I)[1:]:
            parts = re.split(r'<dd\b[^>]*>', block, maxsplit=1, flags=re.I)
            if len(parts) != 2:
                continue
            header = text(parts[0])
            number = re.match(r'\s*(\d+)', header)
            if not number:
                continue
            body = re.split(r'</dl>', parts[1], maxsplit=1, flags=re.I)[0]
            posts.append({'number': int(number[1]), 'header': header, 'text': text(body),
                          'hrefs': [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)', body, re.I)]})
    return posts, encoding


def collect(thread, root, retry_failed):
    key = f"{thread['board']}-{thread['id']}"
    meta_path = root / 'threads' / (key + '.json')
    previous = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta['post_count'] or not retry_failed:
            return meta
        previous = meta
    attempts = list(previous['attempts']) if previous else []
    urls = [thread['url']]
    if thread['board'] == 'news4vip':
        urls.append(f"https://viper.2ch.sc/test/read.cgi/news4vip/{thread['id']}/")
    urls = thread.get('fallback_urls', []) + urls
    if previous:
        missing_urls = {a['url'] for a in attempts if a['status'] == 404}
        urls = [url for url in urls if url not in missing_urls]
    posts = []
    source_url = None
    encoding = None
    for url in urls:
        try:
            raw, resolved = fetch(url)
            candidate, enc = parse_posts(raw)
            attempts.append({'url': url, 'resolved': resolved, 'status': 200, 'posts': len(candidate)})
            if candidate:
                posts, source_url, encoding = candidate, resolved, enc
                with gzip.open(root / 'threads' / (key + '.html.gz'), 'wb') as out:
                    out.write(raw)
                with gzip.open(root / 'threads' / (key + '.posts.json.gz'), 'wt', encoding='utf-8') as out:
                    json.dump(posts, out, ensure_ascii=False, separators=(',', ':'))
                break
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
            attempts.append({'url': url, 'status': getattr(error, 'code', None), 'error': str(error)})
        time.sleep(0.3)
    meta = {**thread, 'source_url': source_url, 'encoding': encoding,
            'post_count': len(posts), 'max_post': max((p['number'] for p in posts), default=0),
            'fetched_at': datetime.now(timezone.utc).isoformat(), 'attempts': attempts}
    meta['coverage'] = ('unavailable' if not posts else
                        'partial' if thread['expected'] and meta['max_post'] < thread['expected'] else
                        'count_matches' if thread['expected'] else 'expected_unknown')
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return meta


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def report(root, rescue, catalog_path, threads):
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    known = {(f['uploader'], f['id']): f for f in catalog['files']}
    with sqlite3.connect((rescue / 'queue.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        saved = {(r['uploader'], r['file_id']): dict(r) for r in db.execute('SELECT * FROM files')}
    aliases = defaultdict(set)
    for uploader, number in known.keys() | saved.keys():
        aliases[uploader.lower()].add(uploader)
    references, legacy, unresolved, upload_posts, coverage = [], [], [], [], []
    for thread in threads:
        key = f"{thread['board']}-{thread['id']}"
        meta_path = root / 'threads' / (key + '.json')
        if not meta_path.exists():
            coverage.append({**thread, 'coverage': 'not_fetched', 'post_count': 0})
            continue
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        coverage.append(meta)
        if not meta['post_count']:
            continue
        with gzip.open(root / 'threads' / (key + '.posts.json.gz'), 'rt', encoding='utf-8') as source:
            posts = json.load(source)
        raw_path = Path(meta['raw_source_path']) if meta.get('raw_source_path') else root / 'threads' / (key + '.html.gz')
        with gzip.open(raw_path, 'rb') as source:
            declared = re.search(rb'class="metastats">(\d+)', source.read(60000)) if meta.get('source_format') not in ('dat', 'embedded_numbered_dat', 'embedded_comment_json') else None
        meta['source_declared_posts'] = int(declared[1]) if declared else None
        meta['missing_floor_count'] = meta['max_post'] - len({p['number'] for p in posts})
        if meta['missing_floor_count']:
            meta['coverage'] = 'partial'
        if meta['source_declared_posts'] and meta['max_post'] < meta['source_declared_posts']:
            meta['coverage'] = 'partial'
        for post in posts:
            urls = set()
            for fragment in [post['text'], *post['hrefs']]:
                lowered = fragment.lower()
                if 'getuploader.com' not in lowered and 'uploader.jp' not in lowered:
                    continue
                for match in URL_RE.finditer(html.unescape(fragment)):
                    raw = match[0].rstrip('.,、。)）]】〉＞')
                    raw = re.sub(r'^ttps?', lambda m: 'h' + m[0], raw, flags=re.I)
                    if not re.match(r'^https?://', raw, re.I):
                        raw = 'https://' + raw
                    parsed = urllib.parse.urlsplit(raw)
                    urls.add(urllib.parse.urlunsplit(('https', parsed.netloc.lower(), parsed.path, parsed.query, '')))
            if not urls:
                continue
            date = re.search(r'\d{2,4}/\d{2}/\d{2}[^\n]*?(?:\d{2}:\d{2}:\d{2}(?:\.\d+)?)', post['header'])
            user_id = re.search(r'ID:([^\s]+)', post['header'])
            source_url = post.get('source_url', meta['source_url'])
            post_url = (source_url + '#' + str(post['number']) if source_url.startswith('https://web.archive.org/web/')
                        else source_url.rstrip('/') + '/' + str(post['number']))
            post_url = post.get('source_post_url') or post_url
            context = {'thread_id': thread['id'], 'board': thread['board'], 'title': thread['title'],
                       'floor': post['number'], 'header': post['header'], 'text': post['text'],
                       'date': date[0] if date else '',
                       'author': re.sub(r'^\d+\s*[：:]?\s*', '', post['header'][:date.start()]) if date else '',
                       'user_id': user_id[1] if user_id else '',
                       'sc_native_candidate': '2ch.sc/' in source_url and '.net' not in post['header'],
                       'thread_url': thread['url'],
                       'post_url': post_url, 'source_post_url': post_url, 'source': source_url}
            upload_posts.append({**context, 'urls': sorted(urls)})
            for url in sorted(urls):
                parsed = urllib.parse.urlsplit(url)
                path = urllib.parse.unquote(parsed.path)
                match = re.match(r'^/([^/]+)/(?:download|dl)/(\d+)(?:/|$|(?=[^\x00-\x7f]))', path, re.I)
                direct = re.match(r'^/g/(?:[0-9a-f-]{36}/)?([^/]+)/(\d+)/(.*)', path, re.I)
                if direct and parsed.hostname.lower().endswith('.getuploader.com'):
                    match = direct
                if not match:
                    old = re.match(r'^/(?:dl|user)/([^/]+)/(?:images/)?([^/]+)', path, re.I)
                    if old and parsed.hostname.lower().endswith('.uploader.jp'):
                        filename = re.sub(r'\.html$', '', old[2])
                        legacy.append({**context, 'url': url, 'uploader': old[1], 'name': filename,
                                       'status': 'legacy_identity_unmatched'})
                        continue
                    unresolved.append({**context, 'url': url, 'kind': 'directory_or_legacy_url'})
                    continue
                uploader, number = match[1], str(int(match[2]))
                exact = (uploader, number)
                alias = aliases.get(uploader.lower(), set())
                matched_uploader = uploader if exact in known or exact in saved else next(iter(alias)) if len(alias) == 1 else uploader
                references.append({**context, 'url': url, 'uploader': uploader, 'id': number,
                                   'linked_filename': direct[3] if direct else path[match.end():] if match[0].endswith('/') else '',
                                   'matched_uploader': matched_uploader})
    files = defaultdict(list)
    for reference in references:
        files[(reference['matched_uploader'], reference['id'])].append(reference)
    inventory = []
    for key, refs in sorted(files.items(), key=lambda item: (item[0][0].lower(), int(item[0][1]))):
        record = saved.get(key)
        entry = known.get(key)
        local_path = rescue / record['local_path'] if record and record['local_path'] else None
        exists = bool(local_path and local_path.is_file())
        actual_size = local_path.stat().st_size if exists else None
        state = ('saved' if record and record['state'] == 'done' and exists and actual_size == record['size'] else
                 'saved_record_file_mismatch' if record and record['state'] == 'done' else
                 'known_not_saved' if record or entry else 'not_in_inventory')
        inventory.append({'uploader': key[0], 'id': key[1], 'status': state,
                          'queue_state': record['state'] if record else '',
                          'name': (record or {}).get('original_name') or (entry or {}).get('name') or next((r['linked_filename'] for r in refs if r['linked_filename']), ''),
                          'file_url': f'https://ux.getuploader.com/{key[0]}/download/{key[1]}',
                          'local_path': str(local_path) if local_path else None, 'actual_size': actual_size,
                          'reference_count': len(refs), 'thread_count': len({r['thread_id'] for r in refs}),
                          'first_thread_id': refs[0]['thread_id'], 'first_thread_title': refs[0]['title'],
                          'first_floor': refs[0]['floor'], 'first_date': refs[0]['date'],
                          'first_post_url': refs[0]['post_url'], 'first_header': refs[0]['header'],
                          'first_text': refs[0]['text']})
    missing = [f for f in inventory if f['status'] != 'saved']
    new = [f for f in inventory if f['status'] == 'not_in_inventory']
    for entry in inventory:
        page_path = root / 'file-pages' / f"{entry['uploader']}--{entry['id']}.json"
        if not page_path.exists():
            entry['remote_availability'] = 'not_checked'
            continue
        page = json.loads(page_path.read_text(encoding='utf-8'))
        entry.update(remote_availability=page['availability'], source_http_status=page['http_status'],
                     page_checked_at=page['checked_at'], page_title=page.get('page_title', ''),
                     remote_name=page.get('fields', {}).get('オリジナル', ''),
                     remote_size=page.get('fields', {}).get('容量', ''))
        entry['name'] = entry['name'] or entry['remote_name'] or page.get('fields', {}).get('ファイル', '')
    legacy_files = {}
    for row in legacy:
        key = (row['uploader'], row['name'])
        if key not in legacy_files:
            legacy_files[key] = {**row, 'reference_count': 0}
        legacy_files[key]['reference_count'] += 1
    coverage_by_year = defaultdict(Counter)
    for thread in coverage:
        year = datetime.fromtimestamp(int(thread['id']), timezone.utc).year
        coverage_by_year[str(year)][thread['coverage']] += 1
    summary = {'generated_at': datetime.now(timezone.utc).isoformat(), 'directory_url': DIRECTORY,
               'directory_rows': len(threads), 'coverage': dict(Counter(t['coverage'] for t in coverage)),
               'coverage_by_year': {y: dict(counts) for y, counts in sorted(coverage_by_year.items())},
               'latest_main_thread_started_at': datetime.fromtimestamp(max(int(t['id']) for t in threads if t['board'] == 'news4vip'), timezone.utc).isoformat(),
               'parsed_posts': sum(t['post_count'] for t in coverage), 'uploader_posts': len(upload_posts),
               'file_references': len(references), 'unique_files': len(inventory),
               'file_status': dict(Counter(f['status'] for f in inventory)),
               'new_file_remote_availability': dict(Counter(f['remote_availability'] for f in new)),
               'new_uploaders': sorted({f['uploader'] for f in new if f['uploader'].lower() not in aliases}),
               'unresolved_url_occurrences': len(unresolved), 'queue_files': len(saved),
               'legacy_file_references': len(legacy), 'unmatched_legacy_files': len(legacy_files),
               'catalog_files': len(known), 'queue_states': dict(Counter(r['state'] for r in saved.values())),
               'notes': ['Numbered file links are references, not proof of original submission or current remote availability.',
                         'Directory/template links are retained separately and are not counted as missing files.',
                         'count_matches compares maximum floor with the directory count; deleted or omitted bodies may remain.',
                         '2ch.sc fallback may include native sc posts; the original header and actual source are preserved.',
                         'Legacy uploader.jp identities are kept separate because migration to current file IDs is not established.',
                         'Existing queue, archive files and website data are read-only.']}
    for name, value in [('summary', summary), ('coverage', coverage), ('files', inventory)]:
        (root / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, value in [('uploader-posts', upload_posts), ('file-references', references), ('legacy-file-references', legacy), ('unresolved-links', unresolved)]:
        with (root / (name + '.jsonl')).open('w', encoding='utf-8') as out:
            for row in value:
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
    fields = ['uploader', 'id', 'status', 'queue_state', 'name', 'file_url', 'reference_count',
              'thread_count', 'first_thread_id', 'first_thread_title', 'first_floor', 'first_date',
              'first_post_url', 'first_header', 'first_text', 'remote_availability',
              'source_http_status', 'page_checked_at', 'remote_name', 'remote_size', 'local_path', 'actual_size']
    for name, value in [('missing-files', missing), ('new-files', new), ('all-referenced-files', inventory)]:
        write_csv(root / (name + '.csv'), value, fields)
    write_csv(root / 'available-new-files.csv', [f for f in new if f['remote_availability'] == 'detail_available'], fields)
    write_csv(root / 'uploader-posts.csv', upload_posts, list(upload_posts[0]) if upload_posts else ['thread_id', 'floor'])
    write_csv(root / 'unresolved-links.csv', unresolved, list(unresolved[0]) if unresolved else ['url'])
    write_csv(root / 'unmatched-legacy-files.csv', list(legacy_files.values()),
              ['uploader', 'name', 'status', 'url', 'reference_count', 'post_url', 'date', 'text'])
    write_csv(root / 'unavailable-threads.csv', [t for t in coverage if t['coverage'] in ('unavailable', 'partial', 'not_fetched')],
              ['board', 'id', 'title', 'url', 'expected', 'post_count', 'max_post', 'coverage', 'attempts'])
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('local/thread-audit'))
    parser.add_argument('--rescue-root', type=Path, default=Path('D:/VIPRPG-Rescue/uploaderjp-202611'))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / 'threads').mkdir(exist_ok=True)
    index = args.root / 'kako.csv'
    if not index.exists():
        index.write_bytes(fetch(DIRECTORY)[0])
    rows = list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig')), delimiter='\t'))
    threads = []
    for row in rows:
        row = [value.strip() for value in row]
        if len(row) != 8 or not row[5].isdigit() or row[4] not in ('', 'V', 'N', 'P'):
            raise ValueError(f'Unexpected directory row: {row}')
        host, board = {'': ('kako.5ch.io', 'news4vip'), 'V': ('mi.5ch.io', 'news4vip'),
                       'N': ('agree.5ch.io', 'vip8'), 'P': ('hayabusa9.5ch.io', 'news4viptasu')}[row[4]]
        threads.append({'id': row[5], 'board': board, 'year': row[0], 'start': row[1], 'end': row[2],
                        'ordinal': row[3], 'title': row[6], 'expected': int(row[7]) if row[7].isdigit() else None,
                        'url': f'https://{host}/test/read.cgi/{board}/{row[5]}/'})
    if args.retry_failed:
        chrono = args.root / 'chrono.html'
        if not chrono.exists():
            chrono.write_bytes(fetch('http://tbk.spawn.jp/viprpg_chrono/index.html')[0])
        chrono_text = chrono.read_bytes().decode('cp932', 'replace')
        fallbacks = defaultdict(list)
        for url, thread_id in re.findall(r'(h?ttps?://[^/\s"<>]+/test/read.cgi/news4vip/(\d+)/)', chrono_text):
            url = re.sub(r'^ttp', 'http', url).replace('.2ch.net', '.5ch.net')
            if url not in fallbacks[thread_id]:
                fallbacks[thread_id].append(url)
        for url, thread_id in re.findall(r'href="(log\d+/(\d+)[^"]+\.html)"', chrono_text):
            fallbacks[thread_id].append('http://tbk.spawn.jp/viprpg_chrono/' + url)
        for thread in threads:
            if thread['id'] in fallbacks:
                thread['fallback_urls'] = fallbacks[thread['id']]
    (args.root / 'directory.json').write_text(json.dumps(threads, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.report_only:
        states = Counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect, t, args.root, args.retry_failed) for t in threads]
            for i, future in enumerate(as_completed(futures), 1):
                meta = future.result()
                states[meta['coverage']] += 1
                if i % 25 == 0 or i == len(threads):
                    print(json.dumps({'processed': i, 'total': len(threads), 'coverage': dict(states)}, ensure_ascii=False), flush=True)
    report(args.root, args.rescue_root, Path(__file__).resolve().parents[1] / 'src/data/catalog.json', threads)


if __name__ == '__main__':
    main()
