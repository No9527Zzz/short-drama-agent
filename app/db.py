from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "short_drama.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL,
                target_episodes INTEGER NOT NULL DEFAULT 80,
                episode_duration_seconds INTEGER NOT NULL DEFAULT 60,
                aspect_ratio TEXT NOT NULL DEFAULT '9:16',
                width INTEGER NOT NULL DEFAULT 1080,
                height INTEGER NOT NULL DEFAULT 1920,
                fps INTEGER NOT NULL DEFAULT 25,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                version INTEGER NOT NULL,
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_source_project
                ON source_documents(project_id, is_current);
            CREATE TABLE IF NOT EXISTS episode_plans (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                logline TEXT NOT NULL DEFAULT '',
                plot_summary TEXT NOT NULL DEFAULT '',
                key_conflict TEXT NOT NULL DEFAULT '',
                ending_hook TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                plan_version INTEGER NOT NULL,
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_episode_plan_project
                ON episode_plans(project_id, is_current, episode_number);
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                role_type TEXT NOT NULL DEFAULT 'supporting',
                voice_name TEXT NOT NULL DEFAULT '',
                reference_image_path TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_characters_project
                ON characters(project_id, is_current);
            CREATE TABLE IF NOT EXISTS locations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                time_of_day TEXT NOT NULL DEFAULT '',
                reference_image_path TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_locations_project
                ON locations(project_id, is_current);
            CREATE TABLE IF NOT EXISTS episode_scripts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                synopsis TEXT NOT NULL DEFAULT '',
                dialogue_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                script_version INTEGER NOT NULL DEFAULT 1,
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_episode_scripts_project
                ON episode_scripts(project_id, is_current, episode_number);
            CREATE TABLE IF NOT EXISTS script_scenes (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                scene_number INTEGER NOT NULL,
                location_name TEXT NOT NULL DEFAULT '',
                time_of_day TEXT NOT NULL DEFAULT '',
                character_names_json TEXT NOT NULL DEFAULT '[]',
                action_text TEXT NOT NULL DEFAULT '',
                dialogue_text TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (script_id) REFERENCES episode_scripts(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_script_scenes_script
                ON script_scenes(script_id, scene_number);
            """
        )
    init_storyboard_tables()
    init_media_tables()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_storyboard_tables() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS storyboards (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                storyboard_version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                is_current INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_storyboards_project
                ON storyboards(project_id, episode_number, is_current);
            CREATE TABLE IF NOT EXISTS shots (
                id TEXT PRIMARY KEY,
                storyboard_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                shot_number INTEGER NOT NULL,
                scene_number INTEGER NOT NULL,
                shot_type TEXT NOT NULL DEFAULT '中景',
                camera TEXT NOT NULL DEFAULT '固定',
                duration_seconds INTEGER NOT NULL DEFAULT 10,
                visual_description TEXT NOT NULL DEFAULT '',
                action_text TEXT NOT NULL DEFAULT '',
                dialogue_text TEXT NOT NULL DEFAULT '',
                character_names_json TEXT NOT NULL DEFAULT '[]',
                location_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (storyboard_id) REFERENCES storyboards(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_shots_storyboard
                ON shots(storyboard_id, shot_number);
            """
        )


def init_media_tables() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS media_assets (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                shot_number INTEGER NOT NULL,
                asset_type TEXT NOT NULL DEFAULT 'image',
                file_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'uploaded',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_media_assets_shot
                ON media_assets(project_id, episode_number, shot_number);
            CREATE TABLE IF NOT EXISTS generation_tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                shot_number INTEGER NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_generation_tasks_project
                ON generation_tasks(project_id, status, created_at);
            """
        )

