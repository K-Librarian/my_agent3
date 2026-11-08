"""시험 데이터 분류·채점·단일 시트 XLSX 생성 (정답 하드코딩 금지)."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
import statistics
import tempfile
from typing import Any

import fitz
from artifact_tool import Blob, SpreadsheetFile, Workbook

CIRCLED = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5}


def pdf_text(raw: bytes) -> str:
    with fitz.open(stream=raw, filetype='pdf') as doc:
        return '\n'.join(page.get_text(sort=False) for page in doc)


def read_spreadsheet(raw: bytes) -> list[list]:
    # artifact_tool은 파일 기반 import를 지원하므로 임시 파일을 사용
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'omr.xlsx'
        p.write_bytes(raw)
        workbook = SpreadsheetFile.import_xlsx(Blob.load(str(p)))
        sheets = list(workbook.worksheets.items)
        if not sheets:
            raise ValueError('엑셀에 시트가 없습니다.')
        return sheets[0].get_used_range().values


def detect_files(files: list[tuple[str, bytes]]) -> dict[str, tuple[str, bytes]]:
    """콘텐츠를 우선 사용하여 파일 유형 검증; 이름만으로 추측하지 않음."""
    detected = {}
    for name, raw in files:
        ext = Path(name).suffix.lower()
        if ext == '.pdf':
            content = pdf_text(raw)
            if '정답표' in content and '배점' in content and '문항' in content:
                kind = 'answer'
            elif '문제지' in content or ('영어 영역' in content and '고르시오' in content):
                kind = 'question'
            else:
                raise ValueError(f'{name}: PDF 내용을 보고 문제지/정답지를 판별하지 못했습니다.')
        elif ext == '.xlsx':
            rows = read_spreadsheet(raw)
            header = [str(v).strip() if v is not None else '' for v in rows[0]] if rows else []
            if any(re.fullmatch(r'Q\d{1,3}', h, re.I) for h in header) and (('학생명' in header) or ('학생번호' in header) or ('학생ID' in header)):
                kind = 'omr'
            else:
                raise ValueError(f'{name}: OMR 데이터의 학생 식별 열 및 Q01~ 문항 열을 찾지 못했습니다.')
        else:
            raise ValueError(f'{name}: 지원하지 않는 형식입니다. PDF 또는 XLSX만 업로드하세요.')
        if kind in detected:
            raise ValueError(f'{name}: {kind} 유형의 파일이 중복되었습니다.')
        detected[kind] = (name, raw)
    return detected


def parse_answers(raw: bytes) -> dict[int, dict[str, int]]:
    content = pdf_text(raw)
    # 업로드 정답표는 '문항번호 / 정답 / 배점'이 반복되는 3열 조합
    triples = re.findall(r'(?m)^\s*(\d{1,3})\s*\n\s*([①②③④⑤1-5])\s*\n\s*(\d{1,2})\s*(?=\n|$)', content)
    if not triples:
        raise ValueError('정답 PDF에서 문항번호/정답/배점을 추출하지 못했습니다. PDF 표 구조를 확인하세요.')
    answers = {}
    for number, choice, point in triples:
        q = int(number)
        a = CIRCLED[choice] if choice in CIRCLED else int(choice)
        p = int(point)
        if q in answers:
            raise ValueError(f'정답 PDF에서 {q}번 문항이 중복되었습니다.')
        if not (1 <= a <= 5 and 0 < p <= 20):
            raise ValueError(f'{q}번 정답 또는 배점 값이 유효하지 않습니다.')
        answers[q] = {'answer': a, 'points': p}
    ordered = sorted(answers)
    if ordered != list(range(1, max(ordered) + 1)):
        raise ValueError('정답 PDF 문항 번호에 누락이 있습니다.')
    return answers


def normalize_choice(value: Any) -> int | None:
    if value is None or str(value).strip() == '':
        return None
    v = str(value).strip()
    if v in CIRCLED:
        return CIRCLED[v]
    try:
        k = float(v)
        if k.is_integer() and 1 <= k <= 5:
            return int(k)
    except ValueError:
        pass
    raise ValueError(f'OMR에서 유효하지 않은 선택지: {value!r}')


def grade(answer_pdf: bytes, omr_xlsx: bytes) -> dict:
    answer_map = parse_answers(answer_pdf)
    rows = read_spreadsheet(omr_xlsx)
    if len(rows) < 2:
        raise ValueError('OMR 엑셀에 학생 데이터가 없습니다.')
    columns = [str(v).strip() if v is not None else '' for v in rows[0]]
    student_col = next((columns.index(c) for c in ('학생명', '학생번호', '학생ID') if c in columns), None)
    if student_col is None:
        raise ValueError('학생명 또는 학생번호 열이 없습니다.')
    qcols = {}
    for idx, col in enumerate(columns):
        m = re.fullmatch(r'Q0*(\d+)', col, re.I)
        if m:
            q = int(m.group(1))
            if q in qcols:
                raise ValueError(f'OMR의 Q{q:02d} 열 중복')
            qcols[q] = idx
    missing = sorted(set(answer_map) - set(qcols))
    extra = sorted(set(qcols) - set(answer_map))
    if missing or extra:
        raise ValueError(f'OMR/정답 문항 불일치. OMR에 없는 문항: {missing}; 정답표에 없는 문항: {extra}')
    questions = sorted(answer_map)
    out = []
    for n, record in enumerate(rows[1:], start=2):
        student = str(record[student_col]).strip() if len(record) > student_col and record[student_col] is not None else ''
        if not student:
            raise ValueError(f'OMR 엑셀 {n}행 학생 식별자가 비어 있습니다.')
        correct = {}
        score = 0
        for q in questions:
            index = qcols[q]
            value = normalize_choice(record[index] if index < len(record) else None)
            matched = value == answer_map[q]['answer']
            correct[q] = bool(matched)
            if matched:
                score += answer_map[q]['points']
        out.append({'student': student, 'score': score, 'correct': correct})
    if len({r['student'] for r in out}) != len(out):
        raise ValueError('OMR의 학생 식별자에 중복이 있습니다.')
    scores = [r['score'] for r in out]
    incorrect = {q: sum(not r['correct'][q] for r in out) for q in questions}
    top3 = sorted(questions, key=lambda q: (-incorrect[q], q))[:3]
    stats = {'count': len(out), 'maximum': sum(v['points'] for v in answer_map.values()),
             'mean': statistics.mean(scores), 'median': statistics.median(scores),
             'std': statistics.pstdev(scores), 'top3': top3,
             'incorrect': incorrect}
    return {'answers': answer_map, 'students': out, 'stats': stats}


def make_excel(graded: dict) -> bytes:
    """하나의 워크시트에 통계 + 학생별 점수/정오표를 함께 기록."""
    wb = Workbook.create()
    sh = wb.worksheets.add('성적분석')
    stats = graded['stats']
    questions = sorted(graded['answers'])
    sh.get_range('A1').values = [['영어 모의고사 자동 채점 결과']]
    sh.get_range('A2:B7').values = [
        ['응시 학생 수', stats['count']],
        ['총 배점', stats['maximum']],
        ['평균', round(stats['mean'], 4)],
        ['중앙값', round(stats['median'], 4)],
        ['표준편차 (모집단)', round(stats['std'], 4)],
        ['오답 많은 문항 TOP 3', ', '.join(f'{q}번' for q in stats['top3'])],
    ]
    sh.get_range('A9').values = [['학생별 성적 및 문항별 정답 여부 (O=정답, X=오답)']]
    header = ['학생명', '점수'] + [f'Q{q:02d}' for q in questions]
    matrix = [header] + [[r['student'],r['score']] + ['O' if r['correct'][q] else 'X' for q in questions]
                          for r in graded['students']]
    sh.get_range_by_indexes(9, 0, len(matrix), len(header)).values = matrix
    sh.get_range('A:A').format.column_width = 22
    sh.get_range('B:B').format.column_width = 15
    sh.get_range_by_indexes(0, 2, 1, len(header)-2).format.column_width = 9
    sh.get_range_by_indexes(9, 0, 1, len(header)).format.fill = '#DCEAF8'
    sh.get_range('A1:B1').format.fill = '#DCEAF8'
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'report.xlsx'
        SpreadsheetFile.export_xlsx(wb).save(str(p))
        return p.read_bytes()
