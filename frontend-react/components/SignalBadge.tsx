'use client';

import React from 'react';
import { Chip } from '@mui/material';

const SIGNAL_COLORS: Record<string, { bg: string; text: string }> = {
  BULLISH:         { bg: 'rgba(157,203,184,0.12)', text: '#9DCBB8' },
  STRONG_GROWTH:   { bg: 'rgba(157,203,184,0.12)', text: '#9DCBB8' },
  EXCELLENT:       { bg: 'rgba(157,203,184,0.12)', text: '#9DCBB8' },
  HEALTHY:         { bg: 'rgba(157,203,184,0.12)', text: '#9DCBB8' },
  MODERATE_GROWTH: { bg: 'rgba(248,203,134,0.12)', text: '#F8CB86' },
  NEUTRAL:         { bg: 'rgba(248,203,134,0.12)', text: '#F8CB86' },
  MIXED:           { bg: 'rgba(248,203,134,0.12)', text: '#F8CB86' },
  FAIR:            { bg: 'rgba(248,203,134,0.12)', text: '#F8CB86' },
  NO_COVERAGE:     { bg: 'rgba(138,134,120,0.12)', text: '#8A8678' },
  BEARISH:         { bg: 'rgba(229,139,109,0.12)', text: '#E58B6D' },
  DECLINING:       { bg: 'rgba(229,139,109,0.12)', text: '#E58B6D' },
  UNPROFITABLE:    { bg: 'rgba(229,139,109,0.12)', text: '#E58B6D' },
};

interface SignalBadgeProps {
  label: string;
  signal?: string;
}

export default function SignalBadge({ label, signal }: SignalBadgeProps) {
  const key = (signal || label || '').toUpperCase().replace(/\s+/g, '_');
  const colors = SIGNAL_COLORS[key] || { bg: 'rgba(138,134,120,0.12)', text: '#8A8678' };

  return (
    <Chip
      label={label || 'N/A'}
      size="small"
      sx={{
        backgroundColor: colors.bg,
        color: colors.text,
        fontWeight: 600,
        fontSize: '0.7rem',
        border: `1px solid ${colors.text}20`,
        boxShadow: `0 0 12px ${colors.text}08`,
      }}
    />
  );
}
