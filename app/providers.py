from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ImageGenerator(Protocol):
    def generate(self, prompt: str, output_path: Path, reference_images: list[Path]) -> Path:
        ...


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str, voice: str, output_path: Path) -> Path:
        ...


@dataclass
class UnconfiguredImageGenerator:
    reason: str = "未配置本地图片模型 Provider"

    def generate(self, prompt: str, output_path: Path, reference_images: list[Path]) -> Path:
        raise RuntimeError(self.reason)


@dataclass
class UnconfiguredSpeechSynthesizer:
    reason: str = "未配置本地 TTS Provider"

    def synthesize(self, text: str, voice: str, output_path: Path) -> Path:
        raise RuntimeError(self.reason)


def get_image_generator() -> ImageGenerator:
    return UnconfiguredImageGenerator()


def get_speech_synthesizer() -> SpeechSynthesizer:
    return UnconfiguredSpeechSynthesizer()

