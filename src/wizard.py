from __future__ import annotations

from .codebeamer_client import CodebeamerClient
from .excel_reader import ExcelReader
from .hierarchy_processor import HierarchyProcessor
from .mapping_service import MappingService
from .models import WizardState
from .wizard_data import WizardDataPreparationMixin
from .wizard_operations import WizardOperationMixin
from .wizard_payload import WizardPayloadMixin
from .wizard_tracker_lookup import WizardTrackerItemLookupMixin
from .wizard_user_lookup import WizardUserLookupMixin


class CodebeamerUploadWizard(
    WizardDataPreparationMixin,
    WizardUserLookupMixin,
    WizardTrackerItemLookupMixin,
    WizardPayloadMixin,
    WizardOperationMixin,
):
    """업로드 전처리, lookup, payload 생성, 실행을 조합하는 최상위 서비스다."""

    def __init__(
        self,
        client: CodebeamerClient,
        processor: HierarchyProcessor | None,
        mapper: MappingService,
        reader: ExcelReader | None = None,
        logger=None,
    ):
        """의존 서비스를 주입받아 업로드 워크플로를 초기화한다."""
        self.client = client
        self.reader = reader
        self.processor = processor
        self.mapper = mapper
        self.logger = logger
        self.state = WizardState()


__all__ = ["CodebeamerUploadWizard"]
