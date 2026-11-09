"""Registry of the confirmed documentation defects.

One entry per distinct defect (several findings can point at the same one). Every quote
below is verbatim from the file at the pinned commit; `python review/defects.py --check`
verifies quotes and line numbers against the clones under ../targets.

"wrong" names the side that the project's source code contradicts (None when the source
does not settle it). Upstream maintainers are the final arbiters of every entry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCHED = "2026-11-07"  # undici: 2026-11-09

DEFECTS = [
    # ------------------------------------------------------------------ fastify
    {
        "id": "fastify-onrequest-body-null", "project": "fastify",
        "title": "What request.body is inside the onRequest hook",
        "a": {"path": "docs/Reference/Hooks.md", "lines": [73, 75],
              "quote": "> In the [onRequest](#onrequest) hook, `request.body` will always be\n> `undefined`, because the body parsing happens before the\n> [preValidation](#prevalidation) hook."},
        "b": {"path": "docs/Reference/TypeScript.md", "lines": [1540, 1541],
              "quote": "Notice: in the `onRequest` hook, request.body will always be null, because the\nbody parsing happens before the `preHandler` hook."},
        "wrong": "b",
        "source": "lib/request.js:40 sets `this.body = undefined`; lib/handle-request.js runs body parsing before the preValidation hooks.",
        "found_by": "standard run, both checks agreed", "findings": ["2f2b5d9048", "bfdf3bfa2b"],
        "patch": "fastify/01-typescript-onrequest-body-undefined.patch",
    },
    {
        "id": "fastify-preparsing-body-null", "project": "fastify",
        "title": "What request.body is inside the preParsing hook",
        "a": {"path": "docs/Reference/Hooks.md", "lines": [104, 106],
              "quote": "> In the [preParsing](#preparsing) hook, `request.body` will always be\n> `undefined`, because the body parsing happens before the\n> [preValidation](#prevalidation) hook."},
        "b": {"path": "docs/Reference/TypeScript.md", "lines": [1550, 1551],
              "quote": "Notice: in the `preParsing` hook, request.body will always be null, because the\nbody parsing happens before the `preValidation` hook."},
        "wrong": "b",
        "source": "lib/request.js:40 sets `this.body = undefined`.",
        "found_by": "standard run, both checks agreed", "findings": ["3359c8962b", "cc29289b7b"],
        "patch": "fastify/02-typescript-preparsing-body-undefined.patch",
    },
    {
        "id": "fastify-httpmethods-union", "project": "fastify",
        "title": "Which HTTP methods Fastify supports",
        "a": {"path": "docs/Reference/Server.md", "lines": [1667, 1668],
              "quote": "Fastify supports the `GET`, `HEAD`, `TRACE`, `DELETE`, `OPTIONS`,\n`PATCH`, `PUT`, `POST` and `QUERY` HTTP methods by default."},
        "b": {"path": "docs/Reference/TypeScript.md", "lines": [1103, 1104],
              "quote": "Union type of: `'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT' |\n'OPTIONS'`"},
        "wrong": "b",
        "source": "types/utils.d.ts:17-18 defines the union with 'QUERY', 'TRACE' and twelve more members. docs/Reference/Routes.md:34-35 repeats the Server.md list.",
        "found_by": "standard run, both checks agreed", "findings": ["2226ed1a9c", "ba8d973e45", "995662794b", "81db55b3f9"],
        "patch": "fastify/03-typescript-httpmethods-union.patch",
    },
    {
        "id": "fastify-onsend-payload-types", "project": "fastify",
        "title": "What an onSend hook may change the payload to",
        "a": {"path": "docs/Reference/Hooks.md", "lines": [240, 241],
              "quote": "> If you change the payload, you may only change it to a `string`, a\n> `Buffer`, a `stream`, a `ReadableStream`, a `Response`, or `null`."},
        "b": {"path": "docs/Reference/TypeScript.md", "lines": [1592, 1593],
              "quote": ">  If you change the payload, you may only change it to a string,\n> a Buffer, a stream, or null."},
        "wrong": "b",
        "source": "lib/reply.js:183-188 accepts web streams (`getReader`) and `Response` objects.",
        "found_by": "standard run, one check agreed", "findings": ["c4c048a190"],
        "patch": "fastify/04-typescript-onsend-payload-types.patch",
    },
    {
        "id": "fastify-reply-final-payload-types", "project": "fastify",
        "title": "Which types the final payload may have",
        "a": {"path": "docs/Reference/Hooks.md", "lines": [240, 241],
              "quote": "> If you change the payload, you may only change it to a `string`, a\n> `Buffer`, a `stream`, a `ReadableStream`, a `Response`, or `null`."},
        "b": {"path": "docs/Reference/Reply.md", "lines": [575, 583],
              "quote": "The type of the sent payload (after serialization and going through any\n[`onSend` hooks](./Hooks.md#onsend)) must be one of the following types,\notherwise, an error will be thrown:\n\n- `string`\n- `Buffer`\n- `stream`\n- `undefined`\n- `null`"},
        "wrong": "b",
        "source": "lib/reply.js:183-188 and the final send path accept web streams and `Response` objects without throwing.",
        "found_by": "not listed by the standard run; it surfaced in the both-orders run below the listing bar, and in the day-1 batch run",
        "findings": ["7b725ab594"],
        "patch": "fastify/05-reply-final-payload-types.patch",
    },
    {
        "id": "fastify-logger-methods", "project": "fastify",
        "title": "Which methods a custom logger must have",
        "a": {"path": "docs/Reference/Server.md", "lines": [366, 368],
              "quote": "A custom logger instance. The logger must be a Pino instance or conform to the\nPino interface by having the following methods: `info`, `error`, `debug`,\n`fatal`, `warn`, `trace`, `child`. For example:"},
        "b": {"path": "docs/Reference/Logging.md", "lines": [226, 228],
              "quote": "- **Methods:** `info`, `error`, `debug`, `fatal`, `warn`, `trace`, `silent`,\n  `child`\n- **Properties:** `level` (string)"},
        "wrong": None,
        "source": "The runtime check in lib/logger-factory.js:68 requires info, error, debug, fatal, warn, trace and child. The TypeScript type FastifyBaseLogger (types/logger.d.ts:27) also requires `level` and `silent`. Each page matches one of the two.",
        "found_by": "not listed by the standard run; day-1 batch run only (with one pair per request /compare returns no passage for it)",
        "findings": [],
        "patch": None,
        "patch_note": "No patch: which list the docs should give is a maintainer decision. Notes for an issue are in upstream-patches/fastify/06-logger-methods-issue-notes.md.",
    },
    # ------------------------------------------------------------------ typeorm
    {
        "id": "typeorm-es-version", "project": "typeorm",
        "title": "Which JavaScript version TypeORM targets",
        "a": {"path": "README.md", "lines": [19, 19],
              "quote": "and can be used with TypeScript and JavaScript (ES2023)."},
        "b": {"path": "docs/docs/getting-started.md", "lines": [5, 5],
              "quote": "and can be used with TypeScript and JavaScript (ES2021)."},
        "wrong": "b",
        "source": "PR #11382 (drop Node 16 and 18) changed the README from ES2021 to ES2023 and moved tsconfig.json to @tsconfig/node20; getting-started.md was not touched.",
        "found_by": "standard run, both checks agreed", "findings": ["29817c707f"],
        "patch": "typeorm/01-getting-started-es2023.patch",
    },
    {
        "id": "typeorm-update-bulk-overload", "project": "typeorm",
        "title": "What update() does with an array",
        "a": {"path": "docs/docs/working-with-entity-manager/5-entity-manager-api.md", "lines": [189, 198],
              "quote": "// Bulk updates with different conditions for each operation\nawait manager.update(User, [\n    { criteria: { id: 1 }, data: { firstName: \"Rizzrak\" } },\n    { criteria: { id: 2 }, data: { firstName: \"Karzzir\" } },\n    { criteria: { age: 18 }, data: { category: \"ADULT\" } },\n])\n// executes three separate UPDATE queries:"},
        "b": {"path": "docs/docs/working-with-entity-manager/6-repository-api.md", "lines": [154, 160],
              "quote": "You can pass an **array of condition objects** to match multiple distinct sets of rows in a single call (conditions are OR'd together):"},
        "wrong": "a",
        "source": "packages/typeorm/src/entity-manager/EntityManager.ts:897-927 has only update(target, criteria, partialEntity, options); no {criteria, data} form exists in src or test. The example came in with docs PR #12025; the feature PR #10910 implemented OR-ed condition arrays. The same PR added 'three separate queries' comments to the delete and softDelete examples, which the code also runs as one query.",
        "found_by": "standard run, one check agreed", "findings": ["e0951255dd"],
        "patch": "typeorm/02-entity-manager-update-bulk-example.patch",
        "extra_patch": "typeorm/03-delete-softdelete-single-query.patch",
    },
    # --------------------------------------------------------------- prometheus
    {
        "id": "prometheus-st-header-hex", "project": "prometheus",
        "title": "The value st_changed_on is capped at",
        "a": {"path": "tsdb/docs/format/chunks.md", "lines": [149, 151],
              "quote": "   Due to the 7 bit limitation, once a chunk has at least 127 samples,\n   `st_changed_on` is set to 127 (0xEF) and the 127th and further samples will\n   have `st_i` present."},
        "b": {"path": "tsdb/docs/format/chunks.md", "lines": [301, 303],
              "quote": "Once a chunk has at least 127 samples,\n`st_changed_on` is set to 127 (0x7F) and the 128th and further samples will\nhave `st_i` present."},
        "wrong": "a",
        "source": "127 is 0x7F; tsdb/chunkenc/st.go:19 has `maxFirstSTChangeOn = 0x7F`. The two passages also disagree on 127th versus 128th sample; the patch leaves that to the maintainers.",
        "found_by": "standard run, both checks agreed", "findings": ["d5d9babda2"],
        "patch": "prometheus/01-chunks-st-changed-on-hex.patch",
    },
    # ---------------------------------------------------------------- mikro-orm
    {
        "id": "mikroorm-flush-persist", "project": "mikro-orm",
        "title": "Which entities em.flush() checks for changes",
        "a": {"path": "docs/docs/guide/01-first-entity.md", "lines": [389, 389],
              "quote": "Whenever you call [`em.flush()`](/api/core/class/EntityManager#flush), the ORM will iterate over the Identity Map, and for each entity it compares the original state with the values that are currently set on the entity."},
        "b": {"path": "docs/docs/unit-of-work.md", "lines": [85, 85],
              "quote": "Now whenever you call `em.flush()` MikroORM will iterate over all entities you previously marked for persisting via `em.persist()`."},
        "wrong": "b",
        "source": "packages/core/src/unit-of-work/UnitOfWork.ts computeChangeSets walks the identity map (line 769) and then the persist stack (775). unit-of-work.md:34 itself says managed entities need no persist call.",
        "found_by": "standard run, one check agreed", "findings": ["0ec974ef3b", "8bbae9fd13"],
        "patch": "mikro-orm/01-unit-of-work-flush-managed-entities.patch",
    },
    {
        "id": "mikroorm-sqlite-ext-hook", "project": "mikro-orm",
        "title": "How to load SQLite extensions",
        "a": {"path": "docs/docs/usage-with-sql.md", "lines": [162, 162],
              "quote": "Load them via `pool.afterCreate`:"},
        "b": {"path": "docs/docs/usage-with-sqlite.md", "lines": [229, 229],
              "quote": "Once you've downloaded the binaries for the extensions you wish to use, they can be added via the `onCreateConnection` hook:"},
        "wrong": "a",
        "source": "packages/core/src/utils/Configuration.ts:639 defines `onCreateConnection`; PoolConfig (lines 805-812) has only min, max and idleTimeoutMillis.",
        "found_by": "standard run, one check agreed", "findings": ["1a81142d07"],
        "patch": "mikro-orm/02-usage-with-sql-sqlite-extensions-hook.patch",
    },
    {
        "id": "mikroorm-type-tojson-default", "project": "mikro-orm",
        "title": "What Type.toJSON() returns by default",
        "a": {"path": "docs/docs/custom-types.md", "lines": [20, 20],
              "quote": "Converts a value from its JS representation to its serialized JSON form of this type. By default, uses the runtime value."},
        "b": {"path": "docs/docs/defining-entities.md", "lines": [1616, 1616],
              "quote": "Converts a value from its JS representation to its serialized JSON form of this type. By default, converts to the database value."},
        "wrong": "b",
        "source": "packages/core/src/types/Type.ts:90-92: `toJSON(value) { return value; }`.",
        "found_by": "extended run (more pairs), one check agreed", "findings": ["84ca97ee15"],
        "patch": "mikro-orm/03-defining-entities-tojson-default.patch",
    },
    {
        "id": "mikroorm-raw-tojson", "project": "mikro-orm",
        "title": "Whether a raw() fragment can be serialized",
        "a": {"path": "docs/docs/entity-manager.md", "lines": [681, 681],
              "quote": "It disallows serialization (via `toJSON`) as well as working with the value"},
        "b": {"path": "docs/docs/raw-queries.md", "lines": [7, 7],
              "quote": "This fragment is represented by `RawQueryFragment` class instance that can be serialized to a string, so it can be used both as an object value and key."},
        "wrong": "a",
        "source": "packages/core/src/utils/RawQueryFragment.ts:100-102: `toJSON()` returns the string `raw('...')`; only conversion to a non-string primitive throws (lines 86-94).",
        "found_by": "extended run (more pairs), one check agreed", "findings": ["2576821b2a"],
        "patch": "mikro-orm/04-entity-manager-raw-tojson.patch",
    },
    # ------------------------------------------------------------ redux-toolkit
    {
        "id": "rtk-asyncthunk-resolved", "project": "redux-toolkit",
        "title": "The action types createAsyncThunk dispatches",
        "a": {"path": "docs/introduction/getting-started.md", "lines": [157, 157],
              "quote": "generates a thunk that dispatches `pending/fulfilled/rejected` action types based on that promise"},
        "b": {"path": "packages/toolkit/README.md", "lines": [78, 78],
              "quote": "generates a thunk that dispatches `pending/resolved/rejected` action types based on that promise"},
        "wrong": "b",
        "source": "packages/toolkit/src/createAsyncThunk.ts:544 builds `typePrefix + '/fulfilled'`.",
        "found_by": "standard run, both checks agreed", "findings": ["86618b3172"],
        "patch": "redux-toolkit/01-readme-createasyncthunk-fulfilled.patch",
    },
    {
        "id": "rtk-setuplisteners-refetchonmount", "project": "redux-toolkit",
        "title": "Which behaviours setupListeners() enables",
        "a": {"path": "docs/rtk-query/api/setupListeners.mdx", "lines": [14, 14],
              "quote": "A utility used to enable `refetchOnFocus` and `refetchOnReconnect` behaviors."},
        "b": {"path": "docs/introduction/getting-started.md", "lines": [184, 184],
              "quote": "A utility used to enable `refetchOnMount` and `refetchOnReconnect` behaviors."},
        "wrong": "b",
        "source": "packages/toolkit/src/query/core/setupListeners.ts dispatches onFocus, onFocusLost, onOnline and onOffline; nothing in it concerns mounting. The same wording is at docs/rtk-query/overview.md:85 and packages/toolkit/README.md:107.",
        "found_by": "extended run (more pairs), both checks agreed", "findings": ["b76f4539ff", "8dbc525de8"],
        "patch": "redux-toolkit/02-setuplisteners-refetchonfocus.patch",
    },
    # ------------------------------------------------------------------- rollup
    {
        "id": "rollup-esm-node-support", "project": "rollup",
        "title": "Whether Node.js supports ES modules",
        "a": {"path": "README.md", "lines": [71, 71],
              "quote": "Most browsers and Node.js support ES modules."},
        "b": {"path": "docs/introduction/index.md", "lines": [52, 52],
              "quote": "The specification is now fixed, but it is only implemented in modern browsers and not finalised in Node.js."},
        "wrong": "b",
        "source": "No source file settles this; the README paragraph is the newer wording of the same paragraph and matches Node.js since 12.17.",
        "found_by": "not listed by the standard run: /compare flagged it but labelled it a scope difference, which the listing rule drops",
        "findings": ["c4746c62b4"],
        "patch": "rollup/01-introduction-es-modules-support.patch",
    },
    # ------------------------------------------------------------------ undici (later run)
    {
        "id": "undici-keepalive-threshold-default", "project": "undici",
        "title": "The default of keepAliveTimeoutThreshold",
        "a": {"path": "docs/docs/api/Client.md", "lines": [66, 69],
              "quote": "  * `keepAliveTimeoutThreshold` {number|null} A number of milliseconds\n    subtracted from server *keep-alive* hints when overriding `keepAliveTimeout`,\n    to account for timing inaccuracies caused by e.g. transport latency.\n    **Default:** `2e3`."},
        "b": {"path": "docs/docs/api/H2CClient.md", "lines": [80, 82],
              "quote": "  * `keepAliveTimeoutThreshold` {number} A number of milliseconds subtracted from\n    server _keep-alive_ hints when overriding `keepAliveTimeout`, to account for\n    timing inaccuracies such as transport latency. **Default:** `1e3`."},
        "wrong": "b",
        "source": "lib/dispatcher/client.js:311 uses 2e3 when the option is unset, and H2CClient passes it through unchanged; #3145 changed it from 1e3. types/client.d.ts:61 and types/h2c-client.d.ts:43 also still said 1e3. The same PR fixes the H2CClient pipelining default in types/h2c-client.d.ts:47, found while checking.",
        "found_by": "later run on 2026-11-09, outside the measured 15 projects (47 pairs read): /compare flagged it; the checks did not run because the run's credit cap was reached",
        "findings": [], "later_findings": ["e493661deb"], "report": "reports/later/undici.json",
        "patch_note": "Fixed directly in the upstream pull request.",
    },
]

# Projects scanned after the measurements, with the commit each defect is pinned to. They are not demo
# targets and are not counted in review/summary.json.
LATER = {
    "undici": {"repo": "nodejs/undici", "commit": "691eb164daad1daff297c98b87494bdd92bcc3b3"},
}


def target_of(project: str) -> dict:
    from docsdrift.targets import TARGETS
    return TARGETS.get(project) or LATER[project]


UPSTREAM_SEARCH = (
    f"Searched each upstream repository's issues and pull requests on {SEARCHED} (gh search, read-only) "
    "for the file name and the key terms of each defect. No open or closed issue or PR about any of them was found. "
    "typeorm PR #12025 is the merged PR that introduced the update example. "
    "undici was searched on 2026-11-09: open PR #6172 fixes a different line of the same option list, nothing about this default."
)


def check() -> int:
    from docsdrift.targets import TARGETS, TARGETS_ROOT
    bad = 0
    for d in DEFECTS:
        root = TARGETS_ROOT / d["project"]
        if not root.exists():
            print("skip (no clone):", d["id"])
            continue
        for side in ("a", "b"):
            s = d[side]
            lines = (root / s["path"]).read_text(encoding="utf-8").split("\n")
            lo, hi = s["lines"]
            window = "\n".join(l.rstrip("\r") for l in lines[lo - 1:hi])
            first = s["quote"].split("\n")[0]
            if s["quote"] not in window:
                bad += 1
                print(f"MISMATCH {d['id']} side {side}: {s['path']}:{lo}-{hi}\n   expected: {first!r}\n   found:    {window[:200]!r}")
        if d.get("patch") and not (ROOT / "upstream-patches" / d["patch"]).exists():
            bad += 1
            print("missing patch", d["patch"])
    print(len(DEFECTS), "defects,", bad, "problems")
    return 1 if bad else 0


def entries():
    out = []
    for d in DEFECTS:
        t = target_of(d["project"])
        e = dict(d)
        e["repo"], e["commit"] = t["repo"], t["commit"]
        for side in ("a", "b"):
            s = dict(d[side])
            s["url"] = f"https://github.com/{t['repo']}/blob/{t['commit']}/{s['path']}#L{s['lines'][0]}-L{s['lines'][1]}"
            e[side] = s
        out.append(e)
    return out


def write():
    out = entries()
    (ROOT / "review" / "defects.json").write_text(
        json.dumps({"upstream_search": UPSTREAM_SEARCH, "defects": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if "--check" in sys.argv:
        sys.exit(check())
    print(len(write()), "defects written")
