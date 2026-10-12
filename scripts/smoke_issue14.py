#!/usr/bin/env python3
"""Issue 14 verification with a disposable database; never opens the live DB."""
import hashlib
import os
import secrets
import tempfile
from urllib.parse import parse_qsl, urlsplit


def main():
    with tempfile.TemporaryDirectory(prefix="qiupay-issue14-") as directory:
        os.environ.update(DB_PATH=f"{directory}/test.db", TESTING="1",
                          JWT_SECRET=secrets.token_hex(32), ADMIN_PASSWORD=secrets.token_urlsafe(32))
        # Set isolation BEFORE importing modules that load database configuration.
        from app.database import get_db, init_db
        from app.main import app
        from fastapi.testclient import TestClient
        from app.services.callback_service import CallbackService
        init_db()
        key = secrets.token_hex(16)
        with get_db() as db:
            merchant = db.execute(
                "INSERT INTO merchants(username,email,key) VALUES(?,?,?)",
                ("issue14_fixture", "fixture@example.test", key)).lastrowid
            for state in (0, 2, 1):
                db.execute("""INSERT INTO orders
                    (trade_no,out_trade_no,merchant_id,name,original_money,money,
                     base_balance,status,return_url)
                    VALUES(?,?,?,'fixture',1,1,0,?,?)""",
                    (f"FIXTURE_{state}", f"OUT_{state}", merchant, state,
                     "https://merchant.example.test/return"))
        with TestClient(app) as client:
            for state in (0, 2, 1):
                response = client.get(f"/v1/pay/FIXTURE_{state}")
                assert response.status_code == 200
                result = response.json()
                assert result["order"]["status"] == state
                params = dict(parse_qsl(urlsplit(result["return_url"]).query))
                filtered = {k: v for k, v in params.items()
                            if k not in ("sign", "sign_type") and v}
                canonical = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered))
                valid = params.get("sign") == hashlib.md5((canonical + key).encode()).hexdigest()
                if state == 1:
                    assert params.get("trade_status") == "TRADE_SUCCESS" and valid
                else:
                    assert result["return_url"] == "" and not valid
                print(f"state={state} valid_success_signature={valid} PASS")
        with get_db() as db:
            assert db.execute("SELECT count(*) FROM callback_logs").fetchone()[0] == 0
        print("isolated_database=True external_callbacks=0 PASS")


if __name__ == "__main__":
    main()
