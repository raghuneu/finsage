import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 300000, // 5 min for long-running Cortex calls
  headers: { 'Content-Type': 'application/json' },
});

// Dashboard
export const fetchKPIs = (ticker: string) =>
  api.get(`/api/dashboard/kpis`, { params: { ticker } }).then(r => r.data);

export const fetchPriceHistory = (ticker: string, days = 90) =>
  api.get(`/api/dashboard/price-history`, { params: { ticker, days } }).then(r => r.data);

export const fetchHeadlines = (ticker: string, limit = 10) =>
  api.get(`/api/dashboard/headlines`, { params: { ticker, limit } }).then(r => r.data);

// Analytics
export const fetchStockMetrics = (ticker: string, limit = 90) =>
  api.get(`/api/analytics/stock-metrics`, { params: { ticker, limit } }).then(r => r.data);

export const fetchFundamentals = (ticker: string, limit = 12) =>
  api.get(`/api/analytics/fundamentals`, { params: { ticker, limit } }).then(r => r.data);

export const fetchSentiment = (ticker: string, limit = 30) =>
  api.get(`/api/analytics/sentiment`, { params: { ticker, limit } }).then(r => r.data);

export const fetchSecFinancials = (ticker: string, limit = 10) =>
  api.get(`/api/analytics/sec-financials`, { params: { ticker, limit } }).then(r => r.data);

// SEC Filings
export const fetchFilings = (ticker: string) =>
  api.get(`/api/sec/filings`, { params: { ticker } }).then(r => r.data);

export const analyzeFilings = (ticker: string, mode: string) =>
  api.post(`/api/sec/analyze`, { ticker, mode }).then(r => r.data);

// Reports
export const generateQuickReport = (ticker: string) =>
  api.post(`/api/report/quick`, { ticker }).then(r => r.data);

export const startCAVMPipeline = (ticker: string, debug = false, skipCharts = false, detailLevel = 'detailed') =>
  api.post(`/api/report/cavm`, { ticker, debug, skip_charts: skipCharts, detail_level: detailLevel }).then(r => r.data);

export const getCAVMStatus = (taskId: string) =>
  api.get(`/api/report/cavm/status/${taskId}`).then(r => r.data);

export const fetchReportHistory = (ticker: string) =>
  api.get(`/api/report/history/${ticker}`).then(r => r.data);

// Chat
export const askFinSage = (ticker: string, question: string) =>
  api.post(`/api/chat/ask`, { ticker, question }).then(r => r.data);

// Observability
export const fetchHealthChecks = () =>
  api.get(`/api/observability/health-checks`).then(r => r.data);

export const fetchPipelineRuns = (limit = 50) =>
  api.get(`/api/observability/pipeline-runs`, { params: { limit } }).then(r => r.data);

export const fetchPipelineSummary = () =>
  api.get(`/api/observability/pipeline-runs/summary`).then(r => r.data);

export const fetchDataQuality = (days = 7) =>
  api.get(`/api/observability/data-quality`, { params: { days } }).then(r => r.data);

export const fetchLLMCalls = (limit = 50) =>
  api.get(`/api/observability/llm-calls`, { params: { limit } }).then(r => r.data);

export const fetchLLMSummary = () =>
  api.get(`/api/observability/llm-calls/summary`).then(r => r.data);

export const fetchQueryAttribution = () =>
  api.get(`/api/observability/query-attribution`).then(r => r.data);

// Report Chat (conversational Q&A about generated reports)
export const askReportChat = (ticker: string, sessionId: string, question: string) =>
  api.post(`/api/report_chat/ask`, { ticker, session_id: sessionId, question }).then(r => r.data);

export const resetReportChat = (sessionId: string) =>
  api.post(`/api/report_chat/reset`, { session_id: sessionId }).then(r => r.data);

// Meta
export const fetchTickers = () =>
  api.get(`/api/tickers`).then(r => r.data);

export const fetchHealth = () =>
  api.get(`/api/health`).then(r => r.data);
