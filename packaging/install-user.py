#!/usr/bin/env python3
"""Install a built Lumen into a user prefix without pip or root access.

System Python provides the distro's GTK/WebKit runtime dependencies. Versioned
copies keep running installations intact and permit switching back if needed.
"""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home()/'.local')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root/'huectl'
    if not (source/'webui_dist/index.html').is_file():
        parser.error('Build the Vue frontend first: cd webui && npm ci && npm run build')
    missing = [m for m in ('webview','requests','gi','pystray','PIL') if importlib.util.find_spec(m) is None]
    if missing:
        parser.error('Missing distro Python packages: '+', '.join(missing))
    prefix = args.prefix.resolve()
    base = prefix/'share/lumen'
    bindir = prefix/'bin'
    desktop = prefix/'share/applications/lumen.desktop'
    marker = '# Lumen managed launcher'
    entries = {'hue-webui':'huectl.webapp','hue-sync':'huectl.sync','hue':'huectl.cli'}
    for name in entries:
        path = bindir/name
        if path.exists() and marker not in path.read_text():
            parser.error(f'Refusing to replace an unmanaged launcher: {path}')
    if desktop.exists() and 'X-Lumen-Managed=true' not in desktop.read_text():
        parser.error(f'Refusing to replace an unmanaged desktop entry: {desktop}')
    digest = hashlib.sha256()
    files = sorted(p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for path in files:
        digest.update(str(path.relative_to(source)).encode())
        digest.update(path.read_bytes())
    release = base/'releases'/digest.hexdigest()[:16]
    release.parent.mkdir(parents=True,exist_ok=True)
    if not release.exists():
        with tempfile.TemporaryDirectory(dir=release.parent,prefix='.build-') as temp:
            staging = Path(temp)/'app'
            shutil.copytree(source,staging/'huectl',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            os.replace(staging,release)
    current = base/'current'
    if current.exists() and not current.is_symlink():
        parser.error(f'Refusing to replace a non-symlink: {current}')
    link = base/f'.current-{os.getpid()}'
    try:
        link.symlink_to(release.relative_to(base),target_is_directory=True)
        os.replace(link,current)
    finally:
        link.unlink(missing_ok=True)
    bindir.mkdir(parents=True,exist_ok=True)
    for name,module in entries.items():
        text = '#!/bin/sh\n'+marker+'\nexport PYTHONPATH='+shlex.quote(str(current))+'\nexec '+shlex.quote(sys.executable)+' -m '+module+' "$@"\n'
        path = bindir/name
        path.write_text(text);path.chmod(0o755)
    desktop.parent.mkdir(parents=True,exist_ok=True)
    # Desktop Exec uses its own quoting rules, not shell quoting.
    exe = str(bindir/'hue-webui').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Lumen\nComment=Philips Hue control and screen mapping\nExec="'+exe+'"\nIcon=preferences-desktop-display\nTerminal=false\nCategories=Utility;\nStartupNotify=false\nX-Lumen-Managed=true\n')
    print('Installed:',release)
    print('Launcher:',bindir/'hue-webui')
    print('Settings and autostart were not changed.')


if __name__=='__main__':main()
