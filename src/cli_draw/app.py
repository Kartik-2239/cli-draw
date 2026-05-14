from __future__ import annotations

import curses
from dataclasses import dataclass
from pathlib import Path

import pyperclip

from .config import get_brushes, get_color_names, get_colors, load_config


DEFAULT_SAVE_PATH = Path("save.txt")


@dataclass
class Cell:
    char: str = " "
    color_index: int = 0


class App:
    TOP_BAR_HEIGHT = 1
    FOOTER_HEIGHT = 3
    MAX_UNDO = 50

    def __init__(self, stdscr, source_path: Path | None = None, save_path: Path | None = None):
        self.stdscr = stdscr
        self.config = load_config()
        self.colors = get_colors(self.config)
        self.color_names = get_color_names(self.config)
        self.brushes = get_brushes(self.config)
        self.brush_char = self.brushes[0] if self.brushes else "#"
        self.color_index = 0
        self.drawing = False
        self.canvas_height = 1
        self.canvas_width = 1
        self.cells: list[list[Cell]] = [[Cell()]]
        self.last_point: tuple[int, int] | None = None
        self.message = "Ready"
        self.undo_stack: list[list[list[Cell]]] = []
        self.set_brush_mode = False
        self.text_mode = False
        self.text_buffer = ""
        self.text_pending = ""
        self.source_path = source_path
        self.save_path = save_path or DEFAULT_SAVE_PATH
        self.ansi_to_color_index = {ansi: index for index, (_, ansi, _) in enumerate(self.colors)}
        self.loaded_cells = self.load_canvas(source_path) if source_path else None
        if source_path and source_path.exists():
            self.message = f"Opened {source_path}"

    def sync_size(self):
        height, width = self.stdscr.getmaxyx()
        next_canvas_height = max(1, height - self.TOP_BAR_HEIGHT - self.FOOTER_HEIGHT)
        next_canvas_width = max(1, width)

        old_cells = self.cells
        old_height = len(old_cells)
        old_width = len(old_cells[0]) if old_cells else 0

        resized_cells = [
            [Cell() for _ in range(next_canvas_width)] for _ in range(next_canvas_height)
        ]

        for y in range(min(old_height, next_canvas_height)):
            for x in range(min(old_width, next_canvas_width)):
                cell = old_cells[y][x]
                resized_cells[y][x] = Cell(cell.char, cell.color_index)

        self.canvas_height = next_canvas_height
        self.canvas_width = next_canvas_width
        self.cells = resized_cells

        if self.loaded_cells is not None:
            for y in range(min(len(self.loaded_cells), self.canvas_height)):
                for x in range(min(len(self.loaded_cells[y]), self.canvas_width)):
                    cell = self.loaded_cells[y][x]
                    self.cells[y][x] = Cell(cell.char, cell.color_index)
            self.loaded_cells = None

    def setup(self):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        for index, (_, _, curses_color) in enumerate(self.colors, start=1):
            curses.init_pair(index, curses_color, -1)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        curses.mouseinterval(0)
        print("\033[?1003h", end="", flush=True)
        self.stdscr.keypad(True)
        self.stdscr.nodelay(False)
        self.sync_size()

    def clone_cells(self):
        return [[Cell(cell.char, cell.color_index) for cell in row] for row in self.cells]

    def save_state(self):
        self.undo_stack.append(self.clone_cells())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)

    def clear_canvas(self):
        self.save_state()
        for row in self.cells:
            for cell in row:
                cell.char = " "
                cell.color_index = 0
        self.message = "Canvas cleared"

    def undo(self):
        if not self.undo_stack:
            self.message = "Nothing to undo"
            return
        self.cells = self.undo_stack.pop()
        self.canvas_height = len(self.cells)
        self.canvas_width = len(self.cells[0]) if self.cells else 1
        self.message = "Undo"

    def save_to_file(self):
        try:
            self.save_path.write_text(self.render_ansi_canvas(), encoding="utf-8")
            self.message = f"Saved to {self.save_path}"
        except Exception as exc:
            self.message = f"Save failed: {exc}"

    def render_ansi_canvas(self) -> str:
        lines = []
        for row in self.cells:
            line = "".join(
                f"{self.colors[cell.color_index][1]}{cell.char}\033[0m" for cell in row
            )
            lines.append(line)
        return "\n".join(lines) + "\n"

    def copy_to_clipboard(self):
        try:
            pyperclip.copy(self.render_ansi_canvas())
            self.message = "Copied ANSI canvas to clipboard"
        except Exception as exc:
            self.message = f"Copy failed: {exc}"

    def set_color(self, color_index: int):
        if 0 <= color_index < len(self.colors):
            self.color_index = color_index
            color_name = self.color_names[color_index]
            self.message = f"Color {color_index}: {color_name}"

    def load_canvas(self, path: Path) -> list[list[Cell]]:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            self.message = f"Open failed: {exc}"
            return [[Cell()]]

        rows = [self.parse_ansi_line(line) for line in content.splitlines()]
        if not rows:
            return [[Cell()]]

        width = max(len(row) for row in rows) if rows else 1
        normalized_rows = []
        for row in rows:
            padded = row + [Cell() for _ in range(width - len(row))]
            normalized_rows.append(padded or [Cell()])
        return normalized_rows or [[Cell()]]

    def parse_ansi_line(self, line: str) -> list[Cell]:
        cells: list[Cell] = []
        current_color = 0
        index = 0

        while index < len(line):
            if line[index] == "\033":
                end = line.find("m", index)
                if end == -1:
                    break
                code = line[index : end + 1]
                if code == "\033[0m":
                    current_color = 0
                else:
                    current_color = self.ansi_to_color_index.get(code, current_color)
                index = end + 1
                continue

            cells.append(Cell(line[index], current_color))
            index += 1

        return cells

    def begin_brush_selection(self):
        self.set_brush_mode = True
        self.message = "Brush mode: press any printable key, Esc to cancel"

    def begin_text_mode(self):
        self.text_mode = True
        self.text_buffer = ""
        self.message = "Text: type your text, Enter to confirm, Esc to cancel"

    def place_text(self, x: int, y: int):
        for i, char in enumerate(self.text_pending):
            px = x + i
            if 0 <= px < self.canvas_width and 0 <= y < self.canvas_height:
                self.cells[y][px] = Cell(char, self.color_index)
        self.text_pending = ""
        self.message = "Text placed"

    def paint(self, x: int, y: int):
        if not (0 <= x < self.canvas_width and 0 <= y < self.canvas_height):
            return

        if self.last_point is None:
            self.cells[y][x] = Cell(self.brush_char, self.color_index)
            self.last_point = (x, y)
            return

        last_x, last_y = self.last_point
        dx = abs(x - last_x)
        dy = -abs(y - last_y)
        step_x = 1 if last_x < x else -1
        step_y = 1 if last_y < y else -1
        error = dx + dy
        current_x, current_y = last_x, last_y

        while True:
            if 0 <= current_x < self.canvas_width and 0 <= current_y < self.canvas_height:
                self.cells[current_y][current_x] = Cell(self.brush_char, self.color_index)
            if current_x == x and current_y == y:
                break
            twice_error = 2 * error
            if twice_error >= dy:
                error += dy
                current_x += step_x
            if twice_error <= dx:
                error += dx
                current_y += step_y

        self.last_point = (x, y)

    def handle_mouse(self):
        try:
            _, x, y, _, state = curses.getmouse()
        except curses.error:
            return

        canvas_y = y - self.TOP_BAR_HEIGHT
        if not (0 <= canvas_y < self.canvas_height):
            return

        if self.text_pending:
            if state & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
                self.save_state()
                self.place_text(x, canvas_y)
            return

        if state & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED):
            self.save_state()
            self.drawing = True
            self.paint(x, canvas_y)
            return

        if state & curses.BUTTON1_RELEASED:
            if self.drawing:
                self.paint(x, canvas_y)
            self.drawing = False
            self.last_point = None
            return

        if self.drawing and state & curses.REPORT_MOUSE_POSITION:
            self.paint(x, canvas_y)

    def handle_key(self, key: int) -> bool:
        if key in (ord("q"), 27, 3):
            return False

        if self.set_brush_mode:
            if key in (ord("q"), 27):
                self.set_brush_mode = False
                self.message = "Brush change canceled"
                return True
            if 32 <= key <= 126:
                self.brush_char = chr(key)
                self.set_brush_mode = False
                self.message = f"Brush set to '{self.brush_char}'"
            return True

        if self.text_mode:
            if key == 27:
                self.text_mode = False
                self.text_buffer = ""
                self.message = "Text canceled"
                return True
            if key == 10:
                if self.text_buffer:
                    self.text_pending = self.text_buffer
                    self.message = f"Click to place: '{self.text_pending}'"
                else:
                    self.message = "Empty text, canceled"
                self.text_mode = False
                self.text_buffer = ""
                return True
            if key in (8, 127, curses.KEY_BACKSPACE):
                self.text_buffer = self.text_buffer[:-1]
                self.message = f"Text: '{self.text_buffer}'" if self.text_buffer else "Text: (empty)"
                return True
            if 32 <= key <= 126:
                self.text_buffer += chr(key)
                self.message = f"Text: '{self.text_buffer}'"
            return True

        if key == ord("c"):
            self.clear_canvas()
            return True
        if key == ord("b"):
            self.begin_brush_selection()
            return True
        if key == ord("t"):
            self.begin_text_mode()
            return True
        if key == ord("u"):
            self.undo()
            return True
        if key == ord("s"):
            self.save_to_file()
            return True
        if key == ord("y"):
            self.copy_to_clipboard()
            return True
        if ord("0") <= key <= ord("7"):
            self.set_color(key - ord("0"))
            return True
        if key == curses.KEY_MOUSE:
            self.handle_mouse()
            return True

        return True

    def draw_top_bar(self, width: int):
        mode = (
            "BRUSH INPUT" if self.set_brush_mode
            else "TEXT INPUT" if self.text_mode
            else "PLACE TEXT" if self.text_pending
            else "DRAW"
        )
        source_label = self.source_path.name if self.source_path else "new"
        save_label = self.save_path.name
        status = (
            f" cli-draw | mode:{mode} | brush:{self.brush_char} | "
            f"color:{self.color_index} | file:{source_label} | save:{save_label} "
        )
        try:
            self.stdscr.addstr(0, 0, status[: max(0, width - 1)], curses.A_REVERSE | curses.A_BOLD)
            if len(status) < width:
                self.stdscr.addstr(0, len(status), " " * (width - len(status) - 1), curses.A_REVERSE)
        except curses.error:
            pass

    def draw_canvas(self, height: int, width: int):
        visible_height = min(self.canvas_height, max(0, height - self.FOOTER_HEIGHT - self.TOP_BAR_HEIGHT))
        visible_width = min(self.canvas_width, width)
        for y in range(visible_height):
            screen_y = y + self.TOP_BAR_HEIGHT
            for x in range(visible_width):
                cell = self.cells[y][x]
                attrs = curses.color_pair(cell.color_index + 1)
                try:
                    self.stdscr.addstr(screen_y, x, cell.char, attrs)
                except curses.error:
                    pass

    def draw_footer(self, height: int, width: int):
        footer_y = height - self.FOOTER_HEIGHT
        if footer_y < self.TOP_BAR_HEIGHT:
            return

        swatches = []
        for index, name in enumerate(self.color_names):
            label = f"{index}:{name[:3]}"
            if index == self.color_index:
                label = f"[{label}]"
            swatches.append(label)
        palette_line = " colors " + " ".join(swatches)
        info_line = (
            " draw:mouse  brush:b  text:t  clear:c  undo:u  save:s  copy:y  quit:q/esc "
        )
        message_line = f" {self.message}" if self.message else ""

        try:
            self.stdscr.addstr(footer_y, 0, palette_line[: max(0, width - 1)], curses.A_BOLD)
        except curses.error:
            pass

        cursor_x = 8
        for index, name in enumerate(self.color_names):
            token = f"{index}:{name[:3]}"
            if index == self.color_index:
                token = f"[{token}]"
                attrs = curses.color_pair(index + 1) | curses.A_BOLD | curses.A_REVERSE
            else:
                attrs = curses.color_pair(index + 1) | curses.A_BOLD
            try:
                if cursor_x < width - 1:
                    self.stdscr.addstr(footer_y, cursor_x, token[: max(0, width - cursor_x - 1)], attrs)
                cursor_x += len(token) + 1
            except curses.error:
                pass

        try:
            self.stdscr.addstr(footer_y + 1, 0, info_line[: max(0, width - 1)], curses.A_DIM)
            self.stdscr.addstr(footer_y + 2, 0, message_line[: max(0, width - 1)])
        except curses.error:
            pass

    def render(self):
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()

        self.draw_top_bar(width)
        self.draw_canvas(height, width)
        self.draw_footer(height, width)

        self.stdscr.refresh()

    def run(self):
        self.setup()
        try:
            while True:
                self.sync_size()
                self.render()
                if not self.handle_key(self.stdscr.getch()):
                    return
        finally:
            print("\033[?1003l", end="", flush=True)


def run(source_path: str | Path | None = None, save_path: str | Path | None = None):
    source = Path(source_path).expanduser() if source_path else None
    target = Path(save_path).expanduser() if save_path else None
    curses.wrapper(lambda stdscr: App(stdscr, source, target).run())


def main():
    run()
