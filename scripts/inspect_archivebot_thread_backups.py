"""Read the published per-file indexes for the queued forum backups; never fetch games."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--limit', type=int, default=1)
args = parser.parse_args()
root = Path('local/thread-audit')
work = root / 'recovery/public-dat'
queue_path = work / 'archivebot-fullthread-backup-files.json'
queue = json.loads(queue_path.read_text(encoding='utf-8'))
ledger = json.loads((work / 'research-ledger.json').read_text(encoding='utf-8'))
now = datetime.now(timezone.utc)
source_after = max((datetime.fromisoformat(x['next_retry_after_utc'])
                    for x in ledger['source_backoffs'] if x['source'] == 'archive.org'), default=now)
wanted = {x['id'] for x in json.loads((root / 'coverage.json').read_text(encoding='utf-8'))
          if x['coverage'] in ('partial', 'unavailable')}
results = []
for item in sorted(queue['files'], key=lambda x: x['priority']):
    if item.get('status') in ('index_checked', 'authorization_required'):
        continue
    after = max(source_after, datetime.fromisoformat(item['after_utc']))
    if now < after:
        results.append({'url': item['url'], 'status': 'deferred_backoff', 'after_utc': after.isoformat()})
        continue
    if sum(x['status'] != 'deferred_backoff' for x in results) >= args.limit:
        break
    report_path = work / f"archivebot-backup-index-{item['priority']}.json"
    result = {'url': item['url'], 'checked_at': datetime.now(timezone.utc).isoformat(),
              'kind': item['kind'], 'scope_closed': False}
    cache = work / f"archivebot-backup-index-{item['priority']}.original"
    try:
        if cache.exists():
            raw = cache.read_bytes()
        else:
            evidence = work / f"archivebot-backup-index-{item['priority']}.response"
            headers = evidence.with_suffix('.headers')
            stderr = evidence.with_suffix('.stderr.txt')
            result.update(response_cache=str(evidence), headers_cache=str(headers), stderr_cache=str(stderr),
                          client='Installed System32curl, inherited environment, standard certificate validation')
            completed = subprocess.run([
                str(Path(os.environ['SystemRoot']) / 'System32/curl.exe'), '--location',
                '--max-time', '30', '--connect-timeout', '15', '--fail-with-body', '--silent', '--show-error',
                '--user-agent', 'VIPRPG-Thread-Archive/1.0 (personal archival research)',
                '--output', str(evidence), '--dump-header', str(headers),
                '--write-out', '%{http_code}\n%{url_effective}\n%{ssl_verify_result}\n', '--url', item['url']],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW)
            stderr.write_text(completed.stderr, encoding='utf-8')
            values = completed.stdout.splitlines()
            result.update(exit_code=completed.returncode, native_client_summary=values,
                          http_status=int(values[0]) if values and values[0].isdigit() else 0)
            if len(values) > 1:
                result['resolved_url'] = values[1]
            if completed.returncode or result['http_status'] != 200:
                raise RuntimeError('Native HTTP file fetch failed; inspect saved headers, body and stderr')
            raw = evidence.read_bytes()
            cache.write_bytes(raw)
        result.update(cache=str(cache), bytes=len(raw))
        expected_bytes = item.get('expected_compressed_bytes') or item.get('expected_bytes')
        if expected_bytes and len(raw) != expected_bytes:
            raise ValueError('Backup file size differs from the published manifest; inspect retained bytes')
        if item['kind'] == 'per_WARC_original_CDX':
            lines = gzip.decompress(raw).decode('utf-8').splitlines()
            header = lines[0].split()
            if not header or header[0] != 'CDX' or not {'a', 's', 'S', 'V', 'g'} <= set(header[1:]):
                raise ValueError('Unrecognised original CDX header; retain bytes for inspection')
            fields = header[1:]
            records = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                values = line.split()
                if len(values) != len(fields):
                    raise ValueError('CDX row width differs from declared header')
                row = dict(zip(fields, values))
                records.append({'url': row['a'], 'status': row['s'], 'raw_cdx': row})
            result['cdx_fields'] = fields
        elif item['kind'] == 'explicit_backup_URL_list':
            lines = [x.strip() for x in raw.decode('utf-8-sig').splitlines()
                     if x.strip() and not x.lstrip().startswith('#')]
            if not lines or any(not x.startswith(('http://', 'https://')) for x in lines):
                raise ValueError('Response is not the published nonempty URL list')
            records = [{'url': x} for x in lines]
        else:
            raise ValueError('Unsupported queued backup file kind')
        hits = []
        for record in records:
            match = re.search(r'/news4vip/(?:[^?#]*?/)?([0-9]{9,10})(?:[/.]|$)',
                              unquote(record['url']))
            if match and match[1] in wanted:
                hits.append({'thread_id': match[1], **record})
        result.update(status='index_checked', scope_closed=True, records=len(records), hits=hits,
                      interpretation='Index records only; no original thread body merged or completeness claimed.')
        item.update(status='index_checked', index_report=str(report_path), target_records=len(hits))
    except (subprocess.TimeoutExpired, RuntimeError, ValueError, OSError, EOFError) as error:
        result.update(status='access_or_format_error_not_absence', error=str(error))
        retry = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        item.update(status='access_or_format_error', after_utc=retry)
        if result.get('http_status') in (401, 403):
            result['status'] = 'authorization_required_not_absence'
            item.update(status='authorization_required', index_report=str(report_path),
                        retry_condition='Public access restored; do not retry automatically or rotate download hosts.')
        if isinstance(error, (subprocess.TimeoutExpired, RuntimeError)):
            for source in ledger['source_backoffs']:
                if source['source'] == 'archive.org':
                    source.update(next_retry_after_utc=retry, reason=str(error), source_file=item['url'])
            (work / 'research-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    results.append(result)
    queue['updated_at'] = datetime.now(timezone.utc).isoformat()
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if result['status'] != 'index_checked':
        break
print(json.dumps(results, ensure_ascii=False))
