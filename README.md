# chesskida

Chess Vision - Human vs Stockfish.

## Project files
- `main.py` - chess vision and Stockfish controller.
- `pieces_png/` - required 12 transparent PNG piece templates.
- `stockfish.exe` - required locally; not included in this repository.
- `requirements.txt` - Python dependencies.

## PyCharm setup
1. Open this repository as a PyCharm project.
2. Create/select a Python virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Put `stockfish.exe` beside `main.py`.
5. Put the 12 required PNG templates inside `pieces_png/`.
6. Start scrcpy with the chess mobile window title `CHESS_MOBILE`.
7. Run `main.py`.
