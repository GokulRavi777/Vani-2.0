/**
 * WAV Audio Encoding Utility for Vani 2.0
 * 
 * Converts raw audio buffers or browser-recorded WebM/Opus blobs into
 * standard 16-bit linear PCM WAV format required by Gnani AI Speech APIs.
 */

/**
 * Encodes an AudioBuffer into a 16-bit Linear PCM WAV Blob.
 * 
 * @param {AudioBuffer} audioBuffer - Decoded audio buffer
 * @param {number} targetSampleRate - Desired output sample rate (default 16000 Hz)
 * @returns {Blob} Standard audio/wav Blob
 */
export function encodeAudioBufferToWav(audioBuffer, targetSampleRate = 16000) {
  const numChannels = 1; // Downmix to mono for voice cloning
  const sampleRate = targetSampleRate || audioBuffer.sampleRate;
  const format = 1; // Linear PCM
  const bitDepth = 16;

  // Mix down multi-channel audio to mono
  let monoSamples;
  if (audioBuffer.numberOfChannels === 1) {
    monoSamples = audioBuffer.getChannelData(0);
  } else {
    const ch0 = audioBuffer.getChannelData(0);
    const ch1 = audioBuffer.getChannelData(1);
    monoSamples = new Float32Array(ch0.length);
    for (let i = 0; i < ch0.length; i++) {
      monoSamples[i] = (ch0[i] + ch1[i]) / 2;
    }
  }

  // Resample to targetSampleRate if necessary
  let resampled = monoSamples;
  if (audioBuffer.sampleRate !== sampleRate) {
    const ratio = audioBuffer.sampleRate / sampleRate;
    const newLength = Math.round(monoSamples.length / ratio);
    resampled = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const srcIdx = i * ratio;
      const idx0 = Math.floor(srcIdx);
      const idx1 = Math.min(idx0 + 1, monoSamples.length - 1);
      const frac = srcIdx - idx0;
      resampled[i] = monoSamples[idx0] * (1 - frac) + monoSamples[idx1] * frac;
    }
  }

  const bytesPerSample = bitDepth / 8;
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = resampled.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  // RIFF chunk descriptor
  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");

  // "fmt " sub-chunk
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // 16 for PCM
  view.setUint16(20, format, true); // 1 for PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);

  // "data" sub-chunk
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  // Write 16-bit signed PCM audio samples
  let offset = 44;
  for (let i = 0; i < resampled.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, resampled[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

/**
 * Converts any audio Blob (WebM, MP3, AAC, OGG, WAV) into a standard 16kHz PCM WAV Blob
 * using the browser's native AudioContext.
 * 
 * @param {Blob|File} audioBlob - Raw audio blob or file
 * @returns {Promise<Blob>} Standard audio/wav Blob
 */
export async function convertBlobToWav(audioBlob) {
  if (!audioBlob) return null;

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) {
    return audioBlob; // Return original if AudioContext unavailable
  }

  const audioContext = new AudioCtx();
  try {
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    const wavBlob = encodeAudioBufferToWav(audioBuffer, 16000);
    return wavBlob;
  } finally {
    try {
      await audioContext.close();
    } catch {}
  }
}
