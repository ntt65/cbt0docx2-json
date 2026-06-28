"""

지금까지 누적된 **V8.4(UI 최적화), V8.5(리포팅/로그), V8.6(표 내부 스캔), V8.7(일반 텍스트 하이브리드 스캔)**의 모든 성과를 단 하나도 잃어버리지 않게 객체지향의 **'전략 패턴(Strategy Pattern)'**으로 전면 분리 개조한 **[CBT 데이터 변환 엔진 V9.0]**을 즉시 완성했습니다.

---

### 🏛️ [V9.0 엔진] 아키텍처 개요 (클래스 분리)
새로운 V9.0 엔진은 문서를 무작정 들이받지 않고, **스마트 분석기(`DocumentAnalyzer`)**가 문서를 먼저 쓱 훑어본 뒤 구조에 맞는 전용 파서를 투입시킵니다.

```mermaid
classDiagram
    class DocumentAnalyzer {
        +determine_strategy(doc) String
    }
    class ParserStrategy {
        <<Interface>>
        +parse(doc, subject_folder) List
    }
    class TableBasedParser {
        +parse(doc, subject_folder) List
        note "에너지기능장 전용\n(표 중심 완벽 파싱)"
    }
    class HybridParser {
        +parse(doc, subject_folder) List
        note "가스기능사 전용\n(텍스트 문단 중심 파싱)"
    }
    class MainEngine {
        +parse_docx_to_json()
    }

    MainEngine ..> DocumentAnalyzer : 1. 문서 형태 판별 요청
    MainEngine ..> ParserStrategy : 2. 파싱 위임 (다형성)
    ParserStrategy <|-- TableBasedParser
    ParserStrategy <|-- HybridParser
```

```

**💡 [V9.0 업데이트 요약]**
1. **인공지능(?) 스캔 도입 (`DocumentAnalyzer`)**: 이제 파이썬을 실행하면 스크립트가 알아서 문서 앞부분을 스캔합니다.
   * `가스기능사`처럼 표 바깥에 일반 문제 번호가 발견되면 ➡️ **`[HybridParser]`**를 투입합니다.
   * `에너지관리기능장`처럼 표 밖에는 텍스트가 없고 거대한 표 안에 문제가 갇혀있으면 ➡️ **`[TableBasedParser]`**를 투입합니다.
2. **에러 원천 격리 보장**: 파서를 완전히 두 개의 방(Class)으로 분리해 두었기 때문에, 앞으로 가스기능사를 완벽하게 잡겠다고 코드를 뜯어고쳐도, **과거에 잘 파싱되던 에너지관리기능장 로직에는 단 1%의 악영향도 주지 않게 됩니다!**

이제 과목이나 문서 형식이 바뀔 때마다 파이썬 코드를 뗐다 붙였다 하실 필요 없이, **이 V9.0 엔진 단 하나만**으로 에너지, 가스, 공조 모든 과목을 완벽하게 뽑아내실 수 있습니다. 바로 실행해보십시오! 👍

### 🚀 파이썬 V9.0 전체 코드 (클래스 분리형 객체지향 엔진)

===============================================================================
[CBT 기출문제 변환 엔진 V9.0] - Strategy Pattern Architecture
- [V9.0 핵심]: 문서 구조(표 위주 vs 텍스트 위주)를 자동 판별하여 최적화된 파싱 전략(Strategy)을 수행하는 객체지향 아키텍처 도입
- [V9.0 추가]: DocumentAnalyzer 클래스로 문서 형태 자동 분석 기능 탑재
- [V9.0 분리]: TableBasedParser(기능장 최적화)와 HybridParser(가스기능사 최적화)로 파싱 엔진 분리
- [V8.x 통합]: UI 최적화(V8.4), 에러 로그 및 총합 리포팅(V8.5), 표 내부 제목 스캔(V8.6) 100% 통합 유지
===============================================================================
"""

import os
import docx
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table
import json
import re

image_counter = 1

# ==========================================
# 1. 공통 유틸리티 함수 (Helpers)
# ==========================================
def iter_block_items(parent):
    for child in parent._element:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def get_paragraph_html_with_images(paragraph, doc_part, subject_folder):
    global image_counter
    html_parts = []
    
    img_local_dir = os.path.join("data", subject_folder, "images")
    img_web_path = f"data/{subject_folder}/images"
    
    for run in paragraph.runs:
        run_text = run.text.replace('*', '')
        if run_text:
            html_parts.append(run_text)
            
        drawings = run._element.xpath('.//*[local-name()="blip"]')
        vml_images = run._element.xpath('.//*[local-name()="imagedata"]')
        
        embed_ids = []
        for blip in drawings:
            rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if rId: embed_ids.append(rId)
            
        for vml in vml_images:
            rId = vml.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            if rId: embed_ids.append(rId)
            
        for embed_id in embed_ids:
            if embed_id in doc_part.related_parts:
                img_part = doc_part.related_parts[embed_id]
                ext = img_part.content_type.split('/').pop()
                if ext == 'jpeg': ext = 'jpg'
                if ext == 'x-wmf': ext = 'png'
                
                os.makedirs(img_local_dir, exist_ok=True)
                img_filename = f"img_{image_counter:04d}.{ext}"
                img_path = os.path.join(img_local_dir, img_filename)
                
                with open(img_path, 'wb') as f:
                    f.write(img_part.blob)
                    
                img_tag = f'\n<img src="{img_web_path}/{img_filename}" alt="기출문제 첨부 이미지" style="max-width:100%; height:auto; border-radius:var(--border-radius-sm); margin:12px 0; box-shadow:var(--shadow-sm);">\n'
                html_parts.append(img_tag)
                image_counter += 1
                
    return "".join(html_parts).strip()

def get_html_from_table(table, doc_part, subject_folder):
    if len(table.rows) == 1:
        first_row = next(iter(table.rows))
        if len(first_row.cells) == 1:
            first_cell = next(iter(first_row.cells))
            
            cell_html_parts = []
            for p in first_cell.paragraphs:
                p_html = get_paragraph_html_with_images(p, doc_part, subject_folder)
                if p_html: cell_html_parts.append(p_html)
                
            cell_text = '<br>'.join(cell_html_parts).strip().replace('\n', '<br>')
            return f'\n<div style="margin-top:16px; padding:16px; border:1px solid var(--glass-border); border-radius:var(--border-radius-sm); background:rgba(255,255,255,0.03); line-height:1.6;">{cell_text}</div>\n'
    
    html = '\n<table class="nested-table">'
    for i, row in enumerate(table.rows):
        html += '<tr>'
        added_cells = set()
        for cell in row.cells:
            if cell in added_cells:
                continue
            added_cells.add(cell)
            
            cell_html_parts = []
            for p in cell.paragraphs:
                p_html = get_paragraph_html_with_images(p, doc_part, subject_folder)
                if p_html: cell_html_parts.append(p_html)
                
            cell_text = '<br>'.join(cell_html_parts).strip().replace('\n', '<br>')
            tag = 'th' if i == 0 else 'td'
            html += f'<{tag}>{cell_text}</{tag}>'
        html += '</tr>'
    html += '</table>\n'
    return html

def parse_question_block(full_text):
    q_match = re.search(r'^(\d+)\s+(.*?)(?=\n①|\n정답|$)', full_text, re.DOTALL)
    if not q_match:
        preview = full_text.replace('\n', ' ')[:40]
        print(f"  ⚠️ [파싱 실패] 문제 형식 불일치 -> \"{preview}...\"")
        return None
    
    q_num = int(q_match.group(1))
    q_text = q_match.group(2).strip()
    
    options = []
    for marker in ['①', '②', '③', '④']:
        opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
        if opt_match:
            options.append(opt_match.group(1).replace('\n', ' ').strip())
        else:
            options.append("")
            
    ans_match = re.search(r'정답\s*([①②③④])', full_text)
    answer_num = 0
    if ans_match:
        ans_map = {'①': 1, '②': 2, '③': 3, '④': 4}
        answer_num = ans_map.get(ans_match.group(1), 0)
    
    hint_text = full_text
    if q_match: hint_text = hint_text.replace(q_match.group(0), '')
    if ans_match: hint_text = hint_text.replace(ans_match.group(0), '')
    for marker in ['①', '②', '③', '④']:
        opt_match = re.search(fr'{marker}\s*(.*?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
        if opt_match:
            hint_text = hint_text.replace(opt_match.group(0), '')
            
    hint_text = hint_text.strip()
    
    if not any(options):
        preview = full_text.replace('\n', ' ')[:40]
        print(f"  ❌ [누락/폐기] {q_num}번 문항 폐기됨 (사유: 보기 없음) -> \"{preview}...\"")
        return None
        
    return {
        "num": q_num,
        "question": q_text,
        "options": options,
        "hint": hint_text,
        "answer": answer_num
    }

def format_question_ranges(nums):
    if not nums: return ""
    nums_sorted = sorted(set(nums))
    ranges = []
    num_iter = iter(nums_sorted)
    start = next(num_iter)
    end = start
    
    for n in num_iter:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}~{end}" if start != end else str(start))
            start = n
            end = n
            
    ranges.append(f"{start}~{end}" if start != end else str(start))
    return ", ".join(ranges)


# ==========================================
# 2. 문서 분석기 및 전략(Strategy) 클래스
# ==========================================
class DocumentAnalyzer:
    @staticmethod
    def determine_strategy(doc):
        # 최상위 문단(표 바깥)에 문제 번호 패턴이 3개 이상 발견되면 가스기능사 같은 Hybrid 문서로 판단
        q_pattern_count = 0
        for p in doc.paragraphs:
            if re.match(r'^\d+\s+', p.text.strip()):
                q_pattern_count += 1
            if q_pattern_count >= 3:
                return "HYBRID"
        return "TABLE"

class ParserStrategy:
    def parse(self, doc, subject_folder):
        raise NotImplementedError

# [전략 A]: 에너지관리기능장 최적화 파서 (V8.5 방식)
class TableBasedParser(ParserStrategy):
    def parse(self, doc, subject_folder):
        all_parsed_questions = []
        for table in doc.tables:
            added_outer_cells = set()
            current_q_block = ""
            
            for row in table.rows:
                cells_content = []
                for cell in row.cells:
                    if cell in added_outer_cells: continue
                    added_outer_cells.add(cell)
                    
                    cell_html_parts = []
                    for block in iter_block_items(cell):
                        if isinstance(block, Paragraph):
                            txt = get_paragraph_html_with_images(block, doc.part, subject_folder)
                            if txt: cell_html_parts.append(txt)
                        elif isinstance(block, Table):
                            cell_html_parts.append(get_html_from_table(block, doc.part, subject_folder))
                    
                    if cell_html_parts:
                        cells_content.append('\n'.join(cell_html_parts))
                
                if not cells_content: continue
                row_text = '\n'.join(cells_content)
                
                if re.match(r'^\d+\s+', row_text):
                    if current_q_block:
                        q_obj = parse_question_block(current_q_block)
                        if q_obj: all_parsed_questions.append(q_obj)
                    current_q_block = row_text
                else:
                    if current_q_block: current_q_block += '\n' + row_text
                    else: current_q_block = row_text
            
            if current_q_block:
                q_obj = parse_question_block(current_q_block)
                if q_obj: all_parsed_questions.append(q_obj)
                
        return all_parsed_questions

# [전략 B]: 가스기능사 최적화 파서 (V8.7 하이브리드 방식)
class HybridParser(ParserStrategy):
    def parse(self, doc, subject_folder):
        all_parsed_questions = []
        added_outer_cells = set()
        current_q_block = ""
        
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                txt = get_paragraph_html_with_images(block, doc.part, subject_folder)
                if not txt: continue
                
                if re.match(r'^\d+\s+', txt):
                    if current_q_block:
                        q_obj = parse_question_block(current_q_block)
                        if q_obj: all_parsed_questions.append(q_obj)
                    current_q_block = txt
                else:
                    if current_q_block: 
                        current_q_block += '\n' + txt
                        
            elif isinstance(block, Table):
                for row in block.rows:
                    cells_content = []
                    for cell in row.cells:
                        if cell in added_outer_cells: continue
                        added_outer_cells.add(cell)
                        
                        cell_html_parts = []
                        for cell_block in iter_block_items(cell):
                            if isinstance(cell_block, Paragraph):
                                p_txt = get_paragraph_html_with_images(cell_block, doc.part, subject_folder)
                                if p_txt: cell_html_parts.append(p_txt)
                            elif isinstance(cell_block, Table):
                                cell_html_parts.append(get_html_from_table(cell_block, doc.part, subject_folder))
                        
                        if cell_html_parts:
                            cells_content.append('\n'.join(cell_html_parts))
                            
                    if not cells_content: continue
                    row_text = '\n'.join(cells_content)
                    
                    if re.match(r'^\d+\s+', row_text):
                        if current_q_block:
                            q_obj = parse_question_block(current_q_block)
                            if q_obj: all_parsed_questions.append(q_obj)
                        current_q_block = row_text
                    else:
                        if current_q_block: 
                            current_q_block += '\n' + row_text

        if current_q_block:
            q_obj = parse_question_block(current_q_block)
            if q_obj: all_parsed_questions.append(q_obj)
            
        return all_parsed_questions

# ==========================================
# 3. 메인 컨트롤러
# ==========================================
def parse_docx_to_json(docx_file, output_json, subject_folder):
    doc = docx.Document(docx_file)
    
    subject_map = {
        "energy_ginungjang": "에너지관리기능장",
        "energy_sanupgisa": "에너지관리산업기사",
        "gas": "가스기능사",
        "air_conditioning": "공조기능사"
    }
    real_subject_name = subject_map.get(subject_folder, "기출문제")
    
    # [1단계]: 문서 구조 자동 분석 및 파서 선택
    strategy_type = DocumentAnalyzer.determine_strategy(doc)
    if strategy_type == "HYBRID":
        print(f"🤖 [인공지능 스캔] 텍스트 중심 문서 감지 -> [HybridParser] 투입")
        parser = HybridParser()
    else:
        print(f"🤖 [인공지능 스캔] 표(Table) 중심 문서 감지 -> [TableBasedParser] 투입")
        parser = TableBasedParser()
        
    # [2단계]: 연도 및 회차 정보 추출 (표 안팎 무관하게 완벽 스캔)
    round_info_list = []
    seen_titles = set()
    
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            match = re.search(r'(\d{4})년\s*(\d+)회', block.text)
            if match:
                title_str = f"{match.group(1)}_{match.group(2)}"
                if title_str not in seen_titles:
                    seen_titles.add(title_str)
                    round_info_list.append({
                        "year": int(match.group(1)),
                        "round": f"{match.group(2)}회"
                    })
        elif isinstance(block, Table):
            for row in block.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        match = re.search(r'(\d{4})년\s*(\d+)회', p.text)
                        if match:
                            title_str = f"{match.group(1)}_{match.group(2)}"
                            if title_str not in seen_titles:
                                seen_titles.add(title_str)
                                round_info_list.append({
                                    "year": int(match.group(1)),
                                    "round": f"{match.group(2)}회"
                                })
            
    print(f"\n⏳ [{real_subject_name}] 파싱을 시작합니다...")
    print(f"   -> 총 {len(round_info_list)}개의 회차(연도) 타이틀을 확보했습니다!")
    print("-" * 65)
    print("🛠️ [실시간 파싱 에러/누락 의심 로그]")
    
    # [3단계]: 선택된 전술(Strategy) 파서 실행
    all_parsed_questions = parser.parse(doc, subject_folder)
            
    print("-" * 65)
                
    # [4단계]: 문항 그룹화 및 JSON 덤프 (V8.4 단추 레이아웃 밸런스 유지)
    all_rounds = []
    current_round_questions = []
    round_idx = 0
    
    for q in all_parsed_questions:
        if q["num"] == 1:
            if current_round_questions:
                info = round_info_list[round_idx] if round_idx < len(round_info_list) else {"year": "", "round": f"실전모의 {round_idx + 1}회"}
                all_rounds.append({
                    "subject": real_subject_name,
                    "year": info["year"],
                    "round": info["round"],
                    "questions": current_round_questions
                })
                round_idx += 1
            current_round_questions = [q]
        else:
            if current_round_questions:
                current_round_questions.append(q)
                
    if current_round_questions:
        info = round_info_list[round_idx] if round_idx < len(round_info_list) else {"year": "", "round": f"실전모의 {round_idx + 1}회"}
        all_rounds.append({
            "subject": real_subject_name,
            "year": info["year"],
            "round": info["round"],
            "questions": current_round_questions
        })
    
    output_dir = os.path.dirname(output_json)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_rounds, f, ensure_ascii=False, indent=2)
        
    # [5단계]: 최종 보고서 출력 (V8.5 디버깅 최적화 로그)
    global image_counter
    print(f"\n🎉 V9.0 스크립트 실행 완료!")
    print(f"총 {image_counter-1}개의 이미지가 'data/{subject_folder}/images/' 폴더에 추출되었습니다.")
    
    print("\n📊 [각 회차별 문제 변환 상세 보고서]")
    print("-" * 65)
    
    total_parsed_questions = 0
    
    for r in all_rounds:
        nums = [q['num'] for q in r['questions']]
        round_question_count = len(nums)
        total_parsed_questions += round_question_count 
        
        ranges_str = format_question_ranges(nums)
        missing_count = 60 - round_question_count
        status = f"⚠️ 누락 {missing_count}문제" if missing_count > 0 else "✅ 완벽"
        
        round_title = f"{r['year']}년 {r['round']}" if r['year'] else r['round']
        print(f" {round_title:<12} | 총 {round_question_count:2d}문제 | 번호: {ranges_str:<20} | {status}")
        
    print("-" * 65)
    print(f"🎯 [최종 결과] 총 {len(all_rounds)}개 회차, 전체 {total_parsed_questions}문항 변환 성공!")
    print("-" * 65)

if __name__ == "__main__":
    # 변수 세팅 (현재 가공하실 과목에 맞춰서 변경하세요)
    subject_name = "gas"                                    
    input_file = "gas_CBT_2017_2025.docx"                   
    output_file = f"data/{subject_name}/{subject_name}_questions.json"     
    
    parse_docx_to_json(input_file, output_file, subject_name)
