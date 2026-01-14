import { useState, useEffect, useCallback } from 'react'
import { cn } from '../lib/utils'

interface UpdateLogEntry {
  timestamp: string
  mode?: string
  updates: Record<string, {
    status: string
    old_count?: number
    total_count?: number
    new_count?: number
    new_features?: Array<{ title: string; time: string }>
    error?: string
  }>
}

interface RunStatus {
  lastRun: string | null
  isRunning: boolean
}

function AdminPage() {
  // 认证状态
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authToken, setAuthToken] = useState<string | null>(null)
  
  // Changelog 编辑
  const [changelog, setChangelog] = useState('')
  const [changelogLoading, setChangelogLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  
  // 运行状态
  const [logs, setLogs] = useState<UpdateLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(true)
  const [crawlStatus, setCrawlStatus] = useState<RunStatus>({ lastRun: null, isRunning: false })
  const [summaryStatus, setSummaryStatus] = useState<RunStatus>({ lastRun: null, isRunning: false })

  // 检查已保存的 session
  useEffect(() => {
    const savedToken = localStorage.getItem('admin_token')
    if (savedToken) {
      setAuthToken(savedToken)
      setIsAuthenticated(true)
    }
  }, [])

  // 登录后加载数据
  useEffect(() => {
    if (isAuthenticated && authToken) {
      loadChangelog()
      loadLogs()
      loadRunStatus()
    }
  }, [isAuthenticated, authToken])

  const handleLogin = async () => {
    setAuthError('')
    
    try {
      const response = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      })
      
      if (response.ok) {
        const data = await response.json()
        setAuthToken(data.token)
        localStorage.setItem('admin_token', data.token)
        setIsAuthenticated(true)
        setPassword('')
      } else {
        const error = await response.json()
        setAuthError(error.error || '登录失败')
      }
    } catch {
      setAuthError('无法连接到后端服务。请确保 API 服务器正在运行：python3 script/api_server.py')
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    setAuthToken(null)
    setIsAuthenticated(false)
    setChangelog('')
    setLogs([])
  }

  const loadChangelog = useCallback(async () => {
    if (!authToken) return
    
    setChangelogLoading(true)
    try {
      const response = await fetch('/api/admin/changelog', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setChangelog(data.content || '')
      } else if (response.status === 401) {
        handleLogout()
      }
    } catch {
      console.warn('Failed to load changelog')
    } finally {
      setChangelogLoading(false)
    }
  }, [authToken])

  const saveChangelog = async () => {
    if (!authToken) return
    
    setSaving(true)
    setSaveMessage('')
    
    try {
      const response = await fetch('/api/admin/changelog', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ content: changelog })
      })
      
      if (response.ok) {
        setSaveMessage('已保存！正在解析和打标...')
        setTimeout(() => setSaveMessage(''), 5000)
      } else if (response.status === 401) {
        handleLogout()
      } else {
        setSaveMessage('保存失败')
      }
    } catch {
      setSaveMessage('保存失败：无法连接到后端服务')
    } finally {
      setSaving(false)
    }
  }

  const loadRunStatus = async () => {
    try {
      // 先尝试从 API 获取实时状态
      const apiResponse = await fetch('/api/status')
      if (apiResponse.ok) {
        const data = await apiResponse.json()
        setCrawlStatus({
          lastRun: data.crawl_last_run || null,
          isRunning: data.crawl_running || false
        })
        setSummaryStatus({
          lastRun: data.summary_last_run || null,
          isRunning: data.summary_running || false
        })
        
        // 如果有任务正在运行，开始轮询
        if (data.crawl_running) {
          pollTaskStatus('crawl')
        }
        if (data.summary_running) {
          pollTaskStatus('summary')
        }
        return
      }
    } catch {
      // API 不可用，尝试从静态文件获取
    }
    
    try {
      const response = await fetch('/data/info/run_status.json')
      if (response.ok) {
        const data = await response.json()
        setCrawlStatus({
          lastRun: data.crawl_last_run || null,
          isRunning: false
        })
        setSummaryStatus({
          lastRun: data.summary_last_run || null,
          isRunning: false
        })
      }
    } catch {
      // 没有状态文件，使用默认值
    }
  }

  const loadLogs = async () => {
    setLogsLoading(true)

    try {
      let response: Response
      try {
        response = await fetch('/data/logs/index.json')
      } catch {
        setLogs([])
        setLogsLoading(false)
        return
      }

      if (!response.ok) {
        setLogs([])
        setLogsLoading(false)
        return
      }

      const indexData = await response.json()
      const logFiles: string[] = indexData.files || []

      const hundredDaysAgo = new Date()
      hundredDaysAgo.setDate(hundredDaysAgo.getDate() - 100)

      const logPromises = logFiles.map(async (filename: string) => {
        try {
          const logResponse = await fetch(`/data/logs/${filename}`)
          if (!logResponse.ok) return null
          return await logResponse.json() as UpdateLogEntry
        } catch {
          return null
        }
      })

      const loadedLogs = (await Promise.all(logPromises))
        .filter((log): log is UpdateLogEntry => log !== null)
        .filter(log => {
          const logDate = new Date(log.timestamp)
          return logDate >= hundredDaysAgo
        })
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

      setLogs(loadedLogs)
    } catch (err) {
      console.warn('Failed to load logs:', err)
      setLogs([])
    } finally {
      setLogsLoading(false)
    }
  }

  // 轮询检查任务状态
  const pollTaskStatus = async (taskType: 'crawl' | 'summary') => {
    const checkStatus = async () => {
      try {
        const response = await fetch('/api/status')
        if (response.ok) {
          const data = await response.json()
          const isRunning = taskType === 'crawl' ? data.crawl_running : data.summary_running
          
          if (!isRunning) {
            // 任务完成
            if (taskType === 'crawl') {
              setCrawlStatus({
                lastRun: data.crawl_last_run || new Date().toISOString(),
                isRunning: false
              })
              await loadLogs()
            } else {
              setSummaryStatus({
                lastRun: data.summary_last_run || new Date().toISOString(),
                isRunning: false
              })
            }
            return true // 停止轮询
          }
        }
        return false // 继续轮询
      } catch {
        return false
      }
    }

    // 每 2 秒检查一次，最多检查 5 分钟
    let attempts = 0
    const maxAttempts = 150 // 5 分钟
    
    const poll = async () => {
      const done = await checkStatus()
      if (!done && attempts < maxAttempts) {
        attempts++
        setTimeout(poll, 2000)
      }
    }
    
    setTimeout(poll, 2000)
  }

  const runIncrementalUpdate = async () => {
    setCrawlStatus(prev => ({ ...prev, isRunning: true }))
    
    try {
      const response = await fetch('/api/run-crawl', { method: 'POST' })
      
      if (response.ok) {
        // 开始轮询状态
        pollTaskStatus('crawl')
      } else {
        alert('增量更新需要后端支持。\n\n请在终端运行以下命令：\n\npython3 script/monitor.py')
        setCrawlStatus(prev => ({ ...prev, isRunning: false }))
      }
    } catch {
      alert('增量更新需要后端支持。\n\n请在终端运行以下命令：\n\npython3 script/monitor.py')
      setCrawlStatus(prev => ({ ...prev, isRunning: false }))
    }
  }

  const runAISummary = async () => {
    setSummaryStatus(prev => ({ ...prev, isRunning: true }))
    
    try {
      const response = await fetch('/api/run-summary', { method: 'POST' })
      
      if (response.ok) {
        // 开始轮询状态
        pollTaskStatus('summary')
      } else {
        alert('AI 总结需要后端支持。\n\n请在终端运行以下命令：\n\npython3 script/ai_summary.py')
        setSummaryStatus(prev => ({ ...prev, isRunning: false }))
      }
    } catch {
      alert('AI 总结需要后端支持。\n\n请在终端运行以下命令：\n\npython3 script/ai_summary.py')
      setSummaryStatus(prev => ({ ...prev, isRunning: false }))
    }
  }

  const formatLastRun = (isoString: string | null) => {
    if (!isoString) return '从未运行'
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // 未登录显示登录界面
  if (!isAuthenticated) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="bg-white rounded-lg border border-gray-200 p-8 w-full max-w-md shadow-sm">
          <h1 className="text-xl font-semibold mb-6 text-center">Admin 登录</h1>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="请输入管理员密码"
              />
            </div>
            
            {authError && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {authError}
              </div>
            )}
            
            <button
              onClick={handleLogin}
              className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              登录
            </button>
          </div>
          
          <div className="mt-6 text-xs text-gray-400 text-center">
            密码配置在 info/admin_config.json
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Admin 管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            管理 YouWare Changelog 和运行状态
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
        >
          退出登录
        </button>
      </div>

      {/* Changelog 编辑器 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">YouWare Changelog</h2>
            <p className="text-xs text-gray-500">使用 Markdown 格式编辑，保存后自动解析并打标</p>
          </div>
          <div className="flex items-center gap-3">
            {saveMessage && (
              <span className={cn(
                'text-sm',
                saveMessage.includes('失败') ? 'text-red-600' : 'text-green-600'
              )}>
                {saveMessage}
              </span>
            )}
            <button
              onClick={loadChangelog}
              disabled={changelogLoading}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
            >
              刷新
            </button>
            <button
              onClick={saveChangelog}
              disabled={saving}
              className={cn(
                'px-4 py-1.5 text-sm font-medium rounded transition-colors',
                saving
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              )}
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
        
        <div className="p-4">
          {changelogLoading ? (
            <div className="h-96 flex items-center justify-center text-gray-500">
              加载中...
            </div>
          ) : (
            <textarea
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
              className="w-full h-96 p-3 border border-gray-200 rounded-md font-mono text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="# YouWare Changelog&#10;&#10;## v2.7.4 – January 12, 2026&#10;&#10;### Features&#10;&#10;#### Feature Title&#10;Feature description..."
            />
          )}
        </div>
        
        <div className="px-4 pb-4">
          <div className="text-xs text-gray-400 space-y-1">
            <p>格式说明：</p>
            <ul className="list-disc list-inside ml-2 space-y-0.5">
              <li>版本标题: <code className="bg-gray-100 px-1 rounded">## v版本号 – 日期</code></li>
              <li>分类: <code className="bg-gray-100 px-1 rounded">### Features / Improvements / Patches / Integrations</code></li>
              <li>功能标题: <code className="bg-gray-100 px-1 rounded">#### Feature Title</code></li>
              <li>列表项: <code className="bg-gray-100 px-1 rounded">- **标题:** 描述</code> 或 <code className="bg-gray-100 px-1 rounded">- 内容</code></li>
            </ul>
          </div>
        </div>
      </div>

      {/* 操作按钮区域 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 增量更新按钮 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-medium text-gray-900">增量更新</h3>
              <p className="text-xs text-gray-500">爬取 → 打标 → AI 总结</p>
            </div>
            <button
              onClick={runIncrementalUpdate}
              disabled={crawlStatus.isRunning}
              className={cn(
                'px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2',
                crawlStatus.isRunning
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              )}
            >
              {crawlStatus.isRunning && (
                <svg className="animate-spin size-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              )}
              {crawlStatus.isRunning ? '运行中...' : '运行'}
            </button>
          </div>
          <div className="text-xs text-gray-400">
            上次运行: {formatLastRun(crawlStatus.lastRun)}
          </div>
        </div>

        {/* AI 总结按钮 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-medium text-gray-900">AI 总结</h3>
              <p className="text-xs text-gray-500">生成竞品对比分析</p>
            </div>
            <button
              onClick={runAISummary}
              disabled={summaryStatus.isRunning}
              className={cn(
                'px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2',
                summaryStatus.isRunning
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-purple-600 text-white hover:bg-purple-700'
              )}
            >
              {summaryStatus.isRunning && (
                <svg className="animate-spin size-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              )}
              {summaryStatus.isRunning ? '运行中...' : '运行'}
            </button>
          </div>
          <div className="text-xs text-gray-400">
            上次运行: {formatLastRun(summaryStatus.lastRun)}
          </div>
        </div>
      </div>

      {/* 命令提示 */}
      <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">终端命令</h3>
        <div className="space-y-2 text-xs font-mono text-gray-600">
          <div>
            <span className="text-gray-400"># 启动 API 服务器（VPS 必须）</span>
            <pre className="mt-1 bg-white p-2 rounded border">python3 script/api_server.py</pre>
          </div>
          <div>
            <span className="text-gray-400"># 增量更新（爬取+打标+AI总结）</span>
            <pre className="mt-1 bg-white p-2 rounded border">python3 script/monitor.py</pre>
          </div>
          <div>
            <span className="text-gray-400"># 仅生成 AI 总结</span>
            <pre className="mt-1 bg-white p-2 rounded border">python3 script/ai_summary.py</pre>
          </div>
        </div>
      </div>

      {/* 更新日志列表 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">更新日志（最近 100 天）</h2>
          <button
            onClick={loadLogs}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            刷新
          </button>
        </div>
        
        {logsLoading ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-500">
            加载中...
          </div>
        ) : logs.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <div className="text-gray-500">暂无更新日志</div>
            <p className="text-sm text-gray-400 mt-2">
              运行 monitor 脚本后会生成更新日志
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {logs.map((log, idx) => (
              <LogCard key={idx} log={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface LogCardProps {
  log: UpdateLogEntry
}

function LogCard({ log }: LogCardProps) {
  const [expanded, setExpanded] = useState(false)
  const timestamp = new Date(log.timestamp)
  const formattedDate = timestamp.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })

  const updates = Object.entries(log.updates || {})
  const totalNew = updates.reduce((sum, [, info]) => sum + (info.new_count || 0), 0)
  const hasErrors = updates.some(([, info]) => info.status === 'failed' || info.error)
  const hasNewFeatures = totalNew > 0

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            'size-3 rounded-full',
            hasErrors ? 'bg-red-500' : hasNewFeatures ? 'bg-green-500' : 'bg-gray-400'
          )} />
          <div>
            <div className="font-medium">{formattedDate}</div>
            <div className="text-sm text-gray-500">
              {log.mode === 'sync_status' ? '同步状态' : `模式: ${log.mode || 'incremental'}`}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {totalNew > 0 && (
            <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-700 rounded">
              +{totalNew} 新增
            </span>
          )}
          {hasErrors && (
            <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded">
              错误
            </span>
          )}
          <svg
            className={cn('size-5 text-gray-400 transition-transform', expanded && 'rotate-180')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-200 p-4 space-y-3">
          {updates.map(([product, info]) => (
            <div key={product} className="flex items-start justify-between py-2 border-b border-gray-100 last:border-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'size-2 rounded-full',
                  info.status === 'success' ? 'bg-green-500' :
                  info.status === 'failed' || info.error ? 'bg-red-500' :
                  'bg-gray-400'
                )} />
                <span className="font-medium">{product}</span>
              </div>
              <div className="text-sm text-right">
                {info.status === 'success' ? (
                  <>
                    {info.new_count && info.new_count > 0 ? (
                      <span className="text-green-600">+{info.new_count} 新增</span>
                    ) : (
                      <span className="text-gray-500">无变化</span>
                    )}
                    {info.total_count && (
                      <span className="text-gray-400 ml-2">(共 {info.total_count} 条)</span>
                    )}
                  </>
                ) : info.error ? (
                  <span className="text-red-600">{info.error}</span>
                ) : (
                  <span className="text-gray-500">{info.status}</span>
                )}
              </div>
            </div>
          ))}

          {updates.some(([, info]) => info.new_features && info.new_features.length > 0) && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-700 mb-2">新增功能</h4>
              <div className="space-y-2">
                {updates.map(([product, info]) =>
                  info.new_features?.map((feature, idx) => (
                    <div key={`${product}-${idx}`} className="text-sm flex items-start gap-2">
                      <span className="text-gray-400">{product}:</span>
                      <span className="text-gray-700">{feature.title}</span>
                      {feature.time && (
                        <span className="text-gray-400 text-xs">({feature.time})</span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AdminPage
