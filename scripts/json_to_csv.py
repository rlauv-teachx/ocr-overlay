import csv
import json
import sys

def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    if not data:
        csv.writer(sys.stdout).writerow([])
        return
    headers = list(data[0].keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)

if __name__ == "__main__":
    main()
