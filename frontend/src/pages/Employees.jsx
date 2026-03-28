import { useState, useEffect, useRef } from 'react'
import { Users, UserPlus, Pencil, Trash2, Upload, Camera, X, Check, AlertCircle, Search } from 'lucide-react'
import { getEmployees, createEmployee, updateEmployee, deleteEmployee, createEmployeeFromSnapshot, getImageUrl } from '../services/api'

function Employees() {
    const [employees, setEmployees] = useState([])
    const [loading, setLoading] = useState(true)
    const [showAddModal, setShowAddModal] = useState(false)
    const [editingEmployee, setEditingEmployee] = useState(null)
    const [searchQuery, setSearchQuery] = useState('')

    useEffect(() => {
        fetchEmployees()
    }, [])

    const fetchEmployees = async () => {
        try {
            setLoading(true)
            const res = await getEmployees()
            setEmployees(res.data.employees || [])
        } catch (err) {
            console.error('Failed to fetch employees:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async (emp) => {
        if (!confirm(`Delete employee "${emp.name}"? This cannot be undone.`)) return
        try {
            await deleteEmployee(emp.id)
            fetchEmployees()
        } catch (err) {
            console.error('Failed to delete:', err)
            alert('Failed to delete employee')
        }
    }

    const filteredEmployees = employees.filter(emp =>
        emp.name.toLowerCase().includes(searchQuery.toLowerCase())
    )

    return (
        <div className="employees-page">
            <div className="employees-header">
                <div className="employees-title-section">
                    <Users size={28} />
                    <h1>Employee Database</h1>
                    <span className="employee-count">{employees.length} employees</span>
                </div>
                <div className="employees-actions-bar">
                    <div className="employees-search">
                        <Search size={16} />
                        <input
                            type="text"
                            placeholder="Search employees..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
                        <UserPlus size={16} />
                        Add Employee
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="employees-loading">
                    <div className="spinner" />
                    <p>Loading employee database...</p>
                </div>
            ) : filteredEmployees.length === 0 ? (
                <div className="employees-empty">
                    <Users size={64} strokeWidth={1} />
                    <h3>{employees.length === 0 ? 'No Employees Yet' : 'No Matches Found'}</h3>
                    <p>{employees.length === 0
                        ? 'Add employees with their photos to enable face recognition during monitoring.'
                        : 'Try a different search query.'
                    }</p>
                    {employees.length === 0 && (
                        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
                            <UserPlus size={16} /> Add First Employee
                        </button>
                    )}
                </div>
            ) : (
                <div className="employees-grid">
                    {filteredEmployees.map(emp => (
                        <EmployeeCard
                            key={emp.id}
                            employee={emp}
                            onEdit={() => setEditingEmployee(emp)}
                            onDelete={() => handleDelete(emp)}
                        />
                    ))}
                </div>
            )}

            {(showAddModal || editingEmployee) && (
                <EmployeeModal
                    employee={editingEmployee}
                    onClose={() => { setShowAddModal(false); setEditingEmployee(null) }}
                    onSave={() => { setShowAddModal(false); setEditingEmployee(null); fetchEmployees() }}
                />
            )}
        </div>
    )
}


function EmployeeCard({ employee, onEdit, onDelete }) {
    const photoUrl = employee.photo_path ? getImageUrl(employee.photo_path) : null

    return (
        <div className="employee-card">
            <div className="employee-card-photo">
                {photoUrl ? (
                    <img src={photoUrl} alt={employee.name} />
                ) : (
                    <div className="employee-card-avatar">
                        <Users size={40} strokeWidth={1.5} />
                    </div>
                )}
            </div>
            <div className="employee-card-info">
                <h3>{employee.name}</h3>
                <span className="employee-card-id">ID: {employee.id}</span>
                {employee.created_at && (
                    <span className="employee-card-date">
                        Added {new Date(employee.created_at).toLocaleDateString()}
                    </span>
                )}
            </div>
            <div className="employee-card-actions">
                <button className="btn btn-ghost btn-sm" onClick={onEdit} title="Edit">
                    <Pencil size={14} />
                </button>
                <button className="btn btn-ghost btn-sm btn-danger" onClick={onDelete} title="Delete">
                    <Trash2 size={14} />
                </button>
            </div>
        </div>
    )
}


function EmployeeModal({ employee, onClose, onSave }) {
    const [name, setName] = useState(employee?.name || '')
    const [photoFile, setPhotoFile] = useState(null)
    const [photoPreview, setPhotoPreview] = useState(employee?.photo_path ? getImageUrl(employee.photo_path) : null)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)
    const fileInputRef = useRef(null)
    const isEdit = !!employee

    const handlePhotoChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setPhotoFile(file)
            setPhotoPreview(URL.createObjectURL(file))
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!name.trim()) {
            setError('Name is required')
            return
        }
        setSaving(true)
        setError(null)

        try {
            if (isEdit) {
                await updateEmployee(employee.id, name.trim(), photoFile)
            } else {
                await createEmployee(name.trim(), photoFile)
            }
            onSave()
        } catch (err) {
            console.error('Save failed:', err)
            setError(err.response?.data?.detail || 'Failed to save employee')
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content employee-modal" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>{isEdit ? 'Edit Employee' : 'Add New Employee'}</h2>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}>
                        <X size={18} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="employee-modal-photo-section">
                        <div
                            className="employee-modal-photo-preview"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            {photoPreview ? (
                                <img src={photoPreview} alt="Preview" />
                            ) : (
                                <div className="employee-modal-photo-placeholder">
                                    <Camera size={32} />
                                    <span>Click to upload photo</span>
                                </div>
                            )}
                        </div>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            onChange={handlePhotoChange}
                            style={{ display: 'none' }}
                        />
                        <p className="employee-modal-photo-hint">
                            Upload a clear, front-facing photo for best face recognition accuracy.
                        </p>
                    </div>

                    <div className="form-group">
                        <label htmlFor="emp-name">Employee Name</label>
                        <input
                            id="emp-name"
                            type="text"
                            className="form-input"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="Enter full name..."
                            autoFocus
                        />
                    </div>

                    {error && (
                        <div className="form-error">
                            <AlertCircle size={14} /> {error}
                        </div>
                    )}

                    <div className="modal-actions">
                        <button type="button" className="btn btn-ghost" onClick={onClose}>
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary" disabled={saving}>
                            {saving ? 'Saving...' : (
                                <><Check size={16} /> {isEdit ? 'Update' : 'Add Employee'}</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}


/**
 * Reusable modal for naming unknown persons detected during processing.
 * Used in Webcam, LiveStream, and VideoDetail pages.
 */
export function NamePersonModal({ snapshotPath, trackId, onClose, onSave }) {
    const [name, setName] = useState('')
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!name.trim()) {
            setError('Name is required')
            return
        }
        setSaving(true)
        setError(null)

        try {
            await createEmployeeFromSnapshot(name.trim(), snapshotPath)
            onSave(name.trim())
        } catch (err) {
            console.error('Failed to create employee:', err)
            setError(err.response?.data?.detail || 'Failed to save employee')
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content name-person-modal" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>Name This Person</h2>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}>
                        <X size={18} />
                    </button>
                </div>

                <div className="name-person-snapshot">
                    {snapshotPath ? (
                        <img src={getImageUrl(snapshotPath)} alt={`Unknown Person ${trackId}`} />
                    ) : (
                        <div className="name-person-no-photo">
                            <Users size={48} />
                            <span>Unknown-{trackId}</span>
                        </div>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="person-name">Enter employee name</label>
                        <input
                            id="person-name"
                            type="text"
                            className="form-input"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="Full name..."
                            autoFocus
                        />
                    </div>

                    {error && (
                        <div className="form-error">
                            <AlertCircle size={14} /> {error}
                        </div>
                    )}

                    <div className="modal-actions">
                        <button type="button" className="btn btn-ghost" onClick={onClose}>
                            Skip
                        </button>
                        <button type="submit" className="btn btn-primary" disabled={saving}>
                            {saving ? 'Saving...' : <><Check size={16} /> Save Employee</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default Employees
