from __future__ import annotations

import base64
import re

import fitz

_ITEM = re.compile(r"^\s*(\d{1,2})\.")


def extract_question_images(pdf_bytes: bytes, number: int) -> list[str]:
    """선택된 문항에 해당하는 JPEG data URL 1~2개 반환.

    18~40번은 해당 열의 단일 문항 영역을 자른다.
    41~45번은 8쪽 공통 지문이 양쪽 열에 있으므로 두 열 모두 반환한다.
    """
    if not 18 <= number <= 45:
        raise ValueError("듣기 문제(1~17번)는 이미지 추출 대상이 아닙니다.")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if number >= 41:
            if len(doc) < 8:
                raise ValueError("공통 지문을 포함한 마지막 페이지가 없습니다.")
            page = doc[7]
            regions = [fitz.Rect(79, 148, 424, 1090), fitz.Rect(430, 148, 770, 1090)]
        else:
            found = None
            for page in doc:
                # Extract block starts from PDF, not a manually encoded question-location table.
                blocks = []
                for b in page.get_text("blocks"):
                    match = _ITEM.match(b[4])
                    if match and 18 <= int(match.group(1)) <= 45:
                        blocks.append((int(match.group(1)), fitz.Rect(b[:4])))
                for item, rect in blocks:
                    if item == number:
                        found = (page, rect, blocks)
                        break
                if found:
                    break
            if not found:
                raise ValueError(f"PDF에서 {number}번 문항의 위치를 찾지 못했습니다.")
            page, rect, blocks = found
            left = rect.x0 < page.rect.width / 2
            x0, x1 = (79, 424) if left else (430, 770)
            # Start just above the item's heading; stop before the next heading in same column.
            next_y = [
                b.y0 for n, b in blocks
                if (b.x0 < page.rect.width / 2) == left and b.y0 > rect.y0 + 3
            ]
            bottom = min(next_y) - 7 if next_y else 1090
            region = fitz.Rect(x0, max(145, rect.y0 - 8), x1, min(1090, bottom))
            if region.height < 70:
                raise ValueError(f"{number}번 문항의 이미지 범위가 너무 작습니다.")
            regions = [region]

        results = []
        for region in regions:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), clip=region, alpha=False)
            raw = pix.tobytes("jpeg", jpg_quality=82)
            results.append("data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii"))
        return results
