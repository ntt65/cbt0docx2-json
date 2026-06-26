"""
===============================================================================
[CBT 기출문제 변환 엔진 V8] - MS Word to JSON (과목별 동적 폴더 라우팅 적용)

1. 목적 (Purpose)
   - 기출문제를 파싱하여 JSON으로 만들고, 도면/그림은 지정된 과목 폴더에 추출합니다.
   - [V8 신규]: 과목명(subject_folder) 변수를 도입하여, 여러 과목의 이미지가 
     섞이지 않고 각각의 'data/과목명/images/' 폴더에 분리 저장되도록 자동화했습니다.
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

def iter_block_items(parent):
    for child in parent._element:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def get_paragraph_html_with_images(paragraph, doc_part, subject_folder):
    global image_counter
    html_parts = []
    
    # 🔥 실제 컴퓨터에 폴더를 만들 경로와 웹 브라우저가 인식할 상대 경로 지정
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
                ext = img_part.content_type.split('/')[-1]
                if ext == 'jpeg': ext = 'jpg'
                if ext == 'x-wmf': ext = 'png'
                
                # 로컬 폴더 자동 생성 (예: data/energy_ginungjang/images/)
                os.makedirs(img_local_dir, exist_ok=True)
                img_filename = f"img_{image_counter:04d}.{ext}"
                img_path = os.path.join(img_local_dir, img_filename)
                
                with open(img_path, 'wb') as f:
                    f.write(img_part.blob)
                    
                # JSON 내부에 삽입될 웹 호환 상대 경로 태그
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
    nums = sorted(nums)
    ranges = []
    start = nums
    end = nums
    
    for n in nums[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}~{end}" if start != end else str(start))
            start = n
            end = n
    ranges.append(f"{start}~{end}" if start != end else str(start))
    return ", ".join(ranges)

def parse_docx_to_json(docx_file, output_json, subject_folder):
    doc = docx.Document(docx_file)
    all_parsed_questions = []
    
    print(f"⏳ [{subject_folder}] 과목 문서 분석 및 이미지 추출을 시작합니다...")
    print("-----------------------------------------------------------------")
    print("🛠️ [실시간 파싱 에러/누락 의심 로그]")
    
    for table in doc.tables:
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
                        txt = get_paragraph_html_with_images(block, doc.part, subject_folder)
                        if txt:
                            cell_html_parts.append(txt)
                    elif isinstance(block, Table):
                        cell_html_parts.append(get_html_from_table(block, doc.part, subject_folder))
                
                if cell_html_parts:
                    cells_content.append('\n'.join(cell_html_parts))
            
            if not cells_content:
                continue
                
            row_text = '\n'.join(cells_content)
            
            if re.match(r'^\d+\s+', row_text):
                if current_q_block:
                    q_obj = parse_question_block(current_q_block)
                    if q_obj:
                        all_parsed_questions.append(q_obj)
                current_q_block = row_text
            else:
                if current_q_block:
                    current_q_block += '\n' + row_text
                else:
                    current_q_block = row_text
        
        if current_q_block:
            q_obj = parse_question_block(current_q_block)
            if q_obj:
                all_parsed_questions.append(q_obj)
                
    print("-----------------------------------------------------------------")
                
    all_rounds = []
    current_round_questions = []
    
    for q in all_parsed_questions:
        if q["num"] == 1:
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
                
    if current_round_questions:
        all_rounds.append({
            "subject": "에너지관리기능장",
            "year": "",
            "round": f"실전모의 {len(all_rounds) + 1}회",
            "questions": current_round_questions
        })
    
    # JSON이 과목 폴더 내부에 바로 저장되도록 경로 자동 설정
    output_dir = os.path.dirname(output_json)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_rounds, f, ensure_ascii=False, indent=2)
        
    global image_counter
    print(f"\n🎉 V8 스크립트 실행 완료!")
    print(f"총 {image_counter-1}개의 이미지가 'data/{subject_folder}/images/' 폴더에 추출되었습니다.")
    
    print("\n📊 [각 회차별 문제 변환 상세 보고서]")
    print("-" * 65)
    for r in all_rounds:
        nums = [q['num'] for q in r['questions']]
        ranges_str = format_question_ranges(nums)
        missing_count = 60 - len(nums)
        status = f"⚠️ 누락 {missing_count}문제" if missing_count > 0 else "✅ 완벽"
        print(f" {r['round']:<10} | 총 {len(nums):2d}문제 | 번호: {ranges_str:<20} | {status}")
    print("-" * 65)

if __name__ == "__main__":
    # 🔥 [수정 포인트] 여기서 작업하실 과목명과 파일명을 지정해 주시면 됩니다.
    subject_name = "energy_ginungjang"                      # 과목 폴더명 (예: "gas", "energy_ginungjang" 등)
    input_file = "260626_energy_ginungjang_gyojeong.docx"   # 변환할 워드 파일 이름
    output_file = f"data/{subject_name}/questions.json"     # 자동으로 해당 과목 폴더에 JSON 저장
    
    parse_docx_to_json(input_file, output_file, subject_name)