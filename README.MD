

## Project Structure
```
project/
│
├── models/
│   ├── visa_knowledge.py
│   └── page_extraction.py
│
├── utils/
│   ├── scraper_utils.py
│   ├── llm_utils.py
│   ├── prompts_utils.py
│   ├── data_utils.py
│   └── discovery_utils.py
│
├── config.py
├── main.py
├── requirements.txt
├── .env
└── germany_knowledge.csv


## Installation

1. **Create and Activate a Virtual Environment**


2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Your Environment Variables**

   Create a `.env` file in the root directory with content similar to:

   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

   *(Note: The `.env` file is in your .gitignore, so it won’t be pushed to version control.)*

## Usage

To start the crawler, run:

```bash
python main.py
```
