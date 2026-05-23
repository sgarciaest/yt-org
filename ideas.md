Agreement amplifier for channel mapping:

Both run independently. When they agree on the same topic, confidence gets multiplied up. When they disagree, confidence stays at the AI value (or drops slightly), and the video is flagged as a disagreement in the proposal.


AI: escalada 0.68  |  Channel: escalada → agree  → final: 0.68 × 1.25 = 0.85 → move
AI: escalada 0.68  |  Channel: fotografía → disagree → final: 0.68 → review + flag
AI: escalada 0.68  |  Channel: (no match) → final: 0.68 → review (unchanged)
Pros

The most useful signal is disagreement — it directly tells you which videos need human attention
Amplifier factor is tunable and has an intuitive meaning ("how much do I trust corroboration?")
Preserves AI autonomy when there's no channel match
Proposal file can show channel_signal: fotografía and ai_signal: escalada side by side — the human reviewer sees the conflict immediately
Cons

Does not help when AI is confident but wrong and channel mapping agrees (they amplify a wrong answer)
Most complex to surface clearly in the proposal YAML
The multiplier has the same arbitrariness problem as Option 2's bonus

Add relojes, add linux

Upgrade model