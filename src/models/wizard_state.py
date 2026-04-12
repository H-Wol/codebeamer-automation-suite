from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import pandas as pd


@dataclass
class WizardState:
    project_id: int | None = None
    tracker_id: int | None = None

    raw_df: pd.DataFrame | None = None
    merged_df: pd.DataFrame | None = None
    hierarchy_df: pd.DataFrame | None = None
    upload_df: pd.DataFrame | None = None
    converted_upload_df: pd.DataFrame | None = None

    schema: dict | None = None
    schema_df: pd.DataFrame | None = None
    comparison_df: pd.DataFrame | None = None
    option_candidates_df: pd.DataFrame | None = None
    option_maps: dict[str, Any] | None = None
    option_check_df: pd.DataFrame | None = None

    selected_mapping: dict[str, str] = field(default_factory=dict)
    selected_option_mapping: dict[str, str] = field(default_factory=dict)
    table_field_mapping: dict[str, dict[str, Any]] = field(default_factory=dict)
    list_cols: list[str] = field(default_factory=list)
    user_lookup_cache: dict[tuple[int | None, str], tuple[Any, Any, str, str | None]] = field(default_factory=dict)

    upload_result: dict[str, Any] | None = None
