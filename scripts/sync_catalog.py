"""Export a public static snapshot; source and upload ledgers are read-only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from contextlib import closing

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
report = Path((root / 'reports/latest-ia-upload.txt').read_text(encoding='utf-8').strip())
plan = json.loads((report / 'public-plan.json').read_text(encoding='utf-8'))
work = root / 'ia-upload'
transports = json.loads((work / 'transports.json').read_text(encoding='utf-8'))
transport_by_source = {value.get('source_logical_key', key): value for key, value in transports.items()}
with closing(sqlite3.connect((work / 'queue.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    objects = {(row['uploader'], row['file_id']): dict(row)
               for row in db.execute('SELECT * FROM objects')}

groups = []
files = []
for source in plan['files']:
    uploader, file_id = source['uploader'], source['file_id']
    assert uploader and all(c.isascii() and (c.isalnum() or c in '_-') for c in uploader)
    assert file_id.isascii() and file_id.isdigit()
    remote = objects.get((uploader, file_id))
    transport = (transports.get(remote['remote_key']) if remote else None) or transport_by_source.get(source.get('remote_path'), {})
    state = remote['state'] if remote else 'not_uploaded'
    remote_path = transport.get('remote_path') or (remote['remote_key'] if remote else None)
    files.append({
        'uploader': uploader, 'id': file_id,
        'name': source['original_name'], 'sourceUrl': source['detail_url'],
        'listedSize': source['listed_size'], 'date': source['source_date'],
        'size': source['size'], 'localState': source['local_state'], 'state': state,
        'remotePath': remote_path, 'requiresUnwrap': bool(transport.get('requires_unwrap')),
        'archiveMember': transport.get('archive_member'),
    })
for group in plan['groups']:
    records = [file for file in files if file['uploader'] == group['uploader']]
    groups.append({'slug': group['uploader'], 'sourceUrl': group['source_url'],
                   'total': len(records), 'counts': dict(Counter(file['state'] for file in records))})

destination = Path(__file__).resolve().parents[1] / 'src/data/catalog.json'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps({
    'updatedAt': datetime.now(timezone.utc).isoformat(),
    'identifier': plan['identifier'], 'groups': groups, 'files': files,
}, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
print(f'Exported {len(groups)} uploaders and {len(files)} file records to {destination}')
