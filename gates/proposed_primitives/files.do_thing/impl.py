@contract(
    precondition="name is a non-empty string; directory (if given) exists.",
    postcondition="Returns the absolute path of the first file (sorted) in "
    "directory whose filename EXACTLY equals name (case-insensitive), or '' "
    "when no file matches exactly. Read-only - nothing is created or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Returns '' when no exact match exists (an absent file is a "
    "result, never an exception); PreconditionError for an empty name or a "
    "missing directory.",
    returns="str: absolute path of the exact match, or '' when none.",
)
def find_file_exact(name: str, directory: str | None = None) -> str:
    """Find the file in `directory` whose filename EXACTLY equals `name`
    (case-insensitive) and return its absolute path, or '' when no exact
    match exists. Contrast find_file, which matches a substring and raises
    when nothing matches - this is the exact-match probe."""
    if not name or not name.strip():
        raise PreconditionError("find_file_exact requires a non-empty 'name'")
    base = _anchor(directory) if directory else PROJECT_ROOT
    if not base.is_dir():
        raise PreconditionError(f"find_file_exact: directory does not exist: {base}")
    needle = name.strip().lower()
    matches = sorted(
        (p for p in base.iterdir() if p.is_file() and p.name.lower() == needle),
        key=str,
    )
    return str(matches[0]) if matches else ""
