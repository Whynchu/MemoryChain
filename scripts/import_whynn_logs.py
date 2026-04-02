"""
import_whynn_logs.py — Bulk import WHYNN daily log file into MemoryChain.

Usage:
    python scripts/import_whynn_logs.py [--path PATH] [--user-id USER_ID] [--db-path DB_PATH] [--dry-run]

Defaults:
    --path     users/Sam/logs/MUAY THAI/III_DAILY_LOGS.txt
    --user-id  sam
    --db-path  memorychain.db
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from memorychain_api.schemas import (
    ActivityCreate,
    DailyCheckinCreate,
    JournalEntryCreate,
    MetricObservationCreate,
    SourceDocumentCreate,
)
from memorychain_api.services.whynn_extractor import ExtractedWhynnEntry, extract_entry
from memorychain_api.services.whynn_parser import ParsedWhynnEntry, parse_log_file
from memorychain_api.storage.db import connect, initialize
from memorychain_api.storage.repository import Repository


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------

def _activity_type_from_session(session_type: str | None) -> str:
    """Map WHYNN session type string to ActivityType enum value."""
    if not session_type:
        return "workout"
    st = session_type.lower()
    if any(k in st for k in ("run", "sprint", "tempo")):
        return "workout"
    if any(k in st for k in ("mobility", "recovery", "stretch")):
        return "mobility"
    if any(k in st for k in ("breath", "breathwork", "gate", "feldmann")):
        return "breathwork"
    if any(k in st for k in ("strength", "squat", "stair", "vest")):
        return "workout"
    return "workout"


def import_entry(
    repo: Repository,
    parsed: ParsedWhynnEntry,
    extracted: ExtractedWhynnEntry,
    user_id: str,
    dry_run: bool = False,
) -> dict:
    """
    Import one day entry. Returns a stats dict describing what was created.
    """
    if not parsed.date:
        return {"skipped": True, "reason": f"Could not parse date: {parsed.raw_date!r}"}

    effective_at = datetime.combine(parsed.date, datetime.min.time()).replace(tzinfo=timezone.utc)
    stats = {
        "date": str(parsed.date),
        "source_document": False,
        "checkin": False,
        "activities": 0,
        "metrics": 0,
        "journal": False,
        "skipped": False,
    }

    if dry_run:
        # Just report what would be created
        stats["source_document"] = True
        if _has_any_checkin_data(extracted):
            stats["checkin"] = True
        if extracted.training.session_type or extracted.training.total_strikes:
            stats["activities"] += 1
        stats["metrics"] = _count_metrics(extracted)
        if extracted.system_notes:
            stats["journal"] = True
        return stats

    # 1. Source document
    source = repo.create_source_document(
        SourceDocumentCreate(
            user_id=user_id,
            source_type="import",
            effective_at=effective_at,
            title=f"WHYNN Daily Log — {parsed.raw_date}",
            raw_text=parsed.raw_text,
            provenance="import",
        )
    )
    stats["source_document"] = True

    # 2. Daily check-in
    sm = extracted.system
    if _has_any_checkin_data(extracted):
        repo.create_checkin(
            DailyCheckinCreate(
                user_id=user_id,
                source_document_id=source.id,
                date=parsed.date,
                effective_at=effective_at,
                sleep_hours=sm.sleep_hours,
                sleep_quality=int(sm.sleep_quality) if sm.sleep_quality is not None else None,
                mood=int(sm.mood) if sm.mood is not None else None,
                energy=int(sm.energy) if sm.energy is not None else None,
                body_weight=sm.body_weight_lbs,
                body_weight_unit="lbs" if sm.body_weight_lbs is not None else None,
                immediate_thoughts=sm.immediate_thoughts,
                provenance="import",
            )
        )
        stats["checkin"] = True

    # 3. Training activity
    tr = extracted.training
    if tr.session_type or tr.total_strikes or tr.duration_minutes:
        activity_title = tr.session_type or "Training Session"
        metadata: dict = {}
        if tr.total_strikes:
            metadata["total_strikes"] = tr.total_strikes
        if tr.duration_minutes:
            metadata["duration_minutes"] = round(tr.duration_minutes, 1)
        if tr.distance_km:
            metadata["distance_km"] = tr.distance_km
        if tr.avg_hr_bpm:
            metadata["avg_hr_bpm"] = tr.avg_hr_bpm
        if tr.max_hr_bpm:
            metadata["max_hr_bpm"] = tr.max_hr_bpm

        repo.create_activity(
            ActivityCreate(
                user_id=user_id,
                source_document_id=source.id,
                effective_at=effective_at,
                activity_type=_activity_type_from_session(tr.session_type),
                title=activity_title,
                notes=tr.notes,
                metadata=metadata,
                provenance="import",
            )
        )
        stats["activities"] += 1

    # 4. Metric observations
    metrics_created = _create_metrics(repo, user_id, source.id, effective_at, extracted)
    stats["metrics"] = metrics_created

    # 5. Journal entry from system notes (freeform reflection)
    if extracted.system_notes:
        repo.create_journal_entry(
            JournalEntryCreate(
                user_id=user_id,
                source_document_id=source.id,
                effective_at=effective_at,
                entry_type="journal",
                title=f"WHYNN Notes — {parsed.raw_date}",
                text=extracted.system_notes,
                tags=["whynn_import", "system_notes"],
                provenance="import",
            )
        )
        stats["journal"] = True

    return stats


def _has_any_checkin_data(extracted: ExtractedWhynnEntry) -> bool:
    sm = extracted.system
    return any(v is not None for v in [
        sm.sleep_hours, sm.sleep_quality, sm.mood, sm.energy,
        sm.body_weight_lbs, sm.immediate_thoughts,
    ])


def _count_metrics(extracted: ExtractedWhynnEntry) -> int:
    count = 0
    if extracted.breathwork.co2_hold_seconds is not None:
        count += 1
    if extracted.system.body_weight_lbs is not None:
        count += 1
    if extracted.nutrition.hydration_oz is not None:
        count += 1
    if extracted.training.total_strikes is not None:
        count += 1
    if extracted.training.avg_hr_bpm is not None:
        count += 1
    if extracted.training.max_hr_bpm is not None:
        count += 1
    return count


def _create_metrics(repo: Repository, user_id: str, source_id: str, effective_at: datetime, extracted: ExtractedWhynnEntry) -> int:
    created = 0
    metrics_to_create = []

    if extracted.breathwork.co2_hold_seconds is not None:
        metrics_to_create.append(("co2_hold", str(extracted.breathwork.co2_hold_seconds), "seconds"))

    if extracted.system.body_weight_lbs is not None:
        metrics_to_create.append(("body_weight", str(extracted.system.body_weight_lbs), "lbs"))

    if extracted.nutrition.hydration_oz is not None:
        metrics_to_create.append(("hydration", str(extracted.nutrition.hydration_oz), "oz"))

    if extracted.training.total_strikes is not None:
        metrics_to_create.append(("total_strikes", str(extracted.training.total_strikes), "strikes"))

    if extracted.training.avg_hr_bpm is not None:
        metrics_to_create.append(("avg_heart_rate", str(extracted.training.avg_hr_bpm), "bpm"))

    if extracted.training.max_hr_bpm is not None:
        metrics_to_create.append(("max_heart_rate", str(extracted.training.max_hr_bpm), "bpm"))

    for metric_type, value, unit in metrics_to_create:
        repo.create_metric_observation(
            MetricObservationCreate(
                user_id=user_id,
                source_document_id=source_id,
                effective_at=effective_at,
                metric_type=metric_type,
                value=value,
                unit=unit,
                provenance="import",
            )
        )
        created += 1

    return created


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import WHYNN daily logs into MemoryChain.")
    parser.add_argument(
        "--path",
        default="users/Sam/logs/MUAY THAI/III_DAILY_LOGS.txt",
        help="Path to the log file (relative to repo root or absolute)",
    )
    parser.add_argument("--user-id", default="sam", help="User ID to import as")
    parser.add_argument("--db-path", default="memorychain.db", help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
    args = parser.parse_args()

    log_path = Path(args.path)
    if not log_path.is_absolute():
        # Try relative to repo root (one level up from scripts/)
        repo_root = Path(__file__).parent.parent
        log_path = repo_root / log_path

    if not log_path.exists():
        print(f"ERROR: Log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Parsing {log_path} ...")
    entries = parse_log_file(str(log_path))
    print(f"Found {len(entries)} entries.\n")

    if not args.dry_run:
        conn = connect(args.db_path)
        initialize(conn)
        repo = Repository(conn)
    else:
        repo = None

    # Counters
    total = len(entries)
    skipped = 0
    checkins = 0
    activities = 0
    metrics = 0
    journals = 0

    for parsed in entries:
        extracted = extract_entry(parsed)
        result = import_entry(repo, parsed, extracted, args.user_id, dry_run=args.dry_run)

        if result.get("skipped"):
            skipped += 1
            print(f"  SKIP  {result.get('date', '?')} — {result.get('reason', '')}")
            continue

        date_str = result["date"]
        parts = []
        if result["checkin"]:
            checkins += 1
            parts.append("checkin")
        if result["activities"]:
            activities += result["activities"]
            parts.append(f"{result['activities']} activity")
        if result["metrics"]:
            metrics += result["metrics"]
            parts.append(f"{result['metrics']} metrics")
        if result["journal"]:
            journals += 1
            parts.append("journal")

        status = ", ".join(parts) if parts else "source only"
        print(f"  {'DRY ' if args.dry_run else '    '}{date_str}  ->  {status}")

    print(f"""
{'=' * 60}
Import {'preview' if args.dry_run else 'complete'}:
  Entries processed : {total - skipped}/{total}
  Skipped           : {skipped}
  Checkins created  : {checkins}
  Activities created: {activities}
  Metrics created   : {metrics}
  Journal entries   : {journals}
{'=' * 60}
""")


if __name__ == "__main__":
    main()
