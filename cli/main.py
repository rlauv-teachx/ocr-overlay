import sys
import json

from scripts.ocr_processor import process_file
from scripts.cursor_detector import process_cursor_file


def cli_entry():
    if len(sys.argv) < 2:
        print("Usage: ocr-process <file_path> [--mode video|pdf|image] [--visualize] [--numbers] [--bg-color COLOR] [--color-threshold N] [--cursor] [--cursor-dir PATH] [--cursor-threshold N] [--frame-seconds N] [--verbosity] [--export-cursor-templates] [--all-cursor-detections N] [--track-cursor] [--track-radius N]", file=sys.stderr)
        sys.exit(1)
    file_path = sys.argv[1]
    mode = None
    visualize = False
    numbers_mode = False
    bg_color = None
    color_threshold = 30
    cursor_mode = False
    cursor_dir = 'data/cursors'
    cursor_threshold = 0.8
    frame_seconds = None
    verbose = False
    export_cursor_templates = False
    all_cursor_detections = None
    track_cursor = False
    track_radius = 500
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--visualize':
            visualize = True
        elif arg == '--numbers':
            numbers_mode = True
        elif arg.startswith('--mode='):
            mode = arg.split('=')[1]
        elif arg == '--bg-color':
            bg_color = sys.argv[i + 1]
            i += 1
        elif arg == '--color-threshold':
            color_threshold = int(sys.argv[i + 1])
            i += 1
        elif arg == '--cursor':
            cursor_mode = True
        elif arg == '--cursor-dir':
            cursor_dir = sys.argv[i + 1]
            i += 1
        elif arg == '--cursor-threshold':
            cursor_threshold = float(sys.argv[i + 1])
            i += 1
        elif arg == '--frame-seconds':
            frame_seconds = int(sys.argv[i + 1])
            i += 1
        elif arg == '--verbosity':
            verbose = True
        elif arg == '--export-cursor-templates':
            export_cursor_templates = True
        elif arg == '--all-cursor-detections':
            all_cursor_detections = float(sys.argv[i + 1])
            i += 1
        elif arg == '--track-cursor':
            track_cursor = True
        elif arg == '--track-radius':
            track_radius = int(sys.argv[i + 1])
            i += 1
        i += 1
    if not numbers_mode and not cursor_mode:
        print(json.dumps({'error': 'Select at least one feature: --numbers or --cursor'}), file=sys.stderr)
        sys.exit(1)
    try:
        data = {}
        if numbers_mode:
            data['numbers'] = process_file(file_path, mode, visualize, bg_color, color_threshold, frame_seconds, verbose)
        if cursor_mode:
            data['cursor'] = process_cursor_file(
                file_path,
                mode,
                visualize,
                cursor_dir,
                cursor_threshold,
                frame_seconds,
                verbose,
                export_cursor_templates,
                all_cursor_detections,
                track_cursor,
                track_radius,
            )
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_entry()
