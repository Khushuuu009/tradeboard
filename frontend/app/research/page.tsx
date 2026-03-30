"use client";
import { useState, useEffect } from "react";
import axios from "axios";

const RESEARCH_PASSWORD = "tradeboard2026";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function ResearchPage() {
  const [mounted, setMounted] = useState(false);
  const [password, setPassword] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [wrongPassword, setWrongPassword] = useState(false);

  const [analysisData, setAnalysisData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const [backtestData, setBacktestData] = useState<any>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestMonths, setBacktestMonths] = useState(1);
  const [backtestErr, setBacktestErr] = useState("");

  const [activeSection, setActiveSection] = useState("vwap");

  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  const handleLogin = () => {
    if (password === RESEARCH_PASSWORD) {
      setAuthenticated(true);
      setWrongPassword(false);
    } else {
      setWrongPassword(true);
    }
  };

  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/expiry-analysis`);
      setAnalysisData(res.data);
    } catch (err) {
      console.log("Analysis error:", err);
    }
    setLoading(false);
  };

  const runBacktest = async () => {
    setBacktestLoading(true);
    setBacktestErr("");
    setBacktestData(null);
    try {
      const res = await axios.get(`${API_URL}/daily-straddle?months=${backtestMonths}`, { timeout: 300000 });
      setBacktestData(res.data);
    } catch (err) {
      setBacktestErr("Failed to fetch. Is the backend running?");
    }
    setBacktestLoading(false);
  };

  if (!authenticated) {
    return (
      <main className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-md">
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">🔬</div>
            <h1 className="text-2xl font-bold text-white">Research Portal</h1>
            <p className="text-gray-500 text-sm mt-2">Internal use only</p>
          </div>
          <div className="space-y-4">
            <input
              type="password"
              placeholder="Enter research password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
            />
            {wrongPassword && (
              <p className="text-red-400 text-sm text-center">Wrong password!</p>
            )}
            <button
              onClick={handleLogin}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 rounded-xl transition-colors"
            >
              Access Research
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      <nav className="bg-gray-900 border-b border-gray-800 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-purple-400">🔬 Research Portal</span>
            <span className="text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full">Internal Only</span>
          </div>
          <a href="/" className="text-xs text-gray-500 hover:text-white transition-colors">← Back to Dashboard</a>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-6">

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveSection("vwap")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeSection === "vwap" ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-gray-900 text-gray-400 border border-gray-800"}`}
          >
            🎯 Daily Straddle
          </button>
          <button
            onClick={() => setActiveSection("expiry")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeSection === "expiry" ? "bg-purple-500/20 text-purple-400 border border-purple-500/30" : "bg-gray-900 text-gray-400 border border-gray-800"}`}
          >
            📅 Expiry Day Analysis
          </button>
        </div>

        {/* DAILY STRADDLE */}
        {activeSection === "vwap" && (
          <div className="space-y-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400">Period:</label>
                <select
                  value={backtestMonths}
                  onChange={e => setBacktestMonths(Number(e.target.value))}
                  className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none"
                >
                  <option value={1}>1 Month</option>
                  <option value={3}>3 Months</option>
                  <option value={6}>6 Months</option>
                  <option value={12}>12 Months</option>
                </select>
              </div>
              <button
                onClick={runBacktest}
                disabled={backtestLoading}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded-lg text-sm font-bold transition-colors"
              >
                {backtestLoading ? "⏳ Loading..." : "▶ Load Data"}
              </button>
              {backtestErr && <span className="text-xs text-red-400">{backtestErr}</span>}
            </div>

            {!backtestData && !backtestLoading && (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="text-4xl mb-4">📊</div>
                  <p className="text-gray-400 mb-1 font-medium">Daily Straddle Closing</p>
                  <p className="text-gray-500 text-sm">Lowest straddle premium for each trading day</p>
                </div>
              </div>
            )}

            {backtestData && backtestData.status === "success" && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Trading Days</div>
                    <div className="text-3xl font-bold text-white">{backtestData.summary.total_days}</div>
                    <div className="text-xs text-gray-500 mt-1">{backtestData.summary.analysis_period}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Avg Straddle Close</div>
                    <div className="text-3xl font-bold text-yellow-400">{backtestData.summary.avg_straddle_close}</div>
                    <div className="text-xs text-gray-500 mt-1">lowest CE+PE per day</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Data Source</div>
                    <div className="text-sm font-bold text-blue-400 mt-2">Dhan + FinanceDeft</div>
                    <div className="text-xs text-gray-500 mt-1">{backtestData.summary.last_updated}</div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                    <h3 className="text-white font-bold">Daily Straddle Closing Price</h3>
                    <span className="text-xs text-gray-500">{backtestData.results.length} trading days</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-800 bg-gray-900/50">
                          <th className="px-4 py-3 text-left   text-xs font-bold text-gray-400">Date</th>
                          <th className="px-4 py-3 text-left   text-xs font-bold text-gray-400">Day</th>
                          <th className="px-4 py-3 text-left   text-xs font-bold text-gray-400">Expiry</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-gray-400">ATM Strike</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-green-400">CE Close</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-red-400">PE Close</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-yellow-400">Straddle</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-gray-400">Spot Close</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-blue-400">VWAP 3:20</th>
                          <th className="px-4 py-3 text-center text-xs font-bold text-gray-400">Signal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestData.results.map((row: any, i: number) => {
                          const isExpiry = row.date === row.expiry;
                          return (
                            <tr key={i} className={`border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors ${isExpiry ? "bg-yellow-500/5" : ""}`}>
                              <td className="px-4 py-3 text-sm text-white font-medium">
                                {new Date(row.date).toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" })}
                                {isExpiry && <span className="ml-2 text-xs bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">Expiry</span>}
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-400">{row.weekday}</td>
                              <td className="px-4 py-3 text-sm text-gray-400">
                                {new Date(row.expiry).toLocaleDateString("en-IN", { day:"2-digit", month:"short" })}
                              </td>
                              <td className="px-4 py-3 text-sm text-right text-gray-300">{row.atm_strike?.toLocaleString()}</td>
                              <td className="px-4 py-3 text-sm text-right text-green-400 font-bold">{row.ce_close}</td>
                              <td className="px-4 py-3 text-sm text-right text-red-400 font-bold">{row.pe_close}</td>
                              <td className="px-4 py-3 text-sm text-right text-yellow-400 font-bold">{row.straddle_close}</td>
                              <td className="px-4 py-3 text-sm text-right text-gray-400">{row.spot_close?.toLocaleString()}</td>
                              <td className="px-4 py-3 text-sm text-right text-blue-400">{row.vwap_320 ?? "—"}</td>
                              <td className="px-4 py-3 text-center">
                                {row.signal === "N/A" ? (
                                  <span className="text-xs text-gray-600">—</span>
                                ) : (
                                  <span className={`text-xs font-bold px-2 py-1 rounded-full ${row.signal === "ABOVE VWAP" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                                    {row.signal === "ABOVE VWAP" ? "↑ Above" : "↓ Below"}
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {backtestData && backtestData.status === "error" && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
                ❌ {backtestData.message}
              </div>
            )}
          </div>
        )}

        {/* EXPIRY DAY ANALYSIS */}
        {activeSection === "expiry" && (
          <div className="space-y-4">
            {!analysisData && !loading && (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="text-4xl mb-4">📊</div>
                  <p className="text-gray-400 mb-2 font-medium">NIFTY Expiry Day Backtest</p>
                  <p className="text-gray-500 text-sm mb-6">
                    Analyzes 6 months of expiry days<br/>
                    Compares VWAP vs actual closing price
                  </p>
                  <button onClick={fetchAnalysis} className="px-8 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold transition-colors">
                    Run Analysis
                  </button>
                </div>
              </div>
            )}

            {loading && (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="text-4xl mb-4">⏳</div>
                  <p className="text-gray-400">Fetching NIFTY data...</p>
                </div>
              </div>
            )}

            {analysisData && !loading && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Expiry Days</div>
                    <div className="text-3xl font-bold text-white">{analysisData.summary.total_expiry_days}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Within ±50 pts</div>
                    <div className="text-3xl font-bold text-green-400">{analysisData.summary.accuracy_within_50pts}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Within ±100 pts</div>
                    <div className="text-3xl font-bold text-blue-400">{analysisData.summary.accuracy_within_100pts}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Avg Difference</div>
                    <div className="text-3xl font-bold text-yellow-400">{analysisData.summary.avg_difference_pts}</div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                    <h3 className="text-white font-bold">Expiry Day Breakdown</h3>
                    <button onClick={fetchAnalysis} className="text-xs text-purple-400 hover:text-purple-300">🔄 Refresh</button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-800 bg-gray-900/50">
                          <th className="px-4 py-3 text-left   text-xs font-bold text-gray-400">Date</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-gray-400">Close</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-blue-400">VWAP</th>
                          <th className="px-4 py-3 text-right  text-xs font-bold text-gray-400">Difference</th>
                          <th className="px-4 py-3 text-center text-xs font-bold text-gray-400">Range</th>
                          <th className="px-4 py-3 text-center text-xs font-bold text-gray-400">Signal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysisData.expiry_days.map((day: any, index: number) => (
                          <tr key={index} className={`border-b border-gray-800/50 hover:bg-gray-800/30 ${day.within_50pts ? "bg-green-500/5" : ""}`}>
                            <td className="px-4 py-3 text-sm text-white font-medium">{day.date}</td>
                            <td className="px-4 py-3 text-sm text-right text-white">{day.close_price.toLocaleString()}</td>
                            <td className="px-4 py-3 text-sm text-right text-blue-400 font-bold">{day.vwap.toLocaleString()}</td>
                            <td className={`px-4 py-3 text-sm text-right font-bold ${Math.abs(day.difference) <= 50 ? "text-green-400" : Math.abs(day.difference) <= 100 ? "text-yellow-400" : "text-red-400"}`}>
                              {day.difference > 0 ? "+" : ""}{day.difference}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span className={`text-xs px-2 py-1 rounded-full font-bold ${day.within_20pts ? "bg-green-500/20 text-green-400" : day.within_50pts ? "bg-blue-500/20 text-blue-400" : day.within_100pts ? "bg-yellow-500/20 text-yellow-400" : "bg-red-500/20 text-red-400"}`}>
                                {day.within_20pts ? "✅ ±20" : day.within_50pts ? "✅ ±50" : day.within_100pts ? "⚠️ ±100" : "❌ >100"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span className={`text-xs font-bold ${day.signal === "ABOVE VWAP" ? "text-green-400" : "text-red-400"}`}>
                                {day.signal === "ABOVE VWAP" ? "↑ Above" : "↓ Below"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </main>
  );
}