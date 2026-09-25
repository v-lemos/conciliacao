import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import pdfplumber
from amounts import parse_amount


# ============================================================
# CONFIGURAÇÃO
# ============================================================

COLUMNS = [
    "Data",
    "Data-Movimento",
    "Descrição",
    "Moeda",
    "Valor",
    "Saldo",
]


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def parse_number(value):
    """
    Converte números no formato português:

        20.549,67 -> 20549.67
        -22,00     -> -22.00
        36.900,00  -> 36900.00
    """

    value = value.strip()

    if not value:
        return None

    # Remove separador de milhares e troca vírgula decimal
    value = value.replace(".", "").replace(",", ".")

    try:
        return parse_amount(value)
    except ValueError as exc:
        raise ValueError(f"Valor numérico inválido no PDF: {value!r}") from exc


def is_transaction_line(line):
    """
    Verifica se uma linha parece ser um movimento bancário.

    Formato esperado:

        DD-MM DD-MM DESCRIÇÃO VALOR SALDO

    ou:

        DD-MM DESCRIÇÃO VALOR SALDO
    """

    pattern = (
        r"^\s*"
        r"\d{2}-\d{2}\s+"
        r"(?:\d{2}-\d{2}\s+)?"
        r".+?"
        r"\s+"
        r"-?\d{1,3}(?:\.\d{3})*,\d{2}\s+"
        r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
        r"\s*$"
    )

    return bool(re.match(pattern, line))


def parse_transaction(line):
    """
    Extrai uma transação individual.
    """

    pattern = re.compile(
        r"^\s*"
        r"(?P<data>\d{2}-\d{2})\s+"
        r"(?:(?P<data_movimento>\d{2}-\d{2})\s+)?"
        r"(?P<descricao>.*?)\s+"
        r"(?P<valor>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+"
        r"(?P<saldo>-?\d{1,3}(?:\.\d{3})*,\d{2})"
        r"\s*$"
    )

    match = pattern.match(line)

    if not match:
        return None

    data = match.group("data")
    data_movimento = match.group("data_movimento")

    # Em alguns casos Santander pode não repetir a segunda data.
    if data_movimento is None:
        data_movimento = data

    return {
        "data": data,
        "data_movimento": data_movimento,
        "descricao": match.group("descricao").strip(),
        "moeda": "EUR",
        "valor": parse_number(match.group("valor")),
        "saldo": parse_number(match.group("saldo")),
    }


def _transaction_start(line):
    """Return whether a line starts with the date fields of a movement."""
    return bool(re.match(r"^\s*\d{2}-\d{2}(?:\s+\d{2}-\d{2})?\s+", line))


# ============================================================
# EXTRAÇÃO DO PDF
# ============================================================

def extract_transactions(pdf_path):
    """Extract movements from a Santander account statement PDF."""
    transactions = []
    inside_transactions = False
    end_markers = (
        "Saldo Contabilístico Final",
        "Saldo Disponível Final",
        "Saldo da Facilidade",
        "Novo saldo da Facilidade",
    )

    with pdfplumber.open(BytesIO(pdf_path) if isinstance(pdf_path, (bytes, bytearray)) else pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split())
                if not line:
                    continue

                normalized_line = line.casefold()
                if "detalhe de movimentos da conta à ordem" in normalized_line:
                    inside_transactions = True
                    continue
                if not inside_transactions:
                    continue
                if line.startswith(end_markers):
                    return transactions
                if line.startswith("Saldo Inicial") or line in {
                    "Data", "Mov", "Valor", "Descritivo do Movimento",
                    "Moeda", "Saldo", "Continuação",
                }:
                    continue

                # This statement prints both dates, followed by description,
                # movement value and running balance on one extracted line.
                transaction = parse_transaction(line)
                if transaction:
                    transactions.append(transaction)

    return transactions


# ============================================================
# LIMPEZA
# ============================================================

def clean_dataframe(transactions):
    # Parser records use internal lowercase keys; map them to the workbook's
    # user-facing column names (passing COLUMNS directly silently made every
    # exported cell empty because pandas could not match the keys).
    column_mapping = {
        "Data": "data",
        "Data-Movimento": "data_movimento",
        "Descrição": "descricao",
        "Moeda": "moeda",
        "Valor": "valor",
        "Saldo": "saldo",
    }
    df = pd.DataFrame(
        [{column: transaction.get(key) for column, key in column_mapping.items()} for transaction in transactions],
        columns=COLUMNS,
    )

    if df.empty:
        return df

    # Remove duplicados acidentais
    df = df.drop_duplicates()

    # Mantém a ordem original do PDF
    df = df.reset_index(drop=True)

    return df


# ============================================================
# EXPORTAÇÃO
# ============================================================

def export_excel(df, output=None):
    """Return the extracted statement as an Excel workbook in memory."""
    output = output or BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Movimentos")
        worksheet = writer.sheets["Movimentos"]
        for column_cells in worksheet.columns:
            max_length = max(
                (len(str(cell.value)) for cell in column_cells if cell.value is not None),
                default=0,
            )
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 60)
    return output.getvalue() if isinstance(output, BytesIO) else output


def parse_pdf_to_excel(pdf_source):
    """Parse a Santander PDF file (path or bytes) and return Excel workbook bytes."""
    transactions = extract_transactions(pdf_source)
    if not transactions:
        raise ValueError("Não foram encontrados movimentos no PDF. Verifique se é um extrato Santander compatível.")
    return export_excel(clean_dataframe(transactions))
