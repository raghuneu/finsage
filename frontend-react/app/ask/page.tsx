'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Card,
  Typography,
  TextField,
  IconButton,
  Chip,
  Avatar,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { useTicker } from '@/lib/ticker-context';
import { askFinSage } from '@/lib/api';
import ChatMessage from '@/components/ChatMessage';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function AskFinSagePage() {
  const { ticker } = useTicker();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestions = [
    `What is ${ticker}'s competitive advantage?`,
    `Summarize ${ticker}'s risk factors`,
    `How has ${ticker}'s revenue trended?`,
    `Key takeaways from ${ticker}'s MD&A?`,
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { role: 'user', content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const data = await askFinSage(ticker, text.trim());
      if (data.error) {
        setError(data.error);
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: `Error: ${data.error}` },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: data.answer },
        ]);
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : 'Failed to get response';
      setError(errMsg);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${errMsg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      {/* Source badge */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoAwesomeIcon sx={{ color: '#C96BAE', fontSize: 18 }} />
        <Typography variant="body2" sx={{ color: '#6B6760', fontSize: '0.8rem' }}>
          Powered by Snowflake Cortex
        </Typography>
      </Box>

      {/* Suggestion pills */}
      {messages.length === 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ color: '#6B6760', mb: 1.5, fontSize: '0.8rem' }}>
            Suggested questions
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {suggestions.map((s, i) => (
              <Chip
                key={i}
                label={s}
                variant="outlined"
                onClick={() => sendMessage(s)}
                sx={{
                  borderColor: '#E8E4DB',
                  color: '#6B6760',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  '&:hover': {
                    borderColor: '#C96BAE',
                    color: '#C96BAE',
                    backgroundColor: 'rgba(201,107,174,0.05)',
                  },
                }}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Chat messages */}
      <Box
        sx={{
          flexGrow: 1,
          overflow: 'auto',
          mb: 2,
          pr: 1,
        }}
      >
        {messages.length === 0 && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
            }}
          >
            <Typography variant="body2" sx={{ color: '#9A9590' }}>
              Ask a question about {ticker} to get started
            </Typography>
          </Box>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} />
        ))}
        {loading && (
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', ml: 0, mt: 0.5 }}>
            <Avatar
              sx={{
                width: 30,
                height: 30,
                mt: 0.5,
                bgcolor: 'rgba(3,130,183,0.08)',
                color: '#0382B7',
                flexShrink: 0,
              }}
            >
              <SmartToyIcon sx={{ fontSize: 16 }} />
            </Avatar>
            <Box
              sx={{
                display: 'flex',
                gap: 0.6,
                alignItems: 'center',
                px: 2,
                py: 1.5,
                backgroundColor: '#FAFAF8',
                border: '1px solid rgba(3,130,183,0.10)',
                borderRadius: '16px 16px 16px 4px',
              }}
            >
              {[0, 1, 2].map((i) => (
                <Box
                  key={i}
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    backgroundColor: '#0382B7',
                    opacity: 0.5,
                    animation: 'pulse 1.2s ease-in-out infinite',
                    animationDelay: `${i * 0.2}s`,
                    '@keyframes pulse': {
                      '0%, 80%, 100%': { opacity: 0.25, transform: 'scale(0.8)' },
                      '40%': { opacity: 0.8, transform: 'scale(1.1)' },
                    },
                  }}
                />
              ))}
            </Box>
          </Box>
        )}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input area */}
      <Card sx={{ p: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextField
            fullWidth
            placeholder={`Ask about ${ticker}...`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            size="small"
            multiline
            maxRows={3}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: '#F7F5F0',
              },
            }}
          />
          <IconButton
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            sx={{
              backgroundColor: input.trim() ? '#C96BAE' : 'transparent',
              color: input.trim() ? '#FFFFFF' : '#9A9590',
              '&:hover': { backgroundColor: '#D98DC3' },
              '&.Mui-disabled': { backgroundColor: 'transparent', color: '#D8D4CB' },
            }}
          >
            <SendIcon sx={{ fontSize: 20 }} />
          </IconButton>
          {messages.length > 0 && (
            <IconButton
              onClick={() => {
                setMessages([]);
                setError(null);
              }}
              sx={{ color: '#6B6760' }}
              title="Clear chat"
            >
              <DeleteOutlinedIcon sx={{ fontSize: 20 }} />
            </IconButton>
          )}
        </Box>
      </Card>
    </Box>
  );
}
