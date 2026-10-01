function isolatedPort(name, fallback) {
  const value = String(process.env[name] ?? fallback)
  if (!/^\d+$/.test(value) || Number(value) < 1024 || Number(value) > 65535) {
    throw new Error('Invalid isolated P4 browser port')
  }
  return Number(value)
}

export const backendPort = isolatedPort('PROJECT_COLLABORATION_BACKEND_PORT', 3212)
export const frontendPort = isolatedPort('PROJECT_COLLABORATION_FRONTEND_PORT', 3213)
export const backendUrl = `http://127.0.0.1:${backendPort}`
export const frontendUrl = `http://127.0.0.1:${frontendPort}`
