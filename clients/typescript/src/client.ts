import { mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

export type Mode = 'prefetch' | 'hint' | 'miss'
export type Outcome = 'verified' | 'feedback' | 'accepted'

/** Anything that can call an MCP tool: an `@modelcontextprotocol/sdk` `Client` fits. */
export interface ToolCaller {
  callTool(params: { name: string; arguments?: Record<string, unknown> }): Promise<unknown>
}

export interface Step {
  tool: string
  args?: Record<string, unknown>
  returned?: string[]
}

export interface RecallResult {
  mode: Mode
  similarity: number
  trajectoryId: string | null
  nodes: string[]
  stale: string[]
  matchedBy: 'lexical' | 'embedding' | null
  /** What the agent should see; empty-handed misses say "search as usual". */
  text: string
}

export interface RecordInput {
  query: string
  cited: string[]
  outcome?: Outcome
  steps?: Step[]
}

export interface RecordResult {
  recorded: boolean
  trajectoryId: string | null
  nodes: string[]
  text: string
}

export interface RejectResult {
  rejected: string[]
  text: string
}

export interface SpawnOptions {
  /** Scope the server is bound to. Default `default`. */
  scope?: string
  /** SQLite file or `postgresql://` URL. Default `~/.ragtrail/trails.db`. */
  db?: string
  /** Executable that runs the ragtrail CLI. Default `ragtrail`. */
  command?: string
  /** Arguments placed before `serve`, e.g. `['run', 'ragtrail']` with `command: 'uv'`. */
  commandArgs?: string[]
  /** Extra `ragtrail serve` flags, e.g. `['--subforest', 'corpus.db']`. */
  serverArgs?: string[]
  env?: Record<string, string>
}

export class RagtrailError extends Error {
  override name = 'RagtrailError'
}

interface ToolResult {
  isError?: boolean
  content?: Array<{ type: string; text?: string }>
  structuredContent?: Record<string, unknown>
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []
}

/**
 * Thin client for the ragtrail MCP server's `recall`, `record` and `reject` tools.
 *
 * @example
 * const trail = await RagtrailClient.spawn({ scope: 'docs' })
 * const hit = await trail.recall('How do I reset my password?')
 * if (hit.mode !== 'miss') console.log(hit.text)
 * await trail.record({ query: 'How do I reset my password?', cited: ['n3'] })
 * await trail.close()
 */
export class RagtrailClient {
  readonly #caller: ToolCaller
  readonly #close: () => Promise<void>

  constructor(caller: ToolCaller, close: () => Promise<void> = async () => {}) {
    this.#caller = caller
    this.#close = close
  }

  /** Start `ragtrail serve` over stdio and connect to it. */
  static async spawn(options: SpawnOptions = {}): Promise<RagtrailClient> {
    const { Client } = await import('@modelcontextprotocol/sdk/client/index.js')
    const { StdioClientTransport } = await import('@modelcontextprotocol/sdk/client/stdio.js')
    const db = options.db ?? join(homedir(), '.ragtrail', 'trails.db')
    if (!/^postgres(ql)?:\/\//.test(db)) mkdirSync(dirname(db), { recursive: true })
    const transport = new StdioClientTransport({
      command: options.command ?? 'ragtrail',
      args: [
        ...(options.commandArgs ?? []),
        'serve',
        '--db',
        db,
        '--scope',
        options.scope ?? 'default',
        ...(options.serverArgs ?? []),
      ],
      env: options.env,
    })
    const client = new Client({ name: 'ragtrail-ts', version: '0.1.0' })
    await client.connect(transport)
    return new RagtrailClient(client, () => client.close())
  }

  async #call(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    const result = (await this.#caller.callTool({ name, arguments: args })) as ToolResult
    const data = result.structuredContent ?? {}
    const text =
      typeof data.text === 'string'
        ? data.text
        : (result.content ?? []).map((c) => c.text ?? '').join('\n')
    if (result.isError) throw new RagtrailError(text || `ragtrail ${name} failed`)
    return { ...data, text }
  }

  /** Look up the path of a similar question answered before. Pass the user's question verbatim. */
  async recall(query: string, options: { budgetTokens?: number } = {}): Promise<RecallResult> {
    const args: Record<string, unknown> = { query }
    if (options.budgetTokens !== undefined) args.budget_tokens = options.budgetTokens
    const data = await this.#call('recall', args)
    const mode = data.mode === 'prefetch' || data.mode === 'hint' ? data.mode : 'miss'
    return {
      mode,
      similarity: typeof data.similarity === 'number' ? data.similarity : 0,
      trajectoryId: typeof data.trajectory_id === 'string' ? data.trajectory_id : null,
      nodes: strings(data.nodes),
      stale: strings(data.stale),
      matchedBy: data.matched_by === 'lexical' || data.matched_by === 'embedding' ? data.matched_by : null,
      text: String(data.text),
    }
  }

  /** Save the path that answered `query`. Never pass the answer text. */
  async record(input: RecordInput): Promise<RecordResult> {
    const args: Record<string, unknown> = {
      query: input.query,
      cited: input.cited,
      outcome: input.outcome ?? 'accepted',
    }
    if (input.steps?.length) {
      args.steps = input.steps.map((s) => ({ tool: s.tool, args: s.args ?? {}, returned: s.returned ?? [] }))
    }
    const data = await this.#call('record', args)
    return {
      recorded: data.recorded === true,
      trajectoryId: typeof data.trajectory_id === 'string' ? data.trajectory_id : null,
      nodes: strings(data.nodes),
      text: String(data.text),
    }
  }

  /** Report that the user rejected the answer to `query`, so its recalled path is demoted. */
  async reject(query: string): Promise<RejectResult> {
    const data = await this.#call('reject', { query })
    return { rejected: strings(data.rejected), text: String(data.text) }
  }

  async close(): Promise<void> {
    await this.#close()
  }
}
