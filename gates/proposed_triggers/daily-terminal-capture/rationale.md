# Daily Terminal Capture Trigger Proposal

## Capability Gap

This trigger uses `terminal.get_scrollback` which doesn't exist yet. The watcher loop will refuse this trigger at runtime, creating a capability gap record.

## Gap Cause

The trigger's plan references `terminal.get_scrollback`, a primitive that does not exist in the friday/l1/ module set. This is a legitimate missing capability:

- Users need to capture terminal session history for daily summaries
- The existing `screenshot` primitive captures screen images, not terminal text
- There's no scrollback/text capture capability for terminals like kitty

## Why Friday Needs It

1. **Daily Work Summaries**: At end of day, users want to capture what they've been typing/seeing in their terminal
2. **Integration with Messaging**: Works with existing `whatsapp.send_document` primitive to send the captured text
3. **Complementary to Screenshot**: Screenshot captures visual state; this captures textual state of terminal sessions

## Proposed Primitive

`terminal.get_scrollback` - reads the scrollback buffer of a running terminal.

## Next Steps

Run the watcher with this trigger to generate the capability gap, then run gap_triage to draft the primitive proposal.