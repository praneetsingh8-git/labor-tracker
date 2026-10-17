# Daily 3-day report

`make_report.py` turns tracker rows (Supabase `lt_events`) into `report.pdf`, `email.html` and `meta.json` (subject, flags, visits needing an AI summary).
A scheduled Claude routine fetches the rows, runs this script and emails both parents every morning.

    pip install reportlab
    python3 report/make_report.py --data rows.json --out report/out
