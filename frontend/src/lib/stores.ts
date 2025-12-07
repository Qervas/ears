/**
 * Svelte stores for app state
 */

import { writable, derived } from 'svelte/store';
import type { Word, Stats, Language, ActiveLanguage } from './api';

// Persistent writable store (saves to localStorage)
function persistentWritable<T>(key: string, initialValue: T) {
  // Check if running in browser
  const isBrowser = typeof window !== 'undefined';

  // Load from localStorage if available
  const stored = isBrowser ? localStorage.getItem(key) : null;
  const data = stored ? JSON.parse(stored) : initialValue;

  const store = writable<T>(data);

  // Save to localStorage on changes (only in browser)
  if (isBrowser) {
    store.subscribe(value => {
      localStorage.setItem(key, JSON.stringify(value));
    });
  }

  return store;
}

// Current view/page (persisted across refreshes)
export const currentView = persistentWritable<'dashboard' | 'dictionary' | 'study' | 'practice' | 'chat' | 'recordings' | 'settings'>('currentView', 'dashboard');

// Word to open in Study page (for navigation from search)
export const selectedStudyWord = writable<Word | null>(null);

// Vocabulary state
export const vocabulary = writable<Word[]>([]);
export const vocabularyTotal = writable(0);
export const vocabularyLoading = writable(false);
export const vocabularyFilter = writable<string | null>(null);

// Stats
export const stats = writable<Stats | null>(null);

// Selected word for detail view (Dictionary page)
export const selectedWord = writable<Word | null>(null);

// Global word modal (can be opened from anywhere)
export const wordModal = writable<Word | null>(null);

// Active language
export const activeLanguage = writable<ActiveLanguage | null>(null);

// Learning session
export const learningWords = writable<Word[]>([]);
export const currentLearningIndex = writable(0);

// Derived stores
export const currentLearningWord = derived(
  [learningWords, currentLearningIndex],
  ([$words, $index]) => $words[$index] ?? null
);

export const learningProgress = derived(
  [currentLearningIndex, learningWords],
  ([$index, $words]) => ({
    current: $index + 1,
    total: $words.length,
    percent: $words.length > 0 ? Math.round((($index + 1) / $words.length) * 100) : 0,
  })
);
