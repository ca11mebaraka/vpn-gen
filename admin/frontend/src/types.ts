export type Server = {
  name: string
  host: string
  online: boolean
  uptime?: string
  firewall?: string
  failed_units?: number
  disk?: string
  memory?: number
  latency_ms?: number
  load?: number
  error?: string
}

export type Client = {
  public_key: string
  endpoint: string | null
  address: string
  latest_handshake: number
  received_bytes: number
  sent_bytes: number
  name: string
  owner: string
  device_type: string
  enabled: boolean
  managed: boolean
}

export type Credential = { name: string; config: string; qr: string }

export type TelegramPayload = {
  id: number
  auth_date: number
  hash: string
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
}
