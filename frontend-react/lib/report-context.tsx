'use client';

import React, { createContext, useContext, useState, useRef, useCallback, ReactNode } from 'react';
import { generateQuickReport, startCAVMPipeline, getCAVMStatus, fetchReportHistory } from './api';

type ReportType = 'quick' | 'cavm-summary' | 'cavm';

export interface ExistingReport {
  folder_name: string;
  pdf_filename: string;
  run_at: string | null;
  elapsed_seconds: number | null;
  detail_level: 'summary' | 'full';
  pdf_path: string;
}

interface CAVMState {
  taskId: string | null;
  stage: number;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
  ticker: string | null;
  messages: string[];
}

interface ReportContextType {
  reportType: ReportType;
  setReportType: (t: ReportType) => void;
  // Quick report
  quickLoading: boolean;
  quickResult: string | null;
  quickError: string | null;
  quickTicker: string | null;
  startQuickReport: (ticker: string) => void;
  // CAVM pipeline
  cavm: CAVMState;
  debugMode: boolean;
  setDebugMode: (v: boolean) => void;
  skipCharts: boolean;
  setSkipCharts: (v: boolean) => void;
  startCAVM: (ticker: string, reportType: ReportType) => void;
  // Existing reports
  existingReports: ExistingReport[];
  existingReportsLoading: boolean;
  loadReportHistory: (ticker: string) => void;
}

const CAVM_INITIAL: CAVMState = {
  taskId: null,
  stage: 0,
  status: 'idle',
  result: null,
  error: null,
  ticker: null,
  messages: [],
};

const ReportContext = createContext<ReportContextType>({
  reportType: 'quick',
  setReportType: () => {},
  quickLoading: false,
  quickResult: null,
  quickError: null,
  quickTicker: null,
  startQuickReport: () => {},
  cavm: CAVM_INITIAL,
  debugMode: false,
  setDebugMode: () => {},
  skipCharts: false,
  setSkipCharts: () => {},
  startCAVM: () => {},
  existingReports: [],
  existingReportsLoading: false,
  loadReportHistory: () => {},
});

export function ReportProvider({ children }: { children: ReactNode }) {
  const [reportType, setReportType] = useState<ReportType>('quick');

  // Quick report state
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickResult, setQuickResult] = useState<string | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);
  const [quickTicker, setQuickTicker] = useState<string | null>(null);

  // CAVM state
  const [cavm, setCavm] = useState<CAVMState>(CAVM_INITIAL);
  const [debugMode, setDebugMode] = useState(false);
  const [skipCharts, setSkipCharts] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Existing reports state
  const [existingReports, setExistingReports] = useState<ExistingReport[]>([]);
  const [existingReportsLoading, setExistingReportsLoading] = useState(false);
  const latestTickerRef = useRef<string | null>(null);

  const loadReportHistory = useCallback((ticker: string) => {
    latestTickerRef.current = ticker;
    setExistingReportsLoading(true);
    setExistingReports([]);
    fetchReportHistory(ticker)
      .then((data: ExistingReport[]) => {
        if (latestTickerRef.current === ticker) {
          setExistingReports(data);
        }
      })
      .catch(() => {
        if (latestTickerRef.current === ticker) {
          setExistingReports([]);
        }
      })
      .finally(() => {
        if (latestTickerRef.current === ticker) {
          setExistingReportsLoading(false);
        }
      });
  }, []);

  const startQuickReport = useCallback((ticker: string) => {
    setQuickLoading(true);
    setQuickResult(null);
    setQuickError(null);
    setQuickTicker(ticker);
    generateQuickReport(ticker)
      .then((data) => {
        if (data.error) setQuickError(data.error);
        else setQuickResult(data.result);
      })
      .catch((e: Error) => setQuickError(e.message))
      .finally(() => setQuickLoading(false));
  }, []);

  const startCAVM = useCallback((ticker: string, rt: ReportType) => {
    // Clear any existing polling
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    const detailLevel = rt === 'cavm-summary' ? 'summary' : 'detailed';
    setCavm({ taskId: null, stage: 0, status: 'starting', result: null, error: null, ticker, messages: [] });

    startCAVMPipeline(ticker, debugMode, skipCharts, detailLevel)
      .then((data) => {
        if (data.task_id) {
          setCavm((prev) => ({ ...prev, taskId: data.task_id, status: 'running' }));
          pollingRef.current = setInterval(() => {
            getCAVMStatus(data.task_id)
              .then((status) => {
                setCavm((prev) => ({
                  ...prev,
                  stage: status.stage || prev.stage,
                  status: status.status,
                  messages: Array.isArray(status.messages) ? status.messages : prev.messages,
                }));
                if (status.status === 'completed') {
                  setCavm((prev) => ({ ...prev, result: status.result }));
                  if (pollingRef.current) clearInterval(pollingRef.current);
                  pollingRef.current = null;
                } else if (status.status === 'failed') {
                  setCavm((prev) => ({ ...prev, error: status.error }));
                  if (pollingRef.current) clearInterval(pollingRef.current);
                  pollingRef.current = null;
                }
              })
              .catch(() => {});
          }, 5000);
        }
      })
      .catch((e: Error) => {
        setCavm((prev) => ({ ...prev, status: 'failed', error: e.message }));
      });
  }, [debugMode, skipCharts]);

  return (
    <ReportContext.Provider
      value={{
        reportType,
        setReportType,
        quickLoading,
        quickResult,
        quickError,
        quickTicker,
        startQuickReport,
        cavm,
        debugMode,
        setDebugMode,
        skipCharts,
        setSkipCharts,
        startCAVM,
        existingReports,
        existingReportsLoading,
        loadReportHistory,
      }}
    >
      {children}
    </ReportContext.Provider>
  );
}

export function useReport() {
  return useContext(ReportContext);
}
