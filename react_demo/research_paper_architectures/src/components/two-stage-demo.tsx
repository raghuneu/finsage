import { useState } from "react";

const AAPL_DATA = {
  price: { current: 262.18, change: "+7.7%" },
  fundamentals: {
    revenue: "$124.3B (Q1 FY2025)",
    revenueGrowth: "+4.0% YoY",
    netIncome: "$36.3B",
    epsGrowth: "+10.2% YoY",
    peRatio: 31.2,
    forwardPE: 28.5,
    grossMargin: "46.9%",
    operatingMargin: "33.5%",
    cashOnHand: "$30.3B",
    totalDebt: "$97.3B",
    dividendYield: "0.44%",
    buybackQ1: "$23.5B",
  },
};

const MOCK_COAS = [
  {
    perspective: "Revenue & Growth Analysis",
    insight:
      "Apple reported Q1 FY2025 revenue of $124.3B (+4.0% YoY), with EPS growth of +10.2% outpacing top-line growth — signaling meaningful margin expansion. Services revenue reached an all-time high of $26.3B (+14% YoY), now comprising 21% of total revenue and driving gross margin to 46.9%. The divergence between hardware growth (~1% YoY) and services growth (~14% YoY) signals a structural shift toward higher-margin recurring revenue.",
    charts_referenced: [
      "Revenue breakdown: Products vs Services over 8 quarters (bar chart)",
    ],
  },
  {
    perspective: "Valuation & Market Position",
    insight:
      "At a trailing P/E of 31.2x and forward P/E of 28.5x, Apple trades at a premium to the S&P 500 (~22x) but at a discount to pure-play software peers (~40x), suggesting the market has not fully re-priced for its services mix shift. The $23.5B in Q1 buybacks (annualizing to ~$94B) provides ~3.5% annual share count reduction, mechanically supporting EPS growth. With $30.3B cash and $97.3B debt, net leverage is comfortably covered by $36.3B quarterly net income.",
    charts_referenced: [
      "P/E ratio comparison: AAPL vs S&P 500 vs software peers (grouped bar)",
    ],
  },
  {
    perspective: "Risk Assessment",
    insight:
      "Key risks include EU Digital Markets Act compliance costs of ~$500M annually (~40bps operating margin headwind) and Apple Vision Pro underperformance raising questions about Apple's next platform. China concentration (~17% of revenue) is a geopolitical wildcard, partially offset by iPhone share recovery vs Huawei. The stock's 18.3% 30-day volatility and 1.18 beta indicate above-market sensitivity to macro conditions.",
    charts_referenced: [
      "Geographic revenue concentration (pie chart)",
      "Volatility vs peers (line chart)",
    ],
  },
];

const MOCK_ONE_SHOT = `Apple Inc. delivered solid Q1 FY2025 results with revenue of $124.3B, up 4% year-over-year, supported by continued growth in its Services segment. The company's earnings per share grew 10.2%, reflecting ongoing cost discipline and an aggressive share buyback program of $23.5B in the quarter. While iPhone hardware growth remains modest, the Services division continues to be a bright spot for investors.

From a valuation standpoint, Apple trades at a P/E of 31.2x, which appears reasonable given its strong brand, ecosystem, and cash generation capabilities. The company maintains a solid balance sheet with $30.3B in cash, though total debt of $97.3B warrants monitoring. The 0.44% dividend yield is modest, but the real shareholder return comes from buybacks.

Looking ahead, Apple faces a mix of opportunities and challenges. The rollout of Apple Intelligence AI features could drive upgrade cycles, while regulatory pressures in the EU and competitive dynamics in China present headwinds. Overall, Apple remains a high-quality compounder for long-term investors, though near-term upside may be limited at current valuations.`;

const MOCK_TWO_STAGE = `Apple's financial engine is undergoing a structural transformation that raw revenue figures alone do not capture. While Q1 FY2025 top-line growth of +4.0% YoY to $124.3B appears modest, EPS growth of +10.2% reveals the real story: margin expansion driven by a deliberate mix shift toward Services. At $26.3B in Q1 — an all-time high representing 21% of revenue and growing at 14% YoY — the Services segment now contributes disproportionately to Apple's 46.9% gross margin. This divergence between hardware (~1% growth) and services (~14% growth) is the defining financial narrative for Apple's next decade.

Apple's valuation at 31.2x trailing P/E sits at a strategic inflection point. The market prices Apple as a hardware company with software optionality, yet the services mix shift increasingly warrants comparison to platform software peers trading at 40x+. The $23.5B quarterly buyback program — annualizing to roughly $94B — mechanically reduces share count by ~3.5% annually, providing an EPS tailwind independent of revenue growth. With net income of $36.3B against $97.3B total debt, leverage is well-covered, and the $30.3B cash position provides strategic flexibility. The forward P/E of 28.5x implies the market is beginning — but has not completed — re-rating Apple toward software multiples.

Risk factors are real but manageable in context. The EU Digital Markets Act introduces ~$500M in annual compliance costs (~40bps operating margin headwind), absorbable given Apple's 33.5% operating margin. Apple Vision Pro's underwhelming initial sales raise legitimate questions about Apple's next platform bet, though it is premature to declare failure for a first-generation spatial computing device. China concentration (~17% of revenue) remains a geopolitical wildcard, partially offset by iPhone share recovery vs Huawei. The stock's 18.3% 30-day volatility and 1.18 beta signal above-average macro sensitivity — investors should view pullbacks as accumulation opportunities given the structural services growth thesis.`;

const STEPS = [
  { label: "View Input Data", icon: "📋" },
  { label: "Generate CoA Segments", icon: "🔬" },
  { label: "One-Shot Report", icon: "📝" },
  { label: "Two-Stage Report", icon: "📊" },
];

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

export default function TwoStageDemo() {
  const [phase, setPhase] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [coas, setCoas] = useState<any[] | null>(null);
  const [oneShot, setOneShot] = useState<string | null>(null);
  const [twoStage, setTwoStage] = useState<string | null>(null);
  const [showData, setShowData] = useState(false);

  const run = async () => {
    const next = phase + 1;
    setLoading(true);
    await delay(1200 + Math.random() * 800);
    if (next === 0) setShowData(true);
    else if (next === 1) setCoas(MOCK_COAS);
    else if (next === 2) setOneShot(MOCK_ONE_SHOT);
    else if (next === 3) setTwoStage(MOCK_TWO_STAGE);
    setPhase(next);
    setLoading(false);
  };

  const loadingLabel = [
    "Generating CoA segments...",
    "Writing single-pass report...",
    "Writing two-stage report...",
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-5">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
            📝 Two-Stage Writing Framework
          </h1>
          <p className="text-gray-400 text-xs mt-1">
            Live Demo — FinSight Paper, Section 2.5 &nbsp;|&nbsp; CoA Generation
            → Structured Writing vs. Single-Pass
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
          {phase < 3 ? (
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
                  {loadingLabel[phase] ?? "Loading..."}
                </span>
              ) : (
                `${STEPS[phase + 1]?.icon} ${STEPS[phase + 1]?.label}`
              )}
            </button>
          ) : (
            <div className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-emerald-800/60 text-emerald-200 font-semibold text-sm ring-1 ring-emerald-600">
              ✅ Demo Complete — Compare the outputs below
            </div>
          )}
        </div>

        {/* Data panel */}
        {showData && (
          <div className="mb-5">
            <button
              onClick={() => setShowData((s) => !s)}
              className="text-xs text-gray-400 hover:text-gray-200 mb-2 flex items-center gap-1 cursor-pointer"
            >
              <span>📋</span> Input Data — AAPL Q4 2024 – Q1 2025
              <span className="text-gray-600 ml-1">(click to toggle)</span>
            </button>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <p className="text-gray-500 mb-1 font-semibold">Price</p>
                <p className="text-white font-medium">
                  ${AAPL_DATA.price.current}
                </p>
                <p className="text-emerald-400">
                  {AAPL_DATA.price.change} (1W)
                </p>
              </div>
              <div>
                <p className="text-gray-500 mb-1 font-semibold">Revenue</p>
                <p className="text-gray-300">
                  {AAPL_DATA.fundamentals.revenue}
                </p>
                <p className="text-emerald-400">
                  {AAPL_DATA.fundamentals.revenueGrowth}
                </p>
              </div>
              <div>
                <p className="text-gray-500 mb-1 font-semibold">Earnings</p>
                <p className="text-gray-300">
                  Net: {AAPL_DATA.fundamentals.netIncome}
                </p>
                <p className="text-emerald-400">
                  EPS {AAPL_DATA.fundamentals.epsGrowth}
                </p>
              </div>
              <div>
                <p className="text-gray-500 mb-1 font-semibold">Valuation</p>
                <p className="text-gray-300">
                  P/E: {AAPL_DATA.fundamentals.peRatio}
                </p>
                <p className="text-gray-300">
                  Fwd P/E: {AAPL_DATA.fundamentals.forwardPE}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* CoA Segments */}
        {coas && (
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-blue-400">
                STAGE 1
              </span>
              <span className="text-xs text-gray-500">
                Chain-of-Analysis Segments — {coas.length} perspectives
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {coas.map((c, i) => (
                <div
                  key={i}
                  className="bg-blue-950/30 border border-blue-800/40 rounded-lg p-3"
                >
                  <div className="flex items-start gap-2 mb-2">
                    <span className="bg-blue-700 text-white text-xs px-1.5 py-0.5 rounded font-bold shrink-0">
                      CoA {i + 1}
                    </span>
                    <p className="text-blue-200 text-xs font-semibold">
                      {c.perspective}
                    </p>
                  </div>
                  <p className="text-gray-300 text-xs leading-relaxed mb-2">
                    {c.insight}
                  </p>
                  {c.charts_referenced.map((ch: string, j: number) => (
                    <p key={j} className="text-xs text-gray-500 italic">
                      📊 {ch}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Side-by-side */}
        {(oneShot || twoStage) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {oneShot && (
              <div className="rounded-xl border border-amber-600 bg-amber-900/15 overflow-hidden">
                <div className="px-4 py-2 border-b border-gray-700/50 bg-gray-800/40 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="bg-amber-700 text-white text-xs px-2 py-0.5 rounded font-bold">
                      Single-Pass
                    </span>
                    <span className="text-xs text-gray-400">
                      Analyze + Write simultaneously
                    </span>
                  </div>
                  <span className="text-xs text-amber-400 font-mono">
                    Ablation: ~5.9 analytical
                  </span>
                </div>
                <div className="p-4">
                  <p className="text-gray-300 text-xs leading-relaxed whitespace-pre-wrap">
                    {oneShot}
                  </p>
                </div>
              </div>
            )}
            {twoStage && (
              <div className="rounded-xl border border-emerald-500 bg-emerald-900/15 overflow-hidden">
                <div className="px-4 py-2 border-b border-gray-700/50 bg-gray-800/40 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="bg-emerald-700 text-white text-xs px-2 py-0.5 rounded font-bold">
                      Two-Stage
                    </span>
                    <span className="text-xs text-gray-400">
                      CoA → Structured Writing
                    </span>
                  </div>
                  <span className="text-xs text-emerald-400 font-mono">
                    Paper: ~7.9 analytical
                  </span>
                </div>
                <div className="p-4">
                  <p className="text-gray-300 text-xs leading-relaxed whitespace-pre-wrap">
                    {twoStage}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {twoStage && (
          <div className="mt-4 bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-xs text-gray-400 mb-1">
              From FinSight Ablation Study (Table 2):
            </p>
            <p className="text-sm text-gray-200">
              Removing two-stage writing dropped Analytical Quality from{" "}
              <span className="text-emerald-400 font-bold">7.9</span> →{" "}
              <span className="text-amber-400 font-bold">5.9</span> — the{" "}
              <span className="text-white font-semibold">
                biggest single-component impact
              </span>{" "}
              in the entire system
            </p>
          </div>
        )}

        {phase < 0 && (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">📝</p>
            <p className="text-gray-400 text-sm">
              Click the button above to start the demo
            </p>
            <div className="mt-6 max-w-lg mx-auto text-left bg-gray-900 rounded-lg p-4 border border-gray-800">
              <p className="text-gray-300 text-xs font-semibold mb-2">
                How it works (from FinSight §2.5):
              </p>
              <div className="space-y-1.5 text-xs text-gray-400">
                <p>
                  1. <span className="text-blue-400">Stage 1</span> — Generate
                  Chain-of-Analysis segments from multiple perspectives
                </p>
                <p>
                  2. <span className="text-amber-400">Baseline</span> —
                  Single-pass: analyze and write simultaneously
                </p>
                <p>
                  3. <span className="text-emerald-400">Stage 2</span> — Write
                  structured report using CoA segments as foundation
                </p>
                <p>4. Compare the two outputs side by side</p>
              </div>
            </div>
          </div>
        )}

        <div className="text-center mt-6 text-gray-600 text-xs">
          FinSight uses DeepSeek-V3 + R1 for writing &nbsp;|&nbsp; This demo
          simulates the two-stage writing process
        </div>
      </div>
    </div>
  );
}
