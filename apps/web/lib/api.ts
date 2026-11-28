/**
 * Talks to apps/api. The access token lives only in memory; the refresh token is an httpOnly cookie the browser
 * sends to /auth on the API, so a page reload restores the session without exposing either token to scripts.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

let accessToken: string | null = null

/** Sign-in provider: "local" (Ondra's own, for development and tests) or "clerk". */
export const CLERK = process.env.NEXT_PUBLIC_AUTH_PROVIDER === "clerk"

// With Clerk, tokens come from Clerk's session (short-lived, refreshed by Clerk); set by the Clerk bridge.
let tokenSource: (() => Promise<string | null>) | null = null
export function setTokenSource(fn: (() => Promise<string | null>) | null) {
  tokenSource = fn
}

/** The token to send now, whichever provider is in use. */
export async function authToken(): Promise<string | null> {
  return tokenSource ? tokenSource() : accessToken
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function readError(r: Response): Promise<ApiError> {
  const body = await r.json().catch(() => null)
  const detail = body?.detail
  // Validation errors come back as a list; show the first one as a plain sentence.
  const message = Array.isArray(detail)
    ? String(detail[0]?.msg ?? "Check the form.").replace(/^Value error, /, "")
    : (detail ?? `Request failed (${r.status})`)
  return new ApiError(r.status, message)
}

export async function login(email: string, password: string): Promise<void> {
  const r = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!r.ok) throw await readError(r)
  accessToken = (await r.json()).access_token
}

/** Trade the refresh cookie for a new access token. Returns false when there is no live session. */
/** The current access token, for requests `api`/`send` can't make (the live stream). */
export function currentToken(): string | null {
  return accessToken
}

// The refresh cookie is single-use (the API rotates it), so requests that all find the token missing at once (a
// page load fires several) share one refresh. Separate refreshes would race, the losers would fail with a spent
// cookie, and the person would be sent to sign in again.
let refreshing: Promise<boolean> | null = null

export async function refresh(): Promise<boolean> {
  if (tokenSource) return (await tokenSource()) !== null
  refreshing ??= (async () => {
    const r = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" }).catch(() => null)
    if (!r || !r.ok) return false
    accessToken = (await r.json()).access_token
    return true
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

export async function logout(): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => null)
  accessToken = null
}

export async function api<T>(path: string): Promise<T> {
  const go = async () => {
    const token = await authToken()
    return fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  }
  let r = await go()
  if (r.status === 401 && (await refresh())) r = await go()
  if (!r.ok) throw await readError(r)
  return r.json()
}

/** Writes (POST, PUT, PATCH, DELETE) with the same sign-in refresh as `api`. */
export async function send<T = unknown>(method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const go = async () => {
    const token = await authToken()
    return fetch(`${API_URL}${path}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }
  let r = await go()
  if (r.status === 401 && (await refresh())) r = await go()
  if (!r.ok) throw await readError(r)
  return (r.status === 204 ? undefined : await r.json()) as T
}

/** For the invite page: set a password from an invite link (no sign-in). */
export async function acceptInvite(token: string, password: string): Promise<void> {
  const r = await fetch(`${API_URL}/auth/accept-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  })
  if (!r.ok) throw await readError(r)
}

export type Me = {
  id: string
  email: string
  name: string
  role: string
  tenant_id: string
  tenant_name: string
  timezone: string
  phone: string | null
  // Clerk: their role needs two-step sign-in and this session didn't use it
  mfa_required?: boolean
}
export type Page<T> = { items: T[]; total: number }
export type Contact = {
  id: string
  display_name: string
  is_vip: boolean
  vip_owner_user_id?: string | null
  /** Where the name came from: "call" means as Ondra heard it on a phone call (may be misspelt), "typed", "staff". */
  name_source?: "call" | "typed" | "staff" | null
  preferred_channel: string | null
  language: string | null
  tags: string[]
  identities: { kind: string; value: string }[]
  created_at: string
}
export type Vehicle = {
  id: string
  stock_number: string
  vin: string | null
  year: number
  make: string
  model: string
  trim: string | null
  price: string | null
  mileage: number | null
  status: "available" | "hold" | "sold"
}
