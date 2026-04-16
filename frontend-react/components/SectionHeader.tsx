'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
}

export default function SectionHeader({ title, subtitle }: SectionHeaderProps) {
  return (
    <Box sx={{ borderLeft: '3px solid #C96BAE', pl: 2, mb: 2 }}>
      <Typography
        variant="h6"
        sx={{
          fontFamily: '"DM Serif Display", Georgia, serif',
          fontWeight: 400,
          color: '#2C2A25',
        }}
      >
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="body2" sx={{ color: '#6B6760', fontSize: '0.8rem', mt: 0.25 }}>
          {subtitle}
        </Typography>
      )}
    </Box>
  );
}
