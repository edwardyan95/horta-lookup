"""Select a shared data folder and launch the local web application."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.request import urlopen
import webbrowser
from configuration import APP, SETTINGS, settings
from data_bundle import DataBundle

def configure(parent, cfg):
    chosen = filedialog.askdirectory(parent=parent, title='Choose Horta Lookup data folder (contains manifest.json)',
                                     initialdir=cfg.get('data_root') or str(APP))
    if not chosen:
        return None
    DataBundle(chosen)
    cfg['data_root'] = str(Path(chosen).resolve())
    # Validate output/data separation before saving settings.
    cfg = settings(cfg['data_root'], cfg['output_root'], cfg['port'])
    SETTINGS.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    return cfg

def health(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            return json.load(response)
    except Exception:
        return None

def start(cfg):
    bundle = DataBundle(cfg['data_root'])
    for port in range(cfg['port'], cfg['port'] + 10):
        status = health(port)
        if (status and status.get('app') == 'horta-lookup'
            and status.get('data_root') == str(bundle.root)
            and status.get('bundle_id') == bundle.bundle_id
            and status.get('output_root') == cfg['output_root']):
            webbrowser.open(f'http://127.0.0.1:{port}/')
            return
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
                break
            except OSError:
                continue
    else:
        raise ValueError('Local ports are busy. Set a different port in settings.local.json.')
    (APP / 'logs').mkdir(exist_ok=True)
    log = APP / 'logs' / f'server-{port}.log'
    with log.open('ab') as output:
        proc = subprocess.Popen([sys.executable, '-B', str(APP / 'server.py'), '--data-root', cfg['data_root'],
                                 '--output-root', cfg['output_root'], '--port', str(port)],
                                cwd=APP, stdout=output, stderr=output,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        status = health(port)
        if status and status.get('app') == 'horta-lookup' and status.get('bundle_id') == bundle.bundle_id:
            webbrowser.open(f'http://127.0.0.1:{port}/')
            return
        if proc.poll() is not None:
            raise ValueError(f'The app could not start. Details are in {log}')
        time.sleep(.4)
    raise ValueError(f'Startup is taking longer than expected. Check {log}, then reopen the app.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure', action='store_true')
    args = parser.parse_args()
    window = tk.Tk()
    window.withdraw()
    try:
        cfg = settings()
        if args.configure or not cfg['data_root']:
            cfg = configure(window, cfg)
            if cfg is None:
                return
        if args.configure:
            messagebox.showinfo('Data folder saved', 'Reopen Start lookup.cmd to use this data folder.', parent=window)
        else:
            start(cfg)
    except Exception as error:
        messagebox.showerror('Horta Lookup', str(error), parent=window)
    finally:
        window.destroy()

if __name__ == '__main__':
    main()
