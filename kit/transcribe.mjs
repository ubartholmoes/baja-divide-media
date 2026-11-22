// node transcribe.mjs AUDIO OUT.json [language]   (language e.g. english, german; omit = auto)
import { pipeline, env } from '@huggingface/transformers';
import fs from 'fs'; import { execFileSync } from 'child_process';
const kit = new URL('.', import.meta.url).pathname;
env.allowRemoteModels = false; env.localModelPath = kit + 'model/package/models/';
const raw = execFileSync('ffmpeg', ['-v', 'error', '-i', process.argv[2], '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], { maxBuffer: 1 << 30 });
const audio = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const asr = await pipeline('automatic-speech-recognition', 'Xenova/whisper-small', { dtype: 'q8' });
const out = await asr(audio, { language: process.argv[4] || null, task: 'transcribe', return_timestamps: 'word', chunk_length_s: 30, stride_length_s: 5 });
fs.writeFileSync(process.argv[3], JSON.stringify(out, null, 1));
console.log(out.text);
