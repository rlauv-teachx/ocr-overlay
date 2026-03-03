import subprocess
import json
import os
import sys
import colorsys
import tempfile
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

def looks_like_number(text):
    if not text or len(text.strip()) < 1:
        return False
    cleaned = text.strip().replace(',', '').replace(' ', '').rstrip('.').rstrip('%')
    try:
        float(cleaned)
        return True
    except ValueError:
        return False

def color_distance(hue1, hue2):
    diff = abs(hue1 - hue2)
    return min(diff, 360 - diff)

def is_over_background_color(image, left, top, width, height, target_hue, threshold=30):
    # sample avg color from expanded bbox border (background)
    expand = 5
    box = (max(0, left - expand), max(0, top - expand), left + width + expand, top + height + expand)
    crop = image.crop(box).convert('RGB')
    data = list(crop.getdata())
    if not data:
        return False
    avg_r = sum(p[0] for p in data) // len(data)
    avg_g = sum(p[1] for p in data) // len(data)
    avg_b = sum(p[2] for p in data) // len(data)
    h, _, _ = colorsys.rgb_to_hsv(avg_r/255, avg_g/255, avg_b/255)
    hue = h * 360
    return color_distance(hue, target_hue) <= threshold

def get_numbers_from_image(image_path, bg_color=None, color_threshold=30):
    color_img = Image.open(image_path).convert('RGB')
    gray_img = color_img.convert('L')
    gray_img = gray_img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(gray_img)
    gray_img = enhancer.enhance(2.0)
    proc_path = image_path.replace('.png', '_proc.png')
    gray_img.save(proc_path)
    cmd = ['tesseract', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789.,- ', proc_path, 'stdout', 'tsv']
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        os.unlink(proc_path)
        return []
    lines = result.stdout.strip().split('\n')
    numbers = []
    color_map = {'blue': 210, 'red': 0, 'green': 120, 'yellow': 60, 'black': 0, 'white': 0}
    target_hue = color_map.get(bg_color.lower()) if bg_color else None
    for line in lines[1:]:
        parts = line.split('\t')
        if len(parts) >= 12 and int(parts[0]) == 5:
            text = parts[11].strip().rstrip(',').rstrip('.').rstrip('%')
            conf = int(parts[10]) if parts[10].isdigit() else 0
            if text and conf >= 0 and looks_like_number(text):
                left = int(parts[6])
                top = int(parts[7])
                width = int(parts[8])
                height = int(parts[9])
                if target_hue is not None:
                    if not is_over_background_color(color_img, left, top, width, height, target_hue, color_threshold):
                        continue
                numbers.append((text, left, top, width, height))
    os.unlink(proc_path)
    return numbers

def process_file(file_path, mode=None, visualize=False, bg_color=None, color_threshold=30, frame_seconds=None, verbose=False):
    resolved_path = os.path.abspath(file_path)
    if not os.path.exists(resolved_path):
        raise ValueError('File not found')
    if mode is None:
        ext = os.path.splitext(resolved_path)[1].lower()
        if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}:
            mode = 'image'
        elif ext == '.mp4':
            mode = 'video'
        elif ext == '.pdf':
            mode = 'pdf'
        else:
            raise ValueError('Unsupported file extension for numbers detection')
    extracted_dir = 'extracted'
    if visualize:
        os.makedirs(extracted_dir, exist_ok=True)
    data = []
    if mode == 'image':
        if verbose:
            print(f"Processing image {resolved_path}")
        nums = get_numbers_from_image(resolved_path, bg_color, color_threshold)
        for val, x, y, w, h in nums:
            data.append({'value': val, 'top_left_x_coord': x, 'top_left_y_coord': y})
        if nums and verbose:
            print("DETECTED NUMBERS in image")
        if visualize:
            color_img = Image.open(resolved_path).convert('RGB')
            draw = ImageDraw.Draw(color_img)
            for _, x, y, w, h in nums:
                draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
            color_img.save(f'{extracted_dir}/image_numbers.png')
        return data

    with tempfile.TemporaryDirectory(dir='.') as tmp:
        frames_dir = os.path.join(tmp, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        if mode == 'video':
            ffmpeg_cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', resolved_path]
            if frame_seconds:
                ffmpeg_cmd.extend(['-t', str(frame_seconds)])
            ffmpeg_cmd.extend(['-vf', 'fps=1', '-q:v', '2', f'{frames_dir}/frame_%04d.png'])
            subprocess.run(ffmpeg_cmd, check=True)
            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png') and '_proc' not in f])
            if verbose:
                print(f"Processing video {resolved_path}")
            for i, f in enumerate(frame_files):
                frame = i + 1
                img_path = os.path.join(frames_dir, f)
                if verbose:
                    print(f"Checking frame {frame}")
                nums = get_numbers_from_image(img_path, bg_color, color_threshold)
                second = (frame - 1) // 1
                for val, x, y, w, h in nums:
                    data.append({'frame': frame, 'second': second, 'value': val, 'top_left_x_coord': x, 'top_left_y_coord': y})
                if nums and verbose:
                    print(f"DETECTED NUMBERS in frame {frame}")
                if visualize:
                    color_img = Image.open(img_path).convert('RGB')
                    draw = ImageDraw.Draw(color_img)
                    for _, x, y, w, h in nums:
                        draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
                    color_img.save(f'{extracted_dir}/video_frame_{frame}.png')
        else:
            subprocess.run(['pdftoppm', '-png', '-r', '150', '-f', '1', '-l', '3', resolved_path, f'{frames_dir}/page'], check=True)
            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png') and '_proc' not in f])
            if verbose:
                print(f"Processing PDF {resolved_path}")
            for i, f in enumerate(frame_files):
                page = i + 1
                img_path = os.path.join(frames_dir, f)
                if verbose:
                    print(f"Checking page {page}")
                nums = get_numbers_from_image(img_path, bg_color, color_threshold)
                for val, x, y, w, h in nums:
                    data.append({'page': page, 'value': val, 'top_left_x_coord': x, 'top_left_y_coord': y})
                if nums and verbose:
                    print(f"DETECTED NUMBERS on page {page}")
                if visualize:
                    color_img = Image.open(img_path).convert('RGB')
                    draw = ImageDraw.Draw(color_img)
                    for _, x, y, w, h in nums:
                        draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
                    color_img.save(f'{extracted_dir}/pdf_page_{page}.png')
    return data

def main():
    # for CLI/module run
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--mode', choices=['video', 'pdf', 'image'])
    parser.add_argument('--visualize', action='store_true')
    parser.add_argument('--bg-color')
    parser.add_argument('--color-threshold', type=int, default=30)
    parser.add_argument('--frame-seconds', type=int)
    parser.add_argument('--verbosity', action='store_true')
    args = parser.parse_args()
    try:
        data = process_file(
            args.file,
            args.mode,
            args.visualize,
            args.bg_color,
            args.color_threshold,
            args.frame_seconds,
            args.verbosity,
        )
        json.dump(data, sys.stdout, indent=2)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()
