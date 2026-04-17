'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  Button,
  Alert,
  CircularProgress,
  Chip,
} from '@mui/material';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ReactMarkdown from 'react-markdown';
import { useTicker } from '@/lib/ticker-context';
import { fetchFilings, analyzeFilings } from '@/lib/api';
import SectionHeader from '@/components/SectionHeader';
import { TableSkeleton } from '@/components/LoadingSkeleton';

const ANALYSIS_MODES = [
  { value: 'summary', label: 'Executive Summary', desc: 'Generate a concise summary of the latest filing.' },
  { value: 'risks', label: 'Risk Analysis', desc: 'Analyze risk factors disclosed in the filing.' },
  { value: 'mda', label: 'MD&A Analysis', desc: 'Analyze the Management Discussion & Analysis section.' },
  { value: 'compare', label: 'Filing Comparison', desc: 'Compare the two most recent filings for changes.' },
];

export default function SECFilingPage() {
  const { ticker } = useTicker();
  const [filingsData, setFilingsData] = useState<{ source: string; filings: Record<string, unknown>[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState('summary');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setAnalysisResult(null);
    setAnalysisError(null);
    fetchFilings(ticker)
      .then(setFilingsData)
      .catch(() => setFilingsData(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  const runAnalysis = () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisError(null);
    analyzeFilings(ticker, mode)
      .then((data) => {
        if (data.error) {
          setAnalysisError(data.error);
        } else {
          setAnalysisResult(data.result);
        }
      })
      .catch((e) => setAnalysisError(e.message))
      .finally(() => setAnalyzing(false));
  };

  if (loading) return <TableSkeleton rows={8} />;

  const filings = filingsData?.filings || [];
  const source = filingsData?.source || 'none';

  if (filings.length === 0) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" sx={{ color: '#6B6760' }}>
            No SEC filing data found for {ticker}. Run the data pipeline to load SEC filings.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const modeInfo = ANALYSIS_MODES.find((m) => m.value === mode);
  const isDocSource = source === 'documents';

  // Prepare scatter data for timeline
  const scatterData = filings
    .filter((f) => f.FILING_DATE && f.MDA_WORD_COUNT)
    .map((f) => ({
      x: new Date(f.FILING_DATE as string).getTime(),
      y: f.MDA_WORD_COUNT,
      formType: f.FORM_TYPE,
      date: (f.FILING_DATE as string).slice(0, 10),
    }));

  return (
    <Box>
      {/* Filing inventory card */}
      <Card
        sx={{
          mb: 3,
          borderLeft: '3px solid #03B792',
        }}
      >
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
          <Typography variant="h6" sx={{ fontFamily: '"DM Serif Display", Georgia, serif', fontWeight: 400 }}>
            {isDocSource ? 'Filing Documents' : 'XBRL Filings'}
          </Typography>
          <Typography
            variant="h5"
            sx={{
              fontFamily: '"DM Serif Display", Georgia, serif',
              fontWeight: 400,
              color: '#2C2A25',
              mt: 0.5,
            }}
          >
            {filings.length} {isDocSource ? 'document(s)' : 'record(s)'}
          </Typography>
          <Typography variant="caption" sx={{ color: '#9A9590' }}>
            from {isDocSource ? 'RAW_SEC_FILING_DOCUMENTS' : 'RAW_SEC_FILINGS'}
          </Typography>
        </CardContent>
      </Card>

      {/* Filing Timeline */}
      {isDocSource && scatterData.length > 0 && (
        <Card sx={{ mb: 3, p: 2 }}>
          <Typography variant="body2" sx={{ color: '#6B6760', mb: 2, fontSize: '0.8rem' }}>
            Filing Timeline (sized by MD&A word count)
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8E4DB40" />
              <XAxis
                dataKey="x"
                type="number"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                tick={{ fill: '#6B6760', fontSize: 11 }}
              />
              <YAxis dataKey="y" tick={{ fill: '#6B6760', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E8E4DB', borderRadius: 8 }}
                labelFormatter={(v) => new Date(v as number).toLocaleDateString()}
                formatter={(value) => [Number(value).toLocaleString(), 'MD&A Words']}
              />
              <Legend wrapperStyle={{ color: '#2C2A25', fontSize: 11 }} />
              <Scatter
                name="10-K"
                data={scatterData.filter((d) => d.formType === '10-K')}
                fill="#0382B7"
              />
              <Scatter
                name="10-Q"
                data={scatterData.filter((d) => d.formType === '10-Q')}
                fill="#F8CB86"
              />
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Data table */}
      <Card sx={{ mb: 3 }}>
        <TableContainer sx={{ maxHeight: 350 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {Object.keys(filings[0]).map((col) => (
                  <TableCell
                    key={col}
                    sx={{
                      backgroundColor: '#F5F3EE',
                      color: '#6B6760',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                    }}
                  >
                    {col}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {filings.map((row, i) => (
                <TableRow key={i}>
                  {Object.entries(row).map(([col, val], j) => (
                    <TableCell key={j} sx={{ fontSize: '0.75rem', borderColor: '#E8E4DB' }}>
                      {col === 'COMPANY_NAME' && typeof val === 'string'
                        ? val.replace(/\b\w+/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase())
                        : String(val ?? '')}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Analysis Controls */}
      <SectionHeader title="Run Analysis" subtitle="Use Snowflake Cortex to analyze filing content" />

      {!isDocSource && (
        <Alert
          severity="info"
          sx={{
            mb: 2,
            backgroundColor: 'rgba(3,130,183,0.04)',
            border: '1px solid rgba(3,130,183,0.10)',
            color: '#2C2A25',
          }}
        >
          <strong>Analytics-Only Mode:</strong> No extracted filing text found. Analysis will use
          quantitative data from the analytics pipeline. Run the SEC extraction pipeline to enable
          full text-based analysis.
        </Alert>
      )}

      <Card sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            size="small"
            sx={{ minWidth: 200 }}
          >
            {ANALYSIS_MODES.map((m) => (
              <MenuItem key={m.value} value={m.value}>
                {m.label}
              </MenuItem>
            ))}
          </Select>
          <Typography variant="body2" sx={{ color: '#6B6760', fontSize: '0.8rem', flex: 1 }}>
            {modeInfo?.desc}
          </Typography>
          <Button
            variant="contained"
            onClick={runAnalysis}
            disabled={analyzing}
            startIcon={analyzing ? <CircularProgress size={16} /> : <PlayArrowIcon />}
          >
            {analyzing ? 'Analyzing...' : 'Run Analysis'}
          </Button>
        </Box>
      </Card>

      {analysisError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {analysisError}
        </Alert>
      )}

      {analysisResult && (
        <Card sx={{ p: 3 }}>
          <SectionHeader title={`${modeInfo?.label} Results`} />
          <Box className="markdown-content" sx={{ mt: 2 }}>
            <ReactMarkdown>{analysisResult}</ReactMarkdown>
          </Box>
        </Card>
      )}
    </Box>
  );
}
