import './SimulationView.css'

function SimulationView({ simResult, onDeploy, onBack, deploying }) {
    const steps = simResult?.steps || {}

    return (
        <div className="simulation-view">
            <div className="sim-header">
                <span className="sim-badge">✓ Simulation Passed</span>
                <span className="sim-target">{simResult.target_system}</span>
            </div>

            {/* Step-by-step breakdown */}
            <div className="sim-steps">
                <SimStep
                    number="1"
                    title="Incoming Payload"
                    data={steps['1_incoming_payload']}
                />
                <SimStep
                    number="2"
                    title="Transformation Rules"
                    data={steps['2_transformation_rules']}
                />
                <SimStep
                    number="3"
                    title="Transformed Payload (sent to API)"
                    data={steps['3_transformed_payload']}
                    highlight
                />
                <SimStep
                    number="4"
                    title="Target URL"
                    data={steps['4_target_url']}
                    isString
                />
                <SimStep
                    number="5"
                    title="API Response"
                    data={steps['6_api_response']}
                    highlight
                />
                <div className="sim-step">
                    <div className="step-num">6</div>
                    <div className="step-content">
                        <div className="step-title">Upstream Status</div>
                        <span className={`status-code ${steps['7_upstream_status'] === 200 ? 'ok' : 'err'}`}>
                            {steps['7_upstream_status']}
                        </span>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="sim-actions">
                <button className="btn btn-secondary" onClick={onBack}>
                    ← Back to Preview
                </button>
                <button
                    className="btn btn-deploy"
                    onClick={onDeploy}
                    disabled={deploying}
                >
                    {deploying ? '⏳ Deploying...' : '🚀 Deploy to Middleware'}
                </button>
            </div>
        </div>
    )
}

function SimStep({ number, title, data, highlight, isString }) {
    return (
        <div className={`sim-step ${highlight ? 'highlight' : ''}`}>
            <div className="step-num">{number}</div>
            <div className="step-content">
                <div className="step-title">{title}</div>
                <pre className="step-data">
                    {isString ? data : JSON.stringify(data, null, 2)}
                </pre>
            </div>
        </div>
    )
}

export default SimulationView
