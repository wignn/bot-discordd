const LEVELS: Record<string, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

let currentLevel = 1;

export function setLogLevel(level: string) {
  currentLevel = LEVELS[level] ?? 1;
}

function fmt(level: string, tag: string, msg: string, extra?: Record<string, unknown>): string {
  const ts = new Date().toISOString();
  const base = `${ts} [${level.toUpperCase()}] [${tag}] ${msg}`;
  if (extra && Object.keys(extra).length) {
    return `${base} ${JSON.stringify(extra)}`;
  }
  return base;
}

export function debug(tag: string, msg: string, extra?: Record<string, unknown>) {
  if (currentLevel <= 0) console.log(fmt("debug", tag, msg, extra));
}

export function info(tag: string, msg: string, extra?: Record<string, unknown>) {
  if (currentLevel <= 1) console.log(fmt("info", tag, msg, extra));
}

export function warn(tag: string, msg: string, extra?: Record<string, unknown>) {
  if (currentLevel <= 2) console.warn(fmt("warn", tag, msg, extra));
}

export function error(tag: string, msg: string, extra?: Record<string, unknown>) {
  if (currentLevel <= 3) console.error(fmt("error", tag, msg, extra));
}
