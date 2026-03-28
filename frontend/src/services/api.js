import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
})

// Attach auth token to every request automatically
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('viotrack-token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Robust helper to get full absolute URL for static images from backend
export const getImageUrl = (path) => {
    if (!path) return null;
    if (path.startsWith('http') || path.startsWith('data:')) return path;
    const hostname = window.location.hostname;
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `http://${hostname}:8000${cleanPath}`;
}

// Auth
export const loginUser = (credentials) => api.post('/auth/login', credentials)
export const registerUser = (userData) => api.post('/auth/register', userData)
export const getCurrentUser = (token) =>
    api.get('/auth/me', { headers: { Authorization: `Bearer ${token}` } })

// Dashboard
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getRepeatOffenders = (minViolations = 2) =>
    api.get(`/dashboard/repeat-offenders?min_violations=${minViolations}`)
export const getQuickSummary = () => api.get('/dashboard/summary')

// Videos
export const uploadVideo = (file, onProgress, shift = null, sendEmail = false, mailTo = null) => {
    const formData = new FormData()
    formData.append('file', file)
    if (shift) {
        formData.append('shift', shift)
    }
    if (sendEmail) {
        formData.append('send_email', 'true')
        if (mailTo) {
            formData.append('mail_to', mailTo)
        }
    }

    return api.post('/videos/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress?.(progress)
        },
    })
}

export const getVideos = (page = 1, pageSize = 10, status = null) => {
    let url = `/videos?page=${page}&page_size=${pageSize}`
    if (status) url += `&status=${status}`
    return api.get(url)
}

export const getVideo = (videoId) => api.get(`/videos/${videoId}`)
export const getVideoStatus = (videoId) => api.get(`/videos/${videoId}/status`)
export const deleteVideo = (videoId) => api.delete(`/videos/${videoId}`)
export const markVideoReviewed = (videoId) => api.put(`/videos/${videoId}/review`)
export const unmarkVideoReviewed = (videoId) => api.put(`/videos/${videoId}/unreview`)

// Violations
export const getViolations = (params = {}) => {
    const query = new URLSearchParams()
    if (params.page) query.set('page', params.page)
    if (params.pageSize) query.set('page_size', params.pageSize)
    if (params.videoId) query.set('video_id', params.videoId)
    if (params.individualId) query.set('individual_id', params.individualId)
    if (params.violationType) query.set('violation_type', params.violationType)
    if (params.reviewStatus) query.set('review_status', params.reviewStatus)
    if (params.minConfidence) query.set('min_confidence', params.minConfidence)
    if (params.startDate) query.set('start_date', params.startDate)
    if (params.endDate) query.set('end_date', params.endDate)

    return api.get(`/violations?${query.toString()}`)
}

export const getViolation = (violationId) => api.get(`/violations/${violationId}`)

export const reviewViolation = (violationId, isConfirmed, notes = null) =>
    api.post(`/violations/${violationId}/review`, { is_confirmed: isConfirmed, notes })

export const bulkReviewViolations = (violationIds, isConfirmed, notes = null) =>
    api.post('/violations/bulk-review', {
        violation_ids: violationIds,
        is_confirmed: isConfirmed,
        notes
    })

export const getViolationTypes = () => api.get('/violations/types/list')

// Individuals
export const getIndividuals = (videoId) => api.get(`/individuals/${videoId}`)
export const getIndividual = (videoId, trackId) => api.get(`/individuals/${videoId}/${trackId}`)
export const analyzeIndividual = (videoId, trackId) =>
    api.get(`/individuals/${videoId}/${trackId}/analysis`)
export const toggleFine = (videoId, trackId, isFined) => 
    api.put(`/individuals/${videoId}/${trackId}/fine`, { is_fined: isFined })

// Search
export const searchVideos = (date, shift = null, violationType = null) => {
    const params = new URLSearchParams()
    if (date) params.set('date_str', date)
    if (shift) params.set('shift', shift)
    if (violationType) params.set('violation_type', violationType)
    return api.get(`/search/videos?${params.toString()}`)
}

export const getVideoSummary = (videoId) => api.get(`/search/videos/${videoId}/summary`)

export const getAvailableDates = () => api.get('/search/dates')

// Webcam
export const saveWebcamSession = (sessionData) => api.post('/webcam/save-session', sessionData)

// Live Stream
export const stopLiveStream = () => api.post('/stream/stop')

// Employees
export const getEmployees = () => api.get('/employees')
export const getEmployee = (employeeId) => api.get(`/employees/${employeeId}`)
export const createEmployee = (name, photoFile, email, phone, department, role) => {
    const formData = new FormData()
    formData.append('name', name)
    if (photoFile) formData.append('photo', photoFile)
    if (email) formData.append('email', email)
    if (phone) formData.append('phone', phone)
    if (department) formData.append('department', department)
    if (role) formData.append('role', role)
    return api.post('/employees', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
}
export const updateEmployee = (employeeId, name, photoFile, email, phone, department, role) => {
    const formData = new FormData()
    if (name) formData.append('name', name)
    if (photoFile) formData.append('photo', photoFile)
    if (email) formData.append('email', email)
    if (phone) formData.append('phone', phone)
    if (department) formData.append('department', department)
    if (role) formData.append('role', role)
    return api.put(`/employees/${employeeId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
}
export const deleteEmployee = (employeeId) => api.delete(`/employees/${employeeId}`)
export const createEmployeeFromSnapshot = (name, snapshotPath) => {
    const formData = new FormData()
    formData.append('name', name)
    formData.append('snapshot_path', snapshotPath)
    return api.post('/employees/from-snapshot', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
}

export default api
