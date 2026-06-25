"""
===============================================================================
[CBT 기출문제 변환 엔진 V2] - MS Word(.docx) to JSON Converter

1. 목적 (Purpose)
   - MS Word(.docx) 형식으로 작성된 자격증 기출문제(에너지관리기능장 등)를 파싱하여, 
     CBT 웹 앱에서 즉시 사용할 수 있는 구조화된 JSON 데이터베이스로 자동 변환합니다.

2. 설계 상세 (Design Details)
   - OXML 구조 접근: python-docx 라이브러리의 기본 텍스트 추출 한계를 극복하기 위해 
     내부 XML(OXML) 구조에 직접 접근하여 문단(Paragraph)과 표(Table)의 실제 배치 순서를 유지합니다.
   - 시각적 데이터 보존: 지문이나 해설에 포함된 데이터 표(Table)와 박스형 지문(1x1 표)이 
     단순 텍스트로 뭉개지는 현상을 방지하고, 이를 앱 디자인(글라스모피즘, 다크모드)에 맞는 
     HTML 태그(<table class="nested-table">, <div>)로 즉시 렌더링합니다.
   - 정규표현식(Regex) 라우팅: 수집된 전체 텍스트 블록에서 정규식을 이용해 
     '문제 번호 및 지문', '보기(①~④)', '정답', '해설(Hint)' 영역을 정밀하게 분리해 냅니다.
   - 인덱스 버그 회피: 특정 환경에서 배열 인덱스 0이 누락되는 파싱 버그를 원천 차단하기 위해 
     next(iter()) 제너레이터 패턴을 적용하여 안정성을 극대화했습니다.
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
    XML 구조를 스캔하여 셀(Cell) 내부의 문단과 표를 실제 문서에 있는 순서 그대로 추출하는 제너레이터 함수.
    
    Args:
        parent: 순회할 부모 요소 (보통 Table Cell 객체)
        
    Yields:
        Paragraph 또는 Table 객체
    """
    for child in parent._element:
        # 자식 요소가 문단(Paragraph) 타입인 경우
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        # 자식 요소가 표(Table) 타입인 경우
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def get_html_from_table(table):
    """
    python-docx의 표(Table) 객체를 앱 UI에 맞는 HTML 태그 문자열로 변환하는 함수.
    
    Args:
        table: python-docx의 Table 객체
        
    Returns:
        변환된 HTML 문자열 (1x1 표는 <div> 박스로, 그 외는 <table> 로 반환)
    """
    
    # 1. 박스형 지문 처리 (1행 1열짜리 표)
    # 시스템에서 대괄호 인덱스가 삭제되는 버그를 회피하기 위해 next(iter())를 사용하여 첫 번째 요소를 안전하게 추출
    if len(table.rows) == 1:
        first_row = next(iter(table.rows))
        if len(first_row.cells) == 1:
            first_cell = next(iter(first_row.cells))
            # 불필요한 별표(*) 제거 및 줄바꿈을 <br> 태그로 치환
            cell_text = first_cell.text.replace('*', '').strip().replace('\n', '<br>')
            
            # 글라스모피즘 스타일이 적용된 반투명 박스 반환
            return f'\n<div style="margin-top:16px; padding:16px; border:1px solid var(--glass-border); border-radius:var(--border-radius-sm); background:rgba(255,255,255,0.03); line-height:1.6;">{cell_text}</div>\n'
    
    # 2. 일반 데이터 표 처리 (행과 열이 여러 개인 경우)
    html = '\n<table class="nested-table">'
    
    for i, row in enumerate(table.rows):
        html += '<tr>'
        
        # Word 표에서 병합된 셀(Merged Cells)은 내부적으로 여러 번 반복 출력되므로,
        # 중복 출력을 방지하기 위해 이미 추가된 셀을 추적하는 set 자료구조 사용
        added_cells = set()
        
        for cell in row.cells:
            if cell in added_cells:
                continue
            added_cells.add(cell)
            
            # 셀 텍스트 정제
            cell_text = cell.text.replace('*', '').strip().replace('\n', '<br>')
            
            # 첫 번째 행(i==0)은 제목 셀(<th>)로, 나머지는 일반 셀(<td>)로 태그 지정
            tag = 'th' if i == 0 else 'td'
            html += f'<{tag}>{cell_text}</{tag}>'
            
        html += '</tr>'
        
    html += '</table>\n'
    return html

def parse_docx_to_json(docx_file, output_json):
    """
    워드 문서를 읽어 들여 문제를 파싱하고 JSON 파일로 저장하는 메인 엔진 함수.
    
    Args:
        docx_file: 원본 MS Word 파일 경로
        output_json: 결과물을 저장할 JSON 파일 경로
    """
    doc = docx.Document(docx_file)
    all_rounds = []  # 전체 회차 데이터를 담을 리스트
    
    # 문서 내의 최상위 표(문제를 감싸고 있는 큰 틀)들을 순회
    for table in doc.tables:
        questions = []
        
        # 행 단위로 순회하며 1문제 단위로 데이터를 수집
        for row in table.rows:
            cells_content = []
            added_outer_cells = set()
            
            for cell in row.cells:
                # 병합된 셀 중복 처리 방지
                if cell in added_outer_cells:
                    continue
                added_outer_cells.add(cell)
                
                cell_html_parts = []
                
                # 셀 내부의 텍스트(문단)와 표(데이터 표/박스 지문)를 순서대로 읽어 들임
                for block in iter_block_items(cell):
                    if isinstance(block, Paragraph):
                        txt = block.text.replace('*', '').strip()
                        if txt:
                            cell_html_parts.append(txt)
                    elif isinstance(block, Table):
                        # 내부에 포함된 표를 만나면 즉시 HTML로 변환하여 텍스트 사이에 삽입
                        cell_html_parts.append(get_html_from_table(block))
                
                if cell_html_parts:
                    cells_content.append('\n'.join(cell_html_parts))
            
            # 빈 셀인 경우 건너뜀
            if not cells_content:
                continue
                
            # 하나의 셀(한 문제 덩어리)에 담긴 전체 텍스트 조합
            full_text = '\n'.join(cells_content)
            
            # -----------------------------------------------------------
            # 정규표현식(Regex)을 이용한 데이터 분리 (Routing)
            # -----------------------------------------------------------
            
            # 1. 문제 번호 및 지문 추출 ('숫자'로 시작해서 '①' 또는 '정답'이 나오기 전까지)
            q_match = re.search(r'^(\d+)\s+(.*?)(?=\n①|\n정답|$)', full_text, re.DOTALL)
            if not q_match:
                continue
            
            q_num = int(q_match.group(1))
            q_text = q_match.group(2).strip()
            
            # 2. 보기(①~④) 추출
            options = []
            for marker in ['①', '②', '③', '④']:
                # 각 번호 기호부터 다음 번호 기호나 정답이 나오기 전까지 추출
                opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
                if opt_match:
                    options.append(opt_match.group(1).replace('\n', ' ').strip())
                else:
                    options.append("")
                    
            # 3. 정답 번호 추출 (숫자로 매핑)
            ans_match = re.search(r'정답\s*([①②③④])', full_text)
            answer_num = 0
            if ans_match:
                ans_map = {'①': 1, '②': 2, '③': 3, '④': 4}
                answer_num = ans_map.get(ans_match.group(1), 0)
            
            # 4. 해설(Hint) 추출 (전체 텍스트에서 지문, 보기, 정답을 소거하고 남은 텍스트)
            hint_text = full_text
            if q_match: hint_text = hint_text.replace(q_match.group(0), '')
            if ans_match: hint_text = hint_text.replace(ans_match.group(0), '')
            for marker in ['①', '②', '③', '④']:
                opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
                if opt_match:
                    hint_text = hint_text.replace(opt_match.group(0), '')
            
            hint_text = hint_text.strip()
            
            # 파싱된 1개의 문제 데이터를 리스트에 추가
            questions.append({
                "num": q_num,
                "question": q_text,
                "options": options,
                "hint": hint_text,
                "answer": answer_num
            })
            
        # 해당 표(회차)에 문제가 담겨있다면 전체 회차 리스트에 추가
        if questions:
            round_name = f"실전모의 {len(all_rounds) + 1}회"
            all_rounds.append({
                "subject": "에너지관리기능장",
                "year": "",
                "round": round_name,
                "questions": questions
            })
    
    # 최종 결과물을 JSON 파일로 내보내기 (한글 깨짐 방지)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_rounds, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 표 인식 엔진 탑재 V2 스크립트 실행 완료!")
    print(f"총 {len(all_rounds)}개 회차, {sum(len(r['questions']) for r in all_rounds)}문제가 완벽하게 변환되었습니다.")

if __name__ == "__main__":
    # 실행 시 파일명 설정부
    input_file = "260626_energy_ginungjang_gyojeong.docx" 
    output_file = "questions.json"
    parse_docx_to_json(input_file, output_file)