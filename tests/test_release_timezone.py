"""Release/tag safeguards and host-timezone Compose rendering, without deployment."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('file,service,envfile', [
    ('docker-compose.yml', 'qiu-pay', '.env'),
    ('deploy/demo/compose.yaml', 'demo', '.env.demo'),
])
@pytest.mark.parametrize('custom', [False, True])
def test_compose_mounts_host_timezone_file_readonly(tmp_path, file, service, envfile, custom):
    if not shutil.which('docker'):
        pytest.skip('Docker Compose CLI required to render configuration')
    shutil.copyfile(ROOT / file, tmp_path / 'compose.yaml')
    (tmp_path / envfile).write_text('JWT_SECRET=fixture-only\n')
    environment = {**os.environ, 'DEMO_IMAGE': 'qiu-pay:fixture'}
    environment.pop('HOST_TIMEZONE_FILE', None)
    environment.pop('QIUPAY_IMAGE', None)
    if custom:
        environment['HOST_TIMEZONE_FILE'] = '/fixture/timezone-file'
    result = subprocess.run(['docker', 'compose', '-f', str(tmp_path / 'compose.yaml'),
                             'config', '--format', 'json'], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)
    if service == 'qiu-pay':
        assert config['services'][service]['image'] == 'ghcr.io/leoxie2006/qiu-pay:v1.1.3'
    volume = next(v for v in config['services'][service]['volumes']
                  if v.get('target') == '/etc/localtime')
    assert volume['source'] == ('/fixture/timezone-file' if custom else '/etc/localtime')
    assert volume['type'] == 'bind' and volume['read_only'] is True
    # Compose versions may omit false-valued JSON fields (omitempty).
    # Keep the source-level requirement explicit; reject a rendered true value.
    assert 'create_host_path: false' in (ROOT / file).read_text()
    assert (volume.get('bind') or {}).get('create_host_path', False) is False
    assert 'TZ' not in config['services'][service].get('environment', {})


@pytest.mark.parametrize('tag', ['latest', 'v1.2', 'v01.2.3', 'v1.2.3;echo bad'])
def test_release_rejects_invalid_tag(tmp_path, tag):
    result = subprocess.run(['bash', str(ROOT / 'scripts/release/validate-tag.sh'), tag],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2


def test_release_requires_main_ancestry(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()
    git('init', '-q')
    (tmp_path / 'fixture').write_text('main')
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '-q', '-m', 'fixture main')
    main = git('rev-parse', 'HEAD')
    git('update-ref', 'refs/remotes/origin/main', main)
    git('tag', 'v1.2.3')
    result = subprocess.run(['bash', str(ROOT / 'scripts/release/validate-tag.sh'), 'v1.2.3'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == main
    (tmp_path / 'fixture').write_text('unmerged')
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '-q', '-m', 'fixture unmerged')
    git('tag', 'v1.2.4')
    result = subprocess.run(['bash', str(ROOT / 'scripts/release/validate-tag.sh'), 'v1.2.4'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2 and 'main' in result.stdout
