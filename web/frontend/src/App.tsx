import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import {
  Alert,
  AppBar,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  FormControlLabel,
  FormControl,
  FormLabel,
  InputLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  CircularProgress,
  MenuItem,
  Paper,
  LinearProgress,
  Select,
  Slider,
  Stack,
  Radio,
  RadioGroup,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tab,
  Tabs,
  IconButton,
  TextField,
  Typography
} from '@mui/material'
import SettingsIcon from '@mui/icons-material/Settings'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import SaveIcon from '@mui/icons-material/Save'
import EastIcon from '@mui/icons-material/East'
import SouthIcon from '@mui/icons-material/South'
import MenuIcon from '@mui/icons-material/Menu'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap'
import FullscreenExitIcon from '@mui/icons-material/FullscreenExit'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import { API_BASE, RunDetail, RunEvent, RunSummary, apiDelete, apiGet, apiPost, apiPut } from './api'

type ModelOption = { label: string; value: string }
type OptionsResponse = { providers: string[]; models: Record<string, { quick: ModelOption[]; deep: ModelOption[] }> }
type AdminModel = { id: number; label: string; value: string }
type AdminCatalog = {
  providers: string[]
  models: Record<string, { quick: AdminModel[]; deep: AdminModel[] }>
  defaults: { provider: string; quick_model: string; deep_model: string }
}
type TickerItem = { symbol: string; name: string; exchange?: string; type?: string }
type TickerSearchResponse = { items: TickerItem[]; total: number; page: number; page_size: number }

const drawerWidth = 360
const sectionTitleMap: Record<string, string> = {
  market_report: 'Market Analysis',
  sentiment_report: 'Social Sentiment',
  news_report: 'News Analysis',
  fundamentals_report: 'Fundamentals Analysis',
  investment_plan: 'Research Team Decision',
  trader_investment_plan: 'Trading Team Plan',
  final_trade_decision: 'Portfolio Manager Decision'
}

const flowOrder = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Aggressive Analyst',
  'Conservative Analyst',
  'Neutral Analyst',
  'Portfolio Manager'
]

function MarkdownDoc({ content }: { content: string }) {
  return (
    <Box
      sx={{
        '& h1, & h2, & h3, & h4': { mt: 2, mb: 1, fontWeight: 800, lineHeight: 1.25 },
        '& p': { my: 0.9, lineHeight: 1.7 },
        '& ul, & ol': { my: 1, pl: 3 },
        '& li': { my: 0.4, lineHeight: 1.6 },
        '& blockquote': {
          borderLeft: '4px solid #90caf9',
          pl: 1.5,
          ml: 0,
          color: '#455a64',
          bgcolor: '#f8fbff',
          py: 0.5,
          borderRadius: '0 8px 8px 0'
        },
        '& hr': { border: 0, borderTop: '1px solid #dbe6f9', my: 2 },
        '& table': {
          width: '100%',
          borderCollapse: 'collapse',
          my: 1.5,
          display: 'block',
          overflowX: 'auto',
          whiteSpace: 'nowrap'
        },
        '& thead th': {
          bgcolor: '#eef4ff',
          fontWeight: 800
        },
        '& th, & td': {
          border: '1px solid #d6e2f7',
          px: 1,
          py: 0.8,
          textAlign: 'left'
        },
        '& code': {
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
          bgcolor: '#eef3fb',
          px: 0.5,
          py: 0.2,
          borderRadius: '6px',
          fontSize: '0.92em'
        },
        '& pre': {
          p: 1.2,
          borderRadius: '10px',
          bgcolor: '#0f172a',
          color: '#e2e8f0',
          overflowX: 'auto'
        },
        '& pre code': {
          bgcolor: 'transparent',
          p: 0,
          color: 'inherit'
        }
      }}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{content}</ReactMarkdown>
    </Box>
  )
}

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [options, setOptions] = useState<OptionsResponse | null>(null)
  const [provider, setProvider] = useState('openai')
  const [tickerQuery, setTickerQuery] = useState('삼성전자')
  const [ticker, setTicker] = useState('005930.KS')
  const [tickerCandidates, setTickerCandidates] = useState<TickerItem[]>([])
  const [tickerSearchLoading, setTickerSearchLoading] = useState(false)
  const [tickerTotal, setTickerTotal] = useState(0)
  const [tickerPage, setTickerPage] = useState(0)
  const [tickerPageSize, setTickerPageSize] = useState(50)
  const [tickerMarket, setTickerMarket] = useState<'KR' | 'US'>('KR')
  const [hasSearchedTicker, setHasSearchedTicker] = useState(false)
  const tickerSearchSeq = useRef(0)
  const [savedTickers, setSavedTickers] = useState<TickerItem[]>([
    { symbol: '005930.KS', name: 'Samsung Electronics' }
  ])
  const [analysisDate, setAnalysisDate] = useState(new Date().toISOString().slice(0, 10))
  const [researchDepth, setResearchDepth] = useState(1)
  const [quickModel, setQuickModel] = useState('gpt-5.4-mini')
  const [deepModel, setDeepModel] = useState('gpt-5.4')
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [checkedRunIds, setCheckedRunIds] = useState<string[]>([])
  const [agentStatuses, setAgentStatuses] = useState<Record<string, string>>({})
  const [reportContent, setReportContent] = useState('')
  const [selectedReportPath, setSelectedReportPath] = useState('complete_report.md')
  const [tab, setTab] = useState(0)
  const [contentZoomOpen, setContentZoomOpen] = useState(false)
  const [err, setErr] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [adminCatalog, setAdminCatalog] = useState<AdminCatalog | null>(null)
  const [adminProviderInput, setAdminProviderInput] = useState('')
  const [adminRenameInput, setAdminRenameInput] = useState('')
  const [modelMode, setModelMode] = useState<'quick' | 'deep'>('quick')
  const [modelLabelInput, setModelLabelInput] = useState('')
  const [modelValueInput, setModelValueInput] = useState('')
  const [editingModelId, setEditingModelId] = useState<number | null>(null)
  const [tickerSearchOpen, setTickerSearchOpen] = useState(false)
  const [selectedTickerMap, setSelectedTickerMap] = useState<Record<string, TickerItem>>({})
  const [progress, setProgress] = useState(0)

  const modelOptions = useMemo(() => options?.models?.[provider], [options, provider])

  useEffect(() => {
    document.title = '증권거래 길잡이'
  }, [])

  useEffect(() => {
    void loadOptions()
    void loadSavedTickers()
    refreshRuns()
  }, [])

  useEffect(() => {
    if (!modelOptions) return
    if (modelOptions.quick?.[0]) setQuickModel(modelOptions.quick[0].value)
    if (modelOptions.deep?.[0]) setDeepModel(modelOptions.deep[0].value)
  }, [modelOptions])

  useEffect(() => {
    if (!selectedRunId) return
    const qs = '?event_types=message,tool_call,agent_status,progress,status,report_section,meta'
    const es = new EventSource(`${API_BASE}/api/runs/${selectedRunId}/events/stream${qs}`)
    es.onmessage = async (evt) => {
      const data: RunEvent = JSON.parse(evt.data)
      setEvents((prev) => [...prev, data].slice(-300))
      if (data.event_type === 'agent_status') {
        setAgentStatuses(data.payload.statuses ?? {})
      }
      if (data.event_type === 'progress') {
        setProgress(Number(data.payload.value ?? 0))
      }
      if (data.event_type === 'status') {
        if (typeof data.payload.progress === 'number') setProgress(data.payload.progress)
        await loadRun(selectedRunId)
      }
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [selectedRunId])

  const refreshRuns = async () => {
    try {
      const nextRuns = await apiGet<RunSummary[]>('/api/runs')
      setRuns(nextRuns)
      const runIdSet = new Set(nextRuns.map((r) => r.run_id))
      setCheckedRunIds((prev) => prev.filter((id) => runIdSet.has(id)))
      if (selectedRunId && !runIdSet.has(selectedRunId)) {
        setSelectedRunId(null)
        setSelectedRun(null)
        setEvents([])
        setAgentStatuses({})
        setReportContent('')
        setProgress(0)
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  const loadOptions = async () => {
    try {
      const data = await apiGet<OptionsResponse & { defaults?: { provider?: string; quick_model?: string; deep_model?: string } }>('/api/options')
      setOptions(data)
      const defaultProvider = data.defaults?.provider && data.providers.includes(data.defaults.provider)
        ? data.defaults.provider
        : (data.providers.includes('openai') ? 'openai' : data.providers[0])
      setProvider(defaultProvider ?? '')
      const quickList = data.models[defaultProvider ?? '']?.quick ?? []
      const deepList = data.models[defaultProvider ?? '']?.deep ?? []
      setQuickModel(data.defaults?.quick_model && quickList.some((m) => m.value === data.defaults?.quick_model)
        ? data.defaults.quick_model
        : (quickList[0]?.value ?? ''))
      setDeepModel(data.defaults?.deep_model && deepList.some((m) => m.value === data.defaults?.deep_model)
        ? data.defaults.deep_model
        : (deepList[0]?.value ?? ''))
    } catch (e) {
      setErr(String(e))
    }
  }

  const loadAdminCatalog = async () => {
    try {
      const catalog = await apiGet<AdminCatalog>('/api/admin/model-catalog')
      setAdminCatalog(catalog)
      const p = catalog.defaults?.provider || catalog.providers[0] || ''
      if (p) {
        setProvider(p)
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  const loadSavedTickers = async () => {
    try {
      const items = await apiGet<TickerItem[]>('/api/saved-tickers')
      if (items.length > 0) {
        setSavedTickers(items)
        setTicker((prev) => (items.some((t) => t.symbol === prev) ? prev : items[0].symbol))
      } else {
        setSavedTickers([])
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  const searchTicker = async (queryOverride?: string, pageOverride?: number, pageSizeOverride?: number) => {
    let seq = 0
    try {
      const base = queryOverride ?? tickerQuery
      const q = (typeof base === 'string' ? base : String(base ?? '')).trim()
      if (!q) return
      const page = (pageOverride ?? tickerPage) + 1
      const pageSize = pageSizeOverride ?? tickerPageSize
      seq = ++tickerSearchSeq.current
      setTickerSearchLoading(true)
      const res = await apiGet<TickerSearchResponse>(
        `/api/tickers/search?q=${encodeURIComponent(q)}&market=${tickerMarket}&page=${page}&page_size=${pageSize}&max_results=5000`
      )
      // Only apply the latest in-flight request result.
      if (seq === tickerSearchSeq.current) {
        setTickerCandidates(res.items)
        setTickerTotal(res.total)
        setHasSearchedTicker(true)
      }
    } catch (e) {
      setErr(String(e))
    } finally {
      // Do not let slower/older requests clear the loading state for newer ones.
      if (seq === tickerSearchSeq.current) {
        setTickerSearchLoading(false)
      }
    }
  }

  const toggleTickerSelection = (item: TickerItem) => {
    setSelectedTickerMap((prev) => {
      const next = { ...prev }
      if (next[item.symbol]) {
        delete next[item.symbol]
      } else {
        next[item.symbol] = item
      }
      return next
    })
  }

  const saveSelectedTickers = async () => {
    const selectedItems = Object.values(selectedTickerMap)
    if (selectedItems.length === 0) return
    try {
      await apiPost('/api/saved-tickers', { items: selectedItems })
      await loadSavedTickers()
      setTicker(selectedItems[0].symbol)
      setTickerSearchOpen(false)
      setSelectedTickerMap({})
    } catch (e) {
      setErr(String(e))
    }
  }

  const openSettings = async () => {
    setSettingsOpen(true)
    await loadAdminCatalog()
  }

  const addProvider = async () => {
    if (!adminProviderInput.trim()) return
    await apiPost('/api/admin/providers', { name: adminProviderInput.trim() })
    setAdminProviderInput('')
    await loadAdminCatalog()
    await loadOptions()
  }

  const renameProvider = async () => {
    if (!provider || !adminRenameInput.trim()) return
    await apiPut(`/api/admin/providers/${encodeURIComponent(provider)}`, { new_name: adminRenameInput.trim() })
    setAdminRenameInput('')
    await loadAdminCatalog()
    await loadOptions()
  }

  const removeProvider = async () => {
    if (!provider) return
    await apiDelete(`/api/admin/providers/${encodeURIComponent(provider)}`)
    await loadAdminCatalog()
    await loadOptions()
  }

  const addOrUpdateModel = async () => {
    if (!provider || !modelLabelInput.trim() || !modelValueInput.trim()) return
    if (editingModelId) {
      await apiPut(`/api/admin/models/${editingModelId}`, {
        mode: modelMode,
        label: modelLabelInput.trim(),
        value: modelValueInput.trim(),
      })
    } else {
      await apiPost('/api/admin/models', {
        provider,
        mode: modelMode,
        label: modelLabelInput.trim(),
        value: modelValueInput.trim(),
      })
    }
    setEditingModelId(null)
    setModelLabelInput('')
    setModelValueInput('')
    await loadAdminCatalog()
    await loadOptions()
  }

  const startEditModel = (id: number, mode: 'quick' | 'deep', label: string, value: string) => {
    setEditingModelId(id)
    setModelMode(mode)
    setModelLabelInput(label)
    setModelValueInput(value)
  }

  const removeModel = async (id: number) => {
    await apiDelete(`/api/admin/models/${id}`)
    if (editingModelId === id) {
      setEditingModelId(null)
      setModelLabelInput('')
      setModelValueInput('')
    }
    await loadAdminCatalog()
    await loadOptions()
  }

  const saveDefaults = async () => {
    await apiPost('/api/admin/model-defaults', {
      provider,
      quick_model: quickModel,
      deep_model: deepModel
    })
    await loadOptions()
  }

  useEffect(() => {
    if (!tickerSearchOpen || !hasSearchedTicker) return
    void searchTicker(tickerQuery, tickerPage, tickerPageSize)
  }, [tickerPage, tickerPageSize])

  const startRun = async () => {
    try {
      const run = await apiPost<RunSummary>('/api/runs', {
        ticker,
        analysis_date: analysisDate,
        analysts: ['market', 'social', 'news', 'fundamentals'],
        research_depth: researchDepth,
        llm_provider: provider,
        shallow_thinker: quickModel,
        deep_thinker: deepModel,
        checkpoint: true,
        output_language: 'Korean'
      })
      setSelectedRunId(run.run_id)
      setEvents([])
      setAgentStatuses({})
      await refreshRuns()
      await loadRun(run.run_id)
    } catch (e) {
      setErr(String(e))
    }
  }

  const loadRun = async (runId: string) => {
    const run = await apiGet<RunDetail>(`/api/runs/${runId}`)
    setSelectedRun(run)
    setSelectedRunId(runId)
    setProgress(run.progress ?? 0)
    if (run.report_files.length > 0 && run.status === 'completed') {
      const path = run.report_files.includes(selectedReportPath) ? selectedReportPath : run.report_files[0]
      setSelectedReportPath(path)
      await loadReport(runId, path)
    }
  }

  const loadReport = async (runId: string, path: string) => {
    const data = await apiGet<{ path: string; content: string }>(`/api/runs/${runId}/report/${encodeURIComponent(path)}`)
    setReportContent(data.content)
  }

  const messages = events.filter((e) => e.event_type === 'message').slice().reverse()
  const toolCalls = events.filter((e) => e.event_type === 'tool_call').slice().reverse()
  const reportTimeline = events.filter((e) => e.event_type === 'report_section').slice().reverse()
  const requestCancel = async () => {
    if (!selectedRunId) return
    try {
      setSelectedRun((prev) => (
        prev ? { ...prev, cancel_requested: true, status: prev.status === 'queued' ? 'cancelled' : prev.status } : prev
      ))
      const updated = await apiPost<RunDetail>(`/api/runs/${selectedRunId}/cancel`, {})
      setSelectedRun(updated)
      setProgress(updated.progress ?? progress)
      await refreshRuns()
    } catch (e) {
      setErr(`실행 취소에 실패했습니다: ${String(e)}`)
    }
  }

  const toggleRunChecked = (runId: string) => {
    setCheckedRunIds((prev) => (prev.includes(runId) ? prev.filter((id) => id !== runId) : [...prev, runId]))
  }

  const deleteCheckedRuns = async () => {
    if (checkedRunIds.length === 0) return
    try {
      const failures: string[] = []
      for (const runId of checkedRunIds) {
        try {
          await apiDelete(`/api/runs/${runId}`)
        } catch {
          failures.push(runId)
        }
      }
      await refreshRuns()
      setCheckedRunIds(failures)
      if (failures.length > 0) {
        setErr(`일부 항목은 삭제하지 못했습니다: ${failures.join(', ')}`)
      }
    } catch (e) {
      setErr(String(e))
    }
  }

  const nodeStyleByStatus = (status: string) => {
    if (status === 'completed') {
      return { bg: '#2e7d32', color: '#fff', border: '#2e7d32' }
    }
    if (status === 'in_progress') {
      return { bg: '#ef6c00', color: '#fff', border: '#ef6c00' }
    }
    if (status === 'failed') {
      return { bg: '#c62828', color: '#fff', border: '#c62828' }
    }
    return { bg: '#eceff1', color: '#455a64', border: '#cfd8dc' }
  }

  const FlowNode = ({ label }: { label: string }) => {
    const status = agentStatuses[label] ?? 'pending'
    const st = nodeStyleByStatus(status)
    return (
      <Box
        sx={{
          px: 1.2,
          py: 0.95,
          borderRadius: '8px',
          border: `2px solid ${st.border}`,
          bgcolor: st.bg,
          color: st.color,
          fontSize: 14,
          fontWeight: 800,
          whiteSpace: 'normal',
          wordBreak: 'keep-all',
          lineHeight: 1.25,
          textAlign: 'center'
        }}
      >
        {label} · {status}
      </Box>
    )
  }

  const FlowArrow = ({ vertical = false }: { vertical?: boolean }) => (
    <Box
      sx={{
        width: vertical ? '100%' : 36,
        minHeight: vertical ? 34 : undefined,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        color: '#2f528f',
      }}
    >
      {vertical ? <SouthIcon sx={{ fontSize: 50, fontWeight: 900 }} /> : <EastIcon sx={{ fontSize: 46, fontWeight: 900 }} />}
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', width: '100%' }}>
      <Drawer
        variant="persistent"
        open={sidebarOpen}
        sx={{
          width: sidebarOpen ? drawerWidth : 0,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: 'border-box',
            p: 2
          }
        }}
      >
        <Paper sx={{ p: 1.2, mb: 2, background: '#f5f9ff', color: '#1f6fff', border: '1px solid #d6e6ff' }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <TrendingUpIcon sx={{ fontSize: 22 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
              빠른 실행 패널
            </Typography>
          </Stack>
        </Paper>
        <Stack spacing={1.5}>
          <Button variant="outlined" onClick={() => setTickerSearchOpen(true)}>증권코드 검색 팝업</Button>
          <FormControl size="small">
            <InputLabel>저장된 증권코드</InputLabel>
            <Select label="저장된 증권코드" value={ticker} onChange={(e) => setTicker(e.target.value)}>
              {savedTickers.map((s) => (
                <MenuItem key={s.symbol} value={s.symbol}>
                  {s.symbol} {s.name ? `- ${s.name}` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField label="선택된 증권코드" value={ticker} onChange={(e) => setTicker(e.target.value)} size="small" />
          <TextField label="분석일" type="date" value={analysisDate} onChange={(e) => setAnalysisDate(e.target.value)} size="small" InputLabelProps={{ shrink: true }} />

          <Typography variant="body2">Research Depth: {researchDepth}</Typography>
          <Slider value={researchDepth} min={1} max={5} step={1} marks onChange={(_, v) => setResearchDepth(v as number)} />

          <Button variant="contained" size="large" onClick={startRun}>분석 시작</Button>
          <Button variant="text" onClick={refreshRuns}>실행 목록 새로고침</Button>
          <Divider />
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
            수행 결과 목록
          </Typography>
          <List dense sx={{ maxHeight: 260, overflow: 'auto', border: '1px solid #dce6f8', borderRadius: 2 }}>
            {runs.map((r) => (
              <ListItem
                key={r.run_id}
                disablePadding
                secondaryAction={
                  <Checkbox
                    edge="end"
                    checked={checkedRunIds.includes(r.run_id)}
                    onChange={() => toggleRunChecked(r.run_id)}
                    inputProps={{ 'aria-label': `${r.run_id} 선택` }}
                  />
                }
              >
                <ListItemButton selected={selectedRunId === r.run_id} onClick={() => loadRun(r.run_id)}>
                  <ListItemText
                    primary={`${r.ticker} (${r.status})`}
                    secondary={`${r.analysis_date} · ${r.run_id}`}
                  />
                </ListItemButton>
              </ListItem>
            ))}
            {runs.length === 0 && (
              <ListItem>
                <ListItemText primary="저장된 실행 결과가 없습니다." />
              </ListItem>
            )}
          </List>
          <Button
            variant="outlined"
            color="error"
            disabled={checkedRunIds.length === 0}
            onClick={deleteCheckedRuns}
          >
            선택 삭제 ({checkedRunIds.length})
          </Button>
        </Stack>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 2, background: 'radial-gradient(circle at 0% 0%, #e9f1ff, #f7fbff 60%)' }}>
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            mb: 1.5,
            px: 2,
            py: 1.2,
            borderRadius: '12px',
            border: '1px solid #d4e4ff',
            bgcolor: 'rgba(255,255,255,0.92)',
            color: '#1e3a5f',
            backdropFilter: 'blur(4px)'
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <IconButton
                onClick={() => setSidebarOpen((prev) => !prev)}
                sx={{
                  width: 38,
                  height: 38,
                  border: '1px solid #76a8ff',
                  bgcolor: '#f0f6ff',
                  color: '#1f6fff',
                  '&:hover': { bgcolor: '#e6f0ff' },
                  mr: 0.5
                }}
              >
                {sidebarOpen ? <ChevronLeftIcon /> : <MenuIcon />}
              </IconButton>
              <TrendingUpIcon sx={{ fontSize: 24, color: '#1f6fff' }} />
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 900, lineHeight: 1.2 }}>
                  증권거래 길잡이
                </Typography>
                <Typography variant="caption" sx={{ color: '#4e6b8f' }}>
                  AI 기반 투자 분석 컨트롤 패널
                </Typography>
              </Box>
            </Stack>
            <Button
              variant="outlined"
              startIcon={<SettingsIcon />}
              onClick={openSettings}
            >
              관리자 설정
            </Button>
          </Box>
        </AppBar>
        {err && <Alert severity="error" sx={{ mb: 2 }}>{err}</Alert>}

        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">Agent Status</Typography>
          <Divider sx={{ my: 1 }} />
          <Typography variant="h6" sx={{ mb: 1.2, fontWeight: 900 }}>Execution Flow</Typography>
          <Box sx={{ mb: 2, p: 2, border: '2px solid #b8cff4', borderRadius: 2, bgcolor: '#fbfdff' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'nowrap', width: '100%' }}>
              <Box sx={{ width: '22%', minWidth: 200, display: 'flex', flexDirection: 'column' }}>
                <Typography
                  variant="subtitle1"
                  sx={{
                    color: '#23395d',
                    fontWeight: 900,
                    minHeight: 40,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 0.8
                  }}
                >
                  Analyst Team (Parallel)
                </Typography>
                <Stack spacing={0.8}>
                  <FlowNode label="Market Analyst" />
                  <FlowNode label="Social Analyst" />
                  <FlowNode label="News Analyst" />
                  <FlowNode label="Fundamentals Analyst" />
                </Stack>
              </Box>

              <FlowArrow />

              <Box sx={{ width: '30%', minWidth: 320, display: 'flex', flexDirection: 'column' }}>
                <Typography
                  variant="subtitle1"
                  sx={{
                    color: '#23395d',
                    fontWeight: 900,
                    minHeight: 40,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 0.8
                  }}
                >
                  Research Team
                </Typography>
                <Stack spacing={0.8} sx={{ alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', gap: 0.8, flexWrap: 'wrap', justifyContent: 'center' }}>
                    <FlowNode label="Bull Researcher" />
                    <FlowNode label="Bear Researcher" />
                  </Box>
                  <FlowArrow vertical />
                  <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
                    <FlowNode label="Research Manager" />
                  </Box>
                </Stack>
              </Box>

              <FlowArrow />
              <Box sx={{ width: '12%', minWidth: 140, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FlowNode label="Trader" />
              </Box>

              <FlowArrow />

              <Box sx={{ width: '22%', minWidth: 200, display: 'flex', flexDirection: 'column' }}>
                <Typography
                  variant="subtitle1"
                  sx={{
                    color: '#23395d',
                    fontWeight: 900,
                    minHeight: 40,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 0.8
                  }}
                >
                  Risk Team (Parallel)
                </Typography>
                <Stack spacing={0.8}>
                  <FlowNode label="Aggressive Analyst" />
                  <FlowNode label="Conservative Analyst" />
                  <FlowNode label="Neutral Analyst" />
                </Stack>
              </Box>

              <FlowArrow />
              <Box sx={{ width: '14%', minWidth: 170, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FlowNode label="Portfolio Manager" />
              </Box>
            </Box>
          </Box>
          <Typography variant="body2" mb={1}>Progress: {progress}%</Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          {selectedRun && <Typography variant="body2" mt={1}>Current Run: {selectedRun.run_id} / {selectedRun.status}{selectedRun.cancel_requested ? ' (cancel requested)' : ''}</Typography>}
          {selectedRun?.error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {selectedRun.error}
            </Alert>
          )}
          <Stack direction="row" spacing={1} mt={1}>
            <Button
              variant="outlined"
              color="error"
              onClick={requestCancel}
              disabled={
                !selectedRun
                || !['queued', 'running'].includes(selectedRun.status)
                || !!selectedRun.cancel_requested
              }
            >
              실행 취소
            </Button>
          </Stack>
        </Paper>

        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            <IconButton
              onClick={() => setContentZoomOpen(true)}
              disabled={tab !== 0 && tab !== 3}
              sx={{
                width: 36,
                height: 36,
                border: '1px solid #76a8ff',
                bgcolor: '#f0f6ff',
                color: '#1f6fff',
                '&:hover': { bgcolor: '#e6f0ff' }
              }}
            >
              <ZoomOutMapIcon fontSize="small" />
            </IconButton>
          </Box>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label="Messages" />
            <Tab label="Tool Calls" />
            <Tab label="Report Timeline" />
            <Tab label="Report" />
          </Tabs>
          <Divider sx={{ mb: 2 }} />

          {tab === 0 && (
            <Stack spacing={1} sx={{ maxHeight: 420, overflow: 'auto' }}>
              {messages.map((m) => (
                <Paper key={m.id} variant="outlined" sx={{ p: 1.2, borderRadius: '15px', borderColor: '#d8e6ff', background: '#f8fbff' }}>
                  <Typography variant="caption" color="text.secondary">{m.ts} / {m.payload.type}</Typography>
                  <MarkdownDoc content={String(m.payload.content ?? '')} />
                </Paper>
              ))}
            </Stack>
          )}

          {tab === 1 && (
            <Stack spacing={1} sx={{ maxHeight: 420, overflow: 'auto' }}>
              {toolCalls.map((t) => (
                <Paper key={t.id} variant="outlined" sx={{ p: 1 }}>
                  <Typography variant="caption" color="text.secondary">{t.ts}</Typography>
                  <Typography variant="body2" fontWeight={700}>{String(t.payload.name ?? '')}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{JSON.stringify(t.payload.args ?? {}, null, 2)}</Typography>
                </Paper>
              ))}
            </Stack>
          )}

          {tab === 2 && (
            <Stack spacing={1} sx={{ maxHeight: 420, overflow: 'auto' }}>
              {reportTimeline.map((r) => (
                <Paper key={r.id} variant="outlined" sx={{ p: 1.2, borderRadius: '15px', borderColor: '#d8e6ff', background: '#f8fbff' }}>
                  <Typography variant="caption" color="text.secondary">{r.ts}</Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {sectionTitleMap[String(r.payload.section ?? '')] ?? String(r.payload.section ?? 'Report Section')}
                  </Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {String(r.payload.content ?? '').slice(0, 800)}
                    {String(r.payload.content ?? '').length > 800 ? '\n...' : ''}
                  </Typography>
                </Paper>
              ))}
              {reportTimeline.length === 0 && (
                <Typography variant="body2" color="text.secondary">리포트 섹션 이벤트가 아직 없습니다.</Typography>
              )}
            </Stack>
          )}

          {tab === 3 && (
            <Box>
              {selectedRun?.report_files?.length ? (
                <>
                  <FormControl size="small" sx={{ minWidth: 320, mb: 2 }}>
                    <InputLabel>Report File</InputLabel>
                    <Select
                      label="Report File"
                      value={selectedReportPath}
                      onChange={async (e) => {
                        const path = e.target.value
                        setSelectedReportPath(path)
                        if (selectedRunId) await loadReport(selectedRunId, path)
                      }}
                    >
                      {selectedRun.report_files.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
                    </Select>
                  </FormControl>
                  <Paper variant="outlined" sx={{ p: 2, maxHeight: 480, overflow: 'auto' }}>
                    <MarkdownDoc content={reportContent || '리포트 로딩 중...'} />
                  </Paper>
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">완료된 리포트가 아직 없습니다.</Typography>
              )}
            </Box>
          )}
        </Paper>
      </Box>

      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>관리자 설정</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl size="small">
              <InputLabel>Provider</InputLabel>
              <Select label="Provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
                {options?.providers.map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
              </Select>
            </FormControl>

            <FormControl size="small">
              <InputLabel>Quick Model</InputLabel>
              <Select label="Quick Model" value={quickModel} onChange={(e) => setQuickModel(e.target.value)}>
                {modelOptions?.quick.map((m) => <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>)}
              </Select>
            </FormControl>

            <FormControl size="small">
              <InputLabel>Deep Model</InputLabel>
              <Select label="Deep Model" value={deepModel} onChange={(e) => setDeepModel(e.target.value)}>
                {modelOptions?.deep.map((m) => <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>)}
              </Select>
            </FormControl>
            <Button variant="contained" startIcon={<SaveIcon />} onClick={saveDefaults}>
              기본값 저장
            </Button>

            <Divider />
            <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>Provider 관리</Typography>
            <Stack direction="row" spacing={1}>
              <TextField size="small" label="새 Provider" value={adminProviderInput} onChange={(e) => setAdminProviderInput(e.target.value)} fullWidth />
              <Button variant="outlined" onClick={addProvider}>등록</Button>
            </Stack>
            <Stack direction="row" spacing={1}>
              <TextField size="small" label="선택 Provider 이름 변경" value={adminRenameInput} onChange={(e) => setAdminRenameInput(e.target.value)} fullWidth />
              <Button variant="outlined" startIcon={<EditIcon />} onClick={renameProvider}>수정</Button>
              <Button variant="outlined" color="error" startIcon={<DeleteIcon />} onClick={removeProvider}>삭제</Button>
            </Stack>

            <Divider />
            <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>Model 관리</Typography>
            <Stack direction="row" spacing={1}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Mode</InputLabel>
                <Select label="Mode" value={modelMode} onChange={(e) => setModelMode(e.target.value as 'quick' | 'deep')}>
                  <MenuItem value="quick">quick</MenuItem>
                  <MenuItem value="deep">deep</MenuItem>
                </Select>
              </FormControl>
              <TextField size="small" label="Label" value={modelLabelInput} onChange={(e) => setModelLabelInput(e.target.value)} fullWidth />
              <TextField size="small" label="Value" value={modelValueInput} onChange={(e) => setModelValueInput(e.target.value)} fullWidth />
              <Button variant="contained" onClick={addOrUpdateModel}>{editingModelId ? '수정 저장' : '등록'}</Button>
            </Stack>

            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 220 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Mode</TableCell>
                    <TableCell>Label</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell align="right">작업</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(['quick', 'deep'] as const).flatMap((mode) => (adminCatalog?.models?.[provider]?.[mode] ?? []).map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>{mode}</TableCell>
                      <TableCell>{m.label}</TableCell>
                      <TableCell>{m.value}</TableCell>
                      <TableCell align="right">
                        <IconButton size="small" onClick={() => startEditModel(m.id, mode, m.label, m.value)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" color="error" onClick={() => removeModel(m.id)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  )))}
                  {(!adminCatalog?.models?.[provider]?.quick?.length && !adminCatalog?.models?.[provider]?.deep?.length) && (
                    <TableRow>
                      <TableCell colSpan={4}>등록된 모델이 없습니다.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsOpen(false)}>닫기</Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={tickerSearchOpen}
        onClose={() => {
          setTickerSearchOpen(false)
          setSelectedTickerMap({})
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>증권코드 검색</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <FormControl>
              <FormLabel>시장</FormLabel>
              <RadioGroup
                row
                value={tickerMarket}
                onChange={(e) => {
                  setTickerMarket(e.target.value as 'KR' | 'US')
                  setTickerPage(0)
                  setTickerCandidates([])
                  setTickerTotal(0)
                  setHasSearchedTicker(false)
                  setSelectedTickerMap({})
                }}
              >
                <FormControlLabel value="KR" control={<Radio />} label="국내" />
                <FormControlLabel value="US" control={<Radio />} label="미국" />
              </RadioGroup>
            </FormControl>
            <TextField
              label="회사명/검색어"
              value={tickerQuery}
              onChange={(e) => setTickerQuery(e.target.value)}
              size="small"
              helperText="입력 후 검색 버튼을 눌러주세요."
            />
            <Button
              variant="contained"
              onClick={() => {
                setTickerPage(0)
                void searchTicker(tickerQuery, 0, tickerPageSize)
              }}
              disabled={tickerSearchLoading}
            >
              {tickerSearchLoading ? '검색 중...' : '검색'}
            </Button>
            <Typography variant="body2" color="text.secondary">검색 결과: {tickerTotal.toLocaleString()}건</Typography>

            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 320 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>종목코드</TableCell>
                    <TableCell>회사명</TableCell>
                    <TableCell>시장</TableCell>
                    <TableCell align="right">
                      <Checkbox
                        size="small"
                        checked={tickerCandidates.length > 0 && tickerCandidates.every((c) => !!selectedTickerMap[c.symbol])}
                        indeterminate={tickerCandidates.some((c) => !!selectedTickerMap[c.symbol]) && !tickerCandidates.every((c) => !!selectedTickerMap[c.symbol])}
                        onChange={(e) => {
                          const checked = e.target.checked
                          setSelectedTickerMap((prev) => {
                            const next = { ...prev }
                            for (const c of tickerCandidates) {
                              if (checked) next[c.symbol] = c
                              else delete next[c.symbol]
                            }
                            return next
                          })
                        }}
                      />
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tickerSearchLoading && (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <CircularProgress size={16} />
                          <Typography variant="body2">검색 중...</Typography>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  )}
                  {!tickerSearchLoading && tickerCandidates.map((c) => (
                    <TableRow key={`${c.symbol}-${c.exchange}`} hover>
                      <TableCell>{c.symbol}</TableCell>
                      <TableCell>{c.name}</TableCell>
                      <TableCell>{c.exchange ?? '-'}</TableCell>
                      <TableCell align="right">
                        <Checkbox
                          checked={!!selectedTickerMap[c.symbol]}
                          onChange={() => toggleTickerSelection(c)}
                          inputProps={{ 'aria-label': `${c.symbol} 선택` }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {!tickerSearchLoading && tickerCandidates.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Typography variant="body2" color="text.secondary">
                          검색 결과가 없습니다.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={tickerTotal}
              page={tickerPage}
              onPageChange={(_, p) => setTickerPage(p)}
              rowsPerPage={tickerPageSize}
              onRowsPerPageChange={(e) => {
                const v = Number(e.target.value)
                setTickerPageSize(v)
                setTickerPage(0)
              }}
              rowsPerPageOptions={[20, 50, 100, 200]}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            variant="contained"
            disabled={Object.keys(selectedTickerMap).length === 0}
            onClick={saveSelectedTickers}
          >
            저장 ({Object.keys(selectedTickerMap).length})
          </Button>
          <Button onClick={() => {
            setTickerSearchOpen(false)
            setSelectedTickerMap({})
          }}
          >
            닫기
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={contentZoomOpen} onClose={() => setContentZoomOpen(false)} fullScreen>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {tab === 0 ? 'Messages 확대 보기' : 'Report 확대 보기'}
          <IconButton
            onClick={() => setContentZoomOpen(false)}
            sx={{
              width: 36,
              height: 36,
              border: '1px solid #76a8ff',
              bgcolor: '#f0f6ff',
              color: '#1f6fff',
              '&:hover': { bgcolor: '#e6f0ff' }
            }}
          >
            <FullscreenExitIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          {tab === 0 && (
            <Stack spacing={1} sx={{ maxHeight: 'calc(100vh - 140px)', overflow: 'auto' }}>
              {messages.map((m) => (
                <Paper key={`zoom-${m.id}`} variant="outlined" sx={{ p: 1.2, borderRadius: '15px', borderColor: '#d8e6ff', background: '#f8fbff' }}>
                  <Typography variant="caption" color="text.secondary">{m.ts} / {m.payload.type}</Typography>
                  <MarkdownDoc content={String(m.payload.content ?? '')} />
                </Paper>
              ))}
            </Stack>
          )}
          {tab === 3 && (
            <Paper variant="outlined" sx={{ p: 2, maxHeight: 'calc(100vh - 140px)', overflow: 'auto' }}>
              <MarkdownDoc content={reportContent || '리포트 로딩 중...'} />
            </Paper>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setContentZoomOpen(false)}>닫기</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
