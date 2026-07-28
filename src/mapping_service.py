from __future__ import annotations

from .mapping_option import MappingOptionMixin
from .mapping_reference import MappingReferenceMixin
from .mapping_schema import MappingSchemaMixin


class MappingService(
    MappingReferenceMixin,
    MappingSchemaMixin,
    MappingOptionMixin,
):
    """Schema 해석, reference 파싱, option 검증을 묶는 매핑 서비스다."""

    def __init__(self, logger=None):
        """로그 출력을 선택적으로 받아 매핑 서비스 상태를 초기화한다."""
        self.logger = logger


__all__ = ["MappingService"]
