from __future__ import annotations

import re
import sqlite3
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import ROOT, get_connection, init_db, utc_now
from .schemas import (
    EpisodePlan,
    EpisodePlanUpdate,
    PlanningSummary,
    ProjectCreate,
    ProjectSummary,
    SourceCreate,
    SourceSummary,
)

app = FastAPI(title="Short Drama Agent", version="0.2.0")
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


def row_to_source(row: sqlite3.Row) -> SourceSummary:
    data = dict(row)
    data["is_current"] = bool(data["is_current"])
    return SourceSummary(**data)


def row_to_plan(row: sqlite3.Row) -> EpisodePlan:
    data = dict(row)
    data["is_current"] = bool(data["is_current"])
    return EpisodePlan(**data)


def require_project(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return row


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
        row = require_project(connection, project_id)
    return row_to_project(row)


@app.get("/api/projects/{project_id}/source", response_model=SourceSummary | None)
def get_current_source(project_id: str) -> SourceSummary | None:
    with get_connection() as connection:
        require_project(connection, project_id)
        row = connection.execute(
            """
            SELECT * FROM source_documents
            WHERE project_id = ? AND is_current = 1
            ORDER BY version DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return row_to_source(row) if row else None


@app.post("/api/projects/{project_id}/source", response_model=SourceSummary, status_code=201)
def import_source(project_id: str, payload: SourceCreate) -> SourceSummary:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="原始内容不能为空")
    now = utc_now()
    with get_connection() as connection:
        project = require_project(connection, project_id)
        source_type = payload.source_type or project["source_type"]
        latest = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM source_documents WHERE project_id = ?",
            (project_id,),
        ).fetchone()["version"]
        connection.execute(
            "UPDATE source_documents SET is_current = 0 WHERE project_id = ?",
            (project_id,),
        )
        source_id = uuid4().hex
        connection.execute(
            """
            INSERT INTO source_documents
                (id, project_id, source_type, title, content, version, is_current, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                source_id,
                project_id,
                source_type,
                payload.title.strip() or "未命名原始内容",
                content,
                latest + 1,
                now,
            ),
        )
        connection.execute(
            "UPDATE projects SET status = 'source_imported', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
        row = connection.execute(
            "SELECT * FROM source_documents WHERE id = ?", (source_id,)
        ).fetchone()
    return row_to_source(row)


def content_units(content: str) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", content) if item.strip()]
    if len(paragraphs) == 1:
        paragraphs = [item.strip() for item in re.split(r"\n+", content) if item.strip()]
    if len(paragraphs) == 1 and len(paragraphs[0]) > 280:
        text = paragraphs[0]
        paragraphs = [text[index:index + 240] for index in range(0, len(text), 240)]
    return paragraphs or ["待补充故事内容"]


def build_episode(episode_number: int, units: list[str], total: int) -> tuple[str, str, str, str, str]:
    source = units[(episode_number - 1) % len(units)]
    short_source = source.replace("\r", " ").replace("\n", " ").strip()[:240]
    if episode_number == 1:
        title = "开端：主角进入核心冲突"
    elif episode_number == total:
        title = "终局：主线收束"
    elif episode_number % 10 == 0:
        title = f"阶段节点：第{episode_number}集"
    else:
        title = f"推进：第{episode_number}集"
    if episode_number <= len(units):
        logline = short_source
        summary = f"围绕原始内容展开：{short_source}"
    else:
        logline = "待扩写：根据整剧主线补充本集核心事件。"
        summary = "本集尚未从原始内容中提取到独立情节，需要在审核阶段补充人物行动、冲突和结果。"
    conflict = "待确认本集主要冲突与人物目标。"
    hook = "待确认本集结尾的情绪落点或后续悬念。"
    return title, logline, summary, conflict, hook


@app.post("/api/projects/{project_id}/planning/generate", response_model=PlanningSummary)
def generate_planning(project_id: str) -> PlanningSummary:
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        source = connection.execute(
            """
            SELECT * FROM source_documents
            WHERE project_id = ? AND is_current = 1
            ORDER BY version DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if source is None:
            raise HTTPException(status_code=400, detail="请先导入剧本、小说或创意内容")
        current_version = connection.execute(
            "SELECT COALESCE(MAX(plan_version), 0) AS version FROM episode_plans WHERE project_id = ?",
            (project_id,),
        ).fetchone()["version"]
        plan_version = current_version + 1
        connection.execute(
            "UPDATE episode_plans SET is_current = 0 WHERE project_id = ?",
            (project_id,),
        )
        total = connection.execute(
            "SELECT target_episodes FROM projects WHERE id = ?", (project_id,)
        ).fetchone()["target_episodes"]
        units = content_units(source["content"])
        for episode_number in range(1, total + 1):
            title, logline, summary, conflict, hook = build_episode(
                episode_number, units, total
            )
            connection.execute(
                """
                INSERT INTO episode_plans
                    (id, project_id, episode_number, title, logline, plot_summary,
                     key_conflict, ending_hook, status, plan_version, is_current,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, 1, ?, ?)
                """,
                (
                    uuid4().hex,
                    project_id,
                    episode_number,
                    title,
                    logline,
                    summary,
                    conflict,
                    hook,
                    plan_version,
                    now,
                    now,
                ),
            )
        connection.execute(
            "UPDATE projects SET status = 'planning', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
    return PlanningSummary(
        project_id=project_id,
        plan_version=plan_version,
        episode_count=total,
        source_version=source["version"],
        status="draft",
    )


@app.get("/api/projects/{project_id}/planning", response_model=list[EpisodePlan])
def list_planning(project_id: str) -> list[EpisodePlan]:
    with get_connection() as connection:
        require_project(connection, project_id)
        rows = connection.execute(
            """
            SELECT * FROM episode_plans
            WHERE project_id = ? AND is_current = 1
            ORDER BY episode_number
            """,
            (project_id,),
        ).fetchall()
    return [row_to_plan(row) for row in rows]


@app.patch("/api/projects/{project_id}/planning/{episode_number}", response_model=EpisodePlan)
def update_episode_plan(
    project_id: str, episode_number: int, payload: EpisodePlanUpdate
) -> EpisodePlan:
    if episode_number < 1:
        raise HTTPException(status_code=422, detail="集数必须大于 0")
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        current = connection.execute(
            """
            SELECT * FROM episode_plans
            WHERE project_id = ? AND episode_number = ? AND is_current = 1
            """,
            (project_id, episode_number),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="该集规划不存在")
        connection.execute(
            """
            UPDATE episode_plans
            SET title = ?, logline = ?, plot_summary = ?, key_conflict = ?,
                ending_hook = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.title.strip(),
                payload.logline.strip(),
                payload.plot_summary.strip(),
                payload.key_conflict.strip(),
                payload.ending_hook.strip(),
                payload.status,
                now,
                current["id"],
            ),
        )
        connection.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id)
        )
        row = connection.execute(
            "SELECT * FROM episode_plans WHERE id = ?", (current["id"],)
        ).fetchone()
    return row_to_plan(row)

