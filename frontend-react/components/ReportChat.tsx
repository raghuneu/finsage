'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  IconButton,
  Chip,
  CircularProgress,
  Button,
  Divider,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import ChatMessage from '@/components/ChatMessage';
import { askReportChat, resetReportChat } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const STARTER_PROMPTS = [
  'Summarize key findings',
  'What are the biggest risks?',
  'Explain revenue growth trend',
  'Is sentiment bullish or bearish?',
];

interface ReportChatProps {
  ticker: string;
}

export default function ReportChat({ ticker }: ReportChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef(crypto.randomUUID());
  const prevTickerRef = useRef(ticker);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-reset session when ticker changes
  useEffect(() => {
    if (prevTickerRef.current !== ticker) {
      prevTickerRef.current = ticker;
      sessionIdRef.current = crypto.randomUUID();
      setMessages([]);
      setInput('');
      setError(null);
    }
  }, [ticker]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(
    async (question: string) => {
      if (!question.trim() || loading) return;

      setError(null);
      const userMsg: Message = { role: 'user', content: question.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setLoading(true);

      try {
        const data = await askReportChat(ticker, sessionIdRef.current, question.trim());
        const assistantMsg: Message = {
          role: 'assistant',
          content: data.answer,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : 'Unknown error';
        setError(`Failed to get response: ${errMsg}`);
      } finally {
        setLoading(false);
      }
    },
    [ticker, loading],
  );

  const handleClear = async () => {
    await resetReportChat(sessionIdRef.current).catch(() => {});
    sessionIdRef.current = crypto.randomUUID();
    setMessages([]);
    setError(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <Card sx={{ mt: 3, borderLeft: '3px solid #0382B7' }}>
      <CardContent>
        {/* Header: icon + title + ticker chip + clear button */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <SmartToyIcon sx={{ color: '#0382B7', fontSize: 22 }} />
            <Typography
              variant="h6"
              sx={{ fontFamily: '"DM Serif Display", Georgia, serif', fontWeight: 400 }}
            >
              Ask about this report
            </Typography>
            <Chip
              label={ticker}
              size="small"
              sx={{
                backgroundColor: 'rgba(3,130,183,0.08)',
                color: '#0382B7',
                fontWeight: 600,
                fontSize: '0.7rem',
              }}
            />
          </Box>
          {messages.length > 0 && (
            <Button
              size="small"
              startIcon={<DeleteOutlineOutlinedIcon />}
              onClick={handleClear}
              sx={{ color: '#6B6760', textTransform: 'none' }}
            >
              Clear chat
            </Button>
          )}
        </Box>

        <Typography variant="body2" sx={{ color: '#6B6760', mb: 1.5, fontSize: '0.8rem' }}>
          Ask follow-up questions about the generated report for {ticker}.
        </Typography>

        <Divider sx={{ mb: 2 }} />

        {/* Error alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Starter prompts when empty */}
        {messages.length === 0 && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            {STARTER_PROMPTS.map((prompt) => (
              <Chip
                key={prompt}
                label={prompt}
                size="small"
                onClick={() => sendMessage(prompt)}
                sx={{
                  cursor: 'pointer',
                  backgroundColor: 'rgba(3,130,183,0.06)',
                  color: '#0382B7',
                  border: '1px solid rgba(3,130,183,0.15)',
                  '&:hover': { backgroundColor: 'rgba(3,130,183,0.12)' },
                }}
              />
            ))}
          </Box>
        )}

        {/* Message list */}
        <Box sx={{ maxHeight: 420, overflowY: 'auto', mb: 2, pr: 0.5 }}>
          {messages.map((msg, i) => (
            <ChatMessage key={i} role={msg.role} content={msg.content} />
          ))}
          {loading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 5, mb: 1 }}>
              <CircularProgress size={14} sx={{ color: '#0382B7' }} />
              <Typography variant="body2" sx={{ color: '#6B6760', fontSize: '0.8rem' }}>
                Thinking...
              </Typography>
            </Box>
          )}
          <div ref={messagesEndRef} />
        </Box>

        {/* Input */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            fullWidth
            size="small"
            placeholder={`Ask about ${ticker}'s report...`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            multiline
            maxRows={3}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: '12px',
                fontSize: '0.875rem',
              },
            }}
          />
          <IconButton
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            sx={{
              bgcolor: '#0382B7',
              color: '#fff',
              '&:hover': { bgcolor: '#026a96' },
              '&.Mui-disabled': { bgcolor: '#E8E4DB', color: '#B0ADA6' },
              width: 38,
              height: 38,
            }}
          >
            <SendIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>
      </CardContent>
    </Card>
  );
}
