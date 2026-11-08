"""Streamlit: 단일 업로드 창, 자동 분류 및 채점, 단일 시트 엑셀 내보내기."""
import hashlib
import streamlit as st
from grading import detect_files, grade, make_excel

st.set_page_config(page_title='학원 평가 도우미', page_icon='📘', layout='wide')

if 'graded' not in st.session_state:
    st.session_state.graded = None
if 'input_signature' not in st.session_state:
    st.session_state.input_signature = None
if 'excel_bytes' not in st.session_state:
    st.session_state.excel_bytes = None

page = st.sidebar.radio('페이지', ['서비스 소개', '데이터 입력 및 분석'])

if page == '서비스 소개':
    st.title('📘 영어 학원 평가 도우미')
    st.subheader('모의고사 자동 채점과 성적 분석')
    st.write('문제지 PDF, 정답 PDF, OMR 엑셀을 업로드하면 학생별 채점 결과와 전체 통계를 생성합니다.')
    st.info('왼쪽의 **데이터 입력 및 분석** 페이지로 이동하여 시작하세요.')
    st.stop()

st.title('데이터 입력 및 분석')
st.sidebar.markdown('### 시험 파일 업로드')
files = st.sidebar.file_uploader('문제지 PDF · 정답 PDF · OMR XLSX를 한 번에 업로드',
                                 type=['pdf', 'xlsx'], accept_multiple_files=True)
raw_files = [(f.name, f.getvalue()) for f in files]
signature = tuple(sorted((name, hashlib.sha256(data).hexdigest()) for name, data in raw_files))
if signature != st.session_state.input_signature:
    st.session_state.input_signature = signature
    st.session_state.graded = None
    st.session_state.excel_bytes = None

kinds = {}
file_error = None
try:
    kinds = detect_files(raw_files)
except Exception as e:
    file_error = str(e)

with st.sidebar:
    for key, name in [('question', '문제지 PDF'), ('answer', '정답 PDF'), ('omr', 'OMR XLSX')]:
        if key in kinds:
            st.success(f'{name}: {kinds[key][0]}')
        else:
            st.caption(f'미업로드: {name}')
    clicked = st.button('분석 시작', use_container_width=True, type='primary')

if clicked:
    if file_error:
        st.sidebar.error(file_error)
    else:
        missing = [name for key, name in [('question','문제지'), ('answer','정답지'), ('omr','OMR 결과')] if key not in kinds]
        if missing:
            st.sidebar.error('누락된 파일: ' + ', '.join(missing))
        else:
            try:
                with st.spinner('정답 PDF를 읽고 자동 채점하는 중입니다...'):
                    graded = grade(kinds['answer'][1], kinds['omr'][1])
                    excel = make_excel(graded)
                st.session_state.graded = graded
                st.session_state.excel_bytes = excel
                st.sidebar.success('자동 채점이 완료되었습니다.')
            except Exception as e:
                st.session_state.graded = None
                st.session_state.excel_bytes = None
                st.sidebar.error(f'채점 실패: {e}')

with st.sidebar:
    st.download_button('엑셀 추출',
                       data=st.session_state.excel_bytes or b'',
                       file_name='학생_성적_분석.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       disabled=st.session_state.graded is None,
                       use_container_width=True)

if st.session_state.graded is None:
    st.info('왼쪽 사이드바에서 세 종류 파일을 업로드하고 **분석 시작**을 눌러 주세요.')
else:
    result = st.session_state.graded
    stats = result['stats']
    a,b,c,d = st.columns(4)
    a.metric('학생 수', stats['count'])
    b.metric('평균', f"{stats['mean']:.2f}")
    c.metric('중앙값', f"{stats['median']:.2f}")
    d.metric('표준편차', f"{stats['std']:.2f}")
    st.write('가장 많이 틀린 문항 TOP 3:', ', '.join(f'{q}번' for q in stats['top3']))
    st.dataframe([{'학생명': r['student'], '점수': r['score']} for r in result['students']],
                 hide_index=True, use_container_width=True)
    st.caption('챗봇 기능은 이후 단계에서 추가할 예정입니다.')
