from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
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

print("Starting KataGo engine...")
katago_process = subprocess.Popen(
    KATAGO_CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL, # We drop stderr so the buffer doesn't fill up and freeze KataGo
    text=True,
    bufsize=1
)
time.sleep(2) # Give KataGo a moment to load the neural net into memory

def send_gtp_command(command: str) -> str:
    """Sends a command to KataGo and safely reads the standard GTP response."""
    katago_process.stdin.write(command + "\n")
    katago_process.stdin.flush()
    
    response = ""
    while True:
        line = katago_process.stdout.readline()
        if line == "":
            raise ValueError("KataGo engine stopped running.")
        if line == "\n":
            if response != "":
                break # A blank line signifies the end of the GTP response block
            else:
                continue # Ignore leading empty lines
        response += line
    
    # GTP success responses start with '='. Errors start with '?'
    if response.startswith("="):
        return response[1:].strip()
    else:
        raise ValueError(f"KataGo rejected '{command}': {response.strip()}")

class GameState(BaseModel):
    history: list[str]  
    difficulty: str     
    board_size: int = 19 

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.post("/api/move")
async def play_move(state: GameState):
    visits_map = {
        "easy": 10,     
        "medium": 100,  
        "hard": 500    
    }
    max_visits = visits_map.get(state.difficulty, 100)

    try:
        # 1. Clear the board BEFORE resizing, and once more after just to be safe
        send_gtp_command("clear_board")
        send_gtp_command(f"boardsize {state.board_size}")
        send_gtp_command("clear_board")
        
        # 2. Try to set difficulty, but gracefully ignore if KataGo rejects runtime parameter changes
        try:
            send_gtp_command(f"kata-set-param maxVisits {max_visits}")
        except Exception as e:
            print(f"Non-fatal warning: {e}")

        # 3. Replay history to sync the board
        colors = ["black", "white"]
        for idx, move in enumerate(state.history):
            color = colors[idx % 2]
            send_gtp_command(f"play {color} {move}")

        # 4. Generate AI move
        ai_color = colors[len(state.history) % 2]
        ai_move = send_gtp_command(f"genmove {ai_color}")

        return {"ai_move": ai_move}

    except Exception as e:
        print(f"Backend Game Error: {e}")
        return {"ai_move": "PASS"}
