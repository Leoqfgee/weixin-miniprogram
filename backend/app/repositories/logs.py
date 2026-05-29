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
