import json
import copy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DATA_DIR


class MockDB:
    def __init__(self):
        self._customers = self._load("customers.json")
        self._orders = self._load("orders.json")
        self._subscriptions = self._load("subscriptions.json")
        self._tickets = self._load("tickets.json")
        self._actions_log: list[dict] = []

    def _load(self, filename: str) -> list[dict]:
        path = DATA_DIR / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []

    # ---- Customers ----

    def get_customer(self, customer_id: str) -> Optional[dict]:
        for c in self._customers:
            if c["customer_id"] == customer_id:
                return copy.deepcopy(c)
        return None

    def find_customer_by_email(self, email: str) -> Optional[dict]:
        for c in self._customers:
            if c["email"].lower() == email.lower():
                return copy.deepcopy(c)
        return None

    # ---- Orders ----

    def get_order(self, order_id: str) -> Optional[dict]:
        for o in self._orders:
            if o["order_id"] == order_id:
                return copy.deepcopy(o)
        return None

    def get_orders_by_customer(self, customer_id: str) -> list[dict]:
        return [copy.deepcopy(o) for o in self._orders if o["customer_id"] == customer_id]

    # ---- Subscriptions ----

    def get_subscription_by_customer(self, customer_id: str) -> Optional[dict]:
        for s in self._subscriptions:
            if s["customer_id"] == customer_id and s["status"] == "active":
                return copy.deepcopy(s)
        return None

    def get_subscription(self, subscription_id: str) -> Optional[dict]:
        for s in self._subscriptions:
            if s["subscription_id"] == subscription_id:
                return copy.deepcopy(s)
        return None

    def cancel_subscription(self, subscription_id: str) -> dict:
        for s in self._subscriptions:
            if s["subscription_id"] == subscription_id:
                s["status"] = "cancelled"
                s["cancellation_date"] = datetime.now().isoformat()
                self._log_action("cancel_subscription", {"subscription_id": subscription_id})
                return {"success": True, "message": f"Gói đăng ký {subscription_id} đã được huỷ."}
        return {"success": False, "message": f"Không tìm thấy gói đăng ký {subscription_id}."}

    # ---- Tickets ----

    def get_tickets_by_customer(self, customer_id: str) -> list[dict]:
        return [copy.deepcopy(t) for t in self._tickets if t["customer_id"] == customer_id]

    def create_ticket(self, customer_id: str, order_id: Optional[str],
                      ticket_type: str, priority: str, summary: str) -> dict:
        ticket_id = f"TKT-{len(self._tickets) + 1:03d}"
        ticket = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "order_id": order_id,
            "type": ticket_type,
            "status": "open",
            "priority": priority,
            "summary": summary,
            "created_at": datetime.now().isoformat(),
            "created_by": "ai_agent",
            "assigned_to": None,
            "resolution": None,
        }
        self._tickets.append(ticket)
        self._log_action("create_ticket", ticket)
        return {"success": True, "ticket_id": ticket_id, "message": f"Ticket {ticket_id} đã được tạo."}

    # ---- Payments / Refunds ----

    def process_refund(self, order_id: str, amount: float, reason: str) -> dict:
        refund_id = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = {
            "success": True,
            "refund_id": refund_id,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "message": f"Đã hoàn tiền {amount:,.0f}đ cho đơn hàng {order_id}.",
        }
        self._log_action("process_refund", result)
        return result

    # ---- Notifications ----

    def send_notification(self, channel: str, message: str, recipient: str) -> dict:
        result = {
            "success": True,
            "channel": channel,
            "recipient": recipient,
            "message": message,
            "sent_at": datetime.now().isoformat(),
        }
        self._log_action("send_notification", result)
        return result

    # ---- Audit Trail ----

    def _log_action(self, action_type: str, details: dict):
        self._actions_log.append({
            "action": action_type,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        })

    def get_actions_log(self) -> list[dict]:
        return copy.deepcopy(self._actions_log)

    def get_recent_refunds(self, customer_id: str, days: int = 90) -> int:
        """Count recent refunds for a customer within a time window."""
        cutoff = datetime.now() - timedelta(days=days)
        count = 0
        for action in self._actions_log:
            if action["action"] != "process_refund":
                continue
            refund_order_id = action["details"].get("order_id", "")
            order = self.get_order(refund_order_id)
            if order and order.get("customer_id") == customer_id:
                try:
                    action_time = datetime.fromisoformat(action["timestamp"])
                    if action_time >= cutoff:
                        count += 1
                except (ValueError, KeyError):
                    count += 1
        return count
