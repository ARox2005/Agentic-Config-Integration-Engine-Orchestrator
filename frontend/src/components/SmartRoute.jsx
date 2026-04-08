import { useState } from 'react'
import './SmartRoute.css'

const SAMPLE_PAYLOADS = {
    kyc: {
        applicant_data: {
            firstName: 'John',
            lastName: 'Doe',
            dateOfBirth: '1990-05-15',
            panNumber: 'ABCDE1234F',
            aadhaarLast4: '5678',
        },
    },
    gst: {
        business_data: {
            gstin: '29ABCDE1234F1Z5',
            businessName: 'Acme Corp Pvt Ltd',
            panNumber: 'ABCDE1234F',
        },
    },
}

const API_BASE = 'http://localhost:8003/api/orchestrator'

function SmartRoute() {
    const [payloadText, setPayloadText] = useState('')
    const [intent, setIntent] = useState('')
    const [autoExecute, setAutoExecute] = useState(false)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleLoadSample = (type) => {
        setPayloadText(JSON.stringify(SAMPLE_PAYLOADS[type], null, 2))
    }

    const handleRoute = async () => {
        setLoading(true)
        setError(null)
        setResult(null)

        let parsedPayload
        try {
            parsedPayload = JSON.parse(payloadText)
        } catch {
            setError('Invalid JSON payload.')
            setLoading(false)
            return
        }

        try {
            const res = await fetch(`${API_BASE}/route`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    payload: parsedPayload,
                    intent: intent || undefined,
                    auto_execute: autoExecute,
                }),
            })
            const data = await res.json()

            if (!res.ok) {
                setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
                return
            }

            setResult(data)
        } catch (err) {
            setError(`Network error: ${err.message}`)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="smart-route">
            <div className="sr-section">
                <div className="sr-header">
                    <label className="sr-label">Raw Payload</label>
                    <div className="sr-samples">
                        <button className="btn-link" onClick={() => handleLoadSample('kyc')}>KYC sample</button>
                        <button className="btn-link" onClick={() => handleLoadSample('gst')}>GST sample</button>
                    </div>
                </div>
                <textarea
                    className="sr-textarea"
                    value={payloadText}
                    onChange={(e) => setPayloadText(e.target.value)}
                    placeholder='{"applicant_data": {"firstName": "John", ...}}'
                    rows={10}
                    spellCheck={false}
                />
            </div>

            <div className="sr-section">
                <label className="sr-label">Intent (optional)</label>
                <input
                    className="sr-input"
                    type="text"
                    value={intent}
                    onChange={(e) => setIntent(e.target.value)}
                    placeholder='e.g. "verify this customer identity" or leave blank'
                />
            </div>

            <div className="sr-footer">
                <label className="sr-toggle">
                    <input
                        type="checkbox"
                        checked={autoExecute}
                        onChange={(e) => setAutoExecute(e.target.checked)}
                    />
                    <span>Auto-execute via middleware</span>
                </label>
                <button
                    className="btn btn-primary"
                    onClick={handleRoute}
                    disabled={loading || !payloadText.trim()}
                >
                    {loading ? '⏳ Routing...' : '🧠 Route with AI'}
                </button>
            </div>

            {error && <div className="error-banner">{error}</div>}

            {/* Results */}
            {result && (
                <div className="sr-result">
                    {/* Status badge */}
                    <div className={`sr-status ${result.status}`}>
                        {result.status === 'routed' && '✓ Adapter Found'}
                        {result.status === 'executed' && '✓ Routed & Executed'}
                        {result.status === 'no_match' && '✗ No Match'}
                    </div>

                    {/* Selected adapters */}
                    {result.routing?.selected_adapters?.length > 0 && (
                        <div className="sr-adapters">
                            {result.routing.selected_adapters.map((a, i) => (
                                <div key={i} className="sr-adapter-card">
                                    <div className="sr-adapter-name">{a.adapter_name}</div>
                                    <div className="sr-adapter-confidence">
                                        <div
                                            className="confidence-bar"
                                            style={{ width: `${(a.confidence * 100).toFixed(0)}%` }}
                                        />
                                        <span>{(a.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="sr-adapter-reason">{a.reason}</div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* No match reason */}
                    {result.status === 'no_match' && (
                        <div className="sr-no-match">{result.message}</div>
                    )}

                    {/* Execution result */}
                    {result.execution && (
                        <div className="sr-execution">
                            <div className="sr-exec-header">
                                Executed via: <strong>{result.execution.adapter_used}</strong>
                                <span className={`status-code ${result.execution.middleware_status === 200 ? 'ok' : 'err'}`}>
                                    {result.execution.middleware_status}
                                </span>
                            </div>
                            <pre className="sr-exec-data">
                                {JSON.stringify(result.execution.middleware_response, null, 2)}
                            </pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default SmartRoute
