"""商户管理服务模块。"""

import secrets
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models.schemas import Merchant


class MerchantService:
    """商户管理服务：创建、封禁/解封、重置密钥、查询。"""

    @staticmethod
    def _generate_key() -> str:
        """生成 32 位随机十六进制密钥。"""
        return secrets.token_hex(16)

    def create_merchant(self, username: str, email: str) -> Merchant:
        """
        创建商户，分配自增 pid 和 32 位随机 KEY，设置 active=1。

        Raises:
            ValueError: 用户名已存在。
        """
        key = self._generate_key()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO merchants (username, email, key, active, created_at, updated_at)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (username, email, key, now, now),
            )
            db.commit()
            pid = cursor.lastrowid

            return Merchant(
                id=pid,
                username=username,
                email=email,
                key=key,
                active=1,
                created_at=now,
                updated_at=now,
            )
        except Exception as e:
            db.rollback()
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"用户名 '{username}' 已存在") from e
            raise
        finally:
            db.close()

    def toggle_status(self, pid: int, active: bool) -> None:
        """
        封禁或解封商户。

        Args:
            pid: 商户 ID。
            active: True 解封(active=1)，False 封禁(active=0)。

        Raises:
            ValueError: 商户不存在。
        """
        active_val = 1 if active else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        try:
            cursor = db.execute(
                "UPDATE merchants SET active = ?, updated_at = ? WHERE id = ?",
                (active_val, now, pid),
            )
            db.commit()
            if cursor.rowcount == 0:
                raise ValueError(f"商户 pid={pid} 不存在")
        finally:
            db.close()

    def reset_key(self, pid: int) -> str:
        """
        重置商户密钥，生成新 KEY 并立即生效。

        Returns:
            新的 32 位密钥字符串。

        Raises:
            ValueError: 商户不存在。
        """
        new_key = self._generate_key()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        try:
            cursor = db.execute(
                "UPDATE merchants SET key = ?, updated_at = ? WHERE id = ?",
                (new_key, now, pid),
            )
            db.commit()
            if cursor.rowcount == 0:
                raise ValueError(f"商户 pid={pid} 不存在")
            return new_key
        finally:
            db.close()

    def get_merchant_info(self, pid: int) -> dict:
        """
        获取商户信息，含订单统计（总订单数、今日订单数、昨日订单数）。
        余额从已支付订单实时聚合计算。

        Raises:
            ValueError: 商户不存在。
        """
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM merchants WHERE id = ?", (pid,)
            ).fetchone()
            if not row:
                raise ValueError(f"商户 pid={pid} 不存在")

            today = date.today().strftime("%Y-%m-%d")
            yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

            # 总订单数
            total = db.execute(
                "SELECT COUNT(*) AS cnt FROM orders WHERE merchant_id = ?",
                (pid,),
            ).fetchone()["cnt"]

            # 今日订单数
            today_count = db.execute(
                "SELECT COUNT(*) AS cnt FROM orders WHERE merchant_id = ? AND date(created_at) = ?",
                (pid, today),
            ).fetchone()["cnt"]

            # 昨日订单数
            yesterday_count = db.execute(
                "SELECT COUNT(*) AS cnt FROM orders WHERE merchant_id = ? AND date(created_at) = ?",
                (pid, yesterday),
            ).fetchone()["cnt"]

            # 从已支付订单实时计算余额（用整数分求和避免浮点精度问题）
            money_row = db.execute(
                """SELECT COALESCE(SUM(CAST(ROUND(money * 100, 0) AS INTEGER)), 0) AS total_cents
                   FROM orders WHERE merchant_id = ? AND status = 1""",
                (pid,),
            ).fetchone()
            money_yuan = f"{money_row['total_cents'] / 100:.2f}"

            return {
                "code": 1,
                "pid": row["id"],
                "key": row["key"],
                "active": row["active"],
                "money": money_yuan,
                "type": row["settle_type"],
                "account": row["settle_account"] or "",
                "username": row["settle_username"] or "",
                "orders": total,
                "order_today": today_count,
                "order_lastday": yesterday_count,
            }
        finally:
            db.close()

    def list_merchants(self) -> list[dict]:
        """获取所有商户列表，含基本信息和订单统计。余额从已支付订单实时聚合。"""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM merchants ORDER BY id ASC"
            ).fetchall()

            merchants = []
            for row in rows:
                pid = row["id"]

                total = db.execute(
                    "SELECT COUNT(*) AS cnt FROM orders WHERE merchant_id = ?",
                    (pid,),
                ).fetchone()["cnt"]

                today = date.today().strftime("%Y-%m-%d")
                today_count = db.execute(
                    "SELECT COUNT(*) AS cnt FROM orders WHERE merchant_id = ? AND date(created_at) = ?",
                    (pid, today),
                ).fetchone()["cnt"]

                # 从已支付订单实时计算余额（用整数分求和避免浮点精度问题）
                money_row = db.execute(
                    """SELECT COALESCE(SUM(CAST(ROUND(money * 100, 0) AS INTEGER)), 0) AS total_cents
                       FROM orders WHERE merchant_id = ? AND status = 1""",
                    (pid,),
                ).fetchone()

                merchants.append({
                    "pid": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "key": row["key"],
                    "active": row["active"],
                    "money": f"{money_row['total_cents'] / 100:.2f}",
                    "orders": total,
                    "order_today": today_count,
                    "created_at": row["created_at"],
                })

            return merchants
        finally:
            db.close()
