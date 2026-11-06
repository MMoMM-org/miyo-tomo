// version: 0.1.0
// State contract of the tomo-note-view mod: the text of the staged draft view.
export type NoteDraftView = { text: string }

declare module 'claude-code' {
  interface PluginState {
    'tomo-note-view': { view: Shaped<NoteDraftView> }
  }
}
