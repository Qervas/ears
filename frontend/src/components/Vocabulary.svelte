<script lang="ts">
  import { onMount } from 'svelte';
  import { vocabulary, vocabularyTotal, vocabularyLoading, vocabularyFilter, wordModal } from '../lib/stores';
  import { getVocabulary } from '../lib/api';
  import type { Word } from '../lib/api';

  let searchQuery = '';
  let loadingMore = false;
  let viewMode: 'dictionary' | 'shuffle' = 'dictionary';
  let dictionarySort: 'alphabetical' | 'frequency' = 'frequency';
  let shuffleSort: 'random' | 'frequency' = 'random';
  const PAGE_SIZE = 100;

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
    shuffleSort = 'random';
    await loadVocabulary(false);
  }

  function openWord(word: Word) {
    wordModal.set(word);
  }

  $: filteredWords = searchQuery
    ? $vocabulary.filter(w => w.word.includes(searchQuery.toLowerCase()))
    : $vocabulary;

  onMount(async () => {
    await loadVocabulary(false);
  });

  $: $vocabularyFilter, currentSort, loadVocabulary(false);
</script>

<div class="h-full flex flex-col">
  <!-- Header -->
  <div class="p-4 border-b border-slate-700 space-y-4">
    <div class="flex justify-between items-center">
      <h2 class="text-xl font-bold text-white">Dictionary</h2>
      <span class="text-slate-400">{$vocabularyTotal} words</span>
    </div>

    <!-- Search -->
    <input
      type="text"
      placeholder="Search words..."
      bind:value={searchQuery}
      class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
    />

    <div class="flex gap-4">
      <!-- Left: Mode & Sort -->
      <div class="flex-1 space-y-2">
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

        <!-- Sort options -->
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
      </div>

      <!-- Right: Filters -->
      <div class="flex-1">
        <div class="flex gap-2 flex-wrap">
          <button
            class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === null ? 'bg-primary-600 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => vocabularyFilter.set(null)}
          >All</button>
          <button
            class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === 'undiscovered' ? 'bg-slate-500 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => vocabularyFilter.set('undiscovered')}
          >New</button>
          <button
            class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === 'learning' ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => vocabularyFilter.set('learning')}
          >Learning</button>
          <button
            class="px-3 py-1 rounded-full text-sm {$vocabularyFilter === 'known' ? 'bg-green-600 text-white' : 'bg-slate-700 text-slate-300'}"
            on:click={() => vocabularyFilter.set('known')}
          >Known</button>
        </div>
      </div>
    </div>

    <!-- Reshuffle button -->
    {#if viewMode === 'shuffle' && shuffleSort === 'random'}
      <button
        class="w-full px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm"
        on:click={reshuffle}
      >
        Reshuffle
      </button>
    {/if}
  </div>

  <!-- Word Grid -->
  <div class="flex-1 overflow-auto p-4">
    {#if $vocabularyLoading}
      <div class="text-center text-slate-400 py-8">Loading...</div>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
        {#each filteredWords as word}
          <button
            class="p-3 rounded-lg text-left transition-all hover:scale-105
                   {word.status === 'known' ? 'bg-green-900/30 border border-green-700/50 hover:bg-green-900/50' :
                    word.status === 'learning' ? 'bg-yellow-900/30 border border-yellow-700/50 hover:bg-yellow-900/50' :
                    'bg-slate-800 border border-slate-700 hover:bg-slate-700'}"
            on:click={() => openWord(word)}
          >
            <div class="text-white font-medium truncate">{word.word}</div>
            <div class="text-slate-500 text-xs mt-1">{word.frequency}x</div>
          </button>
        {:else}
          <div class="col-span-full text-center text-slate-500 py-8">No words found</div>
        {/each}
      </div>

      <!-- Load More -->
      {#if hasMore}
        <div class="mt-4 text-center">
          <button
            class="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg disabled:opacity-50"
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
