import { RagtrailClient, type ToolCaller } from '../src/index.ts'

export interface Call {
  name: string
  arguments: Record<string, unknown>
}

export function fakeClient(
  respond: (call: Call) => { structuredContent?: Record<string, unknown>; isError?: boolean; text?: string },
): { client: RagtrailClient; calls: Call[] } {
  const calls: Call[] = []
  const caller: ToolCaller = {
    async callTool({ name, arguments: args }) {
      const call = { name, arguments: args ?? {} }
      calls.push(call)
      const r = respond(call)
      const text = r.text ?? String(r.structuredContent?.text ?? '')
      return { content: [{ type: 'text', text }], structuredContent: r.structuredContent, isError: r.isError }
    },
  }
  return { client: new RagtrailClient(caller), calls }
}
