"""
Generate a reproducible synthetic messy CSV dataset (2,500 rows) with no personal data,
and compute expected reconciliation fixture values.
"""
import os
import sys
import json
import random

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ingestion import parse_and_profile_csv

def generate_messy_csv(num_rows: int = 2500, seed: int = 42) -> str:
    random.seed(seed)

    departments = ["Engineering", "Marketing", "Sales", "Support", "Finance"]
    start_year = 2024

    lines = ["transaction_id,transaction_date,department,amount,notes"]

    for i in range(1, num_rows + 1):
        txn_id = f"TXN-{10000 + i}"

        # Inject anomalies at controlled deterministic rates
        # 1. Ragged row (approx 10 occurrences)
        if i in (100, 300, 750, 1200, 1800):
            # Only 3 columns instead of 5
            lines.append(f"{txn_id},2024-03-01,Engineering")
            continue
        elif i in (500, 1500, 2200):
            # 6 columns instead of 5
            lines.append(f"{txn_id},2024-03-01,Engineering,150.00,Extra Column,Extra Value")
            continue

        # 2. Date anomalies
        if i % 250 == 0:
            txn_date = "invalid-date"
        elif i % 333 == 0:
            txn_date = "2024-02-30"  # Invalid calendar day
        elif i % 180 == 0:
            txn_date = ""            # Blank date
        else:
            month = (i % 12) + 1
            day = (i % 28) + 1
            txn_date = f"{start_year}-{month:02d}-{day:02d}"

        # 3. Department anomalies
        if i % 120 == 0:
            dept = ""  # Blank category
        else:
            dept = departments[i % len(departments)]

        # 4. Amount anomalies
        if i % 150 == 0:
            amount_str = "N/A"
        elif i % 275 == 0:
            amount_str = "pending"
        elif i % 210 == 0:
            amount_str = ""  # Blank numeric
        elif i % 40 == 0:
            # Negative amount (refund / discount)
            amount_val = -round((i * 1.75) % 500 + 10.0, 2)
            amount_str = f"{amount_val:.2f}"
        else:
            amount_val = round((i * 3.45) % 1500 + 25.0, 2)
            amount_str = f"{amount_val:.2f}"

        # 5. Notes with quoted commas and occasional multiline
        if i % 70 == 0:
            notes = f'"Quarterly review, milestone {i}"'
        elif i == 42:
            notes = '"First line of note\nSecond line after newline"'
        else:
            notes = f"Standard transaction entry {i}"

        lines.append(f"{txn_id},{txn_date},{dept},{amount_str},{notes}")

    return "\n".join(lines)

def main():
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
    os.makedirs(fixtures_dir, exist_ok=True)

    csv_path = os.path.join(fixtures_dir, "messy_sample.csv")
    json_path = os.path.join(fixtures_dir, "expected_results.json")

    print("Generating synthetic messy CSV (2,500 rows)...")
    csv_text = generate_messy_csv(num_rows=2500, seed=42)

    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(csv_text)
    print(f"Saved CSV to: {csv_path}")

    # Profile the generated CSV using our ingestion engine to record deterministic ground truth
    headers, profile, processed_rows = parse_and_profile_csv(csv_text)

    expected_results = {
        "generator_seed": 42,
        "total_rows": profile["total_rows"],
        "accepted_rows": profile["accepted_rows"],
        "warning_rows": profile["warning_rows"],
        "rejected_rows": profile["rejected_rows"],
        "column_types": {c["name"]: c["inferred_type"] for c in profile["columns"]},
        "ragged_rows_count": sum(1 for r in processed_rows if not r["structurally_valid"]),
        "columns": profile["columns"]
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(expected_results, f, indent=2)
    print(f"Saved expected results fixture to: {json_path}")
    print(f"Summary:")
    print(f"  Total rows: {profile['total_rows']}")
    print(f"  Accepted:   {profile['accepted_rows']}")
    print(f"  Warning:    {profile['warning_rows']}")
    print(f"  Rejected:   {profile['rejected_rows']}")
    print(f"  Reconciled? {profile['total_rows'] == profile['accepted_rows'] + profile['warning_rows'] + profile['rejected_rows']}")

if __name__ == "__main__":
    main()
