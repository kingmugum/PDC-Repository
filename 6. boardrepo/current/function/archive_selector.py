from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Iterable


_REV_RE = re.compile(r"(?:^|[_\-\s])rev(?:ision)?[_\-\s]?(\d+)(?=$|[_\-\s])", re.IGNORECASE)
_DATE_RE = re.compile(r"(?:^|[_\-\s])(\d{6})(?=$|[_\-\s])")
_COUNTER_RE = re.compile(r"[_\-\s](\d{1,3})$")
_SANITIZE_RE = re.compile(r"[^0-9a-z가-힣]+", re.IGNORECASE)


class ArchiveSelectionError(RuntimeError):
    def __init__(self, target_name: str, reason: str, details: Iterable[str] | None = None):
        self.target_name = target_name
        self.reason = reason
        self.details = list(details or [])

        lines = [f"[{target_name}] 최신 압축파일을 자동 결정할 수 없습니다.", "", reason]
        if self.details:
            lines.extend(["", "확인 대상:"])
            lines.extend(f"- {item}" for item in self.details)
        lines.extend(["", "파일명을 확인한 뒤 다시 실행해주세요."])
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class ArchiveInfo:
    path: Path
    rev: int | None
    date_token: str | None
    date_value: date | None
    counter: int

    @property
    def display_order(self) -> str:
        date_text = self.date_token or "날짜없음"
        rev_text = self.rev if self.rev is not None else "없음"
        return f"{self.path.name}  [date={date_text}, rev={rev_text}, counter={self.counter}]"


@dataclass(frozen=True)
class ArchiveSelection:
    target_name: str
    folder: Path
    selected: ArchiveInfo
    candidates: tuple[ArchiveInfo, ...]
    rule_summary: str
    strategy: str


def _normalize_name(value: str) -> str:
    return _SANITIZE_RE.sub("", value.casefold())


def _matches_target_prefix(stem: str, aliases: Iterable[str]) -> bool:
    normalized_stem = _normalize_name(stem)
    normalized_aliases = sorted(
        {_normalize_name(alias) for alias in aliases if _normalize_name(alias)},
        key=len,
        reverse=True,
    )
    return any(normalized_stem.startswith(alias) for alias in normalized_aliases)


def _parse_date(token: str) -> date | None:
    try:
        yy = int(token[0:2])
        mm = int(token[2:4])
        dd = int(token[4:6])
        return date(2000 + yy, mm, dd)
    except (ValueError, TypeError):
        return None


def parse_archive_info(path: Path, *, require_revision: bool = True, require_date: bool = False) -> ArchiveInfo:
    stem = path.stem

    rev_match = _REV_RE.search(stem)
    rev = int(rev_match.group(1)) if rev_match else None
    if require_revision and rev is None:
        raise ValueError("rev 번호를 찾을 수 없음")

    date_tokens = _DATE_RE.findall(stem)
    if len(date_tokens) > 1:
        raise ValueError("YYMMDD 형식 날짜가 2개 이상 존재")

    date_token = date_tokens[0] if date_tokens else None
    if require_date and not date_token:
        raise ValueError("YYMMDD 날짜를 찾을 수 없음")

    date_value = None
    if date_token:
        date_value = _parse_date(date_token)
        if date_value is None:
            raise ValueError(f"유효하지 않은 날짜: {date_token}")

    counter_match = _COUNTER_RE.search(stem)
    counter = int(counter_match.group(1)) if counter_match else 0

    return ArchiveInfo(
        path=path,
        rev=rev,
        date_token=date_token,
        date_value=date_value,
        counter=counter,
    )


def _validate_date_rev_consistency(target_name: str, infos: list[ArchiveInfo]) -> None:
    conflicts: list[str] = []

    for left_index, left in enumerate(infos):
        for right in infos[left_index + 1:]:
            if left.date_value == right.date_value:
                continue
            if left.date_value is None or right.date_value is None:
                continue
            if left.rev is None or right.rev is None:
                continue

            newer, older = (
                (left, right)
                if left.date_value > right.date_value
                else (right, left)
            )

            if newer.rev < older.rev:
                conflicts.extend([newer.display_order, older.display_order])

    if conflicts:
        unique = list(dict.fromkeys(conflicts))
        raise ArchiveSelectionError(
            target_name,
            "날짜 기준 최신 파일의 rev 번호가 더 낮아 날짜 순서와 rev 순서가 서로 충돌합니다. "
            "자동으로 어느 파일이 최신인지 추측하지 않습니다.",
            unique,
        )


def _collect_archives(folder: Path, aliases: Iterable[str], extensions: Iterable[str]) -> list[Path]:
    allowed = {
        ext.casefold() if ext.startswith(".") else f".{ext.casefold()}"
        for ext in extensions
    }
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.casefold() in allowed
        and _matches_target_prefix(path.stem, aliases)
    )


def _select_date_counter_release(
    folder: Path,
    target_name: str,
    archives: list[Path],
) -> ArchiveSelection:
    """
    Package-release strategy used by PassFail and SignalExport.

    The archive's package identity is independent from component revisions inside
    the ZIP.  Ordering is only:
        newest YYMMDD -> highest trailing _N counter.

    A legacy revNN token in the package filename is tolerated during migration,
    but intentionally ignored for ordering.
    """
    infos: list[ArchiveInfo] = []
    parse_errors: list[str] = []
    for path in archives:
        try:
            infos.append(
                parse_archive_info(
                    path,
                    require_revision=False,
                    require_date=True,
                )
            )
        except ValueError as exc:
            parse_errors.append(f"{path.name}  ({exc})")

    if parse_errors:
        raise ArchiveSelectionError(
            target_name,
            "패키지 Release 파일명은 YYMMDD 날짜를 포함해야 합니다. "
            "권장 형식은 TARGET_YYMMDD_N.zip 입니다. 전체 패키지 revNN은 필요하지 않습니다.",
            parse_errors,
        )

    newest_date = max(info.date_value for info in infos)
    same_date = [info for info in infos if info.date_value == newest_date]
    highest_counter = max(info.counter for info in same_date)
    finalists = [info for info in same_date if info.counter == highest_counter]

    if len(finalists) != 1:
        raise ArchiveSelectionError(
            target_name,
            "가장 최신 날짜에서 Release 순번을 하나로 확정할 수 없습니다. "
            "같은 날짜에 여러 파일이 있다면 파일명 끝에 _1, _2, _3 ... 순번을 붙여주세요.",
            [info.display_order for info in finalists],
        )

    selected = finalists[0]
    return ArchiveSelection(
        target_name=target_name,
        folder=folder,
        selected=selected,
        candidates=tuple(infos),
        rule_summary=(
            "패키지 Release: 날짜(YYMMDD) 우선 → 같은 날짜에서 끝 숫자(_1/_2/_3...). "
            "압축파일의 revNN은 사용하지 않음"
        ),
        strategy="date_counter_release",
    )


def _select_date_rev_counter(
    folder: Path,
    target_name: str,
    archives: list[Path],
) -> ArchiveSelection:
    """Legacy versioned-archive strategy retained for Backup."""
    infos: list[ArchiveInfo] = []
    parse_errors: list[str] = []
    for path in archives:
        try:
            infos.append(parse_archive_info(path, require_revision=True, require_date=False))
        except ValueError as exc:
            parse_errors.append(f"{path.name}  ({exc})")

    if parse_errors:
        raise ArchiveSelectionError(
            target_name,
            "비교 대상 압축파일 중 파일명 규칙을 해석할 수 없는 파일이 있습니다. "
            "Backup 규칙에서는 revNN이 필요하고, 날짜를 쓴다면 YYMMDD가 유효해야 합니다.",
            parse_errors,
        )

    dated = [info for info in infos if info.date_value is not None]
    undated = [info for info in infos if info.date_value is None]

    if dated and undated:
        raise ArchiveSelectionError(
            target_name,
            "날짜(YYMMDD)가 있는 파일과 없는 파일이 함께 있어 '날짜 우선' 규칙으로 직접 비교할 수 없습니다.",
            [info.display_order for info in infos],
        )

    if dated:
        _validate_date_rev_consistency(target_name, infos)

        newest_date = max(info.date_value for info in infos)
        same_date = [info for info in infos if info.date_value == newest_date]
        highest_rev = max(info.rev for info in same_date if info.rev is not None)
        same_rev = [info for info in same_date if info.rev == highest_rev]
        highest_counter = max(info.counter for info in same_rev)
        finalists = [info for info in same_rev if info.counter == highest_counter]
        rule_summary = "날짜(YYMMDD) 우선 → 같은 날짜에서 rev 번호 → 같은 rev에서 끝 숫자(_1/_2/_3...)"
    else:
        highest_rev = max(info.rev for info in infos if info.rev is not None)
        same_rev = [info for info in infos if info.rev == highest_rev]
        highest_counter = max(info.counter for info in same_rev)
        finalists = [info for info in same_rev if info.counter == highest_counter]
        rule_summary = "날짜 정보 없음 → rev 번호 우선 → 같은 rev에서 끝 숫자(_1/_2/_3...)"

    if len(finalists) != 1:
        raise ArchiveSelectionError(
            target_name,
            "최종 비교 값이 동일한 압축파일이 여러 개라 자동 선택할 수 없습니다.",
            [info.display_order for info in finalists],
        )

    selected = finalists[0]
    return ArchiveSelection(
        target_name=target_name,
        folder=folder,
        selected=selected,
        candidates=tuple(infos),
        rule_summary=rule_summary,
        strategy="date_rev_counter",
    )


def select_latest_archive(
    folder: Path,
    target_name: str,
    aliases: Iterable[str],
    extensions: Iterable[str] = (".zip", ".7z", ".rar"),
    strategy: str = "date_rev_counter",
) -> ArchiveSelection:
    folder = Path(folder)
    archives = _collect_archives(folder, aliases, extensions)

    if not archives:
        raise ArchiveSelectionError(
            target_name,
            "대상 폴더에 이름이 대상과 일치하는 압축파일(.zip/.7z/.rar)이 없습니다.",
            [str(folder)],
        )

    if strategy == "date_counter_release":
        return _select_date_counter_release(folder, target_name, archives)
    if strategy == "date_rev_counter":
        return _select_date_rev_counter(folder, target_name, archives)

    raise ArchiveSelectionError(
        target_name,
        f"지원하지 않는 archive strategy입니다: {strategy}",
    )


def version_label_from_archive(path: Path, display_name: str) -> str:
    stem = path.stem
    prefix = f"{display_name}_"
    if stem.casefold().startswith(prefix.casefold()):
        return stem[len(prefix):]
    return stem
