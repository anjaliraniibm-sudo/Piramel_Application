# driver_parallel.py
import os
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import all scrapers
from src import biopharma, catalent_new, pharmtech_new, resilience, genenews

SCRAPERS = [biopharma, catalent_new, pharmtech_new, resilience, genenews]
ERROR_LOG_FILE = "scraper_errors.log"
SCRAPER_TIMEOUT = 15 * 60  # 15 minutes in seconds

def run_scraper(scraper):
    """Run a single scraper's main function with timeout."""
    result = {"status": "Failed", "error": "Timeout"}  # default if timed out

    def target():
        try:
            print(f"🚀 Running {scraper.__name__}...")
            scraper.main()
            print(f"✅ {scraper.__name__} completed successfully.\n")
            result["status"] = "Success"
            result["error"] = ""
        except Exception as e:
            print(f"❌ {scraper.__name__} failed. See log for details.\n")
            result["status"] = "Failed"
            result["error"] = str(e)
            error_trace = traceback.format_exc()
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"Error in {scraper.__name__}:\n")
                f.write(error_trace + "\n\n")

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(SCRAPER_TIMEOUT)

    if thread.is_alive():
        print(f"⏰ {scraper.__name__} timed out after {SCRAPER_TIMEOUT/60} minutes.\n")
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{scraper.__name__} timed out after {SCRAPER_TIMEOUT/60} minutes.\n\n")
        # Thread will continue in background but we mark it as failed

    return (scraper.__name__, result["status"], result["error"])

def run_all_scrapers_parallel(max_workers=None):
    if os.path.exists(ERROR_LOG_FILE):
        os.remove(ERROR_LOG_FILE)

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_scraper = {executor.submit(run_scraper, scraper): scraper for scraper in SCRAPERS}

        for future in as_completed(future_to_scraper):
            scraper_name, status, error = future.result()
            results.append((scraper_name, status, error))

    print("🎯 All scrapers finished. Summary:")
    for scraper_name, status, error in results:
        print(f" - {scraper_name}: {status}")
    if os.path.exists(ERROR_LOG_FILE):
        print(f"\nCheck '{ERROR_LOG_FILE}' for error details.")

if __name__ == "__main__":
    run_all_scrapers_parallel(max_workers=5)  # run up to 5 scrapers concurrently
