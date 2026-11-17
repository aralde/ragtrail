import assert from 'node:assert/strict'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import type { SessionHooks } from 'astorlm'
import { RagtrailClient, ragtrailHook, type HookMessage } from '../src/index.ts'

const command = process.env.RAGTRAIL_COMMAND

test('the hook is an astorlm SessionHooks object', () => {
  const hooks: SessionHooks = ragtrailHook({ scope: 'docs' })
  assert.equal(typeof hooks.beforeTurn, 'function')
})

test('a trail recorded through the hook is recalled by the next question', { skip: !command }, async () => {
  const db = join(mkdtempSync(join(tmpdir(), 'ragtrail-ts-')), 'trails.db')
  const hook = ragtrailHook({ scope: 'docs', db, command })
  const ask = async (question: string, answer: string) => {
    const user: HookMessage = { role: 'user', content: [{ type: 'text', text: question }] }
    await hook.beforeTurn({ turn: 1, messages: [user] })
    await hook.afterToolExecution({ toolName: 'docs__read', input: { id: 'n3' }, output: 'Reset [n3]', isError: false })
    await hook.afterTurn({ turn: 2, lastMessage: { role: 'assistant', content: [{ type: 'text', text: answer }] } })
    return user
  }
  try {
    await ask('How do I reset my password?', 'Use the reset link [n3].')
    assert.equal(hook.lastRecall?.mode, 'miss')
    const recorded = await hook.accept()
    assert.equal(recorded?.recorded, true)

    const user = await ask('how can I reset my password', 'Same link [n3].')
    assert.equal(hook.lastRecall?.mode, 'hint')
    assert.deepEqual(hook.lastRecall?.nodes, ['n3'])
    assert.match(user.content.at(-1)?.text ?? '', /n3/)

    assert.deepEqual((await hook.reject())?.rejected, [recorded?.trajectoryId])
  } finally {
    await hook.close()
  }

  const other = await RagtrailClient.spawn({ scope: 'other', db, command })
  try {
    assert.equal((await other.recall('How do I reset my password?')).mode, 'miss')
  } finally {
    await other.close()
  }
})
