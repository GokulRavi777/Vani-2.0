/**
 * WebSocket STT Client Module for Vani 2.0 POC
 * 
 * Provides:
 * - Real-time connection management to backend STT WebSocket.
 * - Binding to assessment_id and question_id to prevent transcript leakage across questions.
 * - Handles partial and final transcript frames.
 * - Preserves binary audio chunk delivery with queue safety.
 * - Clean teardown on unmount or question transition.
 */

export class STTWebSocketClient {
  constructor({ url, assessmentId, questionId, provider = "google", onPartial, onFinal, onError, onClose }) {
    this.url = url;
    this.assessmentId = assessmentId;
    this.questionId = questionId;
    this.provider = provider;
    this.onPartial = onPartial || (() => {});
    this.onFinal = onFinal || (() => {});
    this.onError = onError || (() => {});
    this.onClose = onClose || (() => {});

    this.socket = null;
    this.isConnected = false;
    this.isClosed = false;
    this.sendQueue = [];
    this.firstPartialTime = null;
    this.finalTime = null;
    this.startTime = null;
  }

  connect() {
    this.isClosed = false;
    this.startTime = Date.now();
    try {
      this.socket = new WebSocket(this.url);
      this.socket.binaryType = "arraybuffer";

      this.socket.onopen = () => {
        if (this.isClosed) {
          this.close();
          return;
        }
        this.isConnected = true;
        // Flush any queued audio buffers
        while (this.sendQueue.length > 0 && this.socket.readyState === WebSocket.OPEN) {
          const chunk = this.sendQueue.shift();
          this.socket.send(chunk);
        }
      };

      this.socket.onmessage = (event) => {
        if (this.isClosed) return;
        try {
          const data = JSON.parse(event.data);

          // Check if message belongs to current assessment/question scope
          if (data.question_id && data.question_id !== this.questionId) {
            return;
          }

          if (data.type === "partial" || data.type === "partial_transcript") {
            if (!this.firstPartialTime) {
              this.firstPartialTime = Date.now();
            }
            const text = data.transcript || data.text || "";
            const latency = this.firstPartialTime - this.startTime;
            this.onPartial(text, { latencyMs: latency });
          } else if (data.type === "partial_final" || data.type === "final" || data.type === "done_stt") {
            this.finalTime = Date.now();
            const text = data.transcript || data.transcript_original || data.text || "";
            const latency = this.finalTime - this.startTime;
            this.onFinal(text, { latencyMs: latency });
          } else if (data.type === "error") {
            this.onError(data.message || data.error || "STT provider error occurred");
          }
        } catch {
          // If non-JSON text arrives
          if (typeof event.data === "string") {
            this.onPartial(event.data, { latencyMs: Date.now() - this.startTime });
          }
        }
      };

      this.socket.onerror = (event) => {
        if (this.isClosed) return;
        this.onError(`WebSocket connection error to ${this.provider} endpoint.`);
      };

      this.socket.onclose = (event) => {
        this.isConnected = false;
        if (!this.isClosed) {
          this.onClose(event);
        }
      };
    } catch (err) {
      this.onError(`Failed to create WebSocket: ${err.message}`);
    }
  }

  sendAudioChunk(buffer) {
    if (this.isClosed) return;

    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(buffer);
    } else if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
      // Buffer up to 100 chunks while connecting so audio is not silently discarded
      if (this.sendQueue.length < 100) {
        this.sendQueue.push(buffer);
      }
    }
  }

  /**
   * Send a text "stop" command to the backend.
   * This signals end of audio stream so Sarvam flushes final transcripts.
   * Call this when recording stops — wait a few seconds before calling close().
   */
  sendStop() {
    if (this.isClosed) return;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send("stop");
    }
  }

  close() {
    this.isClosed = true;
    this.isConnected = false;
    this.sendQueue = [];
    if (this.socket) {
      try {
        this.socket.onopen = null;
        this.socket.onmessage = null;
        this.socket.onerror = null;
        this.socket.onclose = null;
        if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
          this.socket.close();
        }
      } catch {}
      this.socket = null;
    }
  }
}
