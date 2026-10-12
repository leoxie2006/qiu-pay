"""Deployment orchestration tests with a fake Docker CLI, never a production host."""
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'ghcr.io/example/qiu-pay@sha256:' + 'a' * 64


def test_demo_rejects_mutable_image(tmp_path):
    result = subprocess.run(['bash', str(ROOT / 'scripts/deploy/demo.sh'),
                             str(tmp_path), 'ghcr.io/example/qiu-pay:latest'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'Immutable' in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_demo_rejects_unmarked_directory(tmp_path):
    result = subprocess.run(['bash', str(ROOT / 'scripts/deploy/demo.sh'),
                             str(tmp_path), IMAGE], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'marker' in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def demo(tmp_path):
    root = tmp_path / 'demo'; root.mkdir()
    (root / '.qiu-pay-demo').touch()
    (root / '.env.demo').write_text('JWT_SECRET=test-only\n')
    (root / 'compose.yaml').write_text((ROOT / 'deploy/demo/compose.yaml').read_text())
    (root / '.image.env').write_text('DEMO_IMAGE=sha256:' + 'b' * 64 + '\n')
    (root / 'data').mkdir(); (root / 'uploads').mkdir()
    with sqlite3.connect(root / 'data/qiupay.db') as db:
        db.execute('CREATE TABLE test_orders(id INTEGER)')
        db.execute('INSERT INTO test_orders VALUES(42)')
    commands = tmp_path / 'bin'; commands.mkdir()
    (commands / 'flock').write_text('#!/bin/sh\nexit 0\n')
    (commands / 'flock').chmod(0o755)
    (commands / 'docker').write_text('''#!/usr/bin/env python3
import os,sys,sqlite3
from pathlib import Path
args=sys.argv[1:]; root=Path.cwd()
with (root/'calls.log').open('a') as log: log.write(repr(args)+'\\n')
current='b' if 'sha256:'+'b'*64 in (root/'.image.env').read_text() else 'a'
if args[0]=='compose':
    if 'ps' in args: print('active')
    if 'up' in args and current=='a' and os.getenv('FAIL_DEPLOY')=='1': sys.exit(1)
elif args[0]=='inspect': print('sha256:'+current*64)
elif args[:2]==['image','inspect']:
    if '--format' in args: print('sha256:'+'a'*64)
elif args[0]=='run':
    assert '--network' in args and args[args.index('--network')+1]=='none'
    mounts=[args[i+1] for i,v in enumerate(args) if v=='-v']
    if any(v.endswith(':/source') for v in mounts):
        dest=Path(next(v.rsplit(':/backup',1)[0] for v in mounts if v.endswith(':/backup')))
        src=sqlite3.connect(root/'data/qiupay.db'); dst=sqlite3.connect(dest/'qiupay.db')
        src.backup(dst); dst.close(); src.close()
    else:
        assert all('/data' not in v and '.env' not in v for v in mounts)
        print('MOCK_IMAGE_VERIFICATION_PASS')
''')
    (commands / 'docker').chmod(0o755)
    return root, {**os.environ, 'PATH': str(commands) + os.pathsep + os.environ['PATH']}


@pytest.mark.parametrize('failed', [False, True])
def test_demo_rollout_and_failure_rollback_preserve_db(demo, failed):
    root, env = demo
    env['FAIL_DEPLOY'] = '1' if failed else '0'
    result = subprocess.run(['bash', str(ROOT / 'scripts/deploy/demo.sh'), str(root), IMAGE],
                            env=env, capture_output=True, text=True)
    assert result.returncode == (1 if failed else 0), result.stdout + result.stderr
    with sqlite3.connect(root / 'data/qiupay.db') as db:
        assert db.execute('SELECT id FROM test_orders').fetchall() == [(42,)]
    release = next((root / 'releases').iterdir())
    with sqlite3.connect(release / 'qiupay.db') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('SELECT id FROM test_orders').fetchall() == [(42,)]
    assert (release / 'uploads.tar.gz').exists()
    if failed:
        assert 'b' * 64 in (root / '.image.env').read_text()
    else:
        rollback = subprocess.run(['bash', str(ROOT / 'scripts/deploy/rollback-demo.sh'),
                                   str(root), str(release)], cwd=root, env=env, capture_output=True, text=True)
        assert rollback.returncode == 0, rollback.stdout + rollback.stderr
        assert 'database_retained=True' in rollback.stdout
        assert 'b' * 64 in (root / '.image.env').read_text()
