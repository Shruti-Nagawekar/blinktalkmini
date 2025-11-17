#!/usr/bin/env python3
"""
BlinkTalk Server
Receives camera stream frames from iPhone for processing
Optimized for continuous frame streaming
"""

import http.server
import socketserver
import json
import base64
import threading
from datetime import datetime
from pathlib import Path
from collections import deque
import cv2
import numpy as np

# Server configuration
MAC_IP = "100.70.127.109"
PORT = 8080
FRAMES_DIR = Path("received_frames")
FRAMES_DIR.mkdir(exist_ok=True)

# Frame statistics
frame_stats = {
    'total_received': 0,
    'total_processed': 0,
    'total_errors': 0,
    'last_frame_time': None
}

# Optional: Keep last N frames in memory for processing
frame_buffer = deque(maxlen=10)

# Initialize OpenCV Haar Cascade face detector
# Try to find cascade files in common locations
import os
cascade_path = None
cv2_dir = os.path.dirname(cv2.__file__)
possible_paths = [
    os.path.join(cv2_dir, 'data', 'haarcascade_frontalface_default.xml'),
    os.path.join(os.path.dirname(cv2_dir), '..', 'pkgs', 'libopencv-*', 'share', 'opencv4', 'haarcascades', 'haarcascade_frontalface_default.xml'),
    '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
    '/opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
]

# Check standard paths
for path in possible_paths:
    if '*' in path:
        # Handle glob pattern
        import glob
        matches = glob.glob(path)
        if matches:
            cascade_path = os.path.dirname(matches[0])
            break
    elif os.path.exists(path):
        cascade_path = os.path.dirname(path)
        break

# If still not found, try to find in conda environment
if cascade_path is None:
    conda_prefix = os.environ.get('CONDA_PREFIX', '')
    if conda_prefix:
        conda_cascade = os.path.join(conda_prefix, 'share', 'opencv4', 'haarcascades', 'haarcascade_frontalface_default.xml')
        if os.path.exists(conda_cascade):
            cascade_path = os.path.dirname(conda_cascade)

if cascade_path is None:
    # Fallback: download or use alternative detection method
    print("Warning: Haar cascade files not found. Face detection may not work.")
    face_detector = None
    eye_detector = None
else:
    face_detector = cv2.CascadeClassifier(os.path.join(cascade_path, 'haarcascade_frontalface_default.xml'))
    eye_detector = cv2.CascadeClassifier(os.path.join(cascade_path, 'haarcascade_eye.xml'))
    print(f"Face detector initialized from: {cascade_path}")

class FaceLandmarkDetector:
    """Detects facial landmarks and extracts eye coordinates using OpenCV"""
    
    @staticmethod
    def detect_landmarks(image_data):
        """
        Detect facial landmarks from image data using OpenCV
        Returns: landmarks dict with eye coordinates or None if no face detected
        """
        try:
            # Convert image data to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return None
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape
            
            # Detect faces
            if face_detector is None:
                return None
            faces = face_detector.detectMultiScale(gray, 1.1, 4, minSize=(50, 50))
            
            if len(faces) == 0:
                return None
            
            # Use first detected face
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w]
            
            # Detect eyes within face region
            if eye_detector is None:
                eyes = []
            else:
                eyes = eye_detector.detectMultiScale(face_roi, 1.1, 3)
            
            if len(eyes) < 2:
                # If eyes not detected, estimate eye positions based on face proportions
                # Standard face proportions: eyes are at ~1/3 from top, ~1/4 from sides
                left_eye_center_x = x + w * 0.25
                right_eye_center_x = x + w * 0.75
                eye_y = y + h * 0.35
                eye_width = w * 0.15
                eye_height = h * 0.15
                
                # Create 6 points for each eye (for EAR calculation)
                # Points: [outer_corner, inner_corner, top1, bottom1, top2, bottom2]
                left_eye_points = np.array([
                    [left_eye_center_x - eye_width/2, eye_y],  # outer corner
                    [left_eye_center_x + eye_width/2, eye_y],  # inner corner
                    [left_eye_center_x - eye_width/4, eye_y - eye_height/2],  # top1
                    [left_eye_center_x - eye_width/4, eye_y + eye_height/2],  # bottom1
                    [left_eye_center_x + eye_width/4, eye_y - eye_height/2],  # top2
                    [left_eye_center_x + eye_width/4, eye_y + eye_height/2],  # bottom2
                ])
                
                right_eye_points = np.array([
                    [right_eye_center_x - eye_width/2, eye_y],  # inner corner
                    [right_eye_center_x + eye_width/2, eye_y],  # outer corner
                    [right_eye_center_x - eye_width/4, eye_y - eye_height/2],  # top1
                    [right_eye_center_x - eye_width/4, eye_y + eye_height/2],  # bottom1
                    [right_eye_center_x + eye_width/4, eye_y - eye_height/2],  # top2
                    [right_eye_center_x + eye_width/4, eye_y + eye_height/2],  # bottom2
                ])
            else:
                # Sort eyes by x-coordinate (left eye first)
                eyes = sorted(eyes, key=lambda e: e[0])
                left_eye, right_eye = eyes[0], eyes[1]
                
                # Extract 6 points for each eye
                # Convert relative to face coordinates to absolute image coordinates
                lx, ly, lw, lh = left_eye
                rx, ry, rw, rh = right_eye
                
                # Left eye points
                left_eye_points = np.array([
                    [x + lx, y + ly + lh/2],  # outer corner
                    [x + lx + lw, y + ly + lh/2],  # inner corner
                    [x + lx + lw/4, y + ly],  # top1
                    [x + lx + lw/4, y + ly + lh],  # bottom1
                    [x + lx + 3*lw/4, y + ly],  # top2
                    [x + lx + 3*lw/4, y + ly + lh],  # bottom2
                ])
                
                # Right eye points
                right_eye_points = np.array([
                    [x + rx, y + ry + rh/2],  # inner corner
                    [x + rx + rw, y + ry + rh/2],  # outer corner
                    [x + rx + rw/4, y + ry],  # top1
                    [x + rx + rw/4, y + ry + rh],  # bottom1
                    [x + rx + 3*rw/4, y + ry],  # top2
                    [x + rx + 3*rw/4, y + ry + rh],  # bottom2
                ])
            
            return {
                'left_eye': left_eye_points,
                'right_eye': right_eye_points,
                'face_detected': True
            }
            
        except Exception as e:
            print(f"FaceLandmarkDetector: Error detecting landmarks: {e}")
            return None

class FrameHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests with frame data from camera stream"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            # Parse JSON data
            data = json.loads(post_data.decode('utf-8'))
            
            # Extract frame data
            frame_base64 = data.get('frame', '')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            frame_id = data.get('frame_id', 'unknown')
            save_frame = data.get('save_frame', False)  # Optional: only save when requested
            
            frame_stats['total_received'] += 1
            frame_stats['last_frame_time'] = datetime.now()
            
            # Log first few received frames
            if frame_stats['total_received'] <= 3:
                print(f"Server: Received frame {frame_id} (total: {frame_stats['total_received']})")
            
            # Decode base64 image
            if frame_base64:
                image_data = base64.b64decode(frame_base64)
                
                # Store frame in buffer for processing
                frame_info = {
                    'frame_id': frame_id,
                    'timestamp': timestamp,
                    'data': image_data,
                    'size': len(image_data)
                }
                frame_buffer.append(frame_info)
                
                # Detect facial landmarks
                try:
                    landmarks = FaceLandmarkDetector.detect_landmarks(image_data)
                    face_detected = landmarks is not None
                    
                    # Log face detection results (every 10 frames to see results more frequently)
                    if frame_stats['total_received'] % 10 == 0:
                        status = "Face detected" if face_detected else "No face detected"
                        print(f"Frame {frame_id}: {status} (total received: {frame_stats['total_received']})")
                    
                    # Also log first few frames for debugging
                    if frame_stats['total_received'] <= 5:
                        status = "Face detected" if face_detected else "No face detected"
                        print(f"Frame {frame_id}: {status} (frame #{frame_stats['total_received']})")
                        if landmarks:
                            print(f"  - Left eye points: {len(landmarks.get('left_eye', []))} points")
                            print(f"  - Right eye points: {len(landmarks.get('right_eye', []))} points")
                except Exception as e:
                    print(f"Error during face detection for frame {frame_id}: {e}")
                    face_detected = False
                    import traceback
                    traceback.print_exc()
                
                # Only save to disk if explicitly requested (to avoid disk I/O bottleneck)
                filepath = None
                if save_frame:
                    filename = f"frame_{frame_id}_{timestamp.replace(':', '-').replace('.', '-')}.jpg"
                    filepath = FRAMES_DIR / filename
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                
                frame_stats['total_processed'] += 1
                
                # Send response with landmark detection result
                response = {
                    'status': 'success',
                    'message': f'Frame {frame_id} received',
                    'frame_id': frame_id,
                    'saved': save_frame,
                    'filepath': str(filepath) if filepath else None,
                    'face_detected': face_detected
                }
            else:
                response = {
                    'status': 'error',
                    'message': 'No frame data provided'
                }
                frame_stats['total_errors'] += 1
                
        except json.JSONDecodeError:
            response = {
                'status': 'error',
                'message': 'Invalid JSON data'
            }
            frame_stats['total_errors'] += 1
        except Exception as e:
            response = {
                'status': 'error',
                'message': f'Error processing frame: {str(e)}'
            }
            frame_stats['total_errors'] += 1
        
        # Send response quickly (non-blocking for streaming)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests - health check and stats"""
        if self.path == '/health':
            response = {
                'status': 'running',
                'server_ip': MAC_IP,
                'port': PORT,
                'stats': {
                    'total_received': frame_stats['total_received'],
                    'total_processed': frame_stats['total_processed'],
                    'total_errors': frame_stats['total_errors'],
                    'frames_in_buffer': len(frame_buffer),
                    'last_frame_time': frame_stats['last_frame_time'].isoformat() if frame_stats['last_frame_time'] else None
                }
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Custom log format - log all requests for debugging"""
        # Log all POST requests and errors
        message = format % args
        if 'POST' in message or 'error' in message.lower():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Frames: {frame_stats['total_received']} | {message}")
        # Log every 100th GET request to avoid spam
        elif 'GET' in message and frame_stats['total_received'] % 100 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Frames: {frame_stats['total_received']} | {message}")

def run_server():
    """Start the server optimized for camera stream"""
    # Use ThreadingMixIn for better concurrent request handling
    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True
    
    with ThreadedTCPServer((MAC_IP, PORT), FrameHandler) as httpd:
        print(f"🚀 BlinkTalk Server started (Streaming Mode)")
        print(f"📡 Listening on {MAC_IP}:{PORT}")
        print(f"📁 Frames directory: {FRAMES_DIR.absolute()}")
        print(f"💡 Health check: http://{MAC_IP}:{PORT}/health")
        print(f"📊 Frames are buffered in memory (last 10 frames)")
        print(f"💾 Frames saved to disk only when 'save_frame: true' is sent")
        print("\nPress Ctrl+C to stop the server\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n\n🛑 Server stopped")
            print(f"📊 Final stats: {frame_stats['total_received']} received, {frame_stats['total_processed']} processed, {frame_stats['total_errors']} errors")

if __name__ == "__main__":
    run_server()

