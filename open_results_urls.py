from playwright.sync_api import sync_playwright
import re
import sys
import io

# Force stdout to use UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_urls_from_results(file_path="results.txt"):
    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) > 3:
                url = parts[-1].strip()
                if url.startswith("http"):
                    urls.append(url)
    return urls

def fetch_url_content(urls):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state="kbid_login.json")
        except FileNotFoundError:
            print("[ERROR] kbid_login.json not found. Please run the login process first.")
            return

        page = context.new_page()

        for url in urls:
            print(f"--- URL: {url} ---")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                detail_selector = ".gongo_detail"
                page.wait_for_selector(detail_selector, timeout=15000)
                
                # Extract text from all matching elements
                detail_elements = page.query_selector_all(detail_selector)
                full_text = ""
                if detail_elements:
                    texts = [el.inner_text() for el in detail_elements]
                    full_text = "\n\n".join(t.strip() for t in texts if t.strip())

                if full_text:
                    print(full_text)
                else:
                    print("[CONTENT NOT FOUND]")

            except Exception as e:
                print(f"[ERROR] Failed to fetch {url}: {e}")
            print("--- END ---")

        browser.close()

if __name__ == "__main__":
    # First, ensure login session is fresh
    try:
        from test import save_login_state
        print("Refreshing login session...")
        save_login_state()
        print("Login session refreshed.")
    except ImportError:
        print("[WARN] Could not import save_login_state from test.py. Using existing session.")

    # Now, fetch content for URLs
    urls_to_fetch = get_urls_from_results()
    if urls_to_fetch:
        fetch_url_content(urls_to_fetch)
    else:
        print("No URLs found in results.txt")