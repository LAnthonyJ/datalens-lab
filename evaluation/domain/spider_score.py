"""Run the pinned Spider author's multi-database evaluator with read-only connections."""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import zipfile

from sql_cases import statement

REVISION = "e97acc546ecbee8fa27fa8dbf025ef61493a876c"


def readonly_cursor(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.text_factory = lambda data: data.decode(errors="ignore")
    connection.execute("PRAGMA query_only=ON")
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 8_000_000)
    deadline = time.monotonic() + 60
    connection.set_progress_handler(lambda: time.monotonic() >= deadline, 10000)
    return connection.cursor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("archive", "evaluator", "fixtures", "answers", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.evaluator), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError(f"Unexpected evaluator {revision}")
    sys.path.insert(0, str(args.evaluator.resolve()))
    import exec_eval
    exec_eval.get_cursor_from_path = readonly_cursor
    with zipfile.ZipFile(args.archive) as z:
        questions = json.loads(z.read("spider_data/dev.json"))
    assert len(questions) == 1034
    args.out.mkdir(exist_ok=True, parents=True)
    for index, q in enumerate(questions):
        key = f"spider-{index:04}"
        source = args.answers / (key + ".json")
        target = args.out / (key + ".json")
        if target.is_file() or not source.is_file():
            continue
        answer = json.loads(source.read_text(encoding="utf8"))
        sql = statement(answer["answer"])
        folder = args.fixtures / q["db_id"]
        if not (folder / (q["db_id"] + ".sqlite")).is_file() or len(list(folder.glob("*.sqlite"))) < 2:
            raise ValueError(f"Missing databases for {q['db_id']}")
        valid = bool(re.match(r"^(?:SELECT|WITH)\b", sql, re.I))
        # Feed a safe, invalid SELECT to the scorer when there is no extractable query.
        passed = valid and bool(exec_eval.eval_exec_match(
            str(folder / (q["db_id"] + ".sqlite")), sql, q["query"], False, False, False))
        item = dict(id=key, database=q["db_id"], passed=passed, extracted=valid)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(item), encoding="utf8")
        tmp.replace(target)


if __name__ == "__main__":
    main()
