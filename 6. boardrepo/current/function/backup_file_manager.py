from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class BackupFileError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupFileInfo:
    path: Path
    size_bytes: int
    family: str
    date_token: str | None
    counter: int
    versioned: bool


@dataclass(frozen=True)
class BackupSelection:
    selected: list[BackupFileInfo]
    superseded: list[BackupFileInfo]


_RELEASE_RE = re.compile(
    r"^(?P<family>.+?)_(?P<date>\d{6})(?:_(?P<counter>\d+))?$",
    re.IGNORECASE,
)

_LEGACY_REV_RE = re.compile(
    r"^(?P<family>.+?)[_-]rev\d+$",
    re.IGNORECASE,
)


def _is_excluded(path: Path, config: dict) -> bool:
    name = path.name
    lower_name = name.casefold()

    if config.get("exclude_hidden", True) and name.startswith("."):
        return True

    for prefix in config.get("exclude_prefixes", ["~$"]):
        if name.startswith(prefix):
            return True

    excluded_names = {str(x).casefold() for x in config.get("exclude_names", [])}
    if lower_name in excluded_names:
        return True

    for suffix in config.get("exclude_suffixes", []):
        if lower_name.endswith(str(suffix).casefold()):
            return True

    return False


def _valid_yymmdd(token: str) -> bool:
    if len(token) != 6 or not token.isdigit():
        return False

    yy = int(token[0:2])
    mm = int(token[2:4])
    dd = int(token[4:6])

    if not 1 <= mm <= 12:
        return False

    # Enough validation for deterministic ordering without introducing
    # locale/timezone behavior. Handle month lengths and leap years.
    year = 2000 + yy
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = {
        1: 31, 2: 29 if leap else 28, 3: 31, 4: 30,
        5: 31, 6: 30, 7: 31, 8: 31,
        9: 30, 10: 31, 11: 30, 12: 31,
    }
    return 1 <= dd <= month_days[mm]


def _parse_backup_archive(path: Path, config: dict) -> BackupFileInfo:
    stem = path.stem
    match = _RELEASE_RE.match(stem)

    if not match:
        # Non-release filenames remain valid standalone families.
        return BackupFileInfo(
            path=path,
            size_bytes=path.stat().st_size,
            family=stem,
            date_token=None,
            counter=0,
            versioned=False,
        )

    family = match.group("family")
    date_token = match.group("date")
    counter_text = match.group("counter")

    if not _valid_yymmdd(date_token):
        raise BackupFileError(
            f"Backup 파일의 YYMMDD 날짜가 올바르지 않습니다: {path.name}"
        )

    if config.get("ignore_legacy_rev_before_date", True):
        legacy = _LEGACY_REV_RE.match(family)
        if legacy:
            family = legacy.group("family")

    counter = int(counter_text) if counter_text is not None else 0

    return BackupFileInfo(
        path=path,
        size_bytes=path.stat().st_size,
        family=family,
        date_token=date_token,
        counter=counter,
        versioned=True,
    )


def _scan_backup_archives(folder: Path, config: dict) -> list[BackupFileInfo]:
    if not folder.exists() or not folder.is_dir():
        raise BackupFileError(f"Backup 폴더를 찾지 못했습니다: {folder}")

    recursive = bool(config.get("recursive", False))
    allowed_exts = {
        str(ext).casefold()
        for ext in config.get("extensions", [".zip", ".7z", ".rar"])
    }

    if recursive:
        candidates = [p for p in folder.rglob("*") if p.is_file()]
    else:
        candidates = [p for p in folder.iterdir() if p.is_file()]

    included = [
        p for p in candidates
        if p.suffix.casefold() in allowed_exts and not _is_excluded(p, config)
    ]
    included.sort(key=lambda p: p.name.casefold())

    return [_parse_backup_archive(p, config) for p in included]


def select_latest_backup_archives(folder: Path, config: dict) -> BackupSelection:
    """
    Group Backup archives by program/family and keep only the newest release
    in each family.

    Versioned family:
        FAMILY_YYMMDD_N.zip
        FAMILY_YYMMDD.zip  -> counter=0 compatibility

    Ordering within one family:
        YYMMDD first, then N.

    Examples:
        BoardRepo_260808_1.zip
        BoardRepo_260808_2.zip
        => BoardRepo_260808_2.zip only

        ToolA_260807_9.zip
        ToolA_260808_1.zip
        => ToolA_260808_1.zip only

    A non-release filename such as LegacyUtility.zip is a standalone family and
    remains selected because there is no comparable date/counter release.
    """
    archives = _scan_backup_archives(folder, config)

    if not config.get("latest_per_family", True):
        return BackupSelection(selected=archives, superseded=[])

    groups: dict[str, list[BackupFileInfo]] = {}
    for info in archives:
        groups.setdefault(info.family.casefold(), []).append(info)

    selected: list[BackupFileInfo] = []
    superseded: list[BackupFileInfo] = []

    for _family_key, items in groups.items():
        versioned = [x for x in items if x.versioned]
        unversioned = [x for x in items if not x.versioned]

        # Normally a family is either versioned or standalone. If an exact
        # family somehow appears in both modes, refuse to guess.
        if versioned and unversioned:
            names = ", ".join(x.path.name for x in items)
            raise BackupFileError(
                "Backup 동일 계열에 날짜형 Release와 무버전 파일이 함께 있어 "
                f"최신판을 안전하게 결정할 수 없습니다: {names}"
            )

        if unversioned:
            # Filesystem cannot contain duplicate exact names in one directory,
            # so each standalone family is naturally unique.
            selected.extend(unversioned)
            continue

        if not versioned:
            continue

        best_key = max((x.date_token, x.counter) for x in versioned)
        winners = [
            x for x in versioned
            if (x.date_token, x.counter) == best_key
        ]

        if len(winners) != 1:
            names = ", ".join(x.path.name for x in winners)
            raise BackupFileError(
                "Backup 동일 계열의 최신 Release가 하나로 결정되지 않습니다: "
                f"{names}"
            )

        winner = winners[0]
        selected.append(winner)
        superseded.extend(x for x in versioned if x is not winner)

    selected.sort(key=lambda x: (x.family.casefold(), x.path.name.casefold()))
    superseded.sort(key=lambda x: (x.family.casefold(), x.path.name.casefold()))

    return BackupSelection(
        selected=selected,
        superseded=superseded,
    )


# Compatibility helper retained for callers that only need the chosen list.
def list_backup_archives(folder: Path, config: dict) -> list[BackupFileInfo]:
    return select_latest_backup_archives(folder, config).selected
