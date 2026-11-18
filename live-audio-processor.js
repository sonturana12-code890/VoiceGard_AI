'use strict';

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SAMPLE_COUNT = 3200;

class VoiceGuardPcmCaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.phase = 0;
        this.accumulator = 0;
        this.accumulatorCount = 0;
        this.chunk = new Int16Array(CHUNK_SAMPLE_COUNT);
        this.chunkIndex = 0;
    }

    process(inputs, outputs) {
        const input = inputs[0] && inputs[0][0];
        const output = outputs[0] && outputs[0][0];
        if (output) output.fill(0);
        if (!input) return true;

        for (let i = 0; i < input.length; i++) {
            this.accumulator += input[i];
            this.accumulatorCount += 1;
            this.phase += TARGET_SAMPLE_RATE;

            if (this.phase >= sampleRate) {
                this.phase -= sampleRate;
                const sample = Math.max(-1, Math.min(1, this.accumulator / this.accumulatorCount));
                this.accumulator = 0;
                this.accumulatorCount = 0;
                this.chunk[this.chunkIndex] = sample < 0 ? sample * 32768 : sample * 32767;
                this.chunkIndex += 1;

                if (this.chunkIndex === CHUNK_SAMPLE_COUNT) {
                    const pcm = new ArrayBuffer(CHUNK_SAMPLE_COUNT * 2);
                    const view = new DataView(pcm);
                    for (let sampleIndex = 0; sampleIndex < CHUNK_SAMPLE_COUNT; sampleIndex++) {
                        view.setInt16(sampleIndex * 2, this.chunk[sampleIndex], true);
                    }
                    this.port.postMessage({ type: 'pcm', buffer: pcm }, [pcm]);
                    this.chunkIndex = 0;
                }
            }
        }

        return true;
    }
}

registerProcessor('voiceguard-pcm-capture', VoiceGuardPcmCaptureProcessor);
