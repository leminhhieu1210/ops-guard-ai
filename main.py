import json
import streamlit as st
from agent.orchestrator import AgentOrchestrator

st.set_page_config(
    page_title="Gold Beauty Spa",
    page_icon="✨",
    layout="wide",
)

@st.cache_resource
def get_agent():
    return AgentOrchestrator()


def main():
    st.title("✨ Gold Beauty Spa Hỗ Trợ Khách Hàng")
    st.caption("Trợ lý AI tự động hoá quy trình hỗ trợ khách hàng")

    with st.sidebar:
        st.header("🔍 Bảng Theo Dõi Agent")

        st.divider()
        st.subheader("Kịch Bản Test Nhanh")
        scenarios = {
            "Giao hàng trễ": "Em đặt đơn #ORD-1001 mà đã trễ 5 ngày rồi. Kiểm tra giúp em với ạ?",
            "Hoàn tiền nhỏ (tự động)": "Em bị tính tiền 2 lần cho đơn #ORD-1002. Hoàn lại 90.000đ trùng giúp em ạ.",
            "Hoàn tiền lớn (chuyển tiếp)": "Em bị tính tiền trùng 2.640.000đ cho đơn #ORD-1003. Hoàn tiền ngay cho em.",
            "Huỷ gói đăng ký": "Em muốn huỷ gói Premium. Mã khách hàng C001. Em có được hoàn tiền tháng này không ạ?",
            "Đe dọa pháp lý": "Huỷ gói NGAY (C003). Bị tính 2.990.000đ và tôi sẽ kiện nếu không hoàn tiền.",
            "Đơn hàng không tồn tại": "Cho em hỏi trạng thái đơn #ORD-9999?",
            "Hỏi chính sách": "Chính sách hoàn tiền của Gold Beauty Spa là gì? Em có bao lâu để yêu cầu hoàn tiền?",
        }

        for label, message in scenarios.items():
            if st.button(label, use_container_width=True):
                st.session_state["prefill"] = message

    agent = get_agent()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_traces" not in st.session_state:
        st.session_state.agent_traces = []

    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

        if msg["role"] == "assistant" and i < len(st.session_state.agent_traces):
            trace = st.session_state.agent_traces[i]
            if trace:
                with st.expander("🔍 Quá Trình Suy Luận Của Agent", expanded=False):
                    display_trace(trace)

    prefill = st.session_state.pop("prefill", "")
    user_input = st.chat_input("Nhập câu hỏi cho Gold Beauty Spa...") or prefill

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Đang xử lý..."):
                response = agent.process_message(user_input)

            st.markdown(response.message)

            if response.escalations:
                for esc in response.escalations:
                    st.warning(f"⚠️ **Cần Chuyển Tiếp** (ưu tiên {esc['priority'].upper()})\n\n"
                               f"**Hành động:** {esc['action']}\n\n"
                               f"**Lý do:** {esc['reason']}\n\n"
                               f"**Mức rủi ro:** {esc['risk_level']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.button("✅ Phê duyệt", key=f"approve_{id(esc)}", disabled=True,
                                  help="Trong thực tế, nhân viên sẽ phê duyệt tại đây")
                    with col2:
                        st.button("❌ Từ chối", key=f"reject_{id(esc)}", disabled=True,
                                  help="Trong thực tế, nhân viên sẽ từ chối tại đây")

            with st.expander("🔍 Quá Trình Suy Luận Của Agent", expanded=False):
                display_trace(response)

        st.session_state.messages.append({"role": "assistant", "content": response.message})
        while len(st.session_state.agent_traces) < len(st.session_state.messages) - 1:
            st.session_state.agent_traces.append(None)
        st.session_state.agent_traces.append(response)


def display_trace(response):
    """Display the agent's reasoning steps."""
    for step in response.steps:
        if step.step_type == "rag_retrieval":
            st.markdown("**📚 Truy Xuất Kiến Thức**")
            if step.result and step.result.get("contexts"):
                for ctx in step.result["contexts"]:
                    st.markdown(f"- `{ctx['source']}` → {ctx['section']} (điểm: {ctx['score']})")
            else:
                st.markdown("- Không tìm thấy ngữ cảnh liên quan")

        elif step.step_type == "policy_check":
            icon = "✅" if step.result and step.result.get("allowed") else "🚫"
            risk = step.result.get("risk_level", "không rõ") if step.result else "không rõ"
            st.markdown(f"**{icon} Kiểm Tra Chính Sách** — `{step.detail.get('tool', '')}` — Rủi ro: {risk}")
            if step.result:
                st.markdown(f"  {step.result.get('reason', '')}")

        elif step.step_type == "tool_call":
            st.markdown(f"**🔧 Gọi Công Cụ** — `{step.detail.get('tool', '')}`")
            st.json(step.detail.get("args", {}))
            if step.result:
                st.json(step.result)

        elif step.step_type == "escalation":
            st.markdown(f"**⚠️ Chuyển Tiếp** — `{step.detail.get('action', '')}`")
            st.markdown(f"  Ưu tiên: {step.detail.get('priority', '')}")
            st.markdown(f"  Lý do: {step.detail.get('reason', '')}")

        elif step.step_type == "llm_response":
            st.markdown("**💬 Đã Tạo Phản Hồi**")

    if response.actions_taken:
        st.divider()
        st.markdown("**Hành Động Đã Thực Hiện:**")
        for action in response.actions_taken:
            st.markdown(f"- ✅ `{action['tool']}` — {action.get('policy', '')}")

    if response.citations:
        st.divider()
        st.markdown("**📎 Nguồn Tham Chiếu:**")
        sources = set()
        for c in response.citations:
            sources.add(f"{c['source']} — {c['section']}")
        for s in sorted(sources):
            st.markdown(f"- {s}")


if __name__ == "__main__":
    main()
