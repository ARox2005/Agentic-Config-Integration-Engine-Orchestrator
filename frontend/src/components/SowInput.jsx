import { useState, useRef } from 'react'
import './SowInput.css'

const SAMPLE_SOW = `Integration SOW: KYC Provider

Business Rule:
When a loan application is submitted, the system must verify the applicant's identity by sending their full name (first + last), date of birth, PAN number, and last 4 digits of Aadhaar to the KYC Provider. If kyc_verified is false, the loan must be rejected.

API Details:
- Service Name: KYC Provider
- Version: v1.0
- Endpoint: http://localhost:8004/mock-kyc/verify
- Method: POST
- Expected Request Fields: full_name, date_of_birth, pan_number, aadhaar_last4
- Expected Response Fields: status, kyc_verified, identity_score, name_match, verification_id

Security:
- Auth Type: Bearer
- Credential Vault Reference: ENV.KYC_PROVIDER_KEY

Source Data Mapping:
- full_name comes from: $.applicant_data.firstName + ' ' + $.applicant_data.lastName
- date_of_birth comes from: $.applicant_data.dateOfBirth
- pan_number comes from: $.applicant_data.panNumber
- aadhaar_last4 comes from: $.applicant_data.aadhaarLast4`

const ACCEPTED_TYPES = '.pdf,.doc,.docx,.txt,.md,.csv'

function SowInput({ sowText, onChange, onGenerate, loading, files, onFilesChange }) {
    const [dragActive, setDragActive] = useState(false)
    const fileInputRef = useRef(null)

    const handleLoadSample = () => {
        onChange(SAMPLE_SOW)
    }

    const handleFiles = (fileList) => {
        const newFiles = Array.from(fileList)
        onFilesChange([...(files || []), ...newFiles])
    }

    const handleDrop = (e) => {
        e.preventDefault()
        setDragActive(false)
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files)
        }
    }

    const handleDragOver = (e) => {
        e.preventDefault()
        setDragActive(true)
    }

    const handleDragLeave = () => {
        setDragActive(false)
    }

    const handleFileInput = (e) => {
        if (e.target.files.length) {
            handleFiles(e.target.files)
        }
        e.target.value = ''  // Reset so same file can be added again
    }

    const removeFile = (index) => {
        const updated = [...files]
        updated.splice(index, 1)
        onFilesChange(updated)
    }

    const formatSize = (bytes) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const hasContent = sowText.trim() || (files && files.length > 0)

    return (
        <div className="sow-input">
            {/* Text Input */}
            <div className="sow-header">
                <label className="sow-label">SOW Document Text</label>
                <button className="btn-link" onClick={handleLoadSample}>
                    Load sample SOW
                </button>
            </div>

            <textarea
                className="sow-textarea"
                value={sowText}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Paste your SOW document text here..."
                rows={12}
                spellCheck={false}
            />

            {/* File Upload */}
            <div className="upload-section">
                <label className="sow-label">Or Upload Documents</label>
                <div
                    className={`drop-zone ${dragActive ? 'drag-active' : ''}`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <span className="drop-icon">📄</span>
                    <span className="drop-text">
                        Drop PDF, DOCX, or TXT files here — or click to browse
                    </span>
                    <span className="drop-hint">Multiple files supported</span>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept={ACCEPTED_TYPES}
                        multiple
                        onChange={handleFileInput}
                        style={{ display: 'none' }}
                    />
                </div>
            </div>

            {/* File List */}
            {files && files.length > 0 && (
                <div className="file-list">
                    {files.map((file, i) => (
                        <div key={i} className="file-chip">
                            <span className="file-ext">{file.name.split('.').pop().toUpperCase()}</span>
                            <span className="file-name">{file.name}</span>
                            <span className="file-size">{formatSize(file.size)}</span>
                            <button className="file-remove" onClick={() => removeFile(i)}>✕</button>
                        </div>
                    ))}
                </div>
            )}

            {/* Footer */}
            <div className="sow-footer">
                <span className="char-count">
                    {sowText.length} chars{files && files.length > 0 ? ` + ${files.length} file${files.length > 1 ? 's' : ''}` : ''}
                </span>
                <button
                    className="btn btn-primary"
                    onClick={onGenerate}
                    disabled={loading || !hasContent}
                >
                    {loading ? '⏳ Generating...' : '→ Generate Blueprint'}
                </button>
            </div>
        </div>
    )
}

export default SowInput
