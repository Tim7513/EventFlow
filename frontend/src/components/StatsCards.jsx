/**
 * Top-row summary cards: total events, average value, unique types.
 */
export default function StatsCards({ stats, loading }) {
  const typeCount = stats ? Object.keys(stats.by_type || {}).length : 0;

  return (
    <div className="cards-row">
      <StatCard
        label="Total Events"
        value={stats ? stats.total_events.toLocaleString() : "—"}
        sub="processed"
        loading={loading}
        accent="indigo"
      />
      <StatCard
        label="Average Value"
        value={stats ? stats.average_value.toFixed(2) : "—"}
        sub="per event"
        loading={loading}
        accent="emerald"
      />
      <StatCard
        label="Total Value"
        value={stats ? stats.total_value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
        sub="cumulative"
        loading={loading}
        accent="amber"
      />
      <StatCard
        label="Event Types"
        value={stats ? typeCount : "—"}
        sub="distinct types"
        loading={loading}
        accent="rose"
      />
    </div>
  );
}

function StatCard({ label, value, sub, loading, accent }) {
  return (
    <div className={`card stat-card accent-${accent}`}>
      <span className="stat-label">{label}</span>
      {loading ? (
        <span className="stat-value skeleton" aria-busy="true">——</span>
      ) : (
        <span className="stat-value">{value}</span>
      )}
      <span className="stat-sub">{sub}</span>
    </div>
  );
}
