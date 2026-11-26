"use client"

/**
 * Live updates from GET /live (server-sent events). Read with fetch so the access token travels in a header, not
 * the URL. Each change names a table and ids only; the caller decides which queries to refresh. Reconnects with
 * backoff, refreshing the sign-in when the token has expired.
 */

import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo } from "react"

import { API_URL, currentToken, refresh } from "@/lib/api"

export type Change = { table: "messages" | "tasks" | "conversations"; id: string; conversation_id: string | null }

export function useLiveUpdates(onChange: (c: Change) => void) {
  useEffect(() => {
    let stopped = false
    let ctrl: AbortController | null = null
    let delay = 1000

    async function connect() {
      while (!stopped) {
        ctrl = new AbortController()
        try {
          const token = currentToken()
          const r = await fetch(`${API_URL}/live`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            signal: ctrl.signal,
          })
          if (r.status === 401) {
            await refresh()
            throw new Error("signed out")
          }
          if (!r.ok || !r.body) throw new Error(`live ${r.status}`)
          delay = 1000
          const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
          let buffer = ""
          for (;;) {
            const { value, done } = await reader.read()
            if (done) break
            buffer += value
            let end
            while ((end = buffer.indexOf("\n\n")) >= 0) {
              const chunk = buffer.slice(0, end)
              buffer = buffer.slice(end + 2)
              const data = chunk.split("\n").find((l) => l.startsWith("data: "))
              if (data) {
                try {
                  onChange(JSON.parse(data.slice(6)) as Change)
                } catch {
                  /* ignore a malformed notice */
                }
              }
            }
          }
        } catch {
          if (stopped) return
        }
        await new Promise((res) => setTimeout(res, delay))
        delay = Math.min(delay * 2, 30000)
      }
    }
    connect()
    return () => {
      stopped = true
      ctrl?.abort()
    }
  }, [onChange])
}

/** Refresh the inbox, open threads and tasks when their data changes. A burst of changes refreshes once. */
export function useLiveInbox() {
  const qc = useQueryClient()
  const handler = useMemo(() => {
    let timer: ReturnType<typeof setTimeout> | null = null
    const conversations = new Set<string>()
    let tasks = false
    return (c: Change) => {
      if (c.conversation_id) conversations.add(c.conversation_id)
      if (c.table === "tasks") tasks = true
      if (timer) return
      timer = setTimeout(() => {
        timer = null
        qc.invalidateQueries({ queryKey: ["conversations"] })
        conversations.forEach((id) => qc.invalidateQueries({ queryKey: ["conversation", id] }))
        if (tasks) qc.invalidateQueries({ queryKey: ["tasks"] })
        conversations.clear()
        tasks = false
      }, 300)
    }
  }, [qc])
  useLiveUpdates(handler)
}
