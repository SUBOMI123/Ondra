/**
 * Talks to apps/api. The access token lives only in memory; the refresh token is an httpOnly cookie the browser
 * sends to /auth on the API, so a page reload restores the session without exposing either token to scripts.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

let accessToken: string | null = null

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

export async function refresh(): Promise<boolean> {
  const r = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" }).catch(() => null)
  if (!r || !r.ok) return false
  accessToken = (await r.json()).access_token
  return true
}

export async function logout(): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => null)
  accessToken = null
}

export async function api<T>(path: string): Promise<T> {
  const go = () =>
    fetch(`${API_URL}${path}`, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
  let r = await go()
  if (r.status === 401 && (await refresh())) r = await go()
  if (!r.ok) throw await readError(r)
  return r.json()
}

/** Writes (POST, PUT, PATCH, DELETE) with the same sign-in refresh as `api`. */
export async function send<T = unknown>(method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const go = () =>
    fetch(`${API_URL}${path}`, {
      method,
      headers: {
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
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

export type Me = { id: string; email: string; name: string; role: string; tenant_id: string; tenant_name: string }
export type Page<T> = { items: T[]; total: number }
export type Contact = {
  id: string
  display_name: string
  is_vip: boolean
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
