# wine_labels.py -- fully automatic with GitHub push
import csv
import requests
import qrcode
import io
import os
import json
import re
import subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

# -------- CONFIG ----------
OUTPUT_PDF = "wine_labels.pdf"
HTML_FOLDER = "wine_pages"
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1KTddeuZ_0kmwKUqL612lr9dGiQTsD67JGwq9-NN1wAI/gviz/tq?tqx=out:csv&gid=1287485054"
GITHUB_USER = "tx3d3sign"   # your GitHub username
GITHUB_REPO = "wine-db"      # your GitHub Pages repo
# --------------------------

if not os.path.exists(HTML_FOLDER):
    os.makedirs(HTML_FOLDER)

ZW_CHARS_RE = re.compile(r'[\u200B-\u200D\uFEFF]')

def clean_field(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    v = ZW_CHARS_RE.sub("", value)
    v = v.replace('\r', ' ').replace('\n', ' ').strip()
    return v

def fetch_wines_from_google_sheet():
    print("Downloading CSV from Google Sheets...")
    response = requests.get(SHEET_CSV_URL)
    response.raise_for_status()
    decoded = response.content.decode("utf-8")
    reader = csv.DictReader(decoded.splitlines())
    raw_rows = list(reader)
    print(f"Raw rows fetched from sheet: {len(raw_rows)}")

    cleaned_rows = []
    for row in raw_rows:
        cleaned = { (k.strip() if k else k): clean_field(v) for k, v in row.items() }
        cleaned_rows.append(cleaned)

    # Only rows with ID starting with W and non-empty Name
    final_rows = []
    seen_ids = set()
    for row in cleaned_rows:
        wine_id = row.get("ID", "").strip()
        name = row.get("Name", "").strip()
        if wine_id.upper().startswith("W") and name:
            if wine_id in seen_ids:
                print(f"WARNING: duplicate ID '{wine_id}' — skipping")
                continue
            seen_ids.add(wine_id)
            final_rows.append(row)

    print(f"Final rows to generate labels for: {len(final_rows)}")
    return final_rows

def generate_html_pages(wines):
    """Generate one HTML page per wine and return relative URLs for QR codes"""
    html_urls = []
    for wine in wines:
        wine_id = wine["ID"]
        html_filename = f"{HTML_FOLDER}/wine_{wine_id}.html"
        html_urls.append(html_filename)

        content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>{wine.get('Name','')} ({wine.get('Vintage','')})</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: auto; }}
                h1 {{ margin-bottom: 0.5em; }}
                p {{ margin: 0.3em 0; }}
            </style>
        </head>
        <body>
            <h1>{wine.get('Name','')} ({wine.get('Vintage','')})</h1>
            <p><b>Type:</b> {wine.get('Type','')}</p>
            <p><b>Region:</b> {wine.get('Region','')}</p>
            <p><b>Purchased at:</b> {wine.get('Purchased at','')}</p>
            <p><b>Notes:</b> {wine.get('Notes','')}</p>
        </body>
        </html>
        """

        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(content)
    return html_urls

def export_json(data, filename="wines.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Exported {len(data)} wines to {filename}")

def push_to_github(filename="wines.json", commit_message="Update wines.json"):
    """Automatically commit and push the JSON file to GitHub"""
    try:
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"✅ Successfully pushed {filename} to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e}")

def generate_pdf(wines):
    c = canvas.Canvas(OUTPUT_PDF, pagesize=letter)
    width, height = letter

    margin_x, margin_y = 50, 50
    col_width, row_height = 300, 120
    qr_size = 80
    items_per_row = 2
    items_per_page = 8

    x_start = margin_x
    y_start = height - margin_y - row_height
    x = x_start
    y = y_start

    BASE_URL = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/wine_pages/"

    for i, wine in enumerate(wines, start=1):
        wine_id = wine["ID"]
        name = wine.get("Name","")
        vintage = wine.get("Vintage","")
        wine_type = wine.get("Type","")
        purchased_at = wine.get("Purchased at","")
        region = wine.get("Region","")
        notes = wine.get("Notes","")

        url = f"{BASE_URL}wine_{wine_id}.html"
        qr = qrcode.make(url)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)
        qr_reader = ImageReader(buffer)

        # Draw QR code
        c.drawImage(qr_reader, x, y, qr_size, qr_size)

        # Draw text
        text_x = x + qr_size + 10
        text_y = y + qr_size - 10
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, f"{name} ({vintage})")
        c.setFont("Helvetica", 9)
        c.drawString(text_x, text_y - 15, f"Type: {wine_type}")
        c.drawString(text_x, text_y - 30, f"Region: {region}")
        c.drawString(text_x, text_y - 45, f"Purchased at: {purchased_at}")
        c.drawString(text_x, text_y - 60, f"Notes: {notes}")

        if i % items_per_row == 0:
            x = x_start
            y -= row_height
        else:
            x += col_width

        if i % items_per_page == 0:
            c.showPage()
            x = x_start
            y = y_start

    c.save()
    print(f"✅ PDF saved: {OUTPUT_PDF}")

# -------- MAIN --------
if __name__ == "__main__":
    wines = fetch_wines_from_google_sheet()
    export_json(wines)
    generate_html_pages(wines)
    generate_pdf(wines)
    push_to_github("wines.json", "Update wines.json after Google Sheet sync")

