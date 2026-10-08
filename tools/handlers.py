import json
from typing import Optional
from tools.mock_db import MockDB


class ToolHandlers:
    def __init__(self, db: MockDB):
        self.db = db

    def get_customer(self, customer_id: str) -> dict:
        customer = self.db.get_customer(customer_id)
        if not customer:
            return {"found": False, "message": f"Không tìm thấy khách hàng với mã {customer_id}"}
        return {"found": True, "customer": customer}

    def get_order(self, order_id: str) -> dict:
        order = self.db.get_order(order_id)
        if not order:
            return {"found": False, "message": f"Không tìm thấy đơn hàng với mã {order_id}"}
        return {"found": True, "order": order}

    def get_orders_by_customer(self, customer_id: str) -> dict:
        orders = self.db.get_orders_by_customer(customer_id)
        return {"found": len(orders) > 0, "count": len(orders), "orders": orders}

    def get_subscription(self, customer_id: str) -> dict:
        sub = self.db.get_subscription_by_customer(customer_id)
        if not sub:
            return {"found": False, "message": f"Không tìm thấy gói đăng ký đang hoạt động cho khách hàng {customer_id}"}
        return {"found": True, "subscription": sub}

    def create_support_ticket(self, customer_id: str, ticket_type: str,
                              priority: str, summary: str, order_id: str = "") -> dict:
        result = self.db.create_ticket(
            customer_id=customer_id,
            order_id=order_id or None,
            ticket_type=ticket_type,
            priority=priority,
            summary=summary,
        )
        return result

    def process_refund(self, order_id: str, amount: float, reason: str) -> dict:
        order = self.db.get_order(order_id)
        if not order:
            return {"success": False, "message": f"Đơn hàng {order_id} không tìm thấy. Không thể hoàn tiền."}

        return self.db.process_refund(order_id=order_id, amount=amount, reason=reason)

    def cancel_subscription(self, subscription_id: str) -> dict:
        return self.db.cancel_subscription(subscription_id)

    def send_notification(self, channel: str, recipient: str, message: str) -> dict:
        return self.db.send_notification(channel=channel, message=message, recipient=recipient)
