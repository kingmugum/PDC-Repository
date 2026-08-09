# -*- coding: utf-8 -*-
"""
txt_split_140_lines.py

기능
- TXT 파일을 140줄마다 분할하여 저장합니다.
- 실행 방식 1) 이 파일과 같은 폴더의 모든 .txt 파일을 자동 분할
- 실행 방식 2) txt 파일을 이 py 파일 위에 드래그 앤 드롭하여 해당 파일만 분할

출력 예시
- 원본: sample.txt
- 출력 폴더: sample_split_140
- 결과:
    sample_part_001.txt
    sample_part_002.txt
    sample_part_003.txt
"""

from pathlib import Path
import sys


CHUNK_LINES = 140
OUTPUT_SUFFIX = "_split_140"


def split_txt_file(txt_path: Path) -> None:
    """txt_path 파일을 CHUNK_LINES 줄 단위로 분할한다."""
    txt_path = txt_path.resolve()

    if not txt_path.exists():
        print(f"[SKIP] 파일 없음: {txt_path}")
        return

    if txt_path.suffix.lower() != ".txt":
        print(f"[SKIP] txt 파일 아님: {txt_path.name}")
        return

    output_dir = txt_path.parent / f"{txt_path.stem}{OUTPUT_SUFFIX}"
    output_dir.mkdir(exist_ok=True)

    part_no = 1
    line_count = 0
    buffer = []

    # utf-8-sig 우선 시도, 실패 시 cp949로 재시도
    encodings = ["utf-8-sig", "cp949"]

    for enc in encodings:
        try:
            with txt_path.open("r", encoding=enc) as f:
                for line in f:
                    buffer.append(line)
                    line_count += 1

                    if len(buffer) >= CHUNK_LINES:
                        save_part(txt_path, output_dir, part_no, buffer)
                        part_no += 1
                        buffer = []

            # 남은 줄 저장
            if buffer:
                save_part(txt_path, output_dir, part_no, buffer)

            print(f"[OK] {txt_path.name} 분할 완료 → {output_dir.name}")
            print(f"     총 줄 수: {line_count}, 생성 파일 수: {part_no if buffer else part_no - 1}")
            return

        except UnicodeDecodeError:
            continue

    print(f"[ERROR] 인코딩 문제로 읽기 실패: {txt_path.name}")


def save_part(original_path: Path, output_dir: Path, part_no: int, lines: list[str]) -> None:
    """분할된 내용을 파일로 저장한다."""
    output_name = f"{original_path.stem}_part_{part_no:03d}.txt"
    output_path = output_dir / output_name

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        f.writelines(lines)


def find_txt_files_in_current_folder() -> list[Path]:
    """현재 폴더에서 분할 대상 txt 파일을 찾는다."""
    current_dir = Path.cwd()
    txt_files = []

    for path in current_dir.glob("*.txt"):
        # 이미 분할 결과처럼 보이는 파일은 제외
        if "_part_" in path.stem:
            continue
        txt_files.append(path)

    return txt_files


def main() -> None:
    # 드래그 앤 드롭 또는 명령행 인자가 있는 경우
    if len(sys.argv) > 1:
        targets = [Path(arg) for arg in sys.argv[1:]]
    else:
        # 인자가 없으면 현재 폴더의 모든 txt 파일 처리
        targets = find_txt_files_in_current_folder()

    if not targets:
        print("[INFO] 분할할 txt 파일이 없습니다.")
        print("       사용법 1: 이 py 파일을 txt 파일이 있는 폴더에 넣고 실행")
        print("       사용법 2: txt 파일을 이 py 파일 위에 드래그 앤 드롭")
        input("\nEnter 키를 누르면 종료합니다...")
        return

    for target in targets:
        split_txt_file(target)

    input("\n작업 완료. Enter 키를 누르면 종료합니다...")


if __name__ == "__main__":
    main()
