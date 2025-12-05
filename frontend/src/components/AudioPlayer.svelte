<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { TranscriptSegment } from '../lib/api';
  import { playTTS } from '../lib/api';

  // Props
  export let audioUrl: string;
  export let segments: TranscriptSegment[] = [];
  export let recordingName: string;

  // Audio state
  let audio: HTMLAudioElement | null = null;
  let isPlaying = false;
  let currentTime = 0;
  let duration = 0;
  let activeSegmentIndex = -1;

  // Initialize audio when URL changes
  $: if (audioUrl && !audio) {
    initAudio();
  }

  function initAudio() {
    if (audio) {
      audio.pause();
      audio = null;
    }

    audio = new Audio(audioUrl);
    audio.preload = 'metadata';

    audio.addEventListener('loadedmetadata', () => {
      duration = audio!.duration;
    });

    audio.addEventListener('timeupdate', () => {
      currentTime = audio!.currentTime;
      updateActiveSegment();
    });

    audio.addEventListener('play', () => { isPlaying = true; });
    audio.addEventListener('pause', () => { isPlaying = false; });
    audio.addEventListener('ended', () => {
      isPlaying = false;
      activeSegmentIndex = -1;
    });

    audio.addEventListener('error', (e) => {
      console.error('Audio error:', e);
    });
  }

  function updateActiveSegment() {
    if (!segments.length) return;

    const idx = segments.findIndex(
      seg => seg.start !== null && seg.end !== null &&
             currentTime >= seg.start && currentTime < seg.end
    );

    if (idx !== activeSegmentIndex) {
      activeSegmentIndex = idx;
      // Auto-scroll to active segment
      if (idx >= 0) {
        const el = document.getElementById(`seg-${recordingName}-${idx}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }
  }

  function togglePlay() {
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
  }

  async function seekTo(time: number) {
    console.log('🎵 Seeking to:', time);

    // Initialize audio if not loaded yet
    if (!audio) {
      console.log('🎵 Initializing audio...');
      initAudio();
      // Wait for metadata to load
      const ready = await new Promise((resolve) => {
        const checkReady = setInterval(() => {
          if (audio && audio.readyState >= 1) {
            clearInterval(checkReady);
            resolve(true);
          }
        }, 50);
        // Timeout after 3 seconds
        setTimeout(() => {
          clearInterval(checkReady);
          resolve(false);
        }, 3000);
      });
      console.log('🎵 Audio ready:', ready);
    }

    if (!audio) {
      console.error('🎵 Audio not available');
      return;
    }

    try {
      console.log('🎵 Setting currentTime to:', time);
      audio.currentTime = time;
      console.log('🎵 Playing...');
      await audio.play();
      console.log('🎵 Playing successfully');
    } catch (err) {
      console.error('🎵 Failed to seek and play:', err);
    }
  }

  async function handleSegmentClick(segment: TranscriptSegment, index: number) {
    console.log('🎯 Segment clicked:', index, segment.text.substring(0, 30) + '...');

    // Immediately highlight the clicked segment
    activeSegmentIndex = index;

    if (segment.start !== null && Number.isFinite(segment.start)) {
      console.log('🎯 Seeking to timestamp:', segment.start);
      await seekTo(segment.start);
    } else {
      console.log('🎯 No timestamp, playing from beginning');
      // No timestamp, just play from beginning
      if (!audio) initAudio();
      audio?.play();
    }
  }

  function handleProgressClick(event: MouseEvent) {
    if (!audio) return;
    const bar = event.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const percent = (event.clientX - rect.left) / rect.width;
    seekTo(percent * duration);
  }

  function formatTime(seconds: number): string {
    if (!Number.isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function speak(text: string) {
    playTTS(text).catch(console.error);
  }

  onDestroy(() => {
    if (audio) {
      audio.pause();
      audio = null;
    }
  });
</script>

<div class="audio-player bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden">
  <!-- Player Controls -->
  <div class="p-4 bg-slate-800/50 border-b border-slate-700">
    <div class="flex items-center gap-4">
      <!-- Play/Pause Button -->
      <button
        class="w-10 h-10 rounded-full bg-primary-600 hover:bg-primary-500 flex items-center justify-center text-white text-xl transition-all hover:scale-105"
        on:click={togglePlay}
      >
        {#if isPlaying}
          ⏸
        {:else}
          ▶
        {/if}
      </button>

      <!-- Progress Bar -->
      <div class="flex-1">
        <div
          class="h-2 bg-slate-700 rounded-full cursor-pointer hover:h-3 transition-all relative group"
          on:click={handleProgressClick}
          role="progressbar"
          tabindex="0"
        >
          <!-- Progress Fill -->
          <div
            class="h-full bg-primary-500 rounded-full transition-all"
            style="width: {duration > 0 ? (currentTime / duration) * 100 : 0}%"
          />
          <!-- Hover Indicator -->
          <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <div class="h-full bg-primary-400/30 rounded-full" />
          </div>
        </div>

        <!-- Time Display -->
        <div class="flex justify-between text-xs text-slate-400 mt-1">
          <span class="font-mono">{formatTime(currentTime)}</span>
          <span class="font-mono">{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Lyrics/Transcript -->
  <div class="max-h-[500px] overflow-y-auto p-4 space-y-1">
    {#each segments as segment, i}
      {@const isActive = activeSegmentIndex === i}
      <div
        id="seg-{recordingName}-{i}"
        class="flex items-start gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all duration-200
          {isActive
            ? 'bg-primary-600/20 scale-[1.01]'
            : 'hover:bg-slate-800/50'}"
        on:click={() => handleSegmentClick(segment, i)}
        on:keydown={(e) => e.key === 'Enter' && handleSegmentClick(segment, i)}
        role="button"
        tabindex="0"
      >
        <!-- Timestamp -->
        <div class="shrink-0 w-12 text-right pt-0.5">
          {#if segment.start !== null}
            <span class="font-mono text-[10px] transition-colors
              {isActive ? 'text-primary-400 font-semibold' : 'text-slate-600'}">
              {formatTime(segment.start)}
            </span>
          {/if}
        </div>

        <!-- Language Badge -->
        <div class="shrink-0 pt-0.5">
          <span class="inline-block w-6 h-4 text-center text-[9px] font-bold rounded leading-4
            {segment.language === 'sv'
              ? 'bg-blue-900/50 text-blue-400'
              : 'bg-purple-900/50 text-purple-400'}">
            {segment.language === 'sv' ? 'SV' : 'EN'}
          </span>
        </div>

        <!-- Segment Text -->
        <p class="flex-1 leading-relaxed transition-all duration-200
          {isActive
            ? 'text-white text-base font-medium'
            : 'text-slate-400 text-sm'}">
          {segment.text}
        </p>

        <!-- TTS Button -->
        <button
          class="shrink-0 w-7 h-7 rounded-full transition-all duration-200 flex items-center justify-center
            {isActive
              ? 'opacity-100 bg-slate-700/50 text-white'
              : 'opacity-0 group-hover:opacity-100 text-slate-500 hover:text-white hover:bg-slate-700/50'}"
          on:click|stopPropagation={() => speak(segment.text)}
          title="Pronounce"
        >
          <span class="text-xs">🔊</span>
        </button>
      </div>
    {/each}

    {#if segments.length === 0}
      <div class="text-center text-slate-500 py-8">
        No transcript segments available
      </div>
    {/if}
  </div>
</div>

<style>
  .audio-player {
    position: relative;
  }
</style>
