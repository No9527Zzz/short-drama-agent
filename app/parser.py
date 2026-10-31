from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedCharacter:
    name: str
    description: str = ""
    role_type: str = "supporting"


@dataclass
class ParsedLocation:
    name: str
    description: str = ""
    time_of_day: str = ""


@dataclass
class ParsedScene:
    scene_number: int
    location_name: str
    time_of_day: str
    character_names: list[str] = field(default_factory=list)
    action_text: str = ""
    dialogue_text: str = ""
    source_text: str = ""


@dataclass
class ParsedSource:
    characters: list[ParsedCharacter]
    locations: list[ParsedLocation]
    scenes: list[ParsedScene]


SCENE_PATTERN = re.compile(
    r"^(?:场景|场次|地点)\s*[:：]\s*(?P<location>[^，,；;]+)"
    r"(?:[，,；;]\s*(?P<time>.+))?$"
)
CHARACTERS_PATTERN = re.compile(r"^(?:人物|角色)\s*[:：]\s*(?P<names>.+)$")
DIALOGUE_PATTERN = re.compile(r"^(?P<name>[^：:\s]{1,20})\s*[:：]\s*(?P<text>.+)$")


def _unique(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def parse_source(content: str) -> ParsedSource:
    characters: dict[str, ParsedCharacter] = {}
    locations: dict[str, ParsedLocation] = {}
    scenes: list[ParsedScene] = []
    current_scene: ParsedScene | None = None
    pending_actions: list[str] = []

    def ensure_scene() -> ParsedScene:
        nonlocal current_scene
        if current_scene is None:
            current_scene = ParsedScene(
                scene_number=len(scenes) + 1,
                location_name="待设定场景",
                time_of_day="",
            )
            scenes.append(current_scene)
        return current_scene

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        scene_match = SCENE_PATTERN.match(line)
        if scene_match:
            if current_scene and pending_actions:
                current_scene.action_text = " ".join(pending_actions).strip()
                pending_actions.clear()
            location = scene_match.group("location").strip()
            time = (scene_match.group("time") or "").strip()
            current_scene = ParsedScene(
                scene_number=len(scenes) + 1,
                location_name=location,
                time_of_day=time,
            )
            scenes.append(current_scene)
            locations.setdefault(location, ParsedLocation(name=location, time_of_day=time))
            continue

        character_match = CHARACTERS_PATTERN.match(line)
        if character_match:
            for name in re.split(r"[、,，/；; ]+", character_match.group("names")):
                if name.strip():
                    characters.setdefault(name.strip(), ParsedCharacter(name=name.strip()))
            continue

        dialogue_match = DIALOGUE_PATTERN.match(line)
        if dialogue_match and not line.startswith(("时间：", "地点：", "备注：")):
            scene = ensure_scene()
            name = dialogue_match.group("name").strip()
            text = dialogue_match.group("text").strip()
            characters.setdefault(name, ParsedCharacter(name=name))
            scene.character_names.append(name)
            scene.dialogue_text = (scene.dialogue_text + "\n" + f"{name}：{text}").strip()
            continue

        scene = ensure_scene()
        pending_actions.append(line)
        scene.source_text = (scene.source_text + "\n" + line).strip()

    if current_scene and pending_actions:
        current_scene.action_text = " ".join(pending_actions).strip()

    for scene in scenes:
        scene.character_names = _unique(scene.character_names)
        if not scene.source_text:
            scene.source_text = scene.action_text or scene.dialogue_text

    if not characters and content.strip():
        characters["待识别角色"] = ParsedCharacter(
            name="待识别角色",
            description="原始内容中尚未识别出明确角色标记，需要人工补充。",
        )
    if not locations and content.strip():
        locations["待设定场景"] = ParsedLocation(
            name="待设定场景",
            description="原始内容中尚未识别出明确场景标记，需要人工补充。",
        )
    return ParsedSource(
        characters=list(characters.values()),
        locations=list(locations.values()),
        scenes=scenes or [ParsedScene(1, "待设定场景", "")],
    )

