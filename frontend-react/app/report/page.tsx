'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Stepper,
  Step,
  StepLabel,
  Chip,
  CircularProgress,
  Alert,
  Checkbox,
  FormControlLabel,
  Divider,
  Grid,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import ReactMarkdown from 'react-markdown';
import { useTicker } from '@/lib/ticker-context';
import { generateQuickReport, startCAVMPipeline, getCAVMStatus } from '@/lib/api';
import SectionHeader from '@/components/SectionHeader';
import MetricCard from '@/components/MetricCard';
import ReportChat from '@/components/ReportChat';

const REPORT_SECTIONS = [
  'Executive Summary',
  'Financial Performance',
  'Stock Analysis',
  'Sentiment',
  'Risk Factors',
  'Mgmt Credibility',
  'Forward Outlook',
];

const CAVM_STAGES = ['Chart Agent', 'Validation', 'Analysis', 'Report'];

export default function ReportPage() {
  const { ticker } = useTicker();
  const [reportType, setReportType] = useState<'quick' | 'cavm-summary' | 'cavm'>('quick');
  const [loading, setLoading] = useState(false);
  const [quickResult, setQuickResult] = useState<string | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);
  const [cavm, setCavm] = useState<{
    taskId: string | null;
    stage: number;
    status: string;
    result: Record<string, unknown> | null;
    error: string | null;
  }>({ taskId: null, stage: 0, status: 'idle', result: null, error: null });
  const [debugMode, setDebugMode] = useState(false);
  const [skipCharts, setSkipCharts] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleQuickReport = () => {
    setLoading(true);
    setQuickResult(null);
    setQuickError(null);
    generateQuickReport(ticker)
      .then((data) => {
        if (data.error) setQuickError(data.error);
        else setQuickResult(data.result);
      })
      .catch((e) => setQuickError(e.message))
      .finally(() => setLoading(false));
  };

  const handleCAVMPipeline = () => {
    const detailLevel = reportType === 'cavm-summary' ? 'summary' : 'detailed';
    setCavm({ taskId: null, stage: 0, status: 'starting', result: null, error: null });
    startCAVMPipeline(ticker, debugMode, skipCharts, detailLevel)
      .then((data) => {
        if (data.task_id) {
          setCavm((prev) => ({ ...prev, taskId: data.task_id, status: 'running' }));
          // Start polling
          pollingRef.current = setInterval(() => {
            getCAVMStatus(data.task_id)
              .then((status) => {
                setCavm((prev) => ({
                  ...prev,
                  stage: status.stage || prev.stage,
                  status: status.status,
                }));
                if (status.status === 'completed') {
                  setCavm((prev) => ({ ...prev, result: status.result }));
                  if (pollingRef.current) clearInterval(pollingRef.current);
                } else if (status.status === 'failed') {
                  setCavm((prev) => ({ ...prev, error: status.error }));
                  if (pollingRef.current) clearInterval(pollingRef.current);
                }
              })
              .catch(() => {});
          }, 5000);
        }
      })
      .catch((e) => {
        setCavm((prev) => ({ ...prev, status: 'failed', error: e.message }));
      });
  };

  const downloadMarkdown = () => {
    if (!quickResult) return;
    const blob = new Blob([quickResult], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${ticker}_research_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      {/* Report Section Pills */}
      <Card sx={{ mb: 3, borderLeft: '3px solid #03B792' }}>
        <CardContent>
          <Typography
            variant="h6"
            sx={{ fontFamily: '"DM Serif Display", Georgia, serif', fontWeight: 400, mb: 1.5 }}
          >
            Report Sections
          </Typography>
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            {REPORT_SECTIONS.map((s, i) => (
              <Chip
                key={s}
                label={`${i + 1}. ${s}`}
                size="small"
                sx={{
                  backgroundColor: 'rgba(3,183,146,0.08)',
                  color: '#03B792',
                  border: '1px solid rgba(3,183,146,0.18)',
                  fontSize: '0.75rem',
                }}
              />
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* Report Type Selector */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            onClick={() => setReportType('quick')}
            sx={{
              cursor: 'pointer',
              borderColor: reportType === 'quick' ? '#03B792' : '#E8E4DB',
              transition: 'border-color 0.25s ease',
              height: '100%',
            }}
          >
            <CardContent>
              <Typography
                variant="h6"
                sx={{
                  fontFamily: '"DM Serif Display", Georgia, serif',
                  fontWeight: 400,
                  color: reportType === 'quick' ? '#03B792' : '#2C2A25',
                }}
              >
                Quick Report
              </Typography>
              <Typography variant="body2" sx={{ color: '#6B6760', mt: 1 }}>
                Generates a Markdown report using Snowflake Cortex LLM and SEC filing analysis. Typically
                completes in 30-60 seconds.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            onClick={() => setReportType('cavm-summary')}
            sx={{
              cursor: 'pointer',
              borderColor: reportType === 'cavm-summary' ? '#03B792' : '#E8E4DB',
              transition: 'border-color 0.25s ease',
              height: '100%',
            }}
          >
            <CardContent>
              <Typography
                variant="h6"
                sx={{
                  fontFamily: '"DM Serif Display", Georgia, serif',
                  fontWeight: 400,
                  color: reportType === 'cavm-summary' ? '#03B792' : '#2C2A25',
                }}
              >
                Summary PDF Report
              </Typography>
              <Typography variant="body2" sx={{ color: '#6B6760', mt: 1 }}>
                CAVM pipeline with charts and condensed analysis. Produces an 8-10 page branded PDF
                with key insights only. Typically takes 3-8 minutes.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            onClick={() => setReportType('cavm')}
            sx={{
              cursor: 'pointer',
              borderColor: reportType === 'cavm' ? '#03B792' : '#E8E4DB',
              transition: 'border-color 0.25s ease',
              height: '100%',
            }}
          >
            <CardContent>
              <Typography
                variant="h6"
                sx={{
                  fontFamily: '"DM Serif Display", Georgia, serif',
                  fontWeight: 400,
                  color: reportType === 'cavm' ? '#03B792' : '#2C2A25',
                }}
              >
                Full CAVM Pipeline
              </Typography>
              <Typography variant="body2" sx={{ color: '#6B6760', mt: 1 }}>
                Generates a branded 15-20 page PDF with VLM-refined charts, chain-of-analysis validation,
                and an investment thesis. Typically takes 5-15 minutes.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Report */}
      {reportType === 'quick' && (
        <Box>
          <Button
            variant="contained"
            onClick={handleQuickReport}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
            sx={{ mb: 2 }}
          >
            {loading ? 'Generating...' : 'Generate Quick Report'}
          </Button>

          {quickError && <Alert severity="error" sx={{ mb: 2 }}>{quickError}</Alert>}

          {quickResult && (
            <Card sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <SectionHeader title="Report" />
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<DownloadIcon />}
                  onClick={downloadMarkdown}
                  sx={{ borderColor: '#E8E4DB', color: '#2C2A25' }}
                >
                  Download .md
                </Button>
              </Box>
              <Divider sx={{ mb: 2 }} />
              <Box className="markdown-content">
                <ReactMarkdown>{quickResult}</ReactMarkdown>
              </Box>
            </Card>
          )}
        </Box>
      )}

      {/* CAVM Pipeline */}
      {(reportType === 'cavm' || reportType === 'cavm-summary') && (
        <Box>
          {/* Pipeline stepper */}
          <Card sx={{ mb: 3, p: 2 }}>
            <Stepper activeStep={cavm.stage} alternativeLabel>
              {CAVM_STAGES.map((label, i) => (
                <Step key={label} completed={i < cavm.stage}>
                  <StepLabel
                    sx={{
                      '& .MuiStepLabel-label': {
                        color:
                          i < cavm.stage
                            ? '#9DCBB8'
                            : i === cavm.stage && cavm.status === 'running'
                            ? '#0382B7'
                            : '#6B6760',
                        fontSize: '0.8rem',
                      },
                    }}
                  >
                    {label}
                  </StepLabel>
                </Step>
              ))}
            </Stepper>
          </Card>

          {/* Options */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={debugMode}
                  onChange={(e) => setDebugMode(e.target.checked)}
                  size="small"
                  sx={{ color: '#6B6760', '&.Mui-checked': { color: '#03B792' } }}
                />
              }
              label={<Typography variant="body2" sx={{ color: '#6B6760' }}>Debug mode</Typography>}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={skipCharts}
                  onChange={(e) => setSkipCharts(e.target.checked)}
                  size="small"
                  sx={{ color: '#6B6760', '&.Mui-checked': { color: '#03B792' } }}
                />
              }
              label={<Typography variant="body2" sx={{ color: '#6B6760' }}>Skip chart generation</Typography>}
            />
          </Box>

          <Button
            variant="contained"
            onClick={handleCAVMPipeline}
            disabled={cavm.status === 'running' || cavm.status === 'starting'}
            startIcon={
              cavm.status === 'running' || cavm.status === 'starting' ? (
                <CircularProgress size={16} />
              ) : (
                <PlayArrowIcon />
              )
            }
            sx={{ mb: 2 }}
          >
            {cavm.status === 'running'
              ? 'Pipeline Running...'
              : reportType === 'cavm-summary'
              ? 'Generate Summary PDF Report'
              : 'Generate Full PDF Report'}
          </Button>

          {cavm.error && <Alert severity="error" sx={{ mb: 2 }}>{cavm.error}</Alert>}

          {cavm.result && (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                PDF report generated successfully!
              </Alert>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 4 }}>
                  <MetricCard title="Charts Generated" value={String((cavm.result as Record<string, unknown>).charts_count || 0)} />
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <MetricCard title="Charts Validated" value={String((cavm.result as Record<string, unknown>).charts_validated || 0)} />
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <MetricCard
                    title="Total Time"
                    value={`${Number((cavm.result as Record<string, unknown>).elapsed_seconds || 0).toFixed(0)}s`}
                  />
                </Grid>
              </Grid>

              {cavm.result && String((cavm.result as Record<string, unknown>).pdf_path) && (
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/report/download/${encodeURIComponent(String((cavm.result as Record<string, unknown>).pdf_path))}`}
                  target="_blank"
                >
                  Download PDF Report
                </Button>
              )}

              {/* Chat about the generated report */}
              <ReportChat ticker={ticker} />
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
