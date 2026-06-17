/**
 * MetricsDashboard.jsx
 *
 * Campos reais do backend (sem total_users, sem conversion_rate, sem p_value):
 * {
 *   control_group: "A",
 *   recommended_group: "A",
 *   recommendation_reason: "...",
 *   lifts: {
 *     B: { gmv: 0.05, net_revenue: 0.10, roi: 0.08, margin: 0.03, avg_ticket: 0.02 }
 *   },
 *   groups: {
 *     A: {
 *       group_name: "A",
 *       buyers: 542,
 *       days: 30,
 *       gmv: 47200,
 *       commission: 4720,
 *       cashback: 3100,
 *       net_revenue: 1620,
 *       avg_ticket: 87.4,
 *       avg_cashback: 5.7,
 *       commission_per_buyer: 8.7,
 *       roi: 0.52,
 *       margin: 0.034,
 *     },
 *     B: { ... }
 *   },
 *   revenue_trend: [{ day: "2024-01-01", A: 1200, B: 1100 }]
 * }
 */

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid,
} from "recharts";

// ── PALETTE ───────────────────────────────────────────────────────────────
const GROUP_PALETTE = [
  "#378ADD",
  "#1D9E75",
  "#D85A30",
  "#BA7517",
  "#534AB7",
  "#993556",
];
const getColor = (i) => GROUP_PALETTE[i % GROUP_PALETTE.length];

// ── MOCK ──────────────────────────────────────────────────────────────────
const MOCK_METRICS = {
  control_group: "A",
  recommended_group: "A",
  recommendation_reason: "Grupo A possui maior ROI (0.52) e receita líquida positiva.",
  lifts: {
    B: { gmv: 0.161, net_revenue: -0.95, roi: -0.97, margin: -0.97, avg_ticket: 0.04 },
  },
  groups: {
    A: {
      group_name: "A", buyers: 542, days: 30,
      gmv: 47200, commission: 4720, cashback: 3100, net_revenue: 1620,
      avg_ticket: 87.4, avg_cashback: 5.7, commission_per_buyer: 8.7,
      roi: 0.52, margin: 0.034,
    },
    B: {
      group_name: "B", buyers: 620, days: 30,
      gmv: 54800, commission: 5480, cashback: 5400, net_revenue: 80,
      avg_ticket: 91.2, avg_cashback: 8.7, commission_per_buyer: 8.9,
      roi: 0.015, margin: 0.001,
    },
  },
  revenue_trend: [
    { day: "Dia 1",  A: 1200,  B: 1100  },
    { day: "Dia 5",  A: 4100,  B: 4800  },
    { day: "Dia 10", A: 7200,  B: 8300  },
    { day: "Dia 14", A: 9400,  B: 11200 },
  ],
};

// ── FORMATTERS ────────────────────────────────────────────────────────────
const fmt = {
  pct:    (v) => `${(v * 100).toFixed(1)}%`,
  brl:    (v) => `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  brlInt: (v) => `R$ ${Number(v).toLocaleString("pt-BR")}`,
  int:    (v) => Number(v).toLocaleString("pt-BR"),
  ratio:  (v) => Number(v).toFixed(2),
};

const liftPct = (base, test) => {
  const EPS = 1e-9;
  if (!isFinite(base) || Math.abs(base) < EPS) return null;
  const delta = (test - base) / Math.abs(base);
  return isFinite(delta) ? delta * 100 : null;
};

// ── METRIC DEFINITIONS (apenas campos que existem no backend) ─────────────
const METRIC_DEFS = [
  { key: "buyers",               label: "Compradores",        format: fmt.int,    positive: true,  liftable: true  },
  { key: "gmv",                  label: "GMV",                format: fmt.brlInt, positive: true,  liftable: true  },
  { key: "commission",           label: "Comissão",           format: fmt.brlInt, positive: true,  liftable: true  },
  { key: "cashback",             label: "Cashback (custo)",   format: fmt.brlInt, positive: false, liftable: true  },
  { key: "net_revenue",          label: "Receita líquida",    format: fmt.brlInt, positive: true,  liftable: true  },
  { key: "roi",                  label: "ROI",                format: fmt.ratio,  positive: true,  liftable: true  },
  { key: "margin",               label: "Margem",             format: fmt.pct,    positive: true,  liftable: true  },
  { key: "avg_ticket",           label: "Ticket médio",       format: fmt.brl,    positive: true,  liftable: true  },
  { key: "avg_cashback",         label: "Cashback médio",     format: fmt.brl,    positive: false, liftable: true  },
  { key: "commission_per_buyer", label: "Comissão/comprador", format: fmt.brl,    positive: true,  liftable: true  },
];

// ── CUSTOM TOOLTIP ────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, formatValue }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#0f1e2e",
      border: "0.5px solid rgba(255,255,255,0.12)",
      borderRadius: 8, padding: "8px 12px", fontSize: 12,
    }}>
      {label && <p style={{ color: "#8BA7C7", marginBottom: 4 }}>{label}</p>}
      {payload.map((p) => (
        <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color, display: "inline-block" }} />
          <span style={{ color: "#e2e8f0" }}>
            {p.name}: <strong>{formatValue ? formatValue(p.value) : p.value}</strong>
          </span>
        </div>
      ))}
    </div>
  );
}

// ── STAT PILL ─────────────────────────────────────────────────────────────
function StatPill({ label, value, accent }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ fontSize: 10, color: "#8BA7C7", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, fontFamily: "monospace", color: accent ? "#1D9E75" : "#e2e8f0" }}>
        {value}
      </div>
    </div>
  );
}

// ── KPI CARD ──────────────────────────────────────────────────────────────
function KpiCard({ label, groupNames, groupColors, values, formatFn, positive }) {
  const controlVal = values[0];
  const testVal = values[values.length - 1];
  const delta = liftPct(controlVal, testVal);
  const isUp = delta !== null && delta >= 0;
  const deltaColor = delta === null ? "#8BA7C7"
    : isUp ? (positive ? "#1D9E75" : "#EF9F27") : "#D85A30";

  return (
    <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 8, padding: "12px 14px" }}>
      <div style={{ fontSize: 10, color: "#8BA7C7", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {groupNames.map((name, i) => (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{
              fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
              background: groupColors[i] + "26", color: groupColors[i], fontFamily: "monospace",
            }}>{name}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0", fontFamily: "monospace" }}>
              {formatFn(values[i])}
            </span>
          </div>
        ))}
      </div>
      {delta !== null && (
        <div style={{ marginTop: 8, fontSize: 11, fontWeight: 600, color: deltaColor }}>
          {isUp ? "↑" : "↓"} {Math.abs(delta).toFixed(1)}%
          {groupNames.length > 2 && (
            <span style={{ fontWeight: 400, color: "#8BA7C7" }}> ({groupNames[groupNames.length - 1]} vs {groupNames[0]})</span>
          )}
        </div>
      )}
    </div>
  );
}

// ── COMPARISON TABLE ──────────────────────────────────────────────────────
function ComparisonTable({ groupNames, groupColors, groupStats, controlGroup, lifts }) {
  const testGroups = groupNames.filter((n) => n !== controlGroup);

  const activeDefs = METRIC_DEFS.filter((def) =>
    groupNames.some((n) => groupStats[n]?.[def.key] != null)
  );

  const th = {
    fontSize: 11, color: "#8BA7C7", fontWeight: 500,
    padding: "6px 10px", textAlign: "right",
    borderBottom: "0.5px solid rgba(255,255,255,0.08)",
    whiteSpace: "nowrap",
  };
  const td = {
    padding: "7px 10px", textAlign: "right",
    color: "#e2e8f0", fontFamily: "monospace", fontSize: 12,
    borderBottom: "0.5px solid rgba(255,255,255,0.05)",
  };

  return (
    <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 8, padding: "14px 16px" }}>
      <div style={{ fontSize: 10, color: "#8BA7C7", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        Comparativo completo — todos os grupos
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 480 }}>
          <thead>
            <tr>
              <th style={{ ...th, textAlign: "left" }}>Métrica</th>
              {groupNames.map((name, i) => (
                <th key={name} style={{ ...th, color: groupColors[i] }}>
                  Grupo {name}{name === controlGroup ? " ★" : ""}
                </th>
              ))}
              {testGroups.map((name) => (
                <th key={`lift-${name}`} style={{ ...th }}>
                  Lift {name} vs {controlGroup}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeDefs.map((def, rowIdx) => {
              const isLast = rowIdx === activeDefs.length - 1;
              const rowTd = isLast ? { ...td, borderBottom: "none" } : td;
              const controlVal = groupStats[controlGroup]?.[def.key];

              return (
                <tr key={def.key}>
                  <td style={{ ...rowTd, textAlign: "left", fontFamily: "sans-serif", color: "#8BA7C7" }}>
                    {def.label}
                  </td>
                  {groupNames.map((name, i) => {
                    const val = groupStats[name]?.[def.key];
                    return (
                      <td key={name} style={{ ...rowTd, color: groupColors[i] }}>
                        {val != null ? def.format(val) : "—"}
                      </td>
                    );
                  })}
                  {testGroups.map((name) => {
                    const backendLift = lifts?.[name]?.[def.key];
                    const testVal = groupStats[name]?.[def.key];
                    const delta = backendLift != null
                      ? backendLift * 100
                      : (def.liftable && controlVal != null && testVal != null
                          ? liftPct(controlVal, testVal)
                          : null);

                    if (delta === null) {
                      return <td key={`lift-${name}`} style={rowTd}><span style={{ color: "#8BA7C7" }}>—</span></td>;
                    }

                    const isUp = delta >= 0;
                    const color = def.positive
                      ? (isUp ? "#1D9E75" : "#D85A30")
                      : (isUp ? "#D85A30" : "#1D9E75");

                    return (
                      <td key={`lift-${name}`} style={rowTd}>
                        <span style={{ color, fontWeight: 600 }}>
                          {isUp ? "+" : ""}{delta.toFixed(1)}%
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── BAR CHART ─────────────────────────────────────────────────────────────
function GroupBarChart({ title, metricKey, groupNames, groupColors, groupStats, formatValue }) {
  const chartData = groupNames.map((name) => ({
    name: `Grupo ${name}`,
    value: groupStats[name]?.[metricKey] ?? 0,
    fill: groupColors[groupNames.indexOf(name)],
  }));
  const maxVal = Math.max(...chartData.map((d) => d.value));

  return (
    <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 8, padding: "14px 16px" }}>
      <div style={{ fontSize: 10, color: "#8BA7C7", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        {title}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} barCategoryGap="35%">
          <XAxis dataKey="name" tick={{ fill: "#8BA7C7", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fill: "#8BA7C7", fontSize: 10 }} axisLine={false} tickLine={false}
            domain={[0, Math.ceil(maxVal * 1.35)]}
            tickFormatter={formatValue}
          />
          <Tooltip content={<ChartTooltip formatValue={formatValue} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey="value" radius={[5, 5, 0, 0]}>
            {chartData.map((e, i) => <Cell key={i} fill={e.fill} opacity={0.85} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── SKELETON ──────────────────────────────────────────────────────────────
function Skeleton({ height = 90 }) {
  return (
    <div style={{
      height, borderRadius: 8,
      background: "rgba(255,255,255,0.06)",
      animation: "pulse 1.5s ease-in-out infinite",
    }} />
  );
}

// ── MAIN ──────────────────────────────────────────────────────────────────
export default function MetricsDashboard({ result, loading }) {
  const data = result || MOCK_METRICS;

  const allGroupNames = Object.keys(data.groups ?? {}).sort((a, b) =>
    a === data.control_group ? -1 : b === data.control_group ? 1 : a.localeCompare(b)
  );
  const groupColors = allGroupNames.map((_, i) => getColor(i));
  const groupStats  = data.groups ?? {};
  const lifts       = data.lifts ?? {};
  const trendData   = data.revenue_trend ?? [];

  // KPI cards — apenas campos reais
  const kpiDefs = [
    { key: "buyers",      label: "Compradores",     format: fmt.int,    positive: true },
    { key: "gmv",         label: "GMV",              format: fmt.brlInt, positive: true },
    { key: "net_revenue", label: "Receita líquida",  format: fmt.brlInt, positive: true },
    { key: "roi",         label: "ROI",              format: fmt.ratio,  positive: true },
  ].filter((def) => allGroupNames.some((n) => groupStats[n]?.[def.key] != null));

  // Pill de dias de observação (pega do primeiro grupo)
  const days = groupStats[allGroupNames[0]]?.days;

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }`}</style>

      {/* ── RECOMENDAÇÃO ──────────────────────────────────────── */}
      {!loading && data.recommended_group && (
        <div style={{
          display: "flex", alignItems: "flex-start", gap: 10,
          background: "rgba(29,158,117,0.12)",
          border: "0.5px solid rgba(29,158,117,0.35)",
          borderRadius: 8, padding: "10px 14px", marginBottom: 14,
        }}>
          <span style={{ fontSize: 18, lineHeight: 1 }}></span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#1D9E75", marginBottom: 3 }}>
              Variante recomendada para escalar: Grupo {data.recommended_group}
            </div>
            {data.recommendation_reason && (
              <div style={{ fontSize: 11, color: "#8BA7C7" }}>{data.recommendation_reason}</div>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
            {[1,2,3,4].map(i => <Skeleton key={i} height={68} />)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
            {[1,2,3,4].map(i => <Skeleton key={i} height={100} />)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <Skeleton height={220} /><Skeleton height={220} />
          </div>
          <Skeleton height={200} />
          <Skeleton height={220} />
        </div>
      ) : (
        <>
          {/* ── STAT BAR ──────────────────────────────────────── */}
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${allGroupNames.length + (days ? 1 : 0)}, 1fr)`,
            gap: 8, marginBottom: 12,
          }}>
            {days != null && (
              <StatPill label="Dias observados" value={fmt.int(days)} />
            )}
            {allGroupNames.map((name, i) => (
              <StatPill
                key={name}
                label={`Compradores ${name}${name === data.control_group ? " ★" : ""}`}
                value={fmt.int(groupStats[name]?.buyers ?? 0)}
                accent={name === data.recommended_group}
              />
            ))}
          </div>

          {/* ── KPI CARDS ─────────────────────────────────────── */}
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${Math.min(kpiDefs.length, 4)}, 1fr)`,
            gap: 8, marginBottom: 12,
          }}>
            {kpiDefs.map((def) => (
              <KpiCard
                key={def.key}
                label={def.label}
                groupNames={allGroupNames}
                groupColors={groupColors}
                values={allGroupNames.map((n) => groupStats[n]?.[def.key] ?? 0)}
                formatFn={def.format}
                positive={def.positive}
              />
            ))}
          </div>

          {/* ── BAR CHARTS ────────────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
            <GroupBarChart
              title="Receita líquida por grupo"
              metricKey="net_revenue"
              groupNames={allGroupNames}
              groupColors={groupColors}
              groupStats={groupStats}
              formatValue={(v) => "R$" + (v / 1000).toFixed(1) + "k"}
            />
            <GroupBarChart
              title="ROI por grupo (receita líquida / cashback)"
              metricKey="roi"
              groupNames={allGroupNames}
              groupColors={groupColors}
              groupStats={groupStats}
              formatValue={(v) => Number(v).toFixed(2)}
            />
          </div>

          {/* ── LINE CHART: Revenue Trend ──────────────────────── */}
          {trendData.length > 0 && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 8, padding: "14px 16px", marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: "#8BA7C7", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Evolução da receita líquida
                </div>
                <div style={{ display: "flex", gap: 14 }}>
                  {allGroupNames.map((name, i) => (
                    <span key={name} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#8BA7C7" }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: groupColors[i], display: "inline-block" }} />
                      Grupo {name}
                    </span>
                  ))}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={190}>
                <LineChart data={trendData}>
                  <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="day" tick={{ fill: "#8BA7C7", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fill: "#8BA7C7", fontSize: 10 }} axisLine={false} tickLine={false}
                    tickFormatter={(v) => "R$" + (v / 1000).toFixed(0) + "k"}
                  />
                  <Tooltip content={<ChartTooltip formatValue={fmt.brlInt} />} />
                  {allGroupNames.map((name, i) => (
                    <Line
                      key={name}
                      type="monotone"
                      dataKey={name}
                      name={`Grupo ${name}`}
                      stroke={groupColors[i]}
                      strokeWidth={2}
                      dot={false}
                      strokeDasharray={i === 0 ? "5 3" : undefined}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* ── TABELA COMPLETA ───────────────────────────────── */}
          <ComparisonTable
            groupNames={allGroupNames}
            groupColors={groupColors}
            groupStats={groupStats}
            controlGroup={data.control_group}
            lifts={lifts}
          />
        </>
      )}
    </div>
  );
}