<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{
  content: string
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

const parsedContent = computed(() => {
  if (!props.content) return []
  
  const result = []
  const text = props.content
  
  // Expresión regular para extraer <think>...</think> o <think>... al final (streaming)
  const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g
  
  let lastIndex = 0
  let match
  
  while ((match = thinkRegex.exec(text)) !== null) {
    // Si hay texto normal antes del bloque de pensamiento
    if (match.index > lastIndex) {
      result.push({
        type: 'text',
        content: md.render(text.substring(lastIndex, match.index))
      })
    }
    
    // Determinar si está en streaming (falta la etiqueta de cierre desde match hasta el final)
    const isStreaming = !text.substring(match.index).includes('</think>')
    
    result.push({
      type: 'think',
      content: md.render(match[1]),
      isStreaming
    })
    
    lastIndex = match.index + match[0].length
  }
  
  // Agregar cualquier texto que quede después del último bloque
  if (lastIndex < text.length) {
    result.push({
      type: 'text',
      content: md.render(text.substring(lastIndex))
    })
  }
  
  return result
})
</script>

<template>
  <div class="markdown-container">
    <template v-for="(block, index) in parsedContent" :key="index">
      
      <!-- Bloque de Pensamiento -->
      <div v-if="block.type === 'think'" class="think-block my-4">
        <details class="think-details group" :open="block.isStreaming || true">
          <summary class="think-summary animate-in fade-in duration-300">
            <svg class="think-caret transform transition-transform duration-200" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
            <div class="flex items-center gap-2">
              <svg v-if="block.isStreaming" class="w-3.5 h-3.5 animate-spin text-[#8b5cf6]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              <span>{{ block.isStreaming ? 'Procesando razonamiento...' : 'Proceso de Razonamiento' }}</span>
            </div>
          </summary>
          <div class="think-content markdown-body animate-in slide-in-from-top-2 duration-300" v-html="block.content"></div>
        </details>
      </div>

      <!-- Texto Normal -->
      <div v-else class="markdown-body" v-html="block.content"></div>
      
    </template>
  </div>
</template>

<style scoped>
/* ── Estilos para el Bloque de Pensamiento (<think>) ── */
.think-block {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background-color: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.think-summary {
  padding: 0.75rem 1rem;
  cursor: pointer;
  font-size: 0.65rem;
  font-weight: 800;
  color: #737373;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  background-color: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  gap: 0.6rem;
  user-select: none;
}

.think-summary:hover {
  color: #9ca3af;
  background-color: rgba(0, 0, 0, 0.4);
}

.think-summary::marker,
.think-summary::-webkit-details-marker {
  display: none;
}

.think-details[open] .think-caret {
  transform: rotate(90deg);
}

.think-details[open] .think-summary {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.think-content {
  padding: 1rem 1.2rem;
  font-size: 0.85em;
  color: #9ca3af;
  background-color: rgba(0, 0, 0, 0.1);
  font-style: italic;
}

/* Modificamos los estilos de markdown internos para que se atenúen */
.think-content :deep(*) {
  color: #9ca3af !important;
}
.think-content :deep(pre) {
  background-color: rgba(0, 0, 0, 0.3) !important;
  border-color: rgba(255, 255, 255, 0.02) !important;
}

/* ── Estilos de Markdown Estándar ── */
.markdown-body {
  word-break: break-word;
  color: #ececec;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  color: #ffffff;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  line-height: 1.3;
}

.markdown-body :deep(h1) { font-size: 1.5rem; }
.markdown-body :deep(h2) { font-size: 1.35rem; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 0.4rem; }
.markdown-body :deep(h3) { font-size: 1.2rem; }
.markdown-body :deep(h4) { font-size: 1.1rem; }

.markdown-body :deep(p) {
  margin-bottom: 1rem;
  line-height: 1.7;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.markdown-body :deep(ul) { list-style-type: disc; }
.markdown-body :deep(ol) { list-style-type: decimal; }
.markdown-body :deep(li) { margin-bottom: 0.5rem; }
.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) { margin-top: 0.5rem; margin-bottom: 0.5rem; }

.markdown-body :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-size: 0.9em;
  color: #f8f8f2;
}

.markdown-body :deep(pre) {
  background-color: #1e1e1e;
  padding: 1rem;
  border-radius: 12px;
  overflow-x: auto;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.markdown-body :deep(pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.85rem;
  display: block;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid rgba(255, 255, 255, 0.2);
  padding-left: 1rem;
  margin-left: 0;
  margin-bottom: 1rem;
  color: #b4b4b4;
  font-style: italic;
}

.markdown-body :deep(hr) {
  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 2rem 0;
}

.markdown-body :deep(strong) {
  color: #ffffff;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #8b5cf6;
  text-decoration: none;
}

.markdown-body :deep(a:hover) { text-decoration: underline; }

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.75rem;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: rgba(255, 255, 255, 0.05);
  font-weight: 600;
}
</style>
