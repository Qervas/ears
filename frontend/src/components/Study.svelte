<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getVocabulary, updateWordStatus, playTTS, getStats, getDueWords, getSRSStats, recordReview, type Word, type SRSWord, type SRSStats } from '../lib/api';
  import { selectedStudyWord, stats, wordModal } from '../lib/stores';

  // Study modes
  type StudyMode = 'overview' | 'discover' | 'review';
  let mode: StudyMode = 'overview';

  // All words for knowledge map
  let allWords: Word[] = [];
  let loadingMap = true;

  // Discover mode state
  let discoverWords: Word[] = [];
  let currentDiscoverIndex = 0;
  let loadingDiscover = false;

  // SRS Review state
  let dueWords: SRSWord[] = [];
  let currentReviewIndex = 0;
  let loadingReview = false;
  let srsStats: SRSStats | null = null;
  let showAnswer = false;
  let sessionComplete = false;
  let reviewedThisSession = 0;

  // Matrix dimensions
  const MATRIX_SIZE = 20; // 20x20 = 400 words per matrix

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

  async function loadAllWords() {
    loadingMap = true;
    try {
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

  async function loadSRSStats() {
    try {
      srsStats = await getSRSStats();
    } catch (e) {
      console.error('Failed to load SRS stats:', e);
    }
  }

  async function startDiscover() {
    mode = 'discover';
    loadingDiscover = true;
    currentDiscoverIndex = 0;
    try {
      const result = await getVocabulary(50, 0, 'undiscovered', 'frequency');
      discoverWords = result.words;
    } catch (e) {
      console.error('Failed to load discover words:', e);
    } finally {
      loadingDiscover = false;
    }
  }

  async function startReview() {
    mode = 'review';
    loadingReview = true;
    currentReviewIndex = 0;
    showAnswer = false;
    sessionComplete = false;
    reviewedThisSession = 0;
    try {
      const result = await getDueWords(20);
      dueWords = result.words;
      if (dueWords.length === 0) {
        sessionComplete = true;
      }
    } catch (e) {
      console.error('Failed to load due words:', e);
    } finally {
      loadingReview = false;
    }
  }

  function backToOverview() {
    mode = 'overview';
    showAnswer = false;
    loadAllWords();
    loadSRSStats();
  }

  // Discover mode: mark and go to next
  async function discoverAction(status: 'learning' | 'known' | 'skip') {
    const currentWord = discoverWords[currentDiscoverIndex];
    if (!currentWord) return;

    if (status !== 'skip') {
      await updateWordStatus(currentWord.word, status);
      allWords = allWords.map(w => w.word === currentWord.word ? { ...w, status } : w);
      const statsData = await getStats();
      stats.set(statsData);
    }

    if (currentDiscoverIndex < discoverWords.length - 1) {
      currentDiscoverIndex++;
    } else {
      const result = await getVocabulary(50, 0, 'undiscovered', 'frequency');
      if (result.words.length > 0) {
        discoverWords = result.words;
        currentDiscoverIndex = 0;
      } else {
        backToOverview();
      }
    }
  }

  // SRS Review: rate recall quality
  async function rateReview(quality: number) {
    const currentWord = dueWords[currentReviewIndex];
    if (!currentWord) return;

    try {
      await recordReview(currentWord.word, quality);
      reviewedThisSession++;

      // Update local word in allWords if quality >= 3 (success)
      if (quality >= 3) {
        allWords = allWords.map(w => w.word === currentWord.word ? { ...w, status: 'learning' } : w);
      }

      // Move to next word
      showAnswer = false;
      if (currentReviewIndex < dueWords.length - 1) {
        currentReviewIndex++;
      } else {
        // Try to load more due words
        const result = await getDueWords(20);
        if (result.words.length > 0) {
          dueWords = result.words;
          currentReviewIndex = 0;
        } else {
          sessionComplete = true;
        }
      }
    } catch (e) {
      console.error('Failed to record review:', e);
    }
  }

  // Mark word as known (remove from learning queue)
  async function markAsKnown() {
    const currentWord = dueWords[currentReviewIndex];
    if (!currentWord) return;

    try {
      await updateWordStatus(currentWord.word, 'known');
      allWords = allWords.map(w => w.word === currentWord.word ? { ...w, status: 'known' } : w);
      const statsData = await getStats();
      stats.set(statsData);

      // Move to next word
      showAnswer = false;
      if (currentReviewIndex < dueWords.length - 1) {
        currentReviewIndex++;
      } else {
        const result = await getDueWords(20);
        if (result.words.length > 0) {
          dueWords = result.words;
          currentReviewIndex = 0;
        } else {
          sessionComplete = true;
        }
      }
    } catch (e) {
      console.error('Failed to mark as known:', e);
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

  // Format interval for display
  function formatInterval(days: number): string {
    if (days < 1) return '< 1 day';
    if (days < 7) return `${Math.round(days)} day${days >= 1.5 ? 's' : ''}`;
    if (days < 30) return `${Math.round(days / 7)} week${days >= 10.5 ? 's' : ''}`;
    if (days < 365) return `${Math.round(days / 30)} month${days >= 45 ? 's' : ''}`;
    return `${Math.round(days / 365)} year${days >= 547 ? 's' : ''}`;
  }

  // Handle word passed from Dictionary page
  onMount(() => {
    const unsubscribe = selectedStudyWord.subscribe(async word => {
      if (word) {
        // Open word in modal instead of detail view
        wordModal.set(word);
        selectedStudyWord.set(null);
      }
    });

    loadAllWords();
    loadSRSStats();

    return () => unsubscribe();
  });

  // Keyboard navigation
  function handleKeydown(e: KeyboardEvent) {
    if (mode === 'review') {
      if (e.key === 'Escape') {
        backToOverview();
      } else if (e.key === ' ' && !showAnswer) {
        e.preventDefault();
        showAnswer = true;
      } else if (showAnswer) {
        if (e.key === '1') rateReview(1);
        else if (e.key === '2') rateReview(3);
        else if (e.key === '3') rateReview(4);
        else if (e.key === '4') rateReview(5);
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
              on:click={startReview}
            >
              <div class="text-yellow-400 text-sm">Learning</div>
              <div class="text-2xl font-bold text-yellow-300">{$stats.learning}</div>
              {#if srsStats}
                <div class="text-xs text-yellow-400/70 mt-1">
                  {srsStats.due_now} due now →
                </div>
              {:else}
                <div class="text-xs text-yellow-400/70 mt-1">Click to review →</div>
              {/if}
            </button>
            <div class="bg-slate-800 rounded-xl p-4 border border-green-700/50">
              <div class="text-green-400 text-sm">Known</div>
              <div class="text-2xl font-bold text-green-300">{$stats.known}</div>
            </div>
          </div>
        {/if}

        <!-- SRS Stats -->
        {#if srsStats && srsStats.total_learning > 0}
          <div class="bg-slate-800 rounded-xl border border-slate-700 p-4 mb-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-6">
                <div>
                  <span class="text-yellow-400 font-bold text-lg">{srsStats.due_now}</span>
                  <span class="text-slate-400 text-sm ml-1">due now</span>
                </div>
                <div>
                  <span class="text-slate-300 font-bold text-lg">{srsStats.due_today}</span>
                  <span class="text-slate-400 text-sm ml-1">due today</span>
                </div>
                <div>
                  <span class="text-green-400 font-bold text-lg">{srsStats.reviewed_today}</span>
                  <span class="text-slate-400 text-sm ml-1">reviewed today</span>
                </div>
              </div>
              {#if srsStats.due_now > 0}
                <button
                  class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg font-medium"
                  on:click={startReview}
                >
                  Start Review
                </button>
              {/if}
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
            on:click={startReview}
          >
            <div class="text-2xl mb-2">🧠</div>
            <h3 class="text-white font-semibold">Spaced Repetition Review</h3>
            <p class="text-slate-400 text-sm">
              {#if srsStats && srsStats.due_now > 0}
                {srsStats.due_now} words due for review
              {:else}
                Review words using the forgetting curve
              {/if}
            </p>
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

  {:else if mode === 'review'}
    <!-- SRS Review Mode -->
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
          <h2 class="text-xl font-bold text-white">Spaced Repetition Review</h2>
          <div class="text-slate-400">
            {reviewedThisSession} reviewed
          </div>
        </div>

        {#if loadingReview}
          <div class="flex-1 flex items-center justify-center text-slate-400">
            Loading review session...
          </div>
        {:else if sessionComplete}
          <div class="flex-1 flex flex-col items-center justify-center">
            <div class="text-5xl mb-4">🎉</div>
            <h3 class="text-xl font-bold text-white mb-2">Session Complete!</h3>
            <p class="text-slate-400 mb-2">You reviewed {reviewedThisSession} words.</p>
            <p class="text-slate-500 text-sm mb-6">Come back later when more words are due.</p>
            <button
              class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg"
              on:click={backToOverview}
            >
              Back to Overview
            </button>
          </div>
        {:else if dueWords.length > 0}
          {@const word = dueWords[currentReviewIndex]}
          {@const explanation = parseExplanation(word)}

          <!-- Flashcard -->
          <div class="flex-1 flex flex-col">
            <div class="bg-slate-800 rounded-xl border border-slate-700 flex-1 flex flex-col">
              <!-- Card Front/Back -->
              <div class="p-8 text-center flex-1 flex flex-col justify-center">
                <!-- Word (always visible) -->
                <button
                  class="text-5xl font-bold text-white mb-4 hover:text-primary-400 transition-colors cursor-pointer"
                  on:click={() => wordModal.set(word)}
                >
                  {word.word}
                </button>
                <button
                  class="mx-auto p-3 rounded-full bg-slate-700 hover:bg-slate-600 text-white text-xl mb-4"
                  on:click={() => playTTS(word.word)}
                >
                  🔊
                </button>

                {#if word.srs_review_count && word.srs_review_count > 0}
                  <div class="text-slate-500 text-xs mb-4">
                    Reviewed {word.srs_review_count} time{word.srs_review_count > 1 ? 's' : ''}
                    {#if word.srs_interval}
                      · Next: {formatInterval(word.srs_interval)}
                    {/if}
                  </div>
                {:else}
                  <div class="text-slate-500 text-xs mb-4">First review</div>
                {/if}

                {#if !showAnswer}
                  <!-- Show Answer Button -->
                  <button
                    class="mt-4 px-8 py-4 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-lg font-medium"
                    on:click={() => showAnswer = true}
                  >
                    Show Answer (Space)
                  </button>
                {:else}
                  <!-- Answer Revealed -->
                  {#if explanation}
                    <div class="mt-4 space-y-3">
                      <div class="text-2xl text-primary-400">{explanation.translation}</div>
                      {#if explanation.type}
                        <div class="text-slate-500">({explanation.type})</div>
                      {/if}
                      {#if explanation.tip}
                        <div class="text-yellow-300/80 text-sm">💡 {explanation.tip}</div>
                      {/if}
                    </div>
                  {:else}
                    <div class="text-slate-500 mt-4">No explanation available</div>
                  {/if}
                  <button
                    class="mt-4 text-slate-500 hover:text-slate-400 text-sm underline"
                    on:click={() => wordModal.set(word)}
                  >
                    View full details
                  </button>
                {/if}
              </div>

              <!-- Rating Buttons (only when answer shown) -->
              {#if showAnswer}
                <div class="p-4 border-t border-slate-700">
                  <div class="text-center text-slate-400 text-sm mb-3">How well did you remember?</div>
                  <div class="grid grid-cols-4 gap-2">
                    <button
                      class="py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg font-medium flex flex-col items-center"
                      on:click={() => rateReview(1)}
                    >
                      <span>Again</span>
                      <span class="text-xs opacity-70">10 min</span>
                    </button>
                    <button
                      class="py-3 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-medium flex flex-col items-center"
                      on:click={() => rateReview(3)}
                    >
                      <span>Hard</span>
                      <span class="text-xs opacity-70">1 day</span>
                    </button>
                    <button
                      class="py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium flex flex-col items-center"
                      on:click={() => rateReview(4)}
                    >
                      <span>Good</span>
                      <span class="text-xs opacity-70">{word.srs_review_count ? formatInterval((word.srs_interval || 1) * (word.srs_ease || 2.5)) : '6 days'}</span>
                    </button>
                    <button
                      class="py-3 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium flex flex-col items-center"
                      on:click={() => rateReview(5)}
                    >
                      <span>Easy</span>
                      <span class="text-xs opacity-70">{word.srs_review_count ? formatInterval((word.srs_interval || 1) * (word.srs_ease || 2.5) * 1.3) : '10 days'}</span>
                    </button>
                  </div>
                  <div class="mt-3 text-center">
                    <button
                      class="text-green-400 hover:text-green-300 text-sm"
                      on:click={markAsKnown}
                    >
                      ✓ I know this word - remove from learning
                    </button>
                  </div>
                </div>
              {/if}
            </div>
          </div>

          <!-- Keyboard hint -->
          <div class="mt-4 text-center text-slate-500 text-sm">
            {#if !showAnswer}
              Press Space to reveal answer
            {:else}
              Press 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
