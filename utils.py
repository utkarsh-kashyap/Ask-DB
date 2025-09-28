import os
import re
import json
from typing import Dict, Set, Tuple

def build_dsn():
    """
    Prefer ORACLE_DSN (Easy Connect). Otherwise build from ORACLE_HOST/PORT/SERVICE.
    """
    dsn = os.getenv("ORACLE_DSN")
    if dsn:
        return dsn.strip()
    host = (os.getenv("ORACLE_HOST") or "").strip()
    port = (os.getenv("ORACLE_PORT") or "1521").strip()
    service = (os.getenv("ORACLE_SERVICE") or "").strip()
    if not (host and service):
        raise ValueError("Either ORACLE_DSN or ORACLE_HOST+ORACLE_SERVICE must be set in .env")
    return f"{host}:{port}/{service}"

def load_json_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def save_json_file(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)

def strip_trailing_semicolon(sql: str) -> str:
    return sql.rstrip().rstrip(";")

def render_template(template: str, placeholders: Dict[str, str]):
    """
    Replace {PLACEHOLDER} with values from placeholders dict.
    Raises ValueError if a placeholder is missing.
    """
    keys = set(re.findall(r"\{([A-Za-z0-9_]+)\}", template))
    missing = [k for k in keys if k not in placeholders]
    if missing:
        raise ValueError(f"Missing placeholders for keys: {missing}")
    return template.format_map(placeholders)

# ---------------------------
# SQL parsing helpers
# ---------------------------

def _strip_string_literals(sql: str) -> str:
    """
    Remove the contents of single-quoted string literals so dots (.) inside strings
    like '%@example.com' don't get misread as TABLE.COLUMN.
    Keeps balanced quotes so downstream regex stays valid.
    """
    out = []
    i = 0
    in_quote = False
    L = len(sql)
    while i < L:
        ch = sql[i]
        if not in_quote:
            if ch == "'":
                in_quote = True
                out.append("''")  # keep an empty quoted literal
                i += 1
            else:
                out.append(ch)
                i += 1
        else:
            # inside a quoted string
            if ch == "'":
                # escaped quote?
                if i + 1 < L and sql[i + 1] == "'":
                    i += 2  # skip escaped quote
                else:
                    in_quote = False
                    out.append("''")
                    i += 1
            else:
                i += 1
    return "".join(out)

def extract_table_names(sql: str) -> Set[str]:
    """
    Best-effort: capture tables after FROM/JOIN/INTO up to the next clause.
    Returns UPPERCASE table names without schema.
    """
    sql_clean = re.sub(r'\s+', ' ', sql)
    pattern = re.compile(
        r'\b(?:FROM|JOIN|INTO)\s+(.+?)(?=\bWHERE\b|\bJOIN\b|\bON\b|\bGROUP\b|\bORDER\b|\bFETCH\b|\bLIMIT\b|;|$)',
        re.IGNORECASE
    )
    tables = set()
    for match in pattern.finditer(sql_clean):
        group = match.group(1).strip()
        if group.startswith("("):
            continue
        parts = re.split(r'\s*,\s*', group)
        for p in parts:
            token = p.split()[0].strip()
            token = token.strip('"').strip("'")
            if "." in token:
                token = token.split(".")[-1]
            token = re.sub(r'[^\w$#]', '', token)
            if token:
                tables.add(token.upper())
    return tables

def extract_alias_mapping(sql: str) -> Dict[str, str]:
    """
    Extract alias mapping from FROM/JOIN clauses.
    Returns dict: {ALIAS -> TABLE_NAME} in UPPERCASE.
    Handles optional AS keyword and schema-qualified names.
    """
    sql_clean = re.sub(r'\s+', ' ', sql)
    # FROM <table> [AS] <alias>
    # JOIN <table> [AS] <alias>
    pattern = re.compile(
        r'\b(?:FROM|JOIN)\s+([A-Za-z0-9_$#".]+)\s+(?:AS\s+)?([A-Za-z0-9_$#"]+)\b',
        re.IGNORECASE
    )
    stop_words = {"WHERE", "ON", "JOIN", "GROUP", "ORDER", "FETCH", "LIMIT"}
    mapping: Dict[str, str] = {}
    for m in pattern.finditer(sql_clean):
        raw_table = m.group(1)
        alias = m.group(2)
        if alias.upper() in stop_words:
            continue
        # normalize table: keep last part if owner-qualified
        table = raw_table.strip('"').split(".")[-1]
        table = table.strip('"').strip("'").upper()
        alias = alias.strip('"').strip("'").upper()
        mapping[alias] = table
    return mapping

def extract_qualified_columns(sql: str) -> Set[Tuple[str, str]]:
    """
    Finds patterns like TABLE.COLUMN but ignores anything inside single-quoted strings.
    Returns set of (QUALIFIER, COLUMN) both UPPERCASE (qualifier may be table or alias).
    """
    stripped = _strip_string_literals(sql)
    pairs = set()
    for match in re.finditer(r'\b([A-Za-z0-9_$#"]+)\.([A-Za-z0-9_$#"]+)\b', stripped):
        t = match.group(1).strip('"').upper()
        c = match.group(2).strip('"').upper()
        if '.' in t:
            t = t.split('.')[-1].upper()
        pairs.add((t, c))
    return pairs
