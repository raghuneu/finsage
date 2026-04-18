'use client';

import React from 'react';
import { Box, Card, Typography, Grid } from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import BarChartIcon from '@mui/icons-material/BarChart';
import DescriptionIcon from '@mui/icons-material/Description';
import VerifiedIcon from '@mui/icons-material/Verified';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import CloudIcon from '@mui/icons-material/Cloud';
import WebIcon from '@mui/icons-material/Web';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';

/* ── High-contrast palette ─────────────────────────────────── */
const C = {
  /* text */
  heading: '#1A202C',
  text: '#2D3748',
  body: '#4A5568',
  muted: '#718096',
  /* accents */
  blue: '#0382B7',
  jade: '#03B792',
  coral: '#E58B6D',
  topaz: '#D4940A',
  purple: '#7C3AED',
  green: '#059669',
  /* surfaces */
  paper: '#FFFFFF',
  border: '#E2E8F0',
  bg: '#FAFAF7',
  /* lane backgrounds */
  laneSrc: 'rgba(3,130,183,0.045)',
  laneIngest: 'rgba(3,183,146,0.04)',
  laneSf: 'rgba(212,148,10,0.04)',
  laneAi: 'rgba(124,58,237,0.045)',
  laneOut: 'rgba(5,150,105,0.04)',
};

const MONO = '"JetBrains Mono", "Fira Code", monospace';

/* ── Keyframes ─────────────────────────────────────────────── */
const KEYFRAMES = `
@keyframes archUp{0%{opacity:0;transform:translateY(24px)}100%{opacity:1;transform:translateY(0)}}
@keyframes flowDash{to{stroke-dashoffset:-14}}
@keyframes pulseGlow{0%,100%{box-shadow:0 4px 24px rgba(124,58,237,0.10)}50%{box-shadow:0 4px 32px rgba(124,58,237,0.22)}}
@keyframes slideRight{0%{opacity:0;transform:translateX(12px)}100%{opacity:1;transform:translateX(0)}}
`;

/* ── Layer Lane wrapper ────────────────────────────────────── */
function LayerLane({
  bg,
  children,
  delay,
}: {
  bg: string;
  children: React.ReactNode;
  delay: number;
}) {
  return (
    <Box
      sx={{
        backgroundColor: bg,
        borderRadius: '16px',
        px: 3,
        py: 2.5,
        mb: 1,
        animation: `archUp 0.5s ease both`,
        animationDelay: `${delay}s`,
      }}
    >
      {children}
    </Box>
  );
}

/* ── Layer heading ─────────────────────────────────────────── */
function LayerHeading({
  text,
  color,
  icon,
}: {
  text: string;
  color: string;
  icon?: React.ReactNode;
}) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {icon && (
          <Box sx={{ color, '& .MuiSvgIcon-root': { fontSize: '1.3rem' } }}>
            {icon}
          </Box>
        )}
        <Typography
          sx={{
            fontFamily: '"DM Serif Display", Georgia, serif',
            fontSize: '1.45rem',
            fontWeight: 700,
            color,
            letterSpacing: '-0.01em',
            lineHeight: 1.2,
          }}
        >
          {text}
        </Typography>
      </Box>
      <Box
        sx={{
          mt: 0.75,
          ml: icon ? '2.8rem' : 0,
          width: 40,
          height: 3,
          borderRadius: 2,
          backgroundColor: color,
          opacity: 0.5,
        }}
      />
    </Box>
  );
}

/* ── Node card with integrated tech badges ─────────────────── */
function NodeCard({
  title,
  subtitle,
  accent,
  delay,
  tech,
  icon,
  elevated,
}: {
  title: string;
  subtitle: string;
  accent: string;
  delay: number;
  tech?: string[];
  icon?: React.ReactNode;
  elevated?: boolean;
}) {
  return (
    <Card
      sx={{
        borderLeft: `4px solid ${accent}`,
        borderTop: elevated ? `2px solid ${accent}` : undefined,
        px: 2.5,
        py: 2,
        height: '100%',
        animation: `archUp 0.5s ease both`,
        animationDelay: `${delay}s`,
        boxShadow: elevated
          ? `0 4px 24px ${accent}18`
          : '0 2px 8px rgba(0,0,0,0.06)',
        transition: 'transform 0.25s ease, box-shadow 0.25s ease',
        ...(elevated && { animation: `archUp 0.5s ease both, pulseGlow 3s ease-in-out infinite` }),
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: `0 8px 28px ${accent}20`,
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 0.75 }}>
        {icon && (
          <Box sx={{ color: accent, '& .MuiSvgIcon-root': { fontSize: '1.1rem' } }}>
            {icon}
          </Box>
        )}
        <Typography
          sx={{
            fontSize: '0.95rem',
            fontWeight: 700,
            color: C.heading,
            fontFamily: '"DM Sans", sans-serif',
          }}
        >
          {title}
        </Typography>
      </Box>
      <Typography
        sx={{
          fontSize: '0.8rem',
          fontWeight: 500,
          color: C.body,
          lineHeight: 1.55,
          mb: tech ? 1.25 : 0,
        }}
      >
        {subtitle}
      </Typography>
      {tech && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {tech.map((t) => (
            <Box
              key={t}
              sx={{
                display: 'inline-flex',
                px: 1,
                py: 0.25,
                borderRadius: '5px',
                backgroundColor: `${accent}10`,
                border: `1px solid ${accent}25`,
              }}
            >
              <Typography
                sx={{
                  fontSize: '0.62rem',
                  fontWeight: 600,
                  color: accent,
                  fontFamily: MONO,
                  letterSpacing: '0.02em',
                }}
              >
                {t}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Card>
  );
}

/* ── Vertical connector arrow with label ───────────────────── */
function Connector({ label, color, delay }: { label?: string; color: string; delay: number }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 0.75,
        animation: `archUp 0.4s ease both`,
        animationDelay: `${delay}s`,
      }}
    >
      <svg width="20" height="48" viewBox="0 0 20 48">
        <line
          x1="10" y1="0" x2="10" y2="38"
          stroke={color}
          strokeWidth="2.5"
          strokeDasharray="5 4"
          style={{ animation: 'flowDash 0.8s linear infinite' }}
        />
        <polygon points="4,36 10,48 16,36" fill={color} />
      </svg>
      {label && (
        <Typography
          sx={{
            fontSize: '0.58rem',
            fontWeight: 600,
            color: C.muted,
            mt: 0.25,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontFamily: MONO,
          }}
        >
          {label}
        </Typography>
      )}
    </Box>
  );
}

/* ── Horizontal flow arrow ─────────────────────────────────── */
function FlowArrow({ label, color }: { label: string; color: string }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        px: 0.5,
      }}
    >
      <svg width="52" height="16" viewBox="0 0 52 16">
        <line
          x1="0" y1="8" x2="40" y2="8"
          stroke={color}
          strokeWidth="2.5"
          strokeDasharray="5 3"
          style={{ animation: 'flowDash 0.8s linear infinite' }}
        />
        <polygon points="40,3 52,8 40,13" fill={color} />
      </svg>
      <Typography
        sx={{
          fontSize: '0.55rem',
          fontWeight: 600,
          color: C.muted,
          mt: 0.25,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          fontFamily: MONO,
        }}
      >
        {label}
      </Typography>
    </Box>
  );
}

/* ── Snowflake stage card (card-in-card) ───────────────────── */
function StageCard({
  name,
  desc,
  tables,
  color,
}: {
  name: string;
  desc: string;
  tables: string[];
  color: string;
}) {
  return (
    <Card
      sx={{
        border: `2px solid ${color}`,
        backgroundColor: `${color}06`,
        boxShadow: `0 2px 12px ${color}10`,
        borderRadius: '12px',
        px: 2.5,
        py: 2,
        minWidth: 170,
        textAlign: 'center',
      }}
    >
      <Typography
        sx={{
          fontSize: '1rem',
          fontWeight: 800,
          color,
          fontFamily: MONO,
          letterSpacing: '0.06em',
        }}
      >
        {name}
      </Typography>
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 500, color: C.body, mt: 0.5, mb: 1.25 }}>
        {desc}
      </Typography>
      <Box sx={{ textAlign: 'left' }}>
        {tables.map((t) => (
          <Typography
            key={t}
            sx={{
              fontSize: '0.72rem',
              color: C.muted,
              fontFamily: MONO,
              lineHeight: 1.7,
              fontWeight: 500,
              '&::before': {
                content: '"\\2022"',
                color,
                mr: 0.75,
                fontSize: '0.6rem',
              },
            }}
          >
            {t}
          </Typography>
        ))}
      </Box>
    </Card>
  );
}

/* ── CAVM Agent box ────────────────────────────────────────── */
function AgentBox({
  step,
  label,
  desc,
  color,
  icon,
}: {
  step: string;
  label: string;
  desc: string;
  color: string;
  icon: React.ReactNode;
}) {
  return (
    <Box sx={{ textAlign: 'center', flex: '1 1 0', minWidth: 110 }}>
      <Box
        sx={{
          width: 48,
          height: 48,
          borderRadius: '12px',
          background: `linear-gradient(135deg, ${color}18 0%, ${color}08 100%)`,
          border: `2px solid ${color}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mx: 'auto',
          mb: 1,
          boxShadow: `0 2px 12px ${color}15`,
        }}
      >
        <Box sx={{ color, '& .MuiSvgIcon-root': { fontSize: '1.25rem' } }}>
          {icon}
        </Box>
      </Box>
      <Typography
        sx={{
          fontSize: '0.65rem',
          fontWeight: 700,
          color,
          fontFamily: MONO,
          letterSpacing: '0.04em',
          mb: 0.25,
        }}
      >
        {step}
      </Typography>
      <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: C.heading }}>{label}</Typography>
      <Typography sx={{ fontSize: '0.72rem', fontWeight: 500, color: C.body, mt: 0.25, lineHeight: 1.45 }}>
        {desc}
      </Typography>
    </Box>
  );
}

/* ══════════════════════════════════════════════════════════════
   MAIN PAGE
   ══════════════════════════════════════════════════════════════ */
export default function ArchitecturePage() {
  return (
    <>
      <style>{KEYFRAMES}</style>

      <Box
        sx={{
          position: 'relative',
          minHeight: '100%',
          backgroundImage: 'radial-gradient(circle, #CBD5E0 0.7px, transparent 0.7px)',
          backgroundSize: '20px 20px',
          mx: -3,
          mt: -3,
          px: 3,
          pt: 3,
          pb: 6,
        }}
      >
        {/* ─── Observability cross-cutting bar (right edge) ─── */}
        <Box
          sx={{
            position: 'absolute',
            top: 100,
            right: 16,
            bottom: 120,
            width: 36,
            display: { xs: 'none', lg: 'flex' },
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            border: `2px dashed ${C.green}60`,
            backgroundColor: `${C.green}08`,
            animation: 'slideRight 0.6s ease both',
            animationDelay: '1.2s',
            zIndex: 2,
          }}
        >
          <MonitorHeartIcon sx={{ fontSize: '1rem', color: C.green, mb: 1 }} />
          <Typography
            sx={{
              writingMode: 'vertical-rl',
              textOrientation: 'mixed',
              fontSize: '0.65rem',
              fontWeight: 700,
              color: C.green,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              fontFamily: MONO,
            }}
          >
            Observability
          </Typography>
        </Box>

        {/* Dotted connectors from lanes to observability bar */}
        {[140, 310, 480, 650, 830].map((top, i) => (
          <Box
            key={i}
            sx={{
              position: 'absolute',
              top,
              right: 52,
              width: 24,
              height: 0,
              borderTop: `1.5px dotted ${C.green}50`,
              display: { xs: 'none', lg: 'block' },
              animation: 'slideRight 0.4s ease both',
              animationDelay: `${1.3 + i * 0.1}s`,
            }}
          />
        ))}

        {/* ─── Hero ─── */}
        <Box sx={{ mb: 4, animation: 'archUp 0.5s ease both', pr: { lg: 6 } }}>
          <Typography
            sx={{
              fontFamily: '"DM Serif Display", Georgia, serif',
              fontSize: { xs: '1.8rem', md: '2.4rem' },
              color: C.heading,
              lineHeight: 1.15,
              fontWeight: 400,
            }}
          >
            System Architecture
          </Typography>
          <Box
            sx={{
              mt: 1,
              width: 56,
              height: 3.5,
              borderRadius: 2,
              background: `linear-gradient(90deg, ${C.jade} 0%, ${C.blue} 50%, ${C.purple} 100%)`,
            }}
          />
          <Typography
            sx={{
              mt: 1.5,
              fontSize: '0.92rem',
              fontWeight: 500,
              color: C.body,
              maxWidth: 680,
              lineHeight: 1.7,
            }}
          >
            End-to-end data flow — from external financial data sources through a three-layer
            Snowflake warehouse, multi-agent AI analysis, and interactive frontends.
          </Typography>
        </Box>

        {/* container that gives room for the observability bar */}
        <Box sx={{ pr: { lg: 6 } }}>

          {/* ═══ LAYER 1 — Data Sources ═══ */}
          <LayerLane bg={C.laneSrc} delay={0.1}>
            <LayerHeading text="Data Sources" color={C.blue} icon={<CloudIcon />} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, md: 3 }}>
                <NodeCard
                  title="Yahoo Finance"
                  subtitle="Daily OHLCV stock prices, market cap, P/E ratios"
                  accent={C.blue}
                  delay={0.15}
                  tech={['yfinance', 'REST API']}
                />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <NodeCard
                  title="Alpha Vantage"
                  subtitle="Quarterly fundamentals — EPS, revenue, margins"
                  accent={C.blue}
                  delay={0.2}
                  tech={['REST API', 'JSON']}
                />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <NodeCard
                  title="NewsAPI"
                  subtitle="Financial news articles with sentiment signals"
                  accent={C.blue}
                  delay={0.25}
                  tech={['REST API', 'NLP']}
                />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <NodeCard
                  title="SEC EDGAR"
                  subtitle="10-K / 10-Q filings, XBRL financial data"
                  accent={C.blue}
                  delay={0.3}
                  tech={['EDGAR API', 'XBRL']}
                />
              </Grid>
            </Grid>
          </LayerLane>

          <Connector label="fetch & validate" color={C.blue} delay={0.35} />

          {/* ═══ LAYER 2 — Ingestion & Orchestration ═══ */}
          <LayerLane bg={C.laneIngest} delay={0.4}>
            <LayerHeading text="Ingestion & Orchestration" color={C.jade} icon={<StorageIcon />} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="Apache Airflow"
                  subtitle="Daily DAG @ 5 PM EST — 4 parallel fetch tasks, dbt transforms, quality check"
                  accent={C.jade}
                  delay={0.45}
                  tech={['Airflow 2.8', 'Celery', 'Redis']}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="Python Data Loaders"
                  subtitle="BaseDataLoader pattern — fetch, validate, quality score, MERGE into RAW"
                  accent={C.jade}
                  delay={0.5}
                  tech={['Python 3.9', 'Snowpark', 'boto3']}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="AWS S3"
                  subtitle="SEC filing document storage — raw PDFs, extracted text chunks"
                  accent={C.coral}
                  delay={0.55}
                  tech={['S3', 'Terraform']}
                  icon={<CloudIcon />}
                />
              </Grid>
            </Grid>
          </LayerLane>

          <Connector label="MERGE into RAW" color={C.jade} delay={0.6} />

          {/* ═══ LAYER 3 — Snowflake Warehouse ═══ */}
          <LayerLane bg={C.laneSf} delay={0.65}>
            <LayerHeading text="Snowflake Data Warehouse" color={C.topaz} icon={<StorageIcon />} />
            <Card
              sx={{
                p: 3,
                background: `linear-gradient(135deg, ${C.paper} 0%, #FEFDF8 100%)`,
                boxShadow: '0 3px 16px rgba(212,148,10,0.10)',
                border: `1px solid ${C.topaz}30`,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  flexWrap: 'wrap',
                  gap: { xs: 2, md: 0 },
                }}
              >
                <StageCard
                  name="RAW"
                  desc="Ingested data with quality scores"
                  tables={['raw_stock_prices', 'raw_fundamentals', 'raw_news', 'raw_sec_filings']}
                  color={C.coral}
                />

                <FlowArrow label="dbt views" color={C.topaz} />

                <StageCard
                  name="STAGING"
                  desc="Cleaned & typed views"
                  tables={['stg_stock_prices', 'stg_fundamentals', 'stg_news', 'stg_sec_filings']}
                  color="#B8860B"
                />

                <FlowArrow label="dbt tables" color={C.jade} />

                <StageCard
                  name="ANALYTICS"
                  desc="Fact & dimension tables"
                  tables={['dim_company', 'fct_stock_metrics', 'fct_fundamentals_growth', 'fct_news_sentiment_agg', 'fct_sec_financial_summary']}
                  color={C.jade}
                />
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2, gap: 0.75 }}>
                {['dbt 1.7', 'Snowflake', 'MERGE', 'Cortex SUMMARIZE'].map((t) => (
                  <Box
                    key={t}
                    sx={{
                      px: 1,
                      py: 0.2,
                      borderRadius: '4px',
                      backgroundColor: `${C.topaz}12`,
                      border: `1px solid ${C.topaz}30`,
                    }}
                  >
                    <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: C.topaz, fontFamily: MONO }}>
                      {t}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Card>
          </LayerLane>

          <Connector label="LLM inference" color={C.purple} delay={0.85} />

          {/* ═══ LAYER 4 — AI & ML Processing ═══ */}
          <LayerLane bg={C.laneAi} delay={0.9}>
            <LayerHeading text="AI & ML Processing" color={C.purple} icon={<SmartToyIcon />} />

            <Grid container spacing={2.5}>
              {/* CAVM Pipeline */}
              <Grid size={{ xs: 12, md: 7 }}>
                <Card
                  sx={{
                    p: 2.5,
                    boxShadow: `0 4px 24px ${C.purple}12`,
                    borderTop: `2px solid ${C.purple}`,
                    animation: 'pulseGlow 3s ease-in-out infinite',
                    height: '100%',
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      color: C.purple,
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      mb: 2,
                      fontFamily: MONO,
                    }}
                  >
                    CAVM Multi-Agent Pipeline
                  </Typography>

                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      flexWrap: 'wrap',
                      gap: { xs: 1.5, md: 0 },
                    }}
                  >
                    {[
                      { step: 'C', label: 'Chart Agent', desc: '8 matplotlib charts + 3-iteration VLM refinement', color: C.blue, icon: <BarChartIcon /> },
                      { step: 'A', label: 'Analysis Agent', desc: 'Per-chart LLM analysis + SEC MD&A summaries', color: C.jade, icon: <DescriptionIcon /> },
                      { step: 'V', label: 'Validation Agent', desc: 'Visual quality & data integrity checks', color: C.topaz, icon: <VerifiedIcon /> },
                      { step: 'M', label: 'Report Agent', desc: 'Branded 15-20 page PDF assembly', color: C.coral, icon: <PictureAsPdfIcon /> },
                    ].map((agent, i, arr) => (
                      <React.Fragment key={agent.step}>
                        <AgentBox {...agent} />
                        {i < arr.length - 1 && (
                          <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', pt: 2 }}>
                            <svg width="32" height="14" viewBox="0 0 32 14">
                              <line
                                x1="0" y1="7" x2="22" y2="7"
                                stroke={C.purple}
                                strokeWidth="2"
                                strokeDasharray="4 3"
                                style={{ animation: 'flowDash 0.8s linear infinite' }}
                              />
                              <polygon points="22,2 32,7 22,12" fill={C.purple} />
                            </svg>
                          </Box>
                        )}
                      </React.Fragment>
                    ))}
                  </Box>

                  {/* Iterative loop: V → A */}
                  <Box
                    sx={{
                      display: { xs: 'none', md: 'flex' },
                      justifyContent: 'center',
                      mt: 1.5,
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        px: 2,
                        py: 0.5,
                        borderRadius: '8px',
                        border: `1.5px dashed ${C.topaz}`,
                        backgroundColor: `${C.topaz}08`,
                      }}
                    >
                      <svg width="24" height="16" viewBox="0 0 24 16">
                        <path
                          d="M20,8 Q20,2 12,2 Q4,2 4,8"
                          fill="none"
                          stroke={C.topaz}
                          strokeWidth="1.5"
                          strokeDasharray="3 2"
                          style={{ animation: 'flowDash 1s linear infinite' }}
                        />
                        <polygon points="2,6 4,10 6,6" fill={C.topaz} />
                      </svg>
                      <Typography
                        sx={{
                          fontSize: '0.6rem',
                          fontWeight: 600,
                          color: C.topaz,
                          fontFamily: MONO,
                          letterSpacing: '0.04em',
                        }}
                      >
                        Re-run on failure: V → A
                      </Typography>
                    </Box>
                  </Box>
                </Card>
              </Grid>

              {/* AI Services — forked paths */}
              <Grid size={{ xs: 12, md: 5 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, height: '100%' }}>
                  {/* Fork label */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <svg width="24" height="28" viewBox="0 0 24 28">
                      <line x1="12" y1="0" x2="12" y2="10" stroke={C.purple} strokeWidth="2" />
                      <line x1="12" y1="10" x2="4" y2="20" stroke={C.blue} strokeWidth="2" />
                      <line x1="12" y1="10" x2="20" y2="20" stroke={C.coral} strokeWidth="2" />
                      <circle cx="12" cy="10" r="2.5" fill={C.purple} />
                    </svg>
                    <Typography
                      sx={{
                        fontSize: '0.62rem',
                        fontWeight: 600,
                        color: C.muted,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        fontFamily: MONO,
                      }}
                    >
                      AI service routing
                    </Typography>
                  </Box>

                  <NodeCard
                    title="Snowflake Cortex"
                    subtitle="Structured SQL tasks — LLM (mistral-large), VLM (claude-sonnet), Cortex Search, SUMMARIZE"
                    accent={C.blue}
                    delay={1.0}
                    tech={['mistral-large', 'claude-sonnet', 'Cortex Search']}
                    icon={<SmartToyIcon />}
                    elevated
                  />
                  <NodeCard
                    title="AWS Bedrock"
                    subtitle="Unstructured RAG — Knowledge Base retrieval, Guardrails (PII / hallucination), multi-model inference"
                    accent={C.coral}
                    delay={1.05}
                    tech={['Llama 3', 'Titan', 'Guardrails', 'RAG']}
                    icon={<CloudIcon />}
                    elevated
                  />
                </Box>
              </Grid>
            </Grid>
          </LayerLane>

          <Connector label="API / PDF" color={C.green} delay={1.1} />

          {/* ═══ LAYER 5 — Presentation ═══ */}
          <LayerLane bg={C.laneOut} delay={1.15}>
            <LayerHeading text="Presentation & Output" color={C.green} icon={<WebIcon />} />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="React Frontend"
                  subtitle="Dashboard, Analytics, SEC Filings, Reports, Observability — interactive data exploration"
                  accent={C.jade}
                  delay={1.2}
                  tech={['Next.js 16', 'MUI v9', 'Recharts']}
                  icon={<WebIcon />}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="Streamlit App"
                  subtitle="10-page interactive UI — RAG search, multi-model comparison, guardrails demo"
                  accent={C.blue}
                  delay={1.25}
                  tech={['Streamlit', 'Plotly', 'boto3']}
                  icon={<WebIcon />}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <NodeCard
                  title="Generated Reports"
                  subtitle="Branded PDF (15-20 pp), 8 chart PNGs, chart_manifest.json, pipeline_result.json"
                  accent={C.topaz}
                  delay={1.3}
                  tech={['reportlab', 'matplotlib', 'PDF']}
                  icon={<PictureAsPdfIcon />}
                />
              </Grid>
            </Grid>
          </LayerLane>

        </Box>{/* end pr container */}
      </Box>
    </>
  );
}
