# -*- coding: utf-8 -*-
"""
split_python_files_to_txt.py

목적
- .py / .pyw 파일을 줄 단위로 200줄씩 그대로 잘라 txt 파일로 분할한다.
- 분할 txt 파일에는 원본 코드 내용만 들어간다.
- 검증/복원용 정보는 별도 split_manifest.json 파일에만 저장한다.

변경 사항
- 자동 검색 대상은 "이 스크립트가 위치한 폴더"로 고정
- 기본 패턴은 *.py / *.pyw 전체
- 자기 자신(split_python_files_to_txt.py)은 자동 검색 대상에서 제외

예시
1) 스크립트가 있는 현재 폴더의 모든 .py / .pyw 자동 분할
   py split_python_files_to_txt.py --output-dir split_output

2) 특정 파일만 분할
   py split_python_files_to_txt.py some_file.py other_file.pyw --output-dir split_output

3) 줄 수 변경
   py split_python_files_to_txt.py --output-dir split_output --lines 200 --overwrite
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


REV_RE = re.compile(r"(?i)(?:^|[_\-.])rev[_\-.]?(\d+)(?:$|[_\-.])")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def part_suffix(index: int) -> str:
    """0 -> a, 1 -> b, ... 25 -> z, 26 -> aa"""
    if index < 0:
        raise ValueError("index must be >= 0")
    letters = []
    n = index
    while True:
        letters.append(chr(ord("a") + (n % 26)))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(letters))


def detect_rev(stem: str) -> Optional[str]:
    m = REV_RE.search(stem)
    return m.group(1) if m else None


def split_lines_as_bytes(data: bytes) -> List[bytes]:
    """
    bytes 기준으로 line ending을 보존하면서 줄 단위 분리.
    마지막 줄에 개행이 없어도 하나의 줄로 취급한다.
    """
    if data == b"":
        return []
    return data.splitlines(keepends=True)


def collect_input_files(args) -> List[Path]:
    files: List[Path] = []

    script_path = Path(__file__).resolve()
    script_dir = script_path.parent

    # 사용자가 파일을 직접 지정한 경우
    if args.files:
        for item in args.files:
            p = Path(item).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"입력 파일 없음: {p}")
            if p.suffix.lower() not in (".py", ".pyw"):
                raise ValueError(f".py/.pyw 파일만 지원: {p}")
            files.append(p)
        return sorted(set(files), key=lambda x: x.name.lower())

    # 자동 검색은 항상 "이 스크립트가 위치한 폴더" 기준
    input_dir = script_dir

    patterns = args.patterns or ["*.py", "*.pyw"]
    for pat in patterns:
        for p in input_dir.glob(pat):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".py", ".pyw"):
                continue
            if p.resolve() == script_path:
                continue
            files.append(p)

    return sorted(set(files), key=lambda x: x.name.lower())


def split_one_file(src: Path, output_dir: Path, lines_per_part: int, overwrite: bool) -> dict:
    raw = src.read_bytes()
    lines = split_lines_as_bytes(raw)

    # 빈 파일이어도 txt 하나는 생성
    if not lines:
        chunks = [b""]
    else:
        chunks = [
            b"".join(lines[i:i + lines_per_part])
            for i in range(0, len(lines), lines_per_part)
        ]

    multi_part = len(chunks) > 1
    parts = []

    for idx, chunk in enumerate(chunks):
        if multi_part:
            txt_name = f"{src.stem}_{part_suffix(idx)}.txt"
        else:
            txt_name = f"{src.stem}.txt"

        txt_path = output_dir / txt_name
        if txt_path.exists() and not overwrite:
            raise FileExistsError(f"이미 존재함: {txt_path}  (--overwrite 사용 가능)")

        txt_path.write_bytes(chunk)

        chunk_line_count = len(split_lines_as_bytes(chunk))
        start_line = idx * lines_per_part + 1 if lines else 0
        end_line = min((idx + 1) * lines_per_part, len(lines)) if lines else 0

        parts.append({
            "index": idx + 1,
            "suffix": part_suffix(idx) if multi_part else "",
            "filename": txt_name,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": chunk_line_count,
            "sha256": sha256_bytes(chunk),
        })

    return {
        "source_filename": src.name,
        "source_stem": src.stem,
        "source_suffix": src.suffix,
        "rev": detect_rev(src.stem),
        "total_lines": len(lines),
        "total_parts": len(parts),
        "lines_per_part": lines_per_part,
        "source_sha256": sha256_bytes(raw),
        "parts": parts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=".py/.pyw 파일을 200줄 단위 txt로 그대로 분할합니다."
    )
    parser.add_argument("files", nargs="*", help="분할할 .py/.pyw 파일 경로. 생략하면 스크립트 위치 폴더에서 자동 검색")
    parser.add_argument("--output-dir", default="split_output", help="분할 txt 출력 폴더")
    parser.add_argument("--lines", type=int, default=200, help="파트당 줄 수. 기본값: 200")
    parser.add_argument(
        "--patterns",
        nargs="*",
        default=None,
        help='자동 검색 패턴. 기본값: "*.py" "*.pyw"',
    )
    parser.add_argument("--overwrite", action="store_true", help="기존 txt/manifest 덮어쓰기")
    args = parser.parse_args()

    if args.lines <= 0:
        raise ValueError("--lines 는 1 이상이어야 합니다.")

    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir).expanduser().resolve()

    # output-dir이 상대경로면 script_dir 기준으로 생성하는 게 직관적
    if not Path(args.output_dir).is_absolute():
        output_dir = (script_dir / args.output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "split_manifest.json"
    if manifest_path.exists() and not args.overwrite:
        raise FileExistsError(f"manifest가 이미 존재함: {manifest_path}  (--overwrite 사용 가능)")

    files = collect_input_files(args)
    if not files:
        raise FileNotFoundError("분할할 .py/.pyw 파일을 찾지 못했습니다.")

    manifest = {
        "tool": "split_python_files_to_txt.py",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_dir": str(script_dir),
        "line_split_policy": "literal line split; txt part files contain original code bytes only",
        "files": [],
    }

    print(f"[INFO] 대상 폴더: {script_dir}")
    print(f"[INFO] 대상 파일 {len(files)}개")

    for src in files:
        record = split_one_file(src, output_dir, args.lines, args.overwrite)
        manifest["files"].append(record)
        print(f"[OK] {src.name} -> {record['total_parts']} part(s), {record['total_lines']} lines")

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] manifest 생성: {manifest_path}")


if __name__ == "__main__":
    main()
