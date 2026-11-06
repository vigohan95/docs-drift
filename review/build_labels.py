"""Verdicts for every raw /compare finding of the v2 pipeline.

Each entry: finding id -> (label, defect id or None, side the source code agrees with, reason).
label: "true" = the two passages really contradict each other; "false" = they do not.
Every verdict was reached by opening both passages at the pinned commit and, for the
true ones, the project's source code. Upstream maintainers are the final arbiters.
Run this file to regenerate review/labels_v2.json.
"""
import json
from pathlib import Path

T, F = "true", "false"
SIBLING = "Two parallel documents about different things"

V = {
 # ---------------------------------------------------------------- fastify
 "2f2b5d9048": (T, "fastify-onrequest-body-null", "a", "Hooks.md:73-75 says request.body is always undefined in onRequest (parsing happens before preValidation); TypeScript.md:1540-1541 says always null (before preHandler). lib/request.js:40 sets this.body = undefined."),
 "3359c8962b": (T, "fastify-preparsing-body-null", "a", "Hooks.md:104-106 says undefined in preParsing; TypeScript.md:1550-1551 says null. lib/request.js:40 sets this.body = undefined."),
 "ba8d973e45": (T, "fastify-httpmethods-union", "a", "Routes.md:34-35 lists TRACE and QUERY among supported methods; TypeScript.md:1103-1104 documents fastify.HTTPMethods as a 7-member union without them. types/utils.d.ts:17-18 has QUERY, TRACE and more."),
 "2226ed1a9c": (T, "fastify-httpmethods-union", "a", "Same stale union in TypeScript.md:1103-1104, against Server.md:1667-1668."),
 "c4c048a190": (T, "fastify-onsend-payload-types", "a", "Hooks.md:240-241 allows string, Buffer, stream, ReadableStream, Response or null; TypeScript.md:1592-1593 only string, Buffer, stream or null. lib/reply.js:183-188 accepts web streams and Response."),
 "b165a9cd62": (F, None, None, "Pairs the onRequest note in Hooks.md with the preParsing note in TypeScript.md: two different hooks. The real TypeScript.md errors are reported by two other findings."),
 # ---------------------------------------------------------------- typeorm
 "e0951255dd": (T, "typeorm-update-bulk-overload", "b", "entity-manager-api.md:189-199 shows manager.update(User, [{criteria, data}, ...]) running three separate UPDATEs; repository-api.md:154-160 says an array is a list of conditions OR-ed into one UPDATE. EntityManager.ts:897-927 only has update(target, criteria, partialEntity, options). The example came in with docs PR #12025; the feature PR #10910 implemented OR-ed condition arrays."),
 "29817c707f": (T, "typeorm-es-version", None, "README.md:19 says JavaScript (ES2023); docs/docs/getting-started.md:5 says (ES2021) in the same sentence. packages/typeorm/tsconfig.json extends @tsconfig/node20; tsconfig.browser.json uses lib es2023."),
 "2a4c1a148e": (F, None, None, "Two sections of one page, one about null and one about undefined."),
 # ------------------------------------------------------------- prometheus
 "d5d9babda2": (T, "prometheus-st-header-hex", "b", "tsdb/docs/format/chunks.md:148-150 says st_changed_on is set to 127 (0xEF) and the 127th and further samples carry st_i; lines 302-304 of the same file say 127 (0x7F) and the 128th. 127 is 0x7F, and tsdb/chunkenc/st.go:19 has maxFirstSTChangeOn = 0x7F."),
 "e480859f1e": (F, None, None, SIBLING + ": chunks.md (block chunks) and head_chunks.md (head chunks)."),
 "4998603c77": (F, None, None, "Reference says the built-in default is 1m; the tutorial example config sets 15s."),
 "e5f4c606de": (F, None, None, "Histogram chunk section vs float histogram chunk section."),
 "b5ef08a1fa": (F, None, None, "Arithmetic operators vs comparison operators: different rules for different operator classes."),
 # ------------------------------------------------------------------- vite
 "c8aa3dc8cb": (F, None, None, "`hotUpdate` and `handleHotUpdate` are two different plugin hooks."),
 # ------------------------------------------------------------------- jest
 "a1ae0202f1": (F, None, None, SIBLING + ": READMEs of two packages."),
 "207557013c": (F, None, None, SIBLING + ": diff-sequences and jest-diff are different packages with different diff functions."),
 "2a05a39a22": (F, None, None, "Same pair as 207557013c."),
 "9477538596": (F, None, None, "Same pair as 207557013c."),
 "a1cfc5254e": (F, None, None, "Same pair as 207557013c."),
 "b35a747b64": (F, None, None, "User option `indent` is a number; the normalised config.indent handed to plugins is a string (pretty-format/src/types.ts:51)."),
 "938fe7ac73": (F, None, None, "`runner` and `testRunner` are two different options."),
 "b1fa385223": (F, None, None, "Default of `runner` (jest-runner) vs default of `testRunner` (jest-circus): two different options."),
 "7bf6348c5f": (F, None, None, "Custom `runner` vs custom `testRunner`: two different options."),
 # --------------------------------------------------------------- mongoose
 "2b4226d453": (F, None, None, "Migration guide to 6 (driver 4.0) vs migration guide to 7 (driver >= 5.0): each is correct for its own version."),
 "5b661a1438": (F, None, None, "Migration guides to 6 and to 9 describe the behaviour of different major versions."),
 # -------------------------------------------------------------- mikro-orm
 "8bbae9fd13": (T, "mikroorm-flush-persist", "a", "guide/01-first-entity.md:389 says flush iterates over the identity map; unit-of-work.md:85 says it iterates over the entities marked via em.persist(). UnitOfWork.ts computeChangeSets walks the identity map (line 769) as well as the persist stack; unit-of-work.md:34 itself says persist is not needed for managed entities."),
 "0ec974ef3b": (T, "mikroorm-flush-persist", "a", "Same defect: guide/01-first-entity.md:391 (updates even without em.persist()) against the unit-of-work.md passage that contains line 85. The quote returned for side B is two sentences earlier than the conflicting one."),
 "1a81142d07": (T, "mikroorm-sqlite-ext-hook", "b", "usage-with-sql.md:162-172 loads SQLite extensions through pool.afterCreate; usage-with-sqlite.md:229-236 through the onCreateConnection hook. Configuration.ts:639 defines onCreateConnection; PoolConfig (805-812) has only min, max and idleTimeoutMillis."),
 "269e58126a": (F, None, None, "configuration.md describes the current default; the v4-to-v5 upgrade guide describes the previous behaviour as previous."),
 "ef26b00142": (F, None, None, SIBLING + ": PGlite page and sql.js page."),
 # ----------------------------------------------------------------- eslint
 "9326d9f226": (F, None, None, "Migration guide to v8 (CLIEngine removed) vs migration guide to v7 (CLIEngine deprecated): each is correct for its version."),
 "0309eaaec1": (F, None, None, "Same pair of migration guides as 9326d9f226."),
 "9fce339194": (F, None, None, "Same pair of migration guides as 9326d9f226."),
 "3482256666": (F, None, None, SIBLING + ": links of two different tutorials."),
 "04b0beca9b": (F, None, None, "Migration guides to v8 and v9 each enabled four rules."),
 "dfda7b2169": (F, None, None, "Migration guides to v10 and v7 each enabled three rules."),
 "e469bad048": (F, None, None, "Migration guide to v8 (four new rules) vs to v7 (three new rules)."),
 # ---------------------------------------------------------- redux-toolkit
 "86618b3172": (T, "rtk-asyncthunk-resolved", "a", "docs/introduction/getting-started.md:157 says createAsyncThunk dispatches pending/fulfilled/rejected; packages/toolkit/README.md:78 says pending/resolved/rejected. createAsyncThunk.ts:544 builds typePrefix + '/fulfilled'."),
 # ----------------------------------------------------------------- vitest
 "6b5e83e074": (F, None, None, "coverage.md (default false, inherits from test.changed) and cli-generated.md (inherits from --changed) agree."),
}
# vitest: the other 17 raw findings are all between sibling pages (react/vue/svelte
# browser packages; TestCase/TestSuite/TestModule/TestSpecification API pages).
for _fid, _why in {
    "f766a81394": "react.md vs svelte.md", "78a90557c2": "react.md vs vue.md", "8bae9cf6cb": "svelte.md vs vue.md",
    "b565e5fe61": "test-case.md vs test-module.md", "fa0e6dbc35": "test-case.md vs test-module.md",
    "b279419c19": "react.md vs svelte.md", "f51b47e7db": "react.md vs svelte.md", "00e821ba42": "react.md vs vue.md",
    "be2bacd0c7": "react.md vs vue.md", "5b1334b3aa": "react.md vs vue.md", "0ee3f3e8c1": "svelte.md vs vue.md",
    "965ee405c7": "svelte.md vs vue.md", "fc3d0974da": "svelte.md vs vue.md",
    "c40322fff6": "test-case.md vs test-specification.md", "7e8e93e36f": "test-case.md vs test-suite.md",
    "09d16ba1f6": "test-case.md vs test-suite.md", "2e7f202b2d": "test-case.md vs test-suite.md",
}.items():
    V[_fid] = (F, None, None, f"{SIBLING}: {_why}.")


def write():
    out = {fid: {"label": l, "defect": d, "source_agrees_with": s, "reason": r} for fid, (l, d, s, r) in V.items()}
    Path(__file__).with_name("labels_v2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(len(write()), "labels written")
