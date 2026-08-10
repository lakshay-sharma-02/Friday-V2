The real gap records (gap_id 18ca581d7f2b0f2a29, 18ca582f77a351d829, 18ca58326015f70b29) show that the primitive `files.do_thing` was called with arguments `name: str:1` and `recursive: bool` but refused because "primitive 'files.do_thing' has no registered contract; refusing to call it". The goal_context for all attempts was "locate the missing artifact and report it". This indicates that the function exists but lacks a contract, preventing its execution. By defining a contract with idempotent read semantics, a clear precondition on arguments, and a postcondition that returns a list of absolute paths, we satisfy the refusal reason and enable the primitive to be used for locating artifacts. The implementation uses only stdlib pathlib to search for a file named `name` (optionally recursively) and returns its absolute path(s), matching the arg shape and goal. The test suite creates temporary files and directories to verify correct behavior without external dependencies, ensuring hermeticity.

## Draft status
- generated: 2026-08-10T04:47:25+00:00
- impl compiles: no
- test compiles: yes
- driving gap records: 3
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. The
  meta-engine approval gate does not exist yet (aspirational, see
  gates/PLAN_STATUS.md). A human must review these files and wire an
  approved primitive through the REAL registration path: create
  friday/l1/<module>.py, then add the module name to planner._L1_MODULES.
