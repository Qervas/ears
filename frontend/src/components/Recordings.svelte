<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getRecordings, transcribeFile, getAudioDevices, getRecordingStatus, startRecording, stopRecording, rebuildVocabulary, getRecordingTranscript, getRecordingAudioUrl } from '../lib/api';
  import type { Recording, AudioDevice, RecordingStatus, RecordingTranscript } from '../lib/api';
  import AudioPlayer from './AudioPlayer.svelte';

  let recordings: Recording[] = [];
  let devices: AudioDevice[] = [];
  let loading = true;
  let transcribing: string | null = null;
  let rebuildingVocab = false;

  // Recording state
  let recordingStatus: RecordingStatus = { recording: false, device_id: null, start_time: null };
  let selectedDevice: number | null = null;
  let recordingTime = 0;
  let recordingTimer: number | null = null;
  let lastRecordedFile: string | null = null;

  // Transcript viewing
  let expandedRecording: string | null = null;
  let transcriptData: Record<string, RecordingTranscript> = {};
  let loadingTranscript: string | null = null;

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

  async function loadDevices() {
    try {
      const data = await getAudioDevices();
      devices = data.devices;
      const pcSpeaker = devices.find(d => d.id === 17);
      const stereoMix = devices.find(d => d.id === 14);
      selectedDevice = pcSpeaker?.id ?? stereoMix?.id ?? devices[0]?.id ?? null;
    } catch (e) {
      console.error('Failed to load devices:', e);
    }
  }

  async function checkRecordingStatus() {
    try {
      recordingStatus = await getRecordingStatus();
      if (recordingStatus.recording && recordingStatus.start_time) {
        const start = new Date(recordingStatus.start_time).getTime();
        recordingTime = Math.floor((Date.now() - start) / 1000);
        startTimer();
      }
    } catch (e) {
      console.error('Failed to get recording status:', e);
    }
  }

  function startTimer() {
    if (recordingTimer) return;
    recordingTimer = window.setInterval(() => {
      recordingTime++;
    }, 1000);
  }

  function stopTimer() {
    if (recordingTimer) {
      clearInterval(recordingTimer);
      recordingTimer = null;
    }
    recordingTime = 0;
  }

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  async function handleStartRecording() {
    if (selectedDevice === null) return;
    try {
      await startRecording(selectedDevice);
      recordingStatus = { recording: true, device_id: selectedDevice, start_time: new Date().toISOString() };
      recordingTime = 0;
      lastRecordedFile = null;
      startTimer();
    } catch (e) {
      console.error('Failed to start recording:', e);
      alert('Failed to start recording. Check if the device is available.');
    }
  }

  async function handleStopRecording() {
    try {
      stopTimer();
      const result = await stopRecording();
      recordingStatus = { recording: false, device_id: null, start_time: null };
      lastRecordedFile = result.filepath;
      await loadRecordings();
    } catch (e) {
      console.error('Failed to stop recording:', e);
      recordingStatus = { recording: false, device_id: null, start_time: null };
    }
  }

  async function transcribe(recording: Recording) {
    transcribing = recording.name;
    try {
      await transcribeFile(recording.path);
      await loadRecordings();
      // Auto-expand after transcription
      await toggleTranscript(recording.name);
    } catch (e) {
      console.error('Failed to transcribe:', e);
    } finally {
      transcribing = null;
    }
  }

  async function toggleTranscript(filename: string) {
    if (expandedRecording === filename) {
      expandedRecording = null;
      return;
    }

    expandedRecording = filename;

    // Load transcript if not cached
    if (!transcriptData[filename]) {
      loadingTranscript = filename;
      try {
        transcriptData[filename] = await getRecordingTranscript(filename);
      } catch (e) {
        console.error('Failed to load transcript:', e);
      } finally {
        loadingTranscript = null;
      }
    }
  }

  async function handleRebuildVocabulary() {
    rebuildingVocab = true;
    try {
      await rebuildVocabulary();
      alert('Vocabulary rebuilt successfully!');
    } catch (e) {
      console.error('Failed to rebuild vocabulary:', e);
      alert('Failed to rebuild vocabulary.');
    } finally {
      rebuildingVocab = false;
    }
  }

  onMount(async () => {
    await Promise.all([loadDevices(), loadRecordings(), checkRecordingStatus()]);
  });

  onDestroy(() => {
    stopTimer();
  });
</script>

<div class="p-8">
  <div class="flex justify-between items-center mb-8">
    <div>
      <h2 class="text-3xl font-bold text-white">Recordings</h2>
      <p class="text-slate-400 mt-1">Record and transcribe Swedish audio</p>
    </div>
    <div class="flex gap-2">
      <button
        class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
        on:click={handleRebuildVocabulary}
        disabled={rebuildingVocab}
      >
        {rebuildingVocab ? '⏳' : '📚'} Rebuild Vocabulary
      </button>
      <button
        class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2"
        on:click={loadRecordings}
      >
        🔄 Refresh
      </button>
    </div>
  </div>

  <!-- Recording Control Panel -->
  <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-8">
    <h3 class="text-lg font-semibold text-white mb-4">Record Audio</h3>

    <div class="flex items-center gap-4">
      <div class="flex-1">
        <label class="block text-sm text-slate-400 mb-2">Audio Device</label>
        <select
          bind:value={selectedDevice}
          disabled={recordingStatus.recording}
          class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white disabled:opacity-50"
        >
          {#each devices as device}
            <option value={device.id}>
              [{device.id}] {device.name}
            </option>
          {/each}
        </select>
      </div>

      <div class="flex items-center gap-4">
        {#if recordingStatus.recording}
          <div class="flex items-center gap-3 px-4 py-2 bg-red-900/50 border border-red-700 rounded-lg">
            <span class="w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
            <span class="text-red-300 font-mono text-lg">{formatTime(recordingTime)}</span>
          </div>

          <button
            class="px-6 py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg font-semibold flex items-center gap-2"
            on:click={handleStopRecording}
          >
            ⏹️ Stop
          </button>
        {:else}
          <button
            class="px-6 py-3 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-semibold flex items-center gap-2"
            on:click={handleStartRecording}
            disabled={selectedDevice === null}
          >
            🎙️ Start Recording
          </button>
        {/if}
      </div>
    </div>

    {#if lastRecordedFile}
      <div class="mt-4 p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
        ✓ Saved: {lastRecordedFile}
      </div>
    {/if}

    <p class="mt-4 text-slate-500 text-sm">
      Tip: Use "Stereo Mix" or "PC Speaker" device to capture system audio (videos, radio, etc.)
    </p>
  </div>

  <!-- Recordings List -->
  {#if loading}
    <div class="text-center text-slate-400 py-16">Loading recordings...</div>
  {:else if recordings.length === 0}
    <div class="bg-slate-800 rounded-xl p-8 text-center border border-slate-700">
      <div class="text-5xl mb-4">🎙️</div>
      <h3 class="text-xl font-bold text-white mb-2">No recordings yet</h3>
      <p class="text-slate-400">Click "Start Recording" above to capture some Swedish audio!</p>
    </div>
  {:else}
    <div class="space-y-4">
      {#each recordings as recording}
        <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <!-- Recording Header -->
          <div class="p-6 flex items-center justify-between">
            <div class="flex items-center gap-4">
              <div class="w-12 h-12 rounded-full bg-slate-700 flex items-center justify-center text-2xl">
                🎵
              </div>
              <div>
                <div class="text-white font-medium">{recording.name}</div>
                <div class="text-slate-400 text-sm">{recording.size_mb} MB</div>
              </div>
            </div>

            <div class="flex items-center gap-3">
              {#if recording.has_transcript}
                <button
                  class="px-4 py-2 bg-green-900/50 hover:bg-green-900 text-green-300 rounded-lg flex items-center gap-2 transition-colors"
                  on:click={() => toggleTranscript(recording.name)}
                >
                  {expandedRecording === recording.name ? '▼' : '▶'} {expandedRecording === recording.name ? 'Hide' : 'Show'} Lyrics
                </button>
                <button
                  class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
                  on:click={() => transcribe(recording)}
                  disabled={transcribing !== null}
                  title="Re-transcribe to regenerate with timestamps"
                >
                  {#if transcribing === recording.name}
                    <span class="animate-spin">⏳</span>
                    Re-transcribing...
                  {:else}
                    🔄 Re-transcribe
                  {/if}
                </button>
              {:else}
                <button
                  class="px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg flex items-center gap-2 transition-colors"
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

          <!-- Audio Player with Lyrics (Expanded) -->
          {#if expandedRecording === recording.name}
            <div class="border-t border-slate-700 p-6 bg-slate-900/30">
              {#if loadingTranscript === recording.name}
                <div class="text-center text-slate-400 py-8">Loading transcript...</div>
              {:else if transcriptData[recording.name]}
                {@const data = transcriptData[recording.name]}

                <!-- Stats -->
                <div class="flex gap-4 mb-4">
                  <div class="px-3 py-1 bg-slate-700 rounded-lg text-sm">
                    <span class="text-slate-400">Total:</span>
                    <span class="text-white ml-1">{data.stats.total} segments</span>
                  </div>
                  <div class="px-3 py-1 bg-blue-900/50 rounded-lg text-sm">
                    <span class="text-blue-400">Swedish:</span>
                    <span class="text-blue-300 ml-1">{data.stats.swedish}</span>
                  </div>
                  <div class="px-3 py-1 bg-purple-900/50 rounded-lg text-sm">
                    <span class="text-purple-400">English:</span>
                    <span class="text-purple-300 ml-1">{data.stats.english}</span>
                  </div>
                </div>

                <!-- Spotify-style Audio Player -->
                <AudioPlayer
                  audioUrl={getRecordingAudioUrl(recording.name)}
                  segments={data.segments}
                  recordingName={recording.name}
                />
              {:else}
                <div class="text-center text-slate-500 py-8">Failed to load transcript</div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Workflow Info -->
  <div class="mt-8 p-4 bg-slate-800/50 rounded-lg border border-slate-700 text-sm text-slate-400">
    <strong>Workflow:</strong> Record → Transcribe → View Results → Rebuild Vocabulary → Learn new words!
  </div>
</div>
