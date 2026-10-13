# -*- coding: utf-8 -*-
"""논문 B(확장 실험)용 평가 목록 생성기.

evaluation/ 폴더에 넣고 저장소 루트에서 실행합니다.
기존 create_evaluation_manifest.py 와 같은 방식으로 회의 음성(KconfSpeech)의
음성-정답 쌍을 찾고, 게재 논문에 쓴 20개를 제외한 뒤 N개를 뽑습니다.
특정 회의에 몰리지 않도록 회의(세션)마다 고르게 돌아가며 뽑습니다.

1) 몇 개나 있는지 세기 (API 호출 없음)
   python evaluation/make_manifest_B.py --speech-root "<speech_data 폴더>" --count

2) 평가 목록 만들기 (API 호출 없음)
   python evaluation/make_manifest_B.py --speech-root "<speech_data 폴더>" --n 1000

출력: evaluation/manifest_B_meeting.csv  (run_stt_model_cer_benchmark.py 의 --manifest 로 사용)
"""
import argparse
import csv
import random
import sys
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "evaluation"
DEFAULT_OUTPUT = EVALUATION_DIR / "manifest_B_meeting.csv"
PAPER_20 = ROOT / "benchmark" / "data" / "audio_file_metadata.csv"  # 게재 논문의 20개 목록
FIELDS = ["audio_id", "dataset", "category", "audio_path", "audio_url", "reference_path", "reference_text"]


def relative_key(path: Path, suffix: str):
    """create_evaluation_manifest.py 와 동일: 경로의 'D20' 이후 부분으로 음성과 정답을 짝짓는다."""
    parts = list(path.parts)
    try:
        start = parts.index("D20")
    except ValueError:
        return None
    return str(Path(*parts[start:]).with_suffix(suffix)).replace("\\", "/")


def find_pairs(speech_root: Path):
    label_root = speech_root / "라벨링데이터"
    audio_root = speech_root / "원천데이터"
    if not label_root.is_dir() or not audio_root.is_dir():
        sys.exit(f"폴더를 찾지 못했습니다: {label_root} / {audio_root}")
    wav_by_key = {}
    for wav in audio_root.rglob("*.wav"):
        key = relative_key(wav, ".txt")
        if key:
            wav_by_key[key] = wav
    rows = []
    for label in sorted(label_root.rglob("*.txt")):
        key = relative_key(label, ".txt")
        if not key or key not in wav_by_key:
            continue
        rows.append({
            "audio_id": f"speech_{label.parent.name}_{label.stem}",
            "dataset": "KconfSpeech",
            "category": "meeting",
            "audio_path": str(wav_by_key[key]),
            "audio_url": "",
            "reference_path": str(label),
            "reference_text": "",
            "_session": label.parent.name,
        })
    return rows


def load_paper_ids(path: Path):
    if not path.exists():
        print(f"[주의] 게재 논문 20개 목록을 찾지 못했습니다: {path}")
        return set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["audio_id"] for row in csv.DictReader(handle) if row.get("audio_id")}


def duration_seconds(path: str) -> float:
    try:
        with wave.open(path, "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except Exception:
        return 0.0


def balanced_sample(rows, n, seed):
    """세션(회의)마다 고르게 뽑는다: 세션별로 섞은 뒤 세션을 돌아가며 하나씩 가져온다."""
    rng = random.Random(seed)
    by_session = {}
    for row in rows:
        by_session.setdefault(row["_session"], []).append(row)
    order = sorted(by_session)
    rng.shuffle(order)
    for key in order:
        rng.shuffle(by_session[key])
    picked, i = [], 0
    while len(picked) < n and any(by_session[k] for k in order):
        key = order[i % len(order)]
        if by_session[key]:
            picked.append(by_session[key].pop())
        i += 1
    return picked


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="논문 B용 회의 음성 평가 목록 생성")
    parser.add_argument("--speech-root", required=True, help="speech_data 폴더 (라벨링데이터/원천데이터가 들어 있는 곳)")
    parser.add_argument("--n", type=int, default=1000, help="뽑을 개수 (기본 1000)")
    parser.add_argument("--seed", type=int, default=2026, help="무작위 추출 시드 (기본 2026, 바꾸지 말 것)")
    parser.add_argument("--exclude", default=str(PAPER_20), help="제외할 audio_id 목록 CSV (기본: 게재 논문 20개)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--count", action="store_true", help="개수만 세고 끝냄 (파일을 만들지 않음)")
    args = parser.parse_args()

    pairs = find_pairs(Path(args.speech_root))
    paper_ids = load_paper_ids(Path(args.exclude))
    found_paper = sum(1 for row in pairs if row["audio_id"] in paper_ids)
    candidates = [row for row in pairs if row["audio_id"] not in paper_ids]
    sessions = Counter(row["_session"] for row in candidates)

    print(f"음성-정답 쌍 전체: {len(pairs)}개")
    print(f"게재 논문 20개 중 이 폴더에서 찾은 것: {found_paper}개 (제외함)")
    print(f"새로 쓸 수 있는 후보: {len(candidates)}개, 회의(세션) {len(sessions)}개")
    if args.count:
        return

    if len(candidates) < args.n:
        print(f"[주의] 후보가 {args.n}개보다 적습니다. 있는 {len(candidates)}개를 모두 씁니다.")
    sample = balanced_sample(candidates, args.n, args.seed)

    total = sum(duration_seconds(row["audio_path"]) for row in sample)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sample)

    per = Counter(row["_session"] for row in sample)
    print(f"뽑은 개수: {len(sample)}개, 회의(세션) {len(per)}개, 시드 {args.seed}")
    print(f"세션당 개수: 최소 {min(per.values())}, 최대 {max(per.values())}")
    print(f"음성 총 길이: {total / 3600:.2f}시간 (평균 {total / max(len(sample), 1):.1f}초)")
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
