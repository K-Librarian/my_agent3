from __future__ import annotations
import re
from io import BytesIO
import fitz

QUESTION_RE = re.compile(r'(?m)^\s*(\d{1,2})\.\s*')

def select_most_missed(graded: dict) -> tuple[int, int]:
    """Return (question number, wrong count); tie-break by smaller number."""
    incorrect = graded['stats']['incorrect']
    if not incorrect:
        raise ValueError('문항별 오답 데이터가 없습니다.')
    q = min(incorrect, key=lambda n: (-incorrect[n], n))
    return int(q), incorrect[q]

def extract_question_text(pdf_bytes: bytes, number: int) -> str:
    """Extract a question in the paper's two-column layout, with limitations.

    For shared passages (41–45), return all page 8 text so the context isn't lost.
    """
    if not 18 <= number <= 45:
        raise ValueError('듣기 문항(1~17번)은 원문 대본이 없어 지원하지 않습니다.')
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        if number >= 41:
            if len(doc) < 8:
                raise ValueError('41~45번의 공통 지문이 있는 페이지를 찾지 못했습니다.')
            page = doc[7]
            left = page.get_text('text', clip=fitz.Rect(75, 145, 425, 1080), sort=True)
            right = page.get_text('text', clip=fitz.Rect(427, 145, 770, 1080), sort=True)
            return (f'[41~45번 공통 지문 포함, 대상 {number}번]\n' + left + '\n' + right).strip()
        for page in doc:
            for side in (fitz.Rect(75, 145, 425, 1080), fitz.Rect(427, 145, 770, 1080)):
                text = page.get_text('text', clip=side, sort=True)
                matches = list(QUESTION_RE.finditer(text))
                for i, match in enumerate(matches):
                    if int(match.group(1)) != number:
                        continue
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                    question = text[match.start():end].strip()
                    if len(question) < 30:
                        raise ValueError(f'{number}번 문항 텍스트가 충분하지 않습니다.')
                    # 25번 도표처럼 그림에 핵심 정보가 있는 유형은 텍스트만으로 불충분
                    return question
    raise ValueError(f'문제지 PDF에서 {number}번을 찾지 못했습니다.')


def prepare_similar_question_source(graded: dict, pdf_bytes: bytes) -> dict:
    """Retrieve the actual most missed question; never silently pick another."""
    number, wrong_count = select_most_missed(graded)
    count = graded['stats']['count']
    if number <= 17:
        return {
            'supported': False, 'number': number, 'wrong_count': wrong_count,
            'message': f'가장 많이 틀린 문항은 {number}번({wrong_count}/{count}명 오답)입니다. 듣기 문항의 대본이 제공되지 않아 유사 문항 생성을 지원하지 않습니다.'
        }
    text = extract_question_text(pdf_bytes, number)
    return {
        'supported': True, 'number': number, 'wrong_count': wrong_count,
        'message': f'가장 많이 틀린 문항은 {number}번({wrong_count}/{count}명 오답)입니다.',
        'question_text': text,
    }