from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO
import os
import base64
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'at-the-moment-secret'
# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Ensure the upload directory exists
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store the latest image path in memory
latest_image_path = None

# -------------------------------------------------------------------
# HTML / CSS / JS TEMPLATE
# -------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>At-the-moment</title>
    <!-- Include Socket.IO client library -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        /* Base Reset & Full Screen Layout */
        body, html { margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #000; }
        
        /* Changed object-fit to 'contain' to preserve aspect ratio without cropping */
        #latest-image { width: 100%; height: 100%; object-fit: contain; display: block; }
        .placeholder { color: #888; display: flex; align-items: center; justify-content: center; height: 100%; font-size: 1.5rem; text-align: center; padding: 20px;}

        /* Upload Progress Bar */
        #progress-container { display: none; position: absolute; top: 0; left: 0; width: 100%; height: 6px; background: rgba(255,255,255,0.2); z-index: 50; }
        #progress-bar { width: 0%; height: 100%; background: #4CAF50; transition: width 0.1s; }

        /* Bottom UI Container */
        .bottom-ui { position: absolute; bottom: 30px; left: 20px; right: 20px; display: flex; justify-content: space-between; align-items: flex-end; z-index: 10; }
        
        /* Brand & Info Button */
        .brand-container { background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(5px); color: white; padding: 12px 20px; border-radius: 30px; display: flex; align-items: center; gap: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        .brand-name { font-weight: bold; font-size: 1.1rem; letter-spacing: 0.5px;}
        .info-btn { background: rgba(255, 255, 255, 0.2); border: none; color: white; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; font-weight: bold; transition: background 0.2s; display: flex; align-items: center; justify-content: center;}
        .info-btn:hover { background: rgba(255, 255, 255, 0.4); }

        /* Floating Action Button (Camera) */
        .fab { background: #ffffff; border: none; width: 65px; height: 65px; border-radius: 50%; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; font-size: 28px; transition: transform 0.2s; }
        .fab:active { transform: scale(0.95); }

        /* Camera Viewport */
        #camera-modal { display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #000; z-index: 20; flex-direction: column; }
        
        /* Changed object-fit to 'contain' here as well so the viewfinder matches the final image exactly */
        video { width: 100%; height: 100%; object-fit: contain; }
        
        .capture-bar { position: absolute; bottom: 40px; width: 100%; display: flex; justify-content: center; align-items: center; gap: 30px; }
        .capture-btn { background: white; width: 75px; height: 75px; border-radius: 50%; border: 6px solid rgba(255,255,255,0.5); background-clip: padding-box; cursor: pointer; }
        
        /* Camera Controls */
        .camera-controls { position: absolute; top: 30px; right: 20px; display: flex; flex-direction: column; gap: 15px; z-index: 21; }
        .control-btn { background: rgba(0,0,0,0.5); color: white; border: none; width: 45px; height: 45px; border-radius: 50%; font-size: 20px; cursor: pointer; backdrop-filter: blur(5px); display: flex; align-items: center; justify-content: center;}
        
        /* Info Dialog */
        .modal-overlay { display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 25; backdrop-filter: blur(3px); }
        #info-modal { display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 16px; z-index: 30; width: 80%; max-width: 350px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        #info-modal h3 { margin-top: 0; color: #333; }
        #info-modal p { color: #666; line-height: 1.5; margin-bottom: 25px; }
        .close-dialog-btn { background: #111; color: white; border: none; padding: 12px 24px; border-radius: 20px; cursor: pointer; font-weight: bold; width: 100%; }
    </style>
</head>
<body>

    <!-- Progress Bar -->
    <div id="progress-container">
        <div id="progress-bar"></div>
    </div>

    <!-- Main Display -->
    {% if latest_image %}
        <img id="latest-image" src="{{ latest_image }}" alt="Latest Moment">
    {% else %}
        <div class="placeholder" id="placeholder">No moments captured yet!<br>Click the camera to start.</div>
        <img id="latest-image" style="display:none;" alt="Latest Moment">
    {% endif %}

    <!-- Bottom UI -->
    <div class="bottom-ui">
        <div class="brand-container">
            <span class="brand-name">At-the-moment</span>
            <button class="info-btn" onclick="toggleInfo()">i</button>
        </div>
        <button class="fab" onclick="openCamera()">📷</button>
    </div>

    <!-- Fullscreen Camera View -->
    <div id="camera-modal">
        <div class="camera-controls">
            <button class="control-btn" onclick="closeCamera()">✕</button>
            <button class="control-btn" onclick="switchCamera()">🔄</button>
        </div>
        <video id="video" autoplay playsinline></video>
        <div class="capture-bar">
            <button class="capture-btn" onclick="captureAndUpload()"></button>
        </div>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>

    <!-- Info Dialog -->
    <div class="modal-overlay" id="overlay" onclick="toggleInfo()"></div>
    <div id="info-modal">
        <h3>About At-the-moment</h3>
        <p>This is a live photo wall. Snap a picture using your camera, and it instantly takes over the screen for everyone looking at the site right now!</p>
        <button class="close-dialog-btn" onclick="toggleInfo()">Got it</button>
    </div>

    <script>
        // --- WebSockets Setup ---
        const socket = io();
        
        socket.on('new_image', function(data) {
            const placeholder = document.getElementById('placeholder');
            if(placeholder) placeholder.style.display = 'none';
            
            const latestImg = document.getElementById('latest-image');
            latestImg.style.display = 'block';
            latestImg.src = data.image_url; 
        });

        // --- Camera Setup ---
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const cameraModal = document.getElementById('camera-modal');
        
        let stream;
        let currentFacingMode = 'environment'; 

        async function openCamera() {
            cameraModal.style.display = 'flex';
            
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }

            try {
                stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: currentFacingMode } 
                });
                video.srcObject = stream;
            } catch (err) {
                alert("Camera access is required. Please ensure you are on HTTPS or localhost, and have granted permissions.");
                closeCamera();
            }
        }

        function switchCamera() {
            currentFacingMode = (currentFacingMode === 'environment') ? 'user' : 'environment';
            openCamera(); 
        }

        function closeCamera() {
            cameraModal.style.display = 'none';
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
        }

        // --- Capture & Upload Setup ---
        function captureAndUpload() {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            
            const imageData = canvas.toDataURL('image/jpeg', 0.8); 
            closeCamera();

            const progressContainer = document.getElementById('progress-container');
            const progressBar = document.getElementById('progress-bar');
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);
            xhr.setRequestHeader('Content-Type', 'application/json');

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                        progressBar.style.width = '0%';
                    }, 500);
                } else {
                    alert("Upload failed. Please try again.");
                    progressContainer.style.display = 'none';
                }
            };

            xhr.send(JSON.stringify({ image: imageData }));
        }

        // --- UI Setup ---
        function toggleInfo() {
            const modal = document.getElementById('info-modal');
            const overlay = document.getElementById('overlay');
            if (modal.style.display === 'block') {
                modal.style.display = 'none';
                overlay.style.display = 'none';
            } else {
                modal.style.display = 'block';
                overlay.style.display = 'block';
            }
        }
    </script>
</body>
</html>
"""

# -------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, latest_image=latest_image_path)

@app.route('/upload', methods=['POST'])
def upload():
    global latest_image_path
    data = request.json
    
    if 'image' not in data:
        return jsonify({'error': 'No image provided'}), 400

    # Extract base64 image data
    image_data = data['image'].split(',')[1] 
    
    # Generate filename and save
    filename = f"capture_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    with open(filepath, "wb") as fh:
        fh.write(base64.b64decode(image_data))

    # Save globally
    url_path = f"/{filepath}?t={int(time.time())}"
    latest_image_path = url_path
    
    # BROADCAST TO ALL CONNECTED CLIENTS VIA WEBSOCKET
    socketio.emit('new_image', {'image_url': url_path})
    
    return jsonify({'success': True})

if __name__ == '__main__':
    # Use socketio.run instead of app.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)