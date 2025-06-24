import os
from playwright.sync_api import sync_playwright

def run():
    auth_file = 'auth/instagram_auth_state.json'
    
    # Ensure the auth directory exists
    os.makedirs(os.path.dirname(auth_file), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.instagram.com/")

        print("\n" + "="*50)
        print("Please log in to Instagram in the browser window.")
        print("After you have successfully logged in and handled any pop-ups, press Enter in this terminal.")
        print("="*50)
        
        input() # Pause execution and wait for user to press Enter

        print("Saving authentication state...")
        context.storage_state(path=auth_file)
        print(f"Authentication state saved to {auth_file}")

        browser.close()

if __name__ == "__main__":
    run()
