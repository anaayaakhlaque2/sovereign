import { useState, useEffect } from 'react';
import { X, Play, Download, BarChart2, TrendingUp, RefreshCw, Layers } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  LineChart,
  Line,
} from 'recharts';
import { useClusterStore } from '../store/clusterStore';
import { fetchElections, runBenchmark } from '../lib/api';
import { ElectionRecord } from '../lib/types';

export function AnalyticsModal() {
  const activeTab = useClusterStore((s) => s.activeTab);
  const setActiveTab = useClusterStore((s) => s.setActiveTab);
  const theme = useClusterStore((s) => s.theme);
  const isDay = theme === 'day';

  const [elections, setElections] = useState<ElectionRecord[]>([]);
  const [benchmarkLoading, setBenchmarkLoading] = useState<boolean>(false);
  const [chartType, setChartType] = useState<'bar' | 'line'>('bar');
  const [chartData, setChartData] = useState<any[]>([
    { name: 'N=3', Bully: 5, Ring: 4, BullyWorst: 5, RingWorst: 4 },
    { name: 'N=4', Bully: 8, Ring: 6, BullyWorst: 9, RingWorst: 6 },
    { name: 'N=5', Bully: 12, Ring: 8, BullyWorst: 14, RingWorst: 8 },
    { name: 'N=6', Bully: 16, Ring: 10, BullyWorst: 20, RingWorst: 10 },
    { name: 'N=7', Bully: 22, Ring: 12, BullyWorst: 27, RingWorst: 12 },
    { name: 'N=8', Bully: 28, Ring: 14, BullyWorst: 35, RingWorst: 14 },
    { name: 'N=9', Bully: 35, Ring: 16, BullyWorst: 44, RingWorst: 16 },
  ]);

  useEffect(() => {
    if (activeTab === 'analytics') {
      loadData();
    }
  }, [activeTab]);

  const loadData = async () => {
    try {
      const data = await fetchElections();
      setElections(data);
    } catch (e) {
      console.error('Failed to load elections:', e);
    }
  };

  const handleRunBenchmark = async () => {
    setBenchmarkLoading(true);
    try {
      const res = await runBenchmark(10, [3, 4, 5, 6, 7, 8, 9]);
      if (res && res.benchmark) {
        // Group by node_count
        const formatted: Record<number, any> = {};
        res.benchmark.forEach((b: any) => {
          const n = b.node_count;
          if (!formatted[n]) formatted[n] = { name: `N=${n}` };
          if (b.algorithm === 'bully') {
            formatted[n].Bully = b.avg_messages;
            formatted[n].BullyWorst = b.worst_messages;
          }
          if (b.algorithm === 'ring') {
            formatted[n].Ring = b.avg_messages;
            formatted[n].RingWorst = b.worst_messages;
          }
        });
        setChartData(Object.values(formatted));
      }
      await loadData();
    } catch (e) {
      console.error('Benchmark error:', e);
    } finally {
      setBenchmarkLoading(false);
    }
  };

  if (activeTab !== 'analytics') return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 dark:bg-[#050810]/80 backdrop-blur-xl flex items-center justify-center p-6 pointer-events-auto">
      <div className="w-full max-w-5xl h-[85vh] glass-panel rounded-3xl p-6 flex flex-col shadow-2xl border border-[var(--gold)]/30">
        {/* Modal Top Bar */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-4 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[var(--gold)]/20 border border-[var(--gold)]/40 text-[var(--gold)]">
              <BarChart2 className="w-6 h-6" />
            </div>
            <div>
              <h2 className="font-cinzel font-bold text-lg text-[var(--gold)] tracking-wider uppercase">
                Analytics & Empirical Comparison
              </h2>
              <p className="text-xs text-[var(--mute)]">
                Bully Algorithm O(N²) worst-case vs Ring Algorithm O(N) linear message complexity
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Run Benchmark Button */}
            <button
              onClick={handleRunBenchmark}
              disabled={benchmarkLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-[#ffe3a1] to-[#e8c36a] text-[#050810] font-bold text-xs shadow-md shadow-[#e8c36a]/30 hover:scale-105 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${benchmarkLoading ? 'animate-spin' : ''}`} />
              <span>{benchmarkLoading ? 'Computing...' : 'Run Benchmark'}</span>
            </button>

            {/* Export CSV */}
            <a
              href="/api/export/csv"
              download
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl glass-panel text-xs text-[var(--ink)] hover:border-[var(--gold)]/50 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </a>

            {/* Close */}
            <button
              onClick={() => setActiveTab('dashboard')}
              className="p-2 rounded-xl hover:bg-white/10 text-[var(--mute)] hover:text-[var(--ink)] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* 2-Column Split: Left is strictly FIXED (Non-Scrolling Graph), Right is SCROLLING Table */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
          {/* LEFT COLUMN: Fixed Chart (7 cols) - Absolutely Non-Scrolling! */}
          <div className="lg:col-span-7 flex flex-col glass-panel rounded-2xl p-5 border border-white/10 h-full overflow-hidden">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <div>
                <h3 className="font-cinzel font-bold text-sm text-[var(--gold)] flex items-center gap-2">
                  <span>Message Complexity Analysis</span>
                </h3>
                <span className="text-[11px] text-[var(--mute)]">
                  Total election messages exchanged across cluster size N
                </span>
              </div>

              {/* Chart Type Toggle: Bar vs Line */}
              <div className="flex p-0.5 rounded-lg glass-panel text-[11px]">
                <button
                  onClick={() => setChartType('bar')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                    chartType === 'bar' ? 'bg-[var(--gold)] text-[#050810] font-bold' : 'text-[var(--mute)]'
                  }`}
                >
                  Bar
                </button>
                <button
                  onClick={() => setChartType('line')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer ${
                    chartType === 'line' ? 'bg-[var(--gold)] text-[#050810] font-bold' : 'text-[var(--mute)]'
                  }`}
                >
                  Curve (O(N²))
                </button>
              </div>
            </div>

            {/* Fixed Graph Area */}
            <div className="flex-1 w-full min-h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                {chartType === 'bar' ? (
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={isDay ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'} />
                    <XAxis
                      dataKey="name"
                      stroke={isDay ? '#334155' : '#9aa3bd'}
                      tick={{ fill: isDay ? '#334155' : '#9aa3bd', fontSize: 11, fontWeight: isDay ? 600 : 400 }}
                    />
                    <YAxis
                      stroke={isDay ? '#334155' : '#9aa3bd'}
                      tick={{ fill: isDay ? '#334155' : '#9aa3bd', fontSize: 11, fontWeight: isDay ? 600 : 400 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: isDay ? '#ffffff' : '#0d1326',
                        borderColor: isDay ? '#b48312' : '#e8c36a',
                        borderRadius: '12px',
                        color: isDay ? '#0f172a' : '#fff',
                        boxShadow: '0 10px 25px -5px rgba(0,0,0,0.2)',
                      }}
                      labelStyle={{ color: isDay ? '#b48312' : '#ffe3a1', fontWeight: 'bold' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                    <Bar dataKey="Bully" fill="#ff6b3d" radius={[5, 5, 0, 0]} name="Bully (Average)" />
                    <Bar dataKey="Ring" fill="#e8c36a" radius={[5, 5, 0, 0]} name="Ring (2(N-1))" />
                  </BarChart>
                ) : (
                  <LineChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={isDay ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'} />
                    <XAxis
                      dataKey="name"
                      stroke={isDay ? '#334155' : '#9aa3bd'}
                      tick={{ fill: isDay ? '#334155' : '#9aa3bd', fontSize: 11, fontWeight: isDay ? 600 : 400 }}
                    />
                    <YAxis
                      stroke={isDay ? '#334155' : '#9aa3bd'}
                      tick={{ fill: isDay ? '#334155' : '#9aa3bd', fontSize: 11, fontWeight: isDay ? 600 : 400 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: isDay ? '#ffffff' : '#0d1326',
                        borderColor: isDay ? '#b48312' : '#e8c36a',
                        borderRadius: '12px',
                        color: isDay ? '#0f172a' : '#fff',
                        boxShadow: '0 10px 25px -5px rgba(0,0,0,0.2)',
                      }}
                      labelStyle={{ color: isDay ? '#b48312' : '#ffe3a1', fontWeight: 'bold' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                    <Line type="monotone" dataKey="BullyWorst" stroke="#ff4500" strokeWidth={3} dot={{ r: 4 }} name="Bully Worst O(N²)" />
                    <Line type="monotone" dataKey="Bully" stroke="#ff8c00" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }} name="Bully Average" />
                    <Line type="monotone" dataKey="Ring" stroke="#e8c36a" strokeWidth={3} dot={{ r: 4 }} name="Ring Linear O(N)" />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>

            {/* Complexity badges below chart */}
            <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-slate-200 dark:border-white/10 shrink-0 text-xs">
              <div className="p-2.5 rounded-xl bg-orange-50 dark:bg-[#ff6b3d]/10 border border-orange-200 dark:border-[#ff6b3d]/30">
                <div className="font-bold text-orange-700 dark:text-[#ff6b3d]">Bully Algorithm: O(N²)</div>
                <div className="text-[10px] text-slate-600 dark:text-[var(--mute)]">Chatty broadcast: up to N(N-1)/2 + (N-1) messages</div>
              </div>
              <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-[#e8c36a]/10 border border-amber-200 dark:border-[#e8c36a]/30">
                <div className="font-bold text-amber-800 dark:text-[var(--gold)]">Ring Algorithm: O(N)</div>
                <div className="text-[10px] text-slate-600 dark:text-[var(--mute)]">Token circulation: strictly 2(N-1) messages</div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Independently Scrolling Election Records List (5 cols) */}
          <div className="lg:col-span-5 flex flex-col glass-panel rounded-2xl p-4 border border-slate-200 dark:border-white/10 h-full overflow-hidden">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-200 dark:border-white/10 shrink-0">
              <h3 className="font-cinzel font-bold text-sm text-[var(--gold)]">
                Election History ({elections.length})
              </h3>
              <span className="text-[10px] text-slate-500 dark:text-[var(--mute)] font-mono font-semibold">SQLite DB</span>
            </div>

            {/* Scrollable list */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1.5 text-xs">
              {elections.length === 0 ? (
                <div className="text-center py-20 text-[var(--mute)]">No recorded elections yet.</div>
              ) : (
                elections.map((el) => (
                  <div
                    key={el.id}
                    className="p-3 rounded-xl theme-item-card border border-slate-200 dark:border-white/10 hover:border-amber-400 dark:hover:border-white/25 transition-all shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          el.algorithm === 'bully'
                            ? 'bg-orange-100 text-orange-700 dark:bg-[#ff6b3d]/20 dark:text-[#ff6b3d] border border-orange-300 dark:border-[#ff6b3d]/40'
                            : 'bg-amber-100 text-amber-800 dark:bg-[#e8c36a]/20 dark:text-[var(--gold)] border border-amber-300 dark:border-[#e8c36a]/40'
                        }`}
                      >
                        {el.algorithm}
                      </span>
                      <span className="font-mono text-slate-500 dark:text-[var(--mute)] text-[10px] font-semibold">
                        {el.election_id.slice(-8)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-800 dark:text-[var(--ink)]">
                      <div>
                        Sovereign: <strong className="text-amber-700 dark:text-[var(--gold)] font-bold">Node {el.winner_id ?? el.node_count}</strong>
                        <span className="text-slate-500 dark:text-[var(--mute)] ml-1.5">({el.node_count} nodes)</span>
                      </div>
                      <div className="text-right">
                        <span className="font-mono font-bold text-amber-700 dark:text-[var(--gold)]">{el.election_messages} msgs</span>
                        <span className="text-[10px] text-slate-500 dark:text-[var(--mute)] ml-1.5 font-mono font-semibold">
                          {el.duration_ms ? `${Math.round(el.duration_ms)}ms` : '<1s'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
