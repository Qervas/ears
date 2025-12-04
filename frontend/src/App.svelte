<script lang="ts">
  import { onMount } from 'svelte';
  import { currentView, stats } from './lib/stores';
  import { getStats } from './lib/api';
  import Dashboard from './components/Dashboard.svelte';
  import Vocabulary from './components/Vocabulary.svelte';
  import Learn from './components/Learn.svelte';
  import Chat from './components/Chat.svelte';
  import Recordings from './components/Recordings.svelte';
  import Sidebar from './components/Sidebar.svelte';

  onMount(async () => {
    try {
      const data = await getStats();
      stats.set(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  });
</script>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto">
    {#if $currentView === 'dashboard'}
      <Dashboard />
    {:else if $currentView === 'vocabulary'}
      <Vocabulary />
    {:else if $currentView === 'learn'}
      <Learn />
    {:else if $currentView === 'chat'}
      <Chat />
    {:else if $currentView === 'recordings'}
      <Recordings />
    {/if}
  </main>
</div>
