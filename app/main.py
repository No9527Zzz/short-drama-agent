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



import json
from .parser import parse_source
from .schemas import (
    CharacterAsset,
    EpisodeScript,
    LocationAsset,
    ParseSummary,
    ScriptScene,
)


def row_to_character(row: sqlite3.Row) -> CharacterAsset:
    data = dict(row)
    data["is_current"] = bool(data["is_current"])
    return CharacterAsset(**data)


def row_to_location(row: sqlite3.Row) -> LocationAsset:
    data = dict(row)
    data["is_current"] = bool(data["is_current"])
    return LocationAsset(**data)


def row_to_script(row: sqlite3.Row) -> EpisodeScript:
    data = dict(row)
    data["is_current"] = bool(data["is_current"])
    return EpisodeScript(**data)


def row_to_scene(row: sqlite3.Row) -> ScriptScene:
    data = dict(row)
    data["character_names"] = json.loads(data["character_names_json"])
    del data["character_names_json"]
    return ScriptScene(**data)


@app.post("/api/projects/{project_id}/parse", response_model=ParseSummary)
def parse_project_source(project_id: str) -> ParseSummary:
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
            raise HTTPException(status_code=400, detail="请先导入原始内容")
        parsed = parse_source(source["content"])
        connection.execute(
            "UPDATE characters SET is_current = 0 WHERE project_id = ?",
            (project_id,),
        )
        connection.execute(
            "UPDATE locations SET is_current = 0 WHERE project_id = ?",
            (project_id,),
        )
        for character in parsed.characters:
            connection.execute(
                """
                INSERT INTO characters
                    (id, project_id, name, description, role_type, voice_name,
                     reference_image_path, version, is_current, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', '', 1, 1, ?, ?)
                """,
                (
                    uuid4().hex, project_id, character.name, character.description,
                    character.role_type, now, now,
                ),
            )
        for location in parsed.locations:
            connection.execute(
                """
                INSERT INTO locations
                    (id, project_id, name, description, time_of_day,
                     reference_image_path, version, is_current, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', 1, 1, ?, ?)
                """,
                (
                    uuid4().hex, project_id, location.name, location.description,
                    location.time_of_day, now, now,
                ),
            )
        connection.execute(
            "UPDATE episode_scripts SET is_current = 0 WHERE project_id = ?",
            (project_id,),
        )
        plans = connection.execute(
            """
            SELECT * FROM episode_plans
            WHERE project_id = ? AND is_current = 1
            ORDER BY episode_number
            """,
            (project_id,),
        ).fetchall()
        script_rows = []
        for plan in plans:
            script_id = uuid4().hex
            connection.execute(
                """
                INSERT INTO episode_scripts
                    (id, project_id, episode_number, title, synopsis, dialogue_text,
                     status, script_version, is_current, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', 'draft', 1, 1, ?, ?)
                """,
                (
                    script_id, project_id, plan["episode_number"], plan["title"],
                    plan["plot_summary"], now, now,
                ),
            )
            script_rows.append((script_id, plan["episode_number"], plan["plot_summary"]))
        connection.execute(
            "DELETE FROM script_scenes WHERE project_id = ?", (project_id,)
        )
        template_scene = parsed.scenes[0]
        for script_id, episode_number, summary in script_rows:
            scene = parsed.scenes[(episode_number - 1) % len(parsed.scenes)]
            source_text = scene.source_text or summary
            connection.execute(
                """
                INSERT INTO script_scenes
                    (id, script_id, project_id, episode_number, scene_number,
                     location_name, time_of_day, character_names_json, action_text,
                     dialogue_text, source_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex, script_id, project_id, episode_number,
                    scene.location_name or template_scene.location_name,
                    scene.time_of_day,
                    json.dumps(scene.character_names, ensure_ascii=False),
                    scene.action_text or "待补充分镜动作。",
                    scene.dialogue_text,
                    source_text,
                    now, now,
                ),
            )
        connection.execute(
            "UPDATE projects SET status = 'parsed', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
    return ParseSummary(
        project_id=project_id,
        source_version=source["version"],
        character_count=len(parsed.characters),
        location_count=len(parsed.locations),
        scene_count=len(parsed.scenes),
        script_count=len(script_rows),
    )


@app.get("/api/projects/{project_id}/characters", response_model=list[CharacterAsset])
def list_characters(project_id: str) -> list[CharacterAsset]:
    with get_connection() as connection:
        require_project(connection, project_id)
        rows = connection.execute(
            """
            SELECT * FROM characters
            WHERE project_id = ? AND is_current = 1 ORDER BY name
            """,
            (project_id,),
        ).fetchall()
    return [row_to_character(row) for row in rows]


@app.get("/api/projects/{project_id}/locations", response_model=list[LocationAsset])
def list_locations(project_id: str) -> list[LocationAsset]:
    with get_connection() as connection:
        require_project(connection, project_id)
        rows = connection.execute(
            """
            SELECT * FROM locations
            WHERE project_id = ? AND is_current = 1 ORDER BY name
            """,
            (project_id,),
        ).fetchall()
    return [row_to_location(row) for row in rows]


@app.get("/api/projects/{project_id}/scripts", response_model=list[EpisodeScript])
def list_scripts(project_id: str) -> list[EpisodeScript]:
    with get_connection() as connection:
        require_project(connection, project_id)
        rows = connection.execute(
            """
            SELECT * FROM episode_scripts
            WHERE project_id = ? AND is_current = 1
            ORDER BY episode_number
            """,
            (project_id,),
        ).fetchall()
    return [row_to_script(row) for row in rows]


@app.get("/api/projects/{project_id}/scripts/{episode_number}/scenes", response_model=list[ScriptScene])
def list_script_scenes(project_id: str, episode_number: int) -> list[ScriptScene]:
    with get_connection() as connection:
        require_project(connection, project_id)
        rows = connection.execute(
            """
            SELECT * FROM script_scenes
            WHERE project_id = ? AND episode_number = ?
            ORDER BY scene_number
            """,
            (project_id, episode_number),
        ).fetchall()
    return [row_to_scene(row) for row in rows]



from .schemas import (
    CharacterUpdate,
    EpisodeScriptUpdate,
    LocationUpdate,
    ScriptSceneUpdate,
)


@app.patch("/api/projects/{project_id}/characters/{character_id}", response_model=CharacterAsset)
def update_character(
    project_id: str, character_id: str, payload: CharacterUpdate
) -> CharacterAsset:
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        current = connection.execute(
            "SELECT * FROM characters WHERE id = ? AND project_id = ? AND is_current = 1",
            (character_id, project_id),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="角色不存在")
        connection.execute(
            """
            UPDATE characters
            SET name = ?, description = ?, role_type = ?, voice_name = ?,
                reference_image_path = ?, version = version + 1, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(), payload.description.strip(), payload.role_type.strip(),
                payload.voice_name.strip(), payload.reference_image_path.strip(), now,
                character_id,
            ),
        )
        connection.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id)
        )
        row = connection.execute(
            "SELECT * FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
    return row_to_character(row)


@app.patch("/api/projects/{project_id}/locations/{location_id}", response_model=LocationAsset)
def update_location(
    project_id: str, location_id: str, payload: LocationUpdate
) -> LocationAsset:
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        current = connection.execute(
            "SELECT * FROM locations WHERE id = ? AND project_id = ? AND is_current = 1",
            (location_id, project_id),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="场景不存在")
        connection.execute(
            """
            UPDATE locations
            SET name = ?, description = ?, time_of_day = ?,
                reference_image_path = ?, version = version + 1, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(), payload.description.strip(), payload.time_of_day.strip(),
                payload.reference_image_path.strip(), now, location_id,
            ),
        )
        connection.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id)
        )
        row = connection.execute(
            "SELECT * FROM locations WHERE id = ?", (location_id,)
        ).fetchone()
    return row_to_location(row)


@app.patch("/api/projects/{project_id}/scripts/{episode_number}", response_model=EpisodeScript)
def update_episode_script(
    project_id: str, episode_number: int, payload: EpisodeScriptUpdate
) -> EpisodeScript:
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        current = connection.execute(
            """
            SELECT * FROM episode_scripts
            WHERE project_id = ? AND episode_number = ? AND is_current = 1
            """,
            (project_id, episode_number),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="单集剧本不存在")
        connection.execute(
            """
            UPDATE episode_scripts
            SET title = ?, synopsis = ?, dialogue_text = ?, status = ?,
                script_version = script_version + 1, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.title.strip(), payload.synopsis.strip(),
                payload.dialogue_text.strip(), payload.status, now, current["id"],
            ),
        )
        connection.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id)
        )
        row = connection.execute(
            "SELECT * FROM episode_scripts WHERE id = ?", (current["id"],)
        ).fetchone()
    return row_to_script(row)


@app.patch(
    "/api/projects/{project_id}/scripts/{episode_number}/scenes/{scene_number}",
    response_model=ScriptScene,
)
def update_script_scene(
    project_id: str,
    episode_number: int,
    scene_number: int,
    payload: ScriptSceneUpdate,
) -> ScriptScene:
    now = utc_now()
    with get_connection() as connection:
        require_project(connection, project_id)
        current = connection.execute(
            """
            SELECT * FROM script_scenes
            WHERE project_id = ? AND episode_number = ? AND scene_number = ?
            """,
            (project_id, episode_number, scene_number),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="场景不存在")
        connection.execute(
            """
            UPDATE script_scenes
            SET location_name = ?, time_of_day = ?, character_names_json = ?,
                action_text = ?, dialogue_text = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.location_name.strip(), payload.time_of_day.strip(),
                json.dumps(payload.character_names, ensure_ascii=False),
                payload.action_text.strip(), payload.dialogue_text.strip(), now,
                current["id"],
            ),
        )
        connection.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id)
        )
        row = connection.execute(
            "SELECT * FROM script_scenes WHERE id = ?", (current["id"],)
        ).fetchone()
    return row_to_scene(row)

