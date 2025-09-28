import json
import os
from dotenv import load_dotenv
from utils import strip_trailing_semicolon
from llm_client import call_llm

load_dotenv()
CONFIG = json.load(open("config.json", "r", encoding="utf-8"))

PROMPT_TEMPLATE = """
You are a SQL generator for an Oracle database. IMPORTANT: return only ONE valid SQL SELECT query (no explanation).
- Use only tables and column names that exist in the schema.
- Oracle SQL syntax, single quotes for string literals.
- Do NOT use destructive statements: DELETE, DROP, UPDATE, INSERT, TRUNCATE, ALTER, MERGE.
- One statement only; no comments; no code fences.

=== SCHEMA (table: columns) ===
{schema_snippet}
=== END SCHEMA ===

=== EXAMPLE QUERIES (for reference) ===
{examples_snippet}
=== END EXAMPLES ===

User request:
\"\"\"{user_input}\"\"\"

Return only the SQL query:
"""

def _schema_to_lines(schema: dict):
    lines = []
    for table, info in schema.items():
        cols = ", ".join(info.get("columns", {}).keys())
        lines.append(f"{table}: {cols}")
    return "\n".join(lines)

def _examples_to_lines(config: dict):
    eq = config.get("example_queries", {}) or {}
    return "\n".join([f"{k}: {v}" for k, v in eq.items()])

def generate_sql(user_input: str, schema: dict, *_unused) -> str:
    schema_snippet = _schema_to_lines(schema)
    examples_snippet = _examples_to_lines(CONFIG)
    prompt = PROMPT_TEMPLATE.format(
        schema_snippet=schema_snippet,
        examples_snippet=examples_snippet,
        user_input=user_input
    )
    resp = call_llm(
        prompt,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024"))
    )
    sql = strip_trailing_semicolon(resp).strip().strip("`")
    return sql
