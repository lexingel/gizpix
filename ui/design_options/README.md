# Design options for the Gizpix UI

Six visual worlds were sketched for the same screen ("Cut outfit layer", 1440 x 900) and scored by an independent review (heuristics, specificity, task clarity, legibility, buildability) plus the design detector. The winner, the **Animation Exposure Sheet**, is what `ui/web` implements. The other sketches stay here as static, no-JavaScript HTML files you can open in a browser, so a different world can be built on the same server later: only `ui/web/style.css` (tokens at the top) and `ui/web/strings.js` carry the look and the words.

| Sketch | World | Composite score | Note |
|---|---|---|---|
| `model-pick.html` | Animation exposure sheet | **75.6** (chosen) | Frames as columns with numbers and a red-pencil mark: "numbers and eyes together" |
| `challenger-console.html` | Dark working console | 68.6 | Most buildable shell; generic skin, small type, decorative grid |
| `assigned.html` | Cyanotype plate | 57.6 | Numbered specimen plates; white silhouettes make colours impossible to judge |
| `challenger-exposure.html` | Darkroom exposure record | 50.6 | Stacked translucent sheets hide the pixels being judged |
| `canon.html` | Category standard | 46.2 | Layout bug as sketched (main not placed in the grid) |
| `challenger-orienteering.html` | Orienteering map | 40.0 | Clipped at 1440 px, needs a legend to be understood |

These are sketches, not finished screens: copy, pixel art and some layouts are placeholders (the exposure-sheet sketch has a text stand-in for the scrubber that the real UI replaces with a slider).
