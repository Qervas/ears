<script lang="ts">
  import { onMount } from 'svelte';
  import { stats, currentView } from '../lib/stores';
  import { getProgress, getVocabulary } from '../lib/api';
  import type { Word } from '../lib/api';

  let progress = { total_words: 0, known: 0, learning: 0, new: 0, progress_percent: 0 };
  let recentWords: Word[] = [];
  let loading = true;

  onMount(async () => {
    try {
      const [progressData, vocabData] = await Promise.all([
        getProgress(),
        getVocabulary(10, 0, undefined, 'recent')
      ]);
      progress = progressData;
      recentWords = vocabData.words;
    } catch (e) {
      console.error('Failed to load dashboard:', e);
    } finally {
      loading = false;
    }
  });
</script>

<div class="p-8">
  <h2 class="text-3xl font-bold text-white mb-8">Dashboard</h2>

  {#if loading}
    <div class="text-slate-400">Loading...</div>
  {:else}
    <!-- Stats Cards -->
    <div class="grid grid-cols-4 gap-6 mb-8">
      <div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div class="text-slate-400 text-sm mb-1">Total Words</div>
        <div class="text-3xl font-bold text-white">{progress.total_words}</div>
      </div>
      <div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div class="text-slate-400 text-sm mb-1">Known</div>
        <div class="text-3xl font-bold text-green-400">{progress.known}</div>
      </div>
      <div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div class="text-slate-400 text-sm mb-1">Learning</div>
        <div class="text-3xl font-bold text-yellow-400">{progress.learning}</div>
      </div>
      <div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div class="text-slate-400 text-sm mb-1">Progress</div>
        <div class="text-3xl font-bold text-primary-400">{progress.progress_percent}%</div>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-8">
      <div class="flex justify-between mb-2">
        <span class="text-slate-300">Overall Progress</span>
        <span class="text-slate-400">{progress.known} / {progress.total_words} words mastered</span>
      </div>
      <div class="h-4 bg-slate-700 rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-primary-500 to-green-500 transition-all duration-500"
          style="width: {progress.progress_percent}%"
        ></div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="grid grid-cols-2 gap-6 mb-8">
      <button
        class="bg-primary-600 hover:bg-primary-500 text-white rounded-xl p-6 text-left transition-colors"
        on:click={() => currentView.set('practice')}
      >
        <div class="text-2xl mb-2">🎯</div>
        <div class="text-xl font-semibold">Start Learning</div>
        <div class="text-primary-200 text-sm">Practice your vocabulary</div>
      </button>
      <button
        class="bg-slate-800 hover:bg-slate-700 text-white rounded-xl p-6 text-left border border-slate-700 transition-colors"
        on:click={() => currentView.set('recordings')}
      >
        <div class="text-2xl mb-2">🎙️</div>
        <div class="text-xl font-semibold">Add Content</div>
        <div class="text-slate-400 text-sm">Record and transcribe new audio</div>
      </button>
    </div>

    <!-- Recent Words -->
    <div class="bg-slate-800 rounded-xl border border-slate-700">
      <div class="p-4 border-b border-slate-700 flex justify-between items-center">
        <h3 class="text-lg font-semibold text-white">Recent Words</h3>
        <button
          class="text-primary-400 hover:text-primary-300 text-sm"
          on:click={() => currentView.set('dictionary')}
        >
          View all →
        </button>
      </div>
      <div class="divide-y divide-slate-700">
        {#each recentWords as word}
          <div class="p-4 flex justify-between items-center">
            <div>
              <span class="text-white font-medium">{word.word}</span>
              <span class="text-slate-500 text-sm ml-2">seen {word.frequency}x</span>
            </div>
            <span class="px-2 py-1 rounded text-xs
              {word.status === 'known' ? 'bg-green-900 text-green-300' :
               word.status === 'learning' ? 'bg-yellow-900 text-yellow-300' :
               'bg-slate-700 text-slate-400'}">
              {word.status}
            </span>
          </div>
        {:else}
          <div class="p-8 text-center text-slate-500">
            No words yet. Record some audio to get started!
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
