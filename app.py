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
    if katago_process.poll() is not None:
        return "PASS"
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
    """Parses the board from KataGo to handle captures correctly."""
    board_raw = send_gtp_command("showboard")
    stones = {}
    # Regex to find stone positions in KataGo's ASCII output
    # Looks for lines like "19 . . . X O . . ."
    lines = board_raw.split('\n')
    columns = "ABCDEFGHJKLMNOPQRST"
    
    row_num = 19
    for line in lines:
        match = re.search(r'^\s*(\d+)\s+(.+)', line)
        if match:
            current_row = int(match.group(1))
            # Get the grid part and remove spaces
            grid_parts = match.group(2).strip().split(' ')
            grid_parts = [p for p in grid_parts if p in ['.', 'X', 'O', '@', '#']]
            
            for col_idx, char in enumerate(grid_parts):
                if col_idx < 19:
                    coord = f"{columns[col_idx]}{current_row}"
                    if char in ['X', '@']: # Black stone
                        stones[coord] = 'black'
                    elif char in ['O', '#']: # White stone
                        stones[coord] = 'white'
            row_num -= 1
    return stones

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
        except: pass

        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            send_gtp_command(f"play {colors[idx % 2]} {move}")

        ai_color = colors[len(state.history) % 2]
        ai_move = send_gtp_command(f"genmove {ai_color}")
        
        # Sync the board stones (handles captures)
        current_stones = get_current_stones()
        
        score = None
        if "PASS" in ai_move.upper() or "RESIGN" in ai_move.upper():
            score = send_gtp_command("final_score")
            if not score or score == "PASS":
                score = send_gtp_command("kata-compute-score")

        return {"ai_move": ai_move, "stones": current_stones, "score": score}

    except Exception as e:
        print(f"Error: {e}")
        return {"ai_move": "PASS", "stones": {}, "score": "0"}