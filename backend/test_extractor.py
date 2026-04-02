import urllib.parse
from app.services.pdf_parser import parse_pdf
from app.services.table_extractor import extract_parameters
from app.services.table_extractor import classify_columns

with open('C:/components pdf/nmos infineon.pdf', 'rb') as f:
    b = f.read()

doc = parse_pdf(b)
for page in doc.pages:
    for t in page.tables:
        params = extract_parameters(t)
        print(f"\n--- Page {page.page} Table ---")
        print("Headers:", t.headers)
        print("Roles:", classify_columns(t.headers))
        if t.rows:
            print("First row:", t.rows[0])
            if len(t.rows) > 1:
                print("Second row:", t.rows[1])
        print(f"Extracted parameters: {len(params)}")
