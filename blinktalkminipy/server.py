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
import dlib
import urllib.request

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

# Blink detection state (per session)
blink_state = {
    'was_closed': False,  # Previous frame EAR state (True if EAR ≤ threshold)
    'blink_count': 0,     # Total blinks in current session
    'session_active': False,  # Whether a session is active
    'session_start_time': None
}

# EAR threshold for blink detection
# Based on observed values: closed ~0.33, open ~0.46
# Using 0.35 as threshold (adjust if needed)
EAR_BLINK_THRESHOLD = 0.35

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
else:
    face_detector = cv2.CascadeClassifier(os.path.join(cascade_path, 'haarcascade_frontalface_default.xml'))
    print(f"Face detector initialized from: {cascade_path}")

# Initialize dlib facial landmark predictor
# Download shape predictor if not present
SHAPE_PREDICTOR_URL = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
# Use absolute path relative to script location
SCRIPT_DIR = Path(__file__).parent.absolute()
SHAPE_PREDICTOR_PATH = SCRIPT_DIR / "shape_predictor_68_face_landmarks.dat"
SHAPE_PREDICTOR_COMPRESSED = SCRIPT_DIR / "shape_predictor_68_face_landmarks.dat.bz2"

landmark_predictor = None
dlib_face_detector = None

try:
    # Check if shape predictor exists
    if not SHAPE_PREDICTOR_PATH.exists():
        print("Downloading dlib shape predictor (68-point facial landmark model)...")
        print("This is a one-time download (~100MB). Please wait...")
        
        # Download compressed file
        urllib.request.urlretrieve(SHAPE_PREDICTOR_URL, SHAPE_PREDICTOR_COMPRESSED)
        
        # Decompress (bz2)
        import bz2
        with bz2.open(SHAPE_PREDICTOR_COMPRESSED, 'rb') as f_in:
            with open(SHAPE_PREDICTOR_PATH, 'wb') as f_out:
                f_out.write(f_in.read())
        
        # Remove compressed file
        SHAPE_PREDICTOR_COMPRESSED.unlink()
        print("Shape predictor downloaded and extracted successfully.")
    
    # Initialize dlib components
    landmark_predictor = dlib.shape_predictor(str(SHAPE_PREDICTOR_PATH))
    dlib_face_detector = dlib.get_frontal_face_detector()
    print("dlib facial landmark detector initialized successfully.")
    
except Exception as e:
    print(f"Warning: Failed to initialize dlib: {e}")
    print("Falling back to OpenCV Haar Cascade eye detection.")
    landmark_predictor = None
    dlib_face_detector = None

class FaceLandmarkDetector:
    """Detects facial landmarks and extracts eye coordinates using dlib"""
    _last_log_frame = 0
    
    @staticmethod
    def detect_landmarks(image_data):
        """
        Detect facial landmarks from image data using dlib
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
            
            # Use OpenCV for face detection, then dlib for landmarks (hybrid approach)
            # This combines OpenCV's reliable face detection with dlib's accurate landmarks
            if face_detector is not None and landmark_predictor is not None:
                # Detect faces using OpenCV (more reliable)
                faces = face_detector.detectMultiScale(gray, 1.1, 4, minSize=(50, 50))
                
                if len(faces) == 0:
                    # Log occasionally to debug
                    if FaceLandmarkDetector._last_log_frame < frame_stats.get('total_received', 0):
                        FaceLandmarkDetector._last_log_frame = frame_stats.get('total_received', 0) + 50
                        print(f"FaceLandmarkDetector: OpenCV detected 0 faces (dlib path)")
                    return None
                
                # Use first detected face
                (x, y, w, h) = faces[0]
                
                # Convert OpenCV rectangle to dlib rectangle format
                # dlib uses (left, top, right, bottom) format
                try:
                    dlib_rect = dlib.rectangle(int(x), int(y), int(x + w), int(y + h))
                    
                    # Ensure gray is contiguous for dlib
                    if not gray.flags['C_CONTIGUOUS']:
                        gray = np.ascontiguousarray(gray)
                    
                    # Get facial landmarks (68 points) using dlib
                    landmarks = landmark_predictor(gray, dlib_rect)
                    
                    # Extract eye landmarks from 68-point model
                    # Left eye: points 36-41 (0-indexed: 36, 37, 38, 39, 40, 41)
                    # Right eye: points 42-47 (0-indexed: 42, 43, 44, 45, 46, 47)
                    # For EAR calculation, we need 6 points per eye:
                    # [outer_corner, inner_corner, top1, bottom1, top2, bottom2]
                    
                    # Left eye points (36-41)
                    # 36 = outer corner, 39 = inner corner
                    # 37 = top1, 41 = bottom1, 38 = top2, 40 = bottom2
                    left_eye_points = np.array([
                        [landmarks.part(36).x, landmarks.part(36).y],  # outer corner
                        [landmarks.part(39).x, landmarks.part(39).y],  # inner corner
                        [landmarks.part(37).x, landmarks.part(37).y],  # top1
                        [landmarks.part(41).x, landmarks.part(41).y],  # bottom1
                        [landmarks.part(38).x, landmarks.part(38).y],  # top2
                        [landmarks.part(40).x, landmarks.part(40).y],  # bottom2
                    ])
                    
                    # Right eye points (42-47)
                    # 42 = inner corner, 45 = outer corner
                    # 43 = top1, 47 = bottom1, 44 = top2, 46 = bottom2
                    right_eye_points = np.array([
                        [landmarks.part(45).x, landmarks.part(45).y],  # outer corner
                        [landmarks.part(42).x, landmarks.part(42).y],  # inner corner
                        [landmarks.part(43).x, landmarks.part(43).y],  # top1
                        [landmarks.part(47).x, landmarks.part(47).y],  # bottom1
                        [landmarks.part(44).x, landmarks.part(44).y],  # top2
                        [landmarks.part(46).x, landmarks.part(46).y],  # bottom2
                    ])
                    
                    return {
                        'left_eye': left_eye_points,
                        'right_eye': right_eye_points,
                        'face_detected': True,
                        'eyes_detected': True  # dlib always provides eye landmarks
                    }
                except Exception as e:
                    # If dlib fails, fall through to OpenCV fallback
                    print(f"FaceLandmarkDetector: dlib landmark prediction/extraction failed: {e}")
                    # Fall through to OpenCV fallback below
            
            # Fallback to OpenCV if dlib not available
            if face_detector is None:
                if FaceLandmarkDetector._last_log_frame < frame_stats.get('total_received', 0):
                    FaceLandmarkDetector._last_log_frame = frame_stats.get('total_received', 0) + 50
                    print(f"FaceLandmarkDetector: face_detector is None, cannot detect faces")
                return None
            
            # Check if we're in fallback mode (dlib not available)
            if landmark_predictor is None:
                if FaceLandmarkDetector._last_log_frame < frame_stats.get('total_received', 0):
                    FaceLandmarkDetector._last_log_frame = frame_stats.get('total_received', 0) + 50
                    print(f"FaceLandmarkDetector: Using OpenCV fallback (dlib not available)")
            
            faces = face_detector.detectMultiScale(gray, 1.1, 4, minSize=(50, 50))
            
            if len(faces) == 0:
                # Log occasionally to debug
                if FaceLandmarkDetector._last_log_frame < frame_stats.get('total_received', 0):
                    FaceLandmarkDetector._last_log_frame = frame_stats.get('total_received', 0) + 50
                    print(f"FaceLandmarkDetector: OpenCV detected 0 faces (fallback path)")
                return None
            
            # Use first detected face
            (x, y, w, h) = faces[0]
            
            # Estimate eye positions based on face proportions (fallback)
            left_eye_center_x = x + w * 0.25
            right_eye_center_x = x + w * 0.75
            eye_y = y + h * 0.35
            eye_width = w * 0.20
            eye_height = h * 0.125
            
            # Create 6 points for each eye (for EAR calculation)
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
            
            return {
                'left_eye': left_eye_points,
                'right_eye': right_eye_points,
                'face_detected': True,
                'eyes_detected': False  # Using estimated positions
            }
            
        except Exception as e:
            print(f"FaceLandmarkDetector: Error detecting landmarks: {e}")
            return None

class EARCalculator:
    """Calculates Eye Aspect Ratio (EAR) from eye landmark points"""
    
    @staticmethod
    def calculate_ear(eye_points):
        """
        Calculate EAR for a single eye
        Formula: EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        Where:
        - p1, p4: horizontal eye corners (outer, inner)
        - p2, p3: vertical points on top eyelid
        - p5, p6: vertical points on bottom eyelid
        
        Args:
            eye_points: numpy array of 6 points [p1, p4, p2, p5, p3, p6]
        
        Returns:
            EAR value (float) or None if calculation fails
        """
        if eye_points is None or len(eye_points) < 6:
            return None
        
        try:
            # Extract points
            p1 = eye_points[0]  # outer corner
            p4 = eye_points[1]  # inner corner
            p2 = eye_points[2]  # top1
            p5 = eye_points[3]  # bottom1
            p3 = eye_points[4]  # top2
            p6 = eye_points[5]  # bottom2
            
            # Calculate Euclidean distances
            # Vertical distances (top eyelid to bottom eyelid)
            # Formula: EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
            vertical1 = np.linalg.norm(p2 - p6)  # |p2-p6| (top1 to bottom2)
            vertical2 = np.linalg.norm(p3 - p5)  # |p3-p5| (top2 to bottom1)
            
            # Horizontal distance (corner to corner)
            horizontal = np.linalg.norm(p1 - p4)  # |p1-p4|
            
            # Avoid division by zero
            if horizontal == 0:
                return None
            
            # Calculate EAR
            ear = (vertical1 + vertical2) / (2.0 * horizontal)
            return ear
            
        except Exception as e:
            print(f"EARCalculator: Error calculating EAR: {e}")
            return None
    
    @staticmethod
    def calculate_average_ear(landmarks):
        """
        Calculate average EAR from both eyes
        
        Args:
            landmarks: dict with 'left_eye' and 'right_eye' arrays
        
        Returns:
            Average EAR value (float) or None if calculation fails
        """
        if landmarks is None:
            return None
        
        left_ear = EARCalculator.calculate_ear(landmarks.get('left_eye'))
        right_ear = EARCalculator.calculate_ear(landmarks.get('right_eye'))
        
        # If both eyes calculated successfully, return average
        if left_ear is not None and right_ear is not None:
            return (left_ear + right_ear) / 2.0
        
        # If only one eye calculated, return that value
        if left_ear is not None:
            return left_ear
        if right_ear is not None:
            return right_ear
        
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
                
                # Detect facial landmarks and calculate EAR
                try:
                    landmarks = FaceLandmarkDetector.detect_landmarks(image_data)
                    face_detected = landmarks is not None
                    ear_value = None
                    
                    if landmarks:
                        # Calculate EAR value
                        ear_value = EARCalculator.calculate_average_ear(landmarks)
                        
                        # Blink detection only when session is active
                        if ear_value is not None and blink_state['session_active']:
                            # Blink detection: count when EAR transitions from closed to open
                            is_closed = ear_value <= EAR_BLINK_THRESHOLD
                            
                            # If was closed and now open, increment blink count
                            if blink_state['was_closed'] and not is_closed:
                                blink_state['blink_count'] += 1
                                print(f"Blink detected! Total blinks: {blink_state['blink_count']} (EAR: {ear_value:.3f})")
                            
                            # Update state for next frame
                            blink_state['was_closed'] = is_closed
                    
                    # Log face detection and EAR results (every 10 frames to see results more frequently)
                    if frame_stats['total_received'] % 10 == 0:
                        status = "Face detected" if face_detected else "No face detected"
                        ear_str = f", EAR: {ear_value:.3f}" if ear_value is not None else ""
                        
                        # Add info about which detection method was used
                        detection_method = ""
                        if landmarks:
                            if landmarks.get('eyes_detected', False):
                                detection_method = " [dlib landmarks]"
                            else:
                                detection_method = " [estimated positions]"
                        
                        # Log individual eye EAR values for debugging
                        if landmarks and ear_value is not None:
                            left_ear = EARCalculator.calculate_ear(landmarks.get('left_eye'))
                            right_ear = EARCalculator.calculate_ear(landmarks.get('right_eye'))
                            if left_ear is not None and right_ear is not None:
                                ear_str += f" (L:{left_ear:.3f}, R:{right_ear:.3f})"
                        
                        print(f"Frame {frame_id}: {status}{ear_str}{detection_method} (total received: {frame_stats['total_received']})")
                    
                    # Also log first few frames for debugging
                    if frame_stats['total_received'] <= 5:
                        status = "Face detected" if face_detected else "No face detected"
                        print(f"Frame {frame_id}: {status} (frame #{frame_stats['total_received']})")
                        if landmarks:
                            left_eye = landmarks.get('left_eye')
                            right_eye = landmarks.get('right_eye')
                            eyes_detected = landmarks.get('eyes_detected', False)
                            print(f"  - Eyes actually detected: {eyes_detected}")
                            print(f"  - Left eye points: {len(left_eye) if left_eye is not None else 0} points")
                            print(f"  - Right eye points: {len(right_eye) if right_eye is not None else 0} points")
                            if ear_value is not None:
                                print(f"  - EAR value: {ear_value:.3f}")
                                if not eyes_detected:
                                    print(f"  - WARNING: Using estimated eye positions (actual eyes not detected)")
                                    print(f"  - Estimated positions won't change when blinking - need actual eye detection")
                except Exception as e:
                    print(f"Error during face detection for frame {frame_id}: {e}")
                    face_detected = False
                    ear_value = None
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
                
                # Send response with landmark detection and EAR result
                response = {
                    'status': 'success',
                    'message': f'Frame {frame_id} received',
                    'frame_id': frame_id,
                    'saved': save_frame,
                    'filepath': str(filepath) if filepath else None,
                    'face_detected': face_detected,
                    'ear_value': ear_value
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
        """Custom log format - minimal logging to avoid spam"""
        # Only log errors, suppress normal POST/GET request logs
        message = format % args
        if 'error' in message.lower():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {message}")

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

