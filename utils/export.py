"""Export helpers for Streamlit download actions."""

from __future__ import annotations

import io

import pandas as pd


def dataframe_to_excel_bytes(dataframe: pd.DataFrame, sheet_name: str) -> bytes:
    """Serialize a DataFrame to an in-memory Excel workbook."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
