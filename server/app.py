from flask import Flask, request, jsonify
import os
from scripts.ocr_processor import process_file

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path required'}), 400
    file_path = data['file_path']
    mode = data.get('mode')
    visualize = data.get('visualize', False)
    bg_color = data.get('bg_color')
    color_threshold = data.get('color_threshold', 30)
    try:
        result = process_file(file_path, mode, visualize, bg_color, color_threshold)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == "__main__":
    run_server()
