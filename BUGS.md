# Cammy Bugs

## Blocking Bugs

- [x] **FIXED** `server.is_running` is a property, not a method - Called as `is_running()` in `main.py:143` and `main.py:169` causing `TypeError: 'bool' object is not callable`
- [x] **FIXED** Dependency version conflicts - Fixed by installing compatible versions:
  - `tensorflow==2.16.2` (2.21.0 had protobuf compatibility issues)
  - `protobuf==4.25.6` (5.x incompatible with TF 2.16)
  - `ml-dtypes==0.3.2` (0.4.x+ and 0.5.x had attribute errors with jax)
  - `jax==0.4.25` (0.4.38 required ml-dtypes>=0.4.0)
  - `jaxlib==0.4.25` (must match jax version)
  - `mediapipe==0.10.18` (0.10.33 had no `solutions` attribute)

## Non-Blocking Bugs

- [ ] **DeepFace tensorflow compatibility** - Requires `tf-keras` package which creates dependency conflicts with current setup (face recognition won't work until resolved)
- [ ] **pyautogui not available** - Keyboard control actions won't work without it
- [ ] **Camera reader thread exception** - May fail if no camera device available (handled gracefully with logging)

## Notes

- All 75 backend tests pass
- Frontend builds successfully
- Backend starts and runs without errors
- MediaPipe face and hand detection working
- Gesture classification working (rule-based)
- WebSocket and REST server working
