import os
import hashlib
import streamlit as st
from grading import detect_files, grade, make_excel
from chatbot import answer_question, classify_question
from similar_question import generate_similar_question


st.set_page_config(
    page_title="학원 평가 도우미",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* 채팅 메시지의 긴 문장 자동 줄바꿈 */
[data-testid="stChatMessage"] {
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: normal;
}

/* Markdown으로 출력되는 영어 지문 */
[data-testid="stChatMessage"] p {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

/* 코드 블록으로 출력되는 경우에도 줄바꿈 */
[data-testid="stChatMessage"] pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
</style>
""", unsafe_allow_html=True)

# 파일이나 페이지를 바꿔도 채점 결과를 유지하기 위한 세션 데이터
for key, initial in {
    "graded": None,
    "input_signature": None,
    "excel_bytes": None,
    "saved_raw_files": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = initial


def show_home():
    st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)

    left, center, right = st.columns([1, 1, 1])

    with center:
        st.image("images/slogan_4.png", use_container_width=True)

    st.markdown(
        "<h2 style='text-align: center; margin-top: 35px;'>"
        "OO 학원 평가 도우미"
        "</h2>",
        unsafe_allow_html=True
    )


def show_analysis():
    # 실제 st.sidebar이므로 화면 왼쪽 화살표로 접고 펼칠 수 있음
    with st.sidebar:
        st.subheader("시험 파일 업로드")
        uploads = st.file_uploader(
            "문제지 PDF · 정답 PDF · OMR XLSX를 한 번에 업로드",
            type=["pdf", "xlsx"],
            accept_multiple_files=True,
            key="exam_uploads",
        )

        if uploads:
            raw_files = [(f.name, f.getvalue()) for f in uploads]
            signature = tuple(sorted(
                (name, hashlib.sha256(data).hexdigest()) for name, data in raw_files
            ))
            if signature != st.session_state.input_signature:
                st.session_state.input_signature = signature
                st.session_state.saved_raw_files = raw_files
                st.session_state.graded = None
                st.session_state.excel_bytes = None
        else:
            # 페이지 이동 뒤 업로드 위젯이 초기화되어도 기존 분석 상태는 유지
            raw_files = st.session_state.saved_raw_files
            if raw_files:
                st.caption("이전에 등록한 시험 파일을 유지하고 있습니다.")

        kinds = {}
        file_error = None
        try:
            kinds = detect_files(raw_files)
        except Exception as exc:
            file_error = str(exc)
            st.error(file_error)

        for key, label in [
            ("question", "문제지 PDF"),
            ("answer", "정답 PDF"),
            ("omr", "OMR XLSX"),
        ]:
            if key in kinds:
                st.success(f"{label}: {kinds[key][0]}")
            else:
                st.caption(f"미업로드: {label}")

        if st.button("분석 시작", type="primary", use_container_width=True):
            if file_error:
                st.error("파일 형식을 확인해 주세요.")
            else:
                missing = [label for key, label in [
                    ("question", "문제지 PDF"),
                    ("answer", "정답 PDF"),
                    ("omr", "OMR XLSX"),
                ] if key not in kinds]
                if missing:
                    st.error("누락된 파일: " + ", ".join(missing))
                else:
                    try:
                        with st.spinner("정답 PDF를 읽고 채점하는 중입니다..."):
                            graded = grade(kinds["answer"][1], kinds["omr"][1])
                            excel_data = make_excel(graded)
                        st.session_state.graded = graded
                        st.session_state.excel_bytes = excel_data
                        st.session_state.chat_history = []
                        st.success("자동 채점이 완료되었습니다.")
                    except Exception as exc:
                        st.session_state.graded = None
                        st.session_state.excel_bytes = None
                        st.error(f"채점 실패: {exc}")

        st.download_button(
            "엑셀 추출",
            data=st.session_state.excel_bytes or b"",
            file_name="학생_성적_분석.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=st.session_state.graded is None,
            use_container_width=True,
        )

        if st.button("파일 및 채점 결과 초기화", use_container_width=True):
            st.session_state.saved_raw_files = []
            st.session_state.input_signature = None
            st.session_state.graded = None
            st.session_state.excel_bytes = None
            
            # 위젯에 직접 값을 대입하지 않고, 제거하여 다음 실행에서 초기화
            st.session_state.pop("exam_uploads", None)
            st.rerun()

        # 채팅 기록 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    st.subheader("AI 성적 분석 챗봇")

    # 채팅 내역 출력
    chat_container = st.container(height=550)

    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"], unsafe_allow_html=True)

    # 채점 완료 전까지 입력 비활성화
    user_input = st.chat_input(
        "성적 분석에 대해 질문해 주세요.",
        disabled=st.session_state.graded is None
    )

    if user_input:
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })
        # 채점 결과를 이용해 답변 생성
        if classify_question(user_input) == "generate_similar":
            # 업로드된 문제지 PDF 가져오기
            files = detect_files(st.session_state.saved_raw_files)
            question_pdf = files["question"][1]
            # API 키 가져오기
            try:
                api_key = st.secrets["OPENAI_API_KEY"]
            except (KeyError, FileNotFoundError):
                api_key = os.environ.get("OPENAI_API_KEY")

            with st.spinner("유사 영어 문제 생성 중..."):
                answer = generate_similar_question(
                    st.session_state.graded,
                    question_pdf,
                    api_key
                )
        else:
            answer = answer_question(
                user_input,
                st.session_state.graded
            )

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer
        })
        st.rerun()


# 페이지 선택은 기본 사이드바 밖, Streamlit의 상단 내비게이션으로 이동
pages = [
    st.Page(show_home, title="서비스 소개", icon="🏠", default=True),
    st.Page(show_analysis, title="데이터 입력 및 분석", icon="📊"),
]
selected_page = st.navigation(pages, position="sidebar")
selected_page.run()
