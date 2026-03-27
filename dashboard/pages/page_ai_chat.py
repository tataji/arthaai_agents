"""
dashboard/pages/page_ai_chat.py — Claude AI Trading Assistant
"""

import os
import sys
import streamlit as st
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


SYSTEM_PROMPT = """You are ArthAI, an expert AI trading assistant for Indian stock markets (NSE and BSE).
You have deep expertise in:
- Indian equity markets: NIFTY 50, SENSEX, BANK NIFTY, FINNIFTY, sector indices
- F&O trading: index/stock options, Greeks (delta, theta, gamma, vega), strategies (Iron Condor, Bull Call Spread, Straddle, etc.)
- Technical analysis: RSI, MACD, Bollinger Bands, Fibonacci, support/resistance, candlestick patterns
- Fundamental analysis: PE, EV/EBITDA, ROE, debt ratios for Indian companies (SEBI filings, screener.in data)
- SEBI regulations, circuit breakers, margin requirements, T+1 settlement
- Macro: RBI monetary policy, INR/USD, FII/DII flows, GST data, IIP, CPI

Response style:
- Specific and actionable (not generic)
- Use Indian number system (lakhs, crores) and ₹ symbol
- Structure trade ideas clearly: Entry | Stop Loss | Target | Rationale
- Add brief risk disclaimer where relevant
- Be concise — respect the trader's time"""

QUICK_PROMPTS = [
    "Analyse RELIANCE for a swing trade",
    "Top NSE momentum stocks today",
    "Best F&O strategy for current VIX 13?",
    "Review NIFTY 50 trend & key levels",
    "Explain Iron Condor with an example",
    "HDFCBANK vs ICICIBANK — which to buy?",
    "What is the PCR indicating today?",
    "Suggest a portfolio rebalancing strategy",
]


def render():
    st.markdown('<div class="page-title">🤖 AI Trading Assistant</div>', unsafe_allow_html=True)
    st.caption("Powered by Claude · Ask anything about NSE/BSE markets")

    # ── Layout ────────────────────────────────────────────────────────────────
    col_chat, col_context = st.columns([3, 1])

    with col_chat:
        # ── Quick prompts ──────────────────────────────────────────────────────
        st.markdown("**Quick prompts**")
        cols = st.columns(4)
        for i, prompt in enumerate(QUICK_PROMPTS):
            with cols[i % 4]:
                if st.button(prompt, key=f"qp_{i}", use_container_width=True):
                    _add_message("user", prompt)
                    _call_claude(prompt)
                    st.rerun()

        st.divider()

        # ── Chat history ───────────────────────────────────────────────────────
        history = st.session_state.get("chat_history", [])
        chat_html = '<div class="chat-container">'
        for msg in history:
            css_class = "chat-msg-user" if msg["role"] == "user" else "chat-msg-ai"
            content   = msg["content"].replace("<", "&lt;").replace(">", "&gt;")
            chat_html += f'<div class="{css_class}">{content}</div>'
        chat_html += "</div>"
        st.markdown(chat_html, unsafe_allow_html=True)

        if st.session_state.get("chat_loading"):
            st.markdown(
                '<div class="chat-msg-thinking">Analysing market data…</div>',
                unsafe_allow_html=True,
            )

        # ── Input ──────────────────────────────────────────────────────────────
        with st.form("chat_form", clear_on_submit=True):
            col_in, col_btn = st.columns([5, 1])
            with col_in:
                user_input = st.text_input(
                    "Message",
                    placeholder="Ask about stocks, F&O, technical analysis…",
                    label_visibility="collapsed",
                )
            with col_btn:
                submit = st.form_submit_button("Send ↗", use_container_width=True, type="primary")

        if submit and user_input.strip():
            _add_message("user", user_input.strip())
            _call_claude(user_input.strip())
            st.rerun()

        # ── Clear chat ──────────────────────────────────────────────────────────
        if len(history) > 1:
            if st.button("🗑 Clear conversation", type="secondary"):
                st.session_state["chat_history"] = [history[0]]
                st.rerun()

    with col_context:
        # ── Market context panel ───────────────────────────────────────────────
        st.markdown("**Live Context**")
        from dashboard.services.data_service import get_market_overview
        mkt = get_market_overview()

        items = [
            ("NIFTY 50",   mkt["nifty50"]),
            ("SENSEX",     mkt["sensex"]),
            ("BANK NIFTY", mkt["banknifty"]),
            ("INDIA VIX",  mkt["india_vix"]),
        ]
        for label, d in items:
            chg   = d["chg_pct"]
            color = "#059669" if chg >= 0 else "#dc2626"
            sign  = "+" if chg >= 0 else ""
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;font-size:12px;
     padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05)">
  <span style="color:#6b7280">{label}</span>
  <span style="color:{color};font-weight:500">{sign}{chg:.2f}%</span>
</div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        fii = mkt["fii_net"]
        dii = mkt["dii_net"]
        st.markdown(f"""
<div style="font-size:12px">
  <div style="color:#6b7280;font-size:11px;margin-bottom:4px">FII / DII FLOW TODAY</div>
  <div style="color:{'#059669' if fii >= 0 else '#dc2626'}">
    FII: ₹{abs(fii):,.0f}Cr {'▲' if fii >= 0 else '▼'}
  </div>
  <div style="color:{'#059669' if dii >= 0 else '#dc2626'}">
    DII: ₹{abs(dii):,.0f}Cr {'▲' if dii >= 0 else '▼'}
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Conversation Stats**")
        user_msgs = sum(1 for m in history if m["role"] == "user")
        st.caption(f"{user_msgs} messages · {len(history)} total")

        if st.button("Export Chat", use_container_width=True):
            text = "\n\n".join(
                f"[{m['role'].upper()}]: {m['content']}" for m in history
            )
            st.download_button(
                "📥 Download .txt",
                data=text,
                file_name=f"arthaai_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )


def _add_message(role: str, content: str):
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    st.session_state["chat_history"].append({"role": role, "content": content})


def _call_claude(user_msg: str):
    api_key = st.session_state.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        _add_message("assistant",
                     "⚠️ No API key configured. Add your Anthropic API key in **Settings**.")
        return

    st.session_state["chat_loading"] = True
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        history = st.session_state.get("chat_history", [])
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]

        response = client.messages.create(
            model=st.session_state.get("claude_model", "claude-sonnet-4-20250514"),
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        reply = response.content[0].text
        _add_message("assistant", reply)
    except Exception as e:
        _add_message("assistant", f"❌ Error: {e}\n\nCheck your API key in Settings.")
    finally:
        st.session_state["chat_loading"] = False
