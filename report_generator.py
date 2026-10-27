
import csv
import io
import json


def create_csv_report(records):
    output = io.StringIO()

    if not records:
        output.write("No records found\n")
        return output.getvalue()

    fieldnames = list(records[0].keys())
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()

    for record in records:
        row = {
            key: json.dumps(value, ensure_ascii=False)
            if isinstance(value, (list, dict))
            else value
            for key, value in record.items()
        }
        writer.writerow(row)

    return output.getvalue()


def create_json_report(records):
    return json.dumps(
        records, indent=4, ensure_ascii=False
    )