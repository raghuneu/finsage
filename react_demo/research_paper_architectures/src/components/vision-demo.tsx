import { useState } from "react";
import {
  ComposedChart,
  Line,
  Bar,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const RAW = [
  { date: "Jan 6", close: 243.36, volume: 40.5, high: 247.1, low: 240.8 },
  { date: "Jan 13", close: 248.13, volume: 38.2, high: 250.4, low: 245.6 },
  { date: "Jan 21", close: 241.84, volume: 55.1, high: 249.2, low: 239.5 },
  { date: "Jan 27", close: 249.72, volume: 45.8, high: 252.0, low: 247.3 },
  { date: "Feb 3", close: 253.2, volume: 41.3, high: 255.8, low: 251.1 },
  { date: "Feb 10", close: 247.88, volume: 48.7, high: 254.2, low: 245.9 },
  { date: "Feb 18", close: 255.64, volume: 53.2, high: 258.1, low: 253.4 },
  { date: "Feb 24", close: 252.12, volume: 39.6, high: 256.3, low: 250.8 },
  { date: "Mar 3", close: 259.45, volume: 50.1, high: 261.8, low: 256.2 },
  { date: "Mar 10", close: 262.18, volume: 55.4, high: 264.5, low: 259.3 },
];

const DATA = RAW.map((d, i, a) => ({
  ...d,
  ma5:
    i >= 4
      ? +(a.slice(i - 4, i + 1).reduce((s, x) => s + x.close, 0) / 5).toFixed(2)
      : null,
}));

type S = {
  key: string;
  name: string;
  type: "line" | "bar" | "area";
  color: string;
  yAxisId: "left" | "right";
  strokeWidth?: number;
  strokeDasharray?: string;
};
type ChartConfig = {
  title: string;
  series: S[];
  showGrid: boolean;
  showLegend: boolean;
  leftYAxisLabel: string;
  rightYAxisLabel: string;
};
type Iter = { config: ChartConfig; critique: string | null };

const MOCK: { config: ChartConfig; critique: string }[] = [
  {
    config: {
      title: "AAPL Stock Price",
      series: [
        {
          key: "close",
          name: "Close",
          type: "line",
          color: "#8884d8",
          yAxisId: "left",
        },
      ],
      showGrid: false,
      showLegend: false,
      leftYAxisLabel: "",
      rightYAxisLabel: "",
    },
    critique: `❌ No grid lines make it impossible to read precise price levels — viewers cannot accurately interpret values.
❌ Volume data is completely absent — a fundamental metric that provides context for price moves.
❌ No moving average overlay — analysts expect at minimum a 5-week MA to identify trends.
❌ Axis labels are missing — the left axis shows raw numbers with no "Price (USD)" label, making units ambiguous.`,
  },
  {
    config: {
      title: "AAPL Weekly Price & Volume (Jan-Mar 2025)",
      series: [
        {
          key: "close",
          name: "Close Price",
          type: "line",
          color: "#2563eb",
          yAxisId: "left",
          strokeWidth: 2,
        },
        {
          key: "ma5",
          name: "5-Week MA",
          type: "line",
          color: "#f59e0b",
          yAxisId: "left",
          strokeWidth: 1.5,
          strokeDasharray: "5 5",
        },
        {
          key: "volume",
          name: "Volume (M)",
          type: "bar",
          color: "#94a3b8",
          yAxisId: "right",
        },
      ],
      showGrid: true,
      showLegend: true,
      leftYAxisLabel: "Price (USD)",
      rightYAxisLabel: "Volume (M)",
    },
    critique: `✅ Significant improvement — dual-axis with volume bars, MA overlay, and grid lines are now present and readable.
⚠️ The close price is a thin line — an area fill would give more visual weight to the price trend for a professional look.
⚠️ High/low range data is available but unused — adding these as subtle reference lines would give analysts important price range context.`,
  },
  {
    config: {
      title: "AAPL Price Action & Volume — Q1 2025 (Weekly)",
      series: [
        {
          key: "close",
          name: "Close Price",
          type: "area",
          color: "#2563eb",
          yAxisId: "left",
          strokeWidth: 2,
        },
        {
          key: "ma5",
          name: "5-Week MA",
          type: "line",
          color: "#f59e0b",
          yAxisId: "left",
          strokeWidth: 2,
          strokeDasharray: "5 5",
        },
        {
          key: "high",
          name: "Weekly High",
          type: "line",
          color: "#16a34a",
          yAxisId: "left",
          strokeWidth: 1,
          strokeDasharray: "3 3",
        },
        {
          key: "low",
          name: "Weekly Low",
          type: "line",
          color: "#dc2626",
          yAxisId: "left",
          strokeWidth: 1,
          strokeDasharray: "3 3",
        },
        {
          key: "volume",
          name: "Volume (M)",
          type: "bar",
          color: "#94a3b8",
          yAxisId: "right",
        },
      ],
      showGrid: true,
      showLegend: true,
      leftYAxisLabel: "Price (USD)",
      rightYAxisLabel: "Volume (M)",
    },
    critique: `✅ APPROVED — This chart meets professional equity research standards: the area fill provides clear visual weight to price trends, the dual-axis cleanly separates price and volume, the MA overlay uses conventional dashed styling, and the high/low reference lines add meaningful price range context without visual clutter.`,
  },
];

const STEPS = [
  { label: "Generate Basic Chart", icon: "📊" },
  { label: "VLM Critique #1", icon: "🔍" },
  { label: "Improve Chart", icon: "🔄" },
  { label: "VLM Critique #2", icon: "🔍" },
  { label: "Final Refinement", icon: "✨" },
  { label: "Final Review", icon: "✅" },
];

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

const ChartView = ({ config }: { config: ChartConfig }) => {
  const hasR = config.series.some((s) => s.yAxisId === "right");
  return (
    <div className="bg-white rounded-lg p-3">
      <p className="text-center font-semibold text-gray-800 text-sm mb-1">
        {config.title}
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart
          data={DATA}
          margin={{ top: 5, right: hasR ? 35 : 15, bottom: 0, left: 10 }}
        >
          {config.showGrid && (
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          )}
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#374151" }} />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 9, fill: "#374151" }}
            width={45}
            domain={["auto", "auto"]}
            label={
              config.leftYAxisLabel
                ? {
                    value: config.leftYAxisLabel,
                    angle: -90,
                    position: "insideLeft",
                    style: { fontSize: 9, fill: "#6b7280" },
                  }
                : undefined
            }
          />
          {hasR && (
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 9 }}
              width={40}
              label={
                config.rightYAxisLabel
                  ? {
                      value: config.rightYAxisLabel,
                      angle: 90,
                      position: "insideRight",
                      style: { fontSize: 9, fill: "#6b7280" },
                    }
                  : undefined
              }
            />
          )}
          <Tooltip
            contentStyle={{
              fontSize: 11,
              backgroundColor: "#1e293b",
              border: "1px solid #475569",
              borderRadius: 8,
              color: "#f1f5f9",
            }}
            labelStyle={{ color: "#93c5fd", fontWeight: 600 }}
          />
          {config.showLegend && <Legend wrapperStyle={{ fontSize: 10 }} />}
          {config.series.map((s, i) => {
            const base = {
              key: i,
              dataKey: s.key,
              name: s.name,
              yAxisId: s.yAxisId,
            };
            if (s.type === "bar")
              return <Bar {...base} fill={s.color} opacity={0.5} />;
            if (s.type === "area")
              return (
                <Area
                  {...base}
                  stroke={s.color}
                  fill={s.color}
                  fillOpacity={0.15}
                  strokeWidth={s.strokeWidth ?? 2}
                />
              );
            return (
              <Line
                {...base}
                stroke={s.color}
                dot={false}
                strokeWidth={s.strokeWidth ?? 2}
                strokeDasharray={s.strokeDasharray}
                connectNulls={false}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default function VisionDemo() {
  const [iters, setIters] = useState<Iter[]>([]);
  const [phase, setPhase] = useState(-1);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    const next = phase + 1;
    setLoading(true);
    await delay(1100 + Math.random() * 700);

    if (next === 0) setIters([{ config: MOCK[0].config, critique: null }]);
    else if (next === 1)
      setIters((p) =>
        p.map((it, i) =>
          i === 0 ? { ...it, critique: MOCK[0].critique } : it,
        ),
      );
    else if (next === 2)
      setIters((p) => [...p, { config: MOCK[1].config, critique: null }]);
    else if (next === 3)
      setIters((p) =>
        p.map((it, i) =>
          i === 1 ? { ...it, critique: MOCK[1].critique } : it,
        ),
      );
    else if (next === 4)
      setIters((p) => [...p, { config: MOCK[2].config, critique: null }]);
    else if (next === 5)
      setIters((p) =>
        p.map((it, i) =>
          i === 2 ? { ...it, critique: MOCK[2].critique } : it,
        ),
      );

    setPhase(next);
    setLoading(false);
  };

  const labels = [
    "Iteration 1 — Basic",
    "Iteration 2 — Improved",
    "Iteration 3 — Professional",
  ];
  const borders = ["border-gray-600", "border-blue-500", "border-emerald-500"];
  const bgs = ["bg-gray-800/40", "bg-blue-900/20", "bg-emerald-900/20"];

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-5">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
            🔬 Iterative Vision-Enhanced Mechanism
          </h1>
          <p className="text-gray-400 text-xs mt-1">
            Live Demo — FinSight Paper, Section 2.4 &nbsp;|&nbsp; LLM generates
            → VLM critiques → refine → repeat
          </p>
        </div>

        <div className="flex flex-wrap justify-center gap-1.5 mb-5">
          {STEPS.map((s, i) => (
            <div
              key={i}
              className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1 transition-all duration-300 ${
                i < phase + 1
                  ? "bg-blue-600 text-white"
                  : i === phase + 1 && !loading
                    ? "bg-gray-700 text-gray-200 ring-1 ring-gray-500"
                    : "bg-gray-800/60 text-gray-500"
              }`}
            >
              <span>{s.icon}</span>
              <span className="hidden md:inline">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="text-center mb-6">
          {phase < 5 ? (
            <button
              onClick={run}
              disabled={loading}
              className={`px-6 py-2.5 rounded-lg font-semibold text-sm shadow-lg transition-all ${
                loading
                  ? "bg-gray-700 text-gray-400 cursor-wait"
                  : "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer hover:shadow-blue-500/25"
              }`}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="inline-block w-4 h-4 border-2 border-gray-400 border-t-white rounded-full animate-spin" />
                  Processing...
                </span>
              ) : (
                `${STEPS[phase + 1]?.icon} ${STEPS[phase + 1]?.label}`
              )}
            </button>
          ) : (
            <div className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-emerald-800/60 text-emerald-200 font-semibold text-sm ring-1 ring-emerald-600">
              ✅ Demo Complete — All 3 Iterations Finished
            </div>
          )}
        </div>

        {iters.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {iters.map((it, i) => (
              <div
                key={i}
                className={`rounded-xl border ${borders[i]} ${bgs[i]} overflow-hidden transition-all duration-500`}
              >
                <div className="px-4 py-2 border-b border-gray-700/50 bg-gray-800/40">
                  <h3 className="font-semibold text-sm">{labels[i]}</h3>
                </div>
                <div className="p-3">
                  <ChartView config={it.config} />
                  {it.critique && (
                    <div
                      className={`mt-3 p-3 rounded-lg text-xs leading-relaxed border ${
                        i === 2
                          ? "bg-emerald-900/30 border-emerald-700/50 text-emerald-200"
                          : "bg-amber-900/20 border-amber-700/40 text-amber-200"
                      }`}
                    >
                      <p className="font-semibold mb-1 opacity-70">
                        {i === 2 ? "VLM Final Review:" : "VLM Critique:"}
                      </p>
                      <p className="whitespace-pre-wrap">{it.critique}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">📈</p>
            <p className="text-gray-400 text-sm">
              Click the button above to start the demo
            </p>
            <p className="text-gray-600 text-xs mt-2">
              AAPL stock data &nbsp;•&nbsp; Basic → Improved → Professional
            </p>
            <div className="mt-6 max-w-md mx-auto text-left bg-gray-900 rounded-lg p-4 border border-gray-800">
              <p className="text-gray-300 text-xs font-semibold mb-2">
                How it works (from FinSight §2.4):
              </p>
              <div className="space-y-1.5 text-xs text-gray-400">
                <p>
                  1. <span className="text-blue-400">LLM</span> generates chart
                  configuration from financial data
                </p>
                <p>
                  2. <span className="text-amber-400">VLM</span> critiques the
                  rendered chart for quality issues
                </p>
                <p>
                  3. Critique is fed back to the{" "}
                  <span className="text-blue-400">LLM</span> for refinement
                </p>
                <p>4. Repeat up to 3 iterations until professional quality</p>
              </div>
            </div>
          </div>
        )}

        <div className="text-center mt-6 text-gray-600 text-xs">
          FinSight uses matplotlib + Qwen2.5-VL-72B &nbsp;|&nbsp; This demo
          simulates the iterative refinement process
        </div>
      </div>
    </div>
  );
}
