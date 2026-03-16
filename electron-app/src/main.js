'use strict'

// Unset ELECTRON_RUN_AS_NODE so that child processes we spawn (bb-browser daemon,
// Python) do not accidentally inherit this flag and run in Node-only mode.
delete process.env.ELECTRON_RUN_AS_NODE

const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const net = require('net')
const { spawn, execSync } = require('child_process')

// ── Path helpers ──────────────────────────────────────────────────────────────
// Note: app.isPackaged is evaluated lazily so it's available after app is ready
function isPkg() { return app.isPackaged }

function getPythonBin() {
  if (isPkg()) {
    return path.join(process.resourcesPath, 'python', 'bin', 'python3')
  }
  return 'python3'
}

function getPythonScriptsDir() {
  if (isPkg()) {
    return path.join(process.resourcesPath, 'python-scripts')
  }
  // dev: electron-app/src/main.js → project root is two levels up
  return path.join(__dirname, '..', '..')
}

function getBbDaemonScript() {
  if (isPkg()) {
    return path.join(process.resourcesPath, 'bb-browser', 'dist', 'cli.js')
  }
  return path.join(__dirname, '..', 'node_modules', 'bb-browser', 'dist', 'cli.js')
}

function getNodeBin() {
  // In development, use system node if available
  // In packaged app, use Electron binary with ELECTRON_RUN_AS_NODE=1
  if (!isPkg()) {
    // Try to find system node
    try {
      const which = require('child_process').execSync('which node', { encoding: 'utf8' }).trim()
      if (which) return which
    } catch (_) {}
  }
  return process.execPath  // Will be used with ELECTRON_RUN_AS_NODE=1
}

function getDataDir() {
  const scriptsDir = getPythonScriptsDir()
  return path.join(scriptsDir, 'data')
}

// ── Window ────────────────────────────────────────────────────────────────────
let mainWindow = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))

  // Open DevTools in dev mode
  if (!isPkg()) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
  // On mac: stop daemon too
  stopBbDaemon()
})

// ── bb-browser daemon ─────────────────────────────────────────────────────────
let bbDaemonProcess = null
let daemonReady = false

function probeTcp(port, host = '127.0.0.1', timeoutMs = 500) {
  return new Promise((resolve) => {
    const sock = new net.Socket()
    const done = (ok) => { try { sock.destroy() } catch (_) {} resolve(ok) }
    sock.setTimeout(timeoutMs)
    sock.once('connect', () => done(true))
    sock.once('error', () => done(false))
    sock.once('timeout', () => done(false))
    sock.connect(port, host)
  })
}

async function waitForDaemon(port = 3399, retries = 30, interval = 500) {
  for (let i = 0; i < retries; i++) {
    if (await probeTcp(port)) return true
    await new Promise(r => setTimeout(r, interval))
  }
  return false
}

async function startBbDaemon() {
  if (daemonReady) return { ok: true, msg: 'Daemon already running' }

  // Check if already listening on port 3399
  if (await probeTcp(3399)) {
    daemonReady = true
    sendStatus('daemon', true)
    return { ok: true, msg: 'Daemon already running on port 3399' }
  }

  const nodeBin = getNodeBin()
  const daemonScript = getBbDaemonScript()

  if (!fs.existsSync(daemonScript)) {
    return { ok: false, msg: `bb-browser not found at: ${daemonScript}` }
  }

  log(`Starting bb-browser daemon: ${nodeBin} ${daemonScript} daemon`)

  // When using Electron binary as Node, set ELECTRON_RUN_AS_NODE=1
  const daemonEnv = { ...process.env }
  if (nodeBin === process.execPath) {
    daemonEnv.ELECTRON_RUN_AS_NODE = '1'
  }

  bbDaemonProcess = spawn(nodeBin, [daemonScript, 'daemon'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    env: daemonEnv,
  })

  bbDaemonProcess.stdout.on('data', (d) => log(`[bb-daemon] ${d.toString().trim()}`))
  bbDaemonProcess.stderr.on('data', (d) => log(`[bb-daemon] ${d.toString().trim()}`))
  bbDaemonProcess.on('exit', (code) => {
    log(`[bb-daemon] exited with code ${code}`)
    daemonReady = false
    sendStatus('daemon', false)
  })

  const ready = await waitForDaemon(3399)
  if (ready) {
    daemonReady = true
    sendStatus('daemon', true)
    return { ok: true, msg: 'Daemon started successfully' }
  } else {
    bbDaemonProcess.kill()
    bbDaemonProcess = null
    return { ok: false, msg: 'Daemon failed to start (port 3399 not responding)' }
  }
}

function stopBbDaemon() {
  if (bbDaemonProcess) {
    bbDaemonProcess.kill()
    bbDaemonProcess = null
    daemonReady = false
  }
}

// ── Chrome CDP management ─────────────────────────────────────────────────────
async function checkChromeCdp(port = 9222) {
  const ok = await probeTcp(port)
  sendStatus('chrome', ok)
  return ok
}

async function launchChrome(port = 9222) {
  const CHROME_PATHS = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ]

  let chromePath = null
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) { chromePath = p; break }
  }
  if (!chromePath) {
    return { ok: false, msg: 'Chrome not found. Please install Google Chrome.' }
  }

  // Check if Chrome is running WITHOUT CDP — if so, quit it first
  const alreadyListening = await probeTcp(port)
  if (!alreadyListening) {
    try {
      // Gracefully quit Chrome so we can re-launch with CDP flag
      execSync(`osascript -e 'quit app "Google Chrome"'`, { timeout: 5000 })
      await new Promise(r => setTimeout(r, 1500))
    } catch (_) {
      // Chrome wasn't running — fine
    }

    log(`Launching Chrome with --remote-debugging-port=${port}`)
    spawn(chromePath, [
      `--remote-debugging-port=${port}`,
      '--no-first-run',
      '--no-default-browser-check',
    ], { detached: true, stdio: 'ignore' }).unref()

    // Wait for CDP to become available
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 600))
      if (await probeTcp(port)) {
        sendStatus('chrome', true)
        return { ok: true, msg: `Chrome launched with CDP on port ${port}` }
      }
    }
    return { ok: false, msg: 'Chrome launched but CDP not responding' }
  } else {
    sendStatus('chrome', true)
    return { ok: true, msg: `Chrome CDP already available on port ${port}` }
  }
}

// ── Python subprocess ─────────────────────────────────────────────────────────
let runningProcess = null

function runPython(args) {
  return new Promise((resolve) => {
    if (runningProcess) {
      resolve({ ok: false, msg: 'Another process is already running' })
      return
    }

    const pythonBin = getPythonBin()
    const scriptsDir = getPythonScriptsDir()

    log(`Running: ${pythonBin} ${args.join(' ')}`)
    log(`CWD: ${scriptsDir}`)

    runningProcess = spawn(pythonBin, args, {
      cwd: scriptsDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env },
    })

    runningProcess.stdout.on('data', (d) => {
      d.toString().split('\n').filter(l => l.trim()).forEach(l => log(l))
    })
    runningProcess.stderr.on('data', (d) => {
      d.toString().split('\n').filter(l => l.trim()).forEach(l => log(`[err] ${l}`))
    })
    runningProcess.on('exit', (code) => {
      runningProcess = null
      sendStatus('running', false)
      resolve({ ok: code === 0, msg: `Process exited with code ${code}` })
    })
    runningProcess.on('error', (err) => {
      runningProcess = null
      sendStatus('running', false)
      resolve({ ok: false, msg: err.message })
    })

    sendStatus('running', true)
  })
}

// ── Config helpers ────────────────────────────────────────────────────────────
function getConfigPath() {
  return path.join(getPythonScriptsDir(), 'config.yaml')
}

function readConfig() {
  const yaml = require('js-yaml')
  try {
    const content = fs.readFileSync(getConfigPath(), 'utf8')
    return yaml.load(content) || {}
  } catch (e) {
    return {}
  }
}

function writeConfig(cfg) {
  const yaml = require('js-yaml')
  fs.writeFileSync(getConfigPath(), yaml.dump(cfg), 'utf8')
}

// ── Logging helper ────────────────────────────────────────────────────────────
function log(msg) {
  const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const line = `[${ts}] ${msg}`
  console.log(line)
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('log', line)
  }
}

function sendStatus(key, value) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('status', { key, value })
  }
}

// ── Loop task ─────────────────────────────────────────────────────────────────
let loopTimer = null

function stopLoop() {
  if (loopTimer) {
    clearTimeout(loopTimer)
    loopTimer = null
    log('⏹ 循环巡检已停止')
    sendStatus('looping', false)
  }
}

async function runLoop(intervalMinutes) {
  const ms = intervalMinutes * 60 * 1000
  const tick = async () => {
    if (!loopTimer) return  // stopped
    log(`\n🔄 循环巡检触发 (间隔 ${intervalMinutes} 分钟)`)
    await runPython(['main.py'])
    if (loopTimer) {
      loopTimer = setTimeout(tick, ms)
    }
  }
  loopTimer = setTimeout(tick, ms)
  sendStatus('looping', true)
  log(`⏰ 循环巡检已启动，每 ${intervalMinutes} 分钟执行一次`)
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.handle('get-status', async () => {
  const chromeOk = await probeTcp(9222)
  const daemonOk = await probeTcp(3399)
  return {
    chrome: chromeOk,
    daemon: daemonOk || daemonReady,
    running: !!runningProcess,
    looping: !!loopTimer,
    configPath: getConfigPath(),
    dataDir: getDataDir(),
    pythonBin: getPythonBin(),
    scriptsDir: getPythonScriptsDir(),
    bbScript: getBbDaemonScript(),
  }
})

ipcMain.handle('start-daemon', async () => {
  return await startBbDaemon()
})

ipcMain.handle('launch-chrome', async () => {
  return await launchChrome()
})

ipcMain.handle('check-chrome', async () => {
  const ok = await checkChromeCdp()
  return { ok }
})

ipcMain.handle('run-once', async () => {
  return await runPython(['main.py'])
})

ipcMain.handle('stop-run', async () => {
  if (runningProcess) {
    runningProcess.kill('SIGTERM')
    runningProcess = null
    sendStatus('running', false)
    log('⏹ 运行已中止')
    return { ok: true }
  }
  return { ok: false, msg: 'No process running' }
})

ipcMain.handle('start-loop', async (_, intervalMinutes) => {
  if (loopTimer) return { ok: false, msg: 'Already looping' }
  await runLoop(intervalMinutes || 60)
  return { ok: true }
})

ipcMain.handle('stop-loop', async () => {
  stopLoop()
  return { ok: true }
})

ipcMain.handle('get-config', async () => {
  return readConfig()
})

ipcMain.handle('save-config', async (_, cfg) => {
  try {
    writeConfig(cfg)
    return { ok: true }
  } catch (e) {
    return { ok: false, msg: e.message }
  }
})

ipcMain.handle('open-data-dir', async () => {
  const dataDir = getDataDir()
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true })
  }
  shell.openPath(dataDir)
  return { ok: true }
})

ipcMain.handle('show-in-finder', async (_, filePath) => {
  shell.showItemInFolder(filePath)
  return { ok: true }
})

ipcMain.handle('get-recent-files', async () => {
  const dataDir = getDataDir()
  if (!fs.existsSync(dataDir)) return []
  const files = fs.readdirSync(dataDir)
    .filter(f => f.endsWith('.xlsx') || f.endsWith('.json'))
    .map(f => ({
      name: f,
      path: path.join(dataDir, f),
      mtime: fs.statSync(path.join(dataDir, f)).mtime,
    }))
    .sort((a, b) => b.mtime - a.mtime)
    .slice(0, 10)
  return files
})

ipcMain.handle('open-file', async (_, filePath) => {
  shell.openPath(filePath)
  return { ok: true }
})

// ── Cron task management ───────────────────────────────────────────────────────
function parseCrontab() {
  try {
    const out = require('child_process').execSync('crontab -l 2>/dev/null || true', { encoding: 'utf8' })
    const lines = out.split('\n').filter(l => l.trim() && !l.trim().startsWith('#'))
    return lines
  } catch (_) { return [] }
}

function writeCrontab(lines) {
  const content = lines.join('\n') + '\n'
  const tmpFile = path.join(require('os').tmpdir(), 'jd_cron_tmp')
  fs.writeFileSync(tmpFile, content)
  require('child_process').execSync(`crontab "${tmpFile}"`)
  fs.unlinkSync(tmpFile)
}

ipcMain.handle('cron-list', async () => {
  try {
    return { ok: true, lines: parseCrontab() }
  } catch (e) { return { ok: false, msg: e.message, lines: [] } }
})

ipcMain.handle('cron-add', async (_, entry) => {
  try {
    const lines = parseCrontab()
    lines.push(entry)
    writeCrontab(lines)
    return { ok: true }
  } catch (e) { return { ok: false, msg: e.message } }
})

ipcMain.handle('cron-delete', async (_, index) => {
  try {
    const lines = parseCrontab()
    if (index < 0 || index >= lines.length) return { ok: false, msg: '索引越界' }
    lines.splice(index, 1)
    writeCrontab(lines)
    return { ok: true }
  } catch (e) { return { ok: false, msg: e.message } }
})
