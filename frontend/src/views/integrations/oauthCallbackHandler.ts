/**
 * OAuth callback handler — listens for postMessage from the OAuth popup.
 *
 * Usage:
 *   import { useOAuthCallback } from './oauthCallbackHandler'
 *   useOAuthCallback((payload) => { ... })
 *
 * The listener is automatically cleaned up after the first message.
 */

export interface OAuthPayload {
  type: 'oauth-success' | 'oauth-error'
  provider: string
  instance_id?: number
  error?: string
  error_description?: string
  detail?: string
}

let activeHandler: ((payload: OAuthPayload) => void) | null = null
let listenerAttached = false

function onMessage(event: MessageEvent) {
  // Accept messages from any origin (the popup loads from our backend)
  const data = event.data as OAuthPayload
  if (!data || typeof data !== 'object') return
  if (data.type !== 'oauth-success' && data.type !== 'oauth-error') return

  if (activeHandler) {
    activeHandler(data)
    activeHandler = null
  }
}

export function useOAuthCallback(handler: (payload: OAuthPayload) => void) {
  activeHandler = handler

  if (!listenerAttached) {
    window.addEventListener('message', onMessage)
    listenerAttached = true
  }

  // Safety cleanup after 15 minutes in case popup is abandoned
  setTimeout(() => {
    activeHandler = null
  }, 15 * 60 * 1000)
}

export function cleanupOAuthCallback() {
  if (listenerAttached) {
    window.removeEventListener('message', onMessage)
    listenerAttached = false
  }
  activeHandler = null
}
