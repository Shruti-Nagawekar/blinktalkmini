# Blink Duration Tracking Implementation Plan

## Goal
Track how long each blink stays closed and categorize it:
- **S**: Blink duration ≤ 1 second (short)
- **L**: Blink duration between 1-2 seconds (long)
- **X**: Blink duration > 2 seconds (extra long)

Replace the current blink count with a sequence string (e.g., "SLLSX") that accumulates during the session.

## Current State
- Blink detection works: tracks transition from closed (EAR ≤ 0.350) to open (EAR > 0.350)
- Currently counts blinks: `blink_state['blink_count']` increments on each closed→open transition
- Session management: `/start_session` and `/end_session` endpoints exist

## Changes Required

### Server-Side (Python - `server.py`)

1. **Replace blink counting with duration tracking**
   - Remove: `blink_state['blink_count']` 
   - Add: `blink_state['blink_sequence'] = ""` (string to accumulate S/L/X)
   - Add: `blink_state['blink_start_time'] = None` (timestamp when eyes closed)

2. **Track blink start time**
   - When eyes transition from open→closed: record `datetime.now()` in `blink_start_time`
   - When eyes transition from closed→open: calculate duration and categorize

3. **Categorize blink duration**
   - Calculate: `duration = (now - blink_start_time).total_seconds()`
   - If `duration ≤ 1.0`: append "S" to sequence
   - If `1.0 < duration ≤ 2.0`: append "L" to sequence  
   - If `duration > 2.0`: append "X" to sequence
   - Log to console: `"Blink detected: {category} (duration: {duration:.3f}s) | Sequence: {sequence}"`

4. **Update session management**
   - `/start_session`: Initialize `blink_sequence = ""` and `blink_start_time = None`
   - `/end_session`: Return `blink_sequence` instead of `total_blinks` in response

5. **Update response format**
   - `/end_session` response should include:
     ```json
     {
       "status": "success",
       "blink_sequence": "SLLSX",
       "session_duration": 45.2
     }
     ```

### Client-Side (Swift - `BlinkDetectionView.swift`)

1. **Update state variables**
   - Remove: `finalBlinkCount: Int?`
   - Add: `blinkSequence: String? = nil`

2. **Update results display**
   - Replace blink count display with sequence display
   - Show sequence string prominently (e.g., "SLLSX")
   - Optionally show sequence breakdown (count of S, L, X)

3. **Update NetworkManager**
   - Modify `endSession` completion handler to receive `blinkSequence: String?` instead of `blinkCount: Int?`
   - Update response parsing in `NetworkManager.swift` to extract `blink_sequence` field

## Implementation Details

### Blink Duration Tracking Logic

```python
# When eyes transition from open→closed:
if not blink_state['was_closed'] and is_closed:
    blink_state['blink_start_time'] = datetime.now()

# When eyes transition from closed→open:
if blink_state['was_closed'] and not is_closed:
    if blink_state['blink_start_time'] is not None:
        duration = (datetime.now() - blink_state['blink_start_time']).total_seconds()
        
        if duration <= 1.0:
            category = "S"
        elif duration <= 2.0:
            category = "L"
        else:
            category = "X"
        
        blink_state['blink_sequence'] += category
        print(f"Blink detected: {category} (duration: {duration:.3f}s) | Sequence: {blink_state['blink_sequence']}")
    
    blink_state['blink_start_time'] = None  # Reset
```

### Edge Cases
- **Face not detected during blink**: If face is lost while eyes are closed, `blink_start_time` may be set but never cleared. Reset `blink_start_time` when face is not detected.
- **Session ends mid-blink**: If session ends while eyes are closed, the final blink won't be counted (acceptable behavior).
- **Very rapid blinks**: If eyes close and open within the same frame processing cycle, duration will be very small (will be categorized as "S").

## Files to Modify

1. **`blinktalkminipy/server.py`**
   - Update `blink_state` initialization (lines ~36-41)
   - Modify blink detection logic (lines ~474-497)
   - Update `/start_session` endpoint (lines ~374-396)
   - Update `/end_session` endpoint (lines ~398-422)

2. **`blinktalkminiswift/blinktalkminiswift/BlinkDetectionView.swift`**
   - Update state variables (line ~13)
   - Update results display UI (lines ~58-67)
   - Update `endSession` call (line ~125)

3. **`blinktalkminiswift/blinktalkminiswift/NetworkManager.swift`**
   - Update `endSession` method to parse and return `blink_sequence` instead of `blinkCount`

## Testing Considerations
- Test with intentional short blinks (<1s)
- Test with intentional long blinks (1-2s)
- Test with very long blinks (>2s)
- Verify sequence accumulates correctly across multiple blinks
- Verify sequence is returned correctly in `/end_session` response
- Verify sequence displays correctly on client screen

