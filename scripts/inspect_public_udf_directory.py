"""Read directory metadata from the discovered public UDF backups over HTTP Range."""
import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time

import requests


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--icb', type=int, required=True)
parser.add_argument('--partition', type=int, default=0)
parser.add_argument('--native-http', action='store_true', help='Use installed native curl with existing connection settings')
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
directory = args.manifest.parent
prefix = args.manifest.stem + '-icb-' + str(args.icb)
output = directory / (prefix + '.json')
if output.exists():
    print(output.read_text(encoding='utf-8'))
    raise SystemExit(0)
requests_made = []


def read_range(start, length):
    cache = directory / (prefix + f'-{start}-{length}.bin')
    if cache.exists():
        return cache.read_bytes()
    if args.native_http:
        body = cache.with_suffix('.response')
        headers = cache.with_suffix('.headers')
        completed = subprocess.run([
            str(Path(os.environ['SystemRoot']) / 'System32/curl.exe'), '--location',
            '--max-time', '30', '--connect-timeout', '15', '--max-filesize', str(length + 1),
            '--fail-with-body', '--silent', '--show-error',
            '--header', f'Range: bytes={start}-{start+length-1}',
            '--output', str(body), '--dump-header', str(headers),
            '--write-out', '%{http_code}\n%{url_effective}\n', '--url', manifest['url']],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW)
        cache.with_suffix('.stderr.txt').write_text(completed.stderr, encoding='utf-8')
        values = completed.stdout.splitlines()
        metadata = {'url': manifest['url'], 'start': start, 'length': length,
                    'exit_code': completed.returncode, 'client_summary': values,
                    'body': str(body), 'headers': str(headers)}
        cache.with_suffix('.request.json').write_text(json.dumps(metadata) + '\n', encoding='utf-8')
        if completed.returncode or not values or values[0] != '206':
            raise ValueError('Original ISO range request failed; inspect retained response diagnostics')
        ranges = re.findall(r'(?im)^Content-Range:\s*(bytes \d+-\d+/\d+)\s*$', headers.read_text(encoding='utf-8'))
        assert ranges and ranges[-1].startswith(f'bytes {start}-{start+length-1}/'), 'Unexpected ISO range'
        raw = body.read_bytes()
        assert len(raw) == length, 'Incomplete ISO directory range'
        cache.write_bytes(raw)
        requests_made.append({'range': ranges[-1], 'cache': str(cache), 'request': metadata})
        time.sleep(2)
        return raw
    with requests.get(manifest['url'], headers={'Range': f'bytes={start}-{start+length-1}'}, timeout=25, stream=True) as response:
        response.raise_for_status()
        assert response.status_code == 206, 'Refuse full ISO download'
        assert response.headers['Content-Range'].startswith(f'bytes {start}-{start+length-1}/')
        raw = response.raw.read(length + 1)
        assert len(raw) == length
        cache.write_bytes(raw)
        requests_made.append({'range': response.headers['Content-Range'], 'cache': str(cache)})
    time.sleep(2)
    return raw


parts = manifest['partition_starts']
fe = read_range((parts[str(args.partition)][0] + args.icb) * 2048, 2048)
assert struct.unpack_from('<H', fe)[0] == 261 and fe[27] == 4, 'Only directory metadata may be read'
flags = struct.unpack_from('<H', fe, 34)[0] & 7
ea, adlen = struct.unpack_from('<II', fe, 168)
ads = fe[176+ea:176+ea+adlen]
if flags == 3:
    raw = ads
else:
    assert flags in (0, 1)
    extents = []
    for i in range(0, len(ads), 8 if flags == 0 else 16):
        length, location = struct.unpack_from('<II', ads, i)
        partition = args.partition if flags == 0 else struct.unpack_from('<H', ads, i+8)[0]
        assert length < 10000000, 'Unexpected directory extent'
        extents.append(read_range((parts[str(partition)][0] + location) * 2048, length))
    raw = b''.join(extents)
files = []
i = 0
while i+38 <= len(raw) and struct.unpack_from('<H', raw, i)[0] == 257:
    chars, n = raw[i+18:i+20]
    length, location, partition = struct.unpack_from('<IIH', raw, i+20)
    impl = struct.unpack_from('<H', raw, i+36)[0]
    name = raw[i+38+impl:i+38+impl+n]
    if name:
        assert name[0] in (8, 16)
        files.append({'name': name[1:].decode('utf-16be' if name[0] == 16 else 'latin1'),
                      'directory': bool(chars & 2), 'icb_location': location, 'partition': partition, 'length': length})
    i += (38+impl+n+3) & ~3
result = {'url': manifest['url'], 'icb_location': args.icb, 'partition': args.partition,
          'files': files, 'requests': requests_made}
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': str(output), 'entries': len(files), 'files': files[:40]}, ensure_ascii=False))
