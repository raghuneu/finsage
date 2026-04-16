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

export const startCAVMPipeline = (ticker: string, debug = false, skipCharts = false) =>
  api.post(`/api/report/cavm`, { ticker, debug, skip_charts: skipCharts }).then(r => r.data);

export const getCAVMStatus = (taskId: string) =>
  api.get(`/api/report/cavm/status/${taskId}`).then(r => r.data);

// Chat
export const askFinSage = (ticker: string, question: string) =>
  api.post(`/api/chat/ask`, { ticker, question }).then(r => r.data);

// Meta
export const fetchTickers = () =>
  api.get(`/api/tickers`).then(r => r.data);

export const fetchHealth = () =>
  api.get(`/api/health`).then(r => r.data);
