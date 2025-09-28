import os
import ujson
from datetime import datetime
from dotenv import load_dotenv
import oracledb
from utils import build_dsn

load_dotenv()

def execute_query_and_save(sql: str, out_dir: str):
    user = os.getenv("ORACLE_USER")
    pwd = os.getenv("ORACLE_PASSWORD")
    dsn = build_dsn()

    conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
    cur = conn.cursor()
    cur.execute(sql)

    cols = [c[0] for c in cur.description] if cur.description else []
    rows = cur.fetchall()

    result = []
    for r in rows:
        obj = {}
        for idx, col in enumerate(cols):
            val = r[idx]
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            obj[col] = val
        result.append(obj)

    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(out_dir, f"result_{ts}.json")
    with open(filename, "w", encoding="utf-8") as fh:
        ujson.dump(result, fh, ensure_ascii=False, indent=2)

    cur.close()
    conn.close()
    return filename, len(result)
