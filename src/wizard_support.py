from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .codebeamer_client import CodebeamerClient
from .excel_reader import ExcelReader
from .hierarchy_processor import HierarchyProcessor
from .mapping_service import MappingService
from .models import DomainModel
from .models import FieldValueType
from .models import OptionCheckStatus
from .models import OptionMapKind
from .models import PayloadStatus
from .models import ReferenceType
from .models import ResolvedFieldKind
from .models import TrackerItemQueryMatchStrategy
from .models import TrackerItemResolutionMode
from .models import GroupReference
from .models import RoleReference
from .models import TableFieldValue
from .models import TrackerItemBase
from .models import UploadStatus
from .models import UserInfo
from .models import UserGroupReference
from .models import UserLookupStatus
from .models import WizardState
from .models.field_values import _build_field_value


UserLookupCacheEntry = tuple[dict[str, Any] | None, dict[str, Any] | None, str, str | None]
MemberLookupCacheEntry = tuple[dict[str, Any] | None, dict[str, Any] | None, str, str | None]
TrackerItemLookupCacheEntry = tuple[Any, str | None, str | None]
DEFAULT_VALUE_COLUMN_LABEL = "(기본값)"
DEFAULT_TRACKER_ITEM_ID_REGEX = r"\[(?:[^:\]]+:)?(\d+)[^\]]*\]|^(\d+)(?:\.0)?$"


__all__ = [name for name in globals() if not name.startswith("__")]
