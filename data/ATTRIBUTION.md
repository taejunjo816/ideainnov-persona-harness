[English](ATTRIBUTION.en.md) | **한국어**

# 데이터 출처 / Data Attribution

이 저장소의 `data/personas_kr_batch1.jsonl`과 `data/personas_kr_core_segment.jsonl`에 들어있는
"real_dataset" 페르소나 행은 다음 데이터셋에서 가져왔습니다.

- **Dataset**: Nemotron-Personas-Korea
- **Creator**: NVIDIA
- **Source**: https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
- **License**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- **Changes made**: 원본은 100만 행(약 2.0GB, 26개 필드)입니다. 이 저장소에는 그중 극히 일부
  (수십 행)만 발췌해 필드를 간추린 하위 집합을 실었습니다. 일부 행(`personas_kr_batch1.jsonl`의
  15개 행, `personas_kr_core_segment.jsonl`의 real_dataset 행 전부)은 네트워크가 제한된 환경에서
  Hugging Face datasets-server API를 통해 조회했으며, 그 과정에서 원문이 요약·일부 영어 의역된
  행이 섞여 있습니다 — 정확한 원문이 필요하면 `data/prepare_personas.py`로 parquet 원본을 직접
  읽어 재수집하세요.
- **Not from this dataset**: `data/personas_kr_core_segment.jsonl`의 `illustrative_construction`
  으로 표시된 5개 행은 실제 데이터셋 행이 아니라, IDEAINNOV의 타깃 도메인에 맞춰 이 프로젝트에서
  직접 구성한 예시 페르소나입니다. CC BY 4.0 표시 의무 대상이 아니지만, 실제 유저 데이터로
  오인되지 않도록 어디서나 이 표시를 유지해야 합니다.

CC BY 4.0은 출처 표시 조건 하에 재배포·상업적 이용을 포함해 자유롭게 허용합니다. 이 저장소를
공개하거나 재배포할 때는 위 출처(NVIDIA, 데이터셋명, 링크, 라이선스)를 유지해 주세요.
