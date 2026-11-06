# 60-second video: script draft

Screen recording with voice-over. Everything shown is real: the demo page and one offline replay in a terminal.
Nothing is staged and no number is rounded up.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00 to 0:07 | Demo page, top. The headline, then scroll to the first pair. | "Documentation drifts. One page gets updated, the page that repeats it does not. Docs Drift finds the places where a project's docs contradict themselves." |
| 0:07 to 0:20 | First pair, fastify. Pointer on `undefined` on the left, `null` on the right, then the code line under it. | "Fastify's hooks reference says request.body is undefined in onRequest. Its TypeScript reference says null. The code sets it to undefined. Both passages link to the exact line at a pinned commit." |
| 0:20 to 0:28 | Scroll past the redux-toolkit pair (`fulfilled` against `resolved`) and the prometheus pair (`0x7F` against `0xEF`). | "Redux Toolkit: fulfilled in the docs, resolved in the README. Prometheus: 127 written as 0x7F in one place and 0xEF in another." |
| 0:28 to 0:40 | Terminal: `python -m docsdrift target fastify --offline`. Output appears: 149 pairs compared, findings listed. | "It pairs passages that restate each other, sends each pair to Clocked Compare, checks the result with Verify and with the pair swapped, and uses Rerank to find where else the fact is stated. This run replays the recorded API answers, so anyone can reproduce it without a key." |
| 0:40 to 0:52 | Demo page, the numbers section. Pointer on "11 of 21", then "11 of 13", then "0 of 8". | "Fifteen projects, sixteen contradictions in six of them. About half of what it reports is real. On four projects scanned after the rules were fixed it reported eight findings and none was real. That number is on the page too." |
| 0:52 to 1:00 | Demo page, scroll through the remaining pairs, end on the "Replay it without a key" block. | "Every finding was checked against both passages and the source code. Sixteen small patches are ready for the maintainers, who have the final word." |

## Notes for recording

- Record the page at 1280 wide so both passages sit side by side.
- Run the terminal command once beforehand so the clone is in place; the replay takes a few seconds.
- If upstream pull requests have been opened by then, replace the last line with their count and show one.
- Do not say "verified by humans" or "100% accurate". Say what was checked and who decides.
- Voice-over is about 150 words. Read it at a normal pace; cut the prometheus half-sentence if it runs long.
