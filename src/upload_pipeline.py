from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .wizard import CodebeamerUploadWizard


@dataclass
class ValidationPreparation:
    comparison_df: pd.DataFrame
    selected_option_mapping: dict[str, str]
    option_check_df: pd.DataFrame
    payload_df: pd.DataFrame


def load_tracker_schema_df(
    wizard: CodebeamerUploadWizard,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """현재 선택된 tracker의 schema와 flatten된 schema_df를 함께 만든다."""
    if wizard.state.tracker_id is None:
        raise ValueError("tracker_id must be selected first.")
    schema = wizard.client.get_tracker_schema(wizard.state.tracker_id)
    schema_df = wizard.mapper.flatten_schema_fields(schema)
    return schema, schema_df


def suggest_mapping_from_headers(
    headers: list[str],
    schema_df: pd.DataFrame,
) -> dict[str, str]:
    """헤더와 schema를 기준으로 자동 매핑 후보를 만든다."""
    selected_mapping: dict[str, str] = {}
    schema_field_names = set(schema_df["field_name"].dropna().astype(str).str.strip())
    table_field_names = set(
        schema_df[schema_df.get("is_table_field", False).fillna(False)]["field_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    for header in headers:
        if header in schema_field_names:
            selected_mapping[header] = header
            continue

        if "." in header:
            potential_table_field = header.split(".", 1)[0].strip()
            if potential_table_field in table_field_names:
                selected_mapping[header] = potential_table_field
                continue

        for schema_field in schema_field_names:
            if header.lower() == schema_field.lower():
                selected_mapping[header] = schema_field
                break

    return selected_mapping


def prepare_upload_dataframe(
    wizard: CodebeamerUploadWizard,
    *,
    file_path: str,
    sheet_name: str | int,
    summary_col: str,
    selected_mapping: dict[str, str],
    schema: dict[str, Any] | None = None,
    schema_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """CLI와 GUI가 공통으로 쓰는 업로드용 DataFrame 준비 함수다."""
    if wizard.reader is None:
        raise ValueError("wizard.reader 가 준비되지 않았습니다.")

    if schema is None or schema_df is None:
        schema, schema_df = load_tracker_schema_df(wizard)

    list_cols = wizard.mapper.get_list_columns_for_mapping(selected_mapping, schema_df)
    wizard.reader.summary_col = summary_col
    raw_df = wizard.reader.read_excel(file_path=file_path, sheet_name=sheet_name)
    wizard.load_raw_dataframe(raw_df, list_cols=list_cols)
    wizard.state.schema = schema
    wizard.state.schema_df = schema_df
    wizard._detect_table_field_columns()
    return raw_df, list_cols


def run_validation_pipeline(
    wizard: CodebeamerUploadWizard,
    selected_mapping: dict[str, str],
) -> ValidationPreparation:
    """CLI와 GUI가 공통으로 쓰는 검증 및 payload 생성 시퀀스다."""
    comparison_df = wizard.load_schema_and_compare(selected_mapping)
    selected_option_mapping, option_check_df = wizard.process_option_mapping(selected_mapping)
    payload_df = wizard.build_payloads(force=True)
    return ValidationPreparation(
        comparison_df=comparison_df,
        selected_option_mapping=selected_option_mapping,
        option_check_df=option_check_df,
        payload_df=payload_df,
    )

