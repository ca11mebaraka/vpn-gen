import type { TelegramPayload } from './types'

export function normalizeTelegram(raw: unknown): TelegramPayload | null {
  if (!raw || typeof raw !== 'object') return null
  const value = raw as Record<string, unknown>
  const id = Number(value.id)
  const authDate = Number(value.auth_date)
  if (!Number.isFinite(id) || !Number.isFinite(authDate) || typeof value.hash !== 'string' || !value.hash) return null
  return {
    id,
    auth_date: authDate,
    hash: value.hash,
    first_name: typeof value.first_name === 'string' ? value.first_name : undefined,
    last_name: typeof value.last_name === 'string' ? value.last_name : undefined,
    username: typeof value.username === 'string' ? value.username : undefined,
    photo_url: typeof value.photo_url === 'string' ? value.photo_url : undefined,
  }
}

export function telegramFromHash(): TelegramPayload | null {
  try {
    const match = (location.hash || '').match(/[#?&]tgAuthResult=([A-Za-z0-9\-_=]*)$/)
    if (!match) return null
    history.replaceState(null, '', location.pathname + location.search)
    let data = match[1].replace(/-/g, '+').replace(/_/g, '/')
    data += '='.repeat((4 - (data.length % 4)) % 4)
    return normalizeTelegram(JSON.parse(atob(data)))
  } catch {
    return null
  }
}

export function redirectTelegram(botId: string, bridgeOrigin: string) {
  const params = new URLSearchParams({
    bot_id: botId,
    origin: bridgeOrigin,
    request_access: 'write',
    return_to: `${bridgeOrigin}/myvpn-telegram-relay`,
  })
  window.location.assign(`https://oauth.telegram.org/auth?${params}`)
}
