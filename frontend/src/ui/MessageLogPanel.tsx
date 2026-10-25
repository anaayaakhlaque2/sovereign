import { useState } from 'react';
import { Trash2, X, MessageSquare } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';

export function MessageLogPanel() {
  const logs = useClusterStore((s) => s.logs);
  const clearLogs = useClusterStore((s) => s.clearLogs);
  const showRightPanel = useClusterStore((s) => s.showRightPanel);
  const toggleRightPanel = useClusterStore((s) => s.toggleRightPanel);
  const setRightPanel = useClusterStore((s) => s.setRightPanel);
  const [filter, setFilter] = useState<string>('ALL');

  const filteredLogs = logs.filter((l) => {
    if (filter === 'ALL') return true;
    if (filter === 'ELECTION') return l.type === 'ELECTION' || l.type === 'RING_ELECTION';
    if (filter === 'OK') return l.type === 'OK';
    if (filter === 'COORDINATOR') return l.type === 'COORDINATOR' || l.type === 'RING_COORDINATOR';
    if (filter === 'HEARTBEAT') return l.type.includes('HEARTBEAT');
    return true;
  });

  const getTagColor = (type: string) => {
    if (type.includes('COORDINATOR') || type === 'LEADER_ELECTED') {
      return 'bg-[#e8c36a]/25 border-[#e8c36a] text-[var(--gold)]';
    }
    if (type.includes('ELECTION')) {
      return 'bg-[#ff6b3d]/25 border-[#ff6b3d] text-[#ff6b3d]';
    }
    if (type === 'OK') {
      return 'bg-emerald-500/20 border-emerald-500/40 text-emerald-500 dark:text-emerald-300';
    }
    if (type.includes('HEARTBEAT')) {
      return 'bg-[#6fb3ff]/20 border-[#6fb3ff]/40 text-[#6fb3ff]';
    }
    return 'bg-white/10 border-white/20 text-[var(--mute)]';
  };

  return (
    <>
      {/* Floating Toggle Button on Right (ONLY visible when panel is closed, completely preventing overlap!) */}
      {!showRightPanel && (
        <div className="fixed right-6 top-24 z-30 pointer-events-auto">
          <button
            onClick={toggleRightPanel}
            className="flex items-center gap-2.5 px-4 py-2.5 rounded-2xl glass-panel shadow-lg hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
            title="Open Live Messenger Logs"
          >
            <span className="text-base">📜</span>
            <span className="font-cinzel font-bold text-xs text-[var(--gold)] tracking-wider">
              Live Logs
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-[var(--gold)]/20 dark:text-[var(--gold)] border border-amber-300 dark:border-[var(--gold)]/40">
              {logs.length}
            </span>
          </button>
        </div>
      )}

      {/* Slide-out Drawer Panel */}
      {showRightPanel && (
        <aside className="fixed right-6 top-24 bottom-28 w-84 glass-panel rounded-2xl p-4 flex flex-col z-30 pointer-events-auto shadow-2xl animate-in fade-in slide-in-from-right-4 duration-200">
          {/* Header (NO OVERLAP!) */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/10 mb-3 shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-lg">📜</span>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-cinzel font-bold text-sm text-amber-800 dark:text-[var(--gold)] tracking-wider uppercase">
                    Live Logs
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 dark:bg-white/10 dark:text-[var(--mute)]">
                    {filteredLogs.length} msgs
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 dark:text-[var(--mute)] font-medium">Real TCP Network Packets</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={clearLogs}
                title="Clear Log"
                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-[var(--mute)] hover:text-slate-900 dark:hover:text-[var(--ink)] transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setRightPanel(false)}
                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-[var(--mute)] hover:text-slate-900 dark:hover:text-[var(--ink)] transition-colors cursor-pointer"
                title="Close panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex flex-wrap gap-1.5 mb-3 pb-2 border-b border-slate-200/60 dark:border-white/5">
            {['ALL', 'ELECTION', 'OK', 'COORDINATOR', 'HEARTBEAT'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border transition-colors cursor-pointer ${
                  filter === f
                    ? 'bg-amber-400 text-slate-950 font-bold border-amber-500 shadow-sm'
                    : 'bg-white dark:bg-black/40 border-slate-300 dark:border-white/10 text-slate-700 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Log Stream */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-xs">
            {filteredLogs.length === 0 ? (
              <div className="text-center py-12 text-slate-500 dark:text-[var(--mute)] text-xs">
                No messages captured.
                <div className="text-[11px] mt-1 text-slate-400 dark:text-[var(--mute)]/70">
                  Crash a node to trigger an election!
                </div>
              </div>
            ) : (
              filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className="p-2.5 rounded-xl bg-white dark:bg-black/40 border border-slate-200 dark:border-white/10 hover:border-amber-400 dark:hover:border-white/20 shadow-sm transition-colors"
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold tracking-wider border ${getTagColor(log.type)}`}>
                      {log.type}
                    </span>
                    <div className="flex items-center gap-1.5 text-[10px]">
                      <span className="font-mono font-bold text-amber-700 dark:text-[var(--gold)]">L:{log.lamport}</span>
                      <span className="text-slate-500 dark:text-[var(--mute)]">{log.timeStr}</span>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-800 dark:text-[var(--ink)] font-mono leading-tight font-medium">
                    {log.text}
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      )}
    </>
  );
}
