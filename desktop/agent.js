// Runs the Xelora local agent (backend/local_agent.py) next to Excel and keeps
// it running. The signed-in web page pairs it (see LocalAgentBridge in the
// frontend); the token is stored encrypted with the OS keychain (DPAPI on
// Windows) and the agent then claims this user's tasks from the cloud API.
const { app, safeStorage } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const EXIT_TOKEN_REJECTED = 3;
const MAX_LOG_BYTES = 5 * 1024 * 1024;
const MAX_RESTART_DELAY_MS = 60_000;

let child = null;
let restartTimer = null;
let restartDelayMs = 2_000;
let startedAt = 0;
let stopping = false;
let status = { state: 'stopped', message: '' };
let notify = () => {};

const linkFile = () => path.join(app.getPath('userData'), 'agent-link.json');
const logFile = () => path.join(app.getPath('userData'), 'logs', 'agent.log');

// Packaged builds ship their own Python + backend under resources/agent
// (built by scripts/bundle-agent.ps1). `npm start` uses the repo's backend
// and the Python on PATH, or XELORA_AGENT_PYTHON.
function runtime() {
  if (app.isPackaged) {
    const root = path.join(process.resourcesPath, 'agent');
    return {
      python: path.join(root, 'python', 'python.exe'),
      script: path.join(root, 'backend', 'local_agent.py'),
    };
  }
  return {
    python: process.env.XELORA_AGENT_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
    script: path.join(__dirname, '..', 'backend', 'local_agent.py'),
  };
}

function setStatus(next) {
  status = { ...status, ...next };
  notify(getStatus());
}

function readLink() {
  try {
    const saved = JSON.parse(fs.readFileSync(linkFile(), 'utf8'));
    const token = saved.encrypted
      ? safeStorage.decryptString(Buffer.from(saved.token, 'base64'))
      : saved.token;
    return { ...saved, token };
  } catch {
    return null;
  }
}

function writeLink({ apiUrl, token, tokenId, userId }) {
  const encrypted = safeStorage.isEncryptionAvailable();
  const stored = encrypted ? safeStorage.encryptString(token).toString('base64') : token;
  fs.mkdirSync(path.dirname(linkFile()), { recursive: true });
  fs.writeFileSync(linkFile(), JSON.stringify({ apiUrl, tokenId, userId, encrypted, token: stored }), { mode: 0o600 });
}

function getStatus() {
  const link = readLink();
  return {
    ...status,
    paired: Boolean(link),
    userId: link ? String(link.userId) : null,
    tokenId: link ? link.tokenId : null,
    apiUrl: link ? link.apiUrl : null,
  };
}

function openLog() {
  const file = logFile();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  try {
    if (fs.statSync(file).size > MAX_LOG_BYTES) fs.renameSync(file, `${file}.1`);
  } catch {
    // no log yet
  }
  return fs.createWriteStream(file, { flags: 'a' });
}

function scheduleRestart() {
  clearTimeout(restartTimer);
  if (Date.now() - startedAt > 60_000) restartDelayMs = 2_000; // it had been healthy
  restartTimer = setTimeout(start, restartDelayMs);
  restartDelayMs = Math.min(restartDelayMs * 2, MAX_RESTART_DELAY_MS);
}

function start() {
  clearTimeout(restartTimer);
  if (child) return getStatus();
  const link = readLink();
  if (!link) {
    setStatus({ state: 'unpaired', message: 'Sign in to connect this PC.' });
    return getStatus();
  }
  const { python, script } = runtime();
  if (app.isPackaged && !fs.existsSync(python)) {
    setStatus({ state: 'unavailable', message: 'This build does not include the local agent.' });
    return getStatus();
  }

  const log = openLog();
  log.write(`\n[${new Date().toISOString()}] starting ${python} ${script}\n`);
  stopping = false;
  startedAt = Date.now();
  setStatus({ state: 'starting', message: 'Connecting to Xelora…' });
  const proc = spawn(python, ['-I', script], {
    env: { ...process.env, XELORA_API_URL: link.apiUrl, XELORA_AGENT_TOKEN: link.token },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child = proc;
  proc.stdout.on('data', (chunk) => {
    log.write(chunk);
    if (status.state !== 'running' && String(chunk).includes('agent connected')) {
      setStatus({ state: 'running', message: 'Ready to run tasks in Excel on this PC.' });
    }
  });
  proc.stderr.on('data', (chunk) => log.write(chunk));
  proc.on('error', (error) => {
    log.write(`[agent] failed to start: ${error.message}\n`);
    if (child !== proc) return;
    child = null;
    setStatus({ state: 'error', message: `Could not start the local agent: ${error.message}` });
    scheduleRestart();
  });
  proc.on('exit', (code) => {
    log.write(`[${new Date().toISOString()}] agent exited with code ${code}\n`);
    log.end();
    if (child !== proc) return; // replaced by a newer agent (re-pairing)
    child = null;
    if (stopping) {
      setStatus({ state: 'stopped', message: '' });
    } else if (code === EXIT_TOKEN_REJECTED) {
      fs.rmSync(linkFile(), { force: true });
      setStatus({ state: 'unpaired', message: 'This PC was disconnected. Sign in again to reconnect.' });
    } else {
      setStatus({ state: 'error', message: 'The local agent stopped; restarting…' });
      scheduleRestart();
    }
  });
  return getStatus();
}

function stop() {
  clearTimeout(restartTimer);
  if (!child) return;
  stopping = true;
  child.kill();
}

function pair(details) {
  const { apiUrl, token, tokenId, userId } = details || {};
  if (typeof apiUrl !== 'string' || !/^https?:\/\//.test(apiUrl) || typeof token !== 'string' || !token.startsWith('xa_')) {
    throw new Error('Invalid pairing details.');
  }
  stop();
  child = null; // the old process's exit handler ignores it from here on
  writeLink({ apiUrl: apiUrl.replace(/\/+$/, ''), token, tokenId, userId: String(userId) });
  return start();
}

function unpair() {
  stop();
  fs.rmSync(linkFile(), { force: true });
  setStatus({ state: 'unpaired', message: '' });
  return getStatus();
}

function init(onChange) {
  notify = onChange;
  if (readLink()) start();
}

module.exports = { init, start, stop, pair, unpair, getStatus };
