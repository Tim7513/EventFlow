/**
 * EventFlow Dashboard
 *
 * State:
 *  - stats / recentEvents fetched on mount and every REFRESH_INTERVAL_MS
 *  - typeFilter controls both the recent-events query and the chart highlight
 *  - countdown ticks every second to show the user when the next refresh fires
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { getStats, getRecentEvents } from "./api/client";
import StatsCards from "./components/StatsCards";
import TypeChart from "./components/TypeChart";
import SendEventForm from "./components/SendEventForm";
import RecentEvents from "./components/RecentEvents";
import { ToastContainer, useToasts } from "./components/Toast";

const REFRESH_MS = parseInt(import.meta.env.VITE_REFRESH_INTERVAL_MS ?? "5000", 10);

export default function App() {
  const [stats, setStats] = useState(null);
  const [recentEvents, setRecentEvents] = useState([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("");
  const [countdown, setCountdown] = useState(Math.floor(REFRESH_MS / 1000));
  const { toasts, addToast } = useToasts();

  // Track when the next refresh fires so the countdown is accurate
  const nextRefreshAt = useRef(Date.now() + REFRESH_MS);

  const fetchStats = useCallback(async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      addToast(`Stats error: ${err.message}`, "error");
    } finally {
      setStatsLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRecent = useCallback(async (filter = typeFilter) => {
    try {
      const data = await getRecentEvents({ limit: 25, type: filter || undefined });
      setRecentEvents(data.events ?? []);
    } catch (err) {
      addToast(`Recent events error: ${err.message}`, "error");
    } finally {
      setEventsLoading(false);
    }
  }, [typeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchRecent();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch recent events when type filter changes
  useEffect(() => {
    setEventsLoading(true);
    fetchRecent(typeFilter);
  }, [typeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh timer
  useEffect(() => {
    const refresh = () => {
      fetchStats();
      fetchRecent();
      nextRefreshAt.current = Date.now() + REFRESH_MS;
    };

    const refreshTimer = setInterval(refresh, REFRESH_MS);

    // Countdown tick
    const countdownTimer = setInterval(() => {
      const remaining = Math.max(0, Math.round((nextRefreshAt.current - Date.now()) / 1000));
      setCountdown(remaining);
    }, 1000);

    return () => {
      clearInterval(refreshTimer);
      clearInterval(countdownTimer);
    };
  }, [fetchStats, fetchRecent]);

  // Called after a successful POST /event — do an immediate refresh
  const handleEventSent = useCallback(() => {
    // Small delay so SQS has time to receive; stats won't update until processed
    setTimeout(() => {
      fetchRecent();
      fetchStats();
      nextRefreshAt.current = Date.now() + REFRESH_MS;
      setCountdown(Math.floor(REFRESH_MS / 1000));
    }, 800);
  }, [fetchRecent, fetchStats]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="8" fill="#6366f1"/>
              <path d="M8 22l6-12 4 8 3-5 3 9" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className="brand-name">EventFlow</span>
          </div>
          <div className="header-meta">
            <span className="status-dot" title="Connected" />
            <span className="status-label">Live</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <StatsCards stats={stats} loading={statsLoading} />

        <div className="middle-row">
          <TypeChart stats={stats} loading={statsLoading} />
          <SendEventForm onSuccess={handleEventSent} addToast={addToast} />
        </div>

        <RecentEvents
          events={recentEvents}
          loading={eventsLoading}
          typeFilter={typeFilter}
          onTypeFilterChange={setTypeFilter}
          countdown={countdown}
        />
      </main>

      <ToastContainer toasts={toasts} />
    </div>
  );
}
