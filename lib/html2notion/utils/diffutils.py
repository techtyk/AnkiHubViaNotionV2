from rich.console import Console
from rich.table import Table
import difflib


def print_diff(text1: str, text2: str):
    differ = difflib.Differ()
    diff = list(differ.compare(text1.splitlines(), text2.splitlines()))
    console = Console()
    table = Table(show_header=False, show_edge=False, show_lines=False)

    table.add_column(justify="left", no_wrap=True)
    table.add_column(justify="left", no_wrap=True)

    left_line = ""
    right_line = ""
    for line in diff:
        if line.startswith('+'):
            style = "bold red"
        elif line.startswith('-'):
            style = "bold green"
        elif line.startswith("?"):
            style = "bold yellow"
        else:
            style = None

        if line.startswith('-'):
            left_line = line
        elif line.startswith('+'):
            right_line = line
        elif line.startswith("?"):
            if left_line and right_line:
                table.add_row(left_line + "\n" + line[2:], right_line + "\n" + line[2:], style=style)
                left_line = ""
                right_line = ""
            elif left_line:
                table.add_row(left_line + "\n" + line[2:], "", style=style)
                left_line = ""
            elif right_line:
                table.add_row("", right_line + "\n" + line[2:], style=style)
                right_line = ""
        else:
            if left_line or right_line:
                table.add_row(left_line, right_line, style=style)
                left_line = ""
                right_line = ""
            table.add_row("", line, style=style)

    console.print(table, overflow="fold")


if __name__ == '__main__':
    # Example usage
    text1 = """This is a sample text.
    It has multiple lines.
    Another line here.
    And one more line."""

    text2 = """This is a simple text.
    It has multiple lines.
    An extra line here.
    And one more line.
    A new line at the end."""

    print_diff(text1, text2)
