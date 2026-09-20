from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

_API_KEY_FILE_MARKER_RE = re.compile(r"api[\s_\-]*key", re.IGNORECASE)
_API_KEY_ASSIGN_RE = re.compile(
    r"^(?:API[_\s\-]*KEY|api[_\s\-]*key)\s*=\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_API_KEY_ALLOWED_SUFFIXES = {".txt", ""}


def _is_probable_api_key_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in _API_KEY_ALLOWED_SUFFIXES:
        return False
    stem = path.stem or path.name
    compact = re.sub(r"[^a-z0-9]+", "", stem.lower())
    return "apikey" in compact


def make_api_key_display_name(api_key_file: Path | str | None) -> str:
    if api_key_file is None:
        return "API KEY 미감지"

    stem = Path(api_key_file).stem or Path(api_key_file).name
    m = _API_KEY_FILE_MARKER_RE.search(stem)
    if m:
        left = stem[:m.start()]
        right = stem[m.end():]
    else:
        return "API 입력됨"

    label = "_".join(x.strip(" _-\t") for x in (left, right) if x.strip(" _-\t"))
    label = re.sub(r"[_\-]+", "_", label).strip("_").strip()
    compact_label = re.sub(r"[\s_\-]+", "", label.lower())
    if not compact_label or re.fullmatch(r"[xyab]+", compact_label):
        return "API 입력됨"
    return label


def _read_api_key_text_file(path: Path) -> str:
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = path.read_text(encoding=enc, errors="replace")
            break
        except Exception:
            continue

    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line or line.startswith("#"):
            continue
        m = _API_KEY_ASSIGN_RE.match(line)
        if m:
            line = m.group("value").strip()
        line = line.strip().strip('"').strip("'").strip()
        if line:
            return line
    return ""


def api_key_search_dirs(base_dir: Path | str) -> list[Path]:
    """Signal Export 호환 Root + Requirement Studio 전용 api_keys 폴더를 검색한다."""
    base = Path(base_dir).expanduser().resolve()
    dirs = [base]
    api_dir = base / "api_keys"
    if api_dir not in dirs:
        dirs.append(api_dir)
    return dirs


def resolve_external_api_key(base_dir: Path | str) -> Tuple[str, Optional[Path], str]:
    """프로젝트 Root와 api_keys/의 API_Key류 파일을 찾아 최신 유효 Key를 반환한다."""
    candidates: list[Path] = []
    for folder in api_key_search_dirs(base_dir):
        if not folder.exists() or not folder.is_dir():
            continue
        candidates.extend(p for p in folder.iterdir() if _is_probable_api_key_file(p))

    # 같은 파일이 중복 수집될 가능성을 방어한다.
    unique = {str(p.resolve()): p for p in candidates}
    candidates = list(unique.values())
    candidates.sort(
        key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name.lower()),
        reverse=True,
    )

    for path in candidates:
        key = _read_api_key_text_file(path)
        if key:
            return key, path, make_api_key_display_name(path)

    return "", None, "API KEY 미감지"
