"""Resolve archive parent IDs from retained link or complete-post evidence without executing JavaScript."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import re
import unicodedata

from bs4 import BeautifulSoup
from audit_thread_uploads import text


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--queue', type=Path, default=Path('local/thread-audit/recovery/public-dat/gon-source-queue.json'))
parser.add_argument('--match-cached-posts', action='store_true', help='Resolve remaining IDs using at least two unique complete post-identity matches')
args = parser.parse_args()
work = Path('local/thread-audit/recovery/public-dat')
queue = json.loads(args.queue.read_text(encoding='utf-8'))
destination = Path(queue['parent_mapping_path'])
previous = json.loads(destination.read_text(encoding='utf-8')) if destination.exists() else {'mappings': {}}
parents = previous['mappings']
old_keys = set(parents)
games = {}
for source in json.loads((work / 'embedded-posts-manifest.json').read_text(encoding='utf-8')):
    soup = BeautifulSoup(gzip.open(source['cache'], 'rb').read(), 'html.parser')
    for row in soup.select('tr.firstline'):
        number = row.select_one('span.id')
        link = row.select_one('a.title[href]')
        match = re.search(r'dlcount.cgi\?(\d+):([^/?&#]+)', link['href']) if link else None
        if not number or not match:
            continue
        key = (number.get_text(strip=True), match[2].removesuffix('.zip'))
        if key in games and games[key]['thread_id'] != match[1]:
            raise ValueError('Conflicting original thread for legacy game ' + str(key))
        games[key] = {'thread_id': match[1], 'old_cache': source['cache'],
                      'old_source_url': source['source_url'], 'old_href': link['href']}
pages = []
for source in queue['sources']:
    cache = Path(source['cache'])
    if not cache.exists():
        continue
    soup = BeautifulSoup(gzip.open(cache, 'rb').read(), 'html.parser')
    content = str(soup)
    match = re.search(r'\bgon\.comments\s*=\s*', content)
    if not match:
        continue
    comments, _ = json.JSONDecoder().raw_decode(content[match.end():])
    found = 0
    for row in soup.select('tr.firstline'):
        link = row.select_one('a.title[href]')
        match = re.search(r'/download/(\d+)/([^/?&#]+)', link['href']) if link else None
        if not match:
            continue
        game_id, basename = match[1], match[2].removesuffix('.zip')
        evidence = games.get((game_id, basename))
        if not evidence:
            continue
        for record in comments.get(game_id, []):
            key = str(record['tkool_dat_id'])
            if key in parents and parents[key]['thread_id'] != evidence['thread_id']:
                raise ValueError('Conflicting original thread for archive database ID ' + key)
            parents.setdefault(key, {**evidence, 'game_id': game_id, 'basename': basename,
                                     'mapping_comment': record, 'new_cache': str(cache),
                                     'new_source_url': source.get('resolved_url') or source['source_url']})
            found += 1
    pages.append({'cache': str(cache), 'identity_join_record_observations': found})
if args.match_cached_posts:
    def signature(number, header, body):
        stamp = re.search(r'(\d{4}/\d{2}/\d{2}).*?(\d{2}:\d{2}:\d{2}(?:\.\d+)?)', header)
        identity = re.search(r'ID:([^\s<>]+)', header)
        if not stamp or not identity:
            return None
        body = unicodedata.normalize('NFC', re.sub(r'\s+', '', unicodedata.normalize('NFKC', body)))
        return number, stamp[1], stamp[2], identity[1], body

    wanted = defaultdict(set)
    evidence = {}
    days = set()
    for source in queue['sources']:
        cache = Path(source['cache'])
        if not cache.exists():
            continue
        content = gzip.open(cache, 'rt', encoding='utf-8').read()
        match = re.search(r'\bgon\.comments\s*=\s*', content)
        if not match:
            continue
        comments, _ = json.JSONDecoder().raw_decode(content[match.end():])
        for game_id, records in comments.items():
            for record in records:
                key = str(record['tkool_dat_id'])
                identity = signature(record['line'], record['date'], text(record['body']))
                if key in parents or identity is None:
                    continue
                wanted[identity].add(key)
                days.add(record['date'][:10])
                evidence.setdefault((key, record['line']), {'new_cache': str(cache), 'game_id': game_id,
                                    'comment_id': record['id'], 'comment_date': record['date']})
    ends = [datetime.strptime(day, '%Y/%m/%d').replace(tzinfo=timezone(timedelta(hours=9))).timestamp() + 86399
            for day in days]
    votes = defaultdict(lambda: defaultdict(dict))
    for thread in json.loads(Path('local/thread-audit/coverage.json').read_text(encoding='utf-8')):
        if thread['board'] != 'news4vip':
            continue
        # Narrow file reads by time; only complete post identity determines a mapping.
        if not any(0 <= end - int(thread['id']) <= 31 * 86400 for end in ends):
            continue
        path = Path('local/thread-audit/threads/news4vip-' + thread['id'] + '.posts.json.gz')
        if not path.exists():
            continue
        for post in json.load(gzip.open(path, 'rt', encoding='utf-8')):
            identity = signature(post['number'], post.get('dateid') or post['header'], post['text'])
            for key in wanted.get(identity, ()):
                votes[key][thread['id']][post['number']] = {
                    **evidence[(key, post['number'])], 'original_posts_path': str(path),
                    'original_floor': post['number'], 'original_header': post['header'],
                    'original_source_url': post.get('source_url') or thread['source_url'],
                }
    for key, threads in votes.items():
        if len(threads) != 1:
            continue
        thread_id, matches = next(iter(threads.items()))
        if len(matches) >= 2:
            parents[key] = {'thread_id': thread_id,
                            'basis': 'At least two unique original post identities: floor, complete timestamp, poster ID and body modulo whitespace/Unicode width',
                            'matched_original_posts': list(matches.values())}
previous.update(updated_at=datetime.now(timezone.utc).isoformat(),
                basis='Verified game ID and basename joins or at least two unique complete original post identities; never assign a thread from dates alone',
                mappings=parents, added_dat_ids=sorted(set(parents) - old_keys), inspected_pages=pages)
previous['identity_matched_dat_ids'] = sorted(key for key, value in parents.items() if value.get('matched_original_posts'))
destination.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'mapping_file': str(destination), 'legacy_game_id_filename_pairs': len(games),
                  'mapped_database_ids': len(parents), 'new_mapped_ids': sorted(set(parents) - old_keys),
                  'inspected_cached_pages': len(pages)}))
