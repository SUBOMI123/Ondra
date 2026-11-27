"""Integrations (BUILD_PLAN.md §8, Step 7): inventory import, the CRM lead push and the DMS, with their health."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from ondra_core.inventory_feed import MAX_BYTES
from ondra_core.permissions import Perm, has_perm
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, get_db
from ondra_api.services.inventory import import_inventory

router = APIRouter(tags=["integrations"])


class ImportIn(BaseModel):
    filename: str = Field("", max_length=200)
    content: str = Field(max_length=MAX_BYTES + 1024)  # the file's text; CSV or XML
    # This file is every car on the lot: feed cars it doesn't list are marked sold. Off: only add and update.
    whole_lot: bool = False
    dry_run: bool = True  # say what would change without changing it


def _may_import(caller: Caller) -> None:
    if not (has_perm(caller.role, Perm.VEHICLES_WRITE) or has_perm(caller.role, Perm.INTEGRATIONS_MANAGE)):
        raise HTTPException(403, "Only owners, admins and managers can import inventory.")


@router.post("/inventory/import")
async def import_file(body: ImportIn, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """Preview (`dry_run`) or apply an inventory file. A file that can't be read at all is a 422 with the reason."""
    caller, db = ctx
    _may_import(caller)
    out = await import_inventory(db, body.content, body.filename, source="upload", whole_lot=body.whole_lot,
                                 dry_run=body.dry_run, user_id=caller.user_id)
    if not out["ok"]:
        if not body.dry_run:
            await db.commit()  # keep the failed attempt on the integration's health before answering
        raise HTTPException(422, out["error"])
    return out
