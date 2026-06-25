import docx
import json
import re

def parse_docx_to_json(docx_file, output_json):
    # Word 문서 불러오기
    doc = docx.Document(docx_file)
    all_rounds = []
    
    # 문서 내 모든 표(Table)를 순회 (일반적으로 표 1개 = 1회차로 간주)
    for table in doc.tables:
        questions = []
        
        for row in table.rows:
            cells_text = []
            
            # 1. 셀(Cell) 데이터 추출 (병합된 셀의 중복 텍스트 방지)
            for cell in row.cells:
                # 불필요한 별표(***) 기호 제거
                text = cell.text.replace('*', '').strip()
                if text and (not cells_text or cells_text[-1] != text):
                    cells_text.append(text)
            
            if not cells_text:
                continue
                
            full_text = '\n'.join(cells_text)
            
            # 2. 문제 번호 및 지문 추출 (예: "01 보일러의...")
            # 번호로 시작하고 보기(①)나 정답이 나오기 전까지의 텍스트
            q_match = re.search(r'^(\d+)\s+(.+?)(?=\n①|\n정답|$)', full_text, re.DOTALL)
            if not q_match:
                continue
            
            q_num = int(q_match.group(1))
            q_text = q_match.group(2).replace('\n', ' ').strip()
            
            # 3. 보기(①~④) 추출
            options = []
            for marker in ['①', '②', '③', '④']:
                opt_match = re.search(fr'{marker}\s*(.+?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
                if opt_match:
                    options.append(opt_match.group(1).replace('\n', ' ').strip())
                else:
                    options.append("")
                    
            # 4. 정답 번호 추출 (예: "정답 ②" -> 2)
            ans_match = re.search(r'정답\s*([①②③④])', full_text)
            answer_num = 0
            if ans_match:
                ans_map = {'①': 1, '②': 2, '③': 3, '④': 4}
                answer_num = ans_map.get(ans_match.group(1), 0)
            
            # 5. 해설(Hint) 추출
            # 전체 텍스트에서 문제, 보기, 정답을 지우고 남은 순수 텍스트를 해설로 사용
            hint_text = full_text
            if q_match: hint_text = hint_text.replace(q_match.group(0), '')
            if ans_match: hint_text = hint_text.replace(ans_match.group(0), '')
            for marker in ['①', '②', '③', '④']:
                opt_match = re.search(fr'{marker}\s*(.+?)(?=\n[①②③④]|\n정답|\n|$)', full_text, re.DOTALL)
                if opt_match:
                    hint_text = hint_text.replace(opt_match.group(0), '')
            
            hint_text = hint_text.strip()
            
            # 파싱된 데이터를 리스트에 추가
            questions.append({
                "num": q_num,
                "question": q_text,
                "options": options,
                "hint": hint_text,
                "answer": answer_num
            })
        
        # 유효한 문제가 추출된 표만 최종 배열에 회차(Round) 단위로 추가
        if questions:
            round_name = f"실전모의 {len(all_rounds) + 1}회"
            all_rounds.append({
                "subject": "에너지관리기능장",
                "year": "",
                "round": round_name,
                "questions": questions
            })
    
    # 6. 완성된 데이터를 깔끔하게 들여쓰기 된 JSON 파일로 저장
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_rounds, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 성공! 총 {len(all_rounds)}개 회차, {sum(len(r['questions']) for r in all_rounds)}문제가 JSON으로 변환되었습니다.")
    print(f"저장된 파일: {output_json}")

# 실행: 동일 폴더 내의 워드 파일 이름을 입력하세요.
if __name__ == "__main__":
    input_file = "260626_energy_ginungjang_gyojeong.docx" # 가지고 계신 파일명으로 변경하세요
    output_file = "questions.json"
    parse_docx_to_json(input_file, output_file)