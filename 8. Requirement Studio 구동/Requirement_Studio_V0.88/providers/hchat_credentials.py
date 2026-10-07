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
# Guide/help/example documents may intentionally contain the string API_KEY in their
# filename.  They must never be treated as credentials.
_NON_SECRET_FILENAME_MARKERS = (
    "readme", "guide", "help", "usage", "manual", "sample", "example", "template",
    "사용법", "설명", "안내", "예시", "샘플",
)


def is_valid_hchat_api_key(value: str) -> bool:
    """Conservative H-Chat key sanity check.

    Real HTTP API keys are expected to be a single printable ASCII token.  This
    intentionally rejects Korean README text, whitespace-containing prose, and
    control characters before they can reach HTTP header encoding.
    """
    token = (value or "").strip()
    if not token:
        return False
    if len(token) < 8:
        return False
    if any(ch.isspace() for ch in token):
        return False
    try:
        raw = token.encode("ascii")
    except UnicodeEncodeError:
        return False
    return all(0x21 <= b <= 0x7E for b in raw)


def _is_probable_api_key_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in _API_KEY_ALLOWED_SUFFIXES:
        return False
    stem = (path.stem or path.name).lower()
    compact = re.sub(r"[^a-z0-9가-힣]+", "", stem)
    if any(marker in compact for marker in _NON_SECRET_FILENAME_MARKERS):
        return False
    return "apikey" in re.sub(r"[^a-z0-9]+", "", stem)


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

    # Do not accept the first arbitrary non-comment line. Scan for the first
    # line that actually looks like a single HTTP-safe API key token.
    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line or line.startswith("#"):
            continue
        m = _API_KEY_ASSIGN_RE.match(line)
        if m:
            line = m.group("value").strip()
        line = line.strip().strip('"').strip("'").strip()
        if is_valid_hchat_api_key(line):
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
    """프로젝트 Root와 api_keys/에서 설명문서를 제외한 유효 API Key를 찾는다."""
    candidates: list[Path] = []
    for folder in api_key_search_dirs(base_dir):
        if not folder.exists() or not folder.is_dir():
            continue
        candidates.extend(p for p in folder.iterdir() if _is_probable_api_key_file(p))

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
