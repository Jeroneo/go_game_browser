from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import time
import os

app = FastAPI()

# ---------------------------------------------------------
# KataGo GTP Integration
# ---------------------------------------------------------
KATAGO_CMD = [
    "./katago", "gtp", 
    "-model", "model.bin.gz", 
    "-config", "gtp_config.cfg"
]

print("Starting KataGo engine...")
try:
    katago_process = subprocess.Popen(
        KATAGO_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    time.sleep(2) # Give KataGo a moment to load the neural net into memory
    print("KataGo is ready!")
except Exception as e:
    print(f"ERROR starting KataGo: {e}")

def send_gtp_command(command: str) -> str:
    """Sends a command to KataGo via standard input and reads the response."""
    katago_process.stdin.write(command + "\n")
    katago_process.stdin.flush()
    
    response = ""
    while True:
        line = katago_process.stdout.readline()
        if line == "\n":
            break
        response += line
    
    if response.startswith("="):
        return response[1:].strip()
    else:
        raise ValueError(f"KataGo Error: {response.strip()}")

class GameState(BaseModel):
    history: list[str]  
    difficulty: str     
    board_size: int = 9 

# Serve the Frontend HTML
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

# AI Compute Endpoint
@app.post("/api/move")
async def play_move(state: GameState):
    visits_map = {
        "easy": 10,     
        "medium": 100,  
        "hard": 500    
    }
    max_visits = visits_map.get(state.difficulty, 100)

    try:
        # Sync board state
        send_gtp_command(f"boardsize {state.board_size}")
        send_gtp_command("clear_board")
        send_gtp_command(f"kata-set-param maxVisits {max_visits}")

        # Replay history
        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            color = colors[idx % 2]
            send_gtp_command(f"play {color} {move}")

        # Calculate AI move based on whose turn it is
        ai_color = colors[len(state.history) % 2]
        ai_move = send_gtp_command(f"genmove {ai_color}")

        return {"ai_move": ai_move}

    except Exception as e:
        print(f"Error communicating with KataGo: {e}")
        return {"ai_move": "PASS"}