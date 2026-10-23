# Navigation visibility defect

## User-visible symptom

After opening Conversation, sidebar selections changed their selected state but “Talk to Amma” stayed on screen. This resembled a hung application even when the event loop was responsive. The earlier storage-latency fix did not resolve this separate defect.

## Confirmed cause

Two independent specialist agents reproduced the same problem with the installed Tk/CustomTkinter widgets. Five routes used `CTkScrollableFrame`, while Conversation used a normal `CTkFrame`. `show_page()` called `tkraise()` on the page. A scrollable frame grids an outer container but inherits `tkraise()` for its inner content; raising that content did not raise its outer page above Conversation.

## Fix

Each route now owns an ordinary frame host. Navigation maps the selected host and removes all other hosts from the grid. Scrollable content remains inside its host. Page selection therefore controls actual outer-page visibility without depending on scrollable-frame internals or stacking behavior.

## Verification

The strengthened widget smoke check failed before the fix: selecting Home left all six pages mapped. The fix passes that check. The permanent navigation regression invokes real sidebar button commands in both directions, repeatedly returns from Conversation, and verifies that exactly one outer host is mapped and exactly the selected page is viewable with usable dimensions.

`winfo_viewable()` is used for content because a canvas-embedded inner frame may retain its own mapped state while an ancestor is hidden. Ordinary host mapping is checked separately. These assertions catch the original error that the former selected-page-only smoke test missed.

The full suite passed 118 tests, and the updated app was restarted. Actual mouse clicks in the running Windows app opened Conversation, returned to Home, and opened Reminders and Camera with the correct visible headings and content. The user resumed interacting with the computer during the remaining click-through, so Connections and Settings were verified through the real-widget visibility regression rather than additional mouse clicks. No sign-in, permission change, message submission or reminder acknowledgment was performed during navigation checks.
