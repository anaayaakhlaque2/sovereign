import { useEffect } from 'react';
import { SceneCanvas } from './scene/SceneCanvas';
import { Header } from './ui/Header';
import { NodeListPanel } from './ui/NodeListPanel';
import { MessageLogPanel } from './ui/MessageLogPanel';
import { ControlDock } from './ui/ControlDock';
import { NodeDetailCard } from './ui/NodeDetailCard';
import { AnalyticsModal } from './ui/AnalyticsModal';
import { ReplayModal } from './ui/ReplayModal';
import { LandingPage } from './ui/LandingPage';
import { useWebSocket } from './lib/useWebSocket';
import { useClusterStore } from './store/clusterStore';
import { assassinateLeader, toggleChaos, triggerElection } from './lib/api';

export function App() {
  // Connect WebSocket to Gateway
  useWebSocket();

  const chaos = useClusterStore((s) => s.chaos);
  const theme = useClusterStore((s) => s.theme);
  const setActiveTab = useClusterStore((s) => s.setActiveTab);

  // Sync theme with document class on mount / change
  useEffect(() => {
    if (theme === 'day') {
      document.documentElement.classList.add('theme-day');
      document.documentElement.classList.remove('theme-night');
    } else {
      document.documentElement.classList.add('theme-night');
      document.documentElement.classList.remove('theme-day');
    }
  }, [theme]);

  // Keyboard shortcuts (K: kill king, E: hold election, C: chaos)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is in an input
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      if (e.key === 'k' || e.key === 'K') {
        assassinateLeader();
      } else if (e.key === 'e' || e.key === 'E') {
        triggerElection();
      } else if (e.key === 'c' || e.key === 'C') {
        toggleChaos(!chaos);
      } else if (e.key === '1') {
        setActiveTab('dashboard');
      } else if (e.key === '2') {
        setActiveTab('analytics');
      } else if (e.key === '3') {
        setActiveTab('replay');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chaos, setActiveTab]);

  const isNight = theme === 'night';

  return (
    <div className={`relative w-screen h-screen overflow-hidden ${isNight ? 'bg-[#050810]' : 'bg-[#c8e2f8]'}`}>
      {/* 3D Scene Canvas */}
      <div className="absolute inset-0 z-0">
        <SceneCanvas />
      </div>

      {/* Floating UI Layer */}
      <Header />
      <NodeListPanel />
      <MessageLogPanel />
      <ControlDock />
      <NodeDetailCard />

      {/* Modals */}
      <AnalyticsModal />
      <ReplayModal />

      {/* 3D Dark Atmospheric Landing Page with Smooth Transition */}
      <LandingPage />
    </div>
  );
}

export default App;
