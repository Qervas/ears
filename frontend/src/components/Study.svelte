<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getVocabulary, getWord, updateWordStatus, playTTS, getStats, type Word } from '../lib/api';
  import { selectedStudyWord, stats, currentView, wordModal } from '../lib/stores';

  // Study modes
  type StudyMode = 'overview' | 'discover' | 'learning' | 'detail';
  let mode: StudyMode = 'overview';

  // All words for knowledge map
  let allWords: Word[] = [];
  let loadingMap = true;

  // Discover mode state
  let discoverWords: Word[] = [];
  let currentDiscoverIndex = 0;
  let loadingDiscover = false;

  // Learning queue state
  let learningWords: Word[] = [];
  let currentLearningIndex = 0;

  // Detail view state
  let selectedWord: Word | null = null;
  let wordContexts: string[] = [];
  let loadingWord = false;

  // Matrix dimensions
  const MATRIX_SIZE = 20; // 20x20 = 400 words per matrix

  async function loadAllWords() {
    loadingMap = true;
    try {
      // Load all words for the knowledge map
      const statsData = await getStats();
      stats.set(statsData);

      const result = await getVocabulary(5000, 0, undefined, 'frequency');
      allWords = result.words;
    } catch (e) {
      console.error('Failed to load words:', e);
    } finally {
      loadingMap = false;
    }
  }

  async function loadLearningWords() {
    try {
      const result = await getVocabulary(100, 0, 'learning', 'frequency');
      learningWords = result.words;
    } catch (e) {
      console.error('Failed to load learning words:', e);
    }
  }

  async function startDiscover() {
    mode = 'discover';
    loadingDiscover = true;
    currentDiscoverIndex = 0;
    try {
      // Load undiscovered words sorted by frequency
      const result = await getVocabulary(50, 0, 'undiscovered', 'frequency');
      discoverWords = result.words;
    } catch (e) {
      console.error('Failed to load discover words:', e);
    } finally {
      loadingDiscover = false;
    }
  }

  async function startLearning() {
    mode = 'learning';
    currentLearningIndex = 0;
    await loadLearningWords();
    if (learningWords.length > 0) {
      await openWordDetail(learningWords[0]);
    }
  }

  async function openWordDetail(word: Word) {
    selectedWord = word;
    mode = 'detail';
    loadingWord = true;
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

  function backToOverview() {
    mode = 'overview';
    selectedWord = null;
    loadAllWords();
    loadLearningWords();
  }

  async function markWord(status: 'undiscovered' | 'learning' | 'known') {
    if (!selectedWord) return;
    try {
      await updateWordStatus(selectedWord.word, status);
      selectedWord = { ...selectedWord, status };

      // Refresh stats
      const statsData = await getStats();
      stats.set(statsData);

      // Update in allWords for map
      allWords = allWords.map(w => w.word === selectedWord!.word ? { ...w, status } : w);
    } catch (e) {
      console.error('Failed to update status:', e);
    }
  }

  // Discover mode: mark and go to next
  async function discoverAction(status: 'learning' | 'known' | 'skip') {
    const currentWord = discoverWords[currentDiscoverIndex];
    if (!currentWord) return;

    if (status !== 'skip') {
      await updateWordStatus(currentWord.word, status);
      // Update in allWords
      allWords = allWords.map(w => w.word === currentWord.word ? { ...w, status } : w);
      // Refresh stats
      const statsData = await getStats();
      stats.set(statsData);
    }

    // Move to next
    if (currentDiscoverIndex < discoverWords.length - 1) {
      currentDiscoverIndex++;
    } else {
      // Reload more undiscovered words or go back
      const result = await getVocabulary(50, 0, 'undiscovered', 'frequency');
      if (result.words.length > 0) {
        discoverWords = result.words;
        currentDiscoverIndex = 0;
      } else {
        backToOverview();
      }
    }
  }

  // Learning mode navigation
  async function nextLearningWord() {
    if (currentLearningIndex < learningWords.length - 1) {
      currentLearningIndex++;
      await openWordDetail(learningWords[currentLearningIndex]);
    }
  }

  async function prevLearningWord() {
    if (currentLearningIndex > 0) {
      currentLearningIndex--;
      await openWordDetail(learningWords[currentLearningIndex]);
    }
  }

  // Parse explanation JSON
  interface Explanation {
    translation?: string;
    type?: string;
    usagePatterns?: { pattern: string; meaning: string; category?: string }[];
    relatedWords?: { word: string; relation: string; translation: string }[];
    tip?: string;
    note?: string;
  }

  function parseExplanation(word: Word): Explanation | null {
    if (!word.explanation_json) return null;
    try {
      return JSON.parse(word.explanation_json);
    } catch {
      return null;
    }
  }

  // Get color for word status
  function getStatusColor(status: string): string {
    switch (status) {
      case 'known': return 'bg-green-500';
      case 'learning': return 'bg-yellow-500';
      default: return 'bg-slate-600';
    }
  }

  // Split words into matrices
  function getMatrices(words: Word[]): Word[][] {
    const matrices: Word[][] = [];
    const wordsPerMatrix = MATRIX_SIZE * MATRIX_SIZE;
    for (let i = 0; i < words.length; i += wordsPerMatrix) {
      matrices.push(words.slice(i, i + wordsPerMatrix));
    }
    return matrices;
  }

  // Handle word passed from Dictionary page
  onMount(() => {
    const unsubscribe = selectedStudyWord.subscribe(async word => {
      if (word) {
        await openWordDetail(word);
        selectedStudyWord.set(null);
      }
    });

    loadAllWords();
    loadLearningWords();

    return () => unsubscribe();
  });

  // Keyboard navigation
  function handleKeydown(e: KeyboardEvent) {
    if (mode === 'detail' || mode === 'learning') {
      if (e.key === 'Escape') {
        backToOverview();
      } else if (e.key === 'ArrowRight' && mode === 'learning') {
        nextLearningWord();
      } else if (e.key === 'ArrowLeft' && mode === 'learning') {
        prevLearningWord();
      }
    } else if (mode === 'discover') {
      if (e.key === 'Escape') {
        backToOverview();
      } else if (e.key === 'l' || e.key === 'L') {
        discoverAction('learning');
      } else if (e.key === 'k' || e.key === 'K') {
        discoverAction('known');
      } else if (e.key === 's' || e.key === 'S' || e.key === ' ') {
        discoverAction('skip');
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

<div class="h-full overflow-auto bg-slate-900">
  {#if mode === 'overview'}
    <!-- Overview with Knowledge Map -->
    <div class="p-8">
      <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="mb-8">
          <h1 class="text-3xl font-bold text-white">Study</h1>
          <p class="text-slate-400 mt-1">Your Swedish vocabulary journey</p>
        </div>

        <!-- Stats Cards -->
        {#if $stats}
          <div class="grid grid-cols-4 gap-4 mb-8">
            <div class="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <div class="text-slate-400 text-sm">Total Words</div>
              <div class="text-2xl font-bold text-white">{$stats.total}</div>
            </div>
            <button
              class="bg-slate-800 rounded-xl p-4 border border-slate-600 hover:border-slate-500 transition-colors text-left"
              on:click={startDiscover}
            >
              <div class="text-slate-400 text-sm">Undiscovered</div>
              <div class="text-2xl font-bold text-slate-300">{$stats.undiscovered}</div>
              <div class="text-xs text-primary-400 mt-1">Click to discover →</div>
            </button>
            <button
              class="bg-slate-800 rounded-xl p-4 border border-yellow-700/50 hover:border-yellow-600 transition-colors text-left"
              on:click={startLearning}
              disabled={learningWords.length === 0}
            >
              <div class="text-yellow-400 text-sm">Learning</div>
              <div class="text-2xl font-bold text-yellow-300">{$stats.learning}</div>
              <div class="text-xs text-yellow-400/70 mt-1">Click to study →</div>
            </button>
            <div class="bg-slate-800 rounded-xl p-4 border border-green-700/50">
              <div class="text-green-400 text-sm">Known</div>
              <div class="text-2xl font-bold text-green-300">{$stats.known}</div>
            </div>
          </div>
        {/if}

        <!-- Knowledge Map -->
        <div class="bg-slate-800 rounded-xl border border-slate-700 p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-white">Knowledge Map</h2>
            <div class="flex items-center gap-4 text-xs">
              <div class="flex items-center gap-1">
                <div class="w-3 h-3 rounded bg-slate-600"></div>
                <span class="text-slate-400">Undiscovered</span>
              </div>
              <div class="flex items-center gap-1">
                <div class="w-3 h-3 rounded bg-yellow-500"></div>
                <span class="text-slate-400">Learning</span>
              </div>
              <div class="flex items-center gap-1">
                <div class="w-3 h-3 rounded bg-green-500"></div>
                <span class="text-slate-400">Known</span>
              </div>
            </div>
          </div>

          {#if loadingMap}
            <div class="text-center text-slate-400 py-8">Loading knowledge map...</div>
          {:else}
            <!-- Matrix Grid -->
            <div class="space-y-6">
              {#each getMatrices(allWords) as matrix, matrixIndex}
                <div>
                  <div class="text-xs text-slate-500 mb-2">
                    Words {matrixIndex * MATRIX_SIZE * MATRIX_SIZE + 1} - {Math.min((matrixIndex + 1) * MATRIX_SIZE * MATRIX_SIZE, allWords.length)}
                    (by frequency)
                  </div>
                  <div class="grid gap-px bg-slate-700 rounded overflow-hidden" style="grid-template-columns: repeat({MATRIX_SIZE}, 1fr);">
                    {#each matrix as word, i}
                      <button
                        class="aspect-square {getStatusColor(word.status)} hover:brightness-125 transition-all"
                        title="{word.word} ({word.frequency}x) - {word.status}"
                        on:click={() => wordModal.set(word)}
                      ></button>
                    {/each}
                    <!-- Fill empty cells if matrix is not complete -->
                    {#each Array(MATRIX_SIZE * MATRIX_SIZE - matrix.length) as _}
                      <div class="aspect-square bg-slate-800"></div>
                    {/each}
                  </div>
                </div>
              {/each}
            </div>

            {#if allWords.length === 0}
              <div class="text-center py-12">
                <div class="text-5xl mb-4">📚</div>
                <p class="text-slate-400">No words yet. Record some Swedish audio to build your vocabulary!</p>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Quick Actions -->
        <div class="mt-6 grid grid-cols-2 gap-4">
          <button
            class="p-4 bg-slate-800 rounded-xl border border-slate-700 hover:border-primary-500 transition-colors text-left"
            on:click={startDiscover}
          >
            <div class="text-2xl mb-2">🔍</div>
            <h3 class="text-white font-semibold">Discover New Words</h3>
            <p class="text-slate-400 text-sm">Go through undiscovered words and add them to your study queue</p>
          </button>
          <button
            class="p-4 bg-slate-800 rounded-xl border border-slate-700 hover:border-yellow-500 transition-colors text-left"
            on:click={startLearning}
            disabled={learningWords.length === 0}
          >
            <div class="text-2xl mb-2">📖</div>
            <h3 class="text-white font-semibold">Study Queue ({learningWords.length})</h3>
            <p class="text-slate-400 text-sm">Review words you're currently learning</p>
          </button>
        </div>
      </div>
    </div>

  {:else if mode === 'discover'}
    <!-- Discover Mode -->
    <div class="p-8 h-full flex flex-col">
      <div class="max-w-2xl mx-auto flex-1 flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
          <button
            on:click={backToOverview}
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          >
            ← Back
          </button>
          <h2 class="text-xl font-bold text-white">Discover New Words</h2>
          <div class="text-slate-400">
            {currentDiscoverIndex + 1} / {discoverWords.length}
          </div>
        </div>

        {#if loadingDiscover}
          <div class="flex-1 flex items-center justify-center text-slate-400">
            Loading words...
          </div>
        {:else if discoverWords.length === 0}
          <div class="flex-1 flex flex-col items-center justify-center">
            <div class="text-5xl mb-4">🎉</div>
            <h3 class="text-xl font-bold text-white mb-2">All Caught Up!</h3>
            <p class="text-slate-400 mb-6">No more undiscovered words to review.</p>
            <button
              class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg"
              on:click={backToOverview}
            >
              Back to Overview
            </button>
          </div>
        {:else}
          {@const word = discoverWords[currentDiscoverIndex]}
          {@const explanation = parseExplanation(word)}

          <!-- Word Card -->
          <div class="flex-1 flex flex-col">
            <div class="bg-slate-800 rounded-xl border border-slate-700 flex-1 flex flex-col">
              <!-- Word -->
              <div class="p-8 text-center flex-1 flex flex-col justify-center">
                <div class="text-slate-400 text-sm mb-2">Seen {word.frequency} times</div>
                <button
                  class="text-5xl font-bold text-white mb-4 hover:text-primary-400 transition-colors cursor-pointer"
                  on:click={() => wordModal.set(word)}
                >
                  {word.word}
                </button>
                <button
                  class="mx-auto p-3 rounded-full bg-slate-700 hover:bg-slate-600 text-white text-xl"
                  on:click={() => playTTS(word.word)}
                >
                  🔊
                </button>

                {#if explanation}
                  <button
                    class="mt-6 text-xl text-primary-400 hover:text-primary-300 transition-colors"
                    on:click={() => wordModal.set(word)}
                  >
                    {explanation.translation}
                  </button>
                  {#if explanation.type}
                    <div class="text-slate-500 text-sm">({explanation.type})</div>
                  {/if}
                {/if}
                <div class="mt-4 text-slate-500 text-xs">Click word for details</div>
              </div>

              <!-- Actions -->
              <div class="p-4 border-t border-slate-700 grid grid-cols-3 gap-3">
                <button
                  class="py-4 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg font-medium text-lg"
                  on:click={() => discoverAction('learning')}
                >
                  📖 Learn (L)
                </button>
                <button
                  class="py-4 bg-slate-600 hover:bg-slate-500 text-white rounded-lg font-medium text-lg"
                  on:click={() => discoverAction('skip')}
                >
                  Skip (S)
                </button>
                <button
                  class="py-4 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium text-lg"
                  on:click={() => discoverAction('known')}
                >
                  ✓ Know (K)
                </button>
              </div>
            </div>
          </div>

          <!-- Keyboard hint -->
          <div class="mt-4 text-center text-slate-500 text-sm">
            Press L to learn, K if you know it, S or Space to skip
          </div>
        {/if}
      </div>
    </div>

  {:else if mode === 'detail' || mode === 'learning'}
    <!-- Word Detail View -->
    <div class="p-8">
      <div class="max-w-3xl mx-auto">
        <!-- Navigation -->
        <div class="mb-6 flex items-center justify-between">
          <button
            on:click={backToOverview}
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          >
            ← Back
          </button>

          {#if mode === 'learning' && learningWords.length > 0}
            <div class="flex items-center gap-2">
              <button
                on:click={prevLearningWord}
                disabled={currentLearningIndex <= 0}
                class="w-10 h-10 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-full"
              >
                ⏮
              </button>
              <span class="text-slate-400 px-4">
                {currentLearningIndex + 1} / {learningWords.length}
              </span>
              <button
                on:click={nextLearningWord}
                disabled={currentLearningIndex >= learningWords.length - 1}
                class="w-10 h-10 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-full"
              >
                ⏭
              </button>
            </div>
          {/if}

          <div></div>
        </div>

        {#if selectedWord}
          {@const explanation = parseExplanation(selectedWord)}

          <!-- Word Card -->
          <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
            <!-- Header -->
            <div class="p-6 border-b border-slate-700 bg-gradient-to-r from-primary-900/20 to-slate-800">
              <div class="flex items-center justify-between">
                <div>
                  <h1 class="text-4xl font-bold text-white">{selectedWord.word}</h1>
                  <div class="flex items-center gap-3 mt-2">
                    <span class="text-slate-400">Seen {selectedWord.frequency} times</span>
                    <span class="text-xs px-2 py-1 rounded {selectedWord.status === 'known' ? 'bg-green-900/50 text-green-400' : selectedWord.status === 'learning' ? 'bg-yellow-900/50 text-yellow-400' : 'bg-slate-700 text-slate-400'}">
                      {selectedWord.status}
                    </span>
                  </div>
                </div>
                <button
                  on:click={() => playTTS(selectedWord.word)}
                  class="w-14 h-14 rounded-full bg-primary-600 hover:bg-primary-500 flex items-center justify-center text-white text-2xl"
                >
                  🔊
                </button>
              </div>
            </div>

            <!-- Content -->
            <div class="p-6 space-y-6">
              {#if loadingWord}
                <div class="text-center text-slate-400 py-8">Loading...</div>
              {:else if explanation}
                <!-- Translation -->
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
                    <div class="space-y-2">
                      {#each explanation.usagePatterns as pattern}
                        <div class="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
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
                        <span class="px-3 py-1 bg-slate-700 rounded text-sm">
                          <span class="text-white">{related.word}</span>
                          <span class="text-slate-400"> - {related.translation}</span>
                        </span>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Tip -->
                {#if explanation.tip}
                  <div class="p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                    <p class="text-yellow-200">💡 {explanation.tip}</p>
                  </div>
                {/if}
              {:else}
                <div class="text-center py-8 text-slate-400">
                  No explanation available. Generate explanations in Settings.
                </div>
              {/if}

              <!-- Contexts -->
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
                        <p class="text-slate-300 italic">"{context}"</p>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>

            <!-- Actions -->
            <div class="p-6 border-t border-slate-700 bg-slate-900/30">
              <div class="flex gap-3">
                <button
                  on:click={() => markWord('known')}
                  class="flex-1 py-3 bg-green-600 hover:bg-green-500 text-white font-medium rounded-lg {selectedWord.status === 'known' ? 'ring-2 ring-green-400' : ''}"
                >
                  {selectedWord.status === 'known' ? '✓ Known' : 'Mark as Known'}
                </button>
                <button
                  on:click={() => markWord('learning')}
                  class="flex-1 py-3 bg-yellow-600 hover:bg-yellow-500 text-white font-medium rounded-lg {selectedWord.status === 'learning' ? 'ring-2 ring-yellow-400' : ''}"
                >
                  {selectedWord.status === 'learning' ? '✓ Learning' : 'Mark as Learning'}
                </button>
              </div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
