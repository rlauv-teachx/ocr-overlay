import os
import subprocess
import json
import sys
import tempfile
from typing import List, Optional, Dict

import numpy as np
from PIL import Image, ImageDraw

try:
    import cv2
except ImportError as exc:
    raise ImportError("opencv-python-headless is required for cursor detection") from exc


def _load_cursor_images(path: str, export_preview: bool = False, max_frames: int = 10) -> List[Dict[str, np.ndarray]]:
    templates: List[Dict[str, np.ndarray]] = []
    base_name = os.path.basename(path)

    for idx in range(max_frames):
        cursor_img = None
        try:
            # Use ImageMagick to extract the frame to a PNG with alpha
            with tempfile.NamedTemporaryFile(suffix='.png', dir='.') as tmp:
                subprocess.run(['convert', f"{path}[{idx}]", tmp.name], check=True, capture_output=True)
                cursor_img = Image.open(tmp.name).convert('RGBA')
        except Exception:
            if idx == 0:
                try:
                    # Fallback to direct PIL open
                    cursor_img = Image.open(path).convert('RGBA')
                except Exception:
                    return templates
            else:
                break

        if cursor_img is None:
            break

        cursor_np = np.array(cursor_img)
        if cursor_np.size == 0:
            continue

        alpha = cursor_np[:, :, 3]
        # Find tight bounding box of non-transparent pixels
        coords = np.argwhere(alpha > 0)
        if coords.size == 0:
            continue
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1  # end is exclusive

        # Crop both image and alpha
        cropped_np = cursor_np[y0:y1, x0:x1]
        if cropped_np.shape[0] < 8 or cropped_np.shape[1] < 8:
            continue
        rgb = cropped_np[:, :, :3]
        alpha = cropped_np[:, :, 3]

        # Create mask: 255 for opaque, 0 for transparent
        mask = (alpha > 0).astype(np.uint8) * 255
        if np.count_nonzero(mask) == 0:
            continue
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        if export_preview:
            try:
                preview_dir = 'extracted/cropped_cursors'
                os.makedirs(preview_dir, exist_ok=True)
                Image.fromarray(cropped_np).save(os.path.join(preview_dir, f"{base_name}{idx}.png"))
            except Exception:
                pass

        templates.append({
            'template': gray,
            'mask': mask,
            'width': gray.shape[1],
            'height': gray.shape[0],
            'variant': idx,
        })

    return templates


def load_cursor_templates(cursors_dir: str = 'data/cursors', export_preview: bool = False) -> List[Dict[str, np.ndarray]]:
    if not os.path.isdir(cursors_dir):
        raise ValueError(f'Cursor directory not found: {cursors_dir}')
    templates = []
    for entry in sorted(os.listdir(cursors_dir)):
        if not entry.lower().endswith('.cur'):
            continue
        path = os.path.join(cursors_dir, entry)
        payloads = _load_cursor_images(path, export_preview=export_preview)
        for payload in payloads:
            payload['name'] = entry
            templates.append(payload)
    if not templates:
        raise ValueError('No cursor templates loaded from .cur files')
    return templates


def load_cursor_templates_with_fallback(cursors_dir: str = 'data/cursors', export_preview: bool = False) -> List[Dict[str, np.ndarray]]:
    try:
        return load_cursor_templates(cursors_dir, export_preview=export_preview)
    except Exception:
        pass

    with tempfile.TemporaryDirectory() as tmp:
        png_dir = os.path.join(tmp, 'cursor_pngs')
        os.makedirs(png_dir, exist_ok=True)
        for entry in sorted(os.listdir(cursors_dir)):
            if not entry.lower().endswith('.cur'):
                continue
            src_path = os.path.join(cursors_dir, entry)
            dst_path = os.path.join(png_dir, f"{os.path.splitext(entry)[0]}.png")
            subprocess.run(['convert', src_path, dst_path], check=False)
        png_templates = []
        for entry in sorted(os.listdir(png_dir)):
            if not entry.lower().endswith('.png'):
                continue
            payloads = _load_cursor_images(os.path.join(png_dir, entry), export_preview=export_preview)
            for payload in payloads:
                payload['name'] = entry
                png_templates.append(payload)
        if not png_templates:
            raise ValueError('No cursor templates could be loaded from .cur files')
        return png_templates


def _prepare_match_image(gray_image: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(gray_image, (3, 3), 0)
    kernel = np.ones((2, 2), np.uint8)
    return cv2.erode(blurred, kernel, iterations=1)


def detect_cursor_in_image(
    image_path: str,
    templates: List[Dict[str, np.ndarray]],
    threshold: float = 0.8,
    all_detections_threshold: Optional[float] = None,
    search_region: Optional[Dict[str, int]] = None,
    max_detections_per_template: int = 20,
) -> Optional[Dict[str, object]]:
    frame = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_frame = _prepare_match_image(gray_frame)

    offset_x = 0
    offset_y = 0
    if search_region:
        x0 = max(0, search_region['x0'])
        y0 = max(0, search_region['y0'])
        x1 = min(gray_frame.shape[1], search_region['x1'])
        y1 = min(gray_frame.shape[0], search_region['y1'])
        gray_frame = gray_frame[y0:y1, x0:x1]
        offset_x = x0
        offset_y = y0

    best = None
    best_by_name: Dict[str, Dict[str, object]] = {}
    detections: List[Dict[str, object]] = []
    for template in templates:
        mask = template['mask']
        template_img = _prepare_match_image(template['template'])
        result = cv2.matchTemplate(gray_frame, template_img, cv2.TM_CCORR_NORMED, mask=mask)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        name = template['name']
        entry = {
            'x': max_loc[0] + offset_x,
            'y': max_loc[1] + offset_y,
            'width': int(template['width']),
            'height': int(template['height']),
            'score': float(max_val),
            'template': name,
        }
        if 'variant' in template:
            entry['variant'] = int(template['variant'])
        existing = best_by_name.get(name)
        if existing is None or entry['score'] > existing['score']:
            best_by_name[name] = entry

        if all_detections_threshold is not None:
            locations = np.where(result >= all_detections_threshold)
            for idx, (y_loc, x_loc) in enumerate(zip(locations[0], locations[1])):
                if idx >= max_detections_per_template:
                    break
                det = {
                    'x': int(x_loc) + offset_x,
                    'y': int(y_loc) + offset_y,
                    'width': int(template['width']),
                    'height': int(template['height']),
                    'score': float(result[y_loc, x_loc]),
                    'template': name,
                }
                if 'variant' in template:
                    det['variant'] = int(template['variant'])
                detections.append(det)

    for entry in best_by_name.values():
        if best is None or entry['score'] > best['score']:
            best = entry

    if all_detections_threshold is not None:
        if not detections:
            return None
        detections.sort(key=lambda item: item['score'], reverse=True)
        return {'detections': detections, 'best': best}

    if best is None or best['score'] < threshold:
        return None
    return best


def process_cursor_file(file_path: str,
                        mode: Optional[str] = None,
                        visualize: bool = False,
                        cursor_dir: str = 'data/cursors',
                        threshold: float = 0.8,
                        frame_seconds: Optional[int] = None,
                        verbose: bool = False,
                        export_templates: bool = False,
                        all_detections_threshold: Optional[float] = None,
                        track_cursor: bool = False,
                        track_radius: int = 500) -> List[Dict[str, object]]:
    resolved_path = os.path.abspath(file_path)
    if not os.path.exists(resolved_path):
        raise ValueError('File not found')
    if mode is None:
        ext = os.path.splitext(resolved_path)[1].lower()
        if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}:
            mode = 'image'
        elif ext == '.mp4':
            mode = 'video'
        else:
            raise ValueError('Unsupported file extension for cursor detection')
    if mode not in {'video', 'image'}:
        raise ValueError('Cursor tracking only supports video or image inputs')

    templates = load_cursor_templates_with_fallback(cursor_dir, export_preview=export_templates)
    extracted_dir = 'extracted'
    if visualize:
        os.makedirs(extracted_dir, exist_ok=True)

    data: List[Dict[str, object]] = []
    if mode == 'image':
        if verbose:
            print(f"Processing image {resolved_path}")
        detection = detect_cursor_in_image(
            resolved_path,
            templates,
            threshold,
            all_detections_threshold,
        )
        if detection:
            if 'detections' in detection:
                for det in detection['detections']:
                    det.update({'frame': 1, 'second': 0})
                    data.append(det)
                best = detection.get('best')
                if best:
                    best.update({'frame': 1, 'second': 0})
            else:
                detection.update({'frame': 1, 'second': 0})
                data.append(detection)
                if verbose:
                    print("DETECTED CURSOR in image")
        if visualize:
            color_img = Image.open(resolved_path).convert('RGB')
            draw = ImageDraw.Draw(color_img)
            for det in data:
                x = det['x']
                y = det['y']
                w = det['width']
                h = det['height']
                draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
            color_img.save(f'{extracted_dir}/cursor_image.png')
        return data

    with tempfile.TemporaryDirectory(dir='.') as tmp:
        frames_dir = os.path.join(tmp, 'cursor_frames')
        os.makedirs(frames_dir, exist_ok=True)
        ffmpeg_cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', resolved_path]
        if frame_seconds:
            ffmpeg_cmd.extend(['-t', str(frame_seconds)])
        ffmpeg_cmd.extend(['-vf', 'fps=1', '-q:v', '2', f'{frames_dir}/frame_%04d.png'])
        subprocess.run(ffmpeg_cmd, check=True)
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
        if verbose:
            print(f"Processing video {resolved_path}")
        last_position: Optional[Dict[str, int]] = None
        for i, f in enumerate(frame_files):
            frame_num = i + 1
            img_path = os.path.join(frames_dir, f)
            if verbose:
                print(f"Checking frame {frame_num}")
            search_region = None
            if track_cursor and last_position:
                search_region = {
                    'x0': last_position['x'] - track_radius,
                    'y0': last_position['y'] - track_radius,
                    'x1': last_position['x'] + track_radius,
                    'y1': last_position['y'] + track_radius,
                }
            detection = detect_cursor_in_image(
                img_path,
                templates,
                threshold,
                all_detections_threshold,
                search_region,
            )
            frame_detections: List[Dict[str, object]] = []
            if detection:
                if 'detections' in detection:
                    for det in detection['detections']:
                        det.update({'frame': frame_num, 'second': (frame_num - 1) // 1})
                        data.append(det)
                        frame_detections.append(det)
                    best = detection.get('best')
                    if best:
                        last_position = {
                            'x': int(best['x']),
                            'y': int(best['y']),
                        }
                        if verbose:
                            print(f"DETECTED CURSOR in frame {frame_num}")
                else:
                    detection.update({'frame': frame_num, 'second': (frame_num - 1) // 1})
                    data.append(detection)
                    frame_detections.append(detection)
                    last_position = {
                        'x': int(detection['x']),
                        'y': int(detection['y']),
                    }
                    if verbose:
                        print(f"DETECTED CURSOR in frame {frame_num}")
            if visualize:
                color_img = Image.open(img_path).convert('RGB')
                draw = ImageDraw.Draw(color_img)
                for det in frame_detections:
                    x = det['x']
                    y = det['y']
                    w = det['width']
                    h = det['height']
                    draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
                color_img.save(f'{extracted_dir}/cursor_frame_{frame_num}.png')

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--mode', choices=['video', 'image'])
    parser.add_argument('--visualize', action='store_true')
    parser.add_argument('--cursor-dir', default='data/cursors')
    parser.add_argument('--cursor-threshold', type=float, default=0.8)
    parser.add_argument('--all-detections-threshold', type=float)
    parser.add_argument('--track-cursor', action='store_true')
    parser.add_argument('--track-radius', type=int, default=500)
    parser.add_argument('--frame-seconds', type=int)
    parser.add_argument('--verbosity', action='store_true')
    parser.add_argument('--export-templates', action='store_true')
    args = parser.parse_args()
    try:
        data = process_cursor_file(
            args.file,
            args.mode,
            args.visualize,
            args.cursor_dir,
            args.cursor_threshold,
            args.frame_seconds,
            args.verbosity,
            args.export_templates,
            args.all_detections_threshold,
            args.track_cursor,
            args.track_radius,
        )
        json.dump(data, sys.stdout, indent=2)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stdout)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
