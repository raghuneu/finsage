'use client';

import React from 'react';
import { Chip } from '@mui/material';

const SIGNAL_COLORS: Record<string, { bg: string; text: string }> = {
  BULLISH:         { bg: 'rgba(34,160,100,0.10)', text: '#1A9E60' },
  STRONG_GROWTH:   { bg: 'rgba(34,160,100,0.10)', text: '#1A9E60' },
  EXCELLENT:       { bg: 'rgba(34,160,100,0.10)', text: '#1A9E60' },
  HEALTHY:         { bg: 'rgba(34,160,100,0.10)', text: '#1A9E60' },
  MODERATE_GROWTH: { bg: 'rgba(210,150,20,0.10)', text: '#C08C00' },
  NEUTRAL:         { bg: 'rgba(210,150,20,0.10)', text: '#C08C00' },
  MIXED:           { bg: 'rgba(210,150,20,0.10)', text: '#C08C00' },
  FAIR:            { bg: 'rgba(210,150,20,0.10)', text: '#C08C00' },
  NO_COVERAGE:     { bg: 'rgba(138,134,120,0.12)', text: '#8A8678' },
  BEARISH:         { bg: 'rgba(210,60,40,0.10)', text: '#C9392C' },
  DECLINING:       { bg: 'rgba(210,60,40,0.10)', text: '#C9392C' },
  UNPROFITABLE:    { bg: 'rgba(210,60,40,0.10)', text: '#C9392C' },
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
        fontWeight: 700,
        fontSize: '0.72rem',
        letterSpacing: '0.02em',
        border: `1px solid ${colors.text}20`,
        boxShadow: `0 0 12px ${colors.text}08`,
      }}
    />
  );
}
