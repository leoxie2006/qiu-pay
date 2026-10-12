"""Promotion ordering, old-run protection and remote digest validation without publishing."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40
DIGEST = 'sha256:' + 'b' * 64


@pytest.mark.parametrize('current,match,expected', [(True,True,0),(False,True,0),(True,False,1)])
def test_latest_promotion(tmp_path, current, match, expected):
    bin = tmp_path / 'bin'; bin.mkdir()
    log = tmp_path / 'docker.log'
    (bin / 'git').write_text('#!/bin/sh\necho "'+(SHA if current else 'c'*40)+' refs/heads/main"\n')
    (bin / 'docker').write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$MOCK_LOG"
if [ "$1 $2 $3" = 'buildx imagetools inspect' ]; then
  echo "Digest: $MOCK_DIGEST"
fi
''')
    for file in bin.iterdir(): file.chmod(0o755)
    env={**os.environ,'PATH':str(bin)+os.pathsep+os.environ['PATH'], 'GITHUB_SHA':SHA,
         'MOCK_LOG':str(log),'MOCK_DIGEST':DIGEST if match else 'sha256:'+'c'*64}
    image='ghcr.io/leoxie2006/qiu-pay:sha-'+SHA
    ref='ghcr.io/leoxie2006/qiu-pay@'+DIGEST
    result=subprocess.run(['bash',str(ROOT/'scripts/release/publish-latest.sh'),image,ref],env=env,capture_output=True,text=True)
    assert result.returncode == expected
    if current:
        assert log.read_text().splitlines()==['tag '+ref+' ghcr.io/leoxie2006/qiu-pay:latest',
             'push ghcr.io/leoxie2006/qiu-pay:latest', 'buildx imagetools inspect ghcr.io/leoxie2006/qiu-pay:latest']
        assert ('LATEST_VERIFIED' in result.stdout)==match
    else:
        assert not log.exists() and 'Skip latest' in result.stdout


def test_latest_is_main_only_after_verification():
    workflow=(ROOT/'.github/workflows/ci-demo.yml').read_text()
    step=workflow.split('- name: Publish latest from current verified main')[1].split('  deploy-demo:')[0]
    assert "github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in step
    assert '${{ steps.publish.outputs.ref }}' in step
    assert workflow.index('Verify actual container image') < workflow.index('Publish immutable revision') < workflow.index('Publish latest')
    assert 'Publish latest' not in (ROOT/'.github/workflows/release.yml').read_text()
