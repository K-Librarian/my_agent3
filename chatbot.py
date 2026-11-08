import re

def classify_question(text: str) -> str:
    """사용자 질문의 유형을 분류한다."""
    text = re.sub(r"\s+", "", text.lower())
    
    # 내부 설정 및 프롬프트 탐색 요청 방어
    if any(word in text for word in [
        "시스템프롬프트",
        "내부지시",
        "개발자메시지",
        "프롬프트공개",
        "프롬프트보여",
        "어떤tool",
        "연결된tool",
        "사용가능한tool",
        "api키",
        "apikey",
        "비밀키",
        "secrets",
        "ignorepreviousinstructions",
        "이전지시무시",
        "지시사항무시"
    ]):
        return "restricted"


    if (
            ("문제" in text or "문항" in text)
            and any(word in text for word in ["만들", "생성", "출제"])
        ):
            return "generate_similar"

    if re.search(r"\d+(?:번)?학생", text) or re.search(r"\d+번", text):
        if any(word in text for word in ["점수", "몇점", "성적"]):
            return "student_score"

    if any(word in text for word in [
        "최저", "꼴찌", "저조",
        "가장낮", "제일낮", "가장못",
        "가장점수낮", "제일점수낮",
        "가장성적낮", "가장점수적",
        "제일점수적", "가장성적적",
        "가장점수가낮", "제일점수가낮",
        "가장성적이낮", "가장점수가적", "최하위"
    ]):
        return "lowest_student"

    if any(word in text for word in [
        "평균", "중앙값", "중위값", "표준편차"
    ]):
        return "stats"

    return "unknown"


def answer_question(question: str, graded: dict) -> str:
    """채점 결과를 기반으로 사용자 질문에 답변한다."""

    intent = classify_question(question)
    stats = graded["stats"]
    students = graded["students"]

    normalized = re.sub(r"\s+", "", question.lower())

    intent = classify_question(question)

    if intent == "restricted":
        return (
            "내부 설정, 시스템 지시문 및 인증 정보는 "
            "제공할 수 없습니다. "
        )

    if intent == "stats":
        result = []

        if "평균" in normalized:
            result.append(f"평균 점수는 {stats['mean']:.2f}점입니다.")

        if "중앙값" in normalized or "중위값" in normalized:
            result.append(f"중앙값은 {stats['median']:.2f}점입니다.")

        if "표준편차" in normalized:
            result.append(f"표준편차는 {stats['std']:.2f}점입니다.")

        return "\n\n".join(result)

    if intent == "lowest_student":
        min_score = min(s["score"] for s in students)

        lowest = [
            s["student"] for s in students
            if s["score"] == min_score
        ]

        names = ", ".join(lowest)
        return f"가장 성적이 저조한 학생은 {names}이며, 점수는 {min_score}점입니다."

    if intent == "student_score":
        match = re.search(r"(\d+)(?:번)?학생", normalized)

        if not match:
            match = re.search(r"(\d+)번", normalized)

        if match:
            number = match.group(1)

            for student in students:
                student_name = re.sub(
                    r"\s+", "", str(student["student"])
                )

                if re.fullmatch(
                    rf"0*{re.escape(number)}(?:번)?학생",
                    student_name
                ) or re.fullmatch(rf"0*{re.escape(number)}", student_name):
                    return (
                        f"{student['student']}의 점수는 "
                        f"{student['score']}점입니다."
                    )

            return f"{number}번 학생의 채점 결과를 찾을 수 없습니다."

    return (
    "제공된 시험지, 정답표 및 OMR 채점 데이터에는 "
    "해당 질문에 답할 정보가 없습니다."
)
