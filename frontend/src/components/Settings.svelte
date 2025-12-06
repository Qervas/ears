<script lang="ts">
  import { onMount } from 'svelte';

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

  const freeModels = [
    'grok-code-fast-1',
    'gpt-4o',
    'gpt-4.1',
    'gpt-5-mini',
    'raptor-mini'
  ];

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

    // Load backups list
    await loadBackups();
  });

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
        alert(`✓ Connection successful!\n\nProvider: ${data.provider}\nModel: ${data.model || 'N/A'}\nResponse: ${data.response}`);
      } else {
        console.error('Connection error details:', data);
        alert(`✗ Connection failed\n\nError: ${data.error}\n\nCheck the browser console for more details.`);
      }
    } catch (e) {
      console.error('Connection test error:', e);
      alert(`✗ Connection test failed\n\nError: ${e}\n\nMake sure the backend server is running.`);
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
        alert(`✓ Backup created successfully!\n\nFile: ${data.path}`);
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
</script>

<div class="h-full overflow-auto p-8 bg-slate-900">
  <div class="max-w-3xl mx-auto">
    <h1 class="text-3xl font-bold text-white mb-8">Settings</h1>

    <!-- AI Provider Selection -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <h2 class="text-xl font-semibold text-white mb-4">AI Provider</h2>

      <div class="space-y-4">
        <!-- Provider Selection -->
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
          <p class="text-xs text-slate-500 mt-1">
            Choose the AI service for explanations and chat
          </p>
        </div>

        <!-- LM Studio Settings -->
        {#if aiProvider === 'lm-studio'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700">
            <h3 class="text-sm font-semibold text-white mb-3">LM Studio Configuration</h3>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                API Base URL
              </label>
              <input
                type="text"
                bind:value={lmStudioUrl}
                placeholder="http://localhost:1234/v1"
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
              <p class="text-xs text-slate-500 mt-1">
                Make sure LM Studio is running with local server enabled
              </p>
            </div>
          </div>
        {/if}

        <!-- Copilot API Settings -->
        {#if aiProvider === 'copilot-api'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700 space-y-4">
            <h3 class="text-sm font-semibold text-white mb-3">GitHub Copilot API Configuration</h3>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                API Base URL
              </label>
              <input
                type="text"
                bind:value={copilotApiUrl}
                placeholder="http://localhost:4141"
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
              <p class="text-xs text-slate-500 mt-1">
                Using <a href="https://github.com/ericc-ch/copilot-api" target="_blank" class="text-primary-400 hover:underline">copilot-api</a> proxy server
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Model
              </label>
              <select
                bind:value={copilotModel}
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-primary-500"
              >
                <optgroup label="Free Models (Recommended)">
                  <option value="grok-code-fast-1">grok-code-fast-1 (Fast & Free)</option>
                  <option value="gpt-4o-mini">gpt-4o-mini (Fast & Free)</option>
                  <option value="gpt-4.1">gpt-4.1 (Free)</option>
                  <option value="gpt-5-mini">gpt-5-mini (Free)</option>
                </optgroup>
                <optgroup label="Premium Models">
                  <option value="claude-sonnet-4.5">Claude Sonnet 4.5</option>
                  <option value="claude-opus-4.5">Claude Opus 4.5</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-5">GPT-5</option>
                </optgroup>
              </select>
              <p class="text-xs text-slate-500 mt-1">
                Free models are recommended for language learning
              </p>
            </div>
          </div>
        {/if}

        <!-- OpenAI Settings -->
        {#if aiProvider === 'openai'}
          <div class="p-4 bg-slate-900/50 rounded-lg border border-slate-700">
            <h3 class="text-sm font-semibold text-white mb-3">OpenAI Configuration</h3>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                API Key
              </label>
              <input
                type="password"
                bind:value={openaiApiKey}
                placeholder="sk-..."
                class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-primary-500"
              />
              <p class="text-xs text-slate-500 mt-1">
                Your OpenAI API key (stored locally)
              </p>
            </div>
          </div>
        {/if}

        <!-- Action Buttons -->
        <div class="flex gap-3 pt-4">
          <button
            on:click={saveSettings}
            disabled={saving}
            class="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors"
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

    <!-- Database Backups Section -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
      <h2 class="text-xl font-semibold text-white mb-4">📦 Database Backups</h2>

      <p class="text-sm text-slate-400 mb-4">
        Automatic backups are created on startup and after bulk generation. You can also create manual backups anytime.
      </p>

      <button
        on:click={createBackup}
        disabled={creatingBackup}
        class="mb-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors"
      >
        {creatingBackup ? 'Creating...' : '💾 Create Manual Backup'}
      </button>

      {#if backups.length > 0}
        <div class="space-y-2">
          <h3 class="text-sm font-semibold text-slate-300">Available Backups ({backups.length})</h3>
          <div class="max-h-64 overflow-y-auto space-y-2">
            {#each backups as backup}
              <div class="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-700">
                <div class="flex-1">
                  <div class="text-sm text-white font-mono">{backup.filename}</div>
                  <div class="text-xs text-slate-500">
                    {backup.created} • {backup.size_mb} MB
                  </div>
                </div>
                <button
                  on:click={() => downloadBackup(backup.filename)}
                  class="ml-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded transition-colors"
                >
                  ⬇ Download
                </button>
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <p class="text-sm text-slate-500">No backups found. Create one to get started!</p>
      {/if}
    </div>

    <!-- Info Section -->
    <div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
      <h2 class="text-xl font-semibold text-white mb-4">About AI Providers</h2>

      <div class="space-y-3 text-sm text-slate-300">
        <div>
          <strong class="text-white">LM Studio:</strong> Run AI models locally on your computer. Free and private.
        </div>
        <div>
          <strong class="text-white">GitHub Copilot API:</strong> Use GitHub Copilot's models via a proxy. Requires GitHub Copilot subscription.
        </div>
        <div>
          <strong class="text-white">OpenAI API:</strong> Use OpenAI's GPT models. Requires API key and costs per use.
        </div>
      </div>
    </div>
  </div>
</div>
