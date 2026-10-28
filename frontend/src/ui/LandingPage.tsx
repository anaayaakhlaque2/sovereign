import { useEffect, useState } from 'react';
import { Crown, Sparkles } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import { triggerElection } from '../lib/api';

export function LandingPage() {
  const showLanding = useClusterStore((s) => s.showLanding);
  const setShowLanding = useClusterStore((s) => s.setShowLanding);
  const setTheme = useClusterStore((s) => s.setTheme);

  // Transition state: 'idle' | 'blooming' | 'revealing'
  const [transitionStage, setTransitionStage] = useState<'idle' | 'blooming' | 'revealing'>('idle');
  const [progress, setProgress] = useState<number>(0);

  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'SOVEREIGN_START') {
        handleStart();
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const handleStart = () => {
    if (transitionStage !== 'idle') return;

    // 1. Initiate grand royal transition
    setTransitionStage('blooming');
    setProgress(15);

    // Progressive loading bar ticks for a satisfying, majestic duration
    const t1 = setTimeout(() => setProgress(55), 600);
    const t2 = setTimeout(() => setProgress(88), 1200);
    const t3 = setTimeout(() => setProgress(100), 1800);

    const t4 = setTimeout(() => {
      // 2. Switch theme to light ('day') and hide landing iframe
      setTheme('day');
      setShowLanding(false);
      setTransitionStage('revealing');

      // Ensure coronation is triggered if no leader is crowned yet
      if (!useClusterStore.getState().leader) {
        triggerElection();
      }

      // 3. Gracefully dissolve golden veil into the light 3D kingdom
      setTimeout(() => {
        setTransitionStage('idle');
        setProgress(0);
      }, 900);
    }, 2100);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  };

  if (!showLanding && transitionStage === 'idle') {
    return null;
  }

  return (
    <div
      className={`fixed inset-0 z-50 overflow-hidden transition-opacity duration-900 pointer-events-auto ${
        transitionStage === 'revealing' ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
    >
      {/* 3D Dark Atmospheric Landing Page */}
      {showLanding && (
        <iframe
          src="/landing.html"
          title="Sovereign 3D Story & Architecture"
          className="w-full h-full border-0 select-none"
        />
      )}

      {/* Cinematic Royal Golden Transition Veil */}
      {transitionStage !== 'idle' && (
        <div
          className={`fixed inset-0 z-50 pointer-events-none transition-all duration-700 ease-out flex flex-col items-center justify-center p-6 ${
            transitionStage === 'blooming'
              ? 'opacity-100 scale-100 bg-gradient-to-tr from-amber-400 via-amber-200 to-white'
              : 'opacity-0 scale-105 bg-white'
          }`}
        >
          <div className="flex flex-col items-center max-w-lg text-center animate-in zoom-in-95 duration-500">
            {/* Glowing Golden Royal Crest */}
            <div className="w-20 h-20 rounded-3xl bg-slate-950/10 border-2 border-amber-600/40 p-1 flex items-center justify-center mb-6 shadow-2xl shadow-amber-600/30 backdrop-blur-md">
              <Crown className="w-10 h-10 text-amber-900 animate-pulse" />
            </div>

            <h1 className="font-cinzel font-black text-4xl md:text-5xl tracking-[0.25em] text-slate-950 mb-3 drop-shadow-sm uppercase">
              ENTERING THE KINGDOM
            </h1>

            <p className="text-slate-800 text-sm md:text-base font-medium tracking-wide mb-8 max-w-md">
              Synchronizing Independent TCP Castles & Initializing Consensus Architecture
            </p>

            {/* Regal Shimmer Progress Bar */}
            <div className="w-64 md:w-80 h-2 bg-slate-950/15 rounded-full overflow-hidden p-0.5 border border-slate-950/20 shadow-inner">
              <div
                className="h-full bg-gradient-to-r from-amber-600 via-amber-700 to-slate-950 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>

            <span className="text-[11px] font-mono font-bold tracking-widest text-slate-700 uppercase mt-3">
              Cluster Readiness {progress}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
