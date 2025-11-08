# /system/apps/sudoku/__init__.py
# GitDoku — GitHub-themed Sudoku for Tufty-style MicroPython badge
# Controls:
#   Arrow keys = move cursor
#   A = cycle number (1-9)
#   B = clear cell
#   C = hint
#   HOME or B+C = pause (A=resume, B=title)
#
# Features:
#   - GitHub-dark palette + dev-themed labels
#   - 9x9 Sudoku grid with 3x3 boxes
#   - Three difficulty levels (Easy/Medium/Hard)
#   - Persistent high scores per difficulty
#   - Timer and mistake tracking
#   - Hint system

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
    State.load("sudoku_hiscores", wrap)
    state["hiscores"] = wrap.get("hiscores", [999999, 999999, 999999])
except Exception:
    pass

# ---------- Sudoku generation ----------
def _is_valid(board, row, col, num):
    # Check row
    for x in range(9):
        if board[row][x] == num:
            return False
    # Check column
    for x in range(9):
        if board[x][col] == num:
            return False
    # Check 3x3 box
    start_row, start_col = 3 * (row // 3), 3 * (col // 3)
    for i in range(3):
        for j in range(3):
            if board[start_row + i][start_col + j] == num:
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
    # Fill diagonal 3x3 boxes first
    for box in range(0, 9, 3):
        nums = list(range(1, 10))
        for i in range(9):
            nums[i], nums[_randint(0, 8)] = nums[_randint(0, 8)], nums[i]
        idx = 0
        for i in range(3):
            for j in range(3):
                board[box + i][box + j] = nums[idx]
                idx += 1
    _solve_sudoku(board)
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

def _new_game():
    solution = _generate_full_board()
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
            State.save("sudoku_hiscores", {"hiscores": state["hiscores"]})
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
    return (hasattr(io, "BUTTON_HOME") and _pressed(io.BUTTON_HOME)) or (_pressed(io.BUTTON_B) and _pressed(io.BUTTON_C))

# Action Handlers
# ... (remaining handlers are unchanged) 

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