"""Explicit, local-only removal of stored alert history; never detector state, devices or other telemetry."""
import sqlite3
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class ClearHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["run", "all"]
    run_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    confirmation: Literal["CLEAR ALERT HISTORY"]


def install_history(app, db_path, require_local):
    @app.post("/api/alerts/history/clear", dependencies=[Depends(require_local)])
    def clear_history(body: ClearHistory, request: Request):
        origin = request.headers.get("origin")
        if origin and (urlparse(origin).netloc != request.headers.get("host") or urlparse(origin).scheme != request.url.scheme):
            raise HTTPException(403, "history changes require the same origin")
        if (body.scope == "run") != bool(body.run_id):
            raise HTTPException(422, "select one session or all history")
        path = Path(db_path).resolve()
        if {"models", "results", "raw", "reference", "engineering", "reports"}.intersection(p.lower() for p in path.parts):
            raise HTTPException(403, "protected evidence cannot be changed")
        db = None
        try:
            # rw refuses to create a missing store; identifiers are fixed, values bound.
            db = sqlite3.connect(f"file:{path.as_posix()}?mode=rw", uri=True, timeout=5)
            db.execute("BEGIN IMMEDIATE")
            # Every session, including the current one: the Alerts page lists all history, so a partial clear left visible alerts behind.
            # alerts mirrors events(event_type='alert'); both go in one transaction. Windows, markers, resources and control stay.
            where, args = ("run_id=?", [body.run_id]) if body.run_id else ("1=1", [])
            ids = [r[0] for r in db.execute("SELECT alert_id FROM alerts WHERE " + where, args)]
            db.execute("DELETE FROM alerts WHERE " + where, args)
            count = db.execute("DELETE FROM events WHERE event_type='alert' AND " + where, args).rowcount
            db.commit()
            return {"deleted_alert_ids": ids, "deleted_events": count, "remaining_alerts": db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]}
        except sqlite3.Error:
            raise HTTPException(503, "alert history could not be changed; retry later")
        finally:
            if db:
                db.close()
