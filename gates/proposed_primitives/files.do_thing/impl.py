import pathlib

def do_thing(name: str, recursive: bool = False) -> list[str]:
    \"\"\"Locate the artifact named `name` and return its absolute path(s).\"\"\"
    cwd = pathlib.Path.cwd()
    if recursive:
        matches = list(cwd.rglob(name))
    else:
        matches = list(cwd.glob(name))
    return [str(p.resolve()) for p in matches]