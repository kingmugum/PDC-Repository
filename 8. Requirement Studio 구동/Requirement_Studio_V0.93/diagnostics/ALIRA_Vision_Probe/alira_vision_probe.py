from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config() -> dict:
    path = project_root() / "config" / "provider_config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def alira_exe() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    return Path(local_app_data) / "Programs" / "alira" / "alira.exe"


def make_fixture(path: Path) -> Path:
    """Create a deterministic Vision-only test card.

    The facts below intentionally do not exist in the accompanying text prompt.
    A model must actually receive/inspect the image to answer all questions.
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
    except Exception as exc:
        raise RuntimeError("PySide6가 필요합니다. Requirement Studio 실행환경에서 다시 시도하세요.") from exc

    image = QImage(900, 520, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(QFont("Arial", 22, QFont.Weight.Bold))
    painter.setPen(QPen(QColor("#0F172A"), 2))
    painter.drawText(40, 55, "ALIRA VISION PROBE / R7K-42")

    # STATE_A blue rectangle
    painter.setBrush(QColor("#3B82F6"))
    painter.setPen(QPen(QColor("#1D4ED8"), 3))
    painter.drawRoundedRect(70, 135, 240, 110, 16, 16)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(125, 205, "STATE_A")

    # STATE_B red circle
    painter.setBrush(QColor("#EF4444"))
    painter.setPen(QPen(QColor("#B91C1C"), 3))
    painter.drawEllipse(590, 125, 145, 145)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(608, 205, "STATE_B")

    # Green arrow A -> B
    painter.setPen(QPen(QColor("#16A34A"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(335, 190, 555, 190)
    painter.drawLine(555, 190, 520, 165)
    painter.drawLine(555, 190, 520, 215)

    # Star to the right of circle (simple star character)
    painter.setFont(QFont("Arial", 44, QFont.Weight.Bold))
    painter.setPen(QColor("#F59E0B"))
    painter.drawText(775, 205, "★")

    # Small table-like facts
    painter.setFont(QFont("Arial", 20))
    painter.setPen(QColor("#0F172A"))
    painter.drawRect(175, 335, 550, 105)
    painter.drawLine(175, 388, 725, 388)
    painter.drawLine(430, 335, 430, 440)
    painter.drawText(200, 372, "Timeout")
    painter.drawText(480, 372, "3.7 s")
    painter.drawText(200, 425, "Mode")
    painter.drawText(480, 425, "VISION_ONLY")
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Fixture 저장 실패: {path}")
    return path


def inspect_environment() -> int:
    cfg = load_config().get("alira", {})
    exe = alira_exe()
    print("[ALIRA Vision Probe / inspect]")
    print(f"Project Root : {project_root()}")
    print(f"ALIRA EXE    : {exe} ({'FOUND' if exe.is_file() else 'NOT FOUND'})")
    print(f"Model        : {cfg.get('model')}")
    print(f"API Base     : {cfg.get('api_base')}")
    print(f"Main Flag    : supports_images={cfg.get('supports_images', False)}")
    if not exe.is_file():
        return 2
    try:
        result = subprocess.run(
            [str(exe), "--help"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20,
        )
        help_text = (result.stdout or "") + "\n" + (result.stderr or "")
        candidates = ["--image", "--images", "--file", "--attachment", "--input-file"]
        found = [flag for flag in candidates if flag in help_text]
        print("Possible image/file flags:", ", ".join(found) if found else "none detected")
        help_out = Path(__file__).with_name("last_alira_help.txt")
        help_out.write_text(help_text, encoding="utf-8")
        print(f"Saved help   : {help_out}")
    except Exception as exc:
        print(f"--help inspection failed: {exc}")
        return 3
    return 0


def vision_prompt() -> str:
    return (
        "첨부 이미지 자체만 보고 다음 항목을 한 줄 JSON으로 답하세요. "
        "이미지를 받지 못했으면 추측하지 말고 IMAGE_NOT_RECEIVED라고 답하세요. "
        "질문: code, arrow_color, arrow_direction, timeout, star_position, mode."
    )


def direct_api_test(image_path: Path, api_key_env: str) -> int:
    import requests

    cfg = load_config().get("alira", {})
    base = str(cfg.get("api_base") or "").rstrip("/")
    model = str(cfg.get("model") or "")
    if not base or not model:
        raise RuntimeError("ALIRA api_base/model 설정이 비어 있습니다.")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    data_url = f"data:{mime};base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(api_key_env, "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": vision_prompt()},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }
    print(f"POST {url}")
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    print("HTTP", response.status_code)
    response.raise_for_status()
    body = response.json()
    try:
        text = body["choices"][0]["message"]["content"]
    except Exception:
        text = json.dumps(body, ensure_ascii=False, indent=2)
    print("\n[DIRECT API RESPONSE]\n", text)
    return 0


def cli_image_test(image_path: Path, cli_image_arg: str) -> int:
    cfg = load_config().get("alira", {})
    exe = alira_exe()
    if not exe.is_file():
        raise RuntimeError(f"ALIRA EXE를 찾을 수 없습니다: {exe}")
    if not cli_image_arg:
        raise RuntimeError("CLI 이미지 인자명이 필요합니다. 예: --cli-image-arg=--image")
    command = [
        str(exe),
        "--model", str(cfg.get("model") or ""),
        "--api-base", str(cfg.get("api_base") or ""),
        "--agent-type", "general_agent",
        "--cwd", str(project_root()),
        cli_image_arg, str(image_path),
        "-p", vision_prompt(),
    ]
    print("CLI command prepared (secret-free):")
    print(" ".join(command))
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(project_root()),
    )
    print("\n[CLI STDOUT]\n", result.stdout)
    if result.stderr:
        print("\n[CLI STDERR]\n", result.stderr)
    return result.returncode



def set_main_capability(value: bool) -> None:
    path = project_root() / "config" / "provider_config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("alira", {})["supports_images"] = bool(value)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Main config updated: alira.supports_images={bool(value)}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Detachable ALIRA native Vision diagnostic")
    parser.add_argument("--inspect", action="store_true", help="ALIRA executable/help/config inspection")
    parser.add_argument("--make-fixture", action="store_true", help="create deterministic Vision test PNG")
    parser.add_argument("--api-image", action="store_true", help="send fixture directly to configured OpenAI-compatible API")
    parser.add_argument("--cli-image", action="store_true", help="send fixture through ALIRA CLI using an explicit image flag")
    parser.add_argument("--image", default="", help="existing image path; otherwise probe_fixture.png")
    parser.add_argument("--cli-image-arg", default="", help="verified ALIRA CLI image flag, e.g. --image")
    parser.add_argument("--api-key-env", default="ALIRA_VISION_PROBE_API_KEY")
    parser.add_argument("--set-capability", choices=("true", "false"), default="", help="explicitly set main alira.supports_images after manual probe review")
    args = parser.parse_args()

    fixture = Path(args.image).resolve() if args.image else Path(__file__).with_name("probe_fixture.png")
    if args.make_fixture or (args.api_image or args.cli_image) and not fixture.exists():
        make_fixture(fixture)
        print(f"Fixture created: {fixture}")

    if args.set_capability:
        set_main_capability(args.set_capability == "true")

    if not any((args.inspect, args.make_fixture, args.api_image, args.cli_image, args.set_capability)):
        args.inspect = True

    rc = 0
    if args.inspect:
        rc = max(rc, inspect_environment())
    if args.api_image:
        rc = max(rc, direct_api_test(fixture, args.api_key_env))
    if args.cli_image:
        rc = max(rc, cli_image_test(fixture, args.cli_image_arg))
    if args.make_fixture and not (args.api_image or args.cli_image):
        print("Expected fixture facts:")
        print("code=R7K-42, arrow_color=green, arrow_direction=STATE_A->STATE_B, timeout=3.7 s, star_position=right of STATE_B, mode=VISION_ONLY")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
