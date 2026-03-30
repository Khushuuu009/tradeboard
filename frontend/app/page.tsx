"use client";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";

const API_URL = "http://localhost:8000/api";
const WS_URL  = "ws://localhost:8000/ws";

const INDICES = [
  { key: "NIFTY",     label: "NIFTY 50",  color: "#00d4aa" },
  { key: "BANKNIFTY", label: "BANKNIFTY", color: "#f59e0b" },
  { key: "SENSEX",    label: "SENSEX",    color: "#6366f1" },
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#1a1f2e", border: "1px solid #2a3441", borderRadius: 6, padding: "8px 12px", fontSize: 11 }}>
      <div style={{ color: "#6b7280", marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color, fontWeight: 700 }}>
          {p.name}: {p.value?.toFixed(2)}
        </div>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [activeIndex, setActiveIndex] = useState("NIFTY");
  const [spot, setSpot]               = useState<number | null>(null);
  const [ce, setCe]                   = useState<number | null>(null);
  const [pe, setPe]                   = useState<number | null>(null);
  const [straddle, setStraddle]       = useState<number | null>(null);
  const [atm, setAtm]                 = useState<number | null>(null);
  const [expiry, setExpiry]           = useState<string | null>(null);
  const [openP, setOpenP]             = useState<number | null>(null);
  const [highP, setHighP]             = useState<number | null>(null);
  const [lowP, setLowP]               = useState<number | null>(null);
  const [ltt, setLtt]                 = useState<string | null>(null);
  const [newsData, setNewsData]       = useState<any[]>([]);
  const [vwapData, setVwapData]       = useState<any>(null);
  const [activeTab, setActiveTab]     = useState("straddle");
  const [currentTime, setCurrentTime] = useState("");
  const [chartData, setChartData]     = useState<any[]>([]);
  const [wsStatus, setWsStatus]       = useState<"connecting"|"connected"|"disconnected">("connecting");
  const [optionChain, setOptionChain] = useState<any[]>([]);
  const wsRef                         = useRef<WebSocket | null>(null);
  const lastMinute                    = useRef<string>("");

  // Clock
  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true
      }));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // WebSocket
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      setWsStatus("connecting");

      ws.onopen = () => setWsStatus("connected");

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // ── Full history on connect ──
          if (data.type === "history") {
            setChartData(data.data || []);
            return;
          }

          // ── Live tick ──
          if (data.type !== "tick" && data.type !== "straddle" && data.type !== "spot") return;

          if (data.spot     != null) setSpot(data.spot);
          if (data.ce       != null) setCe(data.ce);
          if (data.pe       != null) setPe(data.pe);
          if (data.straddle != null) setStraddle(data.straddle);
          if (data.atm      != null) setAtm(data.atm);
          if (data.expiry   != null) setExpiry(data.expiry);
          if (data.open     != null) setOpenP(data.open);
          if (data.high     != null) setHighP(data.high);
          if (data.low      != null) setLowP(data.low);
          if (data.time     != null) setLtt(data.time);

          // Add chart point every minute (frontend also tracks for live session)
          if (data.straddle != null && data.spot != null) {
            const now = new Date().toLocaleTimeString("en-IN", {
              hour: "2-digit", minute: "2-digit", hour12: true
            });
            if (now !== lastMinute.current) {
              lastMinute.current = now;
              setChartData(prev => {
                const last = prev[prev.length - 1];
                if (last?.time === now) return prev; // already added
                return [...prev, {
                  time:     now,
                  straddle: data.straddle,
                  spot:     data.spot,
                  ce:       data.ce,
                  pe:       data.pe,
                }].slice(-500);
              });
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => wsRef.current?.close();
  }, []);

  // Option chain every 5s
  useEffect(() => {
    const fetchChain = async () => {
      try {
        const res = await axios.get(`${API_URL}/live-straddle?symbol=${activeIndex}`);
        if (res.data.status === "success") {
          setOptionChain(res.data.option_chain || []);
          if (!spot) {
            setSpot(res.data.spot);
            setCe(res.data.ce_price);
            setPe(res.data.pe_price);
            setStraddle(res.data.straddle);
            setAtm(res.data.atm);
            setExpiry(res.data.expiry);
          }
        }
      } catch {}
    };
    fetchChain();
    const i = setInterval(fetchChain, 5000);
    return () => clearInterval(i);
  }, [activeIndex]);

  // News + VWAP
  useEffect(() => {
    const fetchNews = async () => { try { const r = await axios.get(`${API_URL}/news`); setNewsData(r.data.news || []); } catch {} };
    const fetchVwap = async () => { try { const r = await axios.get(`${API_URL}/vwap`); setVwapData(r.data); } catch {} };
    fetchNews(); fetchVwap();
    const i1 = setInterval(fetchNews, 300000);
    const i2 = setInterval(fetchVwap, 30000);
    return () => { clearInterval(i1); clearInterval(i2); };
  }, []);

  const activeColor = INDICES.find(i => i.key === activeIndex)?.color || "#00d4aa";

  const getDTE = () => {
    if (!expiry) return "—";
    const diff = Math.ceil((new Date(expiry).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
    return diff >= 0 ? diff : 0;
  };

  const synFut = atm && ce && pe ? Math.round((atm + ce - pe) * 100) / 100 : null;
  const prices = chartData.map(d => d.straddle).filter(Boolean);
  const yMin   = prices.length ? Math.floor(Math.min(...prices) - 5)  : "auto";
  const yMax   = prices.length ? Math.ceil(Math.max(...prices)  + 10) : "auto";
  const wsColor = wsStatus === "connected" ? "#00d4aa" : wsStatus === "connecting" ? "#f59e0b" : "#ef4444";
  const wsLabel = wsStatus === "connected" ? "● LIVE" : wsStatus === "connecting" ? "◌ CONNECTING" : "● CLOSED";

  return (
    <main style={{ minHeight: "100vh", background: "#12161e", color: "#e2e8f0", fontFamily: "system-ui, sans-serif" }}>

      {/* NAV */}
      <nav style={{ background: "#0d1117", borderBottom: "1px solid #1e2530", padding: "10px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 18, fontWeight: 800, color: activeColor, letterSpacing: 1 }}>⬡ TradeBoard</span>
          <div style={{ display: "flex", gap: 4 }}>
            {INDICES.map(idx => (
              <button key={idx.key} onClick={() => setActiveIndex(idx.key)} style={{
                padding: "4px 14px", borderRadius: 6, fontSize: 12, fontWeight: 700,
                border: `1px solid ${activeIndex === idx.key ? idx.color : "#2a3441"}`,
                background: activeIndex === idx.key ? `${idx.color}20` : "transparent",
                color: activeIndex === idx.key ? idx.color : "#6b7280",
                cursor: "pointer",
              }}>
                {idx.label}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <a href="/research" style={{ fontSize: 11, color: "#6b7280", textDecoration: "none" }}>🔬 Research</a>
          <span style={{ fontSize: 12, color: "#4b5563" }}>{currentTime}</span>
          <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20, fontWeight: 700, background: `${wsColor}15`, color: wsColor, border: `1px solid ${wsColor}30` }}>
            {wsLabel}
          </span>
        </div>
      </nav>

      {/* INFO BAR */}
      <div style={{ background: "#0d1117", borderBottom: "1px solid #1e2530", padding: "8px 24px" }}>
        <div style={{ display: "flex", gap: 28, flexWrap: "wrap", alignItems: "center" }}>
          {[
            { label: "DTE",      value: getDTE(),                       color: "#f59e0b"   },
            { label: "SPOT",     value: spot?.toLocaleString("en-IN"),  color: "#e2e8f0"   },
            { label: "OPEN",     value: openP?.toLocaleString("en-IN"), color: "#94a3b8"   },
            { label: "HIGH",     value: highP?.toLocaleString("en-IN"), color: "#4ade80"   },
            { label: "LOW",      value: lowP?.toLocaleString("en-IN"),  color: "#f87171"   },
            { label: "ATM",      value: atm?.toLocaleString("en-IN"),   color: "#e2e8f0"   },
            { label: "STRADDLE", value: straddle,                       color: activeColor },
            { label: "CE",       value: ce,                             color: "#4ade80"   },
            { label: "PE",       value: pe,                             color: "#f87171"   },
            { label: "SYN FUT",  value: synFut?.toLocaleString("en-IN"),color: "#a78bfa"   },
            { label: "EXPIRY",   value: expiry,                         color: "#6b7280"   },
          ].map(item => (
            <div key={item.label} style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <span style={{ fontSize: 9, color: "#4b5563", fontWeight: 700, letterSpacing: 1 }}>{item.label}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: item.color }}>{item.value ?? "—"}</span>
            </div>
          ))}
        </div>
      </div>

      {/* TABS */}
      <div style={{ padding: "12px 24px 0", display: "flex", gap: 8 }}>
        {[
          { id: "straddle", label: "📊 Straddle" },
          { id: "news",     label: "📰 News"     },
          { id: "vwap",     label: "📈 VWAP"     },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            padding: "6px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
            border: `1px solid ${activeTab === tab.id ? activeColor : "#1e2530"}`,
            background: activeTab === tab.id ? `${activeColor}15` : "transparent",
            color: activeTab === tab.id ? activeColor : "#6b7280",
            cursor: "pointer",
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ padding: "16px 24px" }}>

        {/* STRADDLE TAB */}
        {activeTab === "straddle" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>

            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>

              {/* Chart */}
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: "12px 12px 0 0", padding: "20px 8px 12px 8px", position: "relative" }}>
                <div style={{
                  position: "absolute", top: "50%", left: "50%",
                  transform: "translate(-50%, -50%)",
                  fontSize: 48, fontWeight: 900, color: "#1e2530",
                  pointerEvents: "none", userSelect: "none", letterSpacing: 4,
                }}>
                  {activeIndex}
                </div>

                {chartData.length < 2 ? (
                  <div style={{ height: 380, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
                    <div style={{ fontSize: 36 }}>📊</div>
                    <div style={{ color: "#4b5563", fontSize: 13 }}>
                      {wsStatus === "connecting" ? "Connecting to live feed..." : "Chart builds minute by minute from 9:15 AM"}
                    </div>
                    {straddle && <div style={{ color: activeColor, fontSize: 32, fontWeight: 800, marginTop: 8 }}>{straddle}</div>}
                    {spot     && <div style={{ color: "#94a3b8", fontSize: 16, marginTop: 4 }}>Spot: {spot?.toLocaleString("en-IN")}</div>}
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={380}>
                    <AreaChart data={chartData} margin={{ top: 10, right: 70, left: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={activeColor} stopOpacity={0.2}/>
                          <stop offset="95%" stopColor={activeColor} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a1f2a" vertical={false}/>
                      <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#4b5563" }} tickLine={false} axisLine={{ stroke: "#1e2530" }} interval="preserveStartEnd"/>
                      <YAxis domain={[yMin, yMax]} tick={{ fontSize: 10, fill: "#4b5563" }} tickLine={false} axisLine={false} width={55}/>
                      <Tooltip content={<CustomTooltip/>}/>
                      <Area type="monotone" dataKey="straddle" name="Straddle" stroke={activeColor} strokeWidth={2} fill="url(#grad)" dot={false} activeDot={{ r: 4, fill: activeColor }}/>
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Bottom bar */}
              <div style={{
                background: "#0d1117", border: "1px solid #1e2530", borderTop: "none",
                borderRadius: "0 0 12px 12px", padding: "12px 20px",
                display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 8,
              }}>
                {[
                  { label: "Straddle",       value: straddle,                        color: activeColor },
                  { label: "Spot",           value: spot?.toLocaleString("en-IN"),   color: "#e2e8f0"   },
                  { label: "Syn Future",     value: synFut?.toLocaleString("en-IN"), color: "#a78bfa"   },
                  { label: "ATM Strike",     value: atm?.toLocaleString("en-IN"),    color: "#e2e8f0"   },
                  { label: `${atm ?? ""}CE`, value: ce,                              color: "#4ade80"   },
                  { label: `${atm ?? ""}PE`, value: pe,                              color: "#f87171"   },
                  { label: "DTE",            value: getDTE(),                        color: "#f59e0b"   },
                  { label: "Updated",        value: ltt,                             color: "#6b7280"   },
                ].map(item => (
                  <div key={item.label} style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: item.color }}>{item.value ?? "—"}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Option Chain */}
            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #1e2530", display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#e2e8f0" }}>OPTION CHAIN</span>
                <span style={{ fontSize: 10, color: activeColor, fontWeight: 700 }}>{expiry ?? "—"}</span>
              </div>
              <div style={{ overflowY: "auto", maxHeight: 520 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #1e2530", background: "#0d1117", position: "sticky", top: 0 }}>
                      {[
                        { h: "Calls",    a: "left"   as const, c: "#4ade80" },
                        { h: "Strike",   a: "center" as const, c: "#94a3b8" },
                        { h: "Puts",     a: "right"  as const, c: "#f87171" },
                        { h: "Straddle", a: "right"  as const, c: "#f59e0b" },
                      ].map(col => (
                        <th key={col.h} style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, letterSpacing: 1, textAlign: col.a, color: col.c }}>{col.h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.length > 0 ? (
                      optionChain.map((row: any, i: number) => {
                        const isAtm = row.strike === atm;
                        return (
                          <tr key={i} style={{ borderBottom: "1px solid #141820", background: isAtm ? `${activeColor}12` : i % 2 === 0 ? "#0a0d13" : "transparent" }}>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? "#4ade80" : "#22c55e50", textAlign: "left" }}>
                              {isAtm ? ce?.toFixed(2) : row.ce_price?.toFixed(2)}
                            </td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: 700, color: isAtm ? activeColor : "#64748b", textAlign: "center" }}>
                              {row.strike}
                              {isAtm && <span style={{ marginLeft: 4, fontSize: 9, background: `${activeColor}25`, color: activeColor, padding: "1px 5px", borderRadius: 3 }}>ATM</span>}
                            </td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? "#f87171" : "#ef444450", textAlign: "right" }}>
                              {isAtm ? pe?.toFixed(2) : row.pe_price?.toFixed(2)}
                            </td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? activeColor : "#78350f", textAlign: "right" }}>
                              {isAtm ? straddle?.toFixed(2) : row.straddle?.toFixed(2)}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr><td colSpan={4} style={{ padding: 32, textAlign: "center", color: "#4b5563", fontSize: 12 }}>
                        {wsStatus === "connecting" ? "Connecting..." : "Market closed — data at 9:15 AM"}
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* NEWS TAB */}
        {activeTab === "news" && (
          <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <span style={{ fontSize: 14, fontWeight: 700 }}>Market News</span>
              <span style={{ fontSize: 10, color: "#4b5563" }}>Refreshes every 5 mins</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 600, overflowY: "auto" }}>
              {newsData.length === 0 ? (
                <p style={{ color: "#4b5563", textAlign: "center", padding: 32 }}>Loading news...</p>
              ) : newsData.map((news: any, i: number) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: 12, borderRadius: 8, background: "#131920", border: "1px solid #1e2530" }}>
                  <span style={{ fontSize: 20 }}>{news.emoji}</span>
                  <div>
                    <a href={news.link} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, color: "#e2e8f0", textDecoration: "none", fontWeight: 500 }}>{news.title}</a>
                    <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                      <span style={{ fontSize: 10, color: "#4b5563" }}>{news.source}</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: news.impact === "HIGH" ? "#f87171" : news.impact === "MEDIUM" ? "#f59e0b" : "#4ade80" }}>{news.impact}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* VWAP TAB */}
        {activeTab === "vwap" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>INTRADAY VWAP</div>
              <div style={{ fontSize: 36, fontWeight: 800, color: "#6366f1" }}>{vwapData?.intraday_vwap ?? "N/A"}</div>
              <div style={{ marginTop: 8, fontSize: 13, color: "#94a3b8" }}>{vwapData?.intraday_bias ?? vwapData?.message ?? "Market closed"}</div>
            </div>
            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>TREND SIGNAL</div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#f59e0b" }}>{vwapData?.trend_signal?.signal ?? "N/A"}</div>
              <div style={{ marginTop: 8, fontSize: 13, color: "#94a3b8" }}>{vwapData?.trend_signal?.description ?? ""}</div>
              <div style={{ marginTop: 8, fontSize: 13 }}>
                Straddle Bias: <span style={{ color: "#4ade80", fontWeight: 700 }}>{vwapData?.trend_signal?.straddle_bias ?? "N/A"}</span>
              </div>
            </div>
          </div>
        )}

      </div>
    </main>
  );
}