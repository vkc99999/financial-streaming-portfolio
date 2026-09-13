"""Submit a sample report, or fetch a saved result, without printing credentials."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument('report', nargs='?', help='JSON file containing symptom and observations')
parser.add_argument('--get', help='Fetch an existing request UUID')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
settings = dict(line.split('=', 1) for line in (root / '.env.ai').read_text().splitlines() if '=' in line)
headers = {'X-API-Key': settings['API_KEY'], 'Content-Type': 'application/json'}
if args.get:
    from uuid import UUID
    request = Request(f'http://127.0.0.1:18781/investigations/{UUID(args.get)}', headers=headers)
elif args.report:
    body = json.loads(Path(args.report).read_text())
    body.setdefault('request_id', str(uuid4()))
    print('Request ID:', body['request_id'], flush=True)
    request = Request('http://127.0.0.1:18781/investigations', data=json.dumps(body).encode(), headers=headers)
else:
    parser.error('Supply a report file or --get UUID')
try:
    with urlopen(request, timeout=60) as response:
        print(json.dumps(json.load(response), indent=2))
except HTTPError as error:
    print(f'HTTP {error.code}: {error.read().decode()}')
    raise SystemExit(1)
