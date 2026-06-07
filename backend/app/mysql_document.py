import copy
import json
from datetime import datetime

import pymysql
from bson import ObjectId
from pymongo.errors import DuplicateKeyError


ASCENDING = 1
DESCENDING = -1


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, matched_count=0, modified_count=0, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


def _encode(value):
    if isinstance(value, ObjectId):
        return {"$oid": str(value)}
    if isinstance(value, datetime):
        return {"$date": value.isoformat()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        if set(value.keys()) == {"$oid"}:
            return ObjectId(value["$oid"])
        if set(value.keys()) == {"$date"}:
            text = value["$date"]
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        return {key: _decode(item) for key, item in value.items()}
    return value


def _json_dumps(doc):
    return json.dumps(_encode(doc), ensure_ascii=False, separators=(",", ":"))


def _json_loads(text):
    return _decode(json.loads(text))


def _get_path(doc, path):
    value = doc
    for part in str(path).split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _set_path(doc, path, value):
    target = doc
    parts = str(path).split(".")
    for part in parts[:-1]:
        current = target.get(part)
        if not isinstance(current, dict):
            current = {}
            target[part] = current
        target = current
    target[parts[-1]] = value


def _unset_path(doc, path):
    target = doc
    parts = str(path).split(".")
    for part in parts[:-1]:
        target = target.get(part)
        if not isinstance(target, dict):
            return
    target.pop(parts[-1], None)


def _match_field(value, condition):
    if isinstance(condition, dict):
        for op, expected in condition.items():
            if op == "$in":
                if value not in expected:
                    return False
            elif op == "$nin":
                if value in expected:
                    return False
            elif op == "$ne":
                if value == expected:
                    return False
            elif op == "$exists":
                if bool(expected) != (value is not None):
                    return False
            elif op == "$gt":
                if value is None or value <= expected:
                    return False
            elif op == "$gte":
                if value is None or value < expected:
                    return False
            elif op == "$lt":
                if value is None or value >= expected:
                    return False
            elif op == "$lte":
                if value is None or value > expected:
                    return False
            elif op == "$regex":
                import re

                flags = re.I if condition.get("$options") == "i" else 0
                if not re.search(expected, str(value or ""), flags):
                    return False
            elif op == "$options":
                continue
            else:
                if value != condition:
                    return False
        return True
    if isinstance(value, list):
        return condition in value
    return value == condition


def _matches(doc, query=None):
    query = query or {}
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(doc, item) for item in condition):
                return False
        elif key == "$and":
            if not all(_matches(doc, item) for item in condition):
                return False
        elif not _match_field(_get_path(doc, key), condition):
            return False
    return True


def _sort_docs(docs, spec):
    if not spec:
        return docs
    if isinstance(spec, tuple):
        spec = [spec]
    if isinstance(spec, str):
        spec = [(spec, ASCENDING)]
    if isinstance(spec, dict):
        spec = list(spec.items())
    for field, direction in reversed(list(spec)):
        docs.sort(
            key=lambda item: (_get_path(item, field) is None, _get_path(item, field)),
            reverse=int(direction) < 0,
        )
    return docs


class MySQLCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key_or_list, direction=None):
        _sort_docs(self.docs, key_or_list if direction is None else [(key_or_list, direction)])
        return self

    def skip(self, count):
        self.docs = self.docs[int(count) :]
        return self

    def limit(self, count):
        self.docs = self.docs[: int(count)]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self.docs))


class MySQLDocumentCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def _all(self):
        self.db.ensure_connection()
        with self.db.connection.cursor() as cursor:
            cursor.execute("SELECT doc FROM cloud_documents WHERE collection_name=%s", (self.name,))
            return [_json_loads(row["doc"]) for row in cursor.fetchall()]

    def _save(self, doc):
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", ObjectId())
        document_id = str(doc["_id"])
        self.db.ensure_connection()
        with self.db.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cloud_documents (collection_name, document_id, doc)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE doc=VALUES(doc), updated_at=CURRENT_TIMESTAMP
                """,
                (self.name, document_id, _json_dumps(doc)),
            )
        self.db.connection.commit()
        return doc["_id"]

    def _delete_id(self, document_id):
        self.db.ensure_connection()
        with self.db.connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cloud_documents WHERE collection_name=%s AND document_id=%s",
                (self.name, str(document_id)),
            )
            deleted = cursor.rowcount
        self.db.connection.commit()
        return deleted

    def insert_one(self, doc):
        self._check_unique(doc)
        return InsertOneResult(self._save(doc))

    def insert_many(self, docs):
        return InsertManyResult([self._save(doc) for doc in docs])

    def find(self, query=None, *args, **kwargs):
        return MySQLCursor([doc for doc in self._all() if _matches(doc, query)])

    def find_one(self, query=None, *args, **kwargs):
        docs = [doc for doc in self._all() if _matches(doc, query)]
        _sort_docs(docs, kwargs.get("sort"))
        return copy.deepcopy(docs[0]) if docs else None

    def count_documents(self, query=None):
        return sum(1 for doc in self._all() if _matches(doc, query))

    def update_one(self, query, update, upsert=False, *args, **kwargs):
        upsert = upsert or kwargs.get("upsert", False)
        doc = self.find_one(query)
        if doc:
            self._apply_update(doc, update, inserting=False)
            self._save(doc)
            return UpdateResult(matched_count=1, modified_count=1)
        if not upsert:
            return UpdateResult()
        doc = {}
        for key, value in (query or {}).items():
            if not key.startswith("$") and not isinstance(value, dict):
                _set_path(doc, key, value)
        self._apply_update(doc, update, inserting=True)
        return UpdateResult(upserted_id=self._save(doc))

    def update_many(self, query, update, *args, **kwargs):
        matched = 0
        for doc in [item for item in self._all() if _matches(item, query)]:
            matched += 1
            self._apply_update(doc, update, inserting=False)
            self._save(doc)
        return UpdateResult(matched_count=matched, modified_count=matched)

    def delete_one(self, query):
        doc = self.find_one(query)
        return DeleteResult(self._delete_id(doc["_id"]) if doc else 0)

    def delete_many(self, query):
        deleted = 0
        for doc in [item for item in self._all() if _matches(item, query)]:
            deleted += self._delete_id(doc["_id"])
        return DeleteResult(deleted)

    def distinct(self, field, query=None):
        values = []
        seen = set()
        for doc in self.find(query):
            current = _get_path(doc, field)
            candidates = current if isinstance(current, list) else [current]
            for item in candidates:
                marker = str(item)
                if item is not None and marker not in seen:
                    seen.add(marker)
                    values.append(item)
        return values

    def aggregate(self, pipeline):
        docs = self._all()
        for stage in pipeline:
            if "$match" in stage:
                docs = [doc for doc in docs if _matches(doc, stage["$match"])]
            elif "$sort" in stage:
                _sort_docs(docs, stage["$sort"])
            elif "$limit" in stage:
                docs = docs[: int(stage["$limit"])]
            elif "$group" in stage:
                docs = self._group(docs, stage["$group"])
        return MySQLCursor(docs)

    def create_index(self, *args, **kwargs):
        return kwargs.get("name") or "noop_index"

    def index_information(self):
        return {}

    def drop_index(self, name):
        return None

    def _check_unique(self, doc):
        if self.name == "users":
            openid = doc.get("openid")
            if openid and self.find_one({"openid": openid}):
                raise DuplicateKeyError("duplicate users.openid")
            phone = doc.get("phone")
            if phone and self.find_one({"phone": phone}):
                raise DuplicateKeyError("duplicate users.phone")
        if self.name == "user_profiles":
            user_id = doc.get("user_id")
            if user_id and self.find_one({"user_id": user_id}):
                raise DuplicateKeyError("duplicate user_profiles.user_id")

    def _apply_update(self, doc, update, inserting=False):
        if not any(str(key).startswith("$") for key in update):
            doc.clear()
            doc.update(copy.deepcopy(update))
            return
        for key, value in update.get("$set", {}).items():
            _set_path(doc, key, value)
        if inserting:
            for key, value in update.get("$setOnInsert", {}).items():
                _set_path(doc, key, value)
        for key, value in update.get("$inc", {}).items():
            _set_path(doc, key, (_get_path(doc, key) or 0) + value)
        for key in update.get("$unset", {}).keys():
            _unset_path(doc, key)

    def _group(self, docs, group_spec):
        grouped = {}
        id_spec = group_spec.get("_id")
        for doc in docs:
            group_id = self._eval_group_id(doc, id_spec)
            key = str(group_id)
            if key not in grouped:
                grouped[key] = {"_id": group_id}
                for output, expr in group_spec.items():
                    if output == "_id":
                        continue
                    grouped[key][output] = copy.deepcopy(doc) if "$first" in expr else 0
            for output, expr in group_spec.items():
                if output == "_id" or "$first" in expr:
                    continue
                if "$sum" in expr:
                    grouped[key][output] += self._eval_sum(doc, expr["$sum"])
        return list(grouped.values())

    def _eval_group_id(self, doc, spec):
        if isinstance(spec, str) and spec.startswith("$"):
            return _get_path(doc, spec[1:])
        if isinstance(spec, dict) and "$dateToString" in spec:
            date_value = _get_path(doc, spec["$dateToString"]["date"].lstrip("$"))
            if isinstance(date_value, datetime):
                return date_value.strftime(spec["$dateToString"].get("format", "%Y-%m-%d"))
        return spec

    def _eval_sum(self, doc, expr):
        if isinstance(expr, (int, float)):
            return expr
        if isinstance(expr, str) and expr.startswith("$"):
            return _get_path(doc, expr[1:]) or 0
        if isinstance(expr, dict) and "$cond" in expr:
            condition, yes, no = expr["$cond"]
            return yes if self._eval_condition(doc, condition) else no
        return 0

    def _eval_condition(self, doc, expr):
        if "$and" in expr:
            return all(self._eval_condition(doc, item) for item in expr["$and"])
        if "$eq" in expr:
            left, right = expr["$eq"]
            if isinstance(left, str) and left.startswith("$"):
                left = _get_path(doc, left[1:])
            if isinstance(right, str) and right.startswith("$"):
                right = _get_path(doc, right[1:])
            return left == right
        return False


class MySQLDocumentDB:
    def __init__(self, config):
        self.config = dict(config)
        self.connection = None
        self.ensure_connection()
        self._ensure_table()

    def ensure_connection(self):
        if self.connection:
            try:
                self.connection.ping(reconnect=True)
                return
            except Exception:
                try:
                    self.connection.close()
                except Exception:
                    pass
        self.connection = pymysql.connect(
            host=self.config["MYSQL_HOST"],
            port=int(self.config["MYSQL_PORT"]),
            user=self.config["MYSQL_USERNAME"],
            password=self.config["MYSQL_PASSWORD"],
            database=self.config["MYSQL_DATABASE"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def _ensure_table(self):
        self.ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cloud_documents (
                    collection_name VARCHAR(64) NOT NULL,
                    document_id CHAR(24) NOT NULL,
                    doc LONGTEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection_name, document_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        self.connection.commit()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return MySQLDocumentCollection(self, name)

    def __getitem__(self, name):
        return MySQLDocumentCollection(self, name)

    def command(self, name):
        if name == "ping":
            self.ensure_connection()
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"ok": 1}

    def list_collection_names(self):
        self.ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT collection_name FROM cloud_documents")
            return [row["collection_name"] for row in cursor.fetchall()]

    def create_collection(self, name):
        return MySQLDocumentCollection(self, name)

    def close(self):
        if self.connection:
            self.connection.close()
