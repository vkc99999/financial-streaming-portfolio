"""Generate local secrets once; never print them or overwrite an existing file."""
import os
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / '.env.ai'
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('.env.ai already exists; unchanged')
else:
    with os.fdopen(fd, 'w') as handle:
        for name in ('API_KEY', 'INCIDENT_PASSWORD', 'INCIDENT_ADMIN_PASSWORD'):
            handle.write(f'{name}={secrets.token_urlsafe(32)}\n')
        handle.write('OPENAI_API_KEY=\nOPENAI_MODEL=\n')
    print('Created .env.ai. Add your model API key and model name for live calls.')
