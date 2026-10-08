from tools.handlers import ToolHandlers

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": "Tra cứu thông tin khách hàng theo mã khách hàng. Trả về tên, email, hạng thành viên, giá trị trọn đời.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Mã khách hàng (ví dụ: 'C001')"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Tra cứu chi tiết đơn hàng theo mã đơn. Trả về sản phẩm, tổng tiền, trạng thái, thông tin thanh toán và vận chuyển.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Mã đơn hàng (ví dụ: 'ORD-1001')"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders_by_customer",
            "description": "Tra cứu tất cả đơn hàng của một khách hàng. Trả về danh sách đơn hàng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Mã khách hàng"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_subscription",
            "description": "Tra cứu gói đăng ký đang hoạt động của khách hàng. Trả về gói, giá, chu kỳ thanh toán, trạng thái.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Mã khách hàng"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Tạo ticket hỗ trợ mới cho vấn đề cần theo dõi hoặc cần nhân viên xử lý.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Mã khách hàng"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "Mã đơn hàng liên quan (không bắt buộc)",
                        "default": ""
                    },
                    "ticket_type": {
                        "type": "string",
                        "enum": ["delivery_issue", "payment_issue", "subscription_issue",
                                 "product_issue", "general_inquiry", "escalation"],
                        "description": "Loại ticket"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Mức độ ưu tiên"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Mô tả ngắn gọn vấn đề"
                    }
                },
                "required": ["customer_id", "ticket_type", "priority", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": "Xử lý hoàn tiền cho đơn hàng. QUAN TRỌNG: Hành động này phải qua kiểm tra chính sách. Hoàn tiền >= 500.000đ cần phê duyệt của quản lý.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Mã đơn hàng cần hoàn tiền"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Số tiền hoàn (VNĐ)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Lý do hoàn tiền"
                    }
                },
                "required": ["order_id", "amount", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_subscription",
            "description": "Huỷ gói đăng ký của khách hàng. Việc huỷ có hiệu lực vào cuối chu kỳ thanh toán hiện tại.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Mã gói đăng ký cần huỷ"
                    }
                },
                "required": ["subscription_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Gửi thông báo qua Slack hoặc email (mô phỏng). Dùng cho cảnh báo nội bộ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["slack", "email"],
                        "description": "Kênh thông báo"
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Người nhận (tên kênh Slack hoặc địa chỉ email)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Nội dung thông báo"
                    }
                },
                "required": ["channel", "recipient", "message"]
            }
        }
    },
]


class ToolRegistry:
    """Maps tool names to handler functions and manages tool execution."""

    def __init__(self, handlers: ToolHandlers):
        self.handlers = handlers
        self._dispatch = {
            "get_customer": handlers.get_customer,
            "get_order": handlers.get_order,
            "get_orders_by_customer": handlers.get_orders_by_customer,
            "get_subscription": handlers.get_subscription,
            "create_support_ticket": handlers.create_support_ticket,
            "process_refund": handlers.process_refund,
            "cancel_subscription": handlers.cancel_subscription,
            "send_notification": handlers.send_notification,
        }

    def get_schemas(self) -> list[dict]:
        return TOOL_SCHEMAS

    def call(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with given arguments."""
        handler = self._dispatch.get(tool_name)
        if not handler:
            return {"error": f"Công cụ không xác định: {tool_name}"}
        try:
            return handler(**arguments)
        except TypeError as e:
            return {"error": f"Tham số không hợp lệ cho {tool_name}: {e}"}
        except Exception as e:
            return {"error": f"Công cụ {tool_name} gặp lỗi: {e}"}

    def list_tools(self) -> list[str]:
        return list(self._dispatch.keys())
