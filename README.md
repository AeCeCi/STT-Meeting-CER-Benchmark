# STT Meeting CER Benchmark

한국어 회의 음성(AI Hub KconfSpeech) **1,000개**로 5개 상용 STT 엔진(CLOVA, Azure, Whisper, Google, AssemblyAI)의 글자 오류율(CER)을 비교한 벤치마크입니다.
선행 연구(STT-Presentation-Review, 회의 음성 20개)와 같은 스크립트·같은 엔진 옵션·같은 정규화를 그대로 써서 표본을 50배로 늘린 확장 실험이며, 비교를 위해 기존 20개도 같은 날 다시 실행했습니다.

*A character error rate (CER) benchmark of five commercial STT engines on 1,000 Korean meeting-speech clips from AI Hub KconfSpeech, run with the same script, engine options and normalization as the 20-clip study in [STT-Presentation-Review](https://github.com/AeCeCi/STT-Presentation-Review). The original 20 clips were re-run on the same day for comparison. English summary at the end.*

## 결과 요약 (2026-10-13 실행)

평균 CER (%, 낮을수록 좋음). 정규화는 소문자화 → 공백 제거 → `[0-9a-z가-힣]` 외 문자 제거.

| 엔진 | 신규 1,000개 (`B_meeting_1000`) | 기존 20개 재실행 (`B_original20_rerun`) |
|---|---:|---:|
| CLOVA Speech | **12.11** | **6.15** |
| Azure Speech | 13.79 | 6.81 |
| OpenAI Whisper | 16.32 | 9.23 |
| Google STT v2 | 16.75 | 8.04 |
| AssemblyAI | 17.23 | 10.13 |

- 호출 5,000건 + 100건 모두 성공 (ERROR/SKIPPED 0건).
- 1,000개 클립: 180개 회의 세션에서 세션별로 고르게 추출(시드 2026), 총 102.6분, 평균 6.2초.
- 기존 20개: 총 3.6분, 평균 10.8초.
- 1,000개 전체 실행 시간 4시간 10분 (엔진 호출은 순차).

## 폴더 구성

```
evaluation/
  run_stt_model_cer_benchmark.py      # 5개 엔진 호출 + CER 계산 (선행 연구와 동일, 변경 없음)
  make_manifest_B.py                  # KconfSpeech에서 1,000개 평가 목록 추출 (기존 20개 제외, 세션 균등, 시드 2026)
  manifest_B_meeting.csv              # 추출된 1,000개 목록 (코퍼스 내 상대 경로, 전사문 없음)
  speech_audio_reference_manifest.csv # 기존 20개 목록
  results/B_meeting_1000/             # 1,000개 결과
  results/B_original20_rerun/         # 20개 재실행 결과
benchmark/data/audio_file_metadata.csv # 선행 연구 20개 메타데이터 (make_manifest_B.py 의 제외 목록)
```

각 결과 폴더의 파일:

| 파일 | 내용 |
|---|---|
| `stt_model_average_cer_summary.csv` | 엔진별 평균 CER |
| `stt_model_cer_by_audio_file.csv` | 클립 × 엔진 CER 표 |
| `per_file_results.csv` | 클립·엔진별 CER, 치환/삭제/삽입 수, 정답 글자 수 |
| `call_log.csv` | 호출 시각, 엔드포인트, 모델, 소요 시간, 상태 |
| `run_meta.json` | 실행 시각, 스크립트 커밋, Python/OS |

**저장소에 없는 것 (AI Hub 이용 약관):** 음성·정답 전사 파일, 엔진이 돌려준 전사문이 들어 있는 `stt_model_transcripts_and_cer_details.csv`, 원본 응답 `raw/`. 이 파일들은 로컬에 보관하며 재현은 아래 절차로 가능합니다.

## 엔진 호출 조건

| 엔진 | 엔드포인트 / 모델 | 비고 |
|---|---|---|
| CLOVA Speech | recognizer/upload (long sentence) | wordAlignment, 화자분리 요청 |
| Azure Speech | conversation v1 REST, `ko-KR`, koreacentral | 60초 이하 클립 |
| OpenAI Whisper | `/v1/audio/transcriptions`, `whisper-1` | verbose_json |
| Google STT v2 | `recognizers/_:recognize`, `latest_long`, global | 단어 타임스탬프 |
| AssemblyAI | `/v2/transcript`, 기본 모델 | 화자분리 요청 |

타임스탬프·화자분리는 응답에 부가 정보로만 요청했고 CER 계산에는 쓰지 않았습니다. 재시도는 408/429/5xx에 한해 3회.

## 재현 방법

1. AI Hub에서 KconfSpeech(회의 음성) D20 라벨링데이터·원천데이터를 받아 `evaluation/speech_data/` 아래에 둡니다 (`라벨링데이터/`, `원천데이터/`).
2. `.env.example`을 `.env`로 복사해 5개 엔진 키를 채웁니다. Google은 서비스 계정 JSON을 `secrets/`에 둡니다.
3. 저장소 루트에서 실행합니다.

```bash
pip install -r requirements.txt

# 후보 개수 세기 / 1,000개 목록 만들기 (API 호출 없음) — 시드 2026, 결과는 manifest_B_meeting.csv 와 동일해야 함
python evaluation/make_manifest_B.py --speech-root evaluation/speech_data --count
python evaluation/make_manifest_B.py --speech-root evaluation/speech_data --n 1000

# 3개만 시험 → 전체 1,000개 (--reuse-raw: 받은 응답은 다시 호출하지 않음)
python evaluation/run_stt_model_cer_benchmark.py --manifest evaluation/manifest_B_meeting.csv --run-name B_meeting_1000 --limit 3
python evaluation/run_stt_model_cer_benchmark.py --manifest evaluation/manifest_B_meeting.csv --run-name B_meeting_1000 --reuse-raw

# 기존 20개 재실행
python evaluation/run_stt_model_cer_benchmark.py --run-name B_original20_rerun
```

## 참고 사항

- KconfSpeech 정답 전사에는 비언어 표기(`n/`, `o/`, `b/`, `l/`, `u/`)와 이중 표기(`(1)/(하나)`)가 들어 있습니다. 본 저장소의 CER은 선행 연구의 파이프라인 원본 정규화를 그대로 쓴 값이라 이 표기가 정답 글자에 일부 남아 있으며(1,000개 기준 정답 글자의 약 4.9%), 모든 엔진에 동일하게 적용됩니다. 선행 연구 논문 본문의 Table 2는 이 표기를 정리한 교정 정규화 값입니다.
- 엔진 버전은 호출 시점(2026-10-13 KST) 기준이며, 선행 연구(2026-07-22)와 달라졌을 수 있어 20개를 같은 날 다시 실행했습니다.

## English summary

- **Data:** 1,000 clips sampled from AI Hub KconfSpeech (Korean meeting speech, D20), balanced across 180 sessions, seed 2026, excluding the 20 clips of the prior study; 102.6 min of audio, mean 6.2 s. The prior 20 clips (3.6 min) were re-run the same day.
- **Engines:** CLOVA Speech recognizer/upload, Azure Speech conversation v1 (ko-KR), OpenAI Whisper `whisper-1`, Google STT v2 `latest_long`, AssemblyAI v2. Options identical to the prior study; calls made 2026-10-13 KST; all 5,100 calls succeeded.
- **Metric:** CER (%) after lower-casing, removing whitespace and all characters outside `[0-9a-z가-힣]`. Lower is better.
- **Results (mean CER, 1,000 clips / 20 clips):** CLOVA 12.11 / 6.15, Azure 13.79 / 6.81, Whisper 16.32 / 9.23, Google 16.75 / 8.04, AssemblyAI 17.23 / 10.13.
- **Not redistributed:** audio, corpus transcripts, engine transcripts (`stt_model_transcripts_and_cer_details.csv`) and raw responses, per AI Hub licence. Per-file numeric results, call logs, manifests and scripts are included so the run can be reproduced from the corpus.
