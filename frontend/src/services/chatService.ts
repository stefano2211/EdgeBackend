import api from './api'

export const chatService = {
    // Non-streaming fallback
    async sendMessage(query: string, threadId?: string, knowledgeBaseId?: string) {
        const response = await api.post('/api/v1/chat/chat', {
            query,
            thread_id: threadId,
            knowledge_base_id: knowledgeBaseId
        }, { timeout: 540000 })
        return response.data
    },

    // Streaming via SSE
    async sendMessageStream(
        query: string,
        threadId: string | undefined,
        knowledgeBaseId: string | undefined,
        mcpSourceId: string | undefined,
        modelId: string | undefined,
        params: Record<string, any> | undefined,
        onToken: (token: string) => void,
        onMeta: (meta: { thread_id: string }) => void,
        onDone: (fullContent: string) => void,
        onError: (error: string) => void,
        onSubagent: (subagent: { status: string, name: string, input?: any }) => void = () => {},
        onScreenshot: (screenshot: { b64: string, step: number, has_omniparser: boolean, action?: string, click?: { x: number, y: number, type: string } | null }) => void = () => {},
        useGeneralist: boolean = false,
        onReasoning: (reasoning: string) => void = () => {},
        onTakeover: (takeover: { message: string, thread_id: string, action_type: string }) => void = () => {},
        onThought: (thought: string) => void = () => {},
    ): Promise<void> {
        const token = localStorage.getItem('token')
        const baseURL = import.meta.env.PROD ? (import.meta.env.VITE_API_URL || '') : ''

        const response = await fetch(`${baseURL}/api/v1/chat/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
                query,
                thread_id: threadId ? String(threadId) : undefined,
                knowledge_base_id: knowledgeBaseId ? String(knowledgeBaseId) : undefined,
                mcp_source_id: mcpSourceId ? String(mcpSourceId) : undefined,
                model_id: modelId ? String(modelId) : undefined,
                params: params || undefined,
                use_generalist: useGeneralist,
            }),
        })

        if (!response.ok) {
            onError(`HTTP ${response.status}`)
            return
        }

        const reader = response.body?.getReader()
        if (!reader) {
            onError('No readable stream')
            return
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6))
                        if (data.type === 'token') {
                            onToken(data.content)
                        } else if (data.type === 'reasoning') {
                            onReasoning(data.content)
                        } else if (data.type === 'meta') {
                            onMeta(data)
                        } else if (data.type === 'subagent') {
                            onSubagent(data)
                        } else if (data.type === 'screenshot') {
                            onScreenshot(data.data)
                        } else if (data.type === 'done') {
                            onDone(data.full_content)
                        } else if (data.type === 'error') {
                            onError(data.detail)
                        } else if (data.type === 'takeover') {
                            onTakeover(data)
                        } else if (data.type === 'thought') {
                            onThought(data.content)
                        } else if (data.thought) {
                            // Fallback para formato legacy directo
                            onThought(data.thought)
                        }
                    } catch (e) {
                        // Skip malformed JSON lines
                    }
                }
            }
        }
    },

    // Resume a paused thread after human-in-the-loop input
    async resumeThread(threadId: string, userResponse: string) {
        const response = await api.post('/api/v1/chat/chat/resume', {
            thread_id: threadId,
            user_response: userResponse,
        })
        return response.data
    }
}
