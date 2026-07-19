import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, ArrowDown, ArrowUp, Check, ChevronRight, CircleGauge, Copy, Download,
  FileKey2, KeyRound, Laptop, LayoutDashboard, LogOut, Menu, MoreHorizontal,
  Plus, Power, RefreshCw, Router, Server, ShieldCheck, Smartphone, Tablet,
  Terminal, UserRound, Users, X, Zap,
} from 'lucide-react'
import { api, ApiError } from './api'
import { redirectTelegram, telegramFromHash } from './auth'
import type { Client, Credential, Server as ServerType, TelegramPayload } from './types'

type View = 'overview' | 'devices' | 'audit'
type Toast = { id: number; message: string; kind?: 'error' | 'success' }

const formatBytes = (value: number) => {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  return `${(value / 1024 ** index).toFixed(index > 1 ? 1 : 0)} ${units[index]}`
}

const timeAgo = (timestamp: number) => {
  if (!timestamp) return 'Никогда'
  const seconds = Math.max(0, Date.now() / 1000 - timestamp)
  if (seconds < 90) return 'Только что'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} мин назад`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч назад`
  return `${Math.floor(seconds / 86400)} дн назад`
}

const online = (client: Client) => client.enabled && Date.now() / 1000 - client.latest_handshake < 180

function DeviceIcon({ type }: { type: string }) {
  const Icon = type === 'iphone' || type === 'android' ? Smartphone : type === 'tablet' ? Tablet : Laptop
  return <Icon size={16} strokeWidth={1.8} />
}

function Login({ onLogin }: { onLogin: () => Promise<void> }) {
  const [botId, setBotId] = useState('')
  const [bridgeOrigin, setBridgeOrigin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const exchange = useCallback(async (payload: TelegramPayload) => {
    setBusy(true); setError('')
    try {
      await api('/auth/telegram', { method: 'POST', body: JSON.stringify(payload) })
      await onLogin()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось войти')
    } finally { setBusy(false) }
  }, [onLogin])

  useEffect(() => {
    const returned = telegramFromHash()
    if (returned) {
      if (window.opener && window.opener !== window) {
        window.opener.postMessage({ type: 'myvpn:telegram-auth', payload: returned }, location.origin)
        window.close(); return
      }
      void exchange(returned); return
    }
    api<{ bot_id: string; auth_bridge_origin: string }>('/auth/config').then(config => { setBotId(config.bot_id); setBridgeOrigin(config.auth_bridge_origin) }).catch(error => setError(error.message))
  }, [exchange])

  return <div className="login-shell">
    <div className="login-grid" />
    <div className="login-card">
      <div className="login-brand"><Logo /><span>MyVPN</span></div>
      <div className="login-copy"><div className="eyebrow">SECURE CONTROL CENTER</div><h1>Ваша сеть.<br />Под контролем.</h1><p>Управление приватной VPN-инфраструктурой и устройствами из единого пространства.</p></div>
      <button className="telegram-button" disabled={!botId || !bridgeOrigin || busy} onClick={() => redirectTelegram(botId, bridgeOrigin)}>
        <TelegramMark />{busy ? 'Проверяем доступ…' : 'Продолжить через Telegram'}<ChevronRight size={17} />
      </button>
      {error && <div className="login-error">{error}</div>}
      <div className="login-security"><ShieldCheck size={14} /><span>Доступ ограничен администратором системы</span></div>
    </div>
  </div>
}

function Logo() { return <div className="logo"><Zap size={17} fill="currentColor" /></div> }
function TelegramMark() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M21.944 2.506a1.13 1.13 0 0 0-1.161-.134L2.153 9.568c-.89.343-.864 1.614.04 1.92l4.773 1.614 1.854 5.973c.267.862 1.374 1.1 1.976.426l2.67-2.99 4.846 3.553c.69.506 1.672.113 1.83-.73L22.47 3.57a1.13 1.13 0 0 0-.526-1.064ZM9.98 13.77l-.7 3.56-1.136-3.664 8.882-6.806-7.046 6.91Z" /></svg> }

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [servers, setServers] = useState<ServerType[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [view, setView] = useState<View>('overview')
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [credential, setCredential] = useState<Credential | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])

  const notify = useCallback((message: string, kind: Toast['kind'] = 'success') => {
    const id = Date.now(); setToasts(current => [...current, { id, message, kind }])
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 3500)
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [status, peers] = await Promise.all([api<{ servers: ServerType[] }>('/status'), api<{ clients: Client[] }>('/clients')])
      setServers(status.servers); setClients(peers.clients)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setAuthenticated(false)
      else notify(error instanceof Error ? error.message : 'Ошибка обновления', 'error')
    } finally { setLoading(false) }
  }, [notify])

  const enter = useCallback(async () => { await api('/me'); setAuthenticated(true); await refresh() }, [refresh])
  useEffect(() => { void enter().catch(() => setAuthenticated(false)) }, [enter])
  useEffect(() => { if (!authenticated) return; const timer = window.setInterval(() => void refresh(), 30_000); return () => clearInterval(timer) }, [authenticated, refresh])

  if (authenticated === null) return <div className="splash"><Logo /><span>MyVPN</span></div>
  if (!authenticated) return <Login onLogin={enter} />

  const active = clients.filter(online).length
  const traffic = clients.reduce((sum, client) => sum + client.received_bytes + client.sent_bytes, 0)
  const allHealthy = servers.length === 3 && servers.every(server => server.online && !server.failed_units)

  const logout = async () => { await api('/logout', { method: 'POST' }); setAuthenticated(false) }
  const action = async (client: Client, operation: string) => {
    if ((operation === 'disable' || operation === 'rotate') && !confirm(`${operation === 'disable' ? 'Отключить' : 'Заменить ключ для'} ${client.name}?`)) return
    try { await api(`/clients/${client.name}/${operation}`, { method: 'POST' }); notify('Операция выполнена'); await refresh() }
    catch (error) { notify(error instanceof Error ? error.message : 'Ошибка операции', 'error') }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="sidebar-logo"><Logo /></div>
      <nav>
        <NavButton icon={LayoutDashboard} label="Обзор" active={view === 'overview'} onClick={() => setView('overview')} />
        <NavButton icon={Users} label="Устройства" active={view === 'devices'} onClick={() => setView('devices')} />
        <NavButton icon={Terminal} label="Аудит" active={view === 'audit'} onClick={() => setView('audit')} />
      </nav>
      <button className="nav-button sidebar-logout" title="Выйти" onClick={() => void logout()}><LogOut size={18} /></button>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <div className="breadcrumb"><span>MyVPN</span><ChevronRight size={13} /><strong>{view === 'overview' ? 'Обзор' : view === 'devices' ? 'Устройства' : 'Аудит'}</strong></div>
        <div className="top-actions"><div className={`system-pill ${allHealthy ? 'healthy' : 'warning'}`}><span className="pulse" />{allHealthy ? 'Все системы работают' : 'Требуется внимание'}</div><button className="icon-button" onClick={() => void refresh()} title="Обновить"><RefreshCw size={16} className={loading ? 'spin' : ''} /></button><button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={16} />Создать доступ</button></div>
      </header>
      <main>
        {view === 'overview' && <Overview servers={servers} clients={clients} active={active} traffic={traffic} onViewDevices={() => setView('devices')} onAction={action} />}
        {view === 'devices' && <Devices clients={clients} onAction={action} onCreate={() => setCreateOpen(true)} />}
        {view === 'audit' && <Audit />}
      </main>
    </div>
    {createOpen && <CreateModal onClose={() => setCreateOpen(false)} onCreated={result => { setCreateOpen(false); setCredential(result); void refresh() }} notify={notify} />}
    {credential && <CredentialModal credential={credential} onClose={() => setCredential(null)} notify={notify} />}
    <div className="toast-stack">{toasts.map(item => <div key={item.id} className={`toast ${item.kind}`}><Check size={15} />{item.message}</div>)}</div>
  </div>
}

function NavButton({ icon: Icon, label, active, onClick }: { icon: typeof Menu; label: string; active: boolean; onClick: () => void }) {
  return <button className={`nav-button ${active ? 'active' : ''}`} title={label} onClick={onClick}><Icon size={18} /><span>{label}</span></button>
}

function Overview({ servers, clients, active, traffic, onViewDevices, onAction }: { servers: ServerType[]; clients: Client[]; active: number; traffic: number; onViewDevices: () => void; onAction: (client: Client, action: string) => void }) {
  return <>
    <section className="page-heading"><div><div className="eyebrow">ИНФРАСТРУКТУРА</div><h1>Сеть под контролем</h1><p>Каскадный маршрут и подключённые устройства в реальном времени.</p></div><div className="heading-time">Автообновление · 30 сек</div></section>
    <section className="summary-grid">
      <Summary icon={Router} label="Узлы сети" value={`${servers.filter(s => s.online).length}/${servers.length}`} note="доступны" tone="green" />
      <Summary icon={Activity} label="Устройства" value={String(active)} note={`из ${clients.length} онлайн`} tone="blue" />
      <Summary icon={CircleGauge} label="Общий трафик" value={formatBytes(traffic)} note="за текущую сессию" tone="violet" />
      <Summary icon={ShieldCheck} label="Защита" value="Active" note="fail-closed · IPv6 off" tone="amber" />
    </section>
    <section className="panel infrastructure-panel"><PanelTitle title="VPN-каскад" subtitle="Состояние маршрута" /><div className="cascade">{servers.map((server, index) => <div className="cascade-fragment" key={server.name}><ServerNode server={server} />{index < servers.length - 1 && <div className="connection"><span /><small>{index === 0 ? 'SSH control' : 'WireGuard'}</small></div>}</div>)}</div></section>
    <section className="panel devices-panel"><div className="panel-heading"><PanelTitle title="Последние устройства" subtitle="Активность клиентов" /><button className="text-button" onClick={onViewDevices}>Все устройства<ChevronRight size={14} /></button></div><DeviceTable clients={clients.slice(0, 5)} onAction={onAction} /></section>
  </>
}

function Summary({ icon: Icon, label, value, note, tone }: { icon: typeof Router; label: string; value: string; note: string; tone: string }) { return <div className="summary-card"><div className={`summary-icon ${tone}`}><Icon size={17} /></div><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div> }
function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="panel-title"><h2>{title}</h2><span>{subtitle}</span></div> }

function ServerNode({ server }: { server: ServerType }) { return <div className={`server-node ${server.online ? '' : 'down'}`}><div className="server-icon"><Server size={18} /></div><div className="server-copy"><div><strong>{server.name}</strong><span className={`status-dot ${server.online ? 'online' : ''}`} /></div><code>{server.host}</code></div><div className="server-metrics"><span><b>{server.latency_ms ? `${server.latency_ms}ms` : 'local'}</b> latency</span><span><b>{server.memory ?? '—'}{typeof server.memory === 'number' ? '%' : ''}</b> memory</span><span><b>{server.disk || '—'}</b> disk</span></div></div> }

function Devices({ clients, onAction, onCreate }: { clients: Client[]; onAction: (client: Client, action: string) => void; onCreate: () => void }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => clients.filter(client => `${client.owner} ${client.name} ${client.address}`.toLowerCase().includes(query.toLowerCase())), [clients, query])
  return <><section className="page-heading compact"><div><div className="eyebrow">ДОСТУП</div><h1>Пользователи и устройства</h1><p>Ключи, подключения и трафик каждого клиента.</p></div></section><section className="panel"><div className="table-toolbar"><div className="search"><Activity size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Поиск по имени или IP" /></div><button className="primary-button" onClick={onCreate}><Plus size={16} />Новое устройство</button></div><DeviceTable clients={filtered} onAction={onAction} /></section></>
}

function DeviceTable({ clients, onAction }: { clients: Client[]; onAction: (client: Client, action: string) => void }) {
  return <div className="device-table"><div className="device-row table-head"><span>УСТРОЙСТВО</span><span>VPN ADDRESS</span><span>СТАТУС</span><span>ПОСЛЕДНИЙ ВХОД</span><span>ТРАФИК</span><span /></div>{clients.map(client => <div className="device-row" key={client.public_key}><div className="device-identity"><div className="device-icon"><DeviceIcon type={client.device_type} /></div><div><strong>{client.owner}</strong><span>{client.name}</span></div></div><code>{client.address.replace('/32', '')}</code><div><span className={`state-badge ${online(client) ? 'online' : client.enabled ? 'idle' : 'disabled'}`}><i />{online(client) ? 'Онлайн' : client.enabled ? 'Офлайн' : 'Отключён'}</span></div><span className="secondary-text">{timeAgo(client.latest_handshake)}</span><div className="traffic"><span><ArrowDown size={12} />{formatBytes(client.received_bytes)}</span><span><ArrowUp size={12} />{formatBytes(client.sent_bytes)}</span></div><div className="row-actions">{client.managed ? <><button title={client.enabled ? 'Отключить' : 'Включить'} onClick={() => onAction(client, client.enabled ? 'disable' : 'enable')}><Power size={15} /></button><button title="Заменить ключ" onClick={() => onAction(client, 'rotate')}><KeyRound size={15} /></button></> : <span className="managed-label">ANSIBLE</span>}<button title="Ещё"><MoreHorizontal size={16} /></button></div></div>)}</div>
}

function Audit() { const [events, setEvents] = useState<Array<Record<string, unknown>>>([]); useEffect(() => { api<{ events: Array<Record<string, unknown>> }>('/audit').then(data => setEvents(data.events)) }, []); return <><section className="page-heading compact"><div><div className="eyebrow">БЕЗОПАСНОСТЬ</div><h1>Журнал действий</h1><p>Неизменяемая история административных операций.</p></div></section><section className="panel audit-list">{events.length ? events.map((event, i) => <div className="audit-item" key={i}><div className="audit-icon"><Terminal size={15} /></div><div><strong>{String(event.action)}</strong><span>{String(event.target)}</span></div><time>{new Date(String(event.created_at)).toLocaleString('ru')}</time></div>) : <div className="empty-state">Событий пока нет</div>}</section></> }

function CreateModal({ onClose, onCreated, notify }: { onClose: () => void; onCreated: (credential: Credential) => void; notify: (message: string, kind?: Toast['kind']) => void }) {
  const [owner, setOwner] = useState(''); const [device, setDevice] = useState(''); const [type, setType] = useState('iphone'); const [busy, setBusy] = useState(false)
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); try { onCreated(await api('/clients', { method: 'POST', body: JSON.stringify({ owner, device, device_type: type }) })) } catch (error) { notify(error instanceof Error ? error.message : 'Ошибка создания', 'error'); setBusy(false) } }
  return <Modal onClose={onClose}><form onSubmit={submit}><div className="modal-heading"><div className="modal-icon"><UserRound size={20} /></div><div><h2>Новый VPN-доступ</h2><p>Отдельный ключ для нового устройства</p></div><button type="button" onClick={onClose}><X size={18} /></button></div><div className="form-grid"><label><span>Пользователь</span><input autoFocus required pattern="[a-z0-9-]{2,24}" value={owner} onChange={e => setOwner(e.target.value.toLowerCase())} placeholder="ivan" /><small>Латиница, цифры и дефис</small></label><label><span>Название устройства</span><input required pattern="[a-z0-9-]{2,24}" value={device} onChange={e => setDevice(e.target.value.toLowerCase())} placeholder="iphone-15" /></label><label className="full"><span>Тип устройства</span><div className="device-types">{[['iphone','iPhone',Smartphone],['mac','Mac',Laptop],['android','Android',Smartphone],['windows','Windows',Laptop],['tablet','Планшет',Tablet]].map(([value,label,Icon]) => { const TypeIcon=Icon as typeof Smartphone; return <button type="button" key={value as string} className={type === value ? 'selected' : ''} onClick={() => setType(value as string)}><TypeIcon size={17} /><span>{label as string}</span></button> })}</div></label></div><div className="modal-footer"><button type="button" className="secondary-button" onClick={onClose}>Отмена</button><button className="primary-button" disabled={busy}><FileKey2 size={16} />{busy ? 'Создаём…' : 'Создать доступ'}</button></div></form></Modal>
}

function CredentialModal({ credential, onClose, notify }: { credential: Credential; onClose: () => void; notify: (message: string) => void }) {
  const download = () => { const url = URL.createObjectURL(new Blob([credential.config], { type: 'text/plain' })); const anchor = document.createElement('a'); anchor.href=url; anchor.download=`${credential.name}.conf`; anchor.click(); URL.revokeObjectURL(url) }
  const copy = async () => { await navigator.clipboard.writeText(credential.config); notify('Конфигурация скопирована') }
  return <Modal onClose={onClose}><div className="credential"><div className="success-mark"><Check size={24} /></div><h2>Доступ создан</h2><p><code>{credential.name}</code> готов к подключению</p><div className="credential-layout"><div className="qr-card"><img src={credential.qr} alt="WireGuard QR" /><span>iPhone / Android</span><small>Отсканируйте в приложении WireGuard</small></div><div className="file-card"><FileKey2 size={34} /><strong>WireGuard Config</strong><span>{credential.name}.conf</span><button className="primary-button" onClick={download}><Download size={15} />Скачать файл</button><button className="secondary-button" onClick={() => void copy()}><Copy size={15} />Копировать</button></div></div><div className="security-note"><ShieldCheck size={16} /><span>QR и файл содержат приватный ключ. Передавайте их только владельцу устройства.</span></div><button className="done-button" onClick={onClose}>Готово</button></div></Modal>
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><div className="modal">{children}</div></div> }

export default App
