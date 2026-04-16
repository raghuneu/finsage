'use client';

import React from 'react';
import { Skeleton, Card, CardContent, Box, Grid } from '@mui/material';

const skeletonSx = {
  bgcolor: '#EDE9E0',
  '&::after': { background: 'linear-gradient(90deg, transparent, #E2DDD3, transparent)' },
};

export function DashboardSkeleton() {
  return (
    <Box>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[...Array(5)].map((_, i) => (
          <Grid size={{ xs: 6, md: 2.4 }} key={i}>
            <Card>
              <CardContent sx={{ p: 2 }}>
                <Skeleton variant="text" width="60%" height={16} sx={skeletonSx} />
                <Skeleton variant="text" width="80%" height={32} sx={{ mt: 1, ...skeletonSx }} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 1, ...skeletonSx }} />
        </CardContent>
      </Card>
    </Box>
  );
}

export function ChartSkeleton({ height = 350 }: { height?: number }) {
  return (
    <Card>
      <CardContent>
        <Skeleton variant="text" width="30%" height={24} sx={{ mb: 2, ...skeletonSx }} />
        <Skeleton variant="rectangular" height={height} sx={{ borderRadius: 1, ...skeletonSx }} />
      </CardContent>
    </Card>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Card>
      <CardContent>
        <Skeleton variant="text" width="40%" height={24} sx={{ mb: 2, ...skeletonSx }} />
        {[...Array(rows)].map((_, i) => (
          <Skeleton key={i} variant="text" height={32} sx={{ mb: 0.5, ...skeletonSx }} />
        ))}
      </CardContent>
    </Card>
  );
}
