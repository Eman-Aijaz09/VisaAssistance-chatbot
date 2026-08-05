import sqlite3

DATABASE_NAME = "visa_assistant.db"


def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visa_knowledge (

            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stable_id TEXT UNIQUE,

            country TEXT,
            source_url TEXT,
            page_title TEXT,

            purpose TEXT,
            topic TEXT,
            visa_type TEXT,
            entry_type TEXT,

            title TEXT,
            summary TEXT,

            eligibility TEXT,
            required_documents TEXT,
            application_process TEXT,

            processing_time TEXT,
            application_fee TEXT,
            validity TEXT,

            official_links TEXT,
            important_notes TEXT,

            min_income_threshold TEXT,
            min_education_level TEXT,
            min_age INTEGER,
            max_age INTEGER,
            required_language_test TEXT,
            min_language_score TEXT,
            points_required INTEGER,
            mandatory_prerequisites TEXT,
            total_estimated_cost REAL,
            cost_currency TEXT,

            processing_time_days_min INTEGER,
            processing_time_days_max INTEGER,
            pr_pathway_available BOOLEAN,
            pr_pathway_years INTEGER,

            last_verified_date TEXT,

            extra_information TEXT,

            content TEXT,
            embedding_text TEXT,

            content_hash TEXT,          -- NEW: hash of `content`, used to detect real changes
            last_embedded_at TEXT,        -- NEW: timestamp of last successful embedding, for your own tracing

            total_estimated_cost_usd REAL
        );
        """)

    conn.commit()
    conn.close()

    print("Database created successfully.")


if __name__ == "__main__":
    create_database()