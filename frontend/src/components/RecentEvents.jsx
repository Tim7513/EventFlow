/**
 * Table of recent events with type-filter and auto-refresh countdown.
 */
import { useState } from "react";

const TYPE_BADGE_COLORS = {
  purchase: "#10b981",
  view: "#6366f1",
  click: "#f59e0b",
  signup: "#3b82f6",
  refund: "#ef4444",
  error: "#f97316",
};

function badgeColor(type) {
  return TYPE_BADGE_COLORS[type] ?? "#8b5cf6";
}

function relativeTime(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

export default function RecentEvents({ events, loading, typeFilter, onTypeFilterChange, countdown }) {
  const [expandedId, setExpandedId] = useState(null);

  return (
    <div className="card recent-card">
      <div className="recent-header">
        <h2 className="card-title">Recent Events</h2>
        <div className="recent-controls">
          <select
            className="filter-select"
            value={typeFilter}
            onChange={(e) => onTypeFilterChange(e.target.value)}
            aria-label="Filter by type"
          >
            <option value="">All types</option>
            <option value="purchase">purchase</option>
            <option value="view">view</option>
            <option value="click">click</option>
            <option value="signup">signup</option>
            <option value="refund">refund</option>
            <option value="error">error</option>
          </select>
          <span className="refresh-countdown" title="Auto-refreshing">
            ↻ {countdown}s
          </span>
        </div>
      </div>

      {loading && !events.length ? (
        <div className="table-placeholder">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton row-skeleton" aria-busy="true" />
          ))}
        </div>
      ) : !events.length ? (
        <div className="empty-state">
          {typeFilter ? `No "${typeFilter}" events found.` : "No events yet."}
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="events-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Value</th>
                <th>Created</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <>
                  <tr
                    key={ev.event_id}
                    className={`event-row ${expandedId === ev.event_id ? "expanded" : ""}`}
                    onClick={() =>
                      setExpandedId(expandedId === ev.event_id ? null : ev.event_id)
                    }
                    title="Click to expand"
                  >
                    <td>
                      <span
                        className="type-badge"
                        style={{ background: badgeColor(ev.event_type) + "22", color: badgeColor(ev.event_type) }}
                      >
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="value-cell">
                      {typeof ev.value === "number" ? ev.value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : ev.value}
                    </td>
                    <td className="time-cell" title={ev.created_at}>
                      {relativeTime(ev.created_at)}
                    </td>
                    <td className="id-cell">{ev.event_id.slice(0, 8)}…</td>
                  </tr>
                  {expandedId === ev.event_id && (
                    <tr key={`${ev.event_id}-detail`} className="detail-row">
                      <td colSpan={4}>
                        <pre className="detail-json">
                          {JSON.stringify(ev, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
