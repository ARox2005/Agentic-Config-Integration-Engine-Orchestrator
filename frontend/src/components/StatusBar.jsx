import './StatusBar.css'

function StatusBar({ ollamaStatus, registryCount }) {
    const ollamaOk = ollamaStatus?.ollama_running && ollamaStatus?.model_available

    return (
        <div className="status-bar">
            <div className={`status-chip ${ollamaOk ? 'ok' : 'error'}`}>
                <span className="status-dot" />
                {ollamaOk
                    ? `Ollama: ${ollamaStatus.configured_model}`
                    : 'Ollama: offline'}
            </div>
            <div className="status-chip neutral">
                Registry: {registryCount} adapter{registryCount !== 1 ? 's' : ''}
            </div>
        </div>
    )
}

export default StatusBar
