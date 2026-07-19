export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(data.detail || `HTTP ${response.status}`, response.status)
  return data as T
}
