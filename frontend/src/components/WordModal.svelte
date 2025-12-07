<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { wordModal, stats } from '../lib/stores';
  import { getWord, updateWordStatus, playTTS, getStats } from '../lib/api';
  import type { Word } from '../lib/api';

  let word: Word | null = null;
  let loading = false;
  let contexts: string[] = [];

  // Load full word data when modal opens
  $: if ($wordModal) {
    loadWord($wordModal);
  } else {
    word = null;
    contexts = [];
  }

  async function loadWord(w: Word) {
    loading = true;
    try {
      const freshWord = await getWord(w.word);
      word = freshWord;
      contexts = freshWord.contexts || [];
    } catch (e) {
      console.error('Failed to load word:', e);
      word = w;
    } finally {
      loading = false;
    }
  }

  function close() {
    wordModal.set(null);
  }

  async function markStatus(status: 'undiscovered' | 'learning' | 'known') {
    if (!word) return;
    try {
      await updateWordStatus(word.word, status);
      word = { ...word, status };
      // Refresh global stats
      const statsData = await getStats();
      stats.set(statsData);
    } catch (e) {
      console.error('Failed to update status:', e);
    }
  }

  // Parse explanation JSON
  interface Explanation {
    translation?: string;
    type?: string;
    usagePatterns?: { pattern: string; meaning: string }[];
    relatedWords?: { word: string; relation: string; translation: string }[];
    tip?: string;
  }

  function parseExplanation(w: Word): Explanation | null {
    if (!w.explanation_json) return null;
    try {
      return JSON.parse(w.explanation_json);
    } catch {
      return null;
    }
  }

  // Keyboard handler
  function handleKeydown(e: KeyboardEvent) {
    if (!$wordModal) return;
    if (e.key === 'Escape') {
      close();
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

{#if $wordModal}
  <!-- Backdrop with frosted glass effect -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="dialog"
    aria-modal="true"
  >
    <!-- Frosted glass backdrop -->
    <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-md"></div>

    <!-- Modal content -->
    <div
      class="relative w-full max-w-2xl max-h-[85vh] overflow-auto bg-slate-800/90 backdrop-blur-xl rounded-2xl border border-slate-600/50 shadow-2xl"
      on:click|stopPropagation
      on:keydown|stopPropagation
    >
      {#if loading}
        <div class="p-12 text-center text-slate-400">Loading...</div>
      {:else if word}
        {@const explanation = parseExplanation(word)}

        <!-- Header -->
        <div class="sticky top-0 bg-slate-800/95 backdrop-blur-sm border-b border-slate-700/50 p-6">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-4">
                <h1 class="text-4xl font-bold text-white">{word.word}</h1>
                <button
                  on:click={() => playTTS(word.word)}
                  class="w-12 h-12 rounded-full bg-primary-600/80 hover:bg-primary-500 flex items-center justify-center text-white text-xl transition-colors"
                >
                  🔊
                </button>
              </div>
              <div class="flex items-center gap-3 mt-2">
                <span class="text-slate-400">Seen {word.frequency} times</span>
                <span class="text-xs px-2 py-1 rounded-full {word.status === 'known' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : word.status === 'learning' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : 'bg-slate-600/50 text-slate-400 border border-slate-500/30'}">
                  {word.status}
                </span>
              </div>
            </div>
            <button
              on:click={close}
              class="p-2 hover:bg-slate-700/50 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="p-6 space-y-6">
          {#if explanation}
            <!-- Translation -->
            {#if explanation.translation}
              <div>
                <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Translation</h2>
                <div class="flex items-center gap-3">
                  <p class="text-white text-2xl">{explanation.translation}</p>
                  {#if explanation.type}
                    <span class="text-xs px-2 py-1 bg-slate-700/50 text-slate-400 rounded">{explanation.type}</span>
                  {/if}
                </div>
              </div>
            {/if}

            <!-- Usage Patterns -->
            {#if explanation.usagePatterns?.length}
              <div>
                <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Usage Patterns</h2>
                <div class="space-y-2">
                  {#each explanation.usagePatterns as pattern}
                    <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-700/50">
                      <span class="text-white font-medium">{pattern.pattern}</span>
                      <span class="text-slate-400"> → {pattern.meaning}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Related Words -->
            {#if explanation.relatedWords?.length}
              <div>
                <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Related Words</h2>
                <div class="flex flex-wrap gap-2">
                  {#each explanation.relatedWords as related}
                    <button
                      class="px-3 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 rounded-lg text-sm transition-colors"
                      on:click={() => wordModal.set({ word: related.word } as Word)}
                    >
                      <span class="text-white">{related.word}</span>
                      <span class="text-slate-400"> - {related.translation}</span>
                    </button>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Tip -->
            {#if explanation.tip}
              <div class="p-4 bg-yellow-900/20 border border-yellow-700/30 rounded-lg">
                <p class="text-yellow-200/90">💡 {explanation.tip}</p>
              </div>
            {/if}
          {:else}
            <div class="text-center py-6 text-slate-400">
              No explanation available yet.
            </div>
          {/if}

          <!-- Contexts from recordings -->
          {#if contexts.length > 0}
            <div>
              <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">From Your Recordings</h2>
              <div class="space-y-2">
                {#each contexts.slice(0, 5) as context}
                  <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-700/50 flex items-start gap-3">
                    <button
                      on:click={() => playTTS(context)}
                      class="p-2 bg-slate-700/50 hover:bg-slate-600/50 rounded-full text-white shrink-0 transition-colors"
                    >
                      🔊
                    </button>
                    <p class="text-slate-300 italic">"{context}"</p>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <!-- Actions footer -->
        <div class="sticky bottom-0 bg-slate-800/95 backdrop-blur-sm border-t border-slate-700/50 p-4">
          <div class="flex gap-3">
            <button
              on:click={() => markStatus('learning')}
              class="flex-1 py-3 rounded-xl font-medium transition-all {word.status === 'learning' ? 'bg-yellow-500 text-black ring-2 ring-yellow-300' : 'bg-yellow-600/80 hover:bg-yellow-500 text-white'}"
            >
              {word.status === 'learning' ? '📖 Learning' : '📖 Learn'}
            </button>
            <button
              on:click={() => markStatus('known')}
              class="flex-1 py-3 rounded-xl font-medium transition-all {word.status === 'known' ? 'bg-green-500 text-black ring-2 ring-green-300' : 'bg-green-600/80 hover:bg-green-500 text-white'}"
            >
              {word.status === 'known' ? '✓ Known' : '✓ Know'}
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
