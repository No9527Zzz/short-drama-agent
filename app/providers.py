from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
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
class CommandImageGenerator:
    command_template: str

    def generate(self, prompt: str, output_path: Path, reference_images: list[Path]) -> Path:
        reference = str(reference_images[0]) if reference_images else ""
        command = self.command_template.format(
            prompt=prompt,
            output=str(output_path),
            reference=reference,
        )
        result = subprocess.run(
            shlex.split(command, posix=False),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "本地图片命令执行失败")
        if not output_path.exists():
            raise RuntimeError("图片 Provider 未生成输出文件")
        return output_path


@dataclass
class UnconfiguredImageGenerator:
    reason: str = "未配置本地图片模型 Provider"

    def generate(self, prompt: str, output_path: Path, reference_images: list[Path]) -> Path:
        raise RuntimeError(self.reason)


class WindowsSapiSpeechSynthesizer:
    def synthesize(self, text: str, voice: str, output_path: Path) -> Path:
        if os.name != "nt":
            raise RuntimeError("Windows SAPI 配音 Provider 只能在 Windows 上运行")
        script = """
param($Text, $Voice, $OutputPath)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) {
  $match = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq $Voice } | Select-Object -First 1
  if ($match) { $synth.SelectVoice($Voice) }
}
$synth.SetOutputToWaveFile($OutputPath)
$synth.Speak($Text)
$synth.Dispose()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            script_path = Path(handle.name)
        try:
            command = [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path), text, voice or "", str(output_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Windows SAPI 配音失败")
            if not output_path.exists():
                raise RuntimeError("Windows SAPI 未生成音频文件")
            return output_path
        finally:
            script_path.unlink(missing_ok=True)


@dataclass
class UnconfiguredSpeechSynthesizer:
    reason: str = "未配置本地 TTS Provider"

    def synthesize(self, text: str, voice: str, output_path: Path) -> Path:
        raise RuntimeError(self.reason)


def get_image_generator() -> ImageGenerator:
    command = os.getenv("SHORT_DRAMA_IMAGE_COMMAND", "").strip()
    return CommandImageGenerator(command) if command else UnconfiguredImageGenerator()


def get_speech_synthesizer() -> SpeechSynthesizer:
    provider = os.getenv("SHORT_DRAMA_TTS_PROVIDER", "sapi").lower()
    if provider == "sapi":
        return WindowsSapiSpeechSynthesizer()
    return UnconfiguredSpeechSynthesizer()

