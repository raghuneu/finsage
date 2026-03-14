import { useState } from "react";
import CavmDemo from "./components/cavm-demo";
import TwoStageDemo from "./components/two-stage-demo";
import VisionDemo from "./components/vision-demo";

const DEMOS = [
  {
    id: "cavm",
    label: "CAVM Architecture",
    icon: "🗂️",
    subtitle: "Code Agent with Variable Memory",
    description:
      "Unified variable space where data, tools, and agents coexist — all accessible through executable code.",
    section: "§2.3",
    color: "blue",
    component: <CavmDemo />,
  },
  {
    id: "two-stage",
    label: "Two-Stage Writing",
    icon: "📝",
    subtitle: "CoA → Structured Report",
    description:
      "Generate concise Chain-of-Analysis segments first, then expand into a full coherent report.",
    section: "§2.5",
    color: "emerald",
    component: <TwoStageDemo />,
  },
  {
    id: "vision",
    label: "Vision Enhancement",
    icon: "🔬",
    subtitle: "Iterative Chart Refinement",
    description:
      "LLM generates charts, VLM critiques them, LLM refines — repeated until professional quality.",
    section: "§2.4",
    color: "purple",
    component: <VisionDemo />,
  },
];

const colorMap: Record<string, string> = {
  blue: "border-blue-500/60 bg-blue-500/10 text-blue-300 shadow-blue-500/10",
  emerald:
    "border-emerald-500/60 bg-emerald-500/10 text-emerald-300 shadow-emerald-500/10",
  purple:
    "border-purple-500/60 bg-purple-500/10 text-purple-300 shadow-purple-500/10",
};

const activeMap: Record<string, string> = {
  blue: "bg-blue-600 text-white shadow-blue-500/20",
  emerald: "bg-emerald-600 text-white shadow-emerald-500/20",
  purple: "bg-purple-600 text-white shadow-purple-500/20",
};

export default function App() {
  const [active, setActive] = useState("cavm");
  const [started, setStarted] = useState(false);
  const current = DEMOS.find((d) => d.id === active)!;

  // Landing screen
  if (!started) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center px-4">
        {/* Title */}
        <h1 className="text-4xl sm:text-5xl font-extrabold text-center tracking-tight mb-3">
          <span className="text-white">Fin</span>
          <span className="text-blue-400">Sight</span>
          <span className="text-gray-500 font-light"> — US</span>
        </h1>
        <p className="text-gray-400 text-center text-sm sm:text-base max-w-xl mb-2">
          AI-Powered Financial Research Report Generator
        </p>
        <p className="text-gray-600 text-center text-xs max-w-lg mb-10">
          Based on{" "}
          <span className="text-gray-400 italic">
            "FinSight: Towards Real-World Financial Deep Research"
          </span>{" "}
          · Adapted for U.S. Markets on Snowflake
        </p>

        {/* Demo cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl w-full mb-10">
          {DEMOS.map((demo) => (
            <button
              key={demo.id}
              onClick={() => {
                setActive(demo.id);
                setStarted(true);
              }}
              className={`text-left p-4 rounded-xl border cursor-pointer transition-all hover:scale-105 hover:shadow-lg ${colorMap[demo.color]}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{demo.icon}</span>
                <span className="text-xs font-mono opacity-60">
                  {demo.section}
                </span>
              </div>
              <p className="font-semibold text-sm text-white mb-1">
                {demo.label}
              </p>
              <p className="text-xs opacity-70 leading-relaxed">
                {demo.description}
              </p>
            </button>
          ))}
        </div>

        {/* CTA */}
        <button
          onClick={() => setStarted(true)}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl text-sm shadow-lg shadow-blue-500/20 transition-all hover:scale-105 cursor-pointer"
        >
          Launch Interactive Demos →
        </button>

        {/* Footer */}
        <p className="mt-10 text-gray-700 text-xs text-center">
          Team 8 · Snowflake + Airflow + dbt + Cortex LLM
        </p>
      </div>
    );
  }

  // Demo screen
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Sticky Nav */}
      <div className="border-b border-gray-800 bg-gray-900/95 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          {/* Brand */}
          <button
            onClick={() => setStarted(false)}
            className="flex items-center gap-2 cursor-pointer group shrink-0"
          >
            <span className="text-lg font-extrabold">
              <span className="text-white">Fin</span>
              <span className="text-blue-400">Sight</span>
            </span>
            <span className="text-gray-600 text-xs group-hover:text-gray-400 transition-colors hidden sm:inline">
              ← back
            </span>
          </button>

          {/* Tabs */}
          <div className="flex gap-2 justify-center flex-1">
            {DEMOS.map((demo) => (
              <button
                key={demo.id}
                onClick={() => setActive(demo.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all cursor-pointer shadow-lg ${
                  active === demo.id
                    ? activeMap[demo.color]
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
                }`}
              >
                <span>{demo.icon}</span>
                <span className="hidden sm:inline">{demo.label}</span>
                <span className="text-xs font-mono opacity-50 hidden md:inline">
                  {demo.section}
                </span>
              </button>
            ))}
          </div>

          {/* Section label */}
          <div className="text-right shrink-0 hidden sm:block">
            <p className="text-xs text-gray-500">{current.subtitle}</p>
            <p className="text-xs text-gray-700 font-mono">{current.section}</p>
          </div>
        </div>
      </div>

      {/* Demo */}
      <div key={active}>{current.component}</div>
    </div>
  );
}
