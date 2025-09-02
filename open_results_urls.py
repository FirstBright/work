import webbrowser

# 같은 경로에 있는 results.txt 읽기
with open("results.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 2:
        url = parts[-1]  # 마지막 필드를 URL로 사용
        if url.startswith("http"):
            webbrowser.open_new_tab(url)
