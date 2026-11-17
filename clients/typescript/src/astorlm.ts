import {
  RagtrailClient,
  type Outcome,
  type RecallResult,
  type RecordResult,
  type RejectResult,
  type SpawnOptions,
  type Step,
} from './client.ts'

interface Block {
  type: string
  text?: string
  name?: string
}

/** The parts of an astorlm `Message` the hook reads. */
export interface HookMessage {
  role: string
  content: Block[]
}

export interface AcceptOptions {
  outcome?: Outcome
  /** Node ids the answer cites; default: ids seen this run that the answer mentions. */
  cited?: string[]
}

export interface RagtrailHookOptions extends SpawnOptions {
  /** Use this client instead of spawning `ragtrail serve`. */
  client?: RagtrailClient
  budgetTokens?: number
  /** Node ids a tool call returned. Default: ids written as `[id]` in its output. */
  nodesFrom?: (toolName: string, input: unknown, output: string) => string[]
  /** Record without waiting for `accept()` when this returns true for the final answer. */
  autoAccept?: (context: { query: string; answer: string }) => boolean | Promise<boolean>
  /** Called when recall or record fails inside a hook; the agent run goes on. Default: `console.warn`. */
  onError?: (error: unknown) => void
}

/**
 * astorlm session hooks plus the controls the host app calls. Pass the object as `hooks`
 * (merge it if you have your own) and call `accept()` once the user accepts the answer.
 */
export interface RagtrailHook {
  beforeTurn(context: { turn: number; messages: HookMessage[] }): Promise<void>
  afterToolExecution(context: { toolName: string; input: unknown; output: string; isError: boolean }): Promise<string>
  afterTurn(context: { turn: number; lastMessage: HookMessage }): Promise<void>
  /** Record the path of the last answer. Returns null when there is nothing to record. */
  accept(options?: AcceptOptions): Promise<RecordResult | null>
  /** Demote the path recalled for the last question and drop the pending answer. */
  reject(): Promise<RejectResult | null>
  /** Recall result of the current question, if any. */
  readonly lastRecall: RecallResult | null
  close(): Promise<void>
}

const BRACKETED = /\[([A-Za-z0-9_.:\/#-]+)\]/g

function bracketedIds(text: string): string[] {
  return [...text.matchAll(BRACKETED)].map((m) => m[1] as string)
}

function textOf(message: HookMessage): string {
  return message.content
    .filter((b) => b.type === 'text' && typeof b.text === 'string')
    .map((b) => b.text)
    .join('\n')
}

function mentions(answer: string, id: string): boolean {
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(^|[^A-Za-z0-9_])${escaped}($|[^A-Za-z0-9_])`).test(answer)
}

interface Run {
  query: string
  recall: RecallResult | null
  steps: Step[]
  seen: string[]
  answer: string | null
}

/**
 * Hook that recalls before the first turn of each question and records after an accepted answer.
 *
 * @example
 * const trail = ragtrailHook({ scope: 'docs' })
 * const agent = await createAgent({ provider, tools, hooks: trail })
 * await agent.run('How do I reset my password?')
 * if (userLikedIt) await trail.accept()
 */
export function ragtrailHook(options: RagtrailHookOptions = {}): RagtrailHook {
  const nodesFrom = options.nodesFrom ?? ((_tool, _input, output) => bracketedIds(output))
  const onError = options.onError ?? ((error: unknown) => console.warn('ragtrail:', error))
  let client: Promise<RagtrailClient> | null = options.client ? Promise.resolve(options.client) : null
  let run: Run | null = null

  const connect = (): Promise<RagtrailClient> => {
    client ??= RagtrailClient.spawn(options)
    return client
  }

  const see = (ids: string[]): void => {
    if (!run) return
    for (const id of ids) if (!run.seen.includes(id)) run.seen.push(id)
  }

  const accept = async (acceptOptions: AcceptOptions = {}): Promise<RecordResult | null> => {
    const current = run
    if (!current || current.answer === null) return null
    run = null
    const answer = current.answer
    const cited = acceptOptions.cited ?? current.seen.filter((id) => mentions(answer, id))
    if (cited.length === 0) return null
    const steps = current.steps.map((s) => ({ ...s, returned: (s.returned ?? []).filter((id) => cited.includes(id)) }))
    return (await connect()).record({ query: current.query, cited, outcome: acceptOptions.outcome, steps })
  }

  return {
    get lastRecall() {
      return run?.recall ?? null
    },

    async beforeTurn({ turn, messages }) {
      if (turn !== 1) return
      run = null
      const user = messages.findLast((m) => m.role === 'user')
      const query = user ? textOf(user).trim() : ''
      if (!user || !query) return
      run = { query, recall: null, steps: [], seen: [], answer: null }
      try {
        const result = await (await connect()).recall(query, { budgetTokens: options.budgetTokens })
        run.recall = result
        if (result.mode !== 'miss') {
          see(result.nodes)
          user.content.push({ type: 'text', text: result.text })
        }
      } catch (error) {
        onError(error)
      }
    },

    async afterToolExecution({ toolName, input, output, isError }) {
      if (run && !isError && !toolName.startsWith('ragtrail__')) {
        const returned = nodesFrom(toolName, input, output)
        const args = input && typeof input === 'object' ? (input as Record<string, unknown>) : {}
        run.steps.push({ tool: toolName, args, returned })
        see(returned)
      }
      return output
    },

    async afterTurn({ lastMessage }) {
      if (!run || lastMessage.content.some((b) => b.type === 'tool_use')) return
      run.answer = textOf(lastMessage)
      if (!options.autoAccept) return
      try {
        if (await options.autoAccept({ query: run.query, answer: run.answer })) await accept()
      } catch (error) {
        onError(error)
      }
    },

    accept,

    async reject() {
      const current = run
      run = null
      if (!current) return null
      return (await connect()).reject(current.query)
    },

    async close() {
      if (client) await (await client).close()
      client = null
    },
  }
}
