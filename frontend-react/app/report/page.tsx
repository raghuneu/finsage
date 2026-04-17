'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Stepper,
  Step,
  StepLabel,
  StepConnector,
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
import HistoryIcon from '@mui/icons-material/History';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ReactMarkdown from 'react-markdown';
import { useTicker } from '@/lib/ticker-context';
import { useReport } from '@/lib/report-context';
import type { ExistingReport } from '@/lib/report-context';
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
  const {
    reportType,
    setReportType,
    quickLoading,
    quickResult,
    quickError,
    quickTicker,
    startQuickReport,
    cavm,
    skipCharts,
    setSkipCharts,
    startCAVM,
    existingReports,
    existingReportsLoading,
    loadReportHistory,
  } = useReport();

  const downloadMarkdown = () => {
    if (!quickResult) return;
    const blob = new Blob([quickResult], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${quickTicker || ticker}_research_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Show quick report results only if they belong to the current ticker
  const showQuickResult = quickResult && quickTicker === ticker;
  const showQuickError = quickError && quickTicker === ticker;
  const isQuickLoading = quickLoading && quickTicker === ticker;

  // Show CAVM state only if it belongs to the current ticker
  const cavmForTicker = cavm.ticker === ticker;
  const cavmRunning = cavm.status === 'running' || cavm.status === 'starting';

  // Load report history when ticker changes
  useEffect(() => {
    if (ticker) loadReportHistory(ticker);
  }, [ticker, loadReportHistory]);

  // Reload report history when a CAVM pipeline completes
  useEffect(() => {
    if (cavm.status === 'completed' && cavm.ticker) {
      loadReportHistory(cavm.ticker);
    }
  }, [cavm.status, cavm.ticker, loadReportHistory]);

  // Filter existing reports by detail level for the relevant card
  const summaryReports = existingReports.filter((r: ExistingReport) => r.detail_level === 'summary');
  const fullReports = existingReports.filter((r: ExistingReport) => r.detail_level === 'full');

  // Track which report folder the chat is grounded to
  const [activeFolderName, setActiveFolderName] = useState<string | null>(null);

  // Auto-set active folder when a CAVM run completes (use its output folder)
  useEffect(() => {
    if (cavmForTicker && cavm.result) {
      const resultFolder = String((cavm.result as Record<string, unknown>).output_folder || '');
      if (resultFolder) setActiveFolderName(resultFolder);
    }
  }, [cavmForTicker, cavm.result]);

  // Reset active folder when ticker changes
  useEffect(() => {
    setActiveFolderName(null);
  }, [ticker]);

  // Determine the folder to use for chat: explicit selection > latest existing report
  const chatFolderName = activeFolderName
    || (reportType === 'cavm-summary' ? summaryReports[0]?.folder_name : fullReports[0]?.folder_name)
    || existingReports[0]?.folder_name
    || undefined;

  // Show chat when there's a report to talk about (either just-generated or historical)
  const showReportChat = reportType !== 'quick' && (
    (cavmForTicker && cavm.result) || existingReports.length > 0
  );

  const formatReportDate = (isoDate: string | null) => {
    if (!isoDate) return 'Unknown date';
    try {
      const d = new Date(isoDate);
      return d.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return isoDate; }
  };

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  return (
    <Box>
      {/* Banner when a pipeline is running for a different ticker */}
      {cavmRunning && !cavmForTicker && (
        <Alert severity="info" sx={{ mb: 2 }}>
          A CAVM pipeline is currently running for <strong>{cavm.ticker}</strong>. Wait for it to finish before starting a new one.
        </Alert>
      )}
      {quickLoading && !isQuickLoading && (
        <Alert severity="info" sx={{ mb: 2 }}>
          A Quick Report is currently generating for <strong>{quickTicker}</strong>.
        </Alert>
      )}

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
                      backgroundColor: '#F4F2ED',
                      color: '#6B6760',
                      border: '1px solid #E8E4DB',
                      fontSize: '0.75rem',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        backgroundColor: 'rgba(2,149,116,0.08)',
                        color: '#029574',
                        borderColor: 'rgba(2,149,116,0.22)',
                      },
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
              backgroundColor: reportType === 'quick' ? 'rgba(3,183,146,0.04)' : 'transparent',
              transition: 'border-color 0.25s ease, background-color 0.25s ease',
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
              <Typography variant="body2" sx={{ color: '#3D3A36', mt: 1 }}>
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
              backgroundColor: reportType === 'cavm-summary' ? 'rgba(3,183,146,0.04)' : 'transparent',
              transition: 'border-color 0.25s ease, background-color 0.25s ease',
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
              <Typography variant="body2" sx={{ color: '#3D3A36', mt: 1 }}>
                CAVM pipeline with charts and condensed analysis. Produces an 8-10 page branded PDF
                with key insights only. Typically takes 3-8 minutes.
              </Typography>
              {summaryReports.length > 0 && (
                <Box sx={{ mt: 1.5, p: 1.5, backgroundColor: 'rgba(3,183,146,0.06)', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    <HistoryIcon sx={{ fontSize: 14, color: '#03B792' }} />
                    <Typography variant="caption" sx={{ color: '#03B792', fontWeight: 600, fontSize: '0.7rem', letterSpacing: '0.03em' }}>
                      {summaryReports.length} previous report{summaryReports.length > 1 ? 's' : ''} found
                    </Typography>
                  </Box>
                  <Typography variant="caption" sx={{ color: '#6B6760', display: 'block', mb: 0.75 }}>
                    Latest: {formatReportDate(summaryReports[0].run_at)}
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
                    href={`${apiBase}/api/report/download/${encodeURIComponent(summaryReports[0].pdf_path)}`}
                    target="_blank"
                    onClick={(e: React.MouseEvent) => { e.stopPropagation(); setActiveFolderName(summaryReports[0].folder_name); }}
                    sx={{
                      fontSize: '0.7rem', py: 0.25, px: 1,
                      borderColor: 'rgba(3,130,183,0.3)', color: '#0382B7',
                      '&:hover': { borderColor: '#0382B7', backgroundColor: 'rgba(3,130,183,0.08)' },
                    }}
                  >
                    View Previous Report
                  </Button>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            onClick={() => setReportType('cavm')}
            sx={{
              cursor: 'pointer',
              borderColor: reportType === 'cavm' ? '#03B792' : '#E8E4DB',
              backgroundColor: reportType === 'cavm' ? 'rgba(3,183,146,0.04)' : 'transparent',
              transition: 'border-color 0.25s ease, background-color 0.25s ease',
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
              <Typography variant="body2" sx={{ color: '#3D3A36', mt: 1 }}>
                Generates a branded 15-20 page PDF with VLM-refined charts, chain-of-analysis validation,
                and an investment thesis. Typically takes 5-15 minutes.
              </Typography>
              {fullReports.length > 0 && (
                <Box sx={{ mt: 1.5, p: 1.5, backgroundColor: 'rgba(3,183,146,0.06)', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    <HistoryIcon sx={{ fontSize: 14, color: '#03B792' }} />
                    <Typography variant="caption" sx={{ color: '#03B792', fontWeight: 600, fontSize: '0.7rem', letterSpacing: '0.03em' }}>
                      {fullReports.length} previous report{fullReports.length > 1 ? 's' : ''} found
                    </Typography>
                  </Box>
                  <Typography variant="caption" sx={{ color: '#6B6760', display: 'block', mb: 0.75 }}>
                    Latest: {formatReportDate(fullReports[0].run_at)}
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
                    href={`${apiBase}/api/report/download/${encodeURIComponent(fullReports[0].pdf_path)}`}
                    target="_blank"
                    onClick={(e: React.MouseEvent) => { e.stopPropagation(); setActiveFolderName(fullReports[0].folder_name); }}
                    sx={{
                      fontSize: '0.7rem', py: 0.25, px: 1,
                      borderColor: 'rgba(3,130,183,0.3)', color: '#0382B7',
                      '&:hover': { borderColor: '#0382B7', backgroundColor: 'rgba(3,130,183,0.08)' },
                    }}
                  >
                    View Previous Report
                  </Button>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Report */}
      {reportType === 'quick' && (
        <Box>
          <Button
            variant="contained"
            onClick={() => startQuickReport(ticker)}
            disabled={quickLoading}
            startIcon={isQuickLoading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
            sx={{ mb: 2 }}
          >
            {isQuickLoading ? 'Generating...' : quickLoading ? `Generating for ${quickTicker}...` : 'Generate Quick Report'}
          </Button>

          {showQuickError && <Alert severity="error" sx={{ mb: 2 }}>{quickError}</Alert>}

          {showQuickResult && (
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
            <Stepper
              activeStep={cavmForTicker ? cavm.stage : 0}
              alternativeLabel
              connector={
                <StepConnector
                  sx={{
                    '& .MuiStepConnector-line': {
                      borderColor: '#C4BFB5',
                      borderTopStyle: 'dashed',
                      borderTopWidth: 3,
                    },
                    '&.Mui-active .MuiStepConnector-line': {
                      borderColor: '#03B792',
                      borderTopStyle: 'solid',
                    },
                    '&.Mui-completed .MuiStepConnector-line': {
                      borderColor: '#0382B7',
                      borderTopStyle: 'solid',
                    },
                  }}
                />
              }
            >
              {CAVM_STAGES.map((label, i) => (
                <Step key={label} completed={cavmForTicker && i < cavm.stage}>
                  <StepLabel
                    sx={{
                      '& .MuiStepLabel-label': {
                        color:
                          cavmForTicker && i < cavm.stage
                            ? '#0382B7'
                            : cavmForTicker && i === cavm.stage && cavm.status === 'running'
                            ? '#03B792'
                            : '#7A756F',
                        fontSize: '0.8rem',
                        fontWeight: cavmForTicker && i <= cavm.stage ? 600 : 500,
                      },
                      '& .MuiStepIcon-root': {
                        color: '#C4BFB5',
                        '&.Mui-active': { color: '#03B792' },
                        '&.Mui-completed': { color: '#0382B7' },
                      },
                    }}
                  >
                    {label}
                  </StepLabel>
                </Step>
              ))}
            </Stepper>
          </Card>

          {/* Activity Feed — live messages during pipeline execution */}
          {cavmForTicker && cavmRunning && cavm.messages.length > 0 && (
            <Box
              sx={{
                mb: 3,
                px: 2.5,
                py: 2,
                backgroundColor: 'rgba(244,242,237,0.5)',
                borderLeft: '2px solid #E8E4DB',
                borderRadius: '0 6px 6px 0',
                maxHeight: 220,
                overflowY: 'auto',
                '&::-webkit-scrollbar': { width: 4 },
                '&::-webkit-scrollbar-thumb': {
                  backgroundColor: '#C4BFB5',
                  borderRadius: 2,
                },
                '@keyframes slideUpFade': {
                  '0%': { opacity: 0, transform: 'translateY(8px)' },
                  '100%': { opacity: 1, transform: 'translateY(0)' },
                },
                '@keyframes pulseGlow': {
                  '0%, 100%': { opacity: 0.4 },
                  '50%': { opacity: 1 },
                },
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: '#7A756F',
                  fontWeight: 600,
                  fontSize: '0.65rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  mb: 1,
                  display: 'block',
                }}
              >
                Activity
              </Typography>
              {cavm.messages.map((msg, idx) => {
                const isLatest = idx === cavm.messages.length - 1;
                return (
                  <Box
                    key={`${idx}-${msg}`}
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 1,
                      py: 0.5,
                      animation: 'slideUpFade 0.35s ease-out both',
                    }}
                  >
                    <Box
                      sx={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        backgroundColor: isLatest ? '#03B792' : '#C4BFB5',
                        mt: '5px',
                        flexShrink: 0,
                        ...(isLatest && {
                          animation: 'pulseGlow 1.5s ease-in-out infinite',
                        }),
                      }}
                    />
                    <Typography
                      variant="body2"
                      sx={{
                        color: isLatest ? '#2C2A25' : '#6B6760',
                        fontFamily: '"DM Sans", sans-serif',
                        fontStyle: 'italic',
                        fontSize: '0.8rem',
                        lineHeight: 1.5,
                        transition: 'color 0.3s ease',
                      }}
                    >
                      {msg}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          )}

          {/* Options */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
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
            onClick={() => startCAVM(ticker, reportType)}
            disabled={cavmRunning}
            startIcon={
              cavmRunning && cavmForTicker ? (
                <CircularProgress size={16} />
              ) : (
                <PlayArrowIcon />
              )
            }
            sx={{
              mb: 2,
              ...(cavmRunning && {
                '@keyframes pulseBtn': {
                  '0%, 100%': { opacity: 0.75 },
                  '50%': { opacity: 1 },
                },
                animation: 'pulseBtn 2s ease-in-out infinite',
                pointerEvents: 'none',
              }),
            }}
          >
            {cavmRunning && cavmForTicker
              ? 'Pipeline Running...'
              : cavmRunning
              ? `Pipeline Running for ${cavm.ticker}...`
              : reportType === 'cavm-summary'
              ? 'Generate Summary PDF Report'
              : 'Generate Full PDF Report'}
          </Button>

          {cavmForTicker && cavm.error && <Alert severity="error" sx={{ mb: 2 }}>{cavm.error}</Alert>}

          {cavmForTicker && cavm.result && (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                PDF report generated successfully!
              </Alert>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 4 }}>
                  <MetricCard title="Charts Generated" value={String((cavm.result as Record<string, unknown>).charts_count || 0)} color="#0382B7" />
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <MetricCard title="Charts Validated" value={String((cavm.result as Record<string, unknown>).charts_validated || 0)} color="#0382B7" />
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <MetricCard
                    title="Total Time"
                    value={(() => {
                      const totalSec = Number((cavm.result as Record<string, unknown>).elapsed_seconds || 0);
                      const m = Math.floor(totalSec / 60);
                      const s = Math.round(totalSec % 60);
                      return m > 0 ? `${m}m ${s}s` : `${s}s`;
                    })()}
                    color="#0382B7"
                  />
                </Grid>
              </Grid>

              {String((cavm.result as Record<string, unknown>).pdf_path) && (
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  href={`${apiBase}/api/report/download/${encodeURIComponent(String((cavm.result as Record<string, unknown>).pdf_path))}`}
                  target="_blank"
                >
                  Download PDF Report
                </Button>
              )}
            </Box>
          )}

          {/* Chat about the report — visible for both just-generated and historical reports */}
          {showReportChat && (
            <ReportChat ticker={ticker} folderName={chatFolderName} />
          )}
        </Box>
      )}
    </Box>
  );
}
