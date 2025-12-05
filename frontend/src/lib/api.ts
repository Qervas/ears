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
  status: 'learning' | 'known';
  first_seen: string;
  last_seen: string;
  explanation?: string;
  explanation_json?: string;  // JSON string containing structured explanation
  contexts?: string[];
  example?: string;  // Example sentence from context
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

export interface ListeningSegment {
  text: string;
  start: number;
  end: number;
  recording: string;
  audio_url: string;
}

export interface ListeningQuizResponse {
  segments: ListeningSegment[];
}

export async function getListeningQuiz(count = 10): Promise<ListeningQuizResponse> {
  return request(`/learn/listening-quiz?count=${count}`);
}

export interface GrammarQuestion {
  word: string;
  type: string;
  sentence: string;
  options: string[];
  correct_index: number;
  explanation: string;
  real_examples: string[];
}

export interface GrammarQuizResponse {
  questions: GrammarQuestion[];
}

export async function getGrammarQuiz(count = 10): Promise<GrammarQuizResponse> {
  return request(`/learn/grammar-quiz?count=${count}`);
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

export async function getWordsWithoutExplanations(): Promise<{ words: string[] }> {
  return request('/vocabulary/words-without-explanations');
}

export async function generateSingleExplanation(word: string): Promise<{ success: boolean; word: string; error?: string }> {
  return request(`/vocabulary/generate-explanation/${encodeURIComponent(word)}`, {
    method: 'POST',
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
  language: 'sv' | 'en';
}

export interface TranscriptStats {
  total: number;
  swedish: number;
  english: number;
}

export interface TranscriptsResponse {
  transcripts: Transcript[];
  total: number;
  stats: TranscriptStats;
}

export async function getTranscripts(limit = 50, offset = 0, language?: string): Promise<TranscriptsResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (language) params.set('language', language);
  return request(`/transcripts?${params}`);
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

export interface TranscriptSegment {
  text: string;
  language: 'sv' | 'en';
  start: number | null;
  end: number | null;
}

export interface RecordingTranscript {
  full_text: string;
  duration: number | null;
  segments: TranscriptSegment[];
  stats: {
    total: number;
    swedish: number;
    english: number;
  };
}

export async function getRecordingTranscript(filename: string): Promise<RecordingTranscript> {
  return request(`/recordings/${encodeURIComponent(filename)}/transcript`);
}

export function getRecordingAudioUrl(filename: string): string {
  return `${API_BASE}/recordings/${encodeURIComponent(filename)}/audio`;
}

export async function transcribeFile(filepath: string): Promise<void> {
  await request('/transcribe', {
    method: 'POST',
    body: JSON.stringify({ filepath }),
  });
}

// ============== Recording Control ==============

export interface AudioDevice {
  id: number;
  name: string;
  sample_rate: number;
  channels: number;
}

export async function getAudioDevices(): Promise<{ devices: AudioDevice[] }> {
  return request('/audio-devices');
}

export interface RecordingStatus {
  recording: boolean;
  device_id: number | null;
  start_time: string | null;
}

export async function getRecordingStatus(): Promise<RecordingStatus> {
  return request('/recording/status');
}

export async function startRecording(device_id: number): Promise<{ status: string; device_id: number }> {
  return request('/recording/start', {
    method: 'POST',
    body: JSON.stringify({ device_id }),
  });
}

export async function stopRecording(): Promise<{ status: string; filepath: string }> {
  return request('/recording/stop', {
    method: 'POST',
  });
}

export async function rebuildVocabulary(): Promise<{ status: string }> {
  return request('/vocabulary/rebuild', {
    method: 'POST',
  });
}
