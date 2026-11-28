"use client"

/**
 * Team. One job: find anyone on the team fast, then change their access or invite someone new.
 * Built for dealerships of any size: search by name, email or mobile; filter by status and role; 25 per page,
 * all done by the API. Roles are Ondra's; with Clerk they're mirrored onto the Clerk Organization.
 */

import { IconArrowLeft, IconPlus, IconSearch } from "@tabler/icons-react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { useAuth } from "@/components/providers"
import { assignableRoles, canManageTeam, InviteForm, ROLE_LABEL, TeamRows, type TeamData } from "@/components/settings/team"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, ApiError } from "@/lib/api"

const PER_PAGE = 25
type Status = "active" | "invited" | "deactivated"
const STATUS_LABEL: Record<Status, string> = { active: "Active", invited: "Invited", deactivated: "Deactivated" }

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export default function TeamPage() {
  const { me } = useAuth()
  const [q, setQ] = useState("")
  const [status, setStatus] = useState<Status>("active")
  const [role, setRole] = useState("all")
  const [page, setPage] = useState(0)
  const [inviting, setInviting] = useState(false)
  const search = useDebounced(q)
  // A new search or filter starts at the first page.
  useEffect(() => {
    setPage(0)
  }, [search, status, role])

  const params = new URLSearchParams({ status, limit: String(PER_PAGE), offset: String(page * PER_PAGE) })
  if (search.trim()) params.set("q", search.trim())
  if (role !== "all") params.set("role", role)
  const team = useQuery({
    queryKey: ["users", "page", params.toString()],
    queryFn: () => api<TeamData>(`/users?${params}`),
    placeholderData: keepPreviousData,
    retry: false,
  })
  const canManage = canManageTeam(me)
  const counts = team.data?.counts
  const total = team.data?.total ?? 0
  const from = total === 0 ? 0 : page * PER_PAGE + 1
  const to = Math.min(total, (page + 1) * PER_PAGE)
  const filtered = !!search.trim() || role !== "all"

  return (
    <>
      <SiteHeader title="Team" />
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-6 lg:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/settings" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <IconArrowLeft className="size-4" aria-hidden="true" /> Settings
          </Link>
          {canManage && !inviting && (
            <Button onClick={() => setInviting(true)}>
              <IconPlus /> Invite teammate
            </Button>
          )}
        </div>
        {inviting && <InviteForm assignable={assignableRoles(me)} onDone={() => setInviting(false)} />}

        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative min-w-0 flex-1">
            <IconSearch className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name, email or mobile"
              aria-label="Search the team"
              className="pl-9"
              type="search"
            />
          </div>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="w-full md:w-44" aria-label="Role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All roles</SelectItem>
              {Object.entries(ROLE_LABEL).map(([r, label]) => (
                <SelectItem key={r} value={r}>
                  {label}
                  {counts?.role[r] ? ` (${counts.role[r]})` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Tabs value={status} onValueChange={(v) => setStatus(v as Status)}>
          <TabsList>
            {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
              <TabsTrigger key={s} value={s}>
                {STATUS_LABEL[s]}
                {counts && <span className="ml-1.5 text-muted-foreground tabular-nums">{counts.status[s]}</span>}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {team.isPending ? (
          <TableSkeleton rows={8} />
        ) : team.isError ? (
          team.error instanceof ApiError && team.error.status === 403 ? (
            <p className="rounded-xl border p-6 text-sm text-muted-foreground">Only admins and managers can see the team.</p>
          ) : (
            <LoadError message={team.error.message} onRetry={() => team.refetch()} />
          )
        ) : team.data.items.length === 0 ? (
          <div className="rounded-xl border p-6 text-sm">
            {filtered ? (
              <>
                <p className="font-medium">Nobody matches</p>
                <p className="mt-1 text-muted-foreground">Try part of their name, their email, or the last digits of their mobile.</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => { setQ(""); setRole("all") }}>
                  Clear search
                </Button>
              </>
            ) : (
              <p className="text-muted-foreground">
                {status === "invited" ? "No invitations waiting." : status === "deactivated" ? "Nobody has been deactivated." : "No one here yet."}
              </p>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3" aria-busy={team.isFetching || undefined}>
            <TeamRows users={team.data.items} me={me} />
            {total > PER_PAGE && (
              <nav aria-label="Pages" className="flex items-center justify-between gap-3 text-sm">
                <span className="text-muted-foreground tabular-nums">
                  {from} to {to} of {total}
                </span>
                <span className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={to >= total} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </span>
              </nav>
            )}
          </div>
        )}
      </div>
    </>
  )
}
