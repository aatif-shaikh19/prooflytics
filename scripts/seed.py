import sys
import os
import json

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import init_db, SessionLocal, User, Dataset, DatasetRow, Report, ReportBlock
from app.services.auth import hash_password

def seed_database() -> None:
    print("Initializing database tables...")
    init_db()
    db = SessionLocal()

    try:
        # Define seed users
        seed_users_data = [
            (
                "user_a@example.com",
                "Password123!",
                "User A Sample Dataset",
                "User A Executive Summary",
                [
                    {"id": 1, "amount": 120.50, "category": "Subscriptions", "date": "2024-01-15"},
                    {"id": 2, "amount": 450.00, "category": "Hardware", "date": "2024-01-18"},
                    {"id": 3, "amount": 89.99, "category": "Subscriptions", "date": "2024-02-01"},
                    {"id": 4, "amount": 1200.00, "category": "Services", "date": "2024-02-10"},
                    {"id": 5, "amount": 310.25, "category": "Hardware", "date": "2024-02-14"},
                    {"id": 6, "amount": 95.00, "category": "Subscriptions", "date": "2024-03-01"},
                    {"id": 7, "amount": 620.00, "category": "Services", "date": "2024-03-05"},
                    {"id": 8, "amount": 215.50, "category": "Hardware", "date": "2024-03-12"},
                ]
            ),
            (
                "user_b@example.com",
                "Password123!",
                "User B Private Metrics",
                "User B Internal Audit",
                [
                    {"id": 101, "amount": 340.00, "category": "Research", "date": "2024-01-20"},
                    {"id": 102, "amount": 1150.75, "category": "Compute", "date": "2024-02-05"},
                    {"id": 103, "amount": 45.00, "category": "Storage", "date": "2024-02-18"},
                    {"id": 104, "amount": 890.00, "category": "Compute", "date": "2024-03-02"},
                    {"id": 105, "amount": 210.50, "category": "Research", "date": "2024-03-15"},
                ]
            ),
        ]

        schema_dict = {
            "columns": [
                {"name": "id", "type": "number", "blank_count": 0, "invalid_count": 0},
                {"name": "amount", "type": "number", "blank_count": 0, "invalid_count": 0},
                {"name": "category", "type": "category", "blank_count": 0, "invalid_count": 0},
                {"name": "date", "type": "date", "blank_count": 0, "invalid_count": 0},
            ]
        }

        for email, password, dataset_name, report_title, sample_rows in seed_users_data:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                print(f"Creating user: {email}")
                user = User(
                    email=email,
                    password_hash=hash_password(password)
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                print(f"User already exists: {email}")

            profile_dict = {
                "total_rows": len(sample_rows),
                "accepted_rows": len(sample_rows),
                "rejected_rows": 0,
                "columns": [
                    {"name": "id", "type": "number", "blank_count": 0, "invalid_count": 0},
                    {"name": "amount", "type": "number", "blank_count": 0, "invalid_count": 0},
                    {"name": "category", "type": "category", "blank_count": 0, "invalid_count": 0},
                    {"name": "date", "type": "date", "blank_count": 0, "invalid_count": 0},
                ]
            }

            # Check or update sample dataset
            dataset = db.query(Dataset).filter(Dataset.owner_id == user.id, Dataset.name == dataset_name).first()
            if not dataset:
                print(f"Creating sample dataset for {email}: {dataset_name}")
                dataset = Dataset(
                    owner_id=user.id,
                    name=dataset_name,
                    status="ready",
                    original_filename="seed_sample.csv",
                    row_count=len(sample_rows),
                    schema_json=json.dumps(schema_dict),
                    profile_json=json.dumps(profile_dict)
                )
                db.add(dataset)
                db.commit()
                db.refresh(dataset)
            else:
                print(f"Updating sample dataset schema for {email}: {dataset_name}")
                dataset.schema_json = json.dumps(schema_dict)
                dataset.profile_json = json.dumps(profile_dict)
                dataset.row_count = len(sample_rows)
                db.commit()

            # Ensure dataset rows exist
            existing_rows_count = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).count()
            if existing_rows_count == 0:
                print(f"Populating {len(sample_rows)} sample rows for {dataset_name}...")
                for idx, row_dict in enumerate(sample_rows, start=1):
                    raw_dict = {k: str(v) for k, v in row_dict.items()}
                    db.add(DatasetRow(
                        dataset_id=dataset.id,
                        source_row_number=idx,
                        raw_json=json.dumps(raw_dict),
                        typed_json=json.dumps(row_dict),
                        issues_json="[]",
                        structurally_valid=True
                    ))
                db.commit()

            # Check for existing sample report
            report = db.query(Report).filter(Report.owner_id == user.id, Report.title == report_title).first()
            if not report:
                print(f"Creating sample report for {email}: {report_title}")
                report = Report(
                    owner_id=user.id,
                    dataset_id=dataset.id,
                    title=report_title,
                    filter_json="{}"
                )
                db.add(report)
                db.commit()
                db.refresh(report)

                # Add sample blocks: KPI metric, Bar chart, Text note
                b1 = ReportBlock(
                    report_id=report.id,
                    kind="metric",
                    position=0,
                    config_json=json.dumps({"title": "Total Revenue", "op": "SUM", "column": "amount"})
                )
                b2 = ReportBlock(
                    report_id=report.id,
                    kind="bar_chart",
                    position=1,
                    config_json=json.dumps({"title": "Spend by Category", "op": "SUM", "column": "amount", "group_by_column": "category"})
                )
                b3 = ReportBlock(
                    report_id=report.id,
                    kind="note",
                    position=2,
                    config_json=json.dumps({"title": "Executive Context", "note_text": "This report summarizes Q1 operational transactions across all active categories."})
                )
                db.add_all([b1, b2, b3])
                db.commit()

        print("\nSeed completed successfully!")
        print("Test Accounts:")
        print("  - User A: user_a@example.com / Password123!")
        print("  - User B: user_b@example.com / Password123!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
