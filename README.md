# Desktop Viewer

View and control your Windows desktop from any browser, anywhere.

## How It Works

- **GitHub Pages** hosts the web viewer (the `index.html` file)
- **Your Windows machine** runs a Python server that captures the screen and streams it
- **A tunnel** (ngrok or Cloudflare) exposes the server to the internet

## Setup (Your Windows Machine)

1. Install Python 3.9+ from [python.org](https://python.org) (check "Add to PATH")

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Start the server:
   ```
   python server.py
   ```
   It will listen on `ws://0.0.0.0:8765`

4. Expose it to the internet. Pick one:

   **Option A - ngrok (easiest):**
   ```
   ngrok tcp 8765
   ```
   ngrok gives you a URL like `0.tcp.ngrok.io:12345`

   **Option B - Cloudflare Tunnel (free, persistent):**
   ```
   cloudflared access tcp --hostname mydesktop.trycloudflare.com --url localhost:8765
   ```

## Deploy the Viewer (GitHub Pages)

1. Create a new GitHub repository (e.g. `desktop-viewer`)
2. Upload the `index.html` file to the repo root
3. Go to **Settings > Pages > Source** and select `main` branch, root `/`
4. Your viewer is live at `https://YOUR_USERNAME.github.io/YOUR_REPO/`

## Use It

1. Open the GitHub Pages URL in your browser
2. Enter the WebSocket URL from your tunnel:
   - ngrok: `wss://0.tcp.ngrok.io:12345`
   - Cloudflare: `wss://mydesktop.trycloudflare.com`
3. Click **Connect**
4. You'll see your live desktop! You can click, type, scroll, and move the mouse.

## Configuration

Edit `server.py` at the top:

| Setting | Default | Description |
|---------|---------|-------------|
| `FPS` | 15 | Frame rate for screen capture |
| `JPEG_QUALITY` | 60 | Quality (1-95, lower = faster) |
| `MONITOR` | 1 | Which monitor to capture (1 = primary) |
| `PORT` | 8765 | WebSocket port |

## Notes

- The viewer works in any modern browser (Chrome, Firefox, Edge, Safari)
- Lower `JPEG_QUALITY` for better performance on slow connections
- `pyautogui` input works best when the target window is in focus on the Windows machine
- For higher fidelity, increase `FPS` and `JPEG_QUALITY` (requires more bandwidth)
