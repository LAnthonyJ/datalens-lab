"""Create the small pilot inputs without exposing targets to inference."""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pilot_business():
    rows = []
    with (HERE / "pilot-business.tsv").open(encoding="utf-8-sig") as handle:
        for i, row in enumerate(csv.DictReader(handle, delimiter="\t"), 1):
            for arm in ("missing", "complete"):
                prompt = row["missing_question"]
                if arm == "complete":
                    prompt += " " + row["added_evidence"]
                rows.append({"id": f"pilot-a-{i:02}-{arm}", "prompt": prompt})
    assert len(rows) == 80
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = pilot_business()
    with args.output.open("x", encoding="utf8") as f:
        for row in rows:
            print(json.dumps(row), file=f)
