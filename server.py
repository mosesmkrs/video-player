from flask import Flask, send_file, render_template, request, jsonify, Response, redirect, url_for
import os
import mimetypes
import json
import time
import re
import ffmpeg
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = "BE61D9E9B64AC871D85FD7C285F7D"

# Folder path for movies
MOVIE_FOLDER = r"C:\Users\MOSES\Downloads\Telegram Desktop\Yellowstone\Yellowstone1"

# Set Flask app configuration
app.config['MOVIE_FOLDER'] = MOVIE_FOLDER

# File to store playback positions
PLAYBACK_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playback_data.json")

# Initialize playback data
def load_playback_data():
    if os.path.exists(PLAYBACK_DATA_FILE):
        try:
            with open(PLAYBACK_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_playback_data(data):
    with open(PLAYBACK_DATA_FILE, 'w') as f:
        json.dump(data, f)

# Load playback data at startup
playback_data = load_playback_data()

@app.route('/')
def index():
    try:
        all_files = os.listdir(MOVIE_FOLDER)
        print("All files in folder:", all_files)  # Debugging output

        # List all video files
        movies = [f for f in all_files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.ts'))]
        print("Listed video files:", movies)  # Debugging output

    except Exception as e:
        print(f"Error accessing folder: {e}")
        movies = []

    return render_template('index.html', movies=movies)

@app.route('/watch/<movie>')
def watch(movie):
    movie_path = os.path.join(MOVIE_FOLDER, movie)

    # Check if the movie exists
    if not os.path.exists(movie_path):
        return "File not found", 404

    file_extension = os.path.splitext(movie)[1].lower().replace('.', '')
    movie_name = os.path.splitext(movie)[0]

    # Get last saved position
    position = playback_data.get(movie, {}).get('position', 0)

    if file_extension == 'ts':
        return redirect(url_for('convert', movie=movie))

    return render_template('player.html', movie=movie, movie_name=movie_name, position=position, file_extension=file_extension)

@app.route('/convert/<movie>')
def convert(movie):
    movie_path = os.path.join(MOVIE_FOLDER, movie)
    
    if not os.path.exists(movie_path):
        return "File not found", 404
    
    movie_name = os.path.splitext(movie)[0]
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    converted_file = os.path.join(temp_dir, f"{movie_name}.mp4")
    
    if os.path.exists(converted_file):
        position = request.args.get('position', '')
        return render_template('player.html', movie=f"{movie_name}.mp4", movie_name=movie_name, position=position, file_extension='mp4', is_converted=True)
    
    return render_template('convert.html', movie=movie, movie_name=movie_name, file_extension='ts')

@app.route('/convert_process/<movie>')
def convert_process(movie):
    movie_path = os.path.join(MOVIE_FOLDER, movie)
    
    if not os.path.exists(movie_path):
        return "File not found", 404
    
    movie_name = os.path.splitext(movie)[0]
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    converted_file = os.path.join(temp_dir, f"{movie_name}.mp4")
    
    try:
        # Convert the file using ffmpeg
        stream = ffmpeg.input(movie_path)
        stream = ffmpeg.output(stream, converted_file, acodec='copy', vcodec='copy')
        ffmpeg.run(stream, overwrite_output=True)
        
        return redirect(url_for('watch', movie=f"{movie_name}.mp4"))
    except Exception as e:
        print(f"Error converting file: {e}")
        return f"Error converting file: {str(e)}", 500

@app.route('/save_position', methods=['POST'])
def save_position():
    data = request.json
    movie = data.get('movie')
    position = data.get('position')
    
    if movie and position is not None:
        playback_data[movie] = {
            'position': position,
            'timestamp': time.time()
        }
        save_playback_data(playback_data)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Missing data'})

@app.route('/stream/<movie>')
def stream(movie):
    movie_path = os.path.join(MOVIE_FOLDER, movie)
    
    if movie.endswith('.mp4') and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", movie)):
        movie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", movie)
    
    if not os.path.exists(movie_path):
        return "File not found", 404
    
    mime_type, _ = mimetypes.guess_type(movie_path)
    
    if movie.lower().endswith('.ts'):
        mime_type = 'video/MP2T'
    elif mime_type is None:
        mime_type = 'video/mp4'
    
    print(f"Streaming {movie} with MIME type {mime_type}")  # Debugging output
    
    file_size = os.path.getsize(movie_path)
    range_header = request.headers.get('Range', None)
    
    if range_header:
        byte1, byte2 = 0, None
        match = re.search('bytes=(\d+)-(\d*)', range_header)
        groups = match.groups()
        
        if groups[0]: byte1 = int(groups[0])
        if groups[1]: byte2 = int(groups[1])
        
        if byte2 is None:
            byte2 = min(byte1 + 1024*1024, file_size - 1)
            
        length = byte2 - byte1 + 1
        
        with open(movie_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
            
        rv = Response(data, 206, mimetype=mime_type, content_type=mime_type, direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(length))
        rv.headers.add('Cache-Control', 'no-cache')
        return rv
    
    response = send_file(movie_path, mimetype=mime_type)
    response.headers.add('Accept-Ranges', 'bytes')
    response.headers.add('Cache-Control', 'no-cache')
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
