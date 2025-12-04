<script lang="ts">
  import { onMount } from 'svelte';
  import { getRecordings, transcribeFile } from '../lib/api';
  import type { Recording } from '../lib/api';

  let recordings: Recording[] = [];
  let loading = true;
  let transcribing: string | null = null;

  async function loadRecordings() {
    loading = true;
    try {
      const data = await getRecordings();
      recordings = data.recordings;
    } catch (e) {
      console.error('Failed to load recordings:', e);
    } finally {
      loading = false;
    }
  }

  async function transcribe(recording: Recording) {
    transcribing = recording.name;
    try {
      await transcribeFile(recording.path);
      // Reload to update transcript status
      await loadRecordings();
    } catch (e) {
      console.error('Failed to transcribe:', e);
    } finally {
      transcribing = null;
    }
  }

  onMount(loadRecordings);
</script>

<div class="p-8">
  <div class="flex justify-between items-center mb-8">
    <div>
      <h2 class="text-3xl font-bold text-white">Recordings</h2>
      <p class="text-slate-400 mt-1">Audio files ready for transcription</p>
    </div>
    <button
      class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2"
      on:click={loadRecordings}
    >
      🔄 Refresh
    </button>
  </div>

  <!-- Instructions -->
  <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-8">
    <h3 class="text-lg font-semibold text-white mb-3">How to add recordings</h3>
    <div class="text-slate-300 space-y-2">
      <p>1. Open a terminal in the backend folder</p>
      <p>2. Run: <code class="bg-slate-700 px-2 py-1 rounded">python recorder.py</code></p>
      <p>3. Select your audio device and press Enter to start recording</p>
      <p>4. Press Enter again to stop and save the recording</p>
      <p>5. The recording will appear here for transcription</p>
    </div>
  </div>

  {#if loading}
    <div class="text-center text-slate-400 py-16">Loading recordings...</div>
  {:else if recordings.length === 0}
    <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
      <div class="text-5xl mb-4">🎙️</div>
      <h3 class="text-xl font-bold text-white mb-2">No recordings yet</h3>
      <p class="text-slate-400">Use the recorder script to capture some Swedish audio!</p>
    </div>
  {:else}
    <div class="space-y-4">
      {#each recordings as recording}
        <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="text-3xl">🎵</div>
            <div>
              <div class="text-white font-medium">{recording.name}</div>
              <div class="text-slate-400 text-sm">{recording.size_mb} MB</div>
            </div>
          </div>

          <div class="flex items-center gap-3">
            {#if recording.has_transcript}
              <span class="px-3 py-1 bg-green-900 text-green-300 rounded-full text-sm">
                ✓ Transcribed
              </span>
            {:else}
              <button
                class="px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg flex items-center gap-2"
                on:click={() => transcribe(recording)}
                disabled={transcribing !== null}
              >
                {#if transcribing === recording.name}
                  <span class="animate-spin">⏳</span>
                  Transcribing...
                {:else}
                  📝 Transcribe
                {/if}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Tip -->
  <div class="mt-8 p-4 bg-slate-800/50 rounded-lg border border-slate-700 text-sm text-slate-400">
    <strong>Tip:</strong> After transcribing, run <code class="bg-slate-700 px-2 py-1 rounded">python vocabulary.py build</code>
    to update your vocabulary with the new words.
  </div>
</div>
