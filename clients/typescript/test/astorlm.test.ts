import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ragtrailHook, type HookMessage } from '../src/index.ts'
import { fakeClient, type Call } from './fake.ts'

const MISS: { structuredContent: Record<string, unknown> } = { structuredContent: { text: 'ragtrail: no similar question solved before.', mode: 'miss', nodes: [] } }
const RECORDED = { structuredContent: { text: 'Recorded', recorded: true, trajectory_id: 't1', nodes: ['n3'] } }

function server(recall = MISS) {
  return fakeClient((call: Call) => (call.name === 'recall' ? recall : RECORDED))
}

async function runQuestion(hook: ReturnType<typeof ragtrailHook>, question: string, answer: string) {
  const user: HookMessage = { role: 'user', content: [{ type: 'text', text: question }] }
  await hook.beforeTurn({ turn: 1, messages: [user] })
  await hook.afterTurn({ turn: 1, lastMessage: { role: 'assistant', content: [{ type: 'tool_use', name: 'docs__read' }] } })
  await hook.afterToolExecution({
    toolName: 'docs__read',
    input: { id: 'n3' },
    output: 'Passwords › Reset [n3]\nUse the reset link. See also [n9].',
    isError: false,
  })
  await hook.beforeTurn({ turn: 2, messages: [user] })
  await hook.afterTurn({ turn: 2, lastMessage: { role: 'assistant', content: [{ type: 'text', text: answer }] } })
  return user
}

test('recalls once per question and records only on accept', async () => {
  const { client, calls } = server()
  const hook = ragtrailHook({ client })
  await runQuestion(hook, 'How do I reset my password?', 'Use the reset link [n3].')
  assert.deepEqual(calls.map((c) => c.name), ['recall'])
  assert.equal(hook.lastRecall?.mode, 'miss')

  const result = await hook.accept()
  assert.equal(result?.recorded, true)
  assert.deepEqual(calls[1], {
    name: 'record',
    arguments: {
      query: 'How do I reset my password?',
      cited: ['n3'],
      outcome: 'accepted',
      steps: [{ tool: 'docs__read', args: { id: 'n3' }, returned: ['n3'] }],
    },
  })
  assert.equal(await hook.accept(), null)
})

test('never sends the answer text to the server', async () => {
  const { client, calls } = server()
  const hook = ragtrailHook({ client })
  await runQuestion(hook, 'q?', 'SECRET ANSWER [n3]')
  await hook.accept()
  assert.ok(!JSON.stringify(calls).includes('SECRET'))
})

test('a hit is appended to the user message', async () => {
  const hint = {
    structuredContent: { text: 'ragtrail: similar question solved before (mode=hint)', mode: 'hint', nodes: ['n3'] },
  }
  const { client } = server(hint)
  const hook = ragtrailHook({ client })
  const user = await runQuestion(hook, 'reset password?', 'Done.')
  assert.equal(user.content.at(-1)?.text, 'ragtrail: similar question solved before (mode=hint)')
})

test('nothing is recorded without a cited node', async () => {
  const { client, calls } = server()
  const hook = ragtrailHook({ client })
  await runQuestion(hook, 'q?', 'No citation here.')
  assert.equal(await hook.accept(), null)
  assert.deepEqual(calls.map((c) => c.name), ['recall'])
})

test('autoAccept records after the final answer', async () => {
  const { client, calls } = server()
  const hook = ragtrailHook({ client, autoAccept: ({ answer }) => answer.includes('[n3]') })
  await runQuestion(hook, 'q?', 'See [n3].')
  assert.deepEqual(calls.map((c) => c.name), ['recall', 'record'])
})

test('reject demotes the last question and drops the pending answer', async () => {
  const { client, calls } = server()
  const hook = ragtrailHook({ client })
  await runQuestion(hook, 'q?', 'See [n3].')
  await hook.reject()
  assert.deepEqual(calls.at(-1), { name: 'reject', arguments: { query: 'q?' } })
  assert.equal(await hook.accept(), null)
})

test('a failing server does not break the run', async () => {
  const errors: unknown[] = []
  const { client } = fakeClient(() => ({ isError: true, text: 'boom' }))
  const hook = ragtrailHook({ client, onError: (e) => errors.push(e) })
  await runQuestion(hook, 'q?', 'See [n3].')
  assert.equal(errors.length, 1)
})

test('wired into a real astorlm agent', async () => {
  const { createAgent } = await import('astorlm')
  type Agent = Parameters<typeof createAgent>[0]
  const hint = {
    structuredContent: { text: 'ragtrail: hint, start with read("n3")', mode: 'hint', nodes: ['n3'] },
  }
  const { client, calls } = server(hint)
  const seenByModel: string[] = []
  let call = 0
  const provider: Agent['provider'] = {
    name: 'scripted',
    model: 'scripted',
    async *stream({ messages }) {
      seenByModel.push(JSON.stringify(messages))
      call += 1
      const content =
        call === 1
          ? [{ type: 'tool_use' as const, id: 'u1', name: 'read', input: { id: 'n3' } }]
          : [{ type: 'text' as const, text: 'Use the reset link [n3].' }]
      yield {
        type: 'message_end',
        stopReason: call === 1 ? 'tool_use' : 'end_turn',
        assistantMessage: { role: 'assistant', content },
      }
    },
  }
  const read: NonNullable<Agent['tools']>[number] = {
    name: 'read',
    description: 'Read a node',
    inputSchema: { type: 'object', properties: { id: { type: 'string' } } },
    parseInput: (raw) => raw,
    execute: async () => 'Passwords › Reset [n3]\nUse the reset link.',
  }
  const trail = ragtrailHook({ client })
  const agent = await createAgent({ provider, tools: [read], hooks: trail })
  await agent.run('How do I reset my password?')

  assert.match(seenByModel[0] ?? '', /start with read/)
  assert.deepEqual(calls.map((c) => c.name), ['recall'])
  await trail.accept()
  assert.deepEqual(calls[1]?.arguments.cited, ['n3'])
  assert.deepEqual(calls[1]?.arguments.steps, [{ tool: 'read', args: { id: 'n3' }, returned: ['n3'] }])
})
