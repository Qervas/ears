<script lang="ts">
  import { onMount } from 'svelte';
  import { learningWords, currentLearningIndex, currentLearningWord, learningProgress } from '../lib/stores';
  import { getLearningSession, updateWordStatus, playTTS, explainWord } from '../lib/api';

  let showAnswer = false;
  let explanation = '';
  let loading = true;
  let sessionComplete = false;

  async function startSession() {
    loading = true;
    sessionComplete = false;
    showAnswer = false;
    explanation = '';
    currentLearningIndex.set(0);

    try {
      const session = await getLearningSession('vocabulary', 10);
      learningWords.set(session.words || []);
      if (session.words?.length === 0) {
        sessionComplete = true;
      }
    } catch (e) {
      console.error('Failed to start session:', e);
    } finally {
      loading = false;
    }
  }

  function reveal() {
    showAnswer = true;
    if ($currentLearningWord) {
      playTTS($currentLearningWord.word).catch(console.error);
    }
  }

  async function respond(known: boolean) {
    if (!$currentLearningWord) return;

    // Update word status
    const newStatus = known ? 'known' : 'learning';
    await updateWordStatus($currentLearningWord.word, newStatus);

    // Move to next word
    showAnswer = false;
    explanation = '';

    if ($currentLearningIndex >= $learningWords.length - 1) {
      sessionComplete = true;
    } else {
      currentLearningIndex.update(i => i + 1);
    }
  }

  async function getHint() {
    if (!$currentLearningWord) return;
    try {
      const result = await explainWord(
        $currentLearningWord.word,
        $currentLearningWord.example || ''
      );
      explanation = result.explanation;
    } catch (e) {
      explanation = 'Failed to get hint. Is LM Studio running?';
    }
  }

  function speak(text: string) {
    playTTS(text).catch(console.error);
  }

  onMount(startSession);
</script>

<div class="p-8 max-w-2xl mx-auto">
  <h2 class="text-3xl font-bold text-white mb-8">Learn</h2>

  {#if loading}
    <div class="text-center text-slate-400 py-16">Loading session...</div>
  {:else if sessionComplete}
    <!-- Session Complete -->
    <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
      <div class="text-5xl mb-4">🎉</div>
      <h3 class="text-2xl font-bold text-white mb-2">Session Complete!</h3>
      <p class="text-slate-400 mb-6">Great job! You've reviewed all the words in this session.</p>
      <button
        class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
        on:click={startSession}
      >
        Start New Session
      </button>
    </div>
  {:else if $currentLearningWord}
    <!-- Progress Bar -->
    <div class="mb-8">
      <div class="flex justify-between text-sm text-slate-400 mb-2">
        <span>Progress</span>
        <span>{$learningProgress.current} / {$learningProgress.total}</span>
      </div>
      <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          class="h-full bg-primary-500 transition-all duration-300"
          style="width: {$learningProgress.percent}%"
        ></div>
      </div>
    </div>

    <!-- Flashcard -->
    <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <!-- Card Front -->
      <div class="p-8 text-center">
        {#if !showAnswer}
          <div class="text-slate-400 text-sm mb-4">What does this word mean?</div>
        {/if}

        <div class="flex items-center justify-center gap-4 mb-6">
          <h3 class="text-4xl font-bold text-white">{$currentLearningWord.word}</h3>
          <button
            class="p-2 rounded-full bg-slate-700 hover:bg-slate-600 text-white"
            on:click={() => speak($currentLearningWord.word)}
          >
            🔊
          </button>
        </div>

        <div class="text-slate-500 text-sm">
          Seen {$currentLearningWord.frequency} times
        </div>
      </div>

      {#if showAnswer}
        <!-- Card Back (Answer) -->
        <div class="border-t border-slate-700 p-6 bg-slate-750">
          {#if $currentLearningWord.example}
            <div class="mb-4">
              <div class="text-slate-400 text-sm mb-2">Example:</div>
              <div class="flex items-start gap-3">
                <button
                  class="text-slate-400 hover:text-white shrink-0 mt-1"
                  on:click={() => speak($currentLearningWord.example)}
                >🔊</button>
                <p class="text-slate-300 italic">{$currentLearningWord.example}</p>
              </div>
            </div>
          {/if}

          {#if explanation}
            <div class="p-4 bg-slate-700 rounded-lg text-slate-300 whitespace-pre-wrap text-sm">
              {explanation}
            </div>
          {:else}
            <button
              class="text-primary-400 hover:text-primary-300 text-sm"
              on:click={getHint}
            >
              💡 Get AI explanation
            </button>
          {/if}
        </div>

        <!-- Response Buttons -->
        <div class="border-t border-slate-700 p-4 flex gap-4">
          <button
            class="flex-1 py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg font-medium"
            on:click={() => respond(false)}
          >
            Still Learning
          </button>
          <button
            class="flex-1 py-3 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium"
            on:click={() => respond(true)}
          >
            I Know This!
          </button>
        </div>
      {:else}
        <!-- Reveal Button -->
        <div class="border-t border-slate-700 p-4">
          <button
            class="w-full py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
            on:click={reveal}
          >
            Show Answer
          </button>
        </div>
      {/if}
    </div>

    <!-- Skip -->
    <div class="text-center mt-4">
      <button
        class="text-slate-500 hover:text-slate-400 text-sm"
        on:click={() => respond(false)}
      >
        Skip this word
      </button>
    </div>
  {:else}
    <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
      <div class="text-5xl mb-4">📚</div>
      <h3 class="text-xl font-bold text-white mb-2">No words to learn</h3>
      <p class="text-slate-400">Record some audio first to build your vocabulary!</p>
    </div>
  {/if}
</div>
