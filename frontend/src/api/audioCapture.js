/**
 * Audio Recording and Processing Service for Vani 2.0 POC
 * 
 * Provides:
 * 1. Safe microphone permission handling and device queries.
 * 2. MediaRecorder capture for full-answer retention (used for single-recording comparison mode).
 * 3. AudioContext streaming with 16kHz PCM downsampler for realtime STT streaming.
 * 4. Sample rate and channel count inspection.
 */

// Helper to convert Float32 buffer to 16-bit linear PCM
export function floatTo16BitPCM(input) {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

// Resamples audio buffer from inputSampleRate to 16000 Hz using boxcar averaging
export function downsampleTo16k(buffer, sampleRate) {
  const targetRate = 16000;
  if (sampleRate === targetRate) {
    return buffer;
  }
  const ratio = sampleRate / targetRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

export class AudioCaptureService {
  constructor({ onAudioChunk, onStatusChange }) {
    this.onAudioChunk = onAudioChunk || (() => {});
    this.onStatusChange = onStatusChange || (() => {});
    this.mediaStream = null;
    this.audioContext = null;
    this.processorNode = null;
    this.mediaRecorder = null;
    this.recordedChunks = [];
    this.audioBlob = null;
    this.isRecording = false;
    this.audioMetadata = {
      rawSampleRate: null,
      resampledRate: 16000,
      channels: 1
    };
  }

  async checkPermission() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Browser does not support audio capture via MediaDevices API.");
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop tracks immediately after permission check
      stream.getTracks().forEach((t) => t.stop());
      return true;
    } catch (err) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        throw new Error("Microphone access was denied. Please allow microphone permissions in your browser settings.");
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        throw new Error("No microphone device was detected on your system.");
      }
      throw new Error(`Microphone error: ${err.message || err.name}`);
    }
  }

  async startRecording() {
    this.cleanup();
    this.recordedChunks = [];
    this.audioBlob = null;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });

      this.mediaStream = stream;

      // Track microphone stream specs
      const audioTrack = stream.getAudioTracks()[0];
      const settings = audioTrack ? audioTrack.getSettings() : {};
      this.audioMetadata.channels = settings.channelCount || 1;

      // Setup MediaRecorder to preserve original candidate audio for comparison mode
      let mimeType = "";
      if (typeof MediaRecorder !== "undefined") {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        }
        this.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        this.mediaRecorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            this.recordedChunks.push(event.data);
          }
        };
        this.mediaRecorder.start(250);
      }

      // Setup AudioContext for real-time 16kHz PCM streaming
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        try {
          this.audioContext = new AudioCtx({ sampleRate: 16000 });
        } catch {
          this.audioContext = new AudioCtx();
        }

        if (this.audioContext.state === "suspended") {
          await this.audioContext.resume();
        }

        this.audioMetadata.rawSampleRate = this.audioContext.sampleRate;
        const source = this.audioContext.createMediaStreamSource(stream);

        // ScriptProcessorNode provides cross-browser raw audio sample access
        const bufferSize = 4096;
        this.processorNode = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
        window._activeAudioProcessor = this.processorNode; // Prevent GC in V8/Blink

        this.processorNode.onaudioprocess = (e) => {
          if (!this.isRecording) return;
          const inputData = e.inputBuffer.getChannelData(0);
          const resampledFloat = downsampleTo16k(inputData, this.audioContext.sampleRate);
          const pcm16 = floatTo16BitPCM(resampledFloat);
          this.onAudioChunk(pcm16.buffer);
        };

        // Route through zero-gain node so Web Audio graph executes without feedback to speakers
        this.muteGainNode = this.audioContext.createGain();
        this.muteGainNode.gain.setValueAtTime(0, this.audioContext.currentTime);

        source.connect(this.processorNode);
        this.processorNode.connect(this.muteGainNode);
        this.muteGainNode.connect(this.audioContext.destination);
      }

      this.isRecording = true;
      this.onStatusChange({ state: "recording", metadata: this.audioMetadata });
      return this.audioMetadata;
    } catch (err) {
      this.cleanup();
      throw err;
    }
  }

  async stopRecording() {
    this.isRecording = false;

    // Finalize MediaRecorder to get complete candidate audio
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      await new Promise((resolve) => {
        this.mediaRecorder.onstop = () => {
          const type = this.mediaRecorder.mimeType || "audio/webm";
          this.audioBlob = new Blob(this.recordedChunks, { type });
          resolve();
        };
        try {
          this.mediaRecorder.stop();
        } catch {
          resolve();
        }
      });
    }

    this.cleanupNodes();
    this.onStatusChange({ state: "stopped", hasBlob: !!this.audioBlob });
    return this.audioBlob;
  }

  getRecordedBlob() {
    return this.audioBlob;
  }

  cleanupNodes() {
    if (this.processorNode) {
      try {
        this.processorNode.disconnect();
      } catch {}
      this.processorNode = null;
    }
    if (window._activeAudioProcessor) {
      window._activeAudioProcessor = null;
    }
    if (this.muteGainNode) {
      try {
        this.muteGainNode.disconnect();
      } catch {}
      this.muteGainNode = null;
    }
    if (this.audioContext) {
      try {
        this.audioContext.close();
      } catch {}
      this.audioContext = null;
    }
    if (this.mediaStream) {
      try {
        this.mediaStream.getTracks().forEach((t) => t.stop());
      } catch {}
      this.mediaStream = null;
    }
  }

  cleanup() {
    this.isRecording = false;
    this.cleanupNodes();
    this.mediaRecorder = null;
  }
}
