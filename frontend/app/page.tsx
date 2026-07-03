"use client";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  createChart,
  ColorType,
  LineSeries,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
  LineData,
  HistogramData,
} from "lightweight-charts";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000/ws";

const INDICES = [
  { key: "NIFTY", label: "NIFTY 50", color: "#2962ff" },
  { key: "SENSEX", label: "SENSEX", color: "#6366f1" },
];

const TIMEFRAMES = ['1S', '30S', '1M', '3M', '5M', '10M', '15M', '30M', '1H'];

export default function Page() {
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
  const [activeTimeframe, setActiveTimeframe] = useState<'1S' | '30S' | '1M' | '3M' | '5M' | '10M' | '15M' | '30M' | '1H'>('1S');
  const [candleCache, setCandleCache] = useState<Record<string, any[]>>({});
  const [straddleLineData, setStraddleLineData] = useState<LineData[]>([]);
  const [vwapLineData, setVwapLineData] = useState<LineData[]>([]);
  const [volumeData, setVolumeData] = useState<HistogramData[]>([]);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const straddleSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  // ---- Clock ----
  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true
      }));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // ---- Helpers ----
  function getTimeframeSeconds(tf: string): number {
    const map: Record<string, number> = {
      '1S': 1, '30S': 30, '1M': 60, '3M': 180, '5M': 300,
      '10M': 600, '15M': 900, '30M': 1800, '1H': 3600
    };
    return map[tf] || 60;
  }

  // ---- Send symbol change ----
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "set_symbol",
        symbol: activeIndex
      }));
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
        ws.send(JSON.stringify({
          type: "set_symbol",
          symbol: activeIndex
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // ── NEW: Historical line data (instant chart load) ──
          if (data.type === "historical_line_data") {
            const formatted = data.data.map((d: any) => ({
              time: d.time as UTCTimestamp,
              value: d.value,
            }));
            setStraddleLineData(formatted);
            console.log(`📊 Loaded ${formatted.length} historical candles onto the chart`);
            return;
          }

          if (data.type === "history") {
            setChartData(data.data || []);
            return;
          }
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
          if (data.type === "vwap_reset") {
            setVwapLineData([]);
            return;
          }
          if (data.type === "symbol_changed") {
            console.log(`✅ Backend switched to: ${data.symbol}`);
            return;
          }
          if (data.type !== "tick") return;

          // ---- Live tick ----
          if (data.spot != null) setSpot(data.spot);
          if (data.ce != null) setCe(data.ce);
          if (data.pe != null) setPe(data.pe);
          if (data.straddle != null) setStraddle(data.straddle);
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

          // ---- Update Straddle Line in real-time ----
          if (data.straddle != null) {
            const ts = Math.floor(Date.now() / 1000) as UTCTimestamp;
            setStraddleLineData(prev => {
              const last = prev[prev.length - 1];
              if (last && last.time === ts) {
                return [...prev.slice(0, -1), { time: ts, value: data.straddle }];
              }
              return [...prev, { time: ts, value: data.straddle }];
            });
          }

          // ---- Update VWAP Line in real-time ----
          if (data.straddle_vwap != null) {
            const ts = Math.floor(Date.now() / 1000) as UTCTimestamp;
            setVwapLineData(prev => {
              const last = prev[prev.length - 1];
              if (last && last.time === ts) {
                return [...prev.slice(0, -1), { time: ts, value: data.straddle_vwap }];
              }
              return [...prev, { time: ts, value: data.straddle_vwap }];
            });
          }

          // ---- Update Volume ----
          if (data.straddle != null) {
            const ts = Math.floor(Date.now() / 1000) as UTCTimestamp;
            const price = data.straddle;
            setVolumeData(prev => {
              const last = prev[prev.length - 1];
              const color = prev.length > 1 && price > (prev[prev.length - 2]?.value || price) ? '#26a69a' : '#ef5350';
              if (last && last.time === ts) {
                return [...prev.slice(0, -1), { time: ts, value: (last.value as number) + 1, color }];
              }
              return [...prev, { time: ts, value: 1, color }];
            });
          }

          // ---- Save minute chart point (backup) ----
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
  }, [activeIndex, activeTimeframe]);

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

  // ---- News, VWAP, Max Pain ----
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
    fetchNews(); fetchVwap(); fetchMaxPain();
    const i1 = setInterval(fetchNews, 300000);
    const i2 = setInterval(fetchVwap, 30000);
    const i3 = setInterval(fetchMaxPain, 30000);
    return () => { clearInterval(i1); clearInterval(i2); clearInterval(i3); };
  }, [activeIndex]);

  // ---- Chart Initialisation ----
  useEffect(() => {
    if (!chartContainerRef.current) return;
    const container = chartContainerRef.current;
    if (container.clientWidth === 0 || container.clientHeight === 0) {
      const timeout = setTimeout(() => {
        if (container.clientWidth > 0 && container.clientHeight > 0) {
          window.dispatchEvent(new Event('resize'));
        }
      }, 100);
      return () => clearTimeout(timeout);
    }

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#b0b8c4',
      },
      grid: {
        vertLines: { color: '#1e2530', style: 1, visible: true },
        horzLines: { color: '#1e2530', style: 1, visible: true },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#2a3441', width: 1, style: 2 },
        horzLine: { color: '#2a3441', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: '#1e2530',
        timeVisible: true,
        secondsVisible: true,
        tickMarkFormatter: (time: number) => {
          const d = new Date(time * 1000);
          return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },
      },
      rightPriceScale: { borderColor: '#1e2530' },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    // --- Straddle Line Series (main) ---
    const straddleSeries = chart.addSeries(LineSeries, {
      color: '#2962ff',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      priceLineVisible: true,
      lastValueVisible: true,
      title: 'Straddle',
    });

    // --- VWAP Line Series ---
    const vwapSeries = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 2,
      lineStyle: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: true,
      title: 'VWAP',
    });

    // --- Volume Histogram (sub-chart) ---
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
      borderColor: '#1e2530',
      visible: true,
    });

    chartRef.current = chart;
    straddleSeriesRef.current = straddleSeries;
    vwapSeriesRef.current = vwapSeries;
    volumeSeriesRef.current = volumeSeries;

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

  // ---- Update Straddle Line ----
  useEffect(() => {
    if (!straddleSeriesRef.current) return;
    if (straddleLineData.length === 0) {
      try { straddleSeriesRef.current.setData([]); } catch (_) {}
      return;
    }
    const sorted = [...straddleLineData].sort((a,b) => (a.time as number) - (b.time as number));
    const deduped = sorted.filter((d, i, arr) => i === 0 || arr[i-1].time !== d.time);
    try { straddleSeriesRef.current.setData(deduped as LineData<UTCTimestamp>[]); } catch (e) { console.warn(e); }
  }, [straddleLineData]);

  // ---- Update VWAP Line ----
  useEffect(() => {
    if (!vwapSeriesRef.current) return;
    if (vwapLineData.length === 0) {
      try { vwapSeriesRef.current.setData([]); } catch (_) {}
      return;
    }
    const sorted = [...vwapLineData].sort((a,b) => (a.time as number) - (b.time as number));
    const deduped = sorted.filter((d, i, arr) => i === 0 || arr[i-1].time !== d.time);
    try { vwapSeriesRef.current.setData(deduped as LineData<UTCTimestamp>[]); } catch (e) { console.warn(e); }
  }, [vwapLineData]);

  // ---- Update Volume ----
  useEffect(() => {
    if (!volumeSeriesRef.current) return;
    if (volumeData.length === 0) {
      try { volumeSeriesRef.current.setData([]); } catch (_) {}
      return;
    }
    const sorted = [...volumeData].sort((a,b) => (a.time as number) - (b.time as number));
    const deduped = sorted.filter((d, i, arr) => i === 0 || arr[i-1].time !== d.time);
    try { volumeSeriesRef.current.setData(deduped as HistogramData[]); } catch (e) { console.warn(e); }
  }, [volumeData]);

  // ---- Helpers ----
  const activeColor = INDICES.find(i => i.key === activeIndex)?.color || "#2962ff";
  const getDTE = () => { if (!expiry) return "—"; const diff = Math.ceil((new Date(expiry).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)); return diff >= 0 ? diff : 0; };
  const synFut = atm && ce && pe ? Math.round((atm + ce - pe) * 100) / 100 : null;
  const wsColor = wsStatus === "connected" ? "#26a69a" : wsStatus === "connecting" ? "#f59e0b" : "#ef5350";
  const wsLabel = wsStatus === "connected" ? "● LIVE" : wsStatus === "connecting" ? "◌ CONNECTING" : "● CLOSED";

  return (
    <main style={{ minHeight: "100vh", background: "#0d1117", color: "#d1d4dc", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
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
              }}>{idx.label}</button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 12, color: "#4b5563" }}>{currentTime}</span>
          <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20, fontWeight: 700, background: `${wsColor}15`, color: wsColor, border: `1px solid ${wsColor}30` }}>{wsLabel}</span>
        </div>
      </nav>
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
            { label: "VWAP", value: straddleVwap, color: "#f59e0b" },
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
          }}>{tab.label}</button>
        ))}
      </div>
      <div style={{ padding: "16px 24px" }}>
        {activeTab === "straddle" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: "12px 12px 0 0", padding: "12px 16px", display: "flex", flexWrap: "wrap", gap: 6 }}>
                {TIMEFRAMES.map(tf => (
                  <button key={tf} onClick={() => setActiveTimeframe(tf as any)} style={{
                    background: activeTimeframe === tf ? activeColor : "transparent",
                    border: `1px solid ${activeTimeframe === tf ? activeColor : "#2a3441"}`,
                    color: activeTimeframe === tf ? "#0d1117" : "#94a3b8",
                    padding: "4px 12px", borderRadius: 4, fontSize: 11, fontWeight: 700, cursor: "pointer",
                  }}>{tf}</button>
                ))}
                <span style={{ marginLeft: "auto", fontSize: 10, color: "#4b5563" }}>{candleCache[activeTimeframe]?.length || 0} candles</span>
              </div>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderTop: "none", padding: "8px", position: "relative", height: 400 }}>
                <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
              </div>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderTop: "none", borderRadius: "0 0 12px 12px", padding: "12px 20px", display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 8 }}>
                {[
                  { label: "Straddle", value: straddle, color: activeColor },
                  { label: "VWAP", value: straddleVwap, color: "#f59e0b" },
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
            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #1e2530", display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#e2e8f0" }}>OPTION CHAIN</span>
                <span style={{ fontSize: 10, color: activeColor, fontWeight: 700 }}>{expiry ?? "—"}</span>
              </div>
              <div style={{ overflowY: "auto", maxHeight: 520 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr style={{ borderBottom: "1px solid #1e2530", background: "#0d1117", position: "sticky", top: 0 }}>
                    <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, textAlign: "left", color: "#4ade80" }}>Calls</th>
                    <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, textAlign: "center", color: "#94a3b8" }}>Strike</th>
                    <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, textAlign: "right", color: "#f87171" }}>Puts</th>
                    <th style={{ padding: "8px 12px", fontSize: 10, fontWeight: 700, textAlign: "right", color: "#f59e0b" }}>Straddle</th>
                  </tr></thead>
                  <tbody>
                    {optionChain.length > 0 ? (
                      optionChain.map((row: any, i: number) => {
                        const isAtm = row.strike === atm;
                        const isMaxPain = row.strike === maxPainData?.max_pain_level;
                        return (
                          <tr key={i} style={{ borderBottom: "1px solid #141820", background: isAtm ? `${activeColor}12` : isMaxPain ? "#ef444415" : i % 2 === 0 ? "#0a0d13" : "transparent", borderLeft: isMaxPain ? "2px solid #ef4444" : "none" }}>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? "#4ade80" : "#22c55e50", textAlign: "left" }}>{isAtm ? ce?.toFixed(2) : row.ce_price?.toFixed(2)}</td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: 700, color: isMaxPain ? "#ef4444" : isAtm ? activeColor : "#64748b", textAlign: "center" }}>{row.strike}{isAtm && <span style={{ marginLeft: 4, fontSize: 9, background: `${activeColor}25`, color: activeColor, padding: "1px 5px", borderRadius: 3 }}>ATM</span>}{isMaxPain && <span style={{ marginLeft: 4, fontSize: 9, background: "#ef444425", color: "#ef4444", padding: "1px 5px", borderRadius: 3 }}>MP</span>}</td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? "#f87171" : "#ef444450", textAlign: "right" }}>{isAtm ? pe?.toFixed(2) : row.pe_price?.toFixed(2)}</td>
                            <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: isAtm ? 800 : 400, color: isAtm ? activeColor : "#78350f", textAlign: "right" }}>{isAtm ? straddle?.toFixed(2) : row.straddle?.toFixed(2)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr><td colSpan={4} style={{ padding: 32, textAlign: "center", color: "#4b5563", fontSize: 12 }}>{wsStatus === "connecting" ? "Connecting..." : "Market closed — data at 9:15 AM"}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
        {activeTab === "news" && (
          <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}><span style={{ fontSize: 14, fontWeight: 700 }}>Market News</span><span style={{ fontSize: 10, color: "#4b5563" }}>Refreshes every 5 mins</span></div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 600, overflowY: "auto" }}>
              {newsData.length === 0 ? <p style={{ color: "#4b5563", textAlign: "center", padding: 32 }}>Loading news...</p> : newsData.map((news: any, i: number) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: 12, borderRadius: 8, background: "#131920", border: "1px solid #1e2530" }}>
                  <span style={{ fontSize: 20 }}>{news.emoji}</span>
                  <div><a href={news.link} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, color: "#e2e8f0", textDecoration: "none", fontWeight: 500 }}>{news.title}</a>
                  <div style={{ marginTop: 4, display: "flex", gap: 8 }}><span style={{ fontSize: 10, color: "#4b5563" }}>{news.source}</span><span style={{ fontSize: 10, fontWeight: 700, color: news.impact === "HIGH" ? "#f87171" : news.impact === "MEDIUM" ? "#f59e0b" : "#4ade80" }}>{news.impact}</span></div></div>
                </div>
              ))}
            </div>
          </div>
        )}
        {activeTab === "vwap" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>INTRADAY VWAP</div>
                <div style={{ fontSize: 36, fontWeight: 800, color: "#6366f1" }}>{vwapData?.vwap ?? vwapData?.intraday_vwap ?? "N/A"}</div>
                <div style={{ marginTop: 8, fontSize: 13, color: vwapData?.bias?.includes("BULLISH") ? "#4ade80" : vwapData?.bias?.includes("BEARISH") ? "#ef4444" : "#94a3b8" }}>{vwapData?.bias ?? vwapData?.intraday_bias ?? "Waiting for data..."}</div>
                {vwapData?.spot && vwapData?.vwap && <div style={{ marginTop: 8, fontSize: 12 }}>Difference: <span style={{ color: "#f59e0b", fontWeight: 700 }}>{(vwapData.spot - vwapData.vwap).toFixed(2)}</span></div>}
              </div>
              <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>MAX PAIN LEVEL</div>
                <div style={{ fontSize: 36, fontWeight: 800, color: "#ef4444" }}>{maxPainData?.max_pain_level?.toLocaleString("en-IN") ?? "N/A"}</div>
                <div style={{ marginTop: 8, fontSize: 13, color: maxPainData?.bias === "BULLISH" ? "#4ade80" : maxPainData?.bias === "BEARISH" ? "#ef4444" : "#94a3b8" }}>{maxPainData?.signal ?? "Calculating..."}</div>
                <div style={{ marginTop: 8, fontSize: 12 }}>Distance: <span style={{ color: "#f59e0b", fontWeight: 700 }}>{maxPainData?.distance ?? "N/A"}</span></div>
              </div>
            </div>
            <div style={{ background: "#0d1117", border: "1px solid #1e2530", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 9, color: "#4b5563", marginBottom: 4, letterSpacing: 1 }}>MARKET PRESSURE & SENTIMENT</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 12 }}>
                <div><div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>PCR (Put-Call Ratio)</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: maxPainData?.pcr && maxPainData.pcr > 1.2 ? "#ef4444" : maxPainData?.pcr && maxPainData.pcr < 0.8 ? "#4ade80" : "#f59e0b" }}>{maxPainData?.pcr ?? "N/A"}</div>
                <div style={{ fontSize: 11, marginTop: 4, color: "#94a3b8" }}>{maxPainData?.pcr && maxPainData.pcr > 1.2 ? "🟢 Put dominance - Bearish" : maxPainData?.pcr && maxPainData.pcr < 0.8 ? "🔴 Call dominance - Bullish" : "🟡 Neutral market"}</div></div>
                <div><div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>Market Pressure</div>
                <div style={{ fontSize: 14, fontWeight: 700, marginTop: 8 }}>{maxPainData?.market_pressure ?? "N/A"}</div></div>
              </div>
            </div>
          </div>
        )}
      </div> 
    </main>
  );
}