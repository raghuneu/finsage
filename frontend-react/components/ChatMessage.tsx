'use client';

import React from 'react';
import { Box, Paper, Avatar } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
        mb: 2.5,
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
      }}
    >
      <Avatar
        sx={{
          width: 30,
          height: 30,
          mt: 0.5,
          bgcolor: isUser ? '#F0EDE6' : 'rgba(3,130,183,0.08)',
          color: isUser ? '#6B6760' : '#0382B7',
          flexShrink: 0,
        }}
      >
        {isUser ? (
          <PersonIcon sx={{ fontSize: 16 }} />
        ) : (
          <SmartToyIcon sx={{ fontSize: 16 }} />
        )}
      </Avatar>
      <Paper
        elevation={0}
        sx={{
          px: 2.5,
          py: 2,
          maxWidth: '80%',
          backgroundColor: isUser ? '#F0EDE6' : '#FAFAF8',
          border: isUser
            ? '1px solid #E8E4DB'
            : '1px solid rgba(3,130,183,0.10)',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        }}
      >
        {isUser ? (
          <Box
            sx={{
              color: '#2C2A25',
              fontSize: '0.875rem',
              lineHeight: 1.65,
            }}
          >
            {content}
          </Box>
        ) : (
          <Box
            sx={{
              color: '#2C2A25',
              fontSize: '0.875rem',
              lineHeight: 1.7,
              '& h1': {
                fontSize: '1.05rem',
                fontWeight: 700,
                color: '#1A1917',
                mt: 0,
                mb: 1.5,
                lineHeight: 1.3,
                borderBottom: '1px solid rgba(3,130,183,0.12)',
                pb: 1,
              },
              '& h2': {
                fontSize: '0.95rem',
                fontWeight: 650,
                color: '#0382B7',
                mt: 2.5,
                mb: 1,
                lineHeight: 1.3,
              },
              '& h3': {
                fontSize: '0.875rem',
                fontWeight: 650,
                color: '#2C2A25',
                mt: 2,
                mb: 0.75,
                lineHeight: 1.3,
              },
              '& p': {
                my: 0.75,
                lineHeight: 1.7,
              },
              '& p:first-of-type': {
                mt: 0,
              },
              '& p:last-of-type': {
                mb: 0,
              },
              '& ul, & ol': {
                pl: 2.5,
                my: 1,
              },
              '& li': {
                mb: 0.5,
                lineHeight: 1.65,
                '&::marker': {
                  color: '#0382B7',
                },
              },
              '& strong': {
                fontWeight: 650,
                color: '#1A1917',
              },
              '& em': {
                fontStyle: 'italic',
                color: '#4A4743',
              },
              '& code': {
                backgroundColor: 'rgba(3,130,183,0.06)',
                color: '#0382B7',
                px: 0.75,
                py: 0.25,
                borderRadius: '4px',
                fontSize: '0.8rem',
                fontFamily: '"SF Mono", "Fira Code", monospace',
              },
              '& pre': {
                backgroundColor: '#F0EDE6',
                border: '1px solid #E8E4DB',
                borderRadius: '8px',
                p: 1.5,
                my: 1.5,
                overflow: 'auto',
                '& code': {
                  backgroundColor: 'transparent',
                  px: 0,
                  py: 0,
                  color: '#2C2A25',
                },
              },
              '& blockquote': {
                borderLeft: '3px solid #0382B7',
                pl: 2,
                ml: 0,
                my: 1.5,
                color: '#6B6760',
                fontStyle: 'italic',
              },
              '& hr': {
                border: 'none',
                borderTop: '1px solid #E8E4DB',
                my: 2,
              },
              '& table': {
                borderCollapse: 'collapse',
                width: '100%',
                my: 1.5,
                fontSize: '0.82rem',
              },
              '& th': {
                backgroundColor: 'rgba(3,130,183,0.06)',
                border: '1px solid #E8E4DB',
                px: 1.5,
                py: 0.75,
                textAlign: 'left',
                fontWeight: 650,
                color: '#0382B7',
              },
              '& td': {
                border: '1px solid #E8E4DB',
                px: 1.5,
                py: 0.75,
              },
              '& a': {
                color: '#0382B7',
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              },
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
