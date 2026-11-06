"""Export website download paths from an IA migration plan, independent of IA indexing."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan', type=Path, required=True)
args = parser.parse_args()
plan = json.loads(args.plan.read_text(encoding='utf-8'))
files = {file['key']: file['destination_path'] for file in plan['files'] if file['kind'] == 'original'}
assert len(files) == sum(file['kind'] == 'original' for file in plan['files'])
assert all(path and not path.startswith('/') for path in files.values())
destination = Path(__file__).resolve().parents[1] / 'src/data/ia-downloads.json'
destination.write_text(json.dumps(files, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
(destination.parent / 'ia-storage.json').write_text(json.dumps({
    'identifier': plan['destination_identifier'],
}, separators=(',', ':')) + '\n', encoding='utf-8')
print(f'Exported {len(files)} download paths to {destination}')
