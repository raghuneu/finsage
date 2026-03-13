import { useState } from "react";

const INITIAL_VARS = {
  data: [
    {
      name: "stock_prices",
      type: "DataFrame",
      desc: "AAPL OHLCV weekly data (Jan–Mar 2025)",
    },
    { name: "fundamentals", type: "JSON", desc: "Revenue, EPS, P/E, margins" },
    { name: "sec_filings", type: "JSON", desc: "10-K XBRL financial concepts" },
  ],
  tools: [
    {
      name: "Calculate_Metrics",
      desc: "Compute financial ratios & growth rates",
    },
    { name: "Web_Search", desc: "Search the web for information" },
    { name: "Plot_Chart", desc: "Generate visualization from data" },
  ],
  agents: [
    {
      name: "Deep_Search_Agent",
      desc: "Iterative multi-round web investigation",
    },
    { name: "Data_Collection_Agent", desc: "Fetch data from APIs & databases" },
    { name: "Report_Generation_Agent", desc: "Draft & optimize final report" },
  ],
};

const MOCK_STEPS = [
  {
    type: "data",
    reasoning:
      "Before performing any analysis, I need to load available data into working memory. Starting with stock prices and fundamentals gives me the quantitative foundation for all subsequent steps.",
    code: 'stock_df    = call_data("stock_prices")\nfundamentals = call_data("fundamentals")\nprint(f"Latest close: ${stock_df[\'close\'].iloc[-1]:.2f}, Revenue: {fundamentals[\'revenue\']}")',
    output: "Latest close: $262.18, Revenue: $124.3B",
    new_variable: null,
    final_insight: null,
  },
  {
    type: "tool",
    reasoning:
      "With AAPL at $262.18, I need to compute quantitative metrics — volatility, momentum, and Sharpe ratio — to contextualize this price action before forming analytical conclusions.",
    code: 'metrics = call_tool("Calculate_Metrics",\n  data=stock_df,\n  metrics=["volatility", "sharpe_ratio", "momentum"])\nprint(metrics)',
    output:
      "30-day volatility: 18.3%  |  Sharpe ratio: 1.42\nMomentum score: +0.72    |  Beta: 1.18",
    new_variable: {
      name: "aapl_metrics",
      type: "JSON",
      desc: "Computed risk and performance metrics",
    },
    final_insight: null,
  },
  {
    type: "agent",
    reasoning:
      "Metrics confirm strong momentum (0.72) and risk-adjusted returns (Sharpe 1.42). Now I need competitive context — invoking Deep_Search_Agent to investigate AAPL's positioning vs Samsung and Google in 2025.",
    code: 'competitive_intel = call_agent("Deep_Search_Agent",\n  query="AAPL competitive landscape vs Samsung Google 2025")\nprint(competitive_intel)',
    output:
      "Apple holds 18% global smartphone share. Services revenue\n($26.3B) growing 14% YoY, outpacing hardware. Google Pixel\ngaining premium share; Samsung Galaxy S25 competition\nintensifying in Asia markets.",
    new_variable: {
      name: "competitive_analysis",
      type: "TEXT",
      desc: "Competitive intelligence from web research",
    },
    final_insight: null,
  },
  {
    type: "synthesis",
    reasoning:
      "All data sources loaded. Synthesizing quantitative metrics, fundamentals, and competitive intelligence into a final Chain-of-Analysis segment.",
    code: 'analysis = synthesize(stock_df, aapl_metrics, competitive_intel)\nsave_result(analysis, name="aapl_competitive_analysis")\nprint("CoA segment saved to variable space")',
    output: "CoA segment saved to variable space",
    new_variable: null,
    final_insight:
      "Apple demonstrates resilient competitive positioning with AAPL trading at $262.18, backed by a Sharpe ratio of 1.42 and momentum score of +0.72 — indicating strong risk-adjusted outperformance. Services revenue of $26.3B (+14% YoY) is becoming the dominant growth engine, reducing reliance on iPhone hardware cycles. While Google Pixel and Samsung Galaxy S25 intensify premium competition, Apple's 18% global market share remains stable and its ecosystem lock-in provides durable pricing power. The combination of gross margin expansion to 46.9% and accelerating services growth warrants a valuation re-rating toward software multiples.",
  },
];

const STEPS = [
  { label: "View Variable Space", icon: "🗂️" },
  { label: "Step 1: call_data", icon: "📊" },
  { label: "Step 2: call_tool", icon: "🔧" },
  { label: "Step 3: call_agent", icon: "🤖" },
  { label: "Step 4: Synthesize", icon: "✨" },
];

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

export default function CavmDemo() {
  const [phase, setPhase] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState<any[]>([]);
  const [newVars, setNewVars] = useState<any[]>([]);

  const run = async () => {
    const next = phase + 1;
    setLoading(true);
    await delay(1000 + Math.random() * 600);

    if (next > 0) {
      const s = MOCK_STEPS[next - 1];
      setSteps((prev) => [...prev, s]);
      if (s.new_variable) setNewVars((prev) => [...prev, s.new_variable]);
      if (s.type === "synthesis")
        setNewVars((prev) => [
          ...prev,
          {
            name: "aapl_competitive_analysis",
            type: "CoA",
            desc: "Final Chain-of-Analysis segment",
          },
        ]);
    }

    setPhase(next);
    setLoading(false);
  };

  const typeColors: Record<string, string> = {
    data: "text-blue-400",
    tool: "text-amber-400",
    agent: "text-purple-400",
    synthesis: "text-emerald-400",
  };
  const typeBorders: Record<string, string> = {
    data: "border-blue-700/50",
    tool: "border-amber-700/50",
    agent: "border-purple-700/50",
    synthesis: "border-emerald-700/50",
  };
  const typeBgs: Record<string, string> = {
    data: "bg-blue-950/30",
    tool: "bg-amber-950/20",
    agent: "bg-purple-950/20",
    synthesis: "bg-emerald-950/20",
  };
  const typeLabels: Record<string, string> = {
    data: "call_data()",
    tool: "call_tool()",
    agent: "call_agent()",
    synthesis: "synthesize()",
  };
  const typeIcons: Record<string, string> = {
    data: "📊",
    tool: "🔧",
    agent: "🤖",
    synthesis: "✨",
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-5">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
            🗂️ Code Agent with Variable Memory (CAVM)
          </h1>
          <p className="text-gray-400 text-xs mt-1">
            Live Demo — FinSight Paper, Section 2.3 &nbsp;|&nbsp; Unified
            variable space: call data, tools &amp; agents through code
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
          {phase < 4 ? (
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
                  Agent thinking...
                </span>
              ) : (
                `${STEPS[phase + 1]?.icon} ${STEPS[phase + 1]?.label}`
              )}
            </button>
          ) : (
            <div className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-emerald-800/60 text-emerald-200 font-semibold text-sm ring-1 ring-emerald-600">
              ✅ Demo Complete — Full CAVM loop executed
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Variable Space Panel */}
          <div className="md:col-span-1">
            <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden sticky top-4">
              <div className="px-4 py-2 bg-gray-800/60 border-b border-gray-700">
                <h3 className="text-sm font-bold">Unified Variable Space</h3>
                <p className="text-xs text-gray-500">
                  V = V<sub>data</sub> ∪ V<sub>tool</sub> ∪ V<sub>agent</sub>
                </p>
              </div>
              <div className="p-3 space-y-3">
                <div>
                  <p className="text-xs font-semibold text-blue-400 mb-1.5">
                    📊 V<sub>data</sub>
                  </p>
                  <div className="space-y-1">
                    {INITIAL_VARS.data.map((d, i) => (
                      <div
                        key={i}
                        className="bg-blue-950/20 border border-blue-900/30 rounded px-2 py-1"
                      >
                        <p className="text-xs text-blue-200 font-mono">
                          {d.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {d.type} — {d.desc}
                        </p>
                      </div>
                    ))}
                    {newVars
                      .filter((v) => v.type === "JSON")
                      .map((v, i) => (
                        <div
                          key={i}
                          className="bg-blue-950/20 border border-blue-400/50 rounded px-2 py-1 ring-1 ring-blue-500/30"
                        >
                          <p className="text-xs text-blue-200 font-mono">
                            {v.name}{" "}
                            <span className="text-blue-400">✦ new</span>
                          </p>
                          <p className="text-xs text-gray-500">
                            {v.type} — {v.desc}
                          </p>
                        </div>
                      ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-amber-400 mb-1.5">
                    🔧 V<sub>tool</sub>
                  </p>
                  <div className="space-y-1">
                    {INITIAL_VARS.tools.map((t, i) => (
                      <div
                        key={i}
                        className="bg-amber-950/15 border border-amber-900/30 rounded px-2 py-1"
                      >
                        <p className="text-xs text-amber-200 font-mono">
                          {t.name}()
                        </p>
                        <p className="text-xs text-gray-500">{t.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-purple-400 mb-1.5">
                    🤖 V<sub>agent</sub>
                  </p>
                  <div className="space-y-1">
                    {INITIAL_VARS.agents.map((a, i) => (
                      <div
                        key={i}
                        className="bg-purple-950/15 border border-purple-900/30 rounded px-2 py-1"
                      >
                        <p className="text-xs text-purple-200 font-mono">
                          {a.name}
                        </p>
                        <p className="text-xs text-gray-500">{a.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
                {newVars
                  .filter((v) => v.type === "CoA" || v.type === "TEXT")
                  .map((v, i) => (
                    <div key={i}>
                      <p className="text-xs font-semibold text-emerald-400 mb-1.5">
                        ✨ Output
                      </p>
                      <div className="bg-emerald-950/20 border border-emerald-400/50 rounded px-2 py-1 ring-1 ring-emerald-500/30">
                        <p className="text-xs text-emerald-200 font-mono">
                          {v.name}{" "}
                          <span className="text-emerald-400">✦ new</span>
                        </p>
                        <p className="text-xs text-gray-500">
                          {v.type} — {v.desc}
                        </p>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Execution Panel */}
          <div className="md:col-span-2">
            {phase >= 0 ? (
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <div className="px-4 py-2 bg-gray-800/60 border-b border-gray-700 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold">Agent Execution Trace</h3>
                    <p className="text-xs text-gray-500">
                      Task: "Analyze AAPL's competitive position and recent
                      performance"
                    </p>
                  </div>
                  <span className="text-xs text-gray-600">
                    {steps.length} / 4 steps
                  </span>
                </div>
                <div className="p-3 space-y-3">
                  {steps.length === 0 && (
                    <div className="text-center py-8">
                      <p className="text-gray-500 text-xs">
                        Variable space loaded. Click the next step to begin the
                        agent's execution loop.
                      </p>
                    </div>
                  )}
                  {steps.map((s, i) => (
                    <div
                      key={i}
                      className={`border ${typeBorders[s.type]} ${typeBgs[s.type]} rounded-lg p-3`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm">{typeIcons[s.type]}</span>
                        <span
                          className={`text-xs font-bold ${typeColors[s.type]}`}
                        >
                          Step {i + 1}
                        </span>
                        <span
                          className={`text-xs font-mono px-1.5 py-0.5 rounded bg-gray-800 ${typeColors[s.type]}`}
                        >
                          {typeLabels[s.type]}
                        </span>
                      </div>
                      <div className="mb-2 bg-gray-800/50 rounded p-2">
                        <p className="text-xs text-gray-500 font-semibold mb-0.5">
                          💭 Reasoning:
                        </p>
                        <p className="text-xs text-gray-300 italic">
                          {s.reasoning}
                        </p>
                      </div>
                      <div className="mb-2 bg-gray-950 rounded p-2 font-mono">
                        <p className="text-xs text-gray-500 mb-1">
                          {"<execute>"}
                        </p>
                        <pre className="text-xs text-green-300 whitespace-pre-wrap leading-relaxed">
                          {s.code}
                        </pre>
                        <p className="text-xs text-gray-500 mt-1">
                          {"</execute>"}
                        </p>
                      </div>
                      <div className="bg-gray-800/50 rounded p-2">
                        <p className="text-xs text-gray-500 font-semibold mb-0.5">
                          📤 Output:
                        </p>
                        <p className="text-xs text-gray-300 whitespace-pre-wrap">
                          {s.output}
                        </p>
                      </div>
                      {s.final_insight && (
                        <div className="mt-2 bg-emerald-950/30 border border-emerald-700/40 rounded p-2">
                          <p className="text-xs text-emerald-400 font-semibold mb-0.5">
                            📋 Chain-of-Analysis Output:
                          </p>
                          <p className="text-xs text-emerald-200 leading-relaxed">
                            {s.final_insight}
                          </p>
                        </div>
                      )}
                      {s.new_variable && (
                        <div className="mt-2 flex items-center gap-1.5">
                          <span className="text-xs text-gray-600">→</span>
                          <span className={`text-xs ${typeColors[s.type]}`}>
                            Saved to variable space:
                          </span>
                          <span className="text-xs font-mono text-gray-300 bg-gray-800 px-1.5 py-0.5 rounded">
                            {s.new_variable.name}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-16">
                <p className="text-5xl mb-4">🗂️</p>
                <p className="text-gray-400 text-sm">
                  Click the button to view the unified variable space
                </p>
                <div className="mt-6 max-w-md mx-auto text-left bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <p className="text-gray-300 text-xs font-semibold mb-2">
                    CAVM Core Concept (FinSight §2.3):
                  </p>
                  <div className="space-y-1.5 text-xs text-gray-400">
                    <p>
                      1. All <span className="text-blue-400">data</span>,{" "}
                      <span className="text-amber-400">tools</span>, and{" "}
                      <span className="text-purple-400">agents</span> live in
                      one unified variable space
                    </p>
                    <p>
                      2. The agent interacts with everything through{" "}
                      <span className="text-green-400">executable code</span>
                    </p>
                    <p>
                      3. Each step:{" "}
                      <span className="text-gray-300">
                        reason → generate code → execute → update space
                      </span>
                    </p>
                    <p>
                      4. New outputs become variables future steps can access
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {phase >= 4 && (
          <div className="mt-4 bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-xs text-gray-400 mb-1">The key CAVM insight:</p>
            <p className="text-sm text-gray-200">
              <span className="text-blue-400">call_data()</span>,{" "}
              <span className="text-amber-400">call_tool()</span>, and{" "}
              <span className="text-purple-400">call_agent()</span> are all the{" "}
              <span className="text-white font-semibold">same interface</span> —
              the agent doesn't need separate APIs for each. This is what makes
              FinSight's architecture flexible and scalable.
            </p>
          </div>
        )}

        <div className="text-center mt-6 text-gray-600 text-xs">
          FinSight uses DeepSeek-V3 as backbone &nbsp;|&nbsp; This demo
          simulates the CAVM agent loop
        </div>
      </div>
    </div>
  );
}
