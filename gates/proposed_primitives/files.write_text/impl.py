@contract(
    precondition="path is a non-empty string; text is a str; the parent directory exists; append is a bool.",
    postcondition="Creates or overwrites (or appends to) the file at path with "
    "the given text encoded as UTF-8. Parent directories are NOT created. "
    "Side-effect: writes to the filesystem.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError when path is empty, parent directory does "
    "not exist, or path is not a string; OSError propagated on disk-space "
    "failure or read-only filesystem.",
    returns="str: the absolute path of the written file.",
)
def write_text(path: str, text: str, *, append: bool = False) -> str:
    """Write text content to the file at path, creating or replacing it.

    The bounded writer counterpart to read_text: needed by the digest
    trigger's "write the latest digest summary to a notes file" path,
    which was previously refused because no write primitive was
    registered. append=True opens in append mode (idempotency class
    becomes commutative-safe: repeated appends are harmless if the
    content already exists). ~ expands; relative paths anchor at the
    project root (same rule as find_file/read_text). Returns the
    absolute path so a plan step can reference it downstream."""
    if not path or not path.strip():
        raise PreconditionError("write_text requires a non-empty 'path'")
    p = _anchor(path)
    parent = p.parent
    if not parent.is_dir():
        raise PreconditionError(f"write_text: parent directory does not exist: {parent}")
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as f:
        f.write(text)
    return str(p)