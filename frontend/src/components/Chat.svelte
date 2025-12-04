<script lang="ts">
  import { chat, playTTS } from '../lib/api';

  interface Message {
    role: 'user' | 'assistant';
    content: string;
  }

  let messages: Message[] = [];
  let input = '';
  let loading = false;

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    input = '';

    messages = [...messages, { role: 'user', content: userMessage }];
    loading = true;

    try {
      const response = await chat(userMessage);
      messages = [...messages, { role: 'assistant', content: response.response }];
    } catch (e) {
      messages = [...messages, {
        role: 'assistant',
        content: '❌ Failed to get response. Is LM Studio running?'
      }];
    } finally {
      loading = false;
    }
  }

  function speak(text: string) {
    // Extract Swedish part (before any parentheses with English translation)
    const swedishPart = text.split('(')[0].trim();
    playTTS(swedishPart).catch(console.error);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="flex flex-col h-full">
  <!-- Header -->
  <div class="p-4 border-b border-slate-700">
    <h2 class="text-xl font-bold text-white">AI Swedish Tutor</h2>
    <p class="text-sm text-slate-400">Practice conversing in Swedish</p>
  </div>

  <!-- Messages -->
  <div class="flex-1 overflow-auto p-4 space-y-4">
    {#if messages.length === 0}
      <div class="h-full flex flex-col items-center justify-center text-slate-500">
        <div class="text-4xl mb-4">💬</div>
        <p class="mb-2">Start a conversation in Swedish!</p>
        <p class="text-sm">Try: "Hej! Hur mår du?"</p>
      </div>
    {:else}
      {#each messages as message}
        <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
          <div class="max-w-[80%] {message.role === 'user'
            ? 'bg-primary-600 text-white'
            : 'bg-slate-800 text-slate-200 border border-slate-700'} rounded-xl p-4">
            <div class="whitespace-pre-wrap">{message.content}</div>
            {#if message.role === 'assistant'}
              <button
                class="mt-2 text-slate-400 hover:text-white text-sm flex items-center gap-1"
                on:click={() => speak(message.content)}
              >
                🔊 Listen
              </button>
            {/if}
          </div>
        </div>
      {/each}

      {#if loading}
        <div class="flex justify-start">
          <div class="bg-slate-800 border border-slate-700 rounded-xl p-4 text-slate-400">
            <span class="animate-pulse">Thinking...</span>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Input -->
  <div class="p-4 border-t border-slate-700">
    <div class="flex gap-3">
      <input
        type="text"
        placeholder="Write in Swedish or English..."
        bind:value={input}
        on:keydown={handleKeydown}
        disabled={loading}
        class="flex-1 px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500 disabled:opacity-50"
      />
      <button
        class="px-6 py-3 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-medium"
        on:click={sendMessage}
        disabled={loading || !input.trim()}
      >
        Send
      </button>
    </div>
    <div class="mt-2 text-xs text-slate-500">
      Press Enter to send • Shift+Enter for new line
    </div>
  </div>
</div>
