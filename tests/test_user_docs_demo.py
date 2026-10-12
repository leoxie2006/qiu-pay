"""User docs isolation and demo-only merchant checkout, using a temporary DB."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import admin, docs, payment
from app.services import auth
from app.middleware.demo_ip_check import DemoIPCheckMiddleware

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setattr(auth, 'DEMO_MODE', True)
    monkeypatch.setattr(auth, 'DEMO_ALLOWED_IPS', ['testclient'])
    database.init_db()
    app = FastAPI()
    app.include_router(admin.router)
    app.include_router(docs.router)
    app.include_router(payment.router)
    app.add_middleware(DemoIPCheckMiddleware)
    return TestClient(app)


def test_docs_only_user_guides(client, tmp_path, monkeypatch):
    guides = tmp_path / 'docs'; guides.mkdir()
    for file in ['使用教程.md', 'api-guide.md', 'docker-timezone.md', 'deployment.md',
                 'pr-standard.md', 'v1.1.3.md', 'CHANGELOG.md']:
        (guides / file).write_text('# ' + file)
    (guides / 'releases').mkdir()
    (guides / 'releases/v1.1.3.md').write_text('# release')
    (tmp_path / 'README.md').write_text('# repo')
    monkeypatch.setattr(docs, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(docs, 'DOCS_DIR', guides)
    rows = client.get('/api/admin/docs/list').json()['data']
    assert {r['filename'] for r in rows} == {'使用教程.md', 'api-guide.md', 'docker-timezone.md'}
    assert all(r['source'] == 'docs' for r in rows)
    for row in rows:
        assert client.get('/api/admin/docs/content', params=row).status_code == 200
    for file,source in [('deployment.md','docs'), ('pr-standard.md','docs'),
                        ('v1.1.3.md','docs'), ('CHANGELOG.md','docs'), ('README.md','root')]:
        assert client.get('/api/admin/docs/content', params={'filename':file,'source':source}).status_code == 404


@pytest.mark.parametrize('filename', ['../README.md', 'releases/v1.1.3.md', r'..\README.md'])
def test_docs_reject_traversal(client, filename):
    assert client.get('/api/admin/docs/content', params={'filename':filename}).status_code == 400


def merchant(client):
    return client.post('/v1/admin/merchants', json={'username':'demo-shop','email':'demo@example.test'}).json()['merchant']


def test_demo_signs_fixed_order_without_disclosing_key(client):
    from app.services.sign import verify_sign
    m = merchant(client)
    url = f"/v1/admin/merchants/{m['pid']}/test-payment"
    response = client.post(url, json={'money':'999', 'notify_url':'https://example.test/', 'return_url':'https://example.test/'})
    assert response.status_code == 200
    params = response.json()['params']
    assert params['money'] == '0.01' and params['return_url'] == '/admin/orders'
    assert not params.get('notify_url') and params['name'] == 'Demo 测试订单'
    assert params['out_trade_no'].startswith('demo_test_')
    assert verify_sign(params, m['key'], params['sign'])
    assert m['key'] not in response.text
    assert client.post(url).json()['params']['out_trade_no'] != params['out_trade_no']
    from app.database import get_db
    with get_db() as db:
        assert db.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0


def test_production_has_no_demo_endpoint_even_with_admin(client, monkeypatch):
    m = merchant(client)
    monkeypatch.setattr(auth, 'DEMO_MODE', False)
    assert client.post(f"/v1/admin/merchants/{m['pid']}/test-payment").status_code == 401
    token = client.post('/v1/admin/auth/login', json={'username':'admin','password':'admin123'}).json()['token']
    assert client.post(f"/v1/admin/merchants/{m['pid']}/test-payment", headers={'Authorization':'Bearer '+token}).status_code == 404


def test_demo_checks_ip_including_forged_forwarded_header(client, monkeypatch):
    m = merchant(client)
    monkeypatch.setattr(auth, 'DEMO_ALLOWED_IPS', ['127.0.0.1'])
    assert client.post(f"/v1/admin/merchants/{m['pid']}/test-payment", headers={'X-Forwarded-For':'127.0.0.1'}).status_code == 403


def test_demo_rejects_missing_or_disabled_merchant(client):
    assert client.post('/v1/admin/merchants/99999/test-payment').status_code == 404
    m = merchant(client)
    client.put(f"/v1/admin/merchants/{m['pid']}", json={'action':'toggle','active':0})
    assert client.post(f"/v1/admin/merchants/{m['pid']}/test-payment").status_code == 400


def test_demo_checkout_requires_credential_and_preserves_payment_gates(client, monkeypatch):
    from app.database import get_db
    from app.services.sign import verify_sign
    m = merchant(client)
    params = client.post(f"/v1/admin/merchants/{m['pid']}/test-payment").json()['params']
    assert client.post('/xpay/epay/mapi.php', data=params).json()['code'] == -1
    monkeypatch.setattr('app.services.order_service.resolve_credential_for_merchant', lambda pid: {
        'qrcode_url':'/static/demo-fixture.png', 'app_id':'fixture', 'private_key':'fixture', 'public_key':'fixture'})
    monkeypatch.setattr('app.services.alipay_client.AlipayClient', Mock(return_value=Mock(query_balance=Mock(return_value={'available_amount':Decimal('0')}))))
    polling = Mock()
    monkeypatch.setattr('app.services.payment_poller.start_payment_polling', polling)
    response = client.post('/xpay/epay/mapi.php', data=params).json()
    assert response['code'] == 1
    trade = response['trade_no']
    polling.assert_called_once_with(trade)
    with get_db() as db:
        row = db.execute('SELECT * FROM orders WHERE trade_no=?', (trade,)).fetchone()
        assert row['status'] == 0 and not row['notify_url']
        assert row['return_url'] == '/admin/orders'
    from urllib.parse import urlsplit, parse_qsl
    for status in [0, 2, 1]:
        with get_db() as db:
            db.execute('UPDATE orders SET status=? WHERE trade_no=?', (status,trade)); db.commit()
        url = client.get('/v1/pay/'+trade).json()['return_url']
        if status == 1:
            query = dict(parse_qsl(urlsplit(url).query))
            assert query['trade_status'] == 'TRADE_SUCCESS'
            assert verify_sign(query, m['key'], query['sign'])
        else:
            assert url == ''
    assert client.post('/xpay/epay/mapi.php', data={**params,'money':'1.00'}).json()['code'] == -1


def test_release_uses_user_notes_without_internal_status():
    workflow = (ROOT / '.github/workflows/release.yml').read_text()
    assert 'generate-notes' not in workflow
    assert '本流程只发布' not in workflow and '- Commit:' not in workflow
    assert 'release-manifest.json' in workflow
    for version in ['v1.1.2','v1.1.3']:
        body = (ROOT / f'docs/releases/{version}.md').read_text()
        assert '## 安装与更新' in body
        assert 'docker compose pull' in body
        assert '实证' not in body and 'CI 后端' not in body and '远端 demo' not in body
