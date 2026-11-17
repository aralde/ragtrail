# ragtrail (TypeScript)

Thin client for the [ragtrail](https://github.com/aralde/ragtrail) MCP server and a ready hook for
[astorlm](https://github.com/aralde/astorLM). Needs `pip install 'ragtrail[mcp]'` so that `ragtrail serve` is on the
path (or pass `command`). It is not on npm yet: from a checkout, build it with
`cd clients/typescript && npm ci && npm run build`, then install it in your app with
`npm install ./clients/typescript`.

```ts
import { RagtrailClient, ragtrailHook } from 'ragtrail'

const client = await RagtrailClient.spawn({ scope: 'docs', db: 'trails.db' })
const hit = await client.recall('How do I reset my password?')
await client.record({ query: 'How do I reset my password?', cited: ['n3'] })
await client.close()

const trail = ragtrailHook({ scope: 'docs' })   // pass as astorlm `hooks`
await trail.accept()                            // after the user accepts an answer
```

Development: `npm ci && npm run typecheck && npm test`. Set `RAGTRAIL_COMMAND` to a `ragtrail` executable to also run
the end-to-end test against the Python server.
