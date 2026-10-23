#!/usr/bin/env python3
"""Fa terminare i lotti già in corso e riavvia le due code con il tetto locale."""
from contextlib import ExitStack
import os
import subprocess
import sys
import time

from archivio_tools import archive_lock, enforce_budget, local_budget, now, write_json
from divago import ROOT

archive = ROOT / 'archivio'
state = archive / 'stato'
stop = state / 'ferma-scaricamento-icloud'
status = state / 'ripresa-con-limite.json'


def run():
    with archive_lock(archive, name='ripresa-con-limite'):
        token = stop.stat().st_mtime_ns
        write_json(status, {'updated_at': now(), 'phase': 'attesa fine lotti', 'limit_GB': local_budget(archive)['limit_bytes'] / 1_000_000_000})
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            if not stop.exists() or stop.stat().st_mtime_ns != token:
                write_json(status, {'updated_at': now(), 'phase': 'annullata', 'detail': 'Stato di pausa modificato durante l’attesa.'})
                return
            try:
                with ExitStack() as stack:
                    for name in ['scaricamento-icloud', 'scaricamento-video-icloud']:
                        stack.enter_context(archive_lock(archive, name=name))
                    enforce_budget(archive, headroom=2_000_000_000)
                    stop.unlink()
                    stack.close()
                    env = os.environ.copy()
                    env['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + env.get('PATH', '')
                    pids = []
                    for script, log in [('scarica_icloud.py', 'scaricamento-icloud.log'),
                                        ('scarica_video_icloud.py', 'scaricamento-video-icloud.log')]:
                        if script == 'scarica_video_icloud.py' and (state / 'ferma-scaricamento-video').exists():
                            continue
                        with (archive / 'logs' / log).open('a') as output:
                            proc = subprocess.Popen(['/usr/bin/caffeinate', '-is', sys.executable, '-u', '-B', str(ROOT / script)],
                                                    cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                                    stderr=subprocess.STDOUT, start_new_session=True)
                            pids.append(proc.pid)
                    write_json(status, {'updated_at': now(), 'phase': 'code riavviate con limite', 'limit_GB': local_budget(archive)['limit_bytes'] / 1_000_000_000, 'pids': pids})
                    return
            except ValueError as exc:
                if (state / 'limite-raggiunto.json').exists():
                    write_json(status, {'updated_at': now(), 'phase': 'limite raggiunto', 'detail': str(exc)})
                    return
            time.sleep(2)
        write_json(status, {'updated_at': now(), 'phase': 'attesa scaduta', 'detail': 'Code lasciate in pausa; nessun riavvio duplicato.'})


if __name__ == '__main__':
    run()
