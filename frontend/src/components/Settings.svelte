<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { startBulkGeneration, getBulkGenerationStatus, getLanguages, setActiveLanguage as setActiveLang, addLanguage, updateLanguage, deleteLanguage } from '../lib/api';
  import type { BulkGenerationStatus, Language, LanguageInput } from '../lib/api';
  import { activeLanguage } from '../lib/stores';

  type AIProvider = 'lm-studio' | 'copilot-api' | 'openai';

  let aiProvider: AIProvider = 'lm-studio';
  let lmStudioUrl = 'http://localhost:1234/v1';
  let copilotApiUrl = 'http://localhost:4141';
  let copilotModel = 'gpt-4o-mini';
  let openaiApiKey = '';
  let saving = false;
  let saveMessage = '';
  let backups: Array<{ filename: string; size_mb: number; created: string }> = [];
  let creatingBackup = false;

  // Language state
  let languages: Record<string, Language> = {};
  let selectedLanguage = 'de';
  let changingLanguage = false;

  // Language editor modal
  let showLanguageModal = false;
  let editingLanguageCode: string | null = null;
  let languageForm: LanguageInput = {
    code: '',
    name: '',
    native_name: '',
    flag: '',
    tts_voice: '',
    whisper_code: ''
  };
  let savingLanguage = false;

  // Bulk generation state
  let generatingBulk = false;
  let bulkStatus: BulkGenerationStatus = { running: false, current: 0, total: 0, completed: 0, failed: 0, failed_words: [] };
  let statusPollInterval: number | null = null;
  let currentGenerationMode: 'missing' | 'all' | null = null;

  // Danger zone confirmation
  let dangerConfirmText = '';
  const DANGER_CONFIRM_PHRASE = 'REGENERATE';

  // Common TTS voices for quick selection
  const commonVoices: Record<string, string[]> = {
    'de': ['de-DE-KatjaNeural', 'de-DE-ConradNeural', 'de-AT-IngridNeural'],
    'fr': ['fr-FR-DeniseNeural', 'fr-FR-HenriNeural', 'fr-CA-SylvieNeural'],
    'es': ['es-ES-ElviraNeural', 'es-ES-AlvaroNeural', 'es-MX-DaliaNeural'],
    'en': ['en-GB-SoniaNeural', 'en-US-JennyNeural', 'en-AU-NatashaNeural'],
    'ja': ['ja-JP-NanamiNeural', 'ja-JP-KeitaNeural'],
    'ko': ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural'],
    'zh': ['zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural'],
    'it': ['it-IT-ElsaNeural', 'it-IT-DiegoNeural'],
    'pt': ['pt-BR-FranciscaNeural', 'pt-PT-RaquelNeural'],
    'ru': ['ru-RU-SvetlanaNeural', 'ru-RU-DmitryNeural'],
    'sv': ['sv-SE-SofieNeural', 'sv-SE-MattiasNeural'],
    'nl': ['nl-NL-ColetteNeural', 'nl-NL-MaartenNeural'],
  };

  // Common flags
  const commonFlags = ['🇩🇪', '🇫🇷', '🇪🇸', '🇬🇧', '🇺🇸', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇹', '🇧🇷', '🇷🇺', '🇸🇪', '🇳🇱', '🇵🇱', '🇹🇷', '🇸🇦', '🇮🇳', '🇹🇭', '🇻🇳', '🇮🇩'];

  onMount(async () => {
    // Load settings from backend
    try {
      const response = await fetch('http://localhost:8000/api/settings');
      const data = await response.json();

      aiProvider = data.ai_provider || 'lm-studio';
      lmStudioUrl = data.lm_studio_url || 'http://localhost:1234/v1';
      copilotApiUrl = data.copilot_api_url || 'http://localhost:4141';
      copilotModel = data.copilot_model || 'gpt-4o-mini';
      openaiApiKey = data.openai_api_key || '';
    } catch (e) {
      console.error('Failed to load settings:', e);
    }

    // Load languages
    await reloadLanguages();

    // Load backups list
    await loadBackups();

    // Check if bulk generation is already running
    try {
      const status = await getBulkGenerationStatus();
      if (status.running) {
        generatingBulk = true;
        bulkStatus = status;
        statusPollInterval = window.setInterval(pollBulkStatus, 1000);
      }
    } catch (e) {
      console.error('Failed to check bulk generation status:', e);
    }
  });

  async function reloadLanguages() {
    try {
      const langData = await getLanguages();
      languages = langData.languages;
      selectedLanguage = langData.active;
      activeLanguage.set({
        code: langData.active,
        name: languages[langData.active]?.name || langData.active,
        native_name: languages[langData.active]?.native_name || langData.active,
        flag: languages[langData.active]?.flag || '',
        tts_voice: languages[langData.active]?.tts_voice || ''
      });
    } catch (e) {
      console.error('Failed to load languages:', e);
    }
  }

  onDestroy(() => {
    if (statusPollInterval) {
      clearInterval(statusPollInterval);
    }
  });

  async function pollBulkStatus() {
    try {
      bulkStatus = await getBulkGenerationStatus();

      if (!bulkStatus.running && generatingBulk) {
        const mode = currentGenerationMode;
        generatingBulk = false;
        currentGenerationMode = null;

        if (statusPollInterval) {
          clearInterval(statusPollInterval);
          statusPollInterval = null;
        }

        const modeText = mode === 'all' ? 'Regenerated ALL' : 'Generated';
        let message = `Done! ${modeText} ${bulkStatus.completed} explanations`;
        if (bulkStatus.failed > 0) {
          message += ` (${bulkStatus.failed} failed)`;
        }
        alert(message);
      }
    } catch (e) {
      console.error('Failed to poll bulk status:', e);
    }
  }

  async function generateMissingExplanations() {
    try {
      const status = await getBulkGenerationStatus();
      if (status.running) {
        alert(`Generation already in progress! ${status.current}/${status.total}`);
        if (!statusPollInterval) {
          generatingBulk = true;
          statusPollInterval = window.setInterval(pollBulkStatus, 1000);
        }
        return;
      }

      if (!confirm(`Generate AI explanations for words that don't have them yet?\n\nThis runs in the background.`)) {
        return;
      }

      const result = await startBulkGeneration();

      if (result.count === 0) {
        alert('All words already have explanations!');
        return;
      }

      generatingBulk = true;
      currentGenerationMode = 'missing';
      statusPollInterval = window.setInterval(pollBulkStatus, 1000);
    } catch (e) {
      console.error('Failed to start bulk generation:', e);
      alert('Failed to start. Is the AI provider configured?');
    }
  }

  async function regenerateAllExplanations() {
    if (dangerConfirmText !== DANGER_CONFIRM_PHRASE) {
      alert(`Please type "${DANGER_CONFIRM_PHRASE}" to confirm this action.`);
      return;
    }

    try {
      const status = await getBulkGenerationStatus();
      if (status.running) {
        alert(`Generation already in progress! ${status.current}/${status.total}`);
        if (!statusPollInterval) {
          generatingBulk = true;
          statusPollInterval = window.setInterval(pollBulkStatus, 1000);
        }
        return;
      }

      const response = await fetch('http://localhost:8000/api/vocabulary/regenerate-all-explanations', {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed');

      generatingBulk = true;
      currentGenerationMode = 'all';
      dangerConfirmText = '';
      statusPollInterval = window.setInterval(pollBulkStatus, 1000);
    } catch (e) {
      console.error('Failed to start regeneration:', e);
      alert('Failed to start. Is the AI provider configured?');
    }
  }

  async function loadBackups() {
    try {
      const response = await fetch('http://localhost:8000/api/database/backups');
      const data = await response.json();
      backups = data.backups || [];
    } catch (e) {
      console.error('Failed to load backups:', e);
    }
  }

  async function saveSettings() {
    saving = true;
    saveMessage = '';

    try {
      const response = await fetch('http://localhost:8000/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_provider: aiProvider,
          lm_studio_url: lmStudioUrl,
          copilot_api_url: copilotApiUrl,
          copilot_model: copilotModel,
          openai_api_key: openaiApiKey,
        }),
      });

      if (response.ok) {
        saveMessage = 'Settings saved successfully!';
        setTimeout(() => saveMessage = '', 3000);
      } else {
        saveMessage = 'Failed to save settings';
      }
    } catch (e) {
      console.error('Failed to save settings:', e);
      saveMessage = 'Error saving settings';
    } finally {
      saving = false;
    }
  }

  async function testConnection() {
    try {
      const response = await fetch('http://localhost:8000/api/test-ai-connection');
      const data = await response.json();

      if (data.success) {
        alert(`Connection successful!\n\nProvider: ${data.provider}\nModel: ${data.model || 'N/A'}\nResponse: ${data.response}`);
      } else {
        console.error('Connection error details:', data);
        alert(`Connection failed\n\nError: ${data.error}\n\nCheck the browser console for more details.`);
      }
    } catch (e) {
      console.error('Connection test error:', e);
      alert(`Connection test failed\n\nError: ${e}\n\nMake sure the backend server is running.`);
    }
  }

  async function createBackup() {
    creatingBackup = true;
    try {
      const response = await fetch('http://localhost:8000/api/database/backup', {
        method: 'POST',
      });
      const data = await response.json();

      if (response.ok) {
        alert(`Backup created successfully!\n\nFile: ${data.path}`);
        await loadBackups();
      } else {
        alert('Failed to create backup');
      }
    } catch (e) {
      console.error('Backup creation error:', e);
      alert(`Failed to create backup: ${e}`);
    } finally {
      creatingBackup = false;
    }
  }

  function downloadBackup(filename: string) {
    window.open(`http://localhost:8000/api/database/download-backup/${filename}`, '_blank');
  }

  async function deleteBackup(filename: string) {
    if (!confirm(`Are you sure you want to delete backup "${filename}"?`)) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/database/backup/${filename}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await loadBackups();
      } else {
        alert('Failed to delete backup');
      }
    } catch (e) {
      console.error('Delete backup error:', e);
      alert(`Failed to delete backup: ${e}`);
    }
  }

  async function changeLanguage(code: string) {
    if (code === selectedLanguage) return;

    changingLanguage = true;
    try {
      await setActiveLang(code);
      selectedLanguage = code;
      const lang = languages[code];
      activeLanguage.set({
        code,
        name: lang?.name || code,
        native_name: lang?.native_name || code,
        flag: lang?.flag || '',
        tts_voice: lang?.tts_voice || ''
      });
    } catch (e) {
      console.error('Failed to change language:', e);
      alert('Failed to change language');
    } finally {
      changingLanguage = false;
    }
  }

  // Language modal functions
  function openAddLanguageModal() {
    editingLanguageCode = null;
    languageForm = {
      code: '',
      name: '',
      native_name: '',
      flag: '',
      tts_voice: '',
      whisper_code: ''
    };
    showLanguageModal = true;
  }

  function openEditLanguageModal(code: string) {
    const lang = languages[code];
    if (!lang) return;

    editingLanguageCode = code;
    languageForm = {
      code,
      name: lang.name,
      native_name: lang.native_name,
      flag: lang.flag,
      tts_voice: lang.tts_voice,
      whisper_code: lang.whisper_code || code
    };
    showLanguageModal = true;
  }

  function closeLanguageModal() {
    showLanguageModal = false;
    editingLanguageCode = null;
  }

  async function saveLanguage() {
    if (!languageForm.code || !languageForm.name || !languageForm.flag || !languageForm.tts_voice) {
      alert('Please fill in all required fields');
      return;
    }

    savingLanguage = true;
    try {
      if (editingLanguageCode) {
        await updateLanguage(editingLanguageCode, languageForm);
      } else {
        await addLanguage(languageForm);
      }
      await reloadLanguages();
      closeLanguageModal();
    } catch (e: any) {
      console.error('Failed to save language:', e);
      alert(`Failed to save language: ${e.message || e}`);
    } finally {
      savingLanguage = false;
    }
  }

  async function removeLanguage(code: string) {
    const lang = languages[code];
    if (!confirm(`Are you sure you want to delete "${lang?.name || code}"?\n\nThis will NOT delete your vocabulary data for this language.`)) {
      return;
    }

    try {
      await deleteLanguage(code);
      await reloadLanguages();
    } catch (e: any) {
      console.error('Failed to delete language:', e);
      alert(`Failed to delete: ${e.message || e}`);
    }
  }

  function getSuggestedVoices(code: string): string[] {
    return commonVoices[code] || [];
  }
</script>

<div class="h-full overflow-auto p-8 bg-slate-900">
  <div class="max-w-3xl mx-auto">
    <h1 class="text-3xl font-bold text-white mb-8">Settings</h1>

    <!-- Language Selection -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-semibold text-white">🌍 Languages</h2>
        <button
          on:click={openAddLanguageModal}
          class="px-3 py-1.5 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          + Add Language
        </button>
      </div>

      <p class="text-sm text-slate-400 mb-4">
        Select a language to study, or add a new one. Each language has its own vocabulary and progress.
      </p>

      <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {#each Object.entries(languages) as [code, lang]}
          <div class="relative group">
            <button
              on:click={() => changeLanguage(code)}
              disabled={changingLanguage}
              class="w-full p-4 rounded-xl border-2 transition-all text-left {selectedLanguage === code
                ? 'border-primary-500 bg-primary-900/30'
                : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'}"
            >
              <div class="text-2xl mb-1">{lang.flag}</div>
              <div class="text-white font-medium">{lang.name}</div>
              <div class="text-slate-400 text-sm">{lang.native_name}</div>
            </button>
            <!-- Edit/Delete buttons on hover -->
            <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
              <button
                on:click|stopPropagation={() => openEditLanguageModal(code)}
                class="p-1.5 bg-slate-600 hover:bg-slate-500 rounded text-xs"
                title="Edit"
              >
                ✏️
              </button>
              {#if Object.keys(languages).length > 1 && code !== selectedLanguage}
                <button
                  on:click|stopPropagation={() => removeLanguage(code)}
                  class="p-1.5 bg-red-900/50 hover:bg-red-800 rounded text-xs"
                  title="Delete"
                >
                  🗑️
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>

      {#if changingLanguage}
        <div class="mt-4 text-center text-slate-400">
          Switching language...
        </div>
      {/if}
    </div>

    <!-- AI Provider Selection -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <h2 class="text-xl font-semibold text-white mb-4">AI Provider</h2>

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">
            Select AI Provider
          </label>
          <select
            bind:value={aiProvider}
            class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-primary-500"
          >
            <option value="lm-studio">LM Studio (Local)</option>
            <option value="copilot-api">GitHub Copilot API</option>
            <option value="openai">OpenAI API</option>
          </select>
        </div>

        {#if aiProvider === 'lm-studio'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700">
            <h3 class="text-sm font-semibold text-white mb-3">LM Studio Configuration</h3>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">API Base URL</label>
              <input
                type="text"
                bind:value={lmStudioUrl}
                placeholder="http://localhost:1234/v1"
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
        {/if}

        {#if aiProvider === 'copilot-api'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700 space-y-4">
            <h3 class="text-sm font-semibold text-white mb-3">GitHub Copilot API Configuration</h3>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">API Base URL</label>
              <input
                type="text"
                bind:value={copilotApiUrl}
                placeholder="http://localhost:4141"
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">Model</label>
              <select
                bind:value={copilotModel}
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-primary-500"
              >
                <optgroup label="Free Models">
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="grok-code-fast-1">grok-code-fast-1</option>
                </optgroup>
                <optgroup label="Premium">
                  <option value="claude-sonnet-4.5">Claude Sonnet 4.5</option>
                  <option value="gpt-4o">GPT-4o</option>
                </optgroup>
              </select>
            </div>
          </div>
        {/if}

        {#if aiProvider === 'openai'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700">
            <h3 class="text-sm font-semibold text-white mb-3">OpenAI Configuration</h3>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">API Key</label>
              <input
                type="password"
                bind:value={openaiApiKey}
                placeholder="sk-..."
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>
        {/if}

        <div class="flex gap-3 pt-4">
          <button
            on:click={saveSettings}
            disabled={saving}
            class="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-slate-700 text-white font-medium rounded-lg transition-colors"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
          <button
            on:click={testConnection}
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors"
          >
            Test Connection
          </button>
        </div>

        {#if saveMessage}
          <div class="p-3 bg-green-900/30 border border-green-700/50 rounded-lg">
            <p class="text-sm text-green-400">{saveMessage}</p>
          </div>
        {/if}
      </div>
    </div>

    <!-- AI Explanations Section -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <h2 class="text-xl font-semibold text-white mb-4">🤖 AI Explanations</h2>
      <p class="text-sm text-slate-400 mb-4">
        Generate AI-powered explanations for your vocabulary words.
      </p>
      <button
        on:click={generateMissingExplanations}
        disabled={generatingBulk}
        class="w-full px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 text-white font-medium rounded-lg transition-colors"
      >
        {#if generatingBulk && currentGenerationMode === 'missing'}
          Generating... ({bulkStatus.current}/{bulkStatus.total})
        {:else}
          Generate Missing Explanations
        {/if}
      </button>

      {#if generatingBulk}
        <div class="mt-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700">
          <div class="flex justify-between text-sm text-slate-400 mb-2">
            <span>{currentGenerationMode === 'all' ? 'Regenerating ALL' : 'Generating missing'}</span>
            <span>{bulkStatus.current} / {bulkStatus.total}</span>
          </div>
          <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-purple-600 transition-all duration-300"
              style="width: {bulkStatus.total > 0 ? (bulkStatus.current / bulkStatus.total) * 100 : 0}%"
            ></div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Database Backups Section -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <h2 class="text-xl font-semibold text-white mb-4">📦 Database Backups</h2>
      <button
        on:click={createBackup}
        disabled={creatingBackup}
        class="mb-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white font-medium rounded-lg transition-colors"
      >
        {creatingBackup ? 'Creating...' : 'Create Manual Backup'}
      </button>

      {#if backups.length > 0}
        <div class="space-y-2 max-h-48 overflow-y-auto">
          {#each backups as backup}
            <div class="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-700">
              <div class="flex-1">
                <div class="text-sm text-white font-mono">{backup.filename}</div>
                <div class="text-xs text-slate-500">{backup.created} - {backup.size_mb} MB</div>
              </div>
              <div class="flex gap-2">
                <button on:click={() => downloadBackup(backup.filename)} class="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded">Download</button>
                <button on:click={() => deleteBackup(backup.filename)} class="px-2 py-1 bg-red-900/50 hover:bg-red-800 text-red-300 text-sm rounded">Delete</button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-slate-500">No backups found.</p>
      {/if}
    </div>

    <!-- Danger Zone -->
    <div class="bg-red-950/30 rounded-xl p-6 border border-red-900/50">
      <h2 class="text-xl font-semibold text-red-400 mb-4">Danger Zone</h2>
      <div class="p-4 bg-red-900/20 rounded-lg border border-red-800/50">
        <h3 class="text-sm font-semibold text-red-300 mb-2">Regenerate ALL Explanations</h3>
        <p class="text-xs text-red-300/60 mb-3">This will delete and regenerate ALL explanations.</p>
        <div class="flex gap-3 items-end">
          <div class="flex-1">
            <label class="block text-xs text-red-300/60 mb-1">
              Type <span class="font-mono font-bold text-red-400">{DANGER_CONFIRM_PHRASE}</span> to confirm
            </label>
            <input
              type="text"
              bind:value={dangerConfirmText}
              placeholder="Type here..."
              class="w-full px-3 py-2 bg-red-950/50 border border-red-800/50 rounded-lg text-white placeholder-red-300/30 focus:outline-none focus:border-red-600"
            />
          </div>
          <button
            on:click={regenerateAllExplanations}
            disabled={generatingBulk || dangerConfirmText !== DANGER_CONFIRM_PHRASE}
            class="px-4 py-2 bg-red-700 hover:bg-red-600 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors whitespace-nowrap"
          >
            Regenerate ALL
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Language Modal -->
{#if showLanguageModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/70 backdrop-blur-sm"
      on:click={closeLanguageModal}
      on:keydown={(e) => e.key === 'Escape' && closeLanguageModal()}
      role="button"
      tabindex="-1"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md mx-4 p-6 shadow-2xl">
      <h2 class="text-xl font-bold text-white mb-4">
        {editingLanguageCode ? 'Edit Language' : 'Add New Language'}
      </h2>

      <div class="space-y-4">
        <!-- Language Code -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            Language Code <span class="text-red-400">*</span>
          </label>
          <input
            type="text"
            bind:value={languageForm.code}
            placeholder="e.g., ko, zh, it"
            maxlength="5"
            disabled={editingLanguageCode !== null}
            class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500 disabled:opacity-50"
          />
          <p class="text-xs text-slate-500 mt-1">ISO 639-1 code (2 letters usually)</p>
        </div>

        <!-- Name -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            Name (English) <span class="text-red-400">*</span>
          </label>
          <input
            type="text"
            bind:value={languageForm.name}
            placeholder="e.g., Korean"
            class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
          />
        </div>

        <!-- Native Name -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            Native Name
          </label>
          <input
            type="text"
            bind:value={languageForm.native_name}
            placeholder="e.g., 한국어"
            class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
          />
        </div>

        <!-- Flag -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            Flag Emoji <span class="text-red-400">*</span>
          </label>
          <div class="flex gap-2">
            <input
              type="text"
              bind:value={languageForm.flag}
              placeholder="🇰🇷"
              maxlength="4"
              class="w-20 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-center text-2xl placeholder-slate-400 focus:outline-none focus:border-primary-500"
            />
            <div class="flex-1 flex flex-wrap gap-1">
              {#each commonFlags as flag}
                <button
                  type="button"
                  on:click={() => languageForm.flag = flag}
                  class="p-1.5 hover:bg-slate-600 rounded text-lg"
                >
                  {flag}
                </button>
              {/each}
            </div>
          </div>
        </div>

        <!-- TTS Voice -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            TTS Voice <span class="text-red-400">*</span>
          </label>
          <input
            type="text"
            bind:value={languageForm.tts_voice}
            placeholder="e.g., ko-KR-SunHiNeural"
            class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
          />
          {#if languageForm.code && getSuggestedVoices(languageForm.code).length > 0}
            <div class="mt-1 flex flex-wrap gap-1">
              {#each getSuggestedVoices(languageForm.code) as voice}
                <button
                  type="button"
                  on:click={() => languageForm.tts_voice = voice}
                  class="px-2 py-0.5 bg-slate-600 hover:bg-slate-500 rounded text-xs text-slate-300"
                >
                  {voice}
                </button>
              {/each}
            </div>
          {/if}
          <p class="text-xs text-slate-500 mt-1">
            <a href="https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support" target="_blank" class="text-primary-400 hover:underline">
              Find voice IDs here
            </a>
          </p>
        </div>

        <!-- Whisper Code -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">
            Whisper Code
          </label>
          <input
            type="text"
            bind:value={languageForm.whisper_code}
            placeholder="Same as language code if empty"
            class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
          />
          <p class="text-xs text-slate-500 mt-1">For transcription. Usually same as language code.</p>
        </div>
      </div>

      <!-- Buttons -->
      <div class="flex gap-3 mt-6">
        <button
          on:click={closeLanguageModal}
          class="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          on:click={saveLanguage}
          disabled={savingLanguage || !languageForm.code || !languageForm.name || !languageForm.flag || !languageForm.tts_voice}
          class="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors"
        >
          {savingLanguage ? 'Saving...' : (editingLanguageCode ? 'Update' : 'Add Language')}
        </button>
      </div>
    </div>
  </div>
{/if}
