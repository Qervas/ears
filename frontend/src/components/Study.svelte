<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getVocabulary, getWord, updateWordStatus, playTTS, type Word } from '../lib/api';
  import { selectedStudyWord } from '../lib/stores';

  // View modes: queue (list of learning words) or detail (single word)
  type ViewMode = 'queue' | 'detail';
  let viewMode: ViewMode = 'queue';

  // Queue state (words marked as 'learning')
  let queueWords: Word[] = [];
  let queueTotal = 0;
  let loadingQueue = true;
  let currentQueueIndex = 0;

  // Detail state
  let selectedWord: Word | null = null;
  let wordContexts: string[] = [];
  let loadingWord = false;

  // For navigation through queue
  let totalLearningWords = 0;

  async function loadQueue() {
    loadingQueue = true;
    try {
      // Fetch words with 'learning' status
      const result = await getVocabulary(100, 0, 'learning', 'frequency');
      queueWords = result.words;
      queueTotal = result.total;
      totalLearningWords = result.total;
    } catch (e) {
      console.error('Failed to load study queue:', e);
    } finally {
      loadingQueue = false;
    }
  }

  async function openWordDetail(word: Word, index?: number) {
    selectedWord = word;
    viewMode = 'detail';
    loadingWord = true;
    if (index !== undefined) {
      currentQueueIndex = index;
    }

    try {
      const freshWord = await getWord(word.word);
      selectedWord = freshWord;
      wordContexts = freshWord.contexts || [];
    } catch (e) {
      console.error('Failed to load word details:', e);
    } finally {
      loadingWord = false;
    }
  }

  function backToQueue() {
    viewMode = 'queue';
    selectedWord = null;
    wordContexts = [];
    // Refresh queue in case status changed
    loadQueue();
  }

  async function markWord(status: 'known' | 'learning') {
    if (!selectedWord) return;
    try {
      await updateWordStatus(selectedWord.word, status);
      selectedWord = { ...selectedWord, status };
      // Update in queue list
      queueWords = queueWords.map(w => w.word === selectedWord!.word ? { ...w, status } : w);

      // If marked as known, it should be removed from queue
      if (status === 'known') {
        queueWords = queueWords.filter(w => w.word !== selectedWord!.word);
        queueTotal--;
        totalLearningWords--;
      }
    } catch (e) {
      console.error('Failed to update status:', e);
    }
  }

  interface UsagePattern {
    pattern: string;
    meaning: string;
    category?: string;
  }

  interface RelatedWord {
    word: string;
    relation: string;
    translation: string;
  }

  interface Explanation {
    translation?: string;
    type?: string;
    usagePatterns?: UsagePattern[];
    relatedWords?: RelatedWord[];
    tip?: string;
    note?: string;
  }

  function formatExplanation(word: Word): Explanation | null {
    if (!word.explanation_json) return null;
    try {
      return JSON.parse(word.explanation_json);
    } catch {
      return null;
    }
  }

  // Navigation in detail view
  async function goToPrevWord() {
    if (currentQueueIndex > 0) {
      await openWordDetail(queueWords[currentQueueIndex - 1], currentQueueIndex - 1);
    }
  }

  async function goToNextWord() {
    if (currentQueueIndex < queueWords.length - 1) {
      await openWordDetail(queueWords[currentQueueIndex + 1], currentQueueIndex + 1);
    }
  }

  async function goToRandomWord() {
    if (queueWords.length === 0) return;
    const randomIndex = Math.floor(Math.random() * queueWords.length);
    await openWordDetail(queueWords[randomIndex], randomIndex);
  }

  // Handle word passed from Vocabulary page via store
  onMount(() => {
    const unsubscribe = selectedStudyWord.subscribe(async word => {
      if (word) {
        await openWordDetail(word);
        selectedStudyWord.set(null);
      }
    });

    // Load queue if no word was passed
    if (!selectedWord) {
      loadQueue();
    }

    return () => unsubscribe();
  });

  // Keyboard navigation
  function handleKeydown(e: KeyboardEvent) {
    if (viewMode === 'detail') {
      if (e.key === 'Escape') {
        backToQueue();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goToPrevWord();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        goToNextWord();
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        goToRandomWord();
      }
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

<div class="h-full overflow-auto p-8 bg-slate-900">
  {#if viewMode === 'queue'}
    <!-- Study Queue View -->
    <div class="max-w-4xl mx-auto">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white">Study Queue</h1>
        <p class="text-slate-400 mt-1">Words you're currently learning</p>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-3 gap-4 mb-8">
        <div class="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <div class="text-slate-400 text-sm">In Queue</div>
          <div class="text-2xl font-bold text-blue-400">{queueTotal}</div>
        </div>
        <div class="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <div class="text-slate-400 text-sm">Study Progress</div>
          <div class="text-2xl font-bold text-primary-400">
            {queueWords.filter(w => w.status === 'known').length} / {queueTotal}
          </div>
        </div>
        <div class="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <div class="text-slate-400 text-sm">Quick Start</div>
          <button
            on:click={goToRandomWord}
            disabled={queueWords.length === 0}
            class="text-xl font-bold text-yellow-400 hover:text-yellow-300 disabled:text-slate-600"
          >
            Random Word
          </button>
        </div>
      </div>

      <!-- Queue List -->
      <div class="bg-slate-800 rounded-xl border border-slate-700">
        <div class="p-4 border-b border-slate-700">
          <h2 class="text-lg font-semibold text-white">
            Words to Study
            <span class="text-slate-400 font-normal">({queueTotal} words)</span>
          </h2>
        </div>

        {#if loadingQueue}
          <div class="p-8 text-center text-slate-400">Loading your study queue...</div>
        {:else if queueWords.length === 0}
          <div class="p-12 text-center">
            <div class="text-5xl mb-4">🎉</div>
            <h3 class="text-xl font-semibold text-white mb-2">Queue Empty!</h3>
            <p class="text-slate-400 mb-4">
              No words marked as "learning". Visit Vocabulary to add words to your study queue.
            </p>
          </div>
        {:else}
          <div class="divide-y divide-slate-700">
            {#each queueWords as word, index}
              <button
                class="w-full px-4 py-3 text-left hover:bg-slate-700/50 transition-colors flex items-center justify-between"
                on:click={() => openWordDetail(word, index)}
              >
                <div class="flex items-center gap-4">
                  <span class="text-slate-500 text-sm w-8">{index + 1}.</span>
                  <div>
                    <span class="text-white font-medium text-lg">{word.word}</span>
                    {#if formatExplanation(word)?.translation}
                      <span class="text-slate-500 ml-2">- {formatExplanation(word)?.translation}</span>
                    {/if}
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <span class="text-slate-500 text-sm">{word.frequency}x</span>
                  <span class="text-primary-400">→</span>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Tip -->
      <div class="mt-6 p-4 bg-blue-900/20 rounded-lg border border-blue-700/30 text-sm text-blue-200">
        <strong>Tip:</strong> Click any word to study it in detail. Use ← → keys to navigate, R for random.
      </div>
    </div>

  {:else if viewMode === 'detail' && selectedWord}
    <!-- Detail View -->
    <div class="max-w-3xl mx-auto">
      <!-- Navigation Bar -->
      <div class="mb-6 flex items-center justify-between">
        <button
          on:click={backToQueue}
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2"
        >
          ← Queue
        </button>

        <!-- Player-style controls -->
        <div class="flex items-center gap-2">
          <button
            on:click={goToPrevWord}
            disabled={currentQueueIndex <= 0}
            class="w-10 h-10 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-full flex items-center justify-center transition-colors"
            title="Previous word (←)"
          >
            ⏮
          </button>
          <button
            on:click={goToRandomWord}
            disabled={queueWords.length === 0}
            class="w-12 h-12 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-full flex items-center justify-center text-xl transition-all hover:scale-105"
            title="Random word (R)"
          >
            🎲
          </button>
          <button
            on:click={goToNextWord}
            disabled={currentQueueIndex >= queueWords.length - 1}
            class="w-10 h-10 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-full flex items-center justify-center transition-colors"
            title="Next word (→)"
          >
            ⏭
          </button>
        </div>

        <!-- Word counter -->
        <div class="text-slate-400 text-sm">
          {currentQueueIndex + 1} / {queueWords.length} in queue
        </div>
      </div>

      <!-- Word Card -->
      <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <!-- Header -->
        <div class="p-6 border-b border-slate-700 bg-gradient-to-r from-primary-900/20 to-slate-800">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-4xl font-bold text-white">{selectedWord.word}</h1>
              <div class="flex items-center gap-3 mt-2">
                <span class="text-slate-400">Seen {selectedWord.frequency} times</span>
                <span class="text-xs px-2 py-1 rounded {selectedWord.status === 'known' ? 'bg-green-900/50 text-green-400' : selectedWord.status === 'learning' ? 'bg-blue-900/50 text-blue-400' : 'bg-slate-700 text-slate-400'}">
                  {selectedWord.status || 'new'}
                </span>
              </div>
            </div>
            <button
              on:click={() => playTTS(selectedWord.word)}
              class="w-14 h-14 rounded-full bg-primary-600 hover:bg-primary-500 flex items-center justify-center text-white text-2xl transition-all hover:scale-105"
            >
              🔊
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="p-6 space-y-6">
          {#if loadingWord}
            <div class="text-center text-slate-400 py-8">Loading details...</div>
          {:else}
            {@const explanation = formatExplanation(selectedWord)}

            {#if explanation}
              <!-- Translation & Type -->
              {#if explanation.translation}
                <div>
                  <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Translation</h2>
                  <div class="flex items-center gap-3">
                    <p class="text-white text-xl">{explanation.translation}</p>
                    {#if explanation.type}
                      <span class="text-xs px-2 py-1 bg-slate-700 text-slate-400 rounded">{explanation.type}</span>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- Usage Patterns -->
              {#if explanation.usagePatterns?.length}
                <div>
                  <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Usage Patterns</h2>
                  <div class="space-y-3">
                    {#each explanation.usagePatterns as pattern}
                      <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="text-white font-medium">{pattern.pattern}</span>
                          {#if pattern.category}
                            <span class="text-xs px-2 py-0.5 bg-primary-900/50 text-primary-400 rounded">{pattern.category}</span>
                          {/if}
                        </div>
                        <p class="text-slate-400 text-sm">{pattern.meaning}</p>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Related Words -->
              {#if explanation.relatedWords?.length}
                <div>
                  <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">Related Words</h2>
                  <div class="space-y-2">
                    {#each explanation.relatedWords as related}
                      <div class="flex items-center gap-3 p-2 bg-slate-900/30 rounded-lg">
                        <span class="text-white font-medium">{related.word}</span>
                        <span class="text-xs px-2 py-0.5 bg-slate-700 text-slate-400 rounded">{related.relation}</span>
                        <span class="text-slate-400">→ {related.translation}</span>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Tip -->
              {#if explanation.tip}
                <div class="p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                  <h2 class="text-sm font-semibold text-yellow-400 mb-1">Tip</h2>
                  <p class="text-yellow-200">{explanation.tip}</p>
                </div>
              {/if}

              <!-- Note -->
              {#if explanation.note}
                <div class="p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
                  <h2 class="text-sm font-semibold text-blue-400 mb-1">Note</h2>
                  <p class="text-blue-200">{explanation.note}</p>
                </div>
              {/if}
            {:else}
              <div class="text-center py-8">
                <div class="text-4xl mb-3">📝</div>
                <p class="text-slate-400">No explanation available yet.</p>
                <p class="text-slate-500 text-sm mt-1">Generate explanations from Settings → Vocabulary.</p>
              </div>
            {/if}

            <!-- From Your Recordings -->
            {#if wordContexts.length > 0}
              <div>
                <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">From Your Recordings</h2>
                <div class="space-y-2">
                  {#each wordContexts.slice(0, 5) as context}
                    <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-700 flex items-start gap-3">
                      <button
                        on:click={() => playTTS(context)}
                        class="p-2 bg-slate-700 hover:bg-slate-600 rounded-full text-white shrink-0"
                      >
                        🔊
                      </button>
                      <p class="text-slate-300 italic leading-relaxed">"{context}"</p>
                    </div>
                  {/each}
                  {#if wordContexts.length > 5}
                    <p class="text-slate-500 text-sm">And {wordContexts.length - 5} more...</p>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Actions -->
        <div class="p-6 border-t border-slate-700 bg-slate-900/30">
          <div class="flex gap-3">
            <button
              on:click={() => markWord('known')}
              class="flex-1 py-3 bg-green-600 hover:bg-green-500 text-white font-medium rounded-lg transition-colors {selectedWord.status === 'known' ? 'ring-2 ring-green-400' : ''}"
            >
              {selectedWord.status === 'known' ? '✓ Known' : 'Mark as Known'}
            </button>
            <button
              on:click={() => markWord('learning')}
              class="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors {selectedWord.status === 'learning' ? 'ring-2 ring-blue-400' : ''}"
            >
              {selectedWord.status === 'learning' ? '✓ Learning' : 'Mark as Learning'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
