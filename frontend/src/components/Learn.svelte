<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { learningWords, currentLearningIndex, currentLearningWord, learningProgress, stats } from '../lib/stores';
  import { getLearningSession, updateWordStatus, playTTS, explainWord, getStats, getListeningQuiz, getGrammarQuiz, type ListeningSegment, type GrammarQuestion, type Word } from '../lib/api';

  // Learning mode selection
  type LearningMode = 'select' | 'vocabulary' | 'listening' | 'speaking' | 'grammar';
  let mode: LearningMode = 'select';

  // Vocabulary mode state
  let showAnswer = false;
  let explanation: any = null;
  let loading = true;
  let sessionComplete = false;

  // Listening mode state
  let listeningSegments: ListeningSegment[] = [];
  let currentListeningIndex = 0;
  let listeningShowAnswer = false;
  let listeningAudio: HTMLAudioElement | null = null;
  let isPlaying = false;

  // Grammar mode state
  let grammarQuestions: GrammarQuestion[] = [];
  let currentGrammarIndex = 0;
  let selectedAnswer: number | null = null;
  let grammarShowAnswer = false;

  async function loadStats() {
    try {
      const data = await getStats();
      stats.set(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  }

  async function startSession(selectedMode: LearningMode) {
    mode = selectedMode;

    if (selectedMode === 'vocabulary') {
      loading = true;
      sessionComplete = false;
      showAnswer = false;
      explanation = null;
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
    } else if (selectedMode === 'listening') {
      loading = true;
      sessionComplete = false;
      currentListeningIndex = 0;
      listeningShowAnswer = false;

      try {
        const quiz = await getListeningQuiz(10);
        listeningSegments = quiz.segments;
        if (listeningSegments.length === 0) {
          sessionComplete = true;
        }
      } catch (e) {
        console.error('Failed to start listening session:', e);
      } finally {
        loading = false;
      }
    } else if (selectedMode === 'grammar') {
      loading = true;
      sessionComplete = false;
      currentGrammarIndex = 0;
      selectedAnswer = null;
      grammarShowAnswer = false;

      try {
        const quiz = await getGrammarQuiz(10);
        grammarQuestions = quiz.questions;
        if (grammarQuestions.length === 0) {
          sessionComplete = true;
        }
      } catch (e) {
        console.error('Failed to start grammar session:', e);
      } finally {
        loading = false;
      }
    }
  }

  function backToModeSelect() {
    mode = 'select';
    sessionComplete = false;
  }

  // Parse explanation JSON with new format
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

  interface ExplanationData {
    translation?: string;
    type?: string;
    usagePatterns?: UsagePattern[];
    relatedWords?: RelatedWord[];
    tip?: string;
    note?: string;
  }

  function parseExplanation(word: Word): ExplanationData | null {
    if (!word.explanation_json) return null;
    try {
      return JSON.parse(word.explanation_json);
    } catch {
      return null;
    }
  }

  function reveal() {
    showAnswer = true;
    if ($currentLearningWord) {
      playTTS($currentLearningWord.word).catch(console.error);

      // Parse explanation_json with new format
      if ($currentLearningWord.explanation_json) {
        explanation = parseExplanation($currentLearningWord);
      }
    }
  }

  async function respond(known: boolean) {
    if (!$currentLearningWord) return;

    // Update word status
    const newStatus = known ? 'known' : 'learning';
    await updateWordStatus($currentLearningWord.word, newStatus);

    // Move to next word
    showAnswer = false;
    explanation = null;

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
      // Store raw text if AI generates new explanation
      explanation = { raw: result.explanation };
    } catch (e) {
      explanation = { raw: 'Failed to get hint. Is LM Studio running?' };
    }
  }

  function speak(text: string) {
    playTTS(text).catch(console.error);
  }

  // Listening practice functions
  async function playListeningSegment() {
    const segment = listeningSegments[currentListeningIndex];
    if (!segment) return;

    console.log('Playing segment:', segment);

    // If audio exists and is playing, just pause it
    if (listeningAudio && isPlaying) {
      listeningAudio.pause();
      isPlaying = false;
      return;
    }

    // If audio exists but is paused, replay from segment start
    if (listeningAudio && !isPlaying) {
      try {
        listeningAudio.currentTime = segment.start;
        await listeningAudio.play();
        isPlaying = true;
      } catch (e: any) {
        if (e.name !== 'AbortError') {
          console.error('Failed to replay:', e);
        }
      }
      return;
    }

    // Create new audio element
    const fullAudioUrl = `http://localhost:8000${segment.audio_url}`;
    listeningAudio = new Audio(fullAudioUrl);

    function handleTimeUpdate() {
      if (listeningAudio && listeningAudio.currentTime >= segment.end) {
        listeningAudio.pause();
        isPlaying = false;
      }
    }

    function handlePlay() { isPlaying = true; }
    function handlePause() { isPlaying = false; }
    function handleEnded() { isPlaying = false; }
    function handleError(e: Event) {
      console.error('Audio error:', e);
      isPlaying = false;
    }

    listeningAudio.addEventListener('timeupdate', handleTimeUpdate);
    listeningAudio.addEventListener('play', handlePlay);
    listeningAudio.addEventListener('pause', handlePause);
    listeningAudio.addEventListener('ended', handleEnded);
    listeningAudio.addEventListener('error', handleError);

    try {
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Audio load timeout')), 5000);
        listeningAudio!.addEventListener('canplay', () => {
          clearTimeout(timeout);
          resolve(true);
        }, { once: true });
        listeningAudio!.load();
      });

      listeningAudio.currentTime = segment.start;
      await listeningAudio.play();
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        console.error('Failed to play audio:', e);
      }
      isPlaying = false;
    }
  }

  function revealListening() {
    listeningShowAnswer = true;
  }

  function nextListeningSegment() {
    if (currentListeningIndex >= listeningSegments.length - 1) {
      sessionComplete = true;
      if (listeningAudio) {
        listeningAudio.pause();
        listeningAudio = null;
      }
    } else {
      currentListeningIndex++;
      listeningShowAnswer = false;
      if (listeningAudio) {
        listeningAudio.pause();
        listeningAudio = null;
      }
    }
  }

  // Grammar practice functions
  function selectGrammarAnswer(index: number) {
    if (grammarShowAnswer) return;
    selectedAnswer = index;
  }

  function checkGrammarAnswer() {
    grammarShowAnswer = true;
  }

  function nextGrammarQuestion() {
    if (currentGrammarIndex >= grammarQuestions.length - 1) {
      sessionComplete = true;
    } else {
      currentGrammarIndex++;
      selectedAnswer = null;
      grammarShowAnswer = false;
    }
  }

  onMount(() => {
    loadStats();
  });
</script>

<div class="p-8">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h2 class="text-3xl font-bold text-white">Practice</h2>
      <p class="text-slate-400 mt-1">Train your Swedish skills</p>
    </div>
    <div class="flex items-center gap-3">
      {#if mode !== 'select'}
        <button
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          on:click={backToModeSelect}
        >
          ← Back to Modes
        </button>
      {/if}
    </div>
  </div>

  {#if mode === 'select'}
    <!-- Mode Selection -->
    <div class="max-w-4xl mx-auto">
      <!-- Stats Overview -->
      {#if $stats}
        <div class="grid grid-cols-3 gap-4 mb-8">
          <div class="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div class="text-slate-400 text-sm">Total Words</div>
            <div class="text-2xl font-bold text-white">{$stats.total_words}</div>
          </div>
          <div class="bg-slate-800 rounded-lg p-4 border border-blue-700/50">
            <div class="text-blue-400 text-sm">Learning</div>
            <div class="text-2xl font-bold text-blue-300">{$stats.learning}</div>
          </div>
          <div class="bg-slate-800 rounded-lg p-4 border border-green-700/50">
            <div class="text-green-400 text-sm">Known</div>
            <div class="text-2xl font-bold text-green-300">{$stats.known}</div>
          </div>
        </div>
      {/if}

      <!-- Learning Modes Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Vocabulary Mode -->
        <button
          class="bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-primary-500 transition-all text-left group"
          on:click={() => startSession('vocabulary')}
        >
          <div class="flex items-start justify-between mb-4">
            <div class="text-5xl">📚</div>
            <div class="px-3 py-1 bg-primary-900/30 text-primary-400 rounded-lg text-xs font-medium">
              {$stats?.learning || 0} words
            </div>
          </div>
          <h3 class="text-xl font-bold text-white mb-2 group-hover:text-primary-400 transition-colors">
            Vocabulary Flashcards
          </h3>
          <p class="text-slate-400 text-sm mb-4">
            Review Swedish words with flashcards. See the word, think about the meaning, then reveal the answer.
          </p>
          <div class="flex items-center gap-2 text-slate-500 text-xs">
            <span>~15 min</span>
            <span>•</span>
            <span>10 words per session</span>
          </div>
        </button>

        <!-- Listening Mode -->
        <button
          class="bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-primary-500 transition-all text-left group"
          on:click={() => startSession('listening')}
        >
          <div class="flex items-start justify-between mb-4">
            <div class="text-5xl">🎧</div>
            <div class="px-3 py-1 bg-blue-900/30 text-blue-400 rounded-lg text-xs font-medium">
              From recordings
            </div>
          </div>
          <h3 class="text-xl font-bold text-white mb-2 group-hover:text-primary-400 transition-colors">
            Listening Practice
          </h3>
          <p class="text-slate-400 text-sm mb-4">
            Listen to sentences from your recordings. Test your comprehension and learn in context.
          </p>
          <div class="flex items-center gap-2 text-slate-500 text-xs">
            <span>~10 min</span>
            <span>•</span>
            <span>Real Swedish audio</span>
          </div>
        </button>

        <!-- Speaking Mode -->
        <button
          class="bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-primary-500 transition-all text-left group"
          on:click={() => startSession('speaking')}
        >
          <div class="flex items-start justify-between mb-4">
            <div class="text-5xl">🗣️</div>
            <div class="px-3 py-1 bg-purple-900/30 text-purple-400 rounded-lg text-xs font-medium">
              Pronunciation
            </div>
          </div>
          <h3 class="text-xl font-bold text-white mb-2 group-hover:text-primary-400 transition-colors">
            Speaking Practice
          </h3>
          <p class="text-slate-400 text-sm mb-4">
            Practice pronunciation and speaking. Listen, repeat, and build confidence in speaking Swedish.
          </p>
          <div class="flex items-center gap-2 text-slate-500 text-xs">
            <span>~10 min</span>
            <span>•</span>
            <span>TTS pronunciation guide</span>
          </div>
        </button>

        <!-- Grammar Mode -->
        <button
          class="bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-primary-500 transition-all text-left group"
          on:click={() => startSession('grammar')}
        >
          <div class="flex items-start justify-between mb-4">
            <div class="text-5xl">✍️</div>
            <div class="px-3 py-1 bg-green-900/30 text-green-400 rounded-lg text-xs font-medium">
              Patterns
            </div>
          </div>
          <h3 class="text-xl font-bold text-white mb-2 group-hover:text-primary-400 transition-colors">
            Grammar & Patterns
          </h3>
          <p class="text-slate-400 text-sm mb-4">
            Learn Swedish grammar through patterns. Fill in blanks, practice word order, and master prepositions.
          </p>
          <div class="flex items-center gap-2 text-slate-500 text-xs">
            <span>~10 min</span>
            <span>•</span>
            <span>Contextual learning</span>
          </div>
        </button>
      </div>

      <!-- Quick Tips -->
      <div class="mt-8 p-4 bg-slate-800/50 rounded-lg border border-slate-700 text-sm text-slate-400">
        <strong class="text-white">Tip:</strong> Mix different modes for balanced learning. Vocabulary builds your foundation, while Listening and Speaking help you use it naturally!
      </div>
    </div>

  {:else if mode === 'vocabulary'}
    <!-- Vocabulary Flashcard Mode -->
    <div class="max-w-2xl mx-auto">
      {#if loading}
        <div class="text-center text-slate-400 py-16">Loading session...</div>
      {:else if sessionComplete}
        <!-- Session Complete -->
        <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
          <div class="text-5xl mb-4">🎉</div>
          <h3 class="text-2xl font-bold text-white mb-2">Session Complete!</h3>
          <p class="text-slate-400 mb-6">Great job! You've reviewed all the words in this session.</p>
          <div class="flex gap-4 justify-center">
            <button
              class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
              on:click={() => startSession('vocabulary')}
            >
              Start New Session
            </button>
            <button
              class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
              on:click={backToModeSelect}
            >
              Try Other Modes
            </button>
          </div>
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
            {#if explanation.raw}
              <!-- Raw text explanation (from AI hint) -->
              <div class="p-4 bg-slate-700 rounded-lg text-slate-300 whitespace-pre-wrap text-sm">
                {explanation.raw}
              </div>
            {:else}
              <!-- Structured explanation (new format) -->
              <div class="space-y-3">
                {#if explanation.translation}
                  <div class="p-3 bg-slate-700 rounded-lg">
                    <span class="text-primary-400 font-bold text-lg">{explanation.translation}</span>
                    {#if explanation.type}
                      <span class="text-slate-500 text-sm ml-2">({explanation.type})</span>
                    {/if}
                  </div>
                {/if}

                {#if explanation.usagePatterns?.length}
                  <div class="p-3 bg-slate-700 rounded-lg">
                    <div class="text-slate-400 text-xs mb-2">Usage:</div>
                    {#each explanation.usagePatterns.slice(0, 2) as pattern}
                      <div class="text-sm text-slate-300">
                        • <span class="text-white">{pattern.pattern}</span> → {pattern.meaning}
                      </div>
                    {/each}
                  </div>
                {/if}

                {#if explanation.relatedWords?.length}
                  <div class="p-3 bg-slate-700 rounded-lg">
                    <div class="text-slate-400 text-xs mb-1">Related:</div>
                    <div class="text-sm text-slate-300">
                      {explanation.relatedWords.map((r: RelatedWord) => `${r.word} (${r.translation})`).join(', ')}
                    </div>
                  </div>
                {/if}

                {#if explanation.tip}
                  <div class="p-3 bg-yellow-900/30 rounded-lg text-sm text-yellow-200">
                    💡 {explanation.tip}
                  </div>
                {/if}
              </div>
            {/if}
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
          <p class="text-slate-400 mb-4">Record some audio first to build your vocabulary!</p>
          <button
            class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
            on:click={backToModeSelect}
          >
            Back to Modes
          </button>
        </div>
      {/if}
    </div>

  {:else if mode === 'listening'}
    <!-- Listening Practice Mode -->
    <div class="max-w-2xl mx-auto">
      {#if loading}
        <div class="text-center text-slate-400 py-16">Loading listening quiz...</div>
      {:else if sessionComplete}
        <!-- Session Complete -->
        <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
          <div class="text-5xl mb-4">🎉</div>
          <h3 class="text-2xl font-bold text-white mb-2">Great Listening!</h3>
          <p class="text-slate-400 mb-6">You've completed all the listening exercises.</p>
          <div class="flex gap-4 justify-center">
            <button
              class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
              on:click={() => startSession('listening')}
            >
              Start New Session
            </button>
            <button
              class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
              on:click={backToModeSelect}
            >
              Try Other Modes
            </button>
          </div>
        </div>
      {:else if listeningSegments.length > 0}
        {@const segment = listeningSegments[currentListeningIndex]}

        <!-- Progress Bar -->
        <div class="mb-8">
          <div class="flex justify-between text-sm text-slate-400 mb-2">
            <span>Listening Progress</span>
            <span>{currentListeningIndex + 1} / {listeningSegments.length}</span>
          </div>
          <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-blue-500 transition-all duration-300"
              style="width: {((currentListeningIndex + 1) / listeningSegments.length) * 100}%"
            ></div>
          </div>
        </div>

        <!-- Listening Card -->
        <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <!-- Card Front -->
          <div class="p-8 text-center">
            <div class="text-slate-400 text-sm mb-4">🎧 Listen carefully</div>

            <div class="flex items-center justify-center gap-4 mb-6">
              <button
                class="w-16 h-16 rounded-full bg-blue-600 hover:bg-blue-500 flex items-center justify-center text-white text-2xl transition-all hover:scale-105"
                on:click={playListeningSegment}
              >
                {#if isPlaying}
                  ⏸
                {:else}
                  ▶
                {/if}
              </button>
            </div>

            <div class="text-slate-500 text-sm">
              From: {segment.recording}
            </div>
          </div>

          {#if listeningShowAnswer}
            <!-- Card Back (Answer) -->
            <div class="border-t border-slate-700 p-6 bg-slate-900/30">
              <div class="mb-4">
                <div class="text-slate-400 text-sm mb-2">Swedish:</div>
                <div class="flex items-start gap-3">
                  <button
                    class="text-slate-400 hover:text-white shrink-0 mt-1"
                    on:click={playListeningSegment}
                  >🔊</button>
                  <p class="text-white text-lg font-medium">{segment.text}</p>
                </div>
              </div>

              <div class="p-3 bg-blue-900/20 border border-blue-700/50 rounded-lg text-sm text-blue-200">
                💡 This sentence is from your recording at {Math.floor(segment.start)}s - {Math.floor(segment.end)}s
              </div>
            </div>

            <!-- Next Button -->
            <div class="border-t border-slate-700 p-4">
              <button
                class="w-full py-3 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium"
                on:click={nextListeningSegment}
              >
                {currentListeningIndex >= listeningSegments.length - 1 ? 'Finish' : 'Next →'}
              </button>
            </div>
          {:else}
            <!-- Reveal Button -->
            <div class="border-t border-slate-700 p-4">
              <button
                class="w-full py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
                on:click={revealListening}
              >
                Show What I Heard
              </button>
            </div>
          {/if}
        </div>

        <!-- Instructions -->
        <div class="mt-4 p-4 bg-blue-900/10 rounded-lg border border-blue-700/30 text-sm text-blue-200">
          <strong>How it works:</strong> Listen to the Swedish audio, try to understand it, then reveal to see what was said!
        </div>
      {:else}
        <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
          <div class="text-5xl mb-4">🎧</div>
          <h3 class="text-xl font-bold text-white mb-2">No recordings found</h3>
          <p class="text-slate-400 mb-4">Record and transcribe some Swedish audio first!</p>
          <button
            class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
            on:click={backToModeSelect}
          >
            Back to Modes
          </button>
        </div>
      {/if}
    </div>

  {:else if mode === 'speaking'}
    <!-- Speaking Practice Mode -->
    <div class="max-w-2xl mx-auto">
      <div class="bg-slate-800 rounded-xl p-12 text-center border border-slate-700">
        <div class="text-6xl mb-6">🗣️</div>
        <h3 class="text-2xl font-bold text-white mb-4">Speaking Practice</h3>
        <p class="text-slate-400 mb-6">
          Practice pronunciation and build confidence speaking Swedish.
        </p>
        <div class="inline-block px-4 py-2 bg-purple-900/30 text-purple-400 rounded-lg text-sm mb-6">
          Coming Soon
        </div>
        <p class="text-slate-500 text-sm">
          This mode will help you practice pronunciation with words from your vocabulary
        </p>
      </div>
    </div>

  {:else if mode === 'grammar'}
    <!-- Grammar & Patterns Mode -->
    <div class="max-w-2xl mx-auto">
      {#if loading}
        <div class="text-center text-slate-400 py-16">Loading grammar quiz...</div>
      {:else if sessionComplete}
        <!-- Session Complete -->
        <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
          <div class="text-5xl mb-4">🎉</div>
          <h3 class="text-2xl font-bold text-white mb-2">Great Work!</h3>
          <p class="text-slate-400 mb-6">You've completed all the grammar exercises.</p>
          <div class="flex gap-4 justify-center">
            <button
              class="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
              on:click={() => startSession('grammar')}
            >
              Start New Session
            </button>
            <button
              class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
              on:click={backToModeSelect}
            >
              Try Other Modes
            </button>
          </div>
        </div>
      {:else if grammarQuestions.length > 0}
        {@const question = grammarQuestions[currentGrammarIndex]}
        {@const isCorrect = selectedAnswer === question.correct_index}

        <!-- Progress Bar -->
        <div class="mb-8">
          <div class="flex justify-between text-sm text-slate-400 mb-2">
            <span>Grammar Progress</span>
            <span>{currentGrammarIndex + 1} / {grammarQuestions.length}</span>
          </div>
          <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-green-500 transition-all duration-300"
              style="width: {((currentGrammarIndex + 1) / grammarQuestions.length) * 100}%"
            ></div>
          </div>
        </div>

        <!-- Grammar Question Card -->
        <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <!-- Question -->
          <div class="p-8">
            <div class="text-slate-400 text-sm mb-4">Fill in the blank:</div>

            <!-- Sentence with blank -->
            <div class="text-center mb-8">
              <p class="text-2xl font-bold text-white leading-relaxed">
                {question.sentence}
              </p>
            </div>

            <!-- Options -->
            <div class="grid grid-cols-2 gap-3">
              {#each question.options as option, index}
                {@const selected = selectedAnswer === index}
                {@const correct = index === question.correct_index}
                {@const showResult = grammarShowAnswer}

                <button
                  class="px-4 py-3 rounded-lg font-medium transition-all
                    {!showResult && !selected ? 'bg-slate-700 hover:bg-slate-600 text-white' : ''}
                    {!showResult && selected ? 'bg-primary-600 text-white ring-2 ring-primary-400' : ''}
                    {showResult && correct ? 'bg-green-600 text-white ring-2 ring-green-400' : ''}
                    {showResult && selected && !correct ? 'bg-red-600 text-white ring-2 ring-red-400' : ''}
                    {showResult && !selected && !correct ? 'bg-slate-700 text-slate-500' : ''}"
                  on:click={() => selectGrammarAnswer(index)}
                  disabled={grammarShowAnswer}
                >
                  {option}
                </button>
              {/each}
            </div>
          </div>

          {#if grammarShowAnswer}
            <!-- Answer Explanation -->
            <div class="border-t border-slate-700 p-6 bg-slate-900/30">
              {#if isCorrect}
                <div class="p-4 bg-green-900/30 border border-green-700/50 rounded-lg mb-4">
                  <div class="flex items-center gap-2 text-green-300 mb-2">
                    <span class="text-2xl">✓</span>
                    <span class="font-bold">Correct!</span>
                  </div>
                  <p class="text-green-200 text-sm">{question.explanation}</p>
                </div>
              {:else}
                <div class="p-4 bg-red-900/30 border border-red-700/50 rounded-lg mb-4">
                  <div class="flex items-center gap-2 text-red-300 mb-2">
                    <span class="text-2xl">✗</span>
                    <span class="font-bold">Not quite!</span>
                  </div>
                  <p class="text-red-200 text-sm">
                    The correct answer is <strong>{question.options[question.correct_index]}</strong>. {question.explanation}
                  </p>
                </div>
              {/if}

              <!-- Real Examples from Recordings -->
              <div class="p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
                <h4 class="text-blue-300 font-semibold text-sm mb-2">From your recordings:</h4>
                <div class="space-y-1">
                  {#each question.real_examples.slice(0, 3) as example}
                    <p class="text-blue-200 text-sm">• "{example}"</p>
                  {/each}
                </div>
              </div>
            </div>

            <!-- Next Button -->
            <div class="border-t border-slate-700 p-4">
              <button
                class="w-full py-3 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium"
                on:click={nextGrammarQuestion}
              >
                {currentGrammarIndex >= grammarQuestions.length - 1 ? 'Finish' : 'Next →'}
              </button>
            </div>
          {:else}
            <!-- Check Answer Button -->
            <div class="border-t border-slate-700 p-4">
              <button
                class="w-full py-3 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-medium"
                on:click={checkGrammarAnswer}
                disabled={selectedAnswer === null}
              >
                Check Answer
              </button>
            </div>
          {/if}
        </div>

        <!-- Hint -->
        <div class="mt-4 p-4 bg-green-900/10 rounded-lg border border-green-700/30 text-sm text-green-200">
          <strong>Learning {question.type}:</strong> Pattern extracted from your own Swedish recordings!
        </div>
      {:else}
        <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
          <div class="text-5xl mb-4">✍️</div>
          <h3 class="text-xl font-bold text-white mb-2">No patterns found</h3>
          <p class="text-slate-400 mb-4">Record and transcribe more Swedish audio to build grammar patterns!</p>
          <button
            class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
            on:click={backToModeSelect}
          >
            Back to Modes
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
