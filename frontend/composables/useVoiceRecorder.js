import { ref, onBeforeUnmount } from 'vue'

/** Bounded recording, no upload and no persistent browser storage. */
export function useVoiceRecorder() {
  const recording = ref(false)
  const seconds = ref(0)
  const audio = ref(null)
  const audioUrl = ref('')
  let recorder, stream, timer, stopTimer, disposed = false, generation = 0

  function release() {
    clearInterval(timer)
    clearTimeout(stopTimer)
    const currentStream = stream
    stream = null
    currentStream?.getTracks().forEach((track) => track.stop())
  }
  function clear() {
    generation++
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audio.value = null
    audioUrl.value = ''
    seconds.value = 0
  }
  function stop() {
    if (recorder?.state === 'recording') recorder.stop()
    recording.value = false
    release()
  }
  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('unsupported')
    clear()
    const token = generation
    const acquired = await navigator.mediaDevices.getUserMedia({ audio: true })
    if (disposed || token !== generation) { acquired.getTracks().forEach((track) => track.stop()); return }
    stream = acquired
    try {
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4'].find((type) => MediaRecorder.isTypeSupported(type))
      if (!mimeType) throw new Error('unsupported')
      recorder = new MediaRecorder(stream, { mimeType })
      const chunks = []
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = () => {
        release()
        if (disposed || token !== generation) return
        audio.value = new Blob(chunks, { type: mimeType })
        audioUrl.value = URL.createObjectURL(audio.value)
      }
      recorder.onerror = () => { recording.value = false; release() }
      recorder.start()
      recording.value = true
      const began = Date.now()
      timer = setInterval(() => { seconds.value = Math.min(60, Math.floor((Date.now() - began) / 1000)) }, 250)
      stopTimer = setTimeout(() => { seconds.value = 60; stop() }, 60000)
    } catch (error) { release(); throw error }
  }
  onBeforeUnmount(() => { disposed = true; stop(); clear() })
  return { recording, seconds, audio, audioUrl, start, stop, clear }
}
