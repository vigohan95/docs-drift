<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- prometheus CONTRIBUTING.md has no rule about AI assistance. Commits need a DCO sign-off: git commit -s. -->
<!-- Patch: upstream-patches/prometheus/01-chunks-st-changed-on-hex.patch  (apply with `git apply` on top of prometheus/prometheus@0e62286556) -->

**Title:** docs(tsdb): 127 is 0x7F in the chunk format description

## What

One character: the XOR chunk section wrote 127 as 0xEF. The histogram chunk section of the same file has 0x7F.

## Why

Two places in the docs disagree.

This one matches the code: [`tsdb/docs/format/chunks.md` line 301](https://github.com/prometheus/prometheus/blob/0e62286556b1cb798d0afdde11f11689b6cfcd7a/tsdb/docs/format/chunks.md#L301-L303)

> Once a chunk has at least 127 samples,
> `st_changed_on` is set to 127 (0x7F) and the 128th and further samples will
> have `st_i` present.

This one does not: [`tsdb/docs/format/chunks.md` line 149](https://github.com/prometheus/prometheus/blob/0e62286556b1cb798d0afdde11f11689b6cfcd7a/tsdb/docs/format/chunks.md#L149-L151)

>    Due to the 7 bit limitation, once a chunk has at least 127 samples,
>    `st_changed_on` is set to 127 (0xEF) and the 127th and further samples will
>    have `st_i` present.

Code: 127 is 0x7F; tsdb/chunkenc/st.go:19 has `maxFirstSTChangeOn = 0x7F`. The two passages also disagree on 127th versus 128th sample; the patch leaves that to the maintainers.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
