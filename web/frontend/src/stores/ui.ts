import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, put } from '../api'

export type ParticleDensity = 'off' | 'low' | 'medium' | 'high'

export const useUiStore = defineStore('ui', () => {
  const particles = ref<ParticleDensity>(
    (localStorage.getItem('ui.particles') as ParticleDensity) || 'medium')
  const tilt3d = ref(localStorage.getItem('ui.tilt3d') !== 'false')
  const autoSpeak = ref(false)
  const loaded = ref(false)

  async function loadRemote() {
    if (loaded.value) return
    try {
      const cfg = await get('/system/config')
      if (cfg?.ui?.particles) particles.value = cfg.ui.particles
      if (cfg?.ui?.tilt3d !== undefined) tilt3d.value = !!cfg.ui.tilt3d
      if (cfg?.tts?.auto_speak !== undefined) autoSpeak.value = !!cfg.tts.auto_speak
      loaded.value = true
    } catch { /* 未登录时静默 */ }
  }

  function setParticles(v: ParticleDensity) {
    particles.value = v
    localStorage.setItem('ui.particles', v)
    put('/system/config', { path: 'ui.particles', value: v }).catch(() => {})
  }

  function setTilt3d(v: boolean) {
    tilt3d.value = v
    localStorage.setItem('ui.tilt3d', String(v))
    put('/system/config', { path: 'ui.tilt3d', value: v }).catch(() => {})
  }

  async function setAutoSpeak(v: boolean) {
    autoSpeak.value = v
    await put('/media/tts/config', { auto_speak: v })
  }

  return { particles, tilt3d, autoSpeak, loadRemote, setParticles, setTilt3d, setAutoSpeak }
})
