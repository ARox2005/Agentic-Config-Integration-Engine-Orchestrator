import { useState, useEffect } from 'react'
import SowInput from './components/SowInput'
import BlueprintPreview from './components/BlueprintPreview'
import SimulationView from './components/SimulationView'
import StatusBar from './components/StatusBar'
import AuditTrail from './components/AuditTrail'
import './App.css'

const API_BASE = import.meta.env.VITE_ORCHESTRATOR_API_BASE || 'http://localhost:8003/api/orchestrator'
const MIDDLEWARE_BASE = import.meta.env.VITE_MIDDLEWARE_API_BASE || 'http://localhost:8002/api/gateway'
const HEALTH_URL = import.meta.env.VITE_ORCHESTRATOR_HEALTH_URL || 'http://localhost:8003/health/ollama'
const MAIN_APP_URL = import.meta.env.VITE_MAIN_APP_URL || 'http://localhost:5173'

// Sample payloads for simulation (same as main-app)
const SAMPLE_PAYLOADS = {
  kyc_provider: {
    applicant_data: {
      firstName: 'John',
      lastName: 'Doe',
      dateOfBirth: '1990-05-15',
      panNumber: 'ABCDE1234F',
      aadhaarLast4: '5678',
    },
  },
  gst_service: {
    business_data: {
      gstin: '29ABCDE1234F1Z5',
      businessName: 'Acme Corp Pvt Ltd',
      panNumber: 'ABCDE1234F',
    },
  },
}

const TENANTS = [
  { id: 'default', label: 'Default Tenant' },
  { id: 'tenant_a', label: 'Tenant A — Acme Corp' },
  { id: 'tenant_b', label: 'Tenant B — Beta Finance' },
]

function App() {
  // Theme
  const [theme, setTheme] = useState(() => localStorage.getItem('orch-theme') || 'dark')
  const [showInstructions, setShowInstructions] = useState(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : '')
    localStorage.setItem('orch-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark')

  // Workflow state: "input" | "preview" | "simulate" | "deployed"
  const [step, setStep] = useState('input')
  const [showAudit, setShowAudit] = useState(false)

  // Tenant
  const [tenantId, setTenantId] = useState('default')

  // Data
  const [sowText, setSowText] = useState('')
  const [blueprint, setBlueprint] = useState(null)
  const [catalogEntry, setCatalogEntry] = useState(null)
  const [modelUsed, setModelUsed] = useState('')
  const [deployResult, setDeployResult] = useState(null)
  const [simResult, setSimResult] = useState(null)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [discoveryResult, setDiscoveryResult] = useState(null)

  // Edited versions from preview
  const [editedBlueprint, setEditedBlueprint] = useState(null)
  const [editedCatalog, setEditedCatalog] = useState(null)

  // UI state
  const [generating, setGenerating] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState(null)

  // Ollama + registry status
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [registryCount, setRegistryCount] = useState(0)

  useEffect(() => {
    fetchOllamaStatus()
    fetchRegistryCount()
  }, [])

  const fetchOllamaStatus = async () => {
    try {
      const res = await fetch(HEALTH_URL)
      const data = await res.json()
      setOllamaStatus(data)
    } catch {
      setOllamaStatus({ ollama_running: false, error: 'Orchestrator backend not reachable' })
    }
  }

  const fetchRegistryCount = async () => {
    try {
      const res = await fetch(`${API_BASE}/registry`)
      const data = await res.json()
      setRegistryCount(data.total)
    } catch {
      setRegistryCount(0)
    }
  }

  // ── Step 1: Generate ──
  const handleGenerate = async () => {
    const hasText = sowText.trim()
    const hasFiles = uploadedFiles.length > 0

    if (!hasText && !hasFiles) {
      setError('Please paste an SOW document or upload files.')
      return
    }
    setGenerating(true)
    setError(null)

    try {
      let res

      if (hasFiles) {
        // Use multipart upload endpoint
        const formData = new FormData()
        formData.append('sow_text', sowText)
        formData.append('tenant_id', tenantId)
        uploadedFiles.forEach((file) => formData.append('files', file))

        res = await fetch(`${API_BASE}/generate-from-upload`, {
          method: 'POST',
          body: formData,
        })
      } else {
        // Use JSON endpoint (text only)
        res = await fetch(`${API_BASE}/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sow_text: sowText, tenant_id: tenantId }),
        })
      }

      const data = await res.json()

      if (!res.ok) {
        const errDetail = data.detail
        setError(typeof errDetail === 'object' ? errDetail.error || JSON.stringify(errDetail) : errDetail)
        return
      }

      // Handle rejection
      if (data.status === 'rejected') {
        const rej = data.rejection
        setError(
          `⚠️ Integration Rejected: ${rej.reason}\n\n` +
          `Missing: ${(rej.missing_info || []).join(', ')}\n` +
          `Suggestion: ${rej.suggestion || 'N/A'}`
        )
        return
      }

      setBlueprint(data.blueprint)
      setCatalogEntry(data.catalog_entry)
      setModelUsed(data.model_used || '')
      if (data.discovery) {
        setDiscoveryResult(data.discovery)
      }
      setStep('preview')
    } catch (err) {
      setError(`Network error: ${err.message}`)
    } finally {
      setGenerating(false)
    }
  }

  // ── Step 2: Simulate ──
  const handleSimulate = async (bpToSim, catToSim) => {
    setEditedBlueprint(bpToSim)
    setEditedCatalog(catToSim)
    setSimulating(true)
    setError(null)

    // Guess a sample payload based on the target system name
    const systemName = (bpToSim.integration_metadata?.target_system || '').toLowerCase()
    let testPayload = SAMPLE_PAYLOADS.kyc_provider  // default
    if (systemName.includes('gst')) {
      testPayload = SAMPLE_PAYLOADS.gst_service
    }

    try {
      const res = await fetch(`${MIDDLEWARE_BASE}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: bpToSim,
          payload: testPayload,
        }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
        setSimulating(false)
        return
      }

      setSimResult(data)
      setStep('simulate')
    } catch (err) {
      setError(`Simulation failed: ${err.message}. Is the middleware running on port 8002?`)
    } finally {
      setSimulating(false)
    }
  }

  // ── Step 3: Deploy ──
  const handleDeploy = async () => {
    setDeploying(true)
    setError(null)

    const finalBlueprint = editedBlueprint || blueprint
    const finalCatalog = editedCatalog || catalogEntry

    try {
      const res = await fetch(`${API_BASE}/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          blueprint: finalBlueprint,
          catalog_entry: finalCatalog,
          tenant_id: tenantId,
        }),
      })
      const data = await res.json()

      if (!res.ok) {
        const errDetail = data.detail
        setError(typeof errDetail === 'object' ? JSON.stringify(errDetail) : errDetail)
        return
      }

      setDeployResult(data)
      setStep('deployed')
      fetchRegistryCount()
    } catch (err) {
      setError(`Network error: ${err.message}`)
    } finally {
      setDeploying(false)
    }
  }

  // ── Reset ──
  const handleReset = () => {
    setStep('input')
    setSowText('')
    setUploadedFiles([])
    setBlueprint(null)
    setCatalogEntry(null)
    setEditedBlueprint(null)
    setEditedCatalog(null)
    setDeployResult(null)
    setSimResult(null)
    setError(null)
    setDiscoveryResult(null)
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">ZeroOne AI Orchestrator</h1>
          <p className="app-subtitle">
            Upload SOW → Generate → Simulate → Deploy
          </p>
          <StatusBar ollamaStatus={ollamaStatus} registryCount={registryCount} />
        </div>
        <div className="header-actions">
          <a
            href={MAIN_APP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="main-app-link"
            title="Open Main App"
          >
            Main App ↗
          </a>
          <button
            className="help-btn"
            onClick={() => setShowInstructions(true)}
            title="How to use"
          >
            ?
          </button>
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      {/* Tenant Selector + Audit Toggle */}
      <div className="toolbar">
        <div className="tenant-selector">
          <label htmlFor="tenant-select">🏢 Tenant:</label>
          <select
            id="tenant-select"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
          >
            {TENANTS.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
        </div>
        <button
          className={`btn btn-sm ${showAudit ? 'btn-active' : ''}`}
          onClick={() => setShowAudit(!showAudit)}
        >
          📋 {showAudit ? 'Hide' : 'Show'} Audit Trail
        </button>
      </div>

      {/* Audit Trail Panel */}
      {showAudit && <AuditTrail apiBase={API_BASE} />}

      {/* Step Indicator */}
      <div className="step-indicator">
        {['input', 'preview', 'simulate', 'deployed'].map((s, i) => {
          const labels = ['Input', 'Preview', 'Simulate', 'Deployed']
          const stepOrder = ['input', 'preview', 'simulate', 'deployed']
          const currentIdx = stepOrder.indexOf(step)
          const thisIdx = i
          let cls = ''
          if (thisIdx === currentIdx) cls = 'active'
          else if (thisIdx < currentIdx) cls = 'done'
          return (
            <div key={s} style={{ display: 'flex', alignItems: 'center', flex: i < 3 ? 1 : undefined }}>
              <div className={`step-dot ${cls}`}>
                <span>{i + 1}</span> {labels[i]}
              </div>
              {i < 3 && <div className="step-line" />}
            </div>
          )
        })}
      </div>
      {error && <div className="error-banner">{error}</div>}
      {/* Step 1: Input */}
      {step === 'input' && (
        <SowInput
          sowText={sowText}
          onChange={setSowText}
          onGenerate={handleGenerate}
          loading={generating}
          files={uploadedFiles}
          onFilesChange={setUploadedFiles}
        />
      )}
      {/* Step 2: Preview */}
      {step === 'preview' && (
        <BlueprintPreview
          blueprint={blueprint}
          catalogEntry={catalogEntry}
          modelUsed={modelUsed}
          onSimulate={handleSimulate}
          onBack={() => setStep('input')}
          simulating={simulating}
          discovery={discoveryResult}
        />
      )}
      {/* Step 3: Simulate */}
      {step === 'simulate' && simResult && (
        <SimulationView
          simResult={simResult}
          onDeploy={handleDeploy}
          onBack={() => setStep('preview')}
          deploying={deploying}
        />
      )}
      {/* Step 4: Deployed */}
      {step === 'deployed' && deployResult && (
        <div className="deploy-success">
          <div className="success-icon">✓</div>
          <h2>Deployment Complete</h2>
          <div className="deploy-details">
            <div className="detail-row">
              <span className="detail-label">Tenant</span>
              <span className="detail-value mono">{deployResult.tenant_id || tenantId}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Config</span>
              <span className="detail-value success">
                {deployResult.config_deployment?.message}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Registry</span>
              <span className="detail-value success">
                {deployResult.registry_update?.message}
              </span>
            </div>
            {deployResult.config_deployment?.path && (
              <div className="detail-row">
                <span className="detail-label">File</span>
                <span className="detail-value mono">
                  {deployResult.config_deployment.path}
                </span>
              </div>
            )}
          </div>
          <button className="btn btn-primary" onClick={handleReset}>
            ← New Integration
          </button>
        </div>
      )}

      {/* Instructions Modal */}
      {showInstructions && (
        <div className="modal-overlay" onClick={() => setShowInstructions(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowInstructions(false)}>✕</button>
            <h2>How to Use the Orchestrator</h2>
            <h3>Step 1 — Input</h3>
            <ol>
              <li>Select a <strong>Tenant</strong> from the toolbar dropdown.</li>
              <li>Paste an SOW document into the text area, or drag-and-drop files into the upload zone.</li>
              <li>Click <strong>Generate</strong> to produce a blueprint.</li>
            </ol>
            <h3>Step 2 — Preview</h3>
            <ol>
              <li>Review the generated <strong>Blueprint</strong> and <strong>Catalog Entry</strong> JSON.</li>
              <li>You can edit the JSON directly in the editor.</li>
              <li>Click <strong>Simulate</strong> to test the integration.</li>
            </ol>
            <h3>Step 3 — Simulate</h3>
            <ol>
              <li>Review the step-by-step simulation output.</li>
              <li>Check the HTTP status code and response data.</li>
              <li>If satisfied, click <strong>Deploy</strong>.</li>
            </ol>
            <h3>Step 4 — Deploy</h3>
            <p>
              The blueprint is saved to the middleware config directory and registered in the catalog.
              Click <strong>New Integration</strong> to start over.
            </p>
            <h3>Other Features</h3>
            <ol>
              <li><strong>Audit Trail</strong> — Click "Show Audit Trail" in the toolbar to view all past actions.</li>
              <li><strong>Theme</strong> — Use the ☀️/🌙 button to toggle between dark and light mode.</li>
            </ol>
          </div>
        </div>
      )}

    </div>
  )
}
export default App
