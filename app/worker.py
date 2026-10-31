from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .db import ROOT, get_connection, utc_now
from .providers import get_speech_synthesizer

_worker_started = False
_worker_lock = threading.Lock()


def ffmpeg_path() -> str | None:
    configured = os.getenv("SHORT_DRAMA_FFMPEG")
    if configured and Path(configured).exists():
        return configured
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def start_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        recover_stale_tasks()
        _worker_started = True
        threading.Thread(target=worker_loop, name="short-drama-worker", daemon=True).start()


def recover_stale_tasks() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE generation_tasks
            SET status = 'queued', progress = 0, error_message = '服务重启后自动恢复',
                updated_at = ?
            WHERE status = 'running'
              AND updated_at < datetime('now', '-10 minutes')
            """,
            (utc_now(),),
        )


def worker_loop() -> None:
    while True:
        try:
            task = claim_task()
            if task:
                process_task(task)
            else:
                time.sleep(1)
        except Exception:
            time.sleep(2)


def claim_task() -> dict | None:
    with get_connection() as connection:
        task = connection.execute(
            "SELECT * FROM generation_tasks WHERE status = 'queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if task is None:
            return None
        now = utc_now()
        connection.execute(
            """
            UPDATE generation_tasks
            SET status = 'running', progress = 1, error_message = '', updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (now, task["id"]),
        )
        claimed = connection.execute(
            "SELECT * FROM generation_tasks WHERE id = ?", (task["id"],)
        ).fetchone()
    return dict(claimed) if claimed else None


def is_cancelled(task_id: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT status FROM generation_tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return row is None or row["status"] == "cancelled"


def update_task(task_id: str, status: str, progress: int, error: str = "") -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE generation_tasks
            SET status = ?, progress = ?, error_message = ?, updated_at = ?
            WHERE id = ? AND status != 'cancelled'
            """,
            (status, progress, error, utc_now(), task_id),
        )


def process_task(task: dict) -> None:
    try:
        if is_cancelled(task["id"]):
            return
        if task["task_type"] == "compose_episode":
            compose_episode(task)
        elif task["task_type"] == "image_generation":
            raise RuntimeError("尚未配置本地图片模型适配器，请先上传镜头图片")
        elif task["task_type"] == "speech_generation":
            generate_speech(task)
        else:
            raise RuntimeError(f"不支持的任务类型：{task['task_type']}")
    except Exception as exc:
        update_task(task["id"], "failed", 0, str(exc))


def generate_speech(task: dict) -> None:
    project_id = task["project_id"]
    episode_number = task["episode_number"]
    shot_number = task["shot_number"]
    with get_connection() as connection:
        shot = connection.execute(
            """
            SELECT dialogue_text FROM shots
            WHERE project_id = ? AND episode_number = ? AND shot_number = ?
              AND storyboard_id IN (SELECT id FROM storyboards WHERE is_current = 1)
            """,
            (project_id, episode_number, shot_number),
        ).fetchone()
    if shot is None or not shot["dialogue_text"].strip():
        raise RuntimeError("该镜头没有对白")
    output_dir = ROOT / "data" / "media" / project_id / f"episode_{episode_number:03d}" / f"shot_{shot_number:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{task['id']}.wav"
    get_speech_synthesizer().synthesize(shot["dialogue_text"].strip(), "", output_path)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO media_assets
                (id, project_id, episode_number, shot_number, asset_type,
                 file_name, relative_path, mime_type, status, metadata_json, created_at)
            VALUES (?, ?, ?, ?, 'audio', ?, ?, 'audio/wav', 'generated', '{}', ?)
            """,
            (
                task["id"] + "-audio", project_id, episode_number, shot_number,
                output_path.name,
                str(output_path.relative_to(ROOT / "data")).replace("\\", "/"),
                utc_now(),
            ),
        )
    update_task(task["id"], "succeeded", 100)


def get_audio_assets(connection, project_id: str, episode_number: int) -> dict[int, str]:
    rows = connection.execute(
        """
        SELECT shot_number, relative_path FROM media_assets
        WHERE project_id = ? AND episode_number = ? AND shot_number > 0
          AND asset_type = 'audio' AND status IN ('uploaded', 'generated')
        ORDER BY created_at
        """,
        (project_id, episode_number),
    ).fetchall()
    assets = {}
    for row in rows:
        assets.setdefault(row["shot_number"], str(ROOT / "data" / row["relative_path"]))
    return assets

def get_image_assets(connection, project_id: str, episode_number: int) -> dict[int, str]:
    rows = connection.execute(
        """
        SELECT shot_number, relative_path FROM media_assets
        WHERE project_id = ? AND episode_number = ? AND shot_number > 0
          AND asset_type = 'image' AND status = 'uploaded'
        ORDER BY created_at
        """,
        (project_id, episode_number),
    ).fetchall()
    assets = {}
    for row in rows:
        assets.setdefault(row["shot_number"], str(ROOT / "data" / row["relative_path"]))
    return assets


def write_srt(shots: list, output_path: Path) -> None:
    cursor = 0
    lines = []
    for index, shot in enumerate(shots, start=1):
        dialogue = (shot["dialogue_text"] or "").strip()
        if dialogue:
            lines.extend([
                str(index),
                f"{format_timestamp(cursor)} --> {format_timestamp(cursor + shot['duration_seconds'])}",
                dialogue,
                "",
            ])
        cursor += shot["duration_seconds"]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_timestamp(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"


def subtitle_filter(path: Path) -> str:
    escaped = path.as_posix().replace(":", "\\:")
    return f"subtitles='{escaped}'"


def compose_episode(task: dict) -> None:
    binary = ffmpeg_path()
    if not binary:
        raise RuntimeError("未找到 FFmpeg。请安装 FFmpeg，或设置 SHORT_DRAMA_FFMPEG。")
    project_id = task["project_id"]
    episode_number = task["episode_number"]
    with get_connection() as connection:
        storyboard = connection.execute(
            "SELECT id FROM storyboards WHERE project_id = ? AND episode_number = ? AND is_current = 1",
            (project_id, episode_number),
        ).fetchone()
        if storyboard is None:
            raise RuntimeError("该集没有当前分镜")
        shots = connection.execute(
            "SELECT * FROM shots WHERE storyboard_id = ? ORDER BY shot_number",
            (storyboard["id"],),
        ).fetchall()
        images = get_image_assets(connection, project_id, episode_number)
        audios = get_audio_assets(connection, project_id, episode_number)
    if not shots:
        raise RuntimeError("该集没有镜头")
    missing = [shot["shot_number"] for shot in shots if shot["shot_number"] not in images]
    if missing:
        raise RuntimeError("缺少镜头图片：" + "、".join(map(str, missing)))

    export_dir = ROOT / "data" / "media" / project_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_dir / f"episode_{episode_number:03d}.mp4"
    subtitle_path = export_dir / f"episode_{episode_number:03d}.srt"
    temp_dir = Path(tempfile.mkdtemp(prefix="short-drama-", dir=str(export_dir)))
    try:
        write_srt(shots, subtitle_path)
        clips = []
        for index, shot in enumerate(shots, start=1):
            if is_cancelled(task["id"]):
                return
            clip_path = temp_dir / f"shot_{index:02d}.mp4"
            frames = shot["duration_seconds"] * 25
            filter_expression = (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                f"zoompan=z='min(zoom+0.0015,1.08)':d={frames}:s=1080x1920:fps=25"
            )
            command = [
                binary, "-y", "-loop", "1", "-i", images[shot["shot_number"]],
            ]
            if shot["shot_number"] in audios:
                command += ["-i", audios[shot["shot_number"]]]
            command += ["-frames:v", str(frames), "-vf", filter_expression]
            if shot["shot_number"] in audios:
                command += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-c:a", "aac", "-shortest"]
            else:
                command += ["-an", "-c:v", "libx264"]
            command += ["-pix_fmt", "yuv420p", str(clip_path)]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-1200:])
            clips.append(clip_path)
            update_task(task["id"], "running", min(80, 5 + index * 10))
        concat_path = temp_dir / "concat.txt"
        concat_path.write_text(
            "\n".join(f"file '{clip.as_posix()}'" for clip in clips),
            encoding="utf-8",
        )
        filter_expression = subtitle_filter(subtitle_path) if subtitle_path.stat().st_size else "null"
        command = [
            binary, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", filter_expression, "-shortest", "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-r", "25", "-movflags", "+faststart",
            str(output_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1200:])
        with get_connection() as connection:
            now = utc_now()
            connection.execute(
                """
                INSERT OR IGNORE INTO media_assets
                    (id, project_id, episode_number, shot_number, asset_type,
                     file_name, relative_path, mime_type, status, metadata_json, created_at)
                VALUES (?, ?, ?, 0, 'video', ?, ?, 'video/mp4', 'generated', ?, ?)
                """,
                (
                    task["id"] + "-video", project_id, episode_number,
                    output_path.name,
                    str(output_path.relative_to(ROOT / "data")).replace("\\", "/"),
                    json.dumps({"subtitle_path": str(subtitle_path.relative_to(ROOT / "data")).replace("\\", "/")}, ensure_ascii=False),
                    now,
                ),
            )
        update_task(task["id"], "succeeded", 100)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)





