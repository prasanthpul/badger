# /system/apps/gitoku/__init__.py
# GitDoku — GitHub-themed Sudoku for Tufty-style MicroPython badge
# Controls:
#   UP/DOWN = move cursor up/down
#   A = move cursor left
#   C = move cursor right
#   B = cycle number (1→2→3...→9→clear)
#   B+C = pause (A=resume, B=title)
#
# Features:
#   - GitHub-dark palette + dev-themed labels
#   - 9x9 Sudoku grid with 3x3 boxes
#   - Three difficulty levels (Easy/Medium/Hard)
#   - Persistent high scores per difficulty
#   - Timer and mistake tracking

from badgeware import screen, io, brushes, shapes, PixelFont, State
import urandom

# ---------- Safe RNG ----------
def _getrandbits(n):
    try:
        return urandom.getrandbits(n)
    except AttributeError:
        s = _rng_state.get("s", (io.ticks & 0x7fffffff) ^ 0xB5297A4D)
        s = (1103515245 * s + 12345) & 0x7fffffff
        _rng_state["s"] = s
        return s & ((1 << min(n, 24)) - 1)

def _randint(a, b):
    span = (b - a + 1)
    r = _getrandbits(30)
    return a + (r % span)

_rng_state = {"s": (io.ticks & 0x7fffffff) ^ 0x1f123bb5}

# ---------- Display ----------
W, H = 160, 120
CELL = 10
GRID_X = 8
GRID_Y = 10
SIDE_X = GRID_X + 9*CELL + 6

# ---------- GitHub palette ----------
COL_BG = brushes.color(13, 17, 23)
COL_GRID = brushes.color(48, 54, 61)
COL_TEXT = brushes.color(240, 246, 252)
COL_DIM = brushes.color(139, 148, 158)
COL_CURSOR = brushes.color(191, 128, 255)
COL_GIVEN = brushes.color(70, 212, 143)
COL_ERROR = brushes.color(255, 121, 135)
COL_HINT = brushes.color(90, 150, 255)

# ---------- Font ----------
def _load_font():
    for path in ("/system/assets/fonts/tiny.ppf", "/system/assets/fonts/6x8.ppf", "/system/assets/fonts/ark.ppf"):
        try:
            screen.font = PixelFont.load(path)
            return
        except Exception:
            pass
_load_font()

# ---------- Game state ----------
state = {
    "screen": "title",
    "difficulty": 0,  # 0=Easy, 1=Medium, 2=Hard
    "board": None,
    "solution": None,
    "given": None,
    "cursor_x": 0,
    "cursor_y": 0,
    "mistakes": 0,
    "time": 0,
    "start_time": 0,
    "hiscores": [999999, 999999, 999999],
    "last_btn": 0,
    "btn_delay": 200,
}

# Load high scores
try:
    wrap = {"hiscores": [999999, 999999, 999999]}
    State.load("gitoku_hiscores", wrap)
    state["hiscores"] = wrap.get("hiscores", [999999, 999999, 999999])
except Exception:
    pass

# ---------- Sudoku generation ----------
def _is_valid(board, row, col, num):
    # Check row (skip the current cell)
    for x in range(9):
        if x != col and board[row][x] == num:
            return False
    # Check column (skip the current cell)
    for x in range(9):
        if x != row and board[x][col] == num:
            return False
    # Check 3x3 box (skip the current cell)
    start_row, start_col = 3 * (row // 3), 3 * (col // 3)
    for i in range(3):
        for j in range(3):
            r, c = start_row + i, start_col + j
            if (r != row or c != col) and board[r][c] == num:
                return False
    return True

def _solve_sudoku(board):
    for row in range(9):
        for col in range(9):
            if board[row][col] == 0:
                for num in range(1, 10):
                    if _is_valid(board, row, col, num):
                        board[row][col] = num
                        if _solve_sudoku(board):
                            return True
                        board[row][col] = 0
                return False
    return True

def _generate_full_board():
    board = [[0]*9 for _ in range(9)]
    # Fill diagonal 3x3 boxes first (these don't overlap with each other)
    for box in range(0, 9, 3):
        nums = list(range(1, 10))
        # Shuffle the numbers
        for i in range(8, 0, -1):
            j = _randint(0, i)
            nums[i], nums[j] = nums[j], nums[i]
        idx = 0
        for i in range(3):
            for j in range(3):
                board[box + i][box + j] = nums[idx]
                idx += 1
    # Solve the rest of the board
    if not _solve_sudoku(board):
        # If solving fails, try again recursively
        return _generate_full_board()
    return board

def _remove_numbers(board, difficulty):
    # Easy=40 removed, Medium=50, Hard=60
    remove_count = [40, 50, 60][difficulty]
    cells = [(r, c) for r in range(9) for c in range(9)]
    for _ in range(remove_count):
        if not cells:
            break
        idx = _randint(0, len(cells) - 1)
        r, c = cells.pop(idx)
        board[r][c] = 0

def _validate_board(board):
    """Check if board has valid sudoku (no duplicates in rows/cols/boxes)"""
    for row in range(9):
        for col in range(9):
            num = board[row][col]
            if num != 0:
                # Temporarily clear cell
                board[row][col] = 0
                # Check if placing it again would be valid
                if not _is_valid(board, row, col, num):
                    board[row][col] = num
                    return False
                board[row][col] = num
    return True

def _new_game():
    solution = _generate_full_board()
    # Validate the solution
    if not _validate_board(solution):
        # If invalid, try again
        return _new_game()
    board = [row[:] for row in solution]
    _remove_numbers(board, state["difficulty"])
    given = [[board[r][c] != 0 for c in range(9)] for r in range(9)]
    state["board"] = board
    state["solution"] = solution
    state["given"] = given
    state["cursor_x"] = 0
    state["cursor_y"] = 0
    state["mistakes"] = 0
    state["start_time"] = io.ticks
    state["time"] = 0

# ---------- Game logic ----------
def _is_complete():
    for r in range(9):
        for c in range(9):
            if state["board"][r][c] != state["solution"][r][c]:
                return False
    return True

def _place_number(num):
    r, c = state["cursor_y"], state["cursor_x"]
    if state["given"][r][c]:
        return
    state["board"][r][c] = num
    if num != 0 and num != state["solution"][r][c]:
        state["mistakes"] += 1
        _toast("Merge conflict!")
    if _is_complete():
        _to_gameover()

def _hint():
    r, c = state["cursor_y"], state["cursor_x"]
    if not state["given"][r][c]:
        state["board"][r][c] = state["solution"][r][c]
        _toast("Hint applied!")
        if _is_complete():
            _to_gameover()

def _move_cursor(dx, dy):
    state["cursor_x"] = (state["cursor_x"] + dx) % 9
    state["cursor_y"] = (state["cursor_y"] + dy) % 9

# ---------- Screen transitions ----------
def _to_title():
    state["screen"] = "title"

def _to_game():
    state["screen"] = "play"
    _new_game()

def _to_pause():
    state["screen"] = "pause"

def _to_gameover():
    state["screen"] = "gameover"
    if state["time"] < state["hiscores"][state["difficulty"]]:
        state["hiscores"][state["difficulty"]] = state["time"]
        try:
            State.save("gitoku_hiscores", {"hiscores": state["hiscores"]})
        except Exception:
            pass

# ---------- Toast ----------
_toast_msg = {"t": 0, "txt": ""}

def _toast(s):
    _toast_msg["t"] = io.ticks
    _toast_msg["txt"] = s

def _draw_toast():
    if not _toast_msg["txt"]:
        return
    if io.ticks - _toast_msg["t"] > 1400:
        _toast_msg["txt"] = ""
        return
    screen.brush = brushes.color(0, 0, 0, 160)
    screen.draw(shapes.rectangle(GRID_X, GRID_Y + 40, 90, 14))
    screen.brush = COL_TEXT
    screen.text(_toast_msg["txt"], GRID_X + 4, GRID_Y + 42)

# ---------- Input ----------
def _pressed(btn):
    return btn in io.pressed

def _pause_pressed():
    return (hasattr(io, "BUTTON_HOME") and _pressed(io.BUTTON_HOME)) or (io.BUTTON_B in io.held and io.BUTTON_C in io.held)

# ---------- Input Handlers ----------
def _handle_title():
    # Handle difficulty selection
    if _pressed(io.BUTTON_UP):
        state["difficulty"] = (state["difficulty"] - 1) % 3
    elif _pressed(io.BUTTON_DOWN):
        state["difficulty"] = (state["difficulty"] + 1) % 3
    elif _pressed(io.BUTTON_B):
        _to_game()

def _handle_play():
    # Update timer
    state["time"] = (io.ticks - state["start_time"]) // 1000
    
    # Check for pause (B+C held together)
    if _pause_pressed():
        _to_pause()
        return
    
    # Movement - all directions use single-step pressed
    if _pressed(io.BUTTON_UP):
        _move_cursor(0, -1)
    elif _pressed(io.BUTTON_DOWN):
        _move_cursor(0, 1)
    elif _pressed(io.BUTTON_A):
        # A = move left
        _move_cursor(-1, 0)
    elif _pressed(io.BUTTON_C):
        # C = move right
        _move_cursor(1, 0)
    elif _pressed(io.BUTTON_B):
        # B = cycle through numbers, skipping those given (green) in same row/column
        r, c = state["cursor_y"], state["cursor_x"]
        if not state["given"][r][c]:
            current = state["board"][r][c]
            # Collect numbers that are given (green) in same row or column
            skip_numbers = set()
            for x in range(9):
                # Check row for given numbers
                if state["given"][r][x] and state["board"][r][x] != 0:
                    skip_numbers.add(state["board"][r][x])
                # Check column for given numbers
                if state["given"][x][c] and state["board"][x][c] != 0:
                    skip_numbers.add(state["board"][x][c])
            
            # Try next numbers until we find one not in skip list
            for attempt in range(1, 11):  # Max 10 attempts (1-9, then 0)
                next_num = (current + attempt) % 10
                # Allow 0 (clear) or numbers not in the skip list
                if next_num == 0 or next_num not in skip_numbers:
                    _place_number(next_num)
                    break

def _handle_pause():
    if _pressed(io.BUTTON_A):
        state["screen"] = "play"
    elif _pressed(io.BUTTON_B):
        _to_title()

def _handle_gameover():
    if _pressed(io.BUTTON_A):
        _to_game()
    elif _pressed(io.BUTTON_B):
        _to_title()

# ---------- Drawing Functions ----------
def _draw_title():
    screen.brush = COL_BG
    screen.clear()
    
    # Title
    screen.brush = COL_TEXT
    screen.text("GitDoku", W//2 - 24, 10)
    
    # Difficulty options
    difficulties = ["Easy", "Medium", "Hard"]
    for i, diff in enumerate(difficulties):
        y = 35 + i * 15
        if i == state["difficulty"]:
            screen.brush = COL_CURSOR
            screen.draw(shapes.rectangle(20, y - 2, 120, 12))
        screen.brush = COL_TEXT if i == state["difficulty"] else COL_DIM
        screen.text(diff, 40, y)
        
        # Show high score
        hs = state["hiscores"][i]
        hs_text = f"{hs}s" if hs < 999999 else "--"
        screen.text(hs_text, 100, y)
    
    # Instructions
    screen.brush = COL_DIM
    screen.text("UP/DOWN: Select", 20, 95)
    screen.text("B: Start", 20, 105)

def _draw_grid():
    screen.brush = COL_BG
    screen.clear()
    
    # Draw grid lines
    for i in range(10):
        thickness = 2 if i % 3 == 0 else 1
        screen.brush = COL_GRID
        # Vertical lines
        x = GRID_X + i * CELL
        screen.draw(shapes.rectangle(x, GRID_Y, thickness, 9 * CELL))
        # Horizontal lines
        y = GRID_Y + i * CELL
        screen.draw(shapes.rectangle(GRID_X, y, 9 * CELL, thickness))

def _draw_board():
    for r in range(9):
        for c in range(9):
            x = GRID_X + c * CELL
            y = GRID_Y + r * CELL
            
            # Highlight cursor with bright yellow background
            if r == state["cursor_y"] and c == state["cursor_x"]:
                screen.brush = brushes.color(255, 200, 0, 180)  # Bright yellow/gold
                screen.draw(shapes.rectangle(x + 1, y + 1, CELL - 1, CELL - 1))
            
            # Draw number
            num = state["board"][r][c]
            if num != 0:
                if state["given"][r][c]:
                    screen.brush = COL_GIVEN
                elif num != state["solution"][r][c]:
                    screen.brush = COL_ERROR
                else:
                    screen.brush = COL_TEXT
                screen.text(str(num), x + 3, y)

def _draw_sidebar():
    # Time
    screen.brush = COL_TEXT
    screen.text("Time:", SIDE_X, 20)
    screen.text(f"{state['time']}s", SIDE_X, 30)
    
    # Mistakes
    screen.brush = COL_ERROR if state["mistakes"] > 0 else COL_TEXT
    screen.text("Errors:", SIDE_X, 50)
    screen.text(str(state["mistakes"]), SIDE_X, 60)
    
    # Controls
    screen.brush = COL_DIM
    screen.text("B:Num", SIDE_X, 80)

def _draw_pause():
    screen.brush = COL_BG
    screen.clear()
    
    screen.brush = COL_TEXT
    screen.text("PAUSED", W//2 - 24, 40)
    
    screen.brush = COL_DIM
    screen.text("A: Resume", 40, 70)
    screen.text("B: Title", 40, 85)

def _draw_gameover():
    screen.brush = COL_BG
    screen.clear()
    
    screen.brush = COL_GIVEN
    screen.text("COMPLETE!", W//2 - 36, 30)
    
    screen.brush = COL_TEXT
    screen.text(f"Time: {state['time']}s", 40, 55)
    screen.text(f"Errors: {state['mistakes']}", 40, 70)
    
    if state["time"] == state["hiscores"][state["difficulty"]]:
        screen.brush = COL_HINT
        screen.text("NEW RECORD!", 30, 85)
    
    screen.brush = COL_DIM
    screen.text("A: Retry  B: Title", 20, 105)

# ---------- Main update ----------
def update():
    if state["screen"] == "title":
        _handle_title()
        _draw_title()
    elif state["screen"] == "play":
        _handle_play()
        _draw_grid()
        _draw_board()
        _draw_sidebar()
        _draw_toast()
    elif state["screen"] == "pause":
        _handle_pause()
        _draw_pause()
    elif state["screen"] == "gameover":
        _handle_gameover()
        _draw_gameover()

# Initialize
if state["board"] is None:
    _to_title()