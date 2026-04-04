from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import time
import re

app = FastAPI()

KATAGO_CMD = ["./katago", "gtp", "-model", "model.bin.gz", "-config", "gtp_config.cfg"]

print("Starting KataGo engine...")
katago_process = subprocess.Popen(
    KATAGO_CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)
time.sleep(2)

def send_gtp_command(command: str) -> str:
    if katago_process.poll() is not None: return "PASS"
    katago_process.stdin.write(command + "\n")
    katago_process.stdin.flush()
    response = ""
    while True:
        line = katago_process.stdout.readline()
        if line == "": break
        if line == "\n":
            if response != "": break
            else: continue
        response += line
    return response[1:].strip() if response.startswith("=") else ""

def get_current_stones():
    """Asks KataGo for the board state and captures/removals."""
    board_raw = send_gtp_command("showboard")
    stones = {}
    lines = board_raw.split('\n')
    columns = "ABCDEFGHJKLMNOPQRST"
    
    for line in lines:
        # Match lines starting with a row number, e.g., "19 . . X O ..."
        match = re.search(r'^\s*(\d+)\s+(.+)', line)
        if match:
            row = int(match.group(1))
            # Clean the row to get only symbols
            symbols = match.group(2).split()
            for col_idx, char in enumerate(symbols):
                if col_idx < 19:
                    coord = f"{columns[col_idx]}{row}"
                    if char in ['X', '@']: stones[coord] = 'black'
                    elif char in ['O', '#']: stones[coord] = 'white'
    return stones

class GameState(BaseModel):
    history: list[str]
    difficulty: str

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.post("/api/move")
async def play_move(state: GameState):
    visits = {"easy": 10, "medium": 100, "hard": 500}.get(state.difficulty, 100)
    try:
        send_gtp_command("clear_board")
        send_gtp_command("boardsize 19")
        try: send_gtp_command(f"kata-set-param maxVisits {visits}")
        except: pass

        for idx, move in enumerate(state.history):
            color = "black" if idx % 2 == 0 else "white"
            send_gtp_command(f"play {color} {move}")

        ai_color = "black" if len(state.history) % 2 == 0 else "white"
        ai_move = send_gtp_command(f"genmove {ai_color}")
        
        # Get the official board state (after captures)
        stones = get_current_stones()
        
        score = None
        if ai_move.upper() in ["PASS", "RESIGN"]:
            score = send_gtp_command("final_score")
            if not score or "PASS" in score: score = send_gtp_command("kata-compute-score")

        return {"ai_move": ai_move, "stones": stones, "score": score}
    except Exception as e:
        return {"ai_move": "PASS", "stones": {}, "score": "Error"}