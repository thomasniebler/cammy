# Quickstart Guide

Get Cammy running in 5 minutes.

## Prerequisites

- **Python 3.10+** with `uv` package manager
- **Node.js 18+** (for frontend)
- **Webcam** (built-in or USB)
- **macOS / Linux / Windows**

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/cammy.git
cd cammy

# Install backend dependencies
cd backend
uv pip install -e ".[dev]"

# Install frontend dependencies
cd ../frontend
npm install
```

Or use the Taskfile:

```bash
task install
```

## Step 2: Start the Backend

In a terminal, run:

```bash
cd backend
source .venv/bin/activate
python -m cammy.main
```

Or use Taskfile:

```bash
task dev-backend
```

You should see output like:
```
2024-01-01 12:00:00 | INFO | cammy | CammyApp initialized
2024-01-01 12:00:00 | INFO | cammy | Cammy started successfully
```

## Step 3: Start the Frontend

In another terminal, run:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Step 4: Configure Your First Identity

1. **Start your webcam** - The frontend should show your camera feed
2. **Click "Add Identity"** - Enter your name
3. **Look at the camera** - Ensure your face is visible
4. **The system will capture and enroll your face**

## Step 5: Test Gestures

Try these gestures in front of your camera:

| Gesture | Default Action |
|---------|---------------|
| ✊ Fist | Media pause |
| ✋ Open Palm | Media play |
| 👍 Thumbs Up | Volume up |
| 👎 Thumbs Down | Volume down |
| ✌️ Peace | Next track |

## Troubleshooting

### Camera Not Found

```
Error: No camera available
```

**Solution:** Check that your webcam is connected and not in use by another app.

### Low FPS

If detection is slow, edit `~/.config/cammy/config.json`:

```json
{
  "performance": {
    "tier": "low",
    "target_fps": 15
  }
}
```

### Actions Not Working

Actions require `pyautogui`. Install with:

```bash
uv pip install pyautogui
```

### Permission Denied (Linux)

```bash
# Allow camera access
sudo chmod +777 /dev/video0

# Or check with
ls -la /dev/video*
```

## Next Steps

- [Configure custom gestures](./configuration.md#gesture-mappings)
- [Set up webhook actions](./configuration.md#webhook-actions)
- [Adjust detection thresholds](./configuration.md#detection-settings)

## Quick Commands Reference

```bash
# Start everything
task dev

# Run tests
task test

# Build for production
task build
```
