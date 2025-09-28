import re
import sqlparse
from utils import extract_table_names, extract_qualified_columns, extract_alias_mapping

FORBIDDEN_KEYWORDS = ["DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "MERGE", "GRANT", "REVOKE"]

def contains_forbidden(sql: str):
    s = sql.upper()
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', s):
            return True, kw
    return False, None

def is_select_query(sql: str):
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False, "Could not parse SQL"
    stmt = parsed[0]
    for tok in stmt.tokens:
        if not tok.is_whitespace:
            first = tok
            break
    else:
        return False, "No tokens found"
    if getattr(first, "normalized", "").upper() in ("SELECT", "WITH"):
        return True, "SELECT/WITH"
    return False, f"Query must be SELECT or WITH; found: {first.value}"

def validate_against_schema(sql: str, schema: dict):
    """
    - Ensure all referenced tables exist.
    - Ensure qualified columns (t.col) refer to known tables or their aliases, and column exists.
    """
    issues = []

    # 1) Table existence
    tables = extract_table_names(sql)
    for t in tables:
        if t not in schema:
            issues.append(f"Unknown table referenced: {t}")

    # 2) Qualified columns (respect aliases)
    alias_map = extract_alias_mapping(sql)  # ALIAS -> TABLE
    qcols = extract_qualified_columns(sql)  # set of (qualifier, column)
    for qual, col in qcols:
        if qual in schema:
            # qualifier is a real table
            if col not in schema[qual].get("columns", {}):
                issues.append(f"Unknown column {col} in table {qual}")
        elif qual in alias_map:
            real_table = alias_map[qual]
            if real_table not in schema or col not in schema[real_table].get("columns", {}):
                issues.append(f"Unknown column {col} in table {real_table} (alias {qual})")
        else:
            # Qualifier isn't a known table or alias (could be function/schema/etc.) — ignore conservatively
            # We do NOT flag this as an error to avoid false positives.
            pass

    return issues

def validate_sql(sql: str, schema: dict):
    sql = sql.strip()

    # forbid multi-statement chains
    if ";" in sql.rstrip().rstrip(";"):
        return False, "Multiple statements detected; only a single SELECT is allowed."

    # forbid DDL/DML
    forb, kw = contains_forbidden(sql)
    if forb:
        return False, f"Forbidden keyword found: {kw}"

    # ensure SELECT/WITH
    sel_ok, sel_msg = is_select_query(sql)
    if not sel_ok:
        return False, sel_msg

    # schema checks
    schema_issues = validate_against_schema(sql, schema)
    if schema_issues:
        return False, "; ".join(schema_issues)

    return True, "Validation passed"
