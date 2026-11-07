// version: 0.1.2
// tomo-note-view: draws the staged /note draft in a side pane so the user
// sees it whole at the approval question, whatever the model wrote.
// WHY: docs/tomo/dot_claude/skills/tomo-note-view.md
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { NoteDraftView } from '../types'

const PANE = 'note-draft'
const TITLE = 'Note draft'
const VIEW_PATH = 'tomo-tmp/note/view.md'
const NO_DRAFT = 'No staged /note draft.'
// The /note approval dialog (note-from-template step 6): an option labelled
// Deliver, or, in any language, a preview holding the note's title.
const APPROVAL_LABEL = /deliver/i
const MIN_TITLE = 3

type Option = { label?: string; preview?: string }
type Question = { options?: readonly Option[] }

// The note inside view.md's fence: the line after ````markdown up to the
// closing fence of the same length.
function fencedNote(view: string): string {
  const open = /^(`{4,})markdown$/m.exec(view)
  if (!open) return ''
  const body = view.slice(open.index + open[0].length + 1)
  const close = body.lastIndexOf('\n' + open[1])
  return close < 0 ? body : body.slice(0, close + 1)
}

// The frontmatter title (quotes removed), else the first "# " heading.
function noteTitle(view: string): string {
  const note = fencedNote(view)
  const front = /^---\n([\s\S]*?)\n---\n/.exec(note)
  const titled = front && /^title:[ \t]*(.+?)[ \t]*$/m.exec(front[1] ?? '')
  const title = titled?.[1]?.replace(/^(["'])(.*)\1$/, '$2').trim()
  if (title && title.length >= MIN_TITLE) return title
  const rest = front ? note.slice(front[0].length) : note
  const heading = /^# +(.+?)[ \t]*$/m.exec(rest)?.[1] ?? ''
  return heading.length >= MIN_TITLE ? heading : ''
}

function isApproval(questions: readonly Question[] | undefined, view: string): boolean {
  const title = noteTitle(view)
  return (questions ?? []).some(q =>
    (q.options ?? []).some(o =>
      APPROVAL_LABEL.test(o.label ?? '') || (title !== '' && (o.preview ?? '').includes(title))))
}

const view = atom({ plugin: 'tomo-note-view', key: 'view' } as const, { text: '' } as NoteDraftView, {
  shape: 'view-1',
})

// The Markdown element takes tab and newline as its only control characters.
const drawable = (text: string): string =>
  text.replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, '')

async function readView($: EngineInterface): Promise<string | undefined> {
  try {
    if (!(await $.fs.exists(VIEW_PATH))) return undefined
    const text = await $.fs.read(VIEW_PATH)
    return typeof text === 'string' ? drawable(text) : undefined
  } catch {
    return undefined
  }
}

async function isOpen($: EngineInterface): Promise<boolean> {
  const panes = await $.ui.panes()
  return panes.some(pane => pane.id === PANE)
}

async function openPane($: EngineInterface, text: string): Promise<void> {
  await update($, view, () => ({ text }))
  const opened = await $.ui.open({ id: PANE, title: TITLE })
  if (!opened.isPlaced) {
    $.ui.log(`tomo-note-view: the draft pane waits (${opened.reason}); run /note-draft to show it.`)
  }
}

async function closePane($: EngineInterface): Promise<void> {
  if (await isOpen($)) await $.ui.close({ id: PANE })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'note-draft',
      description: 'Show the staged /note draft in a side pane',
    })
    return next(e)
  })

  on('command.run', { command: 'note-draft' }, async $ => {
    const text = await readView($)
    if (text === undefined) return { text: NO_DRAFT }
    await openPane($, text)
    return { text: 'Note draft pane opened.' }
  })

  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    const text = await readView($)
    if (text === undefined) await closePane($)
    else if (isApproval(e.questions, text)) await openPane($, text)
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    if (await isOpen($)) {
      const text = await readView($)
      if (text === undefined) await closePane($)
      else await update($, view, () => ({ text }))
    }
    return ran
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Markdown, Text } = $.ui.resolve(e)
    const { text } = await read($, view)
    if (!text) return <Text dimColor>{NO_DRAFT}</Text>
    return <Markdown text={text} />
  })
}
