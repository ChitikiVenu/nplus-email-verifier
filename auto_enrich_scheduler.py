import os
import time
import csv
import tldextract
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from check_email import main as verify_main

# Simple TLD → Country map
TLD_COUNTRY = {
    "us": "United States",
    "in": "India",
    "uk": "United Kingdom",
    "ca": "Canada",
    "de": "Germany",
    "fr": "France",
    "au": "Australia",
    "it": "Italy",
    "nl": "Netherlands",
    "jp": "Japan",
    "sg": "Singapore",
    "ae": "United Arab Emirates"
}

# Simple keyword → Industry map
INDUSTRY_KEYWORDS = {
    "pharma": "Healthcare / Pharma",
    "med": "Healthcare / Medical",
    "health": "Healthcare",
    "edu": "Education",
    "school": "Education",
    "college": "Education",
    "gov": "Government",
    "tech": "Technology",
    "software": "Technology",
    "law": "Legal",
    "bank": "Finance / Banking",
    "fin": "Finance",
    "auto": "Automotive",
    "real": "Real Estate",
    "prop": "Real Estate",
    "travel": "Travel / Hospitality",
    "hotel": "Hospitality"
}

PENDING_DIR = "pending"
RESULTS_DIR = "results"

if not os.path.exists(PENDING_DIR):
    os.makedirs(PENDING_DIR)
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)


def guess_company_info(email):
    """Extracts company name, website, country, and industry from email domain."""
    domain = email.split("@")[-1].lower().strip()
    ext = tldextract.extract(domain)
    base_domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain

    # Company Name
    company_name = ext.domain.replace("-", " ").replace("_", " ").title()

    # Website
    website = f"https://{base_domain}"

    # Country
    country = TLD_COUNTRY.get(ext.suffix, "Unknown")

    # Industry
    industry = "Other"
    for key, value in INDUSTRY_KEYWORDS.items():
        if key in ext.domain:
            industry = value
            break

    return company_name, website, country, industry


def enrich_csv(input_file, enriched_file):
    """Adds enrichment columns to CSV."""
    with open(input_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"⚠️  No data found in {input_file}")
        return False

    # Enrich each row
    for row in rows:
        email = row.get("Email") or row.get("email") or ""
        company, website, country, industry = guess_company_info(email)
        row["Company"] = company
        row["Website"] = website
        row["Country"] = country
        row["Industry"] = industry

    # Save enriched CSV
    fieldnames = list(rows[0].keys())
    with open(enriched_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Enriched file saved: {enriched_file}")
    return True


class PendingHandler(FileSystemEventHandler):
    """Watches the /pending folder for new CSV files."""

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".csv"):
            return

        time.sleep(2)  # allow file to fully copy
        file_path = event.src_path
        base_name = os.path.basename(file_path)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        enriched_path = os.path.join(RESULTS_DIR, f"enriched_{timestamp}_{base_name}")

        print(f"\n📥 Detected new file: {base_name}")

        if enrich_csv(file_path, enriched_path):
            print(f"🚀 Starting verification for {base_name} ...")
            stats, _ = verify_main(enriched_path, progress_id=None, orig_filename=base_name)
            print(f"✅ Done: {base_name}")
            print(f"📊 Results → Valid: {stats.get('valid',0)} | Risky: {stats.get('catchall',0)} | "
                  f"Bad: {stats.get('invalid',0)} | Unknown: {stats.get('unknown',0)}")

            os.replace(file_path, os.path.join(RESULTS_DIR, base_name))
            print(f"📦 Moved original file to /results\n")


if __name__ == "__main__":
    print("🔁 Auto Enrichment & Scheduler running...")
    print("Drop CSV files into the 'pending/' folder.")
    event_handler = PendingHandler()
    observer = Observer()
    observer.schedule(event_handler, PENDING_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
