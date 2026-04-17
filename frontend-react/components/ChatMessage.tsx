'use client';

import React from 'react';
import { Box, Paper, Typography, Avatar } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        mb: 2,
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: isUser ? '#F0EDE6' : 'rgba(201,107,174,0.08)',
          color: isUser ? '#6B6760' : '#C96BAE',
        }}
      >
        {isUser ? <PersonIcon sx={{ fontSize: 18 }} /> : <SmartToyIcon sx={{ fontSize: 18 }} />}
      </Avatar>
      <Paper
        sx={{
          p: 2,
          maxWidth: '75%',
          backgroundColor: isUser ? '#F0EDE6' : 'rgba(3,130,183,0.04)',
          border: isUser
            ? '1px solid #E8E4DB'
            : '1px solid rgba(3,130,183,0.10)',
        }}
      >
        <Typography
          variant="body2"
          sx={{
            color: '#2C2A25',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.65,
            fontSize: '0.875rem',
          }}
        >
          {content}
        </Typography>
      </Paper>
    </Box>
  );
}
