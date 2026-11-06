<!-- NOTES for an issue, not a patch. Rewrite in your own words before posting. -->
<!-- fastify CONTRIBUTING.md: issues and pull requests must come from a human; pure-AI contributions are not welcome. -->

**Possible title:** docs: Server.md and Logging.md list different requirements for a custom logger

Two reference pages describe what a custom `loggerInstance` must provide, and the lists differ.

[`docs/Reference/Server.md` line 366](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/Server.md#L366-L368)

> A custom logger instance. The logger must be a Pino instance or conform to the
> Pino interface by having the following methods: `info`, `error`, `debug`,
> `fatal`, `warn`, `trace`, `child`.

[`docs/Reference/Logging.md` line 226](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/Logging.md#L226-L228)

> - **Methods:** `info`, `error`, `debug`, `fatal`, `warn`, `trace`, `silent`,
>   `child`
> - **Properties:** `level` (string)

What the code does:

- The runtime check, `validateLogger` in `lib/logger-factory.js` line 68, requires `info`, `error`, `debug`, `fatal`,
  `warn`, `trace` and `child`. It does not look at `silent` or `level`.
- The TypeScript type `FastifyBaseLogger` in `types/logger.d.ts` line 27 picks `level`, `info`, `error`, `debug`,
  `fatal`, `warn`, `trace` and `silent` from Pino's `BaseLogger`, and adds `child`.

So Server.md describes the runtime check and Logging.md describes the type. I did not prepare a patch because I do
not know which of the two the docs are meant to state. One option is for both pages to say that the seven methods are
checked at startup and that TypeScript users also need `level` and `silent`.

How I found it: a script that pairs doc passages which restate each other and asks the Clocked API whether they
conflict flagged this pair; I then read both pages and the two source files myself.
