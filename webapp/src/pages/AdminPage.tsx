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

interface OthersFeature {
  product: string
  feature_index: number
  title: string
  description: string
  time: string
  current_subtags: string[]
}

interface TagsData {
  primary_tags: Array<{
    name: string
    description: string
    subtags: Array<{ name: string; description?: string }>
  }>
  subtag_to_primary: Record<string, string>
}

interface RunStatus {
  lastRun: string | null
  isRunning: boolean
}

interface FeatureItem {
  index: number
  title: string
  description: string
  time: string
  tags: Array<{
    name: string
    subtags: Array<{ name: string }>
  }>
}

function AdminPage() {
  // 认证状态
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authToken, setAuthToken] = useState<string | null>(null)
  
  // 添加新功能
  const [newFeatureTitle, setNewFeatureTitle] = useState('')
  const [newFeatureDescription, setNewFeatureDescription] = useState('')
  const [newFeatureTime, setNewFeatureTime] = useState('')
  const [addingFeature, setAddingFeature] = useState(false)
  const [addFeatureMessage, setAddFeatureMessage] = useState('')
  
  // 过滤标签配置
  const [excludeTags, setExcludeTags] = useState<string[]>([])
  const [newExcludeTag, setNewExcludeTag] = useState('')
  const [excludeTagsSaving, setExcludeTagsSaving] = useState(false)
  const [excludeTagsMessage, setExcludeTagsMessage] = useState('')
  
  // 运行状态
  const [logs, setLogs] = useState<UpdateLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(true)
  const [crawlStatus, setCrawlStatus] = useState<RunStatus>({ lastRun: null, isRunning: false })
  const [summaryStatus, setSummaryStatus] = useState<RunStatus>({ lastRun: null, isRunning: false })
  
  // Others 管理
  const [othersFeatures, setOthersFeatures] = useState<OthersFeature[]>([])
  const [othersLoading, setOthersLoading] = useState(false)
  const [tagsData, setTagsData] = useState<TagsData | null>(null)
  
  // 功能标签编辑
  const [featureProduct, setFeatureProduct] = useState('youware')
  const [features, setFeatures] = useState<FeatureItem[]>([])
  const [featuresLoading, setFeaturesLoading] = useState(false)
  const [featureSearch, setFeatureSearch] = useState('')
  const [featurePage, setFeaturePage] = useState(1)
  const [featureTotal, setFeatureTotal] = useState(0)
  const [editingFeature, setEditingFeature] = useState<FeatureItem | null>(null)
  
  // 标签重命名
  const [renameOldName, setRenameOldName] = useState('')
  const [renameNewName, setRenameNewName] = useState('')
  const [renameType, setRenameType] = useState<'primary' | 'subtag'>('subtag')
  const [renaming, setRenaming] = useState(false)
  const [renameMessage, setRenameMessage] = useState('')

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
      loadLogs()
      loadRunStatus()
      loadExcludeTags()
      loadOthersFeatures()
      loadTagsData()
      // 自动加载 YouWare 功能列表
      loadFeatures('youware', 1, '')
    }
  }, [isAuthenticated, authToken])

  const loadExcludeTags = async () => {
    try {
      const response = await fetch('/data/info/admin_config.json')
      if (response.ok) {
        const config = await response.json()
        setExcludeTags(config.exclude_tags || [])
      }
    } catch {
      console.warn('Failed to load exclude tags')
    }
  }

  const loadOthersFeatures = async () => {
    if (!authToken) return
    
    setOthersLoading(true)
    try {
      const response = await fetch('/api/admin/others', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setOthersFeatures(data.features || [])
      } else if (response.status === 401) {
        handleLogout()
      }
    } catch {
      console.warn('Failed to load Others features')
    } finally {
      setOthersLoading(false)
    }
  }

  const loadTagsData = async () => {
    if (!authToken) return
    
    try {
      const response = await fetch('/api/admin/tags', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setTagsData(data)
      }
    } catch {
      console.warn('Failed to load tags data')
    }
  }

  const updateOthersTag = async (
    product: string,
    featureIndex: number,
    primaryTag: string,
    subtag: string
  ) => {
    if (!authToken) return
    
    try {
      const response = await fetch('/api/admin/others/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          product,
          feature_index: featureIndex,
          primary_tag: primaryTag,
          subtag: subtag
        })
      })
      
      if (response.ok) {
        // 刷新 Others 列表和 Tags 数据
        await loadOthersFeatures()
        await loadTagsData()
      } else if (response.status === 401) {
        handleLogout()
      } else {
        alert('更新失败')
      }
    } catch {
      alert('更新失败：无法连接到后端服务')
    }
  }

  // 加载 features 列表
  const loadFeatures = useCallback(async (product: string, page: number, search: string) => {
    if (!authToken) return
    
    setFeaturesLoading(true)
    try {
      const response = await fetch('/api/admin/features', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ product, page, page_size: 20, search })
      })
      
      if (response.ok) {
        const data = await response.json()
        setFeatures(data.features || [])
        setFeatureTotal(data.total || 0)
      } else if (response.status === 401) {
        handleLogout()
      }
    } catch {
      console.warn('Failed to load features')
    } finally {
      setFeaturesLoading(false)
    }
  }, [authToken])

  // 更新 feature 标签
  const updateFeatureTags = async (product: string, featureIndex: number, newTags: FeatureItem['tags']) => {
    if (!authToken) return false
    
    try {
      const response = await fetch('/api/admin/feature/update-tags', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          product,
          feature_index: featureIndex,
          tags: newTags
        })
      })
      
      if (response.ok) {
        await loadFeatures(product, featurePage, featureSearch)
        return true
      } else if (response.status === 401) {
        handleLogout()
      }
      return false
    } catch {
      return false
    }
  }

  // 重命名标签
  const renameTag = async () => {
    if (!authToken || !renameOldName || !renameNewName) return
    
    setRenaming(true)
    setRenameMessage('')
    
    try {
      const response = await fetch('/api/admin/tag/rename', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          old_name: renameOldName,
          new_name: renameNewName,
          type: renameType
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setRenameMessage(`已重命名！更新了 ${data.updated_products} 个产品`)
        setRenameOldName('')
        setRenameNewName('')
        await loadTagsData()
        setTimeout(() => setRenameMessage(''), 3000)
      } else if (response.status === 401) {
        handleLogout()
      } else {
        setRenameMessage('重命名失败')
      }
    } catch {
      setRenameMessage('重命名失败：无法连接到后端服务')
    } finally {
      setRenaming(false)
    }
  }

  // 加载 features 当产品或页码变化时
  useEffect(() => {
    if (isAuthenticated && authToken) {
      loadFeatures(featureProduct, featurePage, featureSearch)
    }
  }, [isAuthenticated, authToken, featureProduct, featurePage, loadFeatures])

  const saveExcludeTags = async () => {
    if (!authToken) return
    
    setExcludeTagsSaving(true)
    setExcludeTagsMessage('')
    
    try {
      const response = await fetch('/api/admin/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ exclude_tags: excludeTags })
      })
      
      if (response.ok) {
        setExcludeTagsMessage('已保存！刷新页面生效')
        setTimeout(() => setExcludeTagsMessage(''), 3000)
      } else if (response.status === 401) {
        handleLogout()
      } else {
        setExcludeTagsMessage('保存失败')
      }
    } catch {
      setExcludeTagsMessage('保存失败：无法连接到后端服务')
    } finally {
      setExcludeTagsSaving(false)
    }
  }

  const addExcludeTag = () => {
    const tag = newExcludeTag.trim()
    if (tag && !excludeTags.includes(tag)) {
      setExcludeTags([...excludeTags, tag])
      setNewExcludeTag('')
    }
  }

  const removeExcludeTag = (tag: string) => {
    setExcludeTags(excludeTags.filter(t => t !== tag))
  }

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
    setLogs([])
  }

  // 添加新功能
  const addFeature = async () => {
    if (!authToken || !newFeatureTitle.trim()) return
    
    setAddingFeature(true)
    setAddFeatureMessage('')
    
    try {
      const response = await fetch('/api/admin/feature/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          product: 'youware',
          title: newFeatureTitle.trim(),
          description: newFeatureDescription.trim(),
          time: newFeatureTime || new Date().toISOString().split('T')[0],
          auto_tag: true
        })
      })
      
      if (response.ok) {
        setAddFeatureMessage('已添加！正在自动打标...')
        setNewFeatureTitle('')
        setNewFeatureDescription('')
        setNewFeatureTime('')
        // 刷新功能列表
        setTimeout(() => {
          loadFeatures('youware', 1, '')
          setAddFeatureMessage('')
        }, 2000)
      } else if (response.status === 401) {
        handleLogout()
      } else {
        const err = await response.json()
        setAddFeatureMessage(err.error || '添加失败')
      }
    } catch {
      setAddFeatureMessage('添加失败：无法连接到后端服务')
    } finally {
      setAddingFeature(false)
    }
  }

  // 编辑功能
  const editFeature = async (featureIndex: number, updates: { title?: string; description?: string; time?: string }) => {
    if (!authToken) return false
    
    try {
      const response = await fetch('/api/admin/feature/edit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          product: featureProduct,
          feature_index: featureIndex,
          ...updates
        })
      })
      
      if (response.ok) {
        await loadFeatures(featureProduct, featurePage, featureSearch)
        return true
      } else if (response.status === 401) {
        handleLogout()
      }
      return false
    } catch {
      return false
    }
  }

  // 删除功能
  const deleteFeature = async (featureIndex: number, title: string) => {
    if (!authToken) return
    
    if (!confirm(`确定要删除 "${title}" 吗？此操作不可恢复。`)) {
      return
    }
    
    try {
      const response = await fetch('/api/admin/feature/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          product: featureProduct,
          feature_index: featureIndex
        })
      })
      
      if (response.ok) {
        await loadFeatures(featureProduct, featurePage, featureSearch)
      } else if (response.status === 401) {
        handleLogout()
      }
    } catch {
      alert('删除失败')
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

      {/* 添加新功能 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">添加新功能</h2>
            <p className="text-xs text-gray-500">添加后自动打标并更新到 YouWare 功能列表</p>
          </div>
          <div className="flex items-center gap-3">
            {addFeatureMessage && (
              <span className={cn(
                'text-sm',
                addFeatureMessage.includes('失败') ? 'text-red-600' : 'text-green-600'
              )}>
                {addFeatureMessage}
              </span>
            )}
            <button
              onClick={addFeature}
              disabled={addingFeature || !newFeatureTitle.trim()}
              className={cn(
                'px-4 py-1.5 text-sm font-medium rounded transition-colors',
                addingFeature || !newFeatureTitle.trim()
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-green-600 text-white hover:bg-green-700'
              )}
            >
              {addingFeature ? '添加中...' : '添加功能'}
            </button>
          </div>
        </div>
        
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              功能标题 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={newFeatureTitle}
              onChange={(e) => setNewFeatureTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="例如：TailwindCSS Support"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              功能描述
            </label>
            <textarea
              value={newFeatureDescription}
              onChange={(e) => setNewFeatureDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent resize-y"
              placeholder="详细描述这个功能..."
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              发布日期
            </label>
            <input
              type="date"
              value={newFeatureTime}
              onChange={(e) => setNewFeatureTime(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            <span className="text-xs text-gray-400 ml-2">留空则使用今天</span>
          </div>
        </div>
      </div>

      {/* 过滤标签配置 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">过滤标签</h2>
            <p className="text-xs text-gray-500">这些标签将不会显示在 Matrix 和 Tags 页面</p>
          </div>
          <div className="flex items-center gap-3">
            {excludeTagsMessage && (
              <span className={cn(
                'text-sm',
                excludeTagsMessage.includes('失败') ? 'text-red-600' : 'text-green-600'
              )}>
                {excludeTagsMessage}
              </span>
            )}
            <button
              onClick={saveExcludeTags}
              disabled={excludeTagsSaving}
              className={cn(
                'px-4 py-1.5 text-sm font-medium rounded transition-colors',
                excludeTagsSaving
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              )}
            >
              {excludeTagsSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
        
        <div className="p-4">
          {/* 当前过滤的标签 */}
          <div className="flex flex-wrap gap-2 mb-4">
            {excludeTags.length === 0 ? (
              <span className="text-sm text-gray-400">暂无过滤标签</span>
            ) : (
              excludeTags.map(tag => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm"
                >
                  {tag}
                  <button
                    onClick={() => removeExcludeTag(tag)}
                    className="ml-1 hover:text-red-900"
                  >
                    <svg className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              ))
            )}
          </div>
          
          {/* 添加新标签 */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newExcludeTag}
              onChange={(e) => setNewExcludeTag(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addExcludeTag()}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="输入要过滤的标签名称，如 Bug Fixes"
            />
            <button
              onClick={addExcludeTag}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              添加
            </button>
          </div>
        </div>
      </div>

      {/* Others 标签管理 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">Others 标签管理</h2>
            <p className="text-xs text-gray-500">管理被归类为 "Others" 的功能，将其分配到正确的标签</p>
          </div>
          <button
            onClick={loadOthersFeatures}
            disabled={othersLoading}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
          >
            刷新
          </button>
        </div>
        
        <div className="p-4">
          {othersLoading ? (
            <div className="text-center text-gray-500 py-8">加载中...</div>
          ) : othersFeatures.length === 0 ? (
            <div className="text-center text-gray-500 py-8">没有待处理的 Others 标签</div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {othersFeatures.map((feature, idx) => (
                <OthersFeatureCard
                  key={`${feature.product}-${feature.feature_index}-${idx}`}
                  feature={feature}
                  tagsData={tagsData}
                  onUpdate={updateOthersTag}
                />
              ))}
            </div>
          )}
        </div>
        
        <div className="px-4 pb-4">
          <div className="text-xs text-gray-400">
            共 {othersFeatures.length} 个待处理项
          </div>
        </div>
      </div>

      {/* 功能标签编辑 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">功能标签编辑</h2>
            <p className="text-xs text-gray-500">编辑单个 changelog 条目的标签</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={featureProduct}
              onChange={(e) => {
                setFeatureProduct(e.target.value)
                setFeaturePage(1)
              }}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0'].map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="搜索..."
              value={featureSearch}
              onChange={(e) => setFeatureSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadFeatures(featureProduct, 1, featureSearch)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 w-48"
            />
            <button
              onClick={() => {
                setFeaturePage(1)
                loadFeatures(featureProduct, 1, featureSearch)
              }}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
            >
              搜索
            </button>
          </div>
        </div>
        
        <div className="p-4">
          {featuresLoading ? (
            <div className="text-center text-gray-500 py-8">加载中...</div>
          ) : features.length === 0 ? (
            <div className="text-center text-gray-500 py-8">没有找到功能</div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {features.map((feature) => (
                <FeatureTagCard
                  key={`${featureProduct}-${feature.index}`}
                  feature={feature}
                  product={featureProduct}
                  tagsData={tagsData}
                  isEditing={editingFeature?.index === feature.index}
                  onEdit={() => setEditingFeature(editingFeature?.index === feature.index ? null : feature)}
                  onSave={async (newTags) => {
                    const success = await updateFeatureTags(featureProduct, feature.index, newTags)
                    if (success) setEditingFeature(null)
                  }}
                  onEditContent={editFeature}
                  onDelete={deleteFeature}
                />
              ))}
            </div>
          )}
        </div>
        
        <div className="px-4 pb-4 flex items-center justify-between">
          <div className="text-xs text-gray-400">
            共 {featureTotal} 条，第 {featurePage} 页
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setFeaturePage(Math.max(1, featurePage - 1))}
              disabled={featurePage <= 1}
              className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50"
            >
              上一页
            </button>
            <button
              onClick={() => setFeaturePage(featurePage + 1)}
              disabled={featurePage * 20 >= featureTotal}
              className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </div>
      </div>

      {/* 标签重命名 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="font-medium text-gray-900">标签统一重命名</h2>
            <p className="text-xs text-gray-500">批量修改标签名称，影响所有产品数据</p>
          </div>
        </div>
        
        <div className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <select
              value={renameType}
              onChange={(e) => setRenameType(e.target.value as 'primary' | 'subtag')}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="subtag">二级标签</option>
              <option value="primary">一级标签</option>
            </select>
            <input
              type="text"
              placeholder="原标签名"
              value={renameOldName}
              onChange={(e) => setRenameOldName(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="新标签名"
              value={renameNewName}
              onChange={(e) => setRenameNewName(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={renameTag}
              disabled={renaming || !renameOldName || !renameNewName}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded transition-colors',
                renaming || !renameOldName || !renameNewName
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-orange-600 text-white hover:bg-orange-700'
              )}
            >
              {renaming ? '处理中...' : '重命名'}
            </button>
          </div>
          
          {renameMessage && (
            <div className={cn(
              'mt-3 text-sm',
              renameMessage.includes('失败') ? 'text-red-600' : 'text-green-600'
            )}>
              {renameMessage}
            </div>
          )}
          
          {/* 当前标签列表 */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              {renameType === 'primary' ? '一级标签' : '二级标签'}列表
            </h4>
            <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
              {renameType === 'primary' ? (
                tagsData?.primary_tags.map(p => (
                  <button
                    key={p.name}
                    onClick={() => setRenameOldName(p.name)}
                    className={cn(
                      'px-2 py-0.5 text-xs rounded transition-colors',
                      renameOldName === p.name
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    )}
                  >
                    {p.name}
                  </button>
                ))
              ) : (
                tagsData?.primary_tags.flatMap(p => 
                  p.subtags.map(s => (
                    <button
                      key={`${p.name}-${s.name}`}
                      onClick={() => setRenameOldName(s.name)}
                      className={cn(
                        'px-2 py-0.5 text-xs rounded transition-colors',
                        renameOldName === s.name
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      )}
                      title={`${p.name} > ${s.name}`}
                    >
                      {s.name}
                    </button>
                  ))
                )
              )}
            </div>
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

// Others 管理卡片组件
interface OthersFeatureCardProps {
  feature: OthersFeature
  tagsData: TagsData | null
  onUpdate: (product: string, featureIndex: number, primaryTag: string, subtag: string) => Promise<void>
}

function OthersFeatureCard({ feature, tagsData, onUpdate }: OthersFeatureCardProps) {
  const [selectedPrimary, setSelectedPrimary] = useState('')
  const [selectedSubtag, setSelectedSubtag] = useState('')
  const [newSubtag, setNewSubtag] = useState('')
  const [updating, setUpdating] = useState(false)
  
  // 获取可选的 subtags
  const availableSubtags = selectedPrimary && tagsData
    ? tagsData.primary_tags.find(p => p.name === selectedPrimary)?.subtags || []
    : []
  
  const handleUpdate = async () => {
    const subtag = selectedSubtag === '__new__' ? newSubtag.trim() : selectedSubtag
    if (!selectedPrimary || !subtag) return
    
    setUpdating(true)
    try {
      await onUpdate(feature.product, feature.feature_index, selectedPrimary, subtag)
      // 清空选择
      setSelectedPrimary('')
      setSelectedSubtag('')
      setNewSubtag('')
    } finally {
      setUpdating(false)
    }
  }
  
  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
              {feature.product}
            </span>
            <span className="text-xs text-gray-400">{feature.time}</span>
          </div>
          <h4 className="font-medium text-gray-900 mt-1 truncate" title={feature.title}>
            {feature.title}
          </h4>
          {feature.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
              {feature.description}
            </p>
          )}
          <div className="flex flex-wrap gap-1 mt-2">
            {feature.current_subtags.map(st => (
              <span key={st} className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                Others &gt; {st}
              </span>
            ))}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200">
        <select
          value={selectedPrimary}
          onChange={(e) => {
            setSelectedPrimary(e.target.value)
            setSelectedSubtag('')
          }}
          className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">选择一级标签</option>
          {tagsData?.primary_tags.filter(p => p.name !== 'Others').map(p => (
            <option key={p.name} value={p.name}>{p.name}</option>
          ))}
        </select>
        
        {selectedPrimary && (
          <select
            value={selectedSubtag}
            onChange={(e) => setSelectedSubtag(e.target.value)}
            className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">选择二级标签</option>
            {availableSubtags.map(s => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
            <option value="__new__">+ 新建二级标签</option>
          </select>
        )}
        
        {selectedSubtag === '__new__' && (
          <input
            type="text"
            value={newSubtag}
            onChange={(e) => setNewSubtag(e.target.value)}
            placeholder="输入新标签名"
            className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )}
        
        <button
          onClick={handleUpdate}
          disabled={updating || !selectedPrimary || (!selectedSubtag || (selectedSubtag === '__new__' && !newSubtag.trim()))}
          className={cn(
            'px-3 py-1 text-sm font-medium rounded transition-colors',
            updating || !selectedPrimary || (!selectedSubtag || (selectedSubtag === '__new__' && !newSubtag.trim()))
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-green-600 text-white hover:bg-green-700'
          )}
        >
          {updating ? '...' : '确认'}
        </button>
      </div>
    </div>
  )
}

// 功能标签编辑卡片
interface FeatureTagCardProps {
  feature: FeatureItem
  product: string
  tagsData: TagsData | null
  isEditing: boolean
  onEdit: () => void
  onSave: (newTags: FeatureItem['tags']) => Promise<void>
  onEditContent?: (featureIndex: number, updates: { title?: string; description?: string; time?: string }) => Promise<boolean>
  onDelete?: (featureIndex: number, title: string) => Promise<void>
}

function FeatureTagCard({ feature, tagsData, isEditing, onEdit, onSave, onEditContent, onDelete }: FeatureTagCardProps) {
  // 确保 tags 始终是数组
  const normalizeTags = (tags: FeatureItem['tags'] | string | null | undefined): FeatureItem['tags'] => {
    if (!tags || tags === 'None' || typeof tags === 'string') return []
    if (!Array.isArray(tags)) return []
    return tags
  }
  
  const [editedTags, setEditedTags] = useState<FeatureItem['tags']>(normalizeTags(feature.tags))
  const [saving, setSaving] = useState(false)
  const [selectedPrimary, setSelectedPrimary] = useState('')
  const [selectedSubtag, setSelectedSubtag] = useState('')
  const [editingContent, setEditingContent] = useState(false)
  const [editedTitle, setEditedTitle] = useState(feature.title)
  const [editedDescription, setEditedDescription] = useState(feature.description)
  const [editedTime, setEditedTime] = useState(feature.time)
  
  // 当 feature 变化时重置编辑状态
  useEffect(() => {
    setEditedTags(normalizeTags(feature.tags))
    setEditedTitle(feature.title)
    setEditedDescription(feature.description)
    setEditedTime(feature.time)
  }, [feature])
  
  const availableSubtags = selectedPrimary && tagsData
    ? tagsData.primary_tags.find(p => p.name === selectedPrimary)?.subtags || []
    : []
  
  const addTag = () => {
    if (!selectedPrimary || !selectedSubtag) return
    
    // 检查是否已存在
    const existingPrimary = editedTags.find(t => t.name === selectedPrimary)
    if (existingPrimary) {
      const hasSubtag = existingPrimary.subtags.some(s => s.name === selectedSubtag)
      if (!hasSubtag) {
        setEditedTags(editedTags.map(t => 
          t.name === selectedPrimary 
            ? { ...t, subtags: [...t.subtags, { name: selectedSubtag }] }
            : t
        ))
      }
    } else {
      setEditedTags([...editedTags, {
        name: selectedPrimary,
        subtags: [{ name: selectedSubtag }]
      }])
    }
    
    setSelectedPrimary('')
    setSelectedSubtag('')
  }
  
  const removeSubtag = (primaryName: string, subtagName: string) => {
    setEditedTags(editedTags.map(t => {
      if (t.name === primaryName) {
        const newSubtags = t.subtags.filter(s => s.name !== subtagName)
        return newSubtags.length > 0 ? { ...t, subtags: newSubtags } : null
      }
      return t
    }).filter(Boolean) as FeatureItem['tags'])
  }
  
  const handleSave = async () => {
    setSaving(true)
    await onSave(editedTags)
    setSaving(false)
  }

  const handleSaveContent = async () => {
    if (!onEditContent) return
    setSaving(true)
    const success = await onEditContent(feature.index, {
      title: editedTitle,
      description: editedDescription,
      time: editedTime
    })
    if (success) {
      setEditingContent(false)
    }
    setSaving(false)
  }
  
  return (
    <div className={cn(
      'border rounded-lg p-3 transition-colors',
      isEditing || editingContent ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-gray-50'
    )}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          {editingContent ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                placeholder="标题"
              />
              <textarea
                value={editedDescription}
                onChange={(e) => setEditedDescription(e.target.value)}
                rows={2}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded resize-y"
                placeholder="描述"
              />
              <input
                type="date"
                value={editedTime}
                onChange={(e) => setEditedTime(e.target.value)}
                className="px-2 py-1 text-sm border border-gray-300 rounded"
              />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-400">{feature.time}</span>
              </div>
              <h4 className="font-medium text-gray-900 text-sm" title={feature.title}>
                {feature.title}
              </h4>
              {feature.description && (
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{feature.description}</p>
              )}
            </>
          )}
          
          {/* 当前标签 */}
          {!editingContent && (
            <div className="flex flex-wrap gap-1 mt-2">
              {(isEditing ? editedTags : normalizeTags(feature.tags)).map(tag => 
                tag.subtags.map(st => (
                  <span
                    key={`${tag.name}-${st.name}`}
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded',
                      isEditing ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-700'
                    )}
                  >
                    {tag.name} &gt; {st.name}
                    {isEditing && (
                      <button
                        onClick={() => removeSubtag(tag.name, st.name)}
                        className="ml-0.5 hover:text-red-600"
                      >
                        ×
                      </button>
                    )}
                  </span>
                ))
              )}
              {(isEditing ? editedTags : normalizeTags(feature.tags)).length === 0 && (
                <span className="text-xs text-gray-400">无标签</span>
              )}
            </div>
          )}
        </div>
        
        <div className="flex flex-col gap-1 ml-2">
          {editingContent ? (
            <>
              <button
                onClick={handleSaveContent}
                disabled={saving}
                className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
              >
                {saving ? '...' : '保存'}
              </button>
              <button
                onClick={() => {
                  setEditingContent(false)
                  setEditedTitle(feature.title)
                  setEditedDescription(feature.description)
                  setEditedTime(feature.time)
                }}
                className="px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded hover:bg-gray-300"
              >
                取消
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditingContent(true)}
                className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
                title="编辑内容"
              >
                内容
              </button>
              <button
                onClick={onEdit}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  isEditing
                    ? 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                    : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                )}
              >
                {isEditing ? '取消' : '标签'}
              </button>
              {onDelete && (
                <button
                  onClick={() => onDelete(feature.index, feature.title)}
                  className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                  title="删除"
                >
                  删除
                </button>
              )}
            </>
          )}
        </div>
      </div>
      
      {/* 编辑模式 */}
      {isEditing && (
        <div className="mt-3 pt-3 border-t border-blue-200">
          <div className="flex items-center gap-2 mb-2">
            <select
              value={selectedPrimary}
              onChange={(e) => {
                setSelectedPrimary(e.target.value)
                setSelectedSubtag('')
              }}
              className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded"
            >
              <option value="">选择一级标签</option>
              {tagsData?.primary_tags.filter(p => p.name !== 'Others').map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
            
            {selectedPrimary && (
              <select
                value={selectedSubtag}
                onChange={(e) => setSelectedSubtag(e.target.value)}
                className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded"
              >
                <option value="">选择二级标签</option>
                {availableSubtags.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            )}
            
            <button
              onClick={addTag}
              disabled={!selectedPrimary || !selectedSubtag}
              className="px-2 py-1 text-xs bg-blue-600 text-white rounded disabled:opacity-50"
            >
              添加
            </button>
          </div>
          
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded transition-colors',
                saving
                  ? 'bg-gray-100 text-gray-400'
                  : 'bg-green-600 text-white hover:bg-green-700'
              )}
            >
              {saving ? '保存中...' : '保存修改'}
            </button>
          </div>
        </div>
      )}
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
