import assert from 'node:assert/strict'
import { test } from 'node:test'
import { RagtrailError } from '../src/index.ts'
import { fakeClient } from './fake.ts'

test('recall maps the structured result', async () => {
  const { client, calls } = fakeClient(() => ({
    structuredContent: {
      text: 'ragtrail: similar question solved before',
      mode: 'hint',
      similarity: 0.82,
      trajectory_id: 't1',
      nodes: ['n33', 'n58'],
      stale: ['n35'],
      matched_by: 'lexical',
    },
  }))
  const result = await client.recall('How do tokens expire?', { budgetTokens: 400 })
  assert.deepEqual(calls, [{ name: 'recall', arguments: { query: 'How do tokens expire?', budget_tokens: 400 } }])
  assert.deepEqual(result, {
    mode: 'hint',
    similarity: 0.82,
    trajectoryId: 't1',
    nodes: ['n33', 'n58'],
    stale: ['n35'],
    matchedBy: 'lexical',
    text: 'ragtrail: similar question solved before',
  })
})

test('record sends steps in the server shape and defaults the outcome', async () => {
  const { client, calls } = fakeClient(() => ({
    structuredContent: { text: 'Recorded', recorded: true, trajectory_id: 't2', nodes: ['c7'] },
  }))
  const result = await client.record({ query: 'q', cited: ['c7'], steps: [{ tool: 'search', returned: ['c7'] }] })
  assert.deepEqual(calls[0]?.arguments, {
    query: 'q',
    cited: ['c7'],
    outcome: 'accepted',
    steps: [{ tool: 'search', args: {}, returned: ['c7'] }],
  })
  assert.deepEqual(result, { recorded: true, trajectoryId: 't2', nodes: ['c7'], text: 'Recorded' })
})

test('tool errors raise RagtrailError with the server text', async () => {
  const { client } = fakeClient(() => ({ isError: true, text: 'budget_tokens must be at least 1.' }))
  await assert.rejects(client.recall('q', { budgetTokens: 0 }), (err: unknown) => {
    assert.ok(err instanceof RagtrailError)
    assert.equal(err.message, 'budget_tokens must be at least 1.')
    return true
  })
})

test('reject returns the demoted trail ids', async () => {
  const { client } = fakeClient(() => ({ structuredContent: { text: 'Demoted 1 path(s)', rejected: ['t1'] } }))
  assert.deepEqual(await client.reject('q'), { rejected: ['t1'], text: 'Demoted 1 path(s)' })
})
