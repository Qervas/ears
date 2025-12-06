<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { vocabulary, vocabularyTotal, vocabularyLoading, vocabularyFilter, selectedWord } from '../lib/stores';
  import { getVocabulary, getWord, updateWordStatus, playTTS, explainWord, startBulkGeneration, getBulkGenerationStatus } from '../lib/api';
  import type { Word, BulkGenerationStatus } from '../lib/api';

  let searchQuery = '';
  let explanation: any = null;  // Can be string or structured object
  let explaining = false;
  let loadingMore = false;
  let generatingBulk = false;
  let bulkStatus: BulkGenerationStatus = { running: false, current: 0, total: 0, completed: 0, failed: 0, failed_words: [] };
  let statusPollInterval: number | null = null;
  let currentGenerationMode: 'missing' | 'all' | null = null;  // Track which generation mode is running
  let viewMode: 'dictionary' | 'shuffle' = 'dictionary';
  let dictionarySort: 'alphabetical' | 'frequency' = 'frequency';
  let shuffleSort: 'random' | 'frequency' = 'random';
  const PAGE_SIZE = 100;

  // Compute current sort based on mode
  $: currentSort = viewMode === 'dictionary' ? dictionarySort : shuffleSort;

  async function loadVocabulary(append = false) {
    if (append) {
      loadingMore = true;
    } else {
      vocabularyLoading.set(true);
    }
    try {
      const offset = append ? $vocabulary.length : 0;
      const data = await getVocabulary(PAGE_SIZE, offset, $vocabularyFilter ?? undefined, currentSort);
      if (append) {
        vocabulary.update(v => [...v, ...data.words]);
      } else {
        vocabulary.set(data.words);
      }
      vocabularyTotal.set(data.total);
    } catch (e) {
      console.error('Failed to load vocabulary:', e);
    } finally {
      vocabularyLoading.set(false);
      loadingMore = false;
    }
  }

  function loadMore() {
    loadVocabulary(true);
  }

  $: hasMore = $vocabulary.length < $vocabularyTotal;

  function switchMode(mode: 'dictionary' | 'shuffle') {
    viewMode = mode;
  }

  async function reshuffle() {
    // Force reload with random sort
    shuffleSort = 'random';
    await loadVocabulary(false);
  }

  async function selectWord(word: Word) {
    try {
      const fullWord = await getWord(word.word);
      selectedWord.set(fullWord);

      // Load saved explanation (prefer JSON, fallback to text)
      if (fullWord.explanation_json) {
        try {
          explanation = JSON.parse(fullWord.explanation_json);
        } catch (e) {
          console.error('Failed to parse explanation JSON:', e);
          explanation = fullWord.explanation || null;
        }
      } else {
        explanation = fullWord.explanation || null;
      }
    } catch (e) {
      console.error('Failed to load word:', e);
    }
  }

  async function setStatus(word: string, status: string) {
    await updateWordStatus(word, status);
    await loadVocabulary();
    if ($selectedWord?.word === word) {
      selectedWord.update(w => w ? { ...w, status: status as any } : null);
    }
  }

  async function explain() {
    if (!$selectedWord) return;
    explaining = true;
    try {
      const context = $selectedWord.contexts?.[0] || '';
      const result = await explainWord($selectedWord.word, context);
      explanation = result.explanation;
    } catch (e) {
      explanation = 'Failed to get explanation. Is LM Studio running?';
    } finally {
      explaining = false;
    }
  }

  function speak(text: string) {
    playTTS(text).catch(console.error);
  }

  async function pollBulkStatus() {
    try {
      bulkStatus = await getBulkGenerationStatus();

      if (!bulkStatus.running && generatingBulk) {
        // Generation just finished
        const mode = currentGenerationMode;
        generatingBulk = false;
        currentGenerationMode = null;

        if (statusPollInterval) {
          clearInterval(statusPollInterval);
          statusPollInterval = null;
        }

        // Reload vocabulary to show updated explanations
        await loadVocabulary(false);
        if ($selectedWord) {
          await selectWord($selectedWord);
        }

        const modeText = mode === 'all' ? 'Regenerated ALL' : 'Generated';

        // Build completion message
        let message = `✓ ${modeText} ${bulkStatus.completed} explanations`;

        if (bulkStatus.failed > 0) {
          message += `\n\n✗ Failed: ${bulkStatus.failed} words`;

          // Show first 5 failed words
          if (bulkStatus.failed_words && bulkStatus.failed_words.length > 0) {
            message += '\n\nFailed words:';
            const showCount = Math.min(5, bulkStatus.failed_words.length);
            for (let i = 0; i < showCount; i++) {
              const item = bulkStatus.failed_words[i];
              message += `\n  • ${item.word} (${item.error})`;
            }
            if (bulkStatus.failed_words.length > 5) {
              message += `\n  ... and ${bulkStatus.failed_words.length - 5} more`;
            }
            message += '\n\nCheck backend console for full details.';
          }
        }

        alert(message);
      }
    } catch (e) {
      console.error('Failed to poll bulk status:', e);
    }
  }

  async function generateAllExplanations() {
    try {
      // Check if already running first
      const status = await getBulkGenerationStatus();
      if (status.running) {
        alert(`Generation already in progress!\n\nMode: Generate Missing Only\nCurrent: ${status.current}/${status.total}\nCompleted: ${status.completed}\nFailed: ${status.failed}\n\nPlease wait for it to finish.`);

        // Make sure we're polling
        if (!statusPollInterval) {
          generatingBulk = true;
          statusPollInterval = window.setInterval(pollBulkStatus, 1000);
        }
        return;
      }

      if (!confirm(`Generate AI explanations for words that don't have them yet?\n\nThis will ONLY process words without explanations.\nThis will run in the background and may take several minutes.`)) {
        return;
      }

      const result = await startBulkGeneration();

      if (result.count === 0) {
        alert('All words already have explanations!');
        return;
      }

      generatingBulk = true;
      currentGenerationMode = 'missing';  // Track which mode we're in

      // Start polling for status updates every second
      statusPollInterval = window.setInterval(pollBulkStatus, 1000);

      alert(`Started generating explanations for ${result.count} words WITHOUT existing explanations.\n\nYou can continue using the app while this runs in the background.`);
    } catch (e) {
      console.error('Failed to start bulk generation:', e);
      alert('Failed to start bulk generation. Make sure the AI provider is configured and the backend server is active.');
    }
  }

  async function regenerateAllExplanations() {
    try {
      // Check if already running first
      const status = await getBulkGenerationStatus();
      if (status.running) {
        alert(`Generation already in progress!\n\nMode: Regenerate ALL Words\nCurrent: ${status.current}/${status.total}\nCompleted: ${status.completed}\nFailed: ${status.failed}\n\nPlease wait for it to finish before starting a new one.`);

        // Make sure we're polling
        if (!statusPollInterval) {
          generatingBulk = true;
          statusPollInterval = window.setInterval(pollBulkStatus, 1000);
        }
        return;
      }

      if (!confirm(`⚠️ REGENERATE ALL ${$vocabularyTotal} WORDS?\n\nThis will OVERWRITE all existing explanations including the ${$vocabularyTotal - ($vocabularyTotal - 2020)} you already have!\n\nOnly use this if you want to start completely fresh.\n\nAre you sure?`)) {
        return;
      }

      const response = await fetch('http://localhost:8000/api/vocabulary/regenerate-all-explanations', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to start regeneration');
      }

      const result = await response.json();

      generatingBulk = true;
      currentGenerationMode = 'all';  // Track which mode we're in

      // Start polling for status updates every second
      statusPollInterval = window.setInterval(pollBulkStatus, 1000);

      alert(`Started REGENERATING ALL ${result.count} words (including existing ones).\n\nThis will take a very long time. You can continue using the app.`);
    } catch (e) {
      console.error('Failed to start regeneration:', e);
      alert('Failed to start regeneration. Make sure the AI provider is configured and the backend server is active.');
    }
  }

  $: filteredWords = searchQuery
    ? $vocabulary.filter(w => w.word.includes(searchQuery.toLowerCase()))
    : $vocabulary;

  onMount(async () => {
    await loadVocabulary(false);

    // Check if bulk generation is already running
    try {
      const status = await getBulkGenerationStatus();
      if (status.running) {
        generatingBulk = true;
        bulkStatus = status;
        statusPollInterval = window.setInterval(pollBulkStatus, 1000);
      }
    } catch (e) {
      console.error('Failed to check bulk generation status:', e);
    }
  });

  onDestroy(() => {
    if (statusPollInterval) {
      clearInterval(statusPollInterval);
    }
  });

  $: $vocabularyFilter, currentSort, loadVocabulary(false);
</script>

<div class="flex h-full">
  <!-- Word List -->
  <div class="w-1/2 border-r border-slate-700 flex flex-col">
    <!-- Header -->
    <div class="p-4 border-b border-slate-700 space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-xl font-bold text-white">Vocabulary</h2>
        <span class="text-slate-400">{$vocabularyTotal} words</span>
      </div>

      <!-- Search -->
      <input
        type="text"
        placeholder="Search words..."
        bind:value={searchQuery}
        class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
      />

      <!-- Mode Switcher -->
      <div class="flex gap-2">
        <button
          class="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                 {viewMode === 'dictionary' ? 'bg-primary-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
          on:click={() => switchMode('dictionary')}
        >
          Dictionary
        </button>
        <button
          class="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                 {viewMode === 'shuffle' ? 'bg-primary-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
          on:click={() => switchMode('shuffle')}
        >
          Shuffle
        </button>
      </div>

      <!-- Sort options based on mode -->
      <div class="flex gap-2">
        {#if viewMode === 'dictionary'}
          <button
            class="flex-1 px-3 py-1 rounded text-sm {dictionarySort === 'alphabetical' ? 'bg-slate-600 text-white' : 'bg-slate-700 text-slate-400'}"
            on:click={() => dictionarySort = 'alphabetical'}
          >A-Z</button>
          <button
            class="flex-1 px-3 py-1 rounded text-sm {dictionarySort === 'frequency' ? 'bg-slate-600 text-white' : 'bg-slate-700 text-slate-400'}"
            on:click={() => dictionarySort = 'frequency'}
          >Frequency</button>
        {:else}
          <button
            class="flex-1 px-3 py-1 rounded text-sm {shuffleSort === 'random' ? 'bg-slate-600 text-white' : 'bg-slate-700 text-slate-400'}"
            on:click={() => shuffleSort = 'random'}
          >Random</button>
          <button
            class="flex-1 px-3 py-1 rounded text-sm {shuffleSort === 'frequency' ? 'bg-slate-600 text-white' : 'bg-slate-700 text-slate-400'}"
            on:click={() => shuffleSort = 'frequency'}
          >By Frequency</button>
        {/if}
      </div>

      <!-- Filters -->
      <div class="flex gap-2">
        <button
          class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === null ? 'bg-primary-600 text-white' : 'bg-slate-700 text-slate-300'}"
          on:click={() => vocabularyFilter.set(null)}
        >All</button>
        <button
          class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === 'learning' ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-slate-300'}"
          on:click={() => vocabularyFilter.set('learning')}
        >Learning</button>
        <button
          class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === 'known' ? 'bg-green-600 text-white' : 'bg-slate-700 text-slate-300'}"
          on:click={() => vocabularyFilter.set('known')}
        >Known</button>
      </div>

      <!-- Generate Explanations Buttons -->
      <div class="grid grid-cols-2 gap-2">
        <button
          title="Generate explanations only for words that don't have them yet. Safe to use - won't touch existing explanations."
          class="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
          on:click={generateAllExplanations}
          disabled={generatingBulk}
        >
          {#if generatingBulk && currentGenerationMode === 'missing'}
            <span class="animate-spin">⏳</span>
            Generating...
          {:else}
            🤖 Missing Only
          {/if}
        </button>

        <button
          title="⚠️ WARNING: Regenerate ALL words including ones that already have explanations. This will overwrite everything!"
          class="px-3 py-2 bg-orange-600 hover:bg-orange-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
          on:click={regenerateAllExplanations}
          disabled={generatingBulk}
        >
          {#if generatingBulk && currentGenerationMode === 'all'}
            <span class="animate-spin">⏳</span>
            Regenerating...
          {:else}
            ⚠️ Regen ALL
          {/if}
        </button>
      </div>

      <!-- Reshuffle button (only in shuffle mode with random sort) -->
      {#if viewMode === 'shuffle' && shuffleSort === 'random'}
        <button
          class="w-full px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm"
          on:click={reshuffle}
        >
          Reshuffle
        </button>
      {/if}
    </div>

    <!-- Word List -->
    <div class="flex-1 overflow-auto">
      {#if $vocabularyLoading}
        <div class="p-8 text-center text-slate-400">Loading...</div>
      {:else}
        <div class="divide-y divide-slate-700">
          {#each filteredWords as word}
            <button
              class="w-full p-4 text-left hover:bg-slate-800 transition-colors
                     {$selectedWord?.word === word.word ? 'bg-slate-800' : ''}"
              on:click={() => selectWord(word)}
            >
              <div class="flex justify-between items-center">
                <span class="text-white font-medium">{word.word}</span>
                <span class="text-slate-500 text-sm">{word.frequency}x</span>
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="px-2 py-0.5 rounded text-xs
                  {word.status === 'known' ? 'bg-green-900 text-green-300' :
                   'bg-yellow-900 text-yellow-300'}">
                  {word.status}
                </span>
              </div>
            </button>
          {:else}
            <div class="p-8 text-center text-slate-500">No words found</div>
          {/each}
        </div>

        <!-- Load More Button -->
        {#if hasMore}
          <div class="p-4 border-t border-slate-700">
            <button
              class="w-full py-2 px-4 bg-slate-700 hover:bg-slate-600 text-white rounded-lg disabled:opacity-50"
              on:click={loadMore}
              disabled={loadingMore}
            >
              {#if loadingMore}
                Loading...
              {:else}
                Load More ({$vocabulary.length} / {$vocabularyTotal})
              {/if}
            </button>
          </div>
        {/if}
      {/if}
    </div>
  </div>

  <!-- Word Detail -->
  <div class="w-1/2 p-6">
    {#if $selectedWord}
      <div class="space-y-6">
        <!-- Word Header -->
        <div class="flex items-center gap-4">
          <h2 class="text-3xl font-bold text-white">{$selectedWord.word}</h2>
          <button
            class="p-2 rounded-full bg-slate-700 hover:bg-slate-600 text-white"
            on:click={() => speak($selectedWord.word)}
            title="Pronounce"
          >
            🔊
          </button>
        </div>

        <!-- Stats -->
        <div class="flex gap-4 text-sm">
          <span class="text-slate-400">Seen {$selectedWord.frequency} times</span>
          <span class="text-slate-500">•</span>
          <span class="text-slate-400">First seen: {new Date($selectedWord.first_seen).toLocaleDateString()}</span>
        </div>

        <!-- Status Buttons -->
        <div class="flex gap-2">
          <button
            class="px-4 py-2 rounded-lg {$selectedWord.status === 'learning' ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => setStatus($selectedWord.word, 'learning')}
          >Learning</button>
          <button
            class="px-4 py-2 rounded-lg {$selectedWord.status === 'known' ? 'bg-green-600 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => setStatus($selectedWord.word, 'known')}
          >Known</button>
        </div>

        <!-- AI Explanation -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-white">AI Explanation</h3>
            <button
              class="px-3 py-1 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm disabled:opacity-50"
              on:click={explain}
              disabled={explaining}
            >
              {explaining ? 'Generating...' : 'Get Explanation'}
            </button>
          </div>

          {#if explanation}
            {#if typeof explanation === 'object' && !explanation.raw}
              <!-- Structured Explanation -->
              <div class="space-y-4">
                <!-- Translation & Type -->
                <div class="p-4 bg-slate-800 rounded-lg border border-slate-700">
                  <div class="flex items-baseline gap-3">
                    <span class="text-2xl font-bold text-primary-400">{explanation.translation}</span>
                    <span class="text-sm text-slate-500">({explanation.type})</span>
                  </div>
                </div>

                <!-- Usage Patterns -->
                {#if explanation.usagePatterns?.length}
                  <div class="p-4 bg-slate-800 rounded-lg border border-slate-700">
                    <h4 class="text-sm font-semibold text-slate-400 mb-3">💡 Common Usage</h4>
                    <div class="space-y-2">
                      {#each explanation.usagePatterns as pattern}
                        <div class="flex items-start gap-2">
                          <span class="text-slate-600">•</span>
                          <div>
                            <span class="text-white font-medium">{pattern.pattern}</span>
                            <span class="text-slate-500"> → {pattern.meaning}</span>
                            {#if pattern.category}
                              <span class="ml-2 text-xs text-slate-600">({pattern.category})</span>
                            {/if}
                          </div>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Related Words -->
                {#if explanation.relatedWords?.length}
                  <div class="p-4 bg-slate-800 rounded-lg border border-slate-700">
                    <h4 class="text-sm font-semibold text-slate-400 mb-3">🔗 Related Words</h4>
                    <div class="flex flex-wrap gap-2">
                      {#each explanation.relatedWords as related}
                        <div class="px-3 py-1.5 bg-slate-700 rounded-lg text-sm">
                          <span class="text-white font-medium">{related.word}</span>
                          <span class="text-slate-500 mx-1">·</span>
                          <span class="text-slate-400">{related.translation}</span>
                          <span class="ml-1 text-xs text-slate-600">({related.relation})</span>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Tip -->
                {#if explanation.tip}
                  <div class="p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                    <div class="flex items-start gap-2">
                      <span class="text-yellow-400">💡</span>
                      <p class="text-yellow-200 text-sm">{explanation.tip}</p>
                    </div>
                  </div>
                {/if}

                <!-- Cultural Note -->
                {#if explanation.note}
                  <div class="p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
                    <div class="flex items-start gap-2">
                      <span class="text-blue-400">ℹ️</span>
                      <p class="text-blue-200 text-sm">{explanation.note}</p>
                    </div>
                  </div>
                {/if}
              </div>
            {:else}
              <!-- Legacy Plain Text Explanation -->
              <div class="p-4 bg-slate-800 rounded-lg border border-slate-700 whitespace-pre-wrap text-slate-300">
                {typeof explanation === 'object' ? explanation.raw : explanation}
              </div>
            {/if}
          {:else}
            <div class="p-4 bg-slate-800 rounded-lg border border-slate-700 text-slate-500">
              Click "Get Explanation" to have AI explain this word
            </div>
          {/if}
        </div>

        <!-- Example Sentences -->
        {#if $selectedWord.contexts?.length}
          <div>
            <h3 class="text-lg font-semibold text-white mb-3">Example Sentences</h3>
            <div class="space-y-2">
              {#each $selectedWord.contexts as context}
                <div class="p-3 bg-slate-800 rounded-lg border border-slate-700 flex items-start gap-3">
                  <button
                    class="text-slate-400 hover:text-white shrink-0"
                    on:click={() => speak(context)}
                  >🔊</button>
                  <p class="text-slate-300">{context}</p>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <div class="h-full flex items-center justify-center text-slate-500">
        Select a word to see details
      </div>
    {/if}
  </div>
</div>

<!-- Progress Modal -->
{#if generatingBulk && bulkStatus.total > 0}
  <div class="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
    <div class="bg-slate-800 rounded-xl p-8 max-w-md w-full mx-4 border border-slate-700">
      <h3 class="text-xl font-bold text-white mb-2">Generating AI Explanations</h3>

      {#if currentGenerationMode === 'missing'}
        <p class="text-sm text-green-400 mb-4">📝 Mode: Generate Missing Only ({bulkStatus.total} words)</p>
      {:else if currentGenerationMode === 'all'}
        <p class="text-sm text-orange-400 mb-4">⚠️ Mode: Regenerating ALL Words ({bulkStatus.total} words)</p>
      {:else}
        <p class="text-sm text-slate-400 mb-4">Processing {bulkStatus.total} words</p>
      {/if}

      <div class="mb-4">
        <div class="flex justify-between text-sm text-slate-400 mb-2">
          <span>Progress</span>
          <span>{bulkStatus.current} / {bulkStatus.total}</span>
        </div>
        <div class="h-3 bg-slate-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-purple-600 transition-all duration-300"
            style="width: {bulkStatus.total > 0 ? (bulkStatus.current / bulkStatus.total) * 100 : 0}%"
          ></div>
        </div>
      </div>

      <div class="space-y-2 mb-4">
        <div class="flex justify-between text-xs text-slate-500">
          <span>Completed: {bulkStatus.completed}</span>
          <span>Failed: {bulkStatus.failed}</span>
        </div>
      </div>

      <p class="text-slate-400 text-sm text-center">
        Running in background. You can continue using the app.
      </p>
    </div>
  </div>
{/if}
