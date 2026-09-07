[English](ATTRIBUTION.en.md) | 한국어

[데이터 출처]

이 저장소에 실린 "real_dataset" 페르소나 행은 NVIDIA 의 Nemotron-Personas 데이터셋에서 가져왔습니다. 한국 표본과 미국 표본 두 가지를 씁니다.

한국 표본

- Dataset: Nemotron-Personas-Korea
- Creator: NVIDIA
- Source: https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- 해당 파일: `personas_kr_batch1.jsonl`, `personas_kr_core_segment.jsonl`, `../copy-optimizer/data/personas_kr_25_filtered.jsonl`

미국 표본

- Dataset: Nemotron-Personas-USA
- Creator: NVIDIA
- Source: https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- 해당 파일: `../copy-optimizer/data/personas_us_25_filtered.jsonl`

[변경한 내용]

원본은 각각 100만 행 규모입니다. 이 저장소에는 그중 극히 일부만 발췌해 필드를 간추린 하위 집합을 실었습니다.

`personas_kr_batch1.jsonl` 의 15개 행과 `personas_kr_core_segment.jsonl` 의 real_dataset 행 전부는 네트워크가 제한된 환경에서 Hugging Face datasets-server API 를 통해 조회했으며, 그 과정에서 원문이 요약되거나 일부 영어로 의역된 행이 섞여 있습니다. 정확한 원문이 필요하면 `prepare_personas.py` 로 parquet 원본을 직접 읽어 재수집하십시오.

`copy-optimizer/data/` 의 두 filtered 파일은 각 800명 풀에서 `filter_personas.py` 로 걸러낸 25명입니다. 필터 조건은 만 22세 이상이면서 전문·연구·기술직이거나 고등교육 이상 또는 STEM 전공인 경우입니다. 통과율은 한국 34.0퍼센트, 미국 35.1퍼센트이며 통과 표본에 미성년자는 없습니다. 통과율 원본은 같은 폴더의 `_filter_stats_kr.json`, `_filter_stats_us.json` 에 있습니다.

필터를 건 이유는 무작위 표본에 광고 판정과 무관한 행이 섞이기 때문입니다. 실제로 미국 무작위 표본의 첫 행이 생후 0세였습니다. 다만 자사 제품에 딱 맞는 사람으로 좁히면 동어반복이 되므로, 광고가 실제로 노출될 만한 성인 모집단을 남기는 선에서 멈췄습니다.

[이 데이터셋에서 온 것이 아닌 행]

`personas_kr_core_segment.jsonl` 에서 `illustrative_construction` 으로 표시된 5개 행은 실제 데이터셋 행이 아니라, IDEAINNOV 의 타깃 도메인에 맞춰 이 프로젝트에서 직접 구성한 예시 페르소나입니다. CC BY 4.0 표시 의무 대상은 아니지만, 실제 유저 데이터로 오인되지 않도록 어디서나 이 표시를 유지해야 합니다.

[재배포 조건]

CC BY 4.0 은 출처 표시 조건 하에 재배포와 상업적 이용을 포함해 자유롭게 허용합니다. 이 저장소를 공개하거나 재배포할 때는 위 출처(NVIDIA, 데이터셋명, 링크, 라이선스)를 유지해 주십시오.
