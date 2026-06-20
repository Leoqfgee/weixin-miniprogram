import argparse
import sys
from pathlib import Path

from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402
from app.domain.campus import LEGACY_CAMPUS_MAP  # noqa: E402
from app.repositories.products import utc_now  # noqa: E402


TARGET_COLLECTIONS = ("products", "user_profiles")


def normalize_legacy_campus(apply=False):
    client = MongoClient(Config.MONGO_URI)
    db = client[Config.MONGO_DB_NAME]
    now = utc_now()
    summary = {}
    for collection_name in TARGET_COLLECTIONS:
        collection = db[collection_name]
        collection_summary = {}
        for legacy, replacement in LEGACY_CAMPUS_MAP.items():
            count = collection.count_documents({"campus": legacy})
            collection_summary[legacy] = {"replacement": replacement, "matched": count, "modified": 0}
            if apply and count:
                result = collection.update_many(
                    {"campus": legacy},
                    {"$set": {"campus": replacement, "updated_at": now}},
                )
                collection_summary[legacy]["modified"] = result.modified_count
        summary[collection_name] = collection_summary
    client.close()
    return summary


def main():
    parser = argparse.ArgumentParser(description="Normalize legacy campus values to the allowed campus options.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this flag the script only reports counts.")
    args = parser.parse_args()
    summary = normalize_legacy_campus(apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode} database={Config.MONGO_DB_NAME}")
    for collection_name, collection_summary in summary.items():
        for legacy, result in collection_summary.items():
            print(
                f"{collection_name}: {legacy} -> {result['replacement']}, "
                f"matched={result['matched']}, modified={result['modified']}"
            )


if __name__ == "__main__":
    main()
