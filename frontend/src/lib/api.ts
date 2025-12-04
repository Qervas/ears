/**
 * API client for Ears backend
 */

const API_BASE = 'http://localhost:8000/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

// ============== Vocabulary ==============

export interface Word {
  id: number;
  word: string;
  frequency: number;
  status: 'new' | 'learning' | 'known' | 'ignored';
  first_seen: string;
  last_seen: string;
  explanation?: string;
  contexts?: string[];
}

export interface VocabularyResponse {
  words: Word[];
  total: number;
}

export async function getVocabulary(
  limit = 100,
  offset = 0,
  status?: string,
  sort = 'frequency'
): Promise<VocabularyResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset), sort });
  if (status) params.set('status', status);
  return request(`/vocabulary?${params}`);
}

export async function getWord(word: string): Promise<Word> {
  return request(`/vocabulary/${encodeURIComponent(word)}`);
}

export async function updateWordStatus(word: string, status: string): Promise<void> {
  await request(`/vocabulary/${encodeURIComponent(word)}/status`, {
    method: 'PUT',
    body: JSON.stringify({ word, status }),
  });
}

// ============== Stats ==============

export interface Stats {
  total_words: number;
  new: number;
  learning: number;
  known: number;
  total_occurrences: number;
}

export async function getStats(): Promise<Stats> {
  return request('/vocabulary/stats');
}

export interface Progress {
  total_words: number;
  known: number;
  learning: number;
  new: number;
  progress_percent: number;
}

export async function getProgress(): Promise<Progress> {
  return request('/learn/progress');
}

// ============== Learning ==============

export interface LearningSession {
  mode: string;
  words?: Word[];
  sentences?: { raw_text: string; cleaned_text: string }[];
}

export async function getLearningSession(mode = 'vocabulary', count = 10): Promise<LearningSession> {
  return request(`/learn/session?mode=${mode}&count=${count}`);
}

// ============== TTS ==============

export function getTTSUrl(text: string, voice = 'sv-SE-SofieNeural'): string {
  return `${API_BASE}/tts/${encodeURIComponent(text)}?voice=${voice}`;
}

export async function playTTS(text: string): Promise<void> {
  const audio = new Audio(getTTSUrl(text));
  await audio.play();
}

// ============== AI ==============

export interface ExplanationResponse {
  explanation: string;
}

export async function explainWord(word: string, context = ''): Promise<ExplanationResponse> {
  return request('/explain', {
    method: 'POST',
    body: JSON.stringify({ word, context }),
  });
}

export interface ChatResponse {
  response: string;
}

export async function chat(message: string, context = ''): Promise<ChatResponse> {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, context }),
  });
}

// ============== Transcripts ==============

export interface Transcript {
  id: number;
  timestamp: string;
  raw_text: string;
  cleaned_text: string | null;
  confidence: number;
  duration_seconds: number;
}

export interface TranscriptsResponse {
  transcripts: Transcript[];
  total: number;
}

export async function getTranscripts(limit = 50, offset = 0): Promise<TranscriptsResponse> {
  return request(`/transcripts?limit=${limit}&offset=${offset}`);
}

// ============== Recordings ==============

export interface Recording {
  name: string;
  path: string;
  size_mb: number;
  has_transcript: boolean;
}

export async function getRecordings(): Promise<{ recordings: Recording[] }> {
  return request('/recordings');
}

export async function transcribeFile(filepath: string): Promise<void> {
  await request('/transcribe', {
    method: 'POST',
    body: JSON.stringify({ filepath }),
  });
}
