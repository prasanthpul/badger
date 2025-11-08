class Sudoku:
    def __init__(self, board=None):
        if board is None:
            self.board = [[0] * 9 for _ in range(9)]  # Empty board
        else:
            self.board = board
    
    def is_valid(self, row, col, num):
        # Check if 'num' is not in the given row
        for x in range(9):
            if self.board[row][x] == num:
                return False
        
        # Check if 'num' is not in the given column
        for x in range(9):
            if self.board[x][col] == num:
                return False
        
        # Check if 'num' is not in the 3x3 box
        start_row, start_col = 3 * (row // 3), 3 * (col // 3)
        for i in range(3):
            for j in range(3):
                if self.board[start_row + i][start_col + j] == num:
                    return False
        
        return True
    
    def solve(self):
        for row in range(9):
            for col in range(9):
                if self.board[row][col] == 0:  # Find empty space
                    for num in range(1, 10):
                        if self.is_valid(row, col, num):
                            self.board[row][col] = num
                            if self.solve():  # Recursively solve the rest
                                return True
                            self.board[row][col] = 0  # Backtrack
                    return False
        return True
    
    def print_board(self):
        for row in self.board:
            print(" ".join(str(num) for num in row))

# Example of initializing a board
if __name__ == "__main__":
    sudoku_game = Sudoku()
    # Add initial numbers to the board as needed for your game
    sudoku_game.solve()
    sudoku_game.print_board()