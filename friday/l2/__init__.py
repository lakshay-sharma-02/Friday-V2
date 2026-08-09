"""L2 - Verification.

Pure, side-effect-free functions only. A verification function takes zero
mutating action - it reads current state and returns true/false against a
specific claim.

Import discipline (enforced by gates/gate3_proof.py): modules in this
package import ONLY primitives' read-only accessors (idempotency class
`idempotent`), never their mutators. The discipline check walks every L2
module's namespace and fails if any imported primitive's contract is not
`idempotent`.
"""
