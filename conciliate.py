import pandas as pd
from amounts import parse_amount


def precompute_value_cents(df, debito_col, credito_col):
    """
    Pre-computes integer cent values for contabilidade rows.
    Adds a '_value_cents' column to the dataframe in-place.
    Uses sign convention: débito → positive, crédito → negative.
    """
    def row_to_cents(row):
        try:
            D = parse_amount(row[debito_col])
            C = parse_amount(row[credito_col])
        except ValueError as exc:
            raise ValueError(f"Montante inválido na linha {row.name} da Contabilidade: {exc}") from exc
        D = D or 0.0
        C = C or 0.0
        if D != 0 and C != 0:
            raise ValueError(f"A linha {row.name} da Contabilidade tem Débito e Crédito preenchidos.")
        if D != 0:
            return int(round(D * 100))
        elif C != 0:
            return int(round(-C * 100))
        return 0
    df['_value_cents'] = df.apply(row_to_cents, axis=1)


def precompute_extrato_cents(df, value_col):
    """
    Pre-computes integer cent values for extrato rows.
    Adds a '_value_cents' column to the dataframe in-place.
    """
    def to_cents(row):
        idx, value = row.name, row[value_col]
        try:
            amount = parse_amount(value)
        except ValueError as exc:
            raise ValueError(f"Montante inválido na linha {idx} do Extrato: {exc}") from exc
        if amount is None:
            raise ValueError(f"Montante vazio na linha {idx} do Extrato.")
        return int(round(amount * 100))
    df['_value_cents'] = df.apply(to_cents, axis=1)


def group_matches_by_value(df1, df2):
    """
    Groups df1 and df2 index labels by their pre-computed _value_cents values.
    """
    c_groups = {}
    for idx, cents in df1['_value_cents'].items():
        if cents == 0:
            continue
        c_groups.setdefault(cents, []).append(idx)

    e_groups = {}
    for idx, cents in df2['_value_cents'].items():
        e_groups.setdefault(cents, []).append(idx)

    return c_groups, e_groups


def find_next_reconciliation_step(df1, df2, blocked_values=None):
    """
    Scans df1 and df2 for matching transaction groups:
    1. Groups rows by matching numeric values (respecting signs).
    2. Auto-reconciles groups with equal counts of records in both Contabilidade and Extrato.
    3. Identifies the first value where the counts differ (conflict group) and returns it.
    4. If no conflict groups exist, returns status "done".

    Both dataframes must have a pre-computed '_value_cents' column
    (see precompute_value_cents and precompute_extrato_cents).

    Returns:
      - (df1_updated, df2_updated, "done", None)
      - (df1_updated, df2_updated, "conflict", {"value": val_cents, "c_indices": [...], "e_indices": [...]})
    """
    df1_remaining = df1.copy()
    df2_remaining = df2.copy()
    blocked_values = set(blocked_values or ())

    # Build dictionaries once from pre-computed cents
    c_groups, e_groups = group_matches_by_value(df1_remaining, df2_remaining)

    to_drop_df1 = []
    to_drop_df2 = []
    first_conflict = None

    for val, c_indices in c_groups.items():
        e_indices = e_groups.get(val, [])
        if val in blocked_values:
            continue
        if len(e_indices) == 0:
            # No match in extrato — skip (will remain as unmatched)
            continue
        if len(c_indices) == len(e_indices):
            # Auto-reconcile: equal counts
            to_drop_df1.extend(c_indices)
            to_drop_df2.extend(e_indices)
        elif first_conflict is None:
            # First conflict found
            first_conflict = {"value": val, "c_indices": c_indices, "e_indices": e_indices}

    # Drop auto-reconciled rows
    if to_drop_df1:
        df1_remaining.drop(index=to_drop_df1, inplace=True)
    if to_drop_df2:
        df2_remaining.drop(index=to_drop_df2, inplace=True)

    if first_conflict is not None:
        return df1_remaining, df2_remaining, "conflict", first_conflict

    return df1_remaining, df2_remaining, "done", None
