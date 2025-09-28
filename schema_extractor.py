import os
from dotenv import load_dotenv
import oracledb
from utils import build_dsn, save_json_file

load_dotenv()

OUT_FILE = "schema.json"

def extract_schema(output_file=OUT_FILE):
    """
    Extract schema details (tables and their columns) from Oracle DB.
    Controlled by environment variables:
      - SCHEMA_OWNER       : owner/schema name (e.g. DEMO_USER)
      - SCHEMA_TABLES      : comma-separated list of tables (optional)
      - SCHEMA_TABLE_PREFIX: prefix filter (optional)
      - SCHEMA_MAX_TABLES  : limit number of tables fetched (optional)
    """
    user = os.getenv("ORACLE_USER")
    pwd = os.getenv("ORACLE_PASSWORD")
    dsn = build_dsn()
    owner = os.getenv("SCHEMA_OWNER")
    table_list_env = os.getenv("SCHEMA_TABLES")
    prefix = os.getenv("SCHEMA_TABLE_PREFIX")
    max_tables = int(os.getenv("SCHEMA_MAX_TABLES") or 0)

    conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
    cur = conn.cursor()

    # --- Get list of tables ---
    if owner:
        cur.execute(
            "SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER = :owner ORDER BY TABLE_NAME",
            {"owner": owner.upper()}
        )
        tables_raw = [r[0] for r in cur.fetchall()]
    else:
        cur.execute("SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME")
        tables_raw = [r[0] for r in cur.fetchall()]

    # --- Apply filters ---
    tables = []
    if table_list_env:
        raw = table_list_env.strip().strip('"').strip("'")
        wanted = set([t.strip().upper() for t in raw.split(",") if t.strip()])
        tables = [t for t in tables_raw if t.upper() in wanted]
    elif prefix:
        pref = prefix.strip().upper()
        tables = [t for t in tables_raw if t.upper().startswith(pref)]
    else:
        tables = tables_raw

    if max_tables and len(tables) > max_tables:
        tables = tables[:max_tables]

    # --- Extract columns for each table ---
    schema = {}
    for tbl in tables:
        if owner:
            q = """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :owner AND TABLE_NAME = :tbl_name
            ORDER BY COLUMN_ID
            """
            cur.execute(q, {"owner": owner.upper(), "tbl_name": tbl.upper()})
        else:
            q = """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = :tbl_name
            ORDER BY COLUMN_ID
            """
            cur.execute(q, {"tbl_name": tbl.upper()})

        cols = {row[0].upper(): row[1] for row in cur.fetchall()}
        schema[tbl.upper()] = {"columns": cols}

    cur.close()
    conn.close()

    save_json_file(schema, output_file)
    print(f"✅ Extracted {len(schema)} tables to {output_file}")
    return schema


if __name__ == "__main__":
    extract_schema()
