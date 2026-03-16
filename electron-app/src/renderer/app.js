'use strict'
/* global api */

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  running: false,
  looping: false,
  daemonOk: false,
  chromeOk: false,
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $logArea      = document.getElementById('log-area')
const $runStatus    = document.getElementById('run-status-text')
const $progressTrack = document.getElementById('progress-track')
const $btnRunOnce   = document.getElementById('btn-run-once')
const $btnStopRun   = document.getElementById('btn-stop-run')
const $btnStartLoop = document.getElementById('btn-start-loop')
const $btnStopLoop  = document.getElementById('btn-stop-loop')
const $loopInterval = document.getElementById('loop-interval')
const $indDaemon    = document.getElementById('ind-daemon')
const $indChrome    = document.getElementById('ind-chrome')

// ── Navigation ────────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'))
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'))
    btn.classList.add('active')
    const panelId = btn.dataset.panel
    document.getElementById(panelId).classList.add('active')
    if (panelId === 'panel-files') refreshFiles()
    if (panelId === 'panel-chrome') refreshChromeStatus()
  })
})

// ── Log ───────────────────────────────────────────────────────────────────────
function appendLog(msg) {
  const atBottom = $logArea.scrollHeight - $logArea.clientHeight - $logArea.scrollTop < 40
  $logArea.textContent += msg + '\n'
  if (atBottom) $logArea.scrollTop = $logArea.scrollHeight
}

document.getElementById('btn-clear-log').addEventListener('click', () => {
  $logArea.textContent = ''
})

// ── Status helpers ────────────────────────────────────────────────────────────
function setIndicator(el, ok) {
  el.classList.toggle('connected', ok)
  el.classList.toggle('error', !ok)
}

function applyStatus(s) {
  state.running = s.running
  state.looping = s.looping
  state.daemonOk = s.daemon
  state.chromeOk = s.chrome

  document.body.classList.toggle('running', s.running)
  document.body.classList.toggle('looping', s.looping)

  setIndicator($indDaemon, s.daemon)
  setIndicator($indChrome, s.chrome)

  $runStatus.textContent = s.running ? '🔄 运行中…' : (s.looping ? '⏰ 循环等待中' : '就绪')
  if (s.running) {
    $progressTrack.classList.remove('hidden')
  } else {
    $progressTrack.classList.add('hidden')
  }
}

// ── IPC events ────────────────────────────────────────────────────────────────
api.onLog(msg => appendLog(msg))
api.onStatus(({ key, value }) => {
  if (key === 'daemon') {
    state.daemonOk = value
    setIndicator($indDaemon, value)
    updateChromePanel()
  }
  if (key === 'chrome') {
    state.chromeOk = value
    setIndicator($indChrome, value)
    updateChromePanel()
  }
  if (key === 'running') {
    state.running = value
    document.body.classList.toggle('running', value)
    $runStatus.textContent = value ? '🔄 运行中…' : '就绪'
    $progressTrack.classList.toggle('hidden', !value)
  }
  if (key === 'looping') {
    state.looping = value
    document.body.classList.toggle('looping', value)
  }
})

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const status = await api.getStatus()
  applyStatus(status)
  await loadConfig()
  appendLog(`[系统] JD Price Monitor 已启动`)
  appendLog(`[系统] Python: ${status.pythonBin}`)
  appendLog(`[系统] 脚本目录: ${status.scriptsDir}`)

  if (!status.daemon) {
    appendLog('[系统] bb-browser daemon 未运行，正在启动…')
    const r = await api.startDaemon()
    appendLog(`[系统] Daemon: ${r.msg}`)
  }
}

init()

// ── Run once ──────────────────────────────────────────────────────────────────
$btnRunOnce.addEventListener('click', async () => {
  if (state.running) return
  appendLog('\n▶ 开始立即巡检…')
  const r = await api.runOnce()
  appendLog(`\n${r.ok ? '✅' : '❌'} 巡检${r.ok ? '完成' : '失败'}`)
})

$btnStopRun.addEventListener('click', async () => {
  await api.stopRun()
})

// ── Loop ──────────────────────────────────────────────────────────────────────
$btnStartLoop.addEventListener('click', async () => {
  const interval = parseInt($loopInterval.value, 10) || 60
  appendLog(`\n⏰ 启动循环巡检，间隔 ${interval} 分钟…`)
  const r = await api.startLoop(interval)
  if (!r.ok) appendLog(`❌ ${r.msg}`)
})

$btnStopLoop.addEventListener('click', async () => {
  await api.stopLoop()
})

// ── Data dir button ───────────────────────────────────────────────────────────
document.getElementById('btn-open-data').addEventListener('click', () => {
  api.openDataDir()
})

// ── Config ────────────────────────────────────────────────────────────────────
async function loadConfig() {
  const cfg = await api.getConfig()
  const shop = cfg.shop || {}
  const check = cfg.check || {}
  const notify = cfg.dingtalk || {}

  document.getElementById('cfg-shop-name').value = shop.shop_name || ''
  document.getElementById('cfg-shop-id').value   = shop.shop_id   || ''
  document.getElementById('cfg-vendor-id').value = shop.vendor_id || ''
  document.getElementById('cfg-cdp-port').value  = cfg.cdp_port   || 9222

  document.getElementById('cfg-threshold').value  = check.threshold  || ''
  document.getElementById('cfg-interval').value   = check.interval   || ''
  document.getElementById('cfg-keep-days').value  = check.keep_days  || ''

  document.getElementById('cfg-dd-webhook').value = notify.webhook || ''
  document.getElementById('cfg-dd-secret').value  = notify.secret  || ''
  document.getElementById('cfg-dd-enabled').checked = notify.enabled || false
}

async function saveSection(sectionKey) {
  const cfg = await api.getConfig()
  let updated = { ...cfg }

  if (sectionKey === 'shop') {
    updated.shop = {
      shop_name: document.getElementById('cfg-shop-name').value.trim(),
      shop_id:   document.getElementById('cfg-shop-id').value.trim(),
      vendor_id: document.getElementById('cfg-vendor-id').value.trim(),
    }
    updated.cdp_port = parseInt(document.getElementById('cfg-cdp-port').value, 10) || 9222
  }

  if (sectionKey === 'check') {
    updated.check = {
      threshold: parseFloat(document.getElementById('cfg-threshold').value) || 5,
      interval:  parseInt(document.getElementById('cfg-interval').value, 10) || 60,
      keep_days: parseInt(document.getElementById('cfg-keep-days').value, 10) || 7,
    }
  }

  if (sectionKey === 'notify') {
    updated.dingtalk = {
      webhook: document.getElementById('cfg-dd-webhook').value.trim(),
      secret:  document.getElementById('cfg-dd-secret').value.trim(),
      enabled: document.getElementById('cfg-dd-enabled').checked,
    }
  }

  const r = await api.saveConfig(updated)
  if (r.ok) {
    showToast('✅ 已保存')
    appendLog(`[配置] ${sectionKey} 配置已保存`)
  } else {
    showToast(`❌ 保存失败: ${r.msg}`)
  }
}

document.getElementById('btn-save-shop').addEventListener('click', () => saveSection('shop'))
document.getElementById('btn-save-check').addEventListener('click', () => saveSection('check'))
document.getElementById('btn-save-notify').addEventListener('click', () => saveSection('notify'))

// ── Chrome panel ──────────────────────────────────────────────────────────────
function updateChromePanel() {
  const chromeDot  = document.getElementById('chrome-dot')
  const chromeText = document.getElementById('chrome-status-text')
  const daemonDot  = document.getElementById('daemon-dot')
  const daemonText = document.getElementById('daemon-status-text')

  const chromeCard = document.getElementById('chrome-status-card')
  const daemonCard = document.getElementById('daemon-status-card')

  chromeCard.classList.toggle('connected', state.chromeOk)
  chromeCard.classList.toggle('error', !state.chromeOk)
  chromeText.textContent = state.chromeOk ? '✓ 已连接 (CDP :9222)' : '✗ 未连接'

  daemonCard.classList.toggle('connected', state.daemonOk)
  daemonCard.classList.toggle('error', !state.daemonOk)
  daemonText.textContent = state.daemonOk ? '✓ 运行中 (:3399)' : '✗ 未运行'
}

async function refreshChromeStatus() {
  const status = await api.getStatus()
  state.chromeOk = status.chrome
  state.daemonOk = status.daemon
  setIndicator($indDaemon, status.daemon)
  setIndicator($indChrome, status.chrome)
  updateChromePanel()
}

document.getElementById('btn-launch-chrome').addEventListener('click', async () => {
  appendLog('[Chrome] 正在启动 Chrome (CDP)…')
  const r = await api.launchChrome()
  appendLog(`[Chrome] ${r.msg}`)
  await refreshChromeStatus()
})

document.getElementById('btn-check-chrome').addEventListener('click', refreshChromeStatus)

document.getElementById('btn-start-daemon').addEventListener('click', async () => {
  appendLog('[Daemon] 正在启动 bb-browser daemon…')
  const r = await api.startDaemon()
  appendLog(`[Daemon] ${r.msg}`)
  await refreshChromeStatus()
})

// ── Files panel ───────────────────────────────────────────────────────────────
async function refreshFiles() {
  const files = await api.getRecentFiles()
  const container = document.getElementById('file-list')
  if (!files.length) {
    container.innerHTML = '<div class="empty-state">暂无数据文件</div>'
    return
  }
  container.innerHTML = files.map(f => {
    const mtime = new Date(f.mtime).toLocaleString('zh-CN')
    return `
      <div class="file-item">
        <div class="file-item-left">
          <span class="file-name">${f.name}</span>
          <span class="file-meta">${mtime}</span>
        </div>
        <div class="file-actions">
          <button class="btn btn-secondary" style="padding:4px 10px;font-size:12px"
            onclick="api.openFile('${f.path.replace(/'/g, "\\'")}')">打开</button>
          <button class="btn btn-secondary" style="padding:4px 10px;font-size:12px"
            onclick="api.showInFinder('${f.path.replace(/'/g, "\\'")}')">在Finder中显示</button>
        </div>
      </div>
    `
  }).join('')
}

document.getElementById('btn-refresh-files').addEventListener('click', refreshFiles)

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, durationMs = 2500) {
  let toast = document.getElementById('__toast')
  if (!toast) {
    toast = document.createElement('div')
    toast.id = '__toast'
    Object.assign(toast.style, {
      position: 'fixed', bottom: '24px', left: '50%',
      transform: 'translateX(-50%)',
      background: '#1e2535', border: '1px solid #2a3347',
      color: '#e2e8f0', padding: '8px 20px',
      borderRadius: '6px', fontSize: '13px',
      zIndex: '9999', pointerEvents: 'none',
      transition: 'opacity 0.2s',
    })
    document.body.appendChild(toast)
  }
  toast.textContent = msg
  toast.style.opacity = '1'
  clearTimeout(toast._timer)
  toast._timer = setTimeout(() => { toast.style.opacity = '0' }, durationMs)
}
