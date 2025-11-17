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
                
                # Only save to disk if explicitly requested (to avoid disk I/O bottleneck)
                filepath = None
                if save_frame:
                    filename = f"frame_{frame_id}_{timestamp.replace(':', '-').replace('.', '-')}.jpg"
                    filepath = FRAMES_DIR / filename
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                
                frame_stats['total_processed'] += 1
                
                # Send quick response (minimal processing for streaming)
                response = {
                    'status': 'success',
                    'message': f'Frame {frame_id} received',
                    'frame_id': frame_id,
                    'saved': save_frame,
                    'filepath': str(filepath) if filepath else None
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
        """Custom log format - minimal for streaming performance"""
        # Only log errors or every 100th frame to avoid console spam
        if 'error' in format.lower() or frame_stats['total_received'] % 100 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Frames: {frame_stats['total_received']} | {format % args}")

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

