<script lang="ts">
  import { currentView, stats, activeLanguage } from '../lib/stores';

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'study', label: 'Study', icon: '📖' },
    { id: 'dictionary', label: 'Dictionary', icon: '📚' },
    { id: 'practice', label: 'Practice', icon: '🎯' },
    { id: 'chat', label: 'AI Tutor', icon: '💬' },
    { id: 'recordings', label: 'Recordings', icon: '🎙️' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ] as const;
</script>

<aside class="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
  <!-- Logo & Language -->
  <div class="p-6 border-b border-slate-700">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-white">👂 Ears</h1>
      {#if $activeLanguage}
        <button
          class="text-2xl hover:scale-110 transition-transform"
          title="Learning {$activeLanguage.name} - Click to change"
          on:click={() => currentView.set('settings')}
        >
          {$activeLanguage.flag}
        </button>
      {/if}
    </div>
    <p class="text-sm text-slate-400 mt-1">
      {#if $activeLanguage}
        Learning {$activeLanguage.name}
      {:else}
        Learn from what you hear
      {/if}
    </p>
  </div>

  <!-- Navigation -->
  <nav class="flex-1 p-4 space-y-2">
    {#each navItems as item}
      <button
        class="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors
               {$currentView === item.id
                 ? 'bg-primary-600 text-white'
                 : 'text-slate-300 hover:bg-slate-700'}"
        on:click={() => currentView.set(item.id)}
      >
        <span class="text-xl">{item.icon}</span>
        <span class="font-medium">{item.label}</span>
      </button>
    {/each}
  </nav>

  <!-- Stats summary -->
  {#if $stats}
    <div class="p-4 border-t border-slate-700">
      <div class="text-sm text-slate-400 mb-2">Your Progress</div>
      <div class="grid grid-cols-3 gap-2 text-center">
        <div>
          <div class="text-lg font-bold text-slate-400">{$stats.undiscovered}</div>
          <div class="text-xs text-slate-500">New</div>
        </div>
        <div>
          <div class="text-lg font-bold text-yellow-400">{$stats.learning}</div>
          <div class="text-xs text-slate-500">Learning</div>
        </div>
        <div>
          <div class="text-lg font-bold text-green-400">{$stats.known}</div>
          <div class="text-xs text-slate-500">Known</div>
        </div>
      </div>
    </div>
  {/if}
</aside>
