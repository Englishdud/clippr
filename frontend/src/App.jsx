import { useState, useEffect } from 'react'

function Logo() {
  return (
    <div className="text-center">
      <h1 className="text-4xl font-black tracking-tight">
        <span className="text-white">Clippr</span>
        <span className="text-violet-400">.ai</span>
      </h1>
      <p className="mt-1 text-sm text-zinc-500">Paste a link. Get a vertical clip.</p>
    </div>
  )
}

function UrlInput({ url, setUrl, onSubmit, disabled }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !disabled) onSubmit()
  }

  return (
    <div className="space-y-3">
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="https://youtube.com/watch?v=..."
        disabled={disabled}
        className="w-full rounded-xl bg-zinc-800 border border-zinc-700 px-4 py-3 text-white placeholder-zinc-500 focus:border-violet-500 focus:outline-none transition-colors disabled:opacity-50"
      />
      <button
        onClick={onSubmit}
        disabled={disabled || !url.trim()}
        className="w-full rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white font-semibold py-3 transition-colors"
      >
        Generate Clip
      </button>
    </div>
  )
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-8 w-8 text-violet-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

function ProgressIndicator({ message }) {
  return (
    <div className="flex flex-col items-center gap-4 py-4">
      <Spinner />
      <p className="text-zinc-400 text-sm">{message}</p>
    </div>
  )
}

function DownloadPanel({ resultUrl, title, onReset }) {
  return (
    <div className="flex flex-col items-center gap-4 py-2">
      <div className="flex items-center gap-2 text-emerald-400">
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span className="font-semibold">Clip ready!</span>
      </div>
      {title != null && (
        <div className="w-full rounded-xl bg-zinc-800 border border-zinc-700 px-4 py-3 text-center">
          <p className="text-xs text-zinc-500 uppercase tracking-widest mb-1">Suggested title</p>
          <p className="text-white font-semibold text-sm leading-snug">{title}</p>
        </div>
      )}
      <a
        href={resultUrl}
        download
        className="w-full text-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 transition-colors"
      >
        Download Clip
      </a>
      <button
        onClick={onReset}
        className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        Create another clip
      </button>
    </div>
  )
}

function ErrorPanel({ message, onReset }) {
  return (
    <div className="space-y-3">
      <div className="rounded-xl bg-red-950 border border-red-800 px-4 py-3">
        <p className="text-red-400 text-sm">{message}</p>
      </div>
      <button
        onClick={onReset}
        className="w-full rounded-xl bg-zinc-700 hover:bg-zinc-600 text-white font-semibold py-3 transition-colors"
      >
        Try again
      </button>
    </div>
  )
}

export default function App() {
  const [appState, setAppState] = useState('idle')
  const [url, setUrl] = useState('')
  const [jobId, setJobId] = useState(null)
  const [statusMessage, setStatusMessage] = useState('')
  const [resultUrl, setResultUrl] = useState(null)
  const [clipTitle, setClipTitle] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    if (appState !== 'processing' || !jobId) return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`)
        const data = await res.json()
        setStatusMessage(data.message)

        if (data.status === 'done') {
          setResultUrl(data.result_url)
          setClipTitle(data.title)
          setAppState('done')
          clearInterval(interval)
        } else if (data.status === 'error') {
          setErrorMessage(data.error || data.message)
          setAppState('error')
          clearInterval(interval)
        }
      } catch {
        // Network error — keep polling
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [appState, jobId])

  const handleSubmit = async () => {
    if (!url.trim()) return
    setAppState('processing')
    setStatusMessage('Starting...')
    setErrorMessage('')

    try {
      const res = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      setJobId(data.job_id)
    } catch (e) {
      setErrorMessage(e.message || 'Failed to start processing')
      setAppState('error')
    }
  }

  const handleReset = () => {
    setAppState('idle')
    setUrl('')
    setJobId(null)
    setStatusMessage('')
    setResultUrl(null)
    setClipTitle('')
    setErrorMessage('')
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-zinc-900 rounded-2xl border border-zinc-800 p-8 space-y-6">
        <Logo />

        {(appState === 'idle') && (
          <UrlInput url={url} setUrl={setUrl} onSubmit={handleSubmit} disabled={false} />
        )}

        {appState === 'processing' && (
          <ProgressIndicator message={statusMessage} />
        )}

        {appState === 'done' && (
          <DownloadPanel resultUrl={resultUrl} title={clipTitle} onReset={handleReset} />
        )}

        {appState === 'error' && (
          <>
            <ErrorPanel message={errorMessage} onReset={handleReset} />
            <UrlInput url={url} setUrl={setUrl} onSubmit={handleSubmit} disabled={false} />
          </>
        )}
      </div>
    </div>
  )
}
