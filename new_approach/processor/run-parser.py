from parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

parser = HTMLParser(
    input_folder=BASE_DIR / "debug_html",
    report_folder=BASE_DIR / "reports",
    output_folder=BASE_DIR / "cleaned_text",
)

parser.run()
