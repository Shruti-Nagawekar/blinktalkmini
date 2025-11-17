# Blink Detection Implementation Plan

## Goal
Implement EAR (Eye Aspect Ratio) based blink detection with threshold 0-0.2, count blinks per session, and display results at session end.

## Overview
- Navigate from HomeView "Continue" button to BlinkDetectionView
- Show live camera preview on blink detection page
- Calculate EAR value for each frame from facial landmarks
- Count blinks when EAR transitions from ≤0.2 (closed) to >0.2 (open)
- Track blink count during active session (server-side)
- Start sending frames only after "Start Session" button is pressed
- Display final blink count only after "End Session" button is pressed

## Technical Approach

### 1. EAR Calculation
**Formula**: `EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)`
- p1, p4: horizontal eye corners (left, right)
- p2, p3: vertical points on top eyelid
- p5, p6: vertical points on bottom eyelid
- Calculate for both eyes, average the result

### 2. Blink Detection Logic
- **Threshold**: EAR ≤ 0.2 = eyes closed, EAR > 0.2 = eyes open
- **Blink counting**: Count a blink when EAR transitions from ≤0.2 to >0.2
- **State tracking**: Track previous EAR state (closed/open), increment count on closed→open transition
- **No debouncing needed**: Natural state transition prevents duplicate counts

### 3. Implementation Location
**Server-side (Python)** - DECIDED
- Process frames on Mac server using OpenCV/dlib
- Return EAR value + blink status in response
- All blink detection logic handled server-side

## Components Needed

### Server (Python)
1. **Facial Landmark Detection**
   - Use dlib or MediaPipe for 68-point facial landmarks
   - Extract eye region coordinates

2. **EAR Calculator**
   - Function to compute EAR from landmark points
   - Handle missing/partial face detection gracefully

3. **Blink Detector**
   - Track previous EAR state: `was_closed` (True if EAR ≤ 0.2)
   - On each frame: if `was_closed=True` and current EAR > 0.2, increment blink count
   - Update `was_closed` state after checking

4. **Session Management**
   - Track session start/end (initialize on first frame after session start)
   - Maintain blink count per session
   - Endpoint: `POST /start_session` (optional, or auto-start on first frame)
   - Endpoint: `POST /end_session` returns final count

### Client (Swift)
1. **Navigation**
   - HomeView "Continue" button navigates to BlinkDetectionView
   - Use NavigationLink
2. **Session State**
   - `@State var isSessionActive: Bool = false` (frames sent only when true)
   - `@State var finalBlinkCount: Int = 0`
   - `@State var showResults: Bool = false`
   - `@State var cameraPermissionGranted: Bool = false`

3. **Camera Integration**
   - Use AVFoundation (AVCaptureSession) for camera access
   - Display live camera preview using AVCaptureVideoPreviewLayer or CameraPreview SwiftUI wrapper
   - Capture frames from camera output delegate
   - Send frames to server only when `isSessionActive == true`

4. **UI Components**
   - Live camera preview (always visible when on page)
   - "Start Session" button (enables frame sending, starts session on server)
   - "End Session" button (stops frame sending, triggers final count request)
   - Results view showing final blink count (displayed after session ends, overlays or replaces buttons)

5. **Response Handling**
   - On "Start Session": Begin sending frames to server, server initializes session
   - During session: Send frames continuously, server handles blink counting
   - On "End Session": Stop sending frames, call `/end_session` endpoint, display returned count

## API Changes

### Server Response (Enhanced)
```json
{
  "status": "success",
  "ear_value": 0.15,
  "frame_id": "xxx"
}
```
Note: Server tracks blink count internally, not returned per frame.

### New Endpoint: `POST /end_session`
Request body: `{}` (empty or optional session_id)
Response:
```json
{
  "status": "success",
  "total_blinks": 12,
  "session_duration": 45.2
}
```

## Implementation Steps

1. **Phase 1**: Create BlinkDetectionView SwiftUI view with navigation from HomeView
2. **Phase 2**: Integrate AVFoundation camera capture and preview in BlinkDetectionView
3. **Phase 3**: Add facial landmark detection to server
4. **Phase 4**: Implement EAR calculation function on server
5. **Phase 5**: Build blink detection state machine on server
6. **Phase 6**: Add session management endpoints (start/end) on server
7. **Phase 7**: Add "Start Session" and "End Session" buttons to BlinkDetectionView
8. **Phase 8**: Implement frame sending logic (only when session active)
9. **Phase 9**: Integrate end-session API call and display final count
10. **Phase 10**: Test and tune threshold if needed

## Considerations
- **Performance**: Process every Nth frame (e.g., every 3rd) to reduce load
- **Edge cases**: Handle face not detected, partial occlusion (skip frame, don't count)
- **Session scope**: Current session only, no persistence/history
- **State reset**: Reset blink count and `was_closed` state when new session starts
- **Camera permissions**: Request camera access on BlinkDetectionView appear
- **Frame rate**: Limit frame sending rate (e.g., 10-15 fps) to avoid overwhelming server
- **UI layout**: Camera preview should fill most of screen, buttons at bottom

