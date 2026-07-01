"use client";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";
import { createChart, ColorType, CandlestickSeries, LineSeries, IChartApi, ISeriesApi, UTCTimestamp, LineData } from "lightweight-charts";

const API_URL = "http://127.0.0.1:8000/api";
const WS_URL = "ws://127.0.0.1:8000/ws";

const INDICES = [
  { key: "NIFTY", label: "NIFTY 50", color: "#00d4aa" },
  { key: "BANKNIFTY", label: "BANKNIFTY", color: "#f59e0b" },
  { key: "SENSEX", label: "SENSEX", color: "#6366f1" },
];

const TIMEFRAMES = ['1S', '30S', '1M', '3M', '5M', '10M', '15M', '30M', '1H'];

// ---- Custom Tooltip ----
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

export default function Page() {
  // ---- Existing state ----
  const [activeIndex, setActiveIndex] = useState("NIFTY");
  const [spot, setSpot] = useState<number | null>(null);
  const [ce, setCe] = useState<number | null>(null);
  const [pe, setPe] = useState<number | null>(null);
  const [straddle, setStraddle] = useState<number | null>(null);
  const [straddleVwap, setStraddleVwap] = useState<number | null>(null);
  const [atm, setAtm] = useState<number | null>(null);
  const [expiry, setExpiry] = useState<string | null>(null);
  const [openP, setOpenP] = useState<number | null>(null);
  const [highP, setHighP] = useState<number | null>(null);
  const [lowP, setLowP] = useState<number | null>(null);
  const [ltt, setLtt] = useState<string | null>(null);
  const [newsData, setNewsData] = useState<any[]>([]);
  const [vwapData, setVwapData] = useState<any>(null);
  const [maxPainData, setMaxPainData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("straddle");
  const [currentTime, setCurrentTime] = useState("");
  const [chartData, setChartData] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [optionChain, setOptionChain] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const lastMinute = useRef<string>("");

  // ---- Chart state ----
  const [activeTimeframe, setActiveTimeframe] = useState<'1S' | '30S' | '1M' | '3M' | '5M' | '10M' | '15M' | '30M' | '1H'>('1S');
  const [candleCache, setCandleCache] = useState<Record<string, any[]>>({});
  const [vwapLineData, setVwapLineData] = useState<{ time: number; value: number }[]>([]);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const lastStraddleRef = useRef<number | null>(null);

  // ---- Clock ----
  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true
      }));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // ---- Helper: timeframe to seconds ----
  function getTimeframeSeconds(tf: string): number {
    const map: Record<string, number> = {
      '1S': 1, '30S': 30, '1M': 60, '3M': 180, '5M': 300,
      '10M': 600, '15M': 900, '30M': 1800, '1H': 3600
    };
    return map[tf] || 60;
  }

  // ---- NEW: Send symbol change to backend when activeIndex changes ----
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "set_symbol",
        symbol: activeIndex
      }));
      console.log(`📡 Sent symbol change to backend: ${activeIndex}`);
    }
  }, [activeIndex]);

  // ---- WebSocket ----
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      setWsStatus("connecting");

      ws.onopen = () => {
        setWsStatus("connected");
        // Send current symbol on connect
        ws.send(JSON.stringify({
          type: "set_symbol",
          symbol: activeIndex
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // ---- history (1‑min snapshots) ----
          if (data.type === "history") {
            setChartData(data.data || []);
            return;
          }

          // ---- initial_candles ----
          if (data.type === "initial_candles") {
            setCandleCache(prev => {
              const newCache = { ...prev };
              Object.entries(data.data).forEach(([tf, candle]) => {
                if (!candle || typeof candle !== 'object' || !('time' in candle)) return;
                const current = newCache[tf] || [];
                const last = current[current.length - 1];
                if (last && last.time === candle.time) {
                  newCache[tf] = [...current.slice(0, -1), candle];
                } else {
                  newCache[tf] = [...current, candle];
                }
              });
              return newCache;
            });
            return;
          }

          // ---- historical_candles ----
          if (data.type === "historical_candles") {
            setCandleCache(prev => {
              const newCache = { ...prev };
              Object.entries(data.data).forEach(([tf, candlesData]) => {
                const candlesArray = Array.isArray(candlesData) ? candlesData : [candlesData];
                const current = newCache[tf] || [];
                const combined = [...current, ...candlesArray];
                const unique = combined.filter(
                  (c, idx, self) => self.findIndex(c2 => c2.time === c.time) === idx
                );
                newCache[tf] = unique.sort((a, b) => a.time - b.time).slice(-1000);
              });
              return newCache;
            });
            return;
          }

          // ---- candles (finalized) ----
          if (data.type === "candles") {
            setCandleCache(prev => {
              const newCache = { ...prev };
              Object.entries(data.data).forEach(([tf, candle]) => {
                const finalCandle = Array.isArray(candle) ? candle[candle.length - 1] : candle;
                if (!finalCandle || typeof finalCandle !== 'object' || !('time' in finalCandle)) return;
                const current = newCache[tf] || [];
                const last = current[current.length - 1];
                if (last && last.time === finalCandle.time) {
                  newCache[tf] = [...current.slice(0, -1), finalCandle];
                } else {
                  newCache[tf] = [...current, finalCandle];
                }
                if (newCache[tf].length > 1000) newCache[tf] = newCache[tf].slice(-1000);
              });
              return newCache;
            });
            return;
          }

          // ---- vwap_reset ----
          if (data.type === "vwap_reset") {
            setVwapLineData([]);
            console.log(`🔄 VWAP reset for new ATM: ${data.new_atm}`);
            return;
          }

          // ---- symbol_changed ----
          if (data.type === "symbol_changed") {
            console.log(`✅ Backend confirmed symbol switch to: ${data.symbol}`);
            return;
          }

          // ---- Live tick ----
          if (data.type !== "tick") return;

          if (data.spot != null) setSpot(data.spot);
          if (data.ce != null) setCe(data.ce);
          if (data.pe != null) setPe(data.pe);
          if (data.straddle != null) {
            setStraddle(data.straddle);
            lastStraddleRef.current = data.straddle;
          }
          if (data.straddle_vwap != null) setStraddleVwap(data.straddle_vwap);
          if (data.atm != null) setAtm(data.atm);
          if (data.expiry != null) setExpiry(data.expiry);
          if (data.open != null) setOpenP(data.open);
          if (data.high != null) setHighP(data.high);
          if (data.low != null) setLowP(data.low);
          if (data.time != null) setLtt(data.time);

          if (data.vwap != null) {
            setVwapData((prev: any) => ({ ...prev, vwap: data.vwap, bias: data.vwap_bias }));
          }

          // ---- Update VWAP line data ----
          if (data.straddle_vwap != null) {
            const ts = Math.floor(Date.now() / 1000);
            setVwapLineData(prev => {
              const last = prev[prev.length - 1];
              if (last && last.time === ts) {
                return [...prev.slice(0, -1), { time: ts, value: data.straddle_vwap }];
              }
              return [...prev, { time: ts, value: data.straddle_vwap }];
            });
          }

          // ---- Real‑time candle update ----
          if (data.straddle != null) {
            const price = data.straddle;
            const ts = Date.now();
            const tfSeconds = getTimeframeSeconds(activeTimeframe);
            const bucketStart = Math.floor(ts / 1000 / tfSeconds) * tfSeconds;

            setCandleCache(prev => {
              const cache = { ...prev };
              const candles = cache[activeTimeframe] || [];
              if (candles.length === 0) {
                cache[activeTimeframe] = [{
                  time: bucketStart,
                  open: price,
                  high: price,
                  low: price,
                  close: price,
                  volume: 1
                }];
                return cache;
              }
              const last = candles[candles.length - 1];
              if (last.time === bucketStart) {
                const updated = {
                  ...last,
                  high: Math.max(last.high, price),
                  low: Math.min(last.low, price),
                  close: price,
                  volume: last.volume + 1
                };
                cache[activeTimeframe] = [...candles.slice(0, -1), updated];
              } else {
                cache[activeTimeframe] = [...candles, {
                  time: bucketStart,
                  open: price,
                  high: price,
                  low: price,
                  close: price,
                  volume: 1
                }];
              }
              return cache;
            });
          }

          // ---- 1‑min backup chart point ----
          if (data.straddle != null && data.spot != null) {
            const now = new Date().toLocaleTimeString("en-IN", {
              hour: "2-digit", minute: "2-digit", hour12: true
            });
            if (now !== lastMinute.current) {
              lastMinute.current = now;
              setChartData(prev => {
                const last = prev[prev.length - 1];
                if (last?.time === now) return prev;
                return [...prev, {
                  time: now,
                  straddle: data.straddle,
                  spot: data.spot,
                  ce: data.ce,
                  pe: data.pe,
                }].slice(-500);
              });
            }
          }
        } catch (err) {
          console.error("WebSocket message error:", err);
        }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => wsRef.current?.close();
  }, [activeIndex]);

  // ---- Option chain ----
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
          if (res.data.vwap) {
            setVwapData((prev: any) => ({ ...prev, vwap: res.data.vwap, bias: res.data.vwap_bias, spot: res.data.spot }));
          }
        }
      } catch (err) {
        console.error("Option chain fetch error:", err);
      }
    };
    fetchChain();
    const i = setInterval(fetchChain, 5000);
    return () => clearInterval(i);
  }, [activeIndex, spot]);

  // ---- News + VWAP + Max Pain ----
  useEffect(() => {
    const fetchNews = async () => {
      try { const r = await axios.get(`${API_URL}/news`); setNewsData(r.data.news || []); } catch (err) { console.error("News fetch error:", err); }
    };
    const fetchVwap = async () => {
      try { const r = await axios.get(`${API_URL}/vwap`); setVwapData(r.data); } catch (err) { console.error("VWAP fetch error:", err); }
    };
    const fetchMaxPain = async () => {
      try {
        const res = await axios.get(`${API_URL}/max-pain?symbol=${activeIndex}`);
        if (res.data.status === "success") {
          setMaxPainData(res.data);
        }
      } catch (err) {
        console.error("Max pain fetch error:", err);
      }
    };

    fetchNews();
    fetchVwap();
    fetchMaxPain();

    const i1 = setInterval(fetchNews, 300000);
    const i2 = setInterval(fetchVwap, 30000);
    const i3 = setInterval(fetchMaxPain, 30000);

    return () => {
      clearInterval(i1);
      clearInterval(i2);
      clearInterval(i3);
    };
  }, [activeIndex]);

  // ---- Chart initialisation ----
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;
    if (container.clientWidth === 0 || container.clientHeight === 0) {
      console.warn('Chart container has zero size – retrying...');
      const timeout = setTimeout(() => {
        if (container.clientWidth > 0 && container.clientHeight > 0) {
          window.dispatchEvent(new Event('resize'));
        }
      }, 100);
      return () => clearTimeout(timeout);
    }

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#131722' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#2a2e39' },
        horzLines: { color: '#2a2e39' },
      },
      crosshair: { mode: 0 },
      timeScale: {
        borderColor: '#2a2e39',
        timeVisible: true,
        secondsVisible: true,
      },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    const vwapSeries = chart.addSeries(LineSeries, {
      color: '#ff00ff',
      lineWidth: 3,
      priceLineVisible: false,
      lastValueVisible: true,
      title: 'Straddle VWAP',
    });

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    vwapSeriesRef.current = vwapSeries;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.resize(chartContainerRef.current.clientWidth, chartContainerRef.current.clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // ---- Update candle chart (FIXED) ----
  useEffect(() => {
    if (!seriesRef.current) return;

    const candles = candleCache[activeTimeframe] || [];
    if (candles.length === 0) {
      try { seriesRef.current.setData([]); } catch (_) {}
      return;
    }

    const validCandles = candles.filter(
      (c) =>
        c != null &&
        typeof c === 'object' &&
        c.time != null &&
        !isNaN(c.time) &&
        c.open != null &&
        !isNaN(c.open) &&
        c.high != null &&
        !isNaN(c.high) &&
        c.low != null &&
        !isNaN(c.low) &&
        c.close != null &&
        !isNaN(c.close)
    );

    if (validCandles.length === 0) {
      try { seriesRef.current.setData([]); } catch (_) {}
      return;
    }

    const sorted = [...validCandles].sort((a, b) => a.time - b.time);
    const deduped = sorted.filter((c, i, arr) => i === 0 || arr[i - 1].time !== c.time);

    if (deduped.length === 0) {
      try { seriesRef.current.setData([]); } catch (_) {}
      return;
    }

    const data = deduped.map(c => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    try {
      seriesRef.current.setData(data);
      chartRef.current?.timeScale().fitContent();
    } catch (err) {
      console.error('❌ Error setting candle data:', err);
      try {
        const fallback = data.slice(-100);
        seriesRef.current.setData(fallback);
        chartRef.current?.timeScale().fitContent();
      } catch (_) {}
    }
  }, [candleCache, activeTimeframe]);

  // ---- Update VWAP line (FIXED) ----
  useEffect(() => {
    if (!vwapSeriesRef.current) {
      console.warn('⏳ VWAP series not ready yet – skipping update');
      return;
    }

    if (!vwapLineData || vwapLineData.length === 0) {
      try { vwapSeriesRef.current.setData([]); } catch (_) {}
      return;
    }

    const validData = vwapLineData
      .map((d) => {
        const time = Math.floor(Number(d.time));
        const value = Number(d.value);
        if (isNaN(time) || !isFinite(time) || isNaN(value) || !isFinite(value)) {
          return null;
        }
        return { time, value };
      })
      .filter((d): d is { time: number; value: number } => d !== null)
      .sort((a, b) => a.time - b.time)
      .filter((d, i, arr) => i === 0 || arr[i - 1].time !== d.time);

    if (validData.length === 0) {
      try { vwapSeriesRef.current.setData([]); } catch (_) {}
      return;
    }

    try {
      vwapSeriesRef.current.setData(validData as LineData<UTCTimestamp>[]);
      setTimeout(() => {
        chartRef.current?.timeScale().fitContent();
      }, 50);
    } catch (err) {
      console.error('❌ Error setting VWAP data:', err);
      try {
        vwapSeriesRef.current.setData([]);
        const fallback = validData.slice(-100);
        vwapSeriesRef.current.setData(fallback as LineData<UTCTimestamp>[]);
      } catch (_) {}
    }
  }, [vwapLineData]);

  // ---- Helpers ----
  const activeColor = INDICES.find(i => i.key === activeIndex)?.color || "#00d4aa";

  const getDTE = () => {
    if (!expiry) return "—";
    const diff = Math.ceil((new Date(expiry).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
    return diff >= 0 ? diff : 0;
  };

  const synFut = atm && ce && pe ? Math.round((atm + ce - pe) * 100) / 100 : null;
  const prices = chartData.map(d => d.straddle).filter(Boolean);
  const yMin = prices.length ? Math.floor(Math.min(...prices) - 5) : "auto";
  const yMax = prices.length ? Math.ceil(Math.max(...prices) + 10) : "auto";
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
            { label: "DTE", value: getDTE(), color: "#f59e0b" },
            { label: "SPOT", value: spot?.toLocaleString("en-IN"), color: "#e2e8f0" },
            { label: "OPEN", value: openP?.toLocaleString("en-IN"), color: "#94a3b8" },
            { label: "HIGH", value: highP?.toLocaleString("en-IN"), color: "#4ade80" },
            { label: "LOW", value: lowP?.toLocaleString("en-IN"), color: "#f87171" },
            { label: "ATM", value: atm?.toLocaleString("en-IN"), color: "#e2e8f0" },
            { label: "STRADDLE", value: straddle, color: activeColor },
            { label: "VWAP", value: straddleVwap, color: "#ff00ff" },
            { label: "CE", value: ce, color: "#4ade80" },
            { label: "PE", value: pe, color: "#f87171" },
            { label: "MAX PAIN", value: maxPainData?.max_pain_level?.toLocaleString("en-IN"), color: "#ef4444" },
            { label: "PCR", value: maxPainData?.pcr, color: "#f59e0b" },
            { label: "EXPIRY", value: expiry, color: "#6b7280" },
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
          { id: "news", label: "📰 News" },
          { id: "vwap", label: "📈 Analysis" },
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

              {/* Timeframe Buttons */}
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: "12px 12px 0 0", padding: "12px 16px", display: "flex", flexWrap: "wrap", gap: 6 }}>
                {TIMEFRAMES.map(tf => (
                  <button
                    key={tf}
                    onClick={() => setActiveTimeframe(tf as any)}
                    style={{
                      background: activeTimeframe === tf ? activeColor : "transparent",
                      border: `1px solid ${activeTimeframe === tf ? activeColor : "#2a3441"}`,
                      color: activeTimeframe === tf ? "#0d1117" : "#94a3b8",
                      padding: "4px 12px",
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {tf}
                  </button>
                ))}
                <span style={{ marginLeft: "auto", fontSize: 10, color: "#4b5563" }}>
                  {candleCache[activeTimeframe]?.length || 0} candles
                </span>
              </div>

              {/* Chart Container */}
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderTop: "none", padding: "8px", position: "relative", height: 400 }}>
                <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
              </div>

              {/* Bottom Bar */}
              <div style={{
                background: "#0d1117", border: "1px solid #1e2530", borderTop: "none",
                borderRadius: "0 0 12px 12px", padding: "12px 20px",
                display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 8,
              }}>
                {[
                  { label: "Straddle", value: straddle, color: activeColor },
                  { label: "VWAP", value: straddleVwap, color: "#ff00ff" },
                  { label: "Spot", value: spot?.toLocaleString("en-IN"), color: "#e2e8f0" },
                  { label: "Syn Future", value: synFut?.toLocaleString("en-IN"), color: "#a78bfa" },
                  { label: "ATM Strike", value: atm?.toLocaleString("en-IN"), color: "#e2e8f0" },
                  { label: `${atm ?? ""}CE`, value: ce, color: "#4ade80" },
                  { label: `${atm ?? ""}PE`, value: pe, color: "#f87171" },
                  { label: "Max Pain", value: maxPainData?.max_pain_level?.toLocaleString("en-IN"), color: "#ef4444" },
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
                      <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, letterSpacing: 1, textAlign: "left", color: "#4ade80" }}>Calls</th>
                      <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, letterSpacing: 1, textAlign: "center", color: "#94a3b8" }}>Strike</th>
                      <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, letterSpacing: 1, textAlign: "right", color: "#f87171" }}>Puts</th>
                      <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, letterSpacing: 1, textAlign: "right", color: "#f59e0b" }}>Straddle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.length > 0 ? (
                      optionChain.map((row: any, i: number) => {
                        const isAtm = row.strike === atm;
                        const isMaxPain = row.strike === maxPainData?.max_pain_level;
                        return (
                          <tr key={i} style={{
                            borderBottom: "1px solid #141820",
                            background: isAtm ? `${activeColor}12` : isMaxPain ? "#ef444415" : i % 2 === 0 ? "#0a0d13" : "transparent",
                            borderLeft: isMaxPain ? "2px solid #ef4444" : "none"
                          }}>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? "#4ade80" : "#22c55e50", textAlign: "left" }}>
                              {isAtm ? ce?.toFixed(2) : row.ce_price?.toFixed(2)}
                            </td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: 700, color: isMaxPain ? "#ef4444" : isAtm ? activeColor : "#64748b", textAlign: "center" }}>
                              {row.strike}
                              {isAtm && <span style={{ marginLeft: 4, fontSize: 9, background: `${activeColor}25`, color: activeColor, padding: "1px 5px", borderRadius: 3 }}>ATM</span>}
                              {isMaxPain && <span style={{ marginLeft: 4, fontSize: 9, background: "#ef444425", color: "#ef4444", padding: "1px 5px", borderRadius: 3 }}>MP</span>}
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
                      <tr>
                        <td colSpan={4} style={{ padding: 32, textAlign: "center", color: "#4b5563", fontSize: 12 }}>
                          {wsStatus === "connecting" ? "Connecting..." : "Market closed — data at 9:15 AM"}
                        </td>
                      </tr>
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
              ) : (
                newsData.map((news: any, i: number) => (
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
                ))
              )}
            </div>
          </div>
        )}

        {/* ANALYSIS TAB */}
        {activeTab === "vwap" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>INTRADAY VWAP</div>
                <div style={{ fontSize: 36, fontWeight: 800, color: "#6366f1" }}>{vwapData?.vwap ?? vwapData?.intraday_vwap ?? "N/A"}</div>
                <div style={{ marginTop: 8, fontSize: 13, color: vwapData?.bias?.includes("BULLISH") ? "#4ade80" : vwapData?.bias?.includes("BEARISH") ? "#ef4444" : "#94a3b8" }}>
                  {vwapData?.bias ?? vwapData?.intraday_bias ?? "Waiting for data..."}
                </div>
                {vwapData?.spot && vwapData?.vwap && (
                  <div style={{ marginTop: 8, fontSize: 12 }}>
                    Difference: <span style={{ color: "#f59e0b", fontWeight: 700 }}>
                      {(vwapData.spot - vwapData.vwap).toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>MAX PAIN LEVEL</div>
                <div style={{ fontSize: 36, fontWeight: 800, color: "#ef4444" }}>
                  {maxPainData?.max_pain_level?.toLocaleString("en-IN") ?? "N/A"}
                </div>
                <div style={{ marginTop: 8, fontSize: 13, color: maxPainData?.bias === "BULLISH" ? "#4ade80" : maxPainData?.bias === "BEARISH" ? "#ef4444" : "#94a3b8" }}>
                  {maxPainData?.signal ?? "Calculating..."}
                </div>
                <div style={{ marginTop: 8, fontSize: 12 }}>
                  Distance: <span style={{ color: "#f59e0b", fontWeight: 700 }}>
                    {maxPainData?.distance ?? "N/A"}
                  </span>
                </div>
              </div>
            </div>

            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>MARKET PRESSURE & SENTIMENT</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 12 }}>
                <div>
                  <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>PCR (Put-Call Ratio)</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: maxPainData?.pcr && maxPainData.pcr > 1.2 ? "#ef4444" : maxPainData?.pcr && maxPainData.pcr < 0.8 ? "#4ade80" : "#f59e0b" }}>
                    {maxPainData?.pcr ?? "N/A"}
                  </div>
                  <div style={{ fontSize: 11, marginTop: 4, color: "#94a3b8" }}>
                    {maxPainData?.pcr && maxPainData.pcr > 1.2 ? "🟢 Put dominance - Bearish" :
                      maxPainData?.pcr && maxPainData.pcr < 0.8 ? "🔴 Call dominance - Bullish" :
                      "🟡 Neutral market"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>Market Pressure</div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 8 }}>
                    {maxPainData?.market_pressure ?? "N/A"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </main>
  );
}