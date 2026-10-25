import { useState, useEffect } from 'react';
import { X, Play, Pause, RotateCcw, FastForward, Clock } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import { fetchElections, fetchElectionEvents } from '../lib/api';
import { ElectionRecord, EventRecord } from '../lib/types';

export function ReplayModal() {
  const activeTab = useClusterStore((s) => s.activeTab);
  const setActiveTab = useClusterStore((s) => s.setActiveTab);
  const theme = useClusterStore((s) => s.theme);
  const isDay = theme === 'day';

  const [elections, setElections] = useState<ElectionRecord[]>([]);
  const [selectedElectionId, setSelectedElectionId] = useState<string>('');
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  useEffect(() => {
    if (activeTab === 'replay') {
      fetchElections().then((list) => {
        setElections(list);
        if (list.length > 0) {
          setSelectedElectionId(list[0].election_id);
        }
      });
    }
  }, [activeTab]);

  useEffect(() => {
    if (selectedElectionId) {
      fetchElectionEvents(selectedElectionId).then((evts) => {
        setEvents(evts);
        setCurrentIndex(0);
        setIsPlaying(false);
      });
    }
  }, [selectedElectionId]);

  useEffect(() => {
    let timer: any;
    if (isPlaying && currentIndex < events.length - 1) {
      timer = setTimeout(() => {
        setCurrentIndex((prev) => prev + 1);
      }, 700);
    } else if (currentIndex >= events.length - 1) {
      setIsPlaying(false);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, currentIndex, events.length]);

  if (activeTab !== 'replay') return null;

  const currentEvent = events[currentIndex];

  return (
    <div className="fixed inset-0 z-50 bg-black/40 dark:bg-[#050810]/80 backdrop-blur-xl flex items-center justify-center p-8 pointer-events-auto">
      <div className="w-full max-w-4xl h-[78vh] glass-panel rounded-3xl p-7 flex flex-col shadow-2xl border border-[#e8c36a]/30">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-black/10 dark:border-white/10 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#6fb3ff]/20 border border-[#6fb3ff]/40 text-[#6fb3ff]">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <h2 className="font-cinzel font-bold text-xl text-[var(--gold)] tracking-wider uppercase">
                Election Replay Timeline
              </h2>
              <p className="text-xs text-[var(--mute)]">
                Step-by-step causal replay ordered by Lamport logical timestamps
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={selectedElectionId}
              onChange={(e) => setSelectedElectionId(e.target.value)}
              className="bg-white dark:bg-[#0b1022] border border-slate-300 dark:border-white/15 text-xs text-slate-800 dark:text-white rounded-xl px-3 py-2 outline-none cursor-pointer shadow-sm"
            >
              {elections.map((el) => (
                <option key={el.election_id} value={el.election_id} className="bg-white dark:bg-[#0b1022] text-slate-800 dark:text-white">
                  {el.algorithm.toUpperCase()} | {el.election_id.slice(-8)} | Winner: Node {el.winner_id ?? '?'}
                </option>
              ))}
            </select>

            <button
              onClick={() => setActiveTab('dashboard')}
              className="p-2 rounded-xl bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-600 dark:text-[var(--mute)] hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col justify-between">
          {events.length === 0 ? (
            <div className="text-center py-24 text-slate-500 dark:text-[var(--mute)]">
              No events found for this election. Run an election first!
            </div>
          ) : (
            <>
              {/* Event Spotlight Card */}
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-[#0a1020] border border-amber-300/40 dark:border-[#e8c36a]/30 shadow-xl">
                  <div className="flex justify-between items-center text-xs mb-3">
                    <span className="font-mono text-amber-700 dark:text-[#e8c36a] font-bold">
                      Lamport Clock: L={currentEvent?.lamport ?? 0}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/10 text-[10px] text-slate-600 dark:text-[var(--mute)] font-semibold">
                      Step {currentIndex + 1} of {events.length}
                    </span>
                  </div>

                  <div className="text-3xl font-cinzel font-bold text-amber-800 dark:text-[var(--gold)] mb-2">
                    {currentEvent?.msg_type || currentEvent?.event_type}
                  </div>

                  <div className="text-sm text-slate-700 dark:text-[var(--ink)] mb-3">
                    {currentEvent?.from_node !== undefined && currentEvent?.to_node !== undefined ? (
                      <span>
                        Transmitted from <strong className="text-amber-700 dark:text-[var(--gold)]">Node {currentEvent.from_node}</strong> ➔{' '}
                        <strong className="text-amber-700 dark:text-[var(--gold)]">Node {currentEvent.to_node}</strong>
                      </span>
                    ) : (
                      <span>Recorded on Node {currentEvent?.node_id}</span>
                    )}
                  </div>

                  <div className="text-[11px] font-mono text-slate-700 dark:text-[var(--mute)] bg-slate-100 dark:bg-[#050810] p-2.5 rounded-xl border border-slate-200 dark:border-white/5">
                    {currentEvent?.details_json}
                  </div>
                </div>
              </div>

              {/* Scrubber & Controls */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#0a0f20] border border-slate-200 dark:border-white/10 shadow-sm">
                <div className="flex items-center gap-4 mb-3">
                  <input
                    type="range"
                    min="0"
                    max={events.length - 1}
                    value={currentIndex}
                    onChange={(e) => {
                      setIsPlaying(false);
                      setCurrentIndex(Number(e.target.value));
                    }}
                    className="flex-1 accent-[#e8c36a] cursor-pointer"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-bold text-xs shadow-md shadow-amber-500/20 hover:scale-105 active:scale-95 transition-all cursor-pointer"
                    >
                      {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
                      <span>{isPlaying ? 'Pause' : 'Play Timeline'}</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        setCurrentIndex(0);
                      }}
                      className="p-2 rounded-xl bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-600 dark:text-[var(--mute)] hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
                      title="Rewind to start"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  </div>

                  <span className="text-xs font-mono text-slate-600 dark:text-[var(--mute)] font-semibold">
                    {Math.round(((currentIndex + 1) / events.length) * 100)}% Replayed
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
