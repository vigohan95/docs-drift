# Demo video: storyboard and how it is built

85 seconds, 1920x1080, no narration. Every frame has the source on top (the demo page as Chrome rendered it, or the
terminal text of a real run) and a caption bar underneath, so it can be followed with the sound off and the captions
never cover what is being shown.

Nothing is staged:

- The page is `docs/index.html`, rendered by headless Chrome (`video/capture.py`).
- The terminal scene is the text of a real run of the command shown, captured with its timing (`video/capture.py`).
  It is an offline replay, so it needs no key and spends no credits.
- Numbers in captions are placeholders in `video/storyboard.json`, filled by `video/build.py` from
  `review/summary.json`, `review/defects.json` and `review/upstream_prs.json`.

| Time | On screen | Caption |
|---|---|---|
| 0:00 | Page, top: what it is, the 52% and the 0 of 8 | Docs drift: one page gets updated, the page that repeats it does not. Docs Drift lists the places where a project's docs contradict themselves. |
| 0:07 | fastify pair, boxed | fastify: the hooks page says request.body is undefined. The TypeScript page says null. The code says undefined. Both lines link to the pinned commit. |
| 0:17 | typeorm pair, boxed | typeorm: the docs show an update() call that the code does not have. |
| 0:27 | redux-toolkit pair, boxed | redux-toolkit: one page says refetchOnFocus, three others say refetchOnMount. The code handles focus. |
| 0:35 | Upstream pull request table, boxed | The fixes are with the maintainers: (open pull requests) open, covering (their defects). Patches for the other (count) are ready. |
| 0:43 | Terminal: the command is typed, the real output appears, then scrolls | Run it on a repository. It pairs passages that restate each other and asks Clocked /compare which pairs conflict. |
| 0:50 | Terminal, the list | /grounding and a second /compare with the pair swapped decide what is listed. /rerank finds where else the fact is stated. |
| 0:56 | Terminal, end of the list | This run replays recorded API answers: no key, no credits, same result. |
| 1:02 | Page, the numbers, with the tuned and the later result boxed | (projects) real projects: (pairs) pairs read, (listed) listed, (real) real. On (later projects) projects scanned after the rules were fixed: (real) of (listed). It is a list to review, not a verdict. |
| 1:13 | Page, what it listed and got wrong | What it got wrong is on the page too. |
| 1:19 | End card | Built on the Clocked API: /compare, /grounding, /rerank. |

## Build it

```bash
pip install playwright pillow           # plus Google Chrome and ffmpeg on PATH
python scripts/fetch_targets.py fastify
python scripts/build_site.py
python video/capture.py <work dir>      # page.png, page.json, term.json
python video/build.py <work dir> <out dir>
```

`build.py` writes `docs-drift-demo.mp4` (1080p), `docs-drift-demo-small.mp4` (720p, under 10 MB) and
`video-plan.json` with the captions as filled in. The work and output directories are kept outside the repository.

## When things change

- A pull request is merged: edit `review/upstream_prs.json`, rebuild the page, capture and build again. The caption
  counts open pull requests, so reword the `prs` caption in `storyboard.json` if none is open any more.
- The repository address on the end card is in `storyboard.json`.
