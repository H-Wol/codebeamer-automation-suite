from __future__ import annotations

from .wizard_support import *  # noqa: F403


class WizardTrackerItemLookupMixin:
    def _tracker_item_lookup_cache_key(self, schema_field: str, lookup_text: Any) -> tuple[str, str]:
        """TrackerItemChoiceField lookup 결과 캐시 키를 만든다."""
        return (
            str(schema_field).strip(),
            self._normalize_lookup_text(lookup_text).casefold(),
        )

    def _tracker_item_setting(
        self,
        schema_field: str,
        option_info: dict[str, Any],
    ) -> dict[str, Any]:
        """필드별 TrackerItemChoiceField 처리 방식을 정규화한다."""
        raw_setting = self.state.selected_tracker_item_settings.get(str(schema_field).strip(), {})
        source_tracker_ids = option_info.get("tracker_item_source_tracker_ids") or []

        normalized_source_tracker_ids: list[int] = []
        seen_ids: set[int] = set()
        for raw_tracker_id in source_tracker_ids or []:
            try:
                normalized_tracker_id = int(raw_tracker_id)
            except Exception:
                continue
            if normalized_tracker_id in seen_ids:
                continue
            seen_ids.add(normalized_tracker_id)
            normalized_source_tracker_ids.append(normalized_tracker_id)

        mode = str(raw_setting.get("mode") or "").strip()
        if mode not in {
            TrackerItemResolutionMode.REGEX.value,
            TrackerItemResolutionMode.QUERY.value,
        }:
            mode = (
                TrackerItemResolutionMode.QUERY.value
                if normalized_source_tracker_ids
                else TrackerItemResolutionMode.REGEX.value
            )
        if mode == TrackerItemResolutionMode.QUERY.value and not normalized_source_tracker_ids:
            mode = TrackerItemResolutionMode.REGEX.value
        query_match_strategy = str(
            raw_setting.get("query_match_strategy")
            or TrackerItemQueryMatchStrategy.BEST.value
        ).strip()
        if query_match_strategy not in {
            TrackerItemQueryMatchStrategy.FIRST.value,
            TrackerItemQueryMatchStrategy.LAST.value,
            TrackerItemQueryMatchStrategy.BEST.value,
            TrackerItemQueryMatchStrategy.ERROR.value,
        }:
            query_match_strategy = TrackerItemQueryMatchStrategy.BEST.value

        return {
            "mode": mode,
            "regex_pattern": str(raw_setting.get("regex_pattern") or DEFAULT_TRACKER_ITEM_ID_REGEX).strip(),
            "source_tracker_ids": normalized_source_tracker_ids,
            "query_match_strategy": query_match_strategy,
        }

    def _decorate_tracker_item_option_maps(
        self,
        option_maps: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """TrackerItemChoiceField option map에 GUI 선택 설정을 반영한다."""
        decorated: dict[str, dict[str, Any]] = {}
        for schema_field, option_info in option_maps.items():
            if option_info.get("kind") != OptionMapKind.TRACKER_ITEM_DIRECT.value:
                decorated[schema_field] = option_info
                continue

            setting = self._tracker_item_setting(schema_field, option_info)
            decorated[schema_field] = {
                **option_info,
                "tracker_item_mode": setting["mode"],
                "tracker_item_regex_pattern": setting["regex_pattern"],
                "tracker_item_source_tracker_ids": setting["source_tracker_ids"],
                "tracker_item_query_match_strategy": setting["query_match_strategy"],
            }

        return decorated

    @staticmethod
    def _tracker_item_candidate_similarity(lookup_text: str, candidate_name: Any) -> tuple[int, int, int, float, int]:
        normalized_lookup = str(lookup_text or "").strip().casefold()
        normalized_candidate = str(candidate_name or "").strip().casefold()
        if not normalized_candidate:
            return (0, 0, 0, 0.0, 0)
        exact_match = int(normalized_candidate == normalized_lookup)
        prefix_match = int(bool(normalized_lookup) and normalized_candidate.startswith(normalized_lookup))
        contains_match = int(bool(normalized_lookup) and normalized_lookup in normalized_candidate)
        similarity = SequenceMatcher(None, normalized_lookup, normalized_candidate).ratio()
        length_penalty = -abs(len(normalized_candidate) - len(normalized_lookup))
        return (exact_match, prefix_match, contains_match, similarity, length_penalty)

    def _select_tracker_item_query_candidate(
        self,
        lookup_text: str,
        candidates: list[dict[str, Any]],
        option_info: dict[str, Any],
    ) -> TrackerItemLookupCacheEntry:
        strategy = str(
            option_info.get("tracker_item_query_match_strategy")
            or TrackerItemQueryMatchStrategy.BEST.value
        ).strip()
        if len(candidates) == 1:
            return candidates[0], "RESOLVED", None
        if strategy == TrackerItemQueryMatchStrategy.FIRST.value:
            return candidates[0], "RESOLVED", None
        if strategy == TrackerItemQueryMatchStrategy.LAST.value:
            return candidates[-1], "RESOLVED", None
        if strategy == TrackerItemQueryMatchStrategy.BEST.value:
            best_candidate = max(
                candidates,
                key=lambda candidate: self._tracker_item_candidate_similarity(
                    lookup_text,
                    candidate.get("name"),
                ),
            )
            return best_candidate, "RESOLVED", None

        candidate_names = ", ".join(
            str(candidate.get("name") or candidate.get("id"))
            for candidate in candidates[:5]
        )
        return (
            None,
            OptionCheckStatus.TRACKER_ITEM_LOOKUP_AMBIGUOUS.value,
            f"tracker item lookup is ambiguous: {candidate_names}",
        )

    def _lookup_tracker_item_reference_by_query(
        self,
        schema_field: str,
        raw_value: Any,
        option_info: dict[str, Any],
    ) -> TrackerItemLookupCacheEntry:
        """구성된 source tracker에서 이름 또는 summary로 tracker item을 찾는다."""
        lookup_text = self._normalize_lookup_text(raw_value)
        cache_key = self._tracker_item_lookup_cache_key(schema_field, lookup_text)
        if cache_key in self.state.tracker_item_lookup_cache:
            return self.state.tracker_item_lookup_cache[cache_key]

        source_tracker_ids = option_info.get("tracker_item_source_tracker_ids") or []
        if not source_tracker_ids:
            entry = (
                None,
                OptionCheckStatus.OPTION_SOURCE_UNAVAILABLE.value,
                "tracker item query source tracker가 configuration에 없습니다.",
            )
            self.state.tracker_item_lookup_cache[cache_key] = entry
            return entry

        try:
            resolved_candidates: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for source_tracker_id in source_tracker_ids:
                candidates = self.client.search_tracker_items_by_name(
                    tracker_id=int(source_tracker_id),
                    name=lookup_text,
                )
                for candidate in candidates:
                    candidate_id = candidate.get("id")
                    if candidate_id is None:
                        continue
                    normalized_id = int(candidate_id)
                    if normalized_id in seen_ids:
                        continue
                    seen_ids.add(normalized_id)
                    resolved_candidates.append({
                        "id": normalized_id,
                        "name": str(candidate.get("name") or lookup_text).strip() or lookup_text,
                        "type": ReferenceType.TRACKER_ITEM.value,
                    })

            if resolved_candidates:
                entry = self._select_tracker_item_query_candidate(
                    lookup_text,
                    resolved_candidates,
                    option_info,
                )
            else:
                entry = (
                    None,
                    OptionCheckStatus.TRACKER_ITEM_LOOKUP_NOT_FOUND.value,
                    f"tracker item lookup failed: {lookup_text!r}",
                )
        except Exception as exc:
            entry = (None, OptionCheckStatus.LOOKUP_REQUIRED.value, str(exc))

        self.state.tracker_item_lookup_cache[cache_key] = entry
        return entry

    def _resolve_tracker_item_reference_value(
        self,
        schema_field: str,
        raw_value: Any,
        option_info: dict[str, Any],
    ) -> TrackerItemLookupCacheEntry:
        """TrackerItemChoiceField 값을 정규식 또는 query 방식으로 해석한다."""
        mode = str(option_info.get("tracker_item_mode") or TrackerItemResolutionMode.REGEX.value)
        multiple_values = bool(option_info.get("multiple_values", False))

        if mode == TrackerItemResolutionMode.QUERY.value:
            if multiple_values:
                lookup_items = self.mapper.normalize_multi_value_items(raw_value)
                resolved_values = []
                for item in lookup_items:
                    if item is None or self._normalize_lookup_text(item) == "":
                        continue
                    resolved, status, error = self._lookup_tracker_item_reference_by_query(
                        schema_field,
                        item,
                        option_info,
                    )
                    if resolved is None:
                        return None, status, error
                    resolved_values.append(resolved)
                if resolved_values:
                    return resolved_values, "RESOLVED", None

            return self._lookup_tracker_item_reference_by_query(schema_field, raw_value, option_info)

        regex_pattern = str(option_info.get("tracker_item_regex_pattern") or "").strip()
        if not regex_pattern:
            return (
                None,
                OptionCheckStatus.TRACKER_ITEM_REGEX_MISSING.value,
                "tracker item regex pattern is empty",
            )

        try:
            resolved = self.mapper.resolve_tracker_item_reference_value_with_regex(
                raw_value,
                multiple_values=multiple_values,
                pattern=regex_pattern,
            )
            return resolved, "RESOLVED", None
        except Exception as exc:
            return None, OptionCheckStatus.DIRECT_PARSE_FAILED.value, str(exc)

    def collect_tracker_item_query_values(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict[str, Any]],
    ) -> dict[str, set[str]]:
        """query 방식 TrackerItemChoiceField에 필요한 고유 lookup 값을 모은다."""
        values_by_field: dict[str, set[str]] = {}
        for df_col, schema_field in option_mapping.items():
            option_info = option_maps.get(schema_field, {})
            if option_info.get("kind") != OptionMapKind.TRACKER_ITEM_DIRECT.value:
                continue
            if str(option_info.get("tracker_item_mode") or "") != TrackerItemResolutionMode.QUERY.value:
                continue
            if df_col not in upload_df.columns:
                continue

            unique_values = values_by_field.setdefault(schema_field, set())
            for raw_value in upload_df[df_col].tolist():
                items = self.mapper.normalize_multi_value_items(raw_value)
                for item in items:
                    normalized = self._normalize_lookup_text(item)
                    if normalized:
                        unique_values.add(normalized)

        return values_by_field

    def prime_tracker_item_query_values(
        self,
        option_maps: dict[str, dict[str, Any]],
        values_by_field: dict[str, set[str]],
    ) -> None:
        """고유 lookup 값을 먼저 조회해 tracker item query 결과를 캐시에 채운다."""
        for schema_field, values in values_by_field.items():
            option_info = option_maps.get(schema_field, {})
            for lookup_text in sorted(values):
                self._lookup_tracker_item_reference_by_query(schema_field, lookup_text, option_info)

    def _resolve_tracker_item_reference_fields(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict[str, Any]],
    ) -> pd.DataFrame:
        """TrackerItemChoiceField 값을 선택된 전략에 따라 미리 해석한다."""
        work = upload_df.copy()
        self.prime_tracker_item_query_values(
            option_maps,
            self.collect_tracker_item_query_values(work, option_mapping, option_maps),
        )

        for df_col, schema_field in option_mapping.items():
            option_info = option_maps.get(schema_field, {})
            if option_info.get("kind") != OptionMapKind.TRACKER_ITEM_DIRECT.value:
                continue

            resolved_values = []
            statuses = []
            errors = []

            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
                    resolved_values.append(None)
                    statuses.append(None)
                    errors.append(None)
                    continue

                resolved, status, error = self._resolve_tracker_item_reference_value(
                    schema_field,
                    raw_value,
                    option_info,
                )
                resolved_values.append(resolved)
                statuses.append(status)
                errors.append(error)

            work[f"{df_col}__resolved"] = resolved_values
            work[f"{df_col}__lookup_status"] = statuses
            work[f"{df_col}__lookup_error"] = errors

        return work
