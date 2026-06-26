from __future__ import annotations

import argparse
from pathlib import Path

from src.codebeamer_client import CodebeamerClient
from src.config import load_config
from src.logger import setup_logger
from src.mapping_service import MappingService
from src.tracker_contract import build_tracker_contract_bundle
from src.tracker_contract import save_tracker_contract_bundle
from src.tracker_contract import scaffold_start_kit_templates


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="대상 tracker의 schema 계약과 시작 패키지 템플릿을 export 합니다.",
    )
    parser.add_argument("--project-id", type=int, help="대상 project id")
    parser.add_argument("--tracker-id", type=int, help="대상 tracker id")
    parser.add_argument("--output-dir", help="생성물을 저장할 디렉터리")
    return parser.parse_args()


def _default_output_dir(base_output_dir: str, project_id: int, tracker_id: int) -> Path:
    return Path(base_output_dir) / "tracker_contracts" / f"project_{project_id}_tracker_{tracker_id}"


def main() -> None:
    args = _parse_args()
    cfg = load_config()
    logger = setup_logger("tracker-contract-export", level=cfg.log_level)

    project_id = args.project_id if args.project_id is not None else cfg.default_project_id
    tracker_id = args.tracker_id if args.tracker_id is not None else cfg.default_tracker_id

    if project_id is None:
        raise ValueError("project_id is required. --project-id 또는 DEFAULT_PROJECT_ID 를 설정하세요.")
    if tracker_id is None:
        raise ValueError("tracker_id is required. --tracker-id 또는 DEFAULT_TRACKER_ID 를 설정하세요.")

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else _default_output_dir(cfg.output_dir, int(project_id), int(tracker_id))
    )

    client = CodebeamerClient(
        cfg.base_url,
        cfg.username,
        cfg.password,
        logger,
        rate_limit_retry_delay_seconds=cfg.rate_limit_retry_delay_seconds,
        rate_limit_max_retries=cfg.rate_limit_max_retries,
    )
    mapper = MappingService(logger=logger)

    bundle = build_tracker_contract_bundle(
        client=client,
        mapper=mapper,
        project_id=int(project_id),
        tracker_id=int(tracker_id),
    )
    written_files = save_tracker_contract_bundle(bundle, output_dir)
    copied_templates = scaffold_start_kit_templates(
        template_dir=Path(__file__).resolve().parent / "templates" / "codebeamer-upload-starter",
        output_dir=output_dir,
    )

    print("[tracker contract export 완료]")
    print(f"- project_id: {project_id}")
    print(f"- tracker_id: {tracker_id}")
    print(f"- output_dir: {output_dir}")
    for key, path in written_files.items():
        print(f"- {key}: {path}")
    if copied_templates:
        print(f"- copied_templates: {len(copied_templates)}")
    else:
        print("- copied_templates: 0 (이미 존재하는 파일은 덮어쓰지 않음)")


if __name__ == "__main__":
    main()
