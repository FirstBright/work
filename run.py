import subprocess
import json
import re
import os

def run_command(command):
    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        print(f"Error running command: {' '.join(command)}")
        print(f"Stderr: {result.stderr}")
        return None
    return result.stdout

def get_company_info(file_path="company_info.txt"):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_results_info(file_path="results.txt"):
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) < 4:
                continue
            try:
                proposal_count_str = parts[0].replace('제안서 수:', '').strip()
                proposal_count = int(proposal_count_str)
                title = parts[1].strip()
                qualification_summary = parts[2].strip()
                url = parts[-1].strip()
                results.append({
                    "title": title, 
                    "proposal_count": proposal_count, 
                    "qualification_summary": qualification_summary,
                    "url": url
                })
            except (ValueError, IndexError):
                continue
    return results

def normalize_text(s):
    return re.sub(r'\s+', ' ', s).strip()

def analyze_single_announcement(content, companies):
    analysis = {
        "적합성": {},
        "자격": [],
        "물품": [],
        "유형": "",
        "제출": "",
        "서류": []
    }

    # Extract details using regex
    analysis["자격"] = list(set(re.findall(r"(정보통신공사업|소프트웨어사업자|기계가스설비공사업|시설물유지관리업|금속구조물창호공사업|도장습식방수석공사업|건설업자|등록사업자)", content)))
    analysis["물품"] = list(set([f'{m[0].strip()}({m[1]}) ' for m in re.findall(r"([가-힣\s]+)\((\d{{10,}})\)", content)]))
    
    if re.search(r"협상에 의한 계약", content): analysis["유형"] = "협상에 의한 계약"
    elif re.search(r"적격심사", content): analysis["유형"] = "적격심사"
    elif re.search(r"최저가", content): analysis["유형"] = "최저가낙찰"

    if re.search(r"(전자입찰|나라장터|g2b)", content, re.I): analysis["제출"] = "전자입찰"
    elif re.search(r"직접방문|방문접수", content): analysis["제출"] = "직접방문"
    
    # Suitability analysis
    for name, profile in companies.items():
        score = 0
        # More sophisticated matching logic can be added here
        company_quals = " ".join(profile.get("업종", []))
        company_items = " ".join(profile.get("직접생산확인서", []))

        for qual in analysis["자격"]:
            if qual in company_quals:
                score += 1
        
        for item in analysis["물품"]:
            if item.split('(')[1] in company_items:
                score += 2

        if score > 1:
            analysis["적합성"][name] = "적합"
        elif score == 1:
            analysis["적합성"][name] = "검토필요"
        else:
            analysis["적합성"][name] = "부적합"

    return analysis

def main():
    print("업데이트된 회사 정보로 분석을 시작합니다.")
    company_info = get_company_info()
    
    print("이전 크롤링 결과를 읽습니다.")
    results_info = get_results_info()
    
    print("공고 상세 내용을 스크랩합니다.")
    scraped_output = run_command(["python", "open_results_urls.py"])
    if not scraped_output:
        print("스크래핑 실패. 종료합니다.")
        return

    scraped_content_map = {}
    current_url = None
    content_buffer = []
    for line in scraped_output.splitlines():
        if line.startswith("---"): # Simplified condition to catch URL lines
            if current_url and content_buffer:
                scraped_content_map[current_url] = '\n'.join(content_buffer)
            
            if "URL:" in line:
                current_url = line.split("URL:")[-1].strip()
            else:
                current_url = None # Reset if it's an END line or similar
            content_buffer = []
        else:
            content_buffer.append(line)

    # Add the last buffered content if any
    if current_url and content_buffer:
        scraped_content_map[current_url] = '\n'.join(content_buffer)

    final_output_lines = []
    for result in results_info:
        title = result["title"]
        final_output_lines.append(f"**[{title}]**")

        if "이미지 건" in result.get("qualification_summary", ""):
            final_output_lines.append("- 이미지 건")
        elif result["proposal_count"] > 8:
            final_output_lines.append("- 제안서 건")
        else:
            content = scraped_content_map.get(result["url"], "")
            if not content or "공고문을 찾을수 없습니다" in content or "pdf" in content:
                final_output_lines.append("- 콘텐츠 없음")
            else:
                analysis = analyze_single_announcement(content, company_info)
                suitability_str = ", ".join([f'{k}({v})' for k, v in analysis["적합성"].items() if analysis["적합성"][k] != '부적합'])
                if not suitability_str: suitability_str = "적합 업체 없음"
                
                final_output_lines.append(f"*   **적합성:** {suitability_str}")
                if analysis["자격"]:
                    final_output_lines.append(f"*   **자격:** {', '.join(analysis['자격'])}")
                if analysis["물품"]:
                    final_output_lines.append(f"*   **물품:** {', '.join(analysis['물품'])}")
                if analysis["유형"]:
                    final_output_lines.append(f"*   **유형:** {analysis['유형']}")
                if analysis["제출"]:
                    final_output_lines.append(f"*   **제출:** {analysis['제출']}")

        final_output_lines.append("\n")

    output_filename = "analysis_output.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write('\n'.join(final_output_lines))
    
    print(f"분석 완료. 결과가 '{output_filename}'에 저장되었습니다.")

if __name__ == "__main__":
    main()
