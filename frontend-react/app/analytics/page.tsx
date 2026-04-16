'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  IconButton,
  Grid,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { useTicker } from '@/lib/ticker-context';
import {
  fetchStockMetrics,
  fetchFundamentals,
  fetchSentiment,
  fetchSecFinancials,
} from '@/lib/api';
import SignalBadge from '@/components/SignalBadge';
import SectionHeader from '@/components/SectionHeader';
import PriceChart from '@/components/PriceChart';
import { ChartSkeleton } from '@/components/LoadingSkeleton';

function fmtMoney(val: number | null | undefined): string {
  if (val == null) return 'N/A';
  const abs = Math.abs(val);
  if (abs >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  return `$${val.toLocaleString()}`;
}

const CHART_COLORS = {
  primary: '#0382B7',
  bullish: '#9DCBB8',
  bearish: '#E58B6D',
  warning: '#F8CB86',
  accent: '#C96BAE',
  muted: '#6B6760',
  grid: '#E8E4DB40',
};

const tooltipStyle = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E8E4DB',
  borderRadius: 8,
};

function RawDataTable({ data }: { data: Record<string, unknown>[] }) {
  const [open, setOpen] = useState(false);
  if (!data || data.length === 0) return null;
  const cols = Object.keys(data[0]);

  return (
    <Box sx={{ mt: 2 }}>
      <Box
        onClick={() => setOpen(!open)}
        sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer', mb: 1 }}
      >
        <Typography variant="body2" sx={{ color: '#6B6760' }}>
          Raw Data
        </Typography>
        <IconButton size="small" sx={{ color: '#6B6760' }}>
          {open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={open}>
        <TableContainer sx={{ maxHeight: 300 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {cols.map((c) => (
                  <TableCell
                    key={c}
                    sx={{ backgroundColor: '#F5F3EE', color: '#6B6760', fontSize: '0.7rem', fontWeight: 600 }}
                  >
                    {c}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.slice(0, 30).map((row, i) => (
                <TableRow key={i}>
                  {cols.map((c) => (
                    <TableCell key={c} sx={{ fontSize: '0.75rem', borderColor: '#E8E4DB' }}>
                      {String(row[c] ?? '')}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Collapse>
    </Box>
  );
}

// ── Stock Metrics Tab ──────────────────────────────────────
function StockMetricsTab() {
  const { ticker } = useTicker();
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchStockMetrics(ticker)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <ChartSkeleton />;
  if (data.length === 0)
    return (
      <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: '#6B6760' }}>
        No stock metrics available.
      </Typography>
    );

  const latest = data[0];

  return (
    <Box>
      <SectionHeader title="Stock Metrics" subtitle="Price history, moving averages, and volatility" />
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" component="span" sx={{ color: '#6B6760' }}>
            Trend: <SignalBadge label={latest.TREND_SIGNAL as string} />
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Latest Close: <strong style={{ color: '#2C2A25' }}>${Number(latest.CLOSE).toFixed(2)}</strong>
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            30d Volatility:{' '}
            <strong style={{ color: '#2C2A25' }}>
              {latest.VOLATILITY_30D_PCT != null ? `${Number(latest.VOLATILITY_30D_PCT).toFixed(2)}%` : 'N/A'}
            </strong>
          </Typography>
        </Grid>
      </Grid>
      <Card sx={{ p: 2 }}>
        <PriceChart
          data={data.map((d) => ({
            date: String(d.DATE),
            open: d.OPEN as number,
            high: d.HIGH as number,
            low: d.LOW as number,
            close: d.CLOSE as number,
            volume: d.VOLUME as number,
            sma_7d: d.SMA_7D as number,
            sma_30d: d.SMA_30D as number,
            sma_90d: d.SMA_90D as number,
          }))}
          height={450}
        />
      </Card>
      <RawDataTable data={data} />
    </Box>
  );
}

// ── Fundamentals Tab ───────────────────────────────────────
function FundamentalsTab() {
  const { ticker } = useTicker();
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchFundamentals(ticker)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <ChartSkeleton />;
  if (data.length === 0)
    return (
      <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: '#6B6760' }}>
        No fundamentals data available.
      </Typography>
    );

  const latest = data[0];
  const sorted = [...data].reverse();

  return (
    <Box>
      <SectionHeader title="Fundamentals Growth" subtitle="Quarterly financials and growth rates" />
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" component="span" sx={{ color: '#6B6760' }}>
            Signal: <SignalBadge label={latest.FUNDAMENTAL_SIGNAL as string} />
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Revenue: <strong style={{ color: '#2C2A25' }}>{fmtMoney(latest.REVENUE as number)}</strong>
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            EPS: <strong style={{ color: '#2C2A25' }}>{latest.EPS != null ? `$${Number(latest.EPS).toFixed(2)}` : 'N/A'}</strong>
          </Typography>
        </Grid>
      </Grid>

      {/* Revenue bar chart */}
      <Card sx={{ p: 2, mb: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Quarterly Revenue
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="FISCAL_QUARTER" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} tickFormatter={(v) => fmtMoney(v)} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
              formatter={(value) => [fmtMoney(value as number), 'Revenue']}
            />
            <Bar dataKey="REVENUE" fill={CHART_COLORS.primary} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* EPS area chart */}
      <Card sx={{ p: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Earnings Per Share Trend
        </Typography>
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="FISCAL_QUARTER" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
              formatter={(value) => [`$${Number(value).toFixed(2)}`, 'EPS']}
            />
            <Area
              type="monotone"
              dataKey="EPS"
              stroke={CHART_COLORS.accent}
              fill="rgba(201,107,174,0.08)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
      <RawDataTable data={data} />
    </Box>
  );
}

// ── Sentiment Tab ──────────────────────────────────────────
function SentimentTab() {
  const { ticker } = useTicker();
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchSentiment(ticker)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <ChartSkeleton />;
  if (data.length === 0)
    return (
      <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: '#6B6760' }}>
        No sentiment data available.
      </Typography>
    );

  const latest = data[0];
  const sorted = [...data].reverse();

  return (
    <Box>
      <SectionHeader title="News Sentiment" subtitle="Daily sentiment aggregation from news articles" />
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" component="span" sx={{ color: '#6B6760' }}>
            Sentiment: <SignalBadge label={latest.SENTIMENT_LABEL as string} />
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Trend: <strong style={{ color: '#2C2A25' }}>{(latest.SENTIMENT_TREND as string) || 'N/A'}</strong>
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Articles Today: <strong style={{ color: '#2C2A25' }}>{String(latest.TOTAL_ARTICLES ?? 0)}</strong>
          </Typography>
        </Grid>
      </Grid>

      {/* Sentiment score line */}
      <Card sx={{ p: 2, mb: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Sentiment Score
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="NEWS_DATE" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
            />
            <Legend wrapperStyle={{ color: '#2C2A25', fontSize: 11 }} />
            <Line type="monotone" dataKey="SENTIMENT_SCORE" stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} name="Daily Score" />
            <Line type="monotone" dataKey="SENTIMENT_SCORE_7D_AVG" stroke={CHART_COLORS.warning} strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="7-Day Avg" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Stacked article bar */}
      <Card sx={{ p: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Article Sentiment Distribution
        </Typography>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="NEWS_DATE" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
            />
            <Legend wrapperStyle={{ color: '#2C2A25', fontSize: 11 }} />
            <Bar dataKey="POSITIVE_COUNT" stackId="a" fill={CHART_COLORS.bullish} name="Positive" />
            <Bar dataKey="NEGATIVE_COUNT" stackId="a" fill={CHART_COLORS.bearish} name="Negative" />
          </BarChart>
        </ResponsiveContainer>
      </Card>
      <RawDataTable data={data} />
    </Box>
  );
}

// ── SEC Financials Tab ─────────────────────────────────────
function SecFinancialsTab() {
  const { ticker } = useTicker();
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchSecFinancials(ticker)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <ChartSkeleton />;
  if (data.length === 0)
    return (
      <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: '#6B6760' }}>
        No SEC financial data available.
      </Typography>
    );

  const latest = data[0];
  const sorted = [...data].reverse().map((d) => ({
    ...d,
    PERIOD: `${d.FISCAL_YEAR} ${d.FISCAL_PERIOD}`,
  }));

  return (
    <Box>
      <SectionHeader title="SEC Financial Summary" subtitle="Financials extracted from SEC filings (XBRL)" />
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" component="span" sx={{ color: '#6B6760' }}>
            Health: <SignalBadge label={latest.FINANCIAL_HEALTH as string} />
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Revenue: <strong style={{ color: '#2C2A25' }}>{fmtMoney(latest.TOTAL_REVENUE as number)}</strong>
          </Typography>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            Net Margin:{' '}
            <strong style={{ color: '#2C2A25' }}>
              {latest.NET_MARGIN_PCT != null ? `${Number(latest.NET_MARGIN_PCT).toFixed(1)}%` : 'N/A'}
            </strong>
          </Typography>
        </Grid>
      </Grid>

      {/* Revenue bar */}
      <Card sx={{ p: 2, mb: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Revenue by Period
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="PERIOD" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} tickFormatter={(v) => fmtMoney(v)} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
              formatter={(value) => [fmtMoney(value as number), 'Revenue']}
            />
            <Bar dataKey="TOTAL_REVENUE" fill={CHART_COLORS.primary} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Margin dual-line */}
      <Card sx={{ p: 2 }}>
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
          Margin Trends
        </Typography>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={sorted}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis dataKey="PERIOD" tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} />
            <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#2C2A25' }}
              formatter={(value) => [`${Number(value).toFixed(1)}%`]}
            />
            <Legend wrapperStyle={{ color: '#2C2A25', fontSize: 11 }} />
            <Line type="monotone" dataKey="OPERATING_MARGIN_PCT" stroke={CHART_COLORS.bullish} strokeWidth={2} dot={{ r: 3 }} name="Operating Margin" />
            <Line type="monotone" dataKey="NET_MARGIN_PCT" stroke={CHART_COLORS.primary} strokeWidth={2} dot={{ r: 3 }} name="Net Margin" />
          </LineChart>
        </ResponsiveContainer>
      </Card>
      <RawDataTable data={data} />
    </Box>
  );
}

// ── Main Analytics Page ────────────────────────────────────
export default function AnalyticsPage() {
  const [tab, setTab] = useState(0);

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': { minHeight: 48 },
            '& .Mui-selected': { color: '#C96BAE' },
            '& .MuiTabs-indicator': { backgroundColor: '#C96BAE' },
          }}
        >
          <Tab label="Stock Metrics" />
          <Tab label="Fundamentals" />
          <Tab label="Sentiment" />
          <Tab label="SEC Financials" />
        </Tabs>
      </Card>
      {tab === 0 && <StockMetricsTab />}
      {tab === 1 && <FundamentalsTab />}
      {tab === 2 && <SentimentTab />}
      {tab === 3 && <SecFinancialsTab />}
    </Box>
  );
}
