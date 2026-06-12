import { useState, useRef } from 'react'
import './App.css'

function FileInput({ label, accept, file, onChange }) {
  const ref = useRef()
  return (
    <div className="field">
      <label>{label}</label>
      <div className="file-row" onClick={() => ref.current.click()}>
        <button type="button" className="choose-btn" tabIndex={-1}>Choose file</button>
        <span className="file-name">{file ? file.name : 'No file chosen'}</span>
        <input
          ref={ref}
          type="file"
          accept={accept}
          style={{ display: 'none' }}
          onChange={e => onChange(e.target.files[0] || null)}
        />
      </div>
    </div>
  )
}

export default function App() {
  const [pdf, setPdf] = useState(null)
  const [rules, setRules] = useState(null)
  const [loading, setLoading] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [filename, setFilename] = useState(null)
  const [error, setError] = useState(null)

  const reset = () => {
    setPdf(null)
    setRules(null)
    setDownloadUrl(null)
    setFilename(null)
    setError(null)
  }

  const runQC = async () => {
    if (!pdf || !rules) return
    setLoading(true)
    setError(null)
    setDownloadUrl(null)

    const form = new FormData()
    form.append('drawing', pdf)
    form.append('rules', rules)

    try {
      const res = await fetch('http://localhost:8001/run-qc', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `Server error: ${res.status}` }))
        throw new Error(err.detail || `Server error: ${res.status}`)
      }
      const blob = await res.blob()
      const fname = res.headers.get('x-filename') || 'qc_results.xlsx'
      setDownloadUrl(URL.createObjectURL(blob))
      setFilename(fname)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="card">
        <h1>Engineering Drawing QC</h1>
        <p className="subtitle">Upload your drawing and rules to run the checklist.</p>

        <FileInput label="Drawing (PDF)" accept=".pdf" file={pdf} onChange={setPdf} />
        <FileInput label="Rules Excel" accept=".xlsx,.xls" file={rules} onChange={setRules} />

        {error && <div className="error-msg">{error}</div>}

        <div className="actions">
          <button className="reset-btn" onClick={reset} disabled={loading}>Reset</button>
          <button
            className="run-btn"
            onClick={runQC}
            disabled={!pdf || !rules || loading}
          >
            {loading ? <span className="spinner" /> : null}
            {loading ? 'Running…' : 'Run QC'}
          </button>
        </div>

        {downloadUrl && (
          <div className="download-wrap">
            <svg className="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="done-text">QC complete</span>
            <a className="download-btn" href={downloadUrl} download={filename}>
              ↓ Download Report
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
