from datetime import datetime, timezone


class OperationLogRepository:
    def __init__(self, db):
        self.db = db

    def create(self, actor_id, action, target_type, target_id, detail=None, trace_id=None):
        doc = {
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "detail": detail or {},
            "trace_id": trace_id,
            "created_at": datetime.now(timezone.utc),
        }
        self.db.operation_logs.insert_one(doc)
        return doc


class BusinessLogRepository:
    def __init__(self, db):
        self.db = db

    def create(
        self,
        action,
        target_type,
        target_id,
        operator_id=None,
        operator_role="system",
        from_status=None,
        to_status=None,
        reason="",
        extra=None,
        trace_id=None,
    ):
        doc = {
            "trace_id": trace_id,
            "operator_id": operator_id,
            "operator_role": operator_role,
            "target_type": target_type,
            "target_id": target_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
            "extra": extra or {},
            "created_at": datetime.now(timezone.utc),
        }
        self.db.business_logs.insert_one(doc)
        return doc
