import csv

from pathlib import Path
from DATA_INGESTION.new_approach.processor.filter import HTMLFilter
from DATA_INGESTION.new_approach.processor.cleaner import HTMLCleaner

class HTMLParser:
    """
    Walk through all scraped HTML pages and decide
    which pages should be kept.

    Current Responsibilities
    ------------------------

    ✓ Traverse debug_html folder
    ✓ Call HTMLFilter
    ✓ Print results
    ✓ Save CSV report

    Future

    ✓ Clean HTML
    ✓ Send relevant pages to LLM
    ✓ Generate embeddings
    """

    def __init__(
        self,
        input_folder,
        report_folder,
        output_folder,
    ):

        self.input_folder = Path(input_folder)
        self.report_folder = Path(report_folder)
        self.output_folder = Path(output_folder)

        self.report_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    def run(self):

        rows = []

        html_files = sorted(
            self.input_folder.rglob("*.html")
        )

        print(f"\nFound {len(html_files)} HTML files.\n")

        for html_file in html_files:

            result = HTMLFilter.evaluate(html_file)

            relative = html_file.relative_to(
                self.input_folder
            )

            parts = relative.parts

            country = parts[0] if len(parts) > 0 else ""
            website = parts[1] if len(parts) > 1 else ""

            decision = "KEEP" if result["keep"] else "SKIP"
            if result["keep"]:

                with open(
                    html_file,
                    "r",
                    encoding="utf-8",
                ) as f:

                    html = f.read()

                clean_text = HTMLCleaner.clean(html)

                output_file = (
                    self.output_folder /
                    relative.with_suffix(".txt")
                )

                output_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with open(
                    output_file,
                    "w",
                    encoding="utf-8",
                ) as f:

                    f.write(clean_text)
            print(
                f"{decision:<5} | "
                f"{country:<12} | "
                f"{website:<25} | "
                f"{relative.name}"
            )

            rows.append({

                "country": country,

                "website": website,

                "file": str(relative),

                "decision": decision,

                "reason": result["reason"],

                "title": result["title"],

                "word_count": result["word_count"],

            })

        self.save_report(rows)

        print("\nFiltering complete.")

    def save_report(self, rows):

        report = self.report_folder / "filter_report.csv"

        with open(
            report,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=[

                    "country",
                    "website",
                    "file",
                    "decision",
                    "reason",
                    "title",
                    "word_count",

                ],
            )

            writer.writeheader()

            writer.writerows(rows)

        print(f"\nReport saved to:\n{report}")