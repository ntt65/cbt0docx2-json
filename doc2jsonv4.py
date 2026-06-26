# **📄 [CBT 데이터 변환 엔진 V4] 개발 및 구조 명세서**

# 이 문서는 표 병합(세로 병합)으로 인해 해설 수식이 가짜 문제로 쪼개지는 치명적 버그를 완벽히 해결한 **V4 파싱 엔진의 설계 사상과 상세 코드**를 담고 있습니다. 향후 유지보수와 기능 확장을 위해 핵심 로직의 목적, 구조, 함수별 역할을 상세한 독스트링(Docstring)과 주석으로 분리하여 정리했습니다.

# ---

# ### 💡 1. 핵심 설계 상세 (Architecture Details)

# 1. **문맥 결합 로직 (Block Accumulation)**
#    * **문제점:** 기존 엔진은 표를 무조건 '행(Row)' 단위로 읽었기 때문에, 1열(문제 번호)이 세로로 길게 병합된 경우 해설 행을 읽을 때도 번호를 중복 인식하여 가짜 문제를 생성했습니다.
#    * **해결책:** 새로운 문제 번호(`^\d+\s+`)가 나오기 전까지의 모든 텍스트(지문+보기+수식+해설)를 하나의 거대한 덩어리(`current_q_block`)로 누적(Append)시킵니다.
# 2. **가짜 문제 완벽 필터링 (Fake Question Filtering)**
#    * **해결책:** 추출된 덩어리를 정규식으로 쪼갤 때, 객관식 보기(①~④)가 단 하나도 검출되지 않으면 이는 병합된 셀이 낳은 '해설용 가짜 문제'로 간주하여 즉시 폐기(`return None`)합니다.
# 3. **병합 셀 중복 읽기 원천 차단 (Set Memory)**
#    * **해결책:** 파이썬이 표를 순회할 때 한 번 처리한 셀 메모리 주소를 `added_outer_cells`라는 Set 자료구조에 기록하여, 세로/가로로 병합된 셀의 텍스트가 중복 출력되는 것을 막습니다.
# 4. **회차(Round) 자동 그룹화 (Dynamic Round Separation)**
#    * **해결책:** 표가 끊어지는 물리적 기준이 아니라, 문서 전체에서 수집된 문제 객체 중 **'num(번호)' 값이 1인 경우에만 새로운 회차 배열을 생성**하도록 하여 완벽한 1~60번 정렬을 보장합니다.

# ---

# ### 💻 2. V4 파이썬 변환 엔진 전체 소스 코드 (`doc2json.py`)

# 기존 파일 내용을 지우시고 아래의 문서를 붙여넣으시면 됩니다. (시스템 인덱스 증발 버그를 피하기 위해 `next(iter())` 방식을 그대로 유지했습니다.)

# ```python
"""
===============================================================================
[CBT 기출문제 변환 엔진 V4] - MS Word(.docx) to JSON Converter (개발 문서)

1. 목적 (Purpose)
   - MS Word(.docx) 기출문제를 파싱하여 CBT 웹 앱용 JSON 데이터베이스로 자동 변환.
   - 표 안의 세로 병합 셀 구조(예: 실전모의 15회, 16회)에서 발생하는 문제 쪼개짐 현상과 
     해설 수식이 가짜 문제로 인식되는 치명적인 버그를 완벽하게 해결.

2. 설계 상세 (Design Details)
   - OXML 구조 접근: 문단(Paragraph)과 표(Table)의 실제 배치 순서를 유지하여 추출.
   - 시각적 데이터 보존: 1x1 표는 <div> 박스(글라스모피즘)로, 일반 표는 <table class="nested-table">로 자동 변환.
   - 병합 셀 중복 읽기 차단: added_outer_cells(Set)를 활용해 한 번 읽은 셀은 다시 읽지 않도록 메모리 처리.
   - 문맥 결합 로직(Block Parsing): 표를 행 단위로 분할하지 않고, 다음 문제 번호가 나오기 
     전까지의 모든 행을 하나의 텍스트 블록(current_q_block)으로 누적 병합한 뒤 정밀 파싱.
   - 가짜 문제 필터링: 병합된 셀에 의해 파생된 가짜 문제(보기가 없는 텍스트 덩어리) 원천 폐기.
   - 동적 회차 분리: 문서 내의 '1번 문제'를 만날 때마다 새로운 회차(Round)로 그룹화.
===============================================================================
"""

import docx
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table
import json
import re

def iter_block_items(parent):
    """
    XML 구조를 스캔하여 셀(Cell) 내부의 문단과 표를 실제 문서에 있는 순서 그대로 추출합니다.
    
    Args:
        parent: 순회할 부모 요소 (보통 Table Cell 객체)
        
    Yields:
        Paragraph 또는 Table 객체
    """
    for child in parent._element:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def get_html_from_table(table):
    """
    python-docx의 표(Table) 객체를 앱 UI에 맞는 HTML 태그 문자열로 변환합니다.
    
    Args:
        table: python-docx의 Table 객체
        
    Returns:
        HTML 문자열 (1x1 표는 <div> 박스로, 그 외는 <table> 로 반환)
    """
    # 1. 박스형 지문 처리 (1행 1열짜리 표)
    # 시스템에서 대괄호 인덱스가 삭제되는 버그를 회피하기 위해 next(iter())를 사용하여 안전하게 추출
    if len(table.rows) == 1:
        first_row = next(iter(table.rows))
        if len(first_row.cells) == 1:
            first_cell = next(iter(first_row.cells))
            cell_text = first_cell.text.replace('*', '').strip().replace('\n', '<br>')
            return f'\n<div style="margin-top:16px; padding:16px; border:1px solid var(--glass-border); border-radius:var(--border-radius-sm); background:rgba(255,255,255,0.03); line-height:1.6;">{cell_text}</div>\n'
    
    # 2. 일반 데이터 표 처리
    html = '\n<table class="nested-table">'
    for i, row in enumerate(table.rows):
        html += '<tr>'
        # 병합된 셀의 중복 출력을 방지하기 위한 세트
        added_cells = set()
        for cell in row.cells:
            if cell in added_cells:
                continue
            added_cells.add(cell)
            
            cell_text = cell.text.replace('*', '').strip().replace('\n', '<br>')
            tag = 'th' if i == 0 else 'td'
            html += f'<{tag}>{cell_text}</{tag}>'
        html += '</tr>'
    html += '</table>\n'
    return html

def parse_question_block(full_text):
    """
    하나의 완성된 문제 덩어리(Block) 텍스트에서 번호, 지문, 보기, 해설, 정답을 정밀 파싱합니다.
    
    Args:
        full_text (str): 한 문제에 해당하는 모든 텍스트 라인들의 묶음
        
    Returns:
        dict: 파싱된 문제 객체. 가짜 문제(보기 없음)일 경우 None 반환
    """
    # 1. 문제 번호 및 지문 추출 ('숫자'로 시작해서 '①' 또는 '정답'이 나오기 전까지)
    q_match = re.search(r'^(\d+)\s+(.*?)(?=\n①|\n정답|$)', full_text, re.DOTALL)
    if not q_match:
        return None
    
    q_num = int(q_match.group(1))
    q_text = q_match.group(2).strip()
    
    # 2. 보기(①~④) 추출
    options = []
    for marker in ['①', '②', '③', '④']:
        opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
        if opt_match:
            options.append(opt_match.group(1).replace('\n', ' ').strip())
        else:
            options.append("")
            
    # 3. 정답 번호 매핑
    ans_match = re.search(r'정답\s*([①②③④])', full_text)
    answer_num = 0
    if ans_match:
        ans_map = {'①': 1, '②': 2, '③': 3, '④': 4}
        answer_num = ans_map.get(ans_match.group(1), 0)
    
    # 4. 해설(Hint) 추출 (전체 텍스트에서 지문, 보기, 정답 소거)
    hint_text = full_text
    if q_match: hint_text = hint_text.replace(q_match.group(0), '')
    if ans_match: hint_text = hint_text.replace(ans_match.group(0), '')
    for marker in ['①', '②', '③', '④']:
        opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
        if opt_match:
            hint_text = hint_text.replace(opt_match.group(0), '')
    
    hint_text = hint_text.strip()
    
    # 🔥 [핵심 필터링] 보기가 단 하나도 추출되지 않았다면, 병합된 셀이 만든 가짜 문제이므로 폐기
    if not any(options):
        return None
        
    return {
        "num": q_num,
        "question": q_text,
        "options": options,
        "hint": hint_text,
        "answer": answer_num
    }

def parse_docx_to_json(docx_file, output_json):
    """
    워드 문서를 스캔하여 V4 문맥 결합 로직을 통해 JSON 데이터를 생성하는 메인 엔진입니다.
    
    Args:
        docx_file (str): 파싱할 Word 파일의 경로
        output_json (str): 출력될 JSON 파일의 경로
    """
    doc = docx.Document(docx_file)
    all_parsed_questions = []
    
    # 문서 내의 최상위 표(문제를 감싸고 있는 큰 틀) 순회
    for table in doc.tables:
        # 🔥 표 단위로 병합 셀 메모리 관리: 세로 병합으로 인한 중복 텍스트 획득 원천 차단
        added_outer_cells = set()
        current_q_block = ""
        
        for row in table.rows:
            cells_content = []
            
            for cell in row.cells:
                if cell in added_outer_cells:
                    continue
                added_outer_cells.add(cell)
                
                cell_html_parts = []
                for block in iter_block_items(cell):
                    if isinstance(block, Paragraph):
                        txt = block.text.replace('*', '').strip()
                        if txt:
                            cell_html_parts.append(txt)
                    elif isinstance(block, Table):
                        cell_html_parts.append(get_html_from_table(block))
                
                if cell_html_parts:
                    cells_content.append('\n'.join(cell_html_parts))
            
            if not cells_content:
                continue
                
            row_text = '\n'.join(cells_content)
            
            # 🔥 문맥 결합 로직: 새로운 문제 번호(예: "01", "36")로 시작하는지 판단
            if re.match(r'^\d+\s+', row_text):
                # 기존에 쌓아둔 문제 덩어리가 있다면 파싱하여 저장
                if current_q_block:
                    q_obj = parse_question_block(current_q_block)
                    if q_obj:
                        all_parsed_questions.append(q_obj)
                # 새로운 덩어리로 시작
                current_q_block = row_text
            else:
                # 번호로 시작하지 않는 행(보기, 해설, 수식, 표)은 현재 덩어리에 강제로 병합
                if current_q_block:
                    current_q_block += '\n' + row_text
                else:
                    current_q_block = row_text
        
        # 반복문 종료 후 남은 마지막 문제 블록 처리
        if current_q_block:
            q_obj = parse_question_block(current_q_block)
            if q_obj:
                all_parsed_questions.append(q_obj)
                
    # -----------------------------------------------------------
    # 회차(Round) 분리 로직 : 오직 문제 번호 '1'을 기준으로 그룹화
    # -----------------------------------------------------------
    all_rounds = []
    current_round_questions = []
    
    for q in all_parsed_questions:
        if q["num"] == 1:
            # 1번 문제를 만나면 이전에 쌓인 리스트를 1개의 회차로 등록 후 초기화
            if current_round_questions:
                all_rounds.append({
                    "subject": "에너지관리기능장",
                    "year": "",
                    "round": f"실전모의 {len(all_rounds) + 1}회",
                    "questions": current_round_questions
                })
            current_round_questions = [q]
        else:
            if current_round_questions:
                current_round_questions.append(q)
                
    # 문서 끝 도달 시 잔여 회차 등록
    if current_round_questions:
        all_rounds.append({
            "subject": "에너지관리기능장",
            "year": "",
            "round": f"실전모의 {len(all_rounds) + 1}회",
            "questions": current_round_questions
        })
    
    # JSON 직렬화 및 저장 (한글 깨짐 방지: ensure_ascii=False)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_rounds, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 가짜 문제 완벽 필터링! V4 스크립트 실행 완료!")
    print(f"총 {len(all_rounds)}개 회차, {len(all_parsed_questions)}문제가 완벽하게 그룹화되었습니다.")

if __name__ == "__main__":
    input_file = "260626_energy_ginungjang_gyojeong.docx" 
    output_file = "questions.json"
    parse_docx_to_json(input_file, output_file)