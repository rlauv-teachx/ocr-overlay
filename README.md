# Zed OCR Extractor

OCR-based number extractor from videos (scrolling docs) and PDFs.

## Structure
- `data/samples/`: Sample files (PDF/video).
- `scripts/`: Core processing modules.
- `cli/`: CLI entrypoint.
- `server/`: Flask API server.
- `extracted/`: Generated visualized images (if enabled).

## Setup
```bash
pip install -e .
```

## Usage

### CLI
```bash
ocr-process /absolute/path/to/data/samples/sample.pdf --mode pdf --visualize --bg-color blue --color-threshold 40
# Filters numbers over blue-ish background (hue dist <=40); outputs JSON; pipe to file: > output.json
```

### JSON to CSV
```bash
python -m scripts.json_to_csv output.json > output.csv
# Or pipe: ocr-process ... | python -m scripts.json_to_csv > output.csv
```

### API Server
```bash
start-server
# Runs on http://0.0.0.0:5000
```

Send request (e.g. with curl; supports bg filtering):
```bash
curl -X POST http://localhost:5000/process \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/absolute/path/to/data/samples/sample.pdf", "mode": "pdf", "visualize": true, "bg_color": "blue", "color_threshold": 40}'
# Returns JSON (only numbers over matching bg hue); pipe/save as needed.
```

For video use MP4 path and mode=video. CSV/JSON formats are lists of dicts (interchangeable).
