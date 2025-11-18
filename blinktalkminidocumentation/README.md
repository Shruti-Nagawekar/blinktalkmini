# BlinkTalk - Mac to iPhone Communication Setup

This project enables communication between a Mac server and iPhone client for frame/image processing.

## Network Configuration

- **Mac IP**: `100.70.127.109`
- **iPhone IP**: `100.70.127.141`
- **Server Port**: `8080`

## Setup Instructions

### 1. Mac Server Setup

1. Make sure Python 3 is installed:
   ```bash
   python3 --version
   ```

2. Navigate to the project directory:
   ```bash
   cd /Users/shruti/Desktop/blinktalkmini
   ```

3. Start the server:
   ```bash
   python3 server.py
   ```

4. You should see:
   ```
   🚀 BlinkTalk Server started
   📡 Listening on 100.70.127.109:8080
   📁 Frames will be saved to: /path/to/received_frames
   ```

5. Test the server (in another terminal):
   ```bash
   curl http://100.70.127.109:8080/health
   ```

### 2. iPhone App Setup

1. Open the project in Xcode:
   ```bash
   open blinktalkminiswift/blinktalkminiswift.xcodeproj
   ```

2. **Important**: Configure Info.plist for local network access:
   - The `Info.plist` file has been created with necessary permissions
   - In Xcode, go to your target's Build Settings
   - Find "Info.plist File" and set it to: `blinktalkminiswift/Info.plist`
   - OR disable "Generate Info.plist File" and use the custom one

3. Build and run the app on your iPhone

### 3. Using the NetworkManager

The `NetworkManager` class is available in your Swift code:

```swift
import SwiftUI

// Check server connection
NetworkManager.shared.checkServerConnection { success, message in
    print("Connection: \(success) - \(message)")
}

// Send a frame (UIImage)
let image = UIImage(named: "test") // or capture from camera
NetworkManager.shared.sendFrame(image) { success, message in
    if success {
        print("Frame sent: \(message)")
    } else {
        print("Error: \(message)")
    }
}
```

## Server API

### POST `/`
Sends a frame to the server.

**Request Body:**
```json
{
  "frame": "base64_encoded_image_data",
  "timestamp": "2025-01-16T10:30:00Z",
  "frame_id": "unique_frame_id"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Frame frame_id received and saved",
  "filepath": "/path/to/received_frames/frame_xxx.jpg"
}
```

### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "running",
  "server_ip": "100.70.127.109",
  "port": 8080
}
```

## Received Frames

Frames sent from the iPhone are automatically saved to the `received_frames/` directory in the project root with the naming format:
```
frame_{frame_id}_{timestamp}.jpg
```

## Troubleshooting

### Server won't start
- Check if port 8080 is already in use: `lsof -i :8080`
- Make sure your Mac's firewall allows connections on port 8080
- Verify the IP address is correct: `ifconfig` or `ipconfig getifaddr en0`

### iPhone can't connect to server
- Ensure both devices are on the same network
- Check that the Mac server is running
- Verify the IP address in `NetworkManager.swift` matches your Mac's IP
- Make sure Info.plist has local network permissions configured
- Test connection: `curl http://100.70.127.109:8080/health` from iPhone's network

### Permission errors on iOS
- iOS 14+ requires explicit local network permissions
- Make sure `NSLocalNetworkUsageDescription` is set in Info.plist
- Check that `NSAllowsLocalNetworking` is set to `true`

## Next Steps

- Integrate camera capture in the iOS app
- Add frame processing logic on the Mac server
- Implement real-time frame streaming
- Add error handling and retry logic

