// version: 0.1.0
// Tests for the tomo-note-view mod under `claude plugin test`: the draft
// pane opens at an AskUserQuestion call while tomo-tmp/note/view.md exists,
// not without it, /note-draft opens it, and the pane draws the file's text.
import { expect, test } from 'claude-code/testing'

const VIEW = 'tomo-tmp/note/view.md'
const TEXT =
  'Template: t_meeting · Final name: Atlas/Meetings/Design review.md\n\n' +
  '````markdown\n# Notes\nAll fine\n````\n'

const PANE = {
  plugin: 'tomo-note-view',
  component: 'Pane',
  requestId: 'note-draft',
  props: {
    title: 'Note draft',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const QUESTION = {
  tool: 'AskUserQuestion',
  questions: [
    {
      question: 'Design review: deliver?',
      header: 'Approval',
      multiSelect: false,
      options: [
        { label: 'Deliver', description: 'Deliver the note' },
        { label: 'Abort', description: 'Discard the draft' },
      ],
    },
  ],
} as const

type Engine = { files: Record<string, string>; opened: string[]; closed: string[]; commands: string[] }

// Nothing sits beneath the plugin: these hooks stand for the engine.
function engine(on: any, files: Record<string, string>): Engine {
  const seen: Engine = { files, opened: [], closed: [], commands: [] }
  on('command.register', (_: unknown, e: { name: string }) => {
    seen.commands.push(e.name)
    return { value: { command: e.name } }
  })
  on('ui.open', (_: unknown, e: { id: string }) => {
    seen.opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.close', (_: unknown, e: { id: string }) => {
    seen.closed.push(e.id)
    return { value: undefined }
  })
  on('ui.panes', () => ({
    value: seen.opened
      .filter(id => !seen.closed.includes(id))
      .map(id => ({ id, title: 'Note draft', isShown: true, isFocused: false, isPlaced: true })),
  }))
  on('fs.exists', (_: unknown, e: { path: string }) => ({ value: e.path in seen.files }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    const text = seen.files[e.path]
    if (text === undefined) throw new Error('ENOENT')
    return { value: text }
  })
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  on('command.run', () => ({ text: 'engine' }))
  return seen
}

async function start($: any) {
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
}

test('the pane opens at the approval dialog while view.md exists', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(QUESTION)
  expect(seen.opened).toContain('note-draft')
})

test('no pane opens at a dialog without view.md', async ($, on) => {
  const seen = engine(on, {})
  await start($)
  await $.tool.call(QUESTION)
  expect(seen.opened).not.toContain('note-draft')
})

test('/note-draft is registered and opens the pane', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  expect(seen.commands).toContain('note-draft')
  const ran = await $.command.run({ command: 'note-draft' })
  expect(seen.opened).toContain('note-draft')
  expect(ran.text).not.toBe('engine')
})

test('/note-draft without a staged draft says so and opens nothing', async ($, on) => {
  const seen = engine(on, {})
  await start($)
  const ran = await $.command.run({ command: 'note-draft' })
  expect(ran.text).toBe('No staged /note draft.')
  expect(seen.opened).not.toContain('note-draft')
})

test('the pane draws the text of view.md, on every surface', async ($, on) => {
  engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(QUESTION)
  for (const surface of ['terminal', 'desktop', 'vscode', 'mobile'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    const drawn = await ui.find({ type: 'Markdown' })
    expect(drawn?.text).toBe(TEXT)
    await ui.unmount()
  }
})

test('a Bash call after the draft is gone closes the pane', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(QUESTION)
  delete seen.files[VIEW]
  await $.tool.call({ tool: 'Bash', command: 'python3 scripts/note-instructions.py drop --stem x' })
  expect(seen.closed).toContain('note-draft')
})
