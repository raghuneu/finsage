'use client';

import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';

interface MetricCardProps {
  title: string;
  value: string;
  delta?: string | null;
  color?: string;
}

export default function MetricCard({ title, value, delta, color }: MetricCardProps) {
  const isPositive = delta ? !delta.startsWith('-') : true;
  const deltaColor = isPositive ? '#9DCBB8' : '#E58B6D';

  return (
    <Card
      sx={{
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        transition: 'border-color 0.25s ease, box-shadow 0.25s ease',
        '&:hover': {
          borderColor: color || 'rgba(201,107,174,0.25)',
          boxShadow: `0 4px 24px ${color ? color + '15' : 'rgba(201,107,174,0.08)'}`,
        },
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          background: color
            ? `linear-gradient(90deg, ${color} 0%, transparent 100%)`
            : 'linear-gradient(90deg, #C96BAE 0%, #0382B7 100%)',
          opacity: 0.6,
        },
      }}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography
          variant="caption"
          sx={{
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontWeight: 600,
            color: '#6B6760',
            fontSize: '0.6rem',
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="h5"
          sx={{
            fontFamily: '"DM Serif Display", Georgia, serif',
            fontWeight: 400,
            color: color || '#2C2A25',
            mt: 0.5,
            lineHeight: 1.2,
          }}
        >
          {value}
        </Typography>
        {delta && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.75 }}>
            {isPositive ? (
              <TrendingUpIcon sx={{ fontSize: 14, color: deltaColor }} />
            ) : (
              <TrendingDownIcon sx={{ fontSize: 14, color: deltaColor }} />
            )}
            <Typography
              variant="caption"
              sx={{ color: deltaColor, fontWeight: 600, fontSize: '0.75rem' }}
            >
              {delta}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
