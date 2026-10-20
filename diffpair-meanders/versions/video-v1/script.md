# Video script: Fang: Simulating Serpentine Length Matching

About 2 min 30 s, at the user's request (2026-10-19) for a longer video that
explains. Three shapes (16:9, 4:5, 9:16), in the format of the MC34063A,
decoupling and buck-noise videos. Every number comes from a run of the study in
`~/diffpair-meanders` (in brackets: mesh level / variant, as in `runs/`), read
from `build/results/results.json` when the frames are drawn. On-screen text
follows the social-figure rules: plain words, one idea to a sentence, no more
than three sentences to a scene, no semicolons, no serial comma. The brand
fonts have no Greek letters, ohm sign or arrow, so the text says "pi" and
"ohm" and the drawings carry the symbols.

The story, in four parts:

1. Why skew matters: what a differential pair does, and what happens when its
   two halves arrive apart.
2. The problem: the board, where the skew comes from, how we simulate it, and
   what the solver sees.
3. The usual fix and why it falls short: the serpentine, what it really
   leaves, at the receiver, then the two reasons (corners and close folds),
   stripline, placement and the impedance cost.
4. What the skew does and what works: the eye and the common mode, sizing the
   serpentine in the solver, rules of thumb and the summary.

Running head on every shape: `Field simulation · openEMS 0.37`.

---

## Part 1: why skew matters

### 1. Title (0:00 to 0:04)

Screen: copperhead's tile, then the title.

- Title: **Fang: Simulating Serpentine Length Matching**
- Line: A U-bend makes one trace of a differential pair shorter. This video
  shows why that matters and how much of it a serpentine fixes.

### 2. A differential pair (0:04 to 0:12)

Screen: a pair drawn in cross-section, P copper and N teal, with a plus on P
and a minus on N. Beside it, three lanes fill behind a cursor: P rising, N
falling, and their difference (the received signal) rising twice as far. A
noise bump hits P and N together and is absent from the difference.

- Kicker: A differential pair
- Headline: Two traces carry equal and opposite signals
- Text: The receiver reads the difference between the two traces. Noise that
  reaches both traces cancels in the difference.

### 3. When the halves arrive apart (0:12 to 0:20)

Screen: the same lanes, with N now arriving late. The difference rises more
slowly, and a fourth lane shows a pulse where the two do not cancel: the
common mode. The pulse glows copper. [medium/B waveforms]

- Kicker: Skew
- Headline: If one half arrives early, the two do not cancel
- Text: For a moment both traces move the same way. We call this part of the
  signal common mode. Common mode does not carry data, and it can radiate from
  the cables.

## Part 2: the problem

### 4. The board (0:20 to 0:28)

Screen: the fixture drawn on a card from the simulated copper: the U-bend with
P (the inner trace) in copper and N in teal, the four ports at the launch. A
small cross-section beside it, true scale, with h, w and s marked. A tag at the
far end: "Arrival time measured here".

- Kicker: The board
- Headline: A differential pair turns through a U-bend
- Text: The traces are 0.25 mm wide on 0.2 mm of dielectric. Their centres are
  0.508 mm (20 mil) apart. We send a step in at one end and measure when each
  trace arrives at the other.

### 5. Where the skew comes from (0:28 to 0:36)

Screen: the bend enlarged. The two arcs light up in turn, with their lengths
written along them (pi R, then pi (R + s)), then the difference glows on the
outer arc. [analytic]

- Kicker: Where the skew comes from
- Headline: The inner trace is 1.596 mm shorter
- Text: Around the bend the outer trace runs pi times the pitch further. At
  20 mil that is 62.8 mil, whatever the radius. Geometry predicts 9.45 ps of
  skew.

### 6. How we simulate it (0:36 to 0:45)

Screen: the bend with the solver's grid drawn over it, fine over the copper and
coarser away from it. Then the four ports light up one at a time, each sending
a pulse in turn. [medium/B mesh, 140 runs]

- Kicker: How we simulate it
- Headline: openEMS solves the fields on 1.24 million cells
- Text: Each run sends a pulse into one of the four ports. Four runs give the
  full response of the board. From it we calculate the waveforms at the
  receiver.

### 7. What the solver sees (0:45 to 0:53)

Screen: a scope of the far-end P (copper) and inverted N (teal) for a 50 ps
edge, behind a copper cursor, slowed down by the factor the cursor shows.
Dotted lines mark each 50 % crossing, and the gap between them is labelled.
Under it, a second lane fills with the common-mode voltage. [medium/B]

- Kicker: The untuned bend in openEMS
- Headline: P arrives 9.3 ps before N
- Text: The field solver agrees with geometry to within 2 %. The skew puts a
  46 mV common-mode pulse on the line.

## Part 3: the usual fix and why it falls short

### 8. The usual fix (0:53 to 1:01)

Screen: the bend again, with two sparse excursions on P lit copper. Beside it, a
length report: P 30.308 mm, N 30.308 mm, "Equal". [geometry C, MTL C]

- Kicker: The usual fix
- Headline: Add 1.596 mm to the inner trace
- Text: A serpentine gives P the missing length. The CAD length report then
  shows P and N equal. A line model that sees only length predicts 0.3 ps of
  skew.

### 9. Three serpentines of exactly the right length (1:01 to 1:11)

Screen: three small drawings in a row (one broad excursion, two, four small
ones), each with its exact length. Under them, bars grow in turn on one scale:
9.3 ps for the untuned bend (grey), then 2.3, 3.6 and 5.2 ps (copper). A thin
teal tick on each bar marks what the line model predicts. [medium/B, F, C, D;
MTL F, C, D]

- Kicker: Three serpentines, each exactly the right length
- Headline: 2.3 to 5.2 ps of the skew stays
- Text: One broad excursion removes 75 % of the skew. Two remove 61 %. Four
  small ones remove only 44 %.

### 10. At the receiver (1:11 to 1:18)

Screen: the scope of scene 7 for the four small excursions: P still ahead of N,
with the untuned bend's edges kept in grey behind. The common-mode lane fills
under it. [medium/B, D]

- Kicker: Four small excursions at the receiver
- Headline: The lengths match but P still arrives first
- Text: The skew falls from 9.3 ps to 5.2 ps, not to zero. The common-mode pulse
  falls from 46 mV to 25 mV.

### 11. The first reason: corners (1:18 to 1:26)

Screen: one excursion enlarged. The centre line that the length report measures
is drawn dashed. Then the path the current takes lights up copper, hugging the
inside of each of the four corners. [medium/F, C, D less MTL]

- Kicker: Why the fix falls short
- Headline: The current takes the inside of each corner
- Text: That path is shorter than the centre line that the length report
  measures. Each excursion has four corners. In these serpentines each one
  loses 1.2 to 2.1 ps of the delay its length predicts.

### 12. The second reason: close folds (1:26 to 1:35)

Screen: two serpentines on a straight pair, each adding 6 mm: folds 1.0 mm
apart and folds 0.15 mm apart. Small arrows show current in opposite
directions in neighbouring folds, then a glow crosses the narrow gap. Beside
each, a bar of the delay it gives against the delay its length predicts.
[medium/S_ref, S_loose, S_tight]

- Kicker: Why the fix falls short
- Headline: Close folds let the signal cross the gap
- Text: Neighbouring folds carry current in opposite directions and couple to
  each other. Folds 1.0 mm apart give 84 % of the predicted delay. Folds
  0.15 mm apart give 68 %.

### 13. Stripline (1:35 to 1:42)

Screen: a stripline cross-section, two planes and the pair between them. Under
it, the same three serpentines as pairs of bars: microstrip (copper) and
stripline (teal), the share of the skew each removes. [medium/B_sl, F_sl,
C_sl, D_sl, S_loose_sl, S_tight_sl]

- Kicker: The same copper in stripline
- Headline: Stripline has the same problem
- Text: Geometry predicts the stripline bend to 0.6 %. The serpentines remove
  81 %, 64 % and 42 % of the skew. Close folds still cost 20 points of delay.

### 14. Where the serpentine goes (1:42 to 1:50)

Screen: two drawings: the two excursions next to the bend, and the same two next
to the launch. Under them, the skew read at each frequency sweeps in from 1 to
30 GHz behind the cursor: next to the bend in teal, flat, and at the launch in
copper, rising. [medium/C, C_far]

- Kicker: Where the serpentine goes
- Headline: Put the fix next to the bend
- Text: At the launch the same serpentine leaves 4.4 ps instead of 3.6 ps. Its
  skew also grows with frequency, from 4.1 ps at 5 GHz to 6.5 ps at 25 GHz.

### 15. The cost of a broad excursion (1:50 to 1:57)

Screen: the impedance the line shows along its length (a TDR trace) sweeps in
behind the cursor: the untuned bend in grey, the broad excursion in copper, with
its peak lit where the excursion is. [medium/B, F]

- Kicker: The cost of a broad excursion
- Headline: The impedance rises where P leaves N
- Text: Over the broad excursion the pair impedance rises to 114 ohm, against
  107 ohm for the plain bend. It reflects more signal than the other
  length-matched serpentines.

## Part 4: what the skew does and what works

### 16. What the skew does to the signal (1:57 to 2:05)

Screen: two 16 Gb/s eyes side by side, the straight pair and the untuned bend,
drawn trace by trace behind the cursor. Under each, the common-mode lane.
[medium/A, B]

- Kicker: What 9.3 ps does at 16 Gb/s
- Headline: The eye barely closes, but common mode grows
- Text: The eye height falls only from 92.9 % to 91.1 % of the swing. Common mode
  grows to 13.6 % of the swing, and that is the real cost.

### 17. The fix that works (2:05 to 2:13)

Screen: the scope again, for the broad excursion: first its 2.3 ps gap in grey,
then the resized version sweeps in copper and teal with the two edges almost on
top of each other. Beside it, the three before and after numbers.
[medium/F, F_cal, C, C_cal, D, D_cal]

- Kicker: Size the serpentine by its delay, not its length
- Headline: One more solver run removes most of the rest
- Text: We add back the delay that each serpentine lost. The broad excursion
  goes to 0.15 ps and two excursions go to 0.56 ps. Four small ones still need a
  second run.

### 18. Rules of thumb (2:13 to 2:21)

Screen: four short rules appear one at a time, each beside a small drawing.

- Kicker: For a bent pair at this pitch
- Headline: Four rules from 140 solver runs
- Text (one rule to a line):
  - Use few excursions.
  - Keep the folds apart.
  - Put the fix next to the bend.
  - Size it by delay, not length.

### 19. Summary (2:21 to 2:26)

- Kicker: Run in openEMS 0.37
- Headline: Equal length is not equal delay
- Text: Untuned bend: 9.3 ps. Serpentines of exactly the right length: 2.3 to
  5.2 ps. Serpentines sized in the solver: 0.15 to 1.9 ps.

### 20. End (2:26 to 2:27)

copperhead's lockup and copperhead.sh.
