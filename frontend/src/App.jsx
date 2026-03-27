// frontend/src/App.jsx — ArthAI React Dashboard

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import {
  TrendingUp, TrendingDown, Activity, Shield, Cpu,
  MessageSquare, List, Settings, RefreshCw, AlertTriangle
} from "lucide-react";

const API = "http://localhost:8000";

// ── Helpers ────────────────────────────────────────────────────────────────────
const fmt = (n) => n?.toLocaleString("en-IN", { maximumFractionDigits: 2 }) ?? "—";
const fmtRs = (n) => `₹${fmt(n)}`;
const pnlColor = (n) => (n >= 0 ? "#1D9E75" : "#E24B4A");

// ── Components ────────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: color || "inherit" }}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

function SignalBadge({ action }) {
  const styles = {
    BUY:  { background: "#E1F5EE", color: "#0F6E56" },
    SELL: { background: "#FCEBEB", color: "#A32D2D" },
    HOLD: { background: "#FAEEDA", color: "#854F0B" },
  };
  const s = styles[action] || styles.HOLD;
  return (
    <span style={{ ...s, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 500 }}>
      {action}
    </span>
  );
}

// ── Chat Panel ─────────────────────────────────────────────────────────────────

function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Namaste! I am your ArthAI trading assistant. Ask me about NSE/BSE stocks, F&O strategies, or your portfolio." }
  ]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    try {
      const history = messages.map(m => ({ role: m.role === "assistant" ? "assistant" : "user", content: m.content }));
      const { data } = await axios.post(`${API}/api/chat`, {
        message: userMsg,
        conversation_history: history,
      });
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "API error — is the backend running?" }]);
    }
    setLoading(false);
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role === "user" ? "user" : "ai"}`}>
            {m.content}
          </div>
        ))}
        {loading && <div className="msg msg-ai msg-thinking">Analysing…</div>}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendMessage()}
          placeholder="Ask about stocks, F&O, portfolio…"
        />
        <button onClick={sendMessage} disabled={loading}>Send</button>
      </div>
    </div>
  );
}

// ── Watchlist Panel ────────────────────────────────────────────────────────────

function WatchlistPanel({ data }) {
  if (!data?.watchlist) return <div className="loading">Loading watchlist…</div>;
  return (
    <div className="card">
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th><th>LTP (₹)</th><th>Signal</th>
            <th>Confidence</th><th>Entry</th><th>SL</th><th>Target</th>
          </tr>
        </thead>
        <tbody>
          {data.watchlist.map(s => (
            <tr key={s.symbol}>
              <td><strong>{s.symbol}</strong></td>
              <td>{fmtRs(s.ltp)}</td>
              <td><SignalBadge action={s.action || "HOLD"} /></td>
              <td>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{
                    width: 48, height: 4, background: "#f0f0f0", borderRadius: 2
                  }}>
                    <div style={{
                      width: `${(s.confidence || 0) * 100}%`,
                      height: "100%",
                      background: pnlColor(s.action === "SELL" ? -1 : 1),
                      borderRadius: 2
                    }} />
                  </div>
                  <span style={{ fontSize: 11 }}>{((s.confidence || 0) * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td>{s.entry ? fmtRs(s.entry) : "—"}</td>
              <td style={{ color: "#E24B4A" }}>{s.stop_loss ? fmtRs(s.stop_loss) : "—"}</td>
              <td style={{ color: "#1D9E75" }}>{s.target ? fmtRs(s.target) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Portfolio Panel ────────────────────────────────────────────────────────────

function PortfolioPanel({ data }) {
  if (!data) return <div className="loading">Loading portfolio…</div>;
  return (
    <div>
      <div className="metrics-grid">
        <MetricCard label="Today P&L" value={fmtRs(data.today_pnl)} color={pnlColor(data.today_pnl)} />
        <MetricCard label="Open Positions" value={data.open_count} sub={`of ${data.max_positions || 15} max`} />
        <MetricCard label="Today Trades" value={data.today_trades} />
        <MetricCard label="Capital" value={fmtRs(data.capital)} />
      </div>
      {data.positions?.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <table className="data-table">
            <thead>
              <tr><th>Symbol</th><th>Action</th><th>Qty</th><th>Avg</th><th>LTP</th><th>P&L</th><th>P&L%</th></tr>
            </thead>
            <tbody>
              {data.positions.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.symbol}</strong></td>
                  <td><SignalBadge action={p.action} /></td>
                  <td>{p.qty}</td>
                  <td>{fmtRs(p.avg_price)}</td>
                  <td>{fmtRs(p.ltp)}</td>
                  <td style={{ color: pnlColor(p.pnl) }}>{fmtRs(p.pnl)}</td>
                  <td style={{ color: pnlColor(p.pnl_pct) }}>{p.pnl_pct?.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab]             = useState("portfolio");
  const [portfolio, setPortfolio] = useState(null);
  const [watchlist, setWatchlist] = useState(null);
  const [risk, setRisk]           = useState(null);
  const [loading, setLoading]     = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const [p, w, r] = await Promise.all([
        axios.get(`${API}/api/portfolio`),
        axios.get(`${API}/api/watchlist`),
        axios.get(`${API}/api/risk`),
      ]);
      setPortfolio(p.data);
      setWatchlist(w.data);
      setRisk(r.data);
    } catch (e) {
      console.error("API fetch error:", e);
    }
    setLoading(false);
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, []);

  const tabs = [
    { id: "portfolio", label: "Portfolio",  icon: <TrendingUp size={14} /> },
    { id: "watchlist", label: "Watchlist",  icon: <List size={14} /> },
    { id: "chat",      label: "AI Chat",    icon: <MessageSquare size={14} /> },
    { id: "risk",      label: "Risk",       icon: <Shield size={14} /> },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">Artha<span>AI</span></div>
        <div className="topbar-right">
          {risk?.trading_halted && (
            <span className="badge badge-red">
              <AlertTriangle size={12} /> Trading Halted
            </span>
          )}
          <span className="badge badge-green">
            <span className="pulse" /> Market Open
          </span>
          <button className="icon-btn" onClick={refresh} disabled={loading}>
            <RefreshCw size={14} className={loading ? "spin" : ""} />
          </button>
        </div>
      </header>

      <nav className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </nav>

      <main className="main-content">
        {tab === "portfolio" && <PortfolioPanel data={portfolio} />}
        {tab === "watchlist" && <WatchlistPanel data={watchlist} />}
        {tab === "chat"      && <ChatPanel />}
        {tab === "risk"      && (
          <div className="metrics-grid">
            <MetricCard label="Total Exposure" value={fmtRs(risk?.total_exposure)} />
            <MetricCard label="Exposure %" value={`${risk?.exposure_pct ?? 0}%`} />
            <MetricCard label="Total Risk" value={fmtRs(risk?.total_risk)} color="#E24B4A" />
            <MetricCard label="Loss Buffer Used" value={`${risk?.loss_buffer_used ?? 0}%`} color={pnlColor(-(risk?.loss_buffer_used ?? 0))} />
          </div>
        )}
      </main>
    </div>
  );
}
