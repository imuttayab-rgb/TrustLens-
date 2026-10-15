# Local chat and calling acceptance check

Use two eligible test accounts in separate browsers on the same computer. Allow microphones and use headphones. Keep synthetic test content out of real customer conversations.

| Check | Expected result |
| --- | --- |
| A sends text; B opens the conversation | Correct sender, ordering and read state |
| A edits inside 60 seconds | Both see the edited body; original/version remains retained server-side |
| A deletes for everyone inside 60 seconds | Both see a tombstone; original remains retained server-side |
| A tries an edit/delete after 60 seconds | UI and API reject the change |
| A clears and then undoes inside 10 seconds | Only A's view changes; B keeps their history |
| Record, pause/resume and preview voice | Microphone stops when recording is discarded or finished |
| Send voice with a brief simulated upload interruption | Recording stays available to retry; retry must not create duplicates |
| Play voice, seek, change speed, navigate pages | One player stays active; playback state remains consistent |
| Call B and accept | Both sides hear live audio; do not infer this from a connected label alone |
| Microphone mute/unmute | Only outgoing microphone audio changes |
| Received-sound mute/unmute | Incoming call audio changes independently of microphone mute |
| Select another microphone/speaker where supported | Actual route changes; denied/unavailable devices report an error and preserve valid selection |
| Minimize/expand | Call continues and End remains reachable |
| End while a device switch is pending | No ghost call, active microphone or orphaned audio element remains |
| Blocked user / closed conversation | Server rejects new sends/calls regardless of UI state |
| Sold/inactive listing after 72 hours | Old messages readable; further messaging/calling is unavailable |
| Sign out / switch account | Old private query/player/call state is cleared according to the session lifecycle |

For public hosting, repeat on actual phones and different networks after configuring HTTPS, WSS, TURN and firewall rules. Test closed/background browser behavior honestly; the browser platform does not guarantee native app-style incoming calls.
