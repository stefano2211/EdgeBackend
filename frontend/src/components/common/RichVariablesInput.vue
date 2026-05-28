<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
  (e: 'cursor-update', pos: number): void
  (e: 'enter', event: KeyboardEvent): void
}>()

const editor = ref<HTMLElement | null>(null)

// Initial render
onMounted(() => {
  if (editor.value && props.modelValue) {
    editor.value.innerHTML = renderToHtml(props.modelValue)
  }
})

// Watch external changes (like variable insertions from the autocompleter)
watch(() => props.modelValue, (newVal) => {
  if (!editor.value) return
  
  const currentRaw = parseToRaw(editor.value)
  if (newVal === currentRaw) return // Unchanged, ignore

  editor.value.innerHTML = renderToHtml(newVal)
})

function onInput() {
  if (!editor.value) return
  const raw = parseToRaw(editor.value)
  emit('update:modelValue', raw)
  updateCursorPosition()
}

function updateCursorPosition() {
  if (!editor.value) return
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return
  
  const pos = getCaretCharacterOffsetWithin(editor.value)
  emit('cursor-update', pos)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    emit('enter', e)
  }
}

// Focus and move cursor to a specific raw position
function focusAndSetCursor(rawPos: number) {
  if (!editor.value) return
  editor.value.focus()
  setCursorToRawPosition(editor.value, rawPos)
}

defineExpose({
  focusAndSetCursor
})

// ---- Parsing & Rendering Logic ----

function renderToHtml(raw: string) {
  if (!raw) return ''
  
  // Replace anything in {{...}} with a "chip" element
  const htmlSafe = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  
  return htmlSafe.replace(/\{\{([^}]+)\}\}/g, (match, content) => {
    // E.g., match = {{Maquinas.get.key_figures.Temperatura}}
    // content = Maquinas.get.key_figures.Temperatura
    const rawMatch = match.replace(/&amp;/g, '&'); // Restore just in case
    
    const parts = content.split('.')
    let label = content
    let sublabel = ''
    
    if (parts.length >= 4) {
      if (['key_figures', 'key_values', 'params'].includes(parts[2])) {
         label = parts.slice(3).join('.')
      } else {
         label = parts[parts.length - 1]
      }
    } else {
      label = parts[parts.length - 1]
    }
    
    // Very minimal, compact black box with slightly lighter black, no underline
    return `<span class="inline-block align-baseline shrink-0 px-2 py-[2px] mx-[2px] bg-[#222222] border border-[#383838] text-[#ececec] rounded-md text-[14px] font-medium leading-normal cursor-default select-none shadow-sm transition-all hover:bg-[#111111]" contenteditable="false" data-raw="${rawMatch}">${label}</span>\u200B` // Zero-width space helps cursor targeting
  }).replace(/\n/g, '<br>')
}

function parseToRaw(htmlElement: DocumentFragment | HTMLElement): string {
  let rawText = '';
  for (const node of htmlElement.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      // Replace non-breaking spaces
      rawText += (node.textContent || '').replace(/\u00A0/g, ' ').replace(/\u200B/g, '');
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      if (el.tagName === 'BR') {
         rawText += '\n';
      } else if (el.dataset.raw) {
         rawText += el.dataset.raw;
      } else {
         rawText += parseToRaw(el);
      }
    }
  }
  return rawText;
}

function getCaretCharacterOffsetWithin(element: HTMLElement) {
    let caretOffset = 0;
    const doc = element.ownerDocument || element.document;
    const win = doc.defaultView || doc.parentWindow;
    let sel;
    if (typeof win.getSelection !== "undefined") {
        sel = win.getSelection();
        if (sel && sel.rangeCount > 0) {
            const range = sel.getRangeAt(0);
            const preCaretRange = range.cloneRange();
            preCaretRange.selectNodeContents(element);
            preCaretRange.setEnd(range.endContainer, range.endOffset);
            
            const fragment = preCaretRange.cloneContents();
            caretOffset = parseToRaw(fragment).length;
        }
    }
    return caretOffset;
}

function setCursorToRawPosition(element: HTMLElement, targetPos: number) {
  let currentPos = 0;
  let found = false;
  let targetNode: Node | null = null;
  let targetOffset = 0;

  function traverse(node: Node) {
    if (found) return;
    
    if (node.nodeType === Node.TEXT_NODE) {
      const text = (node.textContent || '').replace(/\u200B/g, '');
      const textLen = text.length;
      
      if (currentPos + textLen >= targetPos) {
        found = true;
        targetNode = node;
        // Adjust for zero-width spaces in the offset
        const rawOffset = targetPos - currentPos;
        // Count actual string length in the DOM text node to reach rawOffset characters
        let domOffset = 0;
        let c = 0;
        while (c < rawOffset && domOffset < (node.textContent || '').length) {
          if ((node.textContent || '')[domOffset] !== '\u200B') {
            c++;
          }
          domOffset++;
        }
        targetOffset = domOffset;
      } else {
        currentPos += textLen;
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      if (el.tagName === 'BR') {
        if (currentPos + 1 >= targetPos) {
          found = true;
          targetNode = el.parentNode;
          targetOffset = Array.from(el.parentNode!.childNodes).indexOf(el) + 1;
        } else {
          currentPos += 1;
        }
      } else if (el.dataset.raw) {
        const rawLen = el.dataset.raw.length;
        if (currentPos + rawLen >= targetPos) {
          found = true;
          targetNode = el.parentNode;
          targetOffset = Array.from(el.parentNode!.childNodes).indexOf(el) + 1;
        } else {
          currentPos += rawLen;
        }
      } else {
        for (const child of node.childNodes) {
          traverse(child);
        }
      }
    }
  }

  traverse(element);

  if (targetNode) {
    try {
      const range = document.createRange();
      const sel = window.getSelection();
      range.setStart(targetNode, targetOffset);
      range.collapse(true);
      sel?.removeAllRanges();
      sel?.addRange(range);
    } catch(e) {}
  } else {
    // default to end if out of bounds
    const range = document.createRange();
    const sel = window.getSelection();
    range.selectNodeContents(element);
    range.collapse(false);
    sel?.removeAllRanges();
    sel?.addRange(range);
  }
}
</script>

<template>
  <div 
    ref="editor"
    contenteditable="true"
    spellcheck="false"
    :placeholder="placeholder"
    class="w-full bg-transparent outline-none px-4 py-2.5 max-h-[200px] overflow-y-auto text-[15px] text-[#ececec] placeholder-[#7a7a7a] empty:before:content-[attr(placeholder)] empty:before:text-[#7a7a7a] break-words whitespace-pre-wrap"
    @input="onInput"
    @keydown="onKeydown"
    @click="updateCursorPosition"
    @keyup="updateCursorPosition"
  ></div>
</template>

<style scoped>
div[contenteditable]:empty:before {
    content: attr(placeholder);
    pointer-events: none;
    display: block; /* For Firefox */
}
/* Basic scrollbar styling for the editor */
div[contenteditable]::-webkit-scrollbar {
    width: 6px;
}
div[contenteditable]::-webkit-scrollbar-track {
    background: transparent;
}
div[contenteditable]::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
}
</style>
