import { useEffect, useRef } from 'react';
import { useClusterStore } from '../store/clusterStore';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);

  const setConnected = useClusterStore((s) => s.setConnected);
  const updateSnapshot = useClusterStore((s) => s.updateSnapshot);
  const handleEvent = useClusterStore((s) => s.handleEvent);
  const handleConfigChange = useClusterStore((s) => s.handleConfigChange);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) return;
        setConnected(true);
      };

      ws.onmessage = (event) => {
        if (unmounted) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'SNAPSHOT') {
            updateSnapshot(msg);
          } else if (msg.type === 'EVENT' || msg.event_type) {
            handleEvent(msg);
          } else if (msg.type === 'CONFIG_CHANGED') {
            handleConfigChange(msg);
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setConnected(false);
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [setConnected, updateSnapshot, handleEvent]);
}
