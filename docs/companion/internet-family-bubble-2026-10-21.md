# Internet, family photos and growing conversation bubbles

Implemented in the native desktop app on 21 October 2026. No browser preview
is required. This extends the existing Groq tool loop and local recognition.

## Internet access

`get_weather` uses Open-Meteo geocoding and modelled current conditions. It
requires a city, with optional country code and region. Several matching
countries/states cause a clarification instead of choosing the first result.
The live test caught Kochi resolving to Japan; Kochi + IN + Kerala correctly
resolved to India. Weather includes units, provider time and resolved location.
It is not live GPS or a local thermometer.

`search_web` calls Groq's documented browser tool using the existing Groq key
and GPT-OSS 20B. It sends only the search query and a date/source instruction,
not conversation history, family pictures or desktop files. Public weather
requests receive no provider credentials. There is no additional search API
key, but Groq tokens/tool usage remain subject to its pricing and quota.

Search success requires browser execution metadata and source URLs from that
metadata. Generated digest URLs are not accepted as source evidence. A short
digest and browser excerpts are returned as untrusted quoted evidence; they
cannot authorize desktop actions. Search results and publication dates can
still be incomplete or wrong. The reply prompt asks for source names, distinct
publication/event dates and an honest failure when live lookup is unavailable.
The voice does not read lengthy URLs aloud. Source URLs remain in the local
internet lookup journal. This is search access, not unrestricted browsing,
website login or download execution.

The app exposes these tools through its configured Groq reply path. The
alternative Sarvam-only reply branch does not run this local tool loop.

Research: [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api),
[weather](https://open-meteo.com/en/docs), and
[Groq browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search).

## Family photo enrollment

Open Setta → Camera. Enter a label such as **Father**, then choose **Add a
family photo…**. Select a clear single-person PNG, JPG or WebP under 20 MB and
25 megapixels. The original picture is processed locally and is not copied to
the project or sent to a vision provider. DeepFace may fetch model weights if
missing; that is a model download, not a photo upload.

Detection is enforced for uploaded pictures. Group photos, undetected faces and
very small faces are rejected. The same default DeepFace embedding model as
the existing camera matcher is used. Up to five samples per label persist in
the local NPY file; repeated enrollment adds samples. Stored embeddings update
atomically, with a lock around concurrent matching. Existing single-vector
files continue to load.

When the camera is active, recognition compares against these references.
Near ties between two people return Unknown. A fresh match enters Amma's
context as a tentative user-labelled match, with a three-second freshness
limit. It is not proof of identity, liveness, or protection against a displayed
photo. One photo cannot establish reliable recognition across lighting, age,
pose or glasses. Add several varied clear photos and test with the person.
No father reference has been supplied or enrolled during this change.

Research: [DeepFace recognition and representations](https://github.com/serengil/deepface).
No attribute/emotion classifiers were added.

## Growing bubble

Bubble size now uses real font measurements. It grows from 280 px to at most
440 px wide and from 78 px to at most 250 px tall, further bounded by the
monitor's work area. The character moves within the transparent canvas while
the window expands upwards, preserving the bottom anchor where bounds allow.
The close control stays accessible. Clearing the bubble restores the compact
window. Showing a bubble stops desktop walking so it does not fight resizing.

Beyond the height limit, complete text is paginated. Streaming partials follow
the newest page, while finalized text starts at the beginning. Manglish display
conversion remains active. The bubble can grow; it does not expand without
limit or cover the whole screen. This is a functional change to the existing
cloud design, not a character artwork change.

## Storage and code

| Item | Absolute location |
|---|---|
| Read-only internet tools | `D:\projects codes\PROJECT SETTA\src\web_tools.py` |
| Tool schemas and dispatch | `D:\projects codes\PROJECT SETTA\src\agent_tools.py` |
| Photo upload UI | `D:\projects codes\PROJECT SETTA\src\modern_hub.py` |
| Embeddings and matching | `D:\projects codes\PROJECT SETTA\src\face_id.py` |
| Family embeddings | `D:\projects codes\PROJECT SETTA\data\known_faces\<label>.npy` |
| Bubble layout | `D:\projects codes\PROJECT SETTA\src\thought_bubble.py` |
| Window growth and identity observations | `D:\projects codes\PROJECT SETTA\src\app.py` |
| Internet queries, results and source URLs | `D:\projects codes\PROJECT SETTA\data\conversation-archive\events.sqlite`, stage `internet_lookup` |
| Live API smoke evidence | `D:\projects codes\PROJECT SETTA\runtime\internet-smoke.json` |
| Source-backed search and complete companion weather check | `D:\projects codes\PROJECT SETTA\runtime\internet-companion-smoke.json` |

## Verification boundaries

Final full regression run: 155 tests passed. The complete companion tool loop
requested weather with city Kochi, country IN and region Kerala, then produced
an answer from that API result. A separate final search check returned browser
execution evidence and source URLs. The restarted desktop process was observed
running after initialization. Live camera matching of the father's face remains
unverified because no father photo was provided.

New tests cover credential separation, ambiguous places, safe error responses,
source provenance, persistent multiple face samples, uncertain ties, group
photo rejection and bounded lossless bubble pagination. The uploaded-face
detector is mocked in the group-photo test; this is not proof of recognizing
the user's father. Live weather/search calls succeeded; actual Tk font and
canvas bounds were checked for short, medium and paginated text.

During regression checks the legacy browser server reset rejected POST sockets
on Windows before clients received HTTP 403. It now drains only a tiny bounded
request body with a one-second timeout before rejecting it. Authentication is
unchanged and that legacy server is not started by these features.

Agent Reach's GitHub route was attempted but its network call failed; official
documentation was read through the available web tool. The REA routing guide
selected ordinary source inspection for this complete source project.
