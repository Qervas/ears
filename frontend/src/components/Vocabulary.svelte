<script lang="ts">
  import { onMount } from 'svelte';
  import { vocabulary, vocabularyTotal, vocabularyLoading, vocabularyFilter, selectedWord } from '../lib/stores';
  import { getVocabulary, getWord, updateWordStatus, playTTS, explainWord, getWordsWithoutExplanations, generateSingleExplanation } from '../lib/api';
  import type { Word } from '../lib/api';

  let searchQuery = '';
  let explanation: any = null;  // Can be string or structured object
  let explaining = false;
  let loadingMore = false;
  let generatingBulk = false;
  let bulkProgress = { current: 0, total: 0 };
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

  async function generateAllExplanations() {
    try {
      // Get words without explanations
      const { words: wordsWithout } = await getWordsWithoutExplanations();

      if (wordsWithout.length === 0) {
        alert('All words already have explanations!');
        return;
      }

      if (!confirm(`Generate AI explanations for ${wordsWithout.length} words? This may take several minutes and requires LM Studio to be running.`)) {
        return;
      }

      generatingBulk = true;
      bulkProgress = { current: 0, total: wordsWithout.length };

      let successCount = 0;
      let failCount = 0;

      // Generate explanations one by one
      for (let i = 0; i < wordsWithout.length; i++) {
        const word = wordsWithout[i];
        try {
          const result = await generateSingleExplanation(word);
          if (result.success) {
            successCount++;
          } else {
            failCount++;
            console.error(`Failed to generate for ${word}:`, result.error);
          }
        } catch (e) {
          failCount++;
          console.error(`Error generating for ${word}:`, e);
        }
        bulkProgress.current = i + 1;
      }

      // Reload vocabulary to show updated explanations
      await loadVocabulary(false);
      // If a word is selected, reload it
      if ($selectedWord) {
        await selectWord($selectedWord);
      }

      alert(`✓ Generated ${successCount} explanations\n${failCount > 0 ? `✗ Failed: ${failCount}` : ''}`);
    } catch (e) {
      console.error('Failed to generate explanations:', e);
      alert('Failed to generate explanations. Make sure LM Studio is running.');
    } finally {
      generatingBulk = false;
      bulkProgress = { current: 0, total: 0 };
    }
  }

  $: filteredWords = searchQuery
    ? $vocabulary.filter(w => w.word.includes(searchQuery.toLowerCase()))
    : $vocabulary;

  onMount(() => loadVocabulary(false));
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

      <!-- Generate All Explanations Button -->
      <button
        class="w-full px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
        on:click={generateAllExplanations}
        disabled={generatingBulk}
      >
        {#if generatingBulk}
          <span class="animate-spin">⏳</span>
          Generating AI Explanations...
        {:else}
          🤖 Generate All AI Explanations
        {/if}
      </button>

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
{#if generatingBulk && bulkProgress.total > 0}
  <div class="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
    <div class="bg-slate-800 rounded-xl p-8 max-w-md w-full mx-4 border border-slate-700">
      <h3 class="text-xl font-bold text-white mb-4">Generating AI Explanations</h3>

      <div class="mb-4">
        <div class="flex justify-between text-sm text-slate-400 mb-2">
          <span>Progress</span>
          <span>{bulkProgress.current} / {bulkProgress.total}</span>
        </div>
        <div class="h-3 bg-slate-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-purple-600 transition-all duration-300"
            style="width: {(bulkProgress.current / bulkProgress.total) * 100}%"
          ></div>
        </div>
      </div>

      <p class="text-slate-400 text-sm text-center">
        This may take several minutes. Please wait...
      </p>
    </div>
  </div>
{/if}
