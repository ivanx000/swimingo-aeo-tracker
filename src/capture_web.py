"""Local web-based manual capture tool for platforms that can't be automated
(ChatGPT, Perplexity, Copilot, Google AI Overviews).

Replaces the terminal-based flow in manual_capture.py (still available,
see its docstring) with a single local web page: paste the platform's
response into a textarea and click "Save & Next". No terminal/browser
window-switching, no END sentinel to type, and a plain textarea handles
long multi-paragraph AI Overview responses cleanly.

Reuses manual_capture's question loading and result saving so the output
is byte-for-byte the same schema/file layout the parse/report pipeline
already expects.

Usage: python capture_web.py <platform> [--port 8765] [--no-browser]
"""
import argparse
import json
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import manual_capture

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AEO capture</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  header {
    padding: 12px 20px;
    border-bottom: 1px solid #8884;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }
  header h1 { font-size: 15px; margin: 0; text-transform: capitalize; }
  #progress { font-size: 13px; opacity: 0.7; }
  main { flex: 1; display: flex; flex-direction: column; padding: 16px 20px; min-height: 0; }
  #meta { font-size: 12px; opacity: 0.65; margin-bottom: 4px; }
  #question { font-size: 18px; font-weight: 600; margin: 0 0 12px 0; }
  textarea {
    flex: 1;
    width: 100%;
    min-height: 0;
    font-size: 14px;
    font-family: ui-monospace, monospace;
    padding: 10px;
    resize: none;
  }
  #controls { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
  button {
    font-size: 14px;
    padding: 10px 18px;
    cursor: pointer;
  }
  #save { font-weight: 600; }
  #hint { font-size: 12px; opacity: 0.6; }
  #status { font-size: 13px; opacity: 0.75; }
  #done-screen { display: none; margin: auto; text-align: center; font-size: 16px; }
</style>
</head>
<body>
<header>
  <h1 id="platform-name">capture</h1>
  <span id="progress"></span>
</header>
<main id="capture-screen">
  <div id="meta"></div>
  <p id="question"></p>
  <textarea id="response" placeholder="Paste the platform's full response here..." autofocus></textarea>
  <div id="controls">
    <button id="save">Save &amp; Next</button>
    <button id="skip">Skip</button>
    <span id="status"></span>
    <span id="hint" style="margin-left:auto">Cmd/Ctrl+Enter to save</span>
  </div>
</main>
<div id="done-screen"></div>
<script>
let currentQuestionId = null;

async function loadState() {
  const res = await fetch("/api/state");
  const state = await res.json();
  render(state);
}

function render(state) {
  document.getElementById("platform-name").textContent = state.platform;
  document.getElementById("progress").textContent =
    state.finished
      ? `${state.done} of ${state.total} done`
      : `Question ${state.done + 1} of ${state.total}`;

  if (state.finished) {
    document.getElementById("capture-screen").style.display = "none";
    const doneScreen = document.getElementById("done-screen");
    doneScreen.style.display = "block";
    doneScreen.textContent =
      `All ${state.total} questions captured for ${state.platform} on ${state.date}.`;
    return;
  }

  document.getElementById("capture-screen").style.display = "flex";
  document.getElementById("done-screen").style.display = "none";

  const q = state.question;
  currentQuestionId = q.id;
  document.getElementById("meta").textContent =
    `Q${q.id} — ${q.city} / ${q.persona} / ${q.type}`;
  document.getElementById("question").textContent = q.question;
  const box = document.getElementById("response");
  box.value = "";
  box.focus();
  document.getElementById("status").textContent = "";
}

async function submit(path) {
  const box = document.getElementById("response");
  const body = { question_id: currentQuestionId, raw_response: box.value };
  document.getElementById("status").textContent = "Saving...";
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    document.getElementById("status").textContent = err.error || "Error saving.";
    return;
  }
  const state = await res.json();
  render(state);
}

document.getElementById("save").addEventListener("click", () => submit("/api/save"));
document.getElementById("skip").addEventListener("click", () => submit("/api/skip"));
document.getElementById("response").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    submit("/api/save");
  }
});

loadState();
</script>
</body>
</html>
"""


def _build_state(platform: str) -> dict:
    """Compute the current progress/next-question payload for a platform."""
    questions = manual_capture.load_questions()
    today = date.today().isoformat()
    path = manual_capture.output_path(today, platform)
    results = manual_capture.load_existing_results(path)
    done_ids = {r["question_id"] for r in results}
    remaining = [q for q in questions if q["id"] not in done_ids]

    total = len(questions)
    done = total - len(remaining)
    return {
        "platform": platform,
        "date": today,
        "total": total,
        "done": done,
        "finished": not remaining,
        "question": remaining[0] if remaining else None,
    }


class CaptureHandler(BaseHTTPRequestHandler):
    platform = None  # bound per-instance by make_handler()

    def _send_json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = PAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/state":
            self._send_json(_build_state(self.platform))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/save", "/api/skip"):
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=400)
            return

        question_id = payload.get("question_id")
        if not isinstance(question_id, int):
            self._send_json({"error": "question_id is required."}, status=400)
            return

        if parsed.path == "/api/save":
            raw_response = (payload.get("raw_response") or "").strip()
            if not raw_response:
                self._send_json({"error": "Response is empty. Use Skip instead."}, status=400)
                return

            today = date.today().isoformat()
            out_path = manual_capture.output_path(today, self.platform)
            results = manual_capture.load_existing_results(out_path)
            results = [r for r in results if r["question_id"] != question_id]
            results.append(
                {
                    "question_id": question_id,
                    "platform": self.platform,
                    "date": today,
                    "raw_response": raw_response,
                }
            )
            manual_capture.save_results(out_path, results)

        # /api/skip just falls through without saving, moving on to the next question.
        self._send_json(_build_state(self.platform))

    def log_message(self, format: str, *args) -> None:
        pass  # keep the terminal quiet; progress is visible in the browser


def make_handler(platform: str) -> type:
    return type("BoundCaptureHandler", (CaptureHandler,), {"platform": platform})


def run(platform: str, port: int = 8765, open_browser: bool = True) -> None:
    """Serve the capture page for one platform until interrupted."""
    if platform not in manual_capture.PLATFORMS:
        raise ValueError(f"Unknown platform '{platform}'. Choose from: {manual_capture.PLATFORMS}")

    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(platform))
    url = f"http://127.0.0.1:{port}/"

    print(f"Capturing responses for: {platform}")
    print(f"Open {url} in your browser" + (" (opening automatically)..." if open_browser else "..."))
    print("Progress is saved after every question. Press Ctrl+C to stop; rerun to resume.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Progress saved; reopen to resume.")
    finally:
        server.server_close()


def main() -> None:
    """Standalone entry point: python capture_web.py [platform] [--port N] [--no-browser]"""
    arg_parser = argparse.ArgumentParser(description="Local web-based manual capture tool.")
    arg_parser.add_argument("platform", choices=manual_capture.PLATFORMS, nargs="?")
    arg_parser.add_argument("--port", type=int, default=8765)
    arg_parser.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser.")
    args = arg_parser.parse_args()

    platform = args.platform or manual_capture.select_platform()
    run(platform, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
