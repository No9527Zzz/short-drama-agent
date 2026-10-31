from __future__ import annotations

import sqlite3
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import ROOT, get_connection, init_db, utc_now
from .schemas import ProjectCreate, ProjectSummary

app = FastAPI(title="Short Drama Agent", version="0.1.0")
STATIC_DIR = ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "short-drama-agent"}


def row_to_project(row: sqlite3.Row) -> ProjectSummary:
    return ProjectSummary(**dict(row))


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall()
    return [row_to_project(row) for row in rows]


@app.post("/api/projects", response_model=ProjectSummary, status_code=201)
def create_project(payload: ProjectCreate) -> ProjectSummary:
    project_id = uuid4().hex
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO projects (
                id, name, description, source_type, target_episodes,
                episode_duration_seconds, aspect_ratio, width, height, fps,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 80, 60, '9:16', 1080, 1920, 25, 'draft', ?, ?)
            """,
            (
                project_id,
                payload.name.strip(),
                payload.description.strip(),
                payload.source_type,
                now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    return row_to_project(row)


@app.get("/api/projects/{project_id}", response_model=ProjectSummary)
def get_project(project_id: str) -> ProjectSummary:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return row_to_project(row)
