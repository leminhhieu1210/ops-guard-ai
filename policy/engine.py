import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from config import (
    AUTO_REFUND_LIMIT,
    MAX_AUTO_REFUNDS_90_DAYS,
    REFUND_ELIGIBILITY_DAYS,
    HIGH_VALUE_ORDER_THRESHOLD,
    CURRENT_DATE,
)


@dataclass
class PolicyResult:
    """Result of a policy check."""
    allowed: bool
    reason: str
    risk_level: str  # "low", "medium", "high", "critical"
    escalation_needed: bool = False
    escalation_priority: str = ""  # "low", "medium", "high", "urgent"
    policy_references: list[str] = field(default_factory=list)


class PolicyEngine:
    def check_refund(
        self,
        amount: float,
        order_data: dict,
        customer_data: Optional[dict] = None,
        recent_refund_count: int = 0,
        customer_message: str = "",
    ) -> PolicyResult:

        # Rule 1: Check for legal threats or aggressive language
        if self._detect_legal_threat(customer_message):
            return PolicyResult(
                allowed=False,
                reason="Phát hiện đe dọa pháp lý trong tin nhắn khách hàng. Bắt buộc chuyển tiếp.",
                risk_level="critical",
                escalation_needed=True,
                escalation_priority="urgent",
                policy_references=["escalation_sop.md — Các Trường Hợp Bắt Buộc Chuyển Tiếp — Đe dọa pháp lý"],
            )

        # Rule 2: Amount threshold
        if amount >= AUTO_REFUND_LIMIT:
            return PolicyResult(
                allowed=False,
                reason=f"Số tiền hoàn {amount:,.0f}đ vượt ngưỡng tự động duyệt {AUTO_REFUND_LIMIT:,.0f}đ.",
                risk_level="high",
                escalation_needed=True,
                escalation_priority="high",
                policy_references=["refund_policy.md — Cần Phê Duyệt Của Quản Lý — Số tiền >= 500.000đ"],
            )

        # Rule 3: Too many recent refunds
        if recent_refund_count >= MAX_AUTO_REFUNDS_90_DAYS:
            return PolicyResult(
                allowed=False,
                reason=f"Khách hàng đã có {recent_refund_count} lần hoàn tiền trong 90 ngày qua (giới hạn: {MAX_AUTO_REFUNDS_90_DAYS}).",
                risk_level="medium",
                escalation_needed=True,
                escalation_priority="medium",
                policy_references=["refund_policy.md — Cần Phê Duyệt Của Quản Lý — Hoàn tiền lặp lại"],
            )

        # Rule 4: Check payment date eligibility
        payment_date = self._get_latest_payment_date(order_data)
        if payment_date:
            days_since = (datetime.fromisoformat(CURRENT_DATE) - payment_date).days
            if days_since > REFUND_ELIGIBILITY_DAYS:
                return PolicyResult(
                    allowed=False,
                    reason=f"Thanh toán cách đây {days_since} ngày, vượt quá thời hạn hoàn tiền {REFUND_ELIGIBILITY_DAYS} ngày.",
                    risk_level="medium",
                    escalation_needed=True,
                    escalation_priority="medium",
                    policy_references=["refund_policy.md — Điều Kiện Áp Dụng — Thời hạn 30 ngày"],
                )

        # All checks passed
        return PolicyResult(
            allowed=True,
            reason=f"Hoàn tiền {amount:,.0f}đ được duyệt. Số tiền dưới {AUTO_REFUND_LIMIT:,.0f}đ, trong thời hạn cho phép.",
            risk_level="low",
            policy_references=["refund_policy.md — Hoàn Tiền Tự Động"],
        )

    def check_cancellation(
        self,
        subscription_data: dict,
        customer_data: Optional[dict] = None,
        customer_message: str = "",
    ) -> PolicyResult:
        """Check if a subscription cancellation can proceed automatically."""

        # Legal threat check
        if self._detect_legal_threat(customer_message):
            return PolicyResult(
                allowed=False,
                reason="Phát hiện đe dọa pháp lý. Bắt buộc chuyển tiếp.",
                risk_level="critical",
                escalation_needed=True,
                escalation_priority="urgent",
                policy_references=["escalation_sop.md — Đe dọa pháp lý"],
            )

        # Cancellation is generally allowed
        plan = subscription_data.get("plan", "")
        customer_id = subscription_data.get("customer_id", "")

        # Check if retention offer should be presented
        started_at = subscription_data.get("started_at", "")
        should_offer_retention = False
        if "premium" in plan.lower() and started_at:
            start_date = datetime.fromisoformat(started_at)
            months_subscribed = (datetime.fromisoformat(CURRENT_DATE) - start_date).days / 30
            if months_subscribed > 6:
                should_offer_retention = True

        return PolicyResult(
            allowed=True,
            reason="Huỷ đăng ký được duyệt. " + (
                "Nên đưa ưu đãi giữ chân (khách Premium > 6 tháng)."
                if should_offer_retention
                else "Huỷ tiêu chuẩn."
            ),
            risk_level="low",
            policy_references=["cancellation_policy.md — Cách Thức Huỷ"],
        )

    def check_ticket_creation(self, priority: str, ticket_type: str) -> PolicyResult:
        """Ticket creation is always allowed."""
        return PolicyResult(
            allowed=True,
            reason="Tạo ticket là thao tác an toàn, không liên quan tài chính.",
            risk_level="low",
            policy_references=[],
        )

    def check_notification(self, channel: str, message: str) -> PolicyResult:
        """Sending internal notifications is always allowed."""
        return PolicyResult(
            allowed=True,
            reason="Gửi thông báo nội bộ là thao tác an toàn.",
            risk_level="low",
            policy_references=[],
        )

    # ---- Internal Helpers ----

    def _detect_legal_threat(self, text: str) -> bool:
        """Detect legal threats or aggressive escalation language."""
        if not text:
            return False
        patterns = [
            r'\b(lawsuit|sue|lawyer|attorney|legal\s+action|litigation|court)\b',
            r'\b(report|complaint).*(bbb|ftc|attorney\s+general|consumer\s+protection)\b',
            r'\b(kiện|luật\s*sư|tòa\s*án|pháp\s*lý|khởi\s*kiện)\b',
            r'\b(báo\s*công\s*an|cơ\s*quan\s*chức\s*năng|bảo\s*vệ\s*người\s*tiêu\s*dùng)\b',
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def _get_latest_payment_date(self, order_data: dict) -> Optional[datetime]:
        """Extract the most recent payment date from order data."""
        payments = order_data.get("payments", [])
        if not payments:
            return None
        latest = max(payments, key=lambda p: p.get("date", ""))
        try:
            return datetime.fromisoformat(latest["date"])
        except (ValueError, KeyError):
            return None
