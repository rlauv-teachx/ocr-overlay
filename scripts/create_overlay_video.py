import subprocess
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
from scripts.ocr_processor import process_file  # reuse core

def create_overlay_video(input_video, output_video='output_overlay.mp4', mode='video', bg_color=None, color_threshold=30):
    with tempfile.TemporaryDirectory() as tmp:
        frames_dir = f'{tmp}/frames'
        os.makedirs(frames_dir, exist_ok=True)
        # extract frames (use fps=5 for performance on full video; re-encode keeps duration)
        subprocess.run(['ffmpeg', '-i', input_video, '-vf', 'fps=5', '-q:v', '2', f'{frames_dir}/frame_%04d.png'], check=True)
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
        from scripts.ocr_processor import get_numbers_from_image
        for i, f in enumerate(frame_files):
            frame_num = i + 1
            img_path = os.path.join(frames_dir, f)
            color_img = Image.open(img_path).convert('RGB')
            nums = get_numbers_from_image(img_path, bg_color, color_threshold)
            draw = ImageDraw.Draw(color_img)
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 20)
            except:
                font = ImageFont.load_default()
            for val, x, y, w, h in nums:
                draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
                draw.text((x, y - 25), val, fill='red', font=font)
            color_img.save(img_path)
        # reassemble (output same length by matching original duration via -r)
        subprocess.run(['ffmpeg', '-framerate', '5', '-i', f'{frames_dir}/frame_%04d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '60', '-y', output_video], check=True)
    print(f'Overlay video created: {output_video} (same length as input)')

if __name__ == "__main__":
    import sys
    input_v = sys.argv[1] if len(sys.argv) > 1 else 'data/samples/sample.mp4'
    create_overlay_video(input_v)
