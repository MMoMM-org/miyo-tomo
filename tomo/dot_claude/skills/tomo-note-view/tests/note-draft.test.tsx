// version: 0.1.2
// Tests for the tomo-note-view mod under `claude plugin test`: the draft
// pane opens at an AskUserQuestion call while tomo-tmp/note/view.md exists,
// not without it, only for the approval dialog (an option labelled deliver,
// or a preview holding the note's title, in any language),
// /note-draft opens it, and the pane draws the file's text.
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
  tool: 'AskUserQuestion' as const,
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
}

// Any other dialog: the process destination question of step 9.
const OTHER_QUESTION = {
  tool: 'AskUserQuestion' as const,
  questions: [
    {
      question: 't_meeting: where do the notes go?',
      header: 'Destination',
      multiSelect: false,
      options: [
        { label: '1 Default', description: 'The atomic-note folder' },
        { label: '2 Another folder', description: 'Name a folder' },
      ],
    },
  ],
}

const numbered = (label: string) => ({
  ...QUESTION,
  questions: QUESTION.questions.map(q => ({
    ...q,
    options: q.options.map((o, i) => ({ ...o, label: i === 0 ? label : o.label })),
  })),
})

async function drawn($: any, surface: 'terminal' | 'desktop' = 'terminal') {
  const ui = await $.ui.mount({ ...PANE, surface })
  const markdown = await ui.find({ type: 'Markdown' })
  await ui.unmount()
  return markdown?.text
}

// The kit's command.run takes the full input; the engine fills origin and
// presentation for a typed command, which a test does not model.
const NOTE_DRAFT = { command: 'note-draft' } as any

type Engine = { files: Record<string, string>; opened: string[]; closed: string[]; commands: string[] }

// The engine hands fs ops the path resolved against the working directory.
const fileOf = (files: Record<string, string>, path: string) =>
  Object.keys(files).find(rel => path === rel || path.endsWith('/' + rel))

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
  on('fs.exists', (_: unknown, e: { path: string }) => ({ value: fileOf(seen.files, e.path) !== undefined }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    const rel = fileOf(seen.files, e.path)
    if (rel === undefined) throw new Error('ENOENT')
    return { value: seen.files[rel] }
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
  const ran = await $.command.run(NOTE_DRAFT)
  expect(seen.opened).toContain('note-draft')
  expect(ran.text).not.toBe('engine')
})

test('/note-draft without a staged draft says so and opens nothing', async ($, on) => {
  const seen = engine(on, {})
  await start($)
  const ran = await $.command.run(NOTE_DRAFT)
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

test('a dialog without a Deliver option opens no pane, even with view.md', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(OTHER_QUESTION)
  expect(seen.opened).not.toContain('note-draft')
})

test('a numbered "1 Deliver" option opens the pane', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(numbered('1 Deliver'))
  expect(seen.opened).toContain('note-draft')
})

test('control characters other than tab and newline are not drawn', async ($, on) => {
  engine(on, { [VIEW]: 'Template: t\u001b[31m red\u0000x\tok\n' })
  await start($)
  await $.tool.call(QUESTION)
  expect(await drawn($)).toBe('Template: t[31m redx\tok\n')
})

test('a Bash call while the pane is open shows the changed view.md', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(QUESTION)
  seen.files[VIEW] = 'Template: t_meeting · Final name: Atlas/Meetings/Renamed.md\n'
  await $.tool.call({ tool: 'Bash', command: 'python3 scripts/note-instructions.py stage --stem x' })
  expect(await drawn($)).toBe('Template: t_meeting · Final name: Atlas/Meetings/Renamed.md\n')
  expect(seen.closed).not.toContain('note-draft')
})

test('any dialog closes a stale pane once view.md is gone', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(QUESTION)
  delete seen.files[VIEW]
  await $.tool.call(OTHER_QUESTION)
  expect(seen.closed).toContain('note-draft')
})

const NOTE = '---\ntitle: "Design review"\n---\n# Notizen\nAlles gut\n'
const TITLED = 'Template: t_meeting · Final name: Atlas/Meetings/Design review.md\n\n' +
  '````markdown\n' + NOTE + '````\n'
const HEADED_NOTE = '---\ndate: 2026-11-06\n---\n# Retro Q3\nfine\n'
const HEADED = 'Template: t_retro · Final name: Atlas/Retro Q3.md\n\n````markdown\n' + HEADED_NOTE + '````\n'

const german = (preview: string) => ({
  tool: 'AskUserQuestion' as const,
  questions: [
    {
      question: 'Notiz abliefern?',
      header: 'Freigabe',
      multiSelect: false,
      options: [
        { label: '1 Abliefern', description: 'Notiz liefern', preview },
        { label: '2 Etwas ändern', description: 'Ändern', preview },
        { label: '3 Abbrechen', description: 'Verwerfen', preview },
      ],
    },
  ],
})

test('German labels with the note in the preview open the pane (frontmatter title)', async ($, on) => {
  const seen = engine(on, { [VIEW]: TITLED })
  await start($)
  // Only the frontmatter part, so the heading cannot be what matched.
  await $.tool.call(german('Template: t_meeting\n\n---\ntitle: "Design review"\n---\n'))
  expect(seen.opened).toContain('note-draft')
})

test('the first heading is the title when the frontmatter has none', async ($, on) => {
  const seen = engine(on, { [VIEW]: HEADED })
  await start($)
  await $.tool.call(german(HEADED_NOTE))
  expect(seen.opened).toContain('note-draft')
})

test('an unrelated dialog whose preview lacks the title opens no pane', async ($, on) => {
  const seen = engine(on, { [VIEW]: TITLED })
  await start($)
  await $.tool.call(german('note_include: t_*\nmatched: 4'))
  expect(seen.opened).not.toContain('note-draft')
})

test('a lower-case deliver label opens the pane', async ($, on) => {
  const seen = engine(on, { [VIEW]: TEXT })
  await start($)
  await $.tool.call(numbered('deliver'))
  expect(seen.opened).toContain('note-draft')
})
