"""
Read the current slide's presenter notes from Keynote (via AppleScript).

Only touched when the phone's presenter panel is open (subscribed), so the
Automation permission prompt ("kPad wants to control Keynote") appears at a
sensible time. Guarded by `is running`, so it never launches Keynote. PowerPoint
support can be added the same way; Google Slides isn't scriptable.
"""

import subprocess

# Returns "<slide-number>\t<notes text>", or "" if Keynote isn't presenting.
_KEYNOTE = r'''
set out to ""
if application "Keynote" is running then
  tell application "Keynote"
    try
      if (exists front document) then
        set s to current slide of front document
        set out to (slide number of s as text) & "\t" & (notes of s)
      end if
    end try
  end tell
end if
return out
'''


def read_current_notes():
    """(slide_number:str, notes:str) or None if nothing is presenting."""
    try:
        r = subprocess.run(
            ["osascript", "-e", _KEYNOTE],
            capture_output=True, text=True, timeout=3,
        )
        out = (r.stdout or "").rstrip("\n")
        if "\t" in out:
            num, _, text = out.partition("\t")
            return num, text
    except Exception:
        pass
    return None
