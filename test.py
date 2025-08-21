from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os, time, re, argparse, sys
from pathlib import Path

# ===================== 텍스트 처리 유틸 =====================

def normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[•·▶►\\-–—]+", " ", s)
    canon_map = {
        r"직\s*접\s*생\s*산\s*확\s*인\s*증\s*명\s*서": "직접생산확인증명서",
        r"입\s*찰\s*참\s*가\s*자\s*격": "입찰참가자격",
        r"참\s*가\s*자\s*격": "참가자격",
        r"분\s*류\s*번\s*호": "분류번호",
        r"제\s*조\s*물\s*품": "제조물품",
    }
    for pat, rep in canon_map.items():
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s

SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:제?\s*\d+\s*[-\.]?\s*)?(?:입찰)?\s*참가자격[^\n]*\n"
    r"(.*?)"
    r"(?=\n\s*(?:제?\s*\d+\s*[-\.]?\s*(?:[^\n]{0,20})$|[IVX]+\.|[가-하]\)|\d+\)|\d+\.)|\n{2,}|\Z)",
    re.S | re.M
)

def extract_participant_section(full_text: str) -> str:
    t = normalize_text(full_text)
    m = SECTION_RE.search(t)
    if not m:
        return ""
    body = m.group(1).strip()
    body = re.sub(r"^\s*(?:\d+[-\.]\d*\.?\s*)?(?:참가자격등록|참가자격)\s*$", "", body, flags=re.M)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body

# ===================== 크롤러/설정 =====================

KBID_LOGIN_URL = "https://www.kbid.co.kr/login/common_login.htm"
KBID_HOME_URL  = "https://www.kbid.co.kr"
COUNT_KEYWORD = "제안서"
LOGIN_ID = os.environ.get('LOGIN_ID')
LOGIN_PW = os.environ.get('LOGIN_PW')
UA       = os.getenv("KBID_USER_AGENT") or \
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

def save_login_state(storage_path="kbid_login.json"):
    load_dotenv()    

    if not LOGIN_ID or not LOGIN_PW:
        print("[ERROR] .env에 KBID_ID / KBID_PW를 설정하세요.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=80,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            viewport=None,
            user_agent=UA,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        page = context.new_page()
        page.goto(KBID_LOGIN_URL, wait_until="load", timeout=30000)

        page.fill("#MemID", LOGIN_ID)
        page.fill("#MemPW", LOGIN_PW)
        page.click('input[type="image"][name="images"]')

        page.wait_for_load_state("networkidle", timeout=15000)
        page.goto(KBID_HOME_URL, wait_until="load", timeout=30000)

        context.storage_state(path=storage_path)
        print(f"[OK] 로그인 세션 저장: {storage_path}")
        browser.close()

def load_keywords(input_file: str) -> list[str]:
    if not Path(input_file).exists():
        print(f"[WARN] {input_file} 가 없어 기본 예시를 생성합니다.")
        Path(input_file).write_text("예시 키워드1\n예시 키워드2\n", encoding="utf-8")
    with open(input_file, "r", encoding="utf-8") as f:
        return [re.sub(r"\(재공고\)\s*$", "", line.strip()) for line in f if line.strip()]

def search_and_save_results(input_file="keywords.txt", output_file="results.txt", collect_urls=False) -> list[str]:
    """collect_urls=True면 수집한 상세 URL 리스트를 리턴(탭 오픈용)"""
    urls_collected = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=100)
        context = browser.new_context(storage_state="kbid_login.json")
        page = context.new_page()
        page.goto(KBID_HOME_URL, wait_until="load", timeout=30000)

        keywords = load_keywords(input_file)

        with open(output_file, "w", encoding="utf-8") as out_f:
            for keyword in keywords:
                if not keyword:
                    continue

                search_selector = "#s_search_word"
                page.fill(search_selector, keyword)
                page.press(search_selector, "Enter")

                result_selector = "#listBody1 tr:nth-child(1) td.subject a"
                detail_url = ""
                subject_number = 0
                participant_text = "이미지 건"

                try:
                    page.wait_for_selector(result_selector, timeout=10000)
                except:
                    out_f.write(f"{keyword} | {participant_text} | 제안서 수: {subject_number} | {detail_url}\n")
                    page.goto(KBID_HOME_URL, wait_until="load", timeout=30000)
                    time.sleep(1.0)
                    continue

                with page.expect_popup() as popup_info:
                    page.click(result_selector)
                new_tab = popup_info.value
                new_tab.wait_for_load_state("networkidle", timeout=30000)

                try:
                    detail_url = new_tab.url or ""
                except:
                    detail_url = ""

                detail_selector = ".gongo_detail"

                try:
                    new_tab.wait_for_selector(detail_selector, timeout=60000)
                    new_tab.wait_for_function(
                        "() => document.querySelector('.gongo_detail')?.innerText?.length > 0",
                        timeout=60000
                    )
                    detail_elements = new_tab.query_selector_all(detail_selector)
                    if detail_elements:
                        full_texts = []
                        for el in detail_elements:
                            t = (el.inner_text() or "").strip()
                            if t:
                                full_texts.append(t)
                            time.sleep(0.05)
                        full_text = "\n".join(full_texts)

                        subject_number = len(re.findall(re.escape(COUNT_KEYWORD), full_text))
                        sec = extract_participant_section(full_text)
                        participant_text = sec if sec else "이미지 건"
                    else:
                        participant_text = "이미지 건"

                except Exception:
                    participant_text = "이미지 건"
                finally:
                    try:
                        new_tab.close()
                    except:
                        pass

                out_f.write(f"{keyword} | {participant_text} | 제안서 수: {subject_number} | {detail_url}\n")
                if collect_urls and detail_url:
                    urls_collected.append(detail_url)

                page.goto(KBID_HOME_URL, wait_until="load", timeout=30000)
                time.sleep(0.8)

        browser.close()

    print(f"[OK] 결과 저장: {output_file} / 수집 URL: {len(urls_collected)}개")
    return urls_collected

def open_urls_in_tabs(urls: list[str], throttle_ms: int = 300):
    """수집된 URL을 순서대로 새 탭에 모두 띄움(가시 브라우저)"""
    if not urls:
        print("[INFO] 열 URL이 없습니다.")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport=None, locale="ko-KR", timezone_id="Asia/Seoul")
        for u in urls:
            page = context.new_page()
            try:
                page.goto(u, wait_until="load", timeout=45000)
            except:
                pass
            time.sleep(throttle_ms / 1000.0)
        print(f"[OK] 총 {len(urls)}개 탭 오픈 완료. 브라우저를 수동으로 닫으세요.")

# ===================== CLI 진입점 =====================

# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--save-login", action="store_true", help="로그인 세션 저장만 수행")
#     parser.add_argument("--crawl", action="store_true", help="검색/결과 저장 수행")
#     parser.add_argument("--open-tabs", action="store_true", help="수집한 상세 URL을 가시 브라우저 탭으로 모두 오픈")
#     parser.add_argument("--input", default="keywords.txt", help="키워드 입력 파일")
#     parser.add_argument("--output", default="results.txt", help="결과 출력 파일")
#     args = parser.parse_args()

#     if args.save_login:
#         save_login_state()

#     urls = []
#     if args.crawl:
#         urls = search_and_save_results(input_file=args.input, output_file=args.output, collect_urls=args.open_tabs)

#     if args.open_tabs and urls:
#         # 방금 수집한 URL이 있으면 그것으로, 아니면 results.txt에서 추출
#         open_urls_in_tabs(urls)

# if __name__ == "__main__":
#     main()
# 1) 최초 1회: 로그인 세션 저장 
save_login_state()
 # 2) 검색 및 결과 저장 
search_and_save_results()
