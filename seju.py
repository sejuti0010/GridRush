from OpenGL.GL import *
from OpenGL.GLUT import *
import random
import sys

# ---------------- Window / layout ----------------
W, H = 650, 500
GRID = 8
CELL = 46
GX, GY = 50, 40                      # grid er bottom-left corner
SLOT_X, SLOT_W, SLOT_H, SLOT_GAP = 480, 130, 112, 16
SLOT_CELL = 24
LIFT = 0
EXIT_RECT = (535, 448, 620, 482)

# (light color, dark color)
COLORS = [
    ((0.93, 0.38, 0.50), (0.75, 0.22, 0.35)),   # pink
    ((0.65, 0.45, 0.85), (0.45, 0.28, 0.65)),   # purple
    ((0.20, 0.55, 0.98), (0.10, 0.35, 0.78)),   # blue
    ((1.00, 0.70, 0.12), (0.85, 0.50, 0.05)),   # orange
]

# shape = list of (dx, dy)
SHAPES = [
    [(0, 0)],
    [(0, 0), (1, 0)],
    [(0, 0), (0, 1)],
    [(0, 0), (1, 0), (2, 0)],
    [(0, 0), (0, 1), (0, 2)],
    [(0, 0), (1, 0), (2, 0), (3, 0)],
    [(0, 0), (0, 1), (0, 2), (0, 3)],
    [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)],
    [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)],
    [(0, 0), (1, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
    [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)],
    [(0, 0), (1, 0), (0, 1)],
    [(0, 0), (1, 0), (1, 1)],
    [(1, 0), (0, 1), (1, 1)],
    [(0, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (2, 0), (0, 1)],
    [(0, 0), (1, 0), (2, 0), (2, 1)],
    [(0, 0), (0, 1), (1, 1), (2, 1)],
    [(2, 0), (0, 1), (1, 1), (2, 1)],
    [(0, 0), (1, 0), (2, 0), (1, 1)],
]

# ---------------- Game state ----------------
grid = [[None] * GRID for _ in range(GRID)]     # grid[row][col], row 0 = bottom
next_group_id = 1
pieces = [None, None, None]
dragging = -1
dragging_grid = None
selected_piece = -1
drag_start_x = 0
drag_start_y = 0
piece_dragged = False
mx, my = 0, 0
score = 0
best = 0
combo = 1
game_over = False


# ---------------- Helper functions ----------------
def shape_size(shape):
    w = max(p[0] for p in shape) + 1
    h = max(p[1] for p in shape) + 1
    return w, h


def new_pieces():
    global pieces
    pieces = [(random.choice(SHAPES), random.randrange(len(COLORS))) for _ in range(3)]


def slot_pos(i):
    # i = 0 sobar upore
    return SLOT_X, GY + (2 - i) * (SLOT_H + SLOT_GAP)


def can_place(shape, gc, gr):
    return all(
        0 <= gc + dx < GRID
        and 0 <= gr + dy < GRID
        and grid[gr + dy][gc + dx] is None
        for dx, dy in shape
    )


def has_any_move():
    return any(
        p is not None and can_place(p[0], c, r)
        for p in pieces
        for r in range(GRID)
        for c in range(GRID)
    )


def piece_drop_cell(shape):
    w, h = shape_size(shape)
    lx = mx - w * CELL / 2.0
    ly = my - h * CELL / 2.0 + LIFT
    gc = int(round((lx - GX) / float(CELL)))
    gr = int(round((ly - GY) / float(CELL)))
    pointer_on_grid = GX <= mx < GX + GRID * CELL and GY <= my < GY + GRID * CELL
    return gc, gr, lx, ly, pointer_on_grid and can_place(shape, gc, gr)


def score_move(gained):
    global score, best, combo
    full_rows = {r for r in range(GRID) if all(grid[r][c] is not None for c in range(GRID))}
    full_cols = {c for c in range(GRID) if all(grid[r][c] is not None for r in range(GRID))}

    for r in range(GRID):
        for c in range(GRID):
            if r in full_rows or c in full_cols:
                grid[r][c] = None

    lines = len(full_rows) + len(full_cols)
    if lines > 0:
        gained += lines * 10 * lines
        gained *= combo
        combo += 1
    else:
        combo = 1

    score += gained
    if score > best:
        best = score


def place_piece(shape, color, gc, gr):
    global next_group_id
    group_id = next_group_id
    next_group_id += 1
    for dx, dy in shape:
        grid[gr + dy][gc + dx] = (color, 1, group_id)
    score_move(len(shape))


def place_slot_piece(index):
    global selected_piece
    shape, color = pieces[index]
    gc, gr, _, _, valid = piece_drop_cell(shape)
    if not valid:
        return False
    place_piece(shape, color, gc, gr)
    pieces[index] = None
    selected_piece = -1
    if all(piece is None for piece in pieces):
        new_pieces()
    refresh_game_over()
    return True


def group_can_place(cells, source_c, source_r, target_c, target_r):
    for c, r, color, level, _ in cells:
        dc, dr = target_c + c - source_c, target_r + r - source_r
        if not (0 <= dc < GRID and 0 <= dr < GRID):
            return False
        target = grid[dr][dc]
        if target is not None:
            if len(cells) != 1 or target[0] != color or target[1] != level:
                return False
    return True


def grid_group_drop():
    cells, source_c, source_r = dragging_grid
    target_c = int(round((mx - GX - CELL / 2) / CELL))
    target_r = int(round((my - GY - CELL / 2) / CELL))
    valid = group_can_place(cells, source_c, source_r, target_c, target_r)
    return target_c, target_r, valid


def draw_grid_group_preview():
    cells, source_c, source_r = dragging_grid
    target_c, target_r, valid = grid_group_drop()
    for c, r, color, level, _ in cells:
        dc = target_c + c - source_c
        dr = target_r + r - source_r
        if not (0 <= dc < GRID and 0 <= dr < GRID):
            continue
        if valid:
            light = COLORS[color][0]
            glColor4f(light[0], light[1], light[2], 0.45)
        else:
            glColor4f(1.0, 0.12, 0.12, 0.65)
        x = GX + dc * CELL
        y = GY + dr * CELL
        draw_rect(x + 2, y + 2, x + CELL - 2, y + CELL - 2)


def max_level():
    return max(
        (cell[1] for row in grid for cell in row if cell is not None),
        default=1,
    )


def refresh_game_over():
    global game_over
    game_over = not has_any_move()


def exit_game():
    if "glutLeaveMainLoop" in globals():
        glutLeaveMainLoop()
        window = glutGetWindow()
        if window:
            glutDestroyWindow(window)
    else:
        sys.exit(0)


def restart():
    global grid, next_group_id, score, combo, game_over, dragging, dragging_grid
    global selected_piece, piece_dragged
    grid = [[None] * GRID for _ in range(GRID)]
    next_group_id = 1
    score = 0
    combo = 1
    game_over = False
    dragging = -1
    dragging_grid = None
    selected_piece = -1
    piece_dragged = False
    new_pieces()


# ---------------- Drawing ----------------
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))


def draw_rect(x1, y1, x2, y2):
    glBegin(GL_QUADS)
    glVertex2f(x1, y1)
    glVertex2f(x2, y1)
    glVertex2f(x2, y2)
    glVertex2f(x1, y2)
    glEnd()


def draw_block(x, y, size, color_id, level=1):
    light, dark = COLORS[color_id]
    glColor3f(*dark)
    draw_rect(x + 1, y + 1, x + size - 1, y + size - 1)
    glColor3f(*light)
    draw_rect(x + 2, y + 4, x + size - 2, y + size - 2)
    if size >= CELL:
        glColor3f(1, 1, 1)
        draw_text(x + size / 2 - 4, y + size / 2 - 5, str(level), GLUT_BITMAP_HELVETICA_18)


def draw_shape(shape, color_id, x, y, size):
    for dx, dy in shape:
        draw_block(x + dx * size, y + dy * size, size, color_id)


def draw_trophy(x, y):
    glColor3f(1.0, 0.8, 0.1)
    glBegin(GL_QUADS)                       # cup
    glVertex2f(x - 14, y + 30)
    glVertex2f(x + 14, y + 30)
    glVertex2f(x + 10, y + 10)
    glVertex2f(x - 10, y + 10)
    glEnd()
    draw_rect(x - 3, y + 3, x + 3, y + 10)  # stem
    draw_rect(x - 12, y - 4, x + 12, y + 3) # base
    glBegin(GL_LINE_LOOP)                   # handles
    glVertex2f(x - 14, y + 27)
    glVertex2f(x - 22, y + 27)
    glVertex2f(x - 22, y + 18)
    glVertex2f(x - 11, y + 14)
    glEnd()
    glBegin(GL_LINE_LOOP)
    glVertex2f(x + 14, y + 27)
    glVertex2f(x + 22, y + 27)
    glVertex2f(x + 22, y + 18)
    glVertex2f(x + 11, y + 14)
    glEnd()


def draw_top_bar():
    # combo box
    glColor3f(1.0, 0.95, 0.15)
    draw_rect(50, 445, 130, 485)
    glColor3f(0, 0, 0)
    draw_text(75, 459, str(combo) + " x")

    # score pill
    glColor3f(0.22, 0.12, 0.26)
    draw_rect(170, 448, 290, 482)
    glColor3f(0.85, 0.8, 0.9)
    draw_text(180, 460, "Score " + str(score).zfill(5))

    # trophy + best
    draw_trophy(350, 450)
    glColor3f(1.0, 0.9, 0.3)
    draw_text(390, 460, str(best).zfill(5))

    glColor3f(0.18, 0.56, 0.34)
    draw_rect(*EXIT_RECT)
    glColor3f(1, 1, 1)
    draw_text(558, 459, "EXIT")
    draw_text(475, 460, "Level " + str(max_level()), GLUT_BITMAP_HELVETICA_12)
    glColor3f(0.85, 0.8, 0.9)
    draw_text(50, 16, "Drag or click a piece to place. Move grid blocks as a group. Press R to reset.", GLUT_BITMAP_HELVETICA_12)


def draw_grid():
    glColor3f(0.20, 0.13, 0.28)
    draw_rect(GX - 4, GY - 4, GX + GRID * CELL + 4, GY + GRID * CELL + 4)
    glColor3f(0.30, 0.22, 0.42)
    draw_rect(GX, GY, GX + GRID * CELL, GY + GRID * CELL)

    glColor3f(0.36, 0.28, 0.50)
    glBegin(GL_LINES)
    for i in range(GRID + 1):
        glVertex2f(GX + i * CELL, GY)
        glVertex2f(GX + i * CELL, GY + GRID * CELL)
        glVertex2f(GX, GY + i * CELL)
        glVertex2f(GX + GRID * CELL, GY + i * CELL)
    glEnd()

    for r in range(GRID):
        for c in range(GRID):
            cell = grid[r][c]
            if cell is not None:
                draw_block(GX + c * CELL, GY + r * CELL, CELL, cell[0], cell[1])


def draw_slots():
    for i in range(3):
        x, y = slot_pos(i)
        glColor3f(0.20, 0.12, 0.27)
        draw_rect(x, y, x + SLOT_W, y + SLOT_H)
        if i == selected_piece:
            glColor3f(1.0, 0.9, 0.3)
            glBegin(GL_LINE_LOOP)
            glVertex2f(x + 2, y + 2)
            glVertex2f(x + SLOT_W - 2, y + 2)
            glVertex2f(x + SLOT_W - 2, y + SLOT_H - 2)
            glVertex2f(x + 2, y + SLOT_H - 2)
            glEnd()
        if pieces[i] is None or i == dragging:
            continue
        shape, color = pieces[i]
        w, h = shape_size(shape)
        px = x + (SLOT_W - w * SLOT_CELL) / 2.0
        py = y + (SLOT_H - h * SLOT_CELL) / 2.0
        draw_shape(shape, color, px, py, SLOT_CELL)


def draw_dragging():
    if dragging_grid is not None:
        draw_grid_group_preview()
        return
    piece_index = dragging if dragging >= 0 else selected_piece
    if piece_index < 0 or pieces[piece_index] is None:
        return
    shape, color = pieces[piece_index]
    gc, gr, _, _, valid = piece_drop_cell(shape)
    if valid:
        light = COLORS[color][0]
        glColor4f(light[0], light[1], light[2], 0.45)
    else:
        glColor4f(1.0, 0.12, 0.12, 0.65)
    for dx, dy in shape:
        x = GX + (gc + dx) * CELL
        y = GY + (gr + dy) * CELL
        draw_rect(x + 2, y + 2, x + CELL - 2, y + CELL - 2)


def draw_game_over():
    glColor4f(0, 0, 0, 0.65)
    draw_rect(GX, GY, GX + GRID * CELL, GY + GRID * CELL)
    glColor3f(1, 1, 1)
    draw_text(GX + 120, GY + 210, "GAME OVER", GLUT_BITMAP_TIMES_ROMAN_24)
    draw_text(GX + 105, GY + 170, "Press R to restart", GLUT_BITMAP_HELVETICA_18)


def showScreen():
    glClearColor(0.27, 0.15, 0.30, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glViewport(0, 0, W, H)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, W, 0, H, 0, 1)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    draw_top_bar()
    draw_grid()
    draw_slots()
    draw_dragging()
    if game_over:
        draw_game_over()

    glutSwapBuffers()


# ---------------- Event handling ----------------
def mouse(button, state, x, y):
    global next_group_id
    global dragging, dragging_grid, selected_piece, drag_start_x, drag_start_y
    global piece_dragged, mx, my
    mx = x
    my = H - y

    if state == GLUT_DOWN:
        x1, y1, x2, y2 = EXIT_RECT
        if x1 <= mx <= x2 and y1 <= my <= y2:
            exit_game()
            return

    if button != GLUT_LEFT_BUTTON:
        return

    if state == GLUT_DOWN:
        c = int((mx - GX) // CELL)
        r = int((my - GY) // CELL)
        slot_selected = False
        if not game_over:
            for i in range(3):
                sx, sy = slot_pos(i)
                if pieces[i] is not None and sx <= mx <= sx + SLOT_W and sy <= my <= sy + SLOT_H:
                    dragging = i
                    drag_start_x, drag_start_y = x, y
                    piece_dragged = False
                    slot_selected = True
                    break
        if not slot_selected and 0 <= c < GRID and 0 <= r < GRID:
            if selected_piece >= 0 and not game_over:
                place_slot_piece(selected_piece)
            elif grid[r][c] is not None:
                cell = grid[r][c]
                group_id = cell[2] if len(cell) > 2 else None
                cells = []
                if group_id is None:
                    cells.append((c, r, cell[0], cell[1], None))
                else:
                    for row_index, row in enumerate(grid):
                        for column_index, member in enumerate(row):
                            if member is not None and member[2] == group_id:
                                cells.append(
                                    (column_index, row_index, member[0], member[1], group_id)
                                )
                for column, row_index, _, _, _ in cells:
                    grid[row_index][column] = None
                dragging_grid = (cells, c, r)
    elif state == GLUT_UP and dragging_grid is not None:
        cells, source_c, source_r = dragging_grid
        gc, gr, valid = grid_group_drop()
        if valid and len(cells) == 1:
            _, _, color, level, _ = cells[0]
            target = grid[gr][gc]
            if target is not None:
                grid[gr][gc] = (color, level + 1, next_group_id)
                next_group_id += 1
                score_move(level * 5)
            else:
                grid[gr][gc] = (color, level, cells[0][4])
                score_move(0)
        elif valid:
            for c, r, color, level, group_id in cells:
                dc = gc + c - source_c
                dr = gr + r - source_r
                grid[dr][dc] = (color, level, group_id)
            score_move(0)
        else:
            for c, r, color, level, group_id in cells:
                grid[r][c] = (color, level, group_id)
        dragging_grid = None
        refresh_game_over()
    elif state == GLUT_UP and dragging >= 0:
        if abs(x - drag_start_x) > 4 or abs(y - drag_start_y) > 4:
            piece_dragged = True
        if piece_dragged:
            if not place_slot_piece(dragging):
                selected_piece = dragging
        else:
            selected_piece = dragging
        dragging = -1
        piece_dragged = False

    glutPostRedisplay()


def motion(x, y):
    global mx, my, piece_dragged
    if dragging >= 0 and (abs(x - drag_start_x) > 4 or abs(y - drag_start_y) > 4):
        piece_dragged = True
    mx = x
    my = H - y
    glutPostRedisplay()


def keyboard(key, x, y):
    if key == b'r' or key == b'R':
        restart()
        glutPostRedisplay()
    elif key == b'\x1b':
        exit_game()


new_pieces()

glutInit()
glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE)
glutInitWindowSize(W, H)
glutInitWindowPosition(200, 100)
glutCreateWindow(b"Block Puzzle Game")

glutDisplayFunc(showScreen)
glutMouseFunc(mouse)
glutMotionFunc(motion)
glutPassiveMotionFunc(motion)
glutKeyboardFunc(keyboard)
glutMainLoop()