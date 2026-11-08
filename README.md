# 영어 학원 평가 도우미


학번: 202334433

이름: 김승연

배포 URL: https://myagent3-jvdhxj635qgiaadddkrhkg.streamlit.app

기능: PDF 문제지/정답지 및 OMR XLSX를 **한 업로드 창**에서 자동 분류, 정답 PDF 자동 읽기, 자동 채점, 통계 및 **단일 워크시트 엑셀** 다운로드.

## 실행

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

실제 업로드 예시: 2026학년도 대학수학능력시험 영어 문제.pdf, 영어 정답.pdf, sample_data.xlsx.

현재 정답 추출기는 제공된 '문항번호-정답-배점' 정답표 텍스트 패턴에 맞춤. 다른 형식의 답안 PDF는 예외 처리되며 검토 및 파서 확장이 필요함.

데이터 재업로드/교체 시 이전 채점 결과와 다운로드는 초기화.
