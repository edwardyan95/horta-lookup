"""Workstation settings; the shared data directory is never written to."""
import json
import os
from pathlib import Path

APP = Path(__file__).resolve().parent
SETTINGS = APP / 'settings.local.json'

def settings(data_root=None, output_root=None, port=None):
    config = json.loads(SETTINGS.read_text(encoding='utf-8')) if SETTINGS.exists() else {}
    config['data_root'] = data_root or os.environ.get('HORTA_LOOKUP_DATA') or config.get('data_root')
    config['output_root'] = output_root or config.get('output_root', 'saved_checks')
    config['port'] = port if port is not None else config.get('port', 8771)
    if not isinstance(config['port'], int) or not 1024 <= config['port'] <= 65525:
        raise ValueError('Choose a port between 1024 and 65525.')
    for key in ('data_root', 'output_root'):
        if config[key]:
            path = Path(config[key]).expanduser()
            config[key] = str((path if path.is_absolute() else APP / path).resolve())
    if config['data_root'] and Path(config['output_root']).is_relative_to(Path(config['data_root'])):
        raise ValueError('Choose an output folder outside the shared data folder.')
    return config
