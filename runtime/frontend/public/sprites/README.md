# Sprites

Placeholder art lives in `src/components/courtroom/Sprite.tsx` as a coloured
plinth with the role's initial. To drop in real artwork, replace the figure
block in that component — the bobbing animation, the speaking/idle states, and
the nameplate stay as they are.

Suggested set per role (`presenter`, `attacker_doctrinal`,
`attacker_evidentiary`, `judge`):

| File | Used when |
| --- | --- |
| `<role>-idle.png` | the role is not speaking |
| `<role>-speaking.png` | the role's model is generating |
| `<role>-objecting.png` | attackers only, during the flourish |

Transparent PNG, roughly 240×320, drawn to sit on a bench line at the bottom
edge. Keep them stylistically consistent — the courtroom is the whimsical half
of the app, but the dissent log next to it is not, and the contrast only works
if the courtroom commits.
