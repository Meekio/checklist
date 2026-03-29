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

function StatusBadge({ status }) {
  const cls = status === 'Correct' ? 'badge correct' : status === 'Incorrect' ? 'badge incorrect' : 'badge error'
  return <span className={cls}>{status}</span>
}

export default function App() {
  const [pdf, setPdf] = useState(null)
  const [rules, setRules] = useState(null)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const reset = () => {
    setPdf(null)
    setRules(null)
    setResults(null)
    setError(null)
  }

  const runQC = async () => {
    if (!pdf || !rules) return
    setLoading(true)
    setError(null)
    setResults(null)

    const form = new FormData()
    form.append('drawing', pdf)
    form.append('rules', rules)

    try {
      const res = await fetch('http://localhost:8000/run-qc', { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      setResults(data.results)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const correct = results?.filter(r => r.status === 'Correct').length ?? 0
  const incorrect = results?.filter(r => r.status === 'Incorrect').length ?? 0
  const errors = results?.filter(r => r.status === 'Error').length ?? 0

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

        {results && (
          <div className="results">
            <div className="summary">
              <span className="badge correct">{correct} Correct</span>
              <span className="badge incorrect">{incorrect} Incorrect</span>
              {errors > 0 && <span className="badge error">{errors} Error</span>}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>QC Rule</th>
                    <th>Status</th>
                    <th>Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => (
                    <tr key={i} className={r.status?.toLowerCase()}>
                      <td>{i + 1}</td>
                      <td className="rule-cell">{r.rule}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td className="remarks-cell">{r.remarks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
