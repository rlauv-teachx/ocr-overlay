import sys
from scripts.ocr_processor import process_file
import json

def cli_entry():
    if len(sys.argv) < 2:
        print("Usage: ocr-process <absolute_file_path> [--mode video|pdf] [--visualize] [--bg-color COLOR] [--color-threshold N]", file=sys.stderr)
        sys.exit(1)
    file_path = sys.argv[1]
    mode = None
    visualize = False
    bg_color = None
    color_threshold = 30
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--visualize':
            visualize = True
        elif arg.startswith('--mode='):
            mode = arg.split('=')[1]
        elif arg == '--bg-color':
            bg_color = sys.argv[i+1]
            i += 1
        elif arg == '--color-threshold':
            color_threshold = int(sys.argv[i+1])
            i += 1
        i += 1
    try:
        data = process_file(file_path, mode, visualize, bg_color, color_threshold)
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli_entry()
