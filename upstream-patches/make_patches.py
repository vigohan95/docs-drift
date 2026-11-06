"""Generate one minimal patch per confirmed contradiction.

Each patch is produced by editing the file in the pinned clone under ../targets/<project>,
running `git diff`, and restoring the file. Nothing is committed or pushed anywhere.

    python -X utf8 upstream-patches/make_patches.py

The PR text drafts next to the patches are written by hand; see the *.md files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = HERE.parent.parent / "targets"

PATCHES = [
    # ------------------------------------------------------------------ fastify
    ("fastify", "01-typescript-onrequest-body-undefined", [
        ("docs/Reference/TypeScript.md",
         "Notice: in the `onRequest` hook, request.body will always be null, because the\n"
         "body parsing happens before the `preHandler` hook.",
         "Notice: in the `onRequest` hook, request.body will always be undefined, because\n"
         "the body parsing happens before the `preValidation` hook."),
    ]),
    ("fastify", "02-typescript-preparsing-body-undefined", [
        ("docs/Reference/TypeScript.md",
         "Notice: in the `preParsing` hook, request.body will always be null, because the\n"
         "body parsing happens before the `preValidation` hook.",
         "Notice: in the `preParsing` hook, request.body will always be undefined, because\n"
         "the body parsing happens before the `preValidation` hook."),
    ]),
    ("fastify", "03-typescript-httpmethods-union", [
        ("docs/Reference/TypeScript.md",
         "Union type of: `'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT' |\n"
         "'OPTIONS'`",
         "Union type of: `'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT' |\n"
         "'OPTIONS' | 'QUERY' | 'PROPFIND' | 'PROPPATCH' | 'MKCOL' | 'COPY' | 'MOVE' |\n"
         "'LOCK' | 'UNLOCK' | 'TRACE' | 'SEARCH' | 'REPORT' | 'MKCALENDAR'` and their\n"
         "lowercase forms. Any other string is accepted as well."),
    ]),
    ("fastify", "04-typescript-onsend-payload-types", [
        ("docs/Reference/TypeScript.md",
         ">  If you change the payload, you may only change it to a string,\n"
         "> a Buffer, a stream, or null.",
         ">  If you change the payload, you may only change it to a string,\n"
         "> a Buffer, a stream, a ReadableStream, a Response, or null."),
    ]),
    ("fastify", "05-reply-final-payload-types", [
        ("docs/Reference/Reply.md",
         "- `string`\n- `Buffer`\n- `stream`\n- `undefined`\n- `null`\n",
         "- `string`\n- `Buffer`\n- `stream`\n- `ReadableStream`\n- `Response`\n- `undefined`\n- `null`\n"),
    ]),
    # ------------------------------------------------------------------ typeorm
    ("typeorm", "01-getting-started-es2023", [
        ("docs/docs/getting-started.md",
         "and can be used with TypeScript and JavaScript (ES2021).",
         "and can be used with TypeScript and JavaScript (ES2023)."),
    ]),
    ("typeorm", "02-entity-manager-update-bulk-example", [
        ("docs/docs/working-with-entity-manager/5-entity-manager-api.md",
         "// executes UPDATE user SET firstName = Rizzrak WHERE id = 1\n"
         "\n"
         "// Bulk updates with different conditions for each operation\n"
         "await manager.update(User, [\n"
         "    { criteria: { id: 1 }, data: { firstName: \"Rizzrak\" } },\n"
         "    { criteria: { id: 2 }, data: { firstName: \"Karzzir\" } },\n"
         "    { criteria: { age: 18 }, data: { category: \"ADULT\" } },\n"
         "])\n"
         "// executes three separate UPDATE queries:\n"
         "// UPDATE user SET firstName = Rizzrak WHERE id = 1\n"
         "// UPDATE user SET firstName = Karzzir WHERE id = 2\n"
         "// UPDATE user SET category = ADULT WHERE age = 18\n"
         "```",
         "// executes UPDATE user SET firstName = Rizzrak WHERE id = 1\n"
         "```"),
    ]),
    ("typeorm", "03-delete-softdelete-single-query", [
        ("docs/docs/working-with-entity-manager/5-entity-manager-api.md",
         "// Bulk deletes with different conditions for each operation\n"
         "await manager.delete(User, [{ firstName: \"Timber\" }, { age: 18 }, { id: 42 }])\n"
         "// executes three separate DELETE queries:\n"
         "// DELETE FROM user WHERE firstName = Timber\n"
         "// DELETE FROM user WHERE age = 18\n"
         "// DELETE FROM user WHERE id = 42\n",
         "// An array of condition objects is OR'd into one query\n"
         "await manager.delete(User, [{ firstName: \"Timber\" }, { age: 18 }, { id: 42 }])\n"
         "// executes DELETE FROM user WHERE firstName = Timber OR age = 18 OR id = 42\n"),
        ("docs/docs/working-with-entity-manager/6-repository-api.md",
         "// Bulk soft deletes with different conditions for each operation\n"
         "await repository.softDelete([{ firstName: \"Jake\" }, { age: 25 }, { id: 42 }])\n"
         "// executes three separate UPDATE queries (setting deletedAt timestamp):\n"
         "// UPDATE entity SET deletedAt = NOW() WHERE firstName = Jake\n"
         "// UPDATE entity SET deletedAt = NOW() WHERE age = 25\n"
         "// UPDATE entity SET deletedAt = NOW() WHERE id = 42\n",
         "// An array of condition objects is OR'd into one query\n"
         "await repository.softDelete([{ firstName: \"Jake\" }, { age: 25 }, { id: 42 }])\n"
         "// executes one UPDATE setting deletedAt WHERE firstName = Jake OR age = 25 OR id = 42\n"),
    ]),
    # --------------------------------------------------------------- prometheus
    ("prometheus", "01-chunks-st-changed-on-hex", [
        ("tsdb/docs/format/chunks.md",
         "`st_changed_on` is set to 127 (0xEF) and the 127th and further samples will",
         "`st_changed_on` is set to 127 (0x7F) and the 127th and further samples will"),
    ]),
    # ---------------------------------------------------------------- mikro-orm
    ("mikro-orm", "01-unit-of-work-flush-managed-entities", [
        ("docs/docs/unit-of-work.md",
         "Now whenever you call `em.flush()` MikroORM will iterate over all entities you previously marked "
         "for persisting via `em.persist()`.",
         "Now whenever you call `em.flush()` MikroORM will iterate over all managed entities in the identity "
         "map, together with the new entities you marked for persisting via `em.persist()`."),
    ]),
    ("mikro-orm", "02-usage-with-sql-sqlite-extensions-hook", [
        ("docs/docs/usage-with-sql.md",
         "Load them via `pool.afterCreate`:\n"
         "\n"
         "```ts\n"
         "const orm = await MikroORM.init({\n"
         "  // ...\n"
         "  pool: {\n"
         "    afterCreate: (conn: any, done: any) => {\n"
         "      conn.loadExtension('/path/to/sqlean');\n"
         "      done(null, conn);\n"
         "    },\n"
         "  },\n"
         "});\n"
         "```",
         "Load them via the `onCreateConnection` hook:\n"
         "\n"
         "```ts\n"
         "const orm = await MikroORM.init({\n"
         "  // ...\n"
         "  onCreateConnection(connection) {\n"
         "    connection.loadExtension('/path/to/sqlean');\n"
         "  },\n"
         "});\n"
         "```"),
    ]),
    ("mikro-orm", "03-defining-entities-tojson-default", [
        ("docs/docs/defining-entities.md",
         "Converts a value from its JS representation to its serialized JSON form of this type. "
         "By default, converts to the database value.",
         "Converts a value from its JS representation to its serialized JSON form of this type. "
         "By default, uses the runtime value."),
    ]),
    ("mikro-orm", "04-entity-manager-raw-tojson", [
        ("docs/docs/entity-manager.md",
         "It disallows serialization (via `toJSON`) as well as working with the value (via "
         "[`valueOf()`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/valueOf)).",
         "It disallows working with the value: converting it to a primitive, other than using it as an "
         "object key, throws an error."),
    ]),
    # ------------------------------------------------------------ redux-toolkit
    ("redux-toolkit", "01-readme-createasyncthunk-fulfilled", [
        ("packages/toolkit/README.md",
         "generates a thunk that dispatches `pending/resolved/rejected` action types",
         "generates a thunk that dispatches `pending/fulfilled/rejected` action types"),
    ]),
    ("redux-toolkit", "02-setuplisteners-refetchonfocus", [
        ("docs/introduction/getting-started.md",
         "A utility used to enable `refetchOnMount` and `refetchOnReconnect` behaviors.",
         "A utility used to enable `refetchOnFocus` and `refetchOnReconnect` behaviors."),
        ("docs/rtk-query/overview.md",
         "A utility used to enable `refetchOnMount` and `refetchOnReconnect` behaviors.",
         "A utility used to enable `refetchOnFocus` and `refetchOnReconnect` behaviors."),
        ("packages/toolkit/README.md",
         "A utility used to enable refetchOnMount and refetchOnReconnect behaviors.",
         "A utility used to enable refetchOnFocus and refetchOnReconnect behaviors."),
    ]),
    # ------------------------------------------------------------------- rollup
    ("rollup", "01-introduction-es-modules-support", [
        ("docs/introduction/index.md",
         "The specification is now fixed, but it is only implemented in modern browsers and not finalised in Node.js.",
         "Most browsers and Node.js support ES modules. However, Node.js releases before 12.17 support ES modules "
         "only behind the `--experimental-modules` flag, and older browsers like Internet Explorer do not support "
         "ES modules at all."),
    ]),
]

def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace"))
    return out.stdout.decode("utf-8")


def replace_once(path: Path, old: str, new: str):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    o, n = old.encode("utf-8"), new.encode("utf-8")
    if crlf:
        o, n = o.replace(b"\n", b"\r\n"), n.replace(b"\n", b"\r\n")
    count = raw.count(o)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence, found {count}: {old[:60]!r}")
    path.write_bytes(raw.replace(o, n))


def main() -> int:
    made = 0
    for project, slug, edits in PATCHES:
        repo = TARGETS / project
        if git(repo, "status", "--porcelain").strip():
            print(f"{project}: working tree is not clean, skipping", file=sys.stderr)
            return 1
        files = []
        try:
            for rel, old, new in edits:
                replace_once(repo / rel, old, new)
                files.append(rel)
            diff = git(repo, "diff", "--no-color", "--", *files)
        finally:
            git(repo, "checkout", "--", *{rel for rel, _, _ in edits})
        if not diff.strip():
            raise RuntimeError(f"{project}/{slug}: empty diff")
        out = HERE / project / f"{slug}.patch"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(diff.replace("\r\n", "\n").encode("utf-8"))
        made += 1
        print(f"{project}/{slug}.patch  ({diff.count(chr(10))} lines, base {git(repo, 'rev-parse', '--short', 'HEAD').strip()})")
        assert not git(repo, "status", "--porcelain").strip()
    print(made, "patches written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
