"""Explicit, database-checked cleanup for orphaned private report attachments.

No startup scheduler or public route invokes this service. Operations must
approve the exact isolated target and run it only after checking DB health.
"""

from pymongo import ReadPreference
from pymongo.read_concern import ReadConcern

from app.models.lab_request import LabRequest
from app.models.report import Report
from app.services.clinical_report_storage import ClinicalReportStorage, LabReportStorage


class ReportCleanupReconciler:
    @staticmethod
    async def run(*, min_age_seconds: int = 24 * 60 * 60) -> dict[str, dict[str, int]]:
        async def clinical_is_referenced(key: str) -> bool:
            collection = Report.get_pymongo_collection().with_options(
                read_preference=ReadPreference.PRIMARY,
                read_concern=ReadConcern("majority"),
            )
            return bool(await collection.count_documents({"file_path": key}, limit=1))

        async def laboratory_is_referenced(key: str) -> bool:
            collection = LabRequest.get_pymongo_collection().with_options(
                read_preference=ReadPreference.PRIMARY,
                read_concern=ReadConcern("majority"),
            )
            return bool(
                await collection.count_documents({"report_storage_key": key}, limit=1)
            )

        return {
            "clinical": await ClinicalReportStorage.reconcile_pending_cleanup(
                clinical_is_referenced, min_age_seconds=min_age_seconds
            ),
            "laboratory": await LabReportStorage.reconcile_pending_cleanup(
                laboratory_is_referenced, min_age_seconds=min_age_seconds
            ),
        }
