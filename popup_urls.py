import re
import webbrowser
from pathlib import Path

def extract_urls_from_file(file_path: str):
    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r"(https?://[^\s]+)", line)
            if match:
                urls.append(match.group(1))
    return urls

def open_urls_in_browser(urls):
    for url in urls:
        webbrowser.open_new_tab(url)

if __name__ == "__main__":
    file_path = Path("results.txt")
    urls = extract_urls_from_file(file_path)
    print(f"총 {len(urls)}개의 URL을 찾았습니다.")
    open_urls_in_browser(urls)