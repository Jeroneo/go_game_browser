from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import threading
import time

app = FastAPI()

# ---------------------------------------------------------
# KataGo GTP Integration
# ---------------------------------------------------------
KATAGO_CMD = [
    "./katago", "gtp",
    "-model", "model.bin.gz",
    "-config", "gtp_config.cfg"
]

# Lock to ensure only one GTP command is in-flight at a time.
# Without this, concurrent requests corrupt the stdin/stdout pipe.
katago_lock = threading.Lock()
katago_process = None


def start_katago() -> subprocess.Popen:
    """Spawns a fresh KataGo subprocess and returns it."""
    print("Starting KataGo engine...")
    proc = subprocess.Popen(
        KATAGO_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    time.sleep(2)  # Give KataGo time to load the neural network

    if proc.poll() is not None:
        error_output = proc.stderr.read()
        print("========================================")
        print("FATAL ERROR: KataGo crashed on startup!")
        print(error_output)
        print("========================================")

    return proc


def get_katago() -> subprocess.Popen:
    """Returns a live KataGo process, restarting it if it has crashed."""
    global katago_process
    if katago_process is None or katago_process.poll() is not None:
        print("KataGo is not running — restarting...")
        katago_process = start_katago()
    return katago_process


def send_gtp_command(command: str) -> str:
    """
    Sends a GTP command to KataGo and reads the response.
    Thread-safe: acquires katago_lock for the full send-receive cycle.
    """
    with katago_lock:
        proc = get_katago()

        proc.stdin.write(command + "\n")
        proc.stdin.flush()

        response = ""
        while True:
            line = proc.stdout.readline()
            if line == "":
                raise ValueError("KataGo engine stopped responding.")
            if line == "\n":
                if response != "":
                    break
                else:
                    continue
            response += line

    if response.startswith("="):
        return response[1:].strip()
    else:
        raise ValueError(f"KataGo rejected '{command}': {response.strip()}")


# Initialise on startup
katago_process = start_katago()


class GameState(BaseModel):
    history: list[str]
    difficulty: str
    board_size: int = 19


@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")


@app.post("/api/move")
async def play_move(state: GameState):
    visits_map = {"easy": 10, "medium": 100, "hard": 500}
    max_visits = visits_map.get(state.difficulty, 100)

    try:
        send_gtp_command("clear_board")
        send_gtp_command(f"boardsize {state.board_size}")
        try:
            send_gtp_command(f"kata-set-param maxVisits {max_visits}")
        except Exception:
            pass  # Non-fatal: older KataGo builds may not support this param

        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            send_gtp_command(f"play {colors[idx % 2]} {move}")

        ai_color = colors[len(state.history) % 2]
        ai_move = send_gtp_command(f"genmove {ai_color}")

        score = None

        if "RESIGN" in ai_move.upper():
            winner = "W" if ai_color == "black" else "B"
            score = f"{winner}+R"

        elif "PASS" in ai_move.upper():
            score = send_gtp_command("final_score")
            # `final_score` can return "PASS" when territory is ambiguous;
            # fall back to KataGo's score estimation in that case.
            if not score or score.upper() == "PASS":
                score = send_gtp_command("kata-compute-score")

        return {"ai_move": ai_move, "score": score}

    except Exception as e:
        print(f"Backend error: {e}")
        return {"ai_move": "PASS", "score": "B+0.5"}