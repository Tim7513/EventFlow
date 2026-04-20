/**
 * Horizontal bar chart showing event count and average value per type.
 * Uses Recharts for rendering.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";

const PALETTE = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444",
  "#3b82f6", "#8b5cf6", "#14b8a6", "#f97316",
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-label">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: <strong>{entry.value.toLocaleString()}</strong>
        </p>
      ))}
    </div>
  );
};

export default function TypeChart({ stats, loading }) {
  if (loading) {
    return (
      <div className="card chart-card">
        <h2 className="card-title">Events by Type</h2>
        <div className="chart-placeholder skeleton" aria-busy="true" />
      </div>
    );
  }

  const data = stats
    ? Object.entries(stats.by_type || {}).map(([type, d], i) => ({
        type,
        count: d.count,
        avg: parseFloat(d.average_value.toFixed(2)),
        color: PALETTE[i % PALETTE.length],
      }))
    : [];

  if (!data.length) {
    return (
      <div className="card chart-card">
        <h2 className="card-title">Events by Type</h2>
        <div className="empty-state">No events yet. Send some using the form →</div>
      </div>
    );
  }

  return (
    <div className="card chart-card">
      <h2 className="card-title">Events by Type</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="type"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="count"
            orientation="left"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <YAxis
            yAxisId="avg"
            orientation="right"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--surface-hover)" }} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
          <Bar yAxisId="count" dataKey="count" name="Count" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.type} fill={entry.color} />
            ))}
          </Bar>
          <Bar yAxisId="avg" dataKey="avg" name="Avg Value" fill="var(--text-muted)" opacity={0.4} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
