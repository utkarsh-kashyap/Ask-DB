import sys
import os
import logging
from dotenv import load_dotenv
from utils import load_json_file, render_template
from schema_extractor import extract_schema
from query_generator import generate_sql
from query_validator import validate_sql
from db_fetcher import execute_query_and_save

load_dotenv()

LOGFILE = "demo.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOGFILE), logging.StreamHandler()]
)

CONFIG = load_json_file("config.json")
OUTPUT_DIR = CONFIG.get("output_folder", os.getenv("OUTPUT_DIR", "output"))

def load_or_extract_schema():
    if os.path.exists("schema.json"):
        logging.info("Loading existing schema.json")
        return load_json_file("schema.json")
    logging.info("schema.json not found — extracting schema from DB")
    return extract_schema("schema.json")

def attempt_correction(original_sql, user_input, schema):
    correction_prompt = f"""The previously generated SQL failed validation.
Original SQL:
{original_sql}

User request:
{user_input}

Please generate a single safe SELECT query that uses only known tables/columns from the schema and matches the user's intent.
Return only the SQL.
"""
    logging.info("Attempting one LLM correction attempt")
    return generate_sql(correction_prompt, schema)

def main():
    schema = load_or_extract_schema()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("Enter your request: ").strip()

    if not user_input:
        # If no input, try default_query (if defined)
        default_query = CONFIG.get("default_query")
        if not default_query:
            print("No input provided and no default_query configured. Exiting.")
            return
        try:
            sql = render_template(default_query, os.environ)
        except Exception as e:
            logging.error(f"Failed to render default_query: {e}")
            return
    else:
        logging.info("Generating SQL via LLM...")
        sql = generate_sql(user_input, schema)

    logging.info("Generated SQL:")
    print("\n--- GENERATED SQL ---")
    print(sql)
    print("---------------------\n")

    logging.info("Validating SQL...")
    ok, msg = validate_sql(sql, schema)
    if not ok:
        logging.warning(f"Validation failed: {msg}")
        corrected = attempt_correction(sql, user_input, schema)
        ok2, msg2 = validate_sql(corrected, schema)
        if ok2:
            logging.info("Correction succeeded.")
            sql = corrected
        else:
            logging.error(f"Correction failed: {msg2}")
            # fallback to default query if available
            default_query = CONFIG.get("default_query")
            if default_query:
                try:
                    sql = render_template(default_query, os.environ)
                    logging.info("Using default_query fallback.")
                except Exception as e:
                    logging.error(f"Cannot render default_query: {e}")
                    return
            else:
                print("No valid SQL could be produced and no default_query is configured. Exiting.")
                return

    logging.info("Executing SQL on DB...")
    out_file, rows = execute_query_and_save(sql, OUTPUT_DIR)
    logging.info(f"Done. {rows} rows saved to {out_file}")
    print(f"✅ Results saved to: {out_file} ({rows} rows)")

if __name__ == "__main__":
    main()
