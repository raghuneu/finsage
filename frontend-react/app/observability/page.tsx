'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  Grid,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import {
  fetchHealthChecks,
  fetchPipelineRuns,
  fetchPipelineSummary,
  fetchDataQuality,
  fetchLLMCalls,
  fetchLLMSummary,
  fetchQueryAttribution,
} from '@/lib/api';
import SectionHeader from '@/components/SectionHeader';
import MetricCard from '@/components/MetricCard';
import { ChartSkeleton } from '@/components/LoadingSkeleton';

const COLORS = {
  healthy: '#1A9E60',
  degraded: '#E5A030',
  down: '#C9392C',
  primary: '#0382B7',
  accent: '#03B792',
  muted: '#6B6760',
  grid: '#E8E4DB40',
  success: '#9DCBB8',
  failed: '#E58B6D',
};

const tooltipStyle = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E8E4DB',
  borderRadius: 8,
};

function statusColor(status: string): string {
  const s = (status || '').toUpperCase();
  if (s === 'HEALTHY' || s === 'SUCCESS') return COLORS.healthy;
  if (s === 'DEGRADED') return COLORS.degraded;
  return COLORS.down;
}

function StatusChip({ status }: { status: string }) {
  return (
    <Chip
      label={status}
      size="small"
      sx={{
        backgroundColor: statusColor(status) + '18',
        color: statusColor(status),
        fontWeight: 600,
        fontSize: '0.7rem',
        height: 22,
      }}
    />
  );
}

// ── Health Overview Tab ──────────────────────────────────────
function HealthTab() {
  const [checks, setChecks] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealthChecks()
      .then(setChecks)
      .catch(() => setChecks([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <ChartSkeleton />;

  const healthyCount = checks.filter((c) => (c.STATUS as string) === 'HEALTHY').length;
  const total = checks.length;

  return (
    <Box>
      <SectionHeader title="System Health" subtitle="Latest status of each monitored component" />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard
            title="Components Checked"
            value={String(total)}
            color={COLORS.primary}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard
            title="Healthy"
            value={String(healthyCount)}
            color={COLORS.healthy}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard
            title="Degraded / Down"
            value={String(total - healthyCount)}
            color={total - healthyCount > 0 ? COLORS.down : COLORS.healthy}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard
            title="Uptime"
            value={total > 0 ? `${Math.round((healthyCount / total) * 100)}%` : 'N/A'}
            color={COLORS.accent}
          />
        </Grid>
      </Grid>

      <Card>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.75rem' }}>Component</TableCell>
                <TableCell sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.75rem' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.75rem' }}>Details</TableCell>
                <TableCell sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.75rem' }}>Checked At</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {checks.map((c, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ fontSize: '0.8rem', fontWeight: 600 }}>{c.COMPONENT as string}</TableCell>
                  <TableCell><StatusChip status={c.STATUS as string} /></TableCell>
                  <TableCell sx={{ fontSize: '0.78rem', color: COLORS.muted }}>{c.DETAILS as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', color: COLORS.muted }}>
                    {c.CHECKED_AT ? new Date(c.CHECKED_AT as string).toLocaleString() : ''}
                  </TableCell>
                </TableRow>
              ))}
              {checks.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} sx={{ textAlign: 'center', py: 4, color: COLORS.muted }}>
                    No health check data yet. The scheduled task runs every 60 minutes.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}

// ── Pipeline Runs Tab ────────────────────────────────────────
function PipelineTab() {
  const [runs, setRuns] = useState<Record<string, unknown>[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchPipelineRuns(100), fetchPipelineSummary()])
      .then(([r, s]) => { setRuns(r); setSummary(s); })
      .catch(() => { setRuns([]); setSummary([]); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <ChartSkeleton />;

  const successCount = runs.filter((r) => (r.STATUS as string) === 'SUCCESS').length;
  const failCount = runs.filter((r) => (r.STATUS as string) === 'FAILED').length;
  const avgDuration = runs.length > 0
    ? (runs.reduce((a, r) => a + (Number(r.DURATION_SECONDS) || 0), 0) / runs.length).toFixed(1)
    : '0';

  return (
    <Box>
      <SectionHeader title="Pipeline Runs" subtitle="Stage-level execution tracking across all pipelines" />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Total Stages" value={String(runs.length)} color={COLORS.primary} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Succeeded" value={String(successCount)} color={COLORS.healthy} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Failed" value={String(failCount)} color={failCount > 0 ? COLORS.down : COLORS.healthy} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Avg Duration" value={`${avgDuration}s`} color={COLORS.accent} />
        </Grid>
      </Grid>

      {/* Summary chart */}
      {summary.length > 0 && (
        <Card sx={{ p: 2, mb: 3 }}>
          <Typography variant="body2" sx={{ color: COLORS.muted, mb: 2, fontSize: '0.8rem' }}>
            Stages by Pipeline Type (Last 7 Days)
          </Typography>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={summary}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis dataKey="PIPELINE_TYPE" tick={{ fill: COLORS.muted, fontSize: 11 }} />
              <YAxis tick={{ fill: COLORS.muted, fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#2C2A25' }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="STAGE_COUNT" name="Stages" radius={[4, 4, 0, 0]}>
                {summary.map((entry, idx) => (
                  <Cell key={idx} fill={(entry.STATUS as string) === 'SUCCESS' ? COLORS.success : COLORS.failed} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Recent runs table */}
      <Card>
        <TableContainer sx={{ maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {['Run ID', 'Pipeline', 'Ticker', 'Stage', 'Status', 'Duration', 'Started'].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.72rem', backgroundColor: '#F5F3EE' }}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {runs.slice(0, 50).map((r, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ fontSize: '0.72rem', fontFamily: 'monospace' }}>{(r.RUN_ID as string || '').slice(0, 8)}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{r.PIPELINE_TYPE as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem', fontWeight: 600, color: COLORS.primary }}>{r.TICKER as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{r.STAGE as string}</TableCell>
                  <TableCell><StatusChip status={r.STATUS as string} /></TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{r.DURATION_SECONDS != null ? `${Number(r.DURATION_SECONDS).toFixed(1)}s` : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: COLORS.muted }}>
                    {r.STARTED_AT ? new Date(r.STARTED_AT as string).toLocaleString() : ''}
                  </TableCell>
                </TableRow>
              ))}
              {runs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: COLORS.muted }}>
                    No pipeline runs recorded yet. Run a data load or CAVM pipeline to generate data.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}

// ── Data Quality Tab ─────────────────────────────────────────
function QualityTab() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDataQuality(14)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <ChartSkeleton />;
  if (data.length === 0)
    return (
      <Box>
        <SectionHeader title="Data Quality" subtitle="Quality score trends across RAW tables" />
        <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: COLORS.muted }}>
          No quality snapshots yet. The Airflow DAG captures snapshots after each data load.
        </Typography>
      </Box>
    );

  const tables = [...new Set(data.map((d) => d.TABLE_NAME as string))];
  const chartData = data.reduce<Record<string, Record<string, unknown>>>((acc, d) => {
    const date = d.SNAPSHOT_DATE as string;
    if (!acc[date]) acc[date] = { date };
    acc[date][d.TABLE_NAME as string] = Number(d.AVG_SCORE);
    return acc;
  }, {});
  const lineData = Object.values(chartData).sort((a, b) => (a.date as string).localeCompare(b.date as string));

  const tableColors = ['#0382B7', '#03B792', '#1A9E60', '#E5A030', '#E58B6D'];

  return (
    <Box>
      <SectionHeader title="Data Quality" subtitle="Quality score trends across RAW tables (last 14 days)" />

      <Card sx={{ p: 2, mb: 3 }}>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={lineData}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
            <XAxis dataKey="date" tick={{ fill: COLORS.muted, fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: COLORS.muted, fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#2C2A25' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {tables.map((t, i) => (
              <Line
                key={t}
                type="monotone"
                dataKey={t}
                stroke={tableColors[i % tableColors.length]}
                strokeWidth={2}
                dot={{ r: 2 }}
                name={t.replace('RAW_', '')}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Latest snapshot table */}
      <Card>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Table', 'Avg Score', 'Min', 'Max', 'Rows', 'Freshness (hrs)', 'Date'].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.72rem', backgroundColor: '#F5F3EE' }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.slice(0, 20).map((d, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ fontSize: '0.78rem', fontWeight: 600 }}>{(d.TABLE_NAME as string || '').replace('RAW_', '')}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem', fontWeight: 700, color: Number(d.AVG_SCORE) >= 70 ? COLORS.healthy : COLORS.degraded }}>
                    {Number(d.AVG_SCORE).toFixed(1)}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{d.MIN_QUALITY_SCORE != null ? Number(d.MIN_QUALITY_SCORE).toFixed(1) : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{d.MAX_QUALITY_SCORE != null ? Number(d.MAX_QUALITY_SCORE).toFixed(1) : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{d.TOTAL_ROWS != null ? Number(d.TOTAL_ROWS).toLocaleString() : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{d.AVG_FRESHNESS_HOURS != null ? Number(d.AVG_FRESHNESS_HOURS).toFixed(1) : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: COLORS.muted }}>{d.SNAPSHOT_DATE as string}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}

// ── LLM Calls Tab ────────────────────────────────────────────
function LLMTab() {
  const [calls, setCalls] = useState<Record<string, unknown>[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchLLMCalls(100), fetchLLMSummary()])
      .then(([c, s]) => { setCalls(c); setSummary(s); })
      .catch(() => { setCalls([]); setSummary([]); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <ChartSkeleton />;

  const totalCalls = calls.length;
  const avgLatency = totalCalls > 0
    ? Math.round(calls.reduce((a, c) => a + (Number(c.LATENCY_MS) || 0), 0) / totalCalls)
    : 0;
  const failures = calls.filter((c) => (c.STATUS as string) === 'FAILED').length;

  return (
    <Box>
      <SectionHeader title="LLM / VLM Calls" subtitle="Model invocation tracking with latency and token usage" />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Total Calls" value={String(totalCalls)} color={COLORS.primary} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Avg Latency" value={`${avgLatency}ms`} color={COLORS.accent} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Failures" value={String(failures)} color={failures > 0 ? COLORS.down : COLORS.healthy} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <MetricCard title="Models Used" value={String(summary.length)} color={COLORS.primary} />
        </Grid>
      </Grid>

      {/* Summary bar chart */}
      {summary.length > 0 && (
        <Card sx={{ p: 2, mb: 3 }}>
          <Typography variant="body2" sx={{ color: COLORS.muted, mb: 2, fontSize: '0.8rem' }}>
            Calls by Model (Last 7 Days)
          </Typography>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={summary} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis type="number" tick={{ fill: COLORS.muted, fontSize: 11 }} />
              <YAxis dataKey="MODEL_NAME" type="category" tick={{ fill: COLORS.muted, fontSize: 10 }} width={140} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#2C2A25' }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="CALL_COUNT" name="Calls" fill={COLORS.primary} radius={[0, 4, 4, 0]} />
              <Bar dataKey="FAILURES" name="Failures" fill={COLORS.failed} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Recent calls table */}
      <Card>
        <TableContainer sx={{ maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {['Model', 'Provider', 'Type', 'Ticker', 'Latency', 'Tokens', 'Status', 'Time'].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.72rem', backgroundColor: '#F5F3EE' }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {calls.slice(0, 50).map((c, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ fontSize: '0.75rem', fontWeight: 600 }}>{c.MODEL_NAME as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>{c.PROVIDER as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>{c.CALL_TYPE as string}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', color: COLORS.primary }}>{c.TICKER as string || '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>{c.LATENCY_MS != null ? `${c.LATENCY_MS}ms` : '-'}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>
                    {(Number(c.PROMPT_TOKENS) || 0) + (Number(c.COMPLETION_TOKENS) || 0) || '-'}
                  </TableCell>
                  <TableCell><StatusChip status={c.STATUS as string} /></TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: COLORS.muted }}>
                    {c.CALLED_AT ? new Date(c.CALLED_AT as string).toLocaleString() : ''}
                  </TableCell>
                </TableRow>
              ))}
              {calls.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} sx={{ textAlign: 'center', py: 4, color: COLORS.muted }}>
                    No LLM calls recorded yet. Run a CAVM pipeline to generate data.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}

// ── Query Attribution Tab ────────────────────────────────────
function QueryTab() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQueryAttribution()
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <ChartSkeleton />;

  const barColors = ['#0382B7', '#03B792', '#1A9E60', '#E5A030', '#E58B6D', '#6B6760'];

  return (
    <Box>
      <SectionHeader title="Query Attribution" subtitle="Snowflake query breakdown by FinSage component (last 24h)" />

      {data.length > 0 ? (
        <>
          <Card sx={{ p: 2, mb: 3 }}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                <XAxis dataKey="COMPONENT" tick={{ fill: COLORS.muted, fontSize: 11 }} />
                <YAxis tick={{ fill: COLORS.muted, fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#2C2A25' }} />
                <Bar dataKey="QUERY_COUNT" name="Queries" radius={[4, 4, 0, 0]}>
                  {data.map((_, idx) => (
                    <Cell key={idx} fill={barColors[idx % barColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {['Component', 'Query Count', 'Total Elapsed (sec)'].map((h) => (
                      <TableCell key={h} sx={{ fontWeight: 600, color: COLORS.muted, fontSize: '0.72rem', backgroundColor: '#F5F3EE' }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.map((d, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ fontSize: '0.8rem', fontWeight: 600 }}>{d.COMPONENT as string}</TableCell>
                      <TableCell sx={{ fontSize: '0.8rem' }}>{Number(d.QUERY_COUNT).toLocaleString()}</TableCell>
                      <TableCell sx={{ fontSize: '0.8rem' }}>{d.TOTAL_ELAPSED_SEC as string}s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </>
      ) : (
        <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: COLORS.muted }}>
          No query attribution data. Queries tagged with QUERY_TAG will appear here after execution.
        </Typography>
      )}
    </Box>
  );
}

// ── Main Observability Page ──────────────────────────────────
export default function ObservabilityPage() {
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
            '& .Mui-selected': { color: '#03B792' },
            '& .MuiTabs-indicator': { backgroundColor: '#03B792' },
          }}
        >
          <Tab label="Health" />
          <Tab label="Pipeline Runs" />
          <Tab label="Data Quality" />
          <Tab label="LLM Calls" />
          <Tab label="Query Attribution" />
        </Tabs>
      </Card>
      {tab === 0 && <HealthTab />}
      {tab === 1 && <PipelineTab />}
      {tab === 2 && <QualityTab />}
      {tab === 3 && <LLMTab />}
      {tab === 4 && <QueryTab />}
    </Box>
  );
}
